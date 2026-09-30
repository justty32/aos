# daemon：登記、喚醒與程序生死

← [規格入口](README.md)｜[kernel 樹](scheduling/README.md)｜[通用 tick](tick.md)｜[daemon 協議](protocol/daemon/README.md)

依據：[09-29 新架構](../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../notes/2026-09-29-verdicts.md)、[第十八批](../notes/verdicts/09-special-computing-os.md)、[第十九批](../notes/verdicts/10-tick-minimal-core.md)。kernel 決定成員何時能做事；〔使用者方向 2026-09-30，第十九批〕daemon 是**定期跑 `aos-tick` 的標準程式**，負責它開的程序的啟停與收尾，另開 tick–daemon 通道（B-612～614）。daemon 不是 tick 存在的前提：tick 怎麼被執行不管，cron、人手直接跑也行，只是沒有通道。

〔使用者方向 2026-09-30，第十八批〕本篇是 daemon 行為的正本（[V-01](conformance.md)）；[daemon 協議](protocol/daemon/README.md)（P-100～119）只留設定欄位、method 的 params／result、helper 通道、runner 回報與錯誤碼。

〔使用者方向 2026-09-30，第十九批〕本篇的保證以標準配備全掛為前提（[T-01](terms.md)、[B-629](tick.md)）。daemon 端的重啟清空、收尾、排空、node 框與上限、切換使用者（helper）都屬標準配備；本篇只寫 daemon 那一側，tick 那一側見 [tick](tick.md)。沒 cgroup 時走備援，哪些條文只在有 cgroup 時適用，各條標明（B-605）。

## B-601：記憶體登記與按需執行

〔使用者方向 2026-09-29〕daemon 在記憶體使用一張登記表，**node 資料夾路徑就是 id**。〔使用者方向 2026-09-30，第十九批〕辨識一個 tick 看**資料夾路徑或 inst.json 路徑**：登記時給的是 `<資料夾>/.aos/inst.json` 或 `<資料夾>/inst.json`，一律正規化成所在資料夾；掛載行程（B-613）照給的路徑，可以是單檔。登記的 node 按登記間隔或叫醒開格。

〔使用者方向 2026-09-29；第十九批改寫〕daemon 不讀工作狀態或任務註冊表，不排業務工作、不分資源；只用登記與喚醒資料，讀 inst 僅為 `user` 授權。訊息只在通道上**暫存與轉交**，不解析正文（B-614）。

