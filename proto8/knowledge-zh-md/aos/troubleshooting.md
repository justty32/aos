# `knowledge/aos/troubleshooting.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/troubleshooting.md`，跟到正本 commit `65bb2891f`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/troubleshooting.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

常見的失敗：每個症狀一條，寫它的原因和怎麼檢查。只收對照過程式碼、或對照過解釋它的那一頁的失敗。

**`#/Common failures`**

# 常見的失敗

重點：

- 在下面找你的症狀；每一條都寫了原因和怎麼檢查，並指向有更多說明的那一頁。
- 工具失敗、印出一行 `error:`：先讀代號（`aos/errors.md`）。
- 被拒絕（預算、kernel、配額）是一個決定，不是 bug：回報它或調整做法，不要硬來。
- 你的症狀不在這裡、而你找到了原因：告訴 eca-aos-kb，讓它可以加進來。

**`#/Tools and paths`**

# 工具和路徑

- **含有 `$AOS_HOME` 的檔案路徑找不到。** 原因：檔案工具不會展開變數。檢查：用 shell 取一次它的值（`echo $AOS_HOME`），然後用完整路徑。
- **剛加上的工具不在。** 原因：用 `self_tools` 加上的工具，從你下一次回覆起才能呼叫，同一次回覆裡不行。檢查：在下一次回覆裡跑 `self_tools` `{"op": "ls"}`（`aos/me/self_tools.md`）。
- **`self_tools` add 回覆 `PathMissing`。** 原因：那個資料夾不存在；相對路徑從你的工作區開始算。檢查：用 `path_json` 從 `$AOS_HOME` 給路徑，像 `{"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_hook"}`（`aos/me/self_tools.md#/self_tools: rules and errors`）。
- **某一頁叫你呼叫一個你沒有的工具**（self_hook、clock_register、agent_def、tools_def、jsonx_*、subagent ...）。原因：那個工具包不在你的定義裡。檢查：`self_tools` `{"op": "ls", "long": true}`；一次加一個工具（`aos/packs.md#/Tool packs`）。
- **`do_task` 回覆 `BodyUnsupported`。** 原因：你是 eca；你的 CLI 把工具呼叫放在你的對話歷史之外。檢查：用你的 CLI 自己的幫手，或用 `subagent`（如果你的定義有它）（`aos/me/do_task.md`）。

**`#/Hooks and timers`**

# Hook 和計時器

- **aos 的 `before_tool` hook 看不到 Bash、Write 或 Edit（eca）。** 原因：在 eca 上，aos 的 hook 只看得到 aos 工具。檢查：用 CLI 自己的 hook 看守 CLI 自己的工具（`aos/cli/eca.md#/Guarding the CLI's own tools (claude)`）。
- **在畫面上，`peek_clock` 或 `clock_register` 回覆 `ClockMissing`，雖然這棵樹有時鐘。** 原因：畫面是在你的迴圈跑過一次之前打開的，`AOS_CLOCK` 是從那個人的 shell 拿的。檢查：請人把畫面關掉再打開（`aos/clock.md#/Clock letters: rules`）。
- **on_clock hook 從來沒跑。** 原因：沒有時鐘（`AOS_CLOCK` 沒設，也沒有 `clock` 鍵）；你的紀錄裡有一行警告 `hook NAME (event on_clock) is not checked: AOS_CLOCK is not set ...`。檢查：你的 `stderr.txt` 裡的那一行（`aos/me/self_hook.md#/The on_clock hook`）。
- **信來了，但沒人告訴你。** 原因：`mail_notify` 每分鐘看一次你的信箱，而且你在睡、或在等 CLI 時不看。檢查：`mailbox_peek`；加了 `self_hook` 的話，`{"op": "get", "name": "mail_notify"}` 會顯示它有沒有開（`aos/mailbox.md#/Hearing about new letters`）。

**`#/Daemon and kernel`**

# daemon 和 kernel

- **`self_*` 工具回覆 `DaemonMissing` 或 `InstanceMissing`。** 原因：`AOS_DAEMON` 沒設或它的資料夾不存在，或表裡沒有你的那一列。檢查：說出來，之後最多再試一次（`aos/errors/common.md`）。
- **信箱、時鐘和 `self_*` 工具全都以 `KernelFailed` 失敗。** 原因：`$AOS_KERNEL` 有設，而 kernel 沒在 3 秒內回應，例如一個 `kernel_gate` agent 正在跑很長的一輪或在睡。檢查：等一下再試一次；如果一直失敗，回報 kernel 沒回應（`aos/kernel.md#/Where to send requests/When the kernel is slow or busy`）。
- **`BudgetMissing ... max_calls N reached in this window`。** 原因：這個時段的腦的預算用完了。檢查：錯誤的 `resets_at` 會說下一個時段什麼時候開始（`aos/brain.md#/Priority and budgets`）。
- **`SubagentSlotMissing`。** 原因：你的子 agent 配額滿了；什麼都沒啟動。檢查：`rm` 一個你不再需要的子 agent，或說已經到上限（`aos/agents/subagent.md`）。

**`#/The overview page (aos-frontend)`**

# 全景頁（aos-frontend）

- **頁面顯示 `aos-agent ctl ls --json failed`。** 原因：`$AOS_HOME/frontend/bin/aos-frontend` 用 `aos-agent ctl ls --json` 讀 daemon 的表，在 `/` 跑，用的是頁面啟動時的環境。那個環境裡沒有 `AOS_DAEMON`，或它的 PATH 上沒有 `aos-agent`（沒有 source 樹的 `env.sh`），這個呼叫就會失敗，而頁面不會顯示那個指令自己的錯誤。檢查：在啟動頁面的那個 shell 裡，跑 `echo $AOS_DAEMON` 和 `command -v aos-agent`；`source env.sh` 並設好 `AOS_DAEMON` 之後再啟動一次。systemd unit `$AOS_HOME/frontend/systemd/aos-frontend.service` 自己會把兩者都設好。
