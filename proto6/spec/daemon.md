# daemon：登記、喚醒與程序生死

← [規格入口](README.md)｜[kernel 樹](scheduling/README.md)｜[通用 tick](tick.md)

依據：[09-29 新架構](../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../notes/2026-09-29-verdicts.md)。kernel 決定成員何時能做事；daemon 是所有 tick 程序的爸爸，負責啟停與收尾。

## B-601：記憶體登記與按需執行

〔使用者方向 2026-09-29〕daemon 在記憶體使用一張登記表，**node 資料夾路徑就是 id**。所有 node 都按需啟動。daemon 不讀訊息、工作狀態或任務註冊表，不排業務工作、不分資源；只用登記與喚醒資料，讀 inst 僅為 `user` 授權。

本機 socket 提供登記、解除、pause／resume、wake 及查詢，開關與叫醒規則見 [P-104～106](protocol/daemon.md)。daemon 按登記間隔或 wake 跑 inst；互斥依 [B-602](tick.md)。agent 通常不設定期，由 kernel 決定何時叫醒及同時執行數；kernel 本格結束就退出，不等成員，LLM／工具由後續 tick 收結果。

〔建議預設，未拍板〕登記只留啟動所需資料、執行程序與待喚醒標記，欄位依 [daemon 協議](protocol/daemon.md)。`once` 可用單一 inst 檔，跑一格自動解除；可信 parent_id 固定資源歸屬。重複登記、父子鏈與額度核對依 P-104。

### IPC 授權與身分額度

〔使用者方向 2026-09-29〕登記與控制操作都看 **socket 對面的 Linux 帳號**：該 node 的帳號，或其上層 kernel 的帳號。封包自稱的 sender／user 不算呼叫者身分。身分額度與通用 user 以 [B-301](base/identity-resources.md) 為正本；獲准叫醒不代表獲准擴大額度。

### 執行身分與 helper

〔使用者方向 2026-09-29〕daemon 開 tick 前只讀 [inst 的 `user`](base/inst.md) 授權，不解析其他工作內容；不合額度就不跑並寫該 node 的[待處理事項](scheduling/operations.md)。其餘解析與執行規則依 inst 篇。

啟動路徑與可選 helper 依 [B-303](base/identity-resources.md)。node 問題寫該 node 的 `.aos/attention/`（ignore）；寫不出就 stdout 警告。daemon 自身問題才留 daemon attention／stderr；stdout 另印 helper PID，兩個 PID 提示檔依 [P-102](protocol/daemon.md)。

**驗收：**無事 node 不開 tick；重複叫醒不重疊。身分拒絕及無 helper 情境見 [V-03](conformance.md)。

## B-504：通知只是提示

〔使用者方向 2026-09-29〕daemon 可按已登記的時間、IPC 叫醒或新檔通知開 tick，不讀新檔正文。kernel 才核對自己的收件與成員摘要，決定後續要叫醒誰；通知本身不是接件、消費或完成證據。

〔建議預設，未拍板〕執行中的 node 收到叫醒時，daemon 留一個待喚醒標記，收尾後再開下一格。通知合併或遺失後的補查由 kernel 按 [S-202](scheduling/admission.md) 處理，daemon 不代查內容。

**驗收：**漏掉一次通知，完整投件仍能在所屬 kernel 的後續補查被發現；同一 node 連續收到多次提示不會同時跑兩格。內容發布與去重見 [投件](base/transport.md)，互斥見 [B-602](tick.md)。

## B-603：重啟先清空，再讓樹長回來

〔使用者方向 2026-09-29〕daemon 重啟、整機或 WSL VM 關機，都採**在途程序全殺**；不接續孤兒工作。先確認舊 tick 與受管後代清空，才開新 tick；清不掉的 node 不能重開，故障要可見。安全程序識別及後代清空見 [執行器](base/execution.md)，不能拿一個可能重用的 PID 直接 kill。

daemon 設定檔只列頂層 node 及其啟動設定、身分額度。正常退出把登記表、pause、未處理 wake 存進 `state_dir/state.json`，下次開啟先讀回；這份檔不保存或接續執行中的程序。無檔也能從頂層啟動。

