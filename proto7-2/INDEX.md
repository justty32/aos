# proto7-2 INDEX — 資料夾結構與來源

← [proto7-2 README](README.md)（從 README 拆出的「結構」「來源」兩節，內容原樣）

## 結構

| 位置 | 是什麼 |
|---|---|
| `spec.md` | 核心 spec（只放規則） |
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`（後兩個的本體在工具包），與搬來的 `aos-exec` |
| **核心** `lib/aos7_*.py` | 受行數預算管（見 [README「防再胖」](README.md#防再胖新功能預設進模組)），共九檔： |
| `lib/aos7_daemon.py`、`aos7_daemon_timeline.py` | daemon：登記（寫檔成功才生效）、控制檔、node 消失、status；回收意圖落 nodes.json `reaping`、確認收乾淨才開新時間線、paused.json 存 rounds 倒數 `steps` 與待結算 `owe`（開回合前記、關回合後扣倒數同次清）；reaping 未確認乾淨時重起 status 保留 missing；每個 node 一條時間線（`read_config` 不丟例外、壞值記錯用預設，`owe_round` 補扣）（spec 第 1、2 節） |
| `lib/aos7_tick.py`、`aos7_tock.py` | 開回合（tasks.json、once 的 launch 標記；帶 launch 的 once 先比對槽的 run 再看排程）／關回合（last-round.json、刪槽）（第 3、4、7 節） |
| `lib/aos7_task.py` | 槽、三態判定、lost 前的身分掃描、kill（runner 還在啟動交接＝回 unknown、請求留著）；起任務的環境只帶核心六個 `AOS7_*`（第 5、6 節） |
| `lib/aos7_proc.py` | 程序的事實（`proc`：不在／starttime／不知道）、同一個程序嗎、身分掃描、Q1 範圍的收程序（清場後身分複查最多補收 3 輪；node 級打記著的 pgid 前 `group_is_node` 重驗） |
| `lib/aos7_run.py` | 任務的包裝：pid.json、exit.json（帶 run；run 先取環境 `AOS7_RUN`，birth 讀到再以它為準） |
| `lib/aos7_fs.py` | 錯誤四分支的入口（讀檔 `fact`、紀錄 `hold`、例外 `Unknown`）、原子寫、flock、動作鎖與世代、測試鉤子的轉接（`AOS7_TEST_HOOKS` 有設才載入 `tests/_hooks.py`；`write_json` 有 `inject("write")`） |
| `lib/aos7_mount.py` | 掛載（4.5）：tick 建掛載、審核執行中加掛（連結已建、birth 未記時被殺可冪等恢復） |
| `lib/aos_*.py` | 搬來的 inst 執行器（不算核心預算） |
| **模組** `modules/` | [總覽](modules/README.md)；每包一個資料夾，自帶 README 與 `tests/` |
| `modules/tools/` | [工具包](modules/tools/README.md)：`aos7-ctl`、`aos7-wait-tock`、任務端函式 |
| `modules/control/` | [控制包](modules/control/README.md)：restart／reload 在請求端做 |
| `modules/subd/` | [子 daemon 包](modules/subd/README.md)：包裝程式 `aos7-subd`（替子根設 `AOS7_AUDIT_ALLOW`） |
| `modules/once_retry/` | [once 保證包](modules/once_retry/README.md)：`retry_lost.py`（keep 任務；加回前持表鎖重讀 birth，契約是至少一次） |
| `modules/audit/` | [稽核包](modules/audit/README.md)：包裝程式 `aos7-audit`，可選的寫入紀錄；`AOS7_AUDIT_ALLOW` 豁免 node 內巢狀邊界（subd 設） |
| `modules/diag/` | [診斷包](modules/diag/README.md)：唯讀工具 `aos7-diag`＋會停下等人的情況與恢復步驟 |
| `modules/events/` | [事件保存包](modules/events/README.md)：每 node 一個 `events/`，觀測／必讀兩通道各 1 活躍段＋≤4 封存（上限 12 檔）；`aos7_events_store.py` 保存端、`aos7_events_pub.py` 發布、`aos7_events_read.py` 讀者、`aos7-events` 取樣器（子命令 read／pub；status 去重鍵與截半行記號存 state.json `status_last`／`torn_cut`）；[spec](modules/events/spec.md)＋[取樣器 spec](modules/events/spec-sampler.md)、`examples/`（demo_pub、真 daemon 300 回合 longrun） |
| `modules/counter.py`、`history.py` | 最小示範任務、歷史 module 的參考實作（觀測任務包的雛形；來源檔名可逆編碼 `hist_name`；升級時含 `+`／`%` 的舊檔與 `daemon-events.jsonl` 一次封存成 `.v1`，夾內放 `.names-v2`） |
| **上層任務包** `packs/` | kernel 的任務包（工作語意；通用／agent／LLM 分層，原則 8）；每包一個資料夾，自帶 README（契約卡）、spec、`tests/` |
| `packs/step/` | [step 包](packs/step/README.md)：步驟表直譯器 `aos7-step`＋槽外結果檔＋檢查器（run 步 `unknown_codes`、重送額度記框架 `resends`、啟動清死暫存檔） |
| `packs/budget/` | [budget 包](packs/budget/README.md)：grant／帳／入口（預留→執行→結算），示範資源＝假 API 受理次數；原名 account，為避免跟 Linux account 重疊改名；退出碼 0／1／2／3、單位＝加權成本、帳任務起時清 `gateway/` 死暫存檔；部分結算（settle 收 0≤used≤預留、usage 缺留 pending、超出記 overrun，blueprint-llm2 §4） |
| `packs/llmcall/` | [llmcall 包](packs/llmcall/README.md)：LLM 單次呼叫閘道（假傳輸＋真傳輸 llm.litellm），固定請求→預留→intent→raw→done→結算→回條；本地證據恢復、遲到 adopt、軟 token 帳；退出碼 0～4 |
| `packs/adapt/` | [adapt 包](packs/adapt/README.md)：鄰居 node 的最新值轉接（固定版本、確定性鏈、依據 basis＋出處 src、三態暫存器），示範溫度感測→風扇 |
| `packs/author/` | [author 包](packs/author/README.md)：LLM 作者第一刀（假候選）——需求＋候選經三層驗證、確定性編譯成獨立版本 step 工作，意圖→表鎖內合併自己那一項→回條；`close` 後每需求只留 request＋receipt；`send`／`intake` 經事件必讀通道收單（游標與收件回條在 `author/events.json`，回條寫成後才 ack）；退出碼 0／2／3／4／5；第二刀 `aos7_author_llm.py` 接 `propose --llm` 經 llmcall 真傳輸，`examples/llm-request/` 收一整圈證據 |
| `tests/` | 核心測試 `tests/core/`、共用工具、`run_all.py`；測試導引見 [tests/README.md](tests/README.md) |
| `notes/` | problems.md、core-slimming.md、component-contracts.md、layer-interfaces/、changes-from-7-1.md、play/ |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：**原樣複製自 proto7-1**（10-04；proto7-1 當初從 proto6 複製）。
- `lib/aos7_fs.py`、`aos7_run.py`、`aos7_mount.py`、`modules/tools/aos7_ctl.py`、`modules/audit/aos7_audit.py`、`modules/audit/audit_site/`、`tests/_proc.py`：從 proto7-1 複製後改寫（`aos7_audit.py`、`audit_site/`、`_proc.py`、`aos7_mount.py` 幾乎沒改）。
- `lib/aos7_daemon*.py`、`aos7_tick.py`、`aos7_tock.py`、`aos7_task.py`、`aos7_proc.py`：照 proto7-1 同名檔的結構重寫（程序工具從 proto7-1 `aos7_task.py` 拆出來）。
