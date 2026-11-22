# `knowledge/aos/tools/todo.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/todo.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/todo.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool todo`**

# 工具 todo

給長任務用的你自己的待辦清單。它存在你的 stack 裡，不在你的對話歷史裡：做完摘要之後它還在。它不會自己放進你的提示：要再看就呼叫 `ls`。

任務有 3 步以上時用它：先寫下步驟，開始做某一步時標成 `in_progress`，做完標成 `completed`；`in_progress` 最多只留一個。每次呼叫一個 op；每個 op 都會印出整份清單：

```json
{"op": "set", "items": ["read the config", "write the parser", "add tests"]}
{"op": "mark", "n": 1, "status": "completed"}
{"op": "mark", "n": 2, "status": "in_progress"}
```
印出
```text
1 [x] read the config
2 [>] write the parser
3 [ ] add tests
... 1 of 3 completed
```

空清單印出 `... empty (use set or add)`。

各個 op（ls、set、add、mark）和限制：`aos/tools/todo.md#/todo: ops`。存在哪裡、其他 agent 的清單：`aos/tools/todo.md#/todo: where the list is`。錯誤：`aos/tools/todo.md#/todo: errors`。

**`#/todo: ops`**

# todo：op

- `ls`：印出清單；它從不寫任何東西。`"json": true` 印出一個 JSON 物件：`items`（每項有 `n`、`text`、`status`）、`counter_completed`、`updated_at`（UTC；第一次寫入前是 null）。
- `set`：用 `items` 取代整份清單。一項是一個字串（狀態 `pending`）或 `{"text", "status"}`；兩種可以混用。`[]` 清空。沒有刪除的 op：用 `set` 寫一份不含那項的清單，然後看新的編號。
- `add`：把 `text` 以 `pending` 加在最後；`"after": N` 放在第 N 項後面，`0` 放在最上面。
- `mark`：把第 `n` 項（從 1 起算）設成 `status`：`pending`、`in_progress` 或 `completed`。

標記：`[x]` completed、`[>]` in_progress、`[ ]` pending。有兩個以上 in_progress 時會多一行 `... note: 2 items are in_progress (keep at most one)`。

限制：最多 50 項；每項文字一行，最多 300 個字元（頭尾的空白會去掉）。超過就是 `ArgumentsBad`；不會幫你截斷。

**`#/todo: where the list is`**

# todo：清單在哪裡

- 在你的工具 cell 裡：`<your stack>/tools/todo/todo.json`，第一次寫入時建立。用別的名字登記時，cell 就是那個名字：是另一份清單。
- 做完的清單會一直留著，直到你 `set` 一份新的。
- 每個 agent 有自己的清單：子 agent 有自己的 stack 和清單，看不到你的（你也看不到它的）。`do_task` 摺疊你的對話歷史時不會動到清單。
- 一次一個呼叫：兩個呼叫同時在跑（平行呼叫兩個 `add`）可能會丟掉其中一個改動。

**`#/todo: errors`**

# todo：錯誤

- `ItemMissing`：`n`（或 `after`）不在清單上；訊息會說有幾項。呼叫 `ls`，再用裡面的編號。
- `StatusUnknown`：狀態不是 `pending`、`in_progress` 或 `completed`（例如 `done`）。用這三個之一。
- `ListBad`：存著的清單（`todo.json`）壞了，可能被人手動改過。`ls`、`add` 和 `mark` 會停；`set` 還能用，會寫一份全新的整份清單。
- `OpUnknown`：op 不是 `ls`、`set`、`add` 或 `mark`。
- `ArgumentsBad`：沒有 op、op 不收的鍵、文字是空的或有多行、超過 300 個字元、超過 50 項、`n` 或 `after` 不是整數、`json` 不是 true 或 false、某項有 `text` 和 `status` 以外的鍵、`mark` 沒給 `n` 或 `status`、清單已經有 50 項還 `add`。
- `StackMissing`：沒設 AOS_STACK；這個工具要經由 aos-tools call 跑（你的身體就是這樣做的）。
- `ReadFailed`、`WriteFailed`：`aos/errors/common.md#/Codes from file work`。鍵錯了或不認得：`aos/errors/common.md#/Codes about what you gave`。
