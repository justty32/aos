# 第 1 輪紀錄 — 結算

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/wrap-up.md)

這一輪的收尾：題目那三個數字收到什麼答案，以及仍然不知道的。

## 4. 三個數字

**① 自己手寫了幾次 temp＋rename。** Carmack persona 報 **9 次**：正常 runtime 原始碼 6 個位置，加人工復原臨時手寫 3 組；若只算可重跑腳本則是 **6 次**。Armstrong persona 報 **1 份實作**，正式現場 prepare 48 次、helper commit 47 次，rename 前被殺的 1 次另由人手動 `mv`；成功基線 11 次發布，其中 3 次是 delivery。Cantrill persona 報 **1 份實作**、4 個靜態呼叫點、happy path commit 6 次，事故後另人工補 1 次 rename。Thompson persona 報 **1 份實作**，正常閉環呼叫兩次、故障注入再呼叫一次。這個數字目前有兩種計數口徑：Carmack persona 主要數發布位置／人工交易，其餘三位主要數共用實作份數；各自的呼叫或 commit 次數已一併保留，尚未換算成同一口徑。

**② 哪種「不知道做了沒」本機補不回來。** 四位都報 **1 類**：provider 可能已接受非冪等 request，但 receipt／response／result 尚未在本機提交。Carmack、Thompson persona 都做出本機現場相同而 provider ledger 不同的 accepted／dropped 對照；Armstrong persona 實際盲重試後 ledger 從 1 變 2；Cantrill persona 在 model 與 tool 兩個位置各撞到一次，都是靠 provider query 才補回。這一項四路答案相同，且回報中同時有 snapshot／diff、外部 ledger 與盲重試紀錄。

**③ 有沒有冒出第二個要同時管的工作。** 四位都報 **0 個**。四路都是一個 world、一條 logical job、串行 instruction，沒有 parallel、lane、join、scheduler 或第二個耐久工作；子行程、假 provider process、不同事故 world 都沒有被計作第二個 logical job。回報中沒有建立並行 workload，也沒有測多 producer。

因此目前收到的原始數字是：第一項按「實作份數」為 p1 **6**、p2 **1**、p3 **1**、p4 **1**，但 p1 另以包含人工復原的「交易／位置」口徑報 **9**；第二項四位都是 **1**；第三項四位都是 **0**。這裡只保留各自的口徑與證據，不替不同口徑裁定。

## 5. 仍然不知道的

第一個數字還沒有統一計數單位。「手寫了幾次」究竟數 source 中獨立實作份數、靜態呼叫點、happy-path commit、正式現場所有 commit，還是包含事故後人工 `mv`，四份回報採了不同口徑；因此目前不能只拿 `6／1／1／1` 或 `9／1／1／1` 脫離說明比較。

本輪不知道 power loss 下檔案內容與 directory entry 是否耐久，也不知道跨 filesystem rename、兩個 producer 同時投遞、名稱碰撞、覆蓋競爭、no-replace 與 crash 後重入會發生什麼。Thompson persona 下一輪才預定攻擊雙 producer；其餘路線也沒有建立第二個長壽 world、平行 tool 或 join。

本輪不知道真實 provider 是否提供 query 或 idempotency key。Cantrill persona 的兩次恢復依賴可 query 的假 provider；Carmack、Armstrong、Thompson persona 的不可對帳對照則刻意沒有這些能力。對無 query provider，這輪只記到本機無法分辨 accepted／dropped，以及盲重試可能重複，沒有做出自動恢復。

本輪沒有試真模型 CLI，也沒有網路；四路都用假模型。Armstrong persona 的 SIGINT 是 `timeout --preserve-status -s INT` 對 parent 注入，沒有驗證所有終端前景 process group 行為；Cantrill persona 雖由 PTY 送 `^C`，wrapper 也一起終止，沒有留下獨立的 `aos` 退出碼。

最後，本輪只記到三種 scope 對應的現場數字與各 persona 後續主張；近期 core 應回撤到哪一種大小，尚未在這份書記紀錄中裁定。
