# Linux 接入與持久儲存

← [本輪規劃](README.md)｜[資源與任務方向](../2026-09-28-linux-resources-and-task-scheduling.md)

2026-09-28。以 Linux、10,000 個 agent、每小時活躍不到 100 個、LLM 推論在雲端為前提。UID／cgroup v2／project quota 三軸已接受；取消常駐 CPU worker、取消逐工具 bwrap 是本輪規劃方向。本文只規劃接入與部署，不是已實作功能，也不把每小時活躍量誤當同時併發上限。

## 要引入的能力

需要一份穩定的身分／資源登記、一個受限程序啟動接點、systemd 委派的 cgroup v2 子樹，以及真正啟用 project quota 的持久檔案系統。不是每個 agent 都要一個服務、一個 mount 或一顆常駐 worker。

把有特權的佈建與日常運行分開：佈建負責預留 UID／GID 範圍、建立帳號與目錄、設定 project ID／配額、安裝服務政策；runtime 只使用已批准的登記啟動、停止與記帳。這是權責分界，不要求為佈建再放一個永遠在線的 root server。daemon 是否保留哪些權限、第二道牆採哪種機制，仍待決定，不因三軸已定就視為 root 安全問題已解。

日常執行鏈先確定可信 agent ID 與世代，再取得 UID、cgroup 和容量歸屬；工具不能自行改這些識別。工具沿用委託 agent 的身分與資源域，不再逐工具創造另一套 bwrap 權限；這也代表普通 UID 可以看到的宿主資料仍可見，cgroup／quota 不替代檔案存取權限。

## UID 是穩定數字，不是每次啟動臨時猜名字

registry 保存穩定 agent ID、數字 UID／GID、附加群組、入職世代與資料位置。帳號名稱供人閱讀，runtime 不應每次掃一萬筆帳號尋找空位，也不應把名稱重新指向另一 UID 當成正常重啟。

安裝時由管理者選不衝突的範圍，避開 UID 0、現有真人／系統帳號及其他 UID 配置用途。不能假定某台機器的「系統帳號預設範圍」容得下一萬個 agent。帳號配置不授予 sudo／管理群組；禁用互動登入，無密碼／SSH key 登入入口，配合 nologin shell。僅鎖密碼不等於阻止所有登入途徑；這些是安裝政策要求，不是本輪已驗證的宿主設定。

不為每個 agent 啟用 user manager、linger、PAM 登入 session 或 user service。直接以指定 UID 啟動短命工作，不必模擬一萬人登入。若工具依賴 passwd／home 查詢，初版使用預建的正常 NSS 帳號項目最容易相容；完全只有數字 UID 的方案可後續評估，不把它當零成本替代。

