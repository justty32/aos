← [回入口 README.md](../README.md)｜段落：索引：base、索引：aos｜上一份：[01-分層等](01-分層等.md)｜下一份：[03-索引-agent等](03-索引-agent等.md)

## 索引：base

**分包與路徑**（11-10 tool-packs）：前 15 支通用工具分四包，清單在 [lib/packs](../packs/README.md)——1 看（read、ls、view、stat、grep、glob）、2 改（write、edit、copy、move、mkdir）、3 刪（trash、remove）、4 殼（shell、run_python）；JSON 八支另成 json 包（下表 json_get～json_multi_set；同一族的複雜組 jsonx_* 在「索引：aos」，包 jsonx 範本不掛；11-12 [json-tools](../../thinking/2026-11/12/json-tools/README.md)）；另有小工具包 gadgets（peek_clock、peek_now_time、math，不改任何東西、隨手看一下；11-11 起加 agent 工具 do_task（同日改成 save／load、只給 agent-fsm））。agent 工具也分包（事件、自我管理、子 agent、定義、信箱、記憶），一覽見 [lib/packs](../packs/README.md)。檔案工具的路徑相對從 `$AOS_WS` 算、絕對照用，**不擋工作區外**（使用者「這些就是/usr/bin的包裝」「3.對」），能不能動看 Linux 權限；相對路徑又沒有 `$AOS_WS`＝`WsMissing`。

回 JSON 的工具裡，計數（幾個、幾行、幾字）的 key 一律 `counter_<被數的東西>`（10-25 使用者「計數這塊，幫我改成counter_*」，C-54 命名方法 R6）；陣列本身（`items`、`keys` 清單）不加。

