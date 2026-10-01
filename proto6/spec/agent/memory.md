# 記憶與 context

← [Agent](README.md)｜[儲存](../base/storage.md)

## A-301 持久內容與來源

〔建議預設，未拍板〕history 保存對話與工具結果；notes 保存整理過的知識；context 是某次模型請求實際選用的材料。三者用途不同，直接放在 node 檔案中，用來源 ID 或檔案引用保留關聯。摘要要能追到原始材料；後來修改 notes，不應讓舊請求看起來像用了新內容。

〔使用者方向 2026-09-29〕提交、還原及正式可見性依[通用 tick](../settled/tick.md) 與[儲存](../base/storage.md)。人、agent、工具依相同權限讀寫；需要 group 保證的寫入也要遵守相同協調規則。

〔建議預設，未拍板〕必要來源缺失或損壞時，保留現有證據並寫[待處理事項](../scheduling/operations.md)，不捏造內容或把缺資料當成功。已送出的工作不因本地來源損壞而重新執行。

驗收：摘要所指的原始材料缺失時，可查到缺哪份資料，且不以摘要冒充原始工具結果。

## A-302 context 選擇與來源

〔建議預設，未拍板〕依模型輸入上限與預留輸出空間組 context。必要材料包括 system 指示、正在處理的原始輸入、當前 tool call 及其配對結果；工具結果可採 A-303 的有標記預覽。剩餘空間才放近期歷史及有來源的摘要，保留模型要求的 tool call／結果順序。

每次請求保存實際送出的 context、所需設定材料、來源引用及 token 估算；沒有對應 tokenizer 時標明是估算。必要材料已超限，就回報 `context_over_budget` 與超限原因，不截成壞 JSON、不無限壓縮重試，也不發出明知放不下的請求；處置走[共通操作](../scheduling/operations.md)。

〔第十八批，P-706 從協議篇搬上〕**發一次 LLM 請求的行為**：

- 每次選一筆可推進的 input，略過等待或被擋的；每筆最多一個進行中的模型請求，同一批工具全回來才問下一次。context 依序是 system_prompt、原 user（含附件路徑）、本 input 的 assistant／tool／修補說明；依 seq 排、tool call 成對，不自動摘要、不混進別的 input。
- 工具預覽合計最多 64 KiB（A-303）。token 估算是「messages／tools 的 JSON UTF-8 bytes 加每則訊息 32」，只是估算、不保證是 tokenizer 的上界；加上輸出預留超過 `context_tokens`，或整份 RPC 超過 256 KiB，就報 `context_over_budget`、不送。
- 請求 ID、context、meta、usage 先固定；`llm.chat` 的 params 是 argv 以 `aos llm chat` 開頭的 inst，stdin 指業務 JSON，送設定的 `llm.target_node`；提交後由標準配備投出，後格收結果。要串流就在業務 JSON 帶 `stream_path`（[LLM 協議](../protocol/llm-work.md)）：檔案放哪、權限怎麼開、要不要盯著它，由 agent 決定，aos 不叫醒。目標不是 node 時，投件那一步報錯、不重試（[B-624](../settled/deferred/mq.md)）。
- 〔第十八批〕範本對每個送出的請求預設在封套設鬧鐘（[預設任務](README.md)）；預設值延後（Q26）。

〔使用者方向 2026-09-29〕模型請求交 `llm.target_node` 指定的 [node 與 endpoint 池](../scheduling/llm.md) 處理，資源額度依已裝的 module；context 不另建一套資源管理。摘要若要用模型，也照[通用 tick](../settled/tick.md)派出及收結果。

驗收：必要材料超過模型上限時，不呼叫 API，可查到超限原因與材料來源；需要模型產生的摘要不在本地 tick 裡同步等待。

## A-303 工具結果預覽

〔建議預設，未拍板〕context 可使用工具 stdout／stderr 的有界預覽，合計預設最多 64 KiB UTF-8，不切斷字元。預覽保留原始結果引用、呼叫識別與執行結果；另分清「展示被裁短」及「原始輸出未完整保存」，不能把其中一種說成另一種。

JSON 工具先用完整輸出驗證；裁短的預覽只當字串呈現，不能冒充完整 JSON。這個 bytes 上限不取代 A-302 的模型 token 上限。容量不足、結果保存失敗、保留與清理均依[儲存規則](../base/storage.md)。

驗收：完整 JSON 太長而展示被裁短時，模型可見截斷標記與原始引用；若原始輸出本身已缺失，不宣稱它通過完整 JSON 驗證。

## A-304 清理遍歷〔第十八批，P-716 從協議篇搬上〕

什麼可以清、保留期多久以 [B-404](../base/storage.md) 為準，`aos-clean`（標準配備）的格式見 [P-605～606](../protocol/ops.md)。agent 側的遍歷：

- 以 input_id 追原 `agent.say`、history、context、work、本地 reply、送回的 `agent.say` 與 usage。一般 input 要 done、超過保留期、結果全消費、回話全確認、收件已清且沒有組外引用，才整組封存。
- **只記錄的訊息**（帶 `in_reply_to` 的回話，[A-201](input.md)）沒有 input 可以變 done：以它的接件確認提交的時間為保留期起點，套一般保留期；還有別處引用就保留。不為了清理另建 input。
- 本地動作的 stdout 檔 `state/messages/requests/<id>.stdout` 跟同 ID 的請求副本一起清。過了保留期的壞收件原件（有 `bad_request` 事項，從事項的 `reported_at_ms` 起算）也列入候選；錯誤只報一次、原件留到那時（B-623）。
- unknown 到期連同卡住的 input、pending 與內部引用整組清，不等 input 變 done（[S-401](../scheduling/operations.md)）；卡在 unknown 的輸入要不要另外收尾，延後。序號及在用設定保留；不認得的資料不碰、不回報。

驗收：過保留期且整組結案的 input 被封存，序號不倒退；只記錄的回話依接件確認時間過期後才被清。
