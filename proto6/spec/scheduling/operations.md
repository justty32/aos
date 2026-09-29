# 觀測、人工處置與資料保留

← [排程](README.md)｜[整體验收](../conformance.md)

以下均為〔建議預設，未拍板〕。責任為控制查詢與管理入口；讀取狀態不需啟動agent，也不能讓查詢者透過ID讀到其他owner內容。

## S-401．人工解決 unknown

本條只處理 unknown；非 unknown 原因的 needs_attention 走 [S-102](runs.md) 的可選 resume 重新驗證出口或 run.cancel。

`run.resolve` 必填run_id、job_id、`decision:retry|fail|cancel_with_unknown`，由已授權操作者發出且先核對job屬該run。retry另必填allow_duplicate_effects=true及new_max_attempts，按S-104核對本機程序清空再放行。fail或cancel_with_unknown先持久記 `pending_resolution:{decision,request_id}`、停止新派工並取消該run其餘未終局工作；全部本機受管程序清空後才分別run→failed或canceled。在途未清空時保持needs_attention，不先回終局。二者均記錄接受未知副作用，不改舊attempt的unknown為已證明失敗；pending_resolution決定終局，優先於一般cancel_requested的canceled結算。

補回原attempt的真實結果走可信result導入，不提供任意寫成功文字的管理捷徑。每次resolve記操作者、request_id、時間及選擇，重送去重。取消要求尚在時retry另須 `clear_cancel_requested:true`；省略或false回conflict。只有這個有風險確認的resolve交易可同時清取消要求、准許重試；普通resume不能解除unknown或暗中重做。

驗收：Given unknown job且本機孫程序仍活，When retry或cancel_with_unknown，Then 拒絕完成處置並顯示未清空；清空後合法處置保留原unknown證據。

## S-402．查詢回應與拒絕理由〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 B2、B4〕

run.get回run欄位、`agent_phase`、`pending_jobs:int>=0`、`inflight_jobs:int>=0`、`wait_reason`（null或object）。`agent_phase` 與 `wait_reason` 都由查詢當下的 run／job／attempt 控制事實及已保存的語意 continuation 推導，不是另一份可寫狀態；本條是 wait_reason 的唯一契約。wait_reason必含 `code`（`not_due|quota_wait|local_limit|tool_result|llm_result|paused|canceling|result_unknown|deployment_unavailable|budget_exceeded|needs_attention`）、`since_at_ms`；可省scope_id、next_due_at_ms。`needs_attention` 只涵蓋資料／設定損壞等沒有專屬 code 的非 unknown 人工處置屏障，具體原因仍由 run 的 Error 提供；`result_unknown`、`budget_exceeded` 等專屬理由不得折疊成這個一般理由。wait_reason 只選一個主阻擋原因，不得刪去 run 欄位或各 job／attempt 可查的其他屏障與 unknown 證據。attempt.get回attempt與取消／cleanup狀態；缺權限回unauthorized，不泄漏其他owner結果。過期結果依C-06回gone。

即時quota數可能在回覆後改變，查詢必帶`snapshot_at_ms`，不能把估算等待時間說成保證。操作者能區分ready未入場和已running，不能只顯示busy。profile 不能滿足 cgroup／外牆要求，或已啟用的 quota backend 未通過 probe 時，顯示 deployment_unavailable 且不派新工作；依 [B-304](../base/identity-resources.md) 選用 quota_backend=none 本身不構成部署錯誤。

驗收：Given 同時有quota不足與被pause的工作，When 查詢，Then 主阻擋原因以pause優先，phase 顯示 paused，附帶仍可查quota資訊；無需載入history，也不為查詢觸發tick。Given run 因資料損壞進 needs_attention，When 查詢，Then phase 顯示 error、wait_reason 為 needs_attention 並保留具體 Error。

## S-403．最小量測與過載

每個查核窗保存registered、unique_active、ready、tick／tool／HTTP在途、queue_age、scope等待、unknown數、重試、控制CPU／RSS／FD、帳本提交耗時與拒絕數；數據可彙總，不要求保存所有逐事件log。steady-state與啟動reconcile分開報告，不能用熱cache數據代表冷啟動。

pending數達max_pending_jobs或控制metadata空間保護門檻時，拒絕新提交resource_exhausted；已接納工作仍可查結果與取消。事件／錯誤文字必設長度上限與輪替預算，不因記一個超量錯誤再寫無限log。projectquota滿時管理端仍保留最小失敗摘要；大output留在agent計費容量，不轉移至不限額global庫。

驗收：Given 佇列滿且某agent磁碟quota也滿，When 新請求與舊run取消同時到達，Then 新請求明確拒絕，取消仍可持久登記與回收，不靜默吞掉已接件工作。

## S-404．留存

