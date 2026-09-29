# daemon 協議

← [共用約定](README.md)｜行為正本：[daemon](../daemon.md)、[身分](../base/identity-resources.md)、[inst](../base/inst.md)｜[裁定](../../notes/2026-09-29-verdicts.md)

## P-100．範圍〔使用者方向 2026-09-29〕

本篇定 daemon 的設定、IPC、helper 與 runner；責任與重啟行為見 [daemon 正本](../daemon.md)，JSON 與錯誤見 [共用約定](README.md)。

## P-101．啟動、設定與 socket〔建議預設，未拍板〕

完整 argv：`aos daemon --config /absolute/daemon.json`。前景執行；stdin 不讀，stdout 啟動成功時只印一行 `helper_pid=<PID>`，無 helper 印 `helper_pid=none`；stderr 放啟停及錯誤診斷。讀設定、登記 inst 的原始 bytes（部署須授通用 user 必要讀取及目錄穿越權；讀不到就拒絕，不交 root 代讀），寫 socket、attention 通知及 P-110 的 once 失敗旁檔；不替 node 讀其他檔案。環境不作授權，不定義 `AOS_*` 變數。正常停機回 0；用法／設定尚未開始做事前失敗回 2；初始化、清空或運行中的 daemon 自己失敗回 125。SIGINT／SIGTERM 走 P-114 的正常停機；其他訊號由父程序看 wait 狀態。

[設定 schema](schemas/daemon-config.schema.json)：

| 欄位 | 意思 |
|---|---|
| `version` | 必填，1 |
| `common_user` | 可省，非空帳號名稱或非負 UID；預設見 P-102 |
| `socket_path` | 必填，正規化絕對檔案路徑，例如 `/run/user/1000/aos/daemon.sock`；多 UID 部署可用 `/run/aos/daemon.sock` |
| `attention_dir` | 必填，待處理事項資料夾；daemon 須可寫，檔案格式交 ops 篇 |
| `shutdown_grace_ms` | 可省，預設 2000，非負毫秒；到期後依執行器收尾 |
| `cgroup_root` | 可省，部署已準備且授權的 cgroup v2 子樹絕對路徑；要用 cgroup 動作才需要 |
| `roots` | 必填，頂層登記陣列；每項如下，`node_id` 不可重複 |

頂層項必填 `node_id`、`identity_grant`，可帶正整數 `interval_ms` 與 `provision`；無 parent_id／once。身分額度是非空、不重複的帳號／UID 陣列。inst 尋找及 base 只依 [P-010](README.md)；頂層與普通 node 必須是資料夾，once 可為單檔。找不到 inst 是用法錯 2；IPC 註冊回 -32602／invalid_params，不使 daemon 退出。

`provision` 是可省的固定動作授權：`{"actions":[…],"paths":[…]}`，兩欄必填、各自不得重複；省略等於無佈建權。`actions` 只認 P-107 六種；`paths` 是可佈建的絕對目錄範圍，空陣列不授任何路徑。`cgroup_root` 不是一般可寫路徑授權。

設定於啟動讀定，修改後重開 daemon。部署者先配置 socket 父目錄的穿越權及 socket 的連接權；預設父目錄 0750、socket 0660，群組／ACL 由部署配置，不在封包給任意人改。無法 bind、位置過長或權限不足就明確失敗。每個 socket_path 對應一把同目錄的 `daemon.lock` 獨占鎖；持鎖後才能清理屬於這個實例的殘留 socket，不能刪活著的 socket。可連 socket 不等於通過 method 授權。

## P-102．sudo 與 helper 生死〔使用者方向 2026-09-29〕

啟動模式、SUDO_UID、永久降權、kill helper 不重拉及 daemon 死亡連帶退出，完全依 [B-303](../base/identity-resources.md)。helper PID 依 P-101 輸出；非 root 啟動只准通用 user，改設定不能冒充切 UID。

〔建議預設，未拍板〕root 設定及父目錄不得由不受信任 node 改寫；fork 前固定設定副本，處理設定父死訊號的競態，父死訊號與私有通道斷線共同監看。額度不准 UID 0 或 root 別名。舊程序依 [B-603](../daemon.md) 清空；helper 消失而不能收尾時保留占用、阻止新格，不宣稱清空。

