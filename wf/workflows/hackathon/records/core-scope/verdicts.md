# core scope 黑客松 — 評分與意見（評委）

← [本場索引](README.md)｜[hackathon](../../README.md)

Torvalds persona 逐輪逐位打分（證據強度與誠實度權重最重）、指出下一輪該修什麼、以及「現在就得拍板會選哪個」。

---

## 第 1 輪評分與意見

總分是五項直接相加，滿分 25；不拿它排名。證據與誠實是門檻，沒有現場的完成宣稱，其餘三項再高也沒用。

### p1（Carmack persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

accepted／dropped 的本機 SHA-256 相同、外部 ledger 卻是 1／0，這不是看法，是把「純本機自動恢復」直接判了死刑。你也明寫沒測 fsync、斷電，沒有拿 SIGKILL 冒充 durability，誠實。扣一分只因第一個數字同時報 9 與 6，計數單位沒先鎖死，不能直接拿去拍 scope。

**下一輪：**先定義唯一計數表，逐列列出「原始碼實作份數／靜態呼叫點／實際 commit／人工 rename」，再用私有 `publish`、`deliver`、`effect` 三支原語重跑原本三個 kill point；每案必須輸出恢復前狀態、唯一人工命令、恢復後 ledger，禁止用外部 oracle 替無 query provider 作答。

### p2（Armstrong persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

`tool.exit=137`、`schedule.exit=66`、`aos ... exit=0` 與盲重試後 ledger 由 1 變 2，完整地證明「回合完成」不等於「agent 還活著」，也證明 Effect 不能預設 retry。第一次 `tee` 沒留到證據也照寫並用 fresh world 重跑，這是正確的事故紀錄。11 次 publish 只有 3 次 delivery，讓只做 Deliver 的主張沒有躲閃空間。

**下一輪：**把 key＋receipt 做成可重入的 Publish，讓 rename 前重開不需人工 `mv`；再把無 query provider 的 Effect 固定成 `pending → done | unknown`，只接受明示的 `adopt | retry | abandon`。同一組故障逐個 transition 注入，驗收輸出必須證明每案最多一個高階恢復命令、零搬檔、零重造半批 instruction，並保留重複 effect 的 ledger 檢查。

### p3（Cantrill persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

phase marker 把刀落在哪裡說清楚，錯檔名被三次 exit 0 安靜忽略則抓到一個別人沒抓到的真介面缺陷。PTY 把 wrapper 一起殺掉、拿不到 `aos` exit，你沒有補造數字，這點可信。扣一分同樣是第一個數字混了實作份數、呼叫點、commit 與人工 rename，還不能作橫向判斷。

**下一輪：**做一鍵 crash matrix，先修 harness，讓每一刀都留下獨立的 `aos` exit、instruction exit、queue/temp/final 狀態；再測合法與非法 delivery 名稱、同 target 重投及兩個 producer 同時提交。結果要明確回答 Publish 和 Deliver 各自拒絕什麼、是否 no-replace、錯誤是否可見，別只讓 final 出現就算過。

### p4（Thompson persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 4/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 4/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 4/5 |
| **總分** | **21/25** |

你保留了砍太早的失敗現場，也用 `od` 推翻自己的 `wc -l` 誤判，原始事故證據可信。可是「拿掉 aos 的三行 shell」只跑 happy path，沒有接受同一組 SIGINT、SIGKILL、rename 與重開測試，拿它推出「連 Deliver 都別做」沒有證據。`1` 只說 helper 沒複製，不能消除每個呼叫者仍要正確處理命名、碰撞、receipt 與 recovery 的成本。

**下一輪：**讓 no-aos 三行鏈接受完全相同的三刀與重開驗收，不能另寫人工特例；再讓兩個 producer 各投 1,000 個唯一 ID，輸出投遞數、執行數、遺失數、重複數與覆蓋數。若 shell helper 能在 crash 後無搬檔恢復且全數為零，再談不加 Deliver；否則把失敗點縮成最小 Deliver 的明確契約。

### 路線判斷

**最值得繼續的是 p2 的「共用 Publish 底座，再把 Effect 的 unknown 明文化」這條路。**理由不是它寫得完整，而是兩段輸出正中 scope：成功基線 11 次 publish 只有 3 次 delivery，證明 (a) 只收掉少數提交；盲重試後 `oracle_ledger_lines_after_retry=2`，證明 Effect 不能被一般 Publish 假裝解掉。p1 的 accepted／dropped 本機 snapshot 同 SHA-256、外部 ledger 分別 1／0，是第二份獨立證據；兩份一起足夠支持繼續驗 (b)，而不是憑架構偏好投票。

