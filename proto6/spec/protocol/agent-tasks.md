# agent 預設任務：收話、想、用工具、回話

← [協議入口](README.md)｜[agent 行為](../agent/README.md)｜[CLI 走查](../cli.md)｜[全部裁定](../../notes/2026-09-29-verdicts.md)

## P-700．範圍〔使用者方向 2026-09-29；工程形狀為建議預設〕

四支普通程式：`aos-agent-step` 推進各階段、`aos-agent-tools` 管工具、`aos-agent-check` 查設定、`aos-agent-talk` 說話與查詢。工具用 [work](work.md) 的 once，tick 不等 HTTP／工具。全部沿 [P-203](node.md) 用 node 的 user、cwd、快照及鎖。

LLM 地址是 `config/agent.json` 的 `llm.target_node`。kernel 建立 agent 時決定路線與權限，agent 不辨識對方角色。轉交、用量收集、持久成員與重建屬 kernel 包。

**驗收：**同一份 agent 任務表，換地址與部署權限即可走兩種路線；沒有第二種 LLM RPC。

## P-701．設定檔〔A-101～102、最新 LLM 地址裁定；建議預設〕

[agent-config schema](schemas/agent-config.schema.json) 定 `config/agent.json`，必填：

| 欄位 | 白話意思 |
|---|---|
| `version:1` | 資料格式版本 |
| `llm.target_node` | 請求要投哪個 node，不是 URL 或 收件區 路徑 |
| `llm.pool`、`llm.model` | 交給該地址解讀的池名、模型名；轉交的對應由 kernel 管 |
| `llm.context_tokens` | 模型總 context 上限，正整數 |
| `llm.max_completion_tokens`、`llm.timeout_ms` | 預留輸出及一次模型呼叫逾時，正整數 |
| `system_prompt` | system 文字，可空；不是檔案路徑 |
| `tools_file` | 首版固定 `config/tools.json` |
| `work_target` | 普通工具 work.submit 的所屬 kernel 地址 |
| `attention_dir` | 本 node 有寫權的共同事項資料夾絕對路徑 |

不含 key／endpoint／user。context_tokens 須大於輸出預留；驗地址、回件權限及工具，模型由目標驗，不探測 HTTP。

重要設定先 pause、全空後持鎖手改、驗證／確認 commit，再 resume。每格從 `AOS_CONFIG_COMMIT` 讀定 agent／tools 設定。`state/agent/config-state.json` 用 [agent-config-state](schemas/agent-config-state.schema.json)，只記最後有效的 `valid_commit`（沒有是 null）及當前 config_invalid 的 `issue`（無則 null）；該 commit 的兩份設定保留到沒有工作引用。

無效更新沿舊組、發事項；無舊組停止新工作，仍收結果。重驗須用目前值。attention_dir 壞掉用舊落點；初次也無效則 stderr 報錯。

**驗收：**更改 model 不影響已派請求；壞引用產生事項，下一格不採半份設定。

## P-702．工具清單與最小參數 adapter〔A-401～403、Q3；建議預設〕

[agent-tools](schemas/agent-tools.schema.json) 為 `{version:1,tools:[...]}`，空清單可用。每項是 `name,description,parameters,argv,cwd,result,timeout_ms,output_limit_bytes`；名稱唯一。parameters 是可編譯的 JSON Schema 2020-12，根資料須是 object；不准外部引用、本地 `#` 可用；不支援的規則拒絕。`result.kind` 為 text 或 json；json 必填 `result.schema`，text 不帶 schema。

arguments 物件存 `state/work/<attempt_id>/input.json` 作 inst.stdin 絕對路徑；argv 直接 exec、不插值。cwd 沿設定，base 是發起 node；不填 user，stdout／stderr 用 inherit 讓 aos-work 捕獲。不吃 stdin JSON 的既有程式，用清單指定的普通 adapter 接。

模型 tools 只取 name、description、parameters。work.submit 沿 P-401；kernel 固定可讀 stdin bytes。文字驗 UTF-8，JSON 只驗完整 stdout；截斷、缺失、非零退出照實呈現，格式錯不改原程序證據、不自動重跑。

**驗收：**cat 範例收到 stdin 物件、回傳同一 JSON；將整數傳成字串，不產生 once。換工具清單後，舊結果仍照派出時 `config_commit` 的結果 schema 解讀。

## P-703．檔案落點與格式〔A-201、A-203、A-301；建議預設〕

