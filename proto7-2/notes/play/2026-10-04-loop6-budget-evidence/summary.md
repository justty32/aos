# loop6 B 線（budget）驗收證據

← [loop6 藍圖](../../blueprint-loop6.md) §1 A6-02、§2、§4 B 線｜[astra-5 報告](../2026-10-04-astra-5-infra.md)｜[budget spec](../../../packs/budget/spec.md)

**A6-02 已修：後端 EIO 與真 EACCES 都回 rc 3、一行 JSON、無 traceback，intent／預留留著，恢復後同 K 只有一次效果。astra-5 的 50 案探針重跑 50／50 通過（原本記為 B 的 2 案改照契約判），時鐘整合 8／8；獨立核帳 119 份快照、326 筆轉移全過，5 個負對照全抓紅。** 核心零改動（`git diff proto7-2/lib/` 為空）；沒有用 LLM。

## 改了什麼（只在 `packs/budget/`、`packs/step/`）

| 項 | 做法 |
|---|---|
| A6-02 共同故障邊界 | `gate.run` 第 4 點 `except (Unknown, LedgerDown)` → 非終局 `{"outcome":"unknown","stage":"intent"}`；`call`／`cancel`／`settle` 入口經 `io_boundary` 把 `Unknown`／`LedgerDown`／`OSError` 轉成 `pending` rc 3；`cancel` 拿到非終局也回 3（原本 1）。不重試、不動帳 |
| 缺口 1 取消前置 | spec §4 加「cancel 的前置條件」段；README gateway 卡「明確不管」補齊。不改程式 |
| 缺口 2 時鐘 | 帳每處理一件請求就讀 c，合法且大於 `clock_hw` 就推高（含拒絕、重播；單獨一次寫入，只動這一欄）；spec §2 與 README grant 卡前置條件寫「重建 round.json＝換預算識別、不移植 grant」 |
| 缺口 3 儲存 | (a) 帳任務起時與每次本 node 回合變了掃 `receipts/`：K 已結算、`inbox/` 無同名、第一次掃到後又完成 3 回合（`ORPHAN_ROUNDS`）仍在才刪；(b) spec §10「保存與退役」：成長率、保存契約、五步退役；`retired.json` 在＝帳不收新 K（舊 K 照重播），讀不到＝unknown |
| 缺口 4 holder | README 接法加一句：部署者寫死在 steps.json argv、合作式 |
| 缺口 5 重送上限 | step `run` 步欄 `max_resends`（非負整數，預設 1＝現狀；檢查器驗型別）；step spec §2、§5 第 6 點各一句；兩包 README 各一句 |
| spec §9 | 已知界線五條，一條一行 |

測試：budget 32 → 37（+5：EIO、EACCES、hw 推高、孤兒掃＋重播一致、退役拒收）；step 24 → 26（+2：`max_resends` 型別、`max_resends: 2` 真跑兩次重派後才停）。全套從 repo 根 `python3 proto7-2/tests/run_all.py`：335／335 綠（152.5 秒；含同時在做的 A 線 subd 測試）。

## 探針

| 批 | 腳本 | 結果 | 備註 |
|---|---|---|---|
| astra-5 主批 | [budget-crash/run_probes.py](budget-crash/run_probes.py)（原樣複製） | 41／41，合計 10.489 秒 | `eio-backend.json` 現在 rc 3、`unknown_exit_contract: true`、stderr 無 traceback；其餘 40 案行為不變 |
| astra-5 補充 | [budget-crash/run_extra.py](budget-crash/run_extra.py) | 9／9，1.638 秒 | 唯一改動：`eacces-backend` 原本斷言 B 的樣子（rc 1、無 JSON、PermissionError traceback），改成契約（rc 3、一行 unknown、無 traceback）；改處有註解 |
| loop6 新增 | [budget-crash/run_loop6.py](budget-crash/run_loop6.py) | 6／6，2.876 秒 | 後端 EIO 下 call→cancel→settle→call 全 rc 3，重複 3 次；`clock_hw` 5→10（denied）→12（重播）→退鐘到 6 仍 12、新 K unknown；孤兒回條 c=6～8 留著、c=9 被掃、在途 K 的留著、重播回條除 `at` 外一致；退役：新 K denied、舊 K 重播 0 |
| astra-5 時鐘／step 整合 | [budget-integration/run_probes.py](budget-integration/run_probes.py)（原樣複製） | 自製 6 案＋step／daemon 8／8，9.77 秒 | 兩個 M 觀察 `clock_highwater_after_expired`／`_after_gateway` 現在 `rollback_detected: true`（原本 false）：水位在拒絕與首次准入後的結算都推高了 |

