# 任務輪次、claim 與恢復

← [排程](README.md)｜[共用識別](../contracts.md)

以下均為〔建議預設，未拍板〕，責任為控制帳本寫入者。一輪任務語意可替換，但所有入口與驗收須一起改。依 [09-29 裁定](../../notes/2026-09-29-verdicts.md) 1，「一輪任務」是後續設計的軟性原則，本篇 run 語意是建議預設；任務途中新訊息的歸屬暫不定案。

## S-101．接件與輪次

〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 A1 輪次部分、B3〕本節是輪次建立與輸入歸屬的唯一規範來源；以下仍是可替換預設，任務途中新訊息的歸屬未定案。

每則普通已接納訊息建立一個 queued run，run 必填 `input_seq:int>=1` 且只綁定該訊息，[C-02](../contracts.md) 的 input_ids 僅含這則 request_id，按該 agent 的 input_seq FIFO；同 agent 最多一個「當前 run」，包括 active、已開始的 paused、needs_attention，queued 與未開始的 paused 不占此位置。未開始的 paused 留在 FIFO 原位置，預設阻擋後來的 run，直到恢復或取消。普通新訊息只建後續 run，不插入當前 context，也不隱含取消。

控制交易一併保存輸入索引與 run，才回 accepted。該 run 接納時的版本欄位只保存 `config_revision`，指向引用工具、context policy 與模型設定的不可變 bundle；新設定依 [A-102](../agent/configuration.md) 在下一次 tick 開始時換上並留下換版紀錄，不得在 tick 中途換版。維護 tick 不建立人可見任務，其 job.run_id=null；它不得生成工具／LLM 工作或 final。需要語意工作的維護，由可信系統 principal 經 agent.submit 投普通輸入建立可見 run，沿用相同 input_ids 契約。

驗收：Given R1 active 且再投兩則訊息，When 成功收件，Then R2／R3 queued，各保留原輸入；R1 看不到自動插入的新要求，R2 不越過 R1。

## S-102．Run 合法轉移

〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 A1 輪次部分〕本節是暫停、恢復、取消與 run 轉移的唯一規範來源。

控制請求使用 RPC `run.pause`、`run.resume`、`run.cancel`；外層 id 為 request_id，params 必填 `run_id:ID`（run.resume 另可省管理者用的 `budget`，見 [methods](../base/methods.json)），target agent_id 由受權限檢查的 run 解析，不另收 action 或 UID。控制層依 [A-201](../agent/input.md) 的同一去重 scope 去重並檢查權限。重複同 action 回目前狀態，終態 run 的 pause/resume 回 `run_terminal`。

新增控制欄位 `cancel_requested:bool=false`、`paused_from:queued|active|null=null`。合法邊為：queued→active／paused／canceled；active→paused／succeeded／failed／needs_attention／canceled；paused→queued 或 active（由 paused_from 決定）／canceled／needs_attention；needs_attention→active／paused／failed／canceled。三種終局無外出邊；要再做是新 run。

pause 使 queued/active→paused，先保存 paused_from 再停新派工，不殺在途，結果照收。resume 使尚未開始的 paused→queued、已開始的 paused→active，後者從已保存的 continuation 接續，phase 依 [A-503](../agent/tick.md) 推導。普通 resume 不解除 unknown 或 cancel_requested；取消要求尚在而要 retry，須依 [S-401](operations.md) 由 run.resolve 額外明填 clear_cancel_requested:true，控制層在同一 resolve 交易驗證、清除取消要求並授權重試。

cancel 對 queued/paused/active/needs_attention 先持久 cancel_requested=true、停止新派工並要求回收；全部已委託工作有確定終局（unknown 依 [S-401](operations.md) 人工接受風險者除外）且本機工作已清空後才完成取消，不能把取消要求當成已停止的證據。有未知則 needs_attention，保留取消要求，不自動重試；未知部分須人工接受風險或由證據補齊，不得留下尚未分類的結果不確定性。這些控制狀態持久化，重啟後繼續回收或核對，不能因重啟解除暫停／取消要求。

