# 第 3 輪紀錄 — 結算

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/wrap-up.md)

三輪跑完的最終答案與仍然不知道的。

## 4. 三個數字

**① 自己手寫了幾次 temp＋rename：1／1／2／6。**

| 參賽者 | 答案 | 口徑 |
|---|---|---|
| Carmack | 1 | 一份 `publish.py` |
| Armstrong | 1 | 一份 `immutable_publish()`，8 個呼叫點，用於 payload、ready、claim、aggregate receipt、ack |
| Cantrill | 2 | R1 shell 與 R2 Python／no-replace 各一份；另 7 個靜態呼叫點、9 筆 runtime transaction、1 次人工 rename |
| Thompson | 6 | 靜態實作位置（delivery 1、model-call／tool result／final 3、producer receipt／consumer ack 2）；其中 3 處只有上一輪文字紀錄，本輪無法重驗 |

**② 哪種「不知道做了沒」本機補不回來：四位都是 1 類。** 沒有 query、idempotency 或其他 durable witness 的邊界外 actor，可能已做完，但本機結果尚未 commit。可由 claimed evidence＋ack 修復的本機 consumer ambiguity 不算在內；不合作 consumer 與遠端 provider 同一根因。

**③ 有沒有第二個要同時管的工作：四位都是 0。** producer／consumer／aggregate 是同一 queue protocol 的階段，不是需排程、取消、join、恢復的 agent jobs。

## 6. 仍然不知道的

- consumer acknowledgment 放進現有 `aggregate_instructions()` 時，claim、aggregate target、刪 delivery、ack 與下一個 executor claim 之間的完整原子順序；並行 executor 插入沒測。現有 C++ 發布 aggregate 後直接刪 deliveries，沒有 ack commit。
- ack／receipt ledger 的保留期、清理責任與容量上限（清太早會再變 Unknown）；多 producer、並行 aggregate、receipt 清理、磁碟滿與部分 fsync 失敗的 consumer-ack matrix。
- 正式 Deliver 如何不複製 schema 而驗完整 object／array batch：現有 C ABI 只驗 single object，`read_all()` 沒有 C ABI，array 案沒有 canonical conformance 結果。
- power loss、NFS、非 Linux filesystem 與裝置快取下的結果；`renameat2(RENAME_NOREPLACE)` 的可攜替代；orphan temp 清理契約。
- 無 query／idempotency provider 的 unknown 最後由誰、依什麼權限選 retry、adopt 或 abandon。
- 三輪都沒有真模型、真遠端 provider 或第二個長壽 logical work 的現場。
