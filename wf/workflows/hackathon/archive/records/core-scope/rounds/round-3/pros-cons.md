# 第 3 輪紀錄 — 好處／壞處

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/pros-cons.md)

## 3. 好處／壞處

### 好處

- Effect：response-ready 與 decision-ready 的重複 resolve 都是 commit delta 0、provider ledger delta 0。
- Deliver：合作 consumer 的四個死亡窗都由一個高階 recover 收斂到 ack，重跑不增加 effect；沒有 target 時保留成 Unknown，有 consumer ack 才成為 Already。
- 私有 validator 與 C ABI object parser 的差異有逐案實測。producer、consumer、aggregate 是同一條 protocol 的階段，不需要 lane、join、scheduler 或 proc-table。

### 壞處

- Deliver completion 包含 payload、visibility receipt、claim、aggregate receipt、delivery deletion 與 ack；ack 要讓 producer 在 aggregate 後仍可查，就會留下需要 retention／GC 的紀錄。ack 清太早會重新失憶，不合作 consumer 直接停在 `unknown-consumer-history`。ack gate 要求 ack commit 後才讓 `aos exec` 取 aggregate；另一個 executor 在 receipt／ack 前搶走 `inst.json` 的並行窗口沒測。
- Effect 仍需 request、response、decision、done 四類 evidence，unknown 不能由本機檔案推成 success、failure 或 exactly-once。Publish 仍需唯一 temp、no-replace、內容比對與 receipt；canonical batch parser 沒有公開 C ABI。
