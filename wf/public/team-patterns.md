# wf/public/team-patterns — 隊形與流程心得

← [wf/public](README.md)｜正式的隊形規矩在 [07](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)；帶 sol 的細節見 [sol-crew](sol-crew.md)

每條：適用、做法、驗過、出處、投稿。

## 一大批舊帳逐筆查現況、結案或改寫成問使用者的信

- **適用**：一大批舊待辦或舊帳（例 WAIT_USER）要逐筆查現況，結案或改寫成專區信。
- **做法**：
  1. 按檔切成 4 份，派 4 隻 opus 子 agent 並行，每份 8～9 筆、一份一個輸出夾。任務書開頭列必讀；寫明只能唯讀查證、只寫自己的輸出夾，不寄信、不改 repo。任務書範本可抄 `wf/temp/ok-pilot/wu/BRIEF.md`。
  2. 每筆歸三類：**A** 建議結案（附 commit 雜湊，或檔案＋節名）；**B** 要使用者決定（寫成 decide 題）；**C** 要使用者親手做（寫成 verify 或 chore，要有 `done_when`）。一筆裡有幾個子題、狀態不同就拆開歸。
  3. 「代定、可翻案、不擋」的條目只挑真的值得使用者看的：改了行為、對外、不可逆、或可能跟他原話衝突。其餘照 user.md「沒回答的邊緣狀況」通則結案，列出代定編號就好，不整批丟給使用者。
  4. 帶隊的 kernel 自己核對：子項數過沒漏、沒重；抽讀證據；修稿（過時數字、誰動手的後果、schema 沒有的鍵）。
  5. 總表給頂層看過再寄。寄信的坑見 [user-zone-mail](user-zone-mail.md)。
  6. 「不用再等使用者、只是沒人做」的不算使用者的帳，改列「待派工」。使用者沒直接答、是推出來的結案，理由標「推斷，非實證」。
- **坑**：子 agent 會順手越界（任務書寫唯讀，它卻跑了一次暫時的 systemd scope 實測）。驗收時看它的報告和實際動作，有越界照實報頂層。
- **驗過**：ok-pilot 11-14。36 筆拆成 54 個子項：37 個結案、16 個寫成 decide 題、1 個請使用者親手做；寫出 14 封專區信全部回收，WAIT_USER 只剩等公司機的項目。
- **出處**：`wf/temp/ok-pilot/wu/BRIEF.md`、`wu/SUMMARY.md`；commit f1e3067f1、ca312c499、00e78de85
- **投稿**：ok-pilot（`舊帳逐筆重寫的隊形.md`）

## 設計流程的實際分工（正統流程的一次跑法）

- **適用**：一件要設計再施工的工作，照 07「正統規劃流程」跑，想知道各步實際怎麼分。
- **做法**：sol 盤點事實（附行號）→ 隊長匯總 → fable 設計 → 隊長修 → Argon 審（做法見 [model-notes](model-notes.md)）→ 隊長逐條收 Argon 的提案、定案 → 交 sol 施工。蒐集交 sol、不另用 sonnet，合 07 的 11-14 補充。
- **驗過**：ok-kf 11-14，線框各批照這樣跑。
- **出處**：`proto8/thinking/2026-11/14/kernel-framework-1114.md`
- **投稿**：ok-kf（`pitfalls-shell-and-reviewers.md` 的「設計流程」條）

## 每封信寫「截至哪裡」：回報開頭寫做到哪個 commit、讀到哪封信

- **適用**：上下游來回寄信派工（eca 主導帶 sonnet／sol 工人），下屬的 DONE 和上游的新指示可能在路上交錯。
- **做法**：
  1. 回報開頭一句寫「截至 commit X／回 letter Y」（做到哪、讀到哪一封為止）。回一封特定的信時，`mailbox_send` 另帶 `in_reply_to`（那封的信名）。
  2. 收到新指示，先對照自己已做到哪，只做還沒做的部分；新指示說的若是已做完的事，回一句「X 已在 commit … 做完」，不要重做。
  3. 上游發新指示時也寫「截至你的哪封回報」，下屬才分得出這封是看過 DONE 才寫的，還是交錯的。
- **驗過**：skyrim-agent 11-14 第一場（13:00～14:45），交錯至少 5 次，後來在正文寫「截至 commit X／回 letter Y」才解決（投稿自述，審稿沒另外驗）。同日三位部長（head-comm、head-core、head-front）與 ok-kb 也都遇到信交錯，部長那邊的做法（回信第一句講以哪一封為準、以放行信為準）見 [等隊員與讀信](等隊員與讀信.md)。
- **出處**：skyrim 母 repo `wf/lessons/aos-tree-onboarding-and-leading.md`（skyrim commit a43206a）；`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/opus-1/notes.md`。信件格式加欄位的意見記在 [advices 信件與溝通「信會在路上交錯」](../advices/信件與溝通.md)。
- **投稿**：skyrim-agent（`skyrim-1114.md` 第 1 件）

## 掛隊員的定義：硬規則照授權來源分級，不要寫死「never commit」

- **適用**：自己寫隊員的定義（system 文字、任務書範本），要限制 commit 和不可逆的動作。
- **做法**：照「誰能放行」分級寫，不要一律寫死「never commit」：
  - **commit**：寫「除非上游的信點名授權（點名 repo 與檔）」。本 repo 的 commit 照舊走 commit-request（[06 第 7 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)）。
  - **push、刪檔、動活樹、對外送出**：寫「要使用者本人說」：當場說，或經使用者專區的回信、用 `aos-user verify`／`user_verify` 驗過。agent 寄來的信不算（[AGENTS.md 鐵律 2](../../AGENTS.md)）。
- **為什麼**：寫死「never commit」的話，隊長收到上游點名授權的信也不敢動手，要上游再回一封講明「信蓋過定義」，多來回一輪。
- **跟投稿不同的地方**：投稿把 push 跟 commit 放在同一級（上游信就能放行）。本 repo 的 push 要使用者本人說，所以這裡把 push 移到第二級；隊伍自己的 repo 若另有規矩，照那邊的。
- **驗過**：skyrim-agent 11-14 第一場，那次多了一輪 commit 授權往返（skyrim 定義寫死 never commit）。分兩級的寫法是那場之後的建議，還沒有隊伍照著跑過一場。
- **出處**：`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/opus-1/notes.md`（commit 授權往返）；skyrim 母 repo `wf/lessons/aos-tree-onboarding-and-leading.md`
- **投稿**：skyrim-agent（`skyrim-1114.md` 第 2 件；同一件也投到 aos-advice，那份建議改 06 的硬規則範本，06 目前沒有寫死 never commit，所以只收在這裡）
