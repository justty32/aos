# 第 1 輪紀錄 — 好處／壞處

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/pros-cons.md)

書記對上面那批坑的正反兩面整理：這一輪什麼有效、什麼還是不行。

## 3. 好處／壞處

### 好處

四條路的正常基線都用現成 `aos` 完成三回合，第三回合確實讀到第二回合的工具結果；每回合都是短命 process，狀態留在 world，不需要常駐 driver、daemon 或 session。四路都以 allowlist 或固定檢查把模型輸出限制成具名工具，沒有直接把任意 argv 交給 `aos`。

四路也都看到 temp／ready 邊界會隔離 rename 前的檔案：未完成 rename 的 `.temp` 不會被當成 ready instruction 執行。`.runi` 的保守拒絕會留下事故現場，也阻止另一個 executor 直接靜默重播整批。Armstrong、Cantrill persona 另留下 per-instruction exit，能看出 137、66 與後續 schedule 是否執行；各個 request、attempt、result、batch、final 都可直接從檔案檢查。

Armstrong、Cantrill persona 分別用一支共用 publish helper 服務多種本機提交，沒有為每個輸出各寫一套 temp＋rename。Thompson persona 則實際跑過不使用 `aos` 的三行 shell 對照，留下相同因果鏈可以由更小機制完成的現場。

### 壞處

事故後的恢復都落到人工檔案操作：判讀 `.runi` 內各 instruction 的進度、檢查 result／exit／provider 證據、搬走法醫 batch、手動提升完整 `.temp`，或重造只含剩餘工作的 instruction。沒有 instruction-level program counter 可直接續跑；選擇 replay 或 abandon 時，本機資料又不能替人判定外部 effect 的真相。

`aos exec` 的回合退出碼與 agent loop 是否還能前進不是同一件事。至少三路出現回 0、queue 卻空了或下一輪沒有排出的現場；若沒有另外掃 instruction exit、temp 與 final，會停在 no-op 0。只中止 parent 時，另有三路看到 child 繼續完成 effect，但 exit 永遠沒有回寫。

私有 publish／deliver helper 都還有限制：沒有 fsync、directory fsync、no-replace rename、durable key ledger 或跨 producer 去重；部分 helper 遇到既有 target／temp 會拒絕，恢復前仍要人保存或搬移證據。Cantrill persona 還實際遇到檔名格式錯誤被安靜忽略。四路使用的 provider 都是本機假 provider；有 query 的事故可由外部補回，沒有 query／idempotency 的事故則只能保留 unknown 或由人決定下一步。
