# proto7-2 INDEX — 資料夾結構與來源

← [proto7-2 README](README.md)（從 README 拆出的「結構」「來源」兩節，內容原樣）

## 結構

| 位置 | 是什麼 |
|---|---|
| `spec.md` | 核心 spec（只放規則） |
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`（後兩個的本體在工具包），與搬來的 `aos-exec` |
| **核心** `lib/aos7_*.py` | 受行數預算管（見 [README「防再胖」](README.md#防再胖新功能預設進模組)），共九檔： |
| `lib/aos7_daemon.py`、`aos7_daemon_timeline.py` | daemon：登記、控制檔、node 消失、status；每個 node 一條時間線（spec 第 1、2 節） |
| `lib/aos7_tick.py`、`aos7_tock.py` | 開回合（tasks.json、once 的 launch 標記）／關回合（last-round.json、刪槽）（第 3、4、7 節） |
| `lib/aos7_task.py` | 槽、三態判定、lost 前的身分掃描、kill（第 5、6 節） |
| `lib/aos7_proc.py` | 程序的事實（`proc`：不在／starttime／不知道）、同一個程序嗎、身分掃描、Q1 範圍的收程序 |
| `lib/aos7_run.py` | 任務的包裝：pid.json、exit.json（帶 run） |
| `lib/aos7_fs.py` | 錯誤四分支的入口（讀檔 `fact`、紀錄 `hold`、例外 `Unknown`）、原子寫、flock、動作鎖與世代、測試鉤子的轉接（`AOS7_TEST_HOOKS` 有設才載入 `tests/_hooks.py`） |
| `lib/aos7_mount.py` | 掛載（4.5）：tick 建掛載、審核執行中加掛 |
| `lib/aos_*.py` | 搬來的 inst 執行器（不算核心預算） |
| **模組** `modules/` | [總覽](modules/README.md)；每包一個資料夾，自帶 README 與 `tests/` |
| `modules/tools/` | [工具包](modules/tools/README.md)：`aos7-ctl`、`aos7-wait-tock`、任務端函式 |
| `modules/control/` | [控制包](modules/control/README.md)：restart／reload 在請求端做 |
| `modules/subd/` | [子 daemon 包](modules/subd/README.md)：包裝程式 `aos7-subd` |
| `modules/once_retry/` | [once 保證包](modules/once_retry/README.md)：`retry_lost.py`（keep 任務） |
| `modules/audit/` | [稽核包](modules/audit/README.md)：包裝程式 `aos7-audit`，可選的寫入紀錄 |
| `modules/diag/` | [診斷包](modules/diag/README.md)：唯讀工具 `aos7-diag`＋會停下等人的情況與恢復步驟 |
| `modules/counter.py`、`history.py` | 最小示範任務、歷史 module 的參考實作（觀測任務包的雛形） |
| **上層任務包** `packs/` | kernel 的任務包（工作語意；通用／agent／LLM 分層，原則 8）；每包一個資料夾，自帶 README（契約卡）、spec、`tests/` |
| `packs/step/` | [step 包](packs/step/README.md)：步驟表直譯器 `aos7-step`＋槽外結果檔＋檢查器 |
| `packs/budget/` | [budget 包](packs/budget/README.md)：grant／帳／入口（預留→執行→結算），示範資源＝假 API 受理次數；原名 account，為避免跟 Linux account 重疊改名 |
| `packs/adapt/` | [adapt 包](packs/adapt/README.md)：鄰居 node 的最新值轉接（固定版本、確定性鏈、依據 basis＋出處 src、三態暫存器），示範溫度感測→風扇 |
| `tests/` | 核心測試 `tests/core/`、共用工具、`run_all.py`；測試導引見 [tests/README.md](tests/README.md) |
| `notes/` | problems.md、core-slimming.md、component-contracts.md、layer-interfaces/、changes-from-7-1.md、play/ |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：**原樣複製自 proto7-1**（10-04；proto7-1 當初從 proto6 複製）。
- `lib/aos7_fs.py`、`aos7_run.py`、`aos7_mount.py`、`modules/tools/aos7_ctl.py`、`modules/audit/aos7_audit.py`、`modules/audit/audit_site/`、`tests/_proc.py`：從 proto7-1 複製後改寫（`aos7_audit.py`、`audit_site/`、`_proc.py`、`aos7_mount.py` 幾乎沒改）。
- `lib/aos7_daemon*.py`、`aos7_tick.py`、`aos7_tock.py`、`aos7_task.py`、`aos7_proc.py`：照 proto7-1 同名檔的結構重寫（程序工具從 proto7-1 `aos7_task.py` 拆出來）。
