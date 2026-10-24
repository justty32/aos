← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 pi-tools、file-tools、kernel-llm 頂層（10-24）｜上一份 [05-demo-其他](05-demo-其他.md)（talk、self-improve）

> 2026-10-24 收尾補：這幾個 demo 各作者做的時候沒改 code map。怎麼跑、錯誤代號見 [demo README](../../../../../proto8/demo/README.md) 各節。

### `proto8/demo/pi-tools/`（仿 pi 的寫程式工具）

仿 pi coding agent 預設的四個工具，可重用（agent-pip、self-improve 的改進者用符號連結掛）。每個是資料夾程式＋`tool.json`，arguments 從 stdin 進、stdout 是結果；錯＝stderr 與 stdout 各一行「工具名: 代號 原因」、退 1。設計在 [thinking 2026-10-24-pi-tools](../../../../../proto8/thinking/2026-10-24-pi-tools.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `read/` | 讀檔，最多 2000 行或 50KB，太長附「從第幾行接著讀」（`offset`、`limit`）；路徑不能出 `$AOS_WS`（符號連結也算） |
| `write/` | 建檔或整份蓋掉，上層自動建；先寫 `.` 開頭暫存檔再改名 |
| `edit/` | `edits: [{old_text, new_text}]`：每段對原檔比、要唯一、不重疊，全有或全無；CRLF 照 LF 比、寫回還原 |
| `bash/` | 在 `$AOS_WS` 跑一行指令，留最後 2000 行或 50KB；逾時預設 30、上限 300 秒，整群停；被外面 TERM 也先停指令那群。指令本身擋不住出界 |

### `proto8/demo/file-tools/`（資料夾與檔案的漸進工具）

輸出一律 JSON 的八個工具，路徑限制同 pi-tools；錯＝stderr 一行、stdout 一份 `{"error": 同一行}`、退 1。設計同在 [thinking 2026-10-24-pi-tools](../../../../../proto8/thinking/2026-10-24-pi-tools.md)。每個工具資料夾都是 `_entry`＋`tool.json`。

| 哪裡 | 負責什麼 |
|---|---|
| `common.py` | 共用：讀 stdin 的 arguments、`resolve`（路徑限制在 `$AOS_WS`）、`out`、`die`、`aos_marks`（認 `_entry`、`.env`、`tool.json`、`loop.json`…）、原子寫入；工具名＝資料夾名 |
| `ls/` | 子項陣列：型別、大小、時間、子項數、`aos` 標記、JSON 檔頂層 key（最多 12）；`.` 開頭預設不列；分頁 `offset`／`limit`／`next_offset` |
| `stat/` | 單一個的屬性：大小、可執行、是不是文字、行數、格式、JSON 頂層摘要；資料夾的子項數與 `aos` 標記 |
| `view/` | JSON 照 `pointer` 一層層展開（小的直接給值）；大文字檔先給大綱（Python 的 def、Markdown 標題），再用 `start`／`end` 看那段 |
| `json_edit/` | `set: {指標: 值}`、`del: [指標]`：先檢查全部指得到，再交給 PATH 上的 `aos-json` 原子寫（`batch --parents`、`del`） |
| `mkdir/` | 建資料夾（上層一起建，已有＝沒事） |
| `move/` | 搬移或改名；目的地有東西不搬（`FileBad`）；從垃圾桶搬回也用它 |
| `copy/` | 複製檔或整個資料夾（連結照連結）；目的地有東西不做 |
| `trash/` | 刪除＝搬進 `$AOS_WS/.trash/<時間>/<原路徑>`，可救回；垃圾桶本身不收 |

### `proto8/demo/kernel-llm/`（問腦走 LLM kernel 排隊）

一個 daemon 管 kernel 與三隻走 kernel 的 agent，看服務順序（high 先、同級宣告短 `time_ms` 的先）。設計在 [thinking 2026-10-24-llm-kernel](../../../../../proto8/thinking/2026-10-24-llm-kernel.md)；程式見 [03-kernel-llm](03-kernel-llm.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `_entry` | shell：`AOS_KERNEL=$AOS_STACK/mailbox` 並先建好（免得閘門 `MailboxMissing`）、`exec aos-daemon daemon.json` |
| `daemon.json` | max 25、每 200 毫秒；子項 kernel（`aos-kernel-llm kernel.json`，`interval_ms` 300）與 a、b、c（各跑一次 `agent-ivy`，工作區 `$AOS_WS/<名>`，`BRAIN` 選 `brains/plain.json`／`quick.json`／`urgent.json`） |
| `kernel.json` | `mailbox` 讀 `$AOS_KERNEL`、`slots` 1、`budget`（calls 100、tokens 100000、window day；10-24 下午加，demo 碰不到頂） |
| `agent-ivy/`（含 `brains/`） | 走 kernel 的 agent 與三張腦的單子，逐檔見 [04-demo-agents](04-demo-agents.md) |