下表皆追蹤；requests／responses／work／public／外部 attention_dir 不還原。核對檔名 ID、不跟 symlink 出界。序號由追蹤的 `state/agent/sequence.json`（[agent-sequence](schemas/agent-sequence.schema.json)）在鎖內遞增，同組提交；首次從 0 開始；不代替 kernel 排隊序號。同批任取次序後保存，不靠時間／檔名，清理不倒退 last_seq。

| 路徑 | 格式與用途 |
|---|---|
| `state/messages/requests/<id>.json`、`responses/<id>.json` | P-206 原 bytes；agent.send、agent.reply、accepted 及錯誤，不包新封套 |
| `state/messages/meta/<id>.json` | 自己送出的 message／reply 的 [agent-request](schemas/agent-request.schema.json)，記目標與配對 |
| `state/agent/inputs/<input_id>.json` | [agent-input](schemas/agent-input.schema.json)：回址／seq／時間／狀態／待收 ID；done 有完成時間 |
| `state/agent/history/<event_id>.json` | [agent-history](schemas/agent-history.schema.json)：seq、input_id、at_ms、source_path、P-406 message；每事件一檔 |

工作與正式輸出（request／result schema 沿 [work](work.md)）：

| 路徑 | 格式與用途 |
|---|---|
| `state/work/<attempt_id>/request.json`、`response.json` | LLM 或工具 RPC 原 bytes |
| `state/work/<attempt_id>/meta.json` | agent-request：目標、配對、設定與交付／消費狀態 |
| `state/work/<attempt_id>/input.json` | arguments 原物件，依工具 parameters 驗 |
| `state/agent/contexts/<request_id>.json` | [agent-context](schemas/agent-context.schema.json)：輸入／設定／來源／估算；messages／tools 在 request_path，不重存 |
| `state/agent/replies/<reply_id>.json` | [agent-reply](schemas/agent-reply.schema.json)：id、input_id、seq、at_ms、kind、text、outcome |
| `state/agent/usage/<request_id>.json` | [agent-usage](schemas/agent-usage.schema.json)：本 agent 的 LLM 用量，見 P-710 |
| `state/agent/config-state.json`、`summary.json` | P-701 設定採用依據、P-307 排程摘要 |

message 的 input_id 填 agent.send id；工具自用 LLM 可為 null，預設循環須配既有 input。request_id 跨目標唯一；attempt／job 配新 ID，模型 call ID 不作檔名。

**驗收：**同文字不同 ID 留兩筆；工具可對回原模型、設定及輸入。

## P-704．四階段程式與任務表〔P-203～206、Q1／Q2；建議預設〕

完整 argv：`aos-agent-step --node N --phase collect|prepare|dispatch|cleanup`。人手對應 `aos agent task run N --phase PHASE`，是同一程式；它只接受由 tick 繼承且核對通過的 `AOS_TICK_LOCK_FD`，手動操作完整一格用 `aos node tick N`。`--node` 必須等於實際鎖的 node；缺 tick 設定快照或鎖回 125。不提供自行 commit 的單階段捷徑。

| phase／任務 id | group／needs | 讀檔 → 寫檔 |
|---|---|---|
| collect／agent-collect | agent-prepare／無 | 本格開始的收件區 普通檔清單、既有請求／meta、設定及 inputs → 原件複製、input、history、response、meta、usage、config-state；不刪收件區 |
| prepare／agent-prepare | agent-prepare／agent-collect | collect 的結果、固定設定、相關 history → context、work request/input/meta、reply／回件 request、usage、input、summary |
| dispatch／agent-dispatch | 獨立組／agent-prepare | 已提交請求、回應、meta、summary → 目標 ignored 收件區、public/summary.json；meta.delivery 更新；發布／解除 attention |
| cleanup／agent-cleanup | 獨立組／agent-prepare | 已提交原件與收件區 → 只刪 bytes 相符且已消費的收件區原件；不改追蹤證據 |

前兩項同組，後兩項各自提交。cleanup 不依賴 dispatch。collect 每格只列一次入口清單，本格派出縱使瞬間回件也等下格。每批最多 64 件，剩餘收件區／可推進輸入令 summary.ready=true；等待結果時 false、due_ms=null，無工作 idle，阻擋 needs_attention。

