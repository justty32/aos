#!/usr/bin/env python3
"""造一份可立即試整理的記憶檔，既有檔案不覆蓋。"""
import json
from pathlib import Path
import sys

node = Path(sys.argv[1])
path = node / "notes/journal.jsonl"
path.parent.mkdir(parents=True, exist_ok=True)
rows = [{"text": f"舊紀錄 {i:03d}：" + "已完成的決定與檔名。" * 16} for i in range(200)]
rows += [{"open": True, "text": f"未完成 {i:02d}"} for i in range(20)]
with path.open("x", encoding="utf-8", newline="") as stream:
    stream.write("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
print(f"已造好 {path}：200 則舊紀錄＋20 則 open")
