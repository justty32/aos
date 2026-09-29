# LLM：投件、中央代發與用量交接

← [共用約定與分工](README.md)｜[LLM 排程正本](../scheduling/llm.md)｜[工具／client](../agent/tools.md)｜[09-29 裁定](../../notes/2026-09-29-verdicts.md)

## P-400．範圍與來源〔主編補〕

本篇把 A-302、A-402／A-404、S-301～S-306、C-03／C-04、B-402／B-503／B-603 落成機器介面。中央代發與專用服務 UID 沿〔使用者方向 2026-09-29，裁定 9〕；其餘 wire 形狀、子命令、adapter 版本與範例數值均為〔建議預設，未拍板〕。P-011「09-29 整合者暫定」第 1、3 項是本稿工具收件與 OpenAI 相容 chat completions 的依據，不把暫定升為使用者裁定。

控制 writer 決定 owner、run、准入、attempt、重試及結算。服務只接受已准入派送，持有憑證，執行一次 HTTP，回交可信證據。agent 決定 context、解讀 assistant、提交 history／下一份 Proposal。工具可以投 LLM，但不能透過此入口建立其他 kind 的 job。本文沒有新增公開 JSON-RPC method；`result.ack` 仍不可呼叫。

**Given** 工具要求 LLM 同時附上另一個工具工作，**When** 收件，**Then** 只接受本篇的 LLM payload，額外欄位回 `invalid_record`，不把服務變成第二個排程器。

## P-401．服務啟動、資料流與身分〔建議預設，未拍板〕

systemd／可信部署 launcher 直接 exec 以下完整 argv 範例：

```json
["aos","llm-service","--config-fd","3","--listen-fd","4","--instance-id","service_1"]
```

三個選項都必填，不接受位置參數或其他旗標。fd 3 是管理者提供的唯讀普通檔，內容符合 [llm-config](schemas/llm-config.schema.json)，讀到 EOF 後關閉；fd 4 是管理者建立、已 listen 的 Unix `SOCK_SEQPACKET` socket，服務持有至停機。數字是**實際繼承的 fd**，不是 JSON 中聲稱可開啟的路徑。啟動者把同一份不可變設定 revision 與本次唯一 instance ID 告知控制端；instance ID 每次服務重建都換，不能靠相同 PID 推定同一實例。

服務的真實 UID／GID 須符合設定，UID 非 0、非控制 writer UID、非任何 agent UID。CPU／記憶體屬控制資源域，啟動者核對 `memory_max_bytes`、`cpu_quota_us`／`cpu_period_us` 已施加；`max_concurrent_http` 再限制本地 HTTP 數，不能繞過控制端 scope 准入。服務先取得 state_root 的排他鎖，舊實例未清空時不得啟動第二個有送出能力的實例。控制端重啟時此服務與在途 adapter 都在 B-603 全殺、清空及對帳的受管範圍內，不獨立留下會繼續發送的服務。

stdin 關閉；stdout 不輸出協議，保持空；stderr 僅有有界診斷，單份至多 B-404 的 64 KiB，並依控制部署預算輪替。不能記 Authorization、key、完整 prompt 或整包回應。協議走 fd 4 接受的連線，不解析 log 猜結果。正常停機且約定交接完成 exit 0；argv／部署／啟動前設定不合法 exit 2；本身 I/O、持久發布或停機清空失敗 exit 125。被 signal 終止看 wait 狀態。這些退出碼不表示某個模型請求成功或未執行。

LLM 服務**不讀 AOS_ 環境變數**，也沒有 argv 的 env 備援；工具專用的 `AOS_LLM_ENTRY_DIR` 另見 P-404。服務 launcher 只給明確的乾淨 `PATH`、`HOME`、`TMPDIR`、`LANG`；HOME／TMPDIR 為服務自己的受控位置。忽略並清除繼承的 `AOS_LLM_CONFIG`、provider key／proxy／loader 類環境設定，不從 agent env 找 endpoint 或憑證。provider adapter 首版是服務內建的一次呼叫函式，沒有另一支 executable、argv、stdio、env 或子程序退出碼；同程序呼叫沿 P-001，不強套 RPC。

**Given** agent 帶上 `AOS_LLM_CONFIG` 或假 service UID，**When** 啟動／投件，**Then** 不改服務設定與授權；服務部署錯誤在任何 HTTP 前拒絕。**Given** 程式 exit 0，**When** 控制端沒有結果收據，**Then** 不宣告 attempt 成功。

## P-402．設定與憑證引用〔建議預設，未拍板〕

管理者向服務交付 [完整最小設定](examples/llm/config.minimal.valid.json)。`llm-config.schema.json` 的 `$defs/Endpoint`、`Model`、`Scope`、`CredentialReference` 是設定片段；不是 agent 可寫或可整份查詢的資料。agent 的模型設定只引用 `endpoint_id`／`model` 與 context 所需的限額。job 固定所採用的 `config_revision`，下一 tick 改版不改已派送的快照。

endpoint 含 `base_url`、可 null 的 `credential_ref`、全部適用 `scope_ids`、`adapter_revision`、`estimator_revision`、`rate_accounting_revision` 與 models。`model` 是請求可用名字，`provider_model` 是 HTTP 中的真名；相同 endpoint 的 model、全表 endpoint／scope／credential ID 都不得重複。scope 必須存在，兩個 URL 若共享帳戶限制就引用同一 scope，不由工具挑選。Scope 的 request／token limit 省略或 null 表示未設該維度，其餘 concurrency 與 window 仍生效。

`credential_ref` 指向管理者配置的服務專用普通檔：僅服務 UID／管理者可讀，內容為 UTF-8 非空 Bearer token，允許移除一個結尾 LF；其餘控制字元、空值、symlink／非普通檔拒絕。path 必須為絕對路徑，不由 job 提供、不經 root 代開。null 表示不加 Authorization。schema 從未接收憑證值或任意 headers；控制 writer 的派送／agent 的查詢也不帶 key 或憑證檔內容。

