# 控制 RPC：收件、查詢、排程紀錄與待辦處理

← [共用約定與分工](README.md)｜[通訊正本](../base/transport.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)

## P-100．範圍、來源與 schema 入口〔主編補〕

本篇把控制 daemon、呼叫端 adapter、控制 writer 與 `aos-attend` 之間的機器交接寫明。行為依 C-01～C-04、C-06、B-401／B-402、B-501～B-504、B-603／B-604、A-201～A-203、A-505／A-506、S-101～S-104、S-201～S-204、S-306、S-401～S-405；[使用者裁定](../../notes/2026-09-29-verdicts.md) 優先。以下 argv、欄位編碼及例子均為〔建議預設，未拍板〕；P-011 的八項整合者暫定同樣不是使用者已拍板的產品承諾。本文不改變新訊息歸屬尚未定案、resume 可選、磁碟額度可選、重啟全殺、下一 tick 換設定等邊界。

八份 schema 都採 JSON Schema 2020-12，跨檔 `$ref` 相對於 `schemas/` 解析，不上網取 schema：

- [control-common](schemas/control-common.schema.json)：基本型別與 Error／BlobRef／Outcome／Run／Job／Attempt。
- [control-rpc](schemas/control-rpc.schema.json)：純 JSON-RPC envelope，尚未驗證 method payload。
- [control-handoff](schemas/control-handoff.schema.json)：檔案用的 version/message 包裝。
- [control-methods](schemas/control-methods.schema.json)：本篇十個 method 的 params/result 與完整 request/response。
- [control-config](schemas/control-config.schema.json)：可信部署、通道、容量、准入、停機與系統掛勾容器。
- [control-state](schemas/control-state.schema.json)：控制邏輯紀錄與查詢投影；不是 SQLite 實體 schema。
- [control-attention-policy](schemas/control-attention-policy.schema.json)：待辦 code 的處理表。
- [control-attention-action](schemas/control-attention-action.schema.json)：待辦執行批次與動作稽核。

基本型別只定在 common，別篇使用 `#/$defs/ID`、`BlobRef`、`Error`、`Outcome`、`Run`、`Job`、`Attempt`。範例全部在 [examples/control-rpc/](examples/control-rpc/)；文內 JSON 是完整的一份訊息，不是可省掉其他必填欄位的片段。摘要重複字母只作示意，實際內容另驗 bytes/sha256。下文共用 P-101～P-105 的啟動／傳輸／錯誤規則，不為每個 method 發明一支程序。

**Given** envelope 通過 control-rpc，**When** method payload、owner 或引用尚未驗證，**Then** 不得因此 accepted；只有本篇與所屬 payload schema、授權及持久提交全部通過才成立。

## P-101．控制服務怎麼啟動與停止〔建議預設，未拍板〕

systemd 以非 root 控制 UID 直接 exec 完整 argv：

```json
["aos","control-daemon","--config-fd","3"]
```

`--config-fd` 必填十進位 fd（>=3），不是要 daemon 按輸入路徑代開檔；啟動者預先開啟管理者保護的普通設定檔，僅把該唯讀 fd 繼承給 daemon。daemon 限 256 KiB 讀取一份 control-config JSON 至 EOF，驗證後關閉 fd；這不是經 JSON 傳 fd 數字給另一程序的協議。啟動時 stdin 關閉、stdout 不輸出協議，stderr 僅有界診斷交 journal；常駐交換用設定的 socket／spool。argv 未列的選項拒絕；無隱含 shell。此角色不讀任何 `AOS_*` 環境覆寫；部署以 argv 與設定為準，`PATH`／`LANG` 只供程序執行及診斷，不能提供 UID／owner／claim。控制設定及 socket 不繼承給 agent／工具，LLM key 不在控制設定中。

config 的五個准入上限 `max_tick_inflight/max_tool_inflight/max_llm_inflight/max_pending_jobs/per_agent_inflight` 必填正整數；control 容量保留政策亦必填，缺值不能猜。每 agent tick 至多一個；per_agent_inflight 計工具與 LLM 合計。只有可信管理者可設定通道 UID／principal／權限。系統掛勾容器引用 `agent-hook-registration.schema.json`，實際 stdin／執行及結果由 agent-state／execution 篇規定。設定檔不是公開 RPC，也不授權 agent 修改登記。

先取得單一 writer 排他鎖，再開帳本並進 B-603 恢復：暫停新派工，容許能讀到權威資料的診斷；分批核對非終局 attempts、閘門與可信結果，清空殘留程序。沒有可信結果又不能證明未放行者 unknown，不接續孤兒工作。已有提案提交收據的 tick 不撤回已提交 final；舊程序仍須清空才能放 claim。完成基本對帳後可開放無關 agent，不為巡檢啟動冷 agent。

正常停止由 systemd 的停止要求觸發，先停新准入、保存 queued/ready，再按 `stop_grace_ms` 等候及取消收尾；Linux 建議 30000 ms，WSL 建議不超過 8000 ms，均可配置。daemon 完成持久回報及正常停機才 exit 0；設定／argv 錯 exit 2；自身 I/O、鎖失敗、停止逾時或未清空 exit 125，保留未清空 attempts 證據。父程序看 wait 的信號狀態，不猜 `128+signal`；被 VM 殺死沒有完好退出碼，下一次按 B-603 恢復。

最小部署例（僅示範配置值，不是替部署決定併發）：
```json
{"version":1,"deployment":{"control_root":"/var/lib/aos/control","entry_root":"/var/lib/aos/entry","spool_root":"/var/lib/aos/spool","attention_dir":"/var/lib/aos/attention","rpc_socket":"/run/aos/control.sock","service_socket":"/run/aos/service.sock","helper_socket":"/run/aos/helper.sock","control_uid":980,"service_uid":981},"channels":[{"channel_id":"admin_1000","principal_id":"admin_local","uid":1000,"purpose":"control_rpc","agent_id":null}],"admission":{"max_tick_inflight":4,"max_tool_inflight":8,"max_llm_inflight":4,"max_pending_jobs":10000,"per_agent_inflight":2},"capacity":{"reservation_policy_id":"control_reserved_v1","reserve_bytes":16777216,"max_metadata_bytes":1073741824},"shutdown":{"stop_grace_ms":8000}}
```

