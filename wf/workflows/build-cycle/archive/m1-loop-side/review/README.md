# M1 審查（三鏡頭＋對抗驗證，2026-08-28）

← [M1 plan](../plan.md)｜[spec](../spec.md)

- [report.md](report.md)：28 條發現（27 CONFIRMED、1 PLAUSIBLE；高 5／中 12／低 11）＋文件落差＋對抗驗證清單＋未覆蓋角落＋三件需裁決事項。
- `scripts/`：審查隊的攻擊腳本原樣留存（路徑寫死在 `env.sh`，要重跑先改）。回歸測試優先序：`t3.sh`（#1）、`v11.sh`（#25/#26/#27/#21）、`v7.sh`（#3）、`v8.sh`（#4）——確定性、不需併發，適合直接改成 ctest 案例。

**調度者裁決（2026-08-28，實作層級）**：三件需裁決事項全部採 report §5 的建議——#1 header 加 sweep 標記（清完投遞後標記、只有未 swept 才啟用去重）；#2/#5 §D-5 耐久性射程延伸到取件與釋放；#23 aggregate 批發布改排他（每行程唯一 `.temp` 名＋ `publish_exclusive()`）。修補尚未開始，見 [SESSION-LOG](../../../../SESSION-LOG.md)。
