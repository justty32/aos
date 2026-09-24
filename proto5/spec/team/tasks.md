← [team](README.md)

# 任務單（交接書）與狀態機

`team/tasks/t-0001.json`。**只有郵差寫**：郵差收到申請或信，叫 [`lib/aos_team_task.py`](../../lib/aos_team_task.py) 的函式，函式改好單子、回後續動作。模型看任務表只能用唯讀的 `board` 工具。

## 欄位

```json
{"_metainfo": {"_type": "aos_team_task", "_version": 1},
 "id": "t-0001", "parent": null, "request": "<開單申請的 id>", "opened_by": "lead",
 "assignee": "worker-1", "rev": 1, "attempt": 1, "max_attempts": 3,
 "workflow": "IMPORT.md", "goal": "把 workflows 的 heartbeat 包導入專案", "facts": "facts.json",
 "done_when": [{"kind": "check", "name": "wf_residue"}, {"kind": "judge", "text": "原意沒變"}],
 "status": "queued", "waiting_on": null,
 "created_at": "…", "updated_at": "…", "deadline": null, "review_of": null,
 "verify": [], "review": [], "history": [{"at": "…", "event": "opened", "src": "<申請 id>", "by": "lead",
                                          "from": null, "to": "queued", "effects": […]}]}
```

- `id`：`t-` 加 4 位以上數字，郵差照資料夾裡最大號 +1；審查子單是 `<父單>.r<k>`（k＝那張父單第幾張審查子單）。
- `rev`：交接內容換了（改派）就 +1；`attempt`：同一個 rev 第幾次交件（驗收或審查不過 +1）。
- `waiting_on`：`blocked` 時等開單人（或 `human`），`waiting_user` 時等 `human` 或某題 `q-0003`；其他時候 null。
- `verify`／`review`：歷次驗收、審查結果（`{rev, attempt, pass, results|items, at}`）。
- `history`：每個事件一筆（含被忽略的），`effects` 是當時回的後續動作——冪等靠它。

## 狀態

```text
queued（等郵差投）→ sent（投進負責人 input/）→ working（信被收走）→ verifying（收到 DONE，驗收中）
  → reviewing（機械過了、有 judge 條目，審查子單開出去）→ done
任何沒結束的時候：blocked（負責人回 BLOCKED）／waiting_user（NEEDS-USER 或 ask_human）／cancelled／failed
```

結束的三種：`done`、`failed`、`cancelled`（只剩 `reassign` 能把 `failed` 拉回 queued）。

## 事件（`apply(單, 事件)`；郵差用 `step(lay, 單號, 事件)` 讀、套、寫）

| 事件 | 誰觸發 | 條件 → 結果 |
|---|---|---|
| `delivered` | 郵差把給負責人的信投進 input（`letter_delivered`） | queued → sent |
| `picked_up` | 那封信從 input 消失（`letter_picked_up`） | sent → working |
| `report` | 負責人寄的、`reply_to`＝單號的信（`on_letter`） | **只有 `by`＝負責人、`rev`＝目前 rev 才算**，不然記 `ignored:report`、不改。DONE：有機械條目 → verifying＋`verify`；只有 judge → reviewing＋`open_review`；都沒有 → done。BLOCKED → blocked；NEEDS-USER → waiting_user；FAILED → failed（通知開單人與人）；PROGRESS／REQUEST 只記下。審查子單回 DONE 信只記下（要用 `review_result`） |
| `resume` | 人或開單人寄給負責人的 REQUEST（`on_letter`）；人回答了跟這張單有關的問題 | blocked／waiting_user → sent |
| `needs_user` | 負責人 `ask_human` 帶 `reply_to`＝單號 | sent／working／blocked → waiting_user |
| `verified` | 驗收員結果（第 2 隊）：`{pass, results, rev, attempt}` | verifying 且 rev、attempt 對上：過 → reviewing（有 judge）或 done；不過 → 見下 |
| `reviewed` | 審查子單交回（`on_review_result` 回的 `step` 動作） | reviewing 且 rev、attempt 對上：全 PASS → done；有 FAIL → 見下 |
| `cancel`／`reassign` | 人或開單人的申請 | 見 mail.md |
| `no_reviewer` | `open_review` 找不到 reviewer | → blocked，等人 |
| `expire` | 郵差看到過了 `deadline`（`check_deadlines`） | → failed，通知 |

**驗收或審查不過**：`attempt < max_attempts`＝attempt+1、回 queued、寄「REQUEST 修正 t-0001（第 n/3 次）＋逐條結果」給負責人；用完＝failed、寄 FAILED 給開單人與人。
（workflows 的 FAILED＝終止，所以沒過不用 FAILED。）

## 後續動作（處理函式回的清單，郵差照做、做一件勾一件）

| 動作 | 郵差要做的 |
|---|---|
| `{"do": "letter", "to", "status", "reply_to", "rev", "text", "from"?}` | 寄一封信（`from` 沒寫＝`post`）；給負責人的那封投到了要叫 `letter_delivered` |
| `{"do": "verify", "task", "rev", "attempt"}` | 提交一次性驗收工作（不在郵差裡同步跑）；結果回來用 `verified` 事件 |
| `{"do": "open_review", "task", "rev", "attempt"}` | 叫 `open_review(lay, 名冊, 單號, src)`（src 用這個動作自己的 id），它會開子單並回派送動作 |
| `{"do": "step", "task", "event"}` | 叫 `step(lay, task, event)`，再做它回的動作 |

## 冪等

每個事件帶 `src`（觸發它的信、申請或工作的 id；`delivered`／`picked_up` 用 `delivered:<信 id>` 這種）。
`history` 裡已經有同一個 `src`＝**不改單子、回當初那份後續動作**。開單、開審查子單、問問題也一樣（看 `request`／`review_of`）。
所以郵差可以「先叫處理函式 → 把回的動作記進投遞紀錄 → 逐件做」，崩在任何一步，重跑同一步結果一樣。

## 審查子單

父單進 reviewing 時開 `t-0001.r1`：負責人＝名冊裡第一個 `template: reviewer` 的成員，`opened_by: post`，`done_when`＝父單的 judge 條目（照原順序重新編號），`review_of: {"task", "rev", "attempt", "indices": [父單裡的原編號]}`。
審查員用 `review_result` 逐條回（每條都要）→ 子單 done、父單收到 `reviewed`（`items` 換回父單的原編號）。父單已經改派或取消時，子單照樣 done，父單記 `ignored:reviewed`。