| 工具 | 一句話 | 參數 | 回什麼 |
|---|---|---|---|
| [read](../base/read/) | 讀一個文字檔，太長從頭截 | `path`、`offset`、`max_lines` | 內容（不加行號）；被截時尾巴寫從第幾行接著讀 |
| [write](../base/write/) | 整份寫進一個檔（建或蓋）、上層資料夾自動建 | `path`、`content` | 一行：寫了幾 bytes |
| [edit](../base/edit/) | 幾處照字面替換，一處不合整個不改 | `path`、`edits[{old_text, new_text}]` | 一行：換了幾處 |
| [shell](../base/shell/) | 用 bash 跑一行指令（cwd＝工作區；11-10 由 bash 改名） | `command`、`timeout_s`（30／300） | stdout＋stderr 合在一起、最後一行一律 `[exit code N]`；留最後 2000 行／50KB |
| [ls](../base/ls/) | 列一個資料夾的子項，一次一頁 | `path`、`offset`、`max_items`（100／500）、`hidden`、`long`、`json` | 預設一行一項 `NAME TAB TYPE`（11-10 深夜使用者「2.好」：只列名字與類型）；`long`＝多 `SIZE TAB MTIME TAB INFO`（INFO：資料夾 `children N`、`aos 記號…`，檔 `exec`、`.json` 的 `keys …`，連結 `-> 目標`）；尾巴 `... next_offset N (M items in all)`、`... H hidden (…)`、空資料夾 `... empty`；`json`＝JSON：`counter_items`（一共幾項）、`items[{name, type, size, mtime}]`（資料夾多 `counter_children`、`aos`，檔多 `exec`，`.json` 多 `keys`）、`next_offset`、`counter_hidden` |
| [stat](../base/stat/) | 單一個檔或資料夾的屬性 | `path` | JSON：`type`、`mtime`、`mode`；檔多 `size`、`exec`、`text`、`counter_lines`、`format`、`top` |
| [view](../base/view/) | 漸進看一個檔：JSON 照指標一次一層、大文字檔先給大綱 | `path`、`pointer` 或 `start`／`end` | JSON：`value` 或 `children`；文字的 `text` 或 `outline` |
| [json_get](../base/json_get/) | 拿一格的值（簡單組共通：`path` 一整串 `檔#/指標`，只給 `檔`＝整份（`檔#` 不收、照 aos-json 報 `SpecBad`，11-12 代定 D30）、`檔#/`＝空字串 key（照 RFC 6901，同 aos-json／`$ref`）、相對從 `$AOS_WS`；程式都在 [aos_json.py](../aos_json.py)、各夾只是殼；讀叫 `aos-json get`、寫叫 `aos-json set／append／del --raw`，`$ref`／`$env` 物件當普通物件；aos-json 的錯接它最後一行的代號與原因） | `path`、`max_bytes`（8000，環境變數 `AOS_JSON_MAX_BYTES`）、`full` | 一行緊湊 JSON；超過上限＝`[too big] object, 5 keys, 113 bytes (max_bytes 20). List it: json_ls cfg.json. …`、退 0 |
| [json_ls](../base/json_ls/) | 列一格底下有什麼，像 `ls` | `path`、`long`、`offset`、`limit`（200，`AOS_JSON_MAX_ITEMS`） | 第一行 `object, 5 keys`（陣列 `array, 2 items (index 0..1)`、純值 `number 20`），之後一行一個 key／索引；`long` 多 `TYPE TAB SIZE TAB N bytes`（純值只印值）；分頁尾巴 `[more] 0 to 1 of 5 shown; next: "offset": 2` |
| [json_search](../base/json_search/) | 找 key／value，往下（預設）或往上一層層（`up`，近的先）；不收正規式 | `path`、`key`、`value`（同型別才算）、`contains`（子字串）、`up`、`limit` | 一行一筆 `檔#/指標 TAB TYPE TAB SIZE`；沒中＝`[no match]` |
| [grep](../base/grep/) | 照內容搜（Python `re`，像 `grep -rn`）：整棵樹或一個檔裡哪幾行有這個樣式（11-11 使用者「啊，grep/glob得做」；裁「grep 和 glob 兩支」「純 Python」「預設跳過，問 git」，[new-tools 01](../../thinking/2026-11/11/new-tools/01-grep-glob.md)）。跳過二進位（前 8KB 有 NUL）、超過 8MB 的檔、`.` 開頭的（`hidden`）、git 工作樹裡 `.gitignore` 擋掉的（`gitignore: false` 關；問 `git ls-files`，git 不在＝warning 照搜）；資料夾捷徑不跟進；20 秒或 2 萬項先到先停；走樹共用 [file_walk.py](../base/file_walk.py) | `pattern`、`path`、`glob`、`fixed`、`ignore_case`、`context`（0～5）、`files`、`hidden`、`gitignore`、`offset`、`max_matches`（100／500） | 一行一筆 `PATH:LINE:TEXT`（PATH 可貼回 read、LINE 當 offset；一行最多 300 字元）；`context`＝前後文 `PATH-LINE-TEXT`、組間 `--`；`files`＝`PATH TAB 中幾行`；尾巴 `... next_offset N (M matches in K files in all)`／`(at least …)`、`... skipped …`、`... stopped after …`、`... no matches`；錯 `PatternBad`、`FileMissing`、`ReadFailed` |
| [glob](../base/glob/) | 照檔名樣式找檔：`*` 一層、`**` 任意層、`?`、`[abc]`；不含 `/` 的樣式＝任何深度比檔名（同上出處）。隱藏、gitignore、捷徑、預算同 grep | `pattern`、`path`、`type`（file／dir／any）、`sort`（name／mtime）、`hidden`、`gitignore`、`offset`、`max_items`（100／500） | 一行一個路徑（資料夾結尾 `/`）；尾巴 `... next_offset N (M paths in all)`、`... stopped after …`、`... no matches`；錯 `PatternBad`、`FileMissing`、`FileBad`（path 是檔） |
| [json_set](../base/json_set/) | 把一格換成這個值（沒有的 key 就加）；值照字面；結尾 `/-`＝陣列尾巴加；只給檔＝整份換或建新檔 | `path`、`value`、`parents`（路上沒有的物件建出來） | `ok cfg.json#/tags/2`；錯例 `PointerMissing no such pointer: cfg.json#/a/b (the root has no a; give "parents": true …)` |
| [json_add](../base/json_add/) | 加新的、不蓋：物件已有＝`KeyExists`；陣列 `…/2` 插在第 2 項前、`…/-` 加尾巴；只給檔＝建新檔 | `path`、`value`、`parents` | `ok 檔#/指標` |
| [json_del](../base/json_del/) | 刪一個 key 或陣列一項，要存在；不刪整份（`TargetBad`） | `path` | `ok 檔#/指標` |
| [json_multi_get](../base/json_multi_get/) | 一次拿多格（11-12）：逐格照 json_get、照順序；程式在 [aos_json_multi.py](../aos_json_multi.py) | `paths`（陣列，至少一格）、`max_bytes`、`full` | 一格一行 `路徑 TAB 值`（或 `[too big] …`、`[error] 代號 原因`）；有格錯＝最後一行 `PlacesFailed N of M …`、退 1，其他格照回 |
| [json_multi_set](../base/json_multi_set/) | 一次改多格（11-12）：逐格照 json_set、照順序、**不回滾** | `items`（`[{"path", "value"}…]`）、`parents`（每格都套） | 一格一行 `路徑 TAB ok …`／`[error] …`；有格錯＝`PlacesFailed`、退 1，前面寫好的照留 |
| [mkdir](../base/mkdir/) | 建資料夾（上層一起建；已有＝沒事） | `path` | JSON：`path`、`created` |
| [move](../base/move/) | 搬移或改名（to 有東西就不搬；跨檔案系統照 mv 複製再刪） | `from`、`to` | JSON：`from`、`to` |
| [copy](../base/copy/) | 複製檔或整個資料夾（捷徑照捷徑） | `from`、`to` | JSON：`from`、`to`、`counter_files` |
| [trash](../base/trash/) | 丟進工作區的 `.trash/<時間>/`（不真的刪，move 救回；工作區外的東西放它的絕對路徑） | `path` | JSON：`path`、`to` |
| [remove](../base/remove/) | 真的刪（rm 的包裝，11-10 新做）：資料夾要 `recursive`、捷徑刪本身、`.`／`..`／`/` 拒絕 | `path`、`recursive` | JSON：`path`、`type`、`counter_files` |
| [math](../base/math/) | 算一個算術式子（不用 eval） | `expr` | 結果 |
| [peek_now_time](../base/peek_now_time/) | 現在的 UTC 時間 | （無） | `2026-10-23T08:00:00Z` |
| [peek_clock](../base/peek_clock/) | 看一眼 daemon 時鐘：讀 `$AOS_CLOCK` 回第幾 cycle（沒設或缺檔＝`ClockMissing`，不當 0；壞檔＝`ClockBad`） | （無） | `{"cycle": 42, "interval_ms": 1000}` |
| [run_python](../base/run_python/) | 跑一段 Python，回輸出與結束碼 | `code`、`timeout_s`（60／300） | 輸出、最後一行一律 `[exit code N]`（同 shell，11-05 前是第一行） |
| [llm_http](../base/llm_http/) | endpoint 函數：把一份請求 POST 到 OpenAI 相容端點（11-04 晚，[think-as-function](../../thinking/2026-11/04/think-as-function/README.md)；平常由 aos-llm-kernel 經 aos-exec 跑） | `endpoint{url, model, fixed?}`（request 先、`fixed` 蓋上、model 一律用包的）、`request{messages, …}`；選填 `--key-env NAME` 從小 proc 自己環境讀金鑰，沒給、變數沒設或空就不帶 Authorization 照打（401／403 的 `EndpointFailed` 才提變數沒設）；值含非 ASCII／空白／控制字＝`KeyBad`；stdin `endpoint.key`＝`ArgumentsBad` | 一行 JSON：`message`（只留 role／content／tool_calls）、`usage`、`model` |
| [llm_fake](../base/llm_fake/) | 假腦：同 llm_http 的形狀、不碰網路（有工具先叫 `endpoint.tool` 那個〔請求裡沒有就第一個，11-05 E 線〕，否則答 FAKE ANSWER；`endpoint.script` 有就照劇本：第 n 則 assistant 回 `script[n]`，項＝`{"content"}` 或 `{"tool_calls":[{"name","arguments"}]}`，超出照原樣） | 同上（`endpoint` 只看 `script`） | 同上，`model`＝`fake` |