## P-103．IPC 封包與授權〔建議預設，未拍板〕

Unix stream，UTF-8 JSON 每行加 LF，含 LF 最多 262144 bytes；不用 batch／notification。請求與回應沿 [common](schemas/common.schema.json) 的 `RpcRequest`／`RpcResponse`；`params` 必填 object。每條連線逐筆處理，回應沿用請求 ID。先驗 JSON／method／參數，再以 `SO_PEERCRED.uid` 和可信註冊鏈授權；不能用 PID、路徑前綴、封包的 `user` 當呼叫者。

登記保存授權時解析出的 `owner_uid`；改 inst 不立即改掉 IPC owner。有效的下一格身分採用或經原 owner／父層授權的重新登記，才更新它。上層指可信註冊鏈的祖先，不是 OS 父目錄；同 UID 共用同一 OS 權限，不能辨別是哪個 node 或工具在呼叫。

| method | 誰可呼叫 |
|---|---|
| `node.register` | 新成員：已登記父 node 的 owner，或該父的祖先 owner；首次必須有父層同意，不能自行接到別人的鏈。既有項：原 owner 或祖先 owner；不能換父或搶別隊 |
| `node.unregister` | 目標 owner 或祖先 owner；效果包含目標已登記子樹 |
| `node.wake` | 目標 owner 或祖先 owner |
| `node.pause`、`node.resume` | 目標 owner 或祖先 owner |
| `daemon.info` | 有 socket 連接權；只回本次啟動 ID，不暴露登記 |
| `node.list` | 有 socket 連接權；逐筆只列 peer 是 owner／祖先 owner 的登記及保留的 once 結果，無可見項回空陣列 |
| `node.get` | 目標 owner 或祖先 owner；含 P-106 保留的 once 結果，不開 tick |
| `node.provision` | 目標 owner 或祖先 owner，且目標登記有相符的 `provision` 授權；需 helper 的動作再由 helper 核對 |

root／通用 user 不因名稱自帶全樹 RPC 特權；它若是 owner／祖先才符合表格。既有成員可重登自己，但不能擴大目前額度或佈建權；新授額度及佈建權限只能由父層 owner／祖先 owner 在自身授權內下授。首次由父層登記，本版不提供首次自登記。

RPC ID 只配對回應，不是永久執行收據。斷線不代表沒做；登記／pause／resume 可核對目前值，wake 可合併但不是永久去重，once 與特權動作不准因沒回應就盲重送。daemon 不加持久重播帳本。

## P-104．註冊〔建議預設，未拍板〕

`node.register` params：`node_id`、`parent_id`、`identity_grant` 必填；`interval_ms`、`once`、`provision` 可省。型別同 P-101，`parent_id` 是已登記父 node；`once` 預設 false。IPC 只登記非頂層；頂層只從設定載入，更新須改設定並重開 daemon。`once:true` 不可帶定期間隔，也不可有成員。

額度按 UID 比較、名稱與 UID 別名不得重複；子額度與動作集合只能是父額度的子集，授予的每個 path 必須落在父已授範圍。不得成環或換父。為建帳號，可預授尚未存在的**確切名稱**，只能由設定往下傳，首次建立後綁住得到的 UID；不支援萬用名稱或「自行造一個 UID」。已存在名稱按系統帳號解析；新 node 的 inst user 在登記時必須已存在。額度不是允許 impersonate 呼叫者的欄位。

有權者重送相同有效登記回成功，不清 paused／pending、不再啟動。既有項內容不同時，只在該 node 及其已登記子樹都暫停且程序全空、且所有子額度仍有效時更新；否則 `busy`。整條鏈的額度／佈建上限仍受頂層啟動設定限制。更新不重跑已開始的 attempt。

result 統一為 `{"node_id":"…"}`。新登記不自動啟動；父 kernel 在重建子 kernel 時明確再送 wake。啟動設定的 roots 由 daemon 自動各開第一格。定期 node 從登記完成起經過 `interval_ms` 才到期；每次完整收尾後重新計時，不補跑漏掉的格數；wake 將本次到期提前，運行中只留一個 pending。

