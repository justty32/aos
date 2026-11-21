# `knowledge/aos/agents/subagent.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/agents/subagent.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 你自己的子 agent：subagent

工具 `subagent` 啟動屬於你的 agent。只有你用它啟動的 agent 才是你的：你可以跟它們講話、改它們的工具、腦、對話歷史、hook 和系統文字，停下並移除它們。它們算在你的配額裡。

一次呼叫一個 op：

- 啟動：`{"op": "add", "def": "defs/helper", "name": "kid", "ws": "kid"}`（`def` = 一個定義夾；還沒有定義？先 `agent_def` `{"op": "new", "template": "agent-fsm", "path": "defs/helper"}`；`ws` = 它的工作區，相對於你的，沒有就建立；預設 = 你自己的）
- 更多 add 選項（`stack`、`limits`、`envs`、`auto_restart` ...）：`aos/agents/subagent.json#/add`
- 列出你的：`{"op": "ls"}`（每個子 agent 一行：NAME STATE WORKSPACE QUEUED REASON，然後 `subagents N/MAX`；`"long": true` 加上健康欄位 QUEUE RESTARTS COOLDOWN LAST ERROR；`"json": true` = 每個欄位都用 JSON）
- 問並等待：`{"op": "ask", "name": "kid", "text": "what time is it?"}`（跑 `aos-agent ask`：你拿到的是這則訊息的回覆，就算同時有別人跟這個子 agent 講話也一樣；預設不限時等待；`timeout_s` 設一個時限（0 = 不限），或 `timeout_cycles` 改成等那麼多個時鐘週期）
- 現在說、晚點讀：`{"op": "say", "name": "kid", "text": "hello"}` 印出信名；然後 `{"op": "listen", "name": "kid", "letter": "<that name>"}` 等那封信的回覆（跟 ask 一樣，同樣的 `timeout_s` / `timeout_cycles`）。沒給 `letter` 時，listen 等它佇列裡還在的最新那封信，沒有就等它拿走了還沒回覆的最後一封，再沒有就給最新的回覆。`"last": 3` 顯示最後 3 筆、不等待（不能跟 `letter` 一起用）
- 它的工具：`{"op": "tools", "name": "kid", "args": {"op": "add", "path": "tools/math"}}`
- 它的腦：`{"op": "llm", "name": "kid", "args": {"op": "set", "settings": {"model": "fake"}}}`
- 它的對話歷史、它的 hook、它的系統文字：`"op": "history"`、`"op": "hook"`、`"op": "system"`
- `{"op": "state", "name": "kid"}`；`stop`/`start`、`sleep`/`wake`、`pause`/`resume` 用法相同
- 移除：`{"op": "rm", "name": "kid"}`（保留它的 stack；`"purge": true` 會刪掉）

`say` 不是煞車：訊息在子 agent 的佇列裡等，agent-fsm 身體要回到 idle 才會收進來，所以正在連續呼叫工具的子 agent 還看不到它。`pause` 不會打斷正在跑的那一步；它只讓下一步不開始。要立刻停下子 agent，用 `sleep`：daemon 結束它的行程，它的 stack 保留，`wake` 再把它啟動。

`args` 就是 `self_tools`、`self_llm`、`self_history`、`self_hook` 或 `self_system` 收的東西（見 `aos/me.json`）；改動落在子 agent 身上，不是你。

等得比 MCP 客戶端自己的工具時限還久，還是會被那個客戶端切斷；去那邊調高（Claude Code：環境變數 MCP_TOOL_TIMEOUT，單位 ms），或用 say + listen 分成較短的幾步。

配額與錯誤：`aos/agents/subagent.json#/errors`。

---

**`#/errors`**

# subagent：配額與錯誤

配額：同時最多 `max_subagents` 個子 agent（預設 4）。它設在你定義的 `subagents.json`；你自己 stack 裡的 `subagents.json` 只用你改的鍵蓋過它，像 `{"max_subagents": 2}`。誰是你的，由工具自己記錄（在你 stack 的 `tools/subagent/` 下）；不要改那份紀錄。

