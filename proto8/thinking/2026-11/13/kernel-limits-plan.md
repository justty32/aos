# kernel 限資源與設 uid（線限 11-13 晚規劃，未施工）：kernel 只定政策、把限制與身分寫進放行的信，daemon 在 fork 時真的套（setrlimit、二期 cgroup、免 root 的 subuid 換身分），bwrap 照舊管看得到什麼，要 root 的隔成預設不裝的包

← [11-13 日索引](README.md)｜分檔夾 [kernel-limits-plan/](kernel-limits-plan/README.md)

> 流程照使用者 11-13 晚定的：opus 帶隊（線限）→ 四隻 sonnet 唯讀搜集 → opus 匯總成備料 → fable 只讀備料設計 → opus 細化對到檔案 → **到此停**。沒起 aos 行程、沒叫真腦、沒碰 `~/aos-home`、沒用 sudo；試驗只在 scratchpad 用 unshare／setpriv／prlimit。

## 使用者原話（逐字）

「對了，我這邊還有個東西想請你跑規劃：讓kernel可以用setrlimit限制資源，還有權限，設置uid這塊。」

## 一張圖

```
使用者帳號 lorkhan(1000)＝一棵樹（含名下 subuid 100000～165535）
│
├ kernel 站（掛 proc 那一包）   政策：limits.default／max／by_sender、users 表
│    放行時改信：自帶 limits 夾進 max、丟掉自帶 user、照表填 user
│
├ daemon（fork 子行程）          保底與機制
│    limits_max 天花板（超過＝LimitBad）→ setrlimit（cpu hard＝soft＋1）
│    → 換 uid sub:N（每支自己一個 user ns，免 root）→ 二期 cgroup 一支一格
│    → 收屍翻譯 limit_hit（SIGXCPU→cpu_s、SIGXFSZ→file_mb、OOM→mem）
│
├ aos-sandbox（呼叫方自己包）    bwrap：看得到哪些夾、網路；user 多認 sub:N
│
└ proc（agent 身、腦、工具）     aos-exec 只管牆鐘 timeout_ms，不變
```

## 結論幾句

- **daemon 早就會 setrlimit 與換帳號**（11-05 做的 `limits`；換帳號要 root）。缺的是 kernel 站不會附限制、`{}` 一封信就能解除限制、cpu 到頂看起來像被 kill、`procs` 在同一個 uid 下不能用。
- **不同 agent 不同 uid 免 root 做得到**：家機的 subuid＋`newuidmap` 實測可換成真的 100004，讀不到使用者 600 的檔、殺不到使用者的行程；群組對到使用者主群組，使用者照樣改得動 agent 寫的檔。
- 要 root 的（真帳號、helper、sudoers）照 11-12「先不做」。

## 分檔

| 檔 | 內容 |
|---|---|
| [01 備料](kernel-limits-plan/01-備料.md) | 原話、各層現況表、家機環境、相關問題 |
| [02 fable 設計](kernel-limits-plan/02-fable設計.md) | fable 原稿 |
| [03 opus 細化](kernel-limits-plan/03-opus細化.md) | 跟 fable 不同的 8 處、分層定稿對到檔、kernel.json 新鍵、邊緣狀況 |
| [04 施工與驗收](kernel-limits-plan/04-施工與驗收.md) | 段 1 daemon 收緊、段 2 kernel 附限制、段 3 subuid、段 4 cgroup、段 5 root（不做） |
| [05 待裁與衝突](kernel-limits-plan/05-待裁與衝突.md) | K1～K11、衝突 C1～C7 |
| [06 試驗紀錄](kernel-limits-plan/06-試驗紀錄.md) | X1～X13 實測、撞到的問題 L1～L7 |