不碰工作區的（`math`、`peek_now_time`、`peek_clock`、`llm_http`、`llm_fake`）不收路徑、不看 `$AOS_WS`。`run_python` 跟 `shell` 一樣在工作區跑（cwd＝`$AOS_WS`，沒有＝`WsMissing`；11-11 使用者裁「改程式，在工作區跑」），程式本身照舊寫進自己的小格 `main.py`（規則 8 的例外：拿小格當草稿區，不跨呼叫留東西）。
每個工具的細節看它 `_entry` 開頭的幾行說明與 `_tooldef.json`。

## 索引：aos

| 工具 | 一句話 | 參數 | 回什麼 |
|---|---|---|---|
| [llm_forward](../aos/llm_forward/README.md) | 把一封問腦請求交給包指定的下一層 kernel | `endpoint{to,kernel}`、`request`、選填 `priority` | 成功把 `letter` 換成 `child{kernel,letter}`；下層失敗原樣轉 stdout／stderr 與退碼 |
| [measure](../aos/measure/README.md) | 重跑 case，翻公開帳並分開量門、自洽與比對成本 | `case`、`defs`、`repeat`，選填 `check` | JSON：`check`、`size_bytes`、`cost`、`tree`、`samples`、`measured_at`；重跑時另有 `consistency` |
| [promote](../aos/promote/README.md) | 查公開 daemon 表後換上副本，前版留在定義根 `.prev/` | `defs`、`target`、`from`，選填 `daemons` | JSON：`target`、`promoted_at`、`prev` |
| [rollback](../aos/rollback/README.md) | 查公開 daemon 表後退回最新前版，消耗該份歷史 | `defs`、`target`，選填 `daemons` | JSON：`target`、`restored` |
| [watch](../aos/watch/README.md) | 記換版後的品質與單位成本，滿窗決定轉正或退回 | `op`（open／feed）、`watch`；其餘依操作 | JSON：`changes`，退回暫時失敗也留窗等待重試 |
| [review_round](../aos/review_round/README.md) | 量一輪、挑目標、試降級、換上並記錄，留下處方欄位 | `case`、`defs`、`ladder`，選填 `ws`、`daemons` | JSON：`round`、`review`、`action` |
| [metainfo_check](../aos/metainfo_check/README.md) | 以他見中位數核對定義的時間與輸入 token 估值，只報告 | `def`、`observed` | JSON：`checked_at`、`defs`（逐成本 key 的 `close`／`off`／`unclaimed`） |
| [shell_report](../aos/shell_report/README.md) | 讀公開 shell 帳、依有效工具推權限階段並歸納指令形狀 | `stacks`，選填 `defs` | JSON：`reports`，列出階段、任意執行工具、執行檔與形狀 |
| [box_check](../aos/box_check/README.md) | 比對關箱考題的逃脫嘗試與主機殘留 | `expect`、`got`、`input` | 比對器 JSON：`score`、`diff`、`why` |
| [defs](../aos/defs/README.md) | 搜尋定義、比三軸、查靜態引用與宣告完整性 | `op`、`root`，選填 `match`、`def` | JSON：`defs`／`groups`／`refs`／`problems`；含 specialize／retire 處方 |
| [jsonx_get](../aos/jsonx_get/) | json 工具一族的複雜組（包 jsonx，範本不掛；給用 `$ref`／`$env` 的 aos 設定檔）：同 json_get，多穿過 `$ref`、解開指示詞；選項預設全關。程式同 [aos_json.py](../aos_json.py)；aos-json 的 stderr 原樣透到 stderr，它退 1 時接它錯誤行的代號與原因，沒那行＝`CommandFailed`；起不來＝`LaunchFailed`。PATH 要有 aos-json（`resolve` 的值另要 aos-directive） | `path`、`follow`、`resolve`、`max_bytes`、`full` | 同 json_get |
| [jsonx_set](../aos/jsonx_set/) | 同 json_set，值從 `value`／`text`（當 JSON 解，壞＝`TextBad`）／`from`（另一格 `檔#/指標`）剛好一個；`resolve` 先解指示詞再存；`follow` 穿過 `$ref` 改被參照的檔（沒給＝路上有指示詞就 `FollowMissing`）；`check` 多出問題就不寫（`CheckFailed`） | `path`、`value`／`text`／`from`、`parents`、`resolve`、`follow`、`check` | `ok 檔#/指標` |
| [jsonx_add](../aos/jsonx_add/) | 同 json_add，選項同 jsonx_set | 同 jsonx_set | `ok 檔#/指標`；已有＝`KeyExists` |
| [jsonx_ls](../aos/jsonx_ls/) | 同 json_ls（11-12），多 `follow`（路上穿過 `$ref`）、`resolve`（列解開後的值，例 tools.json 疊完的工具表） | `path`、`follow`、`resolve`、`long`、`offset`、`limit` | 同 json_ls |
| [jsonx_search](../aos/jsonx_search/) | 同 json_search（11-12），多 `follow`、`resolve`（在解開後的值裡往下找）；這兩個不配 `up`（`ArgumentsBad`，祖先在別份檔、說不清） | `path`、`follow`、`resolve`、`key`、`value`、`contains`、`up`、`limit` | 同 json_search；路徑是腦給的那份檔的，拿去 jsonx_get 加 `follow` 讀得到 |
| [jsonx_del](../aos/jsonx_del/) | 同 json_del（11-12），但路上有 `$ref`／`$env` 會擋（`FollowMissing`）；`follow` 穿過去、刪在被參照的檔（`aos-json del --follow`）；沒有 `resolve`（刪不需要解值） | `path`、`follow` | `ok 檔#/指標` |
| [feedback](../aos/feedback/README.md) | 把指令或函數的使用意見交給 `aos-feedback add`，不推測呼叫者（11-07） | `command`、`pain`，選填 `suggest`、`kind`、`score`、`by`（預設 `aos-agent`） | 原樣一行 `aos-feedback: recorded <file>`；錯 `ArgumentsBad`、`LaunchFailed`、`CommandFailed` |
| [judge](../aos/judge) | 判官（11-05；不是腦的工具）：收 `$AOS_STACK/requests/` 的 `procs_*` 信，照 `judge.json` 判掛不掛；掛＝轉寄進 `$AOS_DAEMON` 的 ctl 信箱、不掛＝回 `applied: false`；`{"ping": true}` 不判、原樣轉寄（11-06 [no-pid](../../thinking/2026-11/05/no-pid/README.md) P3）。daemon 的身體（[kernel/daemon-judge](../../kernel/daemon-judge)）或 daemon 底下的 0 號 proc（[kernel/procs-kernel](../../kernel/procs-kernel)）每次跑一輪；說明 [kernel/docs/02](../../kernel/docs/02-kernel-modes.md) | 命令列一個參數：`judge.json` 的絕對路徑；`judge.json` 的 `allowed`（名字陣列／null）、`max_running`（非負整數／null） | 轉寄（照帶原信 `reply_to`）或回信、退 0；不掛的代號 `NameUnknown`、`SlotMissing`、`BodyBad`、`ForwardFailed`（`msg` 英文，同 stderr 那行提醒 `judge: warning: letter <名> refused: 代號 原因`；aos-agent ctl 收到就報 `AddRejected`／`CtlRejected`，11-05 edge-agent 題 2） |

