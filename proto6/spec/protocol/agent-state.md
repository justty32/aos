# Agent 狀態、tick 與提交協議

← [共用約定與分工](README.md)｜[agent 正本](../agent/README.md)｜[提交契約](../contracts.md)｜[09-29 使用者裁定](../../notes/2026-09-29-verdicts.md)

## P-300．範圍與讀法〔主編補〕

本篇負責控制端交材料給短命 tick、tick 提出一次語意增量，以及設定、內容與掛勾的格式。C-05 是提交語意正本，B-602 是 claim 正本；本文不另造派工表或結果消費者。以下新增欄位、機器子命令與編碼均為〔建議預設，未拍板〕；P-011「09-29 整合者暫定」亦保留這個標記。使用者已定的下一 tick 換版、中央代發、重啟全殺優先。

所有 JSON 沿 P-002：UTF-8、拒絕重複 key、未知欄位與版本、非有限數及尾隨值；byte 限制在解析前檢查。schema 使用 2020-12，只從同目錄解析相對 `$ref`，不連網。ID、BlobRef、Error、Outcome、Run、Job、Attempt 一律引用 `control-common.schema.json#/$defs/...`。以下寫到的 BlobRef 摘要示例只用於格式驗證，不代表內容已導入；整合測試須用真實 bytes 計算摘要與長度。

本文各 JSON 範例的完整檔案在 [examples/agent-state/](examples/agent-state/)；正文內 JSON 是完整物件，沒有省略號。schema 能檢查形狀，不能證明 owner、引用、claim、消費與崩潰恢復正確。

驗收：Given 一筆 schema 合格、但屬另一 agent 的結果，When tick 提交消費，Then 控制端拒絕整份提案，不能把 schema 合格當成授權。

## P-301．控制端如何啟動 tick〔建議預設，未拍板〕

依 A-501、B-602、P-007，控制 writer 取得 claim、固定本 tick 的設定並產生唯讀快照，再由 execution 篇的可信 launcher 降權啟動。機器 argv 固定形狀為：

```json
["aos","tick","--input-fd","3","--commit-fd","4","--blob-fd","5"]
```

三個選項均必填，值為互不相同、已由父程序實際繼承的 fd；上面是標準配置。沒有可省的 path、agent、UID 或 env 替代選項。tick UID/GID、groups、home、資源域由登記決定，cwd 是本次 bundle.cwd。取得 home 獨占鎖及前代 cgroup 清空是控制端啟動前置條件；鎖由可信生命週期持有者保持至整次 tick 與掛勾收尾完成，不能靠 tick stdout 宣稱已解鎖。

| 通道 | 內容與責任 |
|---|---|
| stdin（0） | `/dev/null`；不是使用者輸入，也不是 Proposal。 |
| stdout（1） | 關閉或由 supervisor 收集有界診斷；不解讀成協議結果。 |
| stderr（2） | 有界診斷，沿 B-404 的 64 KiB 上限；不放 key、其他 owner 正文。 |
| input-fd（標準 3） | 父程序開好的普通唯讀快照檔，一份 `agent-tick.schema.json` JSON，從 offset 0 讀到 EOF；不是 DB fd。 |
| commit-fd（標準 4） | 已連線的 Unix stream socket；只承接本 claim 的 `checkpoint.commit`，使用 P-005 的單行 JSON-RPC＋LF。 |
| blob-fd（標準 5） | 已認證、限制為本 owner 的非特權 blob adapter 通道；metadata、fd 傳送與收據沿 storage 篇。 |
| content_fds（標準 6 起） | input 中逐一列出的已繼承普通唯讀檔；role 與 BlobRef 指定內容，不以檔名猜用途。 |

父程序只傳這些白名單 fd；tick 擁有自身 fd 副本，退出或用完即關閉，父程序在交付後關閉不再需要的副本。父程序預先取得的內容 fd，其 storage read_handle_id/pin 映射由可信父程序保存，確認所有副本已關閉或整個接收範圍清空後代送 ReadClose；不是把 pin 塞進 checkpoint。tick 動態經 fd5 取得的 ReadResult 則保留 handle，關閉全部副本後按 storage P-503 送 ReadClose；tick 崩潰由 supervisor 清空證據協助回收，不能靠斷線或 TTL 猜已無讀者。

內容 fd 以唯讀獨立檔案描述取得，不能讓 agent 可寫原件改掉快照。JSON 裡的數字只描述這次真正繼承的 fd，絕不授權開 host path；fd 數字必須唯一；bundle/ledger 各有一份且 ref 分別等於外層 bundle_ref/ledger_snapshot_ref，其他 role 可多份。缺檔、數字重複、非普通檔、可寫 fd 或摘要不符均拒絕。大內容可經 fd5 按 BlobRef 取得，仍須受 owner 與摘要檢查；不把所有歷史一次塞入 fd3。fd5 採 storage 的 SOCK_SEQPACKET＋SCM_RIGHTS，不套 fd4 的 stream/LF framing。

commit 通道由可信父程序綁定 principal、agent、attempt、generation；同 UID 不足以證明 tick 身分，內容自報的 claim 也不算授權。這是縮限的 tick adapter，不把管理控制 socket 傳給工具或掛勾。所有非必要 fd 設 close-on-exec，tick 不直接啟動工具或 HTTP client。

本角色不讀任何 `AOS_*` 環境變數，也不繼承 proto5 的 `AOS_KERNEL_HOME`。環境只沿 B-102 的乾淨集合：PATH、HOME、TMPDIR、LANG；HOME/TMPDIR 由可信登記決定，不可由 bundle 改寫。模型憑證、loader env 與控制 socket 路徑均不傳入。fd 不是環境授權。

exit 0 表示 tick 正常完成本次交換或無提案退出；合法 RPC error 已讀完也可 exit 0。啟動前 argv／fd／輸入不合法 exit 2；自身 I/O、輸出或內部失敗 exit 125。signal 由 wait 狀態判斷。任何退出碼都不能證明 proposal 已提交、run 成功或 claim 可釋放；這些分別查提交收據、帳本與清空證據。tick 沒有 proto5 的 101／102／103 排程退出碼。

驗收：Given fd3 中偽造另一 agent、或 fd4 未綁定 live claim，When 啟動／提交，Then 拒絕而不讀另一 owner 內容；Given RPC 回覆遺失但交易已提交，When tick exit 125，Then 以原收據恢復，不能由退出碼再派一次。

## P-302．Claim、固定設定與唯讀帳本〔建議預設，未拍板〕

控制端 → tick 的根物件由 [agent-tick.schema.json](schemas/agent-tick.schema.json) 定義；claim 使用其 `$defs/Claim`。取得 claim 的交易固定 config_revision 與 bundle_ref，同時處理 A-102 的換版紀錄。claim 的 checkpoint_revision 必須等於 ledger snapshot 的 checkpoint_revision；claim.state 必為 held 才可啟動。run_id=null 只代表維護／空探查，不授權另建隱形任務。

