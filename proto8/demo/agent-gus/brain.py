# brain.py - think 格：帶 $AOS_STACK/history.jsonl＋tools 問腦，回覆一行接進 history（同 agent-dan，但不認領題目：plan 格做了）。
# 拆過的題，history 裡已有「小念頭 sN 的結論」幾則，腦看到就彙整回答；沒拆的題就是 agent-dan 的「想 → 工具 → 想 → 答」。
# 沒設 AOS_BRAIN_URL＝假腦。失敗時 history 不接任何東西、退 1（P-20）。
import os, re
from shared import append_history, ask, die, read_history, system, tools_spec

history = read_history()
if not history or history[-1].get("role") not in ("user", "tool"):
    die("HistoryBad", "history 最後一則不是 user／tool，沒有東西可想（plan 格該先接題目）")


def fake():
    first = next((m["content"] for m in history if m.get("role") == "user"), "")
    goal = re.search(r"^你的目標：(.*)$", first, re.M)
    notes = [m["content"].split("\n", 1)[0] for m in history if m.get("role") == "user"
             and str(m.get("content")).startswith("小念頭 ")]
    if goal:
        return {"role": "assistant", "content": "FAKE CONCLUSION: " + goal.group(1)}
    text = "FAKE ANSWER to: " + first.strip().split("\n")[0]
    if notes:
        text += "（彙整了 %d 個小念頭的結論）" % len(notes)
    return {"role": "assistant", "content": text}


append_history(fake() if not os.environ.get("AOS_BRAIN_URL") else ask("think", system() + history, tools_spec()))
