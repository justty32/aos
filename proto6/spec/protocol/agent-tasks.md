# agent 預設任務：收話、想、用工具、回話

← [協議入口](README.md)｜[agent 行為](../agent/README.md)｜[CLI 走查](../cli.md)｜[全部裁定](../../notes/2026-09-29-verdicts.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - `aos-as`（任務自己換帳號）：第十三批暫緩（[P-212](../settled/deferred/protocol/tick/01-P-207加入設定與P-212切換帳號.md#p-212aos-as切換帳號建議預設未拍板)）；現行切帳號只在 daemon 設定檔做（帳號模組 [B-646](../settled/daemon/account.md)）。
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit/08-1001-node模組與統一更新.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

## P-700．範圍〔第十二批裁定；工程預設〕

`aos-agent-step` 推進 module；`aos-agent-tools` 管工具、`aos-agent-check` 查設定、`aos-agent-talk` 說話與查詢。tick 不等 HTTP／工具。各程式沿 [P-203](../settled/protocol/tick.md) 使用 node 的 user 與鎖；--node 省略用 cwd，任務直接讀設定。

LLM 送到 `llm.target_node`；工具由 `tools.target_node` 決定交 kernel，或自己經通道掛 once（`node.mount`，[B-613](../settled/deferred/daemon/channel.md)）。kernel 建立 agent 時決定地址、權限與資源路線，agent 不辨識對方角色。

## P-701．設定檔〔A-101～102；工程預設〕

[agent-config schema](schemas/agent-config.schema.json) 定 `config/agent.json`：

| 欄位 | 意思 |
|---|---|
| `version:1` | 格式版本 |
| `llm.target_node` | 接收 LLM 請求的 node id；null＝「直連」檔，agent 自己打 endpoint，endpoint 與 key 放哪由 agent 自己定（[S-301](../scheduling/llm.md)，之後再做） |
| `llm.pool`、`llm.model` | 對方解讀的池與模型；`llm.pool` 只在 `target_node` 是 node id 時必填，直連（null）時不需要填（[正例](examples/agent-tasks/agent-config.direct.valid.json)、[反例：有目標卻缺 pool](examples/agent-tasks/agent-config.no-pool.invalid.json)） |
| `llm.context_tokens` | 模型 context 上限，須大於輸出預留 |
| `llm.max_completion_tokens`、`llm.timeout_ms` | 輸出預留與呼叫逾時，正整數 |
| `system_prompt` | system 文字，可空 |
| `tools_file` | 固定 `config/tools.json` |
| `tools.target_node` | node id＝交該 kernel；null＝agent 自己經通道掛 once |
| `daemon_socket` | 可省；daemon IPC socket 絕對路徑，省略就讀環境變數 `AOS_DAEMON_SOCKET`（[P-117](../settled/deferred/protocol/daemon/channel.md)）。只有 agent 由人手或 cron 跑、又想連 daemon 時才需要寫 |

設定不含 key／endpoint／user。驗地址、回件權限及工具；模型由目標驗，不探測 HTTP。〔使用者方向 2026-09-29，第十六批〕**對 LLM 池（`llm.target_node`）有沒有投件權，設定檢查不先擋**：沒權限就在投件那一步報 `target_not_writable`、丟掉待送檔（[B-624](../settled/deferred/mq.md)、[S-301](../scheduling/llm.md)）。設定無效就在 `.aos/attention/open/` 記事項、停相關新工作，仍收已派工作的結果；修好後讀目前檔案重驗。`state/agent/config-state.json`（[schema](schemas/agent-config-state.schema.json)）的 `issue` 記未解問題，不保存設定快照。

改設定的方式與「任務不改 `config/`」這條軟性原則，以 [A-102](../agent/configuration.md) 為準。

## P-702．工具清單與參數 adapter〔A-401～403；工程預設〕

[agent-tools](schemas/agent-tools.schema.json) 是 `{version:1,tools:[...]}`，空清單可用。每項含 `name,description,parameters,argv,cwd,result,timeout_ms,output_limit_bytes`；名稱唯一。parameters 是 JSON Schema 2020-12，根資料是 object，不用外部引用；〔使用者方向 2026-09-29 晚〕執行期驗參數可用第三方 `jsonschema`，這是「Python 只用標準庫」的唯一例外；`result.kind` 為 text 或 json，後者必填 `result.schema`。

arguments 存 `state/work/<attempt_id>/input.json`，以絕對路徑作 inst.stdin；argv 直接 exec、不插值，cwd 沿工具設定、base 是發起 node。stdout／stderr 由 runner 捕獲；不吃 JSON stdin 的程式另接普通 adapter。模型只看到 name、description、parameters。

派出時將工具定義存 `state/work/<attempt_id>/tool.json`，另存參數，結果按那份定義解讀，不因設定改動換 schema。文字驗 UTF-8；JSON 驗完整 stdout。截斷、缺失、非零退出照實呈現，格式錯不改原程序證據、不自動重跑。

## P-703．檔案落點〔A-201、A-203、A-301；工程預設〕

以下都追蹤。根下 requests／responses 是 ignored 收件；work 只放暫存進度，public 是共用空間，`.aos/jobs/` 是 ignored 的 once 工作區。

| 路徑 | 用途 |
|---|---|
| `state/messages/requests/<id>.json`、`state/messages/responses/<id>.json` | 已消費的完整 RPC 原 bytes，供 tick 核對後刪原件 |
| `.aos/outbox/requests/<id>.json`、`.aos/outbox/responses/<id>.json` | [P-206](../settled/protocol/tick.md) 待送封套，tick 提交後投件 |
| `state/messages/meta/<id>.json` | [agent-request](schemas/agent-request.schema.json)，目標與配對 |
| `state/agent/inputs/<input_id>.json` | [agent-input](schemas/agent-input.schema.json)，回址／seq／狀態／待收 ID |
| `state/agent/history/<event_id>.json` | [agent-history](schemas/agent-history.schema.json)，每事件一檔 |

工作與輸出：

| 路徑 | 用途 |
|---|---|
| `state/work/<attempt_id>/request.json`、`response.json`、`meta.json`、`input.json` | 工作請求、結果、配對及參數 |
| `state/agent/contexts/<request_id>.json` | [agent-context](schemas/agent-context.schema.json)，來源與估算；messages／tools 沿 request_path 讀 |
| `state/agent/replies/<reply_id>.json` | [agent-reply](schemas/agent-reply.schema.json)，本地 progress／final |
| `state/agent/usage/<request_id>.json` | [agent-usage](schemas/agent-usage.schema.json)，LLM 或自跑工具用量 |
| `state/agent/sequence.json`、`config-state.json` | 序號與設定診斷 |
| `.aos/summary/summary.json` | P-307 摘要；tick 提交後發布 ignored `published.json` 供上層讀（〔暫緩（2026-10-01）〕發布的 `aos-publish` 在[暫緩區](../settled/deferred/tick/03-B-624與B-621.md#暫緩b-624-發布摘要aos-publish)） |

序號在鎖內遞增、同組提交，首次從 0 開始；不靠牆鐘排輸入，清理不倒退序號。input_id 是原 `agent.say` RPC id；工具自用 LLM 可為 null。request／job／attempt 配自己的 ID，模型 call ID 不作檔名。派出時保存的請求與工具定義就是執行依據。

## P-704．一項 module、一項任務〔第十二批裁定；工程預設〕

行為（每格做什麼、一格處理幾件）以 [agent 預設任務](../agent/README.md)、[A-201](../agent/input.md) 為準，本條只留介面。完整 argv 是 `aos-agent-step [--node N]`，省略 node 就用 cwd（tick 設為 node 根）；人手入口為 `aos agent task run N`。必須繼承並核對 `AOS_TICK_LOCK_FD`。〔第十九批，使用者方向 10〕〔2026-10-01 任務的 `user` 撤回〕任務要用別的帳號跑就在 argv 包 `aos-as`，由 tick 一直握著鎖、經 helper 的「以指定帳號開程序」動作開它，任務照樣繼承同一個鎖 fd、照樣核對；不經 `node.mount`（[B-620](../settled/tick.md)）。〔第十九批〕手動跑完整一格：`aos node tick N` 經 daemon 跑並等格次，或直接跑 `aos-tick`（風險自負，沒有通道，[B-627](../settled/tick.md)）。

| 任務 id | kind／group／needs | 內容 |
|---|---|---|
| agent | agent／省略／省略 | 收話與結果、推進輸入、準備工作及回覆、記用量與摘要 |
| clean | custom／省略／省略 | `aos-clean --config config/clean.json`，到期才清理 |

[任務表](examples/agent-tasks/agent-tasks.minimal.valid.json) 最外層是 `{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[...]}`；每項是帶 `_metainfo` 的 inst，加 `id`、`kind`。〔使用者方向 2026-09-30，第十九批，撤 C-07 永遠禁止鍵；2026-10-01 撤回任務的 `user`〕任務沒有 `user`，寫了當陌生鍵、[schema](schemas/agent-tasks.schema.json) 不擋（[B-620](../settled/tick.md)）；一般任務的 group、needs、指示詞及整份 `$ref` 沿 P-202。

aos-agent-step 的範本 inst 設 `stderr:{"$opt":"inherit"}`，stdin 不讀、stdout 空、stderr 診斷。0 成功或沒事；2 用法錯；125 鎖或前置不符；1 處理／保存失敗，交標準配備還原組。可保存的 failed／unknown／設定問題是業務狀態；commit／還原故障由標準配備回 3 並停格。clean 的輸出與結束碼依 [P-605](ops.md)。

## P-705．收話與收結果〔A-201、A-403、P-303～305；工程預設〕

行為以 [A-201](../agent/input.md)（含通道收件，收件任務用 `node.take`）與 [A-403](../agent/tools.md) 為準。格式：`agent.say` 的 params 是 inst，argv 對應 `aos agent say`，stdin 指向可讀的輸入 JSON；指令結果沿 work-result，收件確認放指令 stdout。工作結果在指令 stdout 裡的格式見 [work](work.md)／[llm-work](llm-work.md)；已消費的回應存 P-703 的 `state/messages/responses/<id>.json`，配對記在 `state/messages/meta/<id>.json` 與 input 的 `pending_requests`。agent 之間的問答、請求被拒收，延後（[P-008](readme/03-P-007-P-008-schema與待決.md#p-008)）。

## P-706．組 context 與發 LLM〔A-302～303、P-406；工程預設〕

行為（選 input、context 順序、估算與 `context_over_budget`、串流、鬧鐘）以 [A-302](../agent/memory.md) 為準。格式：固定的請求 ID、context、meta、usage 存放見 P-703；`llm.chat` 的 params 是 argv 以 `aos llm chat` 開頭的 inst，stdin 指業務 JSON，送設定的 `llm.target_node`；要串流就在業務 JSON 帶 `stream_path`（[llm-work P-406](llm-work.md)）。範本預設在封套設鬧鐘 `alarm_ms`（格式見 [node P-206](../settled/protocol/tick.md)，預設值延後，[P-008](readme/03-P-007-P-008-schema與待決.md#p-008)），所以 [agent-config](schemas/agent-config.schema.json) 這輪不加欄。

## P-707．模型決定與兩種工具路線〔A-401～403、A-503、P-407；工程預設〕

行為以 [A-401](../agent/tools.md)、[A-503](../agent/README.md) 為準。格式：`tools.target_node` 是 node id 時用 `kernel.work.submit`，params.argv 對應 `aos kernel work submit`，業務 JSON 經 stdin；`null` 時下一格由 agent 經通道用 `node.mount` 掛 `.aos/jobs/<attempt_id>/` 裡的 inst，帶 `token`、省略 `parent_id`（上層就是憑證所屬的 tick）、不帶 `identity_grant`、不另 wake（[P-118](../settled/deferred/protocol/daemon/channel.md)）。兩路都沿 [P-402](work.md)、[P-404](work.md)，結果下格收。

## P-708．正式回覆〔A-203；工程預設〕

行為以 [A-203](../agent/input.md) 為準。格式：reply 的 `input_id` 是原 `agent.say` id，progress 的 `outcome` 為 null，final 為 succeeded／failed／canceled／unknown；回話的 stdin JSON 是 `{text,in_reply_to:原 input_id}`，`reply_to` 是 N，目標是原 input 的回址。

## P-709．投件故障與恢復〔Q1／Q2、P-304；工程預設〕

行為以 [A-403](../agent/tools.md) 為準（補投只補交付、不授權重跑；自跑 once 的掛行程照 [B-613](../settled/deferred/daemon/channel.md)，`launch-started` 與 unknown 照 [S-401](../scheduling/operations.md)、[kernel P-807](kernel-tasks.md)）。

## P-710．agent 自記用量〔工具與 LLM 兩路裁定；工程預設〕

行為以 [A-401](../agent/tools.md) 為準。格式：每筆帶 `kind:llm|tool`；自跑工具的可信量測存 `.aos/jobs/<attempt_id>/usage.json`（res-usage）；來源與欄位沿 [agent-usage](schemas/agent-usage.schema.json)。

## P-711．工具清單 CLI〔Q3、H-001；工程預設〕

```text
aos-agent-tools add [--node N] --from F
aos-agent-tools rm [--node N] NAME
aos-agent-tools ls [--node N] [--json]
# 人手：aos agent tools add N --from F／rm N NAME／ls N [--json]
```

F 是任意可讀路徑的 agent-tools JSON。合併、取鎖與安裝提交的行為以 [A-102](../agent/configuration.md) 為準；rm 的名稱不存在回 1。

stdin 不讀；add/rm stdout 印設定路徑，ls 印名稱／用途或完整 JSON；stderr 診斷。0 成功；2 用法／格式／名稱衝突；75 鎖忙；125 無法開始；1 寫入失敗已還原；3 提交／還原故障。ls 不寫檔，空清單回 0，讀失敗回 1。

## P-712．設定檢查與重驗〔A-102、P-601／603；工程預設〕

```text
aos-agent-check [--node N] [--draft F | --validate-only]
aos-agent-check [--node N] --recheck
# 人手：aos agent config check N [--draft F]／recheck N
```

直接開檔驗 inst／tasks／agent／tools、引用與權限（對 LLM 池的投件權除外，見 P-701），不試 provider。draft 是任意可讀替代 agent.json；validate-only 供 caller 持鎖驗工作樹，不再取鎖、不寫。0 有效、1 無效、2 用法錯、125 讀取／前置失敗；stdout 印 valid 或 invalid 與檔案欄位，stderr 診斷。跟 kernel 設定檢查（P-805，無效也回 0）不一致，要不要統一延後（[P-008](readme/03-P-007-P-008-schema與待決.md#p-008)）。

recheck 的行為（取鎖、驗目前值、記設定狀態、不派工、事項另用 `aos attend done N ID` 標完成）見 [A-102](../agent/configuration.md)。鎖忙 75、保存失敗 1、提交／還原故障 3。

## P-713．say／listen〔對話裁定、proto5；工程預設〕

```text
aos-agent-talk say TEXT [--target N] [--from-node R] [--wait [秒]]
aos-agent-talk listen [--target N] (--last [N] | --wait [秒] | --follow)
                      [--show-calls | --show-calls-full] [--json]
# 人手把 aos-agent-talk 換成 aos agent。
```

target 預設 cwd、R 預設 N；TEXT 非空，wait 預設 300 秒。listen 三種看法互斥，show-calls 亦互斥。say 與 listen 的行為（持鎖提交、投件不 wake、讀哪一份 history、分組、`--wait`／`--follow` 的等法）以 [H-004](../cli/commands.md) 第 35、36 列與 [A-201](../agent/input.md)、[A-203](../agent/input.md) 為準，顯示與截字沿 [proto5 say](../../../proto5/spec/aos-agent/cli-talk.md)／[listen](../../../proto5/spec/aos-agent/cli-listen.md)。

用呼叫者權限，stdin 不讀、stderr 診斷。0 成功（final/failed 也表示收到回話）；2 用法；125 前置；1 讀／投失敗；75 鎖忙；3 提交／還原故障。等待逾時或確知卡住回 101，保留已提交訊息、提醒不要重說。

## P-714．replies／context〔A-203、A-302；工程預設〕

```text
aos-agent-talk replies N [--input ID] [--json]
aos-agent-talk context show N --request ID [--json]
# 人手：aos agent replies N …／aos agent context show N …
```

不寫檔、不開 tick。有 git 時只讀同一 commit；〔第十九批，[B-632](../settled/deferred/git.md)〕沒有 git 時讀目前檔案與已完成的紀錄（reply、context 檔各自是完整寫入後才 rename，不會讀到半份），**不保證是一致快照**，同一次查詢內 replies 與 context 可能來自相鄰兩格。replies 按 seq 篩 input_id，文字印 kind／outcome／text，JSON 每筆原 reply 一行；context 顯示來源、估算及真正 messages／tools，缺引用就報錯、不重組。0 查到；2 用法錯；125 前置失敗；1 無資料／損壞；診斷 stderr。

## P-715．new 的完整產物〔[inst 目標](../base/inst.md#inst-目標檔案或資料夾)；工程預設〕

`aos node new N --template agent --agent-config F` 讀 F、填 N，建 repo 與初始 commit；無效回 2，不猜地址或授額外權限。持久登記由 kernel 做。

[完整產物](examples/agent-tasks/agent-template.minimal.valid.json) 的 files 列 `.aos/inst.json`、`.aos/tasks.json`（**2 項**）、agent.json、空 tools.json、clean.json、gitignore；〔第十八批〕範本的 agent 任務對每個送出的請求預設帶鬧鐘（P-706），預設值延後、這輪不加設定欄；不把 template 容器存進 node。另建 requests、responses、work、public、`.aos/jobs/` 與 ignored `.aos/attention/{open,done}/`；state／summary 按需建立。[cat 工具清單](examples/agent-tasks/agent-tools.minimal.valid.json) 可從任意可讀路徑 add。

## P-716．最小清理遍歷〔B-404、P-605～606；工程預設〕

行為（遍歷什麼、何時整組封存、只記錄的訊息、壞收件原件、unknown 到期）以 [A-304](../agent/memory.md) 與 [B-404](../base/storage.md) 為準；格式見 P-605～606。

## P-717．格式驗收〔P-007〕

[範例](examples/agent-tasks/) 依同名前綴驗 schema；template 另核對 node、argv、路徑。〔第十八批〕agent 的 schema 都已放寬：不認得的欄位照收，不再有「多一個欄位」的反例，改由[正例](examples/agent-tasks/agent-config.extra-field.valid.json)示範多一個欄位仍收（[C-07](../contracts.md)、[P-007](README.md)）。〔第十九批〕任務表的 `user` 不再是禁止鍵；〔2026-10-01〕任務的 `user` 撤回，原本的正例刪掉（[B-620](../settled/tick.md)）；`daemon_socket` 可省，最小設定範例就不寫。反例涵蓋相對地址、工具結果缺 schema、done 缺時間、history 越界、final 缺 outcome、負估算、缺 attempt、用量狀態矛盾、錯 commit、負序號、template 缺任務表。線上 agent.say 回話例子見 messages。

正例全過、反例全拒；`bash wf/tools/wf-lint.sh proto6` broken=0。格式驗證不代替權限、狀態配對與端到端循環驗收。
