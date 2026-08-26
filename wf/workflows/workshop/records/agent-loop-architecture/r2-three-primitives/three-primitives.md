# Publish／Deliver／Effect 三個功能家族

> 本輪的任務、合併後的功能清單、三者其實是同一件事的合併與依賴鏈，以及「只能先做三樣」的一致選擇。

這輪不再發散新介面，而是把 R1 的不同命名收成最少的功能組。使用者給的任務只有一句：

> **把 `aos core` 那塊收攏成方向。**

## 合併後的功能清單

四份清單最後只剩 **Publish、Deliver、Effect** 三個功能家族。下表的簽名是四位輸出的共同形狀，
仍是候選介面，不代表使用者已拍板名稱或參數。

| 名字（子命令／函式） | 簽名（候選共同形狀） | 它解決什麼 | 不做的話腳本要自己幹什麼 | 誰提的 |
|---|---|---|---|---|
| **Publish**（也涵蓋 commit／bundle） | CLI：`aos core publish TARGET TEMP [--durable]`；lib：`publish_at(rootfd, target, source, opts) -> receipt` | 用一次提交發布完整檔案或目錄；選擇是否連檔案與目錄一起 fsync，不讓 cursor／event 露出半套 | 每支腳本都要自造同目錄 temp、write-all、fsync、rename，還要避免 cursor 先前進；檔案與目錄又會各寫一套 | 工程師、架構師**兩位獨立地明確提出**；研究人員與開發者在 R2 也把它列進合併清單，但標明另外兩人的 Deliver／Effect 原本已內含同一動作 |
| **Deliver** | CLI：`aos core deliver --to BASE [--key K] [--durable] -`；lib：`deliver_at(rootfd, base, key, json, opts) -> receipt` | 驗 schema／大小，以 key 去重，再把完整 instruction 投入 queue；同一投遞可回 receipt | 腳本要自行配檔名、檢查 JSON、處理短寫、撞名、覆蓋與重送，仍可能把半份 payload 暴露給彙整者 | **四位獨立地都提了**；也是四位一致指出的現存投遞缺口 |
| **Effect**（合併 capture／invoke／run；含 resolve） | CLI：`aos core effect run CALL --key K -- CMD...`；`aos core effect resolve CALL retry\|lost\|abandon\|adopt [FILE]`；lib：`effect_run(...)`／`effect_resolve(...)` | 先記 request／key，再執行外呼；原子提交輸出與 done，crash 留 unknown；resolve 讓人明示重試、放棄或採納外部結果 | shell 只能看到「本機沒有結果」，分不出命令未跑與遠端已收費但尚未落盤；重開後只好盲目重跑，或各自發明 recover 檔案 | **四位獨立地都提了**；capture／invoke／effect 是同一件事，retry／lost／import／reconcile／adopt 被收進同一個 resolve 家族 |

Publish 的「檔案／目錄」仍有一個簽名差異：工程師、架構師、研究人員傳已寫好的 temp／source，
開發者的候選函式可直接收 payload。R2 只把共同提交邊界收成一項，沒有替使用者決定 public API
接收哪一種。

## 其實是同一件事的／可以疊在一起的

**四位各自都做出相同的合併**：

- R1 的 capture、invoke、effect run 都是 **Effect run**：先留下 request／key，再執行 command，
  最後把 stdout／stderr／exit 與狀態一起提交。
- retry、lost、abandon、import、reconcile、adopt 都是在回答 unknown，收成 **Effect resolve**；
  動詞仍可再減，但不再各長一個功能。
- 檔案 commit、目錄 bundle、temp＋rename 都是 **Publish**；差別只在 payload 是檔還是整個目錄。

三個功能也不是平行三座島，而是一條依賴鏈：

```text
Publish
├─ Deliver = schema／上限／key／queue ＋ Publish
└─ Effect  = request／done／unknown／resolve ＋ Publish
                                      └─ 完成的 result／receipt 可再交給 Deliver
```

資深工程師說「Publish 是底座，receipt 可再 Deliver」；資深架構師與研究人員都寫成
「deliver 管 queue、effect 管外呼」；要接工具的開發者則把三者縮成「publish 保完整、deliver 保
交接、effect 保外呼恢復」。**四位獨立地都把 agent 語意留在這條鏈外面。**

## 只能先做三樣的話

四位沒有各選一套不同的三樣；**四位都選中同樣三項，而且依賴順序也相同**：

| 順序 | 功能 | 入選情況 | 四位給的理由 |
|---|---|---|---|
| 1 | **Publish** | **4／4 都選** | 工程師、架構師、研究人員把它稱為 Deliver／Effect 的底座；開發者同樣按此依賴順序排列。先統一完整發布，後兩項才不必各自重寫 temp／fsync／rename |
| 2 | **Deliver** | **4／4 都選** | 這不是為 agent 新想出的功能，而是三步交接早就缺的投遞原語；不補，T5 每支 driver／adapter 都得自行投 queue，繼續承擔半寫、撞名與重送 |
| 3 | **Effect（含 resolve）** | **4／4 都選** | LLM 與其他外呼有付費／副作用，unknown 若沒有日誌與人工出口，crash 後只能盲目重做；resolve 被併進 Effect，沒有占第四個名額 |

這是 R2 最強的訊號：**Publish 的原始明確提案來自兩位，但到了「只能留三樣」時，四位都把它
選為第一層；Deliver 與 Effect 則從 R1 起就是四位獨立提出，R2 又被四位全數保留。**

