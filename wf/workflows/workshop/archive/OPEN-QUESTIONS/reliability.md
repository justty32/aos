# 待答問題：unknown、crash 與斷電耐久
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[白話導讀](../background/questions-reliability.md)

第 12–14 題：遠端 unknown 的預設處置、crash 承諾涵蓋到哪一級、`--durable` 承諾什麼。

## 擋住事情的

### 12. 遠端效果變成 unknown 時預設怎麼辦？

**問題｜**LLM／有副作用工具可能已執行但本機沒記下時，要停住、只在 provider 可對帳時自動恢復，還是直接自動重試？  
**為什麼卡著｜**這決定是否可能重複付費、寄信或部署，也決定近期是否需要 Effect／resolve。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地問了。  
**候選答案｜**

- **unknown 一律停住**——交給人 retry、lost／abandon 或 adopt／import。
- **可對帳才自動恢復**——只有 provider 支援同 key 冪等或 request ID 查詢時才重送／取回。
- **unknown 自動重試**——loop 自動再呼叫，但接受重複付費與副作用的風險。

### 13. crash 要承諾到哪一級？

**問題｜**首版只保優雅 Ctrl-C，還要涵蓋 hard kill，或連斷電都列入恢復契約？  
**為什麼卡著｜**supervisor、`.runi`、temp 清理、fsync 與測試矩陣都取決於故障邊界。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；3 位獨立地分別追問 Ctrl-C、hard kill、斷電。  
**候選答案｜**

- **只承諾 Ctrl-C**——wrapper 有機會主動記狀態；hard kill 與斷電只觀察、不保自動恢復。
- **承諾 Ctrl-C＋hard kill**——逐點 kill，要求本機檔案能辨認未完成，但遠端仍可停在 unknown。
- **連斷電都承諾**——把檔案與目錄 fsync、power-loss durability 一起納入契約與測試。

### 14. `--durable` 與 fsync 承諾什麼？

**問題｜**Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？  
**為什麼卡著｜**這會改變跨平台契約、錯誤種類與每次投遞成本，也決定目錄 fsync 是保證還是盡力。  
**在哪問過｜**〈核心行程與子行程〉、〈agent loop 的實作架構〉、〈aos 與 coding agent、skills、MCP 的協作〉；兩批共 4 位獨立地問了。  
**候選答案｜**

- **只保 rename 可見性**——不宣稱 power-loss durability，第一版不收 `--durable`。
- **可選 `--durable`**——一般模式只 rename；旗標模式另做檔案與目錄 fsync，規格明列平台保證。

