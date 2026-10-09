#!/usr/bin/env python3
"""造一份可立即試整理的記憶檔，既有檔案不覆蓋。"""
import json
from pathlib import Path
import sys

node = Path(sys.argv[1])
path = node / "notes/journal.jsonl"
path.parent.mkdir(parents=True, exist_ok=True)
# 四件事各記 50 則（re＝哪件事，text＝做到哪｜成果原文），像 aos 的工作紀錄。
jobs = ["週報", "新手FAQ", "會議紀錄", "數字表"]
rows = [{"re": name, "at": f"2026-10-09T{9 + (i * 50 + k) // 60:02d}:{(i * 50 + k) % 60:02d}:00",
         "text": f"寫好第 {k} 段；下一步寫第 {k + 1} 段｜" + "成果原文，已完成的決定與檔名。" * 12}
        for i, name in enumerate(jobs) for k in range(1, 51)]
rows += [{"open": True, "text": f"未完成 {i:02d}"} for i in range(20)]
with path.open("x", encoding="utf-8", newline="") as stream:
    stream.write("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
print(f"已造好 {path}：200 則舊紀錄＋20 則 open")
