# 協議篇：共用約定與分工

← [規格入口](../README.md)｜[名詞](../terms.md)｜[daemon](../daemon.md)｜[通用 tick](../tick.md)｜[inst](../base/inst.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)｜[條號索引](#p-index)

2026-09-29 依 node 架構整合，2026-09-30 依第十八批改成純格式篇，依第二十批改時間單位與 tick 核心的格式。本篇把主規格落成**程式之間**的欄位、JSON、schema、範例、argv 與結束碼。人手操作見 [CLI](../cli.md)；本篇定機器用的形狀，同一批程式人也能直接跑（[通則](../README.md#原則能下指令能管檔案就能交給-agent)）。

## P-001．範圍與原則〔主編補〕

- 〔使用者方向 2026-09-30，第十八批〕**主規格是行為正本**：本篇只留欄位、JSON、schema、範例、method／argv 形狀、結束碼與錯誤碼；寫到行為時只留一句加主規格條號。各協議檔對應的行為正本見 P-009，分散兩處的主題照 [V-01 正本表](../conformance.md)。兩邊衝突以主規格和裁定為準；發現缺口補進主規格，不在格式裡偷定新行為。
- **請求路線**〔使用者方向 2026-09-29〕：要 daemon／helper 做事＝**IPC 找 daemon**（本機 socket 上的 JSON-RPC）；要別的 node（上層 kernel、LLM 代發服務、別隊 agent）做事＝**檔案承載的 JSON-RPC**，投進對方收件區。〔使用者方向 2026-09-30，第十九批〕明示例外只有一個：**tick–daemon 通道**。它是 daemon 開的 tick 在同一支 socket 上以憑證跟 daemon 說話的 IPC，可做登記與解除、掛行程與砍掉、叫醒，也可把跟檔案收件同格式的訊息交 daemon 暫存、轉給同一 daemon 底下的 tick（不保證送達）；行為正本見 [B-612～614](../daemon.md)，格式見 P-117～119（[daemon 協議](daemon/README.md)）。不是 daemon 開的 tick 沒有通道，只走檔案。
- 精簡：一個格式能用就不做兩個；欄位只放主規格真的需要的；不為 agent、工具另開入口。
- 原生 Linux 與 WSL2 同一套格式。

## P-002．JSON〔建議預設，未拍板〕

- UTF-8、無 BOM；一份檔案或一行訊息恰好一個 JSON object。拒絕重複 key、非有限數、尾隨資料。
- ID 是字串：`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`，可直接當檔名。node id 是 node 資料夾的絕對路徑（正規化、無 `..`、無結尾 `/`）。
- 時間〔使用者方向 2026-09-30，第二十批；哪些用格數、哪些留毫秒以 [C-01](../contracts.md) 為正本〕：aos 內部決定的時長用格數，欄位名 `_ticks` 結尾（common `Ticks`）；拿來計算的起算點記第幾格，`_seq` 結尾（common `TickSeq`）；外部規定的時長與給人看的時間點用毫秒，`_ms`／`_at_ms` 結尾（common `TimeMs`）。明示例外：cgroup CPU 的 `quota_us`、`period_us`、`usage_us` 直接用微秒，不換算或捨去精度（原本清理設定 `interval_seconds` 的例外改成格數，見 [B-404](../base/storage.md)）。逾時用經過時間，排先後用序號，不靠牆鐘、mtime 或檔名排序。
- 自己的持久 JSON 檔帶 `"version": 1`；inst 與 tasks 用自己的 `_metainfo`，JSON-RPC 用 `"jsonrpc": "2.0"`，不另加 `version`。
- 版本與未知欄位依 [C-07](../contracts.md)〔使用者方向 2026-09-30，第十八批〕：持久檔與檔案 RPC 不認得的欄位忽略，daemon IPC、helper 私有通道與 runner 回報拒絕；永遠禁止的鍵出現就整份拒收。schema 寫法見 P-007。

## P-003．檔案發布與收件〔建議預設，未拍板〕

- **發布**：暫存檔放目標資料夾的 `.tmp/`；名字以 `.` 開頭的檔不算已發布。寫入、同步、rename 與撞名的行為見 [B-402](../base/storage.md)、[B-503](../base/transport.md)。
- **收件區**〔使用者方向 2026-09-29〕：每個 node 根下的 `requests/`（別人問我）與 `responses/`（我問別人、別人回我），都在 `.gitignore` 裡；`inbox` 這名字保留給日後的工具，不當資料夾名。權限布置見 [P-208](node.md)；通知的意思見 [B-504](../daemon.md)。
- **去重**：檔名就是請求 ID；比對規則見 [B-503](../base/transport.md)。
- **消費與送出**：待送檔放 `.aos/outbox/`，格式見 P-206；提交順序見 [B-623](../tick.md)（Q1）、[B-624](../tick.md)（Q2），由標準任務表範本裡的系統級任務做（[B-629](../tick.md)）。

## P-004．JSON-RPC 的兩種載體〔建議預設，未拍板〕

物件形狀照 JSON-RPC 2.0：請求 `{"jsonrpc":"2.0","id":"<ID>","method":"...","params":{...}}`，回應 `{"jsonrpc":"2.0","id":"<ID>","result":{...}}` 或 `"error":{...}`。`id` 必填且是 P-002 的 ID；唯解析／請求錯誤（-32700／-32600）取不到合法 ID 時，回應用 `id:null`，成功回應與請求仍不准 null；不用 batch、不用 notification。公開 method 就是對應指令去掉 `aos`、以 `.` 連接，例如 `agent.say` 對 `aos agent say`；內部 helper 用 `daemon.helper.*` 對 `aos daemon helper ...`，仍只走私有通道。

1. **socket（daemon IPC）**：Unix stream socket，一行一個 object、以 LF 結尾，單行上限 256 KiB。呼叫者怎麼認見 [B-601](../daemon.md)：人手與 CLI 看 `SO_PEERCRED`，封包裡自稱的身分不算；〔使用者方向 2026-09-30，第十九批〕tick–daemon 通道上的請求在 params 帶本格憑證，daemon 以憑證認 tick（[B-612](../daemon.md)，欄位見 P-117）。
2. **檔案（node 之間）**：params 是一份 inst，argv 保留 `aos`；-32601 的條件見 [B-501](../base/transport.md)，由收件這項系統級任務回（[B-623](../tick.md)）。回應 result 用 [work-result](work.md) 的指令執行結果。請求檔名 `<id>.json`，內容就是上面的請求物件，外加頂層 `"reply_to"`：回應要投去的收件區（node id）。子目錄格式見 [messages P-301～303](messages.md)；檔案回應必須有合法 ID，不產生 `null.json`；壞件怎麼處理見 [B-623](../tick.md)。檔案上限 256 KiB，大內容放檔案、用路徑引用。查詢或重送用同一個 `id`，見 [B-503](../base/transport.md)。通道上轉交的訊息就是這個請求物件（[B-614](../daemon.md)）。

## P-005．錯誤〔建議預設，未拍板〕

JSON-RPC `error` 的 `code` 照 2.0 保留碼（-32700 解析、-32600 請求不合法、-32601 沒這個 method、-32602 參數不合法、-32603 內部）；其他一律 -32000，真正的意思放 `error.data.code`（小寫底線字串，例如 `user_not_granted`、`not_registered`、`busy`），另帶 `error.data.retryable`（bool）。各篇列自己的 `data.code`，不另編數字碼；各篇的碼表在哪見下面的[集中碼表](#集中碼表)。錯誤訊息不夾帶別的 node 的內容或 key。

## P-006．程式：argv、環境、結束碼〔建議預設，未拍板〕

- 每支程式的篇章要列：完整 argv、stdin／stdout／stderr 各放什麼、讀寫哪些檔、用誰的身分跑、環境變數、結束碼。
- argv 直接 exec，不經 shell。大資料走 stdin 或檔案，不塞 argv；key 不進 argv 或環境，見 [S-301](../scheduling/llm.md)。
- aos 自己的環境變數用 `AOS_` 開頭；環境不是授權依據。〔使用者方向 2026-09-30，第十九批〕唯一例外是 daemon 開 tick 與掛載行程時放的通道變數 `AOS_DAEMON_SOCKET`、`AOS_TICK_TOKEN`（[B-612](../daemon.md)，格式見 [P-117](daemon/channel.md)）：憑證由 daemon 發、在通道上核對，變數本身仍不授予任何權限。
- 結束碼共同意思：`0` 成功；`2` 用法或設定錯，還沒開始做事；`125` 自己無法開始（如身分不准）；runner 收尾失敗也是 125，須以 P-110 的 started／error 區分，不能只看碼。其他碼由各篇自己定；被訊號殺掉由父程序看 wait 狀態，不猜 `128+n`。
- 程式名：daemon 是 `aos daemon`；其他沿主規格已有名字（`aos-tick`、`aos-clean`、`aos-attend`）。〔第二十批〕系統級任務與普通程式的程式名、argv 與結束碼見 [P-203](node.md)、P-211～213（[node](node.md)）。新公開指令用 `aos <用途> <動作> [更深]`。

### 集中碼表

〔主編補，第十八批〕錯誤碼與結束碼的共同意思只在 P-005／P-006；各處自己的碼表在下列位置，本表只列連結，不重抄碼值。

| 哪一類 | 碼表在哪 |
|---|---|
| JSON-RPC 保留碼、-32000 與 `data.code` 通則 | P-005 |
| daemon IPC 與 helper 私有通道的 `data.code` | [P-111](daemon/provision-and-runner.md) |
| runner 回報、125、未啟動的 `.err` 旁檔 | [P-110](daemon/provision-and-runner.md) |
| inst 的錯誤代號、126／127 | [inst「執行與錯誤」](../base/inst.md#執行與錯誤) |
| `aos-tick` 結束碼（核心的碼與停格碼）；系統級任務與普通程式（`aos-git`、`aos-cg`、`aos-as`、`aos-needs` 等）的結束碼 | [P-203](node.md)、P-211～213（[node](node.md)） |
| tick–daemon 通道的 `data.code`；客戶端的 `no_channel` | [P-119](daemon/channel.md) |
| 檔案 RPC 的業務拒收（method、訊息、取消） | [P-306](messages.md)、[P-411](work.md) |
| 工作拒收 | [P-404](work.md) |
| work／LLM 程式結束碼 | [P-408](work.md) |
| 資源 module | [P-507](resources.md) |
| `aos-clean`、`aos-attend` | [P-605](ops.md)、[P-603](ops.md) |
| agent 任務程式、設定檢查 | [P-704](agent-tasks.md)、[P-712](agent-tasks.md) |
| kernel 設定檢查 | [P-805](kernel-tasks.md) |
| CLI 的失敗代稱 | [H-002](../cli/README.md) |

設定檢查的結束碼 kernel 回 2、agent 回 1，兩邊不一致；要不要統一屬 agent 內部機制，延後（P-008）。

## P-007．schema 與範例〔主編補〕

- schema 用 JSON Schema 2020-12，放 `schemas/`，檔名以該篇前綴開頭（例如 `daemon-register.schema.json`）。共用型別（ID、NodeId、TimeMs、Ticks、TickSeq、Error、JSON-RPC）只在 `schemas/common.schema.json` 的 `$defs`，各篇以相對 `$ref` 引用。
- 範例放 `examples/<篇名>/`，命名 `<主題>.<情境>.valid.json`／`.invalid.json`；每個 invalid 在正文說明為什麼錯。**只做真的需要的範例**：每種訊息一個最小正例、一個主要錯誤；不求量。
- schema 通過不代表授權或狀態正確；那些由主規格的驗收管。

**放寬通則**〔使用者方向 2026-09-30，第十八批；寫法為主編補〕：哪裡放寬、哪些鍵永遠禁止，以 [C-07](../contracts.md) 為正本。schema 照下表寫：

| schema | 不認得的欄位 |
|---|---|
| `daemon-rpc`、`daemon-helper`、`daemon-provision`、`daemon-runner-report`（daemon IPC、helper 私有通道、runner 回報） | 維持 `additionalProperties:false` |
| 其餘全部（持久檔與檔案 RPC，含 `daemon-config`、`daemon-state`、`daemon-launch-error`） | 不寫 `additionalProperties:false`，也不寫 `unevaluatedProperties:false` |

- **禁止鍵**：放寬的 schema 用 `"properties": {"<鍵>": false}` 明列，出現就不合法。
- **兩邊共用的 `$defs`**：嚴格與開放的地方都要用同一個物件時，分成兩個名字，開放版加 `Open` 字尾（檔案 RPC 的沿用 `File` 字首），不靠引用處封口。`common` 裡：`Error`、`RpcRequest`、`RpcResponse` 是嚴格版，給 daemon IPC 與 helper；`ErrorOpen`、`FileRpcRequest`、`FileRpcResponse` 是開放版，給持久檔與檔案 RPC。
- **範例**：放寬的 schema，原本「多一個欄位」的 `.invalid` 範例刪掉，或改成正例示範多一個欄位仍收；嚴格的照留。每個禁止鍵各留一個反例。
- 版本號：小改不動 schema 的 `version` 常數；升版時 schema 同時接受目前版與前一版。

**怎麼驗範例**：從 repo 根目錄跑 `python3 proto6/spec/protocol/examples/messages/validate.py`，驗全部 schema 與 valid／invalid 範例；需要 `jsonschema`（`pip install jsonschema`，會一併帶 `referencing`）。另有 `python3 proto6/spec/check_ids.py`，檢查 spec 與 notes（不含 archive）裡每個 P-／B-／S-／A-／H-／C-／T-／V- 條號引用都有定義處，並抓同一條號兩個標題、只剩索引列沒有正文；[V-01](../conformance.md) 預留而還沒寫正文的新條號只提醒，加 `--strict` 才算錯。有錯就列出並以非 0 結束。

<a id="p-008"></a>

## P-008．延後與待決

### 延後清單

〔使用者方向 2026-09-30，第十八批〕以下這輪只標「延後」，不展開設計；各處只寫一句延後並連到這裡。依據見[第十八批](../../notes/verdicts/09-special-computing-os.md)。

| 延後的東西 | 依據 | 標在哪 |
|---|---|---|
| tick 以外其餘計算單位的外殼（設-14），「隨機性」要不要成為外殼的一欄；隨機性怎麼量、怎麼跟完成度與消耗權衡 | 裁定 1、方向 6 | [T-06](../terms.md)、[T-07](../terms.md) |
| kernel／agent／custom 類任務的逾時與取消 | 裁定 1 補充 | [P-202](node.md)、[P-203](node.md)；[B-203](../base/execution.md) 只適用 once |
| agent 內部機制：agent 請求被拒收（新裁-2）、卡在 unknown 的使用者輸入（裁-10）、agent 設定檢查的結束碼要不要跟 kernel 統一（第 20 題，記錄者歸類） | 裁定 12 | [P-705](agent-tasks.md)、[P-707](agent-tasks.md)、[P-708](agent-tasks.md)、[P-712](agent-tasks.md)、[P-716](agent-tasks.md)、[P-404](work.md)、[P-603](ops.md)、[P-609](ops.md)、[P-805](kernel-tasks.md) |
| agent 之間的問答 | 裁定 11 | [P-705](agent-tasks.md)、[P-306](messages.md)、[P-803](kernel-tasks.md)、[S-406](../scheduling/operations.md) |
| agent 自己開的 once：做完照第十七批不叫醒、結果由 agent 自己收；回查間隔放哪（Q29）；LLM 請求與 agent 自開 once 的取消（裁-5：下一輪要在 forward-state 與 agent 請求加 `submitter_uid`、`canceling` 階段） | 裁定 10、12 | [P-704](agent-tasks.md)、[P-707](agent-tasks.md)、[P-411](work.md) |
| 預設鬧鐘和「投件被丟掉」對不上（Q26） | 裁定 12、13 | [P-706](agent-tasks.md)、[P-206](node.md)、[B-624](../tick.md) |
| 通用外部資源池（設-15）：LLM 池是外部計算的第一個實例，其他外部計算由各 kernel 以資源任務自訂；通用介面隨第一列一起延後 | 裁定 1、Q4 | [S-301](../scheduling/llm.md) |
| git 歷史回收 | 裁定 14 | [B-404](../base/storage.md)、[P-606](ops.md)、[H-034](../cli/gaps.md) |

### 已裁定（第十一批）

- **once 資源歸屬與啟動失敗證據**〔使用者方向 2026-09-29〕：行為見 [B-613](../daemon.md)（〔使用者方向 2026-09-30，第十九批〕once 經通道把行程掛到 daemon；〔第二十批〕是任務呼叫的通道事務），`.err` 旁檔格式見 [P-110](daemon/provision-and-runner.md)。
- **首版網路**〔使用者方向 2026-09-29〕：只記用量摘要，不做硬限速，見 [resources P-506](resources.md)。

### 工程預設與待補接口

第九批已准工程數字先照建議、實作量過再調；各篇「建議預設」可替換，不逐條再問使用者。

- 登記、IPC、去重、摘要發布、資源 method、鎖與故障停格的行為見 [daemon](../daemon.md)、[tick](../tick.md)、[transport](../base/transport.md)；格式見 [daemon 協議](daemon/README.md)、[messages](messages.md)、[node](node.md)。
- **LLM 共享窗口與池狀態**：最小格式由 [kernel P-811～812](kernel-tasks.md) 定義；兩個計數與池政策見 [S-301、S-304](../scheduling/llm.md)，資料保留另依 [P-606](ops.md)。
- **領域接口**：模型／人格／工具 adapter、正式回話、context 與預設清理遍歷已由 [agent 任務篇](agent-tasks.md) 及 [kernel 任務篇](kernel-tasks.md) 定義；unknown 見 [S-401](../scheduling/operations.md)。
- done 留存、磁碟 hardlink 計量與池路由照各篇工程預設；格式驗證不等於產品實作。

## P-009．各協議檔對應的行為正本〔主編補，第十八批〕

協議篇各檔只留左欄的格式；行為寫在右欄的主規格。寫到行為時留一句加右欄條號。還只寫在協議篇的行為句，改到時搬到右欄對應處，原處留一句加條號。

| 協議檔／條款 | 本篇只留 | 行為正本（主規格） |
|---|---|---|
| [daemon](daemon/README.md)／P-100～119 | 設定欄位、IPC method 與 params／result、tick–daemon 通道（P-117～119）、helper 通道、runner 回報、錯誤碼 | [daemon](../daemon.md)（B-601～614；通道 B-612～614）；[身分](../base/identity-resources.md)；[inst](../base/inst.md) |
| [node](node.md)／P-200～213 | 資料夾布局名稱、inst／tasks 的 JSON、`aos-tick` argv 與結束碼、結束碼紀錄、系統級任務與普通程式的 argv、鬧鐘與待送檔格式 | [tick](../tick.md)（B-602、B-620～633）；[儲存](../base/storage.md)；[投件](../base/transport.md)；[執行器 B-202](../base/execution.md) |
| [messages](messages.md)／P-300～309 | 請求／回應檔、method 目錄、摘要檔 | [投件](../base/transport.md)；[tick](../tick.md)；[S-201](../scheduling/admission.md) |
| [work](work.md)／P-400～404、408～411 | 工作 payload、結果 JSON、`work.cancel` 形狀、程式 argv | [工作材料](../base/work.md)；[執行器](../base/execution.md) |
| [llm-work](llm-work.md)／P-405～407 | 池設定、LLM 請求與結果 | [LLM S-301～307](../scheduling/llm.md) |
| [resources](resources.md)／P-500～ | 配額與用量檔、cgroup 檔對照 | [S-203、S-205～207](../scheduling/admission.md)；[身分與 OS 資源](../base/identity-resources.md) |
| [ops](ops.md)／P-600～ | 事項檔、`aos-attend`／`aos-clean` 的 argv、設定與報告 | [S-405](../scheduling/operations.md)；[B-404](../base/storage.md) |
| [agent 任務](agent-tasks.md)／P-700～ | agent 設定、工具清單、對話、context 與用量檔、範本 | [agent](../agent/README.md) |
| [kernel 任務](kernel-tasks.md)／P-800～ | kernel 設定、成員、各狀態檔、範本 | [scheduling](../scheduling/README.md) 各篇（S-201～207、[S-301～307](../scheduling/llm.md)、[S-401、S-405、S-406](../scheduling/operations.md)） |

## P-010．inst 目標：檔案或資料夾

（第十八批：行為已搬到 [inst「inst 目標：檔案或資料夾」](../base/inst.md#inst-目標檔案或資料夾)；條號保留。）

<a id="p-index"></a>

## 條號索引（P-xxx → 檔案）

協議篇各條所在的檔案；別篇多用條號引用，照這張表找。檔案拆分或搬位置時條號不變，只改這張表。daemon 協議的條號表只留在 [daemon/README.md](daemon/README.md) 一份。

| 條號 | 標題 | 檔案 |
|---|---|---|
| P-001 | 範圍與原則 | [README.md](README.md)（本篇） |
| P-002 | JSON | [README.md](README.md)（本篇） |
| P-003 | 檔案發布與收件 | [README.md](README.md)（本篇） |
| P-004 | JSON-RPC 的兩種載體 | [README.md](README.md)（本篇） |
| P-005 | 錯誤 | [README.md](README.md)（本篇） |
| P-006 | 程式：argv、環境、結束碼 | [README.md](README.md)（本篇） |
| P-007 | schema 與範例 | [README.md](README.md)（本篇） |
| P-008 | 延後與待決 | [README.md](README.md)（本篇） |
| P-009 | 各協議檔對應的行為正本 | [README.md](README.md)（本篇） |
| P-010 | inst 目標：檔案或資料夾 | [README.md](README.md)（本篇） |
| P-100～119 | daemon 協議 | 各條所在檔見 [daemon/README.md](daemon/README.md) 的條號表 |
| P-200 | 資料夾布局 | [node.md](node.md) |
| P-201 | inst 的格式與展開驗證 | [node.md](node.md) |
| P-202 | 任務註冊表 | [node.md](node.md) |
| P-203 | aos-tick 與任意任務程式 | [node.md](node.md) |
| P-204 | 成敗、group 與 needs | [node.md](node.md) |
| P-205 | git 提交與恢復 | [node.md](node.md) |
| P-206 | 收件與派送的提交邊界 | [node.md](node.md) |
| P-207 | 加入普通設定與重要設定手改 | [node.md](node.md) |
| P-208 | 收件區權限 | [node.md](node.md) |
| P-209 | 待決與跨篇 | [node.md](node.md) |
| P-210 | 預設範本與恢復前驗證 | [node.md](node.md) |
| P-211 | aos-cg：每項一框 | [node.md](node.md) |
| P-212 | aos-as：切換帳號 | [node.md](node.md) |
| P-213 | 每項結束碼紀錄 | [node.md](node.md) |
| P-300 | 兩條路各做什麼 | [messages.md](messages.md) |
| P-301 | 收件區分請求與回應 | [messages.md](messages.md) |
| P-302 | 完整封包 | [messages.md](messages.md) |
| P-303 | 回應路由與來源 | [messages.md](messages.md) |
| P-304 | 同 ID、衝突與重送 | [messages.md](messages.md) |
| P-305 | 送出、消費與門鈴順序 | [messages.md](messages.md) |
| P-306 | method 就是指令 | [messages.md](messages.md) |
| P-307 | 上層直接讀成員摘要 | [messages.md](messages.md) |
| P-308 | schema 與最小範例 | [messages.md](messages.md) |
| P-309 | 待決與跨篇 | [messages.md](messages.md) |
| P-400 | 兩個入口 | [work.md](work.md) |
| P-401 | 工作材料 | [work.md](work.md) |
| P-402 | once 與工作材料 | [work.md](work.md) |
| P-403 | 結果與串流 | [work.md](work.md) |
| P-404 | unknown 與拒收 | [work.md](work.md) |
| P-405 | 代發啟動與池設定 | [llm-work.md](llm-work.md) |
| P-406 | LLM 請求與 messages | [llm-work.md](llm-work.md) |
| P-407 | LLM 結果、usage 與有限重試 | [llm-work.md](llm-work.md) |
| P-408 | 程式契約 | [work.md](work.md) |
| P-409 | schema 與最小範例 | [work.md](work.md) |
| P-410 | 待決與跨篇 | [work.md](work.md) |
| P-411 | 取消工作 | [work.md](work.md) |
| P-500 | module 就是任務 | [resources.md](resources.md) |
| P-501 | 配額檔 | [resources.md](resources.md) |
| P-502 | 用量摘要與檔案交接 | [resources.md](resources.md) |
| P-503 | CPU、記憶體與 pids | [resources.md](resources.md) |
| P-504 | 套用不是 git 回滾 | [resources.md](resources.md) |
| P-505 | 路線與 LLM 份額 | [resources.md](resources.md) |
| P-506 | 磁碟與網路 | [resources.md](resources.md) |
| P-507 | 沒裝、失敗與驗證 | [resources.md](resources.md) |
| P-508 | 待決與跨篇 | [resources.md](resources.md) |
| P-600 | 範圍 | [ops.md](ops.md) |
| P-601 | 兩處事項 | [ops.md](ops.md) |
| P-603 | aos-attend：列出、查看、標完成 | [ops.md](ops.md) |
| P-605 | aos-clean 的 argv 與設定 | [ops.md](ops.md) |
| P-606 | 清理、封存與回報 | [ops.md](ops.md) |
| P-607 | schema 與最小範例 | [ops.md](ops.md) |
| P-608 | 待決與跨篇 | [ops.md](ops.md) |
| P-609 | 最小設定錯誤與修好後重驗 | [ops.md](ops.md) |
| P-700 | 範圍 | [agent-tasks.md](agent-tasks.md) |
| P-701 | 設定檔 | [agent-tasks.md](agent-tasks.md) |
| P-702 | 工具清單與參數 adapter | [agent-tasks.md](agent-tasks.md) |
| P-703 | 檔案落點 | [agent-tasks.md](agent-tasks.md) |
| P-704 | 一項 module、一項任務 | [agent-tasks.md](agent-tasks.md) |
| P-705 | 收話與收結果 | [agent-tasks.md](agent-tasks.md) |
| P-706 | 組 context 與發 LLM | [agent-tasks.md](agent-tasks.md) |
| P-707 | 模型決定與兩種工具路線 | [agent-tasks.md](agent-tasks.md) |
| P-708 | 正式回覆 | [agent-tasks.md](agent-tasks.md) |
| P-709 | 投件故障與恢復 | [agent-tasks.md](agent-tasks.md) |
| P-710 | agent 自記用量 | [agent-tasks.md](agent-tasks.md) |
| P-711 | 工具清單 CLI | [agent-tasks.md](agent-tasks.md) |
| P-712 | 設定檢查與重驗 | [agent-tasks.md](agent-tasks.md) |
| P-713 | say／listen | [agent-tasks.md](agent-tasks.md) |
| P-714 | replies／context | [agent-tasks.md](agent-tasks.md) |
| P-715 | new 的完整產物 | [agent-tasks.md](agent-tasks.md) |
| P-716 | 最小清理遍歷 | [agent-tasks.md](agent-tasks.md) |
| P-717 | 格式驗收 | [agent-tasks.md](agent-tasks.md) |
| P-800 | 共同契約 | [kernel-tasks.md](kernel-tasks.md) |
| P-801 | 設定與持久成員 | [kernel-tasks.md](kernel-tasks.md) |
| P-802 | 增刪成員與按需同步 | [kernel-tasks.md](kernel-tasks.md) |
| P-803 | 何時叫醒 | [kernel-tasks.md](kernel-tasks.md) |
| P-804 | 分配與量測 | [kernel-tasks.md](kernel-tasks.md) |
| P-805 | 壞設定與重驗 | [kernel-tasks.md](kernel-tasks.md) |
| P-806 | 工具 once module | [kernel-tasks.md](kernel-tasks.md) |
| P-807 | 中斷與恢復 | [kernel-tasks.md](kernel-tasks.md) |
| P-808 | LLM 路由表 | [kernel-tasks.md](kernel-tasks.md) |
| P-809 | LLM 轉交 module | [kernel-tasks.md](kernel-tasks.md) |
| P-810 | 用量收集 module | [kernel-tasks.md](kernel-tasks.md) |
| P-811 | 池與共享窗口 | [kernel-tasks.md](kernel-tasks.md) |
| P-812 | 唯讀查詢 | [kernel-tasks.md](kernel-tasks.md) |
| P-813 | 建立 agent 的兩條路 | [kernel-tasks.md](kernel-tasks.md) |
| P-814 | 完整範本與走查 | [kernel-tasks.md](kernel-tasks.md) |
| P-815 | 格式驗收 | [kernel-tasks.md](kernel-tasks.md) |
