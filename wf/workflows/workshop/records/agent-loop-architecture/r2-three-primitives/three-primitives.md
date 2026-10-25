# Publish／Deliver／Effect 三個功能家族

> 合併後的功能清單、三者其實是同一件事的合併與依賴鏈，以及「只能先做三樣」的選擇。

使用者給這輪的任務：

> **把 `aos core` 那塊收攏成方向。**

## 合併後的功能清單

R1 的候選收成 **Publish、Deliver、Effect** 三個功能家族。簽名是候選介面，名稱與參數未拍板。

| 名字（子命令／函式） | 簽名（候選共同形狀） | 它解決什麼 | 不做的話腳本要自己幹什麼 |
|---|---|---|---|
| **Publish**（也涵蓋 commit／bundle） | CLI：`aos core publish TARGET TEMP [--durable]`；lib：`publish_at(rootfd, target, source, opts) -> receipt` | 用一次提交發布完整檔案或目錄；選擇是否連檔案與目錄一起 fsync，不讓 cursor／event 露出半套 | 每支腳本都要自造同目錄 temp、write-all、fsync、rename，還要避免 cursor 先前進；檔案與目錄又會各寫一套 |
| **Deliver** | CLI：`aos core deliver --to BASE [--key K] [--durable] -`；lib：`deliver_at(rootfd, base, key, json, opts) -> receipt` | 驗 schema／大小，以 key 去重，再把完整 instruction 投入 queue；同一投遞可回 receipt | 腳本要自行配檔名、檢查 JSON、處理短寫、撞名、覆蓋與重送，仍可能把半份 payload 暴露給彙整者 |
| **Effect**（含 resolve） | CLI：`aos core effect run CALL --key K -- CMD...`；`aos core effect resolve CALL retry\|lost\|abandon\|adopt [FILE]`；lib：`effect_run(...)`／`effect_resolve(...)` | 先記 request／key，再執行外呼；原子提交輸出與 done，crash 留 unknown；resolve 讓人明示重試、放棄或採納外部結果 | shell 只能看到「本機沒有結果」，分不出命令未跑與遠端已收費但尚未落盤；重開後只好盲目重跑，或各自發明 recover 檔案 |

Publish 的 public API 接收已寫好的 temp／source，還是直接收 payload，未定。

## 其實是同一件事的／可以疊在一起的

- capture、invoke、effect run 都是 **Effect run**：先留下 request／key，再執行 command，最後把
  stdout／stderr／exit 與狀態一起提交。
- retry、lost、abandon、import、reconcile、adopt 都是在回答 unknown，收成 **Effect resolve**；
  動詞仍可再減，但不各長一個功能。
- 檔案 commit、目錄 bundle、temp＋rename 都是 **Publish**；差別只在 payload 是檔還是整個目錄。

三個功能是一條依賴鏈：

```text
Publish
├─ Deliver = schema／上限／key／queue ＋ Publish
└─ Effect  = request／done／unknown／resolve ＋ Publish
                                      └─ 完成的 result／receipt 可再交給 Deliver
```

publish 保完整、deliver 保交接、effect 保外呼恢復；**agent 語意留在這條鏈外面。**

## 只能先做三樣的話

四位都選同樣三項、同樣順序：

| 順序 | 功能 | 理由 |
|---|---|---|
| 1 | **Publish** | Deliver／Effect 的底座。先統一完整發布，後兩項才不必各自重寫 temp／fsync／rename |
| 2 | **Deliver** | 三步交接早就缺的投遞原語；不補，T5 每支 driver／adapter 都得自行投 queue，繼續承擔半寫、撞名與重送 |
| 3 | **Effect（含 resolve）** | LLM 與其他外呼有付費／副作用，unknown 若沒有日誌與人工出口，crash 後只能盲目重做；resolve 併進 Effect，不占第四個名額 |