本機 socket 提供登記、解除、叫醒、暫停與恢復、佈建、查詢，以及通道事務：登記與解除見 [B-606](#b-606登記解除換父與身分額度)，叫醒、暫停與故障停格見 [B-607](#b-607叫醒暫停故障停格與格次序號)，佈建見 [B-609](#b-609佈建固定動作與-helper-動作)，通道見 [B-612～614](#b-612tickdaemon-通道)，method 形狀見 [daemon 協議](protocol/daemon/README.md)。同一資料夾同時只跑一格由 tick 核心的鎖保證（[B-602](tick.md)）；daemon 另外自己避免同時開同一 node 的兩格，這不是互斥的來源。agent 通常不設定期，由 kernel 決定何時叫醒及同時執行數；kernel 本格結束就退出，不等成員，LLM／工具由後續 tick 收結果。

### IPC 授權與身分額度

〔使用者方向 2026-09-29〕人手與 CLI 的請求看 **socket 對面的 Linux 帳號**（`SO_PEERCRED`）：該 node 的帳號，或其上層的帳號。封包自稱的 sender／user 不算呼叫者身分。〔使用者方向 2026-09-30，第十九批〕明示例外是 tick–daemon 通道：請求帶本格憑證時，呼叫者是憑證所屬的那個 tick（B-612）。上層指**有效上層鏈**（預設看資料夾包含，登記可覆蓋，B-606），不是 OS 父目錄本身。身分額度與通用 user 以 [B-301](base/identity-resources.md) 為正本，額度的寫法與包含判定見 B-606；獲准叫醒不代表獲准擴大額度。

〔建議預設，未拍板；第十九批從 P-103 搬上〕先驗 JSON、method 與參數，再授權；不能用 PID、路徑前綴或封包的 `user` 當呼叫者。同 UID 共用同一 OS 權限，不帶憑證時分不出是哪個 node 或工具在呼叫。root 或通用 user 不因名稱自帶全樹特權，是 owner 或祖先 owner 才符合。可連 socket 不等於通過 method 授權。RPC ID 只配對回應，不是永久執行收據；斷線不代表沒做：登記、pause、resume 可以查目前值核對，wake 可合併但不是永久去重，掛行程與特權動作不准因沒回應就盲目重送。daemon 不加持久重播帳本。

### 執行身分與 helper

〔使用者方向 2026-09-29〕daemon 開 tick 前只讀 [inst 的 `user`](base/inst.md) 授權，不解析其他工作內容；不合額度就不跑，照 B-607 停格。其餘解析與執行規則依 inst 篇。

啟動路徑與可選 helper 的角色依 [B-303](base/identity-resources.md)，helper 做哪些固定動作見 B-609。node 問題寫該 node 的 `.aos/attention/`（ignore）；寫不出就 stdout 警告。daemon 自身問題才留 daemon attention／stderr；stdout 另印 helper PID，兩個 PID 提示檔依 [P-102](protocol/daemon/startup-and-ipc.md)。事項怎麼處理見 [S-405](scheduling/operations.md)。

〔建議預設，未拍板；第十九批從 P-108 搬上〕**helper 的記憶體鏡像**：helper 存活時，登記與更新先經它重驗（啟動設定的頂層額度、可信上層鏈、原始 `user` 與路徑）才生效；鏡像只在記憶體。沒 helper 時，只用通用 user、沒佈建權的登記由 daemon 自己核對；只授 cgroup 動作的，另核對它落在交給 daemon 的子樹內；其他帳號或要 helper 的動作的新登記回 `helper_unavailable`，既有的通用 user 登記照常跑。helper 用安全的程序 handle 追蹤、wait 自己的孩子並跨帳號收尾；daemon 不 wait helper 的孩子、不信裸 PID。helper 失聯時 daemon 只做自己權限做得到的收尾，其他帳號沒確認全空就阻擋，斷線不代表已退出，也不能重送不明的開格。〔建議預設，未拍板；第十九批從 P-102 搬上〕root 用的設定檔及其父目錄不得由不受信任的 node 改寫；helper 在 fork 前固定一份設定副本（B-608）；設定父死訊號時處理競態，父死訊號與私有通道斷線一起監看。額度不准 UID 0 或 root 別名。helper 消失而不能收尾時保留占用、阻止新格，不宣稱清空。

### 開格：runner 與回報

〔建議預設，未拍板；第十九批從 P-109、P-110 搬上〕daemon（或 helper）以固定的 `aos-runner` 開每一格與每個掛載行程：先降權、設好群組與資源，runner 再核對 UID 與 inst 原來源的 bytes 跟授權時的快照相同，才照 [inst](base/inst.md) 解析、開檔與執行。argv 與回報形狀見 [P-109、P-110](protocol/daemon/provision-and-runner.md)。

- **串流**：runner 的 stdin／stdout 是 `/dev/null`；stderr 由 daemon 收集成 node 診斷，不直通 daemon 的 stderr，資料夾 node 暫定寫 `.aos/runner-stderr.log`（覆寫、ignore），輪替與留存以後再定。
- **環境**：〔使用者方向 2026-09-30，第十九批〕除了 [B-303](base/identity-resources.md) 與 inst 的規則，daemon 開的每一格、每個掛載行程都多放兩個通道變數（B-612）；不帶管理 fd 或 key。
- **回報**：每次完整收尾只回報一次。前置失敗（身分不在額度內、來源變了等）回 `started:false`；已放行後子程式自己的結束碼照實回報，被訊號結束另帶訊號編號。runner 在已放行後自己收尾失敗，回報 `FinalizeFailed`，不能當成子程式退出 125；沒有完整可信回報就是結果不明，不能推定從未執行。前置檢查可能已建目錄或截斷輸出，125 不代表沒有檔案副作用。
- 後代清空、串流收完與取消競態依 [B-202、B-203](base/execution.md)；範圍沒清空前不釋放名額、不開下一格，所有失敗都不自動重跑結果不明的工作。

**驗收：**無事 node 不開 tick；重複叫醒不重疊。身分拒絕及無 helper 情境見 [V-03](conformance.md)。給 `.aos/inst.json` 或 `inst.json` 路徑登記，得到的 node id 是所在資料夾。

## B-504：通知只是提示

〔使用者方向 2026-09-29〕daemon 可按已登記的時間、IPC 叫醒或新檔通知開 tick，不讀新檔正文。kernel 才核對自己的收件與成員摘要，決定後續要叫醒誰；通知本身不是接件、消費或完成證據。

〔使用者方向 2026-09-30，第十九批〕通道訊息送到時，**只有急件**才叫醒收件 tick，一般件等它自己的下一格（B-614）。

〔建議預設，未拍板〕執行中的 node 收到叫醒時，daemon 留一個待喚醒標記，收尾後再開下一格。通知合併或遺失後的補查由 kernel 按 [S-202](scheduling/admission.md) 處理，daemon 不代查內容。

**驗收：**漏掉一次通知，完整投件仍能在所屬 kernel 的後續補查被發現；同一 node 連續收到多次提示不會同時跑兩格。內容發布與去重見 [投件](base/transport.md)，互斥見 [B-602](tick.md)。

## B-603：重啟先清空，再讓樹長回來

〔使用者方向 2026-09-29〕daemon 重啟、整機或 WSL VM 關機，都採**在途程序全殺**；不接續孤兒工作。先確認舊 tick 與受管後代清空，才開新 tick；清不掉的 node 不能重開，故障要可見。安全程序識別及後代清空見 [執行器](base/execution.md)，不能拿一個可能重用的 PID 直接 kill。〔使用者方向 2026-09-30，第十九批〕重啟清空屬標準配備的 daemon 端。

**啟動順序**：啟動偵測（B-605）→ 取得排他鎖（[B-611](#b-611一棵資源樹只准一個-daemon)），取不到就拒絕啟動，在這之前不讀回、不清殺、不寫狀態 → 讀回 `state.json` → 清空舊程序 → 開 socket、開始開格。

〔使用者方向 2026-09-29 晚〕**清空舊程序**（有 cgroup 時）：daemon 開的每個 tick 程序（含孫程序）都在該 node 的 cgroup 裡（掛載行程在其上層的框裡），daemon 當掉時這些 cgroup 還在。下次啟動、開任何新格之前，daemon 對每個仍有程序的受管框走一次 B-604 的**收尾**（寬限沿用 `shutdown_grace_ms`），確認全空才往下。受管框是 `tick`、`task-*`、`mount-*` 與子 node 的 `n-*`；node 自己開的其他子框是逃生口，照 `kill_escape_cgroups` 決定殺不殺（見 [B-605](#b-605依賴啟動自檢與-cgroup-子樹)，預設不殺）。開 tick 時設 `PR_SET_PDEATHSIG` 只當加分（它只作用於直接子程序），不是必要；不要求跨重啟保存程序表。〔使用者方向 2026-09-30，第十九批〕走備援（沒 cgroup）時，舊 daemon 留下的程序找不回來，重啟清空不成立，這是備援級較弱的地方（B-605）。

**存檔與讀回**：daemon 設定檔只列頂層 node 及其啟動設定、身分額度。正常退出把登記表、pause、未處理 wake 存進 `state_dir/state.json`（格式見 [P-116](protocol/daemon/shutdown.md)），這份檔不保存或接續執行中的程序；無檔也能從頂層啟動。啟動讀回後，依目前 roots、inst 與上層鏈重新核對每筆登記的身分與授權，不合的丟掉；沒有覆蓋的登記重新照資料夾推上層（B-606）；缺檔或壞檔就從 roots 重建，壞檔留診斷。讀回後先把 `clean_shutdown` 原子改成 false，才接受工作。寫檔一律先寫完整暫檔再原子替換（[P-003](protocol/README.md)）。

- 〔使用者方向 2026-09-30，第十九批〕掛載行程（B-613）不存檔、不接回；重啟時被收尾的，由掛它的 tick 照工作結果與 unknown 規則核對。通道上暫存的訊息也不存檔（B-614）。其他未處理 wake 照常接回。
- 讀回的登記一律算新登記：換新的登記識別，格次序號從頭算（B-606、B-607）。

〔使用者方向 2026-09-29〕**pause 批次存檔**：pause 有變動才批次寫 `state.json`，最多每 `pause_save_interval_ms`（預設 1000）原子寫一次，標 `clean_shutdown:false`；正常退出存完整最新狀態。意外退出最多丟最後一個間隔內的 pause 變動，過期登記與未保存 wake 由頂層補查恢復。寫檔失敗寫 daemon 自身事項並報 stderr。

**逐層重建**：**daemon 開啟就自動開始 tick 頂層 node**；已恢復 pause 的頂層保留這次 wake，等 resume。每次啟動換 boot id（[P-115](protocol/daemon/registration.md)），頂層發現改變後重新登記直接成員並叫醒子 kernel，逐層重建。平常只在 boot id 或成員清單變動時補登記，不每格重送（B-606）。壞成員留待辦、跳過，不擋其他子樹。

〔使用者方向 2026-09-30，第十八批〕**空框清理**（有 cgroup 時）：重啟清空後，沒有登記對應的 `mount-*` 框直接刪（掛載行程不會接回）；沒有登記對應的 `n-*` 框先留著，等逐層重建完、仍沒人登記才由下往上刪，避免先刪掉稍後又要重建的框（重建會讓上限要重寫、用量歸零）。〔建議預設，未拍板〕「重建完」的判斷：所有已登記、沒暫停的 node 自這次啟動以來都至少跑完一格。框裡還有逃生口的程序就不刪。框已交給別的帳號時由 helper 刪（B-609）。`task-*` 的清理歸 [B-202](base/execution.md)。

〔使用者方向 2026-09-29〕清空後由 node 按 [tick](tick.md) 恢復檔案，執行器／所屬 kernel 核對工作結果；daemon 不代讀結果或判業務終局。

**驗收：**正常重開讀回 pause／wake，無快照時頂層仍自動跑；pause 批存與全殺、逐層補登記見 [V-03](conformance.md)。逐層重建完仍沒人登記的空框被刪，重建途中的框不先刪。

## B-604：收尾、停機、停用與退役

〔使用者方向 2026-09-30，第十九批〕收尾與排空屬標準配備的 daemon 端。

### 收尾

〔使用者方向 2026-09-30，第十八批；編輯用詞〕**收尾**是 daemon 清掉一個範圍的固定做法：停止這個範圍開新格 → 對範圍內程序送 SIGTERM → 等 `shutdown_grace_ms`（[P-101](protocol/daemon/startup-and-ipc.md)，預設 2000）→ 對仍有程序的框寫 `cgroup.kill` → 確認全空。重啟、停機、解除登記、砍掉掛載行程、helper 停程序都用這一套，取消在跑的工作也用這套收尾（[B-203](base/execution.md)）；範圍含 `tick`、`task-*`、`mount-*` 與已登記子 node 的框，逃生口照 `kill_escape_cgroups`（B-605）。已經在收尾的照開始時的寬限值走完，之後改設定不影響它。確認不了全空就回報失敗、保留阻擋與占用，不能先宣稱完成或假裝名額已釋放。執行器自己的逾時（照 inst 的寬限）與 `task-*` 殘留（直接 `cgroup.kill`）屬 [B-202](base/execution.md)，不是這裡的收尾。

〔使用者方向 2026-09-30，第十九批〕**沒 cgroup 時**，收尾改走標準配備的備援（[B-631](tick.md)）：daemon 自己是 child subreaper，每一格與每個掛載行程開在自己的程序群組；收尾對那個程序群組送 SIGTERM、等 `shutdown_grace_ms`、再送 SIGKILL，並回收掛到 daemon 名下的孤兒程序。跳出程序群組又還活著的後代不保證被殺，這是備援級較弱的地方。

〔使用者方向 2026-09-30，第十八批〕「排空」只指下面的排空停機；解除登記不叫排空。

### 停機：立即與排空

〔使用者方向 2026-09-29 晚；第十八批加排空〕daemon 收到 SIGINT（前景 Ctrl-C）或 SIGTERM 時停機；走哪一種由設定 `stop_mode` 決定（`immediate`／`drain`，預設 `immediate`），不開停機用的 IPC。訊號、結束碼與設定欄位見 [P-114](protocol/daemon/shutdown.md)。

- **立即停**：停止新登記、叫醒、掛行程與開格，對所有在途程序做一次收尾；清空後存 B-603 的完整 `state.json`、讓 helper 退出、清 socket 與 PID 檔，然後回 0；清不空或存檔失敗回 125。通道上暫存的訊息直接丟掉（B-614）。
- **排空停**〔使用者方向 2026-09-30，第十八批〕：
  1. 拒收新的掛行程與新成員登記（回 `stopping`）；已登記的 node 照常開格，讓 kernel 能繼續收結果，通道照常收送。被拒的掛行程不會啟動；沒收到回應時照 [S-401](scheduling/operations.md) 判讀。
  2. 等已掛的行程全部跑完；然後停止開新格，等在途 tick 自然結束。
  3. 全部結束就照立即停的後半存檔、退出。
  4. 從收到訊號起超過 `drain_timeout_ms`（預設 600000，10 分鐘），或排空途中再按一次 Ctrl-C（SIGINT），就改成立即停〔第十八批 Q16〕；排空途中再收到 SIGTERM 也同樣改立即停〔建議預設，工程補充〕。被收尾的掛載行程由掛它的 tick 照 unknown 規則核對。
- 停機或排空中不接受熱重載（B-608）。突然被殺則下次依 B-603 恢復，不因 socket 不見就推論已全空。未清空要回報失敗，不能先宣稱停止完成。

### 停用與退役

〔使用者方向 2026-09-29〕授權者停用成員時，由所屬 kernel 停止再喚醒／再登記該成員，並請 daemon 解除登記（B-606 的解除就是收尾後刪登記）。停用 kernel 時同樣處理其已登記子樹，不連帶停掉其他隊；只清 daemon 記憶體的一筆資料不能代表持久停用，否則下次上層 kernel tick 會把它登記回來。kernel 何時對成員發解除見 [S-202](scheduling/admission.md)。

退役由授權者明示，所屬 kernel 先核對程序已清空、未結工作與資料歸屬；daemon 不另設持久退役表。UID／GID 及 home 都不自動回收或刪除，資料與 Linux 所有權的處置另由有權限者決定；解除登記不會消除舊檔案的 ownership。

**驗收：**停止一個子 kernel 不妨礙別隊運行；受管後代仍在時不回報收尾完成；解除登記不刪 home、不把舊 UID 自動發給新成員。`stop_mode:"immediate"` 時 Ctrl-C／SIGTERM 後不開新格，等受管後代與 helper 全空才回 0，清不空不回 0。`stop_mode:"drain"` 時 SIGTERM 後新的掛行程被拒、已登記 node 照常開格，已掛的行程做完才退出；超過 `drain_timeout_ms` 或再按一次 Ctrl-C 改立即停。

## B-605：依賴、啟動自檢與 cgroup 子樹

〔使用者方向 2026-09-30，第十九批；推翻第十四、十五批「沒 cgroup v2 就拒絕啟動」〕**tick 核心不需要 cgroup**；cgroup 是標準配備（cgroup 框）用的機制。標準配備內建沒 cgroup 時的備援（[B-631](tick.md)），所以沒 cgroup 仍算全掛，只是降到備援級、保證較弱（[T-01](terms.md)）。初版不使用 systemd 當執行期依賴；systemd 只當準備 cgroup 子樹與開機自動啟動的一種方式（下述）。

**啟動偵測**（取代舊的「不合就報錯退出」）：

- **daemon 自己的最低需求**：Python 3.9；不合就報錯退出（125）。
- **cgroup 走完整路還是備援路**：Linux kernel ≥ 5.14（`cgroup.kill` 從這版起有）、cgroup v2 可用、拿得到準備好的子樹（下述）三者都成立就走完整路；否則走備援路。〔建議預設，未拍板〕設定**明寫** `cgroup_root` 或開了 `create_cgroup` 卻準備不好，照舊報錯退出（125），不默默改走備援；兩者都沒寫時才自動偵測。
- 偵測結果在 stdout 印一行，跟 tick 的 `standard: cgroup=full` 同一種寫法（[B-630](tick.md)、[P-101](protocol/daemon/startup-and-ipc.md)）；走備援時 stderr 另印一次警告，不寫事項。不問 y／n：daemon 端缺 cgroup 時有備援，不算沒全掛；什麼情況才算沒全掛、要問 y／n，以 [B-630](tick.md) 為正本，由各 tick 自己查。
- git 由各 tick 的標準配備自己用，daemon 不查；git 最低版本與檢查步驟見 [B-630](tick.md)，沒 git 的備援見 [B-632](tick.md)。

〔使用者方向 2026-09-30，第十九批〕**走備援時**：本篇只在有 cgroup 時適用的部分——框的命名與委派、資源上限、逃生口、`kill_escape_cgroups`、B-609 的 `cgroup_*` 動作、B-611 對 cgroup 子樹的那把鎖——都不適用；`cgroup_*` 動作回 `unsupported`，`node.show` 的 `cgroup` 為 null。收尾改走備援（B-604），重啟清空不成立（B-603），完整與備援的保證對照見 [B-631](tick.md)。daemon 照常開格、照常提供通道。

### 準備 cgroup 子樹（不用 sudo 的方式優先）

〔使用者方向 2026-09-30，第十九批〕**第一推薦：systemd 使用者委派子樹**，不用 sudo：

```sh
systemd-run --user --scope -p Delegate=yes aos daemon --config ~/.config/aos/daemon.json
```

`cgroup_root` 省略，daemon 就用這個 scope 當子樹。檢查步驟〔建議預設〕：

1. `stat -fc %T /sys/fs/cgroup` 印 `cgroup2fs`：是 cgroup v2。
2. `uname -r` 至少 5.14。
3. `systemctl --user is-system-running` 有回應：有使用者層的 systemd。WSL 要先在 `/etc/wsl.conf` 設 `[boot]` 的 `systemd=true`。
4. 在委派 scope 裡看自己拿到的子樹：`systemd-run --user --scope -p Delegate=yes sh -c 'p=$(sed -n "s/^0:://p" /proc/self/cgroup); ls -ld /sys/fs/cgroup$p /sys/fs/cgroup$p/cgroup.subtree_control; cat /sys/fs/cgroup$p/cgroup.controllers'`：資料夾與 `cgroup.subtree_control` 的擁有者是自己；`cgroup.controllers` 至少有 `memory pids`。沒有 `cpu` 時 CPU 上限回 `unsupported`，其餘照用（要 `cpu` 得讓使用者層的 systemd 委派它，屬部署設定）。
5. 開機自動啟動：寫成使用者層的 service（`Delegate=yes`），並對該帳號 `loginctl enable-linger`；用 root 開的系統層範例見文末附錄。

**cgroup 子樹：一條通用規則**〔使用者方向 2026-09-29 晚，第十五批；第十九批改「沒有就報錯退出」為走備援〕：走完整路時一定要有一棵**已經準備好的** cgroup v2 子樹。

- 子樹在哪：設定的 `cgroup_root`（[P-101](protocol/daemon/startup-and-ipc.md)）；省略時就用 daemon 程序自己目前所在的 cgroup。〔第十六批、第十七批〕不論省略或有寫，只要 daemon（或其他程序）就在子樹根那層，daemon 啟動先在那層開 `daemon` 子層、把那層程序全搬進去，讓那層只當分支、不放程序（cgroup v2 規定已有子層又要開 controller 的那層不能放程序）；搬不動或一直有新程序進來，有寫 `cgroup_root` 就報錯退出，省略時改走備援。
- 「準備好」是指：這棵子樹存在；它的資料夾和根上的委派檔（`cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads`）交給了 daemon 跑的帳號（sudo 開時是降權後的帳號）。不用 sudo 開時，daemon 自己也要已經在這棵子樹裡，因為 cgroup v2 搬程序要對共同上層有寫權。
- 〔使用者方向 2026-09-29 晚〕**sudo 開時**：daemon 在降權前（還是 root 時）把子樹資料夾及其根的委派檔交給降權後的帳號、自己搬進子樹下的葉框，父層不動；搬程序跨過子樹邊界要 root，所以只在降權前做。
- **開關 `--create-cgroup`**（設定檔對應 `create_cgroup: true`，預設關）：子樹不在時由 daemon 自己建，建在 `cgroup_root`（開了就必須寫，否則用法錯 2）；sudo 開時在降權前建。建不了（例如沒 root、上層不給寫）就報錯退出；子樹已經在就直接用，不重建。
- 其他準備方式（只是範例）：系統層 systemd service 寫 `Delegate=yes`（文末附錄），`cgroup_root` 可省；手動用 `systemd-run --scope -p Delegate=yes sudo aos daemon --config …`；沒有 systemd 的機器，由 root 事先 mkdir 並 chown 上述檔案。
- **提醒**：在有 systemd 的機器上用 `--create-cgroup` 讓 daemon 自己建，會違反 systemd「cgroup 只有一個寫入者」的約定。通常能用，但不保證，aos 也不擋。
- 〔使用者方向 2026-09-30，第十八批〕**硬上限由部署者在更外層設**：頂層 kernel 的額度檔只是分配政策，不承諾頂層真的被卡住；整棵子樹（含 daemon 自己建的）要有總上限，由部署者事先設在子樹根或更上一層。

〔使用者方向 2026-09-29，第十六批〕**框的命名**（有 cgroup 時；node id 是任意長的絕對路徑，不能直接當 cgroup 名）：

- daemon 自己：`<子樹>/daemon`。
- node：框放在有效上層 node 的框下（頂層放子樹根下），名字 `n-<h>`，`<h>` 是 node_id 的 UTF-8 bytes 做 sha256 取前 16 個小寫 hex；這格的程序放在它底下的 `tick` 葉框，子 node 的框與 `tick` 並列，所以 node 框只當分支。
- 掛載行程〔第十九批改名，原 `once-<h>`〕：框放在掛它的 node 的框下，名字 `mount-<h>`（同法），本身就是葉框（B-613）。
- 任務層〔第十七批〕：tick 跑的每個任務在 node 框下開 `task-<序號>`，與 `tick` 並列；開、殺、刪與格首清上一格殘留以 [B-202](base/execution.md) 為正本（成本見[實測](../notes/probes/per-task-cgroup-cost.md)）。
- **委派**：tick 以 node 的帳號自己建任務層並把子程序搬進去，所以 daemon 建 node 框時要把 `n-<h>` 資料夾及其 `cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads` 交給 node 的執行帳號；上限檔仍歸 daemon，node 改不了。帳號不是 daemon 自己時經 helper 做（B-609）。
- 保留名稱：`daemon`、`tick`、`task-*`、`n-*`、`mount-*`，node 自己開子框不能用這些名字。16 hex 碰撞機率可忽略，首版不另做碰撞偵測。

**資源上限設在 node 那層**〔使用者方向 2026-09-29 晚〕：寫在 `n-<h>` 分支一次，之後每格沿用、不在每格重設；隨時可改（B-609）。

〔使用者方向 2026-09-30，第十八批〕**逃生口**（有 cgroup 時）：node 可以在自己的 `n-<h>` 下另開子框（名字避開保留名稱），把程序搬進去刻意留常駐程序。格次收尾只看 `tick` 與 `task-*`，不管這些子框。daemon 重啟（B-603）與解除登記（B-606）時，這些子框殺不殺由設定 `kill_escape_cgroups` 決定：預設 false，不殺、框留著；設成 true 就一併收尾。逃生口的程序仍在 node 框裡，照樣受 node 的資源上限管。框裡還有逃生口時，`n-<h>` 刪不掉，解除登記照樣完成、框留著並寫該 node 的事項，等之後空了由 B-603 的空框清理刪。

**有就用的可選功能**〔使用者方向 2026-09-29 晚〕：project quota 等功能在啟動時自動偵測，設定檔可強制關（P-101 的 `disable`，可熱重載，B-608）。沒有 quota 時，磁碟用量由磁碟資源任務定期量（[B-304](base/identity-resources.md)、[S-203](scheduling/admission.md)）。檔案系統不限定：node 放在不支援某些功能的地方，那些功能就不支援，不列白名單或拒絕清單。

**初版不做**〔使用者方向 2026-09-29 晚〕：systemd 的沙盒防護（`CapabilityBoundingSet` 等）以後再考慮；helper 掛 tmpfs 拿掉；原本打算交給 systemd 的開程序、定時叫醒、資源框等做法，留到以後當有 systemd 時的可選增強，初版全由 daemon 自己用 cgroup 做。

**驗收：**Python 低於 3.9 時啟動報錯退出；Linux 低於 5.14、沒有 cgroup v2、或省略 `cgroup_root` 時自己所在的 cgroup 沒委派給自己，daemon 照常啟動並印出走備援、照常開格；明寫 `cgroup_root` 卻沒準備好、也沒開 `--create-cgroup` 時報錯退出，不自己建；照第一推薦用 `systemd-run --user --scope -p Delegate=yes` 開、不寫 `cgroup_root` 時走完整路；省略 `cgroup_root`、或有寫但該層有程序時，原層只剩子層、沒有程序；開了 `--create-cgroup` 卻沒寫 `cgroup_root` 時以用法／設定錯退出（結束碼 2，第十七批），建不了時報錯退出；偵測得到 quota 但設定強制關時不使用；有 cgroup 時 daemon 被 SIGKILL 後重開，仍有程序的受管框先收到 SIGTERM、寬限後被清空，才開新格。node 自開的子框在預設設定下，重啟與解除登記後程序還在；`kill_escape_cgroups:true` 時被清空。

## B-606：登記、解除、換父與身分額度

〔使用者方向 2026-09-29；第十八批改寫，行為從 P-104／105 搬上〕method 形狀見 [P-104～105](protocol/daemon/registration.md)，誰可呼叫見 [P-103](protocol/daemon/startup-and-ipc.md)。

〔使用者方向 2026-09-30，第十九批〕**登記是什麼**：登記＝請 daemon 定期或被叫醒時跑這個 tick（排程），外加可選的**覆蓋上層**。登記不是 tick 存在的前提；上下層預設由資料夾決定（[B-628](tick.md)），登記只影響 daemon 的排程與覆蓋。

**上層怎麼定**〔使用者方向 2026-09-30，第十九批〕：

- **預設看資料夾**：從本 node 的資料夾往上，最近一個有 tick 的資料夾就是上層（判準與路徑比對見 [B-628](tick.md)）。〔建議預設〕不論預設或覆蓋，**有效上層都必須已在同一個 daemon 登記**，否則回 `not_registered`；所以沒有覆蓋時，資料夾推得的上層沒登記就登記不了。
- **覆蓋**：登記時帶 `parent_id` 指定別的上層，就蓋過預設。覆蓋存在 daemon 的登記裡，不在 daemon 底下的 tick 沒有覆蓋。**新舊兩個上層都要同意**：舊上層是目前的有效上層（新登記時就是資料夾推得的那個），新上層是 `parent_id`；呼叫者必須同時是兩者的 owner 或祖先 owner（帶憑證時，憑證所屬的 tick 必須同時是兩者或兩者的上層鏈上的一個）。〔暫定〕資料夾推不出上層，或推得的上層不在這個 daemon 登記時，它沒辦法經 daemon 表態，只要新上層同意。
- **覆蓋只改管理關係**：覆蓋後的上層負責分資源（框放在它的框下）、叫醒、解除與佈建授權；**管轄權仍跟著資料夾**，資料夾上層對那個資料夾的檔案仍有最高裁量。
- 〔暫定〕daemon 在登記時解析一次有效上層並記下；之後有人在中間的資料夾新開、登記 tick，daemon 不自動改這筆的上層，要改就照下面的換父。同一筆重送時解析結果不同，當成換父處理。
- 頂層只從設定載入，上層固定是 null。〔暫定〕設定裡兩棵 root 的資料夾互相包含時，整份設定不收（`config_invalid`）。
- 身分繼承（inst 的 `user` 省略時繼承上層）跟**有效上層**，見 [inst](base/inst.md)。

**新登記**：頂層只從設定載入（增刪走熱重載，B-608）；其餘 node 由有效上層的 owner 或祖先 owner 經 `node.register` 登記（帶憑證時，由有效上層那個 tick 或它的上層鏈上的 tick 登記），首次必須有上層同意，本版不提供首次自登記。新登記不自動啟動，上層 kernel 重建子 kernel 時明確再送 wake；頂層由 daemon 自動各排第一格。每筆登記保存授權時解析出的 `owner_uid`；改 inst 不立即改掉 owner，有效的下一格身分採用或經原 owner／上層授權的重新登記才更新。inst 尋找依 [inst](base/inst.md)；登記的 node 必須是資料夾（單檔 inst 要用掛載行程，B-613）。同一個 id 不能同時是登記又是掛載行程，衝突回 `registration_conflict`。

**登記識別與別每格重登**：每次新登記（首次登記、解除後再登、換父、daemon 重啟後讀回或重建）daemon 配一個新的 `registration_id`；同一筆登記的重送與內容更新不換。kernel 在自己的 repo 記下成功同步的 boot id 與成員版本，每格只比對小查詢，兩者沒變且無待修復差異就不重登；重開、清單改變或已知解除時才補差異，並叫醒子 kernel 逐層重建；失敗筆不標成功、不擋其他成員，也不重送結果不明的掛行程。kernel 那側何時登記成員見 [S-202](scheduling/admission.md)。

**身分額度**〔使用者方向 2026-09-30，第十八批；推翻第十一批「不支援萬用名稱」〕：額度的每一項可以是

| 寫法 | 意思 |
|---|---|
| 帳號名稱（字串） | 確切名稱；可預授尚未存在的名稱，只能由設定往下傳 |
| UID（整數） | 確切 UID |
| `{"prefix":"aos-"}` | 名稱以這個前綴開頭的帳號（比名稱，不比 UID） |
| `{"uid_min":N,"uid_max":M}` | UID 在 N～M 之間（含兩端，N ≤ M） |

- 一律排除 UID 0 與 root 別名；前綴與範圍規則也一律不涵蓋 UID < 1000 的系統帳號。
- 名稱與 UID 別名不得重複。帳號第一次被建立（或第一次經前綴比中）後，daemon 綁住名稱與得到的 UID；之後同名卻是別的 UID 回 `user_mismatch`，不能接管同名帳號。
- **子額度必須被上層額度包含**：確切名稱或 UID 要落在上層的某一項裡（解析成名稱比前綴、解析成 UID 比範圍）；前綴要以上層的某個前綴開頭；範圍要落在上層的某個範圍內。前綴與範圍之間互不算包含。佈建權的動作集合、路徑、群組同樣只能是上層的子集（B-609）。整條鏈的上限仍受頂層啟動設定限制。這裡的上層是有效上層。
- 新 node 的 inst user 在登記時必須已存在，不存在就回 `user_invalid`，不延到 wake 才擋（wake 時仍重新解析一次）。額度不是允許 impersonate 呼叫者的欄位。〔使用者方向 2026-09-30，第十九批〕任務表裡個別任務帶的 `user` 也要落在這個 node 的額度內，由標準配備的切換使用者核（[B-620](tick.md)）。

**重送與更新**：有權者重送相同有效登記回成功，不清 paused／pending、不再啟動。既有項內容不同時，由原 owner 或祖先 owner 更新：`interval_ms` 從下一次到期開始算；擴大額度或佈建權只能由上層在自身授權內下授，即時生效；縮小即時生效，已往下授出去的子孫若因此超出，下一格授權檢查不過就照 B-607 停格並寫事項，不自動收回、不回 `busy`。更新不重跑已開始的 attempt。〔第十八批 Q8〕

**換父**〔使用者方向 2026-09-30，第十九批改寫第十八批審稿裁定 6 與 Q10〕：換上層有兩條路。

1. **搬資料夾**：把 node 的資料夾搬進別的 tick 的資料夾，新位置最近的那個自動成為上層。路徑就是 id，所以等於舊 id 解除、新 id 重登：先由舊上層照下面的解除收掉舊 id，搬完再由新上層以新 id 登記。引用舊路徑的回址會失效，風險自負（[T-03](terms.md)）。
2. **改登記**：用同一個 `node.register` 讓有效上層變成別人——帶不同的 `parent_id`，或拿掉原本的 `parent_id` 回到資料夾推得的上層。已登記子樹跟著搬。

兩條都有的條件與效果：

- 條件：被搬的 node 與整棵已登記子樹都已暫停且程序全空，否則 `busy`〔沿第十八批 Q10〕；新上層不能在被搬的子樹裡（成環回 `registration_conflict`）；頂層不能換父。
- 授權：新舊兩個上層都同意（同上面的覆蓋）；額度與佈建權要被新上層包含。
- 效果（改登記那條）：收掉舊框、在新上層框下重建（上限要由新上層的 kernel 重寫，用量歸零）；子樹跟著搬，暫停狀態保留，由呼叫者 resume；被搬的每筆登記換新 `registration_id`，格次序號從頭算。
- 舊上層 kernel 要先把它從成員清單拿掉，否則下一格同步又會以舊上層登記回去（[P-802](protocol/kernel-tasks.md)）。

**解除**：`node.unregister` 立即阻止目標及已登記子樹的新格，對整個範圍做 B-604 的收尾；確認全空後由下往上刪框（框已交給別的帳號時由 helper 刪；逃生口還在就留框並寫事項，見 B-605），刪登記、丟掉它在通道上的暫存訊息（B-614）、回成功。無法清空回 `cleanup_failed`，保留阻擋狀態。自己在 tick 內同步等自身解除會被收尾，呼叫者不得依賴收到成功才能退出；通常由上層發起。持久停用仍由上層 kernel 改自己的成員設定（B-604）。掛載行程不用解除，用 `node.kill`（B-613）；對掛載行程送 `node.unregister` 回 `kind_mismatch`。

**once**：〔使用者方向 2026-09-30，第十九批〕once 屬標準配備，不再是登記的一種；daemon 那一側改成通道上的掛行程與砍掉，見 [B-613](#b-613掛行程與砍掉)。

**驗收：**偽造 payload 帳號不能登記別人的資料夾；子額度寫成上層沒有的前綴或更大的範圍被拒；前綴規則比不中 UID < 1000 的帳號；不帶 `parent_id` 登記時，上層是最近一個已登記的包含資料夾，那個資料夾沒登記時回 `not_registered`；帶 `parent_id` 覆蓋時只有一方上層同意被拒，覆蓋後框在新上層下、資料夾上層的檔案權限不變；換父時子樹沒停或新上層在子樹裡被拒，搬好後框在新上層下、`registration_id` 換新；搬資料夾後舊 id 解除、新 id 由新位置的上層登記；解除在跑的 node 時寬限後被殺、框被刪；縮小中間 node 的額度後，超出的子孫下一格停格並有事項。

## B-607：叫醒、暫停、故障停格與格次序號

〔使用者方向 2026-09-29；第十八批改寫，行為從 P-104～106 搬上〕method 形狀見 [P-105～106](protocol/daemon/registration.md)。

**定期與叫醒**：定期 node 從登記完成起經過 `interval_ms` 才到期；每次完整收尾後重新計時，不補跑漏掉的格數。`node.wake` 要求現在跑一格，把本次到期提前；正在跑時合併成一個 pending，paused 時只記 pending，停機中（`stopping`）拒絕，排空中照收（B-604）。wake 成功不是已開跑或工作完成證據。〔使用者方向 2026-09-30，第十九批〕tick 可以經通道叫醒別的 tick（B-612）；急件訊息由 daemon 代為叫醒（B-614）。對掛載行程送 wake、pause、resume 回 `kind_mismatch`。

**暫停與恢復**〔第十批〕：`node.pause` 只停**該 node** 的新格，不殺本格、不遞迴暫停子樹，回成功代表閘門已關；手改還須 `node.show` 看 `running:false`（包括後代清理期間），再持 node 鎖、修改及 commit。`node.resume` 只開該 node 的閘門，呼叫者先完成 [A-102](agent/configuration.md) 的驗證與 commit；daemon 不讀 git、不替手改 commit，也不替 unknown 工作重試。pending 或到期才開格。pause／resume 同狀態重送無害，是關／開閘門，不等於 wake；保存依 B-603 的批次存檔。

**故障停格**：登記的 node 把可信子程式退出 `3`／`125` 保留為停格碼；runner 前置失敗、身分不在額度內、缺可信回報或後代清不空也停格。daemon 先設 `paused:true` 再處理 pending／到期，寫該 node 的 `.aos/attention/`（格式見 [P-601](protocol/ops.md)，處理見 [S-405](scheduling/operations.md)），不解析 stderr、不靠 tick 再發 IPC。這是所有登記目標的調度約定；普通程式回這兩碼也暫停，但不因此推論它沒執行。tick 自己什麼時候回 3 或 125 見 [tick](tick.md)。〔使用者方向 2026-09-30，第十九批〕回 `75`（鎖被占，例如有人手正在直接跑同一個資料夾，[B-602](tick.md)）當普通結束：不停格、不寫事項，pending 照留，收尾後照常再開下一格。手動 pause 與自動停格使用同一閘門；resume 前修復者須清後代、持鎖核對基線並移除擋板。事項寫不出就 stdout 警告，不阻止停格。〔使用者方向 2026-09-29，從 P-601 搬上〕daemon 產生的事項（自身的、要寫進 node `.aos/attention/` 的）先暫放記憶體，每 1000 ms 批次寫出，寫完就從記憶體清掉；重開後不讀回記憶體。事項檔的位置與格式見 [P-601](protocol/ops.md)。

**最近一格與格次序號**〔使用者方向 2026-09-30，第十八批〕：daemon 為每筆登記只保存最近一格（欄位見 [P-106](protocol/daemon/registration.md)），新格派出時取代前格，不是完整歷史。每開一格，這筆登記的 `tick_seq` 加 1，從 1 起算；配上 B-606 的 `registration_id`，就是「第幾格」的依據，不用牆鐘排序或推算逾時。

- 父層（或人手）判斷「wake 之後新的一格已經做完」：記下 wake 回應的 `registration_id` 與 `tick_seq`，之後 `node.show` 看到 `registration_id` 相同、`last_tick.tick_seq` 較大且 `outcome` 不是 `running`，就算做完；`registration_id` 已改變，表示舊登記已結束（解除、換父或 daemon 重啟），要重新核對，不再等舊的那格。
- 人手「經 daemon 跑一格」就用 wake 加上面的等法，不另開 method。〔使用者方向 2026-09-30，第十九批〕人手或 cron 也可以直接跑 `aos-tick`，風險自負，那一格沒有通道、daemon 也不知道（[B-627](tick.md)）。

**最近一格怎麼判**〔建議預設，未拍板；第十九批從 P-106 搬上〕：`started_at_ms` 是 daemon 接受開格、進入啟動流程的時間，不是程式已開始的證據。`outcome` 為 `completed` 只表示可信回報 started:true 且收尾完成，可以是非零、絕不等於業務成功；`launch_failed` 是可信回報 started:false；`unknown` 是沒有可信回報或 `FinalizeFailed`，不從 runner 的 wait 碼猜業務退出碼。已放行後程式自己回 125 是 `completed`，身分拒絕的 125 是 `launch_failed`（仍可能已有開檔副作用）。後代清不空時仍算 `running:true`、`outcome:running`，另以 `stopping:true` 與事項暴露故障，不能先記成已完。時間可能受牆鐘校正影響，排格數用 `tick_seq`。

**查詢**〔建議預設，未拍板；第十九批從 P-106 搬上〕：`node.show` 不開 tick；`cgroup` 回實際讀到的配置，不是上次請求的快取，應存在卻讀不到回 `resource_observation_failed`，不能回 null 冒充沒配置。`node.ls` 先按呼叫者權限篩，再分頁；只列有權看的，不洩漏總數或無權項。不同頁不是同一瞬間的快照：每次接續用剛收到、嚴格前進的游標，`boot_id` 變了就從頭列，要核對單項用 `node.show`；持續變動時不追補游標之前新插入的項，免得無限追列。一頁裝不下就縮頁，單項就超過封包上限回 `response_too_large`。畫面要把「已結束的掛載行程」「未啟動」「還在跑」「結果不明」分開。

**驗收：**定期 node 不補跑漏掉的格；運行中收到多次 wake 只多跑一格；pause 不遞迴；子程式回 3 或 125 後自動停格、有事項；wake 後等到 `tick_seq` 前進且不是 running 才算新格做完，daemon 重啟後 `registration_id` 改變。不同 UID 只能列自己的授權子樹；未跑顯示 `last_tick:null`；分頁跨重啟能靠 `boot_id` 發現。

## B-608：熱重載與「即時改／要重開」

〔使用者方向 2026-09-30，第十八批〕改設定、改樹不必重開 daemon：除了重大或危險的操作要重開，其餘都盡量即時改。

**熱重載**：daemon 只在收到 **SIGHUP** 時重讀啟動時的同一份設定檔；能送訊號的只有同帳號或 root，不開 IPC、沒有 CLI 子命令（人手用 `kill -HUP`）。流程：讀新設定並驗證整份 → 跟目前設定比對差異 → 依下表套用能即時改的，其餘不套用。

- 新設定讀不進來或不合 schema：整份不套用，舊設定繼續用，stderr 說明並寫 daemon 事項（`config_invalid`）。
- 有「要重開」的欄位改了：能即時改的照套，這些欄位不套用，stdout 列出並寫 daemon 事項（`restart_required`），直到重開或改回為止。
- 每次重載在 stdout 印一行，列出已套用與要重開的欄位；不認得的欄位照 [C-07](contracts.md) 忽略並印出名字。
- 停機或排空中收到 SIGHUP 不重載，印一行警告。

〔使用者方向 2026-09-30，第十八批〕**helper 的界線**：helper 在 fork 前固定一份設定副本，用它核對頂層額度（[P-102](protocol/daemon/startup-and-ipc.md)）；重載不改 helper 那份。所以牽涉 helper 的欄位——**通用 user 以外帳號的身分額度、佈建權**——改了仍要重開。要少重開，就在啟動設定用前綴或範圍一次授出夠大的範圍（B-606）。

### 設定項

| 設定 | 改了怎麼辦 | 說明 |
|---|---|---|
| `version` | 重載時照樣檢查 | 版本不同整份不收（`config_invalid`） |
| `common_user` | **要重開** | daemon 已永久變成這個帳號，換帳號等於換一個 daemon |
| `socket_path` | **要重開** | 連線全斷、各 kernel 記的位置與已開 tick 的通道變數都會失效；防雙開的鎖在 socket 目錄 |
| `state_dir` | **要重開** | 恢復資料在舊位置，也是排他鎖的對象（B-611） |
| `cgroup_root` | **要重開** | 程序要跨子樹搬家，需要 root；也是排他鎖的對象 |
| `create_cgroup` | 只在啟動時有用 | 重載時改了不套用，也不算要重開 |
| `pause_save_interval_ms` | 即時改 | 下一次存檔用新值 |
| `shutdown_grace_ms` | 即時改 | 只影響之後才開始的收尾 |
| `stop_mode`、`drain_timeout_ms` | 即時改 | 下一次停機用新值 |
| `kill_escape_cgroups` | 即時改 | 下一次重啟清空或解除用新值 |
| `mount_diag_max`、`mount_diag_ttl_ms` | 即時改 | 下一輪淘汰用新值（B-610） |
| `disable` | 即時改 | 只影響之後的 quota 動作，已設好的歸屬不收回；重新打開時再偵測一次 |
| roots：加一棵 | 即時改；額度含通用 user 以外帳號或帶 `provision` 的**要重開** | 等於一次沒有上層的登記加一次 wake |
| roots：刪一棵 | 即時改 | 走 B-606 的解除；清不空就一直擋著並寫事項 |
| roots：`node_id` 改名 | 當成刪一棵加一棵 | 舊的那棵要收尾 |
| roots：`interval_ms` | 即時改 | 從下一次到期開始算 |
| roots：`identity_grant` | 只動通用 user 的即時改；動到其他帳號（含前綴、範圍）的**要重開** | 重開後依 B-603 重核讀回的登記；超出的子孫照 B-607 停格 |
| roots：`provision` | **要重開** | helper 核對的是啟動時那份 |
| 有沒有 helper（用不用 sudo 開） | **要重開** | 拉起 helper 需要 root |

寫死、不開放成設定的：IPC 封包上限 256 KiB、`node.ls` 每頁 64 筆、socket 權限預設值、最低版本、通道的暫存上限與單件上限（B-614）；版本檢查只在啟動時做。

### 操作

| 操作 | 即時／要重開 | 說明 |
|---|---|---|
| 啟動 `aos daemon` | — | 啟動偵測、取鎖、準備 cgroup、清空舊程序都只在這時做 |
| 立即停、排空停 | — | B-604 |
| 熱重載（SIGHUP） | — | 本條 |
| `daemon.info` | 即時 | 查本次啟動 ID |
| `node.register`：新登記、重送、更新、覆蓋上層、換父 | 即時 | B-606；換父只要求被搬的那棵先停 |
| `node.unregister` | 即時 | B-606 |
| `node.wake`、`node.pause`、`node.resume` | 即時 | B-607 |
| `node.mount`、`node.kill` | 即時 | B-613 |
| `node.send`、`node.take` | 即時 | B-614 |
| `node.show`、`node.ls` | 即時 | 最近一格含格次序號 |
| `mount.clear` | 即時 | B-610 |
| `node.provision`（含改 cgroup 上限、helper 新動作） | 即時 | B-609 |
| `daemon.attention.*` | 即時 | [P-601](protocol/ops.md) |
| helper 被 kill 之後恢復特權操作 | **要重開** | 需要 root 才拉得起來（[B-303](base/identity-resources.md)） |

要重開的共同原因：一改就等於換了 daemon 的身分、恢復資料、整棵資源樹，或 helper 的授權依據，而且大多要 root 才做得到。其餘最多只要求被動到的那一棵先停下，不影響別的樹。

**驗收：**SIGHUP 後改 `interval_ms`、加一棵只用通用 user 的 root 立刻生效；改 `socket_path` 或 root 的其他帳號額度時其餘照套、這些欄位回報要重開且不生效；壞設定整份不套用、舊設定照跑；非同帳號送不了 SIGHUP。

## B-609：佈建固定動作與 helper 動作

〔使用者方向 2026-09-29；第十八批加動作，行為從 P-107 搬上〕helper 的角色與界線以 [B-303](base/identity-resources.md) 為正本；`node.provision` 的參數見 [P-107](protocol/daemon/provision-and-runner.md)，helper 私有通道見 [P-108](protocol/daemon/provision-and-runner.md)。〔使用者方向 2026-09-30，第十九批〕helper 與佈建動作屬標準配備的切換使用者；`cgroup_*` 動作屬 cgroup 框，只在有 cgroup 時適用（B-605）。

**通則**：每次只做一件固定動作，不提供 shell、argv、任意 syscall 或任意 mount options。授權、允許的路徑與群組都取**該 node 的登記**（`provision` 的 `actions`、`paths`、`groups`），執行端不信封包自報。路徑按元件判定、不用字串前綴；helper 固定目錄 handle、拒絕 symlink 穿越及替換競態，逐步核對實體路徑。OS 現況已符合就核對後成功，不同回 `conflict`、不覆蓋。做完並驗證才回成功，不能把已送 helper 當完成；沒有跨步回滾，斷線或中途失敗須先核對 OS 事實，不能盲重送或自動「撤回」。首次建 node 前，可先用上層 node 的佈建權在授權路徑建立必要權限與帳號，再登記成員；建帳號不擴大額度。

**動作**：

| 動作 | 做什麼 | 要 helper |
|---|---|---|
| `account_create` | 建一個非 root 帳號及同名主群組；名稱要落在額度的確切名稱或前綴裡、尚未存在（範圍規則不能授權建帳號）。無登入 shell、不建 home、不收密碼；建好後綁住 UID（B-606）。已存在且符合綁定就核對後成功 | 要 |
| `chown` | 單一路徑改為額度內既存帳號與其主 GID；不遞迴、不收任意 GID、不跟隨 symlink | 要 |
| `cgroup_create` | 在可信上層框下建本 node 的 `n-<h>` 與 `tick`，並照 B-605 委派；路徑由登記推導，呼叫者不能給 cgroup 路徑。node 還沒建框時 daemon 開格前自己建（不寫上限） | 上層框或委派對象不是 daemon 帳號時要 |
| `cgroup_limits` | 寫 `n-<h>` 的 CPU、記憶體、程序數上限，作用於整個分支含後代；只寫這些 controller，不設就不新增該項限制 | 不要 |
| `quota` | 只配置該路徑的 project **計量歸屬**，不設磁碟硬上限或 soft limit；不搶走其他 node 的歸屬 | 要 |
| `cgroup_delegate`〔第十八批〕 | 把本 node 的 `n-<h>` 與三個委派檔重新交給這個 node 目前的執行帳號（inst 的 user 換了時用）；上限檔不動 | 帳號不是 daemon 自己時要 |
| `group_create`〔第十八批〕 | 建一個系統群組；名稱要是確切名稱，且落在登記 `groups` 授權的名稱或前綴裡 | 要 |
| `group_add_member`〔第十八批〕 | 把額度內的一個帳號加進授權的群組；只對之後新開的程序生效 | 要 |
| `chgrp`〔第十八批〕 | 把單一路徑改成授權的群組；不遞迴、不跟隨 symlink，路徑要在 `paths` 內 | 要 |

〔使用者方向 2026-09-29 晚〕原有的 `mount`（helper 掛 tmpfs）首版拿掉，暫存就在磁碟。〔第十八批 Q21〕不加遞迴改群組與 chmod／setgid。多帳號交接首版只用群組，不用 ACL。

**cgroup 上限隨時改**〔使用者方向 2026-09-30，第十八批；拿掉「整棵子樹全空才改」〕：`cgroup_limits` 調高、調低都隨時寫，不關閘門、不等全空；同一框的寫入依序做。調低時現用量超過新上限，由 Linux 自己處理（例如記憶體回收或 OOM、新 fork 失敗），aos 不擋；要記一筆的是下指令的 kernel，記在它自己的資源狀態檔（[S-203](scheduling/admission.md)）。已是相同值就核對後成功，不重寫；controller 不可用回 `unsupported`。改限制值不算中途換資源範圍（[B-302](base/identity-resources.md)）。

**daemon 自己做的與 helper 做的**：daemon 在交給它的子樹內自己建框、寫限制、讀實際值，不經 systemd；無 helper 時用通用 user 做，授權和上層限制照舊。凡是要動到不屬於 daemon 帳號的檔或框（其他帳號、群組、quota，或上層框已委派給別的帳號時建框、刪框），才經 helper；無 helper 回 `helper_unavailable`。helper 另有一個只給 daemon 用、不開放給 `node.provision` 的動作：**刪殘留框**，只刪 cgroup 子樹內、名字是 `n-*`／`mount-*`／`task-*`、已經沒有程序也沒有子框的框（B-603、B-606）。daemon 與 helper 自己留在成員限額之外。

**驗收：**每個動作超出授權路徑、群組或額度都被拒，OS 現況不符回 `conflict`；多帳號部署下能靠這些動作讓兩個 node 帳號經共享群組交接檔案；有程序在跑時也能調低記憶體上限並立即生效；沒 helper 時要 helper 的動作回 `helper_unavailable`；走備援時 `cgroup_*` 動作回 `unsupported`。

## B-610：掛載行程的診斷：留存、淘汰與清除

〔使用者方向 2026-09-29；第十八批加淘汰與清除，行為從 P-106 搬上；第十九批改名，原「once 診斷」〕

**留存**：掛載行程（B-613）結束或被砍掉、收尾完成後，daemon 在記憶體留一筆 `registered:false` 的最近結果，保留原 `owner_uid`、`parent_id` 與 `registration_id`，只供 `node.show`／`node.ls`；`node.kill`、wake、pause、resume 都回 `not_registered`。查詢時以**目前仍在的可信上層鏈**重驗，祖先權限撤銷即生效，不能靠舊祖先快照繼續讀。不寫檔、不算正在占用的登記；登記的 node 被解除不留這筆。新的一次掛行程用新的 inst 路徑，見 [work](base/work.md)。IPC 只回記憶體診斷，不讀工作結果或 git，也不是業務完成或 unknown 重跑許可。

**什麼時候消失**：

- 自動淘汰〔使用者方向 2026-09-30，第十八批〕：同時設容量與保留期。筆數超過 `mount_diag_max`（預設 1024）時先淘汰最早結束的；結束超過 `mount_diag_ttl_ms`（預設 86400000，24 小時）的也淘汰。
- 手動清除〔使用者方向 2026-09-30，第十八批〕：`mount.clear`（[P-105](protocol/daemon/registration.md)）帶一個 `node_id`，清掉這個 id 本身的紀錄，以及上層鏈上有這個 node 的所有已結束掛載行程紀錄（整棵子樹）；只清呼叫者是 owner 或祖先 owner 的那些，看不到的不動、不回報；只清已結束的，還在跑的不動。
- 其餘：上層額度撤掉該 owner 身分、掛它的 node 被解除、同 node_id 又被掛上、daemon 結束時都清掉。

**驗收：**掛載行程結束仍列得到且 `registered:false`；超過容量或保留期的紀錄消失；`mount.clear` 帶上層 node 時整棵子樹的已結束紀錄都清掉、別人的不動；重啟後舊結果消失。

## B-611：一棵資源樹只准一個 daemon

〔主編補，第十八批；審稿新必-3〕兩個 daemon 用不同 socket 卻指向同一個（或互相重疊的）`state_dir` 或 cgroup 子樹時，會互相清殺對方的工作。所以 daemon 啟動時，在任何讀回、清殺、寫狀態之前，以解析後的真實路徑對實際使用的 `state_dir` 與 cgroup 子樹根（含省略 `cgroup_root` 時自己所在那層）各取一把排他鎖，並檢查祖先與子孫：任何一個祖先或子孫已被別的 daemon 鎖住，也算重疊。取不到就拒絕啟動（回 125，stderr 說明）。鎖跟著 daemon 程序存活，程序死了鎖自動放掉。每個 `socket_path` 另有同目錄的 `daemon.lock`（[P-101](protocol/daemon/startup-and-ipc.md)）：〔建議預設，未拍板；第十九批從 P-101 搬上〕持鎖後才能清理屬於這個實例的殘留 socket，不能刪活著的 socket；無法 bind、路徑過長或權限不足就明確失敗。socket 父目錄的穿越權與 socket 的連接權由部署者先配置，不在封包裡給任意人改。〔使用者方向 2026-09-30，第十九批〕`state_dir` 那把一律要取；cgroup 子樹那把屬標準配備的 cgroup 框，只在走完整路時取，走備援時沒有這把（B-605）。

〔建議預設，未拍板〕做法：鎖直接對目錄本身取（開目錄再 `flock`，cgroup 目錄裡不能另建一般檔）；祖先往上試鎖到 cgroup 掛載點（`state_dir` 試到根目錄），子孫往下掃一遍試鎖，試完就放。兩個同時啟動、互為祖孫時，可能雙方都拒絕，重試即可。

**驗收：**兩份設定用不同 socket、同一個 `cgroup_root`（或一個是另一個的子樹，或同一個 `state_dir`）時，後啟動的拒絕啟動，先啟動的工作不受影響。

## B-612：tick–daemon 通道

〔使用者方向 2026-09-30，第十九批第 9 條〕通道是 daemon 開的 tick 跟 daemon 之間的 IPC。一些核心事務要走它：登記與解除（含覆蓋上層）、把行程掛到 daemon 上跑與砍掉、叫醒別的 tick、收件任務取暫存訊息；通道上的傳訊任務屬標準配備（[B-629](tick.md)）。method 形狀、參數與錯誤碼見 [P-117～119](protocol/daemon/channel.md)。

**誰有通道**：只有 daemon 開的程序——登記的 node 的每一格，以及每個掛載行程（B-613）。daemon 開它時在環境放兩個變數：

| 變數 | 內容 |
|---|---|
| `AOS_DAEMON_SOCKET` | daemon 的 socket 絕對路徑，就是設定的 `socket_path` |
| `AOS_TICK_TOKEN` | 本格憑證 |

- 任務會繼承這兩個變數；在「投件權就是執行權」之下這是預期行為（[T-08](terms.md)）。inst 的 `envs` 用 `clear` 時兩個都會被清掉，等於不給那一項通道。怎麼放進子程序環境以 [inst](base/inst.md) 為正本。
- cron、人手直接跑的 tick 沒有這兩個變數，只能走檔案收件。缺變數時由客戶端自己擋下、報 `no_channel`，不送到 daemon（P-117）。沒通道只算功能受限，不算沒全掛（[B-630](tick.md)）。
- 變數本身不授予權限：socket 的連接權照部署設定，授權看下面的憑證。

**憑證**〔使用者方向 2026-09-30，第十九批；做法為建議預設〕：

- **發放**：daemon 每開一格（或一個掛載行程）就產生一張，至少 128 位元的密碼學隨機值，綁定「node id、`registration_id`、`tick_seq`」（掛載行程沒有 `tick_seq`）。只放 daemon 記憶體，不寫檔、不放 argv（別的帳號看得到 argv）。
- **核對**：通道上的請求在 params 帶 `token`；daemon 以固定時間比對。對上了，還要看 socket 對面的帳號是這一格開起來時的執行帳號，或落在該 node 的身分額度內（任務可以帶自己的 `user`）；都成立才把呼叫者當成那個 tick。對不上一律回 `token_invalid`，不說是哪一項不合。
- **作廢**：該格的主程序結束（daemon 收到 runner 回報）即作廢，之後後代還拿著也沒用；登記被解除或換父（`registration_id` 改變）時作廢；daemon 重啟時全部作廢。
- **用憑證時怎麼授權**：[P-103](protocol/daemon/startup-and-ipc.md) 表中「X 的 owner 或祖先 owner」，帶憑證時讀成「憑證所屬的 tick 就是 X，或在 X 的有效上層鏈上」。不帶憑證的請求照舊看 socket 對面的帳號，給人手與 CLI 用；兩條路授權的是同一張表。

**哪些 method 收憑證**：`node.register`、`node.unregister`、`node.wake`、`node.mount`、`node.kill` 可帶可不帶；`node.send`、`node.take` 一定要帶。其餘 method 只看 socket 對面的帳號。

**格式**：通道上的請求屬 daemon IPC，照 [C-07](contracts.md) 維持嚴格，不認得的欄位拒收；封包上限同 IPC 的 256 KiB。

**驗收：**daemon 開的 tick 有兩個變數，直接跑的沒有、客戶端報 `no_channel`；上一格的憑證在下一格用回 `token_invalid`；daemon 重啟後舊憑證全部失效；別的帳號拿到憑證也用不了；inst 的 `envs` 用 `clear` 的任務拿不到變數。

## B-613：掛行程與砍掉

〔使用者方向 2026-09-30，第十九批第 3、9、10 條〕把一個行程掛到 daemon 上跑、之後再砍掉，是通道的核心事務；原本 daemon 端的 once 登記改成這一套，once 本身屬標準配備（[B-629](tick.md)）。被掛的可以是任何 inst，也可以是另一個 tick 的資料夾（daemon 就跑它一格）。

- **掛上**：`node.mount` 帶目標 inst 路徑（資料夾或單檔），daemon 立刻開一個 runner 跑它，不需要事先登記、不接受週期、不能有成員，也不要求 tasks 或 git。回應帶這次的 `registration_id`，之後用 `node.show` 查結果。
- **資源與核權歸掛的那個 tick**：帶憑證時，上層就是憑證所屬的 tick；也可以帶 `parent_id` 指定成它有效上層鏈之下的某個 node（例如 kernel 替成員掛工作，歸成員），但不能指定成自己以上或別隊的 node。不帶憑證時（人手、CLI）必須帶 `parent_id`，呼叫者要是它的 owner 或祖先 owner。不另收可自報的 cgroup 路徑：框放在上層框下（`mount-<h>`，B-605），inst 的 `user` 要落在上層的身分額度內，不合回 `user_not_granted`，不存在回 `user_invalid`。kernel 不能把成員工作掛在自己的較大額度。各參數怎麼填（含 agent 自跑工具、LLM 池代發）見 [P-402](protocol/work.md)。
- **結束**：行程跑完或被砍，daemon 收尾、自動移出登記表，留下 B-610 的診斷。〔使用者方向 2026-09-30，第十九批〕掛它的 tick 用 `node.show` 看 `last_tick` 拿結果：`outcome`、`exit_code`、`signal` 就是這個行程的（例如任務帶別的 `user` 時，tick 用 `node.mount` 開它，再用 `node.show` 等結束碼，[B-620](tick.md)）；這筆診斷會被淘汰（B-610），要留存的結果由掛的一方自己記。同一個 id 在跑時再掛回 `registration_conflict`；掛載行程沒有第二次、也沒有 pending。
- **砍掉**：`node.kill` 對它做 B-604 的收尾。核權看掛它的那個 tick 的**路徑**（上層與上層鏈），不看當時那張憑證，所以上一格掛的、這一格也能砍。已經結束的回 `not_registered`；對登記的 node 送 `node.kill` 回 `kind_mismatch`。取消在跑的工作就用它（[B-203](base/execution.md)）。
- **失敗證據**：前置失敗也算用掉這次掛行程；沒確認後代清空就保留阻擋。`not_registered`、重啟或沒收到回應都不是重跑許可，判讀見 [S-401](scheduling/operations.md)。
- **單檔的未啟動旁檔**〔使用者方向 2026-09-29，第十一批與後續旁檔改名裁定；第十九批從 P-110 搬上〕：目標是單檔、而 daemon／helper 拒絕啟動 runner 或可信 runner 回報 `started:false` 時，daemon 在這個 inst 旁發布 `<inst 檔名>.err`（例如 `job.json.err`，格式見 [P-110](protocol/daemon/provision-and-runner.md)）。私有的 PascalCase 錯誤要映成 `user_not_granted`、`user_mismatch`、`source_changed` 或 `start_failed` 等小寫代碼，不直接抄 runner 的錯誤。每次掛行程用新的 inst 路徑，不覆蓋既有旁檔；以已授權目標的目錄 handle 發布，不能藉此任意寫檔。旁檔衝突或寫不出就 stdout 印一行警告，不另存 daemon 事項，掛的一方沒證據仍保留 unknown。目標是資料夾時，啟動失敗寫它自己的 `.aos/attention/`，不寫旁檔。runner 已放行後不寫這份旁檔；之後的 125、126／127 或結果遺失依 [work](base/work.md) 處理。
- 排空停機時拒收新的掛行程，等已掛的跑完（B-604）；掛載行程不存檔，重啟後不接回（B-603）。
- 掛載行程也有通道（B-612），憑證綁它自己；它沒有收件匣，`node.take` 回 `kind_mismatch`。

**驗收：**tick 在第一格掛一個常駐行程、第四格用 `node.kill` 砍掉，砍得掉而且收尾完成；別隊的 tick 砍不掉；帶 `parent_id` 指到自己上層鏈之外被拒；人手不帶憑證又沒帶 `parent_id` 被拒；單檔目標未啟動時有 `.err`，已放行後沒有。

## B-614：暫存訊息與急件

〔使用者方向 2026-09-30，第十九批第 9 條與疑點裁定 6、7〕同一個 daemon 底下的 tick 可以經 daemon 互傳訊息。

- **格式**：訊息跟檔案收件相同，是一份放進 `requests/` 的請求物件（[P-301](protocol/messages.md)）；daemon 只驗外形，不解析正文。回應仍照回址走檔案投件。照 [C-07](contracts.md)：通道請求的外層（`node.send` 的 params）照 daemon IPC 嚴格；夾帶的 `message` 照檔案 RPC 放寬，不認得的欄位忽略。
- **送**：`node.send` 帶收件 tick 的 id、訊息與是否急件。收件 tick 要在這個 daemon 登記，否則回 `not_registered`；掛載行程沒有收件匣（`kind_mismatch`）。
- **誰能送**：看寄件 tick 的執行帳號對收件 tick 的 `requests/` 有沒有寫權——能不能在那裡建檔（`requests/` 的寫與穿越權，以及上層各段的穿越權），跟檔案投件同一個判準；沒有就回 `forbidden`。首版不用 ACL，所以 daemon 以那個帳號的 UID 與群組，對權限位計算即可。「投件權就是執行權」同樣適用（[T-08](terms.md)）。
- **存**：放 daemon 記憶體，按收件 tick 分開、先進先出。**不保證送達**：daemon 當掉、重啟、立即停機，或收件 tick 被解除，暫存的都丟掉。〔建議預設〕每個收件 tick 最多 256 件、合計 16 MiB，滿了回 `mailbox_full`；單件訊息序列化後最多 196608 bytes（192 KiB），超過回 `message_too_large`，這樣一件一定裝得進一個 `node.take` 回應。
- **取**：收件 tick 的收件任務自己上通道用 `node.take` 取；取走的 daemon 同時刪掉，之後怎麼落地、去重歸收件任務（[B-623](tick.md)）。一次回應裝不下就分幾次取，回應會說還有沒有。
- **急件**：送到時 daemon 照 `node.wake` 叫醒收件 tick（合併、paused 只記 pending、停機中不叫，B-607）；一般件等它自己的下一格。〔暫定，改寫計畫疑-9 使用者未答〕急件直接叫醒，不問上層，不受上層 kernel 的節流。
- 排空停機時通道照常收送（B-604）。

**驗收：**寄件帳號對收件 `requests/` 沒寫權被拒；一般件不叫醒、下一格取得到；急件送到後收件 tick 被叫醒；取過的再取不到；daemon 重啟後暫存的都不見；超過上限回 `mailbox_full`、`message_too_large`。

## 附錄：開機自動啟動的 systemd service 範例

〔使用者方向 2026-09-29 晚〕要開機自動啟動，就把 daemon 寫成一個 systemd service；這只是範例，不算執行期依賴。不用 sudo 的使用者層做法見 B-605 的第一推薦。

```ini
# /etc/systemd/system/aos-daemon.service（範例）
[Unit]
Description=aos daemon
After=local-fs.target

[Service]
# 以 root 開＝sudo 模式（有 helper）。服務啟動沒有 SUDO_UID，所以設定檔一定要寫 common_user（B-303）
# 要單帳號模式（沒 helper）就加 User=<帳號>，common_user 可省
ExecStart=/usr/local/bin/aos daemon --config /etc/aos/daemon.json
# 熱重載（B-608）
ExecReload=/bin/kill -HUP $MAINPID
# 讓 systemd 把 daemon 所在的 cgroup 劃給它，當成準備好的子樹（B-605）
Delegate=yes
# 停服務時先只對 daemon 送 SIGTERM，讓它自己收尾在途程序（B-604）
KillMode=mixed
# 設定用 stop_mode:"drain" 時，這個值要大於 drain_timeout_ms 加 shutdown_grace_ms，否則 systemd 會先強殺
TimeoutStopSec=15min

[Install]
WantedBy=multi-user.target
```
