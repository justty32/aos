# agent 定義夾裡的 .py 收進 py/ 子夾、重新規劃架構（使用者 11-20 晚，逐字）：只記錄，之後再做

← [2026-11-20](README.md)

## 使用者原話（家機，瀏覽剛重建的 `~/aos-home` 時）

「我現在正在瀏覽~/aos-home底下的一些東西。有些問題和我覺得之後該改進的點：~/aos-home/agents/ann裏面，那些.py，每個都好幾百行，一大堆注解，他們是怎麽來的？是否可以收縮成ann/py/...，然後重新規劃架構，讓以後比較好維護？這個先記下來。」

## 決定

- 先記下來；沒派線、沒改程式。

## 現況（頂層當場查的，回答「他們是怎麽來的」）

- `~/aos-home/agents/ann/` 是 `templates/start-api/agents/ann/` 的抄本，那份又是 `templates/agent-fsm/` 的逐字抄本（`cp -r` 起手範本時整夾帶過來）。
- 夾裡 8 支 .py 共 1825 行：`wait.py` 644、`idle.py` 330、`compact.py` 260、`brain.py` 258、`act.py` 233、`llm_settings.py` 45、`cell_common.py` 40、`atomic_file.py` 15。前五支是狀態機的格程式（`fsm.json` 每一格跑一支）與 compact；後三支是它們共用的小模組。
- 這些 .py 跟 `system.txt`、`tools.json`、`llm.json`、`fsm.json`、`hooks.json` 等設定檔平放在同一層。
- 註解多半是檔頭那一大段（結束碼、信怎麼收、引哪條規範與哪份 thinking）。

## 註（記錄者加，不是使用者的話）

- 格程式的路徑寫在 `fsm.json`；搬進子夾要跟著改 `fsm.json`、範本的抄本比對測試（`templates/tests/`）與編譯程式庫（`defs.Agent` 的 fsm 那一欄）。
- 「重新規劃架構」規劃到哪一層（只搬位置／拆檔瘦身／格程式收回 `lib/` 讓定義夾不帶程式）他沒說，沒問。
