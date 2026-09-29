# 共用資料與提交契約

← [規格入口](README.md)｜[名詞](terms.md)

以下 C 節均為〔建議預設，未拍板〕。欄位是邏輯資料，不要求一欄一檔或指定 SQL schema；序列化與驗收必須保留其含義。權威資料由控制帳本寫入者保存，agent 提案不是直接改帳本的授權。

## C-01．基本型別與版本

所有識別採字串，匹配 `[A-Za-z0-9_-]{1,128}`，大小寫敏感；拒絕路徑分隔、空白及 `.`。所有持久紀錄必填 `version:1`。`*_at_ms` 是 UTC epoch 毫秒整數 >=0；持續時間為毫秒整數 >=0；世代與序號為整數 >=1；所有整數上界為9007199254740991；不接受 bool 代替數字。UTC 用於跨重啟時間點，運行中的逾時使用經過時間，不因牆鐘倒退無限延長。

未特別列「可省」的欄位為必填；本篇或各領域規格未列出的欄位拒絕，擴充只能置於可省 `extensions` object，預設 `{}`，不影響授權與狀態。未知 version 拒絕，不嘗試猜測。可省且允許空值的引用預設 null；空字串不是 null。跨篇另定 payload 也遵守這些規則。

驗收：Given `generation:true` 或 `version:2`，When 導入提交，Then 回 `invalid_record`，不更新 checkpoint 或派工。

## C-02．Owner 與 run

Agent registry 必填 `agent_id`、`uid`、`gid`（整數 >=0）、`groups`（整數陣列，去重）、`home`（絕對路徑）、`resource_domain`（ID）、`project`（object，含 `filesystem_id` ID 與 `project_id` 整數 >=1；profile 的 `quota_backend=none` 時為 null，見 [B-304](base/identity-resources.md)）、`status`（`enabled|disabled|retired`）。這些由管理者登記；普通 request 不得更改。registry另必填 `registry_revision:int>=1`、`profile_id:ID`。UID/GID須在profile允許範圍，拒絕UID0與daemon/kernel/管理者UID；不同 live agent 不得共用 UID；`generation` 初始 1，僅控制層遞增。

〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 B3〕Run 必填 `run_id`、`agent_id`、`state`、`created_at_ms`、`config_revision`（ID）、`input_ids`（非空 request_id 陣列）。`finished_at_ms`、`final_ref`、`error` 可省，預設 null；終局必須填 finished_at_ms，成功必填 final_ref，失敗必填 error。config_revision 對應不可變設定 bundle，由它引用工具、context policy 與模型設定，不是正在編輯的路徑；子版本可供查詢展開，不另存為 run 的權威版本欄位。可省 `config_changes`（換版紀錄陣列，預設 []）；設定更新在下一次 tick 開始時換上，依 [A-102](agent/configuration.md)。

驗收：Given A 的普通投件包含 B 的 uid，When 接口驗證，Then 拒絕無此欄位／冒名，不能以該值開程序；run 之後改配置，進行中的 tick 仍用原 revision，下一次 tick 依 [A-102](agent/configuration.md) 換版並留下換版紀錄。

## C-03．Job 與 attempt

Job 必填 `job_id`、`agent_id`、`run_id`（ID；僅maintenance tick可null）、`kind`（`tool|llm|tick`）、`state`、`payload_ref`（BlobRef）、`created_at_ms`、`seq`（正整數，控制帳本配發的持久遞增建立序號，排隊先後以它為準，見 [S-204](scheduling/admission.md)）、`retry_class`（`never|safe`）。可省 `ready_seq`（每次進入 ready 時配發）、`next_due_at_ms`、`selected_attempt_id`、`outcome` 預設 null；`priority` 整數預設 0，只有控制政策可填；`max_attempts` 正整數預設 1（kind=llm 預設 3，見 [S-303](scheduling/llm.md)）。新 job state=queued；每 job 同時最多一個非終局 attempt。

Attempt 必填 `attempt_id`、`job_id`、`agent_id`、`ordinal`（正整數，該 job 依次增加）、`generation`、`state`、`created_at_ms`。可省 `started_at_ms`、`finished_at_ms`、`execution_ref`（ID）、`outcome` 預設 null。reserved 只表示入場預留，不表示子程序／HTTP 已啟動。tick attempt 的 generation 決定其提案能否提交；工具結果先歸原 attempt，不能直接拿舊 generation 改現 checkpoint。

