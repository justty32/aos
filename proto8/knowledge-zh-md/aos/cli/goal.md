# `knowledge/aos/cli/goal.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/goal.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/goal.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/The goal of one agent`**

# 一個 agent 的目標

用 aos-agent goal 給一個 agent 一個目標，它自己停下來時（最後一次回覆沒有呼叫工具，而且佇列是空的）會被提醒。它只寫那個 agent 的 `<stack>/goal.json`。父 agent 也用同樣的方法設定子 agent 的目標。

```sh
aos-agent goal -t bob                         # = get: status, text, reminded N of LIMIT, reason, set_by, updated; or "no goal"
aos-agent goal -t bob get --json              # the goal.json object, or null
aos-agent goal -t bob set Fix the failing test in src/.
aos-agent goal -t bob set --limit 3 -  < goal.txt
aos-agent goal -t bob pause waiting for the review
aos-agent goal -t bob resume                  # the count starts again at 0 (also after the limit paused it)
aos-agent goal -t bob done the test passes    # --abandoned = given up
aos-agent goal -t bob clear -y
```

- `set`：旗標放在 TEXT 前面；從第一個字起全部都是目標文字（`set Read --help first.` 會保留 `--help`）。
- `set -n N` = `--limit N`：1 到 1000，預設 10（這裡的 `-n` 不是 `--name`）。文字最多 1000 個字元。`done -a` = `--abandoned`。文字給 `-` 就從 stdin 讀。
- 提醒是 agent 對話歷史裡的一則訊息 `[aos] goal: TEXT (reminder N of LIMIT. ...)`。信會排在前面。還沒回覆過任何東西的 agent（對話歷史是空的）會把目標當成第一則訊息收到。
- 提醒之後的一次工具呼叫（goal 本身除外）算進展：次數歸 0。連續 LIMIT 次提醒都沒有進展（預設 10）時，目標會暫停，並附上最後一則訊息說明這件事。
- agent-fsm 的 agent 和 eca（claude、codex、pi）都能用；對 eca 來說，工具呼叫是從那個 CLI 自己的對話紀錄（transcript）裡看到的。
- `GoalMissing`：沒有目標。`GoalEnded`：已完成或已放棄的目標不能暫停或恢復（設一個新的）。`GoalBad`：檔案壞了（set 或 clear 會重寫它）。
- agent 自己的工具和提醒的規則：`aos/tools/goal.md`。
