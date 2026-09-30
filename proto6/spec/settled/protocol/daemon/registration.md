# daemon 協議：註冊、叫醒與查登記

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../base/identity-resources.md)、[inst](../../../base/inst.md)｜[裁定](../../../../notes/2026-09-29-verdicts.md)

本檔只留 method 的 params、result 與錯誤碼（第十八批）。行為去這裡找：

| 要找什麼 | 正本 |
|---|---|
| 登記、解除、換父、額度 | [B-606](../../daemon/registration.md) |
| 叫醒、暫停、故障停格、格次序號 | [B-607](../../daemon/registration.md) |
| 掛載行程的診斷 | [B-610](../../daemon/channel.md) |
| 誰可呼叫 | [P-103](startup-and-ipc.md) |
| 通道憑證 `token` | [P-117](channel.md) |
| 掛行程與砍掉 | [P-118](channel.md) |

## P-104．註冊〔建議預設，未拍板〕

`node.register` 登記一個非頂層 node；頂層只從設定載入，不走 IPC。

| params | 意思 |
|---|---|
| `node_id` | 必填。可給資料夾，或它的 `.aos/inst.json`、`inst.json` 路徑，daemon 正規化成資料夾（第十九批） |
| `identity_grant` | 必填。型別同 [P-101](startup-and-ipc.md)，可含前綴與範圍 |
| `parent_id` | 可省。省略＝用資料夾推得的上層；帶了就是覆蓋（第十九批） |
| `interval_ms`、`provision` | 可省。型別同 P-101 |
| `token` | 可省。通道憑證（P-117） |

- 原本的 `once` 欄拿掉了，改用 [`node.mount`](channel.md)（第十九批）。
- 上層怎麼定、覆蓋與換父見 [B-606](../../daemon/registration.md)。

**result**：`{node_id, parent_id, registration_id}`＝正規化後的 id、有效上層、登記識別。

schema 見 [daemon-registration](../../../protocol/schemas/daemon-registration.schema.json) 的 `RegisterParams`。範例：[看資料夾推上層](../../../protocol/examples/daemon/register.minimal.valid.json)、[帶憑證覆蓋上層](../../../protocol/examples/daemon/register.override-token.valid.json)、[回應](../../../protocol/examples/daemon/register_result.minimal.valid.json)、[反例：帶已拿掉的 once](../../../protocol/examples/daemon/register.once.invalid.json)、〔第十八批〕[前綴額度](../../../protocol/examples/daemon/register.grant-prefix.valid.json)。

**常見錯誤**（碼表見 P-111、[P-119](channel.md)）：

| 情況 | code |
|---|---|
| 上層或目標不存在；推得的上層沒登記 | `not_registered` |
| 搶登記、成環、id 已是掛載行程 | `registration_conflict` |
| 要兩方上層同意卻只有一方同意（舊上層沒在這個 daemon 登記時只看新上層，[B-606](../../daemon/registration.md)） | `forbidden` |
| 超出上層額度 | `user_not_granted` |
| inst 的 user 不存在 | `user_invalid` |
| 換父時被搬的子樹沒停或沒全空 | `busy` |
| 排空或停機中的新成員 | `stopping` |
| 憑證不對 | `token_invalid` |

## P-105．解除、叫醒、暫停、恢復與清除掛載診斷〔建議預設，未拍板〕

| method | params | result |
|---|---|---|
| `node.unregister` | `{node_id}`，〔第十九批〕可加 `token` | `{node_id}` |
| `node.wake` | `{node_id}`，〔第十九批〕可加 `token` | 〔第十八批〕`{node_id, registration_id, tick_seq}` |
| `node.pause`、`node.resume` | `{node_id}` | `{node_id}` |
| `mount.clear`〔第十八批；第十九批改名，原 `once.clear`〕 | `{node_id}` | `{node_id, cleared}` |

**`node.wake` 的回應**：

- `registration_id`：目標目前的登記識別。
- `tick_seq`：接受 wake 當下最近一格的格次序號；還沒開過格為 0。
- 怎樣算「wake 之後新的一格做完」見 [B-607](../../daemon/registration.md)。
- 範例：[請求](../../../protocol/examples/daemon/wake.minimal.valid.json)、[回應](../../../protocol/examples/daemon/wake_result.minimal.valid.json)。

**`mount.clear` 的回應**：`cleared` 是實際清掉的筆數（非負整數）；沒有可清的回 0，不算錯誤。範例：[請求](../../../protocol/examples/daemon/mount_clear.minimal.valid.json)、[回應](../../../protocol/examples/daemon/mount_clear_result.minimal.valid.json)、[反例：多一個欄位](../../../protocol/examples/daemon/mount_clear.extra.invalid.json)。

**錯誤**：

| 情況 | code |
|---|---|
| 目標不存在（包括重送已完成的解除） | `not_registered` |
| 解除時無法確認全空 | `cleanup_failed` |
| 停機中的 wake | `stopping` |
| 對掛載行程送這幾個 method | `kind_mismatch` |

**故障停格**：行為以 [B-607](../../daemon/registration.md) 為正本。一句話：daemon 不看結束碼、不看停格檔，只看擋板檔 `.aos/tick-blocked`，在就不開格（第二十批）。檔案位置見 [node P-200](../node.md)。

## P-106．查登記與最近一格〔使用者方向 2026-09-29，CLI H-034 D1；欄位為工程預設〕

### `node.show`

params 只有 `node_id`。result 欄位：

