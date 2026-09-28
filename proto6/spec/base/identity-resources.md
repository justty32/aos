# 身分與資源

← [基底](README.md)｜[Linux 規劃來源](../../notes/plan/linux-and-storage.md)

## B-301：權限與額度歸屬〔使用者方向 2026-09-28，[來源](../../notes/2026-09-28-linux-resources-and-task-scheduling.md)〕

一 agent 一 Linux 使用者；工具沿用委託 agent 的權限及資源域。UID／GID 管存取，cgroup v2 管執行資源，project quota 管自有容量，三者不可互相冒充。控制程序留在獨立控制域。取消逐工具 bwrap 必須與身分及整套 aos 外牆一起遷移；本條不選擇 VM、宿主 root 或 user namespace。

**Given** 同一 agent 同時有 tick 與兩個工具；**When** 執行；**Then** 三者使用同一登記身分並受同一 agent 合計上限，不能各取得一整份配額；另一 agent 不可讀其私有檔。

## B-302：部署與登記契約〔建議預設，未拍板〕

Owner：管理者佈建、控制層唯讀使用。deployment profile 必填 `profile_id`（ID）、`wall_backend`（非空字串）、`launcher_backend`（非空字串）、`uid_mapping`（身分映射設定物件）、`cgroup_root`（絕對路徑）、`quota_backend`（`xfs|ext4`）、`data_root`、`control_root`（絕對路徑）、`writable_scope`（非空路徑及容量政策陣列）、`probe_revision`（正整數）。沒有隱式預設 backend；未安裝對應實作或驗證失敗禁止准入。profile 必須說清宿主可見／可寫範圍、映射後 UID 權限與控制程序特權，不能只標「已隔離」。

登記以共用契約 C-02 為正本，另必填 `registry_revision`（正整數）、`profile_id`（ID）。本部署有效 UID／GID 必須在 profile 明示分配範圍內；額外禁止 UID／GID 0 及 daemon／kernel／管理身分，不能讓 agent 與控制端共用 UID；`groups` 由管理者批准，禁止 sudo／管理群組。控制層解析可信 principal 後查登記，拒絕 payload 覆寫。registry_revision 不等於 tick generation；前者改權限配置，後者防舊 tick 提交。任一登記版本改動先停止該 agent 准入並排空，才啟用新版。

啟動 probe 要實際驗證兩身分不能互讀私有檔、可在域內 fork、不能搬離 cgroup、quota 實際拒寫、外牆可寫範圍符合宣告。只見到核心支援不算成功。數字 UID 不立即重用，登記 retirement 後按生命週期退役。

**Given** 少一項 probe、映射重複或 profile 未指定；**When** 申請啟動；**Then** fail closed，狀態保留 queued/waiting 並可查部署錯誤，不以當前 daemon UID 降級執行。

## B-303：先限制、再降權、再工作〔建議預設，未拍板〕

Owner：可信 launcher。次序是查登記→建立 attempt leaf／設限→固定可信 child 進域→清附加群組、設 GID、設 UID→清 capabilities、禁止提權、關閉非核准 fd→核對有效身分與 cgroup→放行降權 runner。不同 profile 可改機制而不能改先後保證；降權與資源安置任一步失敗，child 不可讀工作描述並退出。工具不可寫 registry、SQLite、cgroup 控制檔與管理 mailbox。

必填上限：全局 work 域與 agent 域各有 `memory_max_bytes,pids_max`（正整數）、`cpu_quota_us,cpu_period_us`（正整數，period 預設 100000，範圍 1000..1000000）。記憶體、程序上限無無限值或硬體猜測預設；管理者須給值才准入。設定 memory.oom.group=1 於 attempt leaf；控制域配置獨立保留預算。空 agent cgroup 可按需建立，合計上限在建葉前生效。swap 預設 memory.swap.max=0，backend 不支援則 profile 不合格。CPU 配額是頻寬而非獨占核心。

**Given** 移入 cgroup 或 setuid 失敗；**When** 放行程序；**Then** 不執行 agent argv。兩工具合計超 memory.max 時按共同域限制而非倍增。

## B-304：容量與可寫路徑〔建議預設，未拍板〕

Owner：quota backend 管理者。每 agent 必填 `quota_bytes,quota_inodes`（正整數硬上限，無預設），project ID 與 filesystem ID 一起識別；home、history、checkpoint blobs、輸出與 scratch 設繼承 project。部署拒絕沒有 enforcement 的 backend，不回退到 du 統計。外部 workspace 的容量由其管理者負責，profile 必須逐項聲明；`TMPDIR` 只是預設位置，不能當成阻止寫 `/tmp` 的機制。所有其他可寫路徑必須受全局容量政策控制。

寫 checkpoint 遇 EDQUOT 不更新 pointer，控制帳本記錄 quota、暫停該 agent 新准入並通知上層；現有工作按取消流程排空。只有清理後 probe 有可寫空間且管理者恢復，才解除暫停。不以刪歷史或加額度自動補救。工具私自寫檔的 EDQUOT 未必可被 supervisor 觀察；只有受控 I/O errno 或明確診斷才標 quota，否則保存 exit 原因，不猜測。

**Given** block／inode quota 各滿一次；**When** 提交 checkpoint；**Then** 舊 pointer 可讀、控制區仍保存原因、取消可完成。工具忽略 EDQUOT 後 exit 0 不被宣稱已驗證其業務資料完整。

機制依據：[Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) 的 cpu.max period、memory.oom.group、memory.swap.max、cgroup.kill 定義；profile 必須實測可用性，文件支援不等於部署已有權限。

## 待使用者拍板與現況

三軸及共享歸屬為既有方向；具體 profile、數值與恢復操作均待拍板。先驗兩 agent，再驗萬級登記；metadata 測試不能替代真 UID／quota 驗收。
