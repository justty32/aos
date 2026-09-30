# LLM 代發

← [共用約定與分工](README.md)｜[工作與結果](work.md)｜[LLM 池](../scheduling/llm.md)

本篇原屬 [work](work.md)，2026-09-29 拆出；條號不變。once 資料夾與掛載參數（P-402）、結果形狀（P-403）、程式契約（P-408）與 schema 範例（P-409）仍在 work。

〔使用者方向 2026-09-30，第十八批〕本篇只留池設定、LLM 請求與結果的欄位與 JSON；行為以 [LLM 池 S-301～S-307](../scheduling/llm.md) 為正本（三檔、兩條路線、份額、key、重試、unknown 占用、池 node 誰收件）。LLM 池是預設 kernel 範本的一種資源，不是 aos 寫死的特例（[T-06](../terms.md)）。本篇 schema 照 [P-007](README.md) 放寬：不認得的欄位忽略，只有 [C-07](../contracts.md) 的禁止鍵出現就拒收。

## P-405．代發啟動與池設定〔使用者方向 2026-09-29〕

key 保護到哪裡、同帳號部署為什麼不受保護，以 [S-301](../scheduling/llm.md) 為正本；〔使用者方向 2026-09-30，第十八批〕保護只對整條投件鏈以外的帳號成立（[T-08](../terms.md)）。本篇格式上的約定是：key 不進 prompt、工作請求、結果、inst、argv 或給成員的環境。

池就是一個 node，收件、回覆與串流檔照 [S-301](../scheduling/llm.md)；池 node 的任務表怎麼裝、誰收 `llm.chat`、`aos-llm` 怎麼派 `aos-llm-call`，照 [S-307](../scheduling/llm.md)。任務表項的 argv 是 `aos-llm --config <設定路徑>`，路徑可相對（依呼叫時的 cwd，tick 裡就是 node 根；範本寫 `config/llm-pools.json`）。

[`llm-config`](schemas/llm-config.schema.json) 是 `version:1` 與 `pools` 陣列，每項必有 `id`、`endpoint`、`model`、`quota_scope`，可加 `key_ref`、有限正整數 `max_attempts`（預設 3，只給 `schedule` 為 `aos` 的池）及 `schedule`。〔使用者方向 2026-09-30，第十八批〕不認得的欄位忽略；`api_key` 是永遠禁止的鍵，出現就整份拒收（[C-07](../contracts.md)，[反例](examples/work/llm-config.inline-key.invalid.json)）。endpoint 是無認證資訊、query、fragment 的 HTTP(S) base URL，末尾補 `/chat/completions`。model 是 provider 真名；同一份表不允許重複 pool id。`quota_scope` 是共享限制的名字，格式是非空字串；哪些池共用同一個 scope、集中或分片由 kernel 決定，計數規則見 [S-301](../scheduling/llm.md)。

〔使用者方向 2026-09-29 晚〕`schedule` 選這個池是哪一檔（三檔的意思以 [S-301](../scheduling/llm.md) 為正本），只有兩個值：

- `aos`（省略即此值）＝「自己排」：並行、窗口、冷卻與排隊的規則見 [S-302、S-303](../scheduling/llm.md)，限制檔格式見 [kernel P-811](kernel-tasks.md)。
- `endpoint`＝「交給 endpoint」：這個池只轉發（行為見 [S-301](../scheduling/llm.md)，不讀 `llm-limits.json`、不做窗口與並行上限）。〔使用者方向 2026-09-29 晚，第十五批〕429、限流與重試全交給 endpoint，aos 不重試：每件請求只打一次 HTTP，schema 擋掉 `max_attempts`：`schedule` 為 `endpoint` 的池不允許有這欄，寫了就是設定錯誤（[正例](examples/work/llm-config.endpoint.valid.json)、[反例](examples/work/llm-config.endpoint-max-attempts.invalid.json)）。這和 [kernel P-809](kernel-tasks.md) 轉給另一個 kernel 的轉交是兩件事。

一個池只對一個 endpoint，見 [S-301](../scheduling/llm.md)。

`key_ref` **只准出現在代發服務設定**，值是私有憑證檔絕對路徑；缺省＝不帶 Authorization。代發程序讀 key 建 HTTP header，禁止把原文存進 node 資料、git、交付檔或日誌；這是輸出約定，不是讀取權的界線（界線見 [S-301](../scheduling/llm.md)）。派出時固定的 `W/llm-config.json`（[P-402](work.md)）只含本池一項與 `key_ref`，不複製 key。

## P-406．LLM 請求與 messages〔建議預設，未拍板〕

[`llm-request`](schemas/llm-request.schema.json) 的 stdin 材料除工作識別，必填 `pool`、`model`、`messages`、`max_completion_tokens` 與正整數 `timeout_ms`；pool／model 是目標 node 所公布的路由名；轉交時 pool 可映到下一個 node 的 pool、原 node_id／job_id／attempt_id 保留，規則見 [S-307](../scheduling/llm.md)。可帶 `tools`；〔使用者方向 2026-09-29 晚〕可帶 `stream_path`（絕對檔案路徑）要求串流，省略就不串流，見 [S-305](../scheduling/llm.md)。請求不能覆寫 endpoint、key 或加入任意 HTTP header。

