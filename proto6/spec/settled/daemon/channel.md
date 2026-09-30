# daemon 核心：通道、掛行程與診斷

← [daemon 目錄](README.md)｜[整理區](../README.md)

## B-610：掛載行程的診斷：留存、淘汰與清除

**掛載行程結束後，daemon 在記憶體留一筆最近結果，只供查詢。**

### 留存

- 掛載行程（B-613）結束或被砍掉、收尾完成後，daemon 在記憶體留一筆 `registered:false` 的最近結果，保留原 `owner_uid`、`parent_id` 與 `registration_id`。
- 只供 `node.show`／`node.ls`；`node.kill`、wake、pause、resume 都回 `not_registered`。
- 查詢時以**目前仍在的可信上層鏈**重驗；祖先權限撤銷即生效，不能靠舊祖先快照繼續讀。
- 不寫檔、不算正在占用的登記；登記的 node 被解除不留這筆。
- 新的一次掛行程用新的 inst 路徑，見 [work](../../base/work.md)。
- IPC 只回記憶體診斷，不讀工作結果或 git，也不是業務完成或 unknown 重跑許可。

### 什麼時候消失

- **自動淘汰**（第十八批）：同時設容量與保留期。筆數超過 `mount_diag_max`（預設 1024）時先淘汰最早結束的；結束後，掛它的上層又開了 `mount_diag_ttl_ticks` 格（預設 1000）的也淘汰。
- **手動清除**（第十八批）：`mount.clear`（[P-105](../protocol/daemon/registration.md)）帶一個 `node_id`，清掉這個 id 本身的紀錄，以及上層鏈上有這個 node 的所有已結束掛載行程紀錄（整棵子樹）。只清呼叫者是 owner 或祖先 owner 的那些，看不到的不動、不回報；只清已結束的，還在跑的不動。
- **其餘**：上層額度撤掉該 owner 身分、掛它的 node 被解除、同 node_id 又被掛上、daemon 結束時都清掉。

- 〔暫定，astra 審整理區裁定裁-2〕保留期算**掛它的上層**的格：daemon 數上層那筆登記的格次序號 `tick_seq`（B-607）前進了幾格，不讀 tick 的結束碼紀錄。上層沒有週期、一直沒開格時，只靠容量淘汰；上層本身是掛載行程時，它結束就一起清（同「掛它的 node 被解除」）。

依據：使用者方向 2026-09-29；第十八批加淘汰與清除（行為從 P-106 搬上）；第十九批改名（原「once 診斷」）；astra 審整理區裁定裁-2（保留期改成上層的格數）。

**驗收：**掛載行程結束仍列得到且 `registered:false`；超過容量或保留期的紀錄消失；`mount.clear` 帶上層 node 時整棵子樹的已結束紀錄都清掉、別人的不動；重啟後舊結果消失。

## B-612：tick–daemon 通道

〔使用者方向 2026-09-30 晚〕通道與憑證留核心，訊息收送由 [B-614 訊息部件](messaging.md) 提供。不開 daemon 時 node 之間的溝通，基底不考慮。

依據：[09-30 晚裁定](../../../notes/2026-09-30-daemon-split-and-multi-daemon.md)；開關細節見 [B-615](components.md)。

**通道是 daemon 開的 tick 跟 daemon 之間的 IPC，也是唯一逃生口。** 通道上只有這幾件事：

- 登記與解除（含覆蓋上層）；
- 把行程掛到 daemon 上跑與砍掉；
- 叫醒別的 tick；
- 傳訊（送與取暫存訊息）。

其他所有事都必須在某一格 tick 裡做，不准有別的背景程序或常駐服務繞過 tick；要常駐就用 `node.mount` 掛（B-613）。

**通道事務由任務自己呼叫**，都不是 daemon 的事：系統訊息佇列由系統級任務 `aos-mq post` 送、`aos-mq get` 取（[B-624](../tick.md)、[B-623](../tick.md)）；once 由任務掛行程；換帳號由普通程式 `aos-as` 呼叫 `spawn_as`（B-609）。method 形狀、參數與錯誤碼見 [P-117～119](../protocol/daemon/channel.md)。

依據：第十九批第 9 條；第二十批方向 4、追答 5。

### 誰有通道

只有 daemon 開的程序——登記的 node 的每一格，以及每個掛載行程（B-613）。daemon 開它時在環境放兩個變數：

| 變數 | 內容 |
|---|---|
| `AOS_DAEMON_SOCKET` | daemon 的 socket 絕對路徑，就是設定的 `socket_path` |
| `AOS_TICK_TOKEN` | 本格憑證 |

- 任務會繼承這兩個變數；在「投件權就是執行權」之下這是預期行為（[T-08](../../terms.md)）。
- inst 的 `envs` 用 `clear` 時兩個都會被清掉，等於不給那一項通道。怎麼放進子程序環境以 [inst](../../base/inst.md) 為正本。
- cron、人手直接跑的 tick 沒有這兩個變數。缺變數時由客戶端自己擋下、報 `no_channel`，不送到 daemon（P-117）。沒通道只算功能受限：`aos-mq`、`aos-as`、once 用不了，其他照常（[T-10](../terms.md)）。
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

客戶端只對前兩列附憑證，其他照舊用自己的帳號送（[P-117](../protocol/daemon/channel.md)）。