`reservation_policy_id` 必須由可信部署解析成經 probe 驗證的容量保留機制；填 bytes 或換資料夾不代表已保留。control_uid/service_uid 非 root、互異且不得是 agent UID，實際部署需核對；LLM 專用 UID 由 llm-config 持有，亦不得與控制 writer 共用。channels 的 channel_id 必須唯一，tick_commit/tool_llm 通道必須綁已登記 agent，agent_id=null 只供可信管理者控制通道，principal_id 不是 payload 自報授權。capabilities 的 resume_needs_attention/resume_budget_increase 省略為 false，後者啟用須前者可用。system_hooks 每項是 `{hook,agent_ids}`，agent_ids=null 表示所有 agent，非空陣列表示指定集合；hook 本體只引用 agent-state 的登記格式。

**Given** daemon 在送出工具後重啟或 WSL VM 關閉，**When** 恢復找不到可信已發布結果，**Then** 記 unknown、保留副作用不明與取消屏障，不自動重派。**Given** 配置少了 max_pending_jobs，**When** 啟動，**Then** exit 2 且不派工作。

## P-102．socket 與 stdio adapter 的認證交接〔建議預設，未拍板〕

caller 可直接連設定的本機 Unix stream socket；入口取 SO_PEERCRED 的 UID 對照可信登記，解析目標 run／attempt 的 owner 後檢查該方法權限。控制 socket 只接受 JSON bytes，不接收 caller 隨附的 fd 或 host 路徑。管理者與 agent 同樣走權限檢查，payload 的 sender、uid、owner 宣告一律無效。root helper 的 SO_PEERCRED 白名單及可信 fd 通道另依 execution 篇，不公開成 RPC。

單次 adapter 由 caller 以自己的 UID 直接 exec：

```json
["aos","rpc-adapter","--socket","/run/aos/control.sock"]
```

`--socket` 必填絕對路徑，由可信部署交給 caller；adapter 不提權。stdin 讀一份原 JSON-RPC 至 EOF，上限 256 KiB；發送時壓成單行加 LF，stdout 回一份原 envelope（可尾隨 LF），stderr 有界診斷。socket 上每個 LF 結束一封，JSON 內 LF 必須跳脫，JSON bytes 上限不含分隔 LF；半封、一次讀兩封、讀取邊界都按 P-005 處理。可省 `--timeout-ms` 正整數，預設 30000，涵蓋連線、發送與回覆，按經過時間計；超時只表示未確認，不能合成 accepted。adapter 不讀 `AOS_*`，不傳憑證環境，關閉自行建立的 socket；其餘 fd 不傳給 server。

完整回傳合法成功或 error envelope 均 exit 0。argv／部署錯 exit 2；連線、I/O 或缺完整回覆 exit 125；合法啟動後 stdin JSON 錯，能回完整 C-04 error 時 exit 0。結果不明者仍用原 request_id 重送，不由包裝器退出碼判斷有無生效。

完整原 request 與 response：

```json
{"jsonrpc":"2.0","id":"req_pause_1","method":"run.pause","params":{"run_id":"run_3"}}
```

```json
{"jsonrpc":"2.0","id":"req_pause_1","result":{"accepted":true,"request_id":"req_pause_1","run_id":"run_3"}}
```

**Given** request 已送出但回覆前 socket 中斷，**When** adapter exit 125 並重送原 ID，**Then** 回原收據而非重做；若同 UID 工具嘗試 checkpoint.commit，仍須另驗 live claim，SO_PEERCRED 本身不授予提交權。

## P-103．每 UID 丟檔、耐久收據與重送〔建議預設，未拍板〕

sender 只向已登記 `<entry_root>/<channel_id>/.tmp/` 寫候選，依 P-004 發布至 `requests/<delivery_id>.json`；每通道綁定可信 UID/principal/用途，同 UID 可有多用途通道，不能因檔內自稱換 owner。回覆由入口匯出至同通道 `responses/<delivery_id>.json`，sender 唯讀。完整持久請求：

```json
{"version":1,"message":{"jsonrpc":"2.0","id":"req_pause_1","method":"run.pause","params":{"run_id":"run_3"}}}
```

完整持久回覆：

```json
{"version":1,"message":{"jsonrpc":"2.0","id":"req_pause_1","result":{"accepted":true,"request_id":"req_pause_1","run_id":"run_3"}}}
```

二者驗 control-handoff，內層再依方法驗 control-methods；含包裝檔案總長也不得超過 256 KiB。入口以 sender 權限開普通檔 fd、拒 symlink／特殊檔、限長快照，再交控制端純資料；root 不代開。sender 不能改 channel 父目錄或 responses。跨 UID 依受控 ACL／fd 交付，控制 spool 與帳本仍只允許可信寫入者。

控制端依 P-003 保存 `<spool_root>/<channel_id>/requests/processing/responses/done/failed` 各狀態（每個名稱是獨立子目錄）；只在快照及必要 DB/outbox 持久後回 accepted。done 是交接完成，不是工作成功；failed 是本次交接拒絕，不拿業務 failed 代替。`.tmp`、inotify 或 rename 尚不足以證明 accepted。跨 filesystem 重新在接收端發布，不能當成一次原子搬移。

去重鍵固定 `(authenticated sender,target agent_id,method,request_id)`；摘要材料精確為 `{"method":method,"params":params}` 的 RFC 8785 canonical JSON，target 由已授權目標解析。delivery_id、包裝、牆鐘不入摘要。相同鍵同內容回原收據，異內容 conflict；不同 ID 相同文字仍是不同請求。再次查詢新狀態用新 request_id；以舊 ID 重送查詢依 B-503 得原快照，不冒充即時結果。保留與 gone 依 C-06，結果被讀走不等於語意消費，result.ack 不存在。

**Given** 同一請求換 delivery_id 重送且原回覆丟失，**When** 對帳，**Then** input_seq／控制意圖只生成一次。**Given** rename、fsync、DB commit、回覆匯出各點中斷，**When** 重啟，**Then** processing 依持久索引重放，不憑留檔推定程序仍活或 job 成功。

## P-104．錯誤與共用紀錄〔建議預設，未拍板〕

Error、BlobRef、Outcome、Run、Job、Attempt 的必填／null／default 按 common；持久紀錄 `version:1`，嵌入 Error／BlobRef／Outcome 及原 RPC 不另加 version。schema 不會驗 UTF-8、重複 key、原 token 的整數型態或實際 byte 上限，解析器必須先做。未知欄位拒絕，只有明列 extensions 能擴充，不能藉 extensions 加權限。

RPC error.code 整數只用 C-04 對應，data 是完整 Error。解析失敗 id=null；可辨識合法 id 的未知 method 保留該 id。`retryable:true` 不是重派授權，未知副作用只能走可信補證或 S-401 處置。完整結構化失敗：