**看起來漂亮但藏成本的，也是 (b) 裡的 Effect。**只要把它說成「可靠執行副作用」，成本立刻膨脹成 provider-specific idempotency key、query／reconcile、決策 ledger 與人工權限；對不可查 provider，它仍只能誠實停在 `unknown`。Publish 也不是一支 `mv` 就結束：p2 自己已承認 `test` 再 `mv` 有競爭窗且沒有 fsync，p3 又證明檔名錯誤會被安靜吞掉；若不把 no-replace、receipt、錯誤可見性與 durability 邊界寫死，三個原語只會把檔案手術換個名字。

**致命坑只有一個：想靠本機狀態自動判定非冪等遠端 effect 是否完成。**p1 的相同 SHA-256／不同 ledger 已證明兩個真相映成同一本機狀態；任何自動 replay 或自動 abandon 必然至少錯一邊。這擋住的是「透明自動恢復／exactly-once」整個方向，不擋住一個會保留 `unknown`、要求人或 provider reconcile 的 Effect 原語。

其餘目前都是麻煩，不是方向殺手：rename 前 `.temp` 要人工提升、delivery 檔名錯了被忽略、`.runi` 太粗、孤兒 process group，以及 child 失敗但 `aos exec` 回 0。它們很難用，甚至會安靜停死，但都能用 receipt、嚴格驗證、instruction-level 狀態、process-group supervision 與 status 檢查處理；先拿實測把契約釘死，不需要因此造 lane、join 或 proc-table。

### 可信度判斷

沒有哪一份原始現場需要整份作廢；四位都主動揭露了缺證、誤測或未覆蓋範圍。**不可信的是 p4 回報裡「三行 shell 已反證 aos／Deliver 的必要性」那個 scope 結論**：它只展示 `model → tool → model` 的正常輸出，沒有展示 no-aos 版本在同一批 crash point 後能恢復，更沒有處理它自己已經撞到的 identical-client-state／different-provider-state。那段只能證明 happy path 不需要 queue，不能支撐近期 core 連最小投遞都不做。

### 現在就得拍板

我會建議使用者選 **(b) Publish → Deliver → Effect**，但把 Effect 的承諾限制為記錄 phase、保留 `unknown`、接受明示 reconcile 決策；不要承諾 exactly-once。**第一步只做 Publish**：同 filesystem 的 temp＋原子提交、no-replace、穩定 key、可重入 receipt、明確錯誤與宣告清楚的 fsync 邊界，然後把現有 model response、request、result、final 全部換到同一契約上重跑 crash matrix。Deliver 應薄薄疊在 Publish 上；第三個數字四份都是 0，在出現第二個真實工作以前，不准把控制平面塞進 core。這是評審建議，最後仍由使用者拍板。

## 第 2 輪評分與意見

總分仍是五項直接相加，滿分 25；不拿來排名。這輪先看上輪指示有沒有做，再看輸出是否撐得住結論。

### p1（Carmack persona）

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

### p2（Armstrong persona）

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

### p3（Cantrill persona）

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

### p4（Thompson persona）

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

### 路線判斷

**最值得繼續走的是 p2 這條，但下一步只准攻 consumer acknowledgment。** 具體證據是 p2 的 consumed-before-receipt 輸出：consumer 後 ready 與 receipt 都不存在，最後只能產生 `"durability":"operator-attested-after-ambiguous-consumption"`。這比繼續加 Effect 狀態更值錢，因為它正在決定 Deliver 能否獨立於 aggregate，也決定 (b) 裡 Publish 與 Deliver 的真正分界。p3 的 v1 race 「兩方 exit 0、final target=B」和 p4 的 shared-slot「968 次無聲覆蓋、1,000 件遺失」則已經把 no-replace 的需求證完，不用第三輪再證一次。

**這輪有推翻上輪的一部分判斷。** 「選 (b)」沒被推翻，但「Deliver 應薄薄疊在 Publish 上」已經站不住：p2 證明 queue target 可以在 receipt 前被 consumer 消費，p3 與 p4 又證明 aggregate 後同 key 會失憶。另一個被明確推翻的是上輪 p4 那個「三行 shell 已反證 Deliver」的結論；這輪同命令重開直接把 effect 做了兩次。

**致命的坑仍只有一個：無 query／idempotency 的遠端 effect，在 acceptance 與 committed result 之間被砍後，本機不可能自動還原真相。** p1 的同命令對應 ledger 1／0、p2 的明示 retry 對應 ledger 1→2，p4 的 blind restart 對應 effect 1→2，三份證據已把自動 exactly-once 判死。consumed-before-receipt 則對「獨立 Deliver 自己發完成收據」是致命坑，對 Deliver 本身不是；把 acknowledgment 交給 consumer／aggregate 就能繼續驗。Linux-only `renameat2`、fsync 未做斷電測試、孤兒 temp、receipt 清理、schema 共用與 `.runi` 恢復都只是麻煩；必須解，但沒有一個為控制平面創造了需求。

### 可信度判斷

