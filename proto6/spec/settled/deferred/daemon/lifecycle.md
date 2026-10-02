# daemon 核心：重啟、收尾與停機

← [舊 daemon 目錄（暫緩區）](README.md)｜[整理區](../../README.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊 daemon 的重啟清空、收尾與停機、排他鎖。現行 daemon 收到 Ctrl-C／SIGTERM 直接退出（[B-640](../../daemon/core.md)）。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## B-603：重啟先清空，再讓樹長回來

> **部分已被 [B-643](../../daemon/state.md) 取代，其餘暫緩**（2026-10-01；第十一批改）：「存檔與讀回」「pause 批次存檔」裡的暫停（加上已停）跨重開，改由記住狀態模組做——每次變動當場寫整份、重開讀回，沒掛時暫停仍只在記憶體（[B-641](../../daemon/control.md)）。重啟清空、`state.json` 的登記與 wake 讀回、批次存檔、逐層重建暫緩。條號保留、不重用。

〔使用者方向 2026-09-30 晚〕巢狀時，外層重開收掉內層 daemon 的風險由使用者承擔，aos 不另接管或補救；沒 cgroup 時仍照本條既有的清不掉舊程序界線。

依據：[09-30 晚裁定](../../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)；開關細節見 [B-615](components.md)。

**原則：重啟不接續孤兒工作，在途程序全殺，確認清空才開新格。** 重啟清空是 daemon 自己的職責。

| 情況 | 有 cgroup | 沒有 cgroup |
|---|---|---|
| 整機或 WSL VM 重開 | 舊程序本來就全沒了，照常開格 | 同左 |
| 只有 daemon 重開（例如被 SIGKILL） | 先清空舊框才開格（下面「清空舊程序」） | 舊程序可能還在，daemon 清不掉（已接受） |

不能拿一個可能重用的 PID 直接 kill。

### 啟動順序

1. 啟動自檢（B-605）。
2. 取得排他鎖（[B-611](lifecycle.md#b-611一棵資源樹只准一個-daemon)）；取不到就拒絕啟動。在這之前不讀回、不清殺、不寫狀態。
3. 讀回 `state.json`。
4. 清空舊程序（有 cgroup 才有這一步，見下面）。
5. 寫 PID 提示檔、開 socket、開始開格。

**PID 提示檔**〔astra 審整理區必-8 從 P-102 搬上〕：`state_dir/daemon.pid` 與 `state_dir/helper.pid`（沒 helper 寫 `none`），啟動時寫，正常退出時刪；helper 的 PID 另印在 stdout。啟動時看到舊檔只當提示，不拿來殺程序。格式見 [P-102](../protocol/daemon/startup-and-ipc.md)。

### 清空舊程序

有 cgroup 時清空舊程序，照 [B-603 的 cgroup 部分](cgroup.md#重啟清框b-603)。

**沒有 cgroup 時**〔第二十批：重啟清不掉舊程序，接受〕：舊 daemon 的 runner 與它們名下的程序（B-601）跨不過 daemon 重啟，新 daemon 找不回來，**daemon 重開時的清空不成立**。

- 後果：舊的一格還沒結束、還握著鎖 fd 時，同一資料夾的新格回 75（[B-602](../../tick.md)），等它自己結束。
- 後果：舊的掛載行程可能跟掛它的 tick 重新掛上的那個同時在跑，掛的一方照 unknown 規則核對（[S-401](../../../scheduling/operations.md)）。

兩種都一樣：開 runner 時設 `PR_SET_PDEATHSIG` 只當加分（它只作用於直接子程序），不是必要；不要求跨重啟保存程序表。

### 存檔與讀回

- daemon 設定檔只列頂層 node 及其啟動設定、身分額度。
- **正常退出**把登記表、pause、未處理 wake 存進 `state_dir/state.json`（格式見 [P-116](../protocol/daemon/shutdown.md)）。這份檔不保存或接續執行中的程序；無檔也能從頂層啟動。
- **讀回後**依目前 roots、inst 與上層鏈重新核對每筆登記的身分與授權，不合的丟掉；沒有覆蓋的登記重新照資料夾推上層（B-606）；缺檔或壞檔就從 roots 重建，壞檔留診斷。
- 讀回後先把 `clean_shutdown` 原子改成 false，才接受工作。寫檔一律先寫完整暫檔再原子替換（[P-003](../../../protocol/README.md)）。
- 讀回的登記一律算新登記：換新的登記識別，格次序號從頭算（B-606、B-607）。
- **不存檔、不接回的**：掛載行程（B-613；重啟時被收尾的，由掛它的 tick 照工作結果與 unknown 規則核對）、通道上暫存的訊息（B-614）。其他未處理 wake 照常接回。

### pause 批次存檔

- pause 有變動才批次寫 `state.json`，最多每 `pause_save_interval_ms`（預設 1000）原子寫一次，標 `clean_shutdown:false`；正常退出存完整最新狀態。
- 意外退出最多丟最後一個間隔內的 pause 變動；過期登記與未保存 wake 由頂層補查恢復。
- 寫檔失敗寫 daemon 自身事項並報 stderr。

### 逐層重建

- **daemon 開啟就自動開始 tick 頂層 node**；已恢復 pause 的頂層保留這次 wake，等 resume。
- **boot id**〔astra 審整理區必-8 從 P-115 搬上〕：每次啟動新生一個，整次存續不變；只放記憶體，重開不得沿用，socket 路徑相同也不行。`daemon.info`、`node.show`、`node.ls` 回的都是它（格式見 [P-115](../protocol/daemon/registration.md)）。node 路徑別名、重用或跨機重名的風險由使用者承擔。
- 〔使用例：kernel 那側〕頂層發現 boot id 改變後重新登記直接成員並叫醒子 kernel，逐層重建。平常只在 boot id 或成員清單變動時補登記，不每格重送（B-606）。壞成員留待辦、跳過，不擋其他子樹。
- 有 cgroup 時的空框清理見 [B-603 的 cgroup 部分](cgroup.md#重建後刪空框b-603)。
- 清空後由 node 按 [tick](../../tick.md) 恢復檔案，執行器／所屬 kernel 核對工作結果；daemon 不代讀結果或判業務終局。

依據：使用者方向 2026-09-29（全殺、存檔與讀回、pause 批次存檔、逐層重建）；第十八批（空框清理）；第十九批（掛載行程與暫存訊息不存檔）；第二十批（重啟清空是 daemon 職責；沒有 cgroup 時清不掉，接受）；納入 cgroup 與 git 疑-8（記上次的子樹根）。

**驗收：**正常重開讀回 pause／wake，無快照時頂層仍自動跑；daemon 重開後 `boot_id` 改變；正常退出後 PID 提示檔被刪，啟動時看到舊檔不殺那個 PID；pause 批存與逐層補登記見 [V-03](../../../conformance.md)。沒有 cgroup 時 daemon 被 SIGKILL 後重開，舊格還握著鎖時同資料夾的新格回 75、不重疊。有 cgroup 時 daemon 被 SIGKILL 後以新的 scope 重開，舊 scope 裡仍有程序的受管框先收到 SIGTERM、寬限後被清空，才開新格；重建途中不先刪空框，重建完仍沒人登記的才刪。

## B-604：收尾、停機、停用與退役

> **暫緩**（2026-10-01）：收尾寬限、排空停機、停用與退役；最核心 daemon 第一版不做（使用者 2026-10-01）。第一版停機見 [B-640](../../daemon/core.md)：Ctrl-C／SIGTERM 直接退出、回 0，不殺也不等正在跑的 `aos-exec`。條號保留、不重用。

收尾、排空與立即停機是 daemon 自己的職責（第二十批）。

### 收尾

**收尾是 daemon 清掉一個範圍的固定做法**。runner 那一套一定做（B-601）；有 cgroup 時最後用框兜底：

1. 停止這個範圍開新格；
2. 對範圍內每個 runner 送 SIGTERM（runner 轉給它名下的程序，B-601）；
3. 等 `shutdown_grace_ms`（[P-101](../protocol/daemon/startup-and-ipc.md)，預設 2000）；
4. 對還沒結束的 runner 再送一次 SIGTERM，runner 就清空自己名下、回報、結束（B-601）；
5. wait 回收每個 runner。runner 在第二次 SIGTERM 之後還不結束，daemon 才對它送 SIGKILL，這一次開格記結果不明、算清不空；
6. 有 cgroup 時追加 [B-604 的框收尾](cgroup.md#收尾最後清框b-604)。

- **誰用這一套**：重啟清空（有 cgroup 時，B-603）、停機、解除登記、砍掉掛載行程、helper 停程序；取消在跑的工作也用這套（[B-203](../../../base/execution.md)）。
- **範圍**：這個 node（或掛載行程）目前那一格的 runner、它掛上而還在跑的掛載行程，以及已登記子 node 的同樣範圍。有 cgroup 時換成框：`tick`、`task-*`、`mount-*` 與已登記子 node 的 `n-*`；node 自己開的其他子框是逃生口，照 `kill_escape_cgroups`（B-605）。
- 已經在收尾的照開始時的寬限值走完，之後改設定不影響它。
- 確認不了全空就回報失敗、保留阻擋與占用，不能先宣稱完成或假裝名額已釋放。
- **不是這裡的收尾**：runner 處理 inst 自己的逾時（照 inst 的 2 秒）屬 [inst](../../../base/inst.md)；一格正常結束後的殘留見 B-601 的格後收尾；`aos-cg` 對自己 `task-*` 框直接 `cgroup.kill` 屬 [B-634](../cg.md)。
- **清不到的**：沒有 cgroup 時見 B-601（經外部服務開的、自設 subreaper 的、換成別的帳號的）；有 cgroup 時只剩經外部服務開的。它們若還握著 tick 的鎖 fd，同資料夾的下一格回 75（[B-602](../../tick.md)）。
- 用詞：「排空」只指下面的排空停機；解除登記不叫排空。

依據：第十八批（收尾、用詞；以 cgroup 收尾）；第十九批（程序群組管不到的）；astra 審整理區必-1（經 runner 收尾），使用者確認定案；納入 cgroup 與 git 改寫計畫（有 cgroup 時最後以 `cgroup.kill` 兜底）。

### 停機：立即與排空

〔使用者方向 2026-09-30 晚〕排空停機留核心，可單獨關掉。〔建議預設，未拍板〕`enable_drain:false` 時，即使 `stop_mode:"drain"`，SIGINT／SIGTERM 也走下面的立即停；`drain_timeout_ms` 不使用。收尾與正常存檔仍照做。

依據：[09-30 晚裁定](../../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)；開關細節見 [B-615](components.md)。

daemon 收到 SIGINT（前景 Ctrl-C）或 SIGTERM 時停機。排空功能開著時，走哪一種由設定 `stop_mode` 決定（`immediate`／`drain`，預設 `immediate`），不開停機用的 IPC。訊號、結束碼與設定欄位見 [P-114](../protocol/daemon/shutdown.md)。

**立即停**：

1. 停止新登記、叫醒、掛行程與開格；
2. 對所有在途程序做一次收尾；通道上暫存的訊息直接丟掉（B-614）；
3. 清空後存 B-603 的完整 `state.json`、讓 helper 退出、清 socket 與 PID 檔，然後回 0。

清不空或存檔失敗回 125。

**排空停**（第十八批）：

1. 拒收新的掛行程與新成員登記（回 `stopping`）。已登記的 node 照常開格，讓 kernel 能繼續收結果；通道照常收送。被拒的掛行程不會啟動；沒收到回應時照 [S-401](../../../scheduling/operations.md) 判讀。
2. 等已掛的行程全部跑完；然後停止開新格，等在途 tick 自然結束。
3. 全部結束就照立即停的後半存檔、退出。
4. 從收到訊號起超過 `drain_timeout_ms`（預設 600000，10 分鐘），或排空途中再按一次 Ctrl-C（SIGINT），就改成立即停（第十八批 Q16）；排空途中再收到 SIGTERM 也同樣改立即停〔建議預設，工程補充〕。被收尾的掛載行程由掛它的 tick 照 unknown 規則核對。

**共通**：停機或排空中不接受熱重載（B-608）。突然被殺則下次依 B-603 恢復，不因 socket 不見就推論已全空。未清空要回報失敗，不能先宣稱停止完成。

依據：使用者方向 2026-09-29 晚；第十八批加排空。

### 停用與退役

- **停用**：授權者停用成員時，由所屬 kernel 停止再喚醒／再登記該成員，並請 daemon 解除登記（B-606 的解除就是收尾後刪登記）。停用 kernel 時同樣處理其已登記子樹，不連帶停掉其他隊。只清 daemon 記憶體的一筆資料不能代表持久停用，否則下次上層 kernel tick 會把它登記回來。kernel 何時對成員發解除見 [S-202](../../../scheduling/admission.md)。
- **退役**：由授權者明示，所屬 kernel 先核對程序已清空、未結工作與資料歸屬；daemon 不另設持久退役表。UID／GID 及 home 都不自動回收或刪除，資料與 Linux 所有權的處置另由有權限者決定；解除登記不會消除舊檔案的 ownership。

依據：使用者方向 2026-09-29。

**驗收：**停止一個子 kernel 不妨礙別隊運行；受管後代仍在時不回報收尾完成；任務忽略 SIGTERM 時，寬限到了仍被清掉（有 cgroup 時最後是 `cgroup.kill`）；解除登記不刪 home、不把舊 UID 自動發給新成員。`stop_mode:"immediate"` 時 Ctrl-C／SIGTERM 後不開新格，等受管後代與 helper 全空才回 0，清不空不回 0。`stop_mode:"drain"` 時 SIGTERM 後新的掛行程被拒、已登記 node 照常開格，已掛的行程做完才退出；超過 `drain_timeout_ms` 或再按一次 Ctrl-C 改立即停。

## B-611：一棵資源樹只准一個 daemon

> **暫緩**（2026-10-01）：`state_dir` 排他鎖與 cgroup 子樹鎖；最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。

〔使用者方向 2026-09-30 晚〕同一台機器可有多個 daemon 實例，各管自己的 node 樹，也可巢狀。備援由外部工具重開；取不到既有排他鎖仍回 125，不加等鎖待命模式。

依據：[09-30 晚裁定](../../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)；開關細節見 [B-615](components.md)。

**daemon 啟動時，在任何讀回、清殺、寫狀態之前，先對實際使用的 `state_dir` 取一把排他鎖；取不到就拒絕啟動**（回 125，stderr 說明）。

- **為什麼**：兩個 daemon 用不同 socket 卻指向同一個（或互相重疊的）`state_dir` 或 cgroup 子樹時，會互相搶恢復資料、清殺對方的工作。
- **怎麼算重疊**：以解析後的真實路徑取鎖，並檢查祖先與子孫；任何一個祖先或子孫已被別的 daemon 鎖住，也算重疊。
- 鎖跟著 daemon 程序存活，程序死了鎖自動放掉。
- 有 cgroup 時另取 [B-611 的 cgroup 子樹鎖](cgroup.md#cgroup-子樹鎖b-611)；沒有 cgroup 時只取 `state_dir` 那把資源鎖，socket 鎖仍照下段。
- **socket 的鎖**：每個 `socket_path` 另有同目錄的 `daemon.lock`（[P-101](../protocol/daemon/startup-and-ipc.md)）。〔建議預設；第十九批從 P-101 搬上〕持鎖後才能清理屬於這個實例的殘留 socket，不能刪活著的 socket；無法 bind、路徑過長或權限不足就明確失敗。socket 父目錄的穿越權與 socket 的連接權由部署者先配置，不在封包裡給任意人改。

〔建議預設〕做法：鎖直接對目錄本身取（開目錄再 `flock`）；`state_dir` 祖先往上試鎖到根目錄，子孫往下掃一遍試鎖，試完就放。兩個同時啟動、互為祖孫時，可能雙方都拒絕，重試即可。

依據：主編補，第十八批（審稿新必-3）；第十九批；納入 cgroup 與 git 疑-11（巢狀 daemon 自動偵測時當成沒有 cgroup）。

**驗收：**兩份設定用不同 socket、同一個 `state_dir`（或一個是另一個的子目錄）時，後啟動的拒絕啟動，先啟動的工作不受影響；同一個（或重疊的）明寫 `cgroup_root` 時後啟動的回 125；某個 tick 用 `node.mount` 掛了另一個 daemon（沒寫 `cgroup_root`），內層印 `cgroup=off` 照跑，仍受外層框的上限。

**驗收（開關／多實例）：**〔建議預設，未拍板〕關排空而設定 drain 時，收到 SIGTERM 即停止新格並收尾。〔使用者方向 2026-09-30 晚〕不同實例的樹各自運作；鎖衝突仍回 125，不待命接手。
