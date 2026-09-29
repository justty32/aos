# 觀測、人工處置與資料保留

← [排程](README.md)｜[整體验收](../conformance.md)

以下均為〔建議預設，未拍板〕。責任為控制查詢與管理入口；讀取狀態不需啟動agent，也不能讓查詢者透過ID讀到其他owner內容。

## S-401．人工解決 unknown

本條只處理 unknown；非 unknown 原因的 needs_attention 走 [S-102](runs.md) 的可選 resume 重新驗證出口或 run.cancel。

`run.resolve` 必填run_id、job_id、`decision:retry|fail|cancel_with_unknown`，由已授權操作者發出且先核對job屬該run。retry另必填allow_duplicate_effects=true及new_max_attempts，按S-104核對本機程序清空再放行。fail或cancel_with_unknown先持久記 `pending_resolution:{decision,request_id}`、停止新派工並取消該run其餘未終局工作；全部本機受管程序清空後才分別run→failed或canceled。在途未清空時保持needs_attention，不先回終局。二者均記錄接受未知副作用，不改舊attempt的unknown為已證明失敗；pending_resolution決定終局，優先於一般cancel_requested的canceled結算。

補回原attempt的真實結果走可信result導入，不提供任意寫成功文字的管理捷徑。每次resolve記操作者、request_id、時間及選擇，重送去重。取消要求尚在時retry另須 `clear_cancel_requested:true`；省略或false回conflict。只有這個有風險確認的resolve交易可同時清取消要求、准許重試；普通resume不能解除unknown或暗中重做。

驗收：Given unknown job且本機孫程序仍活，When retry或cancel_with_unknown，Then 拒絕完成處置並顯示未清空；清空後合法處置保留原unknown證據。

## S-402．查詢回應與拒絕理由

run.get回run欄位、`agent_phase`、`pending_jobs:int>=0`、`inflight_jobs:int>=0`、`wait_reason`（null或object）。wait_reason必含 `code`（`not_due|quota_wait|local_limit|tool_result|llm_result|paused|canceling|result_unknown|claim_suspect|deployment_unavailable|budget_exceeded`）、`since_at_ms`；可省scope_id、next_due_at_ms。attempt.get回attempt與取消／cleanup狀態；缺權限回unauthorized，不泄漏其他owner結果。過期結果依C-06回gone。

即時quota數可能在回覆後改變，查詢必帶`snapshot_at_ms`，不能把估算等待時間說成保證。操作者能區分ready未入場和已running，不能只顯示busy。profile不能滿足quota／cgroup／外牆時顯示deployment_unavailable且不派新工作。

驗收：Given 同時有quota不足與被pause的工作，When 查詢，Then 主阻擋原因以pause優先，附帶仍可查quota資訊；無需載入history，也不為查詢觸發tick。

## S-403．最小量測與過載

每個查核窗保存registered、unique_active、ready、tick／tool／HTTP在途、queue_age、scope等待、unknown數、重試、控制CPU／RSS／FD、帳本提交耗時與拒絕數；數據可彙總，不要求保存所有逐事件log。steady-state與啟動reconcile分開報告，不能用熱cache數據代表冷啟動。

pending數達max_pending_jobs或控制metadata空間保護門檻時，拒絕新提交resource_exhausted；已接納工作仍可查結果與取消。事件／錯誤文字必設長度上限與輪替預算，不因記一個超量錯誤再寫無限log。projectquota滿時管理端仍保留最小失敗摘要；大output留在agent計費容量，不轉移至不限額global庫。

驗收：Given 佇列滿且某agent磁碟quota也滿，When 新請求與舊run取消同時到達，Then 新請求明確拒絕，取消仍可持久登記與回收，不靜默吞掉已接件工作。

## S-404．留存

結果、checkpoint與去重依C-06保留至少run終局後30日的可查證據；未完成或unknown資料不得單靠時間刪除。管理者可調整政策但必須顯示其生效時間，不能使已承諾的收據立即失去去重能力。刪大blob需保留result摘要、run終局及ID tombstone；孤立未接納blob可較早回收，但不誤刪已引用blob。

原本的舊 worker 後端遷移段依 [09-29 裁定](../../notes/2026-09-29-verdicts.md) 3（proto6 新寫、不在 proto5 上就地演進）移至[執行後端切換附註](../../notes/plan/backend-switch.md)。

驗收：Given 終局 run 的去重摘要仍在保留期內，When 管理者縮短保留政策後同 request 重送，Then 回原終局摘要並可查新政策生效時間；未終局或unknown資料不因到期被刪。
