# wf/public/user-zone-mail — 經使用者專區寄信、讀回信、照授權動手

← [wf/public](README.md)｜指令兩行在 [aos-teams 入口第 2 件](../workflows/dispatch/aos-teams.md)；專區本身見知識庫 `aos/user_zone.md`；授權規矩見 AGENTS.md 鐵律 2

## 寄信、讀回信、照授權刪檔

要問使用者、請他做事、或要他授權 push／刪檔時，經使用者專區（`~/.aos/user`）寄信與讀回信。

### 寄

- 指令：`aos-user send --kind <decide|verify|chore|fyi> --from <線名> --reply-to <自己 stack>/mailbox FILE.json`。
- **拿 `aos-user send` 本身當檢查**：有些規則 `schema/letter.json` 看不出來，自己寫的檢查會漏。例：fyi 信的 status 只能是 DONE、FAILED、BLOCKED（schema 的 enum 還列了 NEEDS-USER），否則退件 `SchemaBad fyi status must be one of DONE, FAILED, BLOCKED`。
- **每個寄件人每小時最多 10 封**，超過就分批、隔一小時寄下一批。
- **從沒收過信、stack 底下還沒有 `mailbox/` 也能直接寄**：回信地址是自己的 `$AOS_STACK/mailbox` 時，`aos-user send` 先替你建好（照 `aos-post init`），stderr 印一行 `made your reply mailbox …`。`--reply-to` 指到別處、`$AOS_STACK` 沒設或 stack 夾不在的，不建，照舊報 `MailboxMissing`，錯誤句後面寫原因與修法。
- decide 信一封最多 7 題，每題要有 `id`、`question`、`eli5`、`options`、`recommend`。
- push、刪檔、對外的題寫 `risk: irreversible`，不能帶 `default_if_silent`。
- schema 沒有的頂層鍵（例 `details`）不要放，內容併進 `what`。
- 會變的數字（例「幾個 commit 沒推」）寄出當下才查、才填：重跑來源腳本，改稿時保留舊稿。
- 後果寫清楚誰動手（例「推由頂層做」），不要寫成寄信那條線做。

### 題目怎麼寫

- 每題把「我推薦哪個、為什麼」寫進去；選項要真的都能做，使用者常會選不是推薦的那個。
- 題目第一句寫結論；正文老實寫效果的量級與但書（「效果不大」就寫出來）；會改到使用者舊裁定的，標題就寫出來並附原話出處（怎麼找原話見 [設計與查證](設計與查證.md)）；寄題的人（工作室是 eca-aos）自己裁掉的小題在正文報備。
- 回信驗過再轉給線，轉的時候附兩個信名（題目與回信）。
- 使用者多半在看全景頁，寫得清楚的題幾分鐘內就回。
- **等很久沒回信時，先看使用者的公告**：`aos-user announce`（沒有就印 `no announcement`）或 `aos-user door`，也就是 `~/.aos/user/door.json` 的 `announce`（`text`、`at`、`until`；`until` 是 null＝掛到他收掉）。這兩個指令不印過期的；自己直接讀 `door.json` 可能還看到過期那格，要自己比 `until`，過了就不算。公告說他不在，就等，不催、不重寄、不另外問。公告不會主動通知誰，要自己去看；只有使用者能貼和收，agent 不寫。

### 讀回信

- **讀信用 `mailbox_read` 就好**：專區回信（含退信）讀完會自動留在 `<stack>/mailbox/archive/<信名>/`，並印一行 `(unverified user-zone reply: kept in …)`（指令帶 `--drop` 才讀完就刪）。拿 `done/` 底下的 reply.json 去驗不行：`VerifyBad not a user-zone reply`。
- **照答案動手前先讀每題的留言**：回信的 `answers` 每題是 `{id, answer, differs}`，使用者對那題留了話才多一格 `comment`；`answer` 是 `other`（他自己的答案）時，答案在那題的 `comment` 或整封的 `note`。`answer_line` 也帶留言（`q1:a「留言」、q2:other*「留言」（備註：…）`）。留言可能改了選項的意思（例「選 a，但只用在示範」）。
- 對 `<stack>/mailbox/archive/<信名>` 跑 `aos-user verify`，看到 `ok: matches ...` 才算數。push、刪檔的授權尤其要這樣驗。
- 回信 `via: cli` 的 push 授權，頂層還會當面再確認一次。
- verify、chore 信，使用者回「好」只代表答應會做，不等於做完；等他回「跑好了」才結帳。有旁證（例 `sudo -n -l`、`id <帳號>`）就順手查。

### 照授權刪檔

- **授權只蓋題目寫到的那個檔、那個版本**：使用者答「刪：只刪這一個檔」之後又冒出第二份（`/dev/shm` 那份），不能順手一起刪，另寄一題。「准裝 v2.0」不含 v1 的修正。
- 回信驗過、頂層也准了才動手。刪之前把 `ls -laR <夾>` 存進紀錄，只 `rm -r` 那一夾，刪完再 ls 確認已不在。