stdin `/dev/null`、stdout 空、stderr `代號: 白話`；無新增環境，沿 P-203。0 本步成功或沒事；2 argv 錯；125 不能開始；1 開始後 I/O／發布／處理失敗。可保存的業務 failed／unknown／設定退回不是程序失敗，記狀態與事項後可回 0；無法保存則回 1，由 tick 還原組。commit／還原故障由 tick 回 3 並停格。沒有任務輸出 JSON 被當成成功證據。

**驗收：**collect 後斷電不丟原件；dispatch 失敗不撤掉已提交請求；收件成功且派送失敗仍能安全清相符原件。

## P-705．收話與收結果〔A-201、A-403、P-303～305；建議預設〕

collect 按 method／原請求分流；自己投自己時，已存 outgoing 原件不等於已消費，須看 input 或接件 accepted 證據。agent.send：固定 reply_to、原文及附件引用，建 input（queued、invalid_count=0、pending_requests=[]）、一個 user history；備好 accepted，與收話一起提交，dispatch 才回件。附件本版只保存引用；context 放原請求附的路徑清單供工具讀，不聲稱曾看過附件 bytes；需要精確內容就用普通讀檔工具，或先在輸入中提供文字。

結果以 RPC id、可信來源、node_id／job_id／attempt_id（含 P-407 重試）對 meta，再存 response；錯誤亦保存，不符留事項。collect 不標 response_consumed；prepare 套進 history／決定才設 true 並移除 pending，一批工具全齊後一起處理。同 bytes 不重吃。

agent.reply 核對原 agent.send、可信來源與 input_id，保存並備 accepted；無配對則留事項，不產生 user／LLM。其 accepted 只更新發件 meta.response_consumed。kernel 收件任務也可採這個分流，不必裝 LLM。

**驗收：**送一次話，收到 accepted、progress、final 各有固定 ID；沒有無限 agent.reply 往返。

## P-706．組 context 與發 LLM〔A-302～303、P-406；建議預設〕

首版每次選一筆可推進 input，略過等待／阻擋者，新話仍可接；不另建 run。每筆同時最多一個模型請求，一批工具全回才問下一次。

context 為 system_prompt → 原 user（含附件路徑）→ 本 input 的 assistant／tool／修補說明，依 seq 且呼叫成對。不自動摘要、不加其他 input／notes；超長報 context_over_budget。工具預覽沿 A-303，合計最多 64 KiB，標原引用、展示截短／原件缺失。

`utf8_bytes_upper_bound` 估算＝messages／tools JSON UTF-8 bytes＋每 message 32，非 tokenizer 精準值或上界保證。加預留輸出超 context_tokens、或 RPC 超 256 KiB 都不送。provider 拒絕照實報，不無限修補。

prepare 固定 ID、config_commit、context、meta、usage；llm.complete 的 reply_to／params.node_id=N。dispatch 投設定地址的 requests/<id>.json，下一格收結果。

**驗收：**context show 可讀當時真正 messages、tools 與來源；超預算沒有投出請求。

## P-707．模型決定、工具派出與下格接續〔A-401～403、A-503、P-407；建議預設〕

prepare 只解讀已由 collect 收到的模型結果，usage 記每次 HTTP 嘗試。最後一項 succeeded 且 finish_reason=stop、無 tool_calls、content 非空，才可準備 final；仍有未結相關工作或 unknown 時不能成功。

有 tool_calls：先把整批名稱、唯一 call ID、arguments JSON object 與該次請求 config_commit 的工具 schema 全部驗完，再準備各工具工作。有一項無效就整批不派，為各 call 留明確的 tool 錯誤文字／未派原因，保持 messages 呼叫與結果成對；invalid_count 加一。重號等無法合法配對時，不把壞 assistant 放回 context；原文留 response，以 developer 事件記錯。第一次可帶錯誤問一次修補；連續第二次停止、needs_attention，不再花 LLM。合法決定歸零；length／空回覆／未知 finish_reason 亦最多修補一次，不作 final。

合法 calls 依序各建 work.submit，記模型／call／工具／input 配對。dispatch 投 work_target，由 kernel 按 P-402 登記、叫醒 once。模型文字可作 progress，無字寫「正在使用工具：…」，outcome=null。

工具全回後按 calls 順序寫 history：結果、預覽及引用，再問 LLM。確定失敗可交模型判斷；unknown 停新副作用、記 needs_attention／progress。LLM 拒收／確定失敗回固定 final/failed；unknown 留 S-401，不藉修設定重試。

