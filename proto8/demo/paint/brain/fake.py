"""假的腦（給畫家 demo 用）：照思考介面（lib/agent.md），stdin {"messages", "tools"} → stdout 一份 OpenAI assistant 訊息。

同一支腳本當兩個角色，看請求裡帶了哪個工具：
- 有 brush（＝畫家）：使用者說要畫什麼 → 叫 brush、引數 {"question"}；brush 回來 → 用它備的顏色畫一張小圖（幾行字），
  並說這是這個 frame 的第幾幅（數 history 裡 user 訊息幾則：同一個 frame 續聊，數字就會往上加）。
- 有 palette（＝畫筆）：收到要畫什麼 → 叫 palette、引數 {"subject"}；palette 回來 → 一句「備好了哪些顏色」。
- 其他：回「收到」。
`--name X`：回覆前面加「〔X〕」，用來看出換了哪顆腦（demo 在 frame 放一份 brain.json 綁定成這顆）。
睡 0.2 秒假裝等回覆。換成真腦＝在 frame 放一份真腦的 brain.json（見 ../README.md）。
"""
import json
import re
import sys
import time

name = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv[1:-1] else None
req = json.load(sys.stdin)
msgs = req["messages"]
tools = {t["function"]["name"] for t in req.get("tools", [])}
last = msgs[-1]
users = [m["content"] for m in msgs if m["role"] == "user"]
time.sleep(0.2)


def subject(text):
    """「幫我畫一隻貓」→「一隻貓」：取「畫」後面到第一個標點那段。"""
    m = re.search(r"畫([^。！？!?，,]+)", text or "")
    return (m.group(1) if m else re.split(r"[。！？!?，,]", text or "")[0]).strip() or "東西"


def call(tool, args):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_%d" % len(msgs), "type": "function",
         "function": {"name": tool, "arguments": json.dumps(args, ensure_ascii=False)}}]}


def result(msg):
    """tool 訊息的 content 是 aos_inst 結果的 JSON 字串，工具 stdout 最後一份在 result。"""
    try:
        return json.loads(msg["content"]).get("result")
    except (ValueError, AttributeError):
        return None


def say(text):
    return {"role": "assistant", "content": ("〔%s〕" % name if name else "") + text}


if "brush" in tools:                                   # 畫家
    if last["role"] == "tool":
        res = result(last) or {}
        colors = res.get("reply") or "（畫筆沒回顏色：%s）" % json.dumps(res, ensure_ascii=False)
        art = "\n".join(["  /\\_/\\", " ( o.o )", "  > ^ <"]) if "貓" in users[-1] else \
            "\n".join(["  (\\__/)", "  (•ㅅ•)", "  /  づ"]) if "狗" in users[-1] else " [ ~~~~ ]"
        out = say("這是這個 frame 的第 %d 幅：%s\n%s\n畫筆說：%s" % (len(users), subject(users[-1]), art, colors))
    else:
        out = call("brush", {"question": "我要畫%s，請備顏料" % subject(last["content"])})
elif "palette" in tools:                               # 畫筆
    if last["role"] == "tool":
        res = result(last) or {}
        out = say("備好了：%s。" % "、".join(res.get("colors") or ["（調色盤沒回）"]))
    else:
        out = call("palette", {"subject": subject(last["content"])})
else:
    out = say("收到「%s」。（我是假的腦）" % last["content"])
print(json.dumps(out, ensure_ascii=False))