也不替每個帳號任意配置 subuid／subgid。那是 user namespace 映射資源，與「agent 使用一個宿主 UID」不是同一需求；部分帳號建立工具會按系統預設配置 subordinate 範圍，佈建需明確控制並核對。來源：[useradd 文件](https://man7.org/linux/man-pages/man8/useradd.8.html)。

UID 與 project quota ID 是不同命名空間。registry 可以把兩者關聯，但不要要求數字相等；project ID 還必須連同檔案系統識別保存。退役也不立即回收：舊檔 ownership、舊 project inode、存活程序、未完成工作都要對帳；增加世代只能擋舊工作單，不能清除舊 UID 的檔案權限。

## cgroup：一個委派子樹、一個管理者

建議由 systemd 將一個服務子樹委派給 runtime，由單一管理者負責其內部建立／限制／清理；systemd 管外層，aos 管委派範圍內，不由兩者同時任意改同一層。員工與工具不能寫 cgroup 控制檔，也不能把自己搬到另一個域。來源：[systemd cgroup delegation](https://systemd.io/CGROUP_DELEGATION/)。

下面是責任示意，不是最終 unit 名稱或固定 schema：

```text
aos 的委派根（不直接放程序）
├─ control（daemon／排程器等控制程序）
└─ work（所有 agent 的共同資源上限，不直接放程序）
   └─ agent-A（該 agent 合計上限，不直接放程序）
      ├─ tick-某次（短命程序 leaf）
      └─ job-某次（工具／LLM client 與其後代 leaf）
```

採一般 domain cgroup；向下分配 domain controllers 的非根節點不能直接放程序。因此委派服務的管理程序移到 control leaf，再啟用子樹的 controllers；tick／job 放 leaf，不把程序塞進 agent-A 後又要求它同時往子層分配 memory。子程序原本會繼承父 cgroup，但現在工作可能由 daemon 另開，不能假設它自然進入委託 agent 的域。[Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)

work 設整體 memory／pids／CPU 上限，agent-A 設自己的合計限制，必要時工作 leaf 再細限。可用 memory.max 作硬上限、memory.high 作壓力控制、pids.max 擋程序／執行緒增長、cpu.max 控時間頻寬；CPU 權重不是硬額度。這些限制不預留每個 agent 等量 RAM／核心，也不能用每小時活躍 100 推算同時要配置多少資源。全局准入與限額應配合壓測選值；控制程序要留有回報失敗與取消的資源。機制見 [cgroup controller 文件](https://docs.kernel.org/admin-guide/cgroup-v2.html)。

idle agent 保留磁碟本體與登記，不保留程序。agent cgroup 可以按需建立，空 leaf 回收；是否保留空的 agent 父節點用小型壓測決定，不能先假設一萬個空 cgroup 必然免費。cgroup 清空後的歷史用量要先彙整到控制帳本，不能靠檔案一直存在充當歷史資料庫。

## 必須先進資源域，再開始工作

啟動器先建立 cgroup、設限，再讓工作執行。候選是 clone3 的 CLONE_INTO_CGROUP 直接在目標域建立子程序；較容易接現有程式的候選是可信的小型 child 等待 go，父程序移入正確 leaf 後才放行。兩者都需驗證失敗關閉：進入或設限失敗就不得執行工作。child 在放行前不能讀員工 inst、啟動工具、fork 後代或配置工作的大量記憶體。不要先啟動 Python 工作再補搬 PID，因為初始配置與已產生後代不會因此得到完整追溯歸屬。來源：[clone3／CLONE_INTO_CGROUP](https://man7.org/linux/man-pages/man2/clone.2.html)。

啟動接點還需做 UID／GID／群組降權、env／fd 清理，之後才讀員工配置。這是所有 exec 工作共同入口，不是只替 Python 工具加 wrapper。關於目前 root 讀 inst 與先開重導向的缺口，見[既有實作調查](../2026-09-28-linux-employee-implementation.md)。

pidfd 適合追蹤單一程序實體，避免後續訊號誤用已重複分配的 PID；它不代表整棵工具後代，也不是跨 daemon 重啟可直接保存的 handle。[pidfd_open](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)

取消先用可控的溫和停止，逾期才以 job 的 cgroup.kill 清除子樹；該介面是強制 SIGKILL，需探測目標核心與權限，不能當 graceful stop。回收前確認無活程序、收好可取得的退出結果並完成對帳，不能只看主 PID 已死。來源：[cgroup.kill／populated](https://docs.kernel.org/admin-guide/cgroup-v2.html)。

## Project quota 的部署門檻

先看 agent 資料將放在哪個檔案系統，而非只看 Linux 核心支援什麼。XFS 要確認 project quota 的 accounting／enforcement 已啟用、專案樹已設 project ID 與繼承旗標，並能查驗 block／inode 額度；不能只有工具裝好就算完成。[XFS project quota](https://man7.org/linux/man-pages/man8/xfs_quota.8.html)

ext4 要確認 project feature、quota 功能與實際啟用／掛載狀態、管理工具相容性；`prjquota` 本身要求 project feature。不能因 mount 顯示 ext4 就斷言可以立即使用。[ext4 feature 與 prjquota](https://man7.org/linux/man-pages/man5/ext4.5.html)

若既有宿主磁碟不符合，候選是另選已具備能力的專用 volume；不默默修改宿主根檔案系統，也不以定期 du 超量刪檔偽裝成 quota。首版只正式支援一個已驗證 backend，降低安裝和恢復矩陣；另一個 filesystem 可後補。這裡不提供改 feature、重掛載或格式化指令。

每個 agent 自有樹配置自己的 project ID，新增與既有 inode 都要校驗繼承。驗收要含 create、rename、hardlink、搬入舊檔、複製／還原後 project metadata，以及普通員工能否改掉 project 屬性逃過額度。別只測往單一新檔寫到上限；也要測 inode 額度，避免大量小檔吃光檔案系統。

quota 是 inode 的專案歸屬，不等於「某 UID 所寫的一切」，也不是替每名 agent 預留空間。一萬份配額上限相加可以超過實體容量；runtime 仍需要整體磁碟水位與准入政策。外部 workspace 不算自有容量，也因此不受該 agent 自有 quota 兜底，workspace 管理者需另訂共享容量政策。

## 資料夾責任草圖與 quota 滿時怎麼活下來

```text
管理區（agent 不可寫）
  registry／授權政策
  任務帳本／工作世代／取消與quota失敗紀錄
  全局日誌（有輪替、大小與速率限制）
agent資料volume
  agent-A/（project A）
    state／history／prompts
    outputs／本地工具資料／scratch
外部workspace
  專案與共享資料（它自己的容量政策）
```

這是責任分區，不要求上述名稱或一人一個 mount。agent 的持久 state、history、outputs 算自有容量；控制面為了排程／恢復保存的少量工作資料不放進該 quota。對來源是 agent 的資料仍限長、限量，不能讓 agent 改用全局 log 或 control store 無限存檔繞過容量限制。

滿 quota 時，agent 可能連 state 的原子替換暫存檔都建不出來；控制面必須仍能寫「quota hit／停止接單／待清理」、讀最後完整版本並取消工作。採容量高水位提前暫停與整理、保留管理儲存空間；僅有軟門檻不是硬配額。控制區若與 agent volume 共用實體磁碟，仍可能一起遇到整體 ENOSPC，因此應配置能保住控制區的整體容量安排；單獨換個資料夾並不形成空間保留。

scratch 可以先是 quota 樹裡的磁碟目錄，TMPDIR 指向它，無須每個 agent 建 tmpfs 或 mount。這只設定正常工具的預設位置，不能阻止程式直接寫宿主 `/tmp`；取消逐工具 bwrap 後，共享暫存區與其他可寫路徑需要明確全局容量政策，不能宣稱 project quota 已覆蓋一切。tmpfs 可未來按需加入，首版不以一萬個 tmpfs 為前提。

## 本機觀測與未驗證部分

本輪只讀探測：`findmnt -T .` 顯示 repo 位於 `/dev/nvme0n1p5` 的 ext4，選項為 `rw,relatime`；`/tmp` 的 statfs 顯示 tmpfs；`/sys/fs/cgroup` 掛為 cgroup2，根 controllers 有 cpu、memory、pids 等。沒有查 superblock project/quota feature、實際 enforcement，沒有取得委派子樹或建立受限 cgroup，所以目前仍不能宣稱已可部署 quota 或 cgroup 限制。

先前[無特權隔離 canary](../2026-09-28-linux-isolation-probes.md)及 [namespace 調查](../../../wf/workflows/investigations/proto5-linux-wall-feasibility.md)只證明各自測到的機制，不是 project quota、多 UID cgroup 或新執行入口的驗收。本輪未 sudo、未改帳號／kernel／掛載／systemd、未接觸 haha。

## 先做小原型，再擴到一萬個靜態身分

第一階段在可丟棄 Linux 測試環境準備 2～3 個帳號、真正 quota volume 與一個委派 cgroup 子樹。驗證工具繼承 UID 與資源域、fork／setsid 不逃出計帳、OOM／pids／quota 失敗能回報、滿 quota 仍可取消與恢復、權限不跨員工、重啟不錯殺／重用識別。先不用雲端 LLM，避免資源隔離失敗被網路變異掩蓋。

第二階段加入少量真 agent 與雲端回合，量啟動開銷、每工作額外程序／fd、控制面記憶體、cgroup 殘留與輸出容量。第三階段才建 10,000 份靜態登記與小資料本體，讓不到 100 個按事件活躍；量的是 idle 管理成本與不同併發負載，不能只用「目錄建得出來」作通過判準。實際硬體承載仍未驗證。

額外維護成本主要是安裝／升級時的帳號與filesystem能力檢查、唯一 cgroup管理者、UID／project ID 生命週期、quota 滿／OOM／程序殘留的故障測試。先支援單一儲存 backend、單一 cgroup委派接法與單一啟動入口，可以避免一開始承擔任意 Linux配置的組合。所有數字配額、併發值與正式部署牆仍待原型量測和使用者選擇。
