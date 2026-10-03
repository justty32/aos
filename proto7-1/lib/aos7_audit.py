"""讀寫入紀錄：把空間裡所有任務的 `writes.jsonl` 拼起來，挑出寫到「自己的 node 與掛載點」之外的（spec.md 第 5 節）。

紀錄由 lib/audit_site/sitecustomize.py 在任務裡寫（環境有 AOS7_AUDIT 才寫）。
"""
import os

from aos7_fs import read_jsonl


def scan(root):
    """回 {"tasks": 有紀錄的任務數, "writes": 寫入筆數, "bad": [(任務資料夾, 紀錄)], "bad_lines": 讀不懂的行數}。

    走實體資料夾、不跟符號連結（掛載點不會讓同一份紀錄被數兩次）。壞行（半行 JSON、半個 UTF-8 字元）只跳過那行、
    計進 `bad_lines`，不讓整個掃描失敗（astra-7 H-04）。"""
    out = {"tasks": 0, "writes": 0, "bad": [], "bad_lines": 0}
    for d, _, files in os.walk(os.path.abspath(root)):
        if "writes.jsonl" not in files or "birth.json" not in files:
            continue
        recs, nbad = read_jsonl(os.path.join(d, "writes.jsonl"), with_bad=True)
        out["tasks"] += 1
        out["writes"] += len(recs)
        out["bad_lines"] += nbad
        out["bad"] += [(d, r) for r in recs if isinstance(r, dict) and not r.get("ok")]
    return out
