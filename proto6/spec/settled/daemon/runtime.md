# daemon 核心：開格與 runner

← [daemon 目錄](README.md)｜[整理區](../README.md)

## B-601：記憶體登記與按需執行

〔使用者方向 2026-09-30 晚〕登記與開格、runner 清自己名下程序（含收屍）屬核心，不受訊息或 cgroup 部件開關影響。

依據：[09-30 晚裁定](../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)；開關細節見 [B-615](components.md)。

daemon 在記憶體放一張登記表，**node 資料夾路徑就是 id**。登記的 node 按登記間隔或叫醒開格。

- **怎麼辨識一個 tick**：看資料夾路徑或 inst.json 路徑。登記時給的是 `<資料夾>/.aos/inst.json` 或 `<資料夾>/inst.json`，一律正規化成所在資料夾。掛載行程（B-613）照給的路徑，可以是單檔。
- **daemon 不做的事**：不讀工作狀態或任務註冊表，不排業務工作、不分資源。只用登記與喚醒資料；讀 inst 只為 `user` 授權。訊息在通道上只**暫存與轉交**，不解析正文（B-614）。
- **不叫排程**：aos 的「排程」是任務表上每格跑一次的程式（[T-07](../terms.md)、[scheduling](../../scheduling/README.md)）；daemon 這邊只做「定期開格」與「叫醒開格」。
- **一格一格來**：同一資料夾同時只跑一格，由 tick 核心的鎖保證（[B-602](../tick.md)）。daemon 另外自己避免同時開同一 node 的兩格，但這不是互斥的來源。
- 〔使用例，不是 daemon 的規則〕agent 通常不設定期，由 kernel 決定何時叫醒及同時執行數；kernel 本格結束就退出，不等成員，LLM／工具由後續 tick 收結果。

依據：使用者方向 2026-09-29；第十九批（辨識 tick、改寫）；第二十批方向 2、追答 3（排程）。

### socket 上有哪些事

