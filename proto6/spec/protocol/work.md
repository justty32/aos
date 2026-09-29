# 工作與 LLM 代發

← [共用約定與分工](README.md)｜[工作材料](../base/work.md)｜[LLM 池](../scheduling/llm.md)

## P-400．兩個入口〔使用者方向 2026-09-29〕

工具／job 用 `work.submit` 投所屬 kernel，LLM 用 `llm.complete` 投池管理 node。路由、提交與去重完全依 [messages](messages.md)。params.node_id 是歸屬 node，job_id 是邏輯工作，attempt_id 是本次嘗試；接件端核對可信來源，不信自報 node／reply_to。兩種 method 只回最終 result 或拒收 error，不先回 ACK 占用同 ID 回應。

## P-401．工作材料〔建議預設，未拍板〕

[`work-request`](schemas/work-request.schema.json) 的 params：

| 欄位 | 意思 |
|---|---|
| `node_id`、`job_id`、`attempt_id` | P-400 的配對識別 |
| `inst` | [inst 第 1 版](../base/inst.md) 原始物件；引用 [node-inst schema](schemas/node-inst.schema.json)，仍須在目標身分展開後驗證 |
| `base` | 原 inst 的絕對基準資料夾；複製材料不能偷偷換成工作資料夾 |
| `timeout_ms`（可省） | 放行後逾時，預設 60000，正整數 |
| `output_limit_bytes`（可省） | 每條捕獲串流上限，預設 1048576，正整數 |

kernel 接納時固定 inst 與必要輸入。需要固定 stdin bytes 就保存副本並使用該副本路徑；外部 `$ref`、程式及 workspace 不因此凍結，見 [B-101](../base/work.md)。工具呼叫先依 [A-401](../agent/tools.md) 驗參數、轉 inst；run／tool_call 對照留在發起 node。

## P-402．once 與工作材料〔使用者方向 2026-09-29〕

once 目標依 [P-010](README.md)，資源歸屬與最小啟動失敗證據依 [daemon P-104／110](daemon.md) 的未拍板提案。

〔建議預設，未拍板〕本篇為保存請求與結果，在 kernel 的 ignored 工作區建 `<attempt_id>/`，以其中的 `inst.json` 單檔登記；資料夾只是材料布局。每次實際嘗試使用不同資料夾，內含：

```text
<attempt_id>/
  inst.json          # daemon 跑的外層 inst
  request.json       # 已接納請求的固定副本
  input/             # 只有需要固定輸入時才有
  stdout.bin         # 有捕獲才有
  stderr.bin         # 有獨立捕獲才有
  result.json        # 執行器完整發布的 B-103 結果
```

外層 inst 的 argv 是 `aos-work --work-dir <絕對工作資料夾>`，`user` 明寫工作所屬 node 已授權的有效身分。內層 `request.json` 的 inst 省略 `user` 時繼承這個身分；寫了或整份指示詞展開後帶了 `user`，必須仍解析成同一 UID。kernel 不可讓工具繼承自己的較高權限；runner 也不能在內層再次切身分。

kernel 先 commit 接納的請求及固定材料依據，再建工作資料夾，以 daemon `node.register` 登記 `node_id=W/inst.json,parent_id=params.node_id,identity_grant=[有效身分],once=true`，再 `node.wake`。parent_id 是可信資源歸屬，與 W 的位置無關，核對規則只依 daemon 篇。工作結果及捕獲檔保留，kernel 下格核對、保存、commit 後才投回呼叫者。結果引用必須對接收者可讀；需要搬運就先複製完整輸出到可讀位置，再發布引用它的回應。

kernel 下格若讀到 `W/inst.json.launch-error.json`，先核對本次目標與可信 daemon 寫入來源，再合成 started:false／failed／start_failed 的工作結果；不把自報旁檔當證據。LLM wrapper 未啟動可合成 failed／not_sent。其他情況只看 result.json；wrapper exec 126／127、崩潰或自身回 125 卻無結果，均不能只靠登記消失推定內層沒跑，缺可保存的可信證據就 unknown。兩份證據矛盾時保留並報事項，不任取最後一份。重啟與重投依 [messages P-304](messages.md)。

## P-403．結果與串流〔建議預設，未拍板〕

[`work-result`](schemas/work-result.schema.json) 同時驗本地結果檔與回應。`result.json` 為 `version:1` 加結果欄位；RPC 的 `result` 直接是相同欄位，**不帶 version、不再包一層**。

