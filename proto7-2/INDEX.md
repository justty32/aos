# proto7-2 INDEX — 資料夾結構與來源

← [proto7-2 README](README.md)（從 README 拆出的「結構」「來源」兩節，內容原樣）

## 結構

| 位置 | 是什麼 |
|---|---|
| `spec.md` | 核心 spec（只放規則） |
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`（後兩個的本體在工具包），與搬來的 `aos-exec` |
| **核心** `lib/aos7_*.py` | 受行數預算管（見 [README「防再胖」](README.md#防再胖新功能預設進模組)），共九檔： |
| `lib/aos7_daemon.py`、`aos7_daemon_timeline.py` | daemon：登記（寫檔成功才生效）、控制檔、node 消失、status；回收意圖落 nodes.json `reaping`、確認收乾淨才開新時間線、paused.json 存 rounds 倒數 `steps` 與待結算 `owe`（開回合前記、關回合後扣倒數同次清）；reaping 未確認乾淨時重起 status 保留 missing；每個 node 一條時間線（`read_config` 不丟例外、壞值記錯用預設，`owe_round` 補扣）（spec 第 1、2 節）；`owe` 存不進就不開回合、等一下回頂端再試（FX1 A10-02） |
| `lib/aos7_tick.py`、`aos7_tock.py` | 開回合（tasks.json、once 的 launch 標記；帶 launch 的 once 先比對槽的 run 再看排程）／關回合（last-round.json、刪槽）（第 3、4、7 節） |
| `lib/aos7_task.py` | 槽、三態判定、lost 前的身分掃描、kill（runner 還在啟動交接＝回 unknown、請求留著）；起任務的環境只帶核心六個 `AOS7_*`（第 5、6 節），繼承來的 `AOS7_*` 只明列放行 `AOS7_LITELLM_KEY`（金鑰只經環境、不落地，FX1 A10-01） |
| `lib/aos7_proc.py` | 程序的事實（`proc`：不在／starttime／不知道）、同一個程序嗎、身分掃描、Q1 範圍的收程序（清場後身分複查最多補收 3 輪；node 級打記著的 pgid 前 `group_is_node` 重驗） |
| `lib/aos7_run.py` | 任務的包裝：pid.json、exit.json（帶 run；run 先取環境 `AOS7_RUN`，birth 讀到再以它為準） |
| `lib/aos7_fs.py` | 錯誤四分支的入口（讀檔 `fact`、紀錄 `hold`、例外 `Unknown`）、原子寫、flock、動作鎖與世代、測試鉤子的轉接（`AOS7_TEST_HOOKS` 有設才載入 `tests/_hooks.py`；`write_json` 有 `inject("write")`） |
| `lib/aos7_mount.py` | 掛載（4.5）：tick 建掛載、審核執行中加掛（連結已建、birth 未記時被殺可冪等恢復） |
| `lib/aos_*.py` | 搬來的 inst 執行器（不算核心預算） |
| **模組** `modules/` | [總覽](modules/README.md)；每包一個資料夾，自帶 README 與 `tests/` |
| `modules/tools/` | [工具包](modules/tools/README.md)：`aos7-ctl`、`aos7-wait-tock`、任務端函式；ctl 用法錯退 2 附例子、讀寫故障或未預期例外退 3 一行（FX1 A10-09） |
| `modules/control/` | [控制包](modules/control/README.md)：restart／reload 在請求端做；restart 失敗回條加 `outcome: unknown|refused`（既有欄位不變），ctl 據此未知退 3、確定拒絕退 1（FX1 A10-09） |
| `modules/subd/` | [子 daemon 包](modules/subd/README.md)：包裝程式 `aos7-subd`（替子根設 `AOS7_AUDIT_ALLOW`）；入口 help／用法錯一行（FX1 B10-01） |
| `modules/once_retry/` | [once 保證包](modules/once_retry/README.md)：`retry_lost.py`（keep 任務；加回前持表鎖重讀 birth，契約是至少一次） |
| `modules/audit/` | [稽核包](modules/audit/README.md)：包裝程式 `aos7-audit`，可選的寫入紀錄；`AOS7_AUDIT_ALLOW` 豁免 node 內巢狀邊界（subd 設）；入口 help／用法錯一行（FX1 B10-01） |
| `modules/diag/` | [診斷包](modules/diag/README.md)：唯讀工具 `aos7-diag`＋會停下等人的情況與恢復步驟；`aos7-diag --llm <node>` 唯讀列沒回條的 llmcall、halted 的 author job、budget 在飛預留（RV-fix-B 從 llmdiag 併入；讀不到檔退 3、給錯層退 2） |
| `modules/events/` | [事件保存包](modules/events/README.md)：每 node 一個 `events/`，觀測／必讀兩通道各 1 活躍段＋≤4 封存（上限 12 檔）；`aos7_events_store.py` 保存端、`aos7_events_pub.py` 發布、`aos7_events_read.py` 讀者、`aos7_events_cli.py` 一行錯誤訊息與 ack 子命令、`aos7-events` 取樣器（子命令 read／pub／ack；status 去重鍵與截半行記號存 state.json `status_last`／`torn_cut`）；[spec](modules/events/spec.md)＋[取樣器 spec](modules/events/spec-sampler.md)、`examples/`（demo_pub、真 daemon 300 回合 longrun） |
| `modules/routines/` | [事務包](modules/routines/README.md)：`aos7-routines`（add／ls／rm；`ls --run` 免 daemon 立刻跑到期的），`aos7_routines.py` 兩張表（例行／一次性），tick 喚醒、先寫執行證據再放鎖同步執行、最多一次，未知留到下一回合 |
| `modules/skills/` | [skill 包](modules/skills/README.md)：`aos7-skills`（index／pick／mount），`aos7_skills.py` 索引行（只 name＋description）與必用表、預設本機關鍵字挑、開帳後經 llmcall 挑；`library/` 內建三本（aos-inbox、aos-test、wf-lint）；`bank.py` 選用題庫（11 本逐題 pick 印分數） |
| `modules/wfnode/` | [node 工作流包](modules/wfnode/README.md)：`aos7-wfnode`（init／state／check），`aos7_wfnode.py` 裝工作流樹與體檢、`wfnode_fill.py` 只照已知事實填模板、`wfnode_judge.py` 處理導入判斷（未知段落留原文）、`wfnode_state.py` 鎖內追加 STATE 與更新 NEXT-SESSION |
| `modules/metrics/` | [效率量測包](modules/metrics/README.md)：`aos7-metrics job`／`aos7_metrics.py` 唯讀量 token、同時呼叫數、秒數、重試；`baseline/r1/` 固定證據（R1 各模型一圈的 llmcall／budget／author 檔，測試基線）；`job --by model｜holder｜day｜hour` 分組（`by()`，原 usage 包）、`--detail`／`--json` 帳差（`ledger()`），不給 `--by` 時預設行不變 |
| `modules/compact/` | [記憶整理包](modules/compact/README.md)：`aos7-compact`（now／forget／watch），`aos7_compact.py` 舊段先封存再換摘要、open 項與最近 N 則留原文、每個換檔點被殺可恢復；選配 llmcall 摘要、events 提醒；llmcall 結果用共用判斷：答到（0／4＋outcome answered）才收摘要、確定失敗退 1、3／未知退 3，失敗都留 pending 與原文（FX1 A10-03） |
| `modules/mail/` | [信箱包](modules/mail/README.md)：`aos7-mail`（send／read／done；audit／roster／team 見 ADVANCED）；`aos7_mail.py` 檔案為權威的郵局（events must 只當提醒；回信白話狀態、正文空段省略，讀信分開 body／plain）、`aos7_mail_box.py` 辦結日誌／歸檔／只讀自身信箱、`aos7_mail_ack.py` 本地游標掃 must 有進展才 ack 一次、`aos7_mail_setup.py` ROSTER 原子追加與團隊發布、`aos7_mail_cli.py`／`aos7_mail_help.py` 參數與說明；壞 ack 游標保留證據、不 ack，退 3 一行（FX1 A10-08） |
| `modules/llmdiag/` | 轉址 stub `aos7-llmdiag`（stderr 一行指向 `aos7-diag --llm`、退 1；r5 移除）；原程式在 [archive/llmdiag/](archive/llmdiag/README.md) |
| `modules/up/` | [up 起步入口](modules/up/README.md)／[進階契約](modules/up/ADVANCED.md)：備好工作簿、帳、技能、三個 keep 任務、人的信箱並起心跳（前景／`-d`）；`status` 六行唯讀（卡住時七行）、`stop` 留檔；`aos7_up.py` 安裝、起動證據與回收，`aos7_up_cli.py` 參數／錯誤／ask、brain exec 分派，`aos7_up_brain.py` 收信一封一回合（FIFO、先寫請求再呼叫 llmcall、被殺接同一筆、不確定滿 deadline 回卡住換下一封（白話卡住信，給維護者的細節寫在 `brain/stuck/<call>/how.md`）；一封信可跨多步（AI 回「回信：／繼續：／要你決定：」，每 5 步寄進度信 PROGRESS、連續 3 步沒進展或滿 40 步停下問你，進度記在 `brain/task.json`）；STATE 去重記 id 在 `brain/state.json`、每回合跑 `aos7-compact now`）＋`prompts/brain.json` 提示模板，`aos7_up_memory.py` 跨信記憶（結案存 `notes/done/`＋目錄、附前件、要檔案、附最新 STATE、提示上限），`aos7_up_ask.py` 人的信箱 `you` 只收本次 REQUEST 的終局回信，顯示一般正文與協定段落，`aos7_up_status.py` 狀態／觀看／子指令與設定驗證；設定 `.aos/up.json`；`examples/` 有 `longtask/`（12 封信長任務）、`multiround/`（一封信跨 8 步）、`real-evidence/`（真 AI 一圈證據）、`brain_node.py`；brain 用共用 `answered` 判斷 llmcall 結果，未知碼當不確定保留接續（FX1） |
| `modules/counter.py`、`history.py` | 最小示範任務、歷史 module 的參考實作（觀測任務包的雛形；來源檔名可逆編碼 `hist_name`；升級時含 `+`／`%` 的舊檔與 `daemon-events.jsonl` 一次封存成 `.v1`，夾內放 `.names-v2`） |
| **上層任務包** `packs/` | kernel 的任務包（工作語意；通用／agent／LLM 分層，原則 8）；每包一個資料夾，自帶 README（契約卡）、spec、`tests/` |
| `packs/step/` | [step 包](packs/step/README.md)：步驟表直譯器 `aos7-step`＋槽外結果檔（子工作包裝 `aos7-step-result`／`aos7_step_result.py`）＋檢查器（run 步 `unknown_codes`、重送額度記框架 `resends`、啟動清死暫存檔）；兩支入口用法錯一行附例子、未預期例外退 3（FX1 B10-01） |
| `packs/budget/` | [budget 包](packs/budget/README.md)：grant／帳／入口（預留→執行→結算），示範資源＝假 API 受理次數（入口／假後端／call 包裝在 `aos7_budget_gate.py`）；原名 account，為避免跟 Linux account 重疊改名；退出碼 0／1／2／3、單位＝加權成本、帳任務起時清 `gateway/` 死暫存檔；部分結算（settle 收 0≤used≤預留、usage 缺留 pending、超出記 overrun，blueprint-llm2 §4） |
| `packs/llmcall/` | [llmcall 包](packs/llmcall/README.md)：LLM 單次呼叫閘道（假傳輸＋真傳輸 llm.litellm），固定請求→預留→intent→raw→done→結算→回條；本地證據恢復、遲到 adopt、軟 token 帳；退出碼 0～4；傳輸在 `aos7_llmcall_fake.py`（假，記受理次數）、`aos7_llmcall_litellm.py`（OpenAI 相容非串流，送一次不重試；取最後一個非空 choice（LiteLLM 拆 sol 開場白），raw 記 choices_n／skipped）；`aos7_llmcall_exit.py` 是呼叫方共用的退出碼對照（`meaning`／`delivered`／`answered`，退 4 只表示帳未清、答沒答成看回條 outcome，FX1）；litellm 傳輸送前驗金鑰字元（不合法不送、退 1），傳輸例外只留型別名、不含原訊息（FX1） |
| `packs/adapt/` | [adapt 包](packs/adapt/README.md)：鄰居 node 的最新值轉接（固定版本、確定性鏈、依據 basis＋出處 src、三態暫存器），示範溫度感測→風扇；入口用法錯一行附例子（FX1 B10-01） |
| `packs/author/` | [author 包](packs/author/README.md)：LLM 作者第一刀（假候選）——需求＋候選經三層驗證、確定性編譯成獨立版本 step 工作，意圖→表鎖內合併自己那一項→回條；`close` 後每需求只留 request＋receipt；`send`／`intake` 經事件必讀通道收單（游標與收件回條在 `author/events.json`，回條寫成後才 ack）；三關入口 `bin/aos7-gates`（預設 rules 離線、publish 要 --repo、索引列插進表格）、aos 路徑 publish 寫結案標記；第二刀 `aos7_author_llm.py` 接 `propose --llm` 經 llmcall 真傳輸，`examples/llm-request/` 收一整圈證據；`aos7_author_aos.py` 接 aos-tool／aos-module 學徒、三關檢查與 llmcall 審查／learn；`aos7_author_pub.py` 發布與恢復；`checkers/aos_three_gates.py` BRIEF、三關驗證與只新增 apprentice 分支的發布器；`toolcards/`（csv、aos-tool、aos-module）題型卡；同形三連題：[events 缺口](packs/author/examples/aos-tool-gap/request.json)、[執行報告](packs/author/examples/aos-tool-runs/request.json)、[mail 未辦](packs/author/examples/aos-tool-audit/request.json)，各有真模組造的測資、固定答案 checker 與參考候選；四道郵局慣例題（AP5，慣例不寫在需求裡、量自我改進用）：[信數](packs/author/examples/aos-tool-mailcount/request.json)、[寄件](packs/author/examples/aos-tool-mailsent/request.json)、[未辦](packs/author/examples/aos-tool-mailopen/request.json)、[狀態](packs/author/examples/aos-tool-mailstatus/request.json)；三關另收「每段一個檔」文字候選（`propose --format text`）；llmcall 1／2＝模型或請求確定沒做成退 1、3／未知退 3（FX1 B10-11）；CSV propose 鎖／寫檔 OSError 退 3 一行（FX1 A10-10） |
| `packs/prompt/` | [prompt 包](packs/prompt/README.md)：`aos7-prompt render` 照 `prompt.json`（`aos_directives` 的 `$ref`／`$fmt`／`$env`／`$opt`，加讀檔 `file`／`tail`／`latest`、訊息 `append`／`clear`）拼出 llmcall 請求；超過 `max_chars` 的段折成 `ref://<sha>`（原文在 `<node>/refs/`），`expand` 換回；回條帶 token 估值（字數／3）；退出碼 0／2／3 |
| `packs/usage/` | 轉址 stub `bin/aos7-usage`（stderr 一行指向 `aos7-metrics job … --by model`、退 1；`--help` stdout 說明退 0；`bin/` 被 gitignore，用 `git add -f` 進版控）；原程式在 [archive/usage/](archive/usage/README.md) |
| `packs/kernel/` | [kernel 包](packs/kernel/README.md)／[進階契約](packs/kernel/ADVANCED.md)：替任務做決策的 keep 任務 `aos7-kernel`（`run`／`status`），每個自己的 tock 讀來源公開事實→純函式規則→整份驗證→先存意圖（`state.json` 一次 rename）再寫目標槽 `ctl.json` kill（綁 run）→核對回條；`aos7_kernel_state.py` 設定／state／快照，`aos7_kernel.py` 驗證／送出核對／主迴圈／status，`aos7_kernel_rules.py` 規則 `supervise-brain`（brain 的 task.json `(id, step)` 停滿 6 回合寄 NEEDS-USER 白話通知、同信只通知一次；滿 12 回合 kill，同一步 kill 退避 12／24／48 回合、最多 `max_kills` 次；done 每筆記基準）；範例 `examples/supervise-brain/`（練習用的 AI 卡住→寄信→kill→brain 接續不重問） |
| `archive/` | 已移除的包原樣存放（`git mv`，不跑測試、不維護）：[usage/](archive/usage/README.md)（併入 metrics `job --by`）、[llmdiag/](archive/llmdiag/README.md)（併入 `aos7-diag --llm`）；原處只留轉址 stub |
| `tests/` | 核心測試 `tests/core/`、共用工具、`run_all.py`；測試導引見 [tests/README.md](tests/README.md) |
| `notes/` | problems.md、core-slimming.md、component-contracts.md、layer-interfaces/、changes-from-7-1.md、play/ |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：**原樣複製自 proto7-1**（10-04；proto7-1 當初從 proto6 複製）；`aos_directives.py` 之後改過：陣列索引去前導零後再檢長度、轉整數（前導零照收，去零後仍超長才退 125；A9-03、FX1 A10-11）。
- `lib/aos7_fs.py`、`aos7_run.py`、`aos7_mount.py`、`modules/tools/aos7_ctl.py`、`modules/audit/aos7_audit.py`、`modules/audit/audit_site/`、`tests/_proc.py`：從 proto7-1 複製後改寫（`aos7_audit.py`、`audit_site/`、`_proc.py`、`aos7_mount.py` 幾乎沒改）。
- `lib/aos7_daemon*.py`、`aos7_tick.py`、`aos7_tock.py`、`aos7_task.py`、`aos7_proc.py`：照 proto7-1 同名檔的結構重寫（程序工具從 proto7-1 `aos7_task.py` 拆出來）。