首版 `adapter_revision="openai-chat-v1"`、`rate_accounting_revision="reserved-window-v1"`。estimator 是部署登記且能處理該模型、完整 messages/tools 的可信實作，revision 不可重用為另一種算法；不認得就 `config_invalid`，不能只相信 caller 的估值。各 endpoint 採用的模型／估算器能力須在發布時驗完，未知 provider 不能套用此 adapter 冒充相容。

`remote_concurrency_policy="estimated_release"` 對應 S-304 的估計釋票，不提供遠端硬 concurrency 保證。要求確切終止證據的部署不能選這個設定；它需要後述待決的 provider 查證 adapter。範例的 8 秒停機、60 秒 uncertain hold、16 MiB 回應上限只是示例可配置值，不替平台或所有模型定死預設。

**Given** 兩 endpoint 引用同 scope，**When** 只剩一席，**Then** 控制端只能准入一個。**Given** 設定有不存在的 credential／estimator，**When** 發布或準備呼叫，**Then** HTTP 前拒絕；不退回 agent 的 key 或 env。

## P-403．請求與 messages 快照〔建議預設，未拍板〕

LLM job 的 `payload_ref` 指向 [llm-request](schemas/llm-request.schema.json) 根／`$defs/Payload`。完整最小例在 [request.minimal](examples/llm/request.minimal.valid.json)：

```json
{"version":1,"endpoint_id":"ep_1","model":"small","messages_ref":{"key":"messages_minimal","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":128},"input_tokens_estimate":8,"max_output_tokens":16,"request_timeout_ms":10000}
```

此段 BlobRef 為形狀示意；examples 中該 messages 引用的 bytes／hash 對得上實際範例檔。`stream` 可省，實作補 false；明填 true 拒絕。URL、key、scope、owner、run、priority 與 retry 上限均不得塞入 payload。retry_class／max_attempts 由 JobDraft／可信政策處理，LLM 初值為 never／3。

`messages_ref` 引用 [llm-messages](schemas/llm-messages.schema.json) 根：

```json
{"version":1,"messages":[{"role":"user","content":"回覆 OK"}]}
```

`messages` 非空；可省 `tools`，省略等同空。system／user 的 content 是字串；assistant 是 `$defs/AssistantMessage`，content 可 null，但 null 必須伴隨非空 tool_calls；tool 是 `role,tool_call_id,content`。工具定義是 provider 的 `type:function`、`function:{name,description,parameters}`，parameters 引用 `agent-tools.schema.json#/$defs/ToolSchema` 且根必須 object。不傳 exec_ref 或本地 argv 給 provider。[完整工具往返例](examples/llm/messages.tools.valid.json) 含 function.arguments 的 JSON 字串及配對 tool 回應。

A-302 的來源、被省略材料、context policy revision 由 agent-content 保存；此 blob 保存**實際要送出的 messages/tools**，不能把 history 陣列當成完整 context。控制端先驗 BlobRef、消息配對與工具 schema，再對完整內容重算 input 估額；要求輸出與模型上限也要檢查。缺材料／必帶材料超限不偷偷截 JSON 或先占票。排隊後不重讀可變 agent home。

同一 assistant 的 call ID 不重複；tool 回覆必須配上先前未完成的 call，配對順序按模型要求。provider 回的 function.arguments 仍是字串；本篇定義的解碼映射為 `call_id=id`、`name=function.name`、`arguments=嚴格解析 function.arguments 所得的 object`。下一 tick 的語意 adapter 執行此純轉換，拒絕重複 key／非有限值／尾隨資料／非 object，按 A-401 驗 manifest，才可派工具；此轉換不自行執行工具。格式不合 C-01 的 call ID 不改名、不截短，保留原始回覆並交 A-401 無效回覆流程。

**Given** [stream 反例](examples/llm/request.stream.invalid.json) 或 [帶 key 反例](examples/llm/request.injected_key.invalid.json)，**When** 導入，**Then** `invalid_record`、沒有 HTTP。**Given** [未配對但 schema 合法的 tool message](examples/llm/messages.unpaired_semantic.valid.json)，**When** 語意驗證，**Then** 拒絕；schema 合法不代表 messages 可送。

## P-404．工具投件的內部 spool〔建議預設，未拍板；依 P-011 暫定 1〕

工具 → 非特權入口 → 控制 writer，使用 P-003 的每 UID 隔離布局。可信 launcher 在啟動該工具時登記 `channel_id → authenticated sender、parent tool attempt、agent、run`，給工具自己的 entry 目錄。每次工具執行的子通道各自綁定，父目錄、綁定與回覆目錄由管理者保護；工具不能自行登記、改 owner 或把 channel 名稱當授權。launcher 注入唯一一個工具發現用變數 `AOS_LLM_ENTRY_DIR`：型別為非空絕對路徑，沒有預設，讀取者為本次工具及其同 UID 子程序，可向該子程序繼承；未注入表示沒有此投件通道。值為 `<entry_root>/<channel_id>`，launcher 覆蓋工作 env 的同名值，不能讓工具聲稱另一個通道。此變數不含 key、控制 socket 或 scope，也不拿環境字串作憑證。工具仍按原固定 argv 和 arguments stdin 啟動，不新增人用 CLI。同 UID 程序仍是同一安全主體，這不宣稱隔離同 UID 的兩支工具。

