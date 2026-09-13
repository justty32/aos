"""llm-cpu 的背景 OpenAI 相容 worker。"""
import json
import os
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request

import llm_cpu_home as home


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


def _error(request_id, endpoint, model, started, kind, message,
           status=None, retryable=False, raw=None):
    return {
        "ok": False, "id": request_id, "endpoint": endpoint,
        "model": model, "text": None, "finish_reason": None,
        "usage": _usage(raw.get("usage") if isinstance(raw, dict) else None),
        "ms": round((time.monotonic() - started) * 1000), "raw": raw,
        "error": {"kind": kind, "msg": message, "status": status,
                  "retryable": retryable},
    }


def _success(request_id, endpoint, raw, started):
    choice = raw["choices"][0]
    return {
        "ok": True, "id": request_id, "endpoint": endpoint,
        "model": raw.get("model"), "text": choice["message"]["content"],
        "finish_reason": choice.get("finish_reason"),
        "usage": _usage(raw.get("usage")),
        "ms": round((time.monotonic() - started) * 1000), "raw": raw,
        "error": None,
    }


def _request(root, request_id, started):
    req = home.read_json(root / "requests" / "running" / (request_id + ".json"))
    endpoint_name = req["_aos"]["endpoint"]
    _, endpoints = home.load_endpoints(root)
    endpoint = endpoints[endpoint_name]
    model = endpoint["model"]
    env_name = endpoint.get("api_key_env")
    headers = {"Content-Type": "application/json"}
    if env_name:
        api_key = os.environ.get(env_name)
        if api_key is None:
            return _error(request_id, endpoint_name, model, started, "no_api_key",
                          "環境變數 %s 沒設" % env_name)
        headers["Authorization"] = "Bearer %s" % api_key
    body = {"model": model, "messages": req["messages"], "stream": False}
    body.update(req.get("params") or {})
    # model 與 stream 都是 cpu 的契約，params 不能暗中蓋掉。
    body["model"] = model
    body["stream"] = False
    timeout_ms = req.get("timeout_ms", endpoint["timeout_ms"])
    url = endpoint["base_url"].rstrip("/") + "/chat/completions"
    http_request = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST")
    try:
        with urllib.request.urlopen(http_request, timeout=timeout_ms / 1000) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = str(exc)
        return _error(request_id, endpoint_name, model, started, "http",
                      detail or str(exc), exc.code,
                      exc.code == 429 or 500 <= exc.code < 600)
    except (TimeoutError, socket.timeout) as exc:
        return _error(request_id, endpoint_name, model, started, "timeout",
                      str(exc) or "連線逾時", retryable=True)
    except urllib.error.URLError as exc:
        reason = exc.reason
        kind = "timeout" if isinstance(reason, (TimeoutError, socket.timeout)) else "connect"
        return _error(request_id, endpoint_name, model, started, kind,
                      str(reason), retryable=True)
    except OSError as exc:
        return _error(request_id, endpoint_name, model, started, "connect",
                      str(exc), retryable=True)
    try:
        raw = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _error(request_id, endpoint_name, model, started, "bad_json",
                      "回應不是合法 JSON：%s" % exc)
    if not isinstance(raw, dict):
        return _error(request_id, endpoint_name, model, started, "bad_json",
                      "回應 JSON 不是物件", raw=raw)
    if raw.get("model") != model:
        return _error(request_id, endpoint_name, raw.get("model"), started,
                      "model_mismatch", "回應 model %r，設定是 %r" %
                      (raw.get("model"), model), raw=raw)
    try:
        return _success(request_id, endpoint_name, raw, started)
    except (KeyError, IndexError, TypeError) as exc:
        return _error(request_id, endpoint_name, model, started, "bad_response",
                      "回應缺少 choices[0].message.content：%s" % exc, raw=raw)


def _write_usage(root, result):
    usage = result.get("usage") or _usage(None)
    row = {
        "at": home.now_text(), "id": result["id"],
        "endpoint": result.get("endpoint"), "model": result.get("model"),
        "prompt": usage.get("prompt"), "completion": usage.get("completion"),
        "total": usage.get("total"), "cached": usage.get("cached"),
        "reasoning": usage.get("reasoning"), "ms": result.get("ms"),
        "ok": result.get("ok", False),
    }
    data = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(data) >= 4096:
        data = (json.dumps({**row, "model": None}, ensure_ascii=False,
                           separators=(",", ":")) + "\n").encode()
    fd = os.open(root / "usage.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def run(directory, request_id):
    root = Path(directory).absolute()
    started = time.monotonic()
    try:
        result = _request(root, request_id, started)
    except BaseException as exc:
        result = _error(request_id, None, None, started, "internal",
                        "%s: %s" % (type(exc).__name__, exc))
    try:
        home.atomic_json(root / "results" / (request_id + ".json"), result)
        _write_usage(root, result)
    except BaseException as exc:
        print("worker 寫結果失敗：%s" % exc, file=sys.stderr)
        return 1
    return 0