| 欄位 | 意思 |
|---|---|
| `node_id`、`job_id`、`attempt_id` | 精確配回原工作與嘗試 |
| `status` | `succeeded`／`failed`／`canceled`／`unknown`，依 [C-03](../contracts.md) |
| `reason` | `exited`、`signal`、`start_failed`、`timeout`、`canceled`、`oom`、`output_limit`、`descendants_remaining`、`output_incomplete`、`unknown` |
| `started` | `true` 已進入 inst 的執行階段；`false` 根本沒跑；`null` 證據不足 |
| `exit_code`、`signal` | 可得的原退出碼或訊號；無資料填 `null`，兩者不同時有值 |
| `diagnostic`（可省） | 無 key 的有界診斷（最多 4096 字元）；可得時保留原始 errno 代號，例如 EAGAIN、ENOMEM |
| `stdout`、`stderr` | `{path,bytes,truncated}` 或 `null`；path 是可讀的絕對路徑，bytes 是實際保存量 |

`null` 表示沒有這份輸出證據；有檔且 `bytes:0` 才是確知空輸出。若 inst 使用 `inherit`，外層將對應 fd 接捕獲 pipe，才由 aos-work 保存為 `.bin`；inst 的一般檔案、append、merge、`/dev/null` 規則照正本，不偷偷改成捕獲。直接寫檔若不能證明這次保存的完整 bytes，結果該串流填 `null`；merge 不虛構獨立 stderr。捕獲上限、OOM 證據與收尾沿 [B-103](../base/work.md)、[B-202／204](../base/execution.md)。

正常退出 0 且後代清空才可 `succeeded/exited`；退出 7 是 `failed/exited`。125 不足以判定是否執行；`started:false/start_failed` 和子程式已跑、自己退出 125 必須分清。訊號保留 `signal`，不把 inst 的 `128+n` 合成碼當作 wait 的退出碼。工具語意錯誤與產品成功依 [A-403](../agent/tools.md)、[A-503](../agent/README.md)，不改程序證據。

## P-404．unknown 與拒收〔使用者方向 2026-09-29〕

unknown、重試及晚到結果依 [C-03](../contracts.md)／[S-401](../scheduling/operations.md)；kernel 合成 unknown 結果時缺失欄位填 null。已發布 RPC 回應不覆寫；可信晚到結果留在原 attempt 的證據旁，由來源核對補清本地狀態，不改舊回件。

拒收沿 P-005：參數錯 -32602；業務錯 -32000，data.code 可為 work_not_authorized、input_unreadable、capacity_unavailable、pool_not_found、model_not_found、key_unavailable。只在能確認尚未接納的暫時容量／讀取問題才可 retryable:true；接納後的失敗回結果。配對錯或衝突留原件及事項，不夾 key／認證標頭。

## P-405．代發啟動與池設定〔使用者方向 2026-09-29〕

**代發服務和管池的 kernel node 同帳號，所以該 kernel 讀得到 key；只有其他帳號的成員才有隔離。**key 不進 prompt、工作請求、結果、inst、argv 或給成員的環境。**沒 helper 時全樹同帳號，key 不受保護**（第八批）；要隔離須用 helper 配合不同帳號，或另用不同帳號跑代發並限制憑證檔權限。這是 OS 讀取權限的界線，不是 JSON 能保證的事。

〔建議預設，未拍板〕池管理 node 的任務表加入 `aos-llm --node <絕對 node 路徑> --config <絕對設定路徑> --phase PHASE`，再依 daemon 篇註冊、叫醒該 node。aos-llm 是短任務：收件、核對共享限制、派送、收結果便退出。它為每個實際 HTTP 嘗試建 P-402 的 once 資料夾，inst 改跑 `aos-llm-call --work-dir <絕對工作資料夾> --config <絕對設定路徑>`，使用池管理 node 的帳號。HTTP 等待由這支受 daemon 管的程序承擔，不占 node 的 tick。結果放工作資料夾，由後續池 tick 發回；LLM 工作沿用 once 的清理與恢復界線。

[`llm-config`](schemas/llm-config.schema.json) 是 `version:1` 與 `pools` 陣列，每項只有 `id`、`endpoint`、`model`、`quota_scope`，可加 `key_ref` 及有限正整數 `max_attempts`（預設 3）。endpoint 是無認證資訊、query、fragment 的 HTTP(S) base URL，末尾補 `/chat/completions`。model 是 provider 真名；同一份表不允許重複 pool id。共享 provider 帳戶／模型限制的項目必須使用相同 `quota_scope`，由同一池管理 node 的 tick 統一分配序號、在途占用及冷卻，不能各開一份計數繞過限制。

