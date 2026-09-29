# 輸入、回覆與控制

← [Agent](README.md)｜[共用契約](../contracts.md)

## A-201 收件格式與確認〔建議預設，未拍板〕

輸入入口由控制層驗證及發布。RPC `agent.submit` 的外層 id 為 request_id，params 只有 `agent_id:ID` 與 `input_ref:BlobRef`，依基底通訊契約。input_ref 的內容必填 `version:1`、`text:string`（非空 UTF-8）；可省 `attachments:array<BlobRef>`（預設 `[]`）。認證後的 `sender:string` 由入口存入內部收件紀錄，不接受內容自稱。控制層給每名 agent 的訊息分配嚴格遞增 `input_seq:int>=1`；輸入原文不可變，保存於 home。單則 text 上限預設 1 MiB；超限、附件不存在、無效 UTF-8 或無權投遞在收件前拒絕。

先持久化內容，再原子登記收件與 ready，成功回覆 C-04 的 `result:{accepted:true,request_id,run_id}`，另必回 `input_seq:int>=1` 帶回 seq；`accepted` 不表示已閱讀。以 `(authenticated principal, target agent_id, method, request_id)` 去重；canonical digest 依基底通訊契約計算，agent_id 也納入內容摘要，同鍵同內容回原收據，不同內容回 `conflict`。資料已寫但尚未登記而崩潰只留下孤立 blob，重送可完成登記；禁止把未登記檔案當成新輸入。無法持久化時不回成功，caller 使用相同 request_id 重送。

驗收：Given 發送者在取得收據前斷線；When 重送相同 request_id 及內容；Then 只產生一個 seq，只有一次可消費輸入。

## A-202 普通訊息的輪次邊界〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 A1 輪次部分〕

agent 依控制層交付的 run 與輸入組 context；輪次建立、輸入綁定及先後順序以 [S-101](../scheduling/runs.md) 為唯一規範來源，設定版本與換版時點依 [A-102](configuration.md)。依 [09-29 裁定](../../notes/2026-09-29-verdicts.md) 1，「一輪任務」是軟性設計原則，任務途中新訊息的歸屬暫不定案。

工具結果是原 job 的證據，依 run_id/job_id/attempt_id 路由，不建立新 run；已完成 run 的遲到結果保存供查核，不冒充新的使用者訊息。停止、暫停及恢復使用控制入口，與普通 text 分開。收件進度與語意處理進度分開顯示；input 消費 cursor 只能隨有效 tick proposal 原子提交。

驗收：Given 採用 S-101 的建議輪次預設，R1 正等工具且收到「改算另一檔」；When 收件成功；Then agent 可區分已收件與本輪已消費，R1 的工作與 context 不被暗中改寫。

## A-203 暫停、取消與輸出〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 A1 輪次部分〕

agent 將暫停、恢復及取消交給控制入口 `run.pause`、`run.resume`、`run.cancel`；請求、權限、去重、轉移及重啟屏障以 [S-102](../scheduling/runs.md) 為唯一規範來源。agent 依控制狀態推進語意，不能把控制收據當成工作已停止或任務已完成的證據；needs_attention 的 resume 是 S-102 所列的可選出口。

回覆是包含 `run_id`、遞增 `output_seq:int>=1`、`kind:progress|final`、`text:string` 的不可變輸出；另必填 version:1。final_ref 引用包含這筆 final 輸出的 BlobRef，必須與提交的 outputs 對應。控制層隨 proposal 提交一次，讀端以 `(run_id, output_seq)` 去重；final 是否完成由 [A-503](tick.md) 判定。持久化前的模型串流片段不算 final，也不作唯一恢復證據。

驗收：Given 一個工具執行中；When pause 後工具完成再重啟；Then 結果仍存在，run 保持 paused，直到 resume 才推進。
