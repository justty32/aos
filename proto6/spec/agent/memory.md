# 記憶與 context

← [Agent](README.md)｜[共用契約](../contracts.md)

## A-301 持久內容與權威引用〔建議預設，未拍板〕

history 是對話與工具證據的追加序列；notes 是 agent 整理的知識；context 是某次模型呼叫所選材料。三者不得互相視為同義。每個 history event 必填 `event_seq:int>=1`、`run_id:ID`、`kind:input|assistant|tool_result|summary|note`、`content_ref:BlobRef`；可省 `source_refs:array<BlobRef>` 預設 `[]`，summary 必須非空。blob 是不可變 UTF-8 或帶 MIME 的二進位內容；hash 校驗失敗不得靜默讀取。

tick 提出新增內容，由保存層先落盤，再由控制層在有效 proposal 提交時登記其可見性。agent 無權覆寫 SQLite checkpoint pointer 或既有 event。notes 更新形成新版本而非改掉被舊 run 引用的內容；工具能寫工作區不等於能提交控制層認可的歷史。

重啟只採用已登記引用；孤立 blob 不算已發出的回覆或已理解的輸入。缺 blob／校驗失敗使相關 run 進 needs_attention、phase error；保留 cursor 與引用供修復，不回退 cursor 以重做副作用。修復後可經 [S-102](../scheduling/runs.md) 的可選 resume 重新驗證出口繼續；實作未提供該出口時只能取消，另建新 run。

驗收：Given tick 寫好回答 blob 後在提交前被殺；When 重啟；Then 使用者看不到正式回答事件，下一 tick 可重算且不產生兩份已提交回答。

## A-302 context 選擇與來源〔建議預設，未拍板〕

context policy 必填 `input_token_limit:int>0`、`output_token_reserve:int>0`（皆由模型設定提供，無通用數字預設）、可省 `summary_mode:off|referenced`（預設 off）。先讀取 run 的剩餘預算快照，以模型上限與該快照為界估組 context；這一步不取得或持有 quota／concurrency 票。完成 messages、工具描述與 max_output_tokens 的完整 payload 估算後才提交 job，由 [S-302](../scheduling/llm.md) 做實際 reservation；排程重新檢查全部 scope 與預算；scope 暫時不足則等待且零占票，run 硬預算耗盡則依 S-306 停新 job、run → needs_attention 並記 budget_exceeded，禁止先 hold 票等 tick 組材料。system、該 run 原始輸入、當前 tool call 及其配對的模型可見結果封套是必帶材料；結果封套可用 A-303 的有標記預覽及原始引用，不要求把整份原始 stdout 放進 context。餘額才放近期歷史及有來源的摘要。run 預算快照沿 [S-306](../scheduling/llm.md) 的 max_jobs／max_llm_attempts／max_tokens_estimate／max_elapsed_ms 與計數，不由 context policy 另造或增加額度。

每次請求保存實際 context 的不可變 blob、採用版本、source refs、估算方法及估算 token 數。排序預設 system → 本輪以前選中的歷史 → 本輪訊息／呼叫／結果，保持模型要求的 tool call 配對順序。摘要不得捏造原始來源；被省略的材料須留下可追查引用。摘要產生若使用模型，仍是普通受預算管理的 job，不得藏在本地 tick 裡繞過准入。

必要材料已超預算時，不截斷 JSON 結構、原始要求或配對結果封套，回 `context_over_budget`，run → needs_attention、phase error；處置走 [S-102](../scheduling/runs.md) 的可選 resume 重新驗證出口：實作若允許同 run 調高預算（S-306）或依 A-102 可選換版換上較大的 context policy，調整後 resume 並重新驗證必要材料已可容納才回 active；否則只能取消，另以較小輸入建新 run。禁止無界自動壓縮重試。缺乏 provider tokenizer 時必須註記估算；provider 拒絕過長請求同樣回顯錯誤及材料清單。

驗收：Given 必要材料已超限；When 準備 LLM job；Then 沒有 API 請求，查詢可見超限值與被保留的來源引用。

## A-303 容量不足與保存期限〔建議預設，未拍板〕

history quota 由基底容量管理提供，agent 不另宣告無限容量。預設不自動刪除 history／notes／引用中的 blob；非終態 run 的證據必須保留。模型每份工具結果的 stdout／stderr 文字預覽合計預設最多 64 KiB UTF-8，超出只取不切斷 UTF-8 字元的前段，保留 Outcome、call_id、完整結果 BlobRef 與明示的 preview_truncated=true。該預覽屬結果封套的字串，不能把半份 JSON 偽裝為合法工具 JSON：json 模式先驗證底座保存的完整 stdout，模型內容不足時再把預覽當字串編碼。此預覽上限不等於 context 額度，封套連同必要材料仍超 token 預算就走 A-302；也不代表底座可無限收集輸出，底座輸出上限仍生效。

入站容量不足時拒絕收件且不發 accepted。工作已完成但 home 無法存結果時，只對已成功持久化的 blob 承諾可恢復；不將寫不下的完整輸出轉存到無限額空間。底座可丟棄無法保存的輸出 bytes，保留有界截斷摘要、錯誤與已知執行證據，明示資料不完整；控制層標記 `storage_blocked`，run → needs_attention，停止新派工。ack 必須在這份明示不完整的交接證據持久登記後才發出，不能假稱完整結果已保存。控制庫本身無法持久化則關閉寫入及派工，回暫時不可用，不能假裝已記錄錯誤。容量恢復後核對已保存證據及原 cursor；完整結果曾持久化才可恢復其消費，只有截斷摘要時仍需人工處置，不能以 resume 憑空找回內容。不得自動重新執行原工具以找回丟失結果，已發生的副作用不會因資料丟失而撤回。

驗收：Given home quota 在工具完成時耗盡；When 保存結果失敗並重啟；Then 工具不重跑，可查有界摘要與 storage_blocked／截斷標記；釋放容量不會讓未保存的 bytes 再出現，已持久結果亦不重複消費。
