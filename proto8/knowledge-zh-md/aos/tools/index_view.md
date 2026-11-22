# `knowledge/aos/tools/index_view.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/index_view.md`，跟到正本 commit `677e79b50`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/index_view.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool index_view`**

# 工具 index_view

透過節點的 index 來看它：agent 對它底下有什麼所記的筆記，每個條目一行 `KEY<TAB>description`。index 是一種視角，不是事實：條目可能缺漏或過時。要看實際上有什麼，用 `ls` 或 `json_ls`。

```json
{"path": "knowledge/aos/tools", "key": "json_set.md"}
```
印出
```text
[index] knowledge/aos/tools/_index.json, 58 entries
json_set.md	Tool json_set: ...
```

- 一個節點的 index 放在哪裡（它的自然位置）：資料夾 `DIR` 有 `DIR/_index.json`；JSON 檔 `FILE` 有 `FILE#/_index`；物件 `FILE#/POINTER` 有 `FILE#/POINTER/_index`。index 也可以放在 `_metainfo` 裡面當它的 `index` 鍵（`DIR/_metainfo.json#/index`、`FILE#/_metainfo/index`、`FILE#/POINTER/_metainfo/index`）；兩個都有時，先讀 `_metainfo` 裡的那個，再把獨立的 `_index` 疊上去（同一個鍵以 `_index` 為準）。第一行 `[index] ...` 一定會寫出讀了哪些地方。壞掉的 `_metainfo`（讀不了、不是物件，或它的 `index` 不是物件）會被跳過，不算錯誤：第一行最後會多一句說明，例如 `(_metainfo.json could not be read, skipped)`。
- 鍵可以接回一條路徑：`DIR/KEY`（資料夾）、`FILE#/KEY` 或 `FILE#/POINTER/KEY`（JSON）。鍵照寫的原樣印出。
- `index` 讀你指名的一張 index 表（例如你自己的視角）。單獨用：只讀那一張。加上 `path`：疊在自然 index 上；同一個鍵以指名的那張為準（整個條目），只在指名那張裡有的鍵加在最後。
- 一個條目也可以帶 `"index": PATH`，一條指向另一個 index 的路徑（`cli/_index.json`、`packs.md#/_index`）；它會顯示成第三欄 `index: PATH`。條目裡也可以放任何其他的鍵；index_view 只讀 `description` 和 `index`，其餘的不印（用 `json_get` 看）。條目是物件（`"a.md": {"description": "..."}`）、單純的字串（`"a.md": "..."`：那個字串就是說明），或 `{"$ref": PATH}`（條目或它的說明從那裡讀）；`_index.json`、JSON 檔裡的 `_index` 和 Markdown 的 index 都一樣。其他東西（數字、陣列、null）只會印出鍵，沒有警告，以 0 結束。`description` 是字串，或字串的陣列（每個一行：`{"description": ["First line.", "Second line."]}`）：這些行會接起來印在那個條目的同一行上，換行和 tab 顯示成空白。空陣列，或陣列裡有任何不是字串的東西，就不算說明：只會印出鍵。JSON 檔裡的 `_index` 本身也可以是這樣一個路徑字串；這時輸出是一行 `[index link] FILE#/_index points to PATH (not followed; ...)`。寫在那裡的 PATH 跟 `$ref` 守同樣的規則：`#` 左邊是檔案路徑，從放它的那個 JSON 檔所在的資料夾算起（`./`、`../`、絕對路徑）；`#` 右邊是 JSON 裡面：`#/a/b` 從檔案的根算起，`#./b` 從放這個字串的物件算起，`#../c` 從那個物件再往上一層算起（可以重複；超過根就是錯的），`#` 或 `#/` 是整個檔案。`#aaa`、`y.json#./x` 和 `y.json#../x` 是錯的。放這個字串的物件，對 `_index` 字串來說，是它所在的那個物件（`FILE#/o/p/_index` 裡的 `#./sub/_index` 就是 `FILE#/o/p/sub/_index`）；對條目的 `index` 來說，是那個條目本身（`_index/KEY`），所以兄弟節點的 index 要寫成 `#../../sub/_index`。沒有 `#` 的檔名就只是那個檔案：`x.json` 是這個檔案旁邊的 `x.json`（`_index.json` 從它所在的資料夾算起）。印出來的 PATH 已經從你的工作區接好了。什麼都不會跟著走：要讀它，用 `{"index": PATH}` 再呼叫一次。
- `key`：只要那個條目（整個鍵，不能用樣式）；不存在＝`[no entry] KEY`。
- Markdown：沒有 `_index.json` 的資料夾可以改放 `_index.md`（一份 `NAME: one sentence` 項目的清單；只在沒有 `_index.json` 時才讀）。`.md` 檔，或它的某一節，它的 index 放在名為 `_index` 的標題底下，沒有的話就是名為 `index` 的標題：同樣的那種清單。index 不必列出資料夾裡的所有東西。
- 沒有自然 index＝`[no index] ...`（以 0 結束）：沒有人在那裡寫過視角；用 `ls`／`json_ls`。指名的 `index` 不存在則是錯誤。
- 分頁跟 json_ls 一樣：`limit`（預設 200，或環境變數 `AOS_JSON_MAX_ITEMS`）、`offset`，最後一行 `[more] ...`。

要改 index，就用 json 工具改 `[index]` 那一行寫的地方：`json_set {"path": "d/_index.json#/a.json", "value": {"description": "..."}}`（新的資料夾 index：先對 `d/_index.json` 做 `json_set`，值為 `{}`）；含有 `/` 的鍵要用 `~1` 寫，例如 `d/_index.json#/data.json#~1items~10` 就是鍵 `data.json#/items/0`。用 `json_del` 刪掉一個條目。

指名的 `index` 加上 `path`，而那個 path 的自然 index 不存在時：第一行最後會是 `(natural index: ... does not exist)`。某個條目的 `index` 欄壞掉時，只在那一行印 `index: bad (...)`；其他條目照常。`_metainfo` 的說明只在有讀到某個 index 時才出現。

錯誤：`IndexBad`（index 不是 JSON 物件，或是個不合法路徑的字串）、`FileMissing`／`FileBad`／`PointerMissing`（節點或指名的 index 不存在或不是 JSON）、`PointerBad`、`ArgumentsBad`。其他代號：`WsMissing`、`LaunchFailed`、`CommandFailed`（`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`）。
