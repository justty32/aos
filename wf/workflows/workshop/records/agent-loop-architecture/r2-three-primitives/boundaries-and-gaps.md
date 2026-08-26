# core 的邊界與還缺的一塊

> 四位刻意留在腳本／adapter 的事，以及三項之外還沒被吃掉的 core 候選。

## 不該進 `aos core` 的

四位收攏時也一起砍掉了 agent 專用政策：

| 留在腳本／adapter／module 的事 | 誰這樣劃界 | 為什麼不進 core |
|---|---|---|
| prompt 組裝、system message、對話裁切 | 工程師、架構師、研究人員；開發者也把組 prompt 留給 driver | 它們隨模型、上下文策略與產品需求變，不是原子交接問題 |
| response 解析、provider／tool schema、response→tool call | **四位獨立地都留在 adapter** | 每家 CLI 與 tool 格式不同；core 只需安全發布 bytes 與外呼狀態，不必理解內容 |
| final 判斷、stop／budget 政策 | **四位都排除** | 「何時不再投遞」是 driver 的 agent 政策；core 只看有沒有下一批 instruction |
| provider request ID 查詢與對帳 | 架構師、研究人員明確排除；工程師也不確定 capture 是否該含 provider adapter | 這是供應商能力；通用 Effect 只表示 unknown，adapter 才知道去哪裡查回結果 |

所以三個 core 原語合起來仍然**不會成為 `aos agent`**。T5 的腳本仍要組 prompt、呼叫正確 adapter、
解出 tool calls、判斷 final；這些不是漏收，而是四位刻意保留的可變部分。

## 還缺的一塊

只跑**串行**模型→工具→模型時，四位認為 Publish＋Deliver＋Effect 已足以支撐；剩下的 script
工作正是 T5 要觀察的 agent 語意。真正還沒被三項功能吃掉的 core 候選有兩塊：

1. **平行工具 join。**資深工程師提出 `effect_join(keys)`：沒有它，driver 必須掃多個 effect，
   判斷是否全 done／是否有 unknown，並防止尚未收齊就提交下一回合。研究人員也不確定 kernel
   尾聲是否要等 parallel tools；其餘兩位沒有把 join 選進前三項。
2. **turn reconcile／barrier。**要接工具的開發者指出，crash 後仍要對齊 event、cursor、receipts
   與 next delivery：哪一個已提交、哪一個只差同 key 補投。若沒有通用功能，driver 要逐一掃檔。
   他自己也標記不確定：若 reconcile 必須理解 turn／final，它就不再是通用 core 原語。

另有一個條件式缺口：研究人員指出，**若 Publish 不支援目錄**，event 與 cursor 仍可能分兩次
可見，腳本就得自行補交易。這不是第四項功能，而是 Publish 是否真的涵蓋 directory bundle 的
規格問題。

provider 對帳仍然得靠 adapter；三個 core 原語最多把狀態誠實地停在 unknown，不能替不同 LLM
CLI 查帳。這同樣是四位刻意留下的邊界，不是要求 core 補 provider-specific 功能。

