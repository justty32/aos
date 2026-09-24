← [team](README.md)

# 信與申請

成員只能往自己的 `team/outbox/<名>/` 放檔（牢裡是 `/work/outbox`）。一個檔＝一封信或一份申請；有 `kind` 欄的是申請，沒有的是信。
**寄件人身分看檔在哪個 outbox**，檔裡的 `from` 只是抄寫；對不上＝`NotSender`，郵差退件。

## 檔名與 id

- 檔名 `<id>.json`，`id`＝`<epoch ns>-<pid>-<寄件人>`（例 `1790000000123456789-4242-worker-1`）；寄件人段要等於資料夾名（`BadId`）。
- 先寫暫存檔（`.` 開頭、`.tmp` 結尾）再 rename，郵差只收不以 `.` 開頭的 `*.json`。
- 郵差自己生的信（任務單的後續動作）`from` 是 `post`，id 由郵差定（建議 `<觸發它的 id>.e<第幾個動作>`，重跑算出來一樣）；id 只准英數與 `. _ ~ -`。

## 信

```json
{"id": "1790000000123456789-4242-worker-1", "from": "worker-1", "to": "lead", "status": "DONE",
 "reply_to": "t-0001", "rev": 1, "text": "導入完成，四條殘留都是 0。", "at": "2026-09-25T10:00:00+08:00"}
```

| 鍵 | 型別 | 意思 |
|---|---|---|
| `id`、`from`、`at` | 字串 | 見上；`at` 是 ISO 8601 含時區 |
| `to` | 字串 | 收件人：寄件人 `mail_to` 裡的名字（`human` 寄的可以是任何成員） |
| `status` | 字串 | 只准 `REQUEST`、`DONE`、`BLOCKED`、`NEEDS-USER`、`FAILED`、`PROGRESS`（`BadStatus`） |
| `reply_to` | 字串或 null | 回的是哪件：任務單號 `t-0001`、審查子單 `t-0001.r1`、問題 `q-0001`、或一封信的 id |
| `rev` | 整數或 null | 回任務單時**要寫**那張單目前的 rev；舊 rev 的回報只記下、不改狀態（tasks.md） |
| `text` | 字串 | 內容，非空、≤ 20000 字 |

其他鍵＝`FormatInvalid`。六個 STATUS 的意思照 workflows 的 inbox 協議：接了事一定要回終局狀態（DONE／BLOCKED／NEEDS-USER／FAILED）；`FAILED`＝終止、不再自己重試。

## 郵差怎麼投（第 2 隊實作，這裡定介面）

- 收件人是成員：投成它 `input/` 裡的 **`mail-<id>.json`**，內容是一則 user 訊息：`aos_team_format.mail_message(信, tz)`。
  投法用 `aos_agent_say.drop_new(資料夾, 檔名, 訊息)`：暫存檔＋`link`，**不覆蓋**；回 False＝同名已在（當作投過了）。
- **去重（崩了重跑不重投）**：`drop_new` 只擋「還在 input 裡」的。投之前先叫 `aos_team_format.already_delivered(收件人的家, 檔名)`，
  三處任一有就當投過：`input/<檔名>`、`input/done/<檔名>.<消費 id>.done`（已收走的封存）、`state.json` 的 `intake.files`／`consuming` 的 `src`（正在收）。
  所以**封存檔在郵差把投遞紀錄寫好之前不准清**（agent state.md §4.1 的封存本來就不自動清）。
- **後續動作的信 id 要固定**：同一個觸發（信、申請、驗收結果）的第 k 個動作永遠是同一個 id（建議 `<觸發 id>.e<k>`；巢狀的 `step` 再往下加 `.e<k>`），重跑算出來一樣，去重才有效。
- 訊息第一行是信頭 `aos_team_format.render_header()`：
  `【來信 lead → worker-1 · REQUEST · t-0007 rev1 · 09-25 10:03】`；人回答問題時是 `【人 → worker-1 · 回覆 q-0003 · 09-25 10:03】`。
  agent 只在閒著時收輸入、一次可能收好幾封、同一次照檔名排不照時間，所以信頭一定帶時間。
