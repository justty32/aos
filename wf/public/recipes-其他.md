# wf/public/recipes-其他 — 第二意見、專區信、舊帳、權限測法、改文件、查證（任務類型→做法）

← [wf/public](README.md)｜[recipes 總頁](recipes.md)

每列一行做法，細節在出處。

<!-- wf-nav -->
| 要做的事 | 做法（一行） | 出處／細節 |
|---|---|---|
| 請 Argon 當第二意見 | 在 /tmp 跑 `agy -p … --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，內容貼進提示並在第一行寫明不准用工具（不寫會沒產出）；要它分 (A) 審查 (B) 提案 | [model-notes](model-notes.md)、[aos-teams/05](../workflows/dispatch/aos-teams/05-同機session與Argon.md) |
| 通知太多想清淨一段 | `wf/tools/quiet.py install`，再 `quiet.py 30m` | [tools/quiet](tools/quiet/README.md) |
| 寄信問使用者／要授權 | `aos-user send --kind … --from <線> --reply-to <stack>/mailbox`；拿 send 當檢查；每寄件人每小時 10 封 | [user-zone-mail](user-zone-mail.md) |
| 讀使用者專區的回信、驗授權 | `mailbox_read`（專區回信自動留在 `mailbox/archive/<信名>`），再跑 `aos-user verify`，見 `ok: matches` 才算 | [user-zone-mail「讀回信」](user-zone-mail.md) |
| 大批舊帳逐筆清 | 切 4 份派 opus 子 agent 唯讀並行，每筆歸 A 結案／B decide／C verify·chore，帶隊者核對後給頂層看再寄 | [team-patterns](team-patterns.md) |
| 驗換 uid 後碰不碰得到檔、殺不殺得到行程（不用 root） | `aos-asuser sub:N -- 程式`（真號＝起點＋N－1）；改 subuid 的檔用 `unshare --map-users … --map-root-user`；暫存夾放 /tmp | [權限與沙箱「免 root」](權限與沙箱.md) |
| 判斷 sudo NOPASSWD 准不准、換身分 | 不信 `sudo -n -l`；真跑 `sudo -n -k … /usr/bin/true` 看退 0；一律帶 `-k`；共用夾只 mkdir 不 chmod | [權限與沙箱「sudo」](權限與沙箱.md) |
| 在家機測 cgroup v2 程式 | `systemd-run --user --scope --collect -p Delegate=yes -p TimeoutStopSec=2s`，收尾 cgroup.kill→stop→reset-failed；有 swap 要 `memory.swap.max=0` | [權限與沙箱「transient scope」](權限與沙箱.md) |
| 改寫全場必讀的規矩檔 | 子 agent 只寫草稿夾 → 全文先抄進 archive → 「舊條文→新位置」表請沒看過表的人對 → 逐檔 git log 後一口氣換上、一個 commit | [改文件與知識庫](改文件與知識庫.md) |
| 量文件好不好查 | 定十來題，請沒看過這條線的 agent 從入口只跟連結走，記走不走得到與讀了多少 bytes；改完換一隻再走 | [改文件與知識庫「請新人照索引走」](改文件與知識庫.md) |
| 給外人照打的文件、要公開的檔 | 用 doc-run 照字實跑頁面的 bash 區塊；scan 掃個人值與金鑰；有動畫的頁截圖加 `--virtual-time-budget` | [發佈前檢查](發佈前檢查.md) |
| 派小修之前 | `git log --oneline <基底>..HEAD -- <要動的檔>` 看有沒有人做了；advices 那條先標「已排入（線名）」 | [設計與查證](設計與查證.md) |
| 想看活樹的檔（哪份碼在跑、誰在用某變數） | 先把路徑一條條列給部長，點了名才看，或請頂層代查；不讀 `/proc/*/environ` | [活樹旁邊「唯讀查看」](活樹旁邊.md) |
| 查祕密有沒有擴散 | 值不落地成檔：行程內比對只印檔名或只比雜湊；`grep -l`、只取等號左邊 | [活樹旁邊「查祕密」](活樹旁邊.md) |
| 寫紀錄或訂截止時刻 | `peek_now_time {"local": true}`；信的 `sent_at` 是 UTC，家機加 8 小時 | [等隊員與讀信「記時刻」](等隊員與讀信.md) |
| 改動會蓋掉使用者舊裁定 | 先找他當時看到的原文（專區、`proto8/user-advice/`）；找不到寄 decide，選項寫明蓋掉哪一天哪一條 | [設計與查證](設計與查證.md) |
| 自己寫 agent 定義、換定義 | eca 的 `cli.json` 加 `"settings": {"autoMemoryEnabled": false}`；換定義用 `ctl set-def`（subagent 掛的不行）；複製後重寫 README | [定義與換定義](定義與換定義.md) |
| 帶 kernel_gate 的樹、獨佔資源上鎖 | 主導每輪做短、下屬 `KernelFailed` 等十幾秒重試；遊戲、桌面這類由主導點名給鎖 | [gate與鎖](gate與鎖.md) |
