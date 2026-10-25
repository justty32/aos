# 第 1 輪紀錄 — 好處／壞處

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/pros-cons.md)

## 3. 好處／壞處

### 好處

- 現成 `aos` 能跑完三回合，第三回合讀得到第二回合的工具結果；每回合是短命 process、狀態留在 world，不需要常駐 driver、daemon 或 session。
- 以 allowlist 或固定檢查把模型輸出限制成具名工具，不直接把任意 argv 交給 `aos`。
- temp／ready 邊界隔離 rename 前的檔案；`.runi` 的保守拒絕留下事故現場，也阻止另一個 executor 靜默重播整批。per-instruction exit 能看出 137、66 與後續是否執行；request、attempt、result、batch、final 都可直接從檔案檢查。
- 一支共用 publish helper 就能服務多種本機提交。

### 壞處

- 事故後的恢復都落到人工檔案操作：判讀 `.runi` 內進度、檢查 result／exit／provider 證據、搬走法醫 batch、手動提升 `.temp`、重造只含剩餘工作的 instruction。沒有 instruction-level program counter；replay 或 abandon 時，本機資料不能判定外部 effect 的真相。
- `aos exec` 的退出碼與 agent loop 是否還能前進不是同一件事；只中止 parent 時 child 可能繼續完成 effect，exit 永遠沒回寫。
- 簡單的 publish／deliver helper 沒有 fsync、directory fsync、no-replace rename、durable key ledger 或跨 producer 去重；錯檔名會被安靜忽略。沒有 query／idempotency 的 provider 事故只能保留 unknown 或由人決定。
