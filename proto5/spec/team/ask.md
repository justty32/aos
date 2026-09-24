← [team](README.md)

# 問人

成員卡在只有人能決定的事，用 `ask_human` 工具寄一份 `kind: ask` 申請；**寄完這一輪就結束**，答案到了是一則新輸入（沒有「等回答」的工具）。

```text
成員 ask_human ──申請──▶ 郵差：建 team/wait-user/q-0003.json（open）；reply_to 是單號＝那張單 → waiting_user
人 aos-team wait ls         看有哪些在等
人 aos-team answer q-0003 "B" ──申請（outbox/human/）──▶ 郵差：投一封【人 → worker-1 · 回覆 q-0003】給發問者、
                                                           問題 → answered；那張單 → working（恢復）
```

## 問題檔 `team/wait-user/q-0003.json`（只有郵差寫）

```json
{"_metainfo": {"_type": "aos_team_question", "_version": 1},
 "id": "q-0003", "request": "<ask 申請的 id>", "from": "worker-1",
 "question": "facts.json 沒寫分支慣例，要用 main 還是開分支？", "options": ["main", "開分支"], "default": "main",
 "reply_to": "t-0001", "task_rev": 1, "asked_at": "…", "status": "open",
 "answer": null, "answered_at": null, "answer_request": null, "effects": []}
```

- `status`：`open`／`answered`／`cancelled`。書記（第 2 隊）照 open 的問題維護 `WAIT_USER.md`。
- 編號 `q-` 加 4 位以上數字，照資料夾最大號 +1。
- 冪等：同一份 ask 申請（看 `request`）再來＝回同一份動作；同一份 answer 申請（看 `answer_request`）再來＝回同一份動作；問題已被別份答覆答過＝`Closed`（郵差退信給人）。

## 答案怎麼到發問者

`on_answer` 回的後續動作：`{"do": "letter", "from": "human", "to": 發問者, "status": "DONE", "reply_to": "q-0003", "text": "問：…\n答：B"}`，
問題綁在單上（發問時問的人是那張單的負責人、單還沒結束；問題檔記 `task_rev`）時再加 `{"do": "step", "task": 單號, "event": {"type": "resume", "q": …, "rev": task_rev, …}}`；
狀態機只在單子正等這一題、rev 沒變時恢復。不是負責人問的、或單已結束的：問題照建、答案照寄，**不動單子**。
信頭（mail.md）：`【人 → worker-1 · 回覆 q-0003 · 09-25 10:03】`。

## 人的指令（第 1 隊）

- `aos-team wait ls [--json]`：一題一行 `q-0003  worker-1 問：…  選項：main / 開分支（預設 main）  [t-0001]`；沒有就印「沒有在等你回答的問題」。
- `aos-team answer q-0003 "文字"`：先讀那題（不在、已答＝退 1、說原因），再往 `team/outbox/human/` 放一份 answer 申請，印「已交給郵差」。有 `options` 而答案不在裡面照樣收（人可以講別的），多印一行提醒。
- talk 裡的 `/answer` 之後由 talk 那隊接。

## 借用：`access_request`、`persona_propose`（第二波 C 隊）

T-access-req、T-persona 這兩種申請**不另開新的 kind**，直接借用 `kind: ask`——模型自己改不到 `access.json`（B 隊地盤）
或人格（信任資料），批准與否本來就要走問人這條路，沒必要多開一種 kind 只為了同一件事。

- `access_request` 工具：把 `{name, path_hint, mode, why}` 組成一句 `question`，選項固定 `["同意", "不同意"]`。
- `persona_propose` 工具：把 `{text, why}` 組成一句 `question`，選項固定 `["同意", "不同意"]`。

兩者都**不會自動生效**：`aos-team answer` 只是把人的答案投回發問者，問句裡已經寫好人同意後要自己跑哪個指令
（`aos-agent access set`／`aos-agent persona append`——[persona.md](../agent/persona.md)）。這支工具本身不碰
`access.json`、不碰 prompts，郵差也不會照答案自動改表——「模型自己改不到」不是靠郵差把關，是這條路本來就沒有
自動寫入這一步。
