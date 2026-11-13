opus 對 fable 設計的修正與細化：三處「待驗」用實測補上、換 uid 改成每支 proc 自己一個 user ns（不是整棵樹進 ns）、群組改用使用者的主群組，並對到要動的檔。

← [入口](../kernel-limits-plan.md)｜上一份 [02 fable 設計](02-fable設計.md)｜下一份 [04 施工與驗收](04-施工與驗收.md)

## 一、跟 fable 不同或補上的地方

1. **cpu 到頂看不到 SIGXCPU：實測確定**（[06](06-試驗紀錄.md) X7、X8）。soft＝hard 時退 137（SIGKILL），hard＝soft＋1 秒時退 152（SIGXCPU）。daemon 改成 `cpu_s` 的 hard＝soft＋1，其他鍵照舊 soft＝hard。
2. **user ns 裡 `procs` 各算各的：實測確定**（X11、X12）。同一個 uid 時 `procs: 10` 連 fork 都不行（使用者自己有約 120 個行程）；換到 subuid 後 `procs: 5` 起三個 sleep 沒事。
3. **換 uid 是「每支 proc 自己一個 user ns」，不是整棵樹進一個 ns**。整棵樹進 ns 的做法看起來更省事（daemon 當 ns 裡的 root，現成的 `setuid` 直接能用），但留在 1000 的 proc 在 ns 裡會變成 uid 0：tmux 的插座改找 `/tmp/tmux-0`（使用者的終端接不上畫面），Claude Code 以 root 身分跑會拒絕略過權限的模式（推的、沒實測）。所以只有要換身分的那支 proc 自己開 ns，其餘照舊在外面。
4. **換身分的步驟**放在 daemon 的 C++ 子行程裡，不另做一支要 exec 的程式（daemon 是在行程內 `run_cli`，不 exec）。`newuidmap` 必須由 ns 外面的行程替它寫對照表，所以要父子對一下：子行程 `unshare(CLONE_NEWUSER)` → 透過一條管子通知 → daemon 這邊跑 `newuidmap <pid> 0 1000 1 N <100000+N-1> 1` 與 `newgidmap` → 子行程 `setresgid`／`setresuid(N)` → `apply_limits` → `run_cli`。aos-sandbox（Python，exec bwrap）要同一件事時，另做一支小程式 `aos-asuser`（做法同上，最後 exec），排在 bwrap 前面；bwrap 在 user ns 裡再開 ns 能不能過，**待驗**。
5. **群組用使用者的主群組，不用共用的 subgid**（X13）。fable 說的共用 subgid＋setgid 夾，使用者自己（1000）不在那個群組裡，一樣改不動 agent 寫的檔。實測可以把 ns 裡的 gid 對到使用者自己的主群組 1001：agent 寫出來的檔是 `100004:1001 664`，使用者照樣能改；600／700 的私檔 agent 照樣讀不到。代價：使用者那些群組可寫的檔，agent 也能寫（家機 umask 一般是 022，這種檔很少）。列成待裁 K6。
6. **`mem_mb` 對 node 類程式不能用**（fable 已提，沒實測）：V8 一啟動就預留很大的虛擬位址，`RLIMIT_AS` 設小了 Claude Code 直接起不來。eca 身不設 `mem_mb`，記憶體交給二期的 cgroup。
7. **daemon 的天花板 `limits_max` 超過時拒、不夾**：fable 說 daemon 也夾一次，但 11-05 代定 2 定了「寫什麼就做什麼、不自動夾成 daemon 的 hard」（C-56）。改成：**kernel 夾**（它是政策層，夾了在信上記號），**daemon 超過天花板就 `LimitBad`、那支起不來**（它是保底，照舊不自作主張）。
8. **kernel 怎麼知道寄件人**：一期只能信信封上的 `sender`（自報，issues #8）；三期換 uid 之後，站可以看信檔的擁有者 uid 對回是哪隻 agent，那才擋得住冒名。這跟 C-47「aos 不驗寄件人」相衝，列成衝突 C6。

## 二、誰在哪層限什麼（定稿）

