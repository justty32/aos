# daemon 協議：註冊、叫醒與查登記

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

## P-104．註冊〔建議預設，未拍板〕

`node.register` params：`node_id`、`parent_id`、`identity_grant` 必填；`interval_ms`、`once`、`provision` 可省。型別同 P-101，`parent_id` 是已登記父 node；`once` 預設 false。IPC 只登記非頂層；頂層只從設定載入，更新須改設定並重開 daemon。`once:true` 不可帶定期間隔，也不可有成員。

額度按 UID 比較、名稱與 UID 別名不得重複；子額度與動作集合只能是父額度的子集，授予的每個 path 必須落在父已授範圍。不得成環或換父。為建帳號，可預授尚未存在的**確切名稱**，只能由設定往下傳，首次建立後綁住得到的 UID；不支援萬用名稱或「自行造一個 UID」。已存在名稱按系統帳號解析；新 node 的 inst user 在登記時必須已存在。額度不是允許 impersonate 呼叫者的欄位。

有權者重送相同有效登記回成功，不清 paused／pending、不再啟動。既有項內容不同時，只在該 node 及其已登記子樹都暫停且程序全空、且所有子額度仍有效時更新；否則 `busy`。整條鏈的額度／佈建上限仍受頂層啟動設定限制。更新不重跑已開始的 attempt。

result 統一為 `{"node_id":"…"}`。新登記不自動啟動；父 kernel 在重建子 kernel 時明確再送 wake。啟動設定的 roots 由 daemon 自動各排第一格；恢復的 pause 仍有效，見 P-116。定期 node 從登記完成起經過 `interval_ms` 才到期；每次完整收尾後重新計時，不補跑漏掉的格數；wake 將本次到期提前，運行中只留一個 pending。

〔使用者方向 2026-09-29〕**once**：kernel 或自管工具的 agent 備好 inst，register 後 wake；一次啟動及收尾後解除，不要求 tasks 或 git。〔建議預設，未拍板；見 P-008〕`parent_id` 同時固定**發起 node 的資源歸屬**，不另收可自報的 cgroup 路徑：daemon 從可信登記核對父存在、呼叫者是父 owner／祖先 owner、工作身分在父額度內，工作 leaf 必須放在父框內。kernel 不能把成員工作掛在自己的較大額度；LLM HTTP 的發起者則是池管理 node。

前置失敗也消耗這次啟動要求並解除；沒確認後代清空就保留阻擋登記。once 不留第二格 pending，結果由 [work P-402～404](../work.md) 交發起者；未啟動證據見 P-110。`not_registered`、重啟或沒收到 IPC 回應都不是重跑許可。

## P-105．解除、叫醒、暫停與恢復〔建議預設，未拍板〕

四個 method 的 params 都只有 `node_id`，result 都是 `{"node_id":"…"}`。

- `node.unregister`：立即阻止目標及已登記子樹的新格，按 [B-604](../../daemon.md) 排空；**確認所有後代全空後**才刪登記並回成功。無法清空回 `cleanup_failed`，保留阻擋狀態。自己在 tick 內同步等自身 unregister 會被收尾，呼叫者不得依賴收到成功才能退出；通常由父層發起。持久停用仍由父 kernel 改自己的成員設定。
- `node.wake`：要求現在跑一格；正在跑時合併成一個 pending，paused 時只記 pending，stopping 時拒絕。成功不是已開跑或工作完成證據。once 只接受第一次待啟動要求，之後合併、不加第二格。
- `node.pause`〔使用者方向 2026-09-29〕（第十批）：只停**該 node**新格，不殺本格、不遞迴暫停子樹；回成功代表閘門已關。手改還須 `node.show` 看 `running:false`，再持 node 鎖、修改及 commit。`running` 包括後代清理期間。
- `node.resume`〔使用者方向 2026-09-29〕（第十批）：只開該 node 的閘門；呼叫者先完成 [A-102](../../agent/configuration.md) 的驗證／commit。daemon 不讀 git、不替手改 commit，也不替 unknown 工作重試。pending 或到期才開格，否則等下一次 wake／到期。

不存在的目標回 `not_registered`（包括重送已完成 unregister）；pause／resume 同狀態重送無害。pause／resume 是關／開閘門，不等於 wake；pause 有變動時按 P-116 批次保存，正常停機完整保存。