**驗收：**兩個工具反序回件也正確配對；程序 0、JSON schema 錯顯示 tool_result_invalid；任何工具 unknown 都擋住成功 final。

## P-708．正式回覆與投回傳訊者〔A-203、D3；建議預設〕

reply 的 input_id 是原 agent.send id；progress.outcome=null，final 為 succeeded／failed／canceled／unknown。後兩種須適用授權及本機收尾，不自動釋放 unknown；正常循環只用進度、成功或確定失敗。

prepare 同組寫 reply、input 及 FileRpcRequest：method=agent.reply、id=reply.id、params=完整 reply（含 version）、reply_to=N，投原 input.reply_to；成功回 accepted。原 agent.send 回應不改；自己回自己也下格收。

有成功 final 才將 input 標 done、填 completed_at_ms；確定失敗／授權結束亦可 done，保留 outcome。模型原話已在 history 就不重複；程式產生的失敗／進度回覆另建 assistant 事件，source_path 指 reply，讓 listen 也看得到。input.pending_requests 只記 LLM／工具尚未消費結果；回話交付另以 message meta 記，done 不代表回話已被對方接納。查 replies 在 reply commit 後立即可見，即使回傳投遞失敗也不消失。

**驗收：**final commit 前查不到；回傳投遞失敗後查得到本地 final，但不能聲稱對方已消費。

## P-709．派送故障與恢復〔Q2、P-304、C-03；建議預設〕

delivery=prepared 不證明沒送，published 只證明完整發布，unknown 表示無法確認。首送僅限本格 prepare 新建、提交且 AOS_CONFIG_COMMIT 尚不存在的請求，本格 needs 必須成功；每 ID 一次，投原 bytes。

舊 prepared 沒可信在途／未送證據就 unknown，哪怕實際當機在提交後、送出前也不猜。published 等結果，不以逾時換 ID。發布後 commit 失敗／組還原同樣處理。證據判準沿 P-304，沒有自動重做 unknown 入口。

固定 RPC 回應／agent.reply 可在原輸入及去重證據仍保留時補投同 bytes，只交付、不重做模型或工具。證據已清、撞名不能比對就報未確認，不覆蓋。cleanup 只刪已提交且 bytes 相符的原件。

**驗收：**在每個 publish 前後、commit 前後中斷，沒有自動多叫一次工具／LLM；已完成回覆只補交原文。

## P-710．agent 自記 LLM 用量〔最新 LLM 路線裁定、S-302～304；建議預設〕

prepare 寫 usage：node_id、request_id、target_node、pool、model、status=pending、attempts=[]。收結果同組改 completed 或 unknown；每項是 attempt_id、status、usage（三種 provider token 數或 null），依 HTTP 次序。以 node／request／attempt 去重。可信拒收記 rejected、空 attempts；unknown 空 attempts 表示沒有證據，不是零。

kernel 固定 commit 讀 usage，同筆替換觀測、不累加每次採樣；pending／unknown 分列，null 不補零。轉交路線也自記供核對；彙總選轉交或自記其中一個來源，不重加。部署須明授 usage 讀權，public summary 權限不代表能讀這些檔。

工具用 LLM 也照同一地址與 Q1/Q2；普通 adapter 在 agent 鎖／group 保存 request/meta/usage，交 collect 核對結果。不信 stdout 自報用量，不另定同步入口。

**驗收：**兩個 HTTP attempts、一次重送回應只記兩項；一項 usage=null 時總量明示不完整。

## P-711．工具清單 CLI〔Q3、H-001；建議預設〕

```text
aos-agent-tools add --node N --from work/F.json
aos-agent-tools rm --node N NAME
aos-agent-tools ls --node N [--json]
# 人手：aos agent tools add N --from work/F.json
#       aos agent tools rm N NAME
#       aos agent tools ls N [--json]
```

from 是 agent-tools 草稿；add 合併新名，同值無變動、異值拒絕；rm 在 ignored work 產生刪項後草稿，不存在回 1。兩者驗 schema／adapter，取鎖、要求乾淨，沿 P-207 安裝／提交 config/tools.json；不巢狀取鎖、不在 tick 內直接呼叫。once 改設定也須協調同把鎖。

