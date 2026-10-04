# loop5 A5-01 修補驗收（subd 重開前回收前代）

← [play](../README.md)｜[astra-4 A5-01](../2026-10-04-astra-4-infra.md)｜[loop5 藍圖](../../blueprint-loop5.md)

修補 commit 8c2145c4（只動 `modules/subd/`，核心零改動）。探針 `stress/run_stress.py` 是 astra-4 原檔逐位元組複製。

| 項目 | 結果 |
|---|---|
| G3 壓力（三次全套並行，4＋3＋3 共 10 案，每案 3 個忽略 TERM 的子任務，父帶 run kill） | **10／10 通過**（astra-4 為 0／10）。每案舊子 daemon 死時 3 個原任務仍活（問題照樣觸發）；替代 daemon 約 kill 後 2.25 秒出現時已全收，新代第 1 回合即通過 |
| 延長確認 `confirm_r7` | 追到 gen 2、r7 已關：原任務與 runner（pid＋starttime）都不在，`last-round.alive` 只有新代 `s*#2` |
| 並行全套 | 三次各 322 全綠，無殘留 |
| 代價 | 替代 daemon 晚約 1.1 秒出現（回收的 TERM／1 秒／KILL） |

原始資料：[results.json](stress/results.json)、[confirm_r7.json](stress/confirm_r7.json)、各案 `g3-*.log`。