```json
{"jsonrpc":"2.0","id":"req_resume_1","error":{"code":-32002,"message":"此部署未提供重新驗證出口","data":{"code":"conflict","message":"此部署未提供重新驗證出口","retryable":false,"details":{"reason":"resume_unsupported"}}}}
```

unknown 是 attempt 的暫定證據，合法 Outcome：

```json
{"status":"unknown","result_ref":null,"error":{"code":"result_unknown","message":"送出後未取得可信完整結果","retryable":false}}
```

可信晚到證據可補齊同 attempt，保留舊 unknown 事件；已選新 attempt 時不覆蓋新結果、不重複結算。確定終局同內容重送忽略，異內容 conflict。B-103 底座 stdout／stderr 達上限截斷，ExecResult 固定為 failed/output_limit 且 truncated=true，不能由 OutcomeAdapter 改判成功；A-403 的模型可見 preview 裁切是另一件事。查詢保留原 result_ref／Error，不由控制 RPC 重定 ExecResult 欄位；[完整截斷查詢](examples/control-rpc/method-attempt-get.truncated.valid.json) 的 result_ref 指向可信 ExecResult。

**Given** 原 accepted 後 attempt unknown，**When** 查原收據及 run.get，**Then** 原收據仍是 accepted，後者有 result_unknown；缺可信帳本則回 internal_error 等結構化不可用，不從舊 log 推成功。

## P-105．十個 method 的共用規則〔建議預設，未拍板〕

方法名稱／授權正本是 methods.json（09-29 已撤除，協議篇待重做）。下列十種 params 都關閉未知欄位；request id 只收 C-01 ID 字串。control-methods 的各 `*Request`／`*Response` 用於整份 envelope；對 response 必須按原請求選對應定義，因為 response 不帶 method，不能只靠聯集猜屬哪種查詢。成功收據中的 request_id 必須等於 envelope id，run_id 必須等於授權目標（非 run 操作可 null）；這些跨欄位關係另做語意驗證。

普通方法不能指定 UID、priority、claim 或任意路徑。checkpoint.commit envelope 用 control-rpc，payload 引 agent-commit，完全由 agent-state 篇持有；不納入本篇十方法聚合。`result.ack`、`job.submit`、`llm.submit` 不在公開集合，未知 method 回 -32601。工具投 LLM 依 P-011 暫定走每 UID 內部收件處，以工具 attempt 推 owner/run/預算，不授權非 LLM 後續工作；格式只由 llm 篇定。

**Given** `{"jsonrpc":"2.0","id":"req_ack_1","method":"result.ack","params":{}}`，**When** 首版入口 dispatch，**Then** 回 -32601，不記消費、不回收結果；envelope 合法不代表方法存在。

## P-110．agent.submit：接納輸入〔建議預設，未拍板〕

可投該 agent 的 principal → 控制入口；params 是 agent_id 與 input_ref，先經 storage 的 blob import 得已驗證引用；本文不重定輸入本體，沿 agent-input。驗 AgentSubmitParams/Result；accepted 含 request_id、run_id、input_seq（正整數）。同一交易記輸入索引、run、ready 及收據，無法持久就不 accepted。S-101 的每訊息一個 queued run 仍為可替換預設，新訊息歸屬沒有因 schema 而變成使用者裁定。

```json
{"jsonrpc":"2.0","id":"req_input_1","method":"agent.submit","params":{"agent_id":"agent_a","input_ref":{"key":"input_1","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":32}}}
```

```json
{"jsonrpc":"2.0","id":"req_input_1","result":{"accepted":true,"request_id":"req_input_1","run_id":"run_3","input_seq":1}}
```

**Given** 收據前斷線，**When** 完整重送上述 request，**Then** 仍得到 run_3/input_seq=1。**Given** 同 ID 換 input_ref，**When** 再送，**Then** conflict；quota／容量滿則拒絕新收件，既有取消與查詢仍保留服務能力。

## P-111．agent.get、run.get：查目前權威投影〔建議預設，未拍板〕

owner／管理者 → 控制入口。agent.get params 僅 agent_id；result 用 AgentQuery，含 phase、generation、checkpoint_revision、當前 run_id/null、wait_reason、pending_jobs、最新 error/null、can_resume 及 snapshot_at_ms。run.get params 僅 run_id；result 用 RunQuery，含 Run、agent_phase、pending_jobs、inflight_jobs、wait_reason、snapshot_at_ms、budget_counters；預算／取消資料沿 Run 或對應投影，不另創 agent 可寫狀態。

```json
{"jsonrpc":"2.0","id":"req_agent_1","method":"agent.get","params":{"agent_id":"agent_a"}}
```

```json
{"jsonrpc":"2.0","id":"req_run_1","method":"run.get","params":{"run_id":"run_3"}}
```

完整最小查詢回覆如下（各自對應自己的 request id）：
```json
{"jsonrpc":"2.0","id":"req_agent_get_1","result":{"agent_id":"agent_a","phase":"idle","generation":1,"checkpoint_revision":0,"run_id":null,"wait_reason":null,"pending_jobs":0,"error":null,"can_resume":false,"snapshot_at_ms":1790000000000}}
```

```json
{"jsonrpc":"2.0","id":"req_run_get_1","result":{"run":{"version":1,"run_id":"run_1","agent_id":"agent_a","state":"queued","created_at_ms":1790000000000,"config_revision":"config_1","input_ids":["req_submit_1"],"input_seq":1,"budget":{}},"agent_phase":"idle","pending_jobs":0,"inflight_jobs":0,"wait_reason":null,"snapshot_at_ms":1790000000000,"budget_counters":{"jobs_created":0,"llm_attempts_created":0,"tokens_known":0,"tokens_uncertain":0,"tokens_reserved":0,"active_elapsed_ms":0,"active_started_at_ms":null}}}
```
phase 由 A-503 推導：paused 優先呈現 paused，未解 unknown／needs_attention 呈 error；think/act/wait 依控制事實與 agent-state 的 continuation 映射。wait_reason 的 code 只用 S-402 集合，含 since_at_ms，可省 scope_id/next_due_at_ms；同時 pause 與 quota_wait 時主因 pause，不刪其他證據。查詢不載入全部 history、不起 tick、不持票；缺權 unauthorized，回收內容 gone。

**Given** run 有 unknown 工具而 phase 可推成 idle，**When** 查詢，**Then** 顯示 error/result_unknown 並保留 attempt 證據；snapshot_at_ms 只表示快照時間，不保證名額仍可用。

## P-112．run.pause、run.resume：屏障與可選重新驗證〔建議預設，未拍板〕

