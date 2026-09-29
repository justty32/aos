# agent 預設任務：收話、想、用工具、回話

← [協議入口](README.md)｜[agent 行為](../agent/README.md)｜[CLI 走查](../cli.md)｜[全部裁定](../../notes/2026-09-29-verdicts.md)

## P-700．範圍〔第十二批裁定；工程預設〕

`aos-agent-step` 推進 module；`aos-agent-tools` 管工具、`aos-agent-check` 查設定、`aos-agent-talk` 說話與查詢。tick 不等 HTTP／工具。各程式沿 [P-203](node.md) 使用 node 的 user 與鎖；--node 省略用 cwd，任務直接讀設定。

LLM 送到 `llm.target_node`；工具由 `tools.target_node` 決定交 kernel 或自己登記 once。kernel 建立 agent 時決定地址、權限與資源路線，agent 不辨識對方角色。

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
| `tools.target_node` | node id＝交該 kernel；null＝agent 自己登記 once |
| `daemon_socket` | daemon IPC socket 絕對路徑，登記 once 用 |

設定不含 key／endpoint／user。驗地址、回件權限及工具；模型由目標驗，不探測 HTTP。設定無效就在 `.aos/attention/open/` 記事項、停相關新工作，仍收已派工作的結果；修好後讀目前檔案重驗。`state/agent/config-state.json`（[schema](schemas/agent-config-state.schema.json)）的 `issue` 記未解問題，不保存設定快照。

改設定在 tick 外用持同把鎖的指令；重要手改先 pause、等全空，驗證並提交後 resume。任務不改 `config/` 是軟性原則，不檢查、不阻擋；自行改的人承擔同格新舊設定混用。

## P-702．工具清單與參數 adapter〔A-401～403；工程預設〕

[agent-tools](schemas/agent-tools.schema.json) 是 `{version:1,tools:[...]}`，空清單可用。每項含 `name,description,parameters,argv,cwd,result,timeout_ms,output_limit_bytes`；名稱唯一。parameters 是 JSON Schema 2020-12，根資料是 object，不用外部引用；〔使用者方向 2026-09-29 晚〕執行期驗參數可用第三方 `jsonschema`，這是「Python 只用標準庫」的唯一例外；`result.kind` 為 text 或 json，後者必填 `result.schema`。

arguments 存 `state/work/<attempt_id>/input.json`，以絕對路徑作 inst.stdin；argv 直接 exec、不插值，cwd 沿工具設定、base 是發起 node。工具 inst 不填 user，stdout／stderr 由 runner 捕獲；不吃 JSON stdin 的程式另接普通 adapter。模型只看到 name、description、parameters。

派出時將工具定義存 `state/work/<attempt_id>/tool.json`，另存參數，結果按那份定義解讀，不因設定改動換 schema。文字驗 UTF-8；JSON 驗完整 stdout。截斷、缺失、非零退出照實呈現，格式錯不改原程序證據、不自動重跑。

## P-703．檔案落點〔A-201、A-203、A-301；工程預設〕

以下都追蹤。根下 requests／responses 是 ignored 收件；work 只放暫存進度，public 是共用空間，`.aos/jobs/` 是 ignored once 工作區。

| 路徑 | 用途 |
|---|---|
| `state/messages/requests/<id>.json`、`state/messages/responses/<id>.json` | 已消費的完整 RPC 原 bytes，供 tick 核對後刪原件 |
| `.aos/outbox/requests/<id>.json`、`.aos/outbox/responses/<id>.json` | [P-206](node.md) 待送封套，tick 提交後投件 |
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
| `.aos/summary/summary.json` | P-307 摘要；tick 提交後發布 ignored `published.json` 供上層讀 |

序號在鎖內遞增、同組提交，首次從 0 開始；不靠牆鐘排輸入，清理不倒退序號。input_id 是原 `agent.say` RPC id；工具自用 LLM 可為 null。request／job／attempt 配自己的 ID，模型 call ID 不作檔名。派出時保存的請求與工具定義就是執行依據。

## P-704．一項 module、一項任務〔第十二批裁定；工程預設〕

完整 argv 是 `aos-agent-step [--node N]`，省略 node 就用 cwd（tick 設為 node 根）；人手入口為 `aos agent task run N`。必須繼承並核對 `AOS_TICK_LOCK_FD`；手動跑完整一格用 `aos node tick N`。