`key_ref` **只准出現在代發服務設定**，值是私有憑證檔絕對路徑；缺省＝不帶 Authorization。代發程序讀 key 建 HTTP header，禁止把原文存進 node 資料、git、交付檔或日誌；這是輸出約定，不是假裝同帳號的 kernel 無讀取權。私有憑證檔放在 node 樹外，只有部署授權的代發帳號可讀；同 UID 成員仍能讀到，不能宣稱靠放在樹外就隔離。設定及必要版本隨派工固定，已派出工作不讀到下一版；私有設定快照只存引用、不複製 key。

## P-406．LLM 請求與 messages〔建議預設，未拍板〕

[`llm-request`](schemas/llm-request.schema.json) 的 params 除工作識別，必填 `pool`、`model`、`messages`、`max_completion_tokens` 與正整數 `timeout_ms`；model 須符合該 pool 設定。可帶 `tools`，`stream` 只准 false 或省略。請求不能覆寫 endpoint、key 或加入任意 HTTP header。

messages 沿 [proto5 格式](../../../proto5/spec/aos-llm/request.md)，採 [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 的**文字與 function tool calls 子集合**，不是所有多模態欄位都支援：

- system／developer／user：`role`、字串 `content`。
- assistant：`role`、字串或 null 的 `content`，可有非空 `tool_calls`；content 為 null 時須有 tool_calls。
- tool call：`id`、`type:"function"`、`function:{name,arguments}`，arguments 是 JSON **字串**，不是 object。
- tool 結果：`role:"tool"`、`tool_call_id`、字串 `content`。呼叫 ID 在一份 assistant 回覆內唯一；工具結果必須對到前面的呼叫，不能重複或孤立。
- `tools` 每項為 `{type:"function",function:{name,parameters,description?}}`。parameters 是工具的 JSON Schema；工具名唯一，adapter 不支援的規則要拒絕，不能忽略。

[`llm-messages`](schemas/llm-messages.schema.json) 驗形狀；順序、ID 唯一性、arguments 能否解析及工具參數驗證由接件／agent 任務另驗。HTTP body 只送 model、messages、tools（有才送）、max_completion_tokens 與 stream:false；供應商不支援就明確拒絕，不把輸出上限默默去掉。發起 node 先由原始檔整理有界 context；超過 P-004 的 256 KiB 就拒收，本版 messages 只收內嵌陣列。

## P-407．LLM 結果、usage 與有限重試〔建議預設，未拍板〕

[`llm-result`](schemas/llm-result.schema.json) 的本地結果檔是 `version:1,node_id,job_id,attempts`；RPC result 去掉 version。`attempts` 依真正 HTTP 嘗試順序排列，每項帶 `attempt_id,status,reason,message,finish_reason,usage,http_status`。第一項 ID 對應請求；重試前由池 tick 固定新 attempt ID 與前次結果、提交後才派出。後續 ID 由這條已提交關係核對，不必假裝仍是第一個 attempt。

每支 aos-llm-call 只做一次 HTTP，結果 attempts 只有一項；池 tick 收齊後按序組成 RPC 回應。最後一項就是這次請求結果，不另放重複的總狀態或總 usage。provider 回應先只取 choices[0].message 的 role/content/tool_calls；tool_calls 是 null 或空陣列就省略，content 為 null 且沒有 calls 就正規化為空字串（沿 proto5），其餘驗 P-406。官方附帶的 annotations 等非本版欄位不抄入結果；非空 refusal 明確記 response_invalid 並保留無 key 的拒絕證據，不假裝空白成功、不自動重試。成功的 message 是 P-406 的 assistant，finish_reason 原樣保存；`length` 表示模型輸出達上限，不能當產品任務完成。只接完整非串流結果；無可用 message 填 null。usage 只取三個計量欄；有完整的 `prompt_tokens,completion_tokens,total_tokens` 才記物件；不可得填 null，不補 0，也不把估算寫成 provider 實際 usage。部分 usage 的原始證據可以保留在私有診斷材料，不能冒充完整計量。

reason：`completed`（成功）、`rate_limited`（確定限流拒絕）、`rejected`（明確拒絕）、`not_sent`（可證明沒送）、`response_invalid`（收到完整但格式不合的回應）、`canceled`（確定未送且取消）、`unknown`（可能已處理）。缺失的 HTTP 狀態、finish_reason 都填 null。收到完整但無法驗證的 provider 回應不自動再問；傳輸中斷或遠端結果不明則 unknown。

有限重試與 unknown 占用完全依 [S-303／304](../scheduling/llm.md)：池 tick 保存 retry_at_ms，後續到期才派，SDK 自動重試關掉。每次用新 attempt_id，同 quota_scope 一起冷卻；達有限次數回 failed/rate_limited，unknown 不再派。usage 按 attempt 去重；缺失不補零，本機連線關閉不證明遠端停算。

## P-408．程式契約〔建議預設，未拍板〕

| 完整 argv | 讀寫、身分與輸出 |
|---|---|
| `aos-work --work-dir W` | 讀 W/request.json 及目標身分可讀的材料，以 `base` 跑內層 inst；寫捕獲檔、W/result.json。用工作 node 身分，無切身分權限 |
| `aos-llm --node N --config C --phase PHASE` | 作為 N 的註冊任務，讀 C、已接納請求／結果與池狀態，寫同 node 追蹤資料及 ignored once 資料夾；用 N 的 user。collect 複製收件及整理結果；prepare 固定下一次請求／回應；dispatch 只送已提交的請求／回應並登記、叫醒 once；cleanup 核對已提交證據後刪相符收件原件。後兩階段分成後組並 needs 相應前組，依 [node P-206](node.md)，不靠 commit callback |
| `aos-llm-call --work-dir W --config C` | C 必須是本次固定的設定副本；讀 C、私有 key_ref 與 W/request.json，只送一次 HTTP，寫 W/result.json；用池管理 node 的 user |

三支程式 stdin 都是 `/dev/null`，stdout 保留為空（業務輸出走檔案），stderr 只放無 key 的 `代號: 白話` 診斷；內層 inst 的 stdin／stdout／stderr 另依 P-403。不新增必需 `AOS_*` 環境變數，PATH／目標帳號環境及 inst.envs 依 inst 正本，不從呼叫者環境取得池 key。

結束碼：0＝這次處理完成且必要結果已完整發布（工作本身仍可能 failed／unknown）；2＝用法／設定錯，未開始；125＝自身無法開始；1＝已開始處理後自身失敗（包括結果寫不出），不能把未發布結果算成功。aos-llm 的 0 只表示本格步驟完成，不代表 HTTP 工作成功。工作 inst 的內層退出碼只記在工作結果，不能拿 wrapper 的 0 代替。訊號由父程序看 wait 狀態；wrapper 沒寫結果時只按 P-402 的旁檔／unknown 規則處理。

## P-409．schema 與最小範例〔建議預設，未拍板〕

每行兩份檔都在 [examples/work/](examples/work/)。schema 只能驗 JSON 形狀，P-002 的重複 key、有限數、位元組上限與執行授權另驗。

| schema | 正例 | 主要錯誤例與原因 |
|---|---|---|
| [work-request](schemas/work-request.schema.json) | [最小請求](examples/work/work-request.minimal.valid.json) | [零逾時](examples/work/work-request.zero-timeout.invalid.json)：必須正整數 |
| [work-result](schemas/work-result.schema.json) | [結果檔](examples/work/work-result.minimal.valid.json) | [假成功](examples/work/work-result.false-success.invalid.json)：成功卻 exit 7 |
| 同上 | [RPC 回應](examples/work/work-response.minimal.valid.json) | [雙分支](examples/work/work-response.both-branches.invalid.json)：result/error 同時有 |
| [llm-config](schemas/llm-config.schema.json) | [池設定](examples/work/llm-config.minimal.valid.json) | [明文 key](examples/work/llm-config.inline-key.invalid.json)：不接受 api_key 欄位 |
| [llm-request](schemas/llm-request.schema.json) | [最小請求](examples/work/llm-request.minimal.valid.json) | [串流](examples/work/llm-request.streaming.invalid.json)：首版不支援 |
| [llm-result](schemas/llm-result.schema.json) | [結果檔](examples/work/llm-result.minimal.valid.json) | [漏回覆](examples/work/llm-result.missing-message.invalid.json)：成功沒有 assistant message |
| 同上 | [RPC 回應](examples/work/llm-response.minimal.valid.json) | [部分 usage](examples/work/llm-response.partial-usage.invalid.json)：不冒充完整用量 |

## P-410．待決與跨篇

見 [README P-008](README.md#p-008)。
