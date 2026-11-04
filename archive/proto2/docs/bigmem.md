# 大記憶與 JSON ref

這輪有兩包工具。另有一個 SQLite 記憶世界。

## ref 包

在 `tools.json` 的 `packs` 加 `ref`。

- `ref_expand(ref, path?, max_chars?)`：讀回指標。`path` 可寫 `#/choices/0`。預設最多 6000 字。硬上限 20000 字。
- `ref_collapse(message_index)`：手動收起一則 JSON。序號從 0 開始。
- `ref_list()`：列最近 20 個指標。

工具結果轉成 JSON 後超過 6000 字，`on_act` 會存進 `<home>/refs/<id>.json`，當格就把模型看到的結果換成 `ref://<id>`、200 字預覽和原字數。
截短的展開結果會明說它只是文字片段。

只在真的需要原文時展開。一般工具不用懂 ref。

## bigmem 包

在 `tools.json` 的 `packs` 加 `bigmem`。

- `mem_put(text, tags?)`：存一筆。
- `mem_find(query, limit?)`：找文字或標籤。預設 10 筆，最多 50 筆。
- `mem_get(id)`：讀完整一筆。
- `mem_forget(id)`：刪一筆。
- `mem_archive_history(from, to)`：歸檔一段對話。頭尾都算。序號從 0 開始。

這些工具先回 `queued` 和請求編號，agent 隨即睡著。
共用層收回結果後直接喚醒，不用輪詢；副本在 `<home>/side/mem/`。
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

`on_act` 可直接回替代值。若同時開成本包，包的先後會決定 cost 看原文還是短指標。

SQLite 搜尋目前只是 `LIKE`。
資料很多後會慢。
同一請求重送、備份、權限與徹底刪除都還沒做。

## 之後換 MongoDB

保留 requests/results 生產格式與 bigmem 包；只有共用層搬結果。
只換 `aos-mem` 裡的儲存層。
用一個共用 `memories` collection，以 `agent` 欄位區分。
主程式用獨立 venv 裡的 `pymongo`。
連線字串只從環境變數讀。
`mongosh` 只給人檢查。
