# modules：核心以外的功能

← [proto7-2](../README.md)｜[核心 spec](../spec.md)（第 9 節：擴充點）｜方案：[核心精簡](../notes/core-slimming.md)第 5、6 節

**新功能預設進這裡，不進核心**（[設計原則](../../proto7/notes/principles.md)第 7 條；進核心的三問見 [README「防再胖」](../README.md#防再胖新功能預設進模組)）。模組只從檔案協定接進來，核心不呼叫它們、不知道它們的語意；模組失敗頂多是一個任務失敗。

接法：**A 任務**（tick 起，收 tock、讀「上一次」檔、寫 tasks.json、ctl）、**B argv 包裝程式**（tasks.json 項目的 argv 前面加它）、**C 工具**（人、LLM、kernel 跑的命令列或函式庫）。核心給的三個小出口：tasks.json 的 `x` 照抄進 birth.json、事實欄位（`never_started`）與事件出口 `log.on`、通用守門檔 `stop-guard.json`。

| 包 | 做什麼 | 接法 | 預設 | 依賴 | 入口 |
|---|---|---|---|---|---|
| [tools](tools/README.md) 工具包 | `aos7-ctl`（寫控制檔、加任務）、`aos7-wait-tock`、任務端函式（task_env、wait_tock、resolver、request、read_jsonl） | C | 開 | 控制包（restart） | `bin/aos7-ctl`、`bin/aos7-wait-tock`、`tools/aos7_ctl.py`、`tools/aos7_taskside.py` |
| [control](control/README.md) 控制包 | restart／reload 在請求端做：先加釘同槽的 once，再寫 kill 帶 run | C | 開（隨工具包） | 核心 kill、once 的 `slot`、`x` | `control/aos7_control.py` |
| [subd](subd/README.md) 子 daemon 包 | 一個 node 的任務擁有子空間根：位置檢查、守門檔、owner、stopped.json；重開前回收前代（`subd-life.json`） | B | 關 | 核心守門檔 | `subd/aos7-subd` |
| [once_retry](once_retry/README.md) once 保證包 | 從沒起來過就 lost 的 once 加回（至少一次） | A | 關 | 事實欄 `never_started`、`x` | `once_retry/retry_lost.py` |
| [audit](audit/README.md) 稽核包 | Python 任務的寫入紀錄（只記不擋） | B | 關 | 無 | `audit/aos7-audit` |
| [diag](diag/README.md) 診斷包 | 唯讀重算判不出的槽、對到恢復步驟；操作手冊 | C | 開（工具） | 核心的判定函式（只讀） | `diag/aos7-diag` |
| [events](events/README.md) 事件保存包 | 每 node 一個 events/ 固定檔數保存事件：取樣核心觀測＋合作來源逐件發布，垃圾由寫者清 | A＋C | 關 | 工具包任務端函式、核心 aos7_fs | `events/aos7-events`（子命令 read／pub） |
| [routines](routines/README.md) 事務包 | 兩張表的例行／一次性到期事務，由 tick 喚醒、最多一次 | A＋C | 關 | 工具包任務端函式、核心 aos7_fs／aos_exec | `routines/aos7-routines`（add／ls／rm） |
| [skills](skills/README.md) skill 包 | node 的 `skills/<名>/SKILL.md`：產索引行（只 name＋description）與必用表、經 llmcall 讓 AI 挑一本、掛載給任務 | C | 開（工具） | llmcall、budget、核心 aos7_fs | `skills/aos7-skills`（子命令 index／pick／mount） |
| [wfnode](wfnode/README.md) node 工作流包 | 給 node 裝 workflows 工作流樹（填事實、不瞎猜）、記續行點、體檢 open 衛生；三個指令 init／state／check | C | 開（工具） | `~/repo/workflows`（`AOS7_WF_HOME`） | `wfnode/aos7-wfnode` |
| [metrics](metrics/README.md) 效率量測包 | 唯讀掃證據算四指標（每單 token、並行呼叫數、收單→結案秒數、重試次數），可重跑 | C | 開（工具） | 無（只讀別包的檔） | `metrics/aos7-metrics`（job） |
| `history.py` 歷史 module | 每個 tock 把「上一次」追加到自己的地方（見下） | A | 關 | 工具包的任務端函式 | `history.py` |
| `counter.py` 示範任務 | 讀同槽上一次的 state、收 tock.json | A | — | 工具包的任務端函式 | `counter.py` |

`history.py`、`counter.py` 是**觀測任務包（kernel 層）的雛形**，這輪不動；它們的測試在 `tests/`。每個包的測試在 `<包>/tests/`，全套用 `python3 proto7-2/tests/run_all.py` 一起跑。

**包的格式**：一個資料夾，有 `README.md`（做什麼、接法、預設、依賴、**契約卡**（職責／前置條件／保證／明確不管，核心卡在[組件契約](../notes/component-contracts.md)）、規則、界線、測試位置）、程式、`tests/`。可執行的包裝程式／工具放包的根目錄（`bin/` 會被 gitignore）。安裝工具 `aos7-pack`（方案第 10 節）尚未實作；上層任務包另放在 `packs/`，目前已有 step、budget、adapt，入口見[專案 README](../README.md) 的結構表。

## 歷史 module（從核心 spec 搬來）

核心只留上一次。要更前面的歷史，用一個**普通的 keep 任務**：

- 每收到一次 tock，讀要記的「上一次」檔（自己 node、或經掛載的別的 node 的 `.aos/last-round.json`，daemon 的 `.aosd/status.json`），追加到它自己的地方（例如 `<node>/history/<id>.jsonl`）；輪替、留多少是它自己的設定（參考實作的 `--max-lines` 同時套在 node 歷史與事件歷史）。收到自己 node 的 tock 時，那一回合的 last-round.json 已經提交（核心 spec 第 7 節）。
- 它是任務，合 S-10（tick 起、只碰給的資料夾），核心完全不知道它存在。
- **代價**：它是取樣的。它慢了、被 pause、或一回合內就跑完兩回合，中間的就看不到；它看得出缺號並記一行 `gap`，但補不回來。它起來之前的回合也記不到，所以「沒有 gap」不等於全歷史完整。
- **已知限制（未修）**：參考實作的檔名是編碼後的 node id 加 `.jsonl`，編碼後超過約 249 bytes（一般檔案系統單一檔名上限 255 bytes；開 `--max-lines` 時暫存檔名再多 5 bytes，約 244）就寫不出來，追加丟例外、整個歷史任務退出（keep 再起又退），同一個任務的其他來源也跟著記不到；很長的 node id 先縮短，或改用自己的命名。
- **daemon 事件**：任務只能從 status 的 `last_event` 取樣，可能漏。要完整的流水帳，放一個空檔 `<root>/.aosd/log.on`（核心的事件出口），daemon 就把事件追加到 `.aosd/log.jsonl`，不清、不輪替，開的人自己管大小（例如讓歷史 module 定期截斷）。
- 不選「核心提供每回合鉤子」：鉤子要在 tock 裡同步呼叫外部程式，失敗、逾時、它自己的歷史都會變成核心的邊緣狀況。