| 任務 id | kind／group／needs | 內容 |
|---|---|---|
| agent | agent／省略／省略 | 收話與結果、推進輸入、準備工作及回覆、記用量與摘要 |
| clean | custom／省略／省略 | `aos-clean --config config/clean.json`，到期才清理 |

[任務表](examples/agent-tasks/agent-tasks.minimal.valid.json) 最外層是 `{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[...]}`；每項是帶 `_metainfo` 的 inst，加 `id`、`kind`，不填 user。一般任務的 group、needs、指示詞及整份 `$ref` 沿 P-202。

module 只把請求／回應放 `.aos/outbox/`，把已消費原件複製到 P-703；tick 在組提交成功後投件、刪相符原件。每格只列一次收件清單，最多處理 64 件；同格回件等下格。還有可推進輸入則 summary.ready=true；只等結果則 false，無到期事務時 due_ms=null。

aos-agent-step 的範本 inst 設 `stderr:{"$opt":"inherit"}`，stdin 不讀、stdout 空、stderr 診斷。0 成功或沒事；2 用法錯；125 鎖或前置不符；1 處理／保存失敗，交 tick 還原組。可保存的 failed／unknown／設定問題是業務狀態；commit／還原故障由 tick 回 3 並停格。clean 的輸出與結束碼依 [P-605](ops.md)。

## P-705．收話與收結果〔A-201、A-403、P-303～305；工程預設〕

`agent.say` 的 params 是 inst，argv 對應 `aos agent say`，stdin 指向可讀的輸入 JSON。接件後保存回址、原文與附件引用，建 queued input 及 user history；可省的 `in_reply_to` 原樣存 history，回話也照此處理。指令結果沿 work-result，收件確認放指令 stdout。附件先只保存引用，要內容就用普通讀檔工具。

結果先核對 RPC id、可信來源及原請求，再保存與套入 history／決定；同 bytes 不重吃。工作結果在指令 stdout 裡按 [work](work.md)／[llm-work](llm-work.md) 解讀，不能把外層指令成功當成工具／LLM 成功。套用後才記 response_consumed、移除 pending；一批工具全齊才處理。

RPC 收件確認只更新發件 meta，不觸發另一則回話；回話本身仍是普通 agent.say。

## P-706．組 context 與發 LLM〔A-302～303、P-406；工程預設〕

每次選一筆可推進 input，略過等待／阻擋者；每筆最多一個模型請求，一批工具全回才問下一次。context 依序是 system_prompt、原 user（含附件路徑）、本 input 的 assistant／tool／修補說明；依 seq 且呼叫成對，不自動摘要或混其他 input。

工具預覽合計最多 64 KiB，標原引用與截短／缺失。`utf8_bytes_upper_bound` 是 messages／tools JSON UTF-8 bytes＋每 message 32 的估算，不保證 tokenizer 上界。加輸出預留超 context_tokens、或 RPC 超 256 KiB，就報 context_over_budget、不送。

固定請求 ID、context、meta、usage；`llm.chat` 的 params 是 argv 以 `aos llm chat` 開頭的 inst，stdin 指業務 JSON，送設定的 target_node。tick 提交後投，後格收結果。〔使用者方向 2026-09-29 晚〕要串流就在業務 JSON 帶 `stream_path`（[llm-work P-406](llm-work.md)）；檔案放哪、權限怎麼開、要不要自己盯著它，由 agent 決定，aos 不叫醒。target_node 不是 node 時投件那一步報錯、不重試；要知道對方有沒有處理，可在封套設鬧鐘 `alarm_ms`（[node P-206](node.md)）。

## P-707．模型決定與兩種工具路線〔A-401～403、A-503、P-407；工程預設〕

只解讀已收結果。最後一次 LLM succeeded、finish_reason=stop、無 tool_calls、content 非空，且沒有未結／unknown 工作，才準備成功 final。

有 tool_calls 時先驗整批名稱、唯一 call ID、arguments object 與派出時保存的工具 schema。有一項無效就整批不派，各 call 留未派原因，保持呼叫與結果成對。invalid_count 加一；第一次可問一次修補，連續第二次 needs_attention。重號等無法配對時，原文留 response，以 developer 事件記錯。合法決定歸零；length／空回覆／未知 finish_reason 也最多修補一次。

合法工具按 calls 順序建材料：

- `tools.target_node` 是 node id：用 `kernel.work.submit`，params.argv 對應 `aos kernel work submit`，業務 JSON 經 stdin，交 tick 投到該 kernel。
- `tools.target_node=null`：agent 先提交工作材料，下一格以自己的可信 parent_id 向 daemon 登記 `.aos/jobs/<attempt_id>/` 裡的 once、wake，自己記用量；kernel 用用量收集 module 讀。