它的「模型的錯」也照規則 3 退 1；回不回給腦由用它們的 agent 的 act 決定（11-04 前的例子 agent-meg、talk 的 member 都回給腦、不停，同 agent-pip；隨 demo 刪了）。

**上層 cmd 共用模組（lib 不 import）[aos_ws.py](../../py/aos_ws.py)**（在 [proto8/py](../../py/README.md)；不是工具、沒有 `_entry`）：「寄信、等答案、讀 stack」；照 agent 對話協議（[CONVENTION P-42](../../docs/CONVENTION/02-題目stack停錯腦/02-P-42.md)）只碰 stack——`stack_of`、`letter_key`（信件名稱的處理順序：有序 `^[0-9]{12}\.` 在前照名字、無序在後照名字，同 aos-post；11-03）、`names`（照 `letter_key` 排）／`where`／`waiting`（queue 的 new／cur／archive）、`put`（一則 user message，`aos-post init`＋`send --ordered`，PATH 上要有 aos-post）、`history`／`answers`／`exchanges`（回答＝沒有 tool_calls 的 assistant）；不認舊協議的工作區 `new/`／`out/`。給人用的 [proto8/cmd/aos-agent](../../cmd/aos-agent/README.md)（aos-agent；extras/human 的 aos-say／listen 11-04 併進它）用 realpath 找到這個資料夾 import（11-03 aos-ai 刪了，只服務它的 `loop_state`、`tail_jsonl` 跟著拿掉）。
