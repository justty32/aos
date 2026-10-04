# 稽核包（audit）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)

**可選的寫入紀錄**：任務是 Python 程式時，記下它每個「寫」的動作，事後挑出寫到「自己的 node 與掛載點」之外的（S-10「只碰給的資料夾」沒有強制，這裡只記不擋）。

| 項目 | 內容 |
|---|---|
| 接法 | B 包裝程式：tasks.json 項目的 argv 寫成 `aos7-audit -- <argv...>`（設 `AOS7_AUDIT=1`、把 `audit_site/` 放到 `PYTHONPATH` 最前面，再 exec argv）。核心不知道稽核 |
| 預設 | 關 |
| 依賴 | 無 |
| 程式 | `aos7-audit`（包裝程式）、`audit_site/sitecustomize.py`（任務裡的 audit hook，寫 `$AOS7_TASK/writes.jsonl`）、`aos7_audit.py`（`scan(root)` 掃全空間的紀錄） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/audit/tests`） |

## 規則

- 例：`{"name": "w", "argv": ["python3", "<proto7-2>/modules/audit/aos7-audit", "--", "python3", "job.py"]}`。
- 紀錄每筆 `{"op", "path"（實際位置）, "ok", "pid", "via"}`；只記空間根底下的寫入。`ok`＝落在自己的 node（扣掉巢狀的別的 node／daemon 根）或某個掛載目標底下。`aos7_audit.scan(root)` 把全空間的紀錄拼起來，挑出 ok 是 false 的。
- `writes.jsonl` 也只留這次 run（換 run 時 tick 清掉）。

## 界線

- 只看得到 Python 程序；sh、C 程式的寫入看不到。只記不擋：S-10「只碰給的資料夾」仍是合作式的。
- 繞過包裝（argv 沒加 `aos7-audit`）就沒有紀錄；以前核心照任務環境的 `AOS7_AUDIT` 自動加，現在核心不知道稽核（方案第 6 節）。
