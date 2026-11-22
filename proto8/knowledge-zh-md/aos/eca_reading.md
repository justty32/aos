# `knowledge/aos/eca_reading.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/eca_reading.md`，跟到正本 commit `65bb2891f`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/eca_reading.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

你是 eca（由 Claude Code、Codex CLI 或 pi 跑你的每一輪）：這個知識庫裡哪些頁和節是給你的，哪些可以跳過。

**`#/Reading as an eca`**

# 以 eca 的身分閱讀

重點：

- 檔案、指令和幫手由你的 CLI 自己的工具處理；aos 給你 mailbox、self、json、index 和幾個小工具（`aos/packs.md#/Tool packs`）。
- 很多頁也描述 agent-fsm。讀寫著 eca、或沒提到身體的那幾行；跳過寫著只有 agent-fsm 的那幾行。
- 頁面教的工具不一定在你的清單裡：`self_tools` `{"op": "ls"}` 會顯示你有什麼。不在內建 eca 範本裡的工具（self_hook、clock_register、agent_def、tools_def、jsonx_*）要用 `self_tools` 一次加一個。
- 出了問題：`aos/troubleshooting.md`；工具失敗了：`aos/errors.md`。

**`#/Read these`**

# 要讀的

- `aos/_description.md`：八個詞和五條規則。
- `aos/body.md`：eca 有什麼不同（腦、工具、hook、畫面、系統文字、對話歷史）。
- `aos/cli/eca.md`：你自己的身體：一回合、畫面、斜線指令、外部 MCP 伺服器、看守 CLI 自己的工具。
- `aos/mailbox.md`：信，以及告訴你有新信的 `mail_notify` hook。
- `aos/me.md`：你的名字、你的 stack、`self_state`、`self_ctl`（內建範本裡 `self_ctl` 是關掉的；用 `self_tools` 加上它）。
- `aos/me/self_tools.md`：加入和移除你自己的工具。
- `aos/user_zone.md`：怎麼問使用者。
- `aos/rules.md`：你絕不能做的事。
- `aos/packs.md#/Tool packs`：eca 有哪些工具包。

**`#/Read when you need them`**

# 需要時再讀

- `aos/me/self_hook.md`：掛在你自己事件上的 hook。先加入 `self_hook`。在 eca 上，`before_tool` / `after_tool` 只看得到 aos 工具，而 `before_compact` / `after_compact` 跟著 CLI 自己的壓縮（claude）。
- `aos/clock.md`：時鐘信（先加入 `clock_register`）和 on_clock hook。
- `aos/me/self_system.md`、`aos/me/self_llm.md`、`aos/me/self_history.md`：你的系統文字、腦的設定和對話歷史。這三個工具在內建範本裡是關掉的；用 `self_tools` 加上它們。在 eca 上，你的腦的設定只有 `model` 和 `reasoning_effort` 有作用。
- `aos/agents.md`：用 `agent_def` 做新的定義（先加入它）；`subagent` 工具包不在內建 eca 範本裡，所以旁支工作用你的 CLI 自己的幫手。
- `aos/definition.md`、`aos/kits.md`：做或改定義（這是人的工作，或用 `agent_def`）。
- `aos/status.md`、`aos/world.md`、`aos/kernel.md`：daemon 的表、心裡的模型、kernel。
- 你有的那些工具在 `aos/tools/` 底下的節點：json 工具、`index_view`、`math`、`peek_clock`、`peek_now_time`。

**`#/Skip these (agent-fsm only)`**

# 可以跳過的（只有 agent-fsm）

- `aos/me/compact.md`：回覆 `[aos] compact:`，以及摺起 agent-fsm 的對話歷史。你的壓縮是 CLI 自己的（`aos/cli/eca.md`）。
- `aos/me/do_task.md`：eca 會拿到 `BodyUnsupported`。
- `aos/agents/fork.md`：fork 只有 agent-fsm 有。
- `aos/brain.md`：寄給 llm kernel 的腦的信；你的 CLI 就是你的腦。
- 檔案和 shell 工具（read、ls、view、stat、grep、glob、write、edit、copy、move、mkdir、trash、remove、shell、run_python）以及 goal 和 todo 在 `aos/tools/` 底下的節點：eca 一個都沒有；用你的 CLI 自己的。
