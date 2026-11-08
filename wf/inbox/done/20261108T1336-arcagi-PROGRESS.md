---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T13:36:30+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi-S4：計畫可以，一點修正：失敗原因抽樣用 training 未解題

## 做了什麼
給 arcagi-S4（回 20261108T1336）。計畫照走，ROSTER 你那格我 commit。
一點修正（防 evaluation 洩漏）：evaluation 的題型標籤只用來**報告**每類解題率；「未解題抽 50 題寫失敗原因、對到缺哪種積木」請**從 training 未解題抽**——那份會直接驅動主線設計，若用 evaluation 等於拿測試集調求解器。若想看 evaluation 的失敗分佈，只給類別層級的統計，不寫逐題機制。
## 產出（檔案路徑 / commit / 分支）
無
## 沒做到、或證據不足的部分
無
## 需要對方或使用者決定的事
無
