#!/usr/bin/env python3
"""一次 OpenAI 相容呼叫；函式庫本身不讀寫檔案。"""
import json
import os
import socket
import time
import urllib.error
import urllib.request


def _usage(raw):
    usage = raw if isinstance(raw, dict) else {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "prompt": usage.get("prompt_tokens"),
        "completion": usage.get("completion_tokens"),
        "total": usage.get("total_tokens"),
        "cached": prompt_details.get("cached_tokens"),
        "reasoning": completion_details.get("reasoning_tokens"),
    }


def _error(request_id, endpoint, model, model_requested, started, kind, message,
           status=None, retryable=False, raw=None, notes=None):
    return {
        "ok": False, "id": request_id, "endpoint": endpoint,
        "model": model, "model_requested": model_requested,
        "text": None, "finish_reason": None,
        "usage": _usage(raw.get("usage") if isinstance(raw, dict) else None),
        "ms": round((time.monotonic() - started) * 1000), "raw": raw,
        "notes": notes or [],
        "error": {"kind": kind, "msg": message, "status": status,
                  "retryable": retryable},
    }


def _endpoint_error(endpoint, req, started, message):
    endpoint = endpoint if isinstance(endpoint, dict) else {}
    return _error(req.get("id") if isinstance(req, dict) else None,
                  endpoint.get("name"), None, endpoint.get("model"), started,
                  "bad_request", message)


def _validate_endpoint(endpoint, need_model=True):
    if not isinstance(endpoint, dict):
        return "endpoint 必須是 JSON 物件"
    for key in ("name", "base_url"):
        if not isinstance(endpoint.get(key), str) or not endpoint[key]:
            return "endpoint %s 必須是非空字串" % key
    if endpoint.get("kind") != "openai":
        return "endpoint kind 只支援 openai"
    if endpoint.get("enabled", True) is not True:
        return "endpoint 沒有啟用：%s" % endpoint["name"]
    if need_model and (not isinstance(endpoint.get("model"), str)
                       or not endpoint["model"]):
        return "endpoint model 必須是非空字串"
    if "timeout_ms" in endpoint and (
            not isinstance(endpoint["timeout_ms"], int)
            or isinstance(endpoint["timeout_ms"], bool)
            or endpoint["timeout_ms"] <= 0):
        return "endpoint timeout_ms 必須是正整數"
    if ("api_key_env" in endpoint
            and (not isinstance(endpoint["api_key_env"], str)
                 or not endpoint["api_key_env"])):
        return "endpoint api_key_env 必須是非空字串"
    if ("strict_model" in endpoint
            and not isinstance(endpoint["strict_model"], bool)):
        return "endpoint strict_model 必須是布林值"
    return None


def _headers(endpoint):
    headers = {"Content-Type": "application/json"}
    env_name = endpoint.get("api_key_env")
    if env_name:
        api_key = os.environ.get(env_name)
        if api_key is None:
            return None, "環境變數 %s 沒設" % env_name
        headers["Authorization"] = "Bearer %s" % api_key
    return headers, None


def _open(http_request, timeout_ms):
    with urllib.request.urlopen(http_request, timeout=timeout_ms / 1000) as response:
        return response.read()