沒有一份整體回報需要作廢，四位都保留了失敗現場。**若必須指出一份不可相信的題目答案，是 p3 回報裡的第一個數字 `9`。** 它有可重現的 transaction 統計，但題目問的是手寫 temp＋rename 幾次；把計數單位改成 runtime transaction，再宣布這是「唯一主口徑」，那個數不能拿來拍 scope。這不是說 p3 造假；正因為他把單位寫得很清楚，才能確定是答錯問題，所以誠實度仍是 5。

### 現在就得拍板

我會建議使用者仍選 **(b) Publish → Deliver → Effect**，但這是三個分段驗收的窄原語，不是一次吞下 618 行原型；Effect 只能保存 `unknown` 與明示決策，不准宣稱 exactly-once。**第一步仍是 Publish**：只做同 filesystem 的唯一 temp、atomic no-replace、stable key、同 bytes `Already`、異 bytes `Conflict` 與 visibility receipt；緊接著在公開 Deliver completion receipt 前，必須用 p2 下一輪的 consumer acknowledgment 實驗決定 ledger 邊界。

跟上輪比，**scope 選擇沒變，第一步也沒變；變的是 Deliver 不再被假定為獨立薄 wrapper**。第三個數四份仍是 0，而且三份 multi-producer 實驗只證明 writer contention，沒有第二個長壽工作；所以 (c) 仍然是為將來虛構需求，不做。這是評審建議，最後由使用者拍板。

## 第 3 輪評分與意見

總分是五項直接相加，滿分 25；不拿來排名。這輪先查上輪指令，再查輸出能不能撐住結論。

### p1（Carmack persona）

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

### p2（Armstrong persona）

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

### p3（Cantrill persona）

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

### p4（Thompson persona）

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

### 路線判斷

**最值得繼續走的仍是 p2 的 consumer-acknowledged Deliver，下一刀是並行 executor，不是再加 ledger 欄位。** 具體證據是 p2 四刀的 `MATRIX_RESULTS`：target、claim、delete、ack 之後殺掉都能 `first_recover_exit=0`，且兩次 `aos exec` 後 `ledger_lines=1`。同一份回報的 rogue consumer 又給出 `unknown-consumer-history` 與 `rogue_recover_exit=1`，證明這條路只對遵守 ack 協定的 consumer 成立，沒有超賣。p4 的 `diff_exit=0` 加上兩歷史都回 Unknown，則從反面證明 producer-only receipt 已經死了。

**這輪沒有推翻上輪的 scope 判斷。** 上輪說選 (b)、Publish 先做、Deliver 不能當薄 wrapper、(c) 沒有證據，這輪全部維持。改變的是證據等級：consumer ack 從「下輪該驗的解法」變成「協定內四個死亡窗口已跑通」，Effect 也從未測 terminal projection 變成重複 resolve 零 delta。這是確認，不是翻案。

**致命的坑有兩個，但致命對象不同。** 無 query、idempotency 或 durable witness 的外部 effect，在 acceptance 與本機 result commit 之間死掉，對「本機自動 exactly-once」是整條路線致命；不支持 consumer ack 的 producer-only Deliver，在 target 被取走後對「獨立 completion receipt」致命。後者不會殺死 Deliver，只是強迫 ack 進 aggregate commit domain。Linux-only no-replace、receipt／ack retention、orphan temp、batch C ABI、parser 共用與 `.runi` replay 都是麻煩，不是推出控制平面的理由；power-cut 沒測則是證據缺口，在補測前不准把 visibility 叫 durability。

### 可信度判斷

**沒有一份整體回報不可信。** 四位都留下自己的 harness 錯誤、作廢原因與未測邊界，沒有人用「做完了」代替輸出。**但 p4 的第一個數字 `6` 不能當成本輪已獲得獨立證明：**其中 3 個只存在上輪文字紀錄，原檔已被 `/tmp` 清掉。說清楚這點使 p4 的誠實度仍是 5，但不會讓證據自動長回來。

### 現在就得拍板

我會建議使用者選 **(b) Publish → Deliver → Effect**，而且必須分段驗收；不是把四份 Python／shell 原型合併就算 core。Publish 只承諾同 filesystem 的唯一 temp、atomic no-replace、stable key、同 bytes `Already`、異 bytes `Conflict` 與明示的 visibility／fsync 邊界；Deliver 的 completion 必須由 consumer／aggregate ack；Effect 只保存 phase、evidence、unknown 與明示 reconcile，不承諾 exactly-once。

**第一步仍是 Publish，答案跟上輪沒變。** 這不是因為架構圖好看，而是 p2 實測一份 primitive 已有 8 個 call site，p3 的 inventory 也是 7 個 call site，而 p4 本輪又為 producer receipt 與 consumer ack 多寫兩處 temp＋rename。第三個數則四份仍是 0，沒有任何 lane、join、cancel 或第二個長壽 job 的輸出；所以 (c) 仍是為將來臆測的抽象，不做。這是評審建議，最後由使用者拍板。
