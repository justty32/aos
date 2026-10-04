"""讀寫入紀錄：把空間裡所有任務的 `writes.jsonl` 拼起來，挑出寫到「自己的 node 與掛載點」之外的（spec.md 第 5 節）。

紀錄由 lib/audit_site/sitecustomize.py 在任務裡寫（環境有 AOS7_AUDIT 才寫）。

由人或檢查工具呼叫 scan；唯讀掃描 root 下帶 birth.json 的 writes.jsonl，不改任務狀態。
對應 spec §4.5、§5.1、§5.5（S-10、S-23）；沿用紀錄工具、未另加本版專測（P2-17）。
"""
import os

from aos7_fs import read_jsonl


def scan(root):
    """回 {"tasks": 有紀錄的任務數, "writes": 寫入筆數, "bad": [(任務資料夾, 紀錄)], "bad_lines": 讀不懂的行數}。

    走實體資料夾、不跟符號連結（掛載點不會讓同一份紀錄被數兩次）。壞行（半行 JSON、半個 UTF-8 字元）只跳過那行、
    計進 `bad_lines`，不讓整個掃描失敗（astra-7 H-04）。

    參數 root 是空間根；回傳上述統計，不重新判定每筆路徑的權限（spec §4.5，P2-17）。
    缺紀錄的槽略過；os.walk 讀不到的目錄亦可能略過，因此 bad 為空不保證沒有越界寫入。
    """
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
