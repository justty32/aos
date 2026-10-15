#!/usr/bin/env python3
"""真的腦：照 agent 的思考介面（agent.md），把請求 POST 到 OpenAI 相容的 `/chat/completions`。純標準庫（urllib）。

    python3 aos_brain_openai.py [--key 值 ...] [CONFIG.json]   < {"messages": [...], "tools": [...]}

- stdin＝請求（JSON 串流只看第一份）：`messages`（OpenAI chat messages）、`tools`（選填，OpenAI function tools）。
- stdout＝一份 OpenAI assistant 訊息 `{"role": "assistant", "content", "tool_calls"?}`（取 choices[0].message）。
- 設定從 CONFIG.json（可接 `#/位置`）或旗標來（stdin 已經是請求，不收 `-`）：
      base_url     預設 http://localhost:4000/v1（LiteLLM，見 wf/workflows/dev-env.md）
      model        必填
      api_key_env  選填：放金鑰的環境變數名（例 DEEPSEEK_API_KEY）；沒寫＝不帶 Authorization（LiteLLM 不用）
      timeout_ms   預設 120000
  金鑰只從環境變數讀，不寫進檔、不印。不串流。
- 出錯：stderr 吐 {"error": {"code", "msg"}}、退出 1。代號：HttpError、ConnectFailed、BadResponse、NoApiKey，設定的照 aos_cli。
"""
import json
import os
import sys
import urllib.error
import urllib.request

import aos_cli
from aos_cli import CliError

FLAGS = ("base_url", "model", "api_key_env", "timeout_ms")
DEFAULT_URL = "http://localhost:4000/v1"


def config(argv):
    doc, _, piped, rest = aos_cli.config(argv, FLAGS)
    if piped or rest is not None:
        raise CliError("Usage", "stdin 是請求；設定只從 CONFIG.json 或旗標來，不收 - 與 --")
    cfg = {"base_url": doc.get("base_url", DEFAULT_URL), "model": doc.get("model"),
           "api_key_env": doc.get("api_key_env"), "timeout_ms": doc.get("timeout_ms", 120000)}
    if not (isinstance(cfg["model"], str) and cfg["model"]):
        raise CliError("FieldType", "model 要是模型名字串，不是 %r" % (cfg["model"],))
    if not (isinstance(cfg["timeout_ms"], int) and cfg["timeout_ms"] > 0):
        raise CliError("FieldType", "timeout_ms 要是正整數，不是 %r" % (cfg["timeout_ms"],))
    return cfg


def ask(cfg, req):
    """送一次請求，回 assistant 訊息 dict。"""
    body = {"model": cfg["model"], "messages": req.get("messages", [])}
    if req.get("tools"):
        body["tools"] = req["tools"]
    headers = {"Content-Type": "application/json"}
    if cfg["api_key_env"]:
        key = os.environ.get(cfg["api_key_env"])
        if not key:
            raise CliError("NoApiKey", "環境變數 %s 沒有設" % cfg["api_key_env"])
        headers["Authorization"] = "Bearer " + key
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    r = urllib.request.Request(url, json.dumps(body).encode("utf-8"), headers, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=cfg["timeout_ms"] / 1000) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise CliError("HttpError", "%s 回 %d：%s" % (url, e.code, e.read()[:500].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError) as e:
        raise CliError("ConnectFailed", "連不上 %s：%s" % (url, e))
    try:
        msg = json.loads(raw)["choices"][0]["message"]
        out = {"role": "assistant", "content": msg.get("content")}
        if msg.get("tool_calls"):
            out["tool_calls"] = [{"id": c["id"], "type": "function",
                                  "function": {"name": c["function"]["name"],
                                               "arguments": c["function"].get("arguments") or "{}"}}
                                 for c in msg["tool_calls"]]
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise CliError("BadResponse", "%s 回的不是 chat completion：%s" % (url, raw[:500].decode("utf-8", "replace")))
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        cfg = config(argv)
        docs = aos_cli.read_stream(sys.stdin.read())
        if not (docs and isinstance(docs[0], dict)):
            raise CliError("JsonSyntax", "stdin 要有一份請求 {\"messages\", \"tools\"}")
        if len(docs) > 1:
            aos_cli.warn("ExtraInput", "stdin 有 %d 份 JSON，只看第一份" % len(docs))
        aos_cli.emit(ask(cfg, docs[0]))
    except CliError as e:
        aos_cli.error(e.code, e.msg)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
