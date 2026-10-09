# aos7-usage

唯讀彙總 node 的 llmcall 回條、budget 帳差與缺口；不修復或改寫 node。

## 第一次跑

```sh
proto7-2/packs/usage/bin/aos7-usage /path/to/node
proto7-2/packs/usage/bin/aos7-usage /path/to/node --by hour
```

預設按 UTC 日期分組；`--by hour` 改按 UTC 小時分組。正常執行在 stdout 輸出恰一行 JSON；node 不是資料夾時退出 2。

## 輸入與輸出

只掃 `llmcall/<budget>/<call>/request.json` 存在的資料夾。`request.request.model` 是字串時作為 model，否則使用 `request.endpoint`；holder 取 `request.holder`。period 取 `raw.json.at` 的 epoch 秒，沒有 raw 時為 `-`。回條的 `used`、`overrun` 欄位都必須存在且為整數或 null；明確的 null 作 0，缺欄位不作 0。缺回條列 `no_receipt`，壞 JSON 或無法解讀的欄位列 `bad_json`，正數 overrun 列 `overrun`；無效整筆不計 groups 或回條合計。

`groups` 按 model、holder、period 排序；`gaps` 按 budget、call_id、why 排序。`budgets` 包含 llmcall 與 budget 目錄中的 budget，`receipts_used` 只計已納入 groups 的回條；ledger 的 used 缺失、無效或為布林值時，`ledger_used` 和 `diff` 都是 null。`diff` 是 ledger used 減 receipts used。

程式在 [aos7_usage.py](aos7_usage.py)，薄入口在 [bin/aos7-usage](bin/aos7-usage)，測試在 [tests/test_usage_aggregation.py](tests/test_usage_aggregation.py)。
