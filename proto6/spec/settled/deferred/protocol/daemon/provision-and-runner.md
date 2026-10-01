# daemon 協議：佈建、私有通道與 runner

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../base/identity-resources.md)、[inst](../../../base/inst.md)｜[裁定](../../../../notes/2026-09-29-verdicts.md)

## P-107．佈建固定動作〔建議預設，未拍板〕

本條只留參數。各動作做什麼、要不要 helper、上限隨時改，以 [B-609](../../daemon/helper-actions.md) 為正本（第十八批）。

`node.provision` 的 params 是 `node_id`、`action`，再加下表該動作的欄位。schema 見 [daemon-provision](../../../protocol/schemas/daemon-provision.schema.json)。成功 result 都是 `{"node_id":"…"}`。

| `action` | 其他必填欄位 |
|---|---|
| `account_create` | `user`：確切帳號名稱 |
| `chown` | `path`、`user` |
| `cgroup_limits` | `limits`：非空 object，可有 `cpu_max:{quota_us,period_us}`、`memory_max_bytes`、`pids_max`，皆正整數；CPU 直接用 cgroup 微秒，是 [P-002](../../../protocol/README.md) 的明示例外。沒有 cgroup（或這個 node 退回沒有框）回 `unsupported` |
| `quota` | `path`、`project_id`：正整數 |
| `group_create`〔第十八批〕 | `group`：確切群組名稱 |
| `group_add_member`〔第十八批〕 | `group`、`user` |
| `chgrp`〔第十八批〕 | `path`、`group` |
| `spawn_as`〔第十九批；第二十批呼叫者改 `aos-as`〕 | `user`（帳號名稱或 UID）、`path`（本 node `.aos/jobs/` 下 `aos-as` 寫好的那份 inst 的絕對路徑，檔名見 [P-212](../node.md)）、`token`（必帶）；`frame` 可省（`task-<seq>-<pid>`，`aos-as` 在 `aos-cg` 開的框裡時帶；沒有 cgroup 時帶了回 `unsupported`）。請求那一行要以同一個 sendmsg 用 SCM_RIGHTS 附 5 個 fd〔第二十批，從 2 個加 stdio〕：鎖 fd、回報 pipe 寫端、stdin、stdout、stderr，順序固定，數量不符回 `invalid_params` |

原本的 `cgroup_create`、`cgroup_delegate` 撤：建框、交框改由 daemon 開格前自動做（[B-605](../../daemon/cgroup.md)、[B-609](../../daemon/helper-actions.md)；納入 cgroup 與 git 疑-10）。

欄位型別：`path` 是絕對路徑；`user` 是帳號名稱或 UID（`account_create` 只收名稱）；`group` 是非空名稱字串。

**`spawn_as` 跟其他動作不一樣**（第十九批）：

- 它不列在登記的 `provision.actions` 授權裡，看的是身分額度。
- runner 開起來就回 `{node_id}`；結束碼走回報 pipe，內容是一行 [runner 回報](../../../protocol/schemas/daemon-runner-report.schema.json)（同 P-110）。
- 誰能叫、帳號限制、放在哪、怎麼回傳，見 [B-609](../../daemon/helper-actions.md)。
- daemon IPC 只有它附 fd；其他請求附了 fd，就關掉並回 `invalid_params`（P-103）。

範例：每個動作一個[正例](../../../protocol/examples/daemon/provision_chown.minimal.valid.json)與一個多欄位的反例，檔名 `provision_<動作>.minimal.valid.json`／`.extra.invalid.json`；`spawn_as` 另有[沒帶憑證的反例](../../../protocol/examples/daemon/provision_spawn_as.no-token.invalid.json)。

## P-108．daemon 與 helper 的私有通道〔建議預設，未拍板〕

**通道本身**：

- fork 前建 Unix `SOCK_SEQPACKET` socketpair，只給 daemon 與 helper 用。
- 每包一個 JSON-RPC，最多 256 KiB，沒有 LF。
- 必要的 fd 以 SCM_RIGHTS 同包傳，數量不符就拒。
- runner 與子程序不繼承這條通道。
- method 對應內部子命令 `aos daemon helper <動作>`，只接這條既有的私有通道與 fd，不是公開 IPC 入口。

