# LLM 代發

← [共用約定與分工](README.md)｜[工作與結果](work.md)｜[LLM 池](../scheduling/llm.md)

本篇原屬 [work](work.md)，2026-09-29 拆出；條號不變。once 資料夾（P-402）、結果形狀（P-403）、程式契約（P-408）與 schema 範例（P-409）仍在 work。

## P-405．代發啟動與池設定〔使用者方向 2026-09-29〕

**代發服務和管池的 kernel node 同帳號，所以該 kernel 讀得到 key；只有其他帳號的成員才有隔離。**key 不進 prompt、工作請求、結果、inst、argv 或給成員的環境。**沒 helper 時全樹同帳號，key 不受保護**（第八批）；要隔離須用 helper 配合不同帳號，或另用不同帳號跑代發並限制憑證檔權限。這是 OS 讀取權限的界線，不是 JSON 能保證的事。

〔使用者方向 2026-09-29 晚〕池就是一個 node：請求投進它的 `requests/`，池照請求的 `reply_to` 回覆、照業務 JSON 的 `stream_path` 寫串流檔；回覆到了之後誰叫醒 agent、各檔權限怎麼開，aos 不管，沒權限就報錯（[S-301](../scheduling/llm.md)）。

〔建議預設，未拍板〕池管理 node 的任務表加入 `aos-llm --config <絕對設定路徑>`，再依 daemon 篇註冊、叫醒該 node。aos-llm 是短任務：收件、核對共享限制、派送、收結果便退出。它為每個實際 HTTP 嘗試建 P-402 的 once 資料夾，inst 改跑 `aos-llm-call --work-dir <絕對工作資料夾> --config <絕對設定路徑>`，使用池管理 node 的帳號。HTTP 等待由這支受 daemon 管的程序承擔，不占 node 的 tick。結果放工作資料夾，由後續池 tick 發回；LLM 工作沿用 once 的清理與恢復界線。

[`llm-config`](schemas/llm-config.schema.json) 是 `version:1` 與 `pools` 陣列，每項只有 `id`、`endpoint`、`model`、`quota_scope`，可加 `key_ref`、有限正整數 `max_attempts`（預設 3）及 `schedule`。endpoint 是無認證資訊、query、fragment 的 HTTP(S) base URL，末尾補 `/chat/completions`。model 是 provider 真名；同一份表不允許重複 pool id。共享 provider 帳戶／模型限制的項目必須使用相同 `quota_scope`，由同一池管理 node 的 tick 統一分配序號、在途占用及冷卻，不能各開一份計數繞過限制。

〔使用者方向 2026-09-29 晚〕`schedule` 選這個池是哪一檔（三檔的意思以 [S-301](../scheduling/llm.md) 為正本），只有兩個值：

- `aos`（省略即此值）＝「自己排」：aos-llm 照 [kernel P-811](kernel-tasks.md) 讀 `llm-limits.json`，做並行、窗口、冷卻與排隊。
- `endpoint`＝「交給 endpoint」：這個池的 aos-llm **只轉發**，把收到的請求逐件交 aos-llm-call 轉給外部 endpoint；不讀 `llm-limits.json`、不做窗口與並行上限，只藏 key、記用量。〔使用者方向 2026-09-29 晚，第十五批〕429、限流與重試全交給 endpoint，aos 不重試：每件請求只打一次 HTTP，`max_attempts` 對這種池不起作用。這和 [kernel P-809](kernel-tasks.md) 轉給另一個 kernel 的轉交是兩件事。

一個池只對一個 endpoint，見 [S-301](../scheduling/llm.md)。

`key_ref` **只准出現在代發服務設定**，值是私有憑證檔絕對路徑；缺省＝不帶 Authorization。代發程序讀 key 建 HTTP header，禁止把原文存進 node 資料、git、交付檔或日誌；這是輸出約定，不是假裝同帳號的 kernel 無讀取權。私有憑證檔放在 node 樹外，只有部署授權的代發帳號可讀；同 UID 成員仍能讀到，不能宣稱靠放在樹外就隔離。任務直接開設定檔；派出時只固定該次工作需要的設定值及憑證引用，不複製 key。

## P-406．LLM 請求與 messages〔建議預設，未拍板〕

[`llm-request`](schemas/llm-request.schema.json) 的 stdin 材料除工作識別，必填 `pool`、`model`、`messages`、`max_completion_tokens` 與正整數 `timeout_ms`；pool／model 是目標 node 所公布的路由名；轉交 kernel 可映到下一個 node 的 pool，model 原值沿路核對，終點核對實際池設定。轉交仍用 llm.chat，不增加另一種 wrapper；保留原 node_id、job_id、attempt_id，另配轉交 RPC id 與 reply_to，由轉交者保存上下游關係。收結果後沿用 stdout 的業務結果，以本 node 及原 RPC id 組成自己的指令結果回覆，不照抄下游指令識別。agent 配對的可信回件來源始終是設定目標。可帶 `tools`；〔使用者方向 2026-09-29 晚〕可帶 `stream_path`（絕對檔案路徑）要求串流，省略就不串流，見 [S-305](../scheduling/llm.md)。轉交沿路原樣保留 stream_path，由最後實際打 HTTP 的 aos-llm-call 寫。請求不能覆寫 endpoint、key 或加入任意 HTTP header。