messages 沿 [proto5 格式](../../../proto5/spec/aos-llm/request.md)，採 [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 的**文字與 function tool calls 子集合**，不是所有多模態欄位都支援：

- system／developer／user：`role`、字串 `content`。
- assistant：`role`、字串或 null 的 `content`，可有非空 `tool_calls`；content 為 null 時須有 tool_calls。
- tool call：`id`、`type:"function"`、`function:{name,arguments}`，arguments 是 JSON **字串**，不是 object。
- tool 結果：`role:"tool"`、`tool_call_id`、字串 `content`。呼叫 ID 在一份 assistant 回覆內唯一；工具結果必須對到前面的呼叫，不能重複或孤立。
- `tools` 每項為 `{type:"function",function:{name,parameters,description?}}`。parameters 是工具的 JSON Schema；工具名唯一，adapter 不支援的規則要拒絕，不能忽略。

[`llm-messages`](schemas/llm-messages.schema.json) 驗形狀；順序、ID 唯一性、arguments 能否解析及工具參數驗證由接件／agent 任務另驗。〔第十八批補，建議預設，未拍板〕〔暫定 a，照舊疑點預設：忽略、不送進 HTTP〕messages 與 tools 裡不認得的欄位照 C-07 忽略，也不送進 HTTP body；HTTP body 只帶本版認得的欄位。HTTP body 只送 model、messages、tools（有才送）、max_completion_tokens 與 stream；沒有 stream_path 送 `stream:false`，有則送 `stream:true`，〔使用者方向 2026-09-29 晚〕並加 `stream_options:{include_usage:true}`，要求 provider 最後附上 usage。供應商不支援就明確拒絕，不把輸出上限默默去掉。agent 發起端的設定、context 定位及用量格式見 [agent 任務 P-701／706／710](agent-tasks.md)。發起 node 先由原始檔整理有界 context；RPC 封包受 P-004 的 256 KiB 限制；messages 在 stdin JSON 材料內，仍受 agent 的 context 上限。

## P-407．LLM 結果、usage 與有限重試〔建議預設，未拍板〕

[`llm-result`](schemas/llm-result.schema.json) 的本地結果檔及 llm.chat stdout JSON 是 `version:1,node_id,job_id,attempts`；RPC result 仍是 P-403 的指令結果。`attempts` 依真正 HTTP 嘗試順序排列，每項帶 `attempt_id,status,reason,message,finish_reason,usage,http_status`，限流失敗的那項可另帶 `retry_at_ms`。第一項 ID 對應請求，是發起 node 配的；後續項的 ID 是池配的，工作目錄前綴也跟著換成池（[P-402](work.md) 的例子）。轉交與重試時 attempt ID 與結果怎麼保存，見 [S-307](../scheduling/llm.md)。

〔第十八批補〕`retry_at_ms` 只出現在 `status:failed`、`reason:rate_limited` 的項，記這次限流後算出的「最早可重試時間」，是這次嘗試的歷史證據；[kernel-work-state](schemas/kernel-work-state.schema.json) 的 `llm.retry_at_ms` 是池排程用的下次派出時間。兩者值可能相同，意思不同，都留。

每支 aos-llm-call 只做一次 HTTP，結果 attempts 只有一項；池任務收齊後按序組成 llm.chat 的 stdout JSON，再保存指令結果回應。最後一項就是這次請求結果，不另放重複的總狀態或總 usage。provider 回應先只取 choices[0].message 的 role/content/tool_calls；tool_calls 是 null 或空陣列就省略，content 為 null 且沒有 calls 就正規化為空字串（沿 proto5），其餘驗 P-406。官方附帶的 annotations 等非本版欄位不抄入結果；非空 refusal 明確記 response_invalid 並保留無 key 的拒絕證據，不假裝空白成功、不自動重試。成功的 message 是 P-406 的 assistant，finish_reason 原樣保存；`length` 表示模型輸出達上限，不能當產品任務完成。結果只看完整回應：串流時是串流正常結束後拼成的完整 message，中途斷掉不算完整；無可用 message 填 null。usage 只取三個計量欄（串流時取最後附帶的 usage，沒給就是不可得）；有完整的 `prompt_tokens,completion_tokens,total_tokens` 才記物件；不可得填 null，不補 0，也不把估算寫成 provider 實際 usage。部分 usage 的原始證據可以保留在私有診斷材料，不能冒充完整計量。

reason：`completed`（成功）、`rate_limited`（確定限流拒絕）、`rejected`（明確拒絕）、`not_sent`（可證明沒送）、`response_invalid`（收到完整但格式不合的回應）、`canceled`（確定未送且取消）、`unknown`（可能已處理）。缺失的 HTTP 狀態、finish_reason 都填 null。收到完整但無法驗證的 provider 回應不自動再問；傳輸中斷或遠端結果不明則 unknown。

有限重試、冷卻、unknown 占用與釋放以 [S-303、S-304](../scheduling/llm.md) 為正本；「交給 endpoint」的池不重試。usage 按 attempt 去重；缺失不補零。
