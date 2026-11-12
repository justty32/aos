# json 工具第二輪：一次多格 json_multi_get／set、複雜組補 jsonx_ls／search／del、刪 json_rewrite

← [json-tools](README.md)｜前一份：[02-施工結果](02-施工結果.md)｜圖紙 [01-規劃](01-規劃.md) §6「之後」

## 使用者原話（11-12，頂層轉來）

頂層列三項後續（一次讀寫多格、複雜組的 ls／search／del、舊的 `json_rewrite` 要不要留），使用者答：

> 「json_read/write都不用留了。一次讀寫多格、複雜組的json工具可以做。」

頂層讀法「都不用留」含 json_rewrite，向使用者確認，使用者答：

> 「json_rewrite也不用留」

11-11 已定照舊：「有需要的話，可以提供工具json_multi_get/set。」（[11-11 json-tools](../../11/json-tools.md)）

## 做了什麼

- **簡單組多兩支**（`lib/base/json_multi_get`、`json_multi_set`，進 json 包；邏輯在新檔 `lib/aos_json_multi.py`，每格叫 `lib/aos_json.py` 原本的 get／set）：
  - `json_multi_get {"paths": [...], "max_bytes"?, "full"?}`；`json_multi_set {"items": [{"path", "value"}...], "parents"?}`。
  - 一格一行 `路徑 TAB 結果`：get 的結果＝json_get 會印的（值、`[too big] …`）；set 的結果＝`ok …`；那格錯＝`[error] 代號 原因`。
  - 有任何一格錯：最後一行 `json_multi_*: error: PlacesFailed N of M places failed …`、退 1；stderr 只有這行（加上 aos-json 自己的錯誤行）。
- **複雜組補三支**（`lib/aos/jsonx_ls`、`jsonx_search`、`jsonx_del`，進 jsonx 包，範本照舊不掛）。
- **刪 `lib/agent/json_rewrite`**：沒有包、範本、測試掛它；C-52 例外名單（CONCEPTS 兩份、conventions）、lib 索引與契約、aos-json README 與 docs/02、impls/docs/01 跟上。
- **範本支數**：json 包多兩支，agent-fsm 45 → 47、eca-claude 24 → 26（`aos-tools --file … ls` 實數過）；兩個 `tools.json` 沒動（疊的是整包）。README、templates/docs/01、知識庫 packs 跟上。
- **知識庫**：五個新節點（`aos/tools/json_multi_get.json`、`json_multi_set.json`〔帶 multi 兩支的 errors〕、`jsonx_ls.json`、`jsonx_search.json`、`jsonx_del.json`）、`_index`、packs、`jsonx_set.json#/errors` 標題擴到六支。
- 順手：`jsonx_get` 的 `follow` 說明原本寫「路上與指到的 `$ref` 都穿過」，實際 `aos-json get --follow` 只穿過路上的；tooldef 與知識庫改成「on the way to the value」。

## 代定（接 D30，可翻案）

- **D31 multi 逐格做、不回滾**：每格各叫一次 aos-json（同一份檔多格＝多次原子寫入），照給的順序；一格錯不擋後面、前面寫好的不撤回。沒用 `aos-json batch`（同檔原子，但沒有 `--raw`、跨檔也不原子），頂層指示「偏向簡單」。
- **D32 有格錯＝退 1、`PlacesFailed`**：lib 契約「有錯誤行不退 0」；其他格的結果行照印在前面，腦只要重送 `[error]` 那幾格。代號照 C-54 推薦的「動作＋Failed」。
- **D33 整批參數錯不做任何一格**：`paths`／`items` 不是非空陣列、`max_bytes` 不是正整數＝只有一行 `ArgumentsBad`；**一格內**的錯（item 不是 `{"path","value"}`、多了別的鍵、沒 `value`、路徑空）算那一格的 `[error]`，其他格照做。
- **D34 multi 的形狀**：get 收字串陣列 `paths`；set 收物件陣列 `items`，每項只認 `path`、`value`；`parents`、`max_bytes`、`full` 是整批一個（不做每格各自的選項，少一層要記的）。不設上限支數（每格已有 `max_bytes`；真腦有需要再加）。
- **D35 複雜組不做 multi**：列進「以後」。
- **D36 jsonx_ls**：`follow`（路上穿過 `$ref`；指到的那格是 `$ref` 時照原樣列，同 `aos-json get --follow`）、`resolve`（列解開後的值，例 tools.json 疊完的工具表）；兩個都說得通，都加。
- **D37 jsonx_search**：`follow`、`resolve` 都加：從穿過／解開後的那格往下找，命中路徑寫成腦給的那份檔的路徑（拿去 `jsonx_get` 加 `follow` 讀得到）；**不配 `up`**（`ArgumentsBad`）：`$ref` 那格的「上一層」在另一份檔，說不清。
- **D38 jsonx_del**：只有 `follow`（`aos-json del --follow`：刪在被參照的檔、合併來源裡對應的鍵也刪）；不給 `follow` 時路上有指示詞＝`FollowMissing`（同 jsonx_set 的保護）；`resolve` 對刪除沒有意義、`check` aos-json del 不收，都不加。
- **D39 multi 程式另開 `lib/aos_json_multi.py`**：`aos_json.py` 已過 300 行（照 01 §6「超過就拆」）；`aos_json.py` 加一個 `MULTI` 開關讓 `die` 改丟例外，multi 抓下來記成那格的結果。

## json_rewrite 刪掉後新工具做不到的

- 它是「給一句話、自己去問腦改」（`{"file", "want"}`，靠 `AOS_LLM_KERNEL` 另叫一次腦，腦 peek 找位置再逐格給新值）。新工具都要叫用的腦自己決定改哪格、什麼值；沒有「把一句話交給別的腦去改 JSON」這條路。沒有任何包或範本掛它，使用者說不用留，照刪。

## 驗證

- `lib/tests` 49 支全過（`test_json_tools.py` 多 `test_aos_ls_search_del`、`test_multi_get`、`test_multi_set`）；knowledge_check、metainfo_check、self_tools、tools_def、defs 的測試全過；templates 全套見當天日誌。
- 真腦（公司 WSL，`/tmp/json-multi-1112` 臨時樹、eca-claude 範本照抄、`llm.json` 換 haiku，`aos-eca-turn` 直接跑、不掛 daemon）：叫它「用一次 json_multi_get 讀三格（其中一格不存在）」——只叫一次 `json_multi_get`，三格照實回（`"bob"`、`"act"`、`nope` 是 PointerMissing）。臨時樹留著沒刪。

## 要重建什麼

- agent 自己的覆蓋層若單獨寫過 `json_rewrite` 那格，要刪掉（資料夾不在了）。範本的 agent 重建即可。

## 以後

- 複雜組的 multi、aos-json 本身的 add／ls／search、`json_len`：做了，見 [04](04-aos-json下沉與len與jsonx-multi.md)。剩 json_ls 的遞迴層數。
