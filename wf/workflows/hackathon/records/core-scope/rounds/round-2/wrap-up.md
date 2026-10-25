# 第 2 輪紀錄 — 結算

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/wrap-up.md)｜[R3 →](../round-3/wrap-up.md)

最終答案以 [第 3 輪結算](../round-3/wrap-up.md) 為準。

## 4. 三個數字

- **①**：仍無共同單位，見第 3 輪。
- **②**：四位都回 **1 類**——provider 可能已接受，但 committed response／result 不存在，且 provider 不能依 key 查詢。Deliver 的 consumed-before-receipt 是本機 ambiguous window，與遠端 Effect unknown 分開，不改這個數字。
- **③**：四位都回 **0**。兩個 producer 是短命 writer／contention，不是第二個長壽 agent、lane、join 或 scheduler。

## 6. 仍然不知道的

仍開著的見 [第 3 輪〈6. 仍然不知道的〉](../round-3/wrap-up.md)。
