# 共用資料與提交契約

← [規格入口](README.md)｜[名詞](terms.md)

以下 C 節均為〔建議預設，未拍板〕。欄位是邏輯資料，不要求一欄一檔或指定 SQL schema；序列化與驗收必須保留其含義。權威資料由控制帳本寫入者保存，agent 提案不是直接改帳本的授權。

## C-01．基本型別與版本

所有識別採字串，匹配 `[A-Za-z0-9_-]{1,128}`，大小寫敏感；拒絕路徑分隔、空白及 `.`。所有持久紀錄必填 `version:1`。`*_at_ms` 是 UTC epoch 毫秒整數 >=0；持續時間為毫秒整數 >=0；世代與序號為整數 >=1；所有整數上界為9007199254740991；不接受 bool 代替數字。UTC 用於跨重啟時間點，運行中的逾時使用經過時間，不因牆鐘倒退無限延長。

未特別列「可省」的欄位為必填；本篇或各領域規格未列出的欄位拒絕，擴充只能置於可省 `extensions` object，預設 `{}`，不影響授權與狀態。未知 version 拒絕，不嘗試猜測。可省且允許空值的引用預設 null；空字串不是 null。跨篇另定 payload 也遵守這些規則。

驗收：Given `generation:true` 或 `version:2`，When 導入提交，Then 回 `invalid_record`，不更新 checkpoint 或派工。

## C-02．Owner 與 run

Agent registry 必填 `agent_id`、`uid`、`gid`（整數 >=0）、`groups`（整數陣列，去重）、`home`（絕對路徑）、`resource_domain`（ID）、`project`（object，含 `filesystem_id` ID 與 `project_id` 整數 >=1；profile 的 `quota_backend=none` 時為 null，見 [B-304](base/identity-resources.md)）、`status`（`enabled|disabled|retired`）。這些由管理者登記；普通 request 不得更改。registry另必填 `registry_revision:int>=1`、`profile_id:ID`。UID/GID須在profile允許範圍，拒絕UID0與daemon/kernel/管理者UID；不同 live agent 不得共用 UID；`generation` 初始 1，僅控制層遞增。

Run 必填 `run_id`、`agent_id`、`state`、`created_at_ms`、`config_revision`、`tools_revision`、`context_revision`（ID）、`input_ids`（非空 request_id 陣列）。`finished_at_ms`、`final_ref`、`error` 可省，預設 null；終局必須填 finished_at_ms，成功必填 final_ref，失敗必填 error。revision 對應不可變快照，不是正在編輯的路徑。

驗收：Given A 的普通投件包含 B 的 uid，When 接口驗證，Then 拒絕無此欄位／冒名，不能以該值開程序；run 之後改配置仍引用原 revision（實作依 [A-102](agent/configuration.md) 選擇在 tick 邊界換版者，須留下換版紀錄）。

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

責任：tick 產生提案，控制寫入者驗證並提交。Proposal 必填 `agent_id`、`run_id`（ID；maintenance tick可null）、`attempt_id`、`generation`、`expected_revision`（整數 >=0）、`checkpoint_ref`（BlobRef）、`consumed_input_ids`（ID 陣列，可空）、`consumed_attempt_ids`（ID 陣列，可空）、`new_jobs`（JobDraft 陣列，可空）、`phase`（agent.phase）、`finish`（`none|succeeded|failed`）。可省 `final_ref`、`error` 預設 null。成功 finish 必填 final_ref；失敗 finish 必填 error。

Blob的受管副本與home同計入agent project quota（啟用時）；global控制庫只存有界metadata及最小錯誤。可直接編輯的來源草稿不改已提交的checkpoint／revision，詳見[儲存](base/storage.md)。

JobDraft 必填 `job_id`、`kind`（`tool|llm`）、`payload_ref`；可省 `retry_class` 預設 never、`max_attempts` 預設1（kind=llm 預設3）。Job ID 可由 tick 提案產生，但控制端驗證唯一與 owner／run 绑定；owner、優先級和 resource_domain 從可信 claim 派生。不能用 new_jobs 提交另一個 tick。

先把 blob 導入可信內容庫，再以單一 SQLite 交易檢查 live claim、generation、expected_revision；成功才一起更新 checkpoint pointer、revision+1、消費 cursor、job 意圖和 phase／run 狀態。失敗不做部分提交。run 尚有在途或未消費的 tool／llm 結果時禁止 finish=succeeded（不含控制tick）。重放相同 attempt／revision／digest 回同一提交結果；相同鍵不同內容報 conflict。一個tick attempt最多提交一份proposal；maintenance run_id=null只可phase=idle、finish=none及new_jobs空。未引用 blob 可在留存期後回收，不可因發現 blob 就推斷已提交。

驗收：Given blob 已發布而交易前崩潰，When 重啟，Then checkpoint 未前進，重放同提案只提交一次；舊 generation 提案回 stale_generation，不能產生新工作。

## C-06．最小例子與保留

```json
{"version":1,"job_id":"job_17","agent_id":"agent_a","run_id":"run_3","kind":"tool","state":"queued","payload_ref":{"key":"blob_9","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":120},"created_at_ms":1790000000000,"seq":42,"retry_class":"never"}
```

範例摘要僅示意。ID tombstone／去重摘要至少保留至run終局後30日（可配置正整數天）；期間不重用ID。未終局／unknown不自動到期清除；清理後保留摘要，過期查詢回gone。

驗收：Given 終局結果已依保留政策回收但 ID tombstone 還在，When 重送同 request，Then 回原終局摘要或 gone，不建立新 run；未終局結果不被這個清理規則刪掉。
