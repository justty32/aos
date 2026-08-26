# 待答問題：workflows 活狀態真源與修改入口
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)｜[白話導讀](../background/questions-workflow-state.md)

第 10–11 題：open 狀態的真源放 Git 還是本機、人要用什麼入口改它。

## 擋住事情的

### 10. workflows 活狀態的真源放哪裡？

**問題｜**open 狀態要隨 Git 跨機，放在 `wf/open/*.md`，還是只作本機狀態，放在 `.aos/wf/*.json`？  
**為什麼卡著｜**這會直接決定唯一真源、status 是否只是 generated view，以及 SESSION-LOG／WAIT_USER 能否由別台機器接手。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地都把它列為最沒把握的一題。  
**候選答案｜**

- **`.aos/wf/*.json` 本機真源**——原子 move 與 generated status 容易；不承諾自然隨 Git 跨機。
- **`wf/open/*.md` Git 真源**——front matter 保存 owner／resume，可跨機與人讀；`.aos` 只負責本次執行。

### 11. 人怎麼修改 workflows 活狀態？

**問題｜**人要直接改 JSON、直接改 markdown front matter，還是只能用 `aos wf` 命令修改？  
**為什麼卡著｜**若資料檔與 generated view 都能手改，就會重新形成雙真相；修復與 reconcile 規則也取決於入口。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位分別提出了三種形狀。  
**候選答案｜**

- **直接改 JSON**——人可修 `ready/<id>.json`，下一次 tick 採用。
- **直接改 markdown**——`wf/open/*.md` 本身是真源，Git diff 就是狀態變更。
- **只用 `aos wf` 命令**——markdown 只由 `status --format md` 產生，不接受反向手改。