BlobRef 為 `{ "key": ID, "sha256": "64位小寫十六進位", "bytes": 非負整數 }`，指管理者控制的不可變內容；不是任意路徑。引用時核對大小與摘要。Outcome 為 `{ "status":"succeeded|failed|canceled|unknown", "result_ref":BlobRef|null, "error":Error|null }`，三欄必填。成功 error=null；其餘 error 必填；失敗可有部分 result_ref，但不得當成功消費。

unknown是保留的暫定判斷事件；可信晚到證據可把自身attempt單調補全為確定終局，保存舊unknown事件。若job已選新attempt，只補舊證據／實際usage，不覆寫新選定結果。確定終局才禁止異內容覆寫。

驗收：Given 重送相同attempt結果，When 導入，Then 只結算一次；確定終局異內容報conflict，unknown補全不是新重試。

## C-04．錯誤與 RPC 對應

Error 必填 `code`（ID）、`message`（字串最多 4096 字元）、`retryable`（bool）；可省 `details` object 預設 `{}`。穩定 code 至少含 `invalid_record|unauthorized|conflict|stale_generation|quota_exceeded|resource_exhausted|timeout|canceled|result_unknown|internal_error`。retryable 只提示可重試條件，不能越過 job retry_class 或未知副作用規則；唯一例外是 [S-303](scheduling/llm.md) 的限流回應：它視為確定未執行，可不受 retry_class 限制在 max_attempts 內重試，但仍不越過 max_attempts 與未知副作用規則。

JSON-RPC 固定 `jsonrpc:"2.0"`、`id:request_id`、`method` 字串、`params` object；操作映射見[通訊](base/transport.md)。收件回應 `result:{accepted:true,request_id,run_id}` 只代表持久接納，不是任務完成；run_id 對非run操作可 null；agent.submit另回input_seq。JSON-RPC `error` 必填整數 `code`、字串 `message` 與 `data:Error`；對應 invalid_record=-32602、unauthorized=-32001、conflict=-32002、其餘=-32000。解析錯誤 -32700，id=null；未知 method -32601，無可用 request id 時 id=null。

驗收：Given 接件成功後工具失敗，When 查詢原 run，Then RPC 接件仍是成功，run 結果是失敗，不修改當初 RPC 為另一種結果。

## C-05．Checkpoint proposal 與 fencing

〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 B1、A1 proposal 部分〕責任：tick 產生提案，控制寫入者驗證並提交。本節是 Proposal 資料、驗證與提交原子性的唯一規範來源；[B-403](base/storage.md) 定容量與導入，[A-502](agent/tick.md) 定 agent 語意 checkpoint。

Proposal 必填 `agent_id`、`run_id`（ID；maintenance tick 可 null）、`attempt_id`、`generation`、`expected_revision`（整數 >=0），另有下列兩部分。這是欄位責任的區分，序列化仍放同一個 Proposal object，不另加包裝層：

- **受限控制增量**：必填 `consumed_input_ids`（ID 陣列，可空）、`consumed_attempt_ids`（ID 陣列，可空）、`new_jobs`（JobDraft 陣列，可空）、`finish`（`none|succeeded|failed|needs_attention`）。可省 `history_append:array<HistoryEvent>`、`outputs:array<Output>`，預設 `[]`；各紀錄含 version:1，格式分別沿 [A-301](agent/memory.md)、[A-203](agent/input.md)。可省 `final_ref`、`error` 預設 null；成功 finish 必填 final_ref 且對應本次 outputs 的 final，失敗 finish 必填 error。`finish=needs_attention` 是 tick 自己發現、需要人處理時的提交路徑，只用於 agent 層能判定的原因（[A-401](agent/tools.md) 連兩次無效回覆、[A-302](agent/memory.md) `context_over_budget`），必填 error；控制層驗證通過後在同一交易把 run 轉 needs_attention，本次消費與歷史照常提交，不另派新工作（new_jobs 須為空）。unknown、blob 缺失、設定不可用等其他 needs_attention 由控制層依控制事實設定，不經提案。〔09-29 補，B4 拿掉 Proposal.phase 後的接縫〕這些是本次新增或消費，不是整份控制狀態的副本；agent.phase 是觀測值（[A-503](agent/tick.md)），不由提案寫入。
- **agent 語意 continuation**：必填 `checkpoint_ref`（BlobRef），引用 A-502 定義、帳本無法重建的 agent 決策與必要計數。history_append／outputs 不再放進 checkpoint；大段語意內容使用已驗證 blob 引用。

