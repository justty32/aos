#!/usr/bin/env python3
"""Usage: python3 -B compareab.py RUNSDIR

Read recursively all summary.json files; no AI calls and no files written.
Blueprint §4 criteria, fixed before experiments:
  ① B passes across gap/runs/audit >= A passes + 4, and B gap >= 3/5.
  ② B format_blocks <= A format_blocks / 3.
  ③ Sum of B per-task mean total_tokens <= 1.3 * corresponding A sum.
All three: 達標; ①② only: 有訊號，再各跑 5 次; otherwise:
機制收下、不往 brain 推. With fewer than five trials in any planned cell,
use actual counts/means and label the decision 次數不足 (no extrapolation).
Only gap/runs/audit enter criteria; other tasks (e.g. mailcount) are shown.
Noise uses population SD of observed pass indicators and rounds; matched
rep differences use sample SD (undefined with fewer than two matched reps).
Token columns use driver total_tokens = apprentice_tokens + review_tokens.
"""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
import sys

TASKS = ("gap", "runs", "audit")
GROUPS = ("A", "B")
TRIALS = 5
PASS_MARGIN = 4
GAP_PASSES = 3
FORMAT_DIVISOR = 3
TOKEN_RATIO = 1.3
NUMBERS = ("rounds", "calls", "format_blocks", "total_tokens", "secs")


def mean(rows, key):
    return statistics.mean(row[key] for row in rows) if rows else None


def sd(rows, key):
    return statistics.pstdev(row[key] for row in rows) if rows else None


def fmt(value, places=2):
    return "—" if value is None else f"{value:,.{places}f}"


def passes(rows):
    return sum(row["passed"] for row in rows)