def call(endpoint: dict, req: dict) -> dict:
    """同步呼叫一次 endpoint，永遠以 v1 result 回報成敗。"""
    started = time.monotonic()
    error = _validate_endpoint(endpoint)
    if error:
        return _endpoint_error(endpoint, req, started, error)
    request_id = req.get("id") if isinstance(req, dict) else None
    name, model = endpoint["name"], endpoint["model"]
    if not isinstance(req, dict):
        return _error(request_id, name, None, model, started, "bad_request",
                      "請求必須是 JSON 物件")
    if not isinstance(req.get("messages"), list) or not req["messages"]:
        return _error(request_id, name, None, model, started, "bad_request",
                      "messages 必須是非空陣列")
    if "model" in req:
        return _error(request_id, name, None, model, started, "bad_request",
                      "不准指定 model；model 固定在 endpoint 設定")
    if "priority" in req and (not isinstance(req["priority"], int)
                              or isinstance(req["priority"], bool)):
        return _error(request_id, name, None, model, started, "bad_request",
                      "priority 必須是整數")
    if "params" in req and not isinstance(req["params"], dict):
        return _error(request_id, name, None, model, started, "bad_request",
                      "params 必須是 JSON 物件")
    if "tools" in req and not isinstance(req["tools"], list):
        return _error(request_id, name, None, model, started, "bad_request",
                      "tools 必須是陣列（OpenAI tools 格式）")
    timeout_ms = req.get("timeout_ms", endpoint.get("timeout_ms", 300000))
    if (not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool)
            or timeout_ms <= 0):
        return _error(request_id, name, None, model, started, "bad_request",
                      "timeout_ms 必須是正整數")
    headers, key_error = _headers(endpoint)
    if key_error:
        return _error(request_id, name, None, model, started, "no_api_key",
                      key_error)
    notes = []
    if endpoint.get("strict_model", True):
        listing = models(endpoint, timeout_ms=timeout_ms)
        if listing["ok"] and model not in listing["ids"]:
            return _error(
                request_id, name, None, model, started, "model_not_found",
                "模型 %r 不在 endpoint 的 /models 列表；未送出 chat 請求" % model,
                raw={"preflight": listing["raw"]})
        if not listing["ok"]:
            notes.append({
                "kind": "model_preflight_skipped",
                "msg": "/models 查不到，仍照原流程送出 chat：%s" %
                       listing["error"]["msg"],
                "error": listing["error"],
            })
    body = {"model": model, "messages": req["messages"], "stream": False}
    body.update(req.get("params") or {})
    for key in ("tools", "tool_choice"):       # 工具呼叫是正式欄位，原樣轉給模型
        if key in req:
            body[key] = req[key]
    body["model"], body["stream"] = model, False
    try:
        http_request = urllib.request.Request(
            endpoint["base_url"].rstrip("/") + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST")
    except (TypeError, ValueError) as exc:
        return _error(request_id, name, None, model, started, "bad_request",
                      "請求或 base_url 不合法：%s" % exc)
    try:
        payload = _open(http_request, timeout_ms)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = str(exc)
        return _error(request_id, name, None, model, started, "http",
                      detail or str(exc), exc.code,
                      exc.code == 429 or 500 <= exc.code < 600, notes=notes)
    except (TimeoutError, socket.timeout) as exc:
        return _error(request_id, name, None, model, started, "timeout",
                      str(exc) or "連線逾時", retryable=True, notes=notes)
    except urllib.error.URLError as exc:
        kind = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "connect"
        return _error(request_id, name, None, model, started, kind,
                      str(exc.reason), retryable=True, notes=notes)
    except OSError as exc:
        return _error(request_id, name, None, model, started, "connect",
                      str(exc), retryable=True, notes=notes)
    try:
        raw = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _error(request_id, name, None, model, started, "bad_json",
                      "回應不是合法 JSON：%s" % exc, notes=notes)
    if not isinstance(raw, dict):
        return _error(request_id, name, None, model, started, "bad_json",
                      "回應 JSON 不是物件", raw=raw, notes=notes)
    if endpoint.get("strict_model", True) and raw.get("model") != model:
        return _error(request_id, name, raw.get("model"), model, started,
                      "model_mismatch", "回應 model %r，設定是 %r；別名 endpoint 請設 strict_model:false" % (raw.get("model"), model), raw=raw,
                      notes=notes)
    try:
        choice = raw["choices"][0]
        return {
            "ok": True, "id": request_id, "endpoint": name,
            "model": raw.get("model"), "model_requested": model,
            "text": choice["message"]["content"],
            "finish_reason": choice.get("finish_reason"),
            "usage": _usage(raw.get("usage")),
            "ms": round((time.monotonic() - started) * 1000), "raw": raw,
            "notes": notes, "error": None,
        }
    except (KeyError, IndexError, TypeError) as exc:
        return _error(request_id, name, raw.get("model"), model, started,
                      "bad_response",
                      "回應缺少 choices[0].message.content：%s" % exc,
                      raw=raw, notes=notes)


def models(endpoint: dict, timeout_ms=None) -> dict:
    """列出 endpoint 的模型 id；不丟出可預期的設定或連線錯誤。"""
    error = _validate_endpoint(endpoint, need_model=False)
    if error:
        return {"ok": False, "ids": [], "raw": None,
                "error": {"kind": "bad_request", "msg": error,
                          "status": None, "retryable": False}}
    headers, key_error = _headers(endpoint)
    if key_error:
        return {"ok": False, "ids": [], "raw": None,
                "error": {"kind": "no_api_key", "msg": key_error,
                          "status": None, "retryable": False}}
    try:
        request = urllib.request.Request(
            endpoint["base_url"].rstrip("/") + "/models", headers=headers,
            method="GET")
        payload = _open(request, timeout_ms or endpoint.get("timeout_ms", 300000))
        raw = json.loads(payload)
        if not isinstance(raw, dict) or not isinstance(raw.get("data"), list):
            raise TypeError("回應缺少 data 陣列")
        ids = [item["id"] for item in raw["data"]
               if isinstance(item, dict) and isinstance(item.get("id"), str)]
        return {"ok": True, "ids": ids, "raw": raw, "error": None}
    except urllib.error.HTTPError as exc:
        exc.close()
        return {"ok": False, "ids": [], "raw": None,
                "error": {"kind": "http", "msg": str(exc),
                          "status": exc.code,
                          "retryable": exc.code == 429 or 500 <= exc.code < 600}}
    except (TimeoutError, socket.timeout) as exc:
        return {"ok": False, "ids": [], "raw": None,
                "error": {"kind": "timeout", "msg": str(exc) or "連線逾時",
                          "status": None, "retryable": True}}
    except urllib.error.URLError as exc:
        kind = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "connect"
        return {"ok": False, "ids": [], "raw": None,
                "error": {"kind": kind, "msg": str(exc.reason),
                          "status": None, "retryable": True}}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "ids": [], "raw": None,
                "error": {"kind": "bad_response", "msg": str(exc),
                          "status": None, "retryable": False}}


def main(argv=None):
    from aos_llm_cli import main as cli_main
    return cli_main(argv)
