# 題目導讀：workflows 活狀態真源與修改入口
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### 題目：open 狀態要隨 Git 跨機，放在 `wf/open/*.md`，還是只作本機狀態，放在 `.aos/wf/*.json`？

**這題其實在問什麼**：你換電腦、clone repo 或讓另一個人接手時，「現在做到哪裡、卡在誰」要不要自然跟著專案走。
**為什麼會有這題**：目前 `.aos/` 依規格整個不進 Git，但 `SESSION-LOG.md`/`WAIT_USER.md` 是 repo 內文件；若把 open 狀態改放 `.aos`，跨機語意會跟著改變。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| `.aos/wf/*.json` 本機真源 | 原子 move、機器查詢與 generated status 簡單 | clone/換機不帶 open 工作，要另做 export/sync | 工作常在家裡／公司接手，狀態比程式更容易丟 |
| `wf/open/*.md` Git 真源 | 人可讀、Git diff、跨機與審查自然 | move＋Deliver 的恢復動作較難，merge conflict 是真問題 | open 工作含本機秘密／短暫執行狀態，進 Git 反而污染專案 |

**如果現在不決定會怎樣**：會擋住 workflows runtime 的任何磁碟版面與 status 是否只是 view；不擋 T5，也可繼續沿用現在手工 Markdown。
**最小的驗證方式**：從最近一個真 open 事項做兩份同內容假資料，一份 JSON 放臨時 `.aos` 樣板、一份 Markdown 放臨時 Git branch 或工作區外草稿；模擬「換機後續做」與「同機器 crash 後恢復」各一次，看你真正需要的來源是 Git 還是 local state。

### 題目：人要直接改 JSON、直接改 markdown front matter，還是只能用 `aos wf` 命令修改？

**這題其實在問什麼**：機器狀態壞了或你想手動改進度時，最後的維修入口是資料檔本身，還是一支保證狀態轉換的命令。
**為什麼會有這題**：如果 JSON 與 Markdown view 都可以直接改，同一 task 會有兩個可互相打架的入口；但全靠命令也會賠掉「檔案系統就是可修現場」的優點。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| 直接改 JSON | 低階、好修現場，tick 下次直接讀 | 無法阻止非法轉換與漏改關聯檔 | 一次手修讓 state、queue、view 互相不一致 |
| 直接改 Markdown front matter | Git 就是編輯與審查界面，人最容易理解 | parser、formatting、merge 與 Deliver 恢復都要處理 | 機器高頻狀態讓 Git diff 充滿噪音 |
| 只用 `aos wf` 命令 | 單一交易入口，view 可隨時重建 | 命令壞了時的手工修復需另設 escape hatch | 只是改一個 owner/文字卻必須學完整 CLI，手感比 Markdown 差 |

**如果現在不決定會怎樣**：會擋住真源檔案的寫入契約、repair/reconcile 設計與 generated view 的定義；可繼續用現有 Markdown 而不啟動 runtime。
**最小的驗證方式**：用同一個假 task 各完成三個修改：`ready→wait-user`、改 question、收到回答後 resume；分別用 JSON、front matter、三支假 CLI 做，再故意在第二步中斷。比較哪個現場最容易看懂與修回，不必先寫 runtime。

