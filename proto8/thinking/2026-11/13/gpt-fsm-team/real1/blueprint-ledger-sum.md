# 真工作圖紙：ledger_sum.py（llm kernel 用量加總）

← [gpt-fsm-team 入口](../../gpt-fsm-team.md)

gpt 隊（astra 指揮、sol 施工）的第一件真工作。用途：把 llm kernel 的 `ledger.jsonl` 按「端點包 × 寄件人」加總呼叫次數與 token，給 05 的 Q1（gpt 隊值不值）回頭看用量。

## 1. 要新增的檔（只有這兩個，其他任何檔都不動）

- `proto8/thinking/2026-11/13/gpt-fsm-team/real1/ledger_sum.py`
- `proto8/thinking/2026-11/13/gpt-fsm-team/real1/testdata/ledger-sample.jsonl`

## 2. ledger_sum.py 的行為

- Python 3，只用標準庫。檔頭第一行是 `#!/usr/bin/env python3`，第二行是一行註解說這支做什麼（`# ledger_sum.py：...`）。
- 用法：`python3 ledger_sum.py <ledger.jsonl 路徑>`。參數不是剛好一個：stderr 印 `usage: ledger_sum.py LEDGER.jsonl`，退出碼 2。
- 檔案讀不到：stderr 印 `ledger_sum: cannot read <路徑>: <原因>`，退出碼 2。
- 一行一筆 JSON。行號從 1 起算，空行也算行號：
  - 空行（只有空白）略過，不印任何東西。
  - 不是 JSON、或不是 JSON 物件的行：stderr 印 `ledger_sum: line <行號>: not JSON, skipped`，繼續往下讀。
  - 每筆取 `endpoint`、`sender`（沒有就當成 `-`），以及 `usage.total_tokens`（`usage` 沒有、或裡面沒有 `total_tokens`，就當成 0）。
- 輸出到 stdout：每個（endpoint, sender）組合一行 `<endpoint> <sender> <呼叫數> <token 總數>`，欄位之間一個空白；先按 endpoint、再按 sender 字串排序。最後一行是 `TOTAL - <全部呼叫數> <全部 token>`。退出碼 0。

## 3. 測試資料 testdata/ledger-sample.jsonl

內容逐字如下（共 7 行；第 3 行是故意壞的，第 5 行是空行）：

```
{"endpoint": "astra-high", "sender": "/t/a", "usage": {"total_tokens": 100}}
{"endpoint": "sol-high", "sender": "/r", "usage": {"total_tokens": 50}}
not json
{"endpoint": "sol-high", "sender": "/r", "usage": {"total_tokens": 70}}

{"endpoint": "astra-high", "sender": "/t/a"}
{"endpoint": "sol-high", "sender": "/t/a", "usage": {"total_tokens": 5}}
```

## 4. 驗收

在 repo 根目錄跑：

```
python3 proto8/thinking/2026-11/13/gpt-fsm-team/real1/ledger_sum.py proto8/thinking/2026-11/13/gpt-fsm-team/real1/testdata/ledger-sample.jsonl
```

stdout 逐字是：

```
astra-high /t/a 2 100
sol-high /r 2 120
sol-high /t/a 1 5
TOTAL - 5 225
```

stderr 逐字是 `ledger_sum: line 3: not JSON, skipped`，退出碼 0。

另外：路徑給 `/nonexistent.jsonl` 時退出碼 2、stderr 以 `ledger_sum: cannot read /nonexistent.jsonl:` 開頭；不給參數時退出碼 2、stderr 是 usage 那一行。

## 5. 拆單

一張工單就夠。