若歷史／回覆增量較大，可省 `append_ref:BlobRef|null`（預設 null）引用 `{version:1,history_append:array<HistoryEvent>,outputs:array<Output>}`，三欄必填；使用 append_ref 時，Proposal 內嵌的兩個陣列必須為空。導入並驗證後得到同一份邏輯增量，下文的 history_append／outputs、final_ref 對應及 maintenance 判空皆以展開後的內容為準。完整提案摘要包含 append_ref 的內容摘要；重送須保持原提案形式，不得換成另一種編碼冒充同份提案。大小依 B-403，不能藉 blob 引用繞過上限。

JobDraft 必填 `job_id`、`kind`（`tool|llm`）、`payload_ref`；可省 `retry_class` 預設 never、`max_attempts` 預設 1（kind=llm 預設 3）。Job ID 可由 tick 提案產生，但控制端驗證唯一與 owner／run 綁定；owner、優先級和 resource_domain 從可信 claim 派生。不能用 new_jobs 提交另一個 tick。

先把引用的 blob 導入可信內容庫，核對大小、摘要與可讀性，再以單一 SQLite 交易驗證目前 live claim 所屬 attempt、generation 及 expected_revision。普通推進須 run active 且無暫停／取消／錯誤屏障；屏障與提案競爭時，後提交的提案回 conflict，不丟棄已登記結果。消費 IDs 不得重複，須已交付、尚未消費且屬同 owner／run；結果須已登記，kind=tick 不得列入語意消費。控制層驗證 history／output 序號連續、引用存在及 run 歸屬，並依 [B-401](base/storage.md) 檢查 pending 額度；執行准入與 LLM 額度仍由排程檢查，提案不授予占票或啟動權。

驗證成功才同交易更新 checkpoint pointer、revision+1、輸入／結果消費事實及 cursor、歷史／回覆可見引用、job 意圖、run 狀態與提案收據，並依 [S-201](scheduling/admission.md) 重算 ready，保留併發新事件。失敗全部不生效，不得提前 ack 消費結果或派工；派工只由已提交意圖驅動。run 完成條件沿 [A-503](agent/tick.md)；控制層以套用本次增量後的帳本檢查 pending／未消費結果／unknown，不接受 tick 自報清空。pending 集合為本輪 kind=tool|llm 中「尚未確定終局，或結果尚未消費」的工作，不含當前控制 tick。

每個 tick attempt 最多提交一份 Proposal。相同 attempt／expected_revision／完整提案摘要重送回原收據，即使原交易已推進 revision 也不重新消費或派工；同鍵異內容回 conflict。未提交提案的舊 generation 回 stale_generation，過期 revision 回 conflict。run_id=null 的維護或空探查只可更新 agent 維護 checkpoint，finish=none，new_jobs、兩種消費陣列、history_append、outputs 均空，不建立未登記任務。

Blob 的受管副本與 home 同計入 agent project quota（啟用時，記帳政策依 [B-304](base/identity-resources.md)）；global 控制庫只存有界 metadata 及最小錯誤。可編輯的來源草稿不改已提交 checkpoint／revision；受控導入與唯讀匯出沿 [B-401](base/storage.md)、[B-505](base/transport.md)。重啟只採已提交 pointer；未引用 blob 依留存政策回收，不因發現 blob 或檔案時間較新就推斷已提交。

驗收：Given 提案同時消費工具結果、新增 LLM job、歷史與回覆，When 在 blob 發布至交易提交之間逐點中斷，Then 所有增量及 checkpoint 全不生效或共同生效，重送只回同一收據；舊 generation、跨 owner 消費、損毀 blob 或 pending 額度不足皆不得部分提交；大段回覆用 append_ref 後仍接受相同驗證與重送規則。Given 帳本仍有 unknown，When tick 只提交精簡 checkpoint 並宣告成功，Then 仍拒絕完成，不靠 checkpoint 的 pending 副本判定。

## C-06．最小例子與保留

```json
{"version":1,"job_id":"job_17","agent_id":"agent_a","run_id":"run_3","kind":"tool","state":"queued","payload_ref":{"key":"blob_9","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":120},"created_at_ms":1790000000000,"seq":42,"retry_class":"never"}
```

範例摘要僅示意。ID tombstone／去重摘要至少保留至run終局後30日（可配置正整數天）；期間不重用ID。未終局／unknown不自動到期清除；清理後保留摘要，過期查詢回gone。清理怎麼做、誰來做依 [B-404](base/storage.md)：跟著該 agent 的 tick 一起處理，過期的刪除或封存。

驗收：Given 終局結果已依保留政策回收但 ID tombstone 還在，When 重送同 request，Then 回原終局摘要或 gone，不建立新 run；未終局結果不被這個清理規則刪掉。
