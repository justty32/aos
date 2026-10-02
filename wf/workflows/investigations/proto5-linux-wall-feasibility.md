# proto5：Linux 外牆的實作可行性與複雜度

## 問題

延續[宿主機 root daemon 第二道牆](proto5-host-root-second-wall.md)：正式員工有專屬 Linux 身分和 tick worker，怎樣落地才不會把權限系統重新做一遍？比較三個 Linux 候選，區分已測機制、尚未整合的設計與長期成本。三條路線不是同等保證，也都不等於 VM。

## 方法

2026-09-28 讀官方文件，執行唯讀能力查詢與無特權、短生命週期隔離實驗；未 sudo、未改服務或帳號、未安裝套件。一次性 Python ctypes 僅在 fork 子程序安裝 Landlock，user namespace 實驗用現有 unshare 與既有 subordinate ID 授權；臨時檔案與 sleep 子程序測完即清理。沒有測試宿主 UID 0，也沒有跑完整 proto5。

環境實測：kernel `6.18.49-1-MANJARO`；LSM `capability,landlock,lockdown,yama,bpf`；Landlock syscall 查詢 ABI **7**。`systemd-run --version` 回報 **261.2-1-manjaro**，bwrap **0.12.0**，setpriv **2.42.3**。先前找不到 `systemd` 執行檔不能推論沒有 systemd；本次也沒有驗證系統 manager 連線或 service 啟動能力。systemd binary 編入 AppArmor 支援不代表目前 kernel 啟用 AppArmor。

<!-- wf-nav -->
| 分檔 | 涵蓋 |
|------|------|
| [01-執行入口與三候選.md](proto5-linux-wall-feasibility/01-執行入口與三候選.md) | 發現：共同需要的執行入口、候選 A：宿主 root，加 systemd 與 AppArmor／SELinux、候選 B：可信 launcher，加 Landlock／能力上限／seccomp／cgroup、候選 C：成熟容器 runtime，daemon 是 namespace root |
| [02-小實驗結果.md](proto5-linux-wall-feasibility/02-小實驗結果.md) | 發現：小實驗結果與可推論範圍 |

## 結論

實作可行，新增複雜度主要是**安全啟動邊界與部署政策**，不是 tick worker 的迴圈。候選 A 把成本放在宿主 MAC／服務部署與排障；B 把成本放在我們的 launcher 與長期安全測試；C 把成本放在容器 runtime、UID 映射、儲存和網路運維。沒有一條是加 `sudo` 或加一個設定就完成，也不應同時把三套全部塞進第一版。

若後續做原型，先固定一種 Linux 部署組合和必要防線，再以兩名員工驗證 tick、工具及停止恢復；同時測越界讀寫、管理 socket、訊號、重啟後舊程序和資源上限。必要 ABI／MAC／namespace／cgroup 條件不滿足，應明確拒絕啟動或拒絕建立該員工，不能默默退成裸跑。這是本專案對必要安全條件的候選要求；與官方範例為相容性而採 best effort 的目標不同。本文不交付未測 unit 或替使用者裁定三條路線。

## 來源

官方連結附於各段；systemd 讀官方 GitHub 文件。kernel 新版文件包含本機未支援的 ABI，已用本機 syscall 與 Linux 6.18 文件區分。上述指令及 ctypes 小實驗只在工具所見 Linux 環境完成，不能推論別台宿主或宿主 root 下也已驗證。
