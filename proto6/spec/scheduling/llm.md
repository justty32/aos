# LLM 入場、用量與未知結果

← [排程](README.md)｜[attempt 狀態](runs.md)

以下均為〔建議預設，未拍板〕。責任為控制端額度管理；agent決定context，client只執行一次請求。這是受管呼叫契約，不聲稱可攔住持有其他金鑰自行出網的程序。

## S-301．請求與 quota scope

LLM payload 必填 `endpoint_id:ID`、`model:string`、`messages_ref:BlobRef`、`input_tokens_estimate:int>=0`、`max_output_tokens:int>=1`、`request_timeout_ms:int>=1`；可省 `stream:bool=false`。endpoint設定由管理者持有，含URL、憑證引用及適用scope ID陣列；job不得傳任意URL或金鑰。scope以帳戶／模型等真實共享限制建立，不把不同URL當成必定獨立。

Scope必填 `scope_id`、`max_concurrent:int>=1`、`window_ms:int>=1`；可省 `request_limit:int>=1|null`、`token_limit:int>=1|null` 預設null表示未配置該維度。token模式首版保守計估計input+要求max_output；adapter可改為供應商語意，但必須版本化。缺tokenizer仍可用標明estimated的上界估法，不宣稱精準硬保供應商額度。

驗收：Given 兩endpoint共scope且只餘一席，When 同時ready，Then 只一請求入場，另一顯示相同scope等待；工具不能改scope逃避限制。

## S-302．預留與結算

Reservation 必填 `attempt_id`、`scope_ids:ID[]`、`state:held|sent|settled|uncertain|released`、`reserved_requests:int=1`、`reserved_tokens:int>=0`、`created_at_ms`、`expires_at_ms`。可省 `sent_at_ms`、`usage_ref:BlobRef` 預設null。一次交易檢查全部scope的window內消耗與held預留及concurrency，同時檢查S-306的run剩餘預算；全足夠才hold，否則零占用。已hold但尚未送出超過30秒預留租期須核對launcher；確定未送才release，不能僅看時間釋票。

client送出前持久標sent，再允許HTTP；這個窗口即使實際沒送也可能保守判uncertain。可信結果攜帶usage與attempt_id後只結算一次。成本帳記實際已知用量，速率帳按adapter規則保留window消耗；不能因輸出短就一律退還供應商已算過的token估額。重複usage同digest忽略，不同digest報conflict。

驗收：Given hold已落盤而client尚未獲go就崩潰，When 證明未送出，Then release且無成本；若sent已落盤但結果缺失，Then uncertain而非直接零成本重試。

## S-303．限流與可重試失敗

429且adapter判為暫時限流時，保留該次attempt失敗證據，job→waiting；`next_due_at_ms` 至少為有效Retry-After時間。無有效提示則預設退避 `min(60000,1000*2^(ordinal-1))` ms，再加0至250ms持久記錄的jitter；每次attempt均計入max_attempts，達上限job→failed。同scope下一次派送不得早於其cooldown；其他獨立scope不被一起停住。

授權、帳務與不可執行輸入錯誤不作無限重試。SDK內建重試必須停用或納入同一attempt預算，不能暗中放大次數。明確未送出的連線建立失敗可依safe政策重試；可能已送出後的斷線依S-304。工具與普通LLM初值max_attempts=1，管理政策可明設有限值。

驗收：Given max_attempts=2且mock兩次回429，When 到期重試，Then 只有兩次實際嘗試，第二次失敗後終止；另一獨立scope仍能前進。

## S-304．取消與不確定性

已排隊而未sent的取消可釋放預留；sent後取消只停止本機等待／連線，不保證遠端停算。未知attempt保持unknown，run→needs_attention，不能由一般timeout自動再問。普通stream片段不是完整結果的證據。

本機HTTP名額在本機連線確定關閉後可回收；遠端不確定名額另記。管理設定必填 `uncertain_hold_ms:int>=1`，期限自本次request deadline起算，過期可釋放本地估計的remote佔額但保留uncertain記錄與估算成本；這只防止永久停擺，不宣稱遠端已停止或實際concurrency硬保證。若部署要求無法超出遠端concurrency，profile必須提供可查終止證據，否則停scope等待人工，不能使用估計釋放。

驗收：Given 遠端可能已完成但網路中斷，When timeout與重啟，Then 無第二attempt；查詢保留unknown與估額。人工同意重試按S-104另建attempt，費用可能重複的風險不被隱藏。

## S-305．串流與 final

首版stream=false；要求true而adapter不支援回invalid_record。未來支援時，每片段必填attempt_id、`chunk_seq:int>=1`、`text:string`、`ephemeral:bool`；片段按序去重，缺片不推斷後續內容。它們可展示但不能把job設succeeded。只有通過完整回應驗證、usage處理及result持久提交的終局才是Outcome。

沒有final而已展示部分文字的工作仍可能unknown。回覆串流、輸出檔追蹤與wake通知各自獨立，不用同一個JSON-RPC id重複發終局回應冒充串流。

驗收：Given 已顯示兩片段但final前中斷，When 使用者查run，Then 顯示部分內容加unknown／未完成，不回成功答案；沒有stream功能時立即喚醒照常可用。

## S-306．有限的 run 預算

Run接納時固定 `budget` object：可省 `max_jobs:int>=1=32`、`max_llm_attempts:int>=1=16`、`max_tokens_estimate:int>=1=100000`、`max_elapsed_ms:int>=1=600000`。這些是可替換起始預設，不是使用者指定額度。可信政策可調整，普通tool不得自行提高。max_jobs計tool／llm邏輯job，排除控制tick；max_llm_attempts計實際建成的LLM attempt，包括未知／失敗。active經過時間包含遠端等待，paused／needs_attention停表；控制層保存累計與最近計時起點。

控制帳本保存jobs_created、llm_attempts_created、tokens_known、tokens_uncertain、tokens_reserved非負整數。新job提交先查job餘量，LLM入場以完整payload由可信估算器重算token需求，不只相信agent估值；和scope一起交易hold run token。成功usage移入known並釋放對應reserved；未送可撤reserved，未知移入uncertain，不自動歸零。真usage超估仍照實記，餘量可耗盡但不得寫負用量。

任一預算不足時停止新的job／attempt，run→needs_attention、Error.code=budget_exceeded，已在途先保存結果，不偷偷丟失或無限自我tick；時間到期另外取消在途本機工作，清空／unknown按原規則處理。後續run不越過此當前run。首版沒有同run加額API：操作者可按run.cancel收尾，或run.resolve fail/cancel_with_unknown處置未知，再以新輸入建run。context只讀餘量快照，不先占scope門票等tick組context。

驗收：Given 模型反覆要求工具且每次都成功，When 建立第33個非tick job或耗盡其他預算，Then 不再派新job，run可查budget_exceeded，無合法無限循環。Given token估額不足而quota scope尚有額度，When 入場，Then 兩邊都不hold，run進needs_attention。