〔使用者方向 2026-09-29，裁定 4〕**可選的 resume 重新驗證出口**：非 unknown 原因的 needs_attention（config_unavailable、blob 缺失／校驗失敗、storage_blocked、連兩次無效回覆、context_over_budget、budget_exceeded），修好後 owner／管理者可送 run.resume；控制層在同一交易重新驗證該原因已消除（引用內容可讀且摘要相符、容量可寫、預算足夠、必要材料可容納；連兩次無效回覆以該次 resume 為人工決議、計數重新起算），通過才 needs_attention→active 並從已保存的 continuation 接續，否則回 conflict、保持原狀並列出仍未解除的原因。實作可只提供取消：此時對 needs_attention 的 resume 回 conflict，`details.reason=resume_unsupported`，只能 run.cancel 另建新 run。有 unknown 或 cancel_requested 時此出口一律不適用，改依 S-401。run 成功的證據條件依 [A-503](../agent/tick.md)，agent idle 不是充分條件。

驗收：Given active run 的工具仍活著，When cancel，Then 先看到 cancel_requested 而非假裝 canceled；若工具結果不明則 needs_attention，重啟也不解除取消要求。Given run 因 blob 校驗失敗進 needs_attention 且 blob 已修復，When run.resume，Then 提供出口的實作重新驗證後回 active、不重做已提交副作用；未提供出口的實作回 conflict（resume_unsupported）而 run 保持 needs_attention，仍可 run.cancel。

## S-103．同 agent 一個狀態寫入者〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 A1 claim 部分、B2〕

排程層依 [B-602](../base/lifecycle.md) 的 claim 契約取得 tick 執行機會；claim 欄位、程序互斥、活性及回收條件以該條為準。已有 tick 或正在清理舊 tick 時，新通知只更新 pending 與 [S-201](admission.md) 的 ready 投影，不另開狀態寫入者。claim 釋放後重新檢查 run 屏障與准入條件，再決定是否派下一個 tick；不得把 claim 釋放當成 run 已完成。

驗收：Given 舊 tick 到 deadline 後尚在清理且新通知到達，When 排程重新檢查，Then 新通知不遺失，待 B-602 允許釋放 claim 後，才依 ready、run 屏障與准入條件決定後續 tick，不把逾時或回收當成 run 成功。

## S-104．Job、attempt 與 retry

job queued↔waiting（依due／名額條件）、queued/waiting→admitted、admitted→running／failed／canceled／unknown、running→succeeded／failed／canceled／unknown。未入場可直接canceled。failed→queued或waiting 僅限確定失敗、retry_class=safe（S-303 確定未執行的限流失敗例外，不看 retry_class）、嘗試未達max_attempts及run未暫停取消；next_due 記錄退避。其餘終局不能自動轉回queued。unknown只能經新證據導入或S-401人工處置。

attempt reserved→starting／failed／canceled；starting→running／failed／canceled／unknown；running→canceling／succeeded／failed／unknown；canceling→canceled／failed／unknown。unknown可經同attempt可信結果補齊至succeeded／failed／canceled，但保留舊事件。attempt不回reserved；重做一定新ID。selected_attempt_id於控制層接受該attempt終局時設定；若人工已指定新attempt，舊attempt晚到只入證據，不覆寫job結果或再次結算。

max_attempts計算已建立的attempt數，預設1（LLM job 預設3，見S-303）。人工對unknown選重試須附 `allow_duplicate_effects:true` 與 `new_max_attempts:int`，且比既有attempt數大；控制端先確認舊本機程序清空，再設新上限、撤銷舊選定、job→queued。原unknown attempt仍存在，這不是exactly-once保證。

驗收：Given max_attempts=1且第一次送出後未知，When 一般timeout處理，Then 不產生第二次；只有具權限的明確風險接受與上限提高才可建立新attempt，舊結果不蓋新結果。