〔使用者方向 2026-09-29〕**once**：kernel 備好 inst，register 後 wake；一次啟動及收尾後解除，不要求 tasks 或 git。〔建議預設，未拍板；見 P-008〕`parent_id` 同時固定**發起 node 的資源歸屬**，不另收可自報的 cgroup 路徑：daemon 從可信登記核對父存在、呼叫者是父 owner／祖先 owner、工作身分在父額度內，工作 leaf 必須放在父框內。kernel 不能把成員工作掛在自己的較大額度；LLM HTTP 的發起者則是池管理 node。

前置失敗也消耗這次啟動要求並解除；沒確認後代清空就保留阻擋登記。once 不留第二格 pending，結果由 [work P-402～404](work.md) 交 kernel；未啟動證據見 P-110。`not_registered`、重啟或沒收到 IPC 回應都不是重跑許可。

## P-105．解除、叫醒、暫停與恢復〔建議預設，未拍板〕

四個 method 的 params 都只有 `node_id`，result 都是 `{"node_id":"…"}`。

- `node.unregister`：立即阻止目標及已登記子樹的新格，按 [B-604](../daemon.md) 排空；**確認所有後代全空後**才刪登記並回成功。無法清空回 `cleanup_failed`，保留阻擋狀態。自己在 tick 內同步等自身 unregister 會被收尾，呼叫者不得依賴收到成功才能退出；通常由父層發起。持久停用仍由父 kernel 改自己的成員設定。
- `node.wake`：接受一個開格提示；正在跑時合併成一個 pending，paused 時只記 pending，stopping 時拒絕。成功不是已開跑或工作完成證據。once 只接受第一次待啟動要求，之後合併、不加第二格。
- `node.pause`〔使用者方向 2026-09-29〕（第十批）：只停**該 node**新格，不殺本格、不遞迴暫停子樹；回成功代表閘門已關。手改還須 `node.get` 看 `running:false`，再持 node 鎖、修改及 commit。`running` 包括後代清理期間。
- `node.resume`〔使用者方向 2026-09-29〕（第十批）：只開該 node 的閘門；呼叫者先完成 [A-102](../agent/configuration.md) 的驗證／commit。daemon 不讀 git、不替手改 commit，也不替 unknown 工作重試。pending 或到期才開格，否則等下一次 wake／到期。

不存在的目標回 `not_registered`（包括重送已完成 unregister）；pause／resume 同狀態重送無害。暫停旗標只在記憶體；重啟會消失，不能代替持久停用或暫停 run。需要維護跨 daemon 重啟時，部署者須停 daemon／調整啟動與父層設定。

**故障停格接法**：非 once 登記把可信子程式退出 `3`／`125` 保留為停格碼；runner 前置失敗、缺可信回報或後代清不空也停格。daemon 先設 `paused:true` 再處理 pending／到期，寫 [ops 事項](ops.md)，不解析 stderr、不靠 tick 再發 IPC。這是所有非 once 目標的調度約定；普通程式回這兩碼也暫停，但不因此推論它沒執行。tick 的 commit／還原故障回 3、格首擋板回 125，見 [node P-203／205](node.md)。手動 node.pause 與自動停格使用同一閘門；resume 前修復者須清後代、持鎖核對基線並移除擋板。擋板寫不出時仍可在本次 daemon 存續期間停格；重啟前須由部署者完成修復，不能把記憶體 pause 當耐久故障紀錄。

## P-106．查登記與最近一格〔使用者方向 2026-09-29，CLI H-034 D1；欄位為工程預設〕

`node.get` params 只有 `node_id`。result 必填 `boot_id`（P-115）、`node_id`、`parent_id`（頂層為 null）、`identity_grant`、`owner_uid`、`once`、`registered`、`paused`、`running`、`pending`、`stopping`、`last_tick`；有設定才附 `interval_ms`、`provision`。root 的 once 固定 false。`registered:true` 表示還在調度表；false 只供已解除的 once 診斷記錄，此時 paused／running／pending／stopping 都是 false。

