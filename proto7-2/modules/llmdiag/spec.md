# llmdiag 檔案與輸出協定

入口：`aos7-llmdiag <node>`。正常退出碼為 0，stdout 恰一行 JSON；node 不是資料夾時退出碼為 2。

- `llmcall/<budget>/<call>/request.json` 是合法 JSON 物件，且同目錄沒有 `receipt.json`：列入 `llmcall_pending`。同目錄有 `raw.json` 時 `stage` 為 `raw`，否則為 `request`；兩檔均只看存在，不解析。
- `jobs/<job>/frame.json` 是 JSON 物件、`phase` 為 `halted`、job 名稱以 `_` 加恰好八位十六進位字元結尾，且 `author/req/<rid>/` 是資料夾：列入 `author_halted`。`rid` 是去掉該後綴的 job 名稱，`kind`、`why` 取自 `halt` 物件；缺少欄位時輸出 JSON null。
- `budget/<budget>/ledger.json` 是 JSON 物件，且 `inflight` 為大於零的整數（不含布林值）：列入 `budget_inflight`。

輸出物件包含 `v: 1`、`llmcall_pending`、`author_halted`、`budget_inflight`。各列欄位依序為 `(budget, call_id, stage)`、`(job, rid, kind, why)`、`(budget, inflight)`；三表分別依 `(budget, call_id, stage)`、`job`、`budget` 排序。讀取失敗、壞 JSON 或非物件的 request、frame、ledger 均略過。
