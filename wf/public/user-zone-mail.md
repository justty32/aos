# wf/public/user-zone-mail — 經使用者專區寄信、讀回信、照授權動手

← [wf/public](README.md)｜專區本身見知識庫 `aos/user_zone.json`；授權規矩見 AGENTS.md 鐵律 2

每條：適用、做法、驗過、出處、投稿。

## 寄信、讀回信、照授權刪檔

- **適用**：要問使用者、請他做事、或要他授權 push／刪檔，經使用者專區（`~/.aos/user`）寄信與讀回信。
- **驗過**：ok-pilot 11-14 實測。兩批共 14 封寄進專區；十多封回信都跑過 `aos-user verify`（level 1）；照驗過的回信刪了 `~/.cache/aos-mcp-aos`。
- **出處**：`wf/temp/ok-pilot/notes.md` 兩節「摩擦」、`wf/temp/ok-pilot/wu/`（SUMMARY.md、answers.md、sent-batch*.log）；commit f1e3067f1、ca312c499、00e78de85
- **投稿**：ok-pilot（`專區寄信與讀回信.md`）

### 寄

- 指令：`~/aos-home/ws/tools/aos-user/aos-user send --kind <decide|verify|chore|fyi> --from <線名> --reply-to <自己 stack>/mailbox FILE.json`。
- **拿 `aos-user send` 本身當檢查**：有些規則 `schema/letter.json` 看不出來，自己寫的檢查會漏。例：fyi 信的 status 只能是 DONE、FAILED、BLOCKED（schema 的 enum 還列了 NEEDS-USER），否則退件 `SchemaBad fyi status must be one of DONE, FAILED, BLOCKED`。
- **每個寄件人每小時最多 10 封**，超過就分批、隔一小時寄下一批。
- decide 信一封最多 7 題，每題要有 `id`、`question`、`eli5`、`options`、`recommend`。
- push、刪檔、對外的題寫 `risk: irreversible`，不能帶 `default_if_silent`。
- schema 沒有的頂層鍵（例 `details`）不要放，內容併進 `what`。
- 會變的數字（例「幾個 commit 沒推」）寄出當下才查、才填：重跑來源腳本，改稿時保留舊稿（ok-llmk2 稿裡寫 62%，寄出前重跑變 60%，標題跟著改）。
- 後果寫清楚誰動手（例「推由頂層做」），不要寫成寄信那條線做。

### 題目怎麼寫（11-14 收尾補）

- 每題把「我推薦哪個、為什麼」寫進去；選項要真的都能做，使用者會選不是推薦的那個（ok-kb 五封十一題、head-tools 五題各有一題這樣）。
- 題目第一句寫結論；正文老實寫效果的量級與但書（「效果不大」就寫出來）；會改到使用者舊裁定的，標題就寫出來並附原話出處（怎麼找原話見 [設計與查證](設計與查證.md)）；部長自己裁掉的小題在正文報備。
- 回信驗過再轉給線，轉的時候附兩個信名（題目與回信）。
- 使用者多半在看全景頁，寫得清楚的題幾分鐘內就回。
- 出處：`wf/temp/{ok-kb,head-tools,ok-view}/wrapup-1114/經驗.md`；`wf/temp/head-tools/decide-*.json`

### 讀回信

- **讀信用 `mailbox_read` 就好**：專區回信（含退信）讀完會自動留在 `<stack>/mailbox/archive/<信名>/`，並印一行 `(unverified user-zone reply: kept in …)`（ace14088d 起；以前要加 `{"keep": true}`，現在加了也不會壞；指令帶 `--drop` 才回到讀完就刪）。拿 `done/` 底下的 reply.json 去驗不行：`VerifyBad not a user-zone reply`。
- 對 `<stack>/mailbox/archive/<信名>` 跑 `aos-user verify`，看到 `ok: matches ...` 才算數。push、刪檔的授權尤其要這樣驗。
- 回信 `via: cli` 的 push 授權，頂層還會當面再確認一次。
- verify、chore 信，使用者回「好」只代表答應會做，不等於做完；等他回「跑好了」才結帳。有旁證（例 `sudo -n -l`、`id <帳號>`）就順手查。

### 照授權刪檔

- **授權只蓋題目寫到的那個檔、那個版本**：使用者答「刪：只刪這一個檔」之後又冒出第二份（`/dev/shm` 那份），不能順手一起刪，另寄一題（head-comm，信 01794635023534900726.3503759.2360918、01794635137582995464.3574411.2372323）。「准裝 v2.0」不含 v1 的修正（ok-view）。
- 回信驗過、頂層也准了才動手。刪之前把 `ls -laR <夾>` 存進紀錄，只 `rm -r` 那一夾，刪完再 ls 確認已不在。
