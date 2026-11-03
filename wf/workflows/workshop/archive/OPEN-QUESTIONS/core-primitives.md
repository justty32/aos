# 待答問題：Publish、Effect 與 join 要不要進 core
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)

第 25–27 題：三個「近期不擋、一旦要自動 agent loop 就得先定」的 core 原語邊界。

## 可以慢慢想的

### 25. Publish 要不要成為公開 API？

**問題｜**Publish 只當 Deliver／Effect 的私有 helper，還是公開給檔案、目錄、cursor 與 event 共用？  
**為什麼卡著｜**只有在近期 scope 不回撤時才會擋 API；公開後要背 temp/source 或 payload、目錄交易與 durability 的相容承諾。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；4 位獨立地先提出、後又收回近期公開。  
**候選答案｜**

- **只作私有 helper**——Deliver 內部共用 temp＋rename，不形成公開 ABI。
- **公開 source/temp 版**——`publish TARGET TEMP`／`publish_at(..., source)` 發布已寫好的檔或目錄。
- **公開 payload 版**——API 直接收內容，由 Publish 自己建立 temp、write-all 與 rename。

### 26. Effect 放 core 還是 adapter？

**問題｜**外呼日誌與 unknown／resolve 要留在 provider adapter，還是成為通用 core Effect？  
**為什麼卡著｜**若近期只做 Deliver 可延後；若要自動 agent loop，就要先定通用狀態與 provider-specific 對帳的切線。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；4 位獨立地先提出通用 Effect，後又撤回近期前置。  
**候選答案｜**

- **全留 adapter／人工**——wrapper 記簡單 attempt，unknown 交人處理，不新增 core ABI。
- **core 只記通用效果狀態**——request／pending／done／unknown 由 core 保存，查 provider 仍由 adapter。
- **core Effect＋resolve**——公開 run 與 retry／lost／abandon／adopt／import 動作，包所有有副作用命令。

### 27. 平行 join／reconcile 放哪裡？

**問題｜**平行工具收齊與 crash 後 event／cursor／receipt／next-delivery 對帳，要留腳本還是升成 core？  
**為什麼卡著｜**串行首版不擋；一旦平行，沒有 barrier 可能提早進下一回合，但升 core 又可能把 agent turn 語意帶進去。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；3 位獨立地問到 join 或 reconcile。  
**候選答案｜**

- **先只跑串行**——沒有平行 join，等實測瓶頸再重開。
- **driver 腳本掃結果**——腳本確認全 done／unknown，再投下一回合。
- **core `effect_join(keys)`**——只理解 effect 狀態，不理解 turn／final。
- **core reconcile／barrier**——一起對齊 event、cursor、receipt 與補投。