`cgroup` 也必填：沒有活的配置為 null（含已解除 once），否則回實際讀到的 `{path,limits}`，不是上次請求快取。limits 的 CPU 用 `{quota_us,period_us}`，memory／pids 沿 P-107，無上限回字串 `"max"`，未啟用 controller 省略。應存在卻讀取失敗回 `resource_observation_failed`，不能回 null 冒充沒配置。

`last_tick:null` 表示本次登記還沒派出過；否則只保存最近一格，必填下表六欄。新格派出時取代前格，不是完整歷史。

| 欄位 | 意思 |
|---|---|
| `started_at_ms` | daemon 接受這次開格並進入啟動流程的 UTC 毫秒；包含啟動前檢查，**不是程式已開始的證據** |
| `ended_at_ms` | 完成收尾的 UTC 毫秒；還在啟動／執行／清後代時為 null |
| `exit_code` | 可信 runner 回報的 0～255 整數；執行中或結果不明為 null |
| `started` | 可信 runner 的 started；completed 為 true、launch_failed 為 false，running 為 null；unknown 只在已有可信 started:true 時填 true，否則 null |
| `signal` | completed 時可信回報明列的子程式訊號（1～64），其餘或沒有則 null；不能從 exit_code 的 128+N 倒猜 |
| `outcome` | `running`＝啟動／執行／收尾中；`completed`＝可信 started:true 且完成收尾；`launch_failed`＝可信 started:false；`unknown`＝沒可信回報或 FinalizeFailed。completed 可是非零，絕不等於業務成功 |

running 時 ended_at_ms／exit_code 必須 null；其他 outcome 必須有 ended_at_ms。launch_failed 的 exit_code 只准 2／125；unknown 必須 null，保留診斷但不從 runner wait 碼猜業務退出碼。running:false 只在受管程序及後代已全空時成立；後代清不空時仍 running:true、outcome:running，另以 stopping:true 及 attention 暴露故障，不能先記成已完。時間可能受牆鐘校正影響，不據此排序格數或推算 timeout。

`node.list` params 是 object，可省 `limit`（1～64，預設 64）與 `after_node_id`（NodeId）。result 是 `{boot_id,nodes,next_after_node_id}`：nodes 每項與 node.get 同形狀，按 node_id 的 UTF-8 bytes 升序；先按 peer 權限篩選，再取嚴格大於 after_node_id 的項。未列完時 next_after_node_id 是本頁末項 ID，列完為 null；不得回空頁卻還給下一頁。每頁亦受 P-103 封包上限約束，裝不下一項就縮頁，單項仍過大回 `response_too_large`。只列有權看者，不泄漏總數或無權項。不同頁不是同一瞬間快照；每次接續必須使用剛收到且嚴格前進的 next_after_node_id，boot_id 變了就重列，需要核對單項用 node.get。持續變動時本輪不追補游標前新插入的項，避免無限追列。

**once 留存**：一次收尾解除後，在本 daemon 記憶體留一筆 registered:false 的最近結果，保留原 owner_uid 與 parent_id，查詢時以**目前仍在的可信父鏈**重驗；祖先權限撤銷即生效，不能靠舊祖先快照繼續讀。父額度撤掉該 owner 身分時一併清除此 once 診斷；父被解除也清除。只供 get/list，wake／pause／resume 等仍回 not_registered。留到 daemon 結束、同 node_id 通過新登記，或其父子樹被明示 unregister；不寫檔、不把它算正在占用的登記。不設計時淘汰，避免人手來不及看；長期大量 once 的診斷記憶體成本可由部署安排重啟清掉。普通 node 被解除不留此記錄。新 once attempt 應用新 inst 路徑，見 work 篇。

人手 `aos node ls --socket S` 使用 node.list，`aos node show N --socket S` 使用 node.get；多個 `--node` 可逐個 get。畫面須把「已解除 once」「未啟動」「還在跑」「結果不明」分開。IPC 只回記憶體診斷，不讀工作結果／git，也不是業務完成或 unknown 重跑許可。