`ledger_snapshot_ref` 指向 `$defs/LedgerSnapshot`：同一 SQLite 快照、單一 owner 的 run/jobs/attempts、checkpoint pointer/revision、pending 集合、輸入／結果交付及消費事實、收件與消費序號、history/output 尾端、phase、wait_reason、due 與預算投影。Run/Job/Attempt 直接引用共用型別；ResultDelivery 只列 version:1、attempt_id 與 consumed，Outcome 從同份 attempts 讀取。phase、pending_job_ids、tail、cursor 都是唯讀投影，不能複製進 checkpoint。

快照內的 inputs 是本 run 已登記交付，sender 由可信入口填入；run 的新訊息歸屬仍沿 S-101 的建議預設，不在這裡定案。input_received_seq 不等於 input_consumed_seq；若已接件但本 run 尚不能消費，不得跳 cursor。所有 pending 工作及本次交付的結果均須可核對；快照量太大時以受管 blob/fd 傳送，不悄悄截短 pending 清單。快照是當時視圖，提交仍以當前帳本重新驗證。

```json
{"version":1,"agent_id":"agent_a","attempt_id":"tick_1","generation":1,"checkpoint_revision":0,"claimed_at_ms":1790000000000,"state":"held"}
```

第一次沒有已提交 checkpoint 時，snapshot.checkpoint_ref=null、revision=0；tick 以 A-502 初始語意值開始。大段內容依 fd 對照或受限 blob adapter 讀取，不對控制庫任意查詢。來源引用缺失／hash 不符依 A-301/B-401 記完整性錯誤並由控制端建立屏障，不能改讀舊版掩蓋。

驗收：Given T1 讀到 revision 8 後控制端接受 pause 或較新事件，When T1 提交，Then pause 屏障使提交衝突；若只是新事件，交易保留新事件並重算 ready，不能因 T1 的快照漏列就刪掉它。Given 前代受管後代仍活著，When deadline 到期，Then 不產生第二個 held claim。

## P-303．Bundle、設定發布材料與換版〔使用者方向 2026-09-29；編碼為建議預設，未拍板〕

管理者用 P-011 暫定的本機發布 adapter，先導入不可變 bundle 及完整引用，控制端驗證成功後原子切換目前 revision；不增公開管理 RPC。普通 owner 自行發布仍延後。機器 argv 為：

```json
["aos","config-publish","--channel-fd","3"]
```

唯一選項必填，fd 是實際繼承的已連線內部 Unix SOCK_SEQPACKET socket；stdin 讀一份 `$defs/PublishRequest` 到 EOF，stdout 寫一份 PublishResult 或 PublishError JSON＋LF，stderr 有界診斷。adapter 以被授權的普通管理者 UID 執行，接收端是控制 writer 的非 root 可信服務。SO_PEERCRED 對照管理授權表；若由管理 launcher 轉交連線，須另外可信綁定真正操作者，不以 JSON 的 agent_id 或 UID 欄位授權。每 packet 一份 JSON、不加 LF、不傳 fd，metadata ≤256 KiB，收包截斷就拒絕；不提供 host path 代開。cwd 無關，沒有 AOS_* 選項，乾淨環境沿 P-007，完成後關閉自己的通道副本。合法 result/error 交換 exit 0，啟動前資料錯 exit 2，未完成交換 exit 125；退出碼不代替發布收據。

PublishRequest 含 version、kind=config_publish、request_id、agent_id、config_revision、bundle_ref 及 bindings。每個 RevisionBinding 是 kind/ref/blob_ref，恰有 model、context_policy、tool_manifest 各一項，ref 必須等於 bundle 中同用途字串。對照表由 writer 持久保存、按 agent 與用途解析，不向未知字串猜路徑；已存在的相同 ref 不得綁到異內容。model blob 解碼為 `$defs/ModelSelection` 的 version/endpoint_id/model，選擇已登記的 endpoint 與邏輯模型，服務端再按 llm-config 找 provider 模型、上限與憑證；不把整份服務設定或 key 匯出。context/tool blob 分別按 ContextPolicy/manifest 驗證，exec_ref 等遞迴引用亦須可讀有效。

去重鍵為（可信管理 principal、agent_id、config_publish、request_id），digest 為完整 request 的 RFC 8785；同 ID 同內容回原收據，同 ID 異內容 conflict，同 config_revision 異 bundle/ref bindings 也 conflict。先保存全部 blob 與版本綁定，才在同一 writer 交易發布指標與收據；不完整引用不能切指標。PublishResult 保存 previous_revision（初次可 null）、config_revision、published_at_ms 與原 request_id/agent_id；它只說版本可在下一 tick 採用，不表示目前 tick 已換版。PublishError 用共同 Error。回覆丟失仍以原 ID 重送，不回滾已發布指標。

[agent-config.schema.json](schemas/agent-config.schema.json) 根為 Bundle，必填 version、model_ref、context_policy_ref、tool_manifest_ref、cwd；system_prompt 可省為空字串，hooks 可省為空陣列。三個設定 ref 都是非空不可變版本引用字串，不是任意路徑；revision → BlobRef 的可信解析由發布 adapter 保存。bundle 不能夾帶 UID、優先權、key 或 endpoint URL。

```json
{"version":1,"model_ref":"model_v1","context_policy_ref":"context_v1","tool_manifest_ref":"tools_empty_v1","cwd":"/home/agent_a"}
```

`$defs/ContextPolicy` 承接 A-302 的 input_token_limit、output_token_reserve 與 summary_mode；沒有通用 token 數字預設。`$defs/ConfigChange` 保存 changed_at_ms、old_config_revision、new_config_revision、attempt_id 及 version，與取得 claim 的換版交易一起提交。進行中的 tick 不換版；排隊或在途工具／LLM 保留提出該 job 時的固定材料。不能因下一 tick 換版就用新 result_schema 解讀舊工具結果。

缺引用、cwd 不存在或該 agent 無法進入、工具 schema 不受支援，回 config_invalid，原指標不動。cwd 探查依 agent 身分執行，writer 不提升成 root 代讀。已引用內容之後遺失，沿 A-102 記 config_unavailable，不派工具或模型；能否 resume 依可選實作能力，不增加必備出口。重送相同 revision 和內容只能回原發布結果；同 revision 不同內容不能覆蓋。

驗收：Given tick_1 取得 V1 後發布 V2，When tick_1 交提案並開始 tick_2，Then tick_1 仍用 V1，tick_2 的 claim 及 run 換版紀錄指向 V2；舊工具的 manifest 引用仍保留。

## P-304．工具清單、tool call 與固定工作〔建議預設，未拍板〕

[agent-tools.schema.json](schemas/agent-tools.schema.json) 根為 `{version:1,tools:[...]}`；每項沿 A-401，空清單合法。`$defs/ToolCall` 是模型回覆經 provider adapter 解碼後的 `{call_id,name,arguments}`，不是持久紀錄，arguments 不加 version。manifest 的 input_schema/result_schema 使用同檔遞迴 meta-schema，嚴格只允許 A-401 那 13 個 keyword；登記另驗 min≤max、keyword 適用型別、重複名稱等不能僅靠 meta-schema 完成的條件。

