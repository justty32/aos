#!/usr/bin/env python3
"""真的腦（ollama 原生）：照 agent 的思考介面（agent.md），把請求 POST 到 ollama 的 `/api/chat`。純標準庫（urllib）。

    python3 aos_brain_ollama.py [--key 值 ...] [CONFIG.json]   < {"messages": [...], "tools": [...]}

為什麼不走 ollama 的 OpenAI 相容 `/v1`：那條設不了 `num_ctx`（context 長度），ollama 會用模型預設、可能吃爆顯存。
- stdin＝請求（一份；多份＝ExtraInput 錯）：`messages`（OpenAI chat messages）、`tools`（選填，OpenAI function tools，ollama 收同樣形狀）。
- stdout＝一份 OpenAI assistant 訊息 `{"role": "assistant", "content", "tool_calls"?, "usage"?}`，跟 aos_brain_openai 一樣
  （usage 由 prompt_eval_count＋eval_count 換成 OpenAI 形狀）。
- 兩邊形狀的翻譯：
      送出：assistant 的 tool_calls arguments（JSON 字串）→ 物件；content null → ""；
            tool 訊息補 `tool_name`（從前面 assistant 的 tool_calls 用 id 找）。
      收回：ollama 的 tool_calls（arguments 是物件、可能沒 id）→ arguments 轉 JSON 字串、沒 id 就編 `call_<亂數>_<n>`（每次不同，history 裡不撞）。
- 設定從 CONFIG.json（可接 `#/位置`）或旗標來（stdin 已經是請求，不收 `-`）：
      base_url     預設 http://localhost:11434（ollama 預設的口；不含 /api）
      model        必填
      num_ctx      預設 4096（送進 options.num_ctx）
      keep_alive   預設 "30s"（用完多久卸載；0＝馬上卸）
      timeout_ms   預設 120000
  不串流（stream: false）。
- 出錯：stderr 吐 {"error": {"code", "msg"}}、退出 1。代號：HttpError（含模型不支援 tools 時 ollama 回的 400）、
  ConnectFailed、BadResponse，設定的照 aos_cli。
"""
import json
import os
import sys
import urllib.error
import urllib.request

import aos_cli
from aos_cli import CliError

FLAGS = ("base_url", "model", "num_ctx", "keep_alive", "timeout_ms")
DEFAULT_URL = "http://localhost:11434"


def config(argv):
    doc, _, piped, rest = aos_cli.config(argv, FLAGS)
    if piped or rest is not None:
        raise CliError("Usage", "stdin 是請求；設定只從 CONFIG.json 或旗標來，不收 - 與 --")
    cfg = {"base_url": doc.get("base_url", DEFAULT_URL), "model": doc.get("model"),
           "num_ctx": doc.get("num_ctx", 4096), "keep_alive": doc.get("keep_alive", "30s"),
           "timeout_ms": doc.get("timeout_ms", 120000)}
    if not (isinstance(cfg["model"], str) and cfg["model"]):
        raise CliError("FieldType", "model 要是模型名字串，不是 %r" % (cfg["model"],))
    for k in ("num_ctx", "timeout_ms"):
        if not (isinstance(cfg[k], int) and not isinstance(cfg[k], bool) and cfg[k] > 0):
            raise CliError("FieldType", "%s 要是正整數，不是 %r" % (k, cfg[k]))
    if not isinstance(cfg["keep_alive"], (str, int)) or isinstance(cfg["keep_alive"], bool):
        raise CliError("FieldType", "keep_alive 要是字串（例 \"30s\"）或秒數，不是 %r" % (cfg["keep_alive"],))
    return cfg


def _args_obj(s):
    if isinstance(s, dict):
        return s
    try:
        v = json.loads(s or "{}")
    except (TypeError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def to_ollama(messages):
    """OpenAI messages → ollama /api/chat messages。"""
    names, out = {}, []
    for m in messages:
        o = {"role": m.get("role"), "content": m.get("content") or ""}
        if m.get("tool_calls"):
            o["tool_calls"] = []
            for c in m["tool_calls"]:
                f = c.get("function", {})
                names[c.get("id")] = f.get("name")
                o["tool_calls"].append({"function": {"name": f.get("name"), "arguments": _args_obj(f.get("arguments"))}})
        if m.get("role") == "tool":
            o["tool_call_id"] = m.get("tool_call_id")
            if m.get("tool_call_id") in names:
                o["tool_name"] = names[m["tool_call_id"]]
        out.append(o)
    return out


def from_ollama(msg):
    """ollama 回的 message → OpenAI assistant 訊息。"""
    out = {"role": "assistant", "content": msg.get("content") or None}
    if msg.get("tool_calls"):
        out["tool_calls"], tag = [], os.urandom(3).hex()
        for i, c in enumerate(msg["tool_calls"]):
            a = c["function"].get("arguments")
            out["tool_calls"].append({"id": c.get("id") or "call_%s_%d" % (tag, i), "type": "function",
                                      "function": {"name": c["function"]["name"],
                                                   "arguments": a if isinstance(a, str) else json.dumps(a or {}, ensure_ascii=False)}})
    return out


def ask(cfg, req):
    """送一次請求，回 assistant 訊息 dict。"""
    body = {"model": cfg["model"], "messages": to_ollama(req.get("messages", [])), "stream": False,
            "options": {"num_ctx": cfg["num_ctx"]}, "keep_alive": cfg["keep_alive"]}
    if req.get("tools"):
        body["tools"] = req["tools"]
    url = cfg["base_url"].rstrip("/") + "/api/chat"
    r = urllib.request.Request(url, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=cfg["timeout_ms"] / 1000) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise CliError("HttpError", "%s 回 %d：%s" % (url, e.code, e.read()[:500].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError) as e:
        raise CliError("ConnectFailed", "連不上 %s：%s" % (url, e))
    try:
        doc = json.loads(raw)
        out = from_ollama(doc["message"])
        p, c = doc.get("prompt_eval_count"), doc.get("eval_count")
        if isinstance(p, int) or isinstance(c, int):        # ollama 的計數 → OpenAI 形狀的 usage
            p, c = p if isinstance(p, int) else 0, c if isinstance(c, int) else 0
            out["usage"] = {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}
        return out
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise CliError("BadResponse", "%s 回的不是 ollama chat 回應：%s" % (url, raw[:500].decode("utf-8", "replace")))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        cfg = config(argv)
        docs = aos_cli.read_stream(sys.stdin.read())
        if not (docs and isinstance(docs[0], dict)):
            raise CliError("JsonSyntax", "stdin 要有一份請求 {\"messages\", \"tools\"}")
        if len(docs) > 1:
            raise CliError("ExtraInput", "stdin 有 %d 份 JSON，請求只要一份" % len(docs))
        aos_cli.emit(ask(cfg, docs[0]))
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