結果、checkpoint與去重依C-06保留至少run終局後30日的可查證據；未完成或unknown資料不得單靠時間刪除。到期後的刪除或封存由 `aos-clean` 做（掛在 tick 後或手動），規則依 [B-404](../base/storage.md)。管理者可調整政策但必須顯示其生效時間，不能使已承諾的收據立即失去去重能力。刪大blob需保留result摘要、run終局及ID tombstone；孤立未接納blob可較早回收，但不誤刪已引用blob。

原本的舊 worker 後端遷移段依 [09-29 裁定](../../notes/2026-09-29-verdicts.md) 3（proto6 新寫、不在 proto5 上就地演進）移至[執行後端切換附註](../../notes/plan/backend-switch.md)。

驗收：Given 終局 run 的去重摘要仍在保留期內，When 管理者縮短保留政策後同 request 重送，Then 回原終局摘要並可查新政策生效時間；未終局或unknown資料不因到期被刪。

## S-405．待處理資料夾〔使用者方向 2026-09-29〕

所有需要使用者處理的事項，控制層都寫成檔案放進管理者指定的資料夾 `attention_dir`，人打開資料夾就能看到全部待辦，不必逐個查詢。包括：run 轉 needs_attention（任何原因，含 unknown、budget_exceeded、context_over_budget、config_unavailable、storage_blocked、blob 缺失、連兩次無效回覆），以及控制端自身的 deployment_unavailable、控制區滿碟等停止新准入的狀況。

每件事一個 JSON 檔，路徑 `<attention_dir>/open/<agent_id>/<item_id>.json`；控制端自身的事項放 `<attention_dir>/open/_control/`。必填 `version:1`、`item_id`、`agent_id`（控制端事項為 null）、`run_id`（可 null）、`code`（沿 [S-402](#s-402查詢回應與拒絕理由建議預設未拍板09-29-精簡依冗餘審查-b2b4) wait_reason code 與 run 的 Error code）、`message`（給人看的一句話）、`since_at_ms`（牆鐘，只供顯示）、`actions`（目前可用的處置，例如 `run.resume`、`run.cancel`、`run.resolve`，實作不支援 resume 時不列）。可省 `job_id`、`attempt_id`、`evidence`（相關 BlobRef 或查詢指令提示）。

檔案用暫存檔寫完再改名，讀者不會看到寫一半的內容；資料夾與檔案只有管理者與控制端可讀寫，agent 與工具 UID 不可讀寫。這些檔案是帳本的**通知副本**，不是權威：處置一律走 run.resume／run.cancel／run.resolve 等 RPC，刪改檔案不會解除屏障。事項解除後，控制層把檔案搬到 `<attention_dir>/done/`（附解除時間與處置方式），之後依 [S-404](#s-404留存) 的保留期清理。控制端重啟時依帳本重建 open 內容：帳本仍有屏障卻缺檔就補寫，屏障已解除卻還在 open 就搬走。

**處理小工具 `aos-attend`**〔使用者方向 2026-09-29；細節為建議預設，未拍板〕：讀 `open/` 裡的事項，一件一件替人把「該做的事」做掉。它只是人的代理：用執行它的人的身分呼叫同一組 RPC（run.resume／run.cancel／run.resolve 等）和其他小程式（例如 `aos-clean`），不直接改帳本或檔案，權限不比人多。

每種 code 對應一個處理方式與風險等級，寫在一份可編輯的處理表裡：

- **安全**：只重新檢查、不會重複做事也不會丟東西，例如修好設定後 resume 重新驗證、磁碟滿時先跑 `aos-clean` 再重新驗證。可自動執行。
- **危險**：可能重複外部副作用、丟掉工作或多花錢，例如 unknown 的 retry（allow_duplicate_effects）、fail、cancel_with_unknown、run.cancel、調高預算。執行前一定先顯示要做什麼、影響哪個 agent／run，**問 y/n**，答 y 才做。
- **只能人看**：沒有可自動做的事（例如需要人補回原始結果），只列出來。

沒有終端可問時（例如排程自動跑），危險動作一律跳過並留在 `open/`，不得用任何「全部答 yes」的參數跳過 retry 這種會重複外部副作用的確認。每次動作都記下誰、何時、對哪件事、做了什麼、結果；做完由控制層照常把事項移到 `done/`，`aos-attend` 自己不搬檔。

驗收：Given run 因 context_over_budget 轉 needs_attention；When 查看 attention_dir；Then open 下有一個對應檔，code 與 run.get 一致；人刪掉該檔後重啟控制端，檔案被補回且 run 仍被擋；經 run.cancel 處置後檔案移到 done。Given 一件 config_unavailable 與一件 unknown；When 在無終端模式跑 aos-attend；Then 前者自動 resume 重新驗證，後者不做任何處置、仍在 open，且紀錄可查。