stdin 不讀，add/rm stdout 印 `config/tools.json`、ls 印工具名／用途（JSON 為原完整清單）；stderr 診斷。執行者身分、無自訂環境、無 group。0 成功／同值；2 參數／schema／名稱衝突；75 鎖忙；125 不能開始；1 寫入失敗已還原；3 提交或還原故障並擋新格。ls 無結果可回空清單 0，讀取失敗 1，不寫任何檔。

**驗收：**只寫 work 草稿不生效；add 後下一格才採用，已有工具工作繼續用舊版。

## P-712．最小設定檢查與來源解除〔A-102、D4、P-601～604；建議預設〕

```text
aos-agent-check --node N [--draft work/F.json | --validate-only]
aos-agent-check --node N --recheck
# 人手：aos agent config check N [--draft work/F.json]
#       aos agent config recheck N
```

check 唯讀固定 HEAD；draft 替換 agent.json；`--validate-only` 供 resume 在鎖內驗目前工作樹的 inst／tasks／agent／tools，不重取鎖、不寫檔。驗 P-701／702、任務順序、引用／權限；不測 provider 或未裝 module。0 有效、1 無效、2 用法錯、125 前置失敗；stdout `valid <commit>` 或 `invalid <檔案:欄位:原因>`，工作樹模式用 `working-tree` 代 commit；診斷 stderr。

recheck 用呼叫者權限取 N tick 鎖、要求乾淨，驗目前設定、不退舊值，提交 config-state 後才由來源核對並移 config_invalid 到 done。stdin 為 ops-attention 時驗 source_node=N／issue_id；直接使用 /dev/null 時核對 config-state。只解設定，不碰 unknown／派工。鎖忙 75、保存失敗 1、commit／還原故障 3；無 group／新環境，輸出同 check。

safe handler 是 exec argv `["aos-agent-check","--node","/srv/aos/a","--recheck"]`、reason=config_invalid；事項 actions=["recheck"]。collect 亦可驗修復、dispatch 提交後解除；掃自己來源的 open 設定事項重新核對，故 commit 後搬移失敗仍可補做，不因 config-state.issue 已清空而失聯。

第 5 步 bad-agent.json 可指不存在的 target_node。P-207 只擋 JSON 語法錯，schema／領域錯下格退回並發事項。重要設定仍 pause 手改，resume 前 `--validate-only` 不用舊值遮掉錯誤。

**驗收：**壞地址更新有事項且沿舊設定；修好後 recheck 自己確認、commit 才移 done，無一次 LLM 呼叫。

## P-713．say／listen〔最新對話裁定、proto5 cli-talk／cli-listen；建議預設〕

```text
aos-agent-talk say TEXT [--target N] [--from-node R] [--wait [秒]]
aos-agent-talk listen [--target N] (--last [N] | --wait [秒] | --follow)
                      [--show-calls | --show-calls-full] [--json]
# 人手把 aos-agent-talk 換成 aos agent，其餘相同。
```

target 預設 cwd、R 預設 N。TEXT 一個且非空，wait 預設 300 秒；`say --wait "你好"` 合法。listen 三種看法必選且互斥，show-calls 亦互斥。完整解析、回話篩選、呼叫顯示／截字沿 [proto5 say](../../../proto5/spec/aos-agent/cli-talk.md)／[listen](../../../proto5/spec/aos-agent/cli-listen.md)，以下差異優先。

say 取 R 鎖、要求乾淨，提交 agent.send 原件／message meta，再投 N、提交 delivery。預設需 N repo 寫權，只有投件權者明給 R。未登記／暫停也能投，印 `said -> <絕對投件路徑>`；不自行 wake，有可信證據才警告並指 node register／resume。

listen 讀固定 commit 的 history，按 seq；JSON 每筆原 message 一行。last 預設 1，單則無 show-calls 只印原文；多則標頭按 input_id 分組、收話時間取 received_at_ms，stderr 回話時間取 event.at_ms。無回話 1，不足 N 全印並提示。讀取失敗不拿工作檔補。

wait／follow 每 200 ms 讀新 commit。listen wait 等開始 seq 之後的新正式 final；say wait 只認本次 input_id，progress 不結束等待。follow 從現在印每個新 assistant 並 flush，含工具呼叫；暫停仍看、Ctrl-C 回 0，歷史縮短重設游標、不重播。

stdin 不讀、診斷 stderr、無新增環境／group，用呼叫者權限。0 成功；2 用法；125 前置失敗；1 讀取／投遞失敗；75 鎖忙；3 commit／還原故障。wait 逾時／確知卡住回 101，stderr 原因、stdout 已提交狀態；say 加「已投入，不要再說一次」，不撤回／重送。等到 final/failed 也回 0，只表示有回話。

