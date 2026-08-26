# 第 3 輪評分與意見

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-2.md)

總分是五項直接相加，滿分 25；不拿來排名。這輪先查上輪指令，再查輸出能不能撐住結論。

## p1（Carmack persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：25 → 25，持平。** 上輪要的兩個 terminal 窗口、同一 resolve 連跑兩次、commit、provider ledger 與 final hash 全部交付；滿分後沒有更高的分可加。

response-ready 案第二次 `commit_delta=0`、`ledger_delta=0`，而且 final hash 與 baseline 相同；decision-ready 案也是零 delta，且沒把 `unknown_abandoned` 偽裝成 success。第一個 harness race 有留原文、作廢、換新 world 重跑，這份回報可信。

**下一輪：**不要再增加 Effect 狀態。換一個支援 query 或 idempotency key 的真實 provider stub，與一個兩者都不支援的 stub，各在 acceptance 後破壞本機 result commit；用同一張轉移表輸出前者可 resolve、後者必須停在 unknown。

## p2（Armstrong persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：25 → 25，持平。** 上輪指定的 target、claim、delete、ack 四刀全部真殺到 exit 137，合作 consumer 四案都收旂，不合作 consumer 則明確 exit 1 停在 unknown；這正是要測的邊界。

最硬的不是 `matrix_assertions=PASS`，而是四份 `PRE_RECOVERY_STATES` 真的不同，而且每案兩次 recover、兩次 `aos exec` 後 `ledger_lines=1`。rogue consumer 的 `unknown-consumer-history` 反例也證明 ack 是協定，不是 producer 自己寫張紙就算完成。

**下一輪：**只補並行 executor 窗口。在 aggregate target commit 後、ack commit 前強制另一個 executor 搶 `inst.json`，輸出 claim 是被 gate 擋住還是真的取走；若取走了，這份 CLI 原型就不能當成可落地的 Deliver 協定。

## p3（Cantrill persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：24 → 25，進步。** 上輪唯一的扣分點已修掉：這次用同一份 inventory 把 2 份實作、7 個 call site、9 筆 transaction、1 次人工 rename 分開，沒再用 runtime 次數回答原碼數量。

直接打現有 C ABI 的結果是 4 案私有 validator 錯放、2 案錯擋，還有 3 案 batch API gap；這比說「schema 可能分叉」有價值。R2 原始現場丟了就只宣稱兩支有 hash 的腳本已復原，沒有為了閉環造假。

**下一輪：**不准寫第三套 parser。做一個最小的 canonical `read_all()` conformance harness，對 single object、array 與錯在第二筆的 batch 各輸出結果；若現有公開邊界根本叫不到 `read_all()`，就把「需要公開 batch validation」當成唯一結論，不要再造 wrapper。

## p4（Thompson persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

**較上輪：25 → 24，退步。** 兩個指定窗口都做對，但第一個數字 `6` 裡有 3 個 R2 位置只靠上輪文字，本輪的原檔已消失，沒有像 p3 那樣用一次 inventory 把全數釘死。這扣的是答案硬度，不是誠實度。

作廢 hard-link／`mv` 版本是對的；`st_nlink` 洩漏歷史就不是不可區分性證明。修正後 `diff_exit=0`，同一 Deliver 命令對兩種歷史都回 Unknown，加上由 claimed bytes 算出的 consumer ack 才回 Already；這段證據很強。

**下一輪：**先把六個 temp＋rename 位置放進同一個可持久、可寫的現場，用一條 source inventory 印出全部六個；做不到就把第一個數字降為「本輪可驗 2，累計主張 6」。別再重測 Already／Unknown／Conflict，那條邊界已經證完。

## 路線判斷

**最值得繼續走的仍是 p2 的 consumer-acknowledged Deliver，下一刀是並行 executor，不是再加 ledger 欄位。** 具體證據是 p2 四刀的 `MATRIX_RESULTS`：target、claim、delete、ack 之後殺掉都能 `first_recover_exit=0`，且兩次 `aos exec` 後 `ledger_lines=1`。同一份回報的 rogue consumer 又給出 `unknown-consumer-history` 與 `rogue_recover_exit=1`，證明這條路只對遵守 ack 協定的 consumer 成立，沒有超賣。p4 的 `diff_exit=0` 加上兩歷史都回 Unknown，則從反面證明 producer-only receipt 已經死了。

**這輪沒有推翻上輪的 scope 判斷。** 上輪說選 (b)、Publish 先做、Deliver 不能當薄 wrapper、(c) 沒有證據，這輪全部維持。改變的是證據等級：consumer ack 從「下輪該驗的解法」變成「協定內四個死亡窗口已跑通」，Effect 也從未測 terminal projection 變成重複 resolve 零 delta。這是確認，不是翻案。

**致命的坑有兩個，但致命對象不同。** 無 query、idempotency 或 durable witness 的外部 effect，在 acceptance 與本機 result commit 之間死掉，對「本機自動 exactly-once」是整條路線致命；不支持 consumer ack 的 producer-only Deliver，在 target 被取走後對「獨立 completion receipt」致命。後者不會殺死 Deliver，只是強迫 ack 進 aggregate commit domain。Linux-only no-replace、receipt／ack retention、orphan temp、batch C ABI、parser 共用與 `.runi` replay 都是麻煩，不是推出控制平面的理由；power-cut 沒測則是證據缺口，在補測前不准把 visibility 叫 durability。

## 可信度判斷

**沒有一份整體回報不可信。** 四位都留下自己的 harness 錯誤、作廢原因與未測邊界，沒有人用「做完了」代替輸出。**但 p4 的第一個數字 `6` 不能當成本輪已獲得獨立證明：**其中 3 個只存在上輪文字紀錄，原檔已被 `/tmp` 清掉。說清楚這點使 p4 的誠實度仍是 5，但不會讓證據自動長回來。

## 現在就得拍板

我會建議使用者選 **(b) Publish → Deliver → Effect**，而且必須分段驗收；不是把四份 Python／shell 原型合併就算 core。Publish 只承諾同 filesystem 的唯一 temp、atomic no-replace、stable key、同 bytes `Already`、異 bytes `Conflict` 與明示的 visibility／fsync 邊界；Deliver 的 completion 必須由 consumer／aggregate ack；Effect 只保存 phase、evidence、unknown 與明示 reconcile，不承諾 exactly-once。

**第一步仍是 Publish，答案跟上輪沒變。** 這不是因為架構圖好看，而是 p2 實測一份 primitive 已有 8 個 call site，p3 的 inventory 也是 7 個 call site，而 p4 本輪又為 producer receipt 與 consumer ack 多寫兩處 temp＋rename。第三個數則四份仍是 0，沒有任何 lane、join、cancel 或第二個長壽 job 的輸出；所以 (c) 仍是為將來臆測的抽象，不做。這是評審建議，最後由使用者拍板。