**格式**：通道上的請求屬 daemon IPC，照 [C-07](../../contracts.md) 維持嚴格，不認得的欄位拒收；封包上限同 IPC 的 256 KiB。

**驗收：**daemon 開的 tick 有兩個變數，直接跑的沒有、客戶端報 `no_channel`；上一格的憑證在下一格用回 `token_invalid`；daemon 重啟後舊憑證全部失效；別的帳號拿到憑證也用不了；inst 的 `envs` 用 `clear` 的任務拿不到變數。

## B-613：掛行程與砍掉

**把一個行程掛到 daemon 上跑、之後再砍掉，是通道的核心事務。** 原本 daemon 端的 once 登記改成這一套；once 是任務自己經通道呼叫的事務，不是系統級任務（[B-629](../tick.md)）。要在格外常駐的程序，一律用這一套掛，daemon 追得到、`node.kill` 砍得掉。被掛的可以是任何 inst，也可以是另一個 tick 的資料夾（daemon 就跑它一格）。

依據：第十九批第 3、9、10 條；第二十批追答 5。

### 掛上

- `node.mount` 帶目標 inst 路徑（資料夾或單檔），daemon 立刻開一個 runner 跑它。
- 不需要事先登記、不接受週期、不能有成員，也不要求 tasks 或 git。
- 回應帶這次的 `registration_id`，之後用 `node.show` 查結果。

### 資源與核權歸掛的那個 tick

- 帶憑證時，上層就是憑證所屬的 tick。也可以帶 `parent_id` 指定成它有效上層鏈之下的某個 node（例如 kernel 替成員掛工作，歸成員），但不能指定成自己以上或別隊的 node。
- 不帶憑證時（人手、CLI）必須帶 `parent_id`，呼叫者要是它的 owner 或祖先 owner。
- 不另收可自報的 cgroup 路徑。掛載行程由自己的 runner 管（B-601），歸上層是核權、解除與收尾範圍的歸屬；有 cgroup 時的框歸屬與清框見 [B-613 的 cgroup 部分](cgroup.md#掛載行程的框b-613)。
- inst 的 `user` 要落在上層的身分額度內，不合回 `user_not_granted`，不存在回 `user_invalid`。kernel 不能把成員工作掛在自己的較大額度。
- 各參數怎麼填（含 agent 自跑工具、LLM 池代發）見 [P-402](../../protocol/work.md)。

### 結束與砍掉

- **結束**：行程跑完或被砍，daemon 收尾、自動移出登記表，留下 B-610 的診斷。掛它的 tick 用 `node.show` 看 `last_tick` 拿結果：`outcome`、`exit_code`、`signal` 就是這個行程的。這筆診斷會被淘汰（B-610），要留存的結果由掛的一方自己記。
- 同一個 id 在跑時再掛回 `registration_conflict`；掛載行程沒有第二次、也沒有 pending。
- **砍掉**：`node.kill` 對它做 B-604 的收尾。核權看掛它的那個 tick 的**路徑**（上層與上層鏈），不看當時那張憑證，所以上一格掛的、這一格也能砍。已經結束的回 `not_registered`；對登記的 node 送 `node.kill` 回 `kind_mismatch`。取消在跑的工作就用它（[B-203](../../base/execution.md)）。
- **失敗證據**：前置失敗也算用掉這次掛行程；沒確認後代清空就保留阻擋。`not_registered`、重啟或沒收到回應都不是重跑許可，判讀見 [S-401](../../scheduling/operations.md)。

### 單檔的未啟動旁檔

目標是單檔、而 daemon／helper 拒絕啟動 runner，或可信 runner 回報 `started:false` 時，daemon 在這個 inst 旁發布 `<inst 檔名>.err`（例如 `job.json.err`，格式見 [P-110](../protocol/daemon/provision-and-runner.md)）。

- 私有的 PascalCase 錯誤要映成 `user_not_granted`、`user_mismatch`、`source_changed` 或 `start_failed` 等小寫代碼，不直接抄 runner 的錯誤。
- 每次掛行程用新的 inst 路徑，不覆蓋既有旁檔；以已授權目標的目錄 handle 發布，不能藉此任意寫檔。
- 旁檔衝突或寫不出就 stdout 印一行警告，不另存 daemon 事項；掛的一方沒證據仍保留 unknown。
- 目標是資料夾時，啟動失敗寫它自己的 `.aos/attention/`，不寫旁檔。
- runner 已放行後不寫這份旁檔；之後的 125、126／127 或結果遺失依 [work](../../base/work.md) 處理。

依據：使用者方向 2026-09-29（第十一批與後續旁檔改名裁定）；第十九批從 P-110 搬上。

### 其他

- 排空停機時拒收新的掛行程，等已掛的跑完（B-604）；掛載行程不存檔，重啟後不接回（B-603）。
- 掛載行程也有通道（B-612），憑證綁它自己；它沒有收件匣，`node.take` 回 `kind_mismatch`。

**驗收：**tick 在第一格掛一個常駐行程、第四格用 `node.kill` 砍掉，砍得掉而且收尾完成；別隊的 tick 砍不掉；帶 `parent_id` 指到自己上層鏈之外被拒；人手不帶憑證又沒帶 `parent_id` 被拒；單檔目標未啟動時有 `.err`，已放行後沒有。

