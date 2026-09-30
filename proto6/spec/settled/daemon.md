# daemon：登記、喚醒與程序生死

← [整理區](README.md)｜[kernel 樹](../scheduling/README.md)｜[通用 tick](tick.md)｜[daemon 協議](protocol/daemon/README.md)

**daemon 是定期跑 `aos-tick` 的程式。** 它照登記的週期（或被叫醒時）開格，負責它開的程序的啟停與收尾，另開 tick–daemon 通道（B-612～614）。它以資料夾或 inst.json 路徑辨識一個 tick（B-601）。kernel 決定成員何時能做事，daemon 只管開格。

daemon 不是 tick 存在的前提：tick 怎麼被執行不管，cron、人手直接跑也行，只是沒有通道。

依據：[09-29 新架構](../../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../../notes/2026-09-29-verdicts.md)、[第十八批](../../notes/verdicts/09-special-computing-os.md)、[第十九批](../../notes/verdicts/10-tick-minimal-core.md)、[第二十批](../../notes/verdicts/11-tick-as-unit.md)。

### 本篇管什麼

- **本篇是 daemon 行為的正本**（[V-01](../conformance.md)）。[daemon 協議](protocol/daemon/README.md)（P-100～119）只留設定欄位、method 的 params／result、helper 通道、[runner](terms.md#t-09收尾排空停機熱重載逃生口) 回報與錯誤碼。
- **daemon 不在任務表上，不是系統級任務。** 開格、格後收尾、重啟清空、排空與立即停機、熱重載、helper 與切換帳號的那一側，都是 daemon 自己的職責（[T-10](terms.md)）。本篇只寫 daemon 那一側，tick 那一側見 [tick](tick.md)。
- **daemon 跟 tick 之間只有通道這一條路**，通道是唯一逃生口（[T-07](terms.md)、B-612）。

依據：第十八批（本篇是正本）；第十九批（daemon 是定期跑 `aos-tick` 的程式）；第二十批（daemon 的職責；取代第十九批「本篇的保證以標準配備全掛為前提」）。

### cgroup 與 git：有就用

**cgroup 與 git 都不是 daemon 跑起來的前提。**

| | 有 | 沒有 |
|---|---|---|
| cgroup | daemon 替每個 node 開框、寫資源上限；runner 那一套照做，格後收尾與收尾最後再用 `cgroup.kill` 兜底，重啟時也清得到舊程序（B-605、B-601、B-603、B-604） | 每一格、每個掛載行程由它自己的 runner 管名下的程序（B-601），收尾經 runner 做（B-604） |
| git | 只有任務表上的 `aos-git` 會用（[B-630](tick.md)）；daemon 不讀 git | 同左 |

- **runner**＝daemon（或 helper）開每一格、每個掛載行程時用的固定程式 `aos-runner`：照 [inst](../base/inst.md) 執行一次（就是 proto5 aos-exec 的慣例），並當收屍人管它名下的程序（[T-09](terms.md)、B-601）。
- 兩種情形並存的做法寫在各條裡；沒有 cgroup 的情形就是原本的做法。

依據：第二十批進行順序（先不含 cgroup 與 git，下一步納入）；納入 cgroup 與 git 的疑點裁定（有就用、沒有就退回）。

### 時間：哪些用毫秒、哪些用格數

〔使用者方向 2026-09-30，astra 審整理區裁定裁-2〕只有外部或作業系統層的時間保留毫秒；aos 自己決定的政策性保留期改用所屬上層的格數。

| 計時 | 單位 | 為什麼 |
|---|---|---|
| 叫醒週期 `interval_ms` | 毫秒 | 外部規定；也是那個 tick「一格」的標準長度（[C-01](../contracts.md)） |
| 收尾寬限 `shutdown_grace_ms`、排空上限 `drain_timeout_ms` | 毫秒 | 作業系統層的停程序；要跟 systemd 的停機逾時對得上（附錄） |
| 掛載診斷保留期 `mount_diag_ttl_ticks` | 掛它的上層的格數 | 政策性保留期（B-610） |
| pause 存檔間隔 `pause_save_interval_ms`、事項批次寫出（1000 ms） | 毫秒 | daemon 自己的寫檔批次，只決定當機時最多丟多少；daemon 不在任何一格裡，沒有「所屬上層的格」可數 |

依據：第二十批追答 4；astra 審整理區裁定裁-2（撤「daemon 不在格內，所以自己的計時都保留毫秒」）；修正輪暫定的裁定（pause 存檔間隔與事項批次保留毫秒）。

## B-601：記憶體登記與按需執行

daemon 在記憶體放一張登記表，**node 資料夾路徑就是 id**。登記的 node 按登記間隔或叫醒開格。

- **怎麼辨識一個 tick**：看資料夾路徑或 inst.json 路徑。登記時給的是 `<資料夾>/.aos/inst.json` 或 `<資料夾>/inst.json`，一律正規化成所在資料夾。掛載行程（B-613）照給的路徑，可以是單檔。
- **daemon 不做的事**：不讀工作狀態或任務註冊表，不排業務工作、不分資源。只用登記與喚醒資料；讀 inst 只為 `user` 授權。訊息在通道上只**暫存與轉交**，不解析正文（B-614）。
- **不叫排程**：aos 的「排程」是任務表上每格跑一次的程式（[T-07](terms.md)、[scheduling](../scheduling/README.md)）；daemon 這邊只做「定期開格」與「叫醒開格」。
- **一格一格來**：同一資料夾同時只跑一格，由 tick 核心的鎖保證（[B-602](tick.md)）。daemon 另外自己避免同時開同一 node 的兩格，但這不是互斥的來源。
- 〔使用例，不是 daemon 的規則〕agent 通常不設定期，由 kernel 決定何時叫醒及同時執行數；kernel 本格結束就退出，不等成員，LLM／工具由後續 tick 收結果。

依據：使用者方向 2026-09-29；第十九批（辨識 tick、改寫）；第二十批方向 2、追答 3（排程）。

### socket 上有哪些事

| 事 | 正本 |
|---|---|
| 登記與解除 | [B-606](#b-606登記解除換父與身分額度) |
| 叫醒、暫停與故障停格、查詢 | [B-607](#b-607叫醒暫停故障停格與格次序號) |
| 佈建 | [B-609](#b-609佈建固定動作與-helper-動作) |
| 通道事務 | [B-612～614](#b-612tickdaemon-通道) |
| method 形狀 | [daemon 協議](protocol/daemon/README.md) |

通道外的這些 IPC（查詢、暫停與恢復、佈建等）給人手、CLI 與格內的任務用自己的帳號呼叫。人手與 CLI 在格外做的事算外部世界，aos 不管（第二十批疑點裁定 8）。

### IPC 授權與身分額度

**呼叫者看 socket 對面的 Linux 帳號**（`SO_PEERCRED`）：該 node 的帳號，或其上層的帳號。封包自稱的 sender／user 不算呼叫者身分。

- **唯一例外是通道**：請求帶本格憑證時，呼叫者是憑證所屬的那個 tick（B-612）。下表的「X 的 owner 或祖先 owner」，帶憑證時讀成「憑證所屬的 tick 就是 X，或在 X 的有效上層鏈上」。
- **上層**指有效上層鏈（預設看資料夾包含，登記可覆蓋，B-606），不是 OS 父目錄本身。
- **owner** 是登記保存的 `owner_uid`，何時更新見 B-606。
- 身分額度與通用 user 以 [B-301](../base/identity-resources.md) 為正本；額度的寫法與包含判定見 B-606。獲准叫醒不代表獲准擴大額度。

**誰可呼叫**〔建議預設；astra 審整理區必-8 從 P-103 搬上〕：

| method | 誰可呼叫 |
|---|---|
| `node.register` | 新成員：有效上層的 owner 或祖先 owner；首次必須有上層同意，不能自行接到別人的鏈。既有項：原 owner 或祖先 owner，不能搶別隊；可重登自己，但不能擴大目前的額度或佈建權。覆蓋上層與換父：同時是新舊兩個上層的 owner 或祖先 owner；舊上層沒在這個 daemon 登記時只看新上層（B-606） |
| `node.unregister` | 目標 owner 或祖先 owner；效果包含目標已登記子樹 |
| `node.wake`、`node.pause`、`node.resume` | 目標 owner 或祖先 owner |
| `node.mount` | 掛載的上層（`parent_id`；帶憑證時省略＝憑證所屬的 tick）的 owner 或祖先 owner（B-613） |
| `node.kill` | 掛它的那個上層的 owner 或祖先 owner；看路徑，不看當時的憑證 |
| `node.send` | 必帶憑證；寄件 tick 的執行帳號對收件 tick 的 `requests/` 有寫權（B-614） |
| `node.take` | 必帶憑證；只取憑證所屬 tick 自己的 |
| `node.show` | 目標 owner 或祖先 owner；含保留的掛載行程結果（B-610） |
| `node.ls` | 有 socket 連接權；逐筆只列 peer 是 owner／祖先 owner 的登記及保留的掛載行程結果，沒有可見項回空陣列 |
| `daemon.info` | 有 socket 連接權；只回本次啟動 ID，不暴露登記 |
| `mount.clear` | 有 socket 連接權；只清 peer 是 owner／祖先 owner 的已結束掛載行程紀錄（B-610） |
| `node.provision` | 目標 owner 或祖先 owner，且目標登記有相符的 `provision` 授權；需 helper 的動作再由 helper 核對。`spawn_as` 例外：必帶憑證、憑證所屬的 tick 就是目標，帳號看身分額度，不看 `provision` 授權（B-609） |
| `daemon.attention.ls`、`daemon.attention.show` | 只回 peer 是來源 owner／祖先 owner 的事項（[P-601](../protocol/ops.md)） |
| `daemon.attention.done` | 來源 owner 或祖先 owner；只把 daemon 自身事項標成完成 |

〔建議預設；第十九批從 P-103 搬上，astra 審整理區必-8 從 P-111 搬上〕授權與處理細節：

- 先驗 JSON、method 與參數，再授權。
- 不能用 PID、路徑前綴或封包的 `user` 當呼叫者。同 UID 共用同一 OS 權限，不帶憑證時分不出是哪個 node 或工具在呼叫。
- root 或通用 user 不因名稱自帶全樹特權，是 owner 或祖先 owner 才符合。可連 socket 不等於通過 method 授權。
- RPC ID 只配對回應，不是永久執行收據。斷線不代表沒做：登記、pause、resume 可以查目前值核對；wake 可合併但不是永久去重；掛行程與特權動作不准因沒回應就盲目重送。daemon 不加持久重播帳本。
- 一行超過封包上限：回一次 `invalid_request` 就關連線，不無界讀下去。回錯時能辨識出合法的請求 ID 就沿用，不另造 ID。

依據：使用者方向 2026-09-29；第十九批（憑證例外）。

### 執行身分與 helper

- daemon 開 tick 前只讀 [inst 的 `user`](../base/inst.md) 授權，不解析其他工作內容；不合額度就不跑，照 B-607 停格。其餘解析與執行規則依 inst 篇。
- 〔astra 審整理區必-8 從 P-101 搬上〕daemon 以通用 user 讀 inst；讀不到就拒絕，**不交給 root 代讀**。部署要先給通用 user 必要的讀權與目錄穿越權。
- 啟動路徑與可選 helper 的角色依 [B-303](helper.md)；helper 做哪些固定動作見 B-609。

**事項往哪寫**：

- node 問題寫該 node 的 `.aos/attention/`（ignore）；寫不出就 stdout 警告。
- daemon 自身問題才留 daemon attention／stderr。
- 事項怎麼處理見 [S-405](../scheduling/operations.md)。
- 〔建議預設；第二十批改寫計畫記錄者建議〕daemon 在格外往 node 資料夾寫的東西——事項、`.aos/runner-stderr.log`、單檔掛載未啟動的 `.err` 旁檔（B-613）——都算開格與收尾的附帶產物，不違反「通道外一切在格內做」。

**helper 的記憶體鏡像**〔建議預設；第十九批從 P-108 搬上〕：

- helper 存活時，登記與更新先經它重驗（啟動設定的頂層額度、可信上層鏈、原始 `user` 與路徑）才生效。鏡像只在記憶體。
- 〔astra 審整理區必-8 從 P-108 搬上〕解除時，一筆登記的鏡像要等它的範圍全空、而且底下沒有已登記子節點才移除；整棵子樹由子到父依序解除。
- 沒 helper 時：只用通用 user、沒佈建權的登記由 daemon 自己核對；其他帳號或要 helper 的動作的新登記回 `helper_unavailable`；既有的通用 user 登記照常跑。
- helper 用安全的程序 handle 追蹤、wait 自己的孩子並跨帳號收尾；daemon 不 wait helper 的孩子、不信裸 PID。
- helper 失聯時，daemon 只做自己權限做得到的收尾；其他帳號沒確認全空就阻擋。斷線不代表已退出，也不能重送不明的開格。helper 消失而不能收尾時保留占用、阻止新格，不宣稱清空。
- 沒 helper 時，只授 `cgroup_limits` 的登記，daemon 另核對它落在交給 daemon 的子樹內（B-605）；沒有 cgroup 時 `cgroup_limits` 回 `unsupported`（B-609）。

**helper 的設定**〔建議預設；第十九批從 P-102 搬上〕：root 用的設定檔及其父目錄不得由不受信任的 node 改寫；helper 在 fork 前固定一份設定副本（B-608）；設定父死訊號時處理競態，父死訊號與私有通道斷線一起監看。額度不准 UID 0 或 root 別名。

### 開格：runner 與回報

〔建議預設；第十九批從 P-109、P-110 搬上〕daemon（或 helper）以固定的 [runner](terms.md#t-09收尾排空停機熱重載逃生口)（`aos-runner`）開每一格與每個掛載行程：

1. fork 後先 `setsid`（runner 自成一個 session，不跟 daemon 的終端同組），降權；有 cgroup 時，runner 開在那個 node 的 `n-<h>/tick` 框裡（掛載行程在 `mount-<h>`，B-605），用 `CLONE_INTO_CGROUP` 或 exec 前寫 `cgroup.procs`；
2. runner 核對 UID，並核對 inst 原來源的 bytes 跟授權時的快照相同；
3. 才照 [inst](../base/inst.md) 解析、開檔與執行。

argv 與回報形狀見 [P-109、P-110](protocol/daemon/provision-and-runner.md)。

- **串流**：runner 的 stdin／stdout 是 `/dev/null`（`spawn_as` 例外：用 `aos-as` 交來的 stdio，B-609）。stderr 由 daemon 收集成 node 診斷，不直通 daemon 的 stderr；資料夾 node 暫定寫 `.aos/runner-stderr.log`（覆寫、ignore），輪替與留存以後再定。
- **環境**：除了 [B-303](helper.md) 與 inst 的規則，daemon 開的每一格、每個掛載行程都多放兩個通道變數（B-612），不帶管理 fd 或 key。daemon 帶了 `--firstdo-fsync` 時，另放 `AOS_TICK_FIRSTDO_FSYNC=1`，讓那一格的 `aos-tick` 開格時 fsync（[B-633](tick.md)）〔使用者 2026-09-30 同意照暫定〕。`spawn_as` 開的程序怎麼補環境見 B-609。
- **回報**：每次完整收尾只回報一次。
  - 前置失敗（身分不在額度內、來源變了等）回 `started:false`。
  - 已放行後，子程式自己的結束碼照實回報；被訊號結束另帶訊號編號。
  - runner 在已放行後自己收尾失敗，回報 `FinalizeFailed`，不能當成子程式退出 125。
  - 沒有完整可信回報就是結果不明，不能推定從未執行。前置檢查可能已建目錄或截斷輸出，125 不代表沒有檔案副作用。
- **helper 開格什麼時候回**〔建議預設；第十九批依方案 A 從 P-108 搬上〕：helper 替 daemon 開的格與掛載行程，要等 runner 回報並結束、wait 回收之後才回覆 daemon。全空但業務失敗仍算開格完成；無法確認全空回 `cleanup_failed`。私有通道按 RPC ID 配對，可同時有多筆在途。helper 拿到的快照是 daemon 取原始 `user` 時的同一份不可變 bytes；inst 的 base 仍照 [inst 目標](../base/inst.md#inst-目標檔案或資料夾)算，不看快照放在哪。`spawn_as` 例外：runner 開起來就回，結束碼走 `aos-as` 交來的 pipe（B-609）。

### 誰管哪些程序

**runner 當收屍人**〔使用者方向 2026-09-30，確認定案〕：每一次開格（或掛載）由那一個 runner 負責它底下的所有程序；daemon／helper 只跟 runner 打交道。有 cgroup 時，daemon 另外用框兜底。

| 誰 | 做什麼 |
|---|---|
| daemon、helper | 自己是 child subreaper。fork＋`setsid`＋exec runner；以 pidfd 追蹤 runner、對它送訊號 |
| runner | 設 `PR_SET_CHILD_SUBREAPER`。照 inst 讓子程式另開 session（子程式群組，[inst](../base/inst.md)）。子程式的後代不論有沒有跳出群組，只要中間的父程序死了，就掛回 runner |

所以 inst 的「子程式另開 session」跟 daemon 的收尾不衝突：受管的不是某一個群組，而是 runner 名下的整棵樹。

**runner 怎麼清空自己名下**（清空步驟）：對子程式群組送 SIGKILL；之後反覆對每個掛回自己的程序，連同它所在的程序群組送 SIGKILL 並 wait 回收，直到 runner 名下沒有程序。

**runner 什麼時候清空**：

| 時機 | runner 怎麼做 |
|---|---|
| 主程式正常結束（格後收尾） | 直接做清空步驟（不先 TERM，主程式已經結束），做完才寫回報、結束 |
| 第一次收到 SIGTERM（daemon 要收尾，B-604） | 把 SIGTERM 轉給子程式群組與每個掛回自己的程序，繼續等 |
| 第二次收到 SIGTERM（寬限到了） | 做清空步驟，寫回報（被訊號結束）、結束 |
| 回報 pipe 的讀端關了（`spawn_as` 的呼叫方不在了，B-609） | 做清空步驟、結束 |

- runner 結束、被 daemon／helper wait 回收，這一次開格的範圍才算全空（沒有 cgroup 時）。
- **清不到的**：經外部服務（systemd、at 等）開的、自己設成 subreaper 的後代、換成別的帳號的程序。它們若還握著 tick 的鎖 fd，同資料夾的下一格回 75（[B-602](tick.md)）。
- **runner 自己意外死掉**（被 SIGKILL、OOM）：它名下的程序掛回 daemon（或 helper）。daemon 分不出它們原本屬於哪一格，一律 SIGKILL 並回收；那一次開格沒有可信回報，照 B-607 記 `unknown`、停格，要人確認後才 resume。
- 後代串流收完與取消競態依 [B-203](../base/execution.md)。範圍沒清空前不釋放名額、不開下一格；所有失敗都不自動重跑結果不明的工作。

### 有 cgroup 時：runner 照做，框再兜一次

有 cgroup 時上面的做法**照舊**，另外加一層框（框的樹見 B-605）：

| 步驟 | 做法 |
|---|---|
| 開格 | runner 開在 `n-<h>/tick` 框（上面開格第 1 步） |
| 格後收尾 | runner 回報、被回收之後，daemon 對 `tick` 框與本格的 `task-*` 框寫 `cgroup.kill`，看 `cgroup.events` 的 populated 變 0，再 rmdir `task-*`（框已交給別的帳號時經 helper 刪）。不另外對程序群組送 SIGKILL |
| 範圍 | 只收 `tick` 與 `task-*`；子 node 的 `n-*`、本 node 掛的 `mount-*`、node 自己開的其他子框（逃生口，B-605）都不碰 |
| 等不到歸零 | 例如 D 狀態程序：算後代清不空，照 B-607 停格 |

- 框兜得住 runner 清不到的：跳出程序群組又自設 subreaper 的、換成別的帳號的（經 `aos-as` 開、放進本 node 框的）。經外部服務開的仍在框外，不歸 aos 管。
- 包了 `aos-cg` 的項，自己在 `task-*` 框裡當場收（[B-634](tick.md)）；daemon 的格後收尾只是兜底。
- 某個 node 建不了框時，那個 node 照沒有 cgroup 的做法跑（B-605「中途失效」）。

依據：第十九批（程序群組）；第二十批追答 8（一格結束後殺殘留歸 daemon）；astra 審整理區必-1（受管範圍改成 runner 名下的整棵樹），使用者確認定案；納入 cgroup 與 git 疑-7（node 自開子框不收）。

**驗收：**無事 node 不開 tick；重複叫醒不重疊；任務在背景留一個 `sleep`，tick 結束後它被清掉、下一格照常開；任務在背景 `setsid` 另開 session 留一個 `sleep`、再讓中間的父程序結束，tick 結束後它也被清掉；兩個 node 同時跑，一邊的格後收尾不碰另一邊的程序。以上在有、沒有 cgroup 的機器上都成立。有 cgroup 時，任務用 `setsid` 加 double fork 再自設 subreaper 留下的程序，格後被 `cgroup.kill`；node 自己開的子框裡的程序不被收。身分拒絕及無 helper 情境見 [V-03](../conformance.md)。給 `.aos/inst.json` 或 `inst.json` 路徑登記，得到的 node id 是所在資料夾。

## B-504：通知只是提示

**daemon 只按登記的週期或叫醒（含急件）開格。** 反應速度就是一格。

- 不看收件區有沒有新檔，也不讀任何檔的正文；不為了「收到就處理」另開監看。
- 一般收件等收件 tick 自己的下一格（[T-07](terms.md)）。通道訊息送到時，**只有急件**才叫醒收件 tick，一般件等它自己的下一格（B-614）。
- kernel 才核對自己的收件與成員摘要，決定後續要叫醒誰。叫醒本身不是接件、消費或完成證據。
- 〔建議預設〕執行中的 node 收到叫醒時，daemon 留一個待喚醒標記，收尾後再開下一格。叫醒合併或遺失後的補查由 kernel 按 [S-202](../scheduling/admission.md) 每格處理，daemon 不代查內容。

依據：使用者方向 2026-09-29；第十九批（急件）；第二十批追答 5、7（刪「新檔通知」）。

**驗收：**往收件區放新檔不會讓 daemon 開格，收件 tick 在自己的下一格（或被叫醒時）才處理；漏掉一次叫醒，完整投件仍能在所屬 kernel 的後續補查被發現；同一 node 連續收到多次叫醒不會同時跑兩格。內容發布與去重見 [投件](../base/transport.md)，互斥見 [B-602](tick.md)。

## B-603：重啟先清空，再讓樹長回來

**原則：重啟不接續孤兒工作，在途程序全殺，確認清空才開新格。** 重啟清空是 daemon 自己的職責。

| 情況 | 有 cgroup | 沒有 cgroup |
|---|---|---|
| 整機或 WSL VM 重開 | 舊程序本來就全沒了，照常開格 | 同左 |
| 只有 daemon 重開（例如被 SIGKILL） | 先清空舊框才開格（下面「清空舊程序」） | 舊程序可能還在，daemon 清不掉（已接受） |

不能拿一個可能重用的 PID 直接 kill。

### 啟動順序

1. 啟動自檢（B-605）。
2. 取得排他鎖（[B-611](#b-611一棵資源樹只准一個-daemon)）；取不到就拒絕啟動。在這之前不讀回、不清殺、不寫狀態。
3. 讀回 `state.json`。
4. 清空舊程序（有 cgroup 才有這一步，見下面）。
5. 寫 PID 提示檔、開 socket、開始開格。

**PID 提示檔**〔astra 審整理區必-8 從 P-102 搬上〕：`state_dir/daemon.pid` 與 `state_dir/helper.pid`（沒 helper 寫 `none`），啟動時寫，正常退出時刪；helper 的 PID 另印在 stdout。啟動時看到舊檔只當提示，不拿來殺程序。格式見 [P-102](protocol/daemon/startup-and-ipc.md)。

### 清空舊程序

**有 cgroup 時**〔使用者方向 2026-09-29 晚；納入 cgroup 與 git 疑-8〕：daemon 開的每一格（含孫程序）都在該 node 的框裡，daemon 當掉時框還在。

1. **找舊框**：`state.json` 記著上次用的子樹根（`cgroup_root_last`，[P-116](protocol/daemon/shutdown.md)）。這次的子樹根不同（例如首推的 `systemd-run --user --scope` 每次開出的 scope 名字都不一樣）、而舊根還在時，先對舊根取 B-611 的鎖；取不到表示另一個 daemon 在用，不碰。
2. **清**：開任何新格之前，對新舊子樹裡每個仍有程序的受管框走一次 B-604 的收尾（寬限沿用 `shutdown_grace_ms`），確認全空才往下。受管框是 `tick`、`task-*`、`mount-*` 與子 node 的 `n-*`；node 自己開的其他子框是逃生口，照 `kill_escape_cgroups` 決定殺不殺（B-605）。
3. 舊 scope 清空後沒有程序，systemd 會自己回收。

**沒有 cgroup 時**〔第二十批：重啟清不掉舊程序，接受〕：舊 daemon 的 runner 與它們名下的程序（B-601）跨不過 daemon 重啟，新 daemon 找不回來，**daemon 重開時的清空不成立**。

- 後果：舊的一格還沒結束、還握著鎖 fd 時，同一資料夾的新格回 75（[B-602](tick.md)），等它自己結束。
- 後果：舊的掛載行程可能跟掛它的 tick 重新掛上的那個同時在跑，掛的一方照 unknown 規則核對（[S-401](../scheduling/operations.md)）。

兩種都一樣：開 runner 時設 `PR_SET_PDEATHSIG` 只當加分（它只作用於直接子程序），不是必要；不要求跨重啟保存程序表。

### 存檔與讀回

- daemon 設定檔只列頂層 node 及其啟動設定、身分額度。
- **正常退出**把登記表、pause、未處理 wake 存進 `state_dir/state.json`（格式見 [P-116](protocol/daemon/shutdown.md)）。這份檔不保存或接續執行中的程序；無檔也能從頂層啟動。
- **讀回後**依目前 roots、inst 與上層鏈重新核對每筆登記的身分與授權，不合的丟掉；沒有覆蓋的登記重新照資料夾推上層（B-606）；缺檔或壞檔就從 roots 重建，壞檔留診斷。
- 讀回後先把 `clean_shutdown` 原子改成 false，才接受工作。寫檔一律先寫完整暫檔再原子替換（[P-003](../protocol/README.md)）。
- 讀回的登記一律算新登記：換新的登記識別，格次序號從頭算（B-606、B-607）。
- **不存檔、不接回的**：掛載行程（B-613；重啟時被收尾的，由掛它的 tick 照工作結果與 unknown 規則核對）、通道上暫存的訊息（B-614）。其他未處理 wake 照常接回。

### pause 批次存檔

- pause 有變動才批次寫 `state.json`，最多每 `pause_save_interval_ms`（預設 1000）原子寫一次，標 `clean_shutdown:false`；正常退出存完整最新狀態。
- 意外退出最多丟最後一個間隔內的 pause 變動；過期登記與未保存 wake 由頂層補查恢復。
- 寫檔失敗寫 daemon 自身事項並報 stderr。

### 逐層重建

- **daemon 開啟就自動開始 tick 頂層 node**；已恢復 pause 的頂層保留這次 wake，等 resume。
- **boot id**〔astra 審整理區必-8 從 P-115 搬上〕：每次啟動新生一個，整次存續不變；只放記憶體，重開不得沿用，socket 路徑相同也不行。`daemon.info`、`node.show`、`node.ls` 回的都是它（格式見 [P-115](protocol/daemon/registration.md)）。node 路徑別名、重用或跨機重名的風險由使用者承擔。
- 〔使用例：kernel 那側〕頂層發現 boot id 改變後重新登記直接成員並叫醒子 kernel，逐層重建。平常只在 boot id 或成員清單變動時補登記，不每格重送（B-606）。壞成員留待辦、跳過，不擋其他子樹。
- **空框清理**（有 cgroup 時；〔使用者方向 2026-09-30，第十八批〕）：重啟清空後，沒有登記對應的 `mount-*` 框直接刪（掛載行程不會接回）；沒有登記對應的 `n-*` 框先留著，等逐層重建完、仍沒人登記才由下往上刪，免得先刪掉稍後又要重建的框（重建會讓上限要重寫、用量歸零）。〔建議預設〕「重建完」＝所有已登記、沒暫停的 node 自這次啟動以來都至少跑完一格。框裡還有逃生口的程序就不刪。框已交給別的帳號時由 helper 刪（B-609）。
- 清空後由 node 按 [tick](tick.md) 恢復檔案，執行器／所屬 kernel 核對工作結果；daemon 不代讀結果或判業務終局。

依據：使用者方向 2026-09-29（全殺、存檔與讀回、pause 批次存檔、逐層重建）；第十八批（空框清理）；第十九批（掛載行程與暫存訊息不存檔）；第二十批（重啟清空是 daemon 職責；沒有 cgroup 時清不掉，接受）；納入 cgroup 與 git 疑-8（記上次的子樹根）。

**驗收：**正常重開讀回 pause／wake，無快照時頂層仍自動跑；daemon 重開後 `boot_id` 改變；正常退出後 PID 提示檔被刪，啟動時看到舊檔不殺那個 PID；pause 批存與逐層補登記見 [V-03](../conformance.md)。沒有 cgroup 時 daemon 被 SIGKILL 後重開，舊格還握著鎖時同資料夾的新格回 75、不重疊。有 cgroup 時 daemon 被 SIGKILL 後以新的 scope 重開，舊 scope 裡仍有程序的受管框先收到 SIGTERM、寬限後被清空，才開新格；重建途中不先刪空框，重建完仍沒人登記的才刪。

## B-604：收尾、停機、停用與退役

收尾、排空與立即停機是 daemon 自己的職責（第二十批）。

### 收尾

**收尾是 daemon 清掉一個範圍的固定做法**。runner 那一套一定做（B-601）；有 cgroup 時最後用框兜底：

1. 停止這個範圍開新格；
2. 對範圍內每個 runner 送 SIGTERM（runner 轉給它名下的程序，B-601）；
3. 等 `shutdown_grace_ms`（[P-101](protocol/daemon/startup-and-ipc.md)，預設 2000）；
4. 對還沒結束的 runner 再送一次 SIGTERM，runner 就清空自己名下、回報、結束（B-601）；
5. wait 回收每個 runner。runner 在第二次 SIGTERM 之後還不結束，daemon 才對它送 SIGKILL，這一次開格記結果不明、算清不空；
6. **有 cgroup 時**：對範圍內仍有程序的框寫 `cgroup.kill`，以 `cgroup.events` 的 populated 確認全空。

- **誰用這一套**：重啟清空（有 cgroup 時，B-603）、停機、解除登記、砍掉掛載行程、helper 停程序；取消在跑的工作也用這套（[B-203](../base/execution.md)）。
- **範圍**：這個 node（或掛載行程）目前那一格的 runner、它掛上而還在跑的掛載行程，以及已登記子 node 的同樣範圍。有 cgroup 時換成框：`tick`、`task-*`、`mount-*` 與已登記子 node 的 `n-*`；node 自己開的其他子框是逃生口，照 `kill_escape_cgroups`（B-605）。
- 已經在收尾的照開始時的寬限值走完，之後改設定不影響它。
- 確認不了全空就回報失敗、保留阻擋與占用，不能先宣稱完成或假裝名額已釋放。
- **不是這裡的收尾**：runner 處理 inst 自己的逾時（照 inst 的 2 秒）屬 [inst](../base/inst.md)；一格正常結束後的殘留見 B-601 的格後收尾；`aos-cg` 對自己 `task-*` 框直接 `cgroup.kill` 屬 [B-634](tick.md)。
- **清不到的**：沒有 cgroup 時見 B-601（經外部服務開的、自設 subreaper 的、換成別的帳號的）；有 cgroup 時只剩經外部服務開的。它們若還握著 tick 的鎖 fd，同資料夾的下一格回 75（[B-602](tick.md)）。
- 用詞：「排空」只指下面的排空停機；解除登記不叫排空。

依據：第十八批（收尾、用詞；以 cgroup 收尾）；第十九批（程序群組管不到的）；astra 審整理區必-1（經 runner 收尾），使用者確認定案；納入 cgroup 與 git 改寫計畫（有 cgroup 時最後以 `cgroup.kill` 兜底）。

### 停機：立即與排空

daemon 收到 SIGINT（前景 Ctrl-C）或 SIGTERM 時停機。走哪一種由設定 `stop_mode` 決定（`immediate`／`drain`，預設 `immediate`），不開停機用的 IPC。訊號、結束碼與設定欄位見 [P-114](protocol/daemon/shutdown.md)。

**立即停**：

1. 停止新登記、叫醒、掛行程與開格；
2. 對所有在途程序做一次收尾；通道上暫存的訊息直接丟掉（B-614）；
3. 清空後存 B-603 的完整 `state.json`、讓 helper 退出、清 socket 與 PID 檔，然後回 0。

清不空或存檔失敗回 125。

**排空停**（第十八批）：

1. 拒收新的掛行程與新成員登記（回 `stopping`）。已登記的 node 照常開格，讓 kernel 能繼續收結果；通道照常收送。被拒的掛行程不會啟動；沒收到回應時照 [S-401](../scheduling/operations.md) 判讀。
2. 等已掛的行程全部跑完；然後停止開新格，等在途 tick 自然結束。
3. 全部結束就照立即停的後半存檔、退出。
4. 從收到訊號起超過 `drain_timeout_ms`（預設 600000，10 分鐘），或排空途中再按一次 Ctrl-C（SIGINT），就改成立即停（第十八批 Q16）；排空途中再收到 SIGTERM 也同樣改立即停〔建議預設，工程補充〕。被收尾的掛載行程由掛它的 tick 照 unknown 規則核對。

**共通**：停機或排空中不接受熱重載（B-608）。突然被殺則下次依 B-603 恢復，不因 socket 不見就推論已全空。未清空要回報失敗，不能先宣稱停止完成。

依據：使用者方向 2026-09-29 晚；第十八批加排空。

### 停用與退役

- **停用**：授權者停用成員時，由所屬 kernel 停止再喚醒／再登記該成員，並請 daemon 解除登記（B-606 的解除就是收尾後刪登記）。停用 kernel 時同樣處理其已登記子樹，不連帶停掉其他隊。只清 daemon 記憶體的一筆資料不能代表持久停用，否則下次上層 kernel tick 會把它登記回來。kernel 何時對成員發解除見 [S-202](../scheduling/admission.md)。
- **退役**：由授權者明示，所屬 kernel 先核對程序已清空、未結工作與資料歸屬；daemon 不另設持久退役表。UID／GID 及 home 都不自動回收或刪除，資料與 Linux 所有權的處置另由有權限者決定；解除登記不會消除舊檔案的 ownership。

依據：使用者方向 2026-09-29。

**驗收：**停止一個子 kernel 不妨礙別隊運行；受管後代仍在時不回報收尾完成；任務忽略 SIGTERM 時，寬限到了仍被清掉（有 cgroup 時最後是 `cgroup.kill`）；解除登記不刪 home、不把舊 UID 自動發給新成員。`stop_mode:"immediate"` 時 Ctrl-C／SIGTERM 後不開新格，等受管後代與 helper 全空才回 0，清不空不回 0。`stop_mode:"drain"` 時 SIGTERM 後新的掛行程被拒、已登記 node 照常開格，已掛的行程做完才退出；超過 `drain_timeout_ms` 或再按一次 Ctrl-C 改立即停。

## B-605：依賴與啟動自檢

**tick 核心不需要 cgroup；daemon 有 cgroup 就用、沒有就退回 runner 那一套**（B-601、B-604）。cgroup 給 daemon／helper（node 框與資源上限）與普通程式 `aos-cg`（每項一框，[B-634](tick.md)）用。

- 撤掉的：第十四、十五批「沒 cgroup v2 就拒絕啟動」；第十九批的「沒 cgroup 走備援、降到備援級」「完整路／備援路」與啟動時印 `standard: cgroup=…`。
- 初版不使用 systemd 當執行期依賴；systemd 只當取得委派子樹、開機自動啟動的方式（下面與文末附錄）。

依據：第十九批（推翻第十四、十五批）；第二十批追答 8；納入 cgroup 與 git 的疑點裁定。

### 啟動自檢

- **daemon 自己的最低需求**：Python 3.9；不合就報錯退出（125）。
- **不查 git**：git 只有任務表上的 `aos-git` 會用（[B-630](tick.md)），daemon 不查。
- **偵測 cgroup**：照下面「什麼算有 cgroup」。stdout 印一行 `cgroup=on` 或 `cgroup=off`，只報 daemon 自己的；`off` 時 stderr 另印一次警告，不寫事項、不問 y／n。〔建議預設〕
- **沒有 cgroup 時**：B-609 的 `cgroup_limits` 回 `unsupported`，`node.show` 的 `cgroup` 為 null，B-611 只取 `state_dir` 那把鎖，程序照 B-601 由 runner 管。

### 什麼算有 cgroup

三個條件都成立才用：Linux ≥ 5.14（`cgroup.kill` 從這版起有）、`/sys/fs/cgroup` 是純 cgroup v2、拿得到**委派給自己**的子樹。

**委派給自己怎麼認**〔使用者方向 2026-09-30，納入 cgroup 與 git 疑-6〕：

| 情形 | 算不算 |
|---|---|
| 設定明寫 `cgroup_root`，或開了 `create_cgroup` | 算：部署者說了就是要（準備不好就報錯退出，下面） |
| 省略時，systemd 說 daemon 所在的單位有 `Delegate=yes` | 算。用 `systemctl [--user] show -p Delegate <單位>` 問，單位名取 `/proc/self/cgroup` 最後一段 |
| 省略時，問不到 systemd，或單位沒有 `Delegate=yes` | 不算，`cgroup=off` |
| cgroup v1、混合模式（v2 掛在 `/sys/fs/cgroup/unified`） | 自動偵測一律不算。混合模式可以明寫 `cgroup_root` 指進去，但 controller 多半在 v1 那邊，上限會回 `unsupported`，只剩收尾與看空不空能用 |
| 自動偵測時，子樹根的祖先已被別的 daemon 鎖住（巢狀 daemon，B-611） | 不算，`cgroup=off` 照跑；它仍被外層的框和上限包住（疑-11） |

- **只看擁有者不夠**（本機實測，WSL、systemd 255）：沒加 `Delegate=yes` 的 `systemd-run --user --scope`，`cgroup.procs` 一樣歸自己；兩種 scope 都沒有 `user.delegate` xattr。只看擁有者，會把沒委派的 scope 當成可以寫，違反 systemd「一個框只有一個寫入者」的約定。
- **明寫卻準備不好**（疑-9）：明寫了 `cgroup_root` 或開了 `create_cgroup`，子樹卻準備不好、搬不動程序，報錯退出（125），不默默改成沒有 cgroup：明寫就是要，默默不用會少了上限。

### 子樹從哪來（首推不用 sudo）

**用 cgroup 時一定要有一棵已經準備好的 cgroup v2 子樹**〔使用者方向 2026-09-29 晚，第十五批；第十九批改成「沒有就照沒有 cgroup 做」〕。依序推薦：

| # | 做法 | 用不用 sudo | 說明 |
|---|---|---|---|
| 1 | `systemd-run --user --scope -p Delegate=yes aos daemon --config ~/.config/aos/daemon.json` | 不用（首推） | 省略 `cgroup_root`，就用這個 scope 當子樹。實測這台 WSL 拿得到 `cpu memory pids` |
| 2 | 使用者層 service：固定單位名、`Delegate=yes`，對該帳號 `loginctl enable-linger` | 不用 | 開機自動啟動用這個；框路徑固定，重啟時 systemd 也會先殺舊程序（文末附錄） |
| 3 | 系統層 service：root 開、`Delegate=yes` | 要 | 有 helper（文末附錄） |
| 4 | 沒有 systemd：root 事先 mkdir 並 chown 下面的委派檔，或 sudo 開加 `--create-cgroup` | 要 | 明寫 `cgroup_root` |
| 5 | 都沒有 | — | `cgroup=off`，照 B-601 跑 |

檢查步驟〔建議預設〕：

1. `stat -fc %T /sys/fs/cgroup` 印 `cgroup2fs`：是 cgroup v2。
2. `uname -r` 至少 5.14。
3. `systemctl --user is-system-running` 有回應：有使用者層的 systemd。
4. 在委派 scope 裡看拿到的子樹：`systemd-run --user --scope -p Delegate=yes sh -c 'p=$(sed -n "s/^0:://p" /proc/self/cgroup); cat /sys/fs/cgroup$p/cgroup.controllers'`，至少有 `memory pids`。沒有 `cpu` 時 CPU 上限回 `unsupported`，其餘照用（要 `cpu` 得讓使用者層的 systemd 委派它，屬部署設定）。

**限制要知道**：

- **不用 sudo 就只能單帳號**：沒有 root helper，就不能把框交給別的帳號，也不能以別的帳號開程序。多帳號部署一定要 sudo（3 或 4）。
- **WSL 的三個坑**（本機實測）：
  - wsl.exe 開的 shell 在 root 擁有的 `/init.scope` 裡，直接跑 daemon 只會是 `cgroup=off`。要先在 `/etc/wsl.conf` 的 `[boot]` 設 `systemd=true`，再用 1 或 2。
  - `systemd-run --user --scope` 每次開出的 scope 名字都不一樣（`run-r<隨機>.scope`），daemon 重啟後要靠 `state.json` 記的上次子樹根去清舊框（B-603）。
  - 框的檔案歸自己，不代表 systemd 真的委派了（上面「只看擁有者不夠」）。
  - 另外：VM 閒置被關時所有東西一起死，照 B-603 的「整機重開」處理。
- **硬上限由部署者在更外層設**〔第十八批〕：頂層 kernel 的額度檔只是分配政策，不承諾頂層真的被卡住；整棵子樹要有總上限，由部署者事先設在子樹根或更上一層。

**子樹的通用規則**〔第十五～十七批〕：

- **在哪**：設定的 `cgroup_root`（[P-101](protocol/daemon/startup-and-ipc.md)）；省略時就用 daemon 自己目前所在的 cgroup。
- **根只當分支**：daemon（或其他程序）就在子樹根那層時，daemon 啟動先開 `daemon` 子層、把那層程序全搬進去（cgroup v2 規定已有子層又要開 controller 的那層不能放程序）。搬不動或一直有新程序進來：明寫 `cgroup_root` 就報錯退出，省略時當成沒有 cgroup。
- **準備好**＝子樹存在；它的資料夾和根上的委派檔（`cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads`）交給了 daemon 跑的帳號。不用 sudo 開時，daemon 自己也要已經在子樹裡，因為 cgroup v2 搬程序要對共同上層有寫權。
- **sudo 開時**：daemon 在降權前（還是 root 時）把子樹資料夾及其委派檔交給降權後的帳號、自己搬進子樹下的葉框；跨子樹邊界搬程序要 root，所以只在降權前做。
- **`--create-cgroup`**（設定 `create_cgroup: true`，預設關）：子樹不在時由 daemon 自己建在 `cgroup_root`（開了就必須寫，否則用法錯 2）；sudo 開時在降權前建。建不了就報錯退出；子樹已經在就直接用。在有 systemd 的機器上這樣做會違反「一個框只有一個寫入者」，通常能用但不保證，aos 不擋。

### 框的樹、命名與交框

```
<子樹根>/daemon                daemon 與 helper
<子樹根>/n-<h>                 頂層 node（分支；上限寫這層）
          ├─ tick              這格的 runner、tick 與沒包 aos-cg 的任務
          ├─ task-<seq>-<pid>  aos-cg 開的每項一框（B-634）
          ├─ mount-<h>         本 node 掛的掛載行程（B-613）
          ├─ n-<h'>            子 node，同樣結構
          └─ （其他名字）      node 自己開的子框：逃生口
```

- **命名**〔第十六批〕：node id 是任意長的絕對路徑，不能直接當 cgroup 名。`<h>` 是 node_id 的 UTF-8 bytes 做 sha256 取前 16 個小寫 hex；碰撞機率可忽略，首版不另做偵測。node 框放在**有效上層** node 的框下（頂層放子樹根下），所以覆蓋上層時框也跟著放（B-606）。
- **保留名**：`daemon`、`tick`、`task-*`、`n-*`、`mount-*`；node 自己開子框不能用這些名字。
- **誰建、誰交**〔納入 cgroup 與 git 疑-10〕：daemon 在 node 第一次開格前自己建 `n-<h>` 與 `tick`（不寫上限）。`aos-cg` 要以 node 的帳號在 `n-<h>` 下開框、搬自己，所以 daemon 把 `n-<h>` 資料夾及其 `cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads` 交給 node 的執行帳號（inst 的 `user`）；上限檔仍歸 daemon，node 改不了。帳號不是 daemon 自己時經 helper 做（B-609 的 helper 內部動作）。開格前發現擁有者跟目前的 `user` 不同（inst 換了帳號），就重交一次。不開放給 `node.provision`。
- **連帶**：交框之後，node 帳號能對自己框裡別的帳號的程序（`aos-as` 開、放進本 node 框的）寫 `cgroup.kill`；這是預期行為。它也能關掉自己 `cgroup.subtree_control` 的 controller，等於撤掉自己子 node 的上限；這在它的權限內，祖先對整棵分支的上限照樣有效（B-609）。
- **資源上限設在 node 那層**〔使用者方向 2026-09-29 晚〕：寫在 `n-<h>` 分支一次，之後每格沿用，隨時可改（B-609）。

### 逃生口：node 自開的子框，不管

〔使用者方向 2026-09-30，第十八批 Q19；納入 cgroup 與 git 疑-7「准」〕node 可以在自己的 `n-<h>` 下另開子框（名字避開保留名），把程序搬進去、刻意留常駐程序。**這不在 aos 的管轄範圍內，aos 不管**，跟「通道是唯一逃生口」（[T-07](terms.md)）不算衝突。

- 格後收尾只看 `tick` 與 `task-*`，不碰這些子框（B-601）。
- daemon 重啟（B-603）與解除登記（B-606）時殺不殺，照設定 `kill_escape_cgroups`：預設 false，不殺、框留著；設成 true 就一併收尾（[P-101](protocol/daemon/startup-and-ipc.md)）。
- 逃生口的程序仍在 node 框裡，照樣受 node 的資源上限管。框裡還有逃生口時 `n-<h>` 刪不掉：解除登記照樣完成、框留著並寫該 node 的事項，等之後空了由 B-603 的空框清理刪。
- 沒有 cgroup 時沒有框，也就沒有這種逃生口；runner 清不到的常駐程序（例如經外部服務開的）本來就不歸 daemon 管（B-601）。
- 要 daemon 追得到、`node.kill` 砍得掉的常駐程序，用通道 `node.mount` 掛（B-613）。

### 中途失效：只影響那個 node

〔建議預設〕daemon 啟動時 `cgroup=on`，之後某個 node 建框或交框失敗（上層關了 controller、權限被改、`cgroup.max.descendants` 滿了）：那個 node 照沒有 cgroup 的做法跑（B-601），寫一件該 node 的事項；別的 node 照常。不整個 daemon 降級，也不停那個 node。之後建得起來就改回用框。

### 有就用的其他功能

- project quota 等功能在啟動時自動偵測，設定檔可強制關（P-101 的 `disable`，可熱重載，B-608）。
- 沒有 quota 時，磁碟用量由磁碟資源任務定期量（[B-304](../base/identity-resources.md)、[S-203](../scheduling/admission.md)）。
- 檔案系統不限定：node 放在不支援某些功能的地方，那些功能就不支援；不列白名單或拒絕清單。

依據：使用者方向 2026-09-29 晚。

### 初版不做

systemd 的沙盒防護（`CapabilityBoundingSet` 等）以後再考慮；helper 掛 tmpfs 拿掉；原本打算交給 systemd 的開程序、定時叫醒等做法，初版全由 daemon 自己做（使用者方向 2026-09-29 晚）。

**驗收：**Python 低於 3.9 時啟動報錯退出。Linux 低於 5.14、沒有純 cgroup v2、WSL 在 `/init.scope` 直接跑、或用沒加 `Delegate=yes` 的 scope 開時，daemon 照常啟動、印 `cgroup=off`、照常開格，stdout 沒有 `standard:` 行；照首推用 `systemd-run --user --scope -p Delegate=yes` 開、不寫 `cgroup_root` 時印 `cgroup=on`；省略 `cgroup_root`、或有寫但該層有程序時，原層只剩子層、沒有程序；明寫 `cgroup_root` 卻沒準備好、也沒開 `--create-cgroup` 時報錯退出（125），不自己建；開了 `--create-cgroup` 卻沒寫 `cgroup_root` 時用法錯（2），建不了時報錯退出；某個 node 建框失敗時只有它照沒有 cgroup 跑、有一件事項；node 自己開的子框裡的程序，格後與重啟時都不被收（`kill_escape_cgroups` 省略時）；偵測得到 quota 但設定強制關時不使用。

## B-606：登記、解除、換父與身分額度

method 形狀見 [P-104～105](protocol/daemon/registration.md)，誰可呼叫見 B-601。

### 登記是什麼

**登記＝請 daemon 照週期定期開格、被叫醒時開格，外加可選的覆蓋上層。**

- 登記不是 tick 存在的前提。上下層預設由資料夾決定（[B-628](tick.md)），登記只影響 daemon 的開格安排與覆蓋。
- 「排程」一詞留給任務表上的排程程式（B-601）。

### 上層怎麼定

- **預設看資料夾**：從本 node 的資料夾往上，最近一個有 tick 的資料夾就是上層（判準與路徑比對見 [B-628](tick.md)）。
- 〔建議預設〕不論預設或覆蓋，**有效上層都必須已在同一個 daemon 登記**，否則回 `not_registered`。所以沒有覆蓋時，資料夾推得的上層沒登記就登記不了。
- **覆蓋**：登記時帶 `parent_id` 指定別的上層，就蓋過預設。覆蓋存在 daemon 的登記裡，不在 daemon 底下的 tick 沒有覆蓋。
- **覆蓋要新舊兩個上層都同意**：
  - 〔建議預設〕舊上層是**目前的有效上層**：新登記或第一次覆蓋時是資料夾推得的那個；已覆蓋過再換時是目前覆蓋的那個（資料夾推得的那個不必再同意，它第一次覆蓋時已同意過）。
  - 新上層是 `parent_id`；拿掉 `parent_id` 回到資料夾時，就是資料夾推得的那個。
  - 呼叫者必須同時是兩者的 owner 或祖先 owner。帶憑證時，憑證所屬的 tick 必須同時是兩者或兩者的上層鏈上的一個。
  - 舊上層推不出來，或沒在這個 daemon 登記（例如 cron、人手跑的）時，aos 管不著它，**只要新上層同意**（第十九批疑點裁定 11）。
- **覆蓋只改管理關係**：覆蓋後的上層負責分資源（有 cgroup 時，框也放在它的框下，B-605）、叫醒、解除與佈建授權。**管轄權仍跟著資料夾**，資料夾上層對那個資料夾的檔案仍有最高裁量。
- 〔暫定〕daemon 在登記時解析一次有效上層並記下。之後有人在中間的資料夾新開、登記 tick，daemon 不自動改這筆的上層，要改就照下面的換父。同一筆重送時解析結果不同，當成換父處理。
- **頂層**只從設定載入，有效上層是 null。〔建議預設〕這算部署者在設定裡做的覆蓋，不是取消資料夾上層：
  - 資料夾上層沒在這個 daemon 登記（例如 `/a` 由 cron 跑、設定只列 `/a/b`）時，照上面的疑點裁定 11 直接成立：daemon 底下 `/a/b` 是頂層，管轄權仍跟著資料夾（`/a` 對 `/a/b` 的檔案仍有最高裁量），直接跑的核心照資料夾仍算出 `/a`（[B-628](tick.md)）。
  - 資料夾上層已是這個 daemon 裡的登記（另一棵 root 或它底下的 node）時，部署者沒辦法替它同意，整份設定不收（`config_invalid`；熱重載照 [B-608](#b-608熱重載與免重開要重開) 不套用）。〔暫定〕設定裡兩棵 root 的資料夾互相包含，就是這一種。
- 身分繼承（inst 的 `user` 省略時繼承上層）跟**有效上層**，見 [inst](../base/inst.md)。

### 新登記

- 頂層只從設定載入（增刪走熱重載，B-608）。其餘 node 由有效上層的 owner 或祖先 owner 經 `node.register` 登記（帶憑證時，由有效上層那個 tick 或它的上層鏈上的 tick 登記）。首次必須有上層同意，本版不提供首次自登記。
- 新登記不自動啟動：上層 kernel 重建子 kernel 時明確再送 wake；頂層由 daemon 自動各排第一格。
- 每筆登記保存授權時解析出的 `owner_uid`。改 inst 不立即改掉 owner；有效的下一格身分採用、或經原 owner／上層授權的重新登記才更新。
- inst 尋找依 [inst](../base/inst.md)。登記的 node 必須是資料夾（單檔 inst 要用掛載行程，B-613）。〔astra 審整理區必-8 從 P-101 搬上〕找不到 inst 時：設定檔裡的頂層算用法錯（daemon 回 2、不啟動）；IPC 登記回 `invalid_params`，daemon 照常跑。同一個 id 不能同時是登記又是掛載行程，衝突回 `registration_conflict`。

### 登記識別與別每格重登

- 每次新登記（首次登記、解除後再登、換父、daemon 重啟後讀回或重建）daemon 配一個新的 `registration_id`；同一筆登記的重送與內容更新不換。
- 〔使用例：kernel 那側，正本在 [S-202](../scheduling/admission.md)〕kernel 在自己的 repo 記下成功同步的 boot id 與成員版本，每格只比對小查詢；兩者沒變且無待修復差異就不重登。重開、清單改變或已知解除時才補差異，並叫醒子 kernel 逐層重建。失敗筆不標成功、不擋其他成員，也不重送結果不明的掛行程。kernel 那側何時登記成員見 [S-202](../scheduling/admission.md)。

### 身分額度

額度的每一項可以是（第十八批；推翻第十一批「不支援萬用名稱」）：

| 寫法 | 意思 |
|---|---|
| 帳號名稱（字串） | 確切名稱；可預授尚未存在的名稱，只能由設定往下傳 |
| UID（整數） | 確切 UID |
| `{"prefix":"aos-"}` | 名稱以這個前綴開頭的帳號（比名稱，不比 UID） |
| `{"uid_min":N,"uid_max":M}` | UID 在 N～M 之間（含兩端，N ≤ M） |

- 一律排除 UID 0 與 root 別名；前綴與範圍規則也一律不涵蓋 UID < 1000 的系統帳號。
- 名稱與 UID 別名不得重複。帳號第一次被建立（或第一次經前綴比中）後，daemon 綁住名稱與得到的 UID；之後同名卻是別的 UID 回 `user_mismatch`，不能接管同名帳號。
- 〔暫定，astra 審整理區設-4〕**這個綁定只在本次 daemon 存續期內有效**：只放記憶體，不存進 `state.json`。daemon 停著的時候帳號被刪掉又用同名重建，重開後會照新的 UID 重新綁定、接受它。要防這種情形，就在 daemon 停著時不要刪建額度內的帳號，或在額度裡寫確切 UID。
- **子額度必須被上層額度包含**（這裡的上層是有效上層）：
  - 確切名稱或 UID 要落在上層的某一項裡（解析成名稱比前綴、解析成 UID 比範圍）；
  - 前綴要以上層的某個前綴開頭；範圍要落在上層的某個範圍內；
  - 前綴與範圍之間互不算包含；
  - 佈建權的動作集合、路徑、群組同樣只能是上層的子集（B-609）；
  - 整條鏈的上限仍受頂層啟動設定限制。
- 新 node 的 inst user 在登記時必須已存在，不存在就回 `user_invalid`，不延到 wake 才擋（wake 時仍重新解析一次）。額度不是允許 impersonate 呼叫者的欄位。
- 任務要用別的帳號跑，要包 `aos-as`，那個帳號也要落在這個 node 的額度內，由 daemon 在 `spawn_as` 核（B-609）。任務表只寫 `user` 而沒包 `aos-as` 的，核心那一項回 125、不會來問 daemon（[B-620](tick.md)；第二十批疑點裁定 6）。

### 重送與更新

- 有權者重送相同有效登記回成功，不清 paused／pending、不再啟動。
- 既有項內容不同時，由原 owner 或祖先 owner 更新：`interval_ms` 從下一次到期開始算。
- 擴大額度或佈建權只能由上層在自身授權內下授，即時生效。
- 縮小即時生效；已往下授出去的子孫若因此超出，下一格授權檢查不過就照 B-607 停格並寫事項，不自動收回、不回 `busy`。
- 更新不重跑已開始的 attempt（第十八批 Q8）。

### 換父

換上層有兩條路（第十九批改寫第十八批審稿裁定 6 與 Q10）：

1. **搬資料夾**：把 node 的資料夾搬進別的 tick 的資料夾，新位置最近的那個自動成為上層。路徑就是 id，所以等於舊 id 解除、新 id 重登：先由舊上層照下面的解除收掉舊 id，搬完再由新上層以新 id 登記。引用舊路徑的回址會失效，風險自負（[T-03](../terms.md)）。
2. **改登記**：用同一個 `node.register` 讓有效上層變成別人——帶不同的 `parent_id`，或拿掉原本的 `parent_id` 回到資料夾推得的上層。已登記子樹跟著搬。

兩條路共同的條件與效果：

- **條件**：被搬的 node 與整棵已登記子樹都已暫停且程序全空，否則 `busy`（沿第十八批 Q10）；新上層不能在被搬的子樹裡（成環回 `registration_conflict`）；頂層不能換父。
- **授權**：新舊兩個上層都同意（同上面的覆蓋）；額度與佈建權要被新上層包含。
- **效果**（改登記那條）：子樹跟著搬，暫停狀態保留，由呼叫者 resume；被搬的每筆登記換新 `registration_id`，格次序號從頭算。有 cgroup 時收掉舊框、在新上層的框下重建：上限要由新上層的 kernel 重寫，用量歸零。
- 舊上層 kernel 要先把它從成員清單拿掉，否則下一格同步又會以舊上層登記回去（[P-802](../protocol/kernel-tasks.md)）。

### 解除

- `node.unregister` 立即阻止目標及已登記子樹的新格，對整個範圍做 B-604 的收尾。
- 確認全空後刪登記、丟掉它在通道上的暫存訊息（B-614）、回成功。有 cgroup 時另外由下往上刪框（框已交給別的帳號時經 helper 刪）；框裡還有逃生口時照 B-605，框留著、寫事項。無法清空回 `cleanup_failed`，保留阻擋狀態。
- 自己在 tick 內同步等自身解除會被收尾，呼叫者不得依賴收到成功才能退出；通常由上層發起。
- 持久停用仍由上層 kernel 改自己的成員設定（B-604）。
- 掛載行程不用解除，用 `node.kill`（B-613）；對掛載行程送 `node.unregister` 回 `kind_mismatch`。

### once

once 不再是登記的一種，是任務自己經通道呼叫的事務。daemon 那一側是通道上的掛行程與砍掉，見 [B-613](#b-613掛行程與砍掉)（第十九批；第二十批改寫）。

依據：使用者方向 2026-09-29；第十八批改寫（行為從 P-104／105 搬上）；第十九批（登記可覆蓋上層、換父兩條路）；第二十批換詞。

**驗收：**偽造 payload 帳號不能登記別人的資料夾；子額度寫成上層沒有的前綴或更大的範圍被拒；前綴規則比不中 UID < 1000 的帳號；不帶 `parent_id` 登記時，上層是 [B-628](tick.md) 推得的預設上層；它不在這個 daemon 登記時回 `not_registered`；帶 `parent_id` 覆蓋、資料夾上層在這個 daemon 登記時只有一方上層同意被拒，資料夾上層由 cron 跑、沒登記時只要新上層同意就收；覆蓋成 B 再換 C 時要 B、C 同意，資料夾上層不必；設定只列 `/a/b` 而 `/a` 是 cron 跑的時 `/a/b` 照常當頂層載入，`/a` 已是另一棵 root 的成員時整份設定不收；覆蓋後資料夾上層的檔案權限不變；換父時子樹沒停或新上層在子樹裡被拒，搬好後有效上層是新的、`registration_id` 換新，有 cgroup 時框也在新上層的框下；搬資料夾後舊 id 解除、新 id 由新位置的上層登記；解除在跑的 node 時寬限後它的程序全被清掉、登記被刪；縮小中間 node 的額度後，超出的子孫下一格停格並有事項。

## B-607：叫醒、暫停、故障停格與格次序號

method 形狀見 [P-105～106](protocol/daemon/registration.md)。

### 定期與叫醒

- `interval_ms` 是一格的標準長度，屬外部規定、保留毫秒（[C-01](../contracts.md)）；上下層週期不同造成的落差不管（第二十批追答 1、4）。
- 定期 node 從登記完成起經過 `interval_ms` 才到期；每次完整收尾後重新計時，不補跑漏掉的格數。
- `node.wake` 要求現在跑一格，把本次到期提前：
  - 正在跑時合併成一個 pending；
  - paused 時只記 pending；
  - 停機中（`stopping`）拒絕，排空中照收（B-604）。
- wake 成功不是已開跑或工作完成證據。
- tick 可以經通道叫醒別的 tick（B-612）；急件訊息由 daemon 代為叫醒（B-614）。
- 對掛載行程送 wake、pause、resume 回 `kind_mismatch`。

### 暫停與恢復

- `node.pause` 只停**該 node** 的新格，不殺本格、不遞迴暫停子樹；回成功代表閘門已關。
- 要手改：先 `node.pause`，再用 `node.show` 看 `running:false`（包括後代清理期間），再持 node 鎖、修改。
- `node.resume` 只開該 node 的閘門；呼叫者先照 [B-625](tick.md) 做恢復前驗證。daemon 不替手改做驗證，也不替 unknown 工作重試。有 git 時，手改要保住就自己提交（[B-602](tick.md)「tick 外的寫入者」）。
- pending 或到期才開格。pause／resume 同狀態重送無害；它們是關／開閘門，不等於 wake。保存依 B-603 的批次存檔。

依據：第十批；納入 cgroup 與 git 疑-3（人手改的不管，要保住自己提交）。

### 故障停格

**daemon 不看任何結束碼，也不看停格檔；tick 那一側要擋住之後的格，只靠擋板檔。** daemon 自己開不了或收不完一格時，才自動停格。

| 情況 | daemon 怎麼做 |
|---|---|
| tick 回任何結束碼（含 3、100、125） | 照普通結束處理，不停格 |
| tick 回 75（鎖被占，例如有人手正在直接跑同一個資料夾，[B-602](tick.md)） | 普通結束：不停格、不寫事項，pending 照留，收尾後照常再開下一格 |
| 停格檔 `.aos/tick/stop` | 不看。它只在任務層面，是 tick 核心停掉本格其餘各項（[B-620](tick.md)），daemon 不因它暫停 node |
| 擋板檔 `.aos/tick-blocked` 在 | 不開這一格（下面細說） |
| daemon 自己的開格故障 | 停格（下面細說） |

**擋板檔 → 不開格**：

- daemon 每次要開格（到期或有 pending）前先看它在不在；在就**不開這一格**：不設 `paused`，pending 照留，到期照下一個週期再看；同一個擋板只寫一次事項。
- 擋板拿掉後，下一次到期或叫醒就照常開格。
- daemon 只看擋板檔在不在（stat），不讀內容。〔建議預設〕daemon 看不到（例如權限不足）時當成不在，stdout 警告一行。
- 〔建議預設〕擋板由任務或人手建（內容是 UTF-8 原因），**只由人手刪**：修復者核對好了才移除；daemon 與 tick 核心都不刪它。

**daemon 自己的開格故障 → 停格**（當成 daemon 對自己開格的安全閘）：runner 前置失敗（`launch_failed`，例如身分不在額度內、來源變了）、缺可信回報（`unknown`）、後代清不空。這些不是 tick 的結束碼，是 daemon 開不了或收不完這一格；不停的話每個週期都會再失敗一次。

**停格時怎麼做**：

- daemon 先設 `paused:true`，再處理 pending／到期。
- 寫該 node 的 `.aos/attention/`（格式見 [P-601](../protocol/ops.md)，處理見 [S-405](../scheduling/operations.md)）；不解析 stderr、不靠 tick 再發 IPC。事項寫不出就 stdout 警告，不阻止停格。
- 要不要恢復、何時恢復由上層或人決定。手動 pause 與自動停格使用同一閘門；resume 前修復者須清後代、持鎖核對；擋板要另外由人手移除。

**事項批次寫出**（從 P-601 搬上）：daemon 產生的事項（自身的、要寫進 node `.aos/attention/` 的）先暫放記憶體，每 1000 ms 批次寫出，寫完就從記憶體清掉；重開後不讀回記憶體。事項檔的位置與格式見 [P-601](../protocol/ops.md)。

依據：第二十批疑點「daemon 何時暫停 node」裁定（取代第十九批「可信子程式退出 `3`／`125` 保留為停格碼」）、第二十批（開格故障仍停格，當安全閘）；第十九批（75 當普通結束）；使用者方向 2026-09-29（事項批次）。

### 最近一格與格次序號

- daemon 為每筆登記只保存最近一格（欄位見 [P-106](protocol/daemon/registration.md)）；新格派出時取代前格，不是完整歷史。
- 每開一格，這筆登記的 `tick_seq` 加 1，從 1 起算。配上 B-606 的 `registration_id`，就是「第幾格」的依據，不用牆鐘排序或推算逾時。
- `tick_seq` 只用在「叫醒後等新格」，跟 tick 核心結束碼紀錄裡的格數 `seq`（[B-633](tick.md)，跨重啟不倒退、沒 daemon 也有）是兩回事。aos 內部以格計的時長一律數 `seq`，不數 `tick_seq`（做法見 [C-01](../contracts.md)）。〔暫定〕唯一例外是 daemon 記憶體裡的掛載診斷保留期（B-610）：daemon 不讀 node 的檔，只數得到自己開的格，而且那筆診斷跟 `tick_seq` 一樣重啟就沒了。

**怎麼等「wake 之後新的一格做完」**：

1. 記下 wake 回應的 `registration_id` 與 `tick_seq`；
2. 之後 `node.show` 看到 `registration_id` 相同、`last_tick.tick_seq` 較大且 `outcome` 不是 `running`，就算做完；
3. `registration_id` 已改變，表示舊登記已結束（解除、換父或 daemon 重啟），要重新核對，不再等舊的那格。

人手「經 daemon 跑一格」就用 wake 加上面的等法，不另開 method。人手或 cron 也可以直接跑 `aos-tick`，風險自負；那一格沒有通道，daemon 也不知道（[B-627](tick.md)）。

依據：第十八批；第十九批（直接跑）；第二十批（`seq` 與 `tick_seq` 分開）。

### 最近一格怎麼判

〔建議預設；第十九批從 P-106 搬上〕

| `outcome` | 意思 |
|---|---|
| `running` | 還在跑；後代清不空時也算 `running:true`、`outcome:running`，另以 `stopping:true` 與事項暴露故障，不能先記成已完 |
| `completed` | 可信回報 started:true 且收尾完成；可以是非零，絕不等於業務成功。已放行後程式自己回 125 也是 `completed` |
| `launch_failed` | 可信回報 started:false。身分拒絕的 125 是這種（仍可能已有開檔副作用） |
| `unknown` | 沒有可信回報或 `FinalizeFailed`；不從 runner 的 wait 碼猜業務退出碼 |

- `started_at_ms` 是 daemon 接受開格、進入啟動流程的時間，不是程式已開始的證據。
- 時間可能受牆鐘校正影響，排格數用 `tick_seq`。

### 查詢

〔建議預設；第十九批從 P-106 搬上〕

- `node.show` 不開 tick。
- `cgroup`：沒有 cgroup、或這個 node 退回沒有框時為 null（B-605）；有框時回實際讀到的配置，不是上次請求的快取。應存在卻讀不到回 `resource_observation_failed`，不能回 null 冒充沒配置。
- `node.ls` 先按呼叫者權限篩，再分頁；只列有權看的，不洩漏總數或無權項。
- 分頁：不同頁不是同一瞬間的快照。每次接續用剛收到、嚴格前進的游標；`boot_id` 變了就從頭列；要核對單項用 `node.show`。持續變動時不追補游標之前新插入的項，免得無限追列。一頁裝不下就縮頁，單項就超過封包上限回 `response_too_large`。
- 畫面要把「已結束的掛載行程」「未啟動」「還在跑」「結果不明」分開。

**驗收：**定期 node 不補跑漏掉的格；運行中收到多次 wake 只多跑一格；pause 不遞迴；tick 回任何結束碼（包括 3、100、125）都不停格；某格的任務建了 `.aos/tick/stop`，daemon 不暫停、下一格照常開；node 有 `.aos/tick-blocked` 時到期與叫醒都不開格、`paused` 不變、只有一件事項，人手刪掉擋板後下一次到期照常開；身分不在額度內的開格失敗後自動停格、有事項；wake 後等到 `tick_seq` 前進且不是 running 才算新格做完，daemon 重啟後 `registration_id` 改變。不同 UID 只能列自己的授權子樹；未跑顯示 `last_tick:null`；分頁跨重啟能靠 `boot_id` 發現。

## B-608：熱重載與「免重開／要重開」

**改設定、改樹不必重開 daemon**：除了重大或危險的操作要重開，其餘都盡量免重開（第十八批）。原本叫「即時改」，第二十批改叫「免重開」，免得跟「反應速度就是一格」（[T-07](terms.md)）的「立刻處理」混；行為不變。

### 熱重載怎麼做

daemon 只在收到 **SIGHUP** 時重讀啟動時的同一份設定檔。能送訊號的只有同帳號或 root；不開 IPC、沒有 CLI 子命令（人手用 `kill -HUP`）。

1. 讀新設定並驗證整份；
2. 跟目前設定比對差異；
3. 依下表套用免重開的，其餘不套用。

| 情況 | 怎麼辦 |
|---|---|
| 新設定讀不進來或不合 schema | 整份不套用，舊設定繼續用；stderr 說明並寫 daemon 事項（`config_invalid`） |
| 有「要重開」的欄位改了 | 免重開的照套，這些欄位不套用；stdout 列出並寫 daemon 事項（`restart_required`），直到重開或改回為止 |
| 不認得的欄位 | 照 [C-07](../contracts.md) 忽略並印出名字 |
| 停機或排空中收到 SIGHUP | 不重載，印一行警告 |

每次重載在 stdout 印一行，列出已套用與要重開的欄位。

**helper 的界線**（第十八批）：helper 在 fork 前固定一份設定副本，用它核對頂層額度（B-601）；重載不改 helper 那份。所以牽涉 helper 的欄位——**通用 user 以外帳號的身分額度、佈建權**——改了仍要重開。要少重開，就在啟動設定用前綴或範圍一次授出夠大的範圍（B-606）。

### 設定項

| 設定 | 改了怎麼辦 | 說明 |
|---|---|---|
| `version` | 重載時照樣檢查 | 版本不同整份不收（`config_invalid`） |
| `common_user` | **要重開** | daemon 已永久變成這個帳號，換帳號等於換一個 daemon |
| `socket_path` | **要重開** | 連線全斷、各 kernel 記的位置與已開 tick 的通道變數都會失效；防雙開的鎖在 socket 目錄 |
| `state_dir` | **要重開** | 恢復資料在舊位置，也是排他鎖的對象（B-611） |
| `cgroup_root` | **要重開** | 程序要跨子樹搬家，需要 root；也是排他鎖的對象（B-605、B-611） |
| `create_cgroup` | 改了沒效果 | 只在啟動時有用 |
| `pause_save_interval_ms` | 免重開 | 下一次存檔用新值 |
| `shutdown_grace_ms` | 免重開 | 只影響之後才開始的收尾 |
| `stop_mode`、`drain_timeout_ms` | 免重開 | 下一次停機用新值 |
| `kill_escape_cgroups` | 免重開 | 之後才開始的重啟清空與解除登記用新值（B-605） |
| `mount_diag_max`、`mount_diag_ttl_ticks` | 免重開 | 下一輪淘汰用新值（B-610） |
| `disable` | 免重開 | 只影響之後的 quota 動作，已設好的歸屬不收回；重新打開時再偵測一次 |
| roots：加一棵 | 免重開；額度含通用 user 以外帳號或帶 `provision` 的**要重開** | 等於一次沒有上層的登記加一次 wake |
| roots：刪一棵 | 免重開 | 走 B-606 的解除；清不空就一直擋著並寫事項 |
| roots：`node_id` 改名 | 當成刪一棵加一棵 | 舊的那棵要收尾 |
| roots：`interval_ms` | 免重開 | 從下一次到期開始算 |
| roots：`identity_grant` | 只動通用 user 的免重開；動到其他帳號（含前綴、範圍）的**要重開** | 重開後依 B-603 重核讀回的登記；超出的子孫照 B-607 停格 |
| roots：`provision` | **要重開** | helper 核對的是啟動時那份 |
| 有沒有 helper（用不用 sudo 開） | **要重開** | 拉起 helper 需要 root |
| 啟動旗標 `--firstdo-fsync`、`--create-cgroup` | **要重開** | 旗標只在啟動時讀（[B-633](tick.md)、B-605） |

寫死、不開放成設定的：IPC 封包上限 256 KiB、`node.ls` 每頁 64 筆、socket 權限預設值、最低版本、通道的暫存上限與單件上限（B-614）。版本檢查只在啟動時做。

### 操作

| 操作 | 免重開／要重開 | 說明 |
|---|---|---|
| 啟動 `aos daemon` | — | 啟動自檢、取鎖、清空舊程序都只在這時做 |
| 立即停、排空停 | — | B-604 |
| 熱重載（SIGHUP） | — | 本條 |
| `daemon.info` | 免重開 | 查本次啟動 ID |
| `node.register`：新登記、重送、更新、覆蓋上層、換父 | 免重開 | B-606；換父只要求被搬的那棵先停 |
| `node.unregister` | 免重開 | B-606 |
| `node.wake`、`node.pause`、`node.resume` | 免重開 | B-607 |
| `node.mount`、`node.kill` | 免重開 | B-613 |
| `node.send`、`node.take` | 免重開 | B-614 |
| `node.show`、`node.ls` | 免重開 | 最近一格含格次序號 |
| `mount.clear` | 免重開 | B-610 |
| `node.provision`（含 helper 新動作、改 cgroup 上限） | 免重開 | B-609 |
| `daemon.attention.*` | 免重開 | [P-601](../protocol/ops.md) |
| helper 被 kill 之後恢復特權操作 | **要重開** | 需要 root 才拉得起來（[B-303](helper.md)） |

要重開的共同原因：一改就等於換了 daemon 的身分、恢復資料、整棵資源樹，或 helper 的授權依據，而且大多要 root 才做得到。其餘最多只要求被動到的那一棵先停下，不影響別的樹。

**驗收：**SIGHUP 後改 `interval_ms`、加一棵只用通用 user 的 root 免重開就生效；改 `socket_path` 或 root 的其他帳號額度時其餘照套、這些欄位回報要重開且不生效；壞設定整份不套用、舊設定照跑；非同帳號送不了 SIGHUP。

## B-609：佈建固定動作與 helper 動作

**`node.provision` 每次只做一件固定動作。** helper 與佈建動作屬 daemon（第二十批）；helper 的角色與界線以 [B-303](helper.md) 為正本。參數見 [P-107](protocol/daemon/provision-and-runner.md)，helper 私有通道見 [P-108](protocol/daemon/provision-and-runner.md)。

- `spawn_as` 給普通程式 `aos-as` 用（[B-303](helper.md)）。
- `cgroup_limits` 是唯一的 cgroup 動作：有 cgroup 時照做，沒有時回 `unsupported`。原本的 `cgroup_create`、`cgroup_delegate` 撤，改由 daemon 開格前自己建框、交框（B-605；納入 cgroup 與 git 疑-10）。

依據：使用者方向 2026-09-29；第十八批加動作（行為從 P-107 搬上）；納入 cgroup 與 git 疑-10（建框、交框改由 daemon 自動做）。

### 通則

- 不提供 shell、argv、任意 syscall 或任意 mount options。
- 授權、允許的路徑與群組都取**該 node 的登記**（`provision` 的 `actions`、`paths`、`groups`），執行端不信封包自報。
- 路徑按元件判定、不用字串前綴；helper 固定目錄 handle、拒絕 symlink 穿越及替換競態，逐步核對實體路徑。
- OS 現況已符合就核對後成功，不同回 `conflict`、不覆蓋。
- 做完並驗證才回成功，不能把已送 helper 當完成。沒有跨步回滾：斷線或中途失敗須先核對 OS 事實，不能盲重送或自動「撤回」。
- 首次建 node 前，可先用上層 node 的佈建權在授權路徑建立必要權限與帳號，再登記成員；建帳號不擴大額度。

### 動作

| 動作 | 做什麼 | 要 helper |
|---|---|---|
| `account_create` | 建一個非 root 帳號及同名主群組；名稱要落在額度的確切名稱或前綴裡、尚未存在（範圍規則不能授權建帳號）。無登入 shell、不建 home、不收密碼；建好後綁住 UID（B-606）。已存在且符合綁定就核對後成功 | 要 |
| `chown` | 單一路徑改為額度內既存帳號與其主 GID；不遞迴、不收任意 GID、不跟隨 symlink | 要 |
| `cgroup_limits` | 寫 `n-<h>` 的 CPU、記憶體、程序數上限，作用於整個分支含後代；只寫這些 controller，不設就不新增該項限制。細節見下面「cgroup 上限」；沒有 cgroup（或這個 node 退回沒有框）回 `unsupported` | 不要 |
| `quota` | 只配置該路徑的 project **計量歸屬**，不設磁碟硬上限或 soft limit；不搶走其他 node 的歸屬 | 要 |
| `group_create`〔第十八批〕 | 建一個系統群組；名稱要是確切名稱，且落在登記 `groups` 授權的名稱或前綴裡 | 要 |
| `group_add_member`〔第十八批〕 | 把額度內的一個帳號加進授權的群組；只對之後新開的程序生效 | 要 |
| `chgrp`〔第十八批〕 | 把單一路徑改成授權的群組；不遞迴、不跟隨 symlink，路徑要在 `paths` 內 | 要 |
| `spawn_as`〔第十九批疑點裁定 10；第二十批改呼叫者〕 | 以指定帳號開程序：替 `aos-as` 用它指定的帳號開原指令，那個程序繼承本格的鎖 fd；限制與放法見下面 | 要 |

其他：原有的 `mount`（helper 掛 tmpfs）首版拿掉，暫存就在磁碟（使用者方向 2026-09-29 晚）。不加遞迴改群組與 chmod／setgid（第十八批 Q21）。多帳號交接首版只用群組，不用 ACL。

### cgroup 上限

〔使用者方向 2026-09-30，第十八批；拿掉「整棵子樹全空才改」〕

- **隨時改**：`cgroup_limits` 調高、調低都隨時寫，不關閘門、不等全空；同一框的寫入依序做。已是相同值就核對後成功，不重寫。改限制值不算中途換資源範圍（[B-302](../base/identity-resources.md)）。
- **調低超過現用量**：由 Linux 自己處理（例如記憶體回收或 OOM、新 fork 失敗），aos 不擋；要記一筆的是下指令的 kernel，記在它自己的資源狀態檔（[S-203](../scheduling/admission.md)）。
- **controller 往下開**：要在子 node 上寫上限，上一層的 `cgroup.subtree_control` 要開 `+cpu +memory +pids`；daemon 建框時就開。某個 controller 不在（例如使用者層 systemd 沒委派 `cpu`），那一項回 `unsupported`，其餘照用。
- 上層 node 帳號關掉自己框的 controller，等於撤了自己子 node 的上限；這在它的權限內，不是逃脫，祖先對整棵分支的上限照樣有效（B-605）。

### 以指定帳號開程序（`spawn_as`）

tick 核心不呼叫它；呼叫者是**帶本格憑證的程序**，實際上就是任務 argv 裡包的 `aos-as`（[B-303](helper.md)、[P-212](protocol/node.md)）。參數見 [P-107](protocol/daemon/provision-and-runner.md)。daemon 這一側的規則（誰能叫、帳號限制、開什麼、回傳）不因呼叫者換人而變。以下做法為〔建議預設〕。

- **誰能叫**：只收通道上帶憑證的請求，`node_id` 必須就是憑證所屬、登記中的 node。掛載行程叫回 `kind_mismatch`，不帶憑證回 `forbidden`。不看登記的 `provision` 授權，看的是身分額度。
- **帳號的限制**：`user` 必須落在這個 node 的身分額度內（B-606 的規則，排除 UID 0 與 root 別名），不合回 `user_not_granted`，不存在回 `user_invalid`；不能用它建帳號。沒有 helper 回 `helper_unavailable`；排空或停機中回 `stopping`。
- **開什麼**：`path` 必須是這個 node 資料夾裡 `.aos/jobs/` 下的一般檔（`aos-as` 寫好的那份 inst，檔名由它定，見 [P-212](protocol/node.md)），逐段核對、不跟隨 symlink。daemon 取它的不可變快照，連同這個已核准的路徑交給 helper（`daemon.helper.spawn` 的 `path`，[P-108](protocol/daemon/provision-and-runner.md)）。helper fork、降成該帳號、exec 固定 aos-runner，以這個路徑當 `--target`；runner 照 B-601 核對原來源的 bytes 跟快照相同（不同回 `source_changed`），再照 [inst](../base/inst.md) 跑。不收 argv、env 或輸出路徑。〔暫定〕這份暫存 inst 要讓目標帳號讀得到（例如用 B-609 的群組動作），讀不到就是前置失敗。
- **鎖與 fd**：請求同包交來 5 個 fd：鎖 fd、回報 pipe 的寫端，以及 `aos-as` 自己的 stdin、stdout、stderr。
  - helper 以 fstat 核對鎖 fd 就是這個 node 的 `.aos/tick.lock`，不符回 `invalid_params`。
  - runner 與它開的程序繼承這份鎖 fd（同一個 open file description），照 [B-602](tick.md) 核對。
  - 〔第二十批，建議預設〕runner 以交來的三個 stdio fd 當自己的 stdin／stdout／stderr（不收集成 `.aos/runner-stderr.log`），原指令照那份 inst 寫的 stdio 走，所以輸出照任務表寫的去處。
  - **環境最後才補**〔暫定，astra 審整理區必-2〕：runner 照 inst 的 `envs` 建好子程式環境之後，最後才放進 `AOS_TICK_LOCK_FD`（runner 收到的鎖 fd 的新號碼；fd 經 SCM_RIGHTS 傳過來號碼可能變了）與這一格的兩個通道變數（B-612）；這三個不受 `clear` 影響，inst 裡寫了同名的也被蓋掉。所以 `aos-as` 寫的 inst 裡不放它們（[B-303](helper.md)），憑證不會落到磁碟上。
- **放在哪**：runner 是 helper 的子程序，不掛回 tick；它名下的程序照 B-601 由它自己清空：原指令結束後先清空、再寫回報。清不到的還握著鎖 fd 時，下一格回 75（[B-602](tick.md)）。
  - **帶 `frame`**（有 cgroup 時）：`aos-as` 在 `aos-cg` 開的 `task-<seq>-<pid>` 框裡時（寫成 `aos-cg -- aos-as <帳號> -- 原指令`，[B-634](tick.md)），請求帶 `frame`＝那個框。helper 核對它是本 node `n-<h>` 的直接子框、存在且沒有程序，把 runner 放進去再 exec。框仍歸 node 的帳號，`aos-cg` 照 B-634 等它清空、必要時 `cgroup.kill`。
  - 沒帶 `frame`、daemon 有 cgroup 時，runner 放進本 node 的 `tick` 框，格後收尾一起收（B-601）。
  - 沒有 cgroup 時帶了 `frame` 回 `unsupported`。
- **回傳**：runner 開起來就回 `{node_id}`，不等它結束；前置失敗回錯、不開程序。結束碼不經回應：runner 把 [P-110](protocol/daemon/provision-and-runner.md) 的那一行回報寫進 `aos-as` 交來的 pipe，`aos-as` 讀到 EOF 為止、照它結束。回應說成功、pipe 卻沒有回報就關了，這一項算失敗、結果不明，不重跑。
- **daemon 不記這個程序**：不進登記表、不留 B-610 的診斷、不發新憑證，也不能對它送 `node.kill`。helper 記下這個 runner 屬於哪個 node；daemon 收尾那個 node 時，helper 對它做 B-604 的收尾。
- **呼叫方不在了**〔暫定，astra 審整理區設-3〕：取消或逾時由呼叫的一方對 `aos-as` 做（它收到 SIGTERM／SIGINT 就結束）。`aos-as` 一結束，回報 pipe 的讀端就關了；runner 發現讀端關了（對寫端 poll 看到錯誤），照 B-601 立刻清空名下的程序、結束，不再寫回報。
  - **這一項什麼時候算結束**：對核心來說是 `aos-as` 結束的時候，所以下一項可能在 runner 清空之前就開了；這段時間裡原指令還握著鎖 fd，同資料夾的下一格拿不到鎖（回 75），但本格的下一項可能跟它短暫重疊。要避免，呼叫方應等 `aos-as` 自己結束，不要中途殺它。

依據：第十九批疑點裁定 10（握著鎖的一方經 helper 以別的帳號開、那個程序只需知道開它的那一格仍握著鎖）；第二十批追答 8、疑點裁定 6（呼叫者從 tick 改成普通程式 `aos-as`）；納入 cgroup 與 git 改寫計畫（`frame`）。

### daemon 自己做的與 helper 做的

- daemon 自己做得到的就自己做，不經 systemd；無 helper 時用通用 user 做，授權和上層限制照舊。
- 凡是要動到不屬於 daemon 帳號的檔或程序（其他帳號、群組、quota、以別的帳號開程序與收尾），才經 helper；無 helper 回 `helper_unavailable`。
- daemon 與 helper 自己留在成員限額之外。
- **有 cgroup 時**：daemon 在交給它的子樹內自己建框、寫限制、讀實際值，不經 systemd。框要交給別的帳號、或上層框已交給別的帳號時，建框、交框、刪框才經 helper。helper 另有兩個只給 daemon 用、不開放給 `node.provision` 的內部動作（[P-108](protocol/daemon/provision-and-runner.md)）：
  - **建框並交框**：在可信上層框下建本 node 的 `n-<h>` 與 `tick`，交給這個 node 目前的執行帳號（B-605）；路徑由登記推導，不收呼叫者給的 cgroup 路徑。
  - **刪殘留框**：只刪子樹內、名字是 `n-*`／`mount-*`／`task-*`、已經沒有程序也沒有子框的框（B-603、B-606）。

**驗收：**每個動作超出授權路徑、群組或額度都被拒；`aos-as` 開的原指令印出的環境裡 `AOS_TICK_LOCK_FD` 是它實際拿到的 fd 號碼、有本格憑證，而 `.aos/jobs/` 那份 inst 裡沒有憑證；暫存 inst 在授權後被改掉時回 `source_changed`；`aos-as` 被 SIGTERM 後，原指令也很快被清掉，下一格拿得到鎖，OS 現況不符回 `conflict`；多帳號部署下能靠這些動作讓兩個 node 帳號經共享群組交接檔案；沒 helper 時要 helper 的動作回 `helper_unavailable`；沒有 cgroup 時 `cgroup_limits` 回 `unsupported`，有 cgroup 時有程序在跑也能調低記憶體上限並立即生效；`spawn_as` 帶 `frame` 時開起來的程序在那個 `task-*` 框裡；`spawn_as` 帶額度外的帳號被拒；`aos-as` 帶本格憑證呼叫時，額度內的帳號開起來的程序以 `AOS_TICK_LOCK_FD` 核對得到獨占鎖，輸出走 `aos-as` 交來的 stdio，結束碼經回報 pipe 回到 `aos-as`；不帶憑證、由掛載行程叫、沒有 cgroup 卻帶 `frame`、附的 fd 不是 5 個都被拒。

## B-610：掛載行程的診斷：留存、淘汰與清除

**掛載行程結束後，daemon 在記憶體留一筆最近結果，只供查詢。**

### 留存

- 掛載行程（B-613）結束或被砍掉、收尾完成後，daemon 在記憶體留一筆 `registered:false` 的最近結果，保留原 `owner_uid`、`parent_id` 與 `registration_id`。
- 只供 `node.show`／`node.ls`；`node.kill`、wake、pause、resume 都回 `not_registered`。
- 查詢時以**目前仍在的可信上層鏈**重驗；祖先權限撤銷即生效，不能靠舊祖先快照繼續讀。
- 不寫檔、不算正在占用的登記；登記的 node 被解除不留這筆。
- 新的一次掛行程用新的 inst 路徑，見 [work](../base/work.md)。
- IPC 只回記憶體診斷，不讀工作結果或 git，也不是業務完成或 unknown 重跑許可。

### 什麼時候消失

- **自動淘汰**（第十八批）：同時設容量與保留期。筆數超過 `mount_diag_max`（預設 1024）時先淘汰最早結束的；結束後，掛它的上層又開了 `mount_diag_ttl_ticks` 格（預設 1000）的也淘汰。
- **手動清除**（第十八批）：`mount.clear`（[P-105](protocol/daemon/registration.md)）帶一個 `node_id`，清掉這個 id 本身的紀錄，以及上層鏈上有這個 node 的所有已結束掛載行程紀錄（整棵子樹）。只清呼叫者是 owner 或祖先 owner 的那些，看不到的不動、不回報；只清已結束的，還在跑的不動。
- **其餘**：上層額度撤掉該 owner 身分、掛它的 node 被解除、同 node_id 又被掛上、daemon 結束時都清掉。

- 〔暫定，astra 審整理區裁定裁-2〕保留期算**掛它的上層**的格：daemon 數上層那筆登記的格次序號 `tick_seq`（B-607）前進了幾格，不讀 tick 的結束碼紀錄。上層沒有週期、一直沒開格時，只靠容量淘汰；上層本身是掛載行程時，它結束就一起清（同「掛它的 node 被解除」）。

依據：使用者方向 2026-09-29；第十八批加淘汰與清除（行為從 P-106 搬上）；第十九批改名（原「once 診斷」）；astra 審整理區裁定裁-2（保留期改成上層的格數）。

**驗收：**掛載行程結束仍列得到且 `registered:false`；超過容量或保留期的紀錄消失；`mount.clear` 帶上層 node 時整棵子樹的已結束紀錄都清掉、別人的不動；重啟後舊結果消失。

## B-611：一棵資源樹只准一個 daemon

**daemon 啟動時，在任何讀回、清殺、寫狀態之前，先對實際使用的 `state_dir` 取一把排他鎖；取不到就拒絕啟動**（回 125，stderr 說明）。

- **為什麼**：兩個 daemon 用不同 socket 卻指向同一個（或互相重疊的）`state_dir` 或 cgroup 子樹時，會互相搶恢復資料、清殺對方的工作。
- **怎麼算重疊**：以解析後的真實路徑取鎖，並檢查祖先與子孫；任何一個祖先或子孫已被別的 daemon 鎖住，也算重疊。
- 鎖跟著 daemon 程序存活，程序死了鎖自動放掉。
- **有 cgroup 時另取一把**：以解析後的真實路徑，對實際使用的 cgroup 子樹根（含省略 `cgroup_root` 時自己所在那層）取排他鎖。明寫 `cgroup_root` 時取不到就拒絕啟動（125）；自動偵測時取不到（巢狀 daemon：祖先被外層 daemon 鎖住），就當成沒有 cgroup，`cgroup=off` 照跑（B-605；納入 cgroup 與 git 疑-11）。沒有 cgroup 時只取 `state_dir` 那把。
- **socket 的鎖**：每個 `socket_path` 另有同目錄的 `daemon.lock`（[P-101](protocol/daemon/startup-and-ipc.md)）。〔建議預設；第十九批從 P-101 搬上〕持鎖後才能清理屬於這個實例的殘留 socket，不能刪活著的 socket；無法 bind、路徑過長或權限不足就明確失敗。socket 父目錄的穿越權與 socket 的連接權由部署者先配置，不在封包裡給任意人改。

〔建議預設〕做法：鎖直接對目錄本身取（開目錄再 `flock`）；`state_dir` 祖先往上試鎖到根目錄，子孫往下掃一遍試鎖，試完就放。兩個同時啟動、互為祖孫時，可能雙方都拒絕，重試即可。cgroup 子樹那把同樣直接對目錄取（cgroup 目錄裡不能另建一般檔；實測開目錄後 flock 可行，第二個 fd 會被擋），祖先往上試鎖到 cgroup 掛載點、子孫往下掃一遍。用首推做法開的兩個 daemon 各在自己的 scope，彼此是兄弟、不重疊，只有 `state_dir` 那把會擋。

依據：主編補，第十八批（審稿新必-3）；第十九批；納入 cgroup 與 git 疑-11（巢狀 daemon 自動偵測時當成沒有 cgroup）。

**驗收：**兩份設定用不同 socket、同一個 `state_dir`（或一個是另一個的子目錄）時，後啟動的拒絕啟動，先啟動的工作不受影響；同一個（或重疊的）明寫 `cgroup_root` 時後啟動的回 125；某個 tick 用 `node.mount` 掛了另一個 daemon（沒寫 `cgroup_root`），內層印 `cgroup=off` 照跑，仍受外層框的上限。

## B-612：tick–daemon 通道

**通道是 daemon 開的 tick 跟 daemon 之間的 IPC，也是唯一逃生口。** 通道上只有這幾件事：

- 登記與解除（含覆蓋上層）；
- 把行程掛到 daemon 上跑與砍掉；
- 叫醒別的 tick；
- 傳訊（送與取暫存訊息）。

其他所有事都必須在某一格 tick 裡做，不准有別的背景程序或常駐服務繞過 tick；要常駐就用 `node.mount` 掛（B-613）。

**通道事務由任務自己呼叫**，都不是 daemon 的事：系統訊息佇列由系統級任務 `aos-mq post` 送、`aos-mq get` 取（[B-624](tick.md)、[B-623](tick.md)）；once 由任務掛行程；換帳號由普通程式 `aos-as` 呼叫 `spawn_as`（B-609）。method 形狀、參數與錯誤碼見 [P-117～119](protocol/daemon/channel.md)。

依據：第十九批第 9 條；第二十批方向 4、追答 5。

### 誰有通道

只有 daemon 開的程序——登記的 node 的每一格，以及每個掛載行程（B-613）。daemon 開它時在環境放兩個變數：

| 變數 | 內容 |
|---|---|
| `AOS_DAEMON_SOCKET` | daemon 的 socket 絕對路徑，就是設定的 `socket_path` |
| `AOS_TICK_TOKEN` | 本格憑證 |

- 任務會繼承這兩個變數；在「投件權就是執行權」之下這是預期行為（[T-08](../terms.md)）。
- inst 的 `envs` 用 `clear` 時兩個都會被清掉，等於不給那一項通道。怎麼放進子程序環境以 [inst](../base/inst.md) 為正本。
- cron、人手直接跑的 tick 沒有這兩個變數。缺變數時由客戶端自己擋下、報 `no_channel`，不送到 daemon（P-117）。沒通道只算功能受限：`aos-mq`、`aos-as`、once 用不了，其他照常（[T-10](terms.md)）。
- 變數本身不授予權限：socket 的連接權照部署設定，授權看下面的憑證。

### 憑證

〔建議預設〕做法（第十九批）：

- **發放**：daemon 每開一格（或一個掛載行程）就產生一張，至少 128 位元的密碼學隨機值，綁定「node id、`registration_id`、`tick_seq`」（掛載行程沒有 `tick_seq`）。只放 daemon 記憶體，不寫檔、不放 argv（別的帳號看得到 argv）。
- **核對**：通道上的請求在 params 帶 `token`，daemon 以固定時間比對。對上了，還要看 socket 對面的帳號是這一格開起來時的執行帳號，或落在該 node 的身分額度內（任務可以帶自己的 `user`）；都成立才把呼叫者當成那個 tick。對不上一律回 `token_invalid`，不說是哪一項不合。
- **作廢**：該格的主程序結束（daemon 收到 runner 回報）即作廢，之後後代還拿著也沒用；登記被解除或換父（`registration_id` 改變）時作廢；daemon 重啟時全部作廢。
- **用憑證時怎麼授權**：B-601「誰可呼叫」表中「X 的 owner 或祖先 owner」，帶憑證時讀成「憑證所屬的 tick 就是 X，或在 X 的有效上層鏈上」。不帶憑證的請求照舊看 socket 對面的帳號，給人手與 CLI 用；兩條路授權的是同一張表。

### 哪些 method 收憑證

| method | 憑證 |
|---|---|
| `node.register`、`node.unregister`、`node.wake`、`node.mount`、`node.kill` | 可帶可不帶 |
| `node.send`、`node.take`、`node.provision` 的 `spawn_as`（B-609） | 一定要帶 |
| 其餘（含 `daemon.info`、`node.show`、`node.provision` 的其他動作） | 不收，只看 socket 對面的帳號 |

客戶端只對前兩列附憑證，其他照舊用自己的帳號送（[P-117](protocol/daemon/channel.md)）。

**格式**：通道上的請求屬 daemon IPC，照 [C-07](../contracts.md) 維持嚴格，不認得的欄位拒收；封包上限同 IPC 的 256 KiB。

**驗收：**daemon 開的 tick 有兩個變數，直接跑的沒有、客戶端報 `no_channel`；上一格的憑證在下一格用回 `token_invalid`；daemon 重啟後舊憑證全部失效；別的帳號拿到憑證也用不了；inst 的 `envs` 用 `clear` 的任務拿不到變數。

## B-613：掛行程與砍掉

**把一個行程掛到 daemon 上跑、之後再砍掉，是通道的核心事務。** 原本 daemon 端的 once 登記改成這一套；once 是任務自己經通道呼叫的事務，不是系統級任務（[B-629](tick.md)）。要在格外常駐的程序，一律用這一套掛，daemon 追得到、`node.kill` 砍得掉。被掛的可以是任何 inst，也可以是另一個 tick 的資料夾（daemon 就跑它一格）。

依據：第十九批第 3、9、10 條；第二十批追答 5。

### 掛上

- `node.mount` 帶目標 inst 路徑（資料夾或單檔），daemon 立刻開一個 runner 跑它。
- 不需要事先登記、不接受週期、不能有成員，也不要求 tasks 或 git。
- 回應帶這次的 `registration_id`，之後用 `node.show` 查結果。

### 資源與核權歸掛的那個 tick

- 帶憑證時，上層就是憑證所屬的 tick。也可以帶 `parent_id` 指定成它有效上層鏈之下的某個 node（例如 kernel 替成員掛工作，歸成員），但不能指定成自己以上或別隊的 node。
- 不帶憑證時（人手、CLI）必須帶 `parent_id`，呼叫者要是它的 owner 或祖先 owner。
- 不另收可自報的 cgroup 路徑。掛載行程由自己的 runner 管（B-601），歸上層是核權、解除與收尾範圍的歸屬；有 cgroup 時它的框放在掛它的 node 框下，名字 `mount-<h>`，本身就是葉框（B-605）。那個 node 的格後收尾不碰它；砍掉或結束時由收尾清空、刪框（B-604、B-603）。
- inst 的 `user` 要落在上層的身分額度內，不合回 `user_not_granted`，不存在回 `user_invalid`。kernel 不能把成員工作掛在自己的較大額度。
- 各參數怎麼填（含 agent 自跑工具、LLM 池代發）見 [P-402](../protocol/work.md)。

### 結束與砍掉

- **結束**：行程跑完或被砍，daemon 收尾、自動移出登記表，留下 B-610 的診斷。掛它的 tick 用 `node.show` 看 `last_tick` 拿結果：`outcome`、`exit_code`、`signal` 就是這個行程的。這筆診斷會被淘汰（B-610），要留存的結果由掛的一方自己記。
- 同一個 id 在跑時再掛回 `registration_conflict`；掛載行程沒有第二次、也沒有 pending。
- **砍掉**：`node.kill` 對它做 B-604 的收尾。核權看掛它的那個 tick 的**路徑**（上層與上層鏈），不看當時那張憑證，所以上一格掛的、這一格也能砍。已經結束的回 `not_registered`；對登記的 node 送 `node.kill` 回 `kind_mismatch`。取消在跑的工作就用它（[B-203](../base/execution.md)）。
- **失敗證據**：前置失敗也算用掉這次掛行程；沒確認後代清空就保留阻擋。`not_registered`、重啟或沒收到回應都不是重跑許可，判讀見 [S-401](../scheduling/operations.md)。

### 單檔的未啟動旁檔

目標是單檔、而 daemon／helper 拒絕啟動 runner，或可信 runner 回報 `started:false` 時，daemon 在這個 inst 旁發布 `<inst 檔名>.err`（例如 `job.json.err`，格式見 [P-110](protocol/daemon/provision-and-runner.md)）。

- 私有的 PascalCase 錯誤要映成 `user_not_granted`、`user_mismatch`、`source_changed` 或 `start_failed` 等小寫代碼，不直接抄 runner 的錯誤。
- 每次掛行程用新的 inst 路徑，不覆蓋既有旁檔；以已授權目標的目錄 handle 發布，不能藉此任意寫檔。
- 旁檔衝突或寫不出就 stdout 印一行警告，不另存 daemon 事項；掛的一方沒證據仍保留 unknown。
- 目標是資料夾時，啟動失敗寫它自己的 `.aos/attention/`，不寫旁檔。
- runner 已放行後不寫這份旁檔；之後的 125、126／127 或結果遺失依 [work](../base/work.md) 處理。

依據：使用者方向 2026-09-29（第十一批與後續旁檔改名裁定）；第十九批從 P-110 搬上。

### 其他

- 排空停機時拒收新的掛行程，等已掛的跑完（B-604）；掛載行程不存檔，重啟後不接回（B-603）。
- 掛載行程也有通道（B-612），憑證綁它自己；它沒有收件匣，`node.take` 回 `kind_mismatch`。

**驗收：**tick 在第一格掛一個常駐行程、第四格用 `node.kill` 砍掉，砍得掉而且收尾完成；別隊的 tick 砍不掉；帶 `parent_id` 指到自己上層鏈之外被拒；人手不帶憑證又沒帶 `parent_id` 被拒；單檔目標未啟動時有 `.err`，已放行後沒有。

## B-614：暫存訊息與急件

**同一個 daemon 底下的 tick 可以經 daemon 互傳訊息（系統訊息佇列）；不保證送達。** tick 那一側由系統級任務 `aos-mq` 送與取（[B-623](tick.md)、[B-624](tick.md)）。

- **格式**：訊息是一份請求物件或回應物件（[P-301](../protocol/messages.md)）；daemon 只驗外形，不解析正文。〔使用者方向 2026-09-30，修正輪暫定的裁定〕請求與回應放同一個佇列，`node.take` 一起取出。
  - 〔暫定，交接疑點「通道訊息放寬」照 a〕照 [C-07](../contracts.md)：通道請求的外層（`node.send` 的 params）照 daemon IPC 嚴格；夾帶的 `message` 照檔案 RPC 放寬，不認得的欄位忽略。
- **送**：`node.send` 帶收件 tick 的 id、訊息與是否急件。收件 tick 要在這個 daemon 登記，否則回 `not_registered`；掛載行程沒有收件匣（`kind_mismatch`）。
- **誰能送**：看寄件 tick 的執行帳號對收件 tick 的 `.aos/mq/get/` 有沒有寫權——能不能在那裡建檔（`.aos/mq/get/` 的寫與穿越權，以及上層各段的穿越權）；沒有就回 `forbidden`。〔使用者方向 2026-09-30，修正輪暫定的裁定：改看 `.aos/mq/` 底下的資料夾，不再看 `requests/`；選 `.aos/mq/get/`：使用者 2026-09-30 同意照暫定〕這個資料夾只拿來當判準，`aos-mq get` 要不要用它放取出的訊息由它自己定（[P-200](protocol/node.md)）。首版不用 ACL，所以 daemon 以那個帳號的 UID 與群組，對權限位計算即可。「投件權就是執行權」同樣適用（[T-08](../terms.md)）。
- **存**：放 daemon 記憶體，按收件 tick 分開、先進先出。daemon 當掉、重啟、立即停機，或收件 tick 被解除，暫存的都丟掉。〔建議預設〕每個收件 tick 最多 256 件、合計 16 MiB，滿了回 `mailbox_full`；單件訊息序列化後最多 196608 bytes（192 KiB），超過回 `message_too_large`，這樣一件一定裝得進一個 `node.take` 回應。
- **取**：收件 tick 裡只有系統級任務 `aos-mq get` 在它的那一格上通道用 `node.take` 取，其他任務不直接取（[B-623](tick.md)）。取走的 daemon 同時刪掉，之後怎麼分派、落地、去重 aos 不管。一次回應裝不下就分幾次取，回應會說還有沒有。daemon 分不出是哪一項在取，「只有它取」是 node 裡的約定。
- **急件**：送到時 daemon 照 `node.wake` 叫醒收件 tick（合併、paused 只記 pending、停機中不叫，B-607）；一般件等它自己的下一格。〔暫定，改寫計畫疑-9 使用者未答〕急件直接叫醒，不問上層，不受上層 kernel 的節流：它會越過上層排程任務的同時叫醒上限（`max_active_members`，[S-202](../scheduling/admission.md)），這是「反應速度就是一格」唯一的例外（第二十批追答 7）。
- 排空停機時通道照常收送（B-604）。

依據：第十九批第 9 條與疑點裁定 6、7；astra 審整理區裁定裁-1 與同日定案（系統訊息佇列 `aos-mq`，只有 `aos-mq get` 取）；修正輪暫定的裁定（回應也走佇列；授權判準改看 `.aos/mq/` 底下的資料夾）。

**驗收：**寄件帳號對收件 `.aos/mq/get/` 沒寫權被拒，對 `requests/` 有沒有寫權不影響；回應物件照樣送得進、取得到；一般件不叫醒、下一格取得到；急件送到後收件 tick 被叫醒；取過的再取不到；daemon 重啟後暫存的都不見；超過上限回 `mailbox_full`、`message_too_large`。

## 附錄：開機自動啟動的 systemd service 範例

〔使用者方向 2026-09-29 晚〕要開機自動啟動，就把 daemon 寫成一個 systemd service；這只是範例，不算執行期依賴。兩種都寫 `Delegate=yes`，讓 systemd 把 daemon 所在的 cgroup 委派給它，daemon 才認得到有 cgroup（B-605）；拿掉就是 `cgroup=off`。

### 使用者層（不用 sudo，單帳號）

〔納入 cgroup 與 git 改寫計畫〕單位名固定，框路徑也固定；重啟時 systemd 會先殺舊程序。要先對這個帳號 `loginctl enable-linger <帳號>`，登出後才不會被停。

```ini
# ~/.config/systemd/user/aos-daemon.service（範例）
[Unit]
Description=aos daemon (user)

[Service]
ExecStart=/usr/local/bin/aos daemon --config %h/.config/aos/daemon.json
ExecReload=/bin/kill -HUP $MAINPID
# 委派 cgroup 子樹給 daemon（B-605）
Delegate=yes
KillMode=mixed
TimeoutStopSec=15min

[Install]
WantedBy=default.target
```

### 系統層（sudo 模式，有 helper）

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
