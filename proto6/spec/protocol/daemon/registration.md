# daemon 協議：註冊、叫醒與查登記

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

〔使用者方向 2026-09-30，第十八批〕本檔只留 method 的 params、result 與錯誤碼；登記、解除、換父與額度的行為見 [B-606](../../daemon.md)，叫醒、暫停、故障停格與格次序號見 [B-607](../../daemon.md)，掛載行程的診斷見 [B-610](../../daemon.md)。誰可呼叫見 [P-103](startup-and-ipc.md)；通道憑證 `token` 見 [P-117](channel.md)，掛行程與砍掉見 [P-118](channel.md)。

## P-104．註冊〔建議預設，未拍板〕

`node.register` params：`node_id`、`identity_grant` 必填；`parent_id`、`interval_ms`、`provision`、`token` 可省。型別同 [P-101](startup-and-ipc.md)（身分額度可含前綴與範圍）。〔使用者方向 2026-09-30，第十九批〕`node_id` 可給資料夾，或它的 `.aos/inst.json`、`inst.json` 路徑，daemon 正規化成資料夾；`parent_id` 省略＝看資料夾推得的上層，帶了就是覆蓋；`once` 欄拿掉，改用 [`node.mount`](channel.md)。IPC 只登記非頂層，頂層只從設定載入。上層怎麼定、覆蓋與換父見 [B-606](../../daemon.md)。

result 為 `{node_id, parent_id, registration_id}`：正規化後的 id、有效上層與登記識別。schema 見 [daemon-registration](../schemas/daemon-registration.schema.json) 的 `RegisterParams`；範例：[看資料夾推上層](../examples/daemon/register.minimal.valid.json)、[帶憑證覆蓋上層](../examples/daemon/register.override-token.valid.json)、[回應](../examples/daemon/register_result.minimal.valid.json)、[反例：帶已拿掉的 once](../examples/daemon/register.once.invalid.json)、〔第十八批〕[前綴額度](../examples/daemon/register.grant-prefix.valid.json)。

常見錯誤（碼表見 P-111、[P-119](channel.md)）：上層或目標不存在、推得的上層沒登記 `not_registered`；搶登記、成環、id 已是掛載行程 `registration_conflict`；只有一方上層同意 `forbidden`；超出上層額度 `user_not_granted`；inst user 不存在 `user_invalid`；換父時被搬的子樹沒停或沒全空 `busy`；排空或停機中的新成員 `stopping`；憑證不對 `token_invalid`。

## P-105．解除、叫醒、暫停、恢復與清除掛載診斷〔建議預設，未拍板〕

| method | params | result |
|---|---|---|
| `node.unregister` | `{node_id}`，〔第十九批〕可加 `token` | `{node_id}` |
| `node.wake` | `{node_id}`，〔第十九批〕可加 `token` | 〔第十八批〕`{node_id, registration_id, tick_seq}` |
| `node.pause`、`node.resume` | `{node_id}` | `{node_id}` |
| `mount.clear`〔第十八批；第十九批改名，原 `once.clear`〕 | `{node_id}` | `{node_id, cleared}` |

- `node.wake` 的 `registration_id` 是目標目前的登記識別，`tick_seq` 是接受 wake 當下最近一格的格次序號（還沒開過格為 0）；等「wake 之後新的一格做完」的判斷見 [B-607](../../daemon.md)。範例：[請求](../examples/daemon/wake.minimal.valid.json)、[回應](../examples/daemon/wake_result.minimal.valid.json)。
- `mount.clear` 的 `cleared` 是實際清掉的筆數（非負整數），沒有可清的回 0，不算錯誤。範例：[請求](../examples/daemon/mount_clear.minimal.valid.json)、[回應](../examples/daemon/mount_clear_result.minimal.valid.json)、[反例：多一個欄位](../examples/daemon/mount_clear.extra.invalid.json)。
- 錯誤：不存在的目標回 `not_registered`（包括重送已完成的解除）；解除時無法確認全空回 `cleanup_failed`；停機中的 wake 回 `stopping`；對掛載行程送這幾個 method 回 `kind_mismatch`。

故障停格的接法以 [B-607](../../daemon.md) 為正本；tick 的停格碼 3 與格首擋板 125 見 [node P-203](../node.md)。

## P-106．查登記與最近一格〔使用者方向 2026-09-29，CLI H-034 D1；欄位為工程預設〕