| 欄位 | 必填 | 意思 |
|---|---|---|
| `boot_id` | 是 | 本次啟動 ID（P-115） |
| `node_id` | 是 | |
| `parent_id` | 是 | 有效上層；頂層為 null |
| `owner_uid` | 是 | |
| `registered` | 是 | true＝還在調度表；false 只用在已結束的掛載行程診斷（[B-610](../../daemon/channel.md)） |
| `paused`、`running`、`pending`、`stopping` | 是 | `registered:false` 時全是 false |
| `cgroup` | 是 | 見下面；`registered:false` 時為 null |
| `last_tick` | 是 | 最近一格，見下面 |
| `registration_id`〔第十八批〕 | 是 | 登記識別，共用 ID；已結束的掛載行程保留它最後一次的值 |
| `parent_override`〔第十九批〕 | 是 | 上層來自登記覆蓋為 true；掛載行程固定 false |
| `mount`〔第十九批〕 | 是 | 掛載行程為 true（取代原 `once`）；頂層固定 false |
| `identity_grant` | 登記的 node 必附 | 掛載行程沒有 |
| `interval_ms`、`provision` | 有設定才附 | 掛載行程沒有 |

掛載行程只有一格，`tick_seq` 為 1。

**`cgroup`**：沒有 cgroup、或這個 node 退回沒有框時為 null（[B-605](../../daemon/cgroup.md)）；否則回實際讀到的 `{path,limits}`。`path` 是 node 分支 `n-<h>`（掛載行程是 `mount-<h>`），不是 `tick` 葉（命名見 [B-605](../../daemon/cgroup.md)）。limits 的 CPU 用 `{quota_us,period_us}`，memory／pids 沿 P-107，無上限回字串 `"max"`，未啟用的 controller 省略。讀取失敗怎麼處理見 [B-607](../../daemon/registration.md)。

### 最近一格 `last_tick`

`last_tick:null`＝本次登記還沒派出過格。否則是最近一格，七欄都必填：

| 欄位 | 意思 |
|---|---|
| `tick_seq`〔第十八批〕 | 格次序號：本次登記內從 1 遞增的整數（[B-607](../../daemon/registration.md)） |
| `started_at_ms` | daemon 接受這次開格、進入啟動流程的 UTC 毫秒。daemon 在格外，這是給人看的紀錄，保留毫秒（第二十批，[C-01](../../../contracts.md)） |
| `ended_at_ms` | 完成收尾的 UTC 毫秒；還在啟動、執行或清後代時為 null |
| `exit_code` | 可信 runner 回報的 0～255 整數；執行中或結果不明為 null |
| `started` | 可信 runner 的 started：completed 為 true、launch_failed 為 false、running 為 null；unknown 只在已有可信 started:true 時填 true，否則 null |
| `signal` | completed 時可信回報明列的子程式訊號（1～64）；其餘或沒有則 null。不能從 exit_code 的 128+N 倒猜 |
| `outcome` | `running`、`completed`、`launch_failed`、`unknown` 四選一；各代表什麼見 [B-607](../../daemon/registration.md) |

欄位之間的約束：

- `running` 時 `ended_at_ms`、`exit_code` 必須 null；其他 outcome 必須有 `ended_at_ms`。
- `launch_failed` 的 `exit_code` 只准 2 或 125；`unknown` 的必須 null。
- `running:false` 只在受管程序與後代已全空時成立（[B-607](../../daemon/registration.md)）。

### `node.ls`

| | 形狀 |
|---|---|
| params | object；可省 `limit`（1～64，預設 64）與 `after_node_id`（NodeId） |
| result | `{boot_id, nodes, next_after_node_id}` |

- `nodes` 每項跟 `node.show` 同形狀，按 `node_id` 的 UTF-8 bytes 升序，只含嚴格大於 `after_node_id` 的項。
- 還沒列完時 `next_after_node_id` 是本頁末項的 ID；列完為 null。不得回空頁卻還給下一頁。
- 篩選、分頁與縮頁規則見 [B-607](../../daemon/registration.md)。

人手指令：`aos node ls --socket S` 用 `node.ls`，`aos node show N --socket S` 用 `node.show`。

範例：[查一個 node](../../../protocol/examples/daemon/get_result.minimal.valid.json)（沒有 cgroup，`cgroup:null`）、[有 cgroup 時查一個 node](../../../protocol/examples/daemon/get_result.cgroup.valid.json)（`cgroup.path` 是 `/srv/aos/team` 為頂層、子樹根 `/sys/fs/cgroup/aos` 時 `/srv/aos/team/member` 的 `n-<h>`）、[已結束的掛載行程未啟動](../../../protocol/examples/daemon/get_result.launch_failed.valid.json)、[列表](../../../protocol/examples/daemon/list_result.minimal.valid.json)；反例：[launch_failed 卻 exit 0](../../../protocol/examples/daemon/get_result.launch_success.invalid.json)、[缺 running](../../../protocol/examples/daemon/get_result.missing_running.invalid.json)、[running 卻有 exit_code](../../../protocol/examples/daemon/list_result.running_exit.invalid.json)、〔第十八批〕[最近一格缺 tick_seq](../../../protocol/examples/daemon/get_result.missing_tick_seq.invalid.json)。

驗收見 [B-607](../../daemon/registration.md)、[B-610](../../daemon/channel.md)。

## P-115．啟動 ID 與按需重建〔使用者方向 2026-09-29，裁定「kernel 別每格都重新註冊」；欄位為工程預設〕

`daemon.info`（對應 `aos daemon info`）：params 為 `{}`，result 只有 `boot_id`（共用 ID，建議隨機 UUID）。`node.show`、`node.ls` 回的 `boot_id` 跟它一致。

`boot_id` 的生命週期、逐層重建與「別每格重登」的行為見 [B-603](../../daemon/lifecycle.md)、[B-606](../../daemon/registration.md)（astra 審整理區必-8 從本條搬上）；kernel 那側見 [kernel 任務篇](../../../protocol/kernel-tasks.md)。驗收見 B-603。
