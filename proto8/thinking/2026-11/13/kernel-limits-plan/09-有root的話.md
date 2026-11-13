有 root 的話可以多做什麼（草案，只想不做；使用者 11-13 22:15「要root的做法可以想想，但先以沒有root的情況做規劃」）：主規劃不靠這些，這裡只列每項多得到什麼、代價、跟免 root 做法的關係。

← [入口](../kernel-limits-plan.md)｜上一份 [08 群組用法](08-群組用法.md)

> 主規劃（段 1～4、07、08）全部免 root。這份不排施工、不動 `cmd/aos-sandbox/root/setup.sh`、沒跑過任何 sudo。11-12「root小daemon先不做」照舊。

## 一張表

| # | 要 root 才做得到的 | 多得到什麼（免 root 做不到的） | 代價 | 跟免 root 做法的關係 |
|---|---|---|---|---|
| R1 | **真帳號**（`useradd aos-a1`… 或每隊一個） | `ls`、`ps` 看得到名字；不需要 user ns，**沒有 subuid 的機器（公司 WSL 若沒有）也能分 uid**；daemon 的 `user: <帳號名>` 11-05 就寫好了 | 每台機器各建一次；帳號數有限、要清 | subuid 做不到時的退路；兩套可並存（`user` 寫名字或 `sub:N`） |
| R2 | **把使用者加進隊伍群組**（`usermod -aG`） | 使用者本來就在隊伍群組裡，共用夾**不用 ACL**，用普通 `2770` 夾 | 改群組要重新登入才生效 | 取代 08 的 G1、G2 大半的 ACL |
| R3 | **只准換成指定帳號的 helper**（11-12 早期想法：root 常駐小程式，收「用 uid X 起這支」的請求） | daemon 不用是 root 也能換成真帳號；helper 用 `SO_PEERCRED` 認請求方、只准名單上的帳號 | 一支常駐的 root 程式＝最大的攻擊面；要寫、要審 | R1 的配套；subuid 路線用不到 |
| R4 | **sudoers 只准換成 `aos-run`**（`setup.sh` 現成、預設乾跑） | 不用寫 helper，一行規則就能換成固定帳號 | 只能換成少數幾個帳號；sudo 設定寫錯影響整台 | R3 的簡化版 |
| R5 | **cgroup 委派補齊**（`systemctl edit user@.service` 加 `Delegate=yes`、或建 `/sys/fs/cgroup/aos` 交給使用者；開 `io` 控制器） | 公司 WSL 也能開 cgroup；多一個磁碟讀寫限制（家機沒委派 `io`） | 改系統設定，兩台各做 | 07 的 `auto` 降級就是在等這個 |
| R6 | **照 uid 管網路**（nftables `meta skuid`） | 指定 agent 只准連 LiteLLM proxy 那個埠、不准連外；比 bwrap 的「全斷或全通」細 | 規則跟 subuid 號碼綁，要跟 users 表同步 | subuid 的 uid 是真的，這條在 subuid 路線上**也能用**（只是設規則要 root） |
| R7 | **磁碟配額**（ext4 quota，照 uid） | 一隻 agent 最多寫幾 GB，總量（不是單檔 `file_mb`） | 要開檔案系統的 quota 選項、重掛 | 一樣能套在 subuid 上 |
| R8 | **只准追加／不可改**（`chattr +a`／`+i`） | 稽核紀錄 agent 只能追加不能改寫；定義夾 agent 改不了 | 使用者自己要改也得 root 先拿掉 | 08 G4 sticky 只擋刪不擋改壞，這條補上 |
| R9 | **加大 subuid 段**（改 `/etc/subuid`） | 65536 不夠分時 | 改系統檔 | 目前 65536 遠夠，不用 |

## 讀法

- **subuid 路線（K4 A）已經拿到最要緊的：真的不同 uid**。root 多給的是「好認」（R1 名字）、「沒有 subuid 的機器」（R1）、「更細的牆」（R6 網路、R7 磁碟、R8 只准追加）、「cgroup 補齊」（R5）。
- 真要做，順序建議：R5（純設定、最小）→ R6（網路，跟 subuid 疊用）→ R1＋R4（公司 WSL 沒 subuid 時）；R3 helper 最後，或永遠不做。
- 全部在使用者親手 `sudo` 之後才有；agent 不建議、不代跑（鐵律 2 的對外／不可逆）。