**daemon 開啟就自動開始 tick 頂層 node**；已恢復 pause 的頂層保留這次 wake，等 resume。每次啟動換 boot id，頂層發現改變後重新登記直接成員並叫醒子 kernel，逐層重建。平常只在 boot id 或成員清單變動時補登記，不每格重送。壞成員留待辦、跳過，不擋其他子樹。

pause 有變動才批次寫 `state.json`；`pause_save_interval_ms` 建議 1000。正常退出存完整最新狀態；意外退出最多丟最後一個間隔內的 pause 變動，過期登記與未保存 wake 由頂層補查恢復。

〔使用者方向 2026-09-29 晚〕daemon 開的每個 tick 程序（含孫程序）都在該 node 的 cgroup 裡（once 在其 parent 的框裡），daemon 當掉時這些 cgroup 還在。下次啟動、開任何新格之前，daemon 對每個仍有程序的 node cgroup 先送 SIGTERM，等一段寬限時間讓它們優雅收尾，再用 `cgroup.kill` 殺掉剩下的，確認全空才往下。開 tick 時設 `PR_SET_PDEATHSIG` 只當加分（它只作用於直接子程序），不是必要。〔使用者方向 2026-09-29 晚〕寬限時間沿用 `shutdown_grace_ms`；不要求跨重啟保存程序表。〔使用者方向 2026-09-29 晚〕逃生口（讓 daemon 系譜的程序脫離管理）以後再設計，技術上可行（例如由 daemon 或 root helper 把程序搬出 node cgroup）。

〔使用者方向 2026-09-29〕清空後由 node 按 [tick](tick.md) 恢復檔案，執行器／所屬 kernel 核對工作結果；daemon 不代讀結果或判業務終局。

**驗收：**正常重開讀回 pause／wake，無快照時頂層仍自動跑；pause 批存與全殺、逐層補登記見 [V-03](conformance.md)。

## B-604：停機、停用與退役

〔使用者方向 2026-09-29 晚〕daemon 正常關閉時，由 daemon 對在途 tick 送信號，讓它們優雅結束。〔建議預設，未拍板〕前景 Ctrl-C（SIGINT／SIGTERM）正常停機先停止新啟動，對在途 tick 送 SIGTERM，等候可設定的寬限時間，再以 `cgroup.kill` 停止未結束程序並清空受管後代；完成後保存 B-603 的完整 `state.json`；突然被殺則下次依 B-603 恢復。未清空要回報失敗，不能先宣稱停止完成或假裝名額已釋放。具體 TERM／逾時收尾見 [B-203](base/execution.md)。

授權者停用成員時，由所屬 kernel 停止再喚醒／再登記該成員，daemon 阻止新啟動並排空既有程序，再解除登記。停用 kernel 時同樣處理其已登記子樹，不連帶停掉其他隊；只清 daemon 記憶體的一筆資料不能代表持久停用，否則下次父 kernel tick 會把它登記回來。

退役由授權者明示，所屬 kernel 先核對程序已清空、未結工作與資料歸屬；daemon 不另設持久退役表。UID／GID 及 home 都不自動回收或刪除，資料與 Linux 所有權的處置另由有權限者決定；解除登記不會消除舊檔案的 ownership。

**驗收：**停止一個子 kernel 不妨礙別隊運行；受管後代仍在時不回報排空完成；解除登記不刪 home、不把舊 UID 自動發給新成員。

## B-605：依賴、啟動自檢與 cgroup 子樹

〔使用者方向 2026-09-29 晚〕**cgroup v2 是必要依賴；初版不使用 systemd。** systemd 只當開機自動啟動的方式，以及準備 cgroup 子樹的一種做法（下述），不是執行期依賴。daemon 啟動時自檢最低版本：Linux kernel 5.14（`cgroup.kill` 從這版起有）、Python 3.9、git 2.35，並確認 cgroup v2 可用；不合就報錯退出。

**cgroup 子樹：一條通用規則**〔使用者方向 2026-09-29 晚，第十五批；取代先前依 sudo／systemd 分情況的寫法〕：daemon 啟動時一定要有一棵**已經準備好的** cgroup v2 子樹，沒有就報錯退出。

