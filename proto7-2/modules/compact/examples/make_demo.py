#!/usr/bin/env python3
"""造一份可立即試整理的記憶檔，既有檔案不覆蓋。"""
import json
from pathlib import Path
import sys

node = Path(sys.argv[1])
path = node / "notes/journal.jsonl"
path.parent.mkdir(parents=True, exist_ok=True)
# 四件事各記 50 則（re＝哪件事，text＝這一則做了什麼｜成果原文），像 aos 的工作紀錄。
jobs = {"週報": ["列大綱", "寫本週進度", "補數字表", "畫進度圖", "寫風險"],
        "新手FAQ": ["收集問題", "挑常見三題", "寫答案", "補指令範例", "請人試讀"],
        "會議紀錄": ["整理決議", "列待辦", "標負責人", "寫風險", "寄給與會者"],
        "數字表": ["抓原始數字", "對帳", "算週增率", "排版", "寫說明"]}
rows = [{"re": name, "at": f"2026-10-09T{9 + (i * 50 + k) // 60:02d}:{(i * 50 + k) % 60:02d}:00",
         "text": f"第 {(k - 1) // 5 + 1} 週{acts[(k - 1) % 5]}｜" + "成果原文，已完成的決定與檔名。" * 12}
        for i, (name, acts) in enumerate(jobs.items()) for k in range(1, 51)]
rows += [{"open": True, "text": f"未完成 {i:02d}"} for i in range(20)]
with path.open("x", encoding="utf-8", newline="") as stream:
    stream.write("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
print(f"已造好 {path}：200 則舊紀錄＋20 則 open")