| 事 | 正本 |
|---|---|
| 登記與解除 | [B-606](registration.md#b-606登記解除換父與身分額度) |
| 叫醒、暫停與故障停格、查詢 | [B-607](registration.md#b-607叫醒暫停故障停格與格次序號) |
| 佈建 | [B-609](helper-actions.md#b-609佈建固定動作與-helper-動作) |
| 通道事務 | [B-612～614](channel.md#b-612tickdaemon-通道) |
| method 形狀 | [daemon 協議](../protocol/daemon/README.md) |

通道外的這些 IPC（查詢、暫停與恢復、佈建等）給人手、CLI 與格內的任務用自己的帳號呼叫。人手與 CLI 在格外做的事算外部世界，aos 不管（第二十批疑點裁定 8）。

### IPC 授權與身分額度

**呼叫者看 socket 對面的 Linux 帳號**（`SO_PEERCRED`）：該 node 的帳號，或其上層的帳號。封包自稱的 sender／user 不算呼叫者身分。

- **唯一例外是通道**：請求帶本格憑證時，呼叫者是憑證所屬的那個 tick（B-612）。下表的「X 的 owner 或祖先 owner」，帶憑證時讀成「憑證所屬的 tick 就是 X，或在 X 的有效上層鏈上」。
- **上層**指有效上層鏈（預設看資料夾包含，登記可覆蓋，B-606），不是 OS 父目錄本身。
- **owner** 是登記保存的 `owner_uid`，何時更新見 B-606。
- 身分額度與通用 user 以 [B-301](../../base/identity-resources.md) 為正本；額度的寫法與包含判定見 B-606。獲准叫醒不代表獲准擴大額度。

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
| `daemon.attention.ls`、`daemon.attention.show` | 只回 peer 是來源 owner／祖先 owner 的事項（[P-601](../../protocol/ops.md)） |
| `daemon.attention.done` | 來源 owner 或祖先 owner；只把 daemon 自身事項標成完成 |

〔建議預設；第十九批從 P-103 搬上，astra 審整理區必-8 從 P-111 搬上〕授權與處理細節：

- 先驗 JSON、method 與參數，再授權。
- 不能用 PID、路徑前綴或封包的 `user` 當呼叫者。同 UID 共用同一 OS 權限，不帶憑證時分不出是哪個 node 或工具在呼叫。
- root 或通用 user 不因名稱自帶全樹特權，是 owner 或祖先 owner 才符合。可連 socket 不等於通過 method 授權。
- RPC ID 只配對回應，不是永久執行收據。斷線不代表沒做：登記、pause、resume 可以查目前值核對；wake 可合併但不是永久去重；掛行程與特權動作不准因沒回應就盲目重送。daemon 不加持久重播帳本。
- 一行超過封包上限：回一次 `invalid_request` 就關連線，不無界讀下去。回錯時能辨識出合法的請求 ID 就沿用，不另造 ID。

依據：使用者方向 2026-09-29；第十九批（憑證例外）。

### 執行身分與 helper

- daemon 開 tick 前只讀 [inst 的 `user`](../../base/inst.md) 授權，不解析其他工作內容；不合額度就不跑，照 B-607 停格。其餘解析與執行規則依 inst 篇。
- 〔astra 審整理區必-8 從 P-101 搬上〕daemon 以通用 user 讀 inst；讀不到就拒絕，**不交給 root 代讀**。部署要先給通用 user 必要的讀權與目錄穿越權。
- 啟動路徑與可選 helper 的角色依 [B-303](../helper.md)；helper 做哪些固定動作見 B-609。

**事項往哪寫**：

- node 問題寫該 node 的 `.aos/attention/`（ignore）；寫不出就 stdout 警告。
- daemon 自身問題才留 daemon attention／stderr。
- 事項怎麼處理見 [S-405](../../scheduling/operations.md)。
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

〔建議預設；第十九批從 P-109、P-110 搬上〕daemon（或 helper）以固定的 [runner](../terms.md#t-09收尾排空停機熱重載逃生口)（`aos-runner`）開每一格與每個掛載行程：

1. fork 後先 `setsid`（runner 自成一個 session，不跟 daemon 的終端同組），降權；有 cgroup 時另照 [B-601 的放框規則](cgroup.md#格後清框b-601)；
2. runner 核對 UID，並核對 inst 原來源的 bytes 跟授權時的快照相同；
3. 才照 [inst](../../base/inst.md) 解析、開檔與執行。

argv 與回報形狀見 [P-109、P-110](../protocol/daemon/provision-and-runner.md)。

- **串流**：runner 的 stdin／stdout 是 `/dev/null`（`spawn_as` 例外：用 `aos-as` 交來的 stdio，B-609）。stderr 由 daemon 收集成 node 診斷，不直通 daemon 的 stderr；資料夾 node 暫定寫 `.aos/runner-stderr.log`（覆寫、ignore），輪替與留存以後再定。
- **環境**：除了 [B-303](../helper.md) 與 inst 的規則，daemon 開的每一格、每個掛載行程都多放兩個通道變數（B-612），不帶管理 fd 或 key。daemon 帶了 `--firstdo-fsync` 時，另放 `AOS_TICK_FIRSTDO_FSYNC=1`，讓那一格的 `aos-tick` 開格時 fsync（[B-633](../tick.md)）〔使用者 2026-09-30 同意照暫定〕。`spawn_as` 開的程序怎麼補環境見 B-609。
- **回報**：每次完整收尾只回報一次。
  - 前置失敗（身分不在額度內、來源變了等）回 `started:false`。
  - 已放行後，子程式自己的結束碼照實回報；被訊號結束另帶訊號編號。
  - runner 在已放行後自己收尾失敗，回報 `FinalizeFailed`，不能當成子程式退出 125。
  - 沒有完整可信回報就是結果不明，不能推定從未執行。前置檢查可能已建目錄或截斷輸出，125 不代表沒有檔案副作用。
- **helper 開格什麼時候回**〔建議預設；第十九批依方案 A 從 P-108 搬上〕：helper 替 daemon 開的格與掛載行程，要等 runner 回報並結束、wait 回收之後才回覆 daemon。全空但業務失敗仍算開格完成；無法確認全空回 `cleanup_failed`。私有通道按 RPC ID 配對，可同時有多筆在途。helper 拿到的快照是 daemon 取原始 `user` 時的同一份不可變 bytes；inst 的 base 仍照 [inst 目標](../../base/inst.md#inst-目標檔案或資料夾)算，不看快照放在哪。`spawn_as` 例外：runner 開起來就回，結束碼走 `aos-as` 交來的 pipe（B-609）。

### 誰管哪些程序

**runner 當收屍人**〔使用者方向 2026-09-30，確認定案〕：每一次開格（或掛載）由那一個 runner 負責它底下的所有程序；daemon／helper 只跟 runner 打交道。有 cgroup 時，daemon 另外用框兜底。

| 誰 | 做什麼 |
|---|---|
| daemon、helper | 自己是 child subreaper。fork＋`setsid`＋exec runner；以 pidfd 追蹤 runner、對它送訊號 |
| runner | 設 `PR_SET_CHILD_SUBREAPER`。照 inst 讓子程式另開 session（子程式群組，[inst](../../base/inst.md)）。子程式的後代不論有沒有跳出群組，只要中間的父程序死了，就掛回 runner |

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
- **清不到的**：經外部服務（systemd、at 等）開的、自己設成 subreaper 的後代、換成別的帳號的程序。它們若還握著 tick 的鎖 fd，同資料夾的下一格回 75（[B-602](../tick.md)）。
- **runner 自己意外死掉**（被 SIGKILL、OOM）：它名下的程序掛回 daemon（或 helper）。daemon 分不出它們原本屬於哪一格，一律 SIGKILL 並回收；那一次開格沒有可信回報，照 B-607 記 `unknown`、停格，要人確認後才 resume。
- 後代串流收完與取消競態依 [B-203](../../base/execution.md)。範圍沒清空前不釋放名額、不開下一格；所有失敗都不自動重跑結果不明的工作。

有 cgroup 時的格後清框見 [B-601 的 cgroup 部分](cgroup.md#格後清框b-601)；runner 上述規則照做。

依據：第十九批（程序群組）；第二十批追答 8（一格結束後殺殘留歸 daemon）；astra 審整理區必-1（受管範圍改成 runner 名下的整棵樹），使用者確認定案；納入 cgroup 與 git 疑-7（node 自開子框不收）。

**驗收：**無事 node 不開 tick；重複叫醒不重疊；任務在背景留一個 `sleep`，tick 結束後它被清掉、下一格照常開；任務在背景 `setsid` 另開 session 留一個 `sleep`、再讓中間的父程序結束，tick 結束後它也被清掉；兩個 node 同時跑，一邊的格後收尾不碰另一邊的程序。以上在有、沒有 cgroup 的機器上都成立。有 cgroup 時，任務用 `setsid` 加 double fork 再自設 subreaper 留下的程序，格後被 `cgroup.kill`；node 自己開的子框裡的程序不被收。身分拒絕及無 helper 情境見 [V-03](../../conformance.md)。給 `.aos/inst.json` 或 `inst.json` 路徑登記，得到的 node id 是所在資料夾。

## B-504：通知只是提示

**daemon 只按登記的週期或叫醒（含急件）開格。** 反應速度就是一格。

- 不看收件區有沒有新檔，也不讀任何檔的正文；不為了「收到就處理」另開監看。
- 一般收件等收件 tick 自己的下一格（[T-07](../terms.md)）。通道訊息送到時，**只有急件**才叫醒收件 tick，一般件等它自己的下一格（B-614）。
- kernel 才核對自己的收件與成員摘要，決定後續要叫醒誰。叫醒本身不是接件、消費或完成證據。
- 〔建議預設〕執行中的 node 收到叫醒時，daemon 留一個待喚醒標記，收尾後再開下一格。叫醒合併或遺失後的補查由 kernel 按 [S-202](../../scheduling/admission.md) 每格處理，daemon 不代查內容。

依據：使用者方向 2026-09-29；第十九批（急件）；第二十批追答 5、7（刪「新檔通知」）。

**驗收：**往收件區放新檔不會讓 daemon 開格，收件 tick 在自己的下一格（或被叫醒時）才處理；漏掉一次叫醒，完整投件仍能在所屬 kernel 的後續補查被發現；同一 node 連續收到多次叫醒不會同時跑兩格。內容發布與去重見 [投件](../../base/transport.md)，互斥見 [B-602](../tick.md)。

## 啟動自檢（B-605 的共通部分）

- **daemon 自己的最低需求**：Python 3.9；不合就報錯退出（125）。
- **不查 git**：git 只有任務表上的 `aos-git` 會用（[B-630](../tick.md)），daemon 不查。

### 有就用的其他功能

- project quota 等功能在啟動時自動偵測，設定檔可強制關（P-101 的 `disable`，可熱重載，B-608）。
- 沒有 quota 時，磁碟用量由磁碟資源任務定期量（[B-304](../../base/identity-resources.md)、[S-203](../../scheduling/admission.md)）。
- 檔案系統不限定：node 放在不支援某些功能的地方，那些功能就不支援；不列白名單或拒絕清單。

依據：使用者方向 2026-09-29 晚。

### 初版不做

systemd 的沙盒防護（`CapabilityBoundingSet` 等）以後再考慮；helper 掛 tmpfs 拿掉；原本打算交給 systemd 的開程序、定時叫醒等做法，初版全由 daemon 自己做（使用者方向 2026-09-29 晚）。

**驗收：**Python 低於 3.9 時回 125；不查 git；quota 的強制關設定照舊。