`node.show` params 只有 `node_id`。result 必填 `boot_id`（P-115）、`node_id`、`parent_id`（頂層為 null）、`owner_uid`、`registered`、`paused`、`running`、`pending`、`stopping`、`cgroup`、`last_tick`，〔第十八批〕`registration_id`（登記識別，共用 ID；已結束的掛載行程保留它最後一次的值），〔第十九批〕`parent_override`（上層來自登記覆蓋為 true）與 `mount`（掛載行程為 true，取代原 `once`）；登記的 node 必附 `identity_grant`，有設定才附 `interval_ms`、`provision`，掛載行程三者都沒有、`parent_override` 固定 false。頂層的 `mount` 固定 false。`registered:true` 表示還在調度表；false 只供已結束的掛載行程診斷（[B-610](../../daemon.md)），此時 paused／running／pending／stopping 都是 false、`cgroup` 為 null。掛載行程只有一格，`tick_seq` 為 1。

`cgroup`：沒有活的配置（含走備援）為 null，否則回實際讀到的 `{path,limits}`。`path` 是 node 分支 `n-<h>`（掛載行程是 `mount-<h>`），不是 `tick` 葉（命名見 [B-605](../../daemon.md)）。limits 的 CPU 用 `{quota_us,period_us}`，memory／pids 沿 P-107，無上限回字串 `"max"`，未啟用 controller 省略。讀取失敗的處理見 [B-607](../../daemon.md)。

`last_tick:null` 表示本次登記還沒派出過；否則是最近一格，必填下表七欄。

| 欄位 | 意思 |
|---|---|
| `tick_seq`〔第十八批〕 | 格次序號：本次登記內從 1 遞增的整數（[B-607](../../daemon.md)） |
| `started_at_ms` | daemon 接受這次開格並進入啟動流程的 UTC 毫秒 |
| `ended_at_ms` | 完成收尾的 UTC 毫秒；還在啟動／執行／清後代時為 null |
| `exit_code` | 可信 runner 回報的 0～255 整數；執行中或結果不明為 null |
| `started` | 可信 runner 的 started；completed 為 true、launch_failed 為 false，running 為 null；unknown 只在已有可信 started:true 時填 true，否則 null |
| `signal` | completed 時可信回報明列的子程式訊號（1～64），其餘或沒有則 null；不能從 exit_code 的 128+N 倒猜 |
| `outcome` | `running`、`completed`、`launch_failed`、`unknown` 四選一；各代表什麼見 [B-607](../../daemon.md) |

running 時 ended_at_ms／exit_code 必須 null；其他 outcome 必須有 ended_at_ms。launch_failed 的 exit_code 只准 2／125；unknown 必須 null。running:false 只在受管程序及後代已全空時成立（[B-607](../../daemon.md)）。

`node.ls` params 是 object，可省 `limit`（1～64，預設 64）與 `after_node_id`（NodeId）。result 是 `{boot_id,nodes,next_after_node_id}`：nodes 每項與 node.show 同形狀，按 node_id 的 UTF-8 bytes 升序，只含嚴格大於 after_node_id 的項。未列完時 next_after_node_id 是本頁末項 ID，列完為 null；不得回空頁卻還給下一頁。篩選、分頁與縮頁規則見 [B-607](../../daemon.md)。

人手 `aos node ls --socket S` 使用 node.ls，`aos node show N --socket S` 使用 node.show。

範例：[查一個 node](../examples/daemon/get_result.minimal.valid.json)（`cgroup.path` 是 `/srv/aos/team` 為頂層、子樹根 `/sys/fs/cgroup/aos` 時 `/srv/aos/team/member` 的 `n-<h>`）、[已結束的掛載行程未啟動](../examples/daemon/get_result.launch_failed.valid.json)、[列表](../examples/daemon/list_result.minimal.valid.json)；反例：[launch_failed 卻 exit 0](../examples/daemon/get_result.launch_success.invalid.json)、[缺 running](../examples/daemon/get_result.missing_running.invalid.json)、[running 卻有 exit_code](../examples/daemon/list_result.running_exit.invalid.json)、〔第十八批〕[最近一格缺 tick_seq](../examples/daemon/get_result.missing_tick_seq.invalid.json)。

驗收見 [B-607](../../daemon.md)、[B-610](../../daemon.md)。

## P-115．啟動 ID 與按需重建〔使用者方向 2026-09-29，裁定「kernel 別每格都重新註冊」；欄位為工程預設〕

`daemon.info` 對應 `aos daemon info`，params 為 `{}`，result 只有 `boot_id`（共用 ID，建議隨機 UUID）。每次 daemon 啟動新生一個，整次存續不變，重開不得沿用；只放記憶體，socket 路徑相同也不能沿用。node.show／node.ls 的 boot_id 跟它一致。node 路徑別名、重用或跨機重名的風險由使用者承擔。

逐層重建與「別每格重登」的行為見 [B-603](../../daemon.md)、[B-606](../../daemon.md)，kernel 那側見 [kernel 任務篇](../kernel-tasks.md)。

**驗收：**連續十格無變動只查 boot_id、不重登十次；daemon 重開後 boot_id 改變，各 kernel 逐層補回成員；改一筆成員只同步差異，失敗筆下次仍能重查。
