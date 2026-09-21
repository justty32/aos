#!/usr/bin/env python3
"""aos-llm-ask：把一個 agent 資料夾問模型**一次**——讀 info.json 那套、組請求、打出去、印回話。

    aos-llm-ask [dir] [--dry-run]

規範是 ../spec/aos-llm-ask.md；資料夾怎麼讀驗在 aos_agent_info.py（../spec/agent.md）。
這支只做三件事：

1. `build_request(dir)`：讀驗 ＋ 組一份 OpenAI chat/completions 的 body（不碰網路）。
   `messages`＝（`system` 有內容才加一則 system）＋ 記憶原樣；`tools`＝合併後去掉 `_` key 的
   工具表（空的就不送這個欄位）；`engine.params` 原樣併進 body，但 `model`／`messages`／
   `tools`／`stream` 四個是這支程式自己決定的，params 撞到就忽略；`stream` 永遠不送。
2. `call(engine, body)`：用 `urllib.request` POST 到 `endpoint`（結尾多餘的 `/` 去掉）＋
   `/chat/completions`，`api_key` 有值才送 `Authorization: Bearer`，等 `timeout_ms`；回
   `choices[0].message` 那個 dict。連不上、非 2xx、逾時、回來不是 JSON、沒有
   `choices[0].message` → `EngineFailed`。
3. `ask(dir)`＝1 ＋ 2。

命令列：`--dry-run` 印 body、不然印 message，**stdout 永遠只有一行 JSON**；退出碼
0（成功）／1（讀驗錯誤：stderr 一行 `aos-llm-ask: <代號>: <白話>`）／2（用法錯）／
3（引擎失敗：stderr 一行 `aos-llm-ask: engine: <白話>`）。不寫任何檔、不碰 state.json、
不跑工具、不重試。aos-agent 的 think 格之後直接 import 這裡的函式，不開子進程。
"""
import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request

import aos_agent_info
from aos_agent_info import AgentError

__all__ = ["EngineFailed", "AgentError", "RESERVED", "build_request", "request_from_info",
           "call", "ask", "main"]

RESERVED = ("model", "messages", "tools", "stream")     # params 裡撞到這四個就忽略
_BODY_PREVIEW = 300                                     # 引擎回錯時 stderr 帶多少回應本文


class EngineFailed(Exception):
    """這次問模型沒成：連不上、HTTP 非 2xx、逾時、回來不是 JSON、沒有 choices[0].message。

    跟 `AgentError`（設定壞了，根本沒送出去）分開：命令列上這是退出碼 3，讀驗錯誤是 1。
    `msg` 是白話，`str(e)` 就是它。
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg


def build_request(dir, env=None):
    """讀驗 `dir` 並組 chat/completions 的 body（規範 §3）。不碰網路。讀驗錯誤丟 `AgentError`。"""
    return request_from_info(aos_agent_info.load(dir, env=env))


def request_from_info(info):
    """從 `aos_agent_info.load()` 回的 dict 組 body：model → messages → tools（有才送）→ params。"""
    body = {"model": info["engine"]["model"]}
    messages = []
    if info["system"] != "":
        messages.append({"role": "system", "content": info["system"]})
    messages.extend(info["history"])
    body["messages"] = messages
    if info["tools"]:
        body["tools"] = info["tools"]
    for k, v in info["engine"]["params"].items():
        if k in RESERVED:
            continue
        body[k] = v
    return body


def call(engine, body):
    """把 `body` POST 到 `engine`（`aos_agent_info` 回的那個 dict）的 chat/completions，回
    `choices[0].message`。任何一種失敗都是 `EngineFailed`。"""
    url = engine["endpoint"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if engine.get("api_key"):
        headers["Authorization"] = "Bearer " + engine["api_key"]
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    timeout = engine.get("timeout_ms", aos_agent_info.DEFAULT_TIMEOUT_MS) / 1000.0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        raise EngineFailed("%s 回 HTTP %d：%s" % (url, e.code, _preview(_safe_read(e))))
    except (socket.timeout, TimeoutError):
        raise EngineFailed("%s 等了 %d ms 沒回（逾時）" % (url, engine.get("timeout_ms", aos_agent_info.DEFAULT_TIMEOUT_MS)))
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise EngineFailed("%s 等了 %d ms 沒回（逾時）" % (url, engine.get("timeout_ms", aos_agent_info.DEFAULT_TIMEOUT_MS)))
        raise EngineFailed("連不上 %s：%s" % (url, reason))
    except OSError as e:
        raise EngineFailed("跟 %s 講話時出錯：%s" % (url, e))
    if not 200 <= status < 300:
        raise EngineFailed("%s 回 HTTP %d：%s" % (url, status, _preview(raw)))
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise EngineFailed("%s 回來的不是合法 JSON（%s）：%s" % (url, e, _preview(raw)))
    return _message(obj, url)


def ask(dir, env=None):
    """`build_request` 再打引擎，回 `choices[0].message`。讀驗錯誤丟 `AgentError`、引擎失敗丟 `EngineFailed`。"""
    info = aos_agent_info.load(dir, env=env)
    return call(info["engine"], request_from_info(info))


def _message(obj, url):
    """從回應裡挖 `choices[0].message`（要是物件）；挖不到＝`EngineFailed`。"""
    choices = obj.get("choices") if isinstance(obj, dict) else None
    if not (isinstance(choices, list) and choices and isinstance(choices[0], dict)):
        raise EngineFailed("%s 回來的 JSON 沒有 choices[0]：%s" % (url, _preview(json.dumps(obj, ensure_ascii=False))))
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        raise EngineFailed("%s 回來的 choices[0] 沒有 message 物件：%s"
                           % (url, _preview(json.dumps(choices[0], ensure_ascii=False))))
    return msg


def _safe_read(resp):
    try:
        return resp.read()
    except Exception:       # 錯誤回應的本文讀不到就算了，狀態碼才是重點
        return b""


def _preview(raw):
    """回應本文的前一小段，放進 stderr 那一行；換行壓成空白，保持一行。"""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    raw = " ".join(raw.split())
    return raw[:_BODY_PREVIEW] + ("…" if len(raw) > _BODY_PREVIEW else "")


# ---------------------------------------------------------------- 命令列 ----

def main(argv=None):
    """命令列：`aos-llm-ask [dir] [--dry-run]`。stdout 只印一行 JSON；退出碼 0／1／2／3。"""
    ap = argparse.ArgumentParser(prog="aos-llm-ask", description="把一個 agent 資料夾問模型一次")
    ap.add_argument("dir", nargs="?", default=".", help="agent 資料夾（有 info.json 的那個）；留空＝.")
    ap.add_argument("--dry-run", action="store_true", help="不送出去，只把組好的請求印成一行 JSON")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if not os.path.isdir(a.dir):
        _err("%s 不是資料夾" % a.dir)
        return 2
    try:
        if a.dry_run:
            out = build_request(a.dir)
        else:
            out = ask(a.dir)
    except AgentError as e:
        _err(str(e))
        return 1
    except EngineFailed as e:
        _err("engine: %s" % e.msg)
        return 3
    sys.stdout.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return 0


def _err(msg):
    sys.stderr.write("aos-llm-ask: %s\n" % " ".join(str(msg).split()))
    sys.stderr.flush()


if __name__ == "__main__":
    sys.exit(main())
