# 證據濃縮：fast-tests 與 deep-play

[README](README.md)｜原證據在 scratchpad（`.../scratchpad/burn/ws/{fast-tests,deep-play}/evidence/`），不進 repo。

## fast-tests

**patch 未保留於 repo**；要重做請照 [fast-tests.md](fast-tests.md)（只動測試與 README，不動產品程式）。

| 組別（364 項、8 CPU） | 輪數 | 中位數秒 | 結果 |
|---|---:|---:|---|
| 改前（串行，含共同穩定性修補） | 3 | 190.19 | 364/364 |
| 改後（4 worker＋耗時排序） | 3 | 65.19 | 364/364 |
| 改後一般重跑 | 10 | 61.56 | 364/364 |
| 改後限 2 CPU | 3 | 82.30 | 364/364 |

省 125 秒（65.7%、2.92 倍）；前後交錯量測，最終 19 輪全過。

**原樣複本不是全綠**：未改的複本跑三次都是 359/364（456.95／220.47／207.79 秒），失敗皆時序敏感案例（ctl 舊 run 殘留、matrix_once launch crash、subd_recover parent kill），故比較基準要先套同一份穩定性修補。

改了 17 個檔（皆測試或 README）：README；subd 的 test_subd_ownership、test_subd_recover；adapt 的 test_adapt_flow；budget 的 budgetcase、test_budget_ledger、test_budget_step；step 的 test_step；tests/ 下的 _matrix、_parallel、_parallel_worker、_test_report、run_all；tests/core 的 test_ctl、test_matrix_faults、test_matrix_once、test_tick_tock。

三種加速手法：
1. 平行：每個測試檔一個程序、`run_all.py -j 4`，依歷史耗時先排慢檔（`-j` 預設 1）。主要收益，串行 187 秒降到 72 秒。
2. 條件等待取代固定 sleep：八處，合計約省 2.5 秒。
3. fixture 快取：budget 測試共用真 CLI 產的開帳範本，init 49 次降到 9 次（`AOS7_TEST_FIXTURE_CACHE=0` 停用）。

2、3 不能加進 125 秒。瓶頸是 test_subd_recover（單檔約 58 秒）。

穩定性修補（兩組共用）：shell fixture 用 `exec sleep`；恢復測試等 runner 真死才判；subd 的 run 改驗「新大於舊」；adapt fast-source 先確認來源真發布兩個新版本；subd 讀日誌等非空；orphan `/proc` 案例先等 runner 死再掃。六個原失敗案例單獨重跑，原版 11/18 失敗、修正版 18/18 過。僅在這台 WSL2 測過。

## deep-play

**C8-01 取消登記後 daemon 被殺，回收義務遺失〔B／高〕**
1. 一個 node、一個忽略 SIGTERM 但身分正常的 keep 任務；daemon 起來、任務 running。
2. 送 `unregister`（`kill:true`），等成功回條。
3. 一秒 TERM 寬限內 `SIGKILL` daemon，用同根起新 daemon。
4. 舊任務（PID、starttime 不變）仍活；重送 unregister 回「沒有登記」；`stop --kill` 也不收。中斷 3/3 漏收，正常對照 0/3。
5. 因：registry 先刪（`lib/aos7_daemon.py:197`），回收只標在記憶體。

**C8-02 node 替換後中斷回收，新舊同活〔B／高〕**
1. 一個 node、一個 keep 任務，等 ready 且 running。
2. 把 node 目錄改名搬走，原址重建新 node 與同樣 tasks.json。
3. 等舊 daemon 對舊任務送 TERM（任務忽略），KILL 寬限內 `SIGKILL` daemon，再起新 daemon。
4. 新 daemon 起新任務，舊任務仍活；30 次取樣全雙活（8.2～9.0 秒）。中斷 3/3，正常 0/3。
5. 因：`reapers`／`missing`／`node_ident` 只在記憶體（`aos7_daemon.py:57,59`）。

兩者同族（回收義務只在記憶體，宜持久化意圖）。另有 C8-03〔G／中〕：任務包槽外 tmp 檔在 writer 被殺後累積。

**壓測（最後檢查點，皆未達門檻）**：全套 364 項在高負載下 357 過、7 失敗（1156 秒）。長跑 20 node，兩階段共約 7832 回合（每 node 中位約 390，目標 2000）。Chaos 約 819 秒（目標一小時），SIGKILL 命中任務 12、daemon 4、tick 9、tock 8。資源：daemon RSS 約 18 MiB，76 程序合計約 1 GiB，殭屍 0。step 中斷 9/9、budget 九持久點×3 為 27/27。
