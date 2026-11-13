# kernel 限資源與設 uid（線限 11-13 晚規劃，未施工）：kernel 只定政策、把限制與身分寫進放行的信，daemon 在 fork 時真的套（setrlimit、二期 cgroup、免 root 的 subuid 換身分），bwrap 照舊管看得到什麼，要 root 的隔成預設不裝的包；11-13 22:15 使用者裁：cgroup 可選（推薦預設關）、群組多挖用法（挖出各自 subgid＋隊伍群組＋ACL，推薦 K6 改它）、先以無 root 規劃，其餘照推薦；新待裁 K12～K16

← [11-13 日索引](README.md)｜分檔夾 [kernel-limits-plan/](kernel-limits-plan/README.md)

> 流程照使用者 11-13 晚定的：opus 帶隊（線限）→ 四隻 sonnet 唯讀搜集 → opus 匯總成備料 → fable 只讀備料設計 → opus 細化對到檔案 → **到此停**。沒起 aos 行程、沒叫真腦、沒碰 `~/aos-home`、沒用 sudo；試驗只在 scratchpad 用 unshare／setpriv／prlimit。

## 使用者原話（逐字）

「對了，我這邊還有個東西想請你跑規劃：讓kernel可以用setrlimit限制資源，還有權限，設置uid這塊。」

## 使用者裁定（11-13 22:15、22:17，逐字）

- 22:15：「astra八題這塊都按照推薦。限制資源這塊十一題：cgroup這塊要可選。群組這塊可以再多挖一些用法。要root的做法可以想想，但先以沒有root的情況做規劃。」
- 22:17（頂層轉來）：「限制資源那塊，我沒說的就按照推薦」

落定（逐題見 [05](kernel-limits-plan/05-待裁與衝突.md#使用者裁定11-13-22152217)）：

- **K3 cgroup 可選**：daemon.json `cgroup: off｜auto｜on`，推薦不寫＝`off`；`auto` 沒委派就降級並警告。開與不開的差別：不開只有「每個行程各自的上限」，開了才有「這隻連子孫加總」，eca 身的記憶體只有開了才管得到（[07](kernel-limits-plan/07-cgroup可選.md)）。
- **K6 群組**：多挖了十種用法並實測（隊伍共寫夾、唯讀分享夾、金鑰門、可改不可刪、投遞箱、stack 不用 chown…，[08](kernel-limits-plan/08-群組用法.md)）；多出選項 C「各自 subgid＋隊伍群組＋預設 ACL 把使用者加進去」，推薦改 C，**仍待裁**。
- **K8 先以沒有 root 規劃**：主規劃全免 root；有 root 能多做什麼只寫草案（[09](kernel-limits-plan/09-有root的話.md)）。
- **K1、K2、K4、K5、K7、K9、K10、K11 照推薦**（使用者明說：「限制資源那塊，我沒說的就按照推薦」）。
- 新冒出的待裁：K12 cgroup 預設值、K13 要不要有 `on`、K14 `stop` 用 `cgroup.kill`、K15 隊伍群組誰定、K16 ACL 誰設（推薦見 05）。

## 一張圖

```
使用者帳號 lorkhan(1000)＝一棵樹（含名下 subuid 100000～165535）
│
├ kernel 站（掛 proc 那一包）   政策：limits.default／max／by_sender、users 表
│    放行時改信：自帶 limits 夾進 max、丟掉自帶 user／groups、照表填 user＋groups
│
├ daemon（fork 子行程）          保底與機制
│    limits_max 天花板（超過＝LimitBad）→ setrlimit（cpu hard＝soft＋1）
│    → 進 cgroup 格（可選：cgroup off｜auto｜on，推薦預設 off）
│    → 換 uid sub:N＋groups（每支自己一個 user ns，免 root）
│    → 起前替 stack 設 ACL（u:sub:N、u:lorkhan）
│    → 收屍翻譯 limit_hit（SIGXCPU→cpu_s、SIGXFSZ→file_mb、OOM→mem）
│
├ 共用夾（aos-share 設 ACL）     隊夾 2770、分享夾、金鑰夾、投遞箱 1730＋預設 ACL
│
├ aos-sandbox（呼叫方自己包）    bwrap：看得到哪些夾、網路；user 多認 sub:N
│
└ proc（agent 身、腦、工具）     aos-exec 只管牆鐘 timeout_ms，不變
```

## 結論幾句

- **daemon 早就會 setrlimit 與換帳號**（11-05 做的 `limits`；換帳號要 root）。缺的是 kernel 站不會附限制、`{}` 一封信就能解除限制、cpu 到頂看起來像被 kill、`procs` 在同一個 uid 下不能用。
- **不同 agent 不同 uid 免 root 做得到**：家機的 subuid＋`newuidmap` 實測可換成真的 100004，讀不到使用者 600 的檔、殺不到使用者的行程；群組對到使用者主群組，使用者照樣改得動 agent 寫的檔。
- 要 root 的（真帳號、helper、sudoers）照 11-12「先不做」；22:15 使用者也說「先以沒有root的情況做規劃」，有 root 能多什麼另寫草案 [09](kernel-limits-plan/09-有root的話.md)。
- **群組免 root 能做的比想的多**：使用者在自己的夾上就能寫別的 uid／gid 的 ACL（X14），隊與隊分得開、使用者照改得動 agent 的檔、投遞箱只能丟不能看（[08](kernel-limits-plan/08-群組用法.md)）。

## 分檔

| 檔 | 內容 |
|---|---|
| [01 備料](kernel-limits-plan/01-備料.md) | 原話、各層現況表、家機環境、相關問題 |
| [02 fable 設計](kernel-limits-plan/02-fable設計.md) | fable 原稿 |
| [03 opus 細化](kernel-limits-plan/03-opus細化.md) | 跟 fable 不同的 8 處、分層定稿對到檔、kernel.json 新鍵、邊緣狀況 |
| [04 施工與驗收](kernel-limits-plan/04-施工與驗收.md) | 段 1 daemon 收緊、段 2 kernel 附限制、段 3 subuid＋群組／ACL、段 4 cgroup（可選）、段 5 root（不做） |
| [05 待裁與衝突](kernel-limits-plan/05-待裁與衝突.md) | 22:15 裁定、新待裁 K6（改版）與 K12～K16、原題 K1～K11、衝突 C1～C7 |
| [06 試驗紀錄](kernel-limits-plan/06-試驗紀錄.md) | X1～X28 實測、撞到的問題 L1～L10 |
| [07 cgroup 可選](kernel-limits-plan/07-cgroup可選.md) | 開關 `off｜auto｜on`、開與不開的差別、K12～K14 |
| [08 群組用法](kernel-limits-plan/08-群組用法.md) | 十種用法（做法／實測／代價／推薦）、K6 選項 C、號段、K15～K16 |
| [09 有 root 的話](kernel-limits-plan/09-有root的話.md) | 草案：真帳號、helper、sudoers、cgroup 委派、照 uid 管網路與磁碟… |
