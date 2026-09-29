# Tick、狀態與恢復

← [Agent](README.md)｜[共用契約](../contracts.md)

## A-501 每次推進的責任〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 A1 proposal 部分、B1〕

tick 是一次短暫語意推進，輸入為可信 claim、固定版本、目前語意 checkpoint、[B-401](../base/storage.md) 的帳本唯讀視圖與已登記的新證據；輸出為 [C-05](../contracts.md) Proposal。它可以整理本輪輸入、選 context、解讀已完成工作、提出下一批 job 或回答。它不能自行執行 cloud LLM、繞過底座啟動工具、直接改寫權威 checkpoint pointer 或派工表。

claim 的單寫者與生命週期沿 [B-602](../base/lifecycle.md)；Proposal 的欄位、提交屏障、世代與版本驗證、重送及 maintenance 限制只依 C-05。tick 遇 conflict 或 stale_generation 不把本地候選當已提交進度；後續由控制層按有效 claim 重新提供輸入。只有有效當前 run 的普通推進才可提出工具與 LLM 工作。

驗收：Given 尚未提交提案的舊 tick T1 遲到且新 tick T2 已取得較高 generation；When T1 提交；Then 被拒絕，T2 的 checkpoint 與派工資料不變。

## A-502 Checkpoint 與提交次序〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 B1、A1 proposal 部分〕

checkpoint blob 只保存帳本無法重建的 agent 語意狀態：必填 `version:1`、`invalid_response_count:int>=0`；可省 `continuation_ref:BlobRef|null`，預設 null，保存尚未提交成 job 的決策、選定 context 或其他續接思路。新本體計數為 0、continuation_ref=null。invalid_response_count 是 [A-401](tools.md) 的連續無效回覆語意計數，帳本的 job 成敗不足以推回，故保留；重設與人工恢復仍沿原條款。

`pending_job_ids`、`phase`、`wait_reason`、`due_at_ms` 與控制 cursor 不屬 checkpoint；由 B-401 帳本唯讀視圖提供，不能由 agent 覆寫。等待須有帳本可驗證的結果、額度、到期或人工處置依據；due 等待須有已登記到期時間，不得憑空設輪詢間隔。`input_seq` 原表示已消費輸入進度，`history_tail` 原表示已登記歷史尾端，兩者均為帳本副本，本版刪除，不另解讀成語意位置。收件 input_seq、語意消費 cursor 與排程通知水位仍各自存在；若 agent 選定某段歷史作為 context 或摘要來源，該不可推回的選擇以明確來源引用保存在 continuation，不用 history_tail 冒充。

`history_append`／`outputs` 是本次 Proposal 的控制增量（可經 C-05 append_ref 引用），型別及驗證由 C-05 定義，不放進 checkpoint。tick 先產生語意候選及所需內容，交 [B-403](../base/storage.md) 導入，取得 BlobRef 後按 C-05 提交。恢復時讀已提交 checkpoint 與帳本視圖接續思路；提交失敗沿 A-501 處理，不能從本地候選認定已消費或已派工。

驗收：Given checkpoint 只有計數與 continuation，而帳本含未消費結果及 unknown 工作；When tick 恢復並產生提案；Then 從唯讀視圖看見完整 pending／等待依據，不能藉省略控制副本宣告成功；history_append／outputs 依 C-05 與消費、新 job 共同提交，checkpoint 不重存它們。

## A-503 Phase 與完成契約〔建議預設，未拍板；09-29 精簡，依冗餘審查 B4〕

phase 六個值保留供觀測，但由 run／job／attempt 的控制事實與已保存的語意 continuation 推導，控制層不保存或檢查完整 phase 轉移表。run 的暫停、取消與錯誤屏障是權威：paused 顯示 `paused`，資料損壞、仍阻擋目前 run 的未解決 unknown 或其他 needs_attention 屏障顯示 `error`，且兩者都不能因 phase 或 continuation 改變而放行派工。已依 [S-401](../scheduling/operations.md) 處置的舊 unknown 仍保留證據，但不再單獨構成目前屏障。其餘情況可依目前語意位置顯示 `idle|think|act|wait`；等待理由只依 [S-402](../scheduling/operations.md) 從控制事實查詢，不另存一份 phase 狀態。

think／act 的語意步驟仍須可由事件或查詢觀察；若沒有需要在重啟後單獨恢復的中間決策，不為一次 think／act 顯示新增持久轉移。有待執行決策、context 選擇或其他不能重算的中間位置時，保存 continuation，再由它恢復語意位置。沒有輸入、到期、結果或可推進工作時釋放 claim，不建立自我喚醒的忙迴圈。

下列完成條件中的工作、結果與 unknown 僅指本輪 kind=tool|llm，排除 kind=tick 控制 job／attempt。run 成功必須同一 proposal 提交 final_ref，且無 pending 工作、無未消費結果、無 unknown、無取消要求；僅模型文字說「完成」不足。finish failed 同樣不得遺留未收回的工作，需附 Error；有在途工作先取消／回收，未知則 needs_attention。phase idle 是目前無語意步驟，不能代替 run 成功；wait 不是完成。queued 後續任務尚未被准許時也可 idle。