**驗收：**不同 UID 只能列自己的授權子樹；未跑顯示 last_tick:null；已放行後程式回 125 是 completed，身分拒絕 125 是 launch_failed（仍可能已有開檔副作用）；once 結束仍列得到且 registered:false；重啟後舊結果消失。分頁跨重啟須能靠 boot_id 發現。

## P-107．佈建固定動作〔建議預設，未拍板〕

`node.provision` params 為 `node_id` 與 `action`，其餘依下表；每次只做一件，不提供 shell、argv、任意 syscall 或任意 mount options。授權與允許 path 取**該 node 的登記**，執行端不信封包自報。成功 result 為 `{"node_id":"…"}`；做完並驗證才回，不能把已送 helper 當完成。

| `action` | 其他必填欄位 | 固定效果與範圍 |
|---|---|---|
| `account_create` | `user`：確切帳號名稱 | 名稱已在身分額度、尚未存在才建立非 root 帳號及同名主群組；無登入 shell、不建 home、不收密碼。已存在且符合先前綁定就核對後成功，不能接管同名不同 UID |
| `chown` | `path`、`user` | 單一路徑改為額度內既存帳號與其主 GID；不遞迴、不收任意 GID、不跟隨 symlink |
| `cgroup_create` | 無 | 在可信父資源子樹內建立本 node 的分支及執行 leaf；路徑由 daemon／helper 從登記推導，呼叫者不能給 cgroup 路徑 |
| `cgroup_limits` | `limits` | 非空 object，可有 `cpu_max:{quota_us,period_us}`、`memory_max_bytes`、`pids_max`，皆正整數；CPU 直接使用 cgroup 微秒，是 P-002 的明示例外，檢查 controller 範圍後原值寫入；只寫這些 controller，作用於 node 分支並含後代；不設該欄就不新增該項限制 |
| `quota` | `path`、`project_id`：正整數 | 只配置該路徑的 project **計量歸屬**；不設定磁碟硬上限或 soft limit。不支援就報 `unsupported`，沒裝磁碟 module 不呼叫 |
| `mount` | `path`、`size_bytes`：正整數 | 首版只支援在已授權的空目錄掛 tmpfs，固定 `nodev,nosuid,noexec`；不用 caller 提供的來源、類型或 options；容量可見，不保證 `/tmp` 都是 tmpfs |

路徑操作必須在被授 `provision.paths` 內（按元件判定，不用字串前綴）；helper 固定目錄 handle、拒絕 symlink 穿越及替換競態，逐步核對實體路徑。已經掛著相同設定核對後成功，不同設定回 `conflict`，不卸載／覆蓋。quota 不搶走其他 node 的 project 歸屬。帳號不自動刪除或回收。

cgroup 的 node 分支承接父限制，執行 leaf 容納本 node 程序，子 node 分支留在同一父資源樹；module 決定哪些限制有值，daemon 不排資源。helper／收尾程序留在成員限額之外。**無 helper 時，daemon 以通用 user 在 systemd 委派的 cgroup_root 子樹內自己建框、寫限制及讀實際值**；授權和父限制照舊。未委派或 controller 不可用回 unsupported。只有建帳號、chown、quota、掛載需要 helper，無 helper 回 helper_unavailable。

cgroup_limits 改值時，daemon 先關受影響子樹的啟動閘門，與 pending start／wake／週期派出互斥；執行端核對整個框及後代全空才套用，否則 busy。已是相同值可核對後成功，不重寫。helper 的 start／limits 也須按同一資源子樹串行；不能只靠呼叫者先查 node.get。kernel 先逐筆暫停受影響子樹、等全空再要求更新；node.pause 本身不遞迴，更新後也不代替呼叫者 resume。

首次建 node 前，可先用父 node 的佈建權在授權 path 建立必要權限／帳號，再登記成員。建立帳號不擴大額度。所有動作只保證單步完成後回覆，沒有跨步回滾；斷線或中途失敗須先核對 OS 事實，不能盲重送或自動「撤回」chown／mount。

## P-108．daemon 與 helper 的私有通道〔建議預設，未拍板〕

