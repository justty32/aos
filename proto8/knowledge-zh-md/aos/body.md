# `knowledge/aos/body.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/body.md`，跟到正本 commit `65bb2891f`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/body.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

你的身體是跑你每一輪的程式：agent-fsm 或 eca。兩者在腦、工具、hook、畫面、系統文字和對話歷史上有什麼不同，以及怎麼看出你是哪一種。

**`#/Two kinds of body`**

# 兩種身體

重點：

- 兩種：agent-fsm（aos 自己的迴圈）或 eca（由 Claude Code、Codex CLI 或 pi 跑你的每一輪）。
- 查出是哪一種：`self_state` `{"parts": ["who"]}` 會給出你的定義夾；那裡有 `cli.json` = eca，`fsm.json` = agent-fsm。
- eca：檔案和指令由 CLI 自己的工具處理；你的 aos 工具透過 aos-mcp 來，名字是 `mcp__aos__...`。
- eca：aos 的 hook 只看得到 aos 工具；要看守 Bash 和 CLI 的其他工具，用 CLI 自己的 hook。
- eca 的每一輪都花 CLI 的錢。

更多：

- 腦、工具、hook、畫面：`aos/body.md#/Brain, tools, hooks, screen`。
- 系統文字、對話歷史：`aos/body.md#/System text, history`。
- 每種身體的檔案：`aos/definition.md`。
- 你是 eca：哪些頁要讀、哪些可以跳過：`aos/eca_reading.md`。

這兩種：

- agent-fsm：aos 自己的迴圈，有四格（idle、think、wait、act）。問你的腦，是寄一封信給 llm kernel；每個工具呼叫由 aos 執行。
- eca（外部的程式寫作 agent）：由 Claude Code、Codex CLI 或 pi 跑你的每一輪。aos 把你佇列裡的信和你的 aos 工具交給它，並把它的回覆寫進你的對話歷史。

**`#/Brain, tools, hooks, screen`**

# 腦、工具、hook、畫面

腦：

- eca：CLI 就是腦。只有 `model` 和 `reasoning_effort` 有作用：claude 是 `--effort`，pi 是 `--thinking`，codex 都不收。
- agent-fsm：每一個 think 步驟都是寄給 llm kernel 的一封信。`model` 指定一個腦的包（brain pack），`temperature` 之類的鍵用來調它。

工具：

- eca，檔案和指令：CLI 自己的工具。claude 範本：Read、Write、Edit、Glob、Grep、Bash、Agent、Skill。pi：它自己的工具。codex：它自己的 shell，在 workspace-write 沙盒裡。
- eca，aos 工具：透過 aos-mcp，名字像 `mcp__aos__peek_now_time`。沒有 aos 的檔案或 shell 工具；json 工具包有（json_get、json_set、...）。
- agent-fsm：只有你註冊過的 aos 工具。
- 兩種都一樣：用 `self_tools` 加上的工具，從你下一次回覆起就能呼叫。

Hook：

- eca：`before_tool` / `after_tool` 只看得到 aos 工具。CLI 自己的工具（Bash、Write、Edit ...）和人在畫面上打的字都看不到。
- eca：要檢查或擋下 CLI 自己的工具，用 CLI 自己的 hook：`aos/cli/eca.md#/Guarding the CLI's own tools (claude)`。
- agent-fsm：每個事件都有。

什麼時候檢查 `on_clock`（`aos/me/self_hook.md#/The on_clock hook`）：

- eca：你閒著的時候，每次你的迴圈繞回來都會檢查（內建範本：大約一秒三次），不管有沒有新訊息。
- eca：aos 在等 CLI 回覆一則佇列訊息時不檢查。
- agent-fsm：在每一格開始時。
- 兩種都一樣：你在睡時不檢查，沒有時鐘時也絕不檢查。

畫面（只有 eca；agent-fsm 沒有）：

- 人用 `aos-agent open` 打開它。
- 畫面開著的 claude，每封佇列裡的信都會立刻收到，形式是署名的訊息（`Message from @NAME`，通知則是 `@aos通知中心`），就算正在一輪的中間也一樣。這不是它的使用者打的字（`aos/cli/eca.md#/aos-eca-turn: one turn`）。
- 畫面拿到的 `AOS_CLOCK`、`AOS_KERNEL` 和 `AOS_LLM_KERNEL` 跟你的迴圈拿到的一樣，不是從那個人的 shell 來的。
- 在你的迴圈跑過一次之前打開的畫面，可能缺這些：`ClockMissing`（`aos/clock.md#/Clock letters: rules`）。請人把它關掉再打開。

**`#/System text, history`**

# 系統文字、對話歷史

系統文字（`self_system`）：

- eca claude：加在 Claude Code 自己的系統文字後面，從你的下一輪開始。
- eca codex：只在開新對話時加上，所以改了要等下一次新對話。aos 不會替你開新對話。
- eca pi：加進 pi 的 system prompt，每一輪重讀。
- agent-fsm：你的文字就是整個 system message，每次呼叫腦之前都重讀。空的 = 沒有 system message。

對話歷史（你的 stack 裡的 `history.jsonl`）：

- eca：CLI 自己保存它的對話。`history.jsonl` 存的是你佇列裡的信和 CLI 每一輪的最終回覆，不含它的工具呼叫。
- eca：`self_history` 改過它之後，下一輪會開一個新對話，帶著改過的紀錄。
- agent-fsm：送給腦的對話，包括工具呼叫和結果。

對話歷史列上的記號（兩種身體都有）：

- 從信來的列有 `"aos": {"letter": "<letter name>"}`。
- 最終回覆（assistant、沒有 `tool_calls`）有 `"aos": {"answer_to": ["<letter name>", ...]}`，也就是它回覆的那些信。
- agent-fsm 把對話送給腦之前，會把每一列的 `aos` 鍵拿掉：模型從來看不到它。
- 寫在信裡的 `aos` 鍵會被換掉。

快取：改了系統文字或對話歷史，下一次呼叫腦會有一次沒命中 prompt cache。