- 收件人是 `human`：放進 `team/human/`（人的收件匣）。
- 讀 outbox 檔用 `aos_team_format.read_outbox_file(路徑, 名冊)`：驗檔名、身分、格式、`mail_to`；回 `('letter', 信)` 或 `('request', 申請)`；不合丟 `TeamError`（代號 `NotSender`、`BadId`、`BadRecipient`、`BadStatus`、`FormatInvalid`、`UnknownKind`、`JsonSyntax`）。
- 每封信處理時叫 `aos_team_task.on_letter(lay, 名冊, 信)`。**派工信**（後續動作裡帶 `dispatch` 的那封）投進 input 之後叫 `letter_delivered(lay, 信, dispatch)`，被收走（從 `input/` 消失）之後叫 `letter_picked_up(lay, 信, dispatch)`；別的信不用叫（叫了也不推狀態）。三支都回後續動作清單（tasks.md）。

## 申請

共同欄位 `id`、`from`、`kind`、`at`（同信），再加各種類自己的欄位。種類與處理函式登記在 [`lib/aos_team_requests.py`](../../lib/aos_team_requests.py) 的 `KINDS`：

| kind | 誰能寄 | 欄位 | 處理 |
|---|---|---|---|
| `handoff` | 模板 may 有它的（領隊）、人 | `assignee`、`workflow`（入口檔；沒有寫「無」）、`goal`、`done_when`（非空）、`facts`?、`max_attempts`?（1～10，預設 3）、`deadline_minutes`? | 開任務單並派給負責人（tasks.md） |
| `cancel` | 人、開單人 | `task`、`reason`? | 單子 → cancelled，通知負責人停下 |
| `reassign` | 人、開單人 | `task`、`assignee` | rev+1、attempt 歸 1、換負責人、重派 |
| `review_result` | 那張審查子單的負責人 | `task`（`t-0001.r1`）、`items`：`[{"i": 0, "pass": true, "why": "…"}]` 每條都要回 | 子單 done，父單收到 reviewed（tasks.md） |
| `ask` | 模板 may 有它的、人 | `question`、`options`?、`default`?（要在 options 裡）、`reply_to`? | 建問題（ask.md） |
| `answer` | 只有人 | `q`、`text` | 投回發問者（ask.md） |
| `compact` | 模板 may 有它的（領隊、工人；`compact_me` 工具）、人 | `member`?（只有人能替別人寄）、`keep_rounds`?、`max_tokens`?、`reason`? | 投進那個成員家的 `compact-req/`，閒著時 tick 縮記憶（[compact-more.md §5](../agent/compact-more.md)） |

`done_when` 每條：`{"kind": "file_exists", "path": …}`、`{"kind": "table_filled", "path": …, 其他參數…}`、`{"kind": "check", "name": 檢查器名, "args": {…}?}`、`{"kind": "cmd_ok", "run": [指令…], "timeout_s": 秒?}`（第二波，要在 `team.json` 白名單裡）、`{"kind": "judge", "text": 要審查員判的一句}`。前四種是驗收員跑的，`judge` 給審查員。郵差收申請時另外驗路徑與操作（[wall.md §3](wall.md)）。

**處理函式的約定**：`handler(lay, 名冊, 申請) → 後續動作清單`；不接受就丟 `TeamError(代號, 白話)`，郵差把原檔搬進 `outbox/<名>/rejected/`、退一封 `FAILED` 給寄件人（白話照抄）。**同一份申請再叫一次要回同一份動作、不多做**。權限（模板的 `may`）由 `aos_team_requests.handle()` 先查。
別隊加種類：在 `KINDS` 加一行 `'kind': '模組:函式'`，欄位自己驗。