fork 前建 Unix SOCK_SEQPACKET socketpair，只供 daemon／helper；每包一個 JSON-RPC、最多 256 KiB、無 LF。必要 fd 以 SCM_RIGHTS 同包傳，數量不符即拒；runner／子程序不繼承通道。這是內部實作，沒有第三種公開入口。

| method | params／fd | 效果 |
|---|---|---|
| helper.bind | registration、owner_uid；1 個密封 inst 快照 fd | 以啟動根額度、可信父鏈、原始 user 及路徑重驗；頂層 registration 用 P-101 形狀，只能是設定已有 roots |
| helper.unbind | node_id；無 fd | 全空且無已登記子節點才移除鏡像，子到父依序解除 |
| helper.start | node_id、target_uid；inst 快照與回報 pipe 共 2 fd | 重驗 UID、安置已配置資源、fork／降權／exec 固定 aos-runner；不收自訂 argv／env／輸出路徑 |
| helper.stop | node_id；無 fd | 只停登記範圍，TERM、2 秒後 KILL、確認後代全空；不收任意 PID／訊號 |
| helper.provision | P-107 params；無 fd | 重驗授權與固定動作後執行 |

成功 result 都為 `{node_id}`。start 要等 runner 結束、wait 回收與後代全空才回；daemon 從送出起就記 running。通道按 id 配對多筆在途，不能因等一格堵住其他 node／stop。全空但業務失敗仍可完成 start；無法全空回 cleanup_failed，保留阻擋及占用。

helper 用安全程序 handle 追蹤、wait 自己的孩子並跨 UID 收尾；daemon 不 wait helper 的孩子、不信裸 PID。helper 失聯時 daemon 只做自身權限可做的收尾，其他 UID 未確認全空就阻擋，斷線不代表退出，也不能重送不明 start。

快照是 daemon 取原始 user 的同份不可變 bytes。helper 不以 root 展開引用；runner 切身分後重新確認原來源可讀且 bytes 相同，才解析快照，base 仍依 P-010，不以快照位置計算。helper 以 OS handle 核對實體路徑，不能只信正規化字串。

鏡像只在記憶體。helper 存活時 bind／更新先通過它才公開；無 helper 時通用 user、無佈建權的登記可本地核對，不要求 cgroup；只授 cgroup 動作時另核對委派子樹。其他 UID／四種特權動作的新登記回 helper_unavailable。既有通用 user 仍可執行。

## P-109．runner argv 與解析〔建議預設，未拍板〕

固定 argv：`aos-runner --inst-fd N --target /absolute/target --authorized-uid UID --status-fd N [--stderr /absolute/path] [--timeout-ms N]`。fd 已由父層打開；target 按 P-010 定原來源與 base，不改尋找規則。timeout 為正整數，省略不另加；authorized-uid 只是核對，不授予直接呼叫者切 UID 的能力。

啟動時已降權、設好群組與資源；依 P-108 驗 UID／來源，再按 [inst 正本](../base/inst.md) 的順序展開與開檔。整份引用不得換已授權身分。

daemon 初始 stdin／stdout 為 /dev/null，stderr 接診斷；inst 可重導向子程序串流。--stderr 由目標身分以覆寫方式開檔、不自建父目錄，蓋過 inst 的 stderr 選項；runner 診斷仍走自身 stderr。status-fd 只供 runner，子程序 exec 前關閉。

環境依 [B-303](../base/identity-resources.md)，不注入 AOS_* 或帶管理 fd／key；$env 先讀該環境，再套 inst.envs。所有檔案、mkdir、exit 皆用目標帳號。

## P-110．runner 結束與 125〔建議預設，未拍板〕

回報 pipe 一行 JSON、LF 結尾，無 version（非持久檔）；[schema](schemas/daemon-runner-report.schema.json)。每次完整收尾只回報一次：

- 前置失敗：`{"started":false,"exit_code":125,"error":{"code":"UserNotGranted","message":"身分不在額度內"}}`。`error.code` 沿 inst 的 PascalCase 代號；CLI 用法錯則 exit_code 2。父層尚未 exec runner 的拒絕由父層合成相同回報。**不寫 inst exit**。
- 已越過執行前檢查／放行：`{"started":true,"exit_code":125}` 也合法，表示子程式自己退出 125；正常結束回原碼，找不到程式 127、不能執行 126 都屬此分支並寫 exit。子程式被 signal 結束時另帶 `signal`，exit_code 依 inst 為 128+N。runner 自己被殺則父程序讀 wait 狀態，不能從 128+N 猜。

