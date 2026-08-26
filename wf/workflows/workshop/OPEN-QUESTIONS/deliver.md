# 待答問題：Deliver 公開契約
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[白話導讀](../background/questions-deliver.md)

第 7–9 題：`aos deliver` 的命令形狀、key 的保證範圍、成功／錯誤／退出碼那一套。

## 擋住事情的

### 7. `aos deliver` 第一版命令長什麼樣？

**問題｜**`aos deliver` 第一版要採哪一組 WORLD、輸入檔／stdin、單筆／批次與旗標介面？  
**為什麼卡著｜**Deliver 是回頭審視後唯一仍保留的近期 core 缺口；參數不定就無法寫 CLI、skill 或 MCP schema。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地問了。  
**候選答案｜**

- **檔案為主**——`aos deliver [--key K] [--durable] <inst-file>`，只明收 instruction array。
- **資料夾＋可選檔案**——`aos deliver [--file FILE] [FOLDER]`，收單筆 object 或 array，FOLDER 預設 `.`。
- **world＋廣義 target**——`aos deliver [W] [--to X.json]`，由 `X.json` 推出 `X.tempd/`。
- **world＋stdin／檔案**——`aos deliver [WORLD] [-f FILE|-] [--key K]`，收單筆或 array。

### 8. Deliver 的 key 到底保證什麼？

**問題｜**沒有耐久 ledger 時，第一版 key 要拿掉、只作 correlation、只在 queue 內去重，還是連 ledger 一起做？  
**為什麼卡著｜**aggregate 會刪投遞檔；若仍宣稱跨回合 Already／Conflict，現有磁碟上沒有可查的舊事實。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地問了。  
**候選答案｜**

- **第一版沒有 key**——只承諾驗證與原子發布，caller 自己避免重送。
- **key 只作 correlation**——寫進檔名／receipt 方便串接，但不回 Already／Conflict。
- **只在 queue 存活期去重**——舊投遞檔還在時判 Already／Conflict，彙整刪除後不再承諾。
- **增加耐久 ledger**——跨回合保存 key、內容 hash 與結果，才承諾 Already／Conflict。

### 9. Deliver 的成功、錯誤與退出碼採哪套？

**問題｜**Deliver 要採哪一組成功 JSON、錯誤 JSON、receipt 欄位與退出碼編號？  
**為什麼卡著｜**skill、MCP、腳本必須讀同一份機器契約；目前只有 `0＝成功` 與錯誤要可定位形成共同形狀。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地各給一套。  
**候選答案｜**

- **receipt＋hash 版**——成功含 `receipt/state/hash`；2 用法、3 格式／大小、4 key 衝突、5 I/O。
- **delivery＋count 版**——成功含 `delivery/count`；2 payload、3 world／版本、4 I/O。
- **最小 JSON＋廣義 target 版**——成功欄位先從簡；2 用法、4 驗證、5 I/O。
- **published＋receipt＋count 版**——2 用法、3 JSON、4 schema、5 key 衝突、6 I/O。

