#!/usr/bin/env python3
"""造一份可立即試整理的記憶檔，既有檔案不覆蓋。"""
import json
from pathlib import Path
import sys

node = Path(sys.argv[1])
path = node / "notes/journal.jsonl"
path.parent.mkdir(parents=True, exist_ok=True)
# 仿 aos 的 brain：四封信各做 50 回合，每回合記一則（哪封信、第幾回合、做到哪｜成果原文）。
jobs = [("you-20261009T090000-5d1c0a7f3e21", "週報"), ("you-20261009T093000-8b42e6c19d07", "新手 FAQ"),
        ("you-20261009T100000-c3f9a1d2b845", "會議紀錄"), ("you-20261009T103000-07ae5b3c6f90", "數字表")]
rows = [{"re": rid, "step": k, "at": f"2026-10-09T{9 + (i * 50 + k) // 60:02d}:{(i * 50 + k) % 60:02d}:00",
         "text": f"{name}第 {k} 段寫好；下一步寫第 {k + 1} 段｜" + "成果原文，已完成的決定與檔名。" * 12}
        for i, (rid, name) in enumerate(jobs) for k in range(1, 51)]
rows += [{"open": True, "text": f"未完成 {i:02d}"} for i in range(20)]
with path.open("x", encoding="utf-8", newline="") as stream:
    stream.write("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
print(f"已造好 {path}：200 則舊紀錄＋20 則 open")
