# 工具與單次 LLM client

← [Agent](README.md)｜[共用契約](../contracts.md)

## A-401 能力清單與參數〔建議預設，未拍板〕

manifest 是不可變工具清單。每項必填 `name:ID`（清單內唯一）、`description:string`、`input_schema:object`（JSON Schema 2020-12 的受支援子集）、`exec_ref:BlobRef`（下述不可變 ExecTemplate）、可省 `result_mode:text|json`（預設 text）、可省 `result_schema:object|null`（預設 null；json 時必填）。不支援的 schema keyword 於登記時拒絕，禁止忽略後假裝驗證。首版 keyword 白名單精確為 `type,properties,required,additionalProperties,items,enum,minLength,maxLength,minItems,maxItems,minimum,maximum,description`，其他 keyword 一律拒絕，包含 $ref、組合條件與 default。type 必填且為 object/array/string/number/integer/boolean/null 其中一個字串，不接受型別陣列；input_schema 根必須 object。properties 值及 items 遞迴使用同一子集，additionalProperties 只收 boolean（省略 true）；required 為不重複字串陣列；enum 為非空不重複 JSON 值陣列。四個長度上下限為非負整數，數值上下限為有限 number，所有 min 不大於 max；description 為字串。keyword 適用型別、字串字元長度及 enum 相等比較按 JSON Schema 2020-12，bool 不算 integer。

ExecTemplate 必填 version:1、argv:非空字串陣列；可省 cwd（預設本 run 固定設定的 cwd）、env、timeout_ms、output_limit_bytes，其型別與預設沿 [B-101](../base/work.md)。Template 不接受 agent_id/run_id/job_id/stdin_blob 或其他欄位。adapter 從可信 claim 補 owner／run／job，複製固定 argv，將驗證後 arguments 以 RFC 8785 UTF-8 JSON 保存為單一 stdin_blob，再形成完整 B-101 工作描述；stdin 只含 arguments 物件，無附加換行，不把參數放到 argv、不拼 shell，大小不得超 B-101 stdin 上限。工具需自行讀 stdin JSON；既有 CLI 由明示固定 argv 的 wrapper 轉接。模型 tool call 必填 `call_id:ID`、`name:ID`、`arguments:object`，同一回覆內 call_id 唯一。不存在工具、重複 call_id、無效參數或清單缺失一律不派工；產生具欄位路徑的 `tool_request_invalid` 結果供下一次思考。連續兩次 LLM 回覆整體格式無效，run → needs_attention、phase error，避免無界修補迴圈；合法回覆將此計數歸零。

驗收：Given 工具要求 integer 而模型傳字串；When agent 處理 call；Then 沒有工具程序，歷史留下參數路徑與結構錯誤。

## A-402 委託執行邊界〔使用者方向 2026-09-28，連 notes〕

來源：[工具繼承委託員工權限](../../notes/2026-09-28-employee-identity.md)。工具代表 caller 行事，沿用 agent 的 Linux 身分及資源歸屬，包含工具內再次呼叫工具／LLM。登記工具不授予檔案權限；執行與降權由基底處理。agent 只提出以 agent_id/run_id 為 owner 的 job，不能傳任意 UID 代替 owner。模型選多工具不代表可以繞過排程准入；工具任意本地執行仍受 OS 資源邊界，透過 aos 發送的後續 job 必須延續同一 owner。

驗收：Given A 呼叫會派出後續工作的工具；When 底座接受工作；Then 所有後續 job 的 owner 仍是 A，無法藉參數換成 B 的資源額度。

## A-403 結果封套與解讀〔建議預設，未拍板〕

結果只採用 [B-103](../base/work.md) 的 ExecResult：C-03 Outcome.result_ref 指向它，stdout／stderr 引用名稱固定為 stdout_blob／stderr_blob；不另造 agent 專用權威結果。OutcomeAdapter 是純讀取轉換：用 job_id 找回 call_id，讀取 Outcome.status/error 及 ExecResult 的 exit_code、reason、stdout_blob、stderr_blob、truncated，按 [A-303](memory.md) 形成有來源的模型可見結果封套。text 模式以 UTF-8 解碼 stdout，無效位元組記 tool_result_invalid，原始 blob 保留；json 模式只有 stdout 已完整保存且未截斷才驗證回傳值；可驗證時解析完整 stdout，拒絕重複 key、非有限數值及尾隨資料，再驗 result_schema。stderr 是診斷，不冒充回傳值；null 串流引用不冒充已保存空字串。模型可見結果封套必填 version:1、call_id:ID、outcome:Outcome、exec_result_ref:BlobRef|null、stdout_preview:string、stderr_preview:string、preview_truncated:bool、output_truncated:bool、semantic_error:Error|null；兩個預覽預設空字串但仍必填，preview_truncated 表示 A-303 的展示裁切，output_truncated 沿 ExecResult.truncated 表示底座資料已截斷，兩者不可混用。控制層確認 attempt 所屬及終局後，agent 才將結果配回原 call。重送相同 attempt 結果僅消費一次；相矛盾結果進 needs_attention，不任取最後一份。

exit 0 只代表程序正常結束；json 模式解析／schema 失敗記 `tool_result_invalid`，底座 attempt 的成功事實不改寫，語意錯誤交給 agent。非零退出、timeout、取消與部分輸出均保留並明確標示，不只留「失敗」文字。預設不因語意錯誤自動重跑工具；agent 如決定再次呼叫，建立新的 job 並引用前次證據，仍受 run 預算限制。

驗收：Given exit 0 的工具輸出不符合 result_schema；When agent 收到結果；Then 可見語意格式錯誤與原始結果，沒有自動重跑。

## A-404 LLM 與未知結果〔建議預設，未拍板〕

cloud LLM client 一次只做一個已准入請求，輸出原始回覆及用量；它不執行工具、不修改 history、不自行重試、不自行換 endpoint。agent 解讀回覆並提出下一步。請求／回覆 schema 無效按 A-401 處理；提供者拒絕等明確失敗保留結構化錯誤，重試政策交排程。

工具或 LLM 在外部效果可能已發生但缺乏可靠結果時，job/attempt 為 unknown，run → needs_attention、phase error。保留 request、attempt、時間及已有輸出，禁止 agent 自動把 unknown 當 failed 重試。補回原 attempt 的結果只能走可信結果導入；操作者不得以文字偽造成功。人工處置依 [S-401](../scheduling/operations.md) 的 run.resolve：retry 必填 allow_duplicate_effects=true、new_max_attempts 且大於既有 attempt 數；若 cancel_requested 尚在，另必填 clear_cancel_requested:true，僅由合法 resolve 交易清除取消要求並重試，依 [S-104](../scheduling/runs.md) 確認舊本機程序清空後才建新 attempt；fail／cancel_with_unknown 保留原 unknown 證據。控制層持久記錄決議，禁止普通 resume 隱含重試；單純重啟或解除取消要求也不消除 unknown。

驗收：Given API 已送出而回覆前失聯；When daemon 重啟；Then 此 attempt 顯示 unknown，沒有第二次 API 呼叫，須有持久人工決議才續行。