驗收：Given 模型回覆 final 但仍有一個工具在途；When 提交 finish succeeded；Then 交易拒絕並保留工作，run 不成功；工具完成並消費後才可提交 final。Given run 已 paused 且保存 act continuation；When 查詢或 tick 嘗試派工；Then phase 顯示 paused、continuation 保留且新工作不被接受。Given 未解決 unknown attempt 仍阻擋目前 run；When 查詢 phase 與 wait_reason；Then 顯示 error 與 result_unknown，不以 idle／wait 掩蓋未知結果。

## A-504 冷本體與可觀測性〔使用者方向 2026-09-28，連 notes〕

來源：[一萬個 agent 與取消 worker 方向](../../notes/2026-09-28-linux-resources-and-task-scheduling.md)。agent 本體持久，tick 按需要啟動；不能每 agent 固定常駐程序或空轉確認 history。喚醒來源交 ready/due、入站及結果事件，tick 不自行維護另一套排程器。

驗收：Given 10,000 個無輸入且無 due 的 agent；When 系統閒置；Then 不因本體數量產生 10,000 個 tick 程序或週期讀取整份 history。

## A-505 錯誤查詢與診斷〔建議預設，未拍板〕

查詢由控制層提供 agent_id、phase、generation、checkpoint revision、當前 run_id 或 null、等待原因、pending jobs、最新 Error 與是否可 resume。事件記錄包括 stale_generation、拒絕的 proposal 與 blob 缺失，但 log 不取代權威帳本。無法取得權威資料時回不可用，不從舊 log 猜測成功。每次轉 needs_attention 必須保存原因與可採取的修復類型；純 resume 不解除尚未解決的 unknown 或資料損壞。

驗收：Given unknown 工具令 run 受阻；When 查詢並只送 resume；Then 查詢顯示原 attempt 與 result_unknown，未滿足恢復前置條件時仍保持受阻，不觸發重試，unknown 及取消要求均不因普通 resume 而清除。

## A-506 tick 前後掛勾〔使用者方向 2026-09-29；細節為建議預設，未拍板〕

可以往 tick 註冊一些程式，讓它們在每次 tick **啟動前（pre）或結束後（post）**執行。清理（[B-404](../base/storage.md) 的 `aos-clean`）是第一個用這個機制的程式；同一支程式也能由人直接呼叫，不一定要經過 tick。

掛勾分兩種，差別在用誰的身分跑：

- **系統掛勾**：管理者在控制端設定裡登記，對所有 agent（或指定的一批）生效，以控制側的專用服務身分執行（不是 root、不是 agent 的 UID），可以做 agent 自己不該做的事，例如清理控制帳本裡的過期紀錄。
- **agent 掛勾**：寫在該 agent 的設定 bundle 裡（隨 [A-102](configuration.md) 在下一次 tick 生效），以該 agent 的 UID、在該 agent 的 cgroup 與 quota 內執行，權限與工具相同，不能寫權威 checkpoint 或提交提案。

每個掛勾登記必填 `name`（登記內唯一）、`when:pre|post`、`argv`（非空字串陣列，形狀同 [A-401](tools.md) ExecTemplate）；可省 `timeout_ms`（預設 30000）、`on_failure:continue|skip_tick`（預設 continue；只對 pre 有意義）、`order:int`（預設 0，小的先跑，同值依 name）。執行時由控制層在 stdin 給一份 JSON：`{version:1,agent_id,run_id|null,when,attempt_id|null,tick_outcome|null}`，其中 `tick_outcome` 只在 post 時有值（`committed|rejected|no_proposal|timeout|killed`）。格式正本在協議篇。

規則：

- pre 掛勾在取得 claim 之後、tick 程序啟動之前依序跑；post 掛勾在提案交易結束（或 tick 程序被收尾）之後、釋放 claim 之前依序跑。agent 掛勾的時間算進該次 tick 的 deadline；系統掛勾另計，不佔 agent 的 tick 時間。
- pre 掛勾失敗且 `on_failure=skip_tick` 時，本次不啟動 tick、釋放 claim、在 run 紀錄留下原因，工作留待下次；不能因此把 run 判失敗。其他失敗只記錄，不影響 tick 結果。
- 掛勾的輸出不是 tick 結果，不進 history，也不能被當成工具結果或 LLM 結果；需要讓 agent 知道的事，要走正常輸入。
- 掛勾不得延長 claim 或讓 agent 在沒有工作時被喚醒；沒有 tick 就沒有掛勾執行。控制端重啟時，執行到一半的掛勾依 [B-603](../base/lifecycle.md) 一起被殺，不補跑也不當成功。
- 系統掛勾是控制側程式，出錯可能影響所有 agent；登記與修改只限管理者。

驗收：Given 系統 post 掛勾 aos-clean 與一個 agent pre 掛勾；When 該 agent 的一次 tick 正常提交；Then 依序看到 pre→tick→post 的執行紀錄，post 收到 `tick_outcome=committed`；agent pre 掛勾設 skip_tick 且失敗時，本次沒有 tick 程序、run 不變、原因可查；控制端在 post 掛勾執行中重啟，掛勾被殺且不被記成成功。

