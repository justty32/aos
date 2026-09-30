# daemon 協議：註冊、叫醒與查登記

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

〔使用者方向 2026-09-30，第十八批〕本檔只留 method 的 params、result 與錯誤碼；登記、解除、換父與額度的行為見 [B-606](../../daemon.md)，叫醒、暫停、故障停格與格次序號見 [B-607](../../daemon.md)，once 診斷見 [B-610](../../daemon.md)。誰可呼叫見 [P-103](startup-and-ipc.md)。

## P-104．註冊〔建議預設，未拍板〕

`node.register` params：`node_id`、`parent_id`、`identity_grant` 必填；`interval_ms`、`once`、`provision` 可省。型別同 [P-101](startup-and-ipc.md)（身分額度可含前綴與範圍），`parent_id` 是已登記父 node；`once` 預設 false，`once:true` 不可帶 `interval_ms`。IPC 只登記非頂層，頂層只從設定載入。帶跟目前不同的 `parent_id` 就是換父。

result 統一為 `{"node_id":"…"}`。schema 見 [daemon-registration](../schemas/daemon-registration.schema.json) 的 `Registration`；範例：[once 登記](../examples/daemon/register.minimal.valid.json)、[反例：once 帶週期](../examples/daemon/register.once_interval.invalid.json)、〔第十八批〕[前綴額度](../examples/daemon/register.grant-prefix.valid.json)。

常見錯誤（碼表見 P-111）：父或目標不存在 `not_registered`；搶登記、換父成環 `registration_conflict`；超出父額度 `user_not_granted`；inst user 不存在 `user_invalid`；換父時被搬的子樹沒停或沒全空 `busy`；排空或停機中的新 once／新成員 `stopping`。

## P-105．解除、叫醒、暫停、恢復與清除 once 診斷〔建議預設，未拍板〕

| method | params | result |
|---|---|---|
| `node.unregister` | `{node_id}` | `{node_id}` |
| `node.wake` | `{node_id}` | 〔第十八批〕`{node_id, registration_id, tick_seq}` |
| `node.pause`、`node.resume` | `{node_id}` | `{node_id}` |
| `once.clear`〔第十八批〕 | `{node_id}` | `{node_id, cleared}` |

- `node.wake` 的 `registration_id` 是目標目前的登記識別，`tick_seq` 是接受 wake 當下最近一格的格次序號（還沒開過格為 0）；等「wake 之後新的一格做完」的判斷見 [B-607](../../daemon.md)。範例：[請求](../examples/daemon/wake.minimal.valid.json)、[回應](../examples/daemon/wake_result.minimal.valid.json)。
- `once.clear` 的 `cleared` 是實際清掉的筆數（非負整數），沒有可清的回 0，不算錯誤。範例：[請求](../examples/daemon/once_clear.minimal.valid.json)、[回應](../examples/daemon/once_clear_result.minimal.valid.json)、[反例：多一個欄位](../examples/daemon/once_clear.extra.invalid.json)。
- 錯誤：不存在的目標回 `not_registered`（包括重送已完成的解除）；解除時無法確認全空回 `cleanup_failed`；停機中的 wake 回 `stopping`。

故障停格的接法以 [B-607](../../daemon.md) 為正本；tick 的停格碼 3 與格首擋板 125 見 [node P-203](../node.md)。

## P-106．查登記與最近一格〔使用者方向 2026-09-29，CLI H-034 D1；欄位為工程預設〕

`node.show` params 只有 `node_id`。result 必填 `boot_id`（P-115）、`node_id`、`parent_id`（頂層為 null）、`identity_grant`、`owner_uid`、`once`、`registered`、`paused`、`running`、`pending`、`stopping`、`cgroup`、`last_tick`，〔第十八批〕`registration_id`（登記識別，共用 ID；已解除 once 保留它最後一次登記的值）；有設定才附 `interval_ms`、`provision`。root 的 once 固定 false。`registered:true` 表示還在調度表；false 只供已解除的 once 診斷記錄（[B-610](../../daemon.md)），此時 paused／running／pending／stopping 都是 false、`cgroup` 為 null。

`cgroup`：沒有活的配置為 null，否則回實際讀到的 `{path,limits}`，不是上次請求快取。`path` 是 node 分支 `n-<h>`（once 是 `once-<h>`），不是 `tick` 葉（命名見 [B-605](../../daemon.md)）。limits 的 CPU 用 `{quota_us,period_us}`，memory／pids 沿 P-107，無上限回字串 `"max"`，未啟用 controller 省略。應存在卻讀取失敗回 `resource_observation_failed`，不能回 null 冒充沒配置。

`last_tick:null` 表示本次登記還沒派出過；否則是最近一格，必填下表七欄。