```json
{"version":1,"tools":[]}
```

```json
{"call_id":"call_1","name":"echo","arguments":{"text":"你好"}}
```

模型 → tick adapter 只提出 call；tick 先用固定 manifest 驗證名稱、參數與同回覆 call_id 唯一，再導入 RFC 8785 arguments bytes（無 BOM、無附加 LF）作 stdin_blob。ExecTemplate 由 `exec_ref` 指定、解碼引用 [execution-template.schema.json](schemas/execution-template.schema.json)；adapter 從可信 claim 與本次 JobDraft 補 agent_id/run_id/job_id，以固定 argv、bundle cwd 的預設形成 [execution-work.schema.json](schemas/execution-work.schema.json)。這一步不 exec、不取准入票。

〔建議預設，未拍板〕kind=tool 的 JobDraft.payload_ref 指向 `$defs/ToolPayload`：保存 version、call、config_revision、tool_manifest_ref、exec_template_ref、work_ref。work_ref 的內容才是 B-101 固定描述；不能把這層 agent 包裝送給 root helper 當 B-101。控制端接受時核對 call、舊 manifest/template、stdin canonical 摘要、work 的 owner/run/job 一致，保留全部引用至 job 留存期結束。如此 A-403 所需 job→call 映射及舊設定可以由已提交 job 找回，無須可寫 pending 副本。

execution 作者的交界是假設接受已核准 work_ref，ToolPayload 只在非特權語意／控制 adapter 解碼。kind=llm 的 JobDraft.payload_ref 直接使用 llm-request schema；工具直接投 LLM 另沿 llm 篇的每 UID 內部 spool，tick 不用它繞過 Proposal。

不存在工具、參數錯誤或同回覆 call_id 重複均不建立 job，保留 tool_request_invalid 與欄位路徑供下一次思考。連續兩次模型回覆整體格式無效時，以 P-308 的 needs_attention 提案提交計數及 error；合法回覆歸零。語意修正不自動重跑已執行工具。

驗收：Given echo 要 integer 而 arguments 是字串，When tick 解讀 call，Then 沒有 tool JobDraft／子程序，保留 tool_request_invalid；Given 改版後收舊 job 結果，Then 仍由該 job 的 ToolPayload 找回原 call/result_schema，重送不新增第二份工作。

## P-305．輸入、歷史、notes 與來源〔建議預設，未拍板〕

已授權 sender → blob adapter 導入 [agent-input.schema.json](schemas/agent-input.schema.json)，再經 control 篇的 agent.submit 交 input_ref。sender 不在輸入正文中自報。text 必為非空字串，預設 UTF-8 bytes 上限 1 MiB；attachments 可省為 []，每個引用須存在且有權讀。收件確認是 control 所有，讀取或導入 blob 都不算 accepted／已消費。

```json
{"version":1,"text":"請回覆你好。"}
```

[agent-content.schema.json](schemas/agent-content.schema.json) 的 `$defs/HistoryEvent` 為歷史追加項：version、event_seq、run_id、kind、content_ref；source_refs 可省，summary 必須非空。這裡 kind 是 input/assistant/tool_result/summary/note；原始內容不由 kind 猜為 provider JSON。普通 UTF-8／二進位 blob 保存原樣，JSON 型內容另按該內容 schema 驗。

```json
{"version":1,"event_seq":1,"run_id":"run_1","kind":"input","content_ref":{"key":"input_1","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":49}}
```

notes 使用 `$defs/Notes` 的 version/content_ref/source_refs，每次更新是新 blob，舊引用不改。summary 的 source_refs 指向原始材料，不只留下摘要自己的 hash。history 的 event_seq 是控制端提交的連續序號；不能把讀到某段歷史誤當已提交 tail 或已消費。

tick → 控制端只能以 Proposal.history_append 或 append_ref 提出歷史與 notes 版本的可見引用；單在 home 寫檔沒有可見性。輸入的重送沿 P-004/B-503，歷史重送沿 C-05，同 proposal 不二次追加。缺內容或摘要錯誤進完整性處理，不回退 cursor 重做副作用。

驗收：Given 回答與 summary blob 已導入而交易尚未提交就被殺，When 重啟，Then 它們是未引用候選，run.outputs 與正式 history 看不到；重送原提案後每個 event_seq 只出現一次。

## P-306．Context 是選材紀錄，不是額度預留〔建議預設，未拍板〕

tick 從 P-302 預算快照及固定 policy 選材；`agent-content.schema.json#/$defs/Context` 保存 version、config_revision、messages_ref、source_refs、omitted_source_refs、estimation。estimation 含 method、version:1、estimator_revision、is_estimate、input_tokens、output_token_reserve；缺 tokenizer 必須標 estimated，estimator_revision 才是估算方法版本，不能暗中變。messages_ref 解碼引用 [llm-messages.schema.json](schemas/llm-messages.schema.json)，provider wire 的 tool-call ID／arguments 字串映射由 llm 篇負責，本篇的 ToolCall 已是解碼物件。

system、該 run 原始輸入、當前 tool call 和配對結果封套為必要材料；依 A-302 排序並保留配對，省略歷史仍保留 omitted_source_refs。context 指向實際送出的完整模型材料，估算須包括工具描述及 max_output_tokens；控制端入場時會重新估算與查 scope，本 tick 沒有持票等待。

必要材料超限，不切 JSON、不刪原始要求或結果封套；保存來源並用 error.code=context_over_budget、finish=needs_attention 提案提交，new_jobs 為空。摘要若需模型，仍提出正常 llm JobDraft，不能藏在本地 tick 執行。因未知結果或缺 blob 受阻則由控制層設定屏障，不假造一份成功結果給 context。

驗收：Given 必要材料超過 policy 或 run 餘量，When 組 context，Then 零 HTTP、零 reservation，能按 source_refs 查出超限材料；Given 同 context 重送原提案，Then 不另加一次 LLM job。

## P-307．Checkpoint、continuation 與 phase〔建議預設，未拍板；沿 P-011 暫定 4〕

[agent-checkpoint.schema.json](schemas/agent-checkpoint.schema.json) 根只存 version、invalid_response_count 及可省 continuation_ref（預設 null）。初始值如下：

```json
{"version":1,"invalid_response_count":0,"continuation_ref":null}
```

`$defs/Continuation` 保存 version、selected_context_ref、decision_ref、source_refs：前兩者至少一項非 null，來源非空；沒有語意續接內容時就用 checkpoint.continuation_ref=null。selected_context_ref 指向 P-306 Context；decision_ref 指向同檔 `$defs/Decision` 的 version、kind、content_ref、source_refs。kind 僅標記已有的三種待做決策 prepare_llm／prepare_tools／prepare_output，不是新控制狀態。其 content_ref 分別指向候選 llm-request、同檔 `$defs/ToolCallCandidates` 的 `{version:1,calls:[ToolCall...]}`（非空且同回覆 call_id 唯一）、或 P-309 Output；候選不等於 job 已提交或 final 已可見。