- `SubagentSlotMissing`：你的配額滿了；什麼都沒啟動。`rm` 一個你不再需要的子 agent，或說已到上限。不要一直重試。
- `AddRejected ... SlotMissing`：是 daemon 滿了（它的 kernel 算每一個 agent），不是你的配額。一樣：移除一個或回報。
- `SubagentUnknown`：那個 agent 不是你用這個工具啟動的。其他 agent 用 `agents_ctl`（你沒辦法跟它們講話）。
- `SubagentMissing`：別人把它移除了；現在已經忘掉它，它的位子空出來了。
- `SubagentQueued`：它還在等位子，還沒有 stack；等 `ls` 顯示它再試。
- `LetterDropped`：子 agent 丟掉了那封信、不會回覆（不是有效訊息、被它的 `before_queue` hook 擋下，或它的 CLI 在拿走信之後永久失敗）；原因在訊息裡。claude print API 暫時性錯誤時，一般的信會保持待處理，冷卻後接續，而不是丟掉；斜線指令就算是暫時性錯誤也會被丟掉。如果還重要就再寄一次。
- `AnswerMissing`：時間內沒有回覆。跑 `state`：`stopped` 加上原因表示它當掉了（見 `aos/status.json`）；`running` 或 `stuck` 表示它很慢：晚點再 `listen`，或用更長的 `timeout_s` / `timeout_cycles`。
- `ToolMissing`：那個 op 用的 `self_*` 工具沒裝在這個工具旁邊。
- `ArgumentsBad`：那個 op 不收你給的某個鍵，或某個值型別不對；訊息會列出它收什麼。

子 agent 用完就移除。沒有人會幫你移除。

---

**`#/add`**

# subagent add：更多選項

`{"op": "add", "def": "defs/helper", "name": "kid"}` 就夠了。可選的鍵（`agents_ctl` add 收一樣的）：

- `ws`：它的工作區，相對於你的（沒有就建立；預設：你的）。`stack`：它的 stack 資料夾（預設：你 daemon 底下的一個）。
- `def_json`、`ws_json`、`stack_json`：取代 `def`、`ws`、`stack`，值照寫的保留，每次啟動都重新查一次，像 `{"$env": "AOS_HOME", "$path": "/templates/agent-fsm"}`。
- `limits`：資源限制，像 `{"mem_mb": 512, "files": 256}`。`mem_mb`、`cpu_s`、`file_mb` 和 `files`（開著的檔案；鍵不是 `nofile`）是每個行程各算：每次跑工具或呼叫腦都是新行程、各自計數，所以 `cpu_s: 2` 擋不住一個 agent 總共用掉好幾分鐘 CPU。`procs` 算同一個使用者的行程數。`mem_total_mb` 和 `procs_total` 限制整個 agent 和它啟動的一切（cgroup；沒有的話 daemon 會警告，並把它們列在 `limits_ignored`）。`user` 用另一個帳號跑它。目前還沒有總 CPU 的鍵。
- `envs`：給它的環境值，像 `{"LANG": "C"}`（字串）。agent-fsm 需要 `AOS_LLM_KERNEL`：它拿到的是 daemon 的環境，不是你的，所以 daemon 沒有的話，就把你的放進 `envs` 傳過去（`{"AOS_LLM_KERNEL": "..."}`）；沒有它，agent 會立刻以 LlmKernelMissing 停下。
- `envs` 裡的 `AOS_PARENT_STACK` 和 `AOS_NOTIFY_BOX`：每次 subagent add 都會記下誰要求的（你的根 stack，就算呼叫來自你的工具或 hook 格子也是）和它的通知寄去哪（預設：你的 `<stack>/mailbox`；`""` = 不寄；另一個信箱資料夾 = 寄去那裡，像 `{"AOS_NOTIFY_BOX": "/home/.../procs/xiaosi/mailbox"}`）。兩者都必須是絕對路徑、不含 `..`。brain_notify 把腦失敗的通知寄到那裡：kernel 拒絕，以及 claude CliFailed / ReplyMissing 事件，帶一個布林的 retry 欄位（暫時性的接續或永久停下）。沒有那個布林的 Codex 事件不出聲。工作回報還是照你那封信的 reply_to。`agents_ctl` add 只有在你給 `envs` 時才記下它們（`aos-agent ctl add`：`--envs`、`--parent`、`--notify-box`）；沒給 envs 的 add 什麼都不記。之後要換信箱：`rm`（stack 還在），再用同一個 `stack` 和新的 envs `add` 一次。子 agent 用 `aos-agent ctl who --json`（`self_state` who）讀這兩個：那是要求者寫的，不是證明。
- `auto_restart`：true = 它每次結束 daemon 都重新啟動它。只給一直開著的 agent 用。
- `on_queued`：還在等位子時 `fail`（預設）或 `ok`。`start` 和 `wake` 也收。
- `timeout_s`：等 daemon 的秒數（預設 30）。
