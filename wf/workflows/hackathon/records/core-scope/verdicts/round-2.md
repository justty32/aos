# 第 2 輪評分與意見

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-1.md)｜[下一份 →](round-3.md)

總分仍是五項直接相加，滿分 25；不拿來排名。這輪先看上輪指示有沒有做，再看輸出是否撐得住結論。

## p1（Carmack persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：24 → 25，進步。** 上輪扣的計數單位這次已拆成 1 份實作、9 個呼叫點、每案 8 次 commit、0 次人工 rename，而且題目答案明確取 1。

上輪要的三支私有原語、故障前後狀態、單一恢復命令和禁止 oracle 作答，全部有做。accepted 與 dropped 用同一條 `abandon-unknown`，完成後才讀到 ledger 為 1 與 0，這才是「本機無解」的有效證明。兩次原型失敗都留了原文並用乾淨案重跑，沒有把修過的故事偽裝成一次成功。

**下一輪：**只打兩個未測窗口：response 已 commit、done 未 commit，以及 decision 已 commit、done 未 commit。每案必須用同一條 resolve 命令連續跑兩次，輸出 provider ledger、commit 數與 final hash，證明可重入且沒有第二次 effect。

## p2（Armstrong persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：25 → 25，持平。** 不是沒進展，是上輪已滿分；這次把 key＋receipt、`pending → done | unknown`、`adopt | retry | abandon` 和零搬檔都真正跑出來，還多打出 consumed-before-receipt。

上輪的驗收條件全數交付，尤其 retry 後 ledger 從 1 變 2，沒有拿「高階命令」四個字假裝安全。更有價值的是 target 被 consumer 吃掉、receipt 未落盤後，只能發出 `operator-attested-after-ambiguous-consumption`；這直接打穿「Deliver 永遠只是 Publish 的薄 wrapper」。第一次 race 死在 mkdir TOCTOU 也照留，誠實度沒有折價。

**下一輪：**就做 consumer acknowledgment，分別砍在 target commit、aggregate claim、delivery deletion、ack commit 後。同一 key 重開必須只得到一個機械可證的結果，且 `adopt-consumed` 必須消失；做不到就用兩個相同磁碟現場、不同歷史的輸出宣告獨立 Deliver receipt 方案死亡。

## p3（Cantrill persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

**較上輪：24 → 24，持平。** harness、錯名、same-target race 與 2,000 件壓力測試全部補齊，但第一個數仍扣一分：題目問「手寫幾次 temp＋rename」，你回的 9 是 runtime transaction，不是手寫位置。

上輪指示的一鍵 matrix 和可見錯誤已做到；Publish v1 兩方 exit 0、B 無聲覆蓋 A，v2 變成單一 published 與 conflict，路線邊界很硬。你也把無效 SIGINT harness 和 `rg -h` 的 135 行誤計數作廢，沒有偷刪失敗。但「自己宣告主口徑」不能改寫題目的單位；9 只能支持 Publish 使用面，不能當第一個數字。

**下一輪：**不要先回填 tarball；先用同一份 source inventory 輸出四欄：實作份數、靜態呼叫點、runtime transaction、人工 rename，題目答案固定取實作份數。然後用現有 `libaos_inst` C ABI 驗證同一批合法／非法 instruction，輸出私有 validator 與 canonical parser 的逐案差異，不准複製第二套 schema。

## p4（Thompson persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：21 → 25，進步。** 上輪沒證據的「三行 shell 足夠」這次被自己的三刀推翻，而 2,000 件對照又把負責點精確縮到 key 與 no-replace 契約。

上輪指示全部照做：no-aos 在 SIGINT／SIGKILL 後都把 effect 從 1 做成 2，shared-slot 實測遺失 1,000 件，global-ID 則 2,000 件全數到達。最值錢的不是改口號，是公開撤回上輪結論，而且用兩行 effect log 和精確集合差來撤。hard-link 原型留下孤兒 temp 也照報，這份回報可信。

**下一輪：**只打 publish-success-before-receipt 與 consumer-delete-before-retry 兩個窗口。對每個磁碟現場用完全相同的 Deliver 重試命令，輸出是 `Already`、`Unknown` 還是 `Conflict`；若沒有 ledger 就無法唯一判定，不要用操作員證言補答案。

## 路線判斷

**最值得繼續走的是 p2 這條，但下一步只准攻 consumer acknowledgment。** 具體證據是 p2 的 consumed-before-receipt 輸出：consumer 後 ready 與 receipt 都不存在，最後只能產生 `"durability":"operator-attested-after-ambiguous-consumption"`。這比繼續加 Effect 狀態更值錢，因為它正在決定 Deliver 能否獨立於 aggregate，也決定 (b) 裡 Publish 與 Deliver 的真正分界。p3 的 v1 race 「兩方 exit 0、final target=B」和 p4 的 shared-slot「968 次無聲覆蓋、1,000 件遺失」則已經把 no-replace 的需求證完，不用第三輪再證一次。

**這輪有推翻上輪的一部分判斷。** 「選 (b)」沒被推翻，但「Deliver 應薄薄疊在 Publish 上」已經站不住：p2 證明 queue target 可以在 receipt 前被 consumer 消費，p3 與 p4 又證明 aggregate 後同 key 會失憶。另一個被明確推翻的是上輪 p4 那個「三行 shell 已反證 Deliver」的結論；這輪同命令重開直接把 effect 做了兩次。

**致命的坑仍只有一個：無 query／idempotency 的遠端 effect，在 acceptance 與 committed result 之間被砍後，本機不可能自動還原真相。** p1 的同命令對應 ledger 1／0、p2 的明示 retry 對應 ledger 1→2，p4 的 blind restart 對應 effect 1→2，三份證據已把自動 exactly-once 判死。consumed-before-receipt 則對「獨立 Deliver 自己發完成收據」是致命坑，對 Deliver 本身不是；把 acknowledgment 交給 consumer／aggregate 就能繼續驗。Linux-only `renameat2`、fsync 未做斷電測試、孤兒 temp、receipt 清理、schema 共用與 `.runi` 恢復都只是麻煩；必須解，但沒有一個為控制平面創造了需求。

## 可信度判斷

沒有一份整體回報需要作廢，四位都保留了失敗現場。**若必須指出一份不可相信的題目答案，是 p3 回報裡的第一個數字 `9`。** 它有可重現的 transaction 統計，但題目問的是手寫 temp＋rename 幾次；把計數單位改成 runtime transaction，再宣布這是「唯一主口徑」，那個數不能拿來拍 scope。這不是說 p3 造假；正因為他把單位寫得很清楚，才能確定是答錯問題，所以誠實度仍是 5。

## 現在就得拍板

我會建議使用者仍選 **(b) Publish → Deliver → Effect**，但這是三個分段驗收的窄原語，不是一次吞下 618 行原型；Effect 只能保存 `unknown` 與明示決策，不准宣稱 exactly-once。**第一步仍是 Publish**：只做同 filesystem 的唯一 temp、atomic no-replace、stable key、同 bytes `Already`、異 bytes `Conflict` 與 visibility receipt；緊接著在公開 Deliver completion receipt 前，必須用 p2 下一輪的 consumer acknowledgment 實驗決定 ledger 邊界。

跟上輪比，**scope 選擇沒變，第一步也沒變；變的是 Deliver 不再被假定為獨立薄 wrapper**。第三個數四份仍是 0，而且三份 multi-producer 實驗只證明 writer contention，沒有第二個長壽工作；所以 (c) 仍然是為將來虛構需求，不做。這是評審建議，最後由使用者拍板。