continuation 僅保存不能由帳本推回的選擇與決策。已落成 job 的關聯由 Job.payload_ref 追溯；沒有未提交決策時不重存一份派工表。禁止 phase、pending_job_ids、wait_reason、due、input_seq、history_tail、消費 cursor 出現在 checkpoint 或 continuation。恢復只跟已提交 checkpoint pointer，不比較 home 候選 mtime。

phase 查詢依 A-503/T-04，先看控制屏障（paused→paused，needs_attention／未解 unknown→error）；其餘由能否推進及語意位置推導。有待準備工具決策可顯示 act，選 context／準備模型或回答可顯示 think；沒有可做決策、只有帳本等待事實時顯示 wait；沒有工作則 idle。這是唯讀展示建議，不能用它放行、完成 run 或產生新 due。具體多項控制等待的優先序仍由 control 篇沿 S-402 決定。

連續無效回覆計數重設沿 A-401/S-102：合法回覆歸零；可選人工 resume 重新起算須有控制端持久決議與交付依據，不能自行修改舊 checkpoint blob。如何把這個重設決議交給下一 tick 見 P-315 待決。

驗收：Given continuation 存 prepare_tools 而 run paused，When agent.get，Then 顯示 paused、不派工具；Given checkpoint 缺 pending 欄位但帳本有 unknown，When 提案聲稱 succeeded，Then 控制端拒絕，不能靠精簡 checkpoint 掩蓋 unknown。

## P-308．Proposal 與 append 材料〔建議預設，未拍板〕

[agent-proposal.schema.json](schemas/agent-proposal.schema.json) 根及 `$defs/Proposal` 精確承接 C-05：version、agent_id、run_id、attempt_id、generation、expected_revision、consumed_input_ids、consumed_attempt_ids、new_jobs、finish、checkpoint_ref。history_append/outputs 預設 []；append_ref/final_ref/error 預設 null。JobDraft 只含 job_id、kind=tool|llm、payload_ref 與可省 retry_class/max_attempts，不接受 UID、priority、resource_domain 或另一個 tick。LLM 預設 max_attempts=3，工具=1；schema default 不會替實作填值。

```json
{"version":1,"agent_id":"agent_a","run_id":null,"attempt_id":"tick_1","generation":1,"expected_revision":0,"consumed_input_ids":[],"consumed_attempt_ids":[],"new_jobs":[],"finish":"none","checkpoint_ref":{"key":"checkpoint_1","sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","bytes":67}}
```

這是維護提案：只能更新維護 checkpoint，其他增量全空。普通 run 提案的消費 IDs 必須唯一、已交付、尚未消費且屬同 owner/run；不能消費 tick attempt。history/output seq 必須接帳本尾端，不能跨 run。finish=succeeded 必須 final_ref 對應本次展開後的 final；failed/needs_attention 必須 Error。needs_attention 只承接 A-401/A-302 的 agent 可判原因，不接受 blob 缺失、unknown 或部署屏障由 agent 自報覆蓋；new_jobs 必須空。

`$defs/Append` 是大增量的 blob 格式：

```json
{"version":1,"history_append":[],"outputs":[]}
```

用 append_ref 時，內嵌 history_append/outputs 必須省略或為 []；驗證與完成條件以展開後的增量為準。BlobRef 不省掉大小計算：提案 JSON ≤256 KiB、checkpoint＋本次歷史／回覆 JSON 預設合計 ≤16 MiB；append 的 version 包裝亦算入。RPC envelope／持久包裝另受 P-005 的 256 KiB 上限，不能用提案剛好沒超限為理由送過大的 envelope。外部 content_ref 正文仍沿 blob 額度。

final/failed 都必須由控制帳本在套用增量後確認沒有遺留 tool/llm pending、未消費結果與不允許的 unknown，並核對取消屏障。checkpoint 沒有權威 pending 副本。Proposal 通過不表示任何工具立即啟動，派工只讀已提交意圖並重新准入。

驗收：Given append_ref 展開含另一 run 的 final，或 inline 與 append 同時有增量，When 提交，Then 全拒絕；Given 一筆提案同時消費輸入/結果、追加歷史/輸出並建新 job，When 交易中斷，Then 全部不生效或全部生效，沒有提前 ACK。

## P-309．Output 與可見 final〔建議預設，未拍板〕

[agent-output.schema.json](schemas/agent-output.schema.json) 根及 `$defs/Output` 是控制端可見輸出的唯一型別。必填 version、run_id、output_seq、kind=progress|final、text；空 text 合法，output_seq 為正整數。control 的 run.outputs 應直接引用它，不另定形狀。

```json
{"version":1,"run_id":"run_1","output_seq":1,"kind":"final","text":"你好。"}
```

tick 先把這筆 Output 作 blob 導入，final_ref 指向含該 final 的不可變內容，再在同一 Proposal.outputs 或 append_ref 提出完全一致的 Output。控制端核對 run_id、seq、kind 與正文，交易成功後才可查見。讀端按 (run_id,output_seq) 去重；讀走、下載或列出結果不提交語意消費，也不清除保存責任。

如果 stdout 有文字、模型已回答或 Output blob 已存在，但沒有提交收據，都不是正式 final。成功提交後回覆前崩潰，輸出仍可見且原提案重送不追加第二次；底層 tick 程序後來 unknown 亦不撤回已提交 final（B-603）。

驗收：Given 有在途工具且 outputs 含 final，When finish=succeeded，Then 拒絕完成；Given 工具已收尾且結果已在本次增量消費，When 同一 final 提案成功並重送，Then run.outputs 僅有原 output_seq 一筆。

## P-310．Blob 導入與 checkpoint.commit〔建議預設，未拍板〕

順序固定：tick 產生候選 bytes → 非特權 blob adapter 取普通檔 fd 快照、驗大小與 hash → 在本 owner 受管內容庫持久發布並回 BlobRef → tick 組 Proposal → fd4 送 checkpoint.commit → 控制 writer 驗證並提交 → 同 fd 回 RPC。fd5 的二進位／metadata、fd 的 SCM_RIGHTS／繼承細節由 [storage.md](storage.md) 及 [storage-blob-transfer.schema.json](schemas/storage-blob-transfer.schema.json) 承接；tick 不能直接指一個 home 路徑叫 root 讀，也不能把本機 fd 數字塞進一般 RPC。

[agent-commit.schema.json](schemas/agent-commit.schema.json) 組合 control-rpc 的外層，獨有 payload 是 params `{proposal:Proposal}`，成功 result 精確為 `{committed:true,revision:正整數}`。不加 accepted、run_id 或 result.ack。檔案通道只用 P-005 `{version:1,message:原envelope}`，requests/responses 以 delivery_id 同名，內層 id 保持 request_id；標準 tick 使用 fd4 socket，不為 socket 另造整套 spool。

