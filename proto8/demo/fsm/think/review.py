"""review 格（cwd＝frame）：看 history 最後一則 assistant。有 tool_calls＝回 next=tool（不在內層表裡、在 end 裡＝交給外層）；
否則把回覆寫進 outbox.txt、回 next=idle（同樣交給外層）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cells"))
from common import history, ret  # noqa: E402

last = history()[-1]
if last.get("tool_calls"):
    ret({"next": "tool", "data": {"tool_calls": [c["function"]["name"] for c in last["tool_calls"]]}})
else:
    with open("outbox.txt", "a", encoding="utf-8") as f:
        f.write((last.get("content") or "") + "\n")
    ret({"next": "idle", "data": {"reply": last.get("content")}})
