# loop6 A6-01 修補驗收（subd 合法 stop 的提交中斷後重開錯收）

← [play](../README.md)｜[astra-5 A6-01](../2026-10-04-astra-5-infra.md)｜[loop6 藍圖](../../blueprint-loop6.md) §1、§4 A 線

修補 commit 95426b17（只動 `modules/subd/`，核心零改動）。探針跑在修補後的工作樹（HEAD 68b6a2c7＋未提交 subd 修補）。

| 項目 | 結果 |
|---|---|
| subd 測試 | 21／21（原 15＋新 6：三窗口、status 讀不到、父 kill 反例兩條）；拿掉 since 過濾時「舊回條＋父 kill」轉紅 |
| `stop/confirm_stop.py` 藍圖流程 | stop-seen、stopped-tmp、life-tmp 各 3／3：中斷時 life=running；重開 rc 1、stopped.json 出現、life 補成 stopped、任務不動；刪掉再起同 PID＋starttime 接回、槽 run=1。normal 3／3 |
| 同上 astra-5 原流程（先刪 stopped.json） | 三窗口各 3／3 保留、無 run 2（life-tmp 多擋一次）；normal 3／3 |
| G3 壓力 `stress/run_stress.py`（逐位元組複製），與全套第 1 次並行 | 10／10；每案都有前代留下，替代 daemon 2.24～2.28 秒出現時已全收 |
| 全套 | 第 1 次 335／335（與 G3 並行）；第 2 次 363 中 3 failures，都在 adapt（C 線進行中）；第 3 次 363／363 |
| 清場 | final_proc_remaining 皆空、/tmp 測試根已刪 |

跟藍圖不同處：測試 +6；收尾不再看 got_term（直接 TERM 子 daemon 不算被允許的 stop，改回收再起）；人在任何一次被擋前就刪 stopped.json 會多擋一次，任務不收；沒有 since 的舊記錄照舊回收；時間比較用 `now()` 牆鐘字串（原則 9，不另防）。
