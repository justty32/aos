"""aos-llm call（問模型一次）：aos-llm.md §1～§7 的設定讀驗、組請求、HTTP 與命令列。

agent 內容讀驗共用 aos_agent_home；不寫記憶、不碰 state、不重試、不跑工具。
"""
import argparse
import http.client
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

from aos_agent_home import AgentError, check_message, load_llm_view, resolve_field
from aos_directives import Context, DirectiveError, is_directive, load_document

RESERVED = ("model", "messages", "tools", "stream")


def config_path(env):
    """模型表位置必須由環境提供絕對路徑。"""
    path = env.get("AOS_LLM_CONFIG")
    if not isinstance(path, str) or not path or not os.path.isabs(path):
        raise AgentError("ConfigInvalid", "AOS_LLM_CONFIG 必須設成 llm.json 的絕對路徑")
    return path


def load_config(path, env=None):
    """整份解指示詞、整份驗 models，中心固定為設定檔所在資料夾。"""
    try:
        doc = load_document(path)
    except DirectiveError as e:
        code = {"ReferenceReadFailed": "ReadFailed", "ReferenceJsonInvalid": "JsonSyntax"}[e.code]
        raise AgentError(code, e.msg) from e
    except UnicodeError as e:
        raise AgentError("JsonSyntax", "%s 不是 UTF-8 JSON：%s" % (path, e)) from e
    if not isinstance(doc.root, dict):
        raise AgentError("NotAnObject", "llm.json 頂層必須是物件")
    if is_directive(doc.root):
        raise AgentError("FieldTypeMismatch", "llm.json 頂層必須是字面物件")
    cfg = resolve_field(doc, Context(doc, base_dir=os.path.dirname(os.path.abspath(path)), env=env), [])
    meta = cfg.get("_metainfo")
    if (not isinstance(meta, dict) or any(k not in meta for k in ("_type", "_version"))
            or meta["_type"] != "llm_config"):
        raise AgentError("ConfigInvalid", "llm.json 必填 _metainfo（_type 為 llm_config，含 _version）")
    if type(meta["_version"]) is not int or meta["_version"] != 1:
        raise AgentError("UnsupportedVersion", "llm.json 的 _version 只認整數 1")
    models = cfg.get("models")
    if not isinstance(models, dict):
        raise AgentError("ConfigInvalid", "llm.json 的 models 必須是物件")
    for name, entry in models.items():
        if not isinstance(entry, dict):
            raise AgentError("ConfigInvalid", "models.%s 必須是物件" % name)
        for key in ("endpoint", "model"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise AgentError("ConfigInvalid", "models.%s.%s 必須是非空字串" % (name, key))
        if entry.get("api_key") is not None and not isinstance(entry["api_key"], str):
            raise AgentError("ConfigInvalid", "models.%s.api_key 必須是字串或 null" % name)
        timeout = entry.setdefault("timeout_ms", 120000)
        if type(timeout) is not int or timeout <= 0:
            raise AgentError("ConfigInvalid", "models.%s.timeout_ms 必須是正整數（bool 不算）" % name)
    return cfg


def build_request(agent_dir, config, env=None, *, with_alias=False):
    """執行當下讀 agent 家，回 (請求 body, 已驗證的模型設定)。"""
    view = load_llm_view(agent_dir, env=env)
    if view["model"] not in config["models"]:
        raise AgentError("UnknownModel", "models 裡沒有代號 %s" % view["model"])
    entry = config["models"][view["model"]]
    messages = []
    if view["system"]:
        messages.append({"role": "system", "content": view["system"]})
    messages.extend(view["history"])
    body = {k: v for k, v in view["params"].items() if k not in RESERVED}
    body.update(model=entry["model"], messages=messages)
    if view["tools"]:
        body["tools"] = view["tools"]
    return (body, entry, view["model"]) if with_alias else (body, entry)


def normalize(msg):
    """先移除空 tool_calls，再補 null content；其他欄位原樣留著。"""
    out = dict(msg)
    if out.get("tool_calls") == []:
        del out["tool_calls"]
    if "content" in out and out["content"] is None and "tool_calls" not in out:
        out["content"] = ""
    return out


def _preview(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    return " ".join(str(raw).split())[:300]


def _post(body, entry, alias=None, seen=None):
    try:
        return _post_http(body, entry) if seen is None else _post_http(body, entry, seen)
    except AgentError as exc:
        if exc.code not in ('EngineFailed', 'Timeout'):
            raise
        message = exc.msg + '（endpoint %s，模型 %s→%s）' % (
            entry['endpoint'], alias or body['model'], entry['model'])
        if entry.get('api_key'):
            message = message.replace(entry['api_key'], '[已隱藏]')
        raise AgentError(exc.code, message) from exc


def _post_http(body, entry, seen=None):
    url = entry["endpoint"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if entry.get("api_key"):
        headers["Authorization"] = "Bearer " + entry["api_key"]
    try:
        req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=entry["timeout_ms"] / 1000.0) as resp:
            raw, status = resp.read(), resp.status
    except urllib.error.HTTPError as e:
        with e:
            try:
                preview = _preview(e.read(1200))
            except (OSError, http.client.HTTPException):
                preview = "（回應本文讀不到）"
        raise AgentError("EngineFailed", "HTTP %d：%s" % (e.code, preview)) from e
    except (socket.timeout, TimeoutError) as e:
        raise AgentError("Timeout", "HTTP 等了 %d ms 仍未完成" % entry["timeout_ms"]) from e
    except urllib.error.URLError as e:
        code = "Timeout" if isinstance(e.reason, TimeoutError) else "EngineFailed"
        raise AgentError(code, "HTTP 請求失敗：%s" % e.reason) from e
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise AgentError("EngineFailed", "HTTP 請求失敗：%s" % e) from e
    if not 200 <= status < 300:
        raise AgentError("EngineFailed", "HTTP %d：%s" % (status, _preview(raw)))
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError) as e:
        raise AgentError("EngineFailed", "回應不是合法 JSON：%s" % _preview(raw)) from e
    if seen is not None and isinstance(obj, dict):
        seen["usage"] = obj.get("usage") if isinstance(obj.get("usage"), dict) else None
    choices = obj.get("choices") if isinstance(obj, dict) else None
    if not (isinstance(choices, list) and choices and isinstance(choices[0], dict)
            and isinstance(choices[0].get("message"), dict)):
        raise AgentError("EngineFailed", "回應缺少 choices[0].message 物件")
    msg = normalize(choices[0]["message"])
    try:
        check_message(msg, from_model=True)
    except AgentError as e:
        raise AgentError("EngineFailed", "模型回覆不合規：%s" % e.msg) from e
    return msg


def call(agent_dir, env=None):
    """讀模型表與 agent 家、問一次模型，回驗過的 assistant message。"""
    env = os.environ if env is None else env
    config = load_config(config_path(env), env=env)
    body, entry, alias = build_request(agent_dir, config, env=env, with_alias=True)
    seen, start = {}, time.monotonic()
    try:
        return _post(body, entry, alias, seen)
    finally:
        if "usage" in seen:
            record_usage(agent_dir, env, alias, entry["model"], seen["usage"],
                         int((time.monotonic() - start) * 1000))


def record_usage(agent_dir, env, alias, model, usage, ms):
    """HTTP 回了 2xx 的 JSON 物件就追加一行到 <家>/log/usage.jsonl（spec/agent/events.md）；寫不進去不影響這一問。

    批 id 從 AOS_LLM_BATCH 拿（aos-agent 送 think 時放進工作 inst 的 envs）；手動跑的沒有＝null。
    usage 是端點回的原樣（LiteLLM／OpenAI 的 prompt_tokens、completion_tokens、total_tokens…），沒回＝null。
    """
    from aos_agent_events import USAGE, append_line, limits, now_iso
    batch = env.get("AOS_LLM_BATCH") or None
    base = os.path.abspath(agent_dir)
    record = {"at": now_iso(), "batch": batch, "alias": alias, "model": model, "ms": ms, "usage": usage}
    append_line(os.path.join(base, USAGE), record, limits(base))


def main(argv=None):
    """aos-llm 的入口：call 是第一個子命令，之後 llm 相關的都掛這裡（09-24 fix-r4）。"""
    ap = argparse.ArgumentParser(prog="aos-llm", description="llm 相關工具；call＝問模型一次，印出 assistant message")
    subs = ap.add_subparsers(dest="command", metavar="{call}")
    sub = subs.add_parser("call", help="問模型一次，印出 assistant message",
                          description="問模型一次，印出 assistant message")
    sub.add_argument("agent_dir", metavar="AGENT_DIR", nargs="?", default=".", help="agent 家（預設為目前資料夾）")
    args = ap.parse_args(argv)
    if args.command is None:
        ap.print_usage(sys.stderr)
        ap.exit(2, "aos-llm: error: 要給子命令：aos-llm call [AGENT_DIR]\n")
    try:
        msg = call(args.agent_dir)
    except AgentError as e:
        sys.stderr.write("aos-llm: %s\n" % " ".join(str(e).split()))
        return 1
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
