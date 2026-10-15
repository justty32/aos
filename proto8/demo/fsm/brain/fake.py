"""假的腦（同步，N-41）：照 agent 的思考介面（lib/agent.md）。stdin {"messages", "tools"} → stdout 一份 OpenAI assistant 訊息。

睡 0.4 秒假裝等回覆，回覆寫死：問「幾點」就叫工具 clock（OpenAI 的 tool_calls）；問「兩個」一次叫兩個 clock；
問「亂」叫一個不存在的工具；剛拿到工具結果就照結果回；其他回「收到」。
工具裡有 clerk（報時員，另一個 agent）時，問「幾點」改叫 clerk、引數 {"question": 原問題}；clerk 回來就轉述。換成真的：frame（或定義資料夾）的 brain.json 換成 brain/openai.json 那種腦設定（例 `run.py brain/litellm.json`）。
"""
import json
import sys
import time

req = json.load(sys.stdin)
msgs = req["messages"]
tools = {t["function"]["name"] for t in req.get("tools", [])}
last = msgs[-1]
time.sleep(0.4)


def call(i, name, args=None):
    return {"id": "call_%d_%d" % (len(msgs), i), "type": "function",
            "function": {"name": name, "arguments": json.dumps(args or {}, ensure_ascii=False)}}


if last["role"] == "tool":
    try:
        res = json.loads(last["content"])["result"]
        text = "報時員說：%s" % res["reply"] if "reply" in res else "現在是 %s。" % res["time"]
    except (ValueError, KeyError, TypeError):
        text = "工具回了：%s" % last["content"]
    out = {"role": "assistant", "content": text}
elif "幾點" in last["content"] and "clerk" in tools:
    out = {"role": "assistant", "content": None, "tool_calls": [call(0, "clerk", {"question": last["content"]})]}
elif "幾點" in last["content"] and "clock" in tools:
    out = {"role": "assistant", "content": None, "tool_calls": [call(0, "clock")]}
elif "兩個" in last["content"]:
    out = {"role": "assistant", "content": None, "tool_calls": [call(0, "clock"), call(1, "clock")]}
elif "亂" in last["content"]:
    out = {"role": "assistant", "content": None, "tool_calls": [call(0, "nope")]}
else:
    out = {"role": "assistant", "content": "收到「%s」。（我是假的腦）" % last["content"]}
print(json.dumps(out, ensure_ascii=False))