runner 用法錯（含資料夾兩處皆無 inst）回 2；前置解析、開檔、身分失敗回 125，stderr 印 `代號: 白話`；其餘碼照 inst。signal、126／127 是 inst 執行規則對 [P-006](README.md) 的特例。前置檢查可能已建立目錄或截斷輸出，125 不是「沒有任何檔案副作用」。

若已放行卻在寫 exit／收尾／發布回報時自己失敗，程序回 125，回報若仍可寫則 `started:true, exit_code:125, error:{code:"FinalizeFailed",message:"…"}`；不能把它當子程序已確定退出 125。沒有完整可信回報則結果不明，不能從 runner 碼推定從未執行。工作篇的結果檔保留這個區別與已取得的 wait 證據，這條 pipe 回報不是另一份持久工作結果。

後代清空、捕獲排空及取消競態依 [B-202／203](../base/execution.md)。最終成功需要該範圍全空；收尾失敗可回 FinalizeFailed，但不能因此釋放尚在用的名額或開下一格。所有失敗不自動重跑 unknown。

〔使用者方向 2026-09-29，第十一批與後續旁檔改名裁定〕**once 未啟動的最小旁檔**：當 daemon／helper 拒絕啟動 runner，或可信 runner 回報 `started:false`，daemon 在本次選定的 inst 旁發布 `<inst 檔名>.err`（例如 `job.json.err`），格式為 `{version:1,node_id,error}`，見 [schema](schemas/daemon-launch-error.schema.json)。error 使用 P-005；私有 PascalCase 必須映成 `user_not_granted`、`user_mismatch` 或 `start_failed` 等小寫代碼，不直接抄 runner error。每個 attempt 用新 inst 路徑；不覆蓋既有旁檔。

註冊時由 daemon 核對目標父目錄、可寫旁檔及 kernel 可讀的權限；單檔不存在但父路徑可信時仍可寫失敗旁檔。資料夾兩處皆缺 inst 時以 `.aos/` 已存在者的 inst.json 為旁檔基準，否則用根 inst.json；只決定診斷位置，不是覆寫尋找規則。不可信／無權的註冊不能藉此任意寫檔。固定目錄 handle、防 symlink、依 P-003 原子發布；同名異內容或寫不出時回錯誤並留 attention／stderr，kernel 沒證據就保留 unknown，不能聲稱一定看得到。

runner 已放行後不寫這份「未啟動」旁檔；wrapper 自己的 125、exec 126／127 或結果遺失依 work 篇處理。daemon 的暫存 wait 證據可供診斷，但不是另一份持久工作結果。

## P-111．錯誤〔建議預設，未拍板〕

RPC error 沿 P-005；`data` 必填 `code`、`retryable`。解析／請求／method／參數／內部錯誤分別用保留碼，其他用 -32000。下列是本篇的業務 code：

| code | 意思；預設 retryable |
|---|---|
| `forbidden`、`user_not_granted` | peer 無權／超出身分額度；false |
| `user_invalid`、`user_mismatch` | 帳號不能解析／前後身分不合；false |
| `not_registered`、`registration_conflict` | 目標或父不存在／搶登記、換父、成環；false |
| `busy` | 活程序、維護狀態不合；true，等全空後先查狀態 |
| `stopping`、`cleanup_failed` | 正在停／無法確認後代清空；false |
| `helper_unavailable`、`unsupported` | helper 不在／部署不支援所選固定動作；false |
| `path_not_granted`、`conflict` | 超路徑範圍／OS 現況不符所要求設定；false |
| `resource_observation_failed` | cgroup 實際配置無法讀取；false |
| `response_too_large` | 一筆查詢結果就超過封包上限；false |
| `provision_failed`、`start_failed` | 固定動作或啟動失敗；false，先核對是否已有副作用 |