**驗收：**連投同一句兩次，各等自己的 input_id；follow 能看中間呼叫，wait 等正式 final。

## P-714．replies／context〔A-203、A-302、H-027～028；建議預設〕

```text
aos-agent-talk replies N [--input ID] [--json]
aos-agent-talk context show N --request ID [--json]
# 人手：aos agent replies N …／aos agent context show N …
```

用執行者讀權，stdin 不讀、無環境／group、不寫檔、不開 tick。replies 固定 commit 讀 P-703 replies，按 seq 排、篩 input_id；文字印 kind、input_id、outcome、text，JSON 原 reply 每筆一行。context 讀同 commit 的 context 及其 request_path，文字印設定版本、來源、估算及真正 messages；JSON 印原 context，實際請求可沿 request_path 讀。缺引用報錯，不重新組一份。

0 查到；2 用法錯；125 不能開始；1 無資料／損壞；診斷 stderr。**驗收：**改 prompt 後查舊 request 仍是舊內容；accepted 與原模型訊息不冒充 final。

## P-715．new 的完整產物〔D2、H-014／036；建議預設〕

`aos node new N --template agent --agent-config F [--user U]` 由 node 建立器讀 F（agent-config），填實際 N／已授權 U，建 repo 與初始 commit。F 缺漏／無效回 2、未建好；不猜地址、不授額外權限。持久登記由 kernel 做。

[完整產物](examples/agent-tasks/agent-template.minimal.valid.json) 由 [agent-template](schemas/agent-template.schema.json) 的 files 列實際內容，不另存 template.json：inst、[tasks](examples/agent-tasks/agent-tasks.minimal.valid.json)、agent.json、空 tools.json、gitignore。另建 ignored requests、responses、work；state 按需建。[cat 清單](examples/agent-tasks/agent-tools.minimal.valid.json) 放 work 再 add。

**驗收：**範本的 tasks 不為空、不含占位程式；空工具清單能回「收到」，加入 cat 可走一次工具往返。

## P-716．最小清理遍歷〔B-404、P-605～606、D4；建議預設〕

aos-clean 的 agent adapter 以 input_id 為組：input → 原 agent.send／accepted → history.source_path → context.history_ids／request_path／config_commit → work request／response／meta／input → replies／agent.reply／accepted → usage。反向查組外引用、保留在用設定；陌生領域不能證明無引用則 clean_blocked。

可清條件同時成立：input done 超過保留期；有正式 final 與 completed_at_ms；所有工作結果已消費、沒有 unknown／待結外部效果；所有回覆有可信 accepted；原收件已清且無衝突；無組外 context／history／目前狀態引用。沒有其他 input 引用時，本組 history 與 context 可一起封存，不因內部互引永遠不能清。usage 未有 kernel 收集的可核對證據時保留，最小版允許整組保留，不冒稱已結算。

沿 P-606 封存／提交；保留期內不清，設定依據、序號及未知問題保留。input_id=null 的工具自用請求首版保留、clean_blocked。無合格項回 unchanged；不回收 git 歷史。

**驗收：**新完成工作 unchanged；30 日後且證據全齊可封存；unknown、未交付回話及仍被下一次 context 引用者保留。

## P-717．驗證與走查接點〔P-007、H-034／036；主編補〕

[examples/agent-tasks/](examples/agent-tasks/) 每個 `agent-X.*.json` 對 `schemas/agent-X.schema.json`；template 另核對 N、argv、路徑，狀態配對及授權是語意驗收。反例原因：config 位址相對；tools 的 JSON 結果漏 schema；input done 漏時間；history 越界；reply final 用 null outcome；context 負估算；request 漏 attempt；usage completed 空 attempts／rejected 卻有 attempt；config-state 用分支名；sequence 負值；tasks 加 user；template 漏 tasks。agent.reply wire 的正反例在 messages 篇。

接通走查 3 的 agent 範本、4 的對話／工具／查詢、5 的重驗、6 的設定檢查、7 的清理證據。daemon／池／成員／重建及 resources 路線由 kernel 包接。cli.md 後續依此換掉「缺」與空 node 例子；本次是規格，非端到端實跑。

**驗收：**正例全過、反例全拒；`bash wf/tools/wf-lint.sh proto6` broken=0。