```json
{"jsonrpc":"2.0","id":"commit_1","method":"checkpoint.commit","params":{"proposal":{"version":1,"agent_id":"agent_a","run_id":null,"attempt_id":"tick_1","generation":1,"expected_revision":0,"consumed_input_ids":[],"consumed_attempt_ids":[],"new_jobs":[],"finish":"none","checkpoint_ref":{"key":"checkpoint_1","sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","bytes":67}}}}
```

```json
{"jsonrpc":"2.0","id":"commit_1","result":{"committed":true,"revision":1}}
```

```json
{"jsonrpc":"2.0","id":"commit_1","error":{"code":-32000,"message":"tick 世代已過期","data":{"code":"stale_generation","message":"tick 世代已過期","retryable":false}}}
```

控制端在單一交易內驗 live claim、generation、expected_revision、引用與摘要、owner/run、屏障、消費、序號、pending 容量及完成條件；成功才一起更新 checkpoint pointer/revision、消費、history、Output、job 意圖、run 與提案收據。失敗不部分落地；錯誤碼沿 C-04，普通 conflict 用 -32002、stale_generation 用 -32000。blob 導入成功卻提交失敗，只留下待回收候選，不授權派工。

有界 I/O 或寫入失敗不承諾成功；同請求無回覆時保留原 request_id、attempt、expected_revision 和提案形式重送。不能把 append_ref 改為 inline 再宣稱同提案，因完整提案摘要不同。schema 的 Error.retryable 不能當成重新執行外部工具的授權。

驗收：Given fd4 一次讀到半行／兩行 JSON，When 解框，Then 不部分處理／不合併 request；Given blob 導入後 SQLite commit 失敗，Then 沒有 revision 遞增、消費或派工；Given合法 RPC error 完整回傳，Then 包裝程序可 exit 0 而提交仍失敗。

## P-311．重送、舊世代與崩潰恢復〔建議預設，未拍板〕

兩層去重都要保留：P-004/B-503 的認證 sender＋target agent＋method＋request_id，以及 C-05 的 attempt＋expected_revision＋完整提案摘要。同 attempt 最多一份 Proposal；已提交的相同提案先命中原收據，即使目前 revision 或 generation 已前進，仍回原 revision，不重新消費。未提交的舊 generation 回 stale_generation，過期 revision／同 attempt 異內容回 conflict。新 delivery_id 只改傳送，不改業務 ID。

控制端重啟先殺掉並清空舊受管範圍，再依耐久提交收據恢復。已有收據者保留 checkpoint/final；沒有收據者保持舊 pointer，清空後可用新 tick job/generation 重新理解舊材料。這只重做沒有外部副作用的語意步驟，不重跑未知工具或 HTTP。工具／LLM unknown 仍由原 attempt 記錄，走人工處置／可信補證據。

| 中斷點 | 恢復結果 |
|---|---|
| 候選未完整導入 | 無 BlobRef 成功收據；依 storage 清理未完成導入。 |
| blob 已發布、proposal 未提交 | 孤立 blob，沒有已消費／已派工／可見輸出。 |
| 交易已提交、RPC 回覆遺失 | 原提案重送回原 revision，一次語意消費。 |
| 回覆已送、tick／post 尚未清空 | 提交保留；claim 保持 held，直到 B-602 清空與對帳完成。 |
| tick 無提案而被殺 | 保留舊 checkpoint；清空後依 ready/屏障決定新 tick，不能自行設 due 忙迴圈。 |

驗收：Given 每個中斷點各執行一次並在重啟後重送兩次，When 查帳本，Then 最多一份提案收據、一組新 jobs、一組 output_seq，且 pending/unknown 證據沒有因重送或釋放 claim 消失。

## P-312．OutcomeAdapter 給模型的結果〔建議預設，未拍板〕

控制端先可信登記 Attempt/Outcome，再交給 tick。OutcomeAdapter 用原 job 的 ToolPayload 配回 call_id 與原 result_mode/schema；讀取 Outcome.result_ref 所指的 [execution-result.schema.json](schemas/execution-result.schema.json)。adapter 不修改原 Outcome 或 ExecResult，不接收工具 stdout 自稱的 succeeded。

[agent-tool-outcome.schema.json](schemas/agent-tool-outcome.schema.json) 根是 A-403 的模型可見封套：version、call_id、outcome、exec_result_ref、stdout_preview、stderr_preview、preview_truncated、output_truncated、semantic_error。exec_result_ref 與 Outcome.result_ref 必須一致（沒有可信詳細結果時都可 null）；兩個預覽即使空也必填。只因展示長度裁切設 preview_truncated；底座未完整保存 bytes 才設 output_truncated，兩者不能互相代替。

text 模式嚴格 UTF-8 解碼；json 模式先核對完整保存且 stdout 未截斷，才解析整份 stdout、拒絕重複 key/尾隨值並驗原 result_schema。錯誤記 tool_result_invalid；原始結果與副作用不被改成另一份失敗執行。模型 stdout/stderr 預覽合計預設 ≤64 KiB UTF-8，不切開字元；JSON 的截斷預覽只當字串，不冒充合法解析值。null stream ref 不代表已保存空串流。

非零退出、signal、timeout、取消、截斷與 unknown 保留原 Outcome/Error/ExecResult 來源。語意格式錯誤不自動重跑工具；unknown 不能當 failed 交模型偷偷重試。展示封套可保存在 history kind=tool_result 的 content_ref，但語意消費仍只隨 Proposal.consumed_attempt_ids 原子提交。

驗收：Given 工具 exit 0 但 stdout JSON 不合 schema，When 組封套，Then Outcome 仍 succeeded、semantic_error=tool_result_invalid、原始引用仍在且沒有新 job；Given 只有部分 bytes 或 unknown，Then 明示不完整／未知，不把空預覽當成功空結果。

## P-313．掛勾登記、stdin 與執行紀錄〔使用者方向 2026-09-29；編碼為建議預設，未拍板〕

[agent-hook-registration.schema.json](schemas/agent-hook-registration.schema.json) 是一個登記項目；agent bundle.hooks 與 control-config 的 system hooks 都引用它，容器決定身分，普通 agent 不能在項目內宣稱 scope=system。登記必填 name、when、argv（持久項含 version），可省 timeout_ms=30000、on_failure=continue、order=0。name 在該登記清單唯一，按 order/name 排序；agent/system 兩組如何串接見 P-315。

launcher 用登記 argv 原樣 exec，沒有額外 shell／參數插值；因此最小測試掛勾可用固定 `["/usr/bin/true"]`。stdin 一份 [agent-hook-input.schema.json](schemas/agent-hook-input.schema.json) JSON 到 EOF；stdout/stderr 是有界不可信診斷，不當 Proposal、工具結果或 agent history。需要傳訊給 agent 必須走正常輸入。system 掛勾可在自身固定 argv 指定 storage 篇的 aos-clean 機器入口，其內部協議與清理收據仍歸 storage，不由 stdout 宣告 claim 完成。