結果檔：各批的 `results.json`、`snapshots.json`、`cleanup.json`、`cleanup-ps.txt`（crash 三批在 `budget-crash/{verified,extra,loop6}/`），執行輸出在 `budget-crash/*-run.log`、`budget-integration/step-unittest.log`。

## 獨立核帳

astra-5 的 [audit.py](budget-integration/audit.py) 原樣複製（只用標準函式庫、不 import budget）。[audit_crash_snapshots.py](budget-integration/audit_crash_snapshots.py) 只加一批 `loop6`。

| 範圍 | 快照 | 轉移 | 結果 |
|---|---|---|---|
| crash verified＋extra＋loop6 | 72＋16＋10＝98 | 277 | 98／98（[crash-audits.json](budget-integration/crash-audits.json)） |
| 整合線（跑的時候逐份核） | 21 | 49 | 21／21（`results.json` 的 `audits`） |
| 負對照（受理計數、log 餘額、重複 reserve、結算雜湊、缺 ops） | 5 | — | 5／5 抓紅（[negative-controls.json](budget-integration/negative-controls.json)） |

## 快照與重跑

四個 `snapshots/` 已就地打包成 `snapshots.tar.gz`（`budget-crash/verified/`、`budget-crash/extra/`、`budget-crash/loop6/`、`budget-integration/`），在該層 `tar -xzf snapshots.tar.gz` 展開；核帳要先展開 crash 三批再跑 `audit_crash_snapshots.py`。

```sh
QA_OUTPUT=/tmp/新名字 python3 proto7-2/notes/play/2026-10-04-loop6-budget-evidence/budget-crash/run_probes.py
QA_OUTPUT=/tmp/新名字 python3 proto7-2/notes/play/2026-10-04-loop6-budget-evidence/budget-crash/run_extra.py
QA_OUTPUT=/tmp/新名字 python3 proto7-2/notes/play/2026-10-04-loop6-budget-evidence/budget-crash/run_loop6.py
python3 proto7-2/notes/play/2026-10-04-loop6-budget-evidence/budget-integration/run_probes.py
```

## 跟藍圖不同處

- 共同故障邊界除了 `Unknown` 也接 `LedgerDown` 與 `OSError`（例如入口紀錄寫不進去），都是「不知道」；程式錯（KeyError 等）照樣 traceback。
- `cancel` 拿到非終局（入口或後端讀不到）原本退出 1，現在 3，跟 call 一致；spec §6 寫明 0／1／3。
- 孤兒回條「每輪」解成「本 node 回合變了才掃」，並加 3 回合寬限（活著的呼叫者每 20ms 輪詢，早讀走了）；萬一刪到還在等的呼叫者，它只會等滿耐性回 3，重播回條相同、不動帳。pause 時不走。
- 做了退役拒收（藍圖寫「若做」）：`retired.json` 只擋新 K，已有 K 照重播。
- `clock_hw` 推高是在帳處理每件請求時讀 c，不在沒有請求時空轉寫帳。

## 清理

各批 `cleanup.json`：`all_waited: true`、`remaining_mentions: []`、測試根已刪（crash 三批共追蹤 475＋49＋44 個子程序）；整合線 [own-cleanup.json](budget-integration/own-cleanup.json) `all_reaped: true`，8 個 step／daemon 案的 `/tmp/aos72-test-*` 都已刪、`live_pids` 皆空。沒有動 scratchpad。