標準碼的 data.code 依序為 parse_error、invalid_request、method_not_found、invalid_params、internal_error，retryable=false。取不到合法 ID 的解析／請求錯誤依 P-004 回 `id:null`；超長行回一次 invalid_request 後關連線，避免無界讀取。可辨識合法 ID 就沿用，不造新 ID。

## P-112．schema 與最小範例〔建議預設，未拍板〕

[common](schemas/common.schema.json) 只放共用型別；[daemon-rpc](schemas/daemon-rpc.schema.json) 驗公開 IPC，[registration](schemas/daemon-registration.schema.json) 與 [provision](schemas/daemon-provision.schema.json) 驗其參數，[helper](schemas/daemon-helper.schema.json) 驗私有通道。

[examples/daemon/](examples/daemon/) 以檔名首段對應 schema：config、runner_report、launch-error 各驗同名 schema；helper_* 驗 helper，其餘驗 rpc。每種訊息一正一反。反例 once_interval＝once 帶週期；version＝錯版本；missing_running／missing_retryable＝缺必填；false_success＝未啟動卻成功；launch-error 的 private-code＝錯把私有字串當 P-005 數字碼；parse-error 的 success＝null ID 冒充成功；其他 extra＝未知欄位或 result/error 雙分支。查詢新增 info／list 正反例；info_result.empty_boot 的 boot_id 不可空、list.zero_limit 的 limit 不可零、list_result.running_exit 的執行中結果不得帶結束碼、get_result.launch_success 的未啟動結果不得帶成功碼。解析、授權與 OS 事實仍依正文檢查。

## P-113．待決與跨篇

見 [README P-008](README.md#p-008)。

## P-114．前景 Ctrl-C 停機〔使用者方向 2026-09-29，裁定「軟性標準」／CLI H-036 第 1、7 步〕

`aos daemon --config F` 收到 SIGINT（前景 Ctrl-C）或 SIGTERM，先停止接受新登記／叫醒／開格，再按 [B-604](../daemon.md) 對所有受管程序及後代收尾。shutdown_grace_ms 到期依執行器 TERM／KILL 與安全程序 handle 規則完成清空；再次收到 SIGINT／SIGTERM 不跳過清空驗證。正常清空、helper 退出及 socket 清理後回 0；清不空／自身收尾失敗回 125 並留 stderr／可寫的 attention，不聲稱安全停止。root helper 也須跟著退出；只 kill helper 不是停止 daemon。

首版沒有跨終端 `aos daemon stop` 或 shutdown IPC。非正常死亡後仍由下次啟動的 B-603 檢查舊程序，不因 socket 不見就推論已全空。

**驗收：**有執行中 node 時 Ctrl-C／SIGTERM 都不開新格，等全部受管後代與 helper 全空才回 0；清不空不得回 0。

## P-115．啟動 ID 與按需重建〔使用者方向 2026-09-29，裁定「kernel 別每格都重新註冊」；欄位為工程預設〕

`daemon.info` params 為 `{}`，result 只有 `boot_id`（共用 ID，建議隨機 UUID）。每次 daemon 啟動新生一個，整次存續不變，重開不得沿用；只放記憶體，socket 路徑相同也不能沿用。node.get／node.list 的 boot_id 跟它一致。這是 daemon 的啟動識別，不是 node 世代號；node 路徑的 symlink 別名、同路徑換 node 或跨機同名不另做識別檢查（最新唯一性裁定）。

kernel 將上次成功同步的 boot_id 與已提交成員清單版本記在自己的 repo；每格可用這個小查詢比對，兩者沒變且沒有待修復差異就不重送 register。daemon 重開、清單改了、或已知成員被解除才核對差異並重登；父 kernel 明確叫醒新重建的子 kernel，讓樹逐層長回來。部分成員失敗不得把它標成已成功同步，壞成員不妨礙其他成員；重查／修復細節由 kernel 任務篇定。重建不包含重送 unknown once 工作。

**驗收：**連續十格無變動只查 boot_id、不重登十次；daemon 重開後 boot_id 改變，各 kernel 逐層補回成員；改一筆成員只同步差異，失敗筆下次仍能重查。
