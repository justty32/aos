# proto8 規範（三）：指示詞、組合子（tasks、fsm）、kernel、命名與持久檔，一條一兩句

← [（一）總則、時空、inst、loop 與 daemon](../NORMS.md)｜[（二）窗](00-規範-2-窗.md)｜[（四）資料夾程式與執行、待定](00-規範-4-資料夾程式與執行.md)

只放規範本體；例子、原話、出處、細則在每組標題連的分檔，條文以分檔全文為準（待裁網頁 條文-N7 選 A）。

## 指示詞

**[基礎設施／命令列與指示詞](06-基礎設施-命令列與指示詞.md)**
- （無條號）規範層只定 aos-exec 的命令列（N-58），其他程式的形狀是慣例 P-44；`檔#/指標` 是全系統唯一的「指」法，誰認它由各個讀者自己宣告（N-62）。
- **N-45**（草稿）指示詞有兩個：`$env` 與 `$ref`，都可帶修飾欄 `$path`、`$prefix`；帶它們的物件整個換成指到的值（同時寫了只看 `$ref`，其餘 key 忽略）。真的解不開（環境變數沒設、讀不到、指不到、繞圈）＝解單子那一層自己的錯、退 1（`DirectiveBad`）；寫法（格式）寬容、不報錯：不認得的 `$xxx` 不管，換不了的整個物件原封不動留著（有 `$ref` 時不改試 `$env`；頂層自定，待使用者確認）。
- **N-45** `$path` 是字串拼接（`#` 開頭直接接，其他中間剛好一個 `/`）；`$env` 讀執行當下的環境；`$ref` 換成那份 JSON 檔、接著解（11-21 起也可以指到 `.md` 檔：`x.md`＝整份文字，`x.md#/標題` 照 md 現有的標題、清單、表格、只有 json 區塊的節去尋，拿到的值不再往下解；使用者 11-21「用$ref可以」，規則 [thinking 11-21](../../thinking/2026-11/21/知識庫-骨架加md-規劃-1121/07-尋址規則.md)），相對路徑從寫著它的那份檔所在的資料夾算，指到資料夾算讀不到；`#` 左邊一律檔案系統、右邊一律 json 內部（`#/`、`#./`、`#../`；只寫 `#/…`＝寫著它的那份檔）；`$ref` 可寫成陣列＝照順序淺層合成一份：都是物件就合 key（同名 key 後面蓋前面），都是陣列就接起來，種類混在一起＝`DirectiveBad`；`$ref` 是最底層的組裝。
- **N-45** argv 陣列裡也能放指示詞，解完每個元素要是字串（不是＝`EntryBad`）；aos 自己的程式讀的 JSON 一律支援指示詞，每支只解自己讀的那幾格（頂層照原則定）；不做字串內插。

## 組合子（tasks、fsm；標準庫）

**[基礎設施／組合子](07-基礎設施-組合子.md)**（[N-34、N-20、N-36](07-基礎設施-組合子/01-N-20～N-36.md)、[N-38～N-41](07-基礎設施-組合子/02-N-38～N-41.md)）
- （無條號）fsm 不管、使用者自行承擔：每格沒有時間上限（格是 inst 單子且寫了 `timeout_ms` 時由 aos-exec 到時打）、兩隻共用同一個 stack、state 寫不了＝`WriteFailed` 退 1、SIGKILL 留下的孤兒格、無窮轉移只靠 loop 的 `max` 擋、`exec` 的相對路徑從 cwd 算、`.env` 外層贏。
- **N-34**（草稿，現無實作）tasks（`seq`／`par`／`if`）起子程式後看它的結束碼決定往哪走；自己的錯退 1、stderr 一行原因；回子程式的碼是透明轉交；沒有 `aos-not`。
- **N-20**（定稿）巢狀 fsm 出口當掉後重跑時，各格的冪等性不保證、不在規範範圍內；fsm 不記格跑到哪、不做重跑保護。
- **N-36**（定稿）aos-fsm 只管一件事：現在是 A 狀態，就跑 A 那格。表 `{"start": 起始狀態名, "states": {狀態名: {"exec": 格, "next": 下一個狀態名}}}`，`exec` 收字串目標、陣列 `[目標, 參數...]`、單子物件；`next` 是字串或 `{結束碼: 狀態名}` 照碼分岔（細節代定、可翻案）；開跑時查整張表，不合＝表壞、退 1、不跑格。
- **N-38**（定稿）fsm 出錯（格非 0 且物件 `next` 沒接住、查不到格、表壞、state 檔在但讀不了）時 state 不動、以那格的碼退出（自己的錯退 1）；接住的照表走、fsm 以 0 結束（N-36；新舊打架，11-17「新的覆蓋舊的」：N-36 的 10-30 較晚）；格的 stderr fsm 不讀、不轉；連錯幾次要停是格自己數（agent 的格不數）；自己收到訊號先轉給那格、跑完再以 128＋N 結束。
- **N-39**（定稿）fsm 的 state 檔在 `$AOS_STACK/stage.txt`，只記現在狀態名、只有 fsm 自己寫；fsm 不開 ctl、lock（交給跑它的 loop）；不寫 `trace.jsonl`（頂層代定、可翻案）；格指回自己 fsm 不擋。
- **N-41**（定稿）一格怎麼跑是那格的事（同步、非同步都合規）；格自己不 setsid／fork 背景行程，格是單子時由跑單子的那方給新行程群組、逾時打整群、轉訊號；要沙箱就在單子 argv 最前面接 `aos-sandbox`，不另開 session。

