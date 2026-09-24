# proto5/notes — 筆記索引

← [proto5 README](../README.md)｜精簡版：[notes-brief/](../notes-brief/README.md)（09-22 那批的 ≤5000 字版＋23 題總表）

任務書副本、astra（codex gpt-6-astra）的調查／審查報告、我的精簡總結、試玩紀錄。按日期排，**新的在下面**。
散檔一律 `日期-主題.md`；同一件事超過三四份就收成 `日期-主題/` 子資料夾，裡面自己有 README。

## 2026-09-21：proto5 開場

| 檔 | 一句 |
|---|---|
| [2026-09-21-exec-task.md](2026-09-21-exec-task.md) | 任務書：proto5 第一支程式 aos-exec |
| [2026-09-21-inst-rev-rules.md](2026-09-21-inst-rev-rules.md) | inst.json posix v1＋指示詞：使用者逐輪拍板的修訂（A～L 節，任務書副本） |
| [2026-09-21-llm-ask-task.md](2026-09-21-llm-ask-task.md) | 任務書：aos-llm-ask 實作（程式 09-24 已移除，換成 `aos-llm call`） |

## 2026-09-22：四份調查、23 題拍板、回流

四個題目各有「任務書（有的沒有）→ astra 原報告 → 我的精簡總結＋待拍板」；四份一起看。

| 題目 | 任務書 | astra 報告 | 精簡總結 |
|---|---|---|---|
| daemon／kernel | [daemon-kernel-spec-task](2026-09-22-daemon-kernel-spec-task.md) | [daemon-kernel-report-astra](2026-09-22-daemon-kernel-report-astra.md) | [daemon-kernel-summary](2026-09-22-daemon-kernel-summary.md) |
| llm cpu | [llm-cpu-plan-task](2026-09-22-llm-cpu-plan-task.md) | [llm-cpu-report-astra](2026-09-22-llm-cpu-report-astra.md) | [llm-cpu-summary](2026-09-22-llm-cpu-summary.md) |
| act 怎麼跑工具 | — | [act-report-astra](2026-09-22-act-report-astra.md) | [act-summary](2026-09-22-act-summary.md) |
| 逾時 | — | [timeout-report-astra](2026-09-22-timeout-report-astra.md) | [timeout-summary](2026-09-22-timeout-summary.md) |

| 檔 | 一句 |
|---|---|
| [2026-09-22-agent-task.md](2026-09-22-agent-task.md) | 任務書：aos-agent 第一版實作（waits 門＋idle／think／act） |
| [2026-09-22-decisions.md](2026-09-22-decisions.md) | **23 題拍板紀錄**（使用者決策），proto5.1 第 4 段與之後的回流都照這份 |
| [2026-09-22-backflow.md](2026-09-22-backflow.md) | proto5.1 規範回流 proto5：搬了什麼、跟舊版差在哪 |

## 2026-09-23～24：重架構 daemon→kernel→cpu