| 層 | 定什麼／做什麼 | 檔 |
|---|---|---|
| kernel 站（掛 proc 那一包） | 政策：`limits.default`／`limits.max`／`limits.by_sender`；把請求自帶的 `limits` 夾進 max、丟掉自帶的 `user`、照 `users` 表填 `user` | `proto8/lib/aos/kernel/procs_rules.py`（新增一個小模組 `limits_rule.py`）、`kernel/README.md`、範本 `kernel/*/kernel.json` |
| daemon（fork 子行程） | 機制與保底：`limits_max` 天花板、setrlimit、換 uid（`sub:N`）、關 fd、清環境、收屍翻譯 `limit_hit`；二期 cgroup 子格 | `proto8/impls/aos-daemon/src/child/limits.{hpp,cpp}`、`child.cpp`、`daemon/daemon.cpp`、`reconcile.cpp`、`table.cpp`（列多欄）、`docs/09-份額.md`、`docs/06`（錯誤表） |
| aos-sandbox | 照舊：呼叫方自己包、管看得到什麼；`user` 多認 `sub:N`（走 `aos-asuser`） | `proto8/cmd/aos-sandbox/bin/aos-sandbox`、README |
| `aos-asuser`（新，三期） | 免 root 換成 subuid 再 exec | `proto8/cmd/aos-asuser/`（新） |
| aos-exec | 不動（牆鐘 `timeout_ms`） | — |
| 要 root 的包（不做） | 真帳號、只准換成指定帳號的 helper／sudoers | 沿用 `cmd/aos-sandbox/root/`，預設乾跑 |
| 條文 | N-28 `limits` 那段、C-64 沙箱段、N-42 kernel、知識庫 `cli/daemon.json`、`cli/sandbox.json`、`kernel.json` | `proto8/docs/…`、`proto8/knowledge/aos/…`（源頭；活樹重抄另放行） |

## 三、kernel.json 新鍵（掛 proc 那一包）

```json
{"limits": {"default": {"cpu_s": 3600, "files": 1024},
            "max":     {"cpu_s": 7200, "files": 4096, "file_mb": 2048},
            "by_sender": {"stacks/sol-T01": {"cpu_s": 600}}},
 "users":  {"sol-*": "sub:2001"}}
```

- 請求裡每個 proc 的 `limits`：沒寫或 `{}`＝用 `default`（`by_sender` 蓋過 default）；寫了就逐鍵取「自帶」與 `max` 較小的；`max` 沒寫的鍵不夾。夾過的在轉寄的 body 那支 proc 上加 `"limits_clamped": ["cpu_s"]`（daemon 不認得的鍵要先確認會不會擋：`is_once` 認的鍵是白名單，**要一起加**）。
- `user`：請求自帶的一律拿掉；`users` 照 proc 名字比對（`*` 萬用），對到就填。
- 沒寫 `limits`／`users`＝跟今天一樣原樣轉寄（框架「沒設限制就能過」）。

## 四、daemon 的列多三欄

`limits`（實際套上的，已有）、`limit_hit`（收屍時翻譯：signal 24→`cpu_s`、25→`file_mb`；二期 cgroup 的 `memory.events` oom_kill 增加→`mem`、`pids.events` max 增加→`procs`）、`limit_suspect`（有 `mem_mb` 又退 1＝`mem_mb`，只是猜）。

## 五、邊緣狀況（補 fable 的表）

| 狀況 | 處理 |
|---|---|
| 換了 uid 的 proc 要寫自己的 stack（`loop.json`、`state.json`） | daemon fork 前把那支的 stack 夾 chown 不了（不是 root）——改成 stack 夾建在 ns 裡、由那支自己第一次起時建；或 stack 夾給群組寫（K6 選主群組就自然成立） |
| daemon `rm` 換了 uid 的 agent | 刪不掉 subuid 擁有的檔：daemon 清理一律經 `aos-asuser` 用同一個 subuid 進去刪；照舊 `rm` 只 detach、stack 留著，問題只在清垃圾 |
| 共用夾的祖先只有 700（X2） | 換 uid 前的檢查：daemon 起之前看工作區每一層祖先「別人」或群組有沒有 x，沒有就 `LimitBad user sub:N: cannot reach <路徑>` |
| 金鑰在環境變數裡 | 換 uid 的子行程照 `env` 白名單（同 aos-sandbox 的 `env`），不白名單的不傳；不換 uid 的照舊 |
| fd 外洩 | 換 uid 前 `close_range(3, ~0)`（stderr 已在 2） |
| daemon 自己用 `prlimit` 包著起 | hard 往下繼承；`limits_max` 寫得比 daemon 的 hard 還寬照舊 `LimitBad` |
| 公司 WSL 沒有 subuid／newuidmap、cgroup 沒委派 | `sub:N` 報 `LimitBad user sub:N: newuidmap missing`；cgroup 不啟用、表上 `cgroup: none` |
| 信箱（aos-post maildir）跨 uid | 收件夾 `new/`、`tmp/` 給群組寫（K6）；投遞箱權限（只能丟不能讀）要 `tmp`→`new` 的 rename 兩邊都寫得進，`1733` 的做法待驗 |
| 子 daemon 換了 uid | 它的子項只能換成同一個 ns 裡對得到的 uid；三期先不准子 daemon 再換（`sub:N` 只在根 daemon） |