def table(headers, rows):
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        print("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in row) + " |")
    print()


def read_summaries(root):
    if not root.is_dir():
        raise ValueError(f"不是資料夾：{root}")
    rows = []
    for path in sorted(root.rglob("summary.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(row, dict):
                raise ValueError("summary 必須是 object")
            if row.get("group") not in GROUPS:
                raise ValueError("group 必須是 A 或 B")
            if not isinstance(row.get("task"), str) or not row["task"]:
                raise ValueError("缺少 task")
            if "rep" not in row or not isinstance(row.get("passed"), bool):
                raise ValueError("缺少 rep 或 passed 不是 bool")
            for key in NUMBERS:
                value = row.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"{key} 必須是非負有限數字")
            rows.append(row)
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"{path}: {exc}") from exc
    return rows


def report(rows):
    cells = defaultdict(list)
    for row in rows:
        cells[row["group"], row["task"]].append(row)
    missing_tokens = any(r.get('token_missing') for r in rows)
    if missing_tokens:
        print('token 回條缺失：表格 token 僅為已確認小計，③ 無法判定。\n')
    batches = {(r.get('model'), r.get('review'), r.get('offline')) for r in rows}
    if len(batches) > 1:
        print('資料含不同模型／審查／離線模式；請分開 RUNSDIR 再做正式比較。\n')
    extras = sorted({row["task"] for row in rows} - set(TASKS))
    tasks = list(TASKS) + extras
    print(f"讀入 {len(rows)} 份 summary.json；主判準只算 gap／runs／audit。\n")
    summary = []
    for group in GROUPS:
        for task in tasks:
            cell = cells[group, task]
            summary.append((group, task, len(cell), f"{passes(cell)}/{len(cell)}",
                            fmt(mean(cell, "rounds")), fmt(mean(cell, "calls")),
                            sum(x["format_blocks"] for x in cell),
                            fmt(mean(cell, "total_tokens"), 0), fmt(mean(cell, "secs")),
                            "次數不足" if len(cell) < TRIALS else ""))
        combined = [row for task in TASKS for row in cells[group, task]]
        summary.append((group, "三題合計", len(combined), f"{passes(combined)}/{len(combined)}",
                        fmt(mean(combined, "rounds")), fmt(mean(combined, "calls")),
                        sum(x["format_blocks"] for x in combined),
                        fmt(mean(combined, "total_tokens"), 0), fmt(mean(combined, "secs")),
                        "次數不足" if any(len(cells[group, t]) < TRIALS for t in TASKS) else ""))
    table(("組", "題", "次數", "通過", "平均輪數", "平均呼叫", "format_blocks", "平均 token", "平均秒數", "備註"), summary)

    planned = {g: [r for t in TASKS for r in cells[g, t]] for g in GROUPS}
    enough = all(len(cells[g, t]) >= TRIALS for g in GROUPS for t in TASKS)
    available = all(cells[g, t] for g in GROUPS for t in TASKS)
    a_pass, b_pass = (passes(planned[g]) for g in GROUPS)
    a_fmt, b_fmt = (sum(r["format_blocks"] for r in planned[g]) for g in GROUPS)
    totals = {g: sum(mean(cells[g, t], "total_tokens") for t in TASKS) if all(cells[g, t] for t in TASKS) else None for g in GROUPS}
    checks = [b_pass >= a_pass + PASS_MARGIN and passes(cells["B", "gap"]) >= GAP_PASSES,
              b_fmt * FORMAT_DIVISOR <= a_fmt,
              totals["B"] <= TOKEN_RATIO * totals["A"] if available else None]
    if missing_tokens:
        checks[2] = None
    # No planned observations cannot establish 0 <= 0 for the format criterion.
    if not planned["A"] or not planned["B"]:
        checks[0] = checks[1] = None
    lights = lambda value: "🟢 達" if value is True else "🔴 未達" if value is False else "⚪ 無資料"
    table(("判準", "燈號", "實際值"), [
        ("① 通過", lights(checks[0]), f"B {b_pass}/{len(planned['B'])} ≥ A {a_pass}/{len(planned['A'])} + 4；B gap {passes(cells['B', 'gap'])}/{len(cells['B', 'gap'])} ≥ 3/5"),
        ("② 格式型被擋", lights(checks[1]), f"B {b_fmt} ≤ A {a_fmt} / 3"),
        ("③ token", lights(checks[2]), f"B 三題平均之和 {fmt(totals['B'], 0)} ≤ A {fmt(totals['A'], 0)} × 1.3"),
    ])
    conclusion = "達標" if all(x is True for x in checks) else "有訊號，再各跑 5 次" if checks[0] is True and checks[1] is True and checks[2] is False else "機制收下、不往 brain 推"
    print(f"結論：{conclusion}" + ("（次數不足；依目前實際次數暫算）" if not enough else "") + "。\n")

    print("雜訊參考：通過分散＝逐次 0／1 的母體標準差；輪數標準差也是母體值。\n")
    table(("組", "題", "通過／失敗", "通過分散 SD", "平均輪數", "輪數 SD"), [
        (g, t, f"{passes(cells[g, t])}／{len(cells[g, t]) - passes(cells[g, t])}", fmt(sd(cells[g, t], "passed")), fmt(mean(cells[g, t], "rounds")), fmt(sd(cells[g, t], "rounds")))
        for t in tasks for g in GROUPS
    ])
    diff_rows = []
    for task in tasks:
        a, b = cells["A", task], cells["B", task]
        a_mean, b_mean = mean(a, "rounds"), mean(b, "rounds")
        # Only pair unambiguous reps; tagged runs may reuse rep numbers.
        by_rep = {g: defaultdict(list) for g in GROUPS}
        for g, data in (("A", a), ("B", b)):
            for row in data:
                by_rep[g][str(row["rep"])].append(row["rounds"])
        pairs = [by_rep["A"][rep][0] - by_rep["B"][rep][0] for rep in by_rep["A"].keys() & by_rep["B"].keys() if len(by_rep["A"][rep]) == len(by_rep["B"][rep]) == 1]
        diff_rows.append((task, fmt(a_mean - b_mean if a_mean is not None and b_mean is not None else None), fmt(sd(a, "rounds")), fmt(sd(b, "rounds")), len(pairs), fmt(statistics.stdev(pairs) if len(pairs) >= 2 else None)))
    table(("題", "A−B 平均輪數差", "A 輪數 SD", "B 輪數 SD", "同 rep 配對數", "配對差樣本 SD"), diff_rows)
    print("單組只跑 1 次時母體 SD 為 0，尚不能估計重跑雜訊；配對差不足 2 筆用 —。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runsdir", type=Path)
    args = parser.parse_args()
    try:
        report(read_summaries(args.runsdir))
    except ValueError as exc:
        print(f"compareab: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
