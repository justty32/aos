# `knowledge/aos/cli/_index.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/_index.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**（index：鍵 → 一句說明）

| 鍵 | 說明 |
|---|---|
| `flags.json` | 每個 aos-* 指令的旗標放哪裡（在它那一層之後的任何位置，或在第一個參數之前）、help 的層級與短名。 |
| `errors.json` | 先看程式名、錯誤代號與原因，再決定要不要重試。 |
| `safety.json` | 在下會破壞東西的指令之前，先確認選到的 daemon、agent 與 stack；腳本不會有確認提示。 |
| `agent.json` | 用 aos-agent ctl 來掛上（add）、列出、查看、停止、睡眠、暫停、尋找與移除 agent。 |
| `talk_settings.json` | 用 aos-agent say、listen、ask、chat、open、close、watch、tools、llm 與 system 來跟一個 agent 說話，並在不改它定義的情況下改它的疊加設定（overlay）。 |
| `history.json` | 用 aos-agent history 來列出、刪除、摘要或替換一個 agent 對話裡的訊息。 |
| `hook.json` | 用 aos-agent hook 來列出、加入或移除一個 agent 的 hook（包括 on_clock 計時器）。 |
| `offer_hooks.json` | 用 aos-hook 讓別人能 hook 進你寫的程式（C++、shell...）：一份 hooks.json 宣告（只供讀取），加上在那個時刻執行 aos-hook fire；結束碼或 stdout 代表什麼，由你的程式決定。 |
| `goal.json` | 用 aos-agent goal 給一個 agent 一個目標，它自己停下時會被提醒；get、set、done、pause、resume、clear。 |
| `mailbox.json` | 用 aos-mailbox 從 shell 看你的信箱資料夾、偷看（peek）、讀與寄信箱裡的信。 |
| `daemon.json` | 用 aos-daemon-ctl 處理一個 daemon 上的任何 proc（add、stop、sleep、pause、ls、ping、shutdown、prune、sweep）；它繞過 kernel。 |
| `tools.json` | 用 aos-tools 來編輯一份登記表（registry），並用 stdin 上的 JSON 呼叫一個已註冊的工具。 |
| `tool_env.json` | 在註冊時就存下 hub 的位置，這樣每次工具呼叫都會用到預期的服務。 |
| `tool_flags.json` | Lib 工具接受由 schema 推出來的旗標，當作提供它們 JSON 輸入鍵的另一種方式。 |
| `grow.json` | 用 aos-grow 把一個函式往上移一層（行內到檔案到資料夾）或往下移；用 --dry-run 預覽。 |
| `eca.json` | aos-eca-turn 回覆外部 coding agent（claude、codex）的一個回合；aos-eca-screen 開啟、關閉或觀看它的畫面；用 CLI 自己的 hook 看守 CLI 自己的工具（Bash ...）。 |
| `clock.json` | aos-clock 把一個 clock 檔往前推一個週期；aos-clock-register 加入 clock 每 N 個週期送一次、只送一次，或在實際時鐘的某些時間送的信。 |
| `mcp.json` | 用 aos-mcp 透過 MCP stdio，把一份 aos-tools 登記表裡的工具提供給外部 agent（Claude Code、codex）。 |
| `mcp_import.json` | 用 aos-mcp-import 把一個外部 MCP server 的工具凍結進它的 server 檔、疊進 tools.json，並用 sync 更新；它的錯誤代號代表什麼。 |
| `sandbox.json` | 用 aos-sandbox 在沙盒裡跑一個程式：它看得到哪些路徑、網路、限制、使用者。 |
| `sweeper.json` | aos-sweeper 為一個 daemon 跑一輪清理：封存大的 stderr 檔、讓過期的封存失效、停掉沒人管的 loop。 |
| `feedback.json` | 用 aos-feedback 記下一個指令或工具哪裡難用，並替它對 AI 來說有多順手打分數。 |
| `gdb.json` | 用 aos-gdb／aos.py Python 函式庫來操控一個 agent（a.X.Y(...) = aos-agent X Y ...）、在某個條件成立時停住它（a.bp.add.before_tool(...)、一個看守的 proc...）、看它為什麼停、看它的 stack（a.look）、繼續執行。 |
| `parts` | 其他指令用來組成的低階程式：aos-exec、aos-loop、aos-fsm、aos-daemon、aos-post、aos-lock、aos-json、aos-directive、aos-llm，以及 llm kernel（工具資料夾 lib/aos/kernel_llm）。 |
| `json_view.json` | aos-json-view 把一個 JSON 檔或它的一部分，用緊湊的排版印出來給人看；只讀，輸出不是 JSON。 |
| `share.json` | 用 aos-share 替一個共用資料夾或一個檔案，對某個群組或使用者 id 設定 ACL（team、read、key、work、drop、stack）；用 --dry-run 預覽。 |
| `sandbox.json#/config` | 指標。aos-asuser：不用 root，以你的某個子 id 身分跑一個程式；aos-sandbox 用它來做 `user: sub:N`。它沒有自己的一頁：看 aos/cli/sandbox.json#/config 裡的 `user` 鍵，再看 `aos-asuser --help`。 |
| `eca.json#/external_mcp` | 指標。aos-mcp-launch SERVER_FILE：啟動一個外部的 stdio MCP server，它的 env_file 只讀進那個 server 的行程裡；eca CLI 會替你跑它。它沒有自己的一頁：aos/cli/eca.json#/external_mcp。 |
| `_description.json` | 給人類與外部 agent 用的指令：在 aos 裡優先用已註冊的工具、daemon 與 agent 怎麼選，以及先讀哪一頁。 |