工具先透過 B-505 導入 messages blob，再將 [ToolSubmission](schemas/llm-request.schema.json#/$defs/ToolSubmission) 寫入 `.tmp/<delivery_id>.<nonce>.tmp`，依 P-004 完整 fsync／同 filesystem 不覆蓋 rename／目錄 fsync，發布至 `<entry_root>/<channel_id>/requests/<delivery_id>.json`。非特權入口以 sender 權限打開普通檔、限 256 KiB 快照，再導入 `<spool_root>/<channel_id>/requests/`。symlink、特殊檔、未知欄位、不存在或跨 owner 的 BlobRef 都拒絕。

完整最小 [tool-submit.minimal](examples/llm/tool-submit.minimal.valid.json) 是 `version,request_id,payload`，沒有自報 run／attempt。首次接納前，控制端核對綁定的 tool attempt、run 仍准許新增工作，檢查 max_jobs／pending，保存 payload、job 意圖、來源 attempt 與收據。同交易配發 job ID／seq，owner、run 由帳本補上。此時不建立無准入的 HTTP attempt，也不占 scope。run 暫停／取消／unknown 屏障或父 attempt 已終結時不接受**新的**提交；已提交請求的重送先查原收據，不受父程序後來退出影響。

正常回覆符合 `$defs/ToolReceipt`，寫入同 delivery_id 的 responses，工具只讀：

```json
{"version":1,"request_id":"req_tool_1","accepted":true,"run_id":"run_1","job_id":"job_1"}
```

拒件完整例見 [tool-receipt.conflict](examples/llm/tool-receipt.conflict.valid.json)；不能解析 request_id 時為 null。入口包裝器若已完整輸出拒件仍算正常交換。此為內部版本化資料，不是 JSON-RPC envelope；P-005 的 `message` 包裝不再套一層。

去重沿 B-503，內部操作標籤固定為 `llm-inbox`，只用於 method＋params 的 canonical digest／去重鍵，**不是公開 method**。params 定為 `{agent_id,run_id,parent_attempt_id,payload}`，前三項取自可信綁定；鍵為 `(authenticated sender,target agent_id,"llm-inbox",request_id)`。不要把 delivery_id、發布時間或 .tmp 名加入 digest。同 ID、同原始 payload（包括原本 stream 是否省略）回原收據；異內容 conflict。dispatch 的預設展開摘要另見 P-406，不能混作入口去重摘要。

結果由控制端另行匯出 `$defs/ToolResult` 至 `<entry_root>/<channel_id>/results/<delivery_id>.json`；此目錄全由入口寫、工具只讀，沿 P-004 耐久發布，不能覆蓋 accepted 收據。它是 [完整 Job＋Attempt 快照](examples/llm/tool-result.minimal.valid.json)，附控制 writer 為該 job 配發的持久遞增 `notification_seq`，只在相應結果已持久後發布；同一 job 可能先有失敗／waiting，再有新 attempt。接收者核對 job／attempt 關係、`selected_attempt_id`，保留已看過的最高 notification_seq，不用較舊快照覆寫；這是投影次序，不是另造排程 seq。不能按檔名／snapshot_at_ms 判先後；同序號異內容回報 conflict，亦可按通知中的 attempt_id 呼叫既有 attempt.get 核對該 attempt。run.get／attempt.get 沒有承諾可查整份 job 清單，不假稱它們能反查未知的下一 attempt。未知到確定的晚到補全另發新 delivery，不覆蓋舊證據。門鈴可漏，控制端以出站意圖補交，工具可分批補讀自己的 results。

工具讀通知只是觀察；它不能提交 result.ack、刪除受管結果或代替 C-05 消費。權威結果仍按一般 LLM job 交同 run 的 tick；tick 判斷來源 parent attempt 後決定語意消費，不能把工具讀取當完成收尾。工具同步等待時仍占該工具的執行額度與 deadline，不占 tick claim；不得靠巢狀投件延長原工具 deadline。

**Given** [原投件](examples/llm/tool-submit.minimal.valid.json) 與 [同 ID 重送](examples/llm/tool-submit.replay.valid.json) 用不同 delivery_id，**When** 首次 DB 已提交但回覆丟失，**Then** 只建立一個 job、回同收據。**Given** [冒名 owner](examples/llm/tool-submit.spoof_owner.invalid.json)，**When** 驗證，**Then** 拒絕，不能借 B 的預算。**Given** 工具讀到 429 attempt 的通知，**When** job 仍 waiting，**Then** 不把本次失敗當成整個 job 已終局。

## P-405．控制端與服務的可信通道〔建議預設，未拍板〕

控制 writer → P-401 的服務 socket。雙方核對 `SO_PEERCRED`：服務只接受設定的 control_uid，控制端只接受設定的 service_uid；socket 父目錄也受管理者保護。入口的工具 spool 不連到這條通道。每個 seqpacket 恰好一份 UTF-8 JSON object，不用 LF 分框，不接受 batch，JSON 上限 256 KiB，`MSG_TRUNC`／`MSG_CTRUNC`／多餘 ancillary fd 一律拒絕，並關閉所有已收到的 fd。P-002 的重複 key、整數 token、未知 version 檢查仍要做。

消息符合 [llm-dispatch](schemas/llm-dispatch.schema.json)。共通的 `message_id` 是內部消息去重鍵，`attempt_id` 是業務鍵，`control_epoch` 是控制 writer 本次啟動的唯一 ID，`service_instance_id` 是本次服務 ID；generation 只在 dispatch／result 帶原 attempt 的世代，不拿 tick 的最新 generation 否決合法舊 LLM 結果。peer 驗證成功後才使用這些 ID，JSON 不自授權。

`dispatch` 唯一附 **一個** `SCM_RIGHTS` fd：對應 payload.messages_ref 的已驗證、不可變、唯讀普通檔，大小／摘要須吻合。它不是檔案路徑，也不把本機 fd 數字放 JSON。控制端送出後關閉自己的這次傳送副本；接收者核對型別／唯讀權限、限長讀完並關閉；錯誤或重複 dispatch 收到的多餘副本也立即關閉。其他消息帶零 fd。大結果經 B-505／storage 的受控導入另取 BlobRef，不在此 socket 塞 provider 本文。

每個方向先保存有界 outbox，再通知；服務只記自己的派送／閘門／回報證據，不修改控制 SQLite。其 state_root 0700、紀錄 0600，由服務 UID 持有，內容與回報 blob 計容量，不是無限診斷庫。跨 UID 由受控導入／查證通道交控制端；不能把服務 state_root 開給 agent。控制 ack 只在自身交易與必要材料耐久後回；ack 本身不要求再 ack，丟失便重放原消息。相同 message_id 同 canonical 完整消息回原回覆；異內容 `conflict`。fd 不入摘要，messages_ref 的 hash／bytes 入摘要且重新核對 fd。

**Given** [dispatch.minimal](examples/llm/dispatch.minimal.valid.json) 附正確 fd，**When** 持久接收，**Then** 回 [ack.minimal](examples/llm/ack.minimal.valid.json)，只表示接收，尚未 HTTP。**Given** [同消息重送](examples/llm/dispatch.replay.valid.json)，**When** 原件已在 processing，**Then** 不啟動第二 adapter。**Given** [過期 epoch 形狀例](examples/llm/dispatch.stale_semantic.valid.json)，**When** 語意核對，**Then** 拒絕，即使 schema 合法。

## P-406．全額准入、sent 閘門與取消競爭〔建議預設，未拍板〕

context 已完整保存後，控制 writer 重新估 `input_tokens_estimate_verified`；`reserved_tokens` 為這個估額加 max_output_tokens。scope 取 endpoint 設定。全部 scope 的 window／held／concurrency、run budget 與服務本地容量一起檢查；任一不足零占票。建 attempt、持久 held reservation 與派送意圖後，才送 `$defs/Dispatch`。held 的預設租期 30000 ms 到期只是要核對 launcher，不能看 expires_at_ms 就釋放。

`request_digest` 是 RFC 8785 後 SHA-256，材料固定為 `{payload,config_revision,adapter_revision}`；payload 的 stream 先展開為 false，其餘欄位不改，messages 的 bytes/hash 已在引用內。同 attempt 的設定、messages、model／endpoint 不可換。它是代發內容摘要，不取代 P-404 的原 request digest。

服務驗設定、messages、限額、取得本機執行位置後，發 [sent_request](examples/llm/sent-request.minimal.valid.json)。控制 writer 同交易核對取消／暫停屏障、原 held、當前 epoch 與 dispatch 摘要，保存 `sent_at_ms`、`deadline_at_ms=sent_at_ms+request_timeout_ms`、gate_id 及 sent_grant 意圖，把 reservation 轉 sent，**提交完成才回 [sent_grant](examples/llm/sent-grant.minimal.valid.json)**。重送同一 grant 不能創造第二張票。

服務在唯一 attempt slot 內先耐久記錄 gate 消耗，再呼叫 adapter 一次。重複 grant 只回查原 gate，不再 HTTP；grant 在斷線／重連後不能憑一段記憶重執行，先核對本機耐久消耗證據及控制狀態。新 service instance／control epoch 絕不重用舊 grant。epoch/instance 的當代限制適用 dispatch、sent_request、sent_grant 與新取消命令；舊 Report 的恢復導入依 P-408，不能一概當過期指令丟掉。從 grant 到實際 HTTP 的持久消耗窗口若崩潰，也可能只能判 unknown，不承諾遠端 exactly-once。HTTP deadline 已開始，傳送／內部準備時間不能重新加一段完整 timeout；延遲抵達且 deadline 已過的 grant 不得開始 HTTP，服務回報可驗的未送證據並關閉 gate；運行中按經過時間判斷，跨重啟按 B-603 對帳。

控制端先保存取消意圖，再送 [cancel](examples/llm/cancel.minimal.valid.json)。服務關閉送出 gate，停止本機等待／連線，以 [cancel_ack](examples/llm/cancel-ack.minimal.valid.json) 回傳 `gate_closed`、`local_connection_closed`、`remote_state`；cancel_ack 可表示本機尚未關完，後續回同 cancel_id 的較新消息補清空證據。cancel_id 相同不重做取消，矛盾證據不得覆寫。sent 與 cancel 以控制交易順序決定：cancel 先提交就不發 grant；sent 先提交而不能證明從未送出，不能宣稱遠端已取消。

**Given** held 到期且有可信未放行、程序／連線已清空證據，**When** 對帳，**Then** [released reservation](examples/llm/reservation.released.valid.json) 配 [ReleaseEvidence](examples/llm/release.minimal.valid.json)，不扣成本。**Given** sent 持久後、grant 回覆前或 gate 消耗後崩潰，**When** 沒有確切未送證據，**Then** uncertain／unknown，不能重放 HTTP。**Given** cancel 在 sent 前提交，**Then** 沒有 HTTP，結果可用 [canceled_unsent](examples/llm/report.canceled_unsent.valid.json)。

## P-407．一次 HTTP adapter 與 provider 映射〔建議預設，未拍板；依 P-011 暫定 3〕

服務內建函式的邏輯介面是 `call_once(已驗 dispatch, messages 值, 固定 endpoint/model 設定, 憑證句柄, 已消耗 gate, 剩餘 deadline, 有界結果 sink)`。只有函式內 HTTP client 看得到解出的 token；回傳值是 P-408 的材料與 transmission 證據，不自行 commit、retry、換 endpoint、跑工具或改 history。SDK retry 必須設零，禁止 HTTP redirect 自動重送 POST／憑證，也不按 proxy env 改目的地。

`POST <base_url 去掉尾端 />/chat/completions`，`Content-Type: application/json`，有 credential 才加 `Authorization: Bearer <token>`。base_url 是管理者設定的 API 基底，例如 `https://provider.example/v1`，不能含 userinfo、query／fragment 或重複 `/chat/completions` 尾段；這些語意在設定發布時驗。HTTP body 依 llm-messages 的 `$defs/ProviderRequest`；[完整檔案例](examples/llm/provider-request.minimal.valid.json) 如下。它是 provider wire，不加 aos version：

```json
{"model":"provider-small","messages":[{"role":"user","content":"回覆 OK"}],"max_tokens":16,"stream":false}
```

model 由設定映射；messages 原序送出；非空 tools 才送；輸出上限只寫設定的 `output_token_field`（max_tokens 或 max_completion_tokens），不能同時送兩個，不能讓 caller 覆蓋。非串流、一次 choice 的基線沿 proto5；超出此文字／function call 子集的 provider features 不作默認透傳。上行工具 parameters 已按 A-401 子集驗，不因 provider 接受更多 JSON Schema keyword 而放寬。

provider 原始回應保存在有界 blob。[成功原文檔](examples/llm/provider-response.minimal.valid.json) 依 llm-result 的 `$defs/ProviderSuccessBody` 作抽取前檢查；此 schema 明許外部 vendor 欄位，標準 assistant／usage 仍須分別驗證。例如成功本文可為：

```json
{"choices":[{"message":{"role":"assistant","content":"OK"}}],"usage":{"prompt_tokens":8,"completion_tokens":1,"total_tokens":9}}
```

HTTP 2xx 先驗完整本文是 JSON object、`choices[0].message` 是 object；取第一個 choice。沿 proto5 的正規化順序：去掉空 tool_calls，再把無 tool_calls 的 null content 改成空字串。原始 response_ref 不受改動；標準 assistant 投影只收 llm-messages 的字段，provider 額外欄位留在原文，不混進關閉未知欄位的 aos 物件。這是特定 adapter 的抽取規則，不是全域忽略未知欄位。

HTTP 完整成功而 message 不合法，保留完整原文、assistant=null、Error=`invalid_record`，由 A-401 的回覆格式計數處理，服務不重問。原生 provider tool call ID 不合 C-01 也如此；function.arguments 字串的 JSON／工具參數語意由 agent 驗證，服務不擅自修好後派工。provider 拒絕／非 2xx 保留結構化錯誤及 bounded 原文；429 用 P-410。其他錯誤不新增 C-04 code，具體原因放 details。

**Given** provider 返回空 tool_calls 與 null content，**When** 正規化，**Then** 得空字串 assistant，但原始 blob 仍保留原 bytes。**Given** response 的 call ID 含斜線或整體格式錯誤，**When** 轉換，**Then** 不派工具；agent 按 A-401 計數，連兩次無效才依正本進 needs_attention。**Given** 一次 500，**When** adapter 結束，**Then** 不在 client 內偷偷重送。

## P-408．可信結果、原文與完整性〔建議預設，未拍板〕

[llm-result](schemas/llm-result.schema.json) 根／`$defs/Result` 是 attempt 的結果材料，含 endpoint/model、adapter revision、request_digest、HTTP status、response_ref、response_complete、truncated、assistant、usage_ref、retry_after、error 與時間。[最小成功材料](examples/llm/result.minimal.valid.json)、[429 材料](examples/llm/result.rate_limited.valid.json)、[截斷材料](examples/llm/result.truncated.valid.json) 都是完整例。raw response_ref 是 provider 本文 bytes，不是 stdout；其大小上限由設定與 B-505 的導入上限共同限制。HTTP headers 不整包保存，只抽出有界的 Retry-After 等已定證據，絕不存 request Authorization。

adapter 的傳輸讀取必須有界；到上限就保存已有部分、truncated=true、response_complete=false、assistant=null。收到完整本文但 JSON 不合法與「尚未收完」是不同失敗：前者有確定回應證據、按無效回覆處理；後者若沒有明確未處理證據，可能已在遠端做完，須保留 unknown；[已確認 429 但本文截斷的例子](examples/llm/result.rate_limited_truncated.valid.json) 仍可按 S-303 記確定失敗，不能僅因錯誤本文被截斷就抹掉該證據。模型 finish_reason=length 也不等於 bytes 被截斷：完整 HTTP／JSON 仍完整，模型語意是否可用交給 agent。

服務先經 storage 的受控 blob 導入保存原文、usage 與 Result 材料，取得控制端可驗的 BlobRef，然後送 `$defs/Report`，亦是 llm-dispatch 的 `type=result` 分支。所有導入都綁原派送 attempt／owner，服務不能拿任意 agent_id 寫另一份帳。[成功 Report](examples/llm/report.minimal.valid.json) 的 Outcome.result_ref 指向 Result blob；這個 Result 自己不內嵌 Outcome，沒有自引用 hash。

Report 必填 `transmission:not_sent|response_received|possibly_sent`、`local_connection_closed:true`。只有本機 HTTP 已清空才發完成回報；清空中先用 cancel_ack。Result 的 error 與 Outcome.error、Report.usage_ref 與 Result.usage_ref 必須一致，所有 attempt、revision、digest 對回原派送。succeeded 要求完整可驗 assistant 與已處理的 usage；unknown 保留 result_unknown 及部分 result_ref，不能把片段當 final。未知成本但有完整回覆的政策另列 P-414，不假裝 provider 必回 usage。

控制端驗可信服務身分及引用後，同交易持久 attempt 證據／Outcome、用量、ready 與 result 收據，才回 stage=result 的 ack。服務在 ack 前保留原 outbox 和材料；丟回覆便重送 [原 Report](examples/llm/report.replay.valid.json)。相同確定終局同摘要只回原收據，異內容 conflict；不能由工具 stdout 或普通投件偽造 Report。查詢／結果匯出只帶 owner 有權讀的內容，不匯出設定或 key。

控制端重啟後，舊 Report 只能走可信恢復導入：當代 llm-service 在停止新派送的恢復階段讀原耐久 outbox，沿 P-405 同一 socket、零 fd 送出原 `$defs/Report`，核對其舊 instance、epoch、attempt、摘要與原控制派送鏈，再交當代 writer 對帳。peer 仍須是當代受信任服務 UID；舊 ID 在此只標記歷史證據，不授予新放行權。它不是在新 socket 重放舊 grant，也不要求舊服務再次送出 HTTP；writer 對原 message_id 回原收據或保存新導入收據，回覆仍為 P-405 的 stage=result Ack，ack_for 與 instance／epoch 保留被確認的舊消息識別，沿當代連線送達恢復程式，才標 outbox 已確認。

unknown 是暫定事件；可信晚到完整證據可以補全原 attempt，保存舊 unknown。若 job 已選新 attempt，舊結果只補證據／實際費用，不覆寫新 selected outcome。晚到資料仍須通過原 request_digest、服務證據鏈與帳本綁定，不能接受舊 socket 的任意 grant 或普通使用者造結果。

**Given** [尚未清空的反例](examples/llm/report.not_closed.invalid.json)，**When** 回報，**Then** 拒絕完成，不回收本機名額。**Given** [截斷卻自稱完整](examples/llm/result.false_complete.invalid.json)，**Then** schema 拒絕。**Given** Report 先持久、ack 丟失，**When** 重送，**Then** 一份終局、一份結算，不要求 provider 再回答。

## P-409．usage、reservation 與 run 結算〔建議預設，未拍板〕

[llm-usage](schemas/llm-usage.schema.json) 是版本化計量，不能直接把任意 provider usage object 當共通帳。它保存 adapter／estimator revision、attempt_id、`source:provider|estimated`、prompt／completion／total tokens、入場 `tokens_estimate`、可 null 的 raw_usage_ref 及 observed_at_ms。完整有效且可比對的 provider 整數計數才標 provider；缺值／不合整數／含不支持維度時保留原文與可知欄位、標 estimated，不用零代替未知。相容 profile 要求 total=prompt+completion，其他計費語意須另一版 adapter。[正常 usage](examples/llm/usage.minimal.valid.json) 是 8+1=9；[未知估額](examples/llm/usage.unknown.valid.json) 是三個 null、estimate=24。

[llm-reservation](schemas/llm-reservation.schema.json) 根／`$defs/Reservation` 沿 S-302：attempt_id、全部 scope_ids、state、reserved_requests=1、reserved_tokens、created_at_ms、expires_at_ms 必填；sent_at_ms／usage_ref 可省預設 null。五態完整例為 [held](examples/llm/reservation.held.valid.json)、[sent](examples/llm/reservation.sent.valid.json)、[settled](examples/llm/reservation.settled.valid.json)、[uncertain](examples/llm/reservation.uncertain.valid.json)、[released](examples/llm/reservation.released.valid.json)。released 只代表有未送證據而撤票；429 是一次已送、已知未處理的失敗，結算該次 reservation，不抹掉 attempt。

`$defs/Settlement` 是控制 writer 保存的**單 attempt 貢獻快照**，不是客戶端要求加減總帳的指令。[結算例](examples/llm/settlement.minimal.valid.json) 把 reserved 24 移為 known 9，uncertain 0；run 的 counters 是所有 attempt 貢獻與可信 job／attempt 計數的合計。重放用 attempt_id＋usage 的 canonical digest 去重；usage_digest 是 RFC 8785 的 usage record SHA-256，不能拿 raw blob 的檔案排版摘要替代。相同 usage 同摘要忽略，異摘要 conflict；unknown→實際 usage 的合法補全由控制交易核對既有暫定狀態、舊 usage 摘要與原 attempt 證據鏈後，替換原暫定貢獻並保留舊事件，不再累加一次；Settlement 不另收 caller 自報的替換指令。真用量超估也照實記，不能把數字削回預留值。

成本帳與速率帳分開。`reserved-window-v1` 在 sent 後保守保留這次 reserved_requests=1 與完整 reserved_tokens 到 scope window 到期；完整結果輸出短或 429 不退回這份速率消耗。成本只記實際已知 tokens，未知估額仍留 tokens_uncertain；明確未執行且無計費證據的 429 成本為 0。provider 特殊速率算法要改版，不默默退票。未送取消／確切未放行失敗可將 reserved 歸零；sent 後 unknown 把 reserved 移入 uncertain。uncertain 的遠端名額到期釋放，不清掉估算成本或 unknown 證據。

run 的 max_jobs、max_llm_attempts、max_tokens_estimate、max_elapsed_ms 及其 counter 沿 S-306，由 control-state 持有，不再造可寫預算。每一個建成的 LLM attempt（含 429／unknown）都計次；工具巢狀請求也算同 run。餘量不足便停止新工作、budget_exceeded／needs_attention；已在途結果仍保存，不能為了不超額丟真實 usage。

**Given** [usage 重送](examples/llm/usage.replay.valid.json) 三次，**When** 入帳，**Then** known 仍只有 9，scope window 保留 24。**Given** [provider 計數缺值](examples/llm/usage.missing_actual.invalid.json)，**Then** 不可標 provider。**Given** run token 不夠但 scope 足夠，**When** 准入，**Then** 兩邊都不 hold；超估的晚到真用量仍照實保存。

## P-410．429、Retry-After、cooldown 與有限重試〔建議預設，未拍板；沿 S-303〕

429 是明確未處理的限流；其他狀態只有特定版本 adapter 有明確未處理證據時才可用相同分類。openai-chat-v1 首版只把 429 放入此例外，不把一般 5xx／timeout 歸進來。Error 可用 quota_exceeded、retryable=true，HTTP status 與證據仍留 Result；retryable 本身不是重派授權。

Retry-After 僅接受 HTTP 的非負整數秒或可解析的 HTTP-date，解析後換成 epoch ms；過去日期以 received_at_ms 為下限。超整數範圍、負值、無效／相矛盾多值視為無有效提示，保留有界 raw 字串與 due=null。有效值不為了方便截短成 60 秒；超長但有效的等待可被 run elapsed budget 截止，不能提前送出。

控制端保存 `$defs/Backoff`：failed attempt、ordinal、scope_ids、明確未處理分類、evidence_ref、解析後 retry_after_due、base_delay、jitter、next_due、cooldown 與記錄時間。[有效 2 秒提示例](examples/llm/backoff.retry_after.valid.json) 的 next_due 不早於 due；[無提示例](examples/llm/backoff.fallback.valid.json) 為 `min(60000,1000*2^(ordinal-1)) + 137` ms。jitter 在 0～250 內一次產生、持久後不重抽，計算須防整數溢位。cooldown 取既有值與本次下限的較晚者；共用 scope 下一次派送不得早於它，獨立 scope 照常前進。

只有控制排程能在未達 max_attempts／run budget 且無屏障時把 job failed→waiting，到期再建新 attempt、新 reservation。LLM 初值 max_attempts=3，retry_class=never 也可在此唯一例外重試；第三次仍 429 就 job failed。其他非 2xx 明確失敗按一般 retry_class；可證明未送的連線建立失敗可按 safe 重試。可能已送出的斷線／無完整回應不是 safe 的重試理由。

**Given** mock 依序三次回相同 429 證據，**When** 控制端採 never／3，**Then** 最多三次 HTTP，每次都有新 attempt 和持久退避，第三次終止。**Given** 改回 500 或送出後斷線，**When** never 政策處理，**Then** 不適用例外，沒有自動第二次呼叫。**Given** 重啟時 jitter 已保存，**Then** 不重新抽短等待。

## P-411．取消、unknown 與重啟〔使用者方向 2026-09-29，裁定 7；細節為建議預設〕

sent 前取消有可信 gate 關閉、從未送出、本機清空證據才可 release。sent 後取消只停止本機等待／連線，不能用 cancel_ack 宣稱遠端停止或零費用。沒有完整可信結果時 [Report 為 unknown](examples/llm/report.unknown.valid.json)、reservation uncertain、run needs_attention，結果與估算成本保存。普通 timeout、resume、讀走結果或重新啟動都不是再次呼叫的授權。

本機 HTTP 名額以連線確定關閉為釋放依據；遠端不確定名額另外記 `$defs/UncertainEvidence`。[完整例](examples/llm/uncertain.minimal.valid.json) 的 remote_release_at_ms 是 request_deadline_at_ms+uncertain_hold_ms，不是從收到取消的時間重算。到期可釋放估計的 remote 名額，record 與 tokens_uncertain 仍在；要求遠端 concurrency 硬保證的部署不能用這個估計釋放模式，只能等可查證終止或人工處置。

重啟先停新派工、清空 B-603 受管範圍，核對服務 instance／control epoch、派送與 gate、持久 Result／Report／ack。有可信已發布結果者導入一次；沒有可信結果又不能確證從未放行者 unknown，不接續孤兒 adapter、不因舊 grant 重送 HTTP。確定未放行的例外須有 gate 證據與清空事實，依 B-603／retry_class 處理，不能僅靠 sent_at_ms 缺欄位判未送。

人工決議只走 S-401 的既有 run.resolve，retry 必填 allow_duplicate_effects=true、new_max_attempts 與必要的 clear_cancel_requested；清空舊本機工作後才建新 attempt。舊 unknown／費用風險不消失。LLM 服務不接受自己定義的 resume／retry 指令。

**Given** provider 可能做完，但回應前斷線或 WSL 整台消失，**When** 恢復，**Then** 沒有自動第二次 HTTP。**Given** remote hold 過期但沒有 provider 終止證據，**Then** 可解除估計名額但仍 unknown、仍保留估額，不能聲稱遠端已停。

## P-412．失敗、拒件與三層驗收〔建議預設，未拍板〕

領域 Error 一律引用 control-common 的 Error，數碼映射依 C-04；內部交接只有 Error，不另造 JSON-RPC 整數 code。可辨識的協議拒件用 [Reject](examples/llm/reject.minimal.valid.json)，原 message_id 無法解析時不猜 attempt／owner，關閉違規連線並留下有界診斷，caller 以原消息重新核對。工具 spool 無可用 request_id 則以 delivery_id 配 request_id=null 的 ToolReceipt。無回覆一律是未確認，不等於未送。

控制區滿碟／EIO 不回假的 durable ack、不放行新 HTTP；服務盡力關閉在途連線、保留 B-404 最小證據，恢復按事實補報或 unknown。service outbox 的 rename 成功、inotify 或 stdout 文字都不是控制端已結算。blob 缺失／摘要毀損沿儲存正本使相關 run needs_attention，不能改讀另一份 prompt 再送。

aos 自有持久紀錄的可省 extensions 沿 C-01，不能改 owner／狀態；[extensions 正例](examples/llm/request.extensions.valid.json) 不進 provider body。schema 反例都放在本篇 [examples](examples/llm/)：`request.stream` 拒 true；`request.injected_key` 與 `tool-submit.spoof_owner` 拒未知欄位；`messages.null_without_call` 拒空 assistant；`usage.missing_actual` 拒把缺值說成 provider 計數；`result.false_complete` 拒截斷卻完整；`report.not_closed` 拒尚未清空便完成；`reservation.sent_without_time` 拒 sent 缺時間；`provider-request.two_limits` 拒同時送兩種輸出上限。`*.valid.json` 只表示 schema 應通過，`unpaired_semantic`／`stale_semantic` 故意留給第二層拒絕。

第一層驗 JSON／2020-12 schema、原始 token、byte 上限與 fd；第二層驗 peer、owner/run、parent attempt、scope、revision、messages 配對、各摘要與狀態轉移；第三層逐點注入崩潰，驗持久承諾。Result／Report／ToolResult 都要驗引用內容和對應關係，schema 通過不等於可信結果。範例中未附實體 provider／gate blob 的 a×64 引用只是形狀示例，不能當整合 fixture 的完整性證據。

**Given** 在來源 rename、接收快照、DB hold、sent commit、gate 消耗、HTTP 返回、blob fsync、result 交易、ack 各點殺程序，**When** 依原 IDs 重送／恢復，**Then** 每點不是「未放行且有證據」就是「原結果只導入一次」或「unknown 保留風險」，不靠沒有檔案猜成零成本重試。此處是協議驗收要求，並未宣稱已有實作通過故障注入。

## P-413．沿用 proto5 與改動理由〔主編補〕

沿用 [proto5 aos-llm/request](../../../proto5/spec/aos-llm/request.md) 的一次非串流 `/chat/completions`、第一個 assistant message、function.arguments 字串與兩步正規化；沿用 [cpu/messages](../../../proto5/spec/cpu/messages.md) 的投主人收件匣、request／response 同名配對、傳輸 ID 與請求 ID 分開。服務內一次 client 仍不寫 history、不跑工具。

proto6 明確不同：單一 aos 機器子命令取代 aos-llm executable；沒有常駐 CPU worker／可繼承 key env；不可變 messages_ref 取代啟動時重讀 agent home；version:1、關閉未知欄位取代 `_metainfo`／指示詞；B-402 rename＋fsync＋帳本修復取代 proto5 link/unlink 發布。結果是可信 Report＋Outcome＋usage，不是 stdout 的 assistant 或 stderr 的失敗文字；usage 寫不進去不能像 proto5 一樣當無事。timeout 按是否可能送出分 unknown／明確失敗；讀結果不等於 ack 消費，更不刪原結果。理由分別是 P-007、裁定 9、A-102／A-302、C-01、B-402、S-302／S-304 與 C-05。

**Given** 以 proto5 成功 stdout 作回歸材料，**When** 轉為本協議，**Then** assistant 意義不變，但必須另具原 attempt、可信結果與計量；不能把 proto5 的 exit 1 一律轉成可自動重試。

## P-414．待決、整合交界與現況〔主編補；建議均未拍板〕

**待決一：usage 缺失／部分可知的終局政策。** S-302／S-305 沒定「完整可用回答但 provider 沒有可用 usage」是否能立即成功。schema 能保存 estimated 與原文，但不藉此宣告成功政策已定。建議完整回答可以保存／交付，成本保留未確定估額，補得可信 usage 才轉 known；是否要擋 run 完成、缺 usage 是否最終轉估算成本，請整合者回 S-302／S-305 定義。此分支不能默認清零或當 failed 自動重問。

**待決二：工具巢狀 LLM 的 parent 關係。** 暫定 1 已授權投件、同 run 記帳，本稿以控制來源綁定 parent attempt、唯讀結果通知及 C-05 唯一消費閉合傳輸。正本未定父工具單獨失敗／取消時，要不要連帶取消已接納的子 LLM，以及 agent 如何把該結果與父工具的最終 stdout 作語意去重。建議保留 parent 關係供 agent-state 查詢、由明示政策決定連帶取消；不能只因父程序退出就默默丟結果、退成本或再次呼叫。run.cancel 的全 run 取消仍照既有規則。

**待決三：更廣 provider 能力。** 目前僅 openai-chat-v1 的文字／function call 子集；多模態、任意 sampling params、不同 usage 計費維度、provider 查終止證據、provider call ID 重新映射都未定。建議各加版本化 adapter／messages 格式與驗收後才啟用；本稿不聲稱所有 OpenAI 相容服務都符合所有限制。估算器的具體 tokenizer／上界算法由可信部署登記並版本化，實作前須證明涵蓋完整 body，不憑 estimator 名稱宣稱硬保額度。

整合者需改 README P-011 末尾仍把工具入口全部列待決的舊驗收，使其符合後加的「暫定 1」；P-012 llm 列宜明寫內部 spool。B-501 宜補內部 LLM 投件沿相同認證／耐久原則但不是公開 JSON-RPC method。A-404／S-301 可連回本篇的 messages／結果格式；S-302／S-305 需要上述缺 usage 政策，A-402／C-05 需要 parent 結果消費交界。本稿沒有改這些檔。

control-rpc 提供唯一 ID／BlobRef／Error／Outcome／Job／Attempt 及預算、查詢；不新增 methods。execution 的可信 launcher 提供不可由工具改寫的 channel→parent attempt 綁定、受保護的 AOS_LLM_ENTRY_DIR 注入、服務受管清空證據；需在 execution env 白名單補此交界。agent-state 引用 llm-request 根、llm-messages 根／`$defs/AssistantMessage`、llm-result 根，負責來源、配對、格式計數與語意消費；本稿反向只引用其 `agent-tools#/$defs/ToolSchema`，不重造工具 schema 白名單。storage 提供 BlobRef 導入／唯讀 fd／匯出與保留，不把跨 UID path 開放當解法；Report 不替它宣布消費或 GC。各篇可按這些公開片段接線；parent attempt 的 tick 可讀投影尚缺欄位，須由整合者決定放在 agent-tick 的交付 metadata 或其他控制投影，不能假稱目前已接通。本作者沒有修改其他人的 schema。

目前交付是正文、七份 schema 與本篇 examples；尚未有 llm-service 實作。驗收仍須由未來實作完成 owner／狀態與崩潰測試。**Given** 五份文件整合，**When** 檢查引用及權威，**Then** LLM 只有一套准入／結算、C-05 只有一個消費提交者，未決政策仍清楚標示。
