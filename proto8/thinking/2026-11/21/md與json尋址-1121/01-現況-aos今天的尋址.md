# 現況：aos 今天「用路徑拿到一段內容」有八種，每種要求來源長什麼樣

← [README](README.md)｜上一份：[00-使用者原話](00-使用者原話.md)｜下一份：[02-md天然結構](02-md天然結構對到json.md)

## 先講一個關鍵事實：知識庫已經是「json 外殼、markdown 內容」

`proto8/knowledge/` 共 156 份 json（4 份是 `_index.json`）。實際數過：

| 數什麼 | 數量 |
|---|---|
| 字串值 | 441 |
| 其中開頭就是 `# 標題` 的（一整段 markdown） | 244 |
| 字串陣列（一行一個元素，等於一段文字） | 110 |
| `$ref`（拆檔留的路） | 13 |
| 其他（數字、物件陣列…） | 31 |

例：`aos/me.json` 打開是 `{"_description": "# Who am I\n\n…", "stack": "# What is in your stack\n\n…", "self_tools": {"$ref": "me/self_tools.json"}, …}`。**每個鍵的值本來就是一篇 md，json 只負責給它一個名字（路徑）**。人覺得難看，主要是因為 md 被包成一行字串，換行變成 `\n`、引號變成 `\"`（`me.json` 裡有 165 個這種跳脫）。

`wf/` 和 thinking 夾的資料檔不一樣：多半是 `wf-table/1` 的表（`rows` 陣列，每列同一組欄位，格子是長中文），或 `wf/progress.json` 這種「一條一個鍵、每條七個欄位」。這兩種才是真的資料，不是包起來的文章。

## 八種尋址

| # | 叫法 | 長什麼樣 | 誰在用 | 來源要什麼 |
|---|---|---|---|---|
| 1 | 統一路徑（JSON 指標） | `aos/me.json#/stack`、`x.json#/rows/3/how` | `json_get`／`json_ls`／`json_set`…、`aos-json`、`aos-json-view` | 合法 JSON；`#` 右邊照 RFC 6901，鍵用 `/` 接、陣列用數字、`~1`＝`/`、`~0`＝`~` |
| 2 | `$ref` | `{"$ref": "me/self_tools.json"}`、`#./`、`#../` | `aos-directive`（aos-exec、loop、daemon、fsm 讀設定都經它）、`jsonx_*` | 指到的檔必須是 JSON，不是就 `DirectiveBad` |
| 3 | `$env`（＋`$path`、`$prefix`） | `{"$env": "AOS_STACK", "$path": "out"}` | 同上 | 環境變數，不是內容尋址；列出來只是因為同屬指示詞 |
| 4 | `AOS_CF`／`AOS_CO` | `AOS_CF`＝正在跑的那份檔，`AOS_CO`＝檔裡的位置（JSON 指標、不帶 `#`） | aos-exec 每層覆寫 | 不是 JSON 時 `AOS_CO` 是空字串 |
| 5 | index（`index_view`） | `_index.json`／`#/_index`／`_metainfo` 的 `index`：`{"鍵": {"description": "一句"}}` | agent 往下找東西的主路 | index 本身是 JSON；**被描述的東西可以是 .md**（thinking 每天的 `_index.json` 就列一堆 .md）；鍵接回路徑是 `夾/鍵` 或 `檔#/鍵` |
| 6 | `tabledb.py` | `tabledb.py x.json get 3`、`find id=7` | `wf/` 的資料檔（鐵律 6） | `wf-table/1` 的 JSON 或扁平 CSV |
| 7 | `index_gen.py` 的「一句話」 | md 取**第一個標題**，json 取 `_description` 那段 md 的標題 | 重生 `_index.json` 與 code map | **已經會讀 md 的結構**（只讀第一個標題） |
| 8 | md 錨點 | `x.md#標題錨`、`<a id="…"></a>` | 人點的連結；STRUCTURE 拆檔時在原檔留 `<a id>`，舊錨照樣通 | GitHub 把標題轉成錨的規則（小寫、空白變 `-`、標點拿掉、中文保留、重名加 `-1`） |

另有 `read`、`grep`、`view` 這些讀整檔或搜字的工具，不算尋址。

## 讀出來的幾點

- **「aos index 方便查找」今天只到「檔」這一層會碰到 md**：index 可以描述一份 .md，但 index_view、`json_get`、`$ref` 都進不了 md 裡面。想拿 md 裡的一節，今天只能 `read` 整份或 `grep`。
- **第 8 種是人在用的 md 尋址，已經大量存在**：repo 裡到處是 `xxx.md#某標題` 的連結，拆檔規矩還特地保住舊錨。它跟第 1 種長得很像（`檔#位置`），但規則不同：md 錨是把標題字壓成一串（`#第-1-題eca_main-傳來的話算不算你的授權`），沒有層級；JSON 指標有層級、照鍵原字。
- **看 json 的程式已經有一支**：`aos-json-view`（11-13 做的，只讀）把字串裡的 `\n` 真的換行、鍵對齊、字串陣列當一段、`$ref` 印 `→`、照終端寬度折中文。它在終端裡已經把知識庫頁印得像 md。它解不了的是：在編輯器、GitHub、檔案總管直接打開 .json 的時候。樣子見 [06](06-往返與最短解.md)。
- 第 1、2、5、6 種**全部要求來源是 JSON**；要讓它們「進得了 md」，不是改 md，就是在這幾支程式前面加一層「把 md 讀成樹」的東西。這就是 [03](03-做法.md) 各做法的分岔點。