stdin 沿 A-506 的 version、agent_id、run_id、when、attempt_id、tick_outcome，另依 P-011 暫定加入 hook_run_id。pre 時 tick_outcome=null；post 只能是 committed/rejected/no_proposal/timeout/killed。attempt_id 仍可 null，hook_run_id 才是一次掛勾執行的識別；控制端事先持久保存 hook_run_id 與原 claim generation/attempt 的關聯，不用 stdin 自稱的 ID 取得權限。

```json
{"version":1,"hook_run_id":"hook_1","agent_id":"agent_a","run_id":"run_1","when":"pre","attempt_id":"tick_1","tick_outcome":null}
```

agent 掛勾以 agent UID、agent cgroup/quota 與固定 bundle cwd 執行；system 掛勾以控制側專用服務 UID、控制域與可信部署 cwd 執行，不用 root 或 agent UID。環境沿 B-102；本協議不新增 AOS_*，也不把 fd4/fd5 或管理 socket/key 傳給 agent 掛勾。系統程式若需內部服務通道，由其受信部署定義縮限 fd 與服務 UID 認證，不能由 agent bundle 取得。

子掛勾 exit 0 在可信 supervisor 確認完整收尾後才是執行成功；非零/信號/timeout/啟動失敗均失敗，無可信終局證據為 unknown。它們是 child 的狀態，不把 125、2 特別解作掛勾自身產品語意。可信觀測由 execution 篇供給，控制端以 [agent-hook-result.schema.json](schemas/agent-hook-result.schema.json) 保存 hook_run_id、claim 關聯、scope/name/when、tick_outcome、執行時間、退出或信號、輸出引用/截斷與結構化錯誤。這不是工具 ExecResult，不為掛勾捏造 tool Job 或 result.ack。

驗收：Given agent 在 bundle 登記名為 clean 的程式，When 啟動，Then 仍只用 agent UID 且無控制通道；Given 同 tick 有三個掛勾，Then 三個不同 hook_run_id 可各自查到，不能用相同 tick attempt_id 去重掉其中兩個。

## P-314．掛勾次序、tick_outcome、失敗與重送〔建議預設，未拍板；沿 P-011 暫定 7〕

控制端取得 claim → 執行 pre → 啟動 tick → 核對提案交易／收尾 → 執行 post → 確認全部受管程序清空 → 釋放 claim。agent pre/post 的耗時包含在本 tick 限額；P-011 暫定總 deadline 自取得 claim 起算，post 只能用剩餘時間，不另起一個完整 timeout 延長 claim。每個掛勾另受自己的 timeout_ms；deadline 用經過時間，claimed_at_ms 只供顯示。system 時間另計與總上限的接縫留 P-315。

tick_outcome 由控制端持久證據判斷：有已提交 proposal 收據為 committed（即使稍後程序被殺）；有確定拒絕、未成功提交為 rejected；正常退出且沒有提案為 no_proposal；未提交且期限到為 timeout；未提交且因外部停止／signal 收尾為 killed。丟回覆不能直接當 rejected/no_proposal，須先補查收據。這不是 tool/llm Outcome；post committed 不表示 run succeeded。

pre 失敗且 on_failure=skip_tick，不起 tick，保留 run，保存原因後收尾釋放 claim；下一次排程依 P-011 的有界退避或新事件，不能因 ready 還在立即重跑。其他失敗只記錄，不推翻已提交提案或把 run 判失敗。pre skip 後是否仍跑 post、沒有剩餘時間時如何記未啟動 post，見 P-315，不能捏造已執行紀錄。

控制端對同 hook_run_id 的同份可信完成紀錄重送只導入一次；確定終局異內容報 conflict。重啟時正在執行的掛勾全殺、無可信結果記 unknown，不補跑該次掛勾；後續正常 tick 可以再次觸發登記項目，但有新的 hook_run_id。sys post 的 aos-clean 另以 storage 的清理 batch 去重，不能因一般掛勾「不補跑」就抹掉已領候選的清理恢復責任。所有 post 的輸出都不自動寫 history。

驗收：Given tick 已提交而 post timeout，When 收尾，Then checkpoint/final 不撤銷、掛勾失敗可查，claim 待清空才 released；Given pre skip_tick 失敗，Then 沒有 tick 程序且不忙迴圈；Given post 執行中重啟，Then 清空、記 unknown、不冒充成功或自動補執行該 hook_run_id。

## P-315．待決與整合者回寫清單〔主編補；建議均未拍板〕

本篇只寫 P-012 分配的檔案，以下不是擅自增加的可呼叫入口：

1. **系統掛勾與總 deadline**：A-506 說 system 時間另計、不占 tick 時間，P-011 暫定 7 說總 deadline 自 claim 起算、post 僅剩餘時間，B-101 又以放行起算。建議明分 claim 的總經過時間上限與 agent 計費時間；execution/control 必須用同一截止點，不因 post 重設 timer。總上限如何配置、system 時間是否扣總上限須整合者補 A-506/B-101/B-602，本文不給相反的保證。
2. **掛勾交錯與未啟動 post**：原文未定 system/agent 同 order 的相對次序、pre skip 後是否執行 post、deadline 用盡的 post 如何記為未啟動。建議兩組先後有固定部署選擇、skip 對應 no_proposal 且有剩餘時間才跑 post；未啟動不可寫 succeeded。須先補原條款，schema 現有 HookResult 只記實際開始／啟動失敗的執行，不新增 tick_outcome 值。
3. **人工重設無效回覆計數**：S-102 允許 resume 使計數重新起算，但 A-502 的計數在不可變 checkpoint，現有唯讀視圖未列恢復決議欄位。建議控制 writer 保留帶 request_id 的恢復事件並在下一 tick 交付；tick 據此以正常 C-05 交易提交 count=0，不能原地改 blob 或用環境旗標。具體事件欄位與一次性套用的依據需 control/agent 正本對齊，尚不封進 schema。
4. **工具與 continuation 的 payload 交界**：P-307 的 ToolCallCandidates 是 provider 回覆解碼後的候選，不是已派工作；P-304 的 ToolPayload 包住 call/舊版本與 work_ref。請整合者在 A-401/A-403 或 execution 導覽明寫取 work_ref 才得到 B-101，避免把 agent 包裝送到只接受固定工作描述的入口。
5. **README 回寫**：P-011 暫定 4 對應本篇 Continuation/Decision；暫定 7 的 hook_run_id/claim 關聯已落格式，但上述時間接縫仍需回寫。P-003 的 attention 舊路徑與暫定 5 不一致，由整合者照 storage 最終內容修；本篇不碰 attention。P-012 的 control run.outputs 請引用 agent-output root 或 `$defs/Output`。
6. **四篇交界**：control-rpc root 須接受 checkpoint.commit 通用 envelope，本篇自行收緊 params/result；execution 取 ToolPayload.work_ref 解碼 B-101、回傳可信工具與掛勾觀測；llm 定 messages 與 provider 原始結果，agent 只選材並提出已版本化 payload；storage 決定 fd5 交付／導入機器介面，導入收據不等於 checkpoint 提交。若最終 schema root 是多種訊息的 union，必須使用對應明確片段以免放寬，不能只因 `$ref` 可解析就算整合完成。
7. **tick fd 啟動交界待補**：本篇 P-301 需要 input/commit/blob/content fd，execution P-204/LaunchRequest 目前只列 work/stdin，runner 也會關閉啟動專用 fd。整合者須在 execution 加「只限 tick 角色、來自可信父程序」的 fd 白名單與重新編號，避免與 runner 原本 3/4/5 等控制 fd 撞號；不能直接開放工具自行指定保留 fd。execution P-209 的 pre/post stdin 範例也須加本篇必填 hook_run_id。這是跨篇交付缺口，尚不能聲稱現在兩份 argv 已完整接通。
8. **發布 adapter 對照**：P-303 已提供 P-011 暫定 2 的 config-publish 入口及 agent-config 公開片段。control 篇請引用其管理者認證／writer 交易責任；llm 篇請核對 ModelSelection.model 為其邏輯模型名、endpoint_id 有效且 agent 可讀內容不含憑證。registry/profile 發布仍歸 execution，不藉本 adapter 更新 Linux 身分。

