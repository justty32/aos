# 工作與結果

← [共用約定與分工](README.md)｜[工作材料](../base/work.md)｜[LLM 代發](llm-work.md)｜[LLM 池](../scheduling/llm.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - `aos-as`（任務自己換帳號）：第十三批暫緩（[P-212](../settled/deferred/protocol/tick.md#p-212aos-as切換帳號建議預設未拍板)）；現行切帳號只在 daemon 設定檔做（帳號模組 [B-646](../settled/daemon/account.md)）。
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit/08-1001-node模組與統一更新.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

LLM 代發（P-405～P-407：池設定、LLM 請求、LLM 結果與重試）在 [llm-work](llm-work.md)；本篇其餘條號不變。取消工作是 P-411（第十七批新增）。

〔使用者方向 2026-09-30，第十八批〕本篇只留欄位、JSON、schema、範例與程式 argv；行為以主規格為正本：工作識別 [T-03](../terms.md)、固定材料與預設值 [B-101](../base/work.md)、結果 [B-103](../base/work.md)、取消 [B-203](../base/execution.md)、掛行程與砍掉 [B-613](../settled/deferred/daemon/channel.md)、標準配備的 once [B-629](../settled/deferred/template.md)、unknown 與從未啟動證據 [S-401](../scheduling/operations.md)。本篇的 schema 照 [P-007](README.md) 的放寬通則：不認得的欄位忽略（[C-07](../contracts.md)）。

## P-400．兩個入口〔使用者方向 2026-09-29〕

工具由 `tools.target_node` 選路：是 node id 就以 `kernel.work.submit` 交該 kernel；是 null 就由 agent 自己經通道 `node.mount` 掛工具行程（〔第十九批〕上層就是憑證所屬的 tick，也就是 agent 自己）、保存用量，kernel 用收集 module 讀。LLM 以 `llm.chat` 投 `llm.target_node`；填 null 是「直連」檔，agent 自己打 endpoint、不經本篇的池。兩條路線與三檔以 [S-301](../scheduling/llm.md) 為正本；開 agent 的 kernel 決定地址與權限。

兩種檔案請求的 params 都是完整 inst，argv 分別以 `aos kernel work submit`、`aos llm chat` 開頭；業務材料是 inst.stdin 指向的 JSON 檔，命令核對見 [messages P-306](messages.md)。材料的 node_id 是最初發起 node，job_id、attempt_id 的意思見 [T-03](../terms.md)；仍須核對可信來源。命令完成才回執行結果，不先回 ACK；內層工作／LLM 結果是命令的 stdout JSON。

## P-401．工作材料〔建議預設，未拍板〕

[`work-request`](schemas/work-request.schema.json) 定義請求；stdin 的工作材料：

| 欄位 | 意思 |
|---|---|
| `node_id`、`job_id`、`attempt_id` | P-400 的配對識別 |
| `inst` | [inst 第 1 版](../base/inst.md) 原始物件；引用 [inst schema](schemas/inst.schema.json)，仍須在目標身分展開後驗證 |
| `base` | 原 inst 的絕對基準資料夾；複製材料不能偷偷換成工作資料夾 |
| `timeout_ms`（可省） | 放行後逾時，正整數；預設值見 [B-101](../base/work.md) |
| `output_limit_bytes`（可省） | 每條捕獲串流上限，正整數；預設值見 B-101 |

接納時固定哪些材料、stdin 副本怎麼存，依 [B-101](../base/work.md)。工具呼叫先依 [A-401](../agent/tools.md) 驗參數、轉 inst；run／tool_call 對照留在發起 node。

## P-402．once 與工作材料〔使用者方向 2026-09-29；第十九批改寫〕

〔使用者方向 2026-09-30，第十九批〕once 是標準配備的一項（[B-629](../settled/deferred/template.md)），做法是經 tick–daemon 通道把行程掛到 daemon 上跑（`node.mount`，[B-613](../settled/deferred/daemon/channel.md)），不再是登記的一種。掛載目標依 [inst 的「inst 目標：檔案或資料夾」](../base/inst.md#inst-目標檔案或資料夾)；資源歸屬與核權依 B-613，通道的環境變數與憑證依 [B-612](../settled/deferred/daemon/channel.md)，啟動失敗旁檔（`.err`）格式依 [daemon P-110](../settled/deferred/protocol/daemon/provision-and-runner.md)。

〔使用者方向 2026-09-29，第十六批〕**工作目錄名要加前綴**：不同成員都可能用 `attempt-1`，同一個 kernel 裡會撞名。目錄名一律是 `<前綴>-<attempt_id>`，前綴是「**配出這個 attempt_id 的 node**」絕對路徑 UTF-8 bytes 的 sha256 前 16 個小寫 hex。node 路徑不能直接當目錄名，雜湊長度固定、只有 `[0-9a-f]`。全篇及 kernel／agent 篇路徑裡的 `state/work/<attempt_id>/`、`.aos/jobs/<attempt_id>/`，`<attempt_id>` 都指這個目錄名；檔案內容與 RPC 裡的 attempt_id 欄位不加前綴。

〔第十八批補，建議預設，未拍板〕配出者不一定是工作材料的 `node_id`：第一次嘗試的 ID 是發起 node 配的，前綴就是發起 node；LLM 池因限流重試時由池自己配新 attempt_id（[P-407](llm-work.md)），前綴就是池 node。材料的 `node_id` 始終保留最初發起 node，不跟著換。安排工作的 node 在工作狀態記下配出者（kernel 記在 [kernel-work-state](schemas/kernel-work-state.schema.json)；省略就是材料的 `node_id`），讀目錄時核對「前綴＝配出者的雜湊」與 request.json 的 attempt_id，不拿材料 node_id 算前綴。碰撞機率可忽略，但仍照這樣核對。

例：`/srv/aos/top/a` 發起 `llm.chat`，attempt_id 是 `attempt-1`，直投池 node `/srv/aos/pool`。

| 嘗試 | 誰配的 ID | 池裡的目錄 |
|---|---|---|
| 第一次 `attempt-1` | 發起 node `/srv/aos/top/a` | `.aos/jobs/94a18415f07a8c0d-attempt-1/` |
| 429 後第二次 `attempt-1.r2`（ID 由池自訂） | 池 node `/srv/aos/pool` | `.aos/jobs/073cf769a1854e5c-attempt-1.r2/` |

兩個目錄裡 request.json 的 `node_id` 都是 `/srv/aos/top/a`。

〔建議預設，未拍板〕本篇為保存請求與結果，在安排工作的 node 建 ignored `.aos/jobs/<attempt_id>/`，以其中的 `inst.json` 單檔掛載；資料夾只是材料布局，不是要被 tick 的 node。每次實際嘗試使用不同資料夾，內含：

```text
.aos/jobs/<attempt_id>/
  inst.json          # daemon 跑的外層 inst
  request.json       # 已接納請求的固定副本
  input/             # 只有需要固定輸入時才有
  llm-config.json    # 只有 LLM 嘗試才有：派出時固定的本池設定（不含 key，見 S-307）
  stdout.bin         # 有捕獲才有
  stderr.bin         # 有獨立捕獲才有
  result.json        # 執行器完整發布的 B-103 結果
  usage.json         # 標準配備的可信收尾量測；量不到可省
  launch-started     # 首次 node.mount 前落地，恢復不盲重跑
```

外層 inst 的 argv 是 `aos-work --work-dir <絕對工作資料夾>`，用工作所屬 node 已授權的有效身分跑；內層 `request.json` 的 inst 用什麼身分，依 [B-101](../base/work.md)（〔使用者方向 2026-10-01〕inst 頂層沒有 `user`）。

**掛載參數**〔使用者方向 2026-09-30，第十九批；參數細節為建議預設，method 與錯誤碼見 [daemon P-118](../settled/deferred/protocol/daemon/channel.md)〕：經通道送 `node.mount`，參數是 `node_id=<W 的絕對路徑>/inst.json`、`token=$AOS_TICK_TOKEN`（socket 位置在 `$AOS_DAEMON_SOCKET`，[P-117](../settled/deferred/protocol/daemon/channel.md)）、必要時 `parent_id`。**不帶 `identity_grant`、不帶週期，也不再另送 `node.wake`**：掛上就開始跑。誰掛、`parent_id` 怎麼填：

| 情況 | `parent_id` | 資源與核權歸誰 |
|---|---|---|
| kernel 的 work 任務替成員派工具 | 填材料的 `node_id`（成員，須在 kernel 有效上層鏈之下） | 成員 |
| agent 自跑工具（`tools.target_node` 為 null） | 省略 | 憑證所屬的 tick，即 agent 自己 |
| LLM 池的 `aos-llm` 派 `aos-llm-call` | 省略 | 憑證所屬的 tick，即池 node 自己 |

省略 `parent_id` 的兩種只能帶本格 `token` 走通道；agent 或池 node 不在 daemon 底下（cron、人手跑）時沒有通道、掛不了，〔記錄者依追答 11 歸類〕算功能受限、不另設替代路（[B-629](../settled/deferred/template.md)）。

`parent_id` 只給資源歸屬與核權（框放在它的框下、身分核對它的身分額度）；掛載的 W 不是要被 tick 的 node，沒有資料夾上下層的問題，其位置也不決定歸屬。〔使用者方向 2026-09-30，第十九批，撤「與目錄位置無關」的一般說法〕一般 node 的上層不是這樣：預設看資料夾包含，可用登記的 `parent_id` 覆蓋（[B-628](../settled/tick.md)）。何時建目錄、何時掛載（本格只保存材料，提交後下一格才掛）依 [B-624](../settled/deferred/mq.md) 與 B-613，kernel 代跑的步驟見 [kernel P-806](kernel-tasks.md)。結果只給路徑，發件者未必讀得到；風險由使用者承擔。

`launch-started` 的建立、`.err` 旁檔與 result.json 怎麼當證據、缺證據何時記 unknown，依 [S-401](../scheduling/operations.md)。標準配備的執行器（[B-629](../settled/deferred/template.md)）在移除掛載框前保存 [res-usage](schemas/res-usage.schema.json) 到 usage.json，發起者下格收量；量不到（包括 cgroup 走備援時，[B-631](../settled/deferred/cg.md)）不寫 usage.json、用量記 null，不採信工具自報。

## P-403．結果與串流〔建議預設，未拍板〕

[`work-result`](schemas/work-result.schema.json) 同時驗本地結果檔與回應。`result.json` 為 `version:1` 加結果欄位；所有檔案 RPC 的 `result` 用同一形狀，**不帶 version**。RPC 指令結果的 node_id 是執行指令的 node，job_id、attempt_id 都用 RPC id；業務材料內的工作識別另留在 stdout JSON。

| 欄位 | 意思 |
|---|---|
| `node_id`、`job_id`、`attempt_id` | 配回工作與嘗試；RPC 命令結果依上段 |
| `status` | `succeeded`／`failed`／`canceled`／`unknown`，依 [C-03](../contracts.md) |
| `reason` | `exited`、`signal`、`start_failed`、`timeout`、`canceled`、`oom`、`output_limit`、`descendants_remaining`、`output_incomplete`、`unknown` |
| `started` | `true` 已進入 inst 的執行階段；`false` 根本沒跑；`null` 證據不足 |
| `exit_code`、`signal` | 可得的原退出碼（0～255）或訊號（1～64，與 [daemon P-106](../settled/deferred/protocol/daemon/registration.md) 一致）；無資料填 `null`，兩者不同時有值 |
| `diagnostic`（可省） | 無 key 的有界診斷（最多 4096 字元）；可得時保留原始 errno 代號，例如 EAGAIN、ENOMEM |
| `stdout`、`stderr` | `{path,bytes,truncated}` 或 `null`；path 是絕對路徑，bytes 是實際保存量 |

`null` 表示沒有這份輸出證據；有檔且 `bytes:0` 才是確知空輸出。〔使用者方向 2026-09-30，第十八批〕當格就做完的本地動作（[messages P-306](messages.md) 表裡 `kernel.work.submit`、`llm.chat` 以外的命令），RPC 結果的 `stdout` 指 `state/messages/requests/<id>.stdout` 的絕對路徑，不填 null；落點與清理見 P-306、[B-103](../base/work.md)。若 inst 使用 `inherit`，外層將對應 fd 接捕獲 pipe，才由 aos-work 保存為 `.bin`；inst 的一般檔案、append、merge、`/dev/null` 規則照正本，不偷偷改成捕獲。直接寫檔若不能證明這次保存的完整 bytes，結果該串流填 `null`；merge 不虛構獨立 stderr。捕獲上限、OOM 證據與收尾沿 [B-103](../base/work.md)、[B-202／204](../base/execution.md)。

欄位怎麼填：退出 7 是 `failed/exited`；訊號保留 `signal`，不把 inst 的 `128+n` 合成碼當作 wait 的退出碼；`started:false/start_failed` 和子程式已跑、自己退出 125 必須分清。何時算 `succeeded`（正常退出 0 且後代清空）依 [B-103](../base/work.md)、[B-202](../base/execution.md)；工具語意錯誤與產品成功依 [A-403](../agent/tools.md)、[A-503](../agent/README.md)，不改程序證據。

## P-404．unknown 與拒收〔使用者方向 2026-09-29〕

unknown 放著不重做依 [S-401](../scheduling/operations.md)。合成 unknown 結果時缺失欄位填 null；已發布 RPC 回應不覆寫。

拒收沿 P-005：參數錯 -32602；業務錯 -32000，data.code 可為 work_not_authorized、input_unreadable、capacity_unavailable、pool_not_found、model_not_found、key_unavailable。只在能確認尚未接納的暫時容量／讀取問題才可 retryable:true；接納後的失敗回結果。配對錯或衝突留原件及事項，不夾 key／認證標頭。agent 的請求被拒收後 agent 怎麼收尾，延後（[P-008](README.md#p-008)）。

## P-411．取消工作〔使用者方向 2026-09-29，第十七批〕

行為（誰有權取消、排隊中與在跑的怎麼處理、收尾競態、只適用 once）以 [B-203](../base/execution.md) 為正本〔使用者方向 2026-09-30，第十八批〕；〔第十九批〕在跑的那一格經通道用 `node.kill` 砍掉掛載行程（[B-613](../settled/deferred/daemon/channel.md)）。本條只定格式。

**請求**：檔案請求 `work.cancel`（`aos work cancel`），投到**持有那件工作的 node** 的 `requests/`；例如 kernel 代跑的工具就投那個 kernel，範本裡由 work 任務宣告處理（[node P-202](../settled/protocol/tick.md)）。stdin 是 [msg-cancel-payload](schemas/msg-cancel-payload.schema.json) 的 `{request_id}`，指原請求（例如 `kernel.work.submit`）的 RPC id。

**回應**：收下就回 `{"accepted":true}`，只表示收下，不等於已取消；終局看原請求的回應（`canceled`／reason `canceled`，排隊中被拿掉的另帶 `started:false`）。

**錯誤**：

| 情況 | 回應 |
|---|---|
| 沒有權限（B-203 的兩種主人與原投件者都不是） | -32000，`data.code` 為 `cancel_not_authorized`；這份取消請求丟掉，原工作不受影響 |
| 找不到這個 request_id 的工作，或工作不在宣告 `work.cancel` 的任務手上（例如 LLM 轉交） | -32000，`work_not_found` |
| 收件 node 沒有任務宣告 `work.cancel`（agent、純池 node） | tick 回 -32601（[B-501](../base/transport.md)） |

**核權要存的欄位**：原請求檔消費後會被刪，B-203 要的兩個 UID 都在接件時記進工作狀態；kernel 記在 [kernel-work-state](schemas/kernel-work-state.schema.json) 的 `submitter_uid`（原請求檔的擁有 UID）與 `owner_exec_uid`（接件那一項任務實際的有效 UID：就是 tick 的有效 UID，即 node inst 的執行帳號；〔暫定〕任務包了 `aos-as` 換帳號時記換成的那個帳號，同 B-203）。

〔使用者方向 2026-09-30，第十八批〕目前只有 kernel 的 work 任務支援取消。LLM 請求與 agent 自己掛的工具行程的取消延後（[P-008](README.md#p-008)）；到時要補的欄位（forward-state 與 agent 請求的 `submitter_uid`、`canceling` 階段）一併列在那裡。

## P-408．程式契約〔建議預設，未拍板〕

| 完整 argv | 讀寫、身分與輸出 |
|---|---|
| `aos-work --work-dir W` | 讀 W/request.json 及目標身分可讀的材料，以 `base` 跑內層 inst；寫捕獲檔、W/result.json。用工作 node 身分，無切身分權限 |
| `aos-llm [--node N] --config C` | 一項 module 任務，node 省略用 cwd（tick 設為 node 根）；C 可相對，依 cwd 解。讀 C、池狀態、既有結果，及收件或 forward 已接納的材料（看任務有沒有宣告 `llm.chat`，[S-307](../scheduling/llm.md)）；保存狀態／待送封套。只對已提交的工作材料經通道 `node.mount` 掛載 `aos-llm-call`；tick 負責 commit 後投件、清收件原件，用 N 的 user |
| `aos-llm-call --work-dir W --config C` | C 是 aos-llm 派出時固定在 `W/llm-config.json` 的本池設定，argv 帶絕對路徑；讀 C、私有 key_ref 與 W/request.json，只送一次 HTTP，寫 W/result.json；請求有 stream_path 時邊收邊寫該檔；用池管理 node 的 user |

三支程式 stdin 都是 `/dev/null`，stdout 保留為空（業務輸出走檔案），stderr 只放無 key 的 `代號: 白話` 診斷；內層 inst 的 stdin／stdout／stderr 另依 P-403。〔使用者方向 2026-09-30，第十九批〕要掛載的程式（`aos-llm`）從 daemon 放的兩個通道變數 `AOS_DAEMON_SOCKET`、`AOS_TICK_TOKEN` 找通道（[B-612](../settled/deferred/daemon/channel.md)、[P-117](../settled/deferred/protocol/daemon/channel.md)），缺任一個就自己擋下、報 `no_channel`、〔暫定〕結束碼 125；`aos-work`、`aos-llm-call` 不用通道，本身不新增必需 `AOS_*` 變數（inst 的 `envs` 用 `clear` 會把通道變數一起清掉）。PATH／目標帳號環境及 inst.envs 依 inst 正本，不從呼叫者環境取得池 key。

結束碼：0＝這次處理完成且必要結果已完整發布（工作本身仍可能 failed／unknown）；2＝用法／設定錯，未開始；125＝自身無法開始；1＝已開始處理後自身失敗（包括結果寫不出），不能把未發布結果算成功。aos-llm 的 0 只表示本格步驟完成，不代表 HTTP 工作成功。串流中途斷線、stream_path 開不了時的結束碼與結果依 [S-305](../scheduling/llm.md)。工作 inst 的內層退出碼只記在工作結果，不能拿 wrapper 的 0 代替。訊號由父程序看 wait 狀態；wrapper 沒寫結果時照 [S-401](../scheduling/operations.md) 的證據規則處理。

## P-409．schema 與最小範例〔建議預設，未拍板〕

每行範例都在 [examples/work/](examples/work/)；`work.cancel` 的範例在 [examples/messages/](examples/messages/)。schema 只能驗 JSON 形狀，P-002 的重複 key、有限數、位元組上限與執行授權另驗。本篇 schema 都放寬（不認得的欄位忽略），只有 C-07 的禁止鍵出現就拒收。

| schema | 正例 | 主要錯誤例與原因 |
|---|---|---|
| [work-request](schemas/work-request.schema.json) | 工作指令 inst 與 stdin 材料 | 零逾時或命令不符 |
| [work-result](schemas/work-result.schema.json) | 本地結果與 RPC 命令結果 | 成功卻 exit 7、雙 result/error、signal 超過 64 |
| [msg-cancel-payload](schemas/msg-cancel-payload.schema.json) | `work.cancel` 的 stdin 材料；取消請求與拒絕回應 | 空物件、argv 不是 `aos work cancel`、同時帶 result 與 error |
| [llm-config](schemas/llm-config.schema.json) | 池設定；多一個不認得的欄位仍收 | 明文 `api_key`（[C-07](../contracts.md) 禁止鍵）；endpoint 池寫了 `max_attempts` |
| [llm-request](schemas/llm-request.schema.json) | LLM 指令 inst 與 stdin 材料（另有串流正例） | 串流檔用相對路徑 |
| [llm-result](schemas/llm-result.schema.json) | stdout 的 LLM 結果 | 成功漏 message、部分 usage |

## P-410．待決與跨篇

見 [README P-008](README.md#p-008)。
