# 第 3 輪紀錄 — 結算

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/wrap-up.md)

這一輪的收尾：題目那三個數字收到什麼答案、評委上一輪交辦的事做到了沒、以及三輪跑完仍然不知道的。

## 4. 三個數字

**① 自己手寫了幾次 temp＋rename。** Carmack persona 回 **1**：一份 `publish.py`，三案另列 8 commits；與上一輪同答案，這輪 continuity hash 與兩次 resolve delta 讓 recovery 共用同一實作的證據更硬。Armstrong persona 回 **1**：一份 `immutable_publish()`、8 個呼叫點、recovery 人工 `mv` 為 0；與上一輪同答案，這輪同一 primitive 實際用於 payload、ready、claim、aggregate receipt、ack，並附 `primitive_definitions=1`，證據更硬。Cantrill persona 回 **2**：R1 shell 與 R2 Python/no-replace 各一份，另列 7 個靜態呼叫點、9 筆 runtime transaction、1 次人工 rename；上一輪答 9 筆 transaction，這輪依題目改取實作份數，並有 source inventory，答案比上一輪硬。Thompson persona 回 **6** 個靜態 temp＋rename 實作位置：R1 delivery 1、R2 model-call／tool result／final 3、R3 producer receipt／consumer ack 2；R3 兩處有逐行輸出，R2 三處因 `/tmp` 消失只能沿用上一輪紀錄，因此總數的本輪證據沒有全部重新取得。四人的原始答案是 **1／1／2／6**；p1、p2、p3 取實作份數，p4 取靜態實作位置。

**② 哪種「不知道做了沒」本機補不回來。** 四位都回 **1 類**：沒有 query、idempotency 或其他 durable witness 的邊界外 actor，可能已做完，但本機結果尚未 commit。p1 指向 provider acceptance 到 committed response；p2 把第一輪遠端 provider 與本輪 rogue consumer 記為同一根因；p3 指向非冪等外部 effect；p4 指向無 query／idempotency 的遠端 effect，並把可由 claimed evidence＋ack 修復的本機 consumer ambiguity 排除在外。數字與上一輪相同；本輪新增合作 consumer 已解、rogue consumer 仍停住的對照，以及 Effect 兩個 terminal window 的重複 resolve，邊界比上一輪更硬。

**③ 有沒有第二個要同時管的工作。** 四位都回 **0**。p1 三輪均沒有第二個長壽工作；p2 把 producer／aggregate 列為協定階段，每個 crash world 仍只有一個 instruction exit；p3 的 model、adapter、tool、scheduler、model 是單線序列；p4 把 producer／consumer列為 queue protocol 兩端，而非兩個需排程、取消、join、恢復的 agent jobs。答案與上一輪相同；這輪沒有新增第二個 logical work 的現場，硬度持平。

## 5. 評委上一輪要他們做的事，做到了沒

**Carmack persona。** 做到只打 response-ready／done-missing 與 decision-ready／done-missing 兩窗；兩案都將同一 resolve 連跑兩次，並輸出 provider ledger、commit 數與 final hash，第二次 delta 都是 0。第一個 response-window harness race 作廢後，用新 world 重跑。

**Armstrong persona。** 做到在 target、claim、delivery deletion、ack commit 後各砍一刀；合作 consumer 的同一 key 都能由 ack 機械恢復，`adopt-consumed` 消失。不合作 consumer 另以 `unknown-consumer-history` 停住，沒有用操作員證言補答案。

**Cantrill persona。** 做到同一份 inventory 輸出 2／7／9／1 四欄，題目答案改取 2 份實作；也直接呼叫現有 `libaos_inst` C ABI，逐案列出私有 validator 與 canonical object parser 的差異，沒有再複製一套 schema。batch 因 C ABI 不提供 `read_all()`，只記為 API gap。

**Thompson persona。** 做到只打 publish-success-before-receipt 與 consumer-delete-before-retry，對不可區分的兩份現場使用完全相同的 Deliver 重試命令，兩案都回 Unknown；consumer ack 存在後才回 Already。第一版 hard-link／`mv` 現場因 link count 可分而作廢，固定版另跑。

## 6. 仍然不知道的

仍不知道 consumer acknowledgment 正式放進現有 `aggregate_instructions()` 時，claim、aggregate target、刪 delivery、ack 與下一個 executor claim 之間的完整原子順序。Armstrong persona 用 gate 避免 ack 前執行 aggregate，但沒有測並行 executor 插入；現有 C++ 仍是發布 aggregate 後直接刪 deliveries，沒有 ack commit。

仍不知道 ack／receipt ledger 的保留期、清理責任與容量上限。合作 consumer 的歷史能靠 ack 補回，但清太早會再變 Unknown；不合作 consumer 沒有 claim／ack 時，本輪只能停住。也沒有多 producer、並行 aggregate、receipt 清理、磁碟滿與部分 fsync 失敗的 consumer-ack matrix。

仍不知道正式 Deliver 如何在不複製 schema 的前提下驗完整 object／array batch。現有 C ABI 只驗 single object；本輪已量到私有 validator 與 canonical object parser 互相有接受／拒絕差異，但 `read_all()` 沒有 C ABI，array 三案沒有 canonical conformance 結果。

仍不知道 power loss、NFS、非 Linux filesystem 與裝置快取下的結果，也不知道 `renameat2(RENAME_NOREPLACE)` 的可攜替代與 orphan temp 清理契約。R2 四份 `/tmp` 現場全數消失後，R3 證據仍只暫存在 `/tmp`。

仍不知道無 query／idempotency provider 的 unknown 最後由誰、依什麼權限選 retry、adopt 或 abandon。這輪只證實完整 response 或既有 decision 能重複投影 terminal state，不會重叫 provider；acceptance 到 response commit 之間的真相仍沒有本機答案。三輪也仍沒有真模型、真遠端 provider 或第二個長壽 logical work 的現場。