owner／管理者 → 控制入口，params 都必填 run_id。pause 保存 paused_from，停新派工但不殺在途，結果照收。resume 回到 queued 或 active；非 unknown 的 needs_attention 只在部署提供可選出口且交易內重新驗證通過時恢復。不支援回 conflict/details.reason=resume_unsupported；終局 pause/resume 回 run_terminal。普通 resume 不清 cancel_requested、不解除 unknown。

```json
{"jsonrpc":"2.0","id":"req_resume_1","method":"run.resume","params":{"run_id":"run_3"}}
```

```json
{"jsonrpc":"2.0","id":"req_resume_1","result":{"accepted":true,"request_id":"req_resume_1","run_id":"run_3"}}
```

pause 的完整交換見 P-102。run.resume 可省 budget，僅管理者可帶，只提高明列維度，未列維度沿現額，不重套初始預設；權限／增額／足夠餘量須同交易驗證，記操作者與前後值。預算增額屬 S-405 危險處置，aos-attend 非互動模式不得自動做。同 ID 重送回原收據；另一 ID 重複同動作依 S-102 現況處理，不重啟工作。

**Given** paused 時工具完成再重啟，**When** resume，**Then** 已登記結果只被語意消費一次。**Given** unknown 或取消要求尚在，**When** 普通 resume，**Then** conflict，不能暗中 retry。

## P-113．run.cancel、attempt.cancel：先記要求，再查收尾〔建議預設，未拍板〕

owner／管理者 → 控制入口。run.cancel params 只有 run_id；同交易持久 cancel_requested、停新派工並發取消意圖，再回 accepted。attempt.cancel params 只有 attempt_id；由帳本解析 owner/run，走 B-203 取消。accepted 的 run_id 取該 attempt 的 run（維護 tick 可 null）；兩者都不表示域已清空。

```json
{"jsonrpc":"2.0","id":"req_cancel_1","method":"run.cancel","params":{"run_id":"run_3"}}
```

```json
{"jsonrpc":"2.0","id":"req_cancel_1","result":{"accepted":true,"request_id":"req_cancel_1","run_id":"run_3"}}
```

```json
{"jsonrpc":"2.0","id":"req_attempt_cancel_1","method":"attempt.cancel","params":{"attempt_id":"attempt_7"}}
```

```json
{"jsonrpc":"2.0","id":"req_attempt_cancel_1","result":{"accepted":true,"request_id":"req_attempt_cancel_1","run_id":"run_3"}}
```

控制層將有程序者交 execution 的可信取消通道；LLM sent 後取消依 llm 篇只關本機等待，不承諾 provider 停算。取消意圖可重放，同 ID 不新建；未清空保留占票／claim，unknown 使 run needs_attention。所有委託工作有確定終局（或合法接受未知副作用）且本機清空才結算 canceled。

**Given** 工具主程序退出而孫程序仍活，**When** 查詢取消後狀態，**Then** cleanup 尚未完成、票未釋放，不能因 adapter exit 0 宣稱 canceled。

## P-114．attempt.get 與 run.resolve：查證據、接受 unknown 風險〔建議預設，未拍板〕

attempt.get 由 owner／管理者呼叫，params 只有 attempt_id；回 AttemptQuery，含 attempt、cancellation（取消／cleanup 投影）及 snapshot_at_ms，程序細節證據另引用 execution 所有的觀測材料，不能拿 PID 數字當活性證明。

```json
{"jsonrpc":"2.0","id":"req_attempt_1","method":"attempt.get","params":{"attempt_id":"attempt_7"}}
```

attempt.get 的完整回覆：
```json
{"jsonrpc":"2.0","id":"req_attempt_get_1","result":{"attempt":{"version":1,"attempt_id":"attempt_1","job_id":"job_1","agent_id":"agent_a","ordinal":1,"generation":1,"state":"reserved","created_at_ms":1790000000000},"cancellation":{"cancel_requested":false,"requested_at_ms":null,"cleanup_state":"not_required","cleanup_evidence_ref":null},"snapshot_at_ms":1790000000000}}
```

run.resolve 僅管理者，params 必填 run_id/job_id/decision。retry 必填 allow_duplicate_effects=true 及 new_max_attempts（大於既有 attempt 數），本機清空才允許新 attempt；有取消要求時另必填 clear_cancel_requested=true。fail/cancel_with_unknown 先持久 pending_resolution，停派並取消其餘工作，全部清空才轉 failed/canceled；pending_resolution 優先於一般取消結算，不改舊 unknown 為假失敗。

```json
{"jsonrpc":"2.0","id":"req_resolve_1","method":"run.resolve","params":{"run_id":"run_3","job_id":"job_17","decision":"retry","allow_duplicate_effects":true,"new_max_attempts":2,"clear_cancel_requested":true}}
```

```json
{"jsonrpc":"2.0","id":"req_resolve_1","result":{"accepted":true,"request_id":"req_resolve_1","run_id":"run_3"}}
```

```json
{"jsonrpc":"2.0","id":"req_resolve_fail_1","method":"run.resolve","params":{"run_id":"run_3","job_id":"job_17","decision":"fail"}}
```

```json
{"jsonrpc":"2.0","id":"req_resolve_cancel_1","method":"run.resolve","params":{"run_id":"run_3","job_id":"job_17","decision":"cancel_with_unknown"}}
```

每次保存操作者、request_id、時間、選擇及風險接受；重送去重。可信原始結果補回走 execution／llm 內部通道，不提供任意寫成功結果的 RPC。aos-attend 無終端不發這三種 resolve。

**Given** unknown job 仍有本機程序，**When** retry，**Then** conflict、保留原 unknown，不產生第二 attempt。**Given** fail 的收據已回而其他工作未清空，**When** run.get，**Then** 仍 needs_attention/pending_resolution，不提前宣稱 failed。

## P-115．run.outputs：讀已提交輸出〔建議預設，未拍板〕

owner／管理者 → 控制入口。params 必填 run_id，可省 after_seq（非負，預設 0）、limit（正整數，預設 100、最多 1000）。result 必填 outputs、next_seq、has_more；Output 引用 `agent-output.schema.json#/$defs/Output`，不得另抄一種 Output。按 output_seq 升序只列大於 after_seq 的已提交可見輸出；next_seq 是本頁最後序號，空頁沿輸入 after_seq；has_more 表示該快照仍有後續，不代表 run 是否完成。受 256 KiB 回覆上限時可少於 limit，輸出正文與 blob 的交界須與 agent-state/storage 篇一致，超大單筆不得靜默截斷成合法 final（待決見 P-190）。

