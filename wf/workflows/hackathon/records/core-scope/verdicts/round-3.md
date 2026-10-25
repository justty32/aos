# 第 3 輪評分與意見

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-2.md)

總分算法同第 1 輪。

| 參賽者 | 總分 | 最硬的證據 |
|---|---:|---|
| p1（Carmack persona） | 25 | response-ready 第二次 resolve `commit_delta=0`、`ledger_delta=0`、final hash 與 baseline 相同；decision-ready 零 delta 且保留 `unknown_abandoned` |
| p2（Armstrong persona） | 25 | 四刀 `PRE_RECOVERY_STATES` 各不同，兩次 recover、兩次 `aos exec` 後 `ledger_lines=1`；rogue consumer 停在 `unknown-consumer-history`，證明 ack 是協定，不是 producer 自己寫張紙 |
| p3（Cantrill persona） | 25 | 現有 C ABI 對照：私有 validator 4 案錯放、2 案錯擋、3 案 batch API gap |
| p4（Thompson persona） | 24 | `diff_exit=0` 兩歷史同回 Unknown，有 consumer ack 才回 Already；第一個數字 `6` 有 3 處只靠上輪文字，不算本輪獨立證明 |

## 路線判斷

**最值得繼續走的是 p2 的 consumer-acknowledged Deliver。** 只對遵守 ack 協定的 consumer 成立；p4 的不可區分對照從反面證明 producer-only receipt 已經死了。第 2 輪的 scope 判斷（選 (b)、Publish 先做、Deliver 不能當薄 wrapper、(c) 沒有證據）全部維持。

**致命的坑有兩個，致命對象不同。** 無 query、idempotency 或 durable witness 的外部 effect，在 acceptance 與本機 result commit 之間死掉，對「本機自動 exactly-once」是整條路線致命；不支持 consumer ack 的 producer-only Deliver，在 target 被取走後對「獨立 completion receipt」致命——後者不會殺死 Deliver，只是強迫 ack 進 aggregate commit domain。Linux-only no-replace、receipt／ack retention、orphan temp、batch C ABI、parser 共用與 `.runi` replay 都是麻煩，不是推出控制平面的理由；power-cut 沒測則是證據缺口，在補測前不准把 visibility 叫 durability。

## 可信度判斷

沒有一份整體回報不可信；四位都留下自己的 harness 錯誤、作廢原因與未測邊界。

## 現在就得拍板

我會建議使用者選 **(b) Publish → Deliver → Effect**，而且必須分段驗收；不是把四份 Python／shell 原型合併就算 core。Publish 只承諾同 filesystem 的唯一 temp、atomic no-replace、stable key、同 bytes `Already`、異 bytes `Conflict` 與明示的 visibility／fsync 邊界；Deliver 的 completion 必須由 consumer／aggregate ack；Effect 只保存 phase、evidence、unknown 與明示 reconcile，不承諾 exactly-once。

**第一步是 Publish**：一份 primitive 已有 8 個 call site（p2）、7 個 call site（p3），producer receipt 與 consumer ack 又多兩處 temp＋rename（p4）。第三個數四份都是 0，沒有任何 lane、join、cancel 或第二個長壽 job 的輸出；(c) 是為將來臆測的抽象，不做。這是評審建議，最後由使用者拍板。

## 若再跑一輪的下一刀

- **Effect**：不再加狀態。用一個支援 query 或 idempotency key 的 provider stub 與一個都不支援的，各在 acceptance 後破壞本機 result commit；同一張轉移表輸出前者可 resolve、後者必須停在 unknown。
- **Deliver**：只補並行 executor 窗口——aggregate target commit 後、ack commit 前強制另一個 executor 搶 `inst.json`，看 claim 是被 gate 擋住還是真的取走；取走了，這份原型就不能當可落地的 Deliver 協定。
- **schema**：不寫第三套 parser。做最小的 canonical `read_all()` conformance harness，對 single object、array、錯在第二筆的 batch 各輸出結果；公開邊界叫不到 `read_all()`，就以「需要公開 batch validation」為唯一結論。
- **第一個數字**：六個 temp＋rename 位置放進同一個可持久、可寫的現場，用一條 source inventory 印出；做不到就降為「本輪可驗 2，累計主張 6」。Already／Unknown／Conflict 的邊界已經證完，不再重測。
