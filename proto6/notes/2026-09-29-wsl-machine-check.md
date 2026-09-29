# WSL 機器查證（公司 WSL2）

← [筆記索引](README.md)｜對照 [notes 審查「機器查證結果（B 隊）」](archive/reviews-2026-09-28/notes-review.md#機器查證結果b-隊)

日期：2026-09-29。使用者要求 proto6 **同時能在原生 Linux 與 WSL 上跑**；Opus agent 在公司 WSL2 做了與 B 隊（Manjaro）同一套唯讀查證，另外在自己的 systemd 委派子樹實測 cgroup 上限（事後清乾淨）。沒用 sudo、沒改系統設定。**這是查證紀錄，不代表建議已採納。**

總結：cgroup、UID、Landlock、systemd 在 WSL 都能用。卡的是四件 WSL 才有的事：**Windows 側開出隔離破口、WSL 常整台關掉、根目錄開不了 project quota、時鐘很不穩**。

## 一、Manjaro 與 WSL 對照

| 項目 | Manjaro（B 隊） | 公司 WSL |
|---|---|---|
| kernel | 6.18.49-1-MANJARO，16 核，60 GiB | 6.6.114.1-microsoft-standard-WSL2，8 核，VM 記憶體 15 GiB、swap 4 GiB；WSL 2.7.3.0、Windows 10.0.26200、Ubuntu 24.04.4 |
| PID 1／systemd | systemd 261.2 | systemd 255.4（wsl.conf `systemd=true`），running |
| 根檔案系統 | nvme ext4 `rw,relatime`，`noquota` | `/dev/sdd`（ext4.vhdx，虛擬 1 TB）ext4 `rw,relatime,discard,errors=remount-ro`，`noquota`；WSL 自己掛，fstab 改不動 |
| quota 工具 | 沒裝；dumpe2fs 被拒 | quota 系列、xfs_quota、mkfs.xfs 都沒裝；dumpe2fs 被拒。kernel 內建 QUOTA、XFS＋XFS_QUOTA、loop；自製 ext4 映像可開 `quota,project` |
| /tmp | tmpfs | **不是 tmpfs**，是根 ext4 上的一般目錄 |
| cgroup | cgroup2，nsdelegate、memory_recursiveprot | 純 cgroup2，nsdelegate，**沒有** memory_recursiveprot；控制器 cpuset、cpu、io、memory、hugetlb、pids、rdma；根層只對子層開 cpu、memory、pids |
| cgroup 委派 | user@1000 Delegate=yes，cpu／memory／pids | 同 |
| 限制實測 | 沒做 | 臨時 unit 內 memory.max、swap.max=0、pids.max、cpu.max 都成功；pids 第 19 次 fork 回 EAGAIN；200 MB 配置被 OOM kill（rc 137）；cgroup.kill 清得掉；無殘留 |
| LSM | capability、landlock、lockdown、yama、bpf | capability、landlock、yama、safesetid、selinux（無 policy）、integrity；AppArmor 編進但未啟用 |
| seccomp | 沒記 | 可用；WSL 已在 PID 1 裝一層 filter，全部繼承 |
| user namespace | unprivileged_userns_clone=1；subuid 100000:65536 | 無該 sysctl；max_user_namespaces 62961；`unshare -Ur` 成功；subuid 100000:65536；沒裝 newuidmap、bwrap |
| UID 範圍 | 沒記 | login.defs 1000～60000，放得下一萬個 |
| 探針 | 退出 0，ABI=7，8 項 PASS | 退出 0，**ABI=3**，8 項 PASS（errno 13），兩個 canary 讀得到，gcc 無警告 |

附帶觀察：
- 沒設 `memory.swap.max=0` 時，200 MB 會被擠去 swap 而不是被殺；WSL 預設開 swap，B-303 要求 swap 設 0 在 WSL 是必要的。
- 從 `wsl.exe` 進來的 shell（含 claude、codex）都在 `/init.scope`（歸 root），不在 systemd 委派樹裡。
- pids 撞上限時，父層 `pids.events` 仍是 `max 0`，不能靠父層判斷。

## 二、在 WSL 上不成立或要改的假設

1. **外牆與 UID 隔離破洞**（[linux-and-storage](archive/import-2026-09-28/plan/linux-and-storage.md)〈要引入的能力〉、[B-302](../spec/base/identity-resources.md)）：`/mnt/c` 無 metadata，全部顯示 UID 1000、777；實測讀得到 ext4.vhdx 檔頭，推論其他 UID 也讀得到＝繞過 Linux 權限讀別的 agent 資料（未用第二個 UID 驗證，需 root）。interop socket 為 `srwxrwxrwx`，任何 UID 都能以 Windows 使用者身分跑 `cmd.exe`／`powershell.exe`。→ WSL 部署必須在 wsl.conf 關 interop、關或收緊 automount（`umask=077,metadata`），B-302 啟動 probe 加這三項檢查。Landlock ABI 3 擋不了 socket。
2. **/tmp 不是 tmpfs**（linux-and-storage 本機觀測段；B-304）：WSL 的 /tmp 和控制區同一顆根磁碟，吃的是磁碟。
3. **磁碟水位**（linux-and-storage 全局容量政策）：Linux 以為還有 940 GB，Windows C: 實際剩 734 GiB，vhdx 會長大。Windows 先滿時 vhdx 寫不進去，`errors=remount-ro` 可能讓整個 distro 變唯讀、控制端跟著停。水位要看 Windows 那顆磁碟。
4. **daemon 由誰啟動**：WSL 上只能用 systemd unit；Windows 排程只負責叫醒 WSL，不要用 `wsl.exe -e aos` 直接起。
5. **重啟語意**（[B-603、B-604](../spec/base/lifecycle.md)）：WSL 整台重開是常態（三週 25 次開機，最短活 32 秒）；官方預設 distro 閒置 15 秒、VM 閒置 60 秒關機，2.6 起有回報 systemd 服務在跑也照關（#13416）；`wsl -t` 約 10 秒結束（#41596），B-604 的 30000 ms 等不到。「boot ID 相同＝舊程序還活著」不能當規則。
6. **時間**（[contracts](../spec/contracts.md)、[S-204](../spec/scheduling/admission.md)、B-602 lease）：monotonic 比 Windows 牆鐘慢約 4%（45.27 對 47.14 秒）；timesyncd 每 32 秒把牆鐘推 +1.4 秒（本次開機 96 次）；Windows 睡眠時 VM 暫停，醒來牆鐘大跳而 monotonic 不算睡掉的時間。「逾時用經過時間」方向對，但「最老先派」要加序號當次鍵；睡醒大批同時到期要靠准入名額攤開。
7. **儲存 backend**（linux-and-storage〈Project quota 的部署門檻〉、B-302 `quota_backend`）：WSL 根 ext4 不能當 backend，要另做專用卷。
8. **外部 workspace**（linux-and-storage 外部 workspace 段；待裁定 10）：放 /mnt/c 就沒有 UID 隔離、沒有 quota、沒有 inotify（#4739）；9p 上 stat 每檔約 0.35 ms（ext4 近 0），Defender 即時掃描開著。
9. **Landlock 當外牆候選**（[隔離實測](archive/import-2026-09-28/2026-09-28-linux-isolation-probes.md)）：WSL 只有 ABI 3，ABI 4 以上的網路、ioctl、scope 規則用不了；profile 要記最低 ABI，不夠就拒絕啟動。
10. **本機觀測描述**只寫了 Manjaro，應依平台分列。

**照樣可行**：一 agent 一 UID；cgroup v2 委派與所有上限；clone3 CLONE_INTO_CGROUP 與 pidfd（6.6 有）；B-303 整條順序；seccomp（待裁定 6）；loop 映像上的 XFS pquota；Linux 側 inotify 當門鈴＋補查；idle 不常駐、SQLite 索引、LLM 門票。

## 三、對待裁定 5、7、8 的影響

- **待裁定 5（日常特權點）**：② 極小 root helper 更站得住——兩平台寫法一樣；① 開 MAC 在 WSL 要改 `.wslconfig` kernel 參數，被接管還波及 Windows 使用者；③ polkit 問題兩邊一樣；④ user namespace 在 Manjaro、原生 Ubuntu 24.04（AppArmor 限 userns）、WSL 三邊行為都不同，也解決不了 interop 與 /mnt/c。另加 WSL 佈建規定：關 interop、收緊 automount。
- **待裁定 7（重啟語意）**：「先接受殺光、全部變 unknown」在 WSL 更站得住——最常見的重啟是整台 VM 消失，獨立 slice 也救不回。要補：恢復測試加「10 秒內 VM 消失」「睡醒牆鐘大跳」兩情境；停機寬限可設定（WSL 8 秒內）；Windows 端 `instanceIdleTimeout=-1` 並在登入時保活，`vmIdleTimeout=-1` 建議一起設（未另外查證）。unknown 會很常見，待裁定 4 的出口更重要。
- **待裁定 8（儲存 backend）**：維持專用 XFS 卷（pquota），WSL 上用 loop 映像，Linux 內佈建一次、systemd mount unit 開機自動掛；原生 Linux 可同法或用真分割區。不選 `wsl --mount`（要 Windows 系統管理員、每次關機後要重掛），也不改根 ext4 feature。映像大小固定、水位看 Windows 磁碟。

## 四、沒查到的

- 用第二個 UID 實測 /mnt/c 與 interop 存取（要 root 建帳號）。
- 根 ext4 開了哪些 feature（讀 `/dev/sdd` 要 root）。
- Windows 端寫檔時 inotify 的實測。
- `wsl --shutdown` 實際給 systemd 多少收尾時間、只終止 distro 時 boot_id 會不會變（要關掉這台 WSL）。
- Defender 排除清單（要 Windows 系統管理員）。
- monotonic 慢 4% 是這台特有還是 WSL 普遍（只有一台樣本）。

## 來源

- [WSL 設定文件](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)（instanceIdleTimeout 15000 ms、vmIdleTimeout 60000 ms、記憶體 50%、swap 25%、automount、interop）
- 閒置與關機：[#13416](https://github.com/microsoft/wsl/issues/13416)、[#41596](https://github.com/microsoft/WSL/issues/41596)、[#13435](https://github.com/microsoft/WSL/issues/13435)、[#8854](https://github.com/microsoft/WSL/issues/8854)、[#9968](https://github.com/microsoft/WSL/issues/9968)
- 時鐘：[#5324](https://github.com/microsoft/WSL/issues/5324)、[#9183](https://github.com/microsoft/WSL/issues/9183)、[#13867](https://github.com/microsoft/WSL/issues/13867)
- inotify：[#4739](https://github.com/microsoft/WSL/issues/4739)、[#5424](https://github.com/microsoft/WSL/issues/5424)
- [9P vs Samba 效能測試](https://allenkuo.medium.com/windows-wsl2-i-o-performance-benchmarking-9p-vs-samba-file-systems-cf2559be41ac)
- [Ubuntu on WSL 安全說明](https://documentation.ubuntu.com/wsl/stable/explanation/security-overview/)
- [wsl --mount 文件](https://learn.microsoft.com/en-us/windows/wsl/wsl2-mount-disk)、[#6414](https://github.com/microsoft/WSL/issues/6414)
