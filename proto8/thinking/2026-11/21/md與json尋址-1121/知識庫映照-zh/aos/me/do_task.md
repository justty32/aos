# `knowledge/aos/me/do_task.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/me/do_task.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# do_task：在你自己的對話裡做一件任務，只留下它的摘要

工具 `do_task` 讓你在自己的對話裡做一件任務，然後把那些工作全部摺成一段短摘要，讓你的對話歷史保持很小。它只在 agent-fsm 身體裡能用（eca 身體，例如 claude 或 codex，會得到 `BodyUnsupported`）。

1. `{"op": "start", "task": "Find where the config is read"}`：這次呼叫就是標記（`task` 可以不給）。
2. 照平常做事：呼叫工具、讀、想。
3. `{"op": "end", "summary": "The config is read in cfg/load.py; it needs AOS_HOME."}`：標記之後、一直到這次呼叫的每一則訊息，會變成一則訊息 `[aos] summary: lines A-B, N messages. Task "..." ended: SUMMARY`。`summary` 一定要給；把你之後還需要的每件事實都寫進去，包括任務期間別人告訴你的：他們的信和提醒也會一起摺掉，除非你在 `end` 加上 `"keep_others": true`。

`{"op": "status"}` 列出你還開著的任務。任務可以巢狀（最多 5 層）；`end` 一律關掉最內層的。

想要另一個獨立的工作者，而不是摺掉你自己的工作？用 `fork`（你的一份複本）或 `subagent`（`aos/agents.json#/subagent`）。規則與錯誤：`aos/me/do_task.json#/rules`。

---

**`#/rules`**

# do_task：規則與錯誤

- 留下的：標記和它的結果，然後是你的摘要。任務期間別人來的訊息（信、`[aos] goal:` 提醒、`[aos] new_mail` 通知）預設也會摺掉；`end` 的結果會說有幾則。在 `end` 上加 `"keep_others": true`，它們就不會被摺掉：它們會照順序留在摘要後面。任務裡你自己的 `[aos] summary:` 訊息一律會摺掉。
- 摺掉的訊息會保留在你對話歷史旁邊的 `history_removed.jsonl`，跟 `self_history` 一樣。
- 開著的任務存在你的工具資料夾（`tools/do_task/tasks.json`）：停下或重新啟動之後，你仍然在那些任務裡；呼叫 `status`。
- `end` 不會動到你的 `todo` 清單和你的 `goal`。
- 如果你自己把標記刪掉或摘要掉（`self_history`），`end` 會關掉任務但不摺：`MarkerMissing`。
- `TaskMissing`：你不在任務裡。`DepthExceeded`：先結束一個任務。`ArgumentsBad`：沒有 `summary`、`keep_others` 不是 true 或 false、或者有這個 op 不收的鍵。`OpUnknown`：op 不是 start、end 或 status。
- `BodyUnsupported`：你的身體把工具呼叫放在對話歷史之外（eca）；改用 `fork` 或 `subagent`。`StateBad`：`tasks.json` 壞了；要人來修。
- `DaemonMissing`、`DaemonFailed`、`InstanceMissing`：暫時不能用；照實說，之後最多再試一次（`aos/errors.json#/common`）。其他錯誤來自 `self_history` 那一層（`aos/me/self_history.json#/rules`）。