## kernel

**[kernel](09-kernel.md)**（[(1) LLM kernel](09-kernel/01-N-42-1-LLM-kernel.md)、[(1) 能力包與份額](09-kernel/02-N-42-1-能力包與份額.md)、[(2) 通用 kernel](09-kernel/03-N-42-2-通用kernel.md)）
- **N-42**（草稿）先做兩種 kernel，都基於 daemon：(1) 管 LLM 呼叫的；(2) 通用管理的（以 agent 作判斷）；兩種收進同一份通用 kernel 框架（現況：框架的骨架、掛 proc 那一包、hook 三個時機在 `py/tools/aos/kernel`，llm kernel 在 `py/tools/aos/kernel_llm`，狀態查詢信由 `aos-agent ctl who` 問；新舊打架，11-14 的現況較晚）；`AOS_LLM_KERNEL` 與 `AOS_KERNEL` 維持兩個變數。
- **N-42** (1)（細節照推薦或代定、可翻案）信帶請求、不帶單子：body＝`{"endpoint"?, "request", "priority"?}`、信封 `reply_to` 必有，回信 body＝`{"message", "usage", "model"}` 或 `{"error": {"code", "msg"}}`；kernel 照 `kernel.json`（`slots`、`budget`、`timeout_ms`、`exec`、`endpoints`、`endpoint`）跑 endpoint 函數，問腦掛成 daemon 的 proc；信箱固定 `$AOS_STACK/requests/`；`aos-llm`（`send`／`recv`／`ask`／`regret`）是基礎工具；`priority.deadline` 寫 ISO 8601（帶時區）或 epoch 秒（待裁網頁 條文-N4 選 A：照實作）。
- **N-42** (1) 能力包（`fixed` 釘死，撞了回 `RequestBad`）；排程看級數＋aging、時限、包的 `speed`；額度到頂回 `BudgetMissing`、不替人降級；kernel 可以嵌套，每層逐封記 `ledger.jsonl`。
- **N-42** (2) 通用 kernel 框架是一包方便零件、不是概念，手寫一個也算 kernel；下一站照三段找：`kernel.json` 的 `next` → `AOS_KERNEL`（指到自己就跳過）→ `AOS_DAEMON`（明寫的 `next` 指到自己＝設定錯，代定）；下一站不是從 `AOS_DAEMON` 來的又設了 `max_running`，就必須寫 `count_daemon`，沒寫＝`CfgBad`；hook 三個時機 `before_verdict`、`after_verdict`、`before_reply`；排隊（`queue`）、有序（`keep_ordered`、`reply_via_me`）都是選項、沒寫＝關；停／收／睡／醒不必過框架站；`aos-daemon-ctl` 一律直寄；ping 原樣轉寄。

## 命名與持久檔

**[命名](命名.md)**（規則在 C-54 命名方法）
- 純文字檔帶 `.txt`；「要跑什麼」一律叫 `exec`；入口預設名 `_entry`，`_` 開頭沒有特別意思；計數一律 `counter_*`；時間點一律 `<發生了什麼>_at`、上限一律 `max_*`（頂層代定、可翻案）；loop 這一系控制自身的窗叫 ctl／state，daemon 管子項的叫 `procs_*`。
- （無條號）概念搬來的檔名與固定名字（`_metainfo`、`interfaces.json`、`tools.json`、`llm.json`、`_index`、`lineage`…）在 [命名（續）](命名-續-概念搬來的檔名.md)。

**[持久檔與暫時檔](附錄4-持久檔.md)**
- 持久檔表只是盤點、不代表要做相容；轉正前照「proto8 當沒有舊版」；正式版當天起，標「持久」的檔加 `format` 版本標記（程式寫的狀態檔一定帶，人寫的配置檔可以不帶），改持久格式寫獨立的升級腳本。
