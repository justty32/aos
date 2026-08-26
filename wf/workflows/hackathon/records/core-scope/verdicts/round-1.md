# 第 1 輪評分與意見

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[下一份 →](round-2.md)

總分是五項直接相加，滿分 25；不拿它排名。證據與誠實是門檻，沒有現場的完成宣稱，其餘三項再高也沒用。

## p1（Carmack persona）

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

## p2（Armstrong persona）

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

## p3（Cantrill persona）

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

## p4（Thompson persona）

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

## 路線判斷

**最值得繼續的是 p2 的「共用 Publish 底座，再把 Effect 的 unknown 明文化」這條路。**理由不是它寫得完整，而是兩段輸出正中 scope：成功基線 11 次 publish 只有 3 次 delivery，證明 (a) 只收掉少數提交；盲重試後 `oracle_ledger_lines_after_retry=2`，證明 Effect 不能被一般 Publish 假裝解掉。p1 的 accepted／dropped 本機 snapshot 同 SHA-256、外部 ledger 分別 1／0，是第二份獨立證據；兩份一起足夠支持繼續驗 (b)，而不是憑架構偏好投票。

**看起來漂亮但藏成本的，也是 (b) 裡的 Effect。**只要把它說成「可靠執行副作用」，成本立刻膨脹成 provider-specific idempotency key、query／reconcile、決策 ledger 與人工權限；對不可查 provider，它仍只能誠實停在 `unknown`。Publish 也不是一支 `mv` 就結束：p2 自己已承認 `test` 再 `mv` 有競爭窗且沒有 fsync，p3 又證明檔名錯誤會被安靜吞掉；若不把 no-replace、receipt、錯誤可見性與 durability 邊界寫死，三個原語只會把檔案手術換個名字。

**致命坑只有一個：想靠本機狀態自動判定非冪等遠端 effect 是否完成。**p1 的相同 SHA-256／不同 ledger 已證明兩個真相映成同一本機狀態；任何自動 replay 或自動 abandon 必然至少錯一邊。這擋住的是「透明自動恢復／exactly-once」整個方向，不擋住一個會保留 `unknown`、要求人或 provider reconcile 的 Effect 原語。

其餘目前都是麻煩，不是方向殺手：rename 前 `.temp` 要人工提升、delivery 檔名錯了被忽略、`.runi` 太粗、孤兒 process group，以及 child 失敗但 `aos exec` 回 0。它們很難用，甚至會安靜停死，但都能用 receipt、嚴格驗證、instruction-level 狀態、process-group supervision 與 status 檢查處理；先拿實測把契約釘死，不需要因此造 lane、join 或 proc-table。

## 可信度判斷

沒有哪一份原始現場需要整份作廢；四位都主動揭露了缺證、誤測或未覆蓋範圍。**不可信的是 p4 回報裡「三行 shell 已反證 aos／Deliver 的必要性」那個 scope 結論**：它只展示 `model → tool → model` 的正常輸出，沒有展示 no-aos 版本在同一批 crash point 後能恢復，更沒有處理它自己已經撞到的 identical-client-state／different-provider-state。那段只能證明 happy path 不需要 queue，不能支撐近期 core 連最小投遞都不做。

## 現在就得拍板

我會建議使用者選 **(b) Publish → Deliver → Effect**，但把 Effect 的承諾限制為記錄 phase、保留 `unknown`、接受明示 reconcile 決策；不要承諾 exactly-once。**第一步只做 Publish**：同 filesystem 的 temp＋原子提交、no-replace、穩定 key、可重入 receipt、明確錯誤與宣告清楚的 fsync 邊界，然後把現有 model response、request、result、final 全部換到同一契約上重跑 crash matrix。Deliver 應薄薄疊在 Publish 上；第三個數字四份都是 0，在出現第二個真實工作以前，不准把控制平面塞進 core。這是評審建議，最後仍由使用者拍板。
