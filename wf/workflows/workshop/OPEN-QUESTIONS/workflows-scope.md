# 待答問題：升格門檻、inbox 與 workflows module 邊界
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)

第 35–37 題：task 何時升成 world／lane、inbox 要機械化到哪裡、workflows module 管到哪一層。

## 可以慢慢想的

### 35. task 何時升成 world／lane？

**問題｜**短 task 要在首次 yield、首次需要獨立恢復，還是需要獨立等待／收件／queue 時升格？  
**為什麼卡著｜**job／lane 已拆開，但升格門檻會決定何時建立 kernel、queue、cursor 與生命週期；回頭審視建議先不自動升格。  
**在哪問過｜**〈核心行程與子行程〉、〈用 aos 實現 workflows〉；兩批共 5 位問到或提出門檻。  
**候選答案｜**

- **首次 yield**——一跨回合就原子升成 lane。
- **首次需要獨立恢復**——只有必須單獨重啟／重試時升格。
- **需要獨立等待／反覆收件／自己的 queue**——時間長本身不算，具備獨立執行需求才升格。

### 36. inbox 要機械化到哪裡？

**問題｜**inbox 要維持手工信件、只加明示 `wf accept`，還是連命名與歸檔生命週期都交給 aos？  
**為什麼卡著｜**信件原本可以不回；若直接變 instruction，就會把知會誤升成必須 claim 的工作。  
**在哪問過｜**〈用 aos 實現 workflows〉；2 位直接問到目前痛點，4 位都要求信與 queue 分開。  
**候選答案｜**

- **維持手工 inbox**——寄、讀、忽略、歸檔都不進 aos runtime。
- **只加 `wf accept MAIL`**——信仍可忽略，只有明示接受才轉 open task／Deliver。
- **管理完整信件生命週期**——aos 配唯一名稱、標未讀／已收／done，但接受前仍不進 instruction queue。

### 37. workflows module 管到哪一層？

**問題｜**non-invasive module 只負責安裝、負責安裝＋升級，還是連 task runtime 一起提供？  
**為什麼卡著｜**`install／init／module add` 三種名字背後的責任尚未對齊；若混在一起，模板來源與活狀態會綁成同一套生命週期。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位提出不同命令形狀並留下責任問題。  
**候選答案｜**

- **只管安裝**——建立 `wf/` 非侵入式骨架，安裝後專案自行分叉。
- **安裝＋升級**——另記 source version／base hash，提供三方 diff，不碰 runtime。
- **安裝＋升級＋runtime**——同一 module 也提供 `wf start／wait／resume／done／status`。