驗收：Given 整合者合併五篇，When 對上述各項逐一對照，Then 已選格式標記仍保留未拍板，未定語意沒有出現在首版可呼叫 method，且所有外部 `$ref` 指向對應訊息型別。

## P-316．沿用 proto5、驗證與現況〔主編補〕

沿用 [proto5 cpu/messages](../../../proto5/spec/cpu/messages.md) 的同名 requests/responses、[aos-exec](../../../proto5/spec/aos-exec/api.md) 的直接 argv 與包裝器失敗分離、[kernel/syscall](../../../proto5/spec/kernel/syscall.md) 的先記意圖再交付、[aos-agent/tick](../../../proto5/spec/aos-agent/tick.md) 的單 tick 與可恢復步驟、[aos-llm/request](../../../proto5/spec/aos-llm/request.md) 的一次模型呼叫且不在 client 內重試。

不同處有正本理由：B-402 改成 fsync＋同 filesystem rename 並修復 DB/spool；B-602 改為控制 claim＋generation fence＋清空證據，沒有 lease 或靠 101/102/103 再排；C-05 把 consumption/history/jobs/checkpoint 合成一次提交，不保留 proto5 state.json 的 pending/intake/phase 權威副本；P-005/C-04 禁 notification、數字 id 與舊 ack 刪回覆；A-102 每 tick 固定 bundle，不能像 proto5 LLM 起跑才重讀可編設定；S-301 key 只在服務 UID，agent 不讀 key env；B-603 重啟全殺、不認領孤兒工作；hooks 是本輪新增機制。

交付的 schema 清單與用途：

| Schema | 責任 |
|---|---|
| [agent-config](schemas/agent-config.schema.json) | Bundle、context policy、換版紀錄、管理者發布及模型選擇材料。 |
| [agent-tools](schemas/agent-tools.schema.json) | Manifest、ToolCall、工具 schema 子集與不可變呼叫關聯。 |
| [agent-input](schemas/agent-input.schema.json) | 輸入正文與附件引用。 |
| [agent-content](schemas/agent-content.schema.json) | HistoryEvent、notes、context 與來源。 |
| [agent-output](schemas/agent-output.schema.json) | 唯一 Output 型別，供 run.outputs 引用。 |
| [agent-tick](schemas/agent-tick.schema.json) | Claim、唯讀帳本、啟動輸入及內容 fd 對照。 |
| [agent-checkpoint](schemas/agent-checkpoint.schema.json) | 語意計數、Continuation、Decision。 |
| [agent-proposal](schemas/agent-proposal.schema.json) | Proposal、JobDraft、Append。 |
| [agent-commit](schemas/agent-commit.schema.json) | checkpoint.commit params/result 與 RPC／檔案包裝。 |
| [agent-tool-outcome](schemas/agent-tool-outcome.schema.json) | 模型可見工具結果、語意錯誤與截斷。 |
| [agent-hook-registration](schemas/agent-hook-registration.schema.json) | 單一掛勾登記。 |
| [agent-hook-input](schemas/agent-hook-input.schema.json) | pre/post stdin 與 hook_run_id。 |
| [agent-hook-result](schemas/agent-hook-result.schema.json) | 掛勾可信執行紀錄與原 claim 關聯。 |