```json
{"jsonrpc":"2.0","id":"req_outputs_1","method":"run.outputs","params":{"run_id":"run_3","after_seq":0,"limit":100}}
```

```json
{"jsonrpc":"2.0","id":"req_outputs_1","result":{"outputs":[],"next_seq":0,"has_more":false}}
```

讀端以 run_id/output_seq 去重；要下一次快照換新 request_id，保留 after_seq；同 request 重送得同頁。讀到 final 仍可查 run 的成功條件，輸出讀取不消費工具結果、不 ACK 或刪結果。

**Given** tick 的 outputs 尚未提交，**When** run.outputs，**Then** 不可見。**Given** 同頁重送或重複讀取，**When** client 合併，**Then** 依 output_seq 去重，不生成兩份回答。

## P-120．ready、due、游標與最小量測〔建議預設，未拍板〕

控制 writer 保存 control-state 的 ReadyDue、SchedulerCursor、MetricsWindow；它們用於可信恢復／診斷交接，不是 agent 可寫 RPC。ReadyDue 的 ready、next_due_at_ms、ready_since_at_ms、pending_seq、served_seq 按 S-201，事件、claim、提案提交及 run 終局交易重算。pending/served 是事件投影水位，不是輸入消費 cursor；不能把 tick 舊視圖覆寫較新事件。

seq/ready_seq 由 writer 持久配發；游標用於 S-202 分批巡檢及 S-204 同級 agent 輪流，不拿目錄順序或牆鐘代替。預設每批 64、低頻補查 60000 ms，可配置；啟動、overflow 與交接不一致觸發補查，允許新件穿插。公平 priority 僅控制政策 0/1，等超過 60 秒的可入場工作按 ready_seq 優先；等候門檻依經過時間，重啟時間恢復不能憑牆鐘改排隊順序。

量測分 steady-state 與 startup_reconcile，記 registered、unique_active、ready、tick/tool/HTTP 在途、queue_age、scope 等待、unknown、重試、CPU/RSS/FD、提交耗時與拒絕數。查核窗有界彙總，不保存無上限逐事件正文。這些紀錄不另開公開 metrics 方法；管理者透過受控診斷匯出取得。

完整 ready、巡檢游標及最小量測例：
```json
{"version":1,"agent_id":"agent_a","ready":false,"next_due_at_ms":null,"ready_since_at_ms":null,"pending_seq":0,"served_seq":0}
```

```json
{"version":1,"cursor_id":"reconcile_main","kind":"reconcile","position":null,"batch_size":64,"last_advanced_at_ms":1790000000000,"round_started_at_ms":1790000000000,"last_completed_at_ms":null,"last_round_duration_ms":null}
```

```json
{"version":1,"window_id":"metrics_1","mode":"steady_state","started_at_ms":1790000000000,"finished_at_ms":1790000060000,"registered":1,"unique_active":0,"ready":0,"tick_inflight":0,"tool_inflight":0,"http_inflight":0,"queue_age_max_ms":0,"scope_waits":[],"unknown_count":0,"retry_count":0,"control_cpu_ms":1,"control_rss_peak_bytes":1048576,"control_fd_peak_count":8,"ledger_commit_count":0,"ledger_commit_total_ms":0,"ledger_commit_max_ms":0,"rejections":[]}
```

**Given** R1 等工具而 R2 入站，**When** ReadyDue 重算，**Then** 不反覆叫 R1 空 tick；R1 終局才同交易讓隊首 R2 ready。**Given** 通知遺失或 overflow，**When** 游標補查，**Then** 持久工作可恢復，冷 agent 不起程序；量測不把熱快照當冷啟動成績。

## P-121．run 預算、控制意圖與處置稽核〔建議預設，未拍板〕

Budget 四項 max_jobs/max_llm_attempts/max_tokens_estimate/max_elapsed_ms 的接納預設分別 32/16/100000/600000；僅屬 S-306 建議。BudgetCounters 保存 jobs_created、llm_attempts_created、tokens_known/uncertain/reserved、active 經過時間累計與最近起點。建 job、建 LLM attempt、scope/run token 預留都經 writer 交易，未知 token 不歸零；usage 可信去重結算由 llm 篇提供，這裡只存 run 總計。active 含遠端等待，paused/needs_attention 停表，UTC 欄位供恢復與顯示，運行時計經過時間。

不足則 needs_attention/budget_exceeded 並停新 job/attempt，已在途結果照收；時間耗盡另取消本機工作。control-state 的 ControlIntent／ResolutionRecord 記已認證操作者與 request、目標及持久要求；不是 sender 可提交的自稱身份。CancellationState 是 attempt.get 的查詢子物件，只有 cancel_requested/requested_at_ms/cleanup_state/cleanup_evidence_ref，不是另一份可直接保存或回寫的控制意圖；沒有自己的 version、actor 或 request_id。writer 先保存意圖才交 execution／llm 執行、收到可信確認再更新；崩潰重放同意圖不重做副作用。紀錄落在控制帳本，若匯出持久檔仍依 P-004，不把任何 JSON 檔直接當 DB 寫入 API。

完整預算、取消意圖與處置紀錄例：
```json
{"version":1,"agent_id":"agent_a","run_id":"run_1","budget":{},"counters":{"jobs_created":0,"llm_attempts_created":0,"tokens_known":0,"tokens_uncertain":0,"tokens_reserved":0,"active_elapsed_ms":0,"active_started_at_ms":null}}
```

```json
{"version":1,"agent_id":"agent_a","actor":"uid:1000","accepted_at_ms":1790000000000,"request":{"jsonrpc":"2.0","id":"req_cancel_1","method":"run.cancel","params":{"run_id":"run_1"}}}
```

```json
{"version":1,"agent_id":"agent_a","run_id":"run_1","job_id":"job_1","actor":"uid:1000","request_id":"req_resolve_1","resolved_at_ms":1790000000000,"decision":"retry","accepted_unknown_effects":true,"new_max_attempts":2}
```

**Given** scope 足夠但 run token 不足，**When** 準入交易，**Then** 兩邊都不 hold，記 budget_exceeded。**Given** resolve 已提交但取消回報丟失，**When** 重啟重放，**Then** 使用原 request 與原意圖，不清 unknown、不提前終局。

## P-130．aos-attend 的機器啟動與處理表〔使用者方向 2026-09-29；格式為建議預設，未拍板〕

角色名 `aos-attend` 以單支 aos 子命令承接；由管理者的程序直接 exec：

```json
["aos","attend","--policy-fd","3","--socket","/run/aos/control.sock","--attention-dir","/var/lib/aos/attention","--audit-dir","/var/lib/aos/attend-audit","--service-socket","/run/aos/service.sock"]
```

