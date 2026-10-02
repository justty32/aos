← [daemon 核心：開格與 runner](../runtime.md)（分檔 1/3）｜[下一份](02-B-601-執行身分與開格.md)

## B-601：記憶體登記與按需執行

> **部分已被取代、其餘暫緩**（2026-10-01）：「照週期開格、同一項同時只跑一個」改成 [B-640](../../../daemon/core.md)：定期叫 `aos-exec`；「node 路徑就是 id」改成核心沒有 id（[B-640](../../../daemon/core.md)）；記憶體登記、IPC 授權與身分額度、helper、runner 開格與回報、收屍與格後清程序暫緩，daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01）。條號保留、不重用。

〔使用者方向 2026-09-30 晚〕登記與開格、runner 清自己名下程序（含收屍）屬核心，不受訊息或 cgroup 部件開關影響。

依據：[09-30 晚裁定](../../../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)；開關細節見 [B-615](../components.md)。

daemon 在記憶體放一張登記表，**node 資料夾路徑就是 id**。登記的 node 按登記間隔或叫醒開格。

- **怎麼辨識一個 tick**：看資料夾路徑或 inst.json 路徑。登記時給的是 `<資料夾>/.aos/inst.json` 或 `<資料夾>/inst.json`，一律正規化成所在資料夾。掛載行程（B-613）照給的路徑，可以是單檔。
- **daemon 不做的事**：不讀工作狀態或任務註冊表，不排業務工作、不分資源。只用登記與喚醒資料；讀 inst 只為 `user` 授權。訊息在通道上只**暫存與轉交**，不解析正文（B-614）。
- **不叫排程**：aos 的「排程」是任務表上每格跑一次的程式（[T-07](../../../terms.md)、[scheduling](../../../../scheduling/README.md)）；daemon 這邊只做「定期開格」與「叫醒開格」。
- **一格一格來**：同一資料夾同時只跑一格，由 tick 核心的鎖保證（[B-602](../../../tick.md)）。daemon 另外自己避免同時開同一 node 的兩格，但這不是互斥的來源。
- 〔使用例，不是 daemon 的規則〕agent 通常不設定期，由 kernel 決定何時叫醒及同時執行數；kernel 本格結束就退出，不等成員，LLM／工具由後續 tick 收結果。

依據：使用者方向 2026-09-29；第十九批（辨識 tick、改寫）；第二十批方向 2、追答 3（排程）。

### socket 上有哪些事

| 事 | 正本 |
|---|---|
| 登記與解除 | [B-606](../registration/01-B-606-登記與上層.md#b-606登記解除換父與身分額度) |
| 叫醒、暫停與故障停格、查詢 | [B-607](../registration/03-B-607-叫醒暫停與故障停格.md#b-607叫醒暫停故障停格與格次序號) |
| 佈建 | [B-609](../helper-actions/01-B-609-通則與動作.md#b-609佈建固定動作與-helper-動作) |
| 通道事務 | [B-612～614](../channel/01-B-610-B-612-診斷與通道.md#b-612tickdaemon-通道) |
| method 形狀 | [舊 daemon 協議](../../protocol/daemon/README.md) |

通道外的這些 IPC（查詢、暫停與恢復、佈建等）給人手、CLI 與格內的任務用自己的帳號呼叫。人手與 CLI 在格外做的事算外部世界，aos 不管（第二十批疑點裁定 8）。

### IPC 授權與身分額度

**呼叫者看 socket 對面的 Linux 帳號**（`SO_PEERCRED`）：該 node 的帳號，或其上層的帳號。封包自稱的 sender／user 不算呼叫者身分。

- **唯一例外是通道**：請求帶本格憑證時，呼叫者是憑證所屬的那個 tick（B-612）。下表的「X 的 owner 或祖先 owner」，帶憑證時讀成「憑證所屬的 tick 就是 X，或在 X 的有效上層鏈上」。
- **上層**指有效上層鏈（預設看資料夾包含，登記可覆蓋，B-606），不是 OS 父目錄本身。
- **owner** 是登記保存的 `owner_uid`，何時更新見 B-606。
- 身分額度與通用 user 以 [B-301](../../../../base/identity-resources.md) 為正本；額度的寫法與包含判定見 B-606。獲准叫醒不代表獲准擴大額度。

**誰可呼叫**〔建議預設；astra 審整理區必-8 從 P-103 搬上〕：

| method | 誰可呼叫 |
|---|---|
| `node.register` | 新成員：有效上層的 owner 或祖先 owner；首次必須有上層同意，不能自行接到別人的鏈。既有項：原 owner 或祖先 owner，不能搶別隊；可重登自己，但不能擴大目前的額度或佈建權。覆蓋上層與換父：同時是新舊兩個上層的 owner 或祖先 owner；舊上層沒在這個 daemon 登記時只看新上層（B-606） |
| `node.unregister` | 目標 owner 或祖先 owner；效果包含目標已登記子樹 |
| `node.wake`、`node.pause`、`node.resume` | 目標 owner 或祖先 owner |
| `node.mount` | 掛載的上層（`parent_id`；帶憑證時省略＝憑證所屬的 tick）的 owner 或祖先 owner（B-613） |
| `node.kill` | 掛它的那個上層的 owner 或祖先 owner；看路徑，不看當時的憑證 |
| `node.send` | 必帶憑證；誰能送照 [B-614「誰能送」](../messaging.md)（看收件 tick 的 `.aos/mq/get/`，不看 `requests/`）〔astra 報告必修 6〕 |
| `node.take` | 必帶憑證；只取憑證所屬 tick 自己的 |
| `node.show` | 目標 owner 或祖先 owner；含保留的掛載行程結果（B-610） |
| `node.ls` | 有 socket 連接權；逐筆只列 peer 是 owner／祖先 owner 的登記及保留的掛載行程結果，沒有可見項回空陣列 |
| `daemon.info` | 有 socket 連接權；只回本次啟動 ID，不暴露登記 |
| `mount.clear` | 有 socket 連接權；只清 peer 是 owner／祖先 owner 的已結束掛載行程紀錄（B-610） |
| `node.provision` | 目標 owner 或祖先 owner，且目標登記有相符的 `provision` 授權；需 helper 的動作再由 helper 核對。`spawn_as` 例外：必帶憑證、憑證所屬的 tick 就是目標，帳號看身分額度，不看 `provision` 授權（B-609） |
| `daemon.attention.ls`、`daemon.attention.show` | 只回 peer 是來源 owner／祖先 owner 的事項（[P-601](../../../../protocol/ops.md)） |
| `daemon.attention.done` | 來源 owner 或祖先 owner；只把 daemon 自身事項標成完成 |

〔建議預設；第十九批從 P-103 搬上，astra 審整理區必-8 從 P-111 搬上〕授權與處理細節：

- 先驗 JSON、method 與參數，再授權。
- 不能用 PID、路徑前綴或封包的 `user` 當呼叫者。同 UID 共用同一 OS 權限，不帶憑證時分不出是哪個 node 或工具在呼叫。
- root 或通用 user 不因名稱自帶全樹特權，是 owner 或祖先 owner 才符合。可連 socket 不等於通過 method 授權。
- RPC ID 只配對回應，不是永久執行收據。斷線不代表沒做：登記、pause、resume 可以查目前值核對；wake 可合併但不是永久去重；掛行程與特權動作不准因沒回應就盲目重送。daemon 不加持久重播帳本。
- 一行超過封包上限：回一次 `invalid_request` 就關連線，不無界讀下去。回錯時能辨識出合法的請求 ID 就沿用，不另造 ID。

依據：使用者方向 2026-09-29；第十九批（憑證例外）。
