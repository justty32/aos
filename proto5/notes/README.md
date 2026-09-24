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
| [play/](play/README.md) | 試玩 r1～r4 與 fix-r1～r4（每輪兩份報告＋任務書、五條標準分數） |
| [2026-09-24-tidy/](2026-09-24-tidy/README.md) | 整理 wf／proto5 notes：SESSION-LOG 搬檔、本索引、壞連結 |
| [2026-09-24-spec-split/](2026-09-24-spec-split/README.md) | spec 九份拆成資料夾＋小檔（逐字搬、≤ 8 KB），指進 spec 的連結全改、astra 抽查 |

## 為什麼散檔沒收進子資料夾（2026-09-24 tidy 判斷）

- 09-22 那四份 astra 報告帶了約 700 條指向 `spec/`、`lib/` 與舊 proto 的連結；搬一層資料夾就得全部改相對路徑，而 `spec/` 正在拆檔、那些連結另一隊也要改，兩邊一定撞。
- [notes-brief/](../notes-brief/README.md) 的檔名跟 09-22 這批一對一，proto5.1 的筆記也連進來；搬了要跟著改的檔在別的領地。
- 已經成串的（重架構、崩潰測試、試玩）本來就在子資料夾；剩下的散檔一天最多十幾份，靠本索引分組就夠。spec 拆完、要再整理時可以重新考慮。
