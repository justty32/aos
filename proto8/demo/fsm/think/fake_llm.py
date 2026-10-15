"""ask 格（同步版，N-41）：假的 LLM。起來就「等回覆」（睡 0.4 秒）、拿到回覆寫進 work/answer.json 才結束，回 next=review。

這裡沒有真的 LLM endpoint，回覆是寫死的。換成真的：把 think/ask.json 換成一張跑 aos-llm（core/llm）的 inst——
stdin 給組好的請求（例如從 work/convo.json 組）、stdout 接到 work/answer.json——其他格都不用動。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cells"))
from common import DIR, args, convo, ret  # noqa: E402

args()
msgs = convo()
last = msgs[-1]
time.sleep(0.4)                                     # 假裝在等 LLM 回覆（同步：阻塞到拿到為止）
if last["role"] == "tool":
    answer = {"reply": "現在是 %s。" % last["text"]}
elif "幾點" in last["text"]:
    answer = {"tool": "clock"}                      # 要用工具
else:
    answer = {"reply": "收到「%s」。（我是假的 LLM）" % last["text"]}
with open(os.path.join(DIR, "work", "answer.json"), "w", encoding="utf-8") as f:
    json.dump(answer, f, ensure_ascii=False)
ret({"next": "review"})