policy-fd 是啟動者以自身權限開的普通唯讀 fd，讀 control-attention-policy 後關閉；socket／service-socket／attention-dir／audit-dir 為必填可信絕對路徑；audit-dir 由管理者保護，僅該操作者與可信控制服務可讀寫，拒絕 symlink 或 agent 可替換的父目錄。以啟動者原 UID 呼叫 RPC／P-132 的清理管理入口，後者以控制服務 UID 啟動 aos-clean；不由 attend setuid、不接收 impersonate 或全部 yes。不讀 `AOS_*`；環境不授權動作。stdin 讀 control-attention-action#/$defs/BatchRequest 至 EOF，max_items 可省預設 64、範圍 1～1000；stdout 回 BatchResult，actions 不超過 max_items，has_more 僅指本次尚有未處理通知，stderr 有界診斷；policy 及每個單次 JSON 都先限 256 KiB 再解析；stderr 按診斷上限，單筆文字不足以表示全部原因時保留結構化錯誤與引用。完整輸出（含跳過／RPC error）exit 0，argv／policy／輸入不合法 exit 2，自身 I/O 或稽核未能完成 exit 125。此機器模式不讀 /dev/tty，不定 y/n 的 UI；危險動作一律跳過。

讀 `<attention_dir>/open/agents/<agent_id>/<item_id>.json` 與 `open/control/<item_id>.json`，沿 P-011 暫定，不禁用合法 agent_id=`_control`。通知 schema、重建與 done 同構由 storage 篇持有。每件先按 item 的 owner/run/attempt 用既有 agent.get/run.get/attempt.get 查權威，再判目前 actions、原因與 policy；通知內容不是授權，不執行其中任意 argv，不刪改／搬移 open 檔。控制事項無 run 時，既有查詢不足以驗證已解除，不捏造新的 control.get；本版 attend 機器模式只 inspect/skipped，交管理者處理。

處理表 code 可配三類：safe 僅重新驗證／依既有留存規則清理；dangerous 涉及重試外部副作用、fail/cancel_with_unknown、run.cancel、增額；manual 只列出。同一 policy 不得重複 code，未知 code 固定 inspect；可編輯表不能把固定危險動作改名成安全。safe resume 不攜 budget，不解除 unknown 或 cancel_requested；can_resume/actions 不允許時跳過。清理候選與完成回報完全依 storage-clean-*，clean_request 引 `storage-clean-request.schema.json#/$defs/Acquire`；自動清理只限該 item.agent_id 的 agent scope 與可信 archive 政策，不能擴成 all_agents/control 或自行選 delete。先清再 resume 必須重新查權威，不能因 clean exit 0 猜屏障解除。刪除模式不藉「安全清理」繞過留存與人為危險處置界線。

完整處理表與一份批次輸入：
```json
{"version":1,"policy_id":"attend_policy_1","rules":[{"code":"config_unavailable","risk":"safe","action":"run.resume"},{"code":"storage_blocked","risk":"safe","action":"aos-clean","clean_policy_id":"archive_30d"},{"code":"result_unknown","risk":"dangerous","action":"run.resolve.retry"}],"default_action":"inspect"}
```

```json
{"version":1,"batch_id":"attend_batch_1","max_items":2}
```

**Given** 一件已修復 config_unavailable 與一件 unknown，**When** 無終端機器批次，**Then** 前者只在提供 resume 出口並重新驗證通過時恢復，後者 skipped 留 open；改 policy 把 retry 寫 safe 也不得執行。

## P-131．aos-attend 的動作稽核與中斷重跑〔建議預設，未拍板〕

planned 是開始前的紀錄；accepted 僅表示 RPC 收件，completed 僅表示有限批次清理交換完成，兩者都不代表 attention 已解除；failed 保留 Error，unknown 是交換結果未確認，skipped 沒有執行請求。每個動作先保存有界 action 記錄：執行人、item/agent/run、時間、選擇、風險、原 RPC request_id 或 clean 的穩定請求識別。這是人的代理執行紀錄，不是第二個 writer 或 attention 權威。action_id 與 batch_id 必須來自可信本機產生器，actor 由程序身分取得；rpc.id/request_id、rpc.params.run_id/run_id、clean scope.agent_id/agent_id 及批次中各 action.batch_id 須相等。批次先把 BatchRequest 保存於 `<audit_dir>/<batch_id>/request.json`；每個 action 存 `<batch_id>/<action_id>/planned.json`，完整結果存同目錄 `response.json`（ActionRecord），交換未確認則另存 `unknown.json` 供診斷。各檔只以唯一正式名耐久發布，不覆蓋異內容；同 batch 以排他鎖序列化。以 ActionRecord/status=planned 按 P-004 耐久發布意圖後才呼叫；結果記 accepted／error／skipped／未確認的對應狀態與證據。未確認不能寫成未執行：有 planned、無 response 時不採用新 policy 改寫原動作，重跑使用原 id 和原內容，先重取收據，再以新查詢 id 查當前狀態。

全部已選項都有確定交換結果（accepted/completed/failed/skipped）後，才保存 `<audit_dir>/<batch_id>/response.json`（BatchResult）；若有 unknown，可輸出本次 BatchResult，但不保存為已完成的批次收據；同 batch_id 同輸入回原批次收據，未完成則恢復既有 action，同 ID 不同 max_items 等內容回 conflict。新批次用新 batch_id 並重查權威；不把 unknown 記錄當完成證據。批次及 actions 依控制診斷的保留／容量政策管理，不形成無上限 log；在選入下一項、尚未開始該動作前，先按允許的 reason/Error 上限預留該 ActionRecord 的序列化 bytes；若加進去可能超過 256 KiB，就停止選取、持久記下尚未處理項並令 has_more=true，留新批次處理。不可做完 1000 項才發現回覆放不下；單項診斷超限只記有界摘要，不截斷 RPC／clean 的必要證據或輸出半份 JSON。

危險動作的 skipped 記原因與建議，不帶可重放的自動授權；本篇不制定外部確認 token。將來互動工具仍須依 S-405 顯示特定動作與目標並逐次得到 y，不能用整份 policy、排程身分或任意 yes 參數代替。稽核寫不下時，不開始新的自動動作；動作後才寫不下則回未確認並保留原意圖供恢復，不能聲稱完成。stdout 結果不取代持久稽核，稽核目錄由管理者保護且不給 agent 讀寫。

