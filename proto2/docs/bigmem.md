# 大記憶與 JSON ref

這輪有兩包工具。另有一個 SQLite 記憶世界。

## ref 包

在 `tools.json` 的 `packs` 加 `ref`。

- `ref_expand(ref, path?, max_chars?)`：讀回指標。`path` 可寫 `#/choices/0`。預設最多 6000 字。硬上限 20000 字。
- `ref_collapse(message_index)`：手動收起一則 JSON。序號從 0 開始。
- `ref_list()`：列最近 20 個指標。

工具結果轉成 JSON 後超過 6000 字，`on_act` 會先存進 `<home>/refs/<id>.json`。
下一次問模型前，原文會換成 `ref://<id>`、200 字預覽和原字數。
截短的展開結果會明說它只是文字片段。

只在真的需要原文時展開。一般工具不用懂 ref。

## bigmem 包

在 `tools.json` 的 `packs` 加 `bigmem`。

- `mem_put(text, tags?)`：存一筆。
- `mem_find(query, limit?)`：找文字或標籤。預設 10 筆，最多 50 筆。
- `mem_get(id)`：讀完整一筆。
- `mem_forget(id)`：刪一筆。
- `mem_archive_history(from, to)`：歸檔一段對話。頭尾都算。序號從 0 開始。

這些工具不等資料庫。
它們先回 `queued` 和請求編號。
排完就先回話，不要在同一輪輪詢。
agent 回到 idle 後才會收結果。
記憶世界處理完後，結果會進 `inbox/mem/`。
歸檔只有在資料庫回成功後，才把原對話換成 `已歸檔 id=…`。

## 設定

在 agent 的 `llm.json` 加記憶世界路徑：

```json
{
  "dir": "../llm",
  "mem_dir": "../memory"
}
```

也可以設 `AOS_MEM_DIR`。
`llm.json` 的 `mem_dir` 優先。
相對路徑從 agent 世界算。

記憶世界的 `.aos/inst` 只有一句：

```text
aos-mem exec .
```

每格讀 `requests/*.json`。
操作只有 `put`、`find`、`get`、`forget`。
結果寫到同名的 `results/`。
原請求搬到 `requests/done/`。
資料放在 `store.sqlite`。

## 什麼時候用

眼前只是太大的工具 JSON，用 ref。
日後還會查、要跨 agent 共用，用 bigmem。
要縮短一大段舊對話，用 `mem_archive_history`。

門檻已定為 40000 字先歸檔舊原文，80000 字先停問模型並硬歸檔最舊一半。
這輪的骨架先提供手動歸檔。
自動停問需要共用 agent 多一個送 LLM 前的攔截接點。

## 坑

現有 `on_act` 不能改工具回傳值。
所以 ref 在 `on_act` 存檔，再由 `on_system_prompt` 在下一次送模型前換指標。

記憶結果只在 agent 的 idle 格收。
剛排隊時看不到結果是正常的。
如果模型在同一輪不停查信箱，它會等不到。工具包提示已叫它先回話。

SQLite 搜尋目前只是 `LIKE`。
資料很多後會慢。
同一請求重送、備份、權限與徹底刪除都還沒做。

## 之後換 MongoDB

保留 requests/results 格式與 bigmem 包。
只換 `aos-mem` 裡的儲存層。
用一個共用 `memories` collection，以 `agent` 欄位區分。
主程式用獨立 venv 裡的 `pymongo`。
連線字串只從環境變數讀。
`mongosh` 只給人檢查。
