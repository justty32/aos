# core 的邊界與還缺的一塊

> 刻意留在腳本／adapter 的事，以及三項之外還沒被吃掉的 core 候選。

## 不該進 `aos core` 的

| 留在腳本／adapter／module 的事 | 為什麼不進 core |
|---|---|
| prompt 組裝、system message、對話裁切 | 它們隨模型、上下文策略與產品需求變，不是原子交接問題 |
| response 解析、provider／tool schema、response→tool call | 每家 CLI 與 tool 格式不同；core 只需安全發布 bytes 與外呼狀態，不必理解內容 |
| final 判斷、stop／budget 政策 | 「何時不再投遞」是 driver 的 agent 政策；core 只看有沒有下一批 instruction |
| provider request ID 查詢與對帳 | 這是供應商能力；通用 Effect 只表示 unknown，adapter 才知道去哪裡查回結果 |

三個 core 原語合起來**不會成為 `aos agent`**。T5 的腳本仍要組 prompt、呼叫正確 adapter、解出 tool
calls、判斷 final；這些是刻意保留的可變部分，不是漏收。

## 還缺的一塊

只跑**串行**模型→工具→模型時，Publish＋Deliver＋Effect 已足以支撐。還沒被三項吃掉的 core 候選有兩塊：

1. **平行工具 join。**候選 `effect_join(keys)`：沒有它，driver 要掃多個 effect，判斷是否全 done／是否
   有 unknown，並防止尚未收齊就提交下一回合。kernel 尾聲是否要等 parallel tools 也未定。
2. **turn reconcile／barrier。**crash 後要對齊 event、cursor、receipts 與 next delivery：哪一個已提交、
   哪一個只差同 key 補投。沒有通用功能，driver 要逐一掃檔。若 reconcile 必須理解 turn／final，它就
   不是通用 core 原語。

條件式缺口：**Publish 若不支援目錄**，event 與 cursor 仍可能分兩次可見，腳本就得自行補交易。這不是
第四項功能，而是 Publish 是否涵蓋 directory bundle 的規格問題。

provider 對帳靠 adapter；三個 core 原語最多把狀態誠實地停在 unknown，不替不同 LLM CLI 查帳。
