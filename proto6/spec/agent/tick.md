# Tick、狀態與恢復

← [Agent](README.md)｜[共用契約](../contracts.md)

## A-501 每次推進的責任〔建議預設，未拍板〕

tick 是一次短暫語意推進，輸入為可信 claim、固定版本、目前 checkpoint 與已登記的新證據；輸出為 C-05 Proposal。它可以整理本輪輸入、選 context、解讀已完成工作、提出下一批 job 或回答。它不能自行執行 cloud LLM、繞過底座啟動工具、直接改寫權威 checkpoint pointer 或派工表。

每個 agent 同時最多一個有效 tick claim。generation 由控制層配置，整數 >=1；回收舊 claim 後新 claim 使用新 generation。控制層只接受目前 claim 所屬 attempt、generation 及 expected_revision 均匹配的 proposal。每 tick attempt 最多提交一份 proposal；同 attempt 同摘要重放回同收據，異內容回 conflict。generation 失效回 stale_generation，既不推進 cursor 也不建立 job。

前置條件為 run active 且未有暫停／取消／錯誤屏障；控制層提交交易內再查一次。暫停或取消與提案競爭時，後提交的提案不得越過已保存的屏障，回 conflict 供重新讀取；不丟掉已登記的結果。run_id=null 的維護或空探查 tick 只可提交 agent 維護 checkpoint、phase idle、finish none，new_jobs 及消費本輪工作陣列均空；不能藉此建立未登記任務。有效當前 run 的普通推進才可提出工具與 LLM 工作。

驗收：Given 舊 tick T1 遲到且新 tick T2 已取得較高 generation；When T1 提交；Then 被拒絕，T2 的 checkpoint 與派工資料不變。

## A-502 Checkpoint 與提交次序〔建議預設，未拍板〕

checkpoint blob 必填 `version:1`、`phase`、`pending_job_ids:array<ID>`、`history_tail:int>=0`、`input_seq:int>=0`、`invalid_response_count:int>=0`；可省 `wait_reason:result|budget|due|operator|null` 與 `due_at_ms`，預設 null；可省 `continuation_ref:BlobRef|null` 預設 null，保存待執行決策或 context 選擇；可省 `history_append:array<HistoryEvent>` 與 `outputs:array<Output>`，預設 `[]`，分別沿 A-301 及 A-203 的事件／回覆格式，且各紀錄含 version:1。新本體初值 idle、空陣列、三個計數皆 0。wait 必須有 wait_reason；due 等待必須有 due_at_ms，其他等待不得憑空設輪詢間隔。

tick 先產生不可變候選 blob，可信導入器校驗、保存後取得 BlobRef，再提交 C-05 原子交易。交易一次更新 checkpoint pointer、revision、輸入／結果消費 cursor、歷史可見引用、phase 與 job 意圖；proposal 的 consumed_input_ids 必須屬本 run，consumed_attempt_ids 必須是已登記且未消費的結果。history 新事件索引由 checkpoint 的 history_append 提供，回覆索引由 outputs 提供，控制層驗證序號連續、引用存在及 run 歸屬後登記。

重啟以 SQLite 已提交 pointer 為準，不把檔案修改時間視為先後。提交前崩潰可重算；提交後但回執前崩潰可重送相同 proposal。未持久寫入控制交易的任何新 job 都不得執行。pending_job_ids 必須等於本輪 kind=tool|llm 工作中「尚未確定終局，或結果尚未消費」的集合，由控制層核對；kind=tick 是控制工作，一律不納入 pending 或語意消費集合，避免當前 tick 等待自己結束。tick 不可刪去未知工作以宣告完成。

驗收：Given proposal 同時包含消費工具結果與新 LLM job；When 在交易中途注入失敗；Then 兩者皆不提交；重放後兩者只共同提交一次。

## A-503 Phase 與完成契約〔建議預設，未拍板〕

phase 合法轉移由下列條件決定；控制層拒絕不符合條件的跳轉。

| 原 phase | 新 phase | 必要條件 |
|---|---|---|
| idle | think | 下一 queued run 被准許啟動 |
| think | act | 已有經驗證的工具決策待提交 |
| think / act | wait | 工作意圖已提交或確有 budget/due 等待 |
| act | think | 呼叫被本地驗證拒絕，形成可解讀錯誤 |
| wait | think / act | 證據到達或等待條件解除；由 continuation 決定 |
| think / act / wait | idle | 當前 run 已滿足終局條件 |
| idle / think / act / wait | paused | 控制層接受暫停，凍結新派工 |
| paused | idle / think / act / wait | resume 依 paused_from 及保存的 continuation 恢復 |
| 任一非 error | error | 設定／資料損壞、不可判定結果、需人工處置錯誤 |
| error | idle / think / act / wait / paused | 控制層驗證修復或人工決議完成後恢復 |

同 phase 提交只允許有持久進度或更新等待依據；沒有輸入、到期、結果或可推進工作時釋放 claim，不建立自我喚醒的忙迴圈。

下列完成條件中的工作、結果與 unknown 僅指本輪 kind=tool|llm，排除 kind=tick 控制 job／attempt。run 成功必須同一 proposal 提交 final_ref，且無 pending 工作、無未消費結果、無 unknown、無取消要求；僅模型文字說「完成」不足。finish failed 同樣不得遺留未收回的工作，需附 Error；有在途工作先取消／回收，未知則 needs_attention。phase idle 是目前無語意步驟，不能代替 run 成功；wait 不是完成。queued 後續任務尚未被准許時也可 idle。

驗收：Given 模型回覆 final 但仍有一個工具在途；When 提交 finish succeeded；Then 交易拒絕並保留工作，run 不成功；工具完成並消費後才可提交 final。

## A-504 冷本體與可觀測性〔使用者方向 2026-09-28，連 notes〕

來源：[一萬個 agent 與取消 worker 方向](../../notes/2026-09-28-linux-resources-and-task-scheduling.md)。agent 本體持久，tick 按需要啟動；不能每 agent 固定常駐程序或空轉確認 history。喚醒來源交 ready/due、入站及結果事件，tick 不自行維護另一套排程器。

驗收：Given 10,000 個無輸入且無 due 的 agent；When 系統閒置；Then 不因本體數量產生 10,000 個 tick 程序或週期讀取整份 history。

## A-505 錯誤查詢與診斷〔建議預設，未拍板〕

查詢由控制層提供 agent_id、phase、generation、checkpoint revision、當前 run_id 或 null、等待原因、pending jobs、最新 Error 與是否可 resume。事件記錄包括 stale_generation、拒絕的 proposal 與 blob 缺失，但 log 不取代權威帳本。無法取得權威資料時回不可用，不從舊 log 猜測成功。每次轉 needs_attention 必須保存原因與可採取的修復類型；純 resume 不解除尚未解決的 unknown 或資料損壞。

驗收：Given unknown 工具令 run 受阻；When 查詢並只送 resume；Then 查詢顯示原 attempt 與 result_unknown，未滿足恢復前置條件時仍保持受阻，不觸發重試，unknown 及取消要求均不因普通 resume 而清除。
