# 任務輪次、claim 與恢復

← [排程](README.md)｜[共用識別](../contracts.md)

以下均為〔建議預設，未拍板〕，責任為控制帳本寫入者。一輪任務語意可替換，但所有入口與驗收須一起改。

## S-101．接件與輪次

每則普通已接納訊息建立一個 queued run，按該 agent 的 input_seq FIFO；同 agent 最多一個「當前 run」，包括 active、已開始的 paused、needs_attention。未開始的 paused 留在 FIFO 原位置，預設阻擋後來的 run，直到恢復或取消。普通新訊息只建後續 run，不插入當前 context。

控制交易一併保存輸入索引與 run，才回 accepted。該 run 的 config_revision／tools_revision／context_revision 在接納時已固定快照；從 queued 切 active 不能悄悄換版。維護 tick 不建立人可見任務，其 job.run_id=null；它不得生成工具／LLM 工作或 final。需要語意工作的維護，由可信系統 principal 經 agent.submit 投普通輸入建立可見 run，沿用相同 input_ids 契約。

驗收：Given R1 active 且再投兩則訊息，When 成功收件，Then R2／R3 queued，各保留原輸入；R1 看不到自動插入的新要求，R2 不越過 R1。

## S-102．Run 合法轉移

新增控制欄位 `cancel_requested:bool=false`、`paused_from:queued|active|null=null`。合法邊為：queued→active／paused／canceled；active→paused／succeeded／failed／needs_attention／canceled；paused→queued 或 active（由 paused_from 決定）／canceled／needs_attention；needs_attention→active／paused／failed／canceled。三種終局無外出邊；要再做是新 run。

pause 先保存原狀態再停新派工，不殺在途，結果照收。cancel 先持久 cancel_requested=true、停止新派工並要求回收；只有全部本機工作已清空、沒有尚未分類的結果不確定性才 canceled。有未知則 needs_attention，保留取消要求；人工接受未知風險或證據補齊後才能完成取消。成功需有效 final_ref、全部已委託tool／llm工作有被消費的確定結果、無 pending 新委託及 cancel_requested=false；控制tick job排除，不讓目前tick等待自己終局。agent idle 不是充分條件。

驗收：Given active run 的工具仍活著，When cancel，Then 先看到 cancel_requested 而非假裝 canceled；若工具結果不明則 needs_attention，重啟也不解除取消要求。

## S-103．同 agent 一個狀態寫入者

Claim 邏輯紀錄必填 agent_id、attempt_id、generation、`checkpoint_revision:int>=0`、`claimed_at_ms`、`heartbeat_at_ms`、`lease_ms:int>=1`（預設30000）、`state:held|suspect|released`。控制交易只在無held/suspect claim、無未清空前代tick程序時配置新 generation 與 tick attempt；同 agent 的家鎖仍是執行互斥的第二層。

可信 supervisor 按 [B-602](../base/lifecycle.md) 每10秒更新活性（可配置且小於lease）；過期只使 claim suspect，不立即重派。管理端確認原 tick 及其受管範圍退出、收導入結果後，才 released／增加 generation。提案按 C-05 generation＋revision fencing；同 attempt 僅能提交一份提案，重送相同 digest 回原收據，不同 digest 衝突。tick 程序可以崩潰，但控制端不能把「lease過期」當作它已死。

驗收：Given 舊 tick 仍運行但 heartbeat停了，When lease到期且新通知來，Then 標suspect且不開第二tick；舊代清空後才重派，遲來舊提案被拒。

## S-104．Job、attempt 與 retry

job queued↔waiting（依due／名額條件）、queued/waiting→admitted、admitted→running／failed／canceled／unknown、running→succeeded／failed／canceled／unknown。未入場可直接canceled。failed→queued或waiting 僅限確定失敗、retry_class=safe、嘗試未達max_attempts及run未暫停取消；next_due 記錄退避。其餘終局不能自動轉回queued。unknown只能經新證據導入或S-401人工處置。

attempt reserved→starting／failed／canceled；starting→running／failed／canceled／unknown；running→canceling／succeeded／failed／unknown；canceling→canceled／failed／unknown。unknown可經同attempt可信結果補齊至succeeded／failed／canceled，但保留舊事件。attempt不回reserved；重做一定新ID。selected_attempt_id於控制層接受該attempt終局時設定；若人工已指定新attempt，舊attempt晚到只入證據，不覆寫job結果或再次結算。

max_attempts計算已建立的attempt數，預設1。人工對unknown選重試須附 `allow_duplicate_effects:true` 與 `new_max_attempts:int`，且比既有attempt數大；控制端先確認舊本機程序清空，再設新上限、撤銷舊選定、job→queued。原unknown attempt仍存在，這不是exactly-once保證。

驗收：Given max_attempts=1且第一次送出後未知，When 一般timeout處理，Then 不產生第二次；只有具權限的明確風險接受與上限提高才可建立新attempt，舊結果不蓋新結果。
