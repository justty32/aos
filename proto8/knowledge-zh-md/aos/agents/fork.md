# `knowledge/aos/agents/fork.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/agents/fork.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/agents/fork.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/fork: a copy of you, one goal, just the conclusion`**

# fork：一份你的複本，一個目標，只拿結論

工具 `fork` 把現在的你複製成你 daemon 上的一個 fork：你的定義、你在 stack 裡改過的設定（工具、llm、hook、系統文字），還有你整段對話。fork 拿到一個目標；你只拿回它簡短的結論，當作這次呼叫的結果。fork 走的步驟不會進你的對話歷史。只給 agent-fsm 身體用（Claude 或 Codex agent 會拿到 `BodyUnsupported`：改用 `subagent`）。

用 `fork` 還是 `subagent`？

- `fork`：一件需要你已經知道的事的支線工作。回一個答案；之後 fork 就被移除。
- `subagent`：一個來自別的定義、你會一直跟它講話的幫手；它只知道你告訴它的事。

呼叫：`{"goal": "Check the three config files we discussed for the port setting and return the values"}`。在 `goal` 裡講要帶回什麼（最多 `max_chars`，預設 600）。

更多：`aos/agents/fork.md#/fork: what is copied`（複製了什麼、fork 看到什麼）、`aos/agents/fork.md#/fork: waiting, depth, keep, errors`（等待、深度、keep、錯誤）。

**`#/fork: what is copied`**

# fork：複製了什麼

- 有複製：你的定義（同一個資料夾）、你的對話，還有你自己那份工具、llm、hook 和系統文字（就是 `self_tools`、`self_llm`、`self_hook`、`self_system` 改過的）。你的定義必須在 `interfaces.json` 裡宣告 `history`（不然 `HistoryMissing`）。
- 沒複製：你的目標、你的待辦清單、你工具的紀錄（子 agent、留著的幫手）、你的佇列和信箱。fork 的 hook 從頭開始。
- fork 的對話停在你那次 fork 呼叫。那裡的結果說它是複本；同一回合後面的呼叫都說沒有執行。接著一則訊息：你是一個 fork、你的任務（目標）、只回覆結論、你不能再 fork。
- 只給 agent-fsm 身體的 agent 用。Claude 或 Codex agent 呼叫 `fork` 會拿到 `BodyUnsupported`：要把工作交給另一個 agent，用 `subagent`。
- fork 改的東西（工作區裡的檔案除外）留在 fork 裡。

**`#/fork: waiting, depth, keep, errors`**

# fork：等待、深度、keep、錯誤

- 等待：最多 `timeout_s` 秒（預設 0 = 不限時），或改用 `timeout_cycles` 個時鐘週期（正整數）。兩個都給 = `ArgumentsBad`。
- 深度：只有一層（`AOS_FORK_DEPTH`）：fork 呼叫 `fork` 會拿到 `DepthExceeded`；它該自己做那一步。
- `keep: true`：fork 被停下而不是移除，回覆會多最後一行 `details: <its stack>/`。要再問它，由人跑 `aos-agent ctl start --target <name>`，再 `say` / `listen`。
- `AnswerMissing`：時間內沒有回覆；錯誤行結尾是 `(details: <its stack>/)`，fork 被停下，留給人處理。
- `ArgumentsBad`：缺 `goal`、值不對，或給了 fork 不收的鍵（`from`、`tools`、`model`：用 `subagent`）。`HistoryMissing`、`InterfaceMissing`、`InterfaceBad`、`DefMissing`：你的定義沒辦法複製。`BodyUnsupported`：不是 agent-fsm 身體；用 `subagent`。
- `DaemonMissing`、`DaemonFailed`：自己做那一步；之後最多再試一次（`aos/errors/common.md`）。
