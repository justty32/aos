# 名詞表：佇列與有限資源
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### Maildir（郵件目錄協定）

**白話**：每封信各自寫在自己的檔案，寫完才搬到收件區，收件者不會讀到半封信。
**嚴格**：Maildir 是以 filesystem directories 與 atomic rename 管理 message delivery/state 的既有郵件儲存協定，其傷痕包括唯一檔名、tmp→new 發布、離線讀取與修復。
**在 aos 裡具體是什麼**：aos 沒有實作 Maildir；`.aos/inst.tempd/<unique>.json.temp`→`.json`、`.bad`、`.runi` 可照這個直覺理解，但差別是 aos 還會把多份投遞彙整成一個 batch。
**為什麼會冒出這個詞**：[隨意發想](../records/free-ideation.md) 四位都獨立用郵局/Maildir 解釋 tempd、instruction、`.bad`、`.runi`；[有限資源場](../records/finite-resource-queue.md) 又用目錄狀態機管 queue。

### queue、spool 與 inbox

**白話**：queue 是一排等著必須被處理的工作；spool 是它們在磁碟上排隊的地方；inbox 則是可以不回的信箱。
**嚴格**：queue 提供 submission/claim/completion 生命週期；spool 是 queue 的耐久 filesystem backing store；inbox/mail 是寬鬆通知 envelope，只有明示 accept 後才可升成必須 claim 的工作。
**在 aos 裡具體是什麼**：`.aos/inst.tempd/`→`inst.json` 是已存在的 instruction queue 交接；`wf/inbox/` 是已存在的 agent 信件；全域 LLM spool 目前只是提案。
**為什麼會冒出這個詞**：[workflows 場](../records/workflows-on-aos.md) 四位特別防止把「可忽略的信」直接變成「必須執行的指令」；[有限資源場](../records/finite-resource-queue.md) 則用 spool 管跨 world 限額。

### GNU make jobserver

**白話**：先放固定數量的通行證在共用地方，子工作要開新工作前先拿一張，做完後歸還，因此同時數不會爆掉。
**嚴格**：GNU make 的 jobserver 用可繼承的共用 pipe/FIFO 中的 tokens 限制遺傳 make 子樹的總併發數；取 token 即佔一 slot，歸還 token 即釋放。
**在 aos 裡具體是什麼**：目前沒有 jobserver；[有限資源場](../records/finite-resource-queue.md) 的 `slots/ready/`→`slots/held/` 候選可照這個直覺理解，但差別是無親緣的 worlds 不共享一條可繼承 pipe，公平與租約因此更難。
**為什麼會冒出這個詞**：[有限資源場](../records/finite-resource-queue.md) 想分開 LLM endpoint 的併發額與每分鐘速率，借 jobserver 解釋「同時只准 N 筆」。

### DMA、staging buffer、doorbell 與 fence

**白話**：先把要給另一個處理者的東西放到共同看得懂的交接區，敲鈴提醒它；之後留一個可查的標記判斷它做完了沒。
**嚴格**：DMA 是裝置在不由 CPU 逐字搬運的情況下存取記憶體；staging buffer 保存傳輸快照；doorbell 是最佳努力通知；fence 是可等待／查詢的完成同步物。
**在 aos 裡具體是什麼**：都還不是 aos 公開原語；候選對應是中央 LLM spool 內的 input snapshot（staging）、inotify/socket（doorbell）、world 中 `.aos/k/llm/<id>.json`（fence）。所以可照 GPU command queue 理解，但差別是 aos 的真源仍是檔案，鈴聲可以丟。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 用 DMA 解釋彙整為何屬取指前端；[有限資源場](../records/finite-resource-queue.md) 用整組硬體直覺處理跨 world 的 LLM 限額。