| 欄位 | 意思 |
|---|---|
| `tick_seq`〔第十八批〕 | 格次序號：本次登記內從 1 遞增的整數（[B-607](../../daemon.md)） |
| `started_at_ms` | daemon 接受這次開格並進入啟動流程的 UTC 毫秒；包含啟動前檢查，**不是程式已開始的證據** |
| `ended_at_ms` | 完成收尾的 UTC 毫秒；還在啟動／執行／清後代時為 null |
| `exit_code` | 可信 runner 回報的 0～255 整數；執行中或結果不明為 null |
| `started` | 可信 runner 的 started；completed 為 true、launch_failed 為 false，running 為 null；unknown 只在已有可信 started:true 時填 true，否則 null |
| `signal` | completed 時可信回報明列的子程式訊號（1～64），其餘或沒有則 null；不能從 exit_code 的 128+N 倒猜 |
| `outcome` | `running`＝啟動／執行／收尾中；`completed`＝可信 started:true 且完成收尾；`launch_failed`＝可信 started:false；`unknown`＝沒可信回報或 FinalizeFailed。completed 可是非零，絕不等於業務成功 |

running 時 ended_at_ms／exit_code 必須 null；其他 outcome 必須有 ended_at_ms。launch_failed 的 exit_code 只准 2／125；unknown 必須 null，保留診斷但不從 runner wait 碼猜業務退出碼。running:false 只在受管程序及後代已全空時成立；後代清不空時仍 running:true、outcome:running，另以 stopping:true 及 attention 暴露故障，不能先記成已完。時間可能受牆鐘校正影響，排格數用 `tick_seq`，不用時間。

`node.ls` params 是 object，可省 `limit`（1～64，預設 64）與 `after_node_id`（NodeId）。result 是 `{boot_id,nodes,next_after_node_id}`：nodes 每項與 node.show 同形狀，按 node_id 的 UTF-8 bytes 升序；先按 peer 權限篩選，再取嚴格大於 after_node_id 的項。未列完時 next_after_node_id 是本頁末項 ID，列完為 null；不得回空頁卻還給下一頁。每頁亦受 P-103 封包上限約束，裝不下一項就縮頁，單項仍過大回 `response_too_large`。只列有權看者，不泄漏總數或無權項。不同頁不是同一瞬間快照；每次接續必須使用剛收到且嚴格前進的 next_after_node_id，boot_id 變了就重列，需要核對單項用 node.show。持續變動時本輪不追補游標前新插入的項，避免無限追列。

人手 `aos node ls --socket S` 使用 node.ls，`aos node show N --socket S` 使用 node.show；多個 `--node` 可逐個 get。畫面須把「已解除 once」「未啟動」「還在跑」「結果不明」分開。

範例：[查一個 node](../examples/daemon/get_result.minimal.valid.json)（`cgroup.path` 是 `/srv/aos/team` 為頂層、子樹根 `/sys/fs/cgroup/aos` 時 `/srv/aos/team/member` 的 `n-<h>`）、[已解除 once 未啟動](../examples/daemon/get_result.launch_failed.valid.json)、[列表](../examples/daemon/list_result.minimal.valid.json)；反例：[launch_failed 卻 exit 0](../examples/daemon/get_result.launch_success.invalid.json)、[缺 running](../examples/daemon/get_result.missing_running.invalid.json)、[running 卻有 exit_code](../examples/daemon/list_result.running_exit.invalid.json)、〔第十八批〕[最近一格缺 tick_seq](../examples/daemon/get_result.missing_tick_seq.invalid.json)。

**驗收：**不同 UID 只能列自己的授權子樹；未跑顯示 last_tick:null；已放行後程式回 125 是 completed，身分拒絕 125 是 launch_failed（仍可能已有開檔副作用）；once 結束仍列得到且 registered:false；重啟後舊結果消失。分頁跨重啟須能靠 boot_id 發現。

## P-115．啟動 ID 與按需重建〔使用者方向 2026-09-29，裁定「kernel 別每格都重新註冊」；欄位為工程預設〕

`daemon.info` 對應 `aos daemon info`，params 為 `{}`，result 只有 `boot_id`（共用 ID，建議隨機 UUID）。每次 daemon 啟動新生一個，整次存續不變，重開不得沿用；只放記憶體，socket 路徑相同也不能沿用。node.show／node.ls 的 boot_id 跟它一致。node 路徑別名、重用或跨機重名的風險由使用者承擔。

逐層重建與「別每格重登」的行為見 [B-603](../../daemon.md)、[B-606](../../daemon.md)，kernel 那側見 [kernel 任務篇](../kernel-tasks.md)。

**驗收：**連續十格無變動只查 boot_id、不重登十次；daemon 重開後 boot_id 改變，各 kernel 逐層補回成員；改一筆成員只同步差異，失敗筆下次仍能重查。
