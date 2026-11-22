# `knowledge/aos/errors/common.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/errors/common.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/errors/common.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Common error codes`**

# 常見錯誤代號

你最常遇到的代號。依類別看更多：`aos/errors/common.md#/Codes about what you gave`、`aos/errors/common.md#/Codes from file work`、`aos/errors/common.md#/Codes from mailboxes`、`aos/errors/common.md#/Codes from external MCP tools`。

- `DaemonMissing`：`AOS_DAEMON` 沒設，或它的目錄不存在。`DaemonFailed`：它存在，但沒有及時回覆（忙、暫停或停了）。`InstanceMissing`：表裡沒有你這一列。`StateMissing`：daemon 的表檔案不在（還沒啟動，或它的狀態窗（state window）關著）。需要 daemon 的功能暫時不能用：直說；之後最多再試一次。
- `AddRejected ... SlotMissing max_running N reached`：kernel 只允許它的 daemon 的表上最多 N 個正在跑的 proc。移除一個子 agent，或回報。
- `AnswerMissing`：你問的 agent 沒有及時回覆（或者，當那行寫著 `stopped on an error before answering`，表示它的腦呼叫失敗而它停了；那行帶著那個錯誤：回報它，不要只是再問一次）。用 `subagent`（不是你的：`agents_ctl`）的 op `state` 查它：phase `stopped` 且有 `reason` 表示它當掉了（修好或回報）；`running` 或 `stuck` 表示它慢，用更長的 `timeout_s` 再問一次。phase 見：`aos/status.md`。
- `ToolExists`：只有真的要取代時，才用 `replace: true`（`self_tools`）或 `--replace`。
- `LlmKernelMissing`：一個 agent-fsm 沒有腦，因為 `AOS_LLM_KERNEL` 沒設或是空白；它在送出前立刻停下，沒有冷卻，並保留它的請求。重新加入它時給 `envs {"AOS_LLM_KERNEL": "<llm kernel stack>"}`／`aos-agent ctl add --envs AOS_LLM_KERNEL=...`，或在 daemon 的 `.env` 裡設定。`aos-llm` 本身在這個變數沒設／是空的，或它解析出的路徑不是資料夾時（相對於 `AOS_DAEMON`，不然相對於目前的目錄），也用這個代號；kernel 資料夾有設定但不存在的 agent-fsm，仍會等待並重試。

**`#/Codes about what you gave`**

# 關於你給的東西的代號

- `ArgumentsBad`：你給的 JSON 不是一個物件、缺了必要的鍵，或某個值型別不對。工具不認得的鍵也是 `ArgumentsBad`：`unknown key foo (known: path, offset, max_lines)`；把它拿掉。原因會說哪裡錯；修正這次呼叫。
- `FlagUnknown`：指令或工具不認得的旗標。`OpUnknown`：工具沒有的 `op`；它的描述列出有哪些 op。
- `PointerBad`：JSON 指標格式錯誤。它以 `/` 開頭；`""` 是整份文件，寫入不能取代它。
- `CfgBad`：工具的或你定義的設定檔壞了（不是 JSON 物件、值不對）。你沒辦法靠呼叫修好它；回報原因裡指出的那個檔。
- `ClockBad`：時鐘檔（`$AOS_CLOCK`）或某個週期數不是有效的整數。在人修好之前，以週期等待都不會動；回報它。

**`#/Codes from file work`**

# 檔案操作的代號

- `WsMissing`：你的工作區（`$AOS_WS`）沒設或不是資料夾。工具不會退回去用目前的資料夾。`StackMissing`：一個需要你 stack（`$AOS_STACK`）的工具沒有 stack。`ModuleMissing`：找不到工具共用的 Python 模組。這三個都是設定問題：回報它們。
- `ReadFailed`：檔案或資料夾在，但讀不了（權限、不是一般檔案、I/O 錯誤）；原因會指出是哪個。用 `stat` 查它；不要重試同一個路徑。
- `WriteFailed`、`CopyFailed`、`MoveFailed`、`RemoveFailed`：系統拒絕這個變更（權限、磁碟滿了、有東西擋著）。重試之前先看看現在那裡有什麼。
- `LogFailed`：`shell` 或 `run_python` 沒辦法在你的 stack 裡寫它的指令紀錄。`cannot prepare command log`：你的指令沒有跑。`cannot write command log`：它已經跑了，它做的事已經做了。

**`#/Codes from mailboxes`**

# 信箱的代號

- `MailboxMissing`：信箱不在：你給的 `box` 不存在，或你指名的 daemon 還沒啟動。檢查名字或信箱；不要手動建信箱資料夾。
- `MailboxBad`：這個資料夾不是信箱（它需要 `tmp/`、`new/` 和 `cur/`）。
- `LetterBad`：一封信壞了（不是有效的 `letter.json`）。回報它的名字；讀下一封。
- `StatusBad`：STATUS 不是那六個字之一（`aos/mailbox.md#/Mailbox rules`）。
- `mailbox_read`／`mailbox_send` 在 `keep` = 一個檔名時給的 `WriteFailed`：那個檔寫不了（它的資料夾必須存在）。讀：那封信還在你的信箱裡。寄：什麼都沒寄出，除非原因以 `letter NAME was sent, but:` 開頭。

**`#/Codes from external MCP tools`**

# 外部 MCP 工具的代號

描述以 `[MCP server NAME]` 開頭的工具，會去呼叫另一個程式的伺服器。

- `ServerFailed`：伺服器失敗或逾時；重試一次，然後回報。
- `ServerRejected`：伺服器拒絕了 token（http 401/403）；回報，不要重試。
- `ServerBad`：伺服器違反了協定；回報。
- `CallFailed`：工具自己說它失敗了；讀錯誤行上面它的文字。

所有代號：`aos/cli/mcp_import.md#/Codes from external MCP tools`。