| method | params／fd | 效果 |
|---|---|---|
| `daemon.helper.bind` | `registration`、`owner_uid`；1 個密封 inst 快照 fd | 以啟動根額度、可信上層鏈、原始 user 與路徑重驗。`registration` 有三種形狀：非頂層登記（`BoundRegistration`，有效上層已解出）；頂層（P-101 形狀，只能是啟動時設定已有的 roots；熱重載新加、只用通用 user 又沒佈建權的頂層不經 helper，[B-608](../../daemon/reload.md)）；〔第十九批〕掛載行程（`MountRecord`） |
| `daemon.helper.unbind` | `node_id`；無 fd | 移除這筆的鏡像；什麼時候可以移除見 [B-601](../../daemon/runtime.md) |
| `daemon.helper.start` | `node_id`、`target_uid`、〔第十九批〕`token`；inst 快照與回報 pipe 共 2 fd | 開一格或一個掛載行程：固定 aos-runner，runner 環境帶兩個通道變數（[P-117](channel.md)）；不收自訂 argv／env／輸出路徑 |
| `daemon.helper.spawn`〔第十九批；第二十批加 stdio；astra 審整理區必-3 加 `path`〕 | `node_id`、`target_uid`、`path`、`token`，`frame` 可省（有 cgroup 時的 `task-*` 框）；inst 快照、鎖 fd、`aos-as` 的回報 pipe、stdin、stdout、stderr 共 6 fd，順序固定 | 公開 `spawn_as`（P-107）的私有那一段：`path` 是 daemon 已核准的那份 inst 路徑，當 runner 的 `--target`；固定 aos-runner 帶 `--lock-fd`，以交來的三個 stdio fd 當 runner 的 stdin／stdout／stderr；不收自訂 argv／env／輸出路徑 |
| `daemon.helper.stop` | `node_id`、`grace_ms`；無 fd | 只停登記範圍，照 [B-604](../../daemon/lifecycle.md) 收尾那個 node 的 runner，寬限用 daemon 帶入的 `grace_ms`（取 `shutdown_grace_ms`）；有 cgroup 時最後對那些框 `cgroup.kill`；不收任意 PID／訊號 |
| `daemon.helper.provision` | P-107 params（`spawn_as` 除外，它走 `daemon.helper.spawn`）；無 fd | 重驗授權與固定動作後執行 |
| `daemon.helper.cgroup_setup`〔納入 cgroup 與 git 疑-10〕 | `node_id`；無 fd | 建框並交框：在可信上層框下建本 node 的 `n-<h>` 與 `tick`，交給這個 node 目前的執行帳號；路徑由登記推導。只給 daemon 用，不是 `node.provision` 的動作（[B-605](../../daemon/cgroup.md)、[B-609](../../daemon/helper-actions.md)） |
| `daemon.helper.cgroup_remove`〔第十八批〕 | `path`；無 fd | 刪殘留框：只刪 cgroup 子樹內、名字是 `n-<16hex>`／`mount-<16hex>`／`task-<seq>-<pid>`、沒有程序也沒有子框的框；不是 `node.provision` 的動作（[B-609](../../daemon/helper-actions.md)） |

成功 result 都是 `{node_id}`。start 與 spawn 何時回、快照與 base、鏡像、失聯與重驗，以 [B-601](../../daemon/runtime.md)、[B-609](../../daemon/helper-actions.md) 為正本。

範例：[spawn](../../../protocol/examples/daemon/helper_spawn.minimal.valid.json)、[反例：spawn 沒帶 path](../../../protocol/examples/daemon/helper_spawn.no-path.invalid.json)、[反例：provision 夾 spawn_as](../../../protocol/examples/daemon/helper_provision.spawn_as.invalid.json)、[建框並交框](../../../protocol/examples/daemon/helper_cgroup_setup.minimal.valid.json)、[反例：建框多一個欄位](../../../protocol/examples/daemon/helper_cgroup_setup.extra.invalid.json)。

## P-109．runner argv 與解析〔建議預設，未拍板〕

固定 argv：

```text
aos-runner --inst-fd N --target /absolute/target --authorized-uid UID --status-fd N
           [--stderr /absolute/path] [--timeout-ms N] [--lock-fd N]
```

