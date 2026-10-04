# 稽核包（audit）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)

**可選的寫入紀錄**：任務是 Python 程式時，記下它每個「寫」的動作，事後挑出寫到「自己的 node 與掛載點」之外的（S-10「只碰給的資料夾」沒有強制，這裡只記不擋）。

| 項目 | 內容 |
|---|---|
| 接法 | 現在：環境變數 `AOS7_AUDIT`（aos7-run 看到就把 `audit_site/` 放進任務的 `PYTHONPATH`）；之後改成 argv 包裝程式 `aos7-audit -- <argv>` |
| 預設 | 關 |
| 依賴 | 無 |
| 程式 | `audit_site/sitecustomize.py`（任務裡的 audit hook，寫 `$AOS7_TASK/writes.jsonl`）、`aos7_audit.py`（`scan(root)` 掃全空間的紀錄） |

- 紀錄每筆 `{"op", "path"（實際位置）, "ok", "pid", "via"}`；只記空間根底下的寫入。`ok`＝落在自己的 node（扣掉巢狀的別的 node／daemon 根）或某個掛載目標底下。
- 只看得到 Python 程序；sh、C 程式的寫入看不到。`writes.jsonl` 也只留這次 run（換 run 時 tick 清掉）。
- 沒有專門測試（P2-17）。
