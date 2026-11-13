cgroup 做成可選（使用者 11-13 22:15「cgroup這塊要可選」）：daemon.json 一個開關 `cgroup: off｜auto｜on`，推薦預設 off；開與不開時每項限制的行為差，與新冒出的三題 K12～K14。

← [入口](../kernel-limits-plan.md)｜上一份 [06 試驗紀錄](06-試驗紀錄.md)｜下一份 [08 群組用法](08-群組用法.md)

> 只是設計，沒施工、沒碰 cgroup 樹（建子格會動到 `user@1000.service` 底下，留給段 4 施工）。

## 開關

daemon.json 頂層一個鍵（不寫＝`off`）：

| 值 | daemon 起的時候 | 機器沒委派時 |
|---|---|---|
| `off` | 完全不碰 cgroup，跟今天一樣 | — |
| `auto` | 探一次：自己所在的 cgroup（讀 `/proc/self/cgroup`）有 `memory`、`pids` 兩個控制器、而且能在底下建子格 → 開；daemon 自己搬進 `<格>/daemon/`（v2 規定有子格的格裡不能留行程），每支 proc 一格 `<格>/procs/<名>/` | **降級**：stderr 一行 `cgroup: none (<原因>)`、daemon 狀態記 `cgroup: none`，之後跟 `off` 一樣 |
| `on` | 同 `auto` | **不起**：`CfgBad cgroup on: <原因>`、退 1（給「沒有總量限制寧可不跑」的樹） |

- **怎麼讓 daemon 起在有委派的格裡**：樹的起法（`launch.json` 的 `wrap`）在 `cgroup` 不是 `off` 時多包一層 `systemd-run --user --scope -p Delegate=yes --`；`off` 時不包。家機 `user@1000.service` 已委派 `cpu memory pids`（[01](01-備料.md) B）；公司 WSL 11-05 這樣包退 1，`auto` 會自己降級。
- **跟換 uid 的順序**：子行程 fork 出來時還是 1000，**先**把自己的 pid 寫進自己那格的 `cgroup.procs`，**再** `unshare(CLONE_NEWUSER)`、換 subuid、`setrlimit`。格子都歸 1000，換了身分的 agent 動不到自己的格（也不需要），跨 uid 搬行程的權限問題整個避開。
- **子 daemon**：它被起在父 daemon 給它的那一格裡（同一個 uid、格子歸 1000），自己也寫 `auto` 就會往下再分；寫 `off` 就整串吃父那格的總量。
- **只有 cgroup 才做得到的鍵**（`mem_total_mb`→`memory.max`、`procs_total`→`pids.max`）在沒開時：stderr 一行 warning、那支照起、表列多 `limits_ignored: ["mem_total_mb"]`。讀法同 K11（寫了就說、不擋）。

## 開與不開，各項限制的差別

| 限制／能力 | 不開（`off`，或 `auto` 降級） | 開 |
|---|---|---|
| `cpu_s`、`files`、`file_mb` | setrlimit，每個行程各算各的 | 同左（這輪不做 `cpu.max` 那種「最多用幾成 CPU」） |
| `mem_mb` | setrlimit 的虛擬位址上限，每個行程各算；node 類（Claude Code）不能用 | 同左 |
| `mem_total_mb` | 不套，warning＋`limits_ignored` | `memory.max`：這支連同全部子孫加起來的記憶體 |
| `procs` | 沒換 uid 時數的是整個帳號（K11 警告一行）；換了 subuid 才是這隻自己的 | 同左 |
| `procs_total` | 不套，warning＋`limits_ignored` | `pids.max`：這支連同子孫最多幾個行程（fork 炸彈停在這） |
| 記憶體到頂認得出嗎 | 只能猜（有 `mem_mb` 又退 1＝`limit_suspect`） | 讀 `memory.events` 的 `oom_kill` → `limit_hit: "mem"` |
| eca 身（Claude Code／Codex CLI）的記憶體 | **完全沒限**（`mem_mb` 對它不能用，K7） | `mem_total_mb` 管得到 |
| `stop` 收全樹 | 只殺行程群組，`setsid` 跑掉的孫子收不到（#25 孤兒） | 可以 `cgroup.kill` 一次收整格（K14） |
| 子 daemon 底下的總量 | 根的 `max_running` 把一台子 daemon 算一格，管不到它底下用了多少 | 整串在父給的那格裡，總量被那格夾住 |
| 公司 WSL（沒驗） | 照跑 | `auto` 降級成左欄；`on` 不起 |

一句話：**不開時只有「每個行程各自的上限」；開了才有「這隻 agent 連子孫加總的上限」**，而 eca 身的記憶體只有開了才管得到。

## 推薦：預設 `off`，要的樹寫 `auto`

- 使用者原話是「要可選」，預設關最貼；11-05 代定 7「不做 cgroup，給人假安全感」那層顧慮也留在預設裡（[衝突 C2](05-待裁與衝突.md#衝突哪條在哪各自後果)）。
- 要開的樹寫 `auto`：沒委派就自己降級、說一聲，兩台機器同一份設定都起得來。
- `on` 只給確定有委派、沒有總量限制寧可不跑的樹。
- 家機活樹要不要寫 `auto`：段 4 在暫存樹驗收過再問，不跟這題綁。

## 新冒出的題（已於同晚再裁，見 [05](05-待裁與衝突.md#使用者再裁11-13-晚k6-與-k12k16)）

- **K12** 不寫 `cgroup` 時的預設：`off`／`auto`。推薦 `off`。
- **K13** 要不要有 `on`（探不過就不起）：有／只留 `off`、`auto`。推薦有。
- **K14** 開了 cgroup 時 `stop` 用 `cgroup.kill` 收整格：是／照舊只殺行程群組。推薦是。