**故障停格接法**：非 once 登記把可信子程式退出 `3`／`125` 保留為停格碼；runner 前置失敗、缺可信回報或後代清不空也停格。daemon 先設 `paused:true` 再處理 pending／到期，寫該 node 的 [`.aos/attention/`](../ops.md)，不解析 stderr、不靠 tick 再發 IPC。這是所有非 once 目標的調度約定；普通程式回這兩碼也暫停，但不因此推論它沒執行。tick 的 commit／還原故障回 3、格首擋板回 125，見 [node P-203／205](../node.md)。手動 node.pause 與自動停格使用同一閘門；resume 前修復者須清後代、持鎖核對基線並移除擋板。擋板寫不出仍停格；事項也寫不出就 stdout 警告，不阻止停格；pause 的意外退出遺失界線依 P-116。

## P-106．查登記與最近一格〔使用者方向 2026-09-29，CLI H-034 D1；欄位為工程預設〕

`node.show` params 只有 `node_id`。result 必填 `boot_id`（P-115）、`node_id`、`parent_id`（頂層為 null）、`identity_grant`、`owner_uid`、`once`、`registered`、`paused`、`running`、`pending`、`stopping`、`last_tick`；有設定才附 `interval_ms`、`provision`。root 的 once 固定 false。`registered:true` 表示還在調度表；false 只供已解除的 once 診斷記錄，此時 paused／running／pending／stopping 都是 false。

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

`node.ls` params 是 object，可省 `limit`（1～64，預設 64）與 `after_node_id`（NodeId）。result 是 `{boot_id,nodes,next_after_node_id}`：nodes 每項與 node.show 同形狀，按 node_id 的 UTF-8 bytes 升序；先按 peer 權限篩選，再取嚴格大於 after_node_id 的項。未列完時 next_after_node_id 是本頁末項 ID，列完為 null；不得回空頁卻還給下一頁。每頁亦受 P-103 封包上限約束，裝不下一項就縮頁，單項仍過大回 `response_too_large`。只列有權看者，不泄漏總數或無權項。不同頁不是同一瞬間快照；每次接續必須使用剛收到且嚴格前進的 next_after_node_id，boot_id 變了就重列，需要核對單項用 node.show。持續變動時本輪不追補游標前新插入的項，避免無限追列。

**once 留存**：一次收尾解除後，在本 daemon 記憶體留一筆 registered:false 的最近結果，保留原 owner_uid 與 parent_id，查詢時以**目前仍在的可信父鏈**重驗；祖先權限撤銷即生效，不能靠舊祖先快照繼續讀。父額度撤掉該 owner 身分時一併清除此 once 診斷；父被解除也清除。只供 get/list，wake／pause／resume 等仍回 not_registered。留到 daemon 結束、同 node_id 通過新登記，或其父子樹被明示 unregister；不寫檔、不把它算正在占用的登記。不設計時淘汰，避免人手來不及看；長期大量 once 的診斷記憶體成本可由部署安排重啟清掉。普通 node 被解除不留此記錄。新 once attempt 應用新 inst 路徑，見 work 篇。

人手 `aos node ls --socket S` 使用 node.ls，`aos node show N --socket S` 使用 node.show；多個 `--node` 可逐個 get。畫面須把「已解除 once」「未啟動」「還在跑」「結果不明」分開。IPC 只回記憶體診斷，不讀工作結果／git，也不是業務完成或 unknown 重跑許可。

**驗收：**不同 UID 只能列自己的授權子樹；未跑顯示 last_tick:null；已放行後程式回 125 是 completed，身分拒絕 125 是 launch_failed（仍可能已有開檔副作用）；once 結束仍列得到且 registered:false；重啟後舊結果消失。分頁跨重啟須能靠 boot_id 發現。

## P-115．啟動 ID 與按需重建〔使用者方向 2026-09-29，裁定「kernel 別每格都重新註冊」；欄位為工程預設〕

`daemon.info` 對應 `aos daemon info`，params 為 `{}`，result 只有 `boot_id`（共用 ID，建議隨機 UUID）。每次 daemon 啟動新生一個，整次存續不變，重開不得沿用；只放記憶體，socket 路徑相同也不能沿用。node.show／node.ls 的 boot_id 跟它一致。node 路徑別名、重用或跨機重名的風險由使用者承擔。

kernel 在自己的 repo 記成功同步的 boot_id 與成員版本；每格只比對小查詢，兩者沒變且無待修復差異就不重登。重開、清單改變或已知解除時才補差異，並叫醒子 kernel 逐層重建；失敗筆不標成功、不擋其他成員，也不重送 unknown once。細節依 [kernel 任務篇](../kernel-tasks.md)。

**驗收：**連續十格無變動只查 boot_id、不重登十次；daemon 重開後 boot_id 改變，各 kernel 逐層補回成員；改一筆成員只同步差異，失敗筆下次仍能重查。