| 參數 | 意思 |
|---|---|
| `--inst-fd` | inst 快照 fd，父層已打開 |
| `--target` | 照 [inst 目標](../../../base/inst.md#inst-目標檔案或資料夾)定原來源與 base，不改尋找規則。開格與掛載取登記的 `node_id`；`daemon.helper.spawn` 取它的 `path` |
| `--authorized-uid` | 只是核對，不授予直接呼叫者切 UID 的能力 |
| `--status-fd` | 回報 pipe（P-110），只給 runner，子程序 exec 前關閉 |
| `--stderr` | 由目標身分以覆寫方式開檔，不自建父目錄，蓋過 inst 的 stderr 選項。〔第二十批〕`daemon.helper.spawn` 開時不帶，runner 的 stdin／stdout／stderr 就是 `aos-as` 交來的三個 fd（[B-609](../../daemon/helper-actions.md)） |
| `--timeout-ms` | 正整數，省略就不另加。〔暫定，第二十批疑-11〕保留毫秒：runner 是格外的程序，用 monotonic 量 |
| `--lock-fd`〔第十九批〕 | 只由 `daemon.helper.spawn` 帶。runner 不關這個 fd、讓子程序繼承；環境怎麼補（`AOS_TICK_LOCK_FD` 與通道變數最後才放）見 [B-609](../../daemon/helper-actions.md) |

環境：runner 帶兩個通道變數（[P-117](channel.md)，第十九批），其餘不帶管理 fd 或 key。

開格的順序、串流落點、環境，以及 runner 怎麼清空名下的程序、對 SIGTERM 與回報 pipe 斷線怎麼反應，見 [B-601](../../daemon/runtime.md)；展開、開檔與身分規則以 [inst](../../../base/inst.md) 為正本。

## P-110．runner 結束與 125〔建議預設，未拍板〕

### 回報 pipe

一行 JSON、LF 結尾；沒有 version（不是持久檔）。[schema](../../../protocol/schemas/daemon-runner-report.schema.json)。每次完整收尾只回報一次；怎麼判讀見 [B-601](../../daemon/runtime.md)、[B-607](../../daemon/registration.md)。

| 情況 | 回報 |
|---|---|
| 前置失敗 | `{"started":false,"exit_code":125,"error":{"code":"UserNotGranted","message":"身分不在額度內"}}`。`error.code` 沿 inst 的 PascalCase 代號；CLI 用法錯時 `exit_code` 是 2。父層還沒 exec runner 就拒絕的，由父層合成同樣的回報。**不寫 inst exit** |
| 已放行，子程式正常結束 | `{"started":true,"exit_code":<原碼>}`。回 125 也合法，表示子程式自己退出 125；找不到程式 127、不能執行 126 也屬這一類，並寫 exit |
| 已放行，子程式被訊號結束 | 另帶 `signal`（1～64）；`exit_code` 依 inst 為 128+N |
| 已放行，runner 寫 exit／收尾／發布回報時自己失敗 | 程序回 125；回報還寫得出時是 `{"started":true,"exit_code":125,"error":{"code":"FinalizeFailed","message":"…"}}` |

runner 自己被殺時，父程序讀 wait 狀態，不能從 128+N 猜。這條 pipe 的回報不是另一份持久工作結果。

### runner 的結束碼

| 碼 | 意思 |
|---|---|
| `2` | 用法錯（含資料夾兩處都沒有 inst） |
| `125` | 前置的解析、開檔、身分失敗；stderr 印 `代號: 白話` |
| 其他 | 照 inst |

signal、126／127 是 inst 執行規則對 [P-006](../../../protocol/README.md) 的特例。

### 掛載行程單檔未啟動的旁檔

`<inst 檔名>.err`（例如 `job.json.err`），格式 `{version:1,node_id,error}`，見 [schema](../../../protocol/schemas/daemon-launch-error.schema.json)。

- 持久檔：`error` 用開放版 `ErrorOpen`，不認得的欄位忽略（[C-07](../../../contracts.md)）。
- `error` 用 P-005 的小寫代碼；發布照 P-003。
- 什麼時候寫、寫不出怎麼辦見 [B-613](../../daemon/channel.md)。

依據：使用者方向 2026-09-29，第十一批與後續旁檔改名裁定。

## P-111．錯誤〔建議預設，未拍板〕

RPC error 沿 P-005。daemon IPC 與 helper 通道維持嚴格：不認得的欄位拒絕（[C-07](../../../contracts.md)）。`data` 必填 `code`、`retryable`。

**標準碼**：解析、請求、method、參數、內部錯誤各用保留碼，`data.code` 依序為 `parse_error`、`invalid_request`、`method_not_found`、`invalid_params`、`internal_error`，`retryable` 都是 false。

- 取不到合法 ID 的解析／請求錯誤，依 P-004 回 `id:null`。
- 超長行與 ID 沿用怎麼處理見 [B-601](../../daemon/runtime.md)。

**業務碼**（-32000）：

| code | 意思 | 預設 retryable |
|---|---|---|
| `forbidden`、`user_not_granted` | 呼叫者無權（含覆蓋上層只有一方同意、寄件帳號對收件 `requests/` 沒寫權）／超出身分額度 | false |
| `user_invalid`、`user_mismatch` | 帳號不能解析／前後身分不合 | false |
| `source_changed`〔第十七批〕 | 授權後 inst 原來源的內容跟快照不同（不一定是身分改了） | false |
| `not_registered`、`registration_conflict` | 目標或上層不存在／搶登記、成環、同一個 id 已是登記或掛載行程 | false |
| `busy` | 活程序、維護狀態不合（例如換父時子樹沒停） | true，等全空後先查狀態 |
| `stopping`、`cleanup_failed` | 正在停或排空中，不收新的掛行程／新成員（[B-604](../../daemon/lifecycle.md)）／無法確認後代清空 | false |
| `not_available`〔建議預設，未拍板〕 | 功能已由設定關閉：B-609 的非 cgroup 對外動作，或 P-119 的訊息送出；行為見 [B-615](../../daemon/components.md) | false |
| `helper_unavailable`、`unsupported` | helper 不在／部署不支援所選固定動作（含沒有 cgroup 時的 `cgroup_limits` 與 `spawn_as` 帶 `frame`） | false |
| `path_not_granted`、`conflict` | 超出路徑範圍／OS 現況不符所要求的設定 | false |
| `group_not_granted`〔第十八批〕 | 群組不在登記的 `groups` 授權裡 | false |
| `resource_observation_failed` | 有框卻讀不到 cgroup 實際配置（[B-607](../../daemon/registration.md)） | false |
| `response_too_large` | 一筆查詢結果就超過封包上限 | false |
| `provision_failed`、`start_failed` | 固定動作或啟動失敗 | false，先核對是否已有副作用 |

通道新增的 `token_invalid`、`kind_mismatch`、`mailbox_full`、`message_too_large` 見 [P-119](channel.md)（第十九批）。

## P-112．schema 與最小範例〔建議預設，未拍板〕

| schema | 驗什麼 |
|---|---|
| [common](../../../protocol/schemas/common.schema.json) | 只放共用型別 |
| [daemon-rpc](../../../protocol/schemas/daemon-rpc.schema.json) | 公開 IPC，含 P-117～119 的通道 method |
| [daemon-registration](../../../protocol/schemas/daemon-registration.schema.json)、[daemon-provision](../../../protocol/schemas/daemon-provision.schema.json) | 上面兩類 method 的參數 |
| [daemon-helper](../../../protocol/schemas/daemon-helper.schema.json) | 私有通道 |

**範例**：[examples/daemon/](../../../protocol/examples/daemon/) 的檔名首段對應 schema：`config`、`state`、`runner_report`、`launch-error` 驗同名 schema，`helper_*` 驗 helper，其餘驗 rpc。正反例涵蓋必填、未知欄位、版本、掛行程帶週期、通道憑證、查詢分頁與結果矛盾；解析、授權與 OS 事實仍要照正文驗收。

**嚴格或放寬**（照 [P-007](../../../protocol/README.md)，第十八批）：

- 持久檔 `daemon-config`、`daemon-state`、`daemon-launch-error`：放寬，不寫 `additionalProperties:false`；它們共用的 `$defs` 用開放版（`TopRegistrationOpen`、`RegistrationOpen`、`ProvisionGrantOpen`、`IdentityGrantOpen`、`GrantItemOpen`、`GroupItemOpen`）。
- 嚴格：`daemon-rpc`、`daemon-helper`、`daemon-provision`、`daemon-runner-report`，以及 `daemon-registration` 的 `RegisterParams`、`BoundRegistration`、`TopRegistration`、`MountRecord`。