事項解除由控制端按權威事實寫 done，附 resolved_at_ms 與 resolution（動作、操作者、request_id），storage 篇定形狀。attend 不自行搬檔，也不因 accepted 就宣告 resolved。控制滿碟可能連 attention 都寫不出，依 B-404 保留容量保存最小證據、恢復後補檔；control/done 清理由管理者明確呼叫 aos-clean，不新設全域定時清理。

完整動作稽核與批次回覆例：
```json
{"version":1,"action_id":"attend_action_1","batch_id":"attend_batch_1","item_id":"attention_config_1","agent_id":"agent_a","run_id":"run_1","actor":{"principal_id":"admin_local","uid":1000},"request_id":"resume_config_1","at_ms":1790640000000,"policy_id":"attend_policy_1","code":"config_unavailable","action":"run.resume","risk":"safe","status":"accepted","reason":"重新驗證請求已持久接納，是否解除屏障仍由帳本決定。","query_request_id":"query_run_1","rpc":{"jsonrpc":"2.0","id":"resume_config_1","method":"run.resume","params":{"run_id":"run_1"}},"error":null}
```

```json
{"version":1,"batch_id":"attend_batch_1","actions":[{"version":1,"action_id":"attend_action_1","batch_id":"attend_batch_1","item_id":"attention_config_1","agent_id":"agent_a","run_id":"run_1","actor":{"principal_id":"admin_local","uid":1000},"request_id":"resume_config_1","at_ms":1790640000000,"policy_id":"attend_policy_1","code":"config_unavailable","action":"run.resume","risk":"safe","status":"accepted","reason":"重新驗證請求已持久接納，是否解除屏障仍由帳本決定。","query_request_id":"query_run_1","rpc":{"jsonrpc":"2.0","id":"resume_config_1","method":"run.resume","params":{"run_id":"run_1"}},"error":null},{"version":1,"action_id":"attend_action_2","batch_id":"attend_batch_1","item_id":"attention_unknown_1","agent_id":"agent_a","run_id":"run_2","actor":{"principal_id":"admin_local","uid":1000},"request_id":null,"at_ms":1790640000000,"policy_id":"attend_policy_1","code":"result_unknown","action":"run.resolve.retry","risk":"dangerous","status":"skipped","reason":"非互動模式不執行危險處置。","query_request_id":"query_run_2","error":null}],"has_more":false}
```

**Given** resume 交易完成但 attend 未收到回覆就崩潰，**When** 重跑同動作，**Then** 從原意圖取同 request_id，得到原收據；只由控制端決定 done。**Given** audit 寫入失敗，**When** 下一件安全動作準備執行，**Then** 不發出新操作，exit 125，既有意圖留待恢復。

## P-132．attend → 管理入口 → aos-clean〔建議預設，未拍板〕

沿 P-011 暫定的控制服務內部通道與 storage P-507。attend 以原管理者 UID 連 `--service-socket`（Unix SOCK_SEQPACKET），驗對端為可信配置的 service_uid；服務核對 SO_PEERCRED 為有權清理該 agent 的管理者。每 packet 一份 JSON、不加 LF、上限 256 KiB，不附 fd；拒絕多餘 fd、MSG_TRUNC/MSG_CTRUNC 與未知 kind，關閉收到的所有非預期 fd。這是管理者的本機啟動 adapter，不是 control-rpc 的新 method。

輸入驗 control-attention-action#/$defs/CleanLaunchRequest，實質引用 storage 的 Acquire，加上本機器模式的 agent scope、trigger=administrator 限制。clean policy 必須是既有可信 archive 政策；服務從認證結果保存啟動授權與原 request_id，不能信任 trigger 字串。服務與唯一 writer 先持久確認該操作者可用的 scope/政策/上限；同 ID 同內容重送恢復原清理批次，同 ID 異內容 conflict，不再領另一批。未取得持久授權不能起 clean。

服務以自己的 service_uid 直接 exec storage P-507 已定 argv：

```json
["aos","clean","--mode","request","--channel-fd","3"]
```

stdin 是同一 Acquire 至 EOF；fd3 是服務替本次已授權執行建立、實際繼承的 clean↔writer 專用 SOCK_SEQPACKET 連線，不能把管理者連線直接轉借，writer 核對服務 UID 及本次持久授權。服務只傳這個受控 fd，clean 與父端各關閉自己的副本；不給 root 或 agent UID。stdout 是 storage 的 Receipt／AcquireError／Report Error，stderr 最多 64 KiB，無 AOS_* 設定或金鑰環境；退出語意完全沿 P-507。服務驗完整 stdout 與 request_id，再向 attend 原連線回一份 CleanLaunchReply，不附 fd；exit 0 仍須讀 kind/error，partial 的 pending_candidate_ids 保留下一輪恢復。

完整請求與零候選收據：

```json
{"version":1,"kind":"clean_acquire","request_id":"clean_request_1","scope":{"kind":"agent","agent_id":"agent_a"},"trigger":"administrator","policy_id":"archive_30d","max_items":64,"max_bytes":16777216,"max_elapsed_ms":1000}
```

```json
{"version":1,"kind":"clean_receipt","request_id":"clean_request_1","batch_id":"clean_batch_1","recorded_candidate_ids":[],"pending_candidate_ids":[],"recorded_at_ms":1790640000000}
```

中斷或 clean 缺完整輸出不推定清理沒發生，attend 記 unknown，用原 request_id 重送並由 writer 核對原批次。服務停機／重啟仍沿全殺及候選恢復，不另起全域清理排程。此入口只限管理者/控制服務，agent 的普通 RPC 權限不通往這裡；control scope 仍留管理者明確手動管理流程，本 attend 模式不發出。

**Given** agent 冒稱 trigger=administrator 或管理者把同 request_id 換成另一 scope，**When** 管理入口驗證，**Then** 分別 unauthorized／conflict，不能啟動清理。**Given** clean 已搬檔而回覆丟失，**When** 同請求重送，**Then** 重取同批候選及收據，只補缺的步驟，不再領新一批。

## P-180．沿用 proto5 與差異〔主編補〕

沿用 [cpu/messages](../../../proto5/spec/cpu/messages.md)、[cpu/layout](../../../proto5/spec/cpu/layout.md)、[cpu/notify](../../../proto5/spec/cpu/notify.md) 的 requests/responses 同名配對、傳送識別與 RPC id 分開、門鈴只提示；沿用 [aos-exec/api](../../../proto5/spec/aos-exec/api.md)、[exit](../../../proto5/spec/aos-exec/exit.md)、[inst-posix/exec](../../../proto5/spec/inst-posix/exec.md) 的直接 argv 與包裝器自身錯誤要分清楚。proto5 [kernel/syscall](../../../proto5/spec/kernel/syscall.md) 的先記出站意圖再送信可作重放思路前例；proto5 [aos-llm/request](../../../proto5/spec/aos-llm/request.md) 的單次非串流代發由 llm 篇承接。

