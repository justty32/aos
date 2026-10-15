"""review 格：讀 work/answer.json。要用工具＝回 next=tool（不在內層表裡、在 end 裡＝交給外層）；
否則把回覆寫進 outbox.txt、回 next=idle（同樣交給外層）。"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cells"))
from common import DIR, args, convo, ret, save  # noqa: E402

args()
with open(os.path.join(DIR, "work", "answer.json"), encoding="utf-8") as f:
    answer = json.load(f)
if "tool" in answer:
    ret({"next": "tool", "data": {"tool": answer["tool"]}})
else:
    save(convo() + [{"role": "assistant", "text": answer["reply"]}])
    with open(os.path.join(DIR, "outbox.txt"), "a", encoding="utf-8") as f:
        f.write(answer["reply"] + "\n")
    ret({"next": "idle", "data": {"reply": answer["reply"]}})