messages 沿 [proto5 格式](../../../proto5/spec/aos-llm/request.md)，採 [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 的**文字與 function tool calls 子集合**，不是所有多模態欄位都支援：

- system／developer／user：`role`、字串 `content`。
- assistant：`role`、字串或 null 的 `content`，可有非空 `tool_calls`；content 為 null 時須有 tool_calls。
- tool call：`id`、`type:"function"`、`function:{name,arguments}`，arguments 是 JSON **字串**，不是 object。
- tool 結果：`role:"tool"`、`tool_call_id`、字串 `content`。呼叫 ID 在一份 assistant 回覆內唯一；工具結果必須對到前面的呼叫，不能重複或孤立。
- `tools` 每項為 `{type:"function",function:{name,parameters,description?}}`。parameters 是工具的 JSON Schema；工具名唯一，adapter 不支援的規則要拒絕，不能忽略。

[`llm-messages`](schemas/llm-messages.schema.json) 驗形狀；順序、ID 唯一性、arguments 能否解析及工具參數驗證由接件／agent 任務另驗。HTTP body 只送 model、messages、tools（有才送）、max_completion_tokens 與 stream；沒有 stream_path 送 `stream:false`，有則送 `stream:true`，〔使用者方向 2026-09-29 晚〕並加 `stream_options:{include_usage:true}`，要求 provider 最後附上 usage。供應商不支援就明確拒絕，不把輸出上限默默去掉。agent 發起端的設定、context 定位及用量格式見 [agent 任務 P-701／706／710](agent-tasks.md)。發起 node 先由原始檔整理有界 context；RPC 封包受 P-004 的 256 KiB 限制；messages 在 stdin JSON 材料內，仍受 agent 的 context 上限。

## P-407．LLM 結果、usage 與有限重試〔建議預設，未拍板〕

[`llm-result`](schemas/llm-result.schema.json) 的本地結果檔及 llm.chat stdout JSON 是 `version:1,node_id,job_id,attempts`；RPC result 仍是 P-403 的指令結果。`attempts` 依真正 HTTP 嘗試順序排列，每項帶 `attempt_id,status,reason,message,finish_reason,usage,http_status`。第一項 ID 對應請求；轉交中間層只轉送／保存同一組結果，不重新計一次 HTTP、不自行再做 provider 重試。重試前由池 tick 固定新 attempt ID 與前次結果、提交後才派出。後續 ID 由這條已提交關係核對，不必假裝仍是第一個 attempt。

每支 aos-llm-call 只做一次 HTTP，結果 attempts 只有一項；池任務收齊後按序組成 llm.chat 的 stdout JSON，再保存指令結果回應。最後一項就是這次請求結果，不另放重複的總狀態或總 usage。provider 回應先只取 choices[0].message 的 role/content/tool_calls；tool_calls 是 null 或空陣列就省略，content 為 null 且沒有 calls 就正規化為空字串（沿 proto5），其餘驗 P-406。官方附帶的 annotations 等非本版欄位不抄入結果；非空 refusal 明確記 response_invalid 並保留無 key 的拒絕證據，不假裝空白成功、不自動重試。成功的 message 是 P-406 的 assistant，finish_reason 原樣保存；`length` 表示模型輸出達上限，不能當產品任務完成。結果只看完整回應：串流時是串流正常結束後拼成的完整 message，中途斷掉不算完整；無可用 message 填 null。usage 只取三個計量欄（串流時取最後附帶的 usage，沒給就是不可得）；有完整的 `prompt_tokens,completion_tokens,total_tokens` 才記物件；不可得填 null，不補 0，也不把估算寫成 provider 實際 usage。部分 usage 的原始證據可以保留在私有診斷材料，不能冒充完整計量。

reason：`completed`（成功）、`rate_limited`（確定限流拒絕）、`rejected`（明確拒絕）、`not_sent`（可證明沒送）、`response_invalid`（收到完整但格式不合的回應）、`canceled`（確定未送且取消）、`unknown`（可能已處理）。缺失的 HTTP 狀態、finish_reason 都填 null。收到完整但無法驗證的 provider 回應不自動再問；傳輸中斷或遠端結果不明則 unknown。

有限重試與 unknown 占用完全依 [S-303／304](../scheduling/llm.md)；「交給 endpoint」的池不重試（P-405）。池 tick 保存 retry_at_ms，後續到期才派，SDK 自動重試關掉。每次用新 attempt_id，同 quota_scope 一起冷卻；達有限次數回 failed/rate_limited，unknown 不再派。usage 按 attempt 去重；缺失不補零，本機連線關閉不證明遠端停算。