兩路都沿 P-402／P-404，結果下格收，不讓工具自選資源歸屬。模型文字可作 progress，無字則寫正在用哪些工具。工具全回後按 calls 順序寫結果、預覽及引用，再問 LLM；確定失敗可交模型判斷，unknown 停新副作用並記事項，不因改設定重跑。

## P-708．正式回覆〔A-203；工程預設〕

reply.input_id 是原 `agent.say` id；progress.outcome=null，final 為 succeeded／failed／canceled／unknown。unknown 回話只說結果不明，原工作仍保持 unknown；取消須完成本機收尾。

同組保存本地 reply、input 與新 ID 的 `agent.say` 請求；stdin JSON 為 `{text,in_reply_to:原 input_id}`，reply_to=N，目標是原 input.reply_to。本地 progress／final 不另變成線上欄位。tick 提交後投件；自己回自己也下格收。原 `agent.say` 回應不改。

有終局回話才把 input 記 done、填 completed_at_ms。模型原話不重存 history；程式產生的進度／失敗另建 assistant 事件，source_path 指 reply。pending_requests 只記 LLM／工具結果，回話交付另記 meta；本地已提交 final 可查，不表示對方已接納。

## P-709．投件故障與恢復〔Q1／Q2、P-304；工程預設〕

投件與清原件都由 tick 依 P-206 做。可以補投同 ID、同 bytes 的待送訊息；這只補交付，不授權重跑工具／LLM。已提交證據保留時，同 ID 不重消費；撞名不同內容留事項、不覆蓋。

自跑 once 沿 kernel P-807：已提交材料且 `.aos/jobs/<attempt_id>/launch-started` 不存在，先原子排他建立這個 ignored marker、同步檔案與父目錄，再首次 register／wake；有 marker 則只核對可信登記、last_tick、完整結果與 `<inst>.err`，仍在途就等。無法確認有結果、仍在途或從未執行，就記 unknown，不因登記消失、逾時或換 boot 自動另開嘗試。

## P-710．agent 自記用量〔工具與 LLM 兩路裁定；工程預設〕

每筆用量帶 `kind:llm|tool`。LLM 請求建立時記 pending，結果改 completed、rejected 或 unknown；每次 HTTP attempt 保留 provider usage，null 不補零。自跑工具由執行器／已裝 module 在 leaf 收尾前保存可信量測到 `.aos/jobs/<attempt_id>/usage.json`（res-usage），agent 下格收；量不到記 null，不信工具自報。工具 target_node 填 agent 自己；來源與欄位沿 [agent-usage](schemas/agent-usage.schema.json)。轉交路線也可留核對資料，但彙總只選轉交或自記一份，不重加。

kernel 讀 agent 已提交用量，以 node／request／attempt 去重，逐筆替換觀測，不把累積數每格再加一次。部署明授用量讀權；摘要可讀不等於能讀用量。工具自用 LLM 仍走同一地址與協議，不信 stdout 自報用量。

## P-711．工具清單 CLI〔Q3、H-001；工程預設〕

```text
aos-agent-tools add [--node N] --from F
aos-agent-tools rm [--node N] NAME
aos-agent-tools ls [--node N] [--json]
# 人手：aos agent tools add N --from F／rm N NAME／ls N [--json]
```

F 是任意可讀路徑的 agent-tools JSON。add 合併新名，同值無變動、異值拒絕；rm 不存在回 1。兩者在 tick 外取同把鎖，驗 schema／adapter，沿 P-207 安裝並提交 `config/tools.json`。不在 work 裡存設定草稿。

stdin 不讀；add/rm stdout 印設定路徑，ls 印名稱／用途或完整 JSON；stderr 診斷。0 成功；2 用法／格式／名稱衝突；75 鎖忙；125 無法開始；1 寫入失敗已還原；3 提交／還原故障。ls 不寫檔，空清單回 0，讀失敗回 1。

## P-712．設定檢查與重驗〔A-102、P-601／603；工程預設〕

```text
aos-agent-check [--node N] [--draft F | --validate-only]
aos-agent-check [--node N] --recheck
# 人手：aos agent config check N [--draft F]／recheck N
```