必要差異：proto5 notification／數字或 null request id／讀走 ack 刪回覆不搬入；C-04/B-501 收緊 envelope，C-05/B-404 將消費與留存獨立。舊 CPU 放檔是 link/unlink，proto6 用 B-402 同 filesystem rename、不覆蓋及 fsync/DB 修復，不宣稱舊版已具同樣耐久。proto5 同 UID 軟性自律改成可信入口快照與受管權限；舊 process group 與固定 CPU worker 不足以替代 B-202 cgroup 清空及 B-601 按需 tick。控制端不按檔名／mtime 排序，S-204 用持久序號；LLM key 不繼承給 agent。不同之處皆是既有 proto6 契約，沒有承諾 wire 向後相容。

**Given** 拿 proto5 ack notification 或 inst redirect 當範本，**When** 送本篇控制入口，**Then** 拒絕，不能刪結果或替 sender 代開路徑。

## P-181．範例拒絕原因與驗證層次〔主編補〕

[範例目錄](examples/control-rpc/) 的 `rpc-request.*.invalid` 分別驗 null／數字 id、缺 id notification、batch、假 sender、額外 version；`rpc-response.both.invalid` 拒 result/error 同存，`rpc-error.mapping.invalid` 拒 RPC 整數碼與領域 Error 不一致。`handoff-version.file.invalid` 拒未知持久版本，`handoff-sender.file.invalid` 拒包裝自稱 sender。這些是結構拒絕，不會部分執行。

`common-attempt.bool-generation.invalid`、`state-ready-due.bool-sequence.invalid` 拒 bool 冒整數；`common-blob.path.invalid`、`common-blob.newline-id.invalid` 拒路徑或尾端換行 ID；`common-outcome.success-error.invalid` 拒成功卻有 Error；`common-run.success-null.invalid` 拒成功但 final_ref=null；`common-job.tool-null-run.invalid` 拒非維護 tick 的空 run。`method-agent-submit.owner.invalid` 拒 uid 夾帶，`method-run-resolve.no-risk-consent.invalid` 拒缺風險接受，`method-run-outputs.limit.invalid` 拒 limit=1001；`method-result-ack.unavailable.invalid` 是 envelope 合法但方法集合拒絕。

`config-daemon.missing-capacity.invalid` 拒缺容量保留政策；`attention-policy.unsafe-retry.invalid` 拒把 retry 說成 safe；`attention-action.safe-budget.invalid` 拒安全 resume 夾預算；`attention-action.control-clean.invalid` 拒自動跨到 control 清理；`attention-action.danger-planned.invalid` 拒把危險動作放入 planned。正例中 `.retry`／`.resend` 保存原 request_id 與原內容；`.unknown`／`.exchange-unknown` 不表示安全未執行；`.truncated` 是完整查詢 JSON，只是其引用的執行結果發生截斷。

JSON 解析及 2020-12 schema 驗證是一層；owner、live claim、跨欄位一致、引用摘要／大小、狀態轉移及同 ID 異內容是第二層；fsync／DB／回覆裂縫、重啟清空與補查是第三層。後兩層以各條 Given/When/Then 驗收，不把 schema 通過當成恢復測試通過。

**Given** 路徑、bool、缺授權承諾及不可呼叫方法各一例，**When** 用相應 schema 驗證，**Then** 對應負例被拒；**Given** 改成跨 owner 但結構正確的 ID，**When** schema 通過，**Then** 仍由入口權限驗證拒絕，不因此建立 run。

## P-190．待決、整合交界與現況〔主編補；建議均未拍板〕

1. **大型 Output 的單頁可傳性待決**：A-203 Output 的 text 尚未限單筆大小，B-403 允許較大增量，但 B-501 回覆上限 256 KiB。建議由 agent-state/storage 整合者定超大單筆引用或受控匯出；本篇不加未授權欄位、不截斷 final。現階段超限回 resource_exhausted，保留原輸出與序號，不回空頁假裝完成。
2. **查詢同 ID 與目前狀態**：本文按 B-503 全方法去重，舊查詢 ID 回原快照、新 ID 才新快照；S-102「重複同 action 回目前狀態」解讀為不同 request_id 重複動作。請整合者在正本明寫此區別；若要查詢排除去重，須改 B-503，不能各 adapter 自定。
3. **設定／登記發布交界**：P-011 已暫定只允許管理者本機 adapter，bundle／引用與換版紀錄屬 agent-state，registry/profile 與可信 launch 快照屬 execution。本篇 control-config 是 daemon 啟動設定，沒有另加公開發布 method。capacity.reservation_policy_id 的可信解析表與實際保留 backend 也待部署整合（建議以管理者設定解析、啟動 probe）；各篇須對齊一次性發布 argv、revision 對照及管理者認證，不能只讓未知字串被視為有效引用。
4. **共同片段交界**：run.outputs 引 agent-output 的 Output；Run 換版紀錄引 agent-config 的 ConfigChange；system_hooks 引 agent-hook-registration；各片段名稱須由整合者核對。控制查詢的 think/act/wait 依 agent-state continuation 映射，不能在 control-state 新增第二份可寫 phase。可信程序結果／清理證據由 execution、LLM reservation 與 usage 由 llm、attention 與 clean 細節由 storage 所有。
5. **正本需要整合者回寫**：S-405 attention 路徑採 open/agents 與 open/control、done 同構及 resolution；A-506 獨立 hook_run_id、claim 起算 deadline、skip_tick 有界退避／新事件再排；B-102/B-303 可信登記快照方式，以及 P-011 尚未回寫的內部 LLM 投件／發布 adapter；storage P-507 的管理啟動端與本篇 P-132 對齊，使用既有 Acquire/Receipt，不新增公開方法。README 的第一階段敘述與交付導航由整合者更新，本作者不改。
6. **系統掛勾與 deadline 的文字交界**：A-506 系統掛勾另計，P-011 又說總 deadline 自 claim 起算。建議 execution/agent-state 明列系統掛勾自身上限及 agent 剩餘 deadline 怎麼計；本篇不另設能延長 claim 的參數，也不替原條款取消「系統另計」。

這次交付是規格與可驗證 JSON，沒有 daemon／adapter 的執行實作；Given/When/Then 的授權、崩潰恢復與程序清空仍須在實作階段驗收。JSON Schema 能證明結構，不證明引用存在、授權、耐久提交或副作用未發生。
