# wf/public/recipes-其他 — 第二意見、專區信、舊帳、權限測法、改文件、查證（任務類型→做法）

← [wf/public](README.md)｜[recipes 總頁](recipes.md)

每列只寫一行做法與出處，細節在出處。投稿：只追加列；做法變了改那一列並在「驗過」欄換日期。狀態：**驗過**＝有人實際照做成功；**聽說**＝文件有寫、還沒人回報照做過。

| 要做的事 | 做法（一行） | 出處／細節 | 驗過 |
|---|---|---|---|
| 請 Argon 當第二意見 | 在 /tmp 跑 `agy -p … --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，內容貼進提示並寫明 `Do not use any tools`（不寫會沒產出）；要它分 (A) 審查 (B) 提案 | [05「Argon 是參與者」](../workflows/dispatch/aos-teams/05-同機session與Argon.md)、[model-notes](model-notes.md) | 11-14 ok-skyrim、ok-astra、ok-kf、ok-llmk2 |
| 通知太多想清淨一段 | `wf/public/tools/quiet`：`quiet.py install` | [tools/quiet](tools/quiet/README.md) | 11-14 repo-aos |
| 寄信問使用者／要授權 | `aos-user send --kind … --from <線> --reply-to <stack>/mailbox`；拿 send 當檢查；每寄件人每小時 10 封 | [user-zone-mail](user-zone-mail.md) | 11-14 ok-pilot |
| 讀使用者專區的回信、驗授權 | `mailbox_read`（專區回信自動留在 `mailbox/archive/<信名>`，ace14088d 起不必加 keep），再跑 `aos-user verify`，見 `ok: matches` 才算 | [user-zone-mail「讀回信」](user-zone-mail.md) | 11-14 ok-pilot |
| 大批舊帳逐筆清 | 切 4 份派 opus 子 agent 唯讀並行，每筆歸 A 結案／B decide／C verify·chore，帶隊者核對後給頂層看再寄 | [team-patterns](team-patterns.md) | 11-14 ok-pilot |
| 驗換 uid 後碰不碰得到檔、殺不殺得到行程（不用 root） | `aos-asuser sub:N -- 程式`（真號＝起點＋N－1）；改 subuid 的檔用 `unshare --map-users … --map-root-user`；暫存夾放 /tmp | [權限與沙箱「免 root」](權限與沙箱.md) | 11-14 ok-sec |
| 判斷 sudo NOPASSWD 准不准、換身分 | 不信 `sudo -n -l`；真跑 `sudo -n -k … /usr/bin/true` 看退 0；一律帶 `-k`；共用夾只 mkdir 不 chmod | [權限與沙箱「sudo」](權限與沙箱.md) | 11-14 ok-limits |
| 在家機測 cgroup v2 程式 | `systemd-run --user --scope --collect -p Delegate=yes -p TimeoutStopSec=2s`，收尾 cgroup.kill→stop→reset-failed；有 swap 要 `memory.swap.max=0` | [權限與沙箱「transient scope」](權限與沙箱.md) | 11-14 ok-limits |
| 改寫全場必讀的規矩檔 | 子 agent 只寫草稿夾 → 全文先抄進 archive → 「舊條文→新位置」表請沒看過表的人對 → 逐檔 git log 後一口氣換上、一個 commit | [改文件與知識庫](改文件與知識庫.md) | 11-14 ok-kb |
| 量文件好不好查 | 定十來題，請沒看過這條線的 agent 從入口只跟連結走，記走不走得到與讀了多少 bytes；改完換一隻再走 | [改文件與知識庫「請新人照索引走」](改文件與知識庫.md) | 11-14 ok-kb |
| 派小修之前 | `git log --oneline <基底>..HEAD -- <要動的檔>` 看有沒有人做了；advices 那條先標「已排入（線名）」 | [設計與查證](設計與查證.md) | 11-14 ok-misc |
| 想看活樹的檔（哪份碼在跑、誰在用某變數） | 先把路徑一條條列給部長，點了名才看，或請頂層代查；不讀 `/proc/*/environ` | [活樹旁邊「唯讀查看」](活樹旁邊.md) | 11-14 ok-kb、ok-limits |
| 查祕密有沒有擴散 | 值不落地成檔：行程內比對只印檔名或只比雜湊；`grep -l`、只取等號左邊 | [活樹旁邊「查祕密」](活樹旁邊.md) | 11-14 ok-board、ok-kf |
| 寫紀錄或訂截止時刻 | `peek_now_time {"local": true}`；信的 `sent_at` 是 UTC，家機加 8 小時 | [等隊員與讀信「記時刻」](等隊員與讀信.md) | 11-14 head-comm、head-tools |
| 改動會蓋掉使用者舊裁定 | 先找他當時看到的原文（專區、`proto8/user-advice/`）；找不到寄 decide，選項寫明蓋掉哪一天哪一條 | [設計與查證](設計與查證.md) | 11-14 head-core |
