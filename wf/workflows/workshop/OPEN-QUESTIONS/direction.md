# 待答問題：痛點、scope 與產品體驗
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[白話導讀](../background/questions-direction.md)

第 1–3 題：aos 到底要先消掉哪個摩擦、近期 core 收到多小、第一個產品體驗做哪一邊。

## 擋住事情的

### 1. workflows 到底是哪一種不好用？

**問題｜**最近一次覺得 workflows 不好用時，主要卡在安裝升級、路由／遵守流程、活狀態維護，還是定時喚醒？  
**為什麼卡著｜**第一個 workflows 功能、磁碟真源與是否需要 runtime 都取決於真正痛點；紀錄中的痛點目前全是推論。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地問了。  
**候選答案｜**

- **安裝／升級**——先做來源版本、base hash、三方 diff 或 doctor，不先做 task runtime。
- **路由／遵守流程**——先改善 workflow 的找到、派發與 agent 遵守方式，不先建活狀態資料庫。
- **活狀態維護**——先做 `start／wait／resume／done／status`，取代手動搬 SESSION-LOG 與 WAIT_USER。
- **tick／schedule**——先把到期判斷、Deliver 與 cursor 更新機械化。

### 2. 近期 core 要回撤到哪裡？

**問題｜**近期 scope 要只留最小 Deliver，保留 Publish→Deliver→Effect 三項，還是繼續連行程控制平面一起設計？  
**為什麼卡著｜**三場早期紀錄與回頭審視給了互斥的近期 roadmap；不先拍板，後面的公開 API、Effect、join、lane 等題目都無法排程。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；4 位獨立地問了。  
**候選答案｜**

- **只做最小 Deliver**——Publish 留內部、Effect 留 adapter／人工，其餘等實測觸發再重開。
- **先做三項 core 原語**——依序公開 Publish、Deliver、Effect＋resolve，再跑 agent loop。
- **保留完整控制平面**——連 lane／proc-table／capability／promotion／join 一起形成耐久行程機制。

### 3. 第一個產品體驗是哪一邊？

**問題｜**第一個做好的體驗，是人在 coding agent 裡呼叫 aos，還是 aos 無人值守地批次召喚 coding agent？  
**為什麼卡著｜**兩者雖共用 CLI，卻需要不同的 session、批准、結果捕捉與 unknown 責任。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；2 位獨立地問了。  
**候選答案｜**

- **coding agent 互動入口**——先讓人透過 skill／MCP 呼叫 Status、Deliver，視權限再 Exec。
- **aos 批次召喚 agent**——先做 request、啟動 CLI、原子捕捉結果、exit／unknown 與完成 commit。