- 子樹在哪：設定的 `cgroup_root`（見 [P-101](protocol/daemon.md)）；省略時就用 daemon 程序自己目前所在的 cgroup。
- 「準備好」是指：這棵子樹存在；它的資料夾和根上的委派檔（`cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads`）交給了 daemon 跑的帳號（sudo 開時是降權後的帳號）。不用 sudo 開時，daemon 自己也要已經在這棵子樹裡，因為 cgroup v2 搬程序要對共同上層有寫權；sudo 開時 daemon 趁還有 root 自己搬進去。
- **開關 `--create-cgroup`**（設定檔對應 `create_cgroup: true`，預設關）：子樹不在時由 daemon 自己建。開了就必須寫 `cgroup_root`，daemon 在那個位置建；建不了（例如沒 root、上層不給寫）就報錯退出。子樹已經在就直接用，不重建。
- 怎麼準備（只是做法範例）：開機由 systemd service 啟動時，unit 寫 `Delegate=yes`（範例見文末附錄），systemd 會把 daemon 所在的 cgroup 劃給它，`cgroup_root` 可省；手動開時可以用 `systemd-run --scope -p Delegate=yes sudo aos daemon --config …` 這類寫法；沒有 systemd 的機器，由 root 事先 mkdir 並 chown 上述檔案。
- **提醒**：在有 systemd 的機器上用 `--create-cgroup` 讓 daemon 自己建，會違反 systemd「cgroup 只有一個寫入者」的約定。通常能用，但不保證，aos 也不擋。

〔使用者方向 2026-09-29 晚〕daemon 自己建子樹時，要在降權前（還是 root 時）建好，只把子樹資料夾及其根的委派檔交給降權後的帳號，父層不動；以 root 開而用現成子樹時，同樣在降權前交給降權後的帳號。daemon 自己搬進子樹下的一個葉框，各 node 的框與它並列，遵守 cgroup v2「程序只放在葉端」的規則；搬程序跨過子樹邊界要 root，所以只在降權前做。

**有就用的可選功能**〔使用者方向 2026-09-29 晚〕：project quota 等功能在啟動時自動偵測，設定檔可強制關（P-101 的 `disable`）。沒有 quota 時，磁碟用量改用定期掃資料夾計算，見 [B-304](base/identity-resources.md)。檔案系統不限定：node 放在不支援某些功能的地方，那些功能就不支援，不列白名單或拒絕清單。

**資源上限設在 node 那層**〔使用者方向 2026-09-29 晚〕：寫在 node 的 cgroup 分支，不是每格設一次，見 [P-107](protocol/daemon.md)。

**初版不做**〔使用者方向 2026-09-29 晚〕：systemd 的沙盒防護（`CapabilityBoundingSet` 等）以後再考慮；helper 掛 tmpfs 拿掉；原本打算交給 systemd 的開程序、定時叫醒、資源框等做法，留到以後當有 systemd 時的可選增強，初版全由 daemon 自己用 cgroup 做。

**驗收：**kernel、Python 或 git 低於最低版本、沒有 cgroup v2 時啟動報錯退出；沒有準備好的子樹、也沒開 `--create-cgroup` 時報錯退出，不自己建；開了 `--create-cgroup` 卻沒寫 `cgroup_root`，或建不了時報錯退出；偵測得到 quota 但設定強制關時不使用；daemon 被 SIGKILL 後重開，仍有程序的 node cgroup 先收到 SIGTERM、寬限後被清空，才開新格。

## 附錄：開機自動啟動的 systemd service 範例

〔使用者方向 2026-09-29 晚〕要開機自動啟動，就把 daemon 寫成一個 systemd service；這只是範例，不算執行期依賴。

```ini
# /etc/systemd/system/aos-daemon.service（範例）
[Unit]
Description=aos daemon
After=local-fs.target

[Service]
# 以 root 開＝sudo 模式（有 helper）；要單帳號模式就加 User=，並在設定寫 common_user
ExecStart=/usr/local/bin/aos daemon --config /etc/aos/daemon.json
# 讓 systemd 把 daemon 所在的 cgroup 劃給它，當成準備好的子樹（B-605）
Delegate=yes
# 停服務時先只對 daemon 送 SIGTERM，讓它自己通知在途 tick 優雅結束
KillMode=mixed

[Install]
WantedBy=multi-user.target
```
