# `knowledge/aos/body.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/body.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 兩種身體

你的身體是跑你每一輪的程式。有兩種：

- agent-fsm：aos 自己的迴圈，有四格（idle、think、wait、act）。問你的腦，是寄一封信給 llm kernel；每個工具呼叫由 aos 執行。
- eca（外部的程式寫作 agent）：由 Claude Code、Codex CLI 或 pi 跑你的每一輪。aos 把你佇列裡的信和你的 aos 工具交給它，並把它的回覆寫進你的對話歷史。

你是哪一種：`self_state` `{"parts": ["who"]}` 會印出你的定義夾；去 `ls` 它。那裡有 `cli.json` = eca（它的 `kind` 會寫 claude、codex 或 pi）；`fsm.json` = agent-fsm。

- 腦、工具、hook、畫面：`aos/body.json#/brain_tools`。
- 系統文字、對話歷史：`aos/body.json#/system_history`。
- 各自的檔案：`aos/definition.json`。

---

**`#/brain_tools`**

# 腦、工具、hook、畫面

- 腦。agent-fsm：每一個 think 步驟都是寄給 llm kernel 的一封信；`model` 指定一個腦的包（brain pack），`temperature` 之類的鍵用來調它。eca：CLI 就是腦；只有 `model` 和 `reasoning_effort` 有作用（claude 是 `--effort`，pi 是 `--thinking`；codex 都不收）。eca 的每一輪都花 CLI 的錢。
- 工具。agent-fsm：只有你註冊過的 aos 工具。eca：CLI 自己處理檔案和指令的工具（claude 範本：Read、Write、Edit、Glob、Grep、Bash、Agent、Skill；pi：它自己的工具；codex：它自己的 shell，在 workspace-write 沙盒裡），再加上透過 aos-mcp 來的你的 aos 工具，名字像 `mcp__aos__peek_now_time`；除了 json 和 jsonx 工具包（json_get、jsonx_get、...）以外，沒有 aos 的檔案或 shell 工具。兩種身體都一樣：用 `self_tools` 加上的工具，從你下一次回覆起就能呼叫。
- Hook。agent-fsm：每個事件都有。eca：`before_tool` / `after_tool` 只對 aos 工具；CLI 自己的工具（Bash、Write、Edit ...）和人在畫面上打的字都看不到。要檢查或擋下 CLI 自己的工具，用 CLI 自己的 hook：`aos/cli/eca.json#/cli_hooks`。`on_clock` 在每一格開始時檢查（agent-fsm）。在 eca 上，你閒著的時候，每次你的迴圈繞回來都會檢查（原廠範本：大約一秒三次），不管有沒有新訊息。aos 在等 CLI 回覆一則佇列訊息時、你在睡時、或沒有時鐘時（`aos/me/self_hook.json#/clock`），都不檢查。
- 畫面。eca 可以有一個讓人打開的終端機畫面（`aos-agent open`）；agent-fsm 沒有。一個畫面開著的 claude 身體，每封佇列裡的信都會立刻收到，形式是署名的訊息（`Message from @NAME`，通知則是 `@aos通知中心`），就算正在一輪的中間也一樣，而不是當成它的使用者打的字（`aos/cli/eca.json#/turn`）。人打開的畫面拿到的 `AOS_CLOCK`、`AOS_KERNEL` 和 `AOS_LLM_KERNEL` 跟你的迴圈手上的一樣，不是從那個人的 shell 來的。在這件事修好之前（或在你的迴圈跑過一次之前）打開的畫面，可能缺這些（`ClockMissing`：`aos/clock.json#/rules`）：請人把它關掉再打開。

---

**`#/system_history`**

# 系統文字、對話歷史

- 系統文字（`self_system`）。agent-fsm：你的文字就是整個 system message，每次呼叫腦之前都重讀；空的 = 沒有 system message。eca claude：你的文字加在 Claude Code 自己的系統文字後面，從你的下一輪開始。eca codex：只在開新對話時加上，所以改了要等下一次新對話；aos 不會替你開新對話。eca pi：加進 pi 的 system prompt，每一輪重讀。
- 對話歷史（你的 stack 裡的 `history.jsonl`）。agent-fsm：送給腦的對話，包括工具呼叫和結果。eca：CLI 自己保存它的對話；`history.jsonl` 存的是你佇列裡的信和 CLI 每一輪的最終回覆，不含它的工具呼叫。`self_history` 改過它之後，下一個 eca 輪會開一個新對話，帶著改過的紀錄。兩種身體都會在列上做記號以便對應：從信來的列有 `"aos": {"letter": "<letter name>"}`；最終回覆（assistant、沒有 `tool_calls`）有 `"aos": {"answer_to": ["<letter name>", ...]}`，也就是它回覆的那些信。agent-fsm 把對話送給腦之前，會把每一列的 `aos` 鍵拿掉，所以模型從來看不到它。寫在信裡的 `aos` 鍵會被換掉。
- 快取。改了系統文字或對話歷史，下一次呼叫腦會有一次沒命中 prompt cache。