| 位置 | 一句 |
|---|---|
| [2026-09-23-rearch/](2026-09-23-rearch/README.md) | 三份新規範（cpu／kernel／daemon）四輪審查、實作、agent 線四輪、LM Studio 真跑、T5 修正（子資料夾，自己有表） |
| [2026-09-24-daemon-crash/](2026-09-24-daemon-crash/README.md) | daemon 崩潰窗口 C-2／C-3 測試：兩個窗口都照規範收斂，產品程式沒改 |
| [2026-09-24-backlog-cleanup.md](2026-09-24-backlog-cleanup.md) | `proto5/backlog/` 六個檔逐一判掉、資料夾拿掉（沒解的進 WAIT_USER A.14／16～18）；09-23 那輪在 [rearch/backlog-cleanup](2026-09-23-rearch/backlog-cleanup.md) |
| [2026-09-24-py312-run.md](2026-09-24-py312-run.md) | Python 3.12 實跑：1016 條在 3.12.13／3.14.7 都綠，不用改程式 |
| [2026-09-24-fix-abs-links.md](2026-09-24-fix-abs-links.md) | 另一台機器的絕對路徑改成相對路徑（16 檔、828 處） |
| [play/](play/README.md) | 試玩 r1～r5 與 fix-r1～r5（每輪兩份報告＋任務書、五條標準分數） |
| [2026-09-24-tidy/](2026-09-24-tidy/README.md) | 整理 wf／proto5 notes：SESSION-LOG 搬檔、本索引、壞連結 |
| [2026-09-24-spec-split/](2026-09-24-spec-split/README.md) | spec 九份拆成資料夾＋小檔（逐字搬、≤ 8 KB），指進 spec 的連結全改、astra 抽查 |
| [2026-09-24-kernel-crash/](2026-09-24-kernel-crash/README.md) | kernel 崩潰窗口 C-7／C-8 測試（15 條，真 KILL）：都照規範收斂，產品程式沒改；stop 箱重放會留同名 stop（同 B-10，待拍） |
| [2026-09-24-advice-r1.md](2026-09-24-advice-r1.md) | 使用者兩條建議：`aos-kernel check --agent` 搬到 `aos-agent check`（K 自己找）、`aos-kernel ls` 改對齊表＋`-v`＋穩定的 `--json`；astra 必修 6 條全修（[任務書](2026-09-24-advice-r1-review-task.md)、[審查](2026-09-24-advice-r1-review-astra.md)） |
| [2026-09-24-tutorials.md](2026-09-24-tutorials.md) | 同輪 B 隊：README 的上手教程拆成 [tutorials/](../tutorials/README.md) 五篇＋附錄（`llm.json`／`AOS_LLM_CONFIG` 在 01 一次設好），README 瘦身；六篇＋五分鐘照抄實跑全過；九條文件／行為不符 |
| [2026-09-24-tools-base.md](2026-09-24-tools-base.md) | base 工具包（仿 pi 的 read／write／edit／bash／grep／find／ls）＋`aos-agent tools add`；deepseek 實跑 write→bash→edit→bash；astra 必修 7 全修（[任務書](2026-09-24-tools-base-review-task.md)、[審查](2026-09-24-tools-base-review-astra.md)） |
| [2026-09-24-listen-tweak.md](2026-09-24-listen-tweak.md) | `aos-agent listen` 微調：`--last [N]`（不給看法＝用法錯）、每輪標頭帶收話時間、`--show-calls`／`--show-calls-full`；真跑輸出、astra 必修 7 條全修（[任務書](2026-09-24-listen-tweak-review-task.md)／[報告](2026-09-24-listen-tweak-review-astra.md)）、README 該改的句子 |
| [2026-09-24-agent-access/](2026-09-24-agent-access/README.md) | **提案**（沒改程式與規範）：agent 工具能碰哪些資料夾、workspace 別名、共用工具改名、環境變數——指示詞寫映射（`access.json`）＋bwrap 當牆；含小實驗、astra 審查、6 題待拍 |
| [2026-09-24-talk.md](2026-09-24-talk.md) | 使用者要的極簡 REPL：`aos-agent talk`（`--wait`、`--show-calls`、`/status` `/context` `/history` 等 slash）；送出前記位置，不踩 `listen --wait` 的坑；真跑畫面；astra 必修 12 條修 11 條，README 舊 `check --agent` 交給拆 README 那隊（[任務書](2026-09-24-talk-review-task.md)、[審查](2026-09-24-talk-review-astra.md)） |
| [2026-09-24-priority-and-shared-cpu/](2026-09-24-priority-and-shared-cpu/README.md) | 提案（不改程式）：agent 優先級——現在先到先派、建議先用專屬池（零改動）、嫌浪費再讓 cpu 服務多池；共用 cpu——其實已全部共用，缺的是工具檔 `_pool`（某支工具走某個池）；astra 審查 |
| [2026-09-24-cli-agents/](2026-09-24-cli-agents/README.md) | **提案**（沒改程式與規範、沒真跑）：Claude Code／Codex 兩支 CLI 納進 kernel／daemon／inst——主方案是「池＋inst 範本＋`aos-cli` 包裝」，不寫新種 cpu；十五個用法、另外四個角色、花錢與權限、astra 必修 11 全改、5 題待拍；＋[stage0.md](2026-09-24-cli-agents/stage0.md)：階 0 做出來（範本、教程 07、四條真跑驗證（牢那條跳過）、一條龍腳本） |
| [2026-09-24-tool-era/](2026-09-24-tool-era/README.md) | **規劃**（沒改程式與規範）：工具大開發時代——ai_core 九軸對到使用者五句＋「邊界」的評分表、`~/repo/workflows` 化成團隊（三個 agent＋四個機械員）、29 個工具清單、三波開發計畫與任務書骨架；astra 審查 |
| [2026-09-24-daemon-split-review/](2026-09-24-daemon-split-review/README.md) | **審查**（沒改程式與規範）：「daemon 要 sudo 才能切使用者，所以跟 kernel 分開」站不住——不用 root 也能切（subuid 實驗）、root daemon 反而更危險；分開剩「生死與排程別互相拖累」；建議現在不動，proto5-2 重寫 kernel 時做「開機合一、家不合一」；權限預設 bwrap、daemon 永不 root；兩派 memo＋反駁、astra 兩份、5 題待拍 |

## 為什麼散檔沒收進子資料夾（2026-09-24 tidy 判斷）

- 09-22 那四份 astra 報告帶了約 700 條指向 `spec/`、`lib/` 與舊 proto 的連結；搬一層資料夾就得全部改相對路徑，而 `spec/` 正在拆檔、那些連結另一隊也要改，兩邊一定撞。
- [notes-brief/](../notes-brief/README.md) 的檔名跟 09-22 這批一對一，proto5.1 的筆記也連進來；搬了要跟著改的檔在別的領地。
- 已經成串的（重架構、崩潰測試、試玩）本來就在子資料夾；剩下的散檔一天最多十幾份，靠本索引分組就夠。spec 拆完、要再整理時可以重新考慮。