驗收分三層：每個 schema 用 `python3 -c 'import json,sys;json.load(open(sys.argv[1]))' 檢查 JSON，再用可用的 jsonschema Draft202012Validator 檢查 schema 與 valid/invalid 範例；語意層另驗同 owner/run、版本/摘要、序號/配對與 fencing；恢復層依 P-311 的中斷點驗證。本文是機器協議草稿，沒有把 schema 測試當作程序、持久性或 OS 隔離已實作驗收。

驗收：Given 只有 schema 測試通過，When 報告現況，Then 只稱格式已驗，不宣稱已完成 tick、掛勾、持久導入或崩潰測試。

## P-317．完整範例與反例的驗法〔主編補〕

下列連結都是完整 JSON 檔，不是片段。`valid` 只表示對應 schema 合格：unknown、結構化失敗、needs_attention 都是合法訊息，不代表工作成功。`invalid` 是形狀上應被拒絕的反例；跨 owner、stale claim、摘要不符與未清空則另依前述 Given/When/Then 驗語意。每項只按表列的 root／`$defs` 驗證，不把多型材料猜成另一種類。

| 主要訊息／驗證位置 | 完整最小例及其他有效情境 |
|---|---|
| agent-config root | [最小 bundle](examples/agent-state/config.minimal.valid.json) |
| agent-config ContextPolicy／ConfigChange／ModelSelection | [policy](examples/agent-state/config.context-policy.valid.json)、[換版](examples/agent-state/config.change.valid.json)、[模型選擇](examples/agent-state/config.model-selection.valid.json) |
| agent-config PublishRequest／PublishResult／PublishError | [發布](examples/agent-state/config.publish-request.valid.json)、[同 ID 重送](examples/agent-state/config.publish-resend.valid.json)、[成功收據](examples/agent-state/config.publish-result.valid.json)、[設定錯誤](examples/agent-state/config.publish-error.valid.json) |
| agent-tools root／ToolCall／ToolPayload | [空清單](examples/agent-state/tools.empty.valid.json)、[一項工具](examples/agent-state/tools.minimal.valid.json)、[call](examples/agent-state/tools.call.valid.json)、[固定呼叫關聯](examples/agent-state/tools.payload.valid.json) |
| agent-input root | [最小輸入](examples/agent-state/input.minimal.valid.json) |
| agent-content HistoryEvent／Notes | [輸入歷史](examples/agent-state/history.input.valid.json)、[有來源的 summary](examples/agent-state/history.summary.valid.json)、[notes](examples/agent-state/notes.minimal.valid.json) |
| agent-content Context | [context 與完整估算來源](examples/agent-state/context.minimal.valid.json) |
| agent-output root | [progress](examples/agent-state/output.progress.valid.json)、[final](examples/agent-state/output.final.valid.json) |
| agent-tick root／Claim | [普通 tick](examples/agent-state/tick.normal.valid.json)、[maintenance tick](examples/agent-state/tick.maintenance.valid.json)、[held claim](examples/agent-state/claim.held.valid.json) |
| agent-tick LedgerSnapshot | [普通 run](examples/agent-state/tick.ledger-normal.valid.json)、[maintenance](examples/agent-state/tick.ledger-maintenance.valid.json)、[unknown 診斷快照](examples/agent-state/tick.ledger-unknown.valid.json) |
| agent-checkpoint root | [初始 checkpoint](examples/agent-state/checkpoint.initial.valid.json)、[帶 continuation](examples/agent-state/checkpoint.continuation.valid.json) |
| agent-checkpoint Continuation／Decision | [已選 context](examples/agent-state/continuation.context.valid.json)、[未提交決策引用](examples/agent-state/continuation.decision.valid.json)、[決策本文](examples/agent-state/continuation.decision-content.valid.json)、[候選 calls](examples/agent-state/continuation.tool-calls.valid.json) |
| agent-proposal root／Append | [maintenance](examples/agent-state/proposal.maintenance.valid.json)、[消費並建立新 job](examples/agent-state/proposal.continue.valid.json)、[final](examples/agent-state/proposal.final.valid.json)、[needs_attention](examples/agent-state/proposal.needs-attention.valid.json)、[引用增量](examples/agent-state/proposal.append.valid.json)、[增量本文](examples/agent-state/append.final.valid.json) |
| agent-commit root | [原 request](examples/agent-state/commit.request.valid.json)、[同 ID 同內容重送](examples/agent-state/commit.request-replay.valid.json)、[成功](examples/agent-state/commit.success.valid.json)、[conflict](examples/agent-state/commit.conflict.valid.json)、[stale_generation](examples/agent-state/commit.stale-generation.valid.json) |
| agent-commit File | [request.file](examples/agent-state/commit.request.file.valid.json)、[success.file](examples/agent-state/commit.success.file.valid.json) |
| agent-tool-outcome root | [最小成功](examples/agent-state/tool-outcome.minimal.valid.json)、[同內容重送](examples/agent-state/tool-outcome.resend.valid.json)、[語意格式錯誤](examples/agent-state/tool-outcome.semantic-failure.valid.json)、[unknown](examples/agent-state/tool-outcome.unknown.valid.json)、[底座與展示截斷](examples/agent-state/tool-outcome.truncated.valid.json) |
| agent-hook-registration root | [最小 pre](examples/agent-state/hook-registration.minimal.valid.json)、[post](examples/agent-state/hook-registration.post.valid.json)、[skip_tick](examples/agent-state/hook-registration.skip-tick.valid.json) |
| agent-hook-input root | [pre stdin](examples/agent-state/hook-input.pre.valid.json)、[post stdin](examples/agent-state/hook-input.post.valid.json) |
| agent-hook-result root | [最小成功](examples/agent-state/hook-result.minimal.valid.json)、[post](examples/agent-state/hook-result.post.valid.json)、[同 ID 重送](examples/agent-state/hook-result.resend.valid.json)、[失敗](examples/agent-state/hook-result.failure.valid.json)、[unknown](examples/agent-state/hook-result.unknown.valid.json)、[截斷](examples/agent-state/hook-result.truncated.valid.json) |

反例拒絕原因：

| 反例 | 使用 schema／拒絕原因 |
|---|---|
| [config.unknown-field](examples/agent-state/config.unknown-field.invalid.json) | agent-config root：bundle 不接受 uid。 |
| [config.publish-missing-binding](examples/agent-state/config.publish-missing-binding.invalid.json) | PublishRequest：缺三種必要 binding 之一。 |
| [config.publish-duplicate-role](examples/agent-state/config.publish-duplicate-role.invalid.json) | PublishRequest：同用途 binding 重複，不能冒充三項已齊。 |
| [tools.schema-forbidden-keyword](examples/agent-state/tools.schema-forbidden-keyword.invalid.json) | agent-tools root：內嵌工具 schema 不接受 `$ref`。 |
| [tools.json-without-schema](examples/agent-state/tools.json-without-schema.invalid.json) | agent-tools root：json result_mode 必須有 result_schema。 |
| [input.impersonated-sender](examples/agent-state/input.impersonated-sender.invalid.json) | agent-input root：輸入正文不可自報 sender。 |
| [history.summary-without-source](examples/agent-state/history.summary-without-source.invalid.json) | HistoryEvent：summary 必須有非空 source_refs。 |
| [checkpoint.control-copy](examples/agent-state/checkpoint.control-copy.invalid.json) | Checkpoint：不接受 phase 等控制副本。 |
| [continuation.empty](examples/agent-state/continuation.empty.invalid.json) | Continuation：context 與 decision 不可同為 null；沒有續接內容應省去整個 continuation。 |
| [proposal.duplicate-consume](examples/agent-state/proposal.duplicate-consume.invalid.json) | Proposal：消費 ID 陣列不得重複。 |
| [proposal.maintenance-new-job](examples/agent-state/proposal.maintenance-new-job.invalid.json) | Proposal：run_id=null 時不能建語意工作。 |
| [proposal.append-and-inline](examples/agent-state/proposal.append-and-inline.invalid.json) | Proposal：非空內嵌增量不能與 append_ref 並用。 |
| [commit.false-success](examples/agent-state/commit.false-success.invalid.json) | agent-commit：成功 result 必為 committed:true，不能回 false 當合法成功收據。 |
| [tool-outcome.missing-preview](examples/agent-state/tool-outcome.missing-preview.invalid.json) | agent-tool-outcome：stdout_preview 即使空也必填。 |
| [hook-registration.empty-argv](examples/agent-state/hook-registration.empty-argv.invalid.json) | agent-hook-registration：argv 不得空陣列。 |
| [hook-input.post-null](examples/agent-state/hook-input.post-null.invalid.json) | agent-hook-input：post 必須有五種 tick_outcome 之一，不能 null。 |
| [hook-result.success-with-error](examples/agent-state/hook-result.success-with-error.invalid.json) | agent-hook-result：succeeded 的 error 必須 null。 |

驗收：Given 表中每個 JSON 與指定型別，When Draft202012Validator 解開本機相對引用驗證，Then valid 全接受、invalid 全拒絕；四組同 ID 重送檔與各自原件的 JSON 值完全相同。格式驗證不替代 P-311 的耐久交易測試。