直接開檔驗 inst／tasks／agent／tools、引用與權限，不試 provider。draft 是任意可讀替代 agent.json；validate-only 供 caller 持鎖驗工作樹，不再取鎖、不寫。0 有效、1 無效、2 用法錯、125 讀取／前置失敗；stdout 印 valid 或 invalid 與檔案欄位，stderr 診斷。

recheck 取同把鎖、驗目前值並提交 config-state，不派工。確認修好後，人或 agent 用 `aos attend done N ID` 標完成。鎖忙 75、保存失敗 1、提交／還原故障 3。

## P-713．say／listen〔對話裁定、proto5；工程預設〕

```text
aos-agent-talk say TEXT [--target N] [--from-node R] [--wait [秒]]
aos-agent-talk listen [--target N] (--last [N] | --wait [秒] | --follow)
                      [--show-calls | --show-calls-full] [--json]
# 人手把 aos-agent-talk 換成 aos agent。
```

target 預設 cwd、R 預設 N；TEXT 非空，wait 預設 300 秒。listen 三種看法互斥，show-calls 亦互斥。顯示與截字沿 [proto5 say](../../../proto5/spec/aos-agent/cli-talk.md)／[listen](../../../proto5/spec/aos-agent/cli-listen.md)，以下差異優先。

say 取 R 鎖、提交 `agent.say` 原件與待送封套，再沿 tick 的交付規則投 N；只有投件權者明給 R。未登記／暫停也能投，印投件位置，不自行 wake。listen 從同一 commit 的 history 按 seq 查，本地依 input_id、收到的回話依 `in_reply_to` 對原句 id 分組，JSON 每筆 message 一行；last 預設 1。wait／follow 每 200 ms 看新 commit，follow 印新回話並 flush，Ctrl-C 回 0。say wait 讀 target 本地 replies，只認本次 input_id 的 final；只有投件權不保證能等到。

用呼叫者權限，stdin 不讀、stderr 診斷。0 成功（final/failed 也表示收到回話）；2 用法；125 前置；1 讀／投失敗；75 鎖忙；3 提交／還原故障。等待逾時或確知卡住回 101，保留已提交訊息、提醒不要重說。

## P-714．replies／context〔A-203、A-302；工程預設〕

```text
aos-agent-talk replies N [--input ID] [--json]
aos-agent-talk context show N --request ID [--json]
# 人手：aos agent replies N …／aos agent context show N …
```

只讀同一 commit，不寫檔、不開 tick。replies 按 seq 篩 input_id，文字印 kind／outcome／text，JSON 每筆原 reply 一行；context 顯示來源、估算及真正 messages／tools，缺引用就報錯、不重組。0 查到；2 用法錯；125 前置失敗；1 無資料／損壞；診斷 stderr。

## P-715．new 的完整產物〔P-010；工程預設〕

`aos node new N --template agent --agent-config F [--user U]` 讀 F、填 N／已授權 U，建 repo 與初始 commit；無效回 2，不猜地址或授額外權限。持久登記由 kernel 做。

[完整產物](examples/agent-tasks/agent-template.minimal.valid.json) 的 files 列 `.aos/inst.json`、`.aos/tasks.json`（**2 項**）、agent.json、空 tools.json、clean.json、gitignore；不把 template 容器存進 node。另建 requests、responses、work、public、`.aos/jobs/` 與 ignored `.aos/attention/{open,done}/`；state／summary 按需建立。[cat 工具清單](examples/agent-tasks/agent-tools.minimal.valid.json) 可從任意可讀路徑 add。

## P-716．最小清理遍歷〔B-404、P-605～606；工程預設〕

aos-clean 以 input_id 追原 `agent.say`、history、context、work、本地 reply、送回的 agent.say 與 usage。一般 input 要 done、超過保留期、結果全消費、回話全確認、收件已清且無組外引用才整組封存。

unknown 依 P-606 到期連同卡住的 input、pending 與內部引用整組清，不等 input 變 done。序號及在用設定保留；不認得的資料不碰、不回報。

## P-717．格式驗收〔P-007〕

[範例](examples/agent-tasks/) 依同名前綴驗 schema；template 另核對 node、argv、路徑。反例涵蓋相對地址、工具結果缺 schema、done 缺時間、history 越界、final 缺 outcome、負估算、缺 attempt、用量狀態矛盾、錯 commit、負序號、task 自設 user、template 缺任務表。線上 agent.say 回話例子見 messages。

正例全過、反例全拒；`bash wf/tools/wf-lint.sh proto6` broken=0。格式驗證不代替權限、狀態配對與端到端循環驗收。
