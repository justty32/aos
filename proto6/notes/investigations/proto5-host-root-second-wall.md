# proto5：宿主機 root daemon 的第二道牆

> 2026-09-28 交接快照；[原始來源](../../../wf/workflows/investigations/proto5-host-root-second-wall.md)保留於原位置。本文的現行行為與實測均指當時 proto5／環境，非 proto6 已實作；僅調整導航與探針重跑路徑。

後續：[Linux 實作可行性、三條路線成本與無特權小實驗](proto5-linux-wall-feasibility.md)。

## 問題

正式員工使用自己的 Linux UID、固定 worker 負責 tick；若 daemon 直接以宿主機 root 執行，能否再由宿主機限制 daemon，避免 daemon 出錯就取得整台機器的控制權？

## 方法

2026-09-28 查閱 Linux kernel、Linux man-pages、systemd、AppArmor、Docker 與 bubblewrap 官方文件。這是設計調查，沒有 sudo、沒有修改主機服務、沒有建立帳號，也沒有驗證可部署的 service unit。

主線提供的唯讀環境觀察：工具所見 kernel 為 `6.18.49-1-MANJARO`，`/sys/kernel/security/lsm` 為 `capability,landlock,lockdown,yama,bpf`；`systemd --version` 找不到指令。這只描述工具所見環境，不證明完整宿主機配置；尤其不能假定現成可用 AppArmor、SELinux 或 systemd。

## 發現

**兩道牆各自管不同事情。** 員工 UID/GID 與檔案權限限制員工彼此；另一道必須由 daemon 外面的宿主 kernel 強制限制 daemon 及其後代。由 daemon 自己檢查路徑的 access 規則，不能防住已被接管的 daemon。

**root 能力可以削減，但「只留切換帳號」仍然很有權力。** `CAP_SETUID`、`CAP_SETGID` 能操作身分，並不是只能選 aos 員工。被接管後仍可能冒用宿主登入使用者；因此移除 `CAP_DAC_OVERRIDE` 不能取代檔案存取外牆。`CAP_SYS_ADMIN` 涵蓋掛載等大量操作，`CAP_SYS_PTRACE` 能跨身分操作程序，原則上不應留給日常 daemon。若跨 UID 管理員工需要 `CAP_KILL`，它也不是只允許殺自己的員工；須另設程序範圍限制或採用更窄的生命週期管理方案。具體最小能力集合須依啟動、收尾與恢復實測，不能直接宣稱兩個 capability 就足夠。[capabilities(7)](https://man7.org/linux/man-pages/man7/capabilities.7.html)

**NoNewPrivileges 可以和切換 UID 並用。** 它阻止 exec 透過 setuid 程式或檔案 capability 新取得權限，會由後代繼承且不能撤銷；並不移除既有 capability，也不禁止具有適當能力的程序呼叫 setuid。員工執行前仍須清乾淨 UID/GID、補充群組與 capability，不能只設定此旗標。[kernel 說明](https://docs.kernel.org/userspace-api/no_new_privs.html)

**systemd system service 可代為建立外部限制，但單一旗標不是完整沙盒。** 可評估 capability bounding set、`NoNewPrivileges`、`ProtectSystem=strict`、`ProtectHome`、`PrivateDevices`、`PrivateTmp` 與 kernel/cgroup 保護。`ReadWritePaths` 只解除特定路徑的唯讀掛載限制，不授予 DAC 權限，也不是讀取白名單。`ProtectProc` 官方明說對 root 無效；`ProcSubset=pid` 也只是裁掉非程序資訊，並非程序隔離。readonly mount 不限制連線 Unix socket；敏感資料的讀取與控制通道需另管。還需考慮後續掛載傳播與 privileged 程序拆除 namespace 限制的能力。[systemd 官方文件原始碼](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)

**AppArmor 或 SELinux 類型的 MAC 可限制 UID 0，但政策必須在 daemon 控制之外。** AppArmor 官方明確說明其限制也適用 root。啟動時由管理員配置、載入並強制套用政策，daemon 不能改政策、卸載政策或切到不受限的執行領域；子程序 exec、UID 切換後的政策繼承或轉換，也須明確驗證。沒有載入 profile 的程序仍可能處於 unconfined，不能只看系統裝了套件。這裡是候選機制，不代表目前環境已具備或已配置。[AppArmor 官方介紹](https://apparmor.net/)、[kernel AppArmor 文件](https://docs.kernel.org/admin-guide/LSM/apparmor.html)

**Landlock 是目前可見環境值得驗證的另一選項。** 可以讓可信啟動器在執行 daemon 前先施加限制，後代繼承且只能再收緊；不要等 daemon 處理不可信資料後才自行選政策。它不取代 DAC；只限制 kernel ABI 支援且 ruleset 納入的操作。預先打開的檔案、socket、傳遞進來的 descriptor，以及程序訊號與 Unix socket scope 都需納入設計。不能從 LSM 名稱存在就推斷所有新版功能已可用，應查 ABI 並對必要防線缺失拒絕啟動。[kernel Landlock 文件](https://docs.kernel.org/userspace-api/landlock.html)

**不得留下能請牆外服務代辦的通道。** 尤其是 systemd 管理 socket／system bus 的管理介面、Docker socket，以及其他高權限 IPC。直接 fork 的孩子會繼承部分限制，但請外面的 service manager 啟動新程序不一定繼承；Docker 官方也把控制 daemon 的權力視為敏感權限。因此檔案唯讀或 NoNewPrivileges 都不能單獨解決這個問題。這是由 IPC 行為推導的設計要求，必須包含 pathname socket、abstract socket、網路管理端點與預先開啟的連線。[Docker security](https://docs.docker.com/engine/security/)、[systemd NoNewPrivileges 說明](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)

**不能一面全面禁止 namespace／mount，一面假定原有 bwrap 照常工作。** bubblewrap 依賴 namespace 與掛載；未特權 user namespace 可在內部取得對該 namespace 有效的能力，因此也不能把「移除主機 CAP_SYS_ADMIN」理解為禁止所有內部 mount。實作要測外牆是否持續有效、bwrap 能否運作、發行版 userns 政策和 seccomp 是否衝突。[bubblewrap 官方 README](https://github.com/containers/bubblewrap)、[user_namespaces(7)](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)

## 結論

可行的方向是「受宿主機限制的 root daemon」，並把正式員工 UID 視為內部隔離、把外部施加的檔案／程序／IPC 限制視為宿主保護。這不是裸跑 `sudo aos-daemon` 就會有的能力，也不等同 VM：仍共享宿主 kernel。

建議先界定一塊公司的資料範圍、唯讀程式範圍及必要執行資源，再評估由宿主 service manager／可信啟動器建立外牆。常態 daemon 不改 `/etc/passwd` 等主機帳號資料；帳號佈建可以放在獨立管理步驟，避免為開員工而放寬整面牆。這是候選設計，沒有替使用者裁定部署工具。

後續實測的判準應是：daemon 即使刻意切成宿主使用者，仍不能讀宿主私密資料、寫範圍外檔案、管理範圍外程序、連控制 socket 或拆掉限制；正常員工 tick、工具、LLM、停止與恢復仍可運作。掛載、capability、MAC/Landlock 與 bwrap 的組合未測前，不交付可直接複製的 unit，也不宣稱已安全。

## 來源

上文各段已連到官方來源；systemd freedesktop 文件站本次回傳 403，改讀其官方 GitHub `man/systemd.exec.xml`。Linux kernel 與 systemd main 文件可能包含本機尚未支援的功能，部署前須以本機版本核對。本文環境資料由主線唯讀調查提供，沒有自行提升權限補查。
