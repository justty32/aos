← [回入口 README.md](../README.md)｜段落：索引：base、索引：aos｜上一份：[01-分層等](01-分層等.md)｜下一份：[03-索引-agent等](03-索引-agent等.md)

## 索引：base

**分包與路徑**（11-10 tool-packs）：前 15 支通用工具分四包，清單在 [lib/packs](../packs/README.md)——1 看（read、ls、view、stat、json_read）、2 改（write、edit、copy、move、mkdir、json_write）、3 刪（trash、remove）、4 殼（shell、run_python）；另有小工具包 gadgets（peek_clock、peek_now_time、math，不改任何東西、隨手看一下；11-11 起加 agent 工具 thought）。agent 工具也分包（事件、自我管理、子 agent、定義、信箱、記憶），一覽見 [lib/packs](../packs/README.md)。檔案工具的路徑相對從 `$AOS_WS` 算、絕對照用，**不擋工作區外**（使用者「這些就是/usr/bin的包裝」「3.對」），能不能動看 Linux 權限；相對路徑又沒有 `$AOS_WS`＝`WsMissing`。

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
| [json_read](../base/json_read/) | 看一份 JSON 檔的某個位置，大的摺起來 | `path`、`pointer`、`depth`（1／10） | JSON：`value`，物件摺成 `{type, keys}`、陣列 `{type, counter_items}`、長字串 `{type, counter_chars, head}` |
| [json_write](../base/json_write/) | 照指標改幾個位置，一處不合整份不寫（11-10 由 json_edit 改名；寫入交給 aos-json） | `path`、`set{指標: 值}`、`del[指標]` | JSON：`counter_set`、`counter_del`（改了幾個）、頂層 key |
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

不碰工作區的（`math`、`peek_now_time`、`peek_clock`、`run_python`、`llm_http`、`llm_fake`）不收路徑、不看 `$AOS_WS`；`run_python` 把程式寫進自己的小格再跑（規則 8 的例外：拿小格當草稿區，不跨呼叫留東西）。
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
| [aos_json](../aos/aos_json/) | 看或改工作區裡的 JSON 檔，一次一個 aos-json 子命令（11-06 從 impls/aos-json/tools 搬來）：`target` 的檔只收工作區裡的相對路徑（`PathBad`）；讀帶 `--follow`、寫帶 `--check --follow`（del 只 `--follow`：aos-json del 不收 `--check`）；`cmd` 不認得＝`OpUnknown`；aos-json 的 stderr 原樣透到 stderr，它退 1 時接它錯誤行的代號與原因（`aos_json: error: PointerMissing …`），沒那行＝`CommandFailed`；aos-json 起不來＝`LaunchFailed`。PATH 要有 aos-json | `cmd`（peek／get／where／set／batch／del／append／merge／check）、`target`（`檔#/指標`）、`value`、`depth` | 讀的回 aos-json 的輸出；寫的回 `ok`；check 有問題＝`problems:` 加一行一條、退 0 |
| [feedback](../aos/feedback/README.md) | 把指令或函數的使用意見交給 `aos-feedback add`，不推測呼叫者（11-07） | `command`、`pain`，選填 `suggest`、`kind`、`score`、`by`（預設 `aos-agent`） | 原樣一行 `aos-feedback: recorded <file>`；錯 `ArgumentsBad`、`LaunchFailed`、`CommandFailed` |
| [judge](../aos/judge) | 判官（11-05；不是腦的工具）：收 `$AOS_STACK/requests/` 的 `procs_*` 信，照 `judge.json` 判掛不掛；掛＝轉寄進 `$AOS_DAEMON` 的 ctl 信箱、不掛＝回 `applied: false`；`{"ping": true}` 不判、原樣轉寄（11-06 [no-pid](../../thinking/2026-11/05/no-pid/README.md) P3）。daemon 的身體（[kernel/daemon-judge](../../kernel/daemon-judge)）或 daemon 底下的 0 號 proc（[kernel/procs-kernel](../../kernel/procs-kernel)）每次跑一輪；說明 [kernel/docs/02](../../kernel/docs/02-kernel-modes.md) | 命令列一個參數：`judge.json` 的絕對路徑；`judge.json` 的 `allowed`（名字陣列／null）、`max_running`（非負整數／null） | 轉寄（照帶原信 `reply_to`）或回信、退 0；不掛的代號 `NameUnknown`、`SlotMissing`、`BodyBad`、`ForwardFailed`（`msg` 英文，同 stderr 那行提醒 `judge: warning: letter <名> refused: 代號 原因`；aos-agent ctl 收到就報 `AddRejected`／`CtlRejected`，11-05 edge-agent 題 2） |

它的「模型的錯」也照規則 3 退 1；回不回給腦由用它們的 agent 的 act 決定（11-04 前的例子 agent-meg、talk 的 member 都回給腦、不停，同 agent-pip；隨 demo 刪了）。

**上層 cmd 共用模組（lib 不 import）[aos_ws.py](../../py/aos_ws.py)**（在 [proto8/py](../../py/README.md)；不是工具、沒有 `_entry`）：「寄信、等答案、讀 stack」；照 agent 對話協議（[CONVENTION P-42](../../docs/CONVENTION/02-題目stack停錯腦/02-P-42.md)）只碰 stack——`stack_of`、`letter_key`（信件名稱的處理順序：有序 `^[0-9]{12}\.` 在前照名字、無序在後照名字，同 aos-post；11-03）、`names`（照 `letter_key` 排）／`where`／`waiting`（queue 的 new／cur／archive）、`put`（一則 user message，`aos-post init`＋`send --ordered`，PATH 上要有 aos-post）、`history`／`answers`／`exchanges`（回答＝沒有 tool_calls 的 assistant）；不認舊協議的工作區 `new/`／`out/`。給人用的 [proto8/cmd/aos-agent](../../cmd/aos-agent/README.md)（aos-agent；extras/human 的 aos-say／listen 11-04 併進它）用 realpath 找到這個資料夾 import（11-03 aos-ai 刪了，只服務它的 `loop_state`、`tail_jsonl` 跟著拿掉）。
