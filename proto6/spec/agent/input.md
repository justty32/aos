# 輸入、回覆與控制

← [Agent](README.md)｜[共用契約](../contracts.md)

## A-201 收件格式與確認〔建議預設，未拍板〕

輸入入口由控制層驗證及發布。RPC `agent.submit` 的外層 id 為 request_id，params 只有 `agent_id:ID` 與 `input_ref:BlobRef`，依基底通訊契約。input_ref 的內容必填 `version:1`、`text:string`（非空 UTF-8）；可省 `attachments:array<BlobRef>`（預設 `[]`）。認證後的 `sender:string` 由入口存入內部收件紀錄，不接受內容自稱。控制層給每名 agent 的訊息分配嚴格遞增 `input_seq:int>=1`；輸入原文不可變，保存於 home。單則 text 上限預設 1 MiB；超限、附件不存在、無效 UTF-8 或無權投遞在收件前拒絕。

先持久化內容，再原子登記收件與 ready，成功回覆 C-04 的 `result:{accepted:true,request_id,run_id}`，可省附加欄位 `input_seq:int>=1` 帶回 seq；`accepted` 不表示已閱讀。以 `(authenticated principal, target agent_id, method, request_id)` 去重；canonical digest 依基底通訊契約計算，agent_id 也納入內容摘要，同鍵同內容回原收據，不同內容回 `conflict`。資料已寫但尚未登記而崩潰只留下孤立 blob，重送可完成登記；禁止把未登記檔案當成新輸入。無法持久化時不回成功，caller 使用相同 request_id 重送。

驗收：Given 發送者在取得收據前斷線；When 重送相同 request_id 及內容；Then 只產生一個 seq，只有一次可消費輸入。

## A-202 普通訊息的輪次邊界〔建議預設，未拍板〕

同一 agent 最多一個 active/paused/needs_attention 的當前 run；尚未開始而被暫停的後續 run 不占此位置，queued 的後續 run 也不算當前 run。沒有當前 run 時，每則已接受普通訊息建立一個 queued run，以 seq FIFO。run 必填 `input_seq:int>=1` 且只綁定該訊息，C-02 的 input_ids 僅含這則 request_id；啟動時 queued → active。run 進行中到來的普通訊息同樣排後續 run，不插入本輪 context，不隱含取消。依 [09-29 裁定](../../notes/2026-09-29-verdicts.md) 1，「一輪任務」是軟性設計原則，任務途中新訊息的歸屬暫不定案；本段是可替換的建議預設。每 run 版本依 [A-102](configuration.md)。

工具結果是原 job 的證據，依 run_id/job_id/attempt_id 路由，不建立新 run；已完成 run 的遲到結果保存供查核，不冒充新的使用者訊息。停止、暫停及恢復使用控制入口，與普通 text 分開。收件進度與語意處理進度分開顯示；input 消費 cursor 只能隨有效 tick proposal 原子提交。

驗收：Given R1 正等工具且收到「改算另一檔」；When 收件成功；Then 新內容建立 R2 queued，R1 的工作與 context 不被暗中改寫。

## A-203 暫停、取消與輸出〔建議預設，未拍板〕

控制請求使用 RPC `run.pause`、`run.resume`、`run.cancel`；外層 id 為 request_id，params 必填 `run_id:ID`（run.resume 另可省管理者用的 `budget`，見 [methods](../base/methods.json)），target agent_id 由受權限檢查的 run 解析，不另收 action 或 UID。控制層依 A-201 的同一去重 scope 去重並檢查權限。pause 使 queued/active → paused 並持久保存 `paused_from:queued|active`，停止新派工，不殺已在途工作；結果仍可持久收回。resume 使尚未開始的 paused → queued、已開始的 paused → active；後者依 checkpoint 選 think/act/wait。對非 unknown 原因的 needs_attention，resume 是 [S-102](../scheduling/runs.md) 的可選重新驗證出口，實作可不提供。重複同 action 回目前狀態，終態 run 的 pause/resume 回 `run_terminal`。普通 resume 不解除 unknown 或 cancel_requested。依 [S-401](../scheduling/operations.md)，取消要求尚在而要 retry，必須由 run.resolve 額外明填 clear_cancel_requested:true；控制層在同一 resolve 交易驗證、清除取消要求並授權重試。

cancel 對 queued/paused/active/needs_attention 關閉新派工，向既有工作提出取消；在途停止未確認前不宣告 run canceled。全部工作有確定終局後才轉 canceled；任何副作用未知依 [A-404](tools.md) 進 needs_attention，不自動重試。這些控制狀態持久化，重啟後繼續回收或核對，不能因重啟解除暫停／取消要求。

回覆是包含 `run_id`、遞增 `output_seq:int>=1`、`kind:progress|final`、`text:string` 的不可變輸出；另必填 version:1。final_ref 引用包含這筆 final 輸出的 BlobRef，必須與提交的 outputs 對應。控制層隨 proposal 提交一次，讀端以 `(run_id, output_seq)` 去重；final 是否完成由 [A-503](tick.md) 判定。持久化前的模型串流片段不算 final，也不作唯一恢復證據。

驗收：Given 一個工具執行中；When pause 後工具完成再重啟；Then 結果仍存在，run 保持 paused，直到 resume 才推進。
