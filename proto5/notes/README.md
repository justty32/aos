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
| [2026-09-24-tool-era/](2026-09-24-tool-era/README.md) | **規劃**（沒改程式與規範）：工具大開發時代——ai_core 九軸對到使用者五句＋「邊界」的評分表、`~/repo/workflows` 化成團隊（三個 agent＋四個機械員）、29 個工具清單、三波開發計畫與任務書骨架；[astra 審查](2026-09-24-tool-era/review-task.md)／[報告](2026-09-24-tool-era/review-astra.md)；＋[t3/](2026-09-24-tool-era/t3/README.md)（第一波第 3 隊：files／wf 工具包、aos-json、aos-directives；[任務書](2026-09-24-tool-era/t3/review-task.md)／[審查](2026-09-24-tool-era/t3/review-astra.md)）；＋[t1/](2026-09-24-tool-era/t1/README.md)（第一波第 1 隊：spec/team 共用格式、aos-team、成員模板、門房、任務單狀態機、問人、tools/task；[任務書](2026-09-24-tool-era/t1/review-task.md)／[審查](2026-09-24-tool-era/t1/review-astra.md)）；＋[t5/](2026-09-24-tool-era/t5/README.md)（第一波收尾隊，見下一列）；＋[w2c/](2026-09-24-tool-era/w2c/README.md)（第二波 C 隊：`lock`／`access_request`／`persona_propose`／`routine_propose` 工具、工具檔 `_pool`、審查子單編號跟父單一致、領隊改寫類單子自動補 `wf_lint_strict`；[任務書](2026-09-24-tool-era/w2c/review-task.md)／[審查](2026-09-24-tool-era/w2c/review-astra.md)） |
| [2026-09-24-tool-era-post.md](2026-09-24-tool-era-post.md) | 工具大開發時代第一波第 2 隊：郵差兼書記 `aos-team post`、驗收員 `verify`、心跳 `beat`／`routine`、`team_say`；追加使用者五題裁決（郵差間隔、心跳身分、`once`、檢查器壞≠沒過、例行完成不擾人）與 astra 第二輪（[任務書](2026-09-24-tool-era/review-post-task.md)／[審查](2026-09-24-tool-era/review-post-astra.md)，追加輪[任務書](2026-09-24-tool-era/review-post2-task.md)／[審查](2026-09-24-tool-era/review-post2-astra.md)） |
| [2026-09-24-tool-era-memory.md](2026-09-24-tool-era-memory.md) | 工具大開發時代第一波第 4 隊：事件紀錄、`aos-agent context`／`compact`（機械壓縮＋自動＋申請）、`note` 工具＋`notes ls/show`、`history --archive`；使用者裁決（封存改 8 KB 機械摘要、自動壓縮預設開 32000、log 輪換）（[任務書](2026-09-24-tool-era/review-memory-task.md)／[審查](2026-09-24-tool-era/review-memory-astra.md)） |
| [2026-09-24-tool-era/w2a/](2026-09-24-tool-era/w2a/README.md) | 工具大開發時代**第二波 A 隊（造工具）**：`aos-agent tools new／test／wrap-py`、`wf_fill`（照事實表機械填佔位）、導入工人模板 `importer`（工具表少一半）、`aos-team route try`、mail 列等人回答的題目；例子 1 導入真跑 3/3 done，模型 6～7 次、3.0～3.6 萬 token、42～54 秒（T5：17～25 次、22～34 萬、141～183 秒）；wrap-py 的工具裝給工人、模型沒寫 bash；[astra 審查](2026-09-24-tool-era/w2a/review-task.md)；要拍 1 題 |
| [2026-09-24-tool-era/w2b/](2026-09-24-tool-era/w2b/README.md) | 工具大開發時代**第二波 B 隊（牆接線）**：門房 `tool` 規則、驗收員的 wf-lint 與新條目 `cmd_ok`（`team.json` 白名單裡的專案指令）關進牢；`wf_init` 本來就在牢裡；郵差讀 outbox 再驗路徑、白名單、假信頭；領隊、工人多掛唯讀 `mem` 與 `recall`／`context` 兩支工具；逃逸測試 19 條全擋；例子 1 關牢跑 10/10 過（15～29 次、122～224 秒）、例子 2 2/2、例子 3 1/1；六軸 L2 S4 R2 F4 H4 B4（T5 的 B3 是推的，這次測過）；規範 [spec/team/wall.md](../spec/team/wall.md)；[astra 審查](2026-09-24-tool-era/w2b/review-task.md)必修 3 修 3；試玩 wall-r1 4/4/3/4/4；要拍 1 題 |
| [2026-09-24-tool-era/w3a/](2026-09-24-tool-era/w3a/README.md) | 工具大開發時代**第三波 W3-1（模型生成員／造工具，提早收線版）**：`spawn_member`／`tool_draft` 兩個申請、`aos-team spawn／tool approve`、名冊 `spawn.templates`；逃逸測試 16 條全擋；T-spawn 對照 2＋2 次：加模型版 token 最多多一倍、時間 1.5～5 倍、人一樣要批每個→建議只用機械版；T-toolsmith 真跑與 astra 審查沒做、留下一輪；要拍 1 題 |
| [2026-09-24-tool-era/w3b/](2026-09-24-tool-era/w3b/README.md) | 工具大開發時代**第三波 W3-2 隊（多叫一次模型）**：`tools wrap-cli`（argparse 靜態讀／help 文字規則解）、wrap-py 與 wrap-cli 的 `--describe-with-llm`（只寫提案、人看過才產包）、`compact --summarize`、`aos-team crystal`（固化建議），四項各附機械版 vs 加模型版六軸與真跑；只有 wrap-py 補描述證明值得（選對工具 3/6→6/6），四項模型版全預設關；[astra 審查](2026-09-24-tool-era/w3b/review-task.md)；要拍 1 題 |
| [2026-09-24-tool-era/t5/](2026-09-24-tool-era/t5/README.md) | 工具大開發時代第一波**收尾隊**：真跑三個例子（導入 3/3、改寫＋審查 2/2、心跳 1/1，都 done；導入時領隊 0 次、模型 17～25 次）、`aos-team score` 六軸彙整（L2 S— R2 F4 H4 B3）、三個模板人格定稿、routes 例子、接 T4 五件（`notes: true`、`compact_me`）、教程 08、新手試玩兩輪（4/4/4/3/4 → 5/4/4/4/4）、wf_doc 關牢讀不到快照修好；[astra 審查](2026-09-24-tool-era/t5/review-task.md)必修 5 修 5；要拍 1 題 |
| [2026-09-24-daemon-split-review/](2026-09-24-daemon-split-review/README.md) | **審查**（沒改程式與規範）：「daemon 要 sudo 才能切使用者，所以跟 kernel 分開」站不住——不用 root 也能切（subuid 實驗）、root daemon 反而更危險；分開剩「生死與排程別互相拖累」；建議現在不動，proto5-2 重寫 kernel 時做「開機合一、家不合一」；權限預設 bwrap、daemon 永不 root；兩派 memo＋反駁、astra 兩份、5 題待拍 |
| [2026-09-24-access-impl/](2026-09-24-access-impl/README.md) | **實作**（照 agent-access 提案）：權限牆＋工具管理 CLI——`access.json` 寫 agent 的工具看得到哪些資料夾，aos-agent 送工具時自動用 `aos-jail`（bwrap）關牢；`tools ls/add/rm/alias/unalias`、`access ls/set/rm/cwd/net`；deepseek-chat 真跑兩輪都過；astra 必修 8 條全修；測試 1343→1447（rebase 後 1470） |
| [2026-09-24-fold-in/](2026-09-24-fold-in/README.md) | **納入**：proto5-2（池式 daemon／kernel）搬進 proto5 取代舊的 daemon／kernel，agent 線保留 proto5 的；規範照 proto5-diffs 換句並搬新章節；`aos-exec`、`aos_kernel_cpu` 拆檔、tidy；proto5-2 只留 spec／notes 當歷史；astra 必修 3 條全修；測試合併後 1597，rebase 後 1723 |
| [2026-09-24-idle-wait-impl/](2026-09-24-idle-wait-impl/README.md) | **實作**（照 proto5-2 idle-wait 提案方案 (b)）：agent 沒事退 102 停車，回音出貨時 kernel 叫醒、`say` 投 `wake` 叫醒，保底 `park_ms` 5 分鐘；閒著 60 秒 kernel 派 agent 從 28 格降到 0 格；kill -9 在「放好回音、存帳本前」重跑驗過；astra 必修 2 條全修；測試 1999→2044 |
| [2026-09-24-one-boot/](2026-09-24-one-boot/README.md) | **實作**（使用者 09-24 拍板）：開機合一、家不合一——一條 `aos up`／`aos down`；kernel cpu、tick 鏈、開機交接拿掉，daemon 定時或有新單時替 kernel 開一格 tick（同時一格＋`K/.tick.lock`）；kernel 帳本換 `K/ledger.sqlite`（只寫變了的列、一筆交易）；`aos-kernel proc --json`；`ls --json` 第 3 版；投單到回音 0.5→0.04 秒；astra 必修 5 條全修；測試 2068→2106 |
| [2026-09-25-commons/](2026-09-25-commons/README.md) | **實作**（commons 隊）：跨團隊公共資料夾＋圖書館員隊（名冊三層預設開、成員唯讀掛 `/work/commons`、`commons_submit`／`commons_search`／`commons_verdict`、郵差機械審、像舊條目才叫便宜模型、`aos-team commons …`、匯入 playbook）；真跑 2 次＋圖書館員單跳；圖書館部怎麼當 aos 團隊掛進公司 |
| [2026-09-24-tick-gap/](2026-09-24-tick-gap/README.md) | **實作**（P2 隊）：先量每一跳（`AOS_HOPS`＋`aos_hops.py report`），再改四條：kernel 叫醒後同一格就派（提交點 D）、agent 退 103「馬上再來」、cpu 等子行程用 pidfd、kernel 派完按 cpu 門鈴；單 agent 一題 11.8→2.1 秒；反覆工作 bad 時 `ls` 第一行不印 ok、`add --on-bad` 寄信（團隊郵差／心跳預設寄給人）；`poll_ms` 量過維持 200；astra 沒審、團隊改後沒真跑（提早收） |

## 2026-09-25：財務部

| 檔 | 一句 |
|---|---|
| [2026-09-25-finance/](2026-09-25-finance/README.md) | 財務部成立：一本帳＋`aos-team cost`＋郵差超預算不派新單；真跑 2 次；今天各家族用量估算；公司帳戶（五家競爭） |

## 2026-09-25：HR 部

| 檔 | 一句 |
|---|---|
| [2026-09-25-hr/](2026-09-25-hr/README.md) | HR 部成立：薪資表＋`aos-team hr trial`（換一人的模型跑同一份任務集、可插評分、照規則調薪）＋名額（新創 10／20／5）＋正式／臨時工；例子 1 試 4 配置：工人換 deepseek 過、領隊換 deepseek 不過 |

## 2026-09-25：組織設計（公司＋市場層）

| 檔 | 一句 |
|---|---|
| [2026-09-25-company/](2026-09-25-company/README.md) | 用 aos 團隊蓋一間新創公司：部門＝團隊資料夾、董事＝human、機械總機搬〔給 部門〕的信；`company.py`、`market.py`（排名撥額度、總池、倒閉、合併）；真跑 2 次（失敗 1、端到端成功 1：3 分 26 秒）；給董事 12 題 |

## 為什麼散檔沒收進子資料夾（2026-09-24 tidy 判斷）

- 09-22 那四份 astra 報告帶了約 700 條指向 `spec/`、`lib/` 與舊 proto 的連結；搬一層資料夾就得全部改相對路徑，而 `spec/` 正在拆檔、那些連結另一隊也要改，兩邊一定撞。
- [notes-brief/](../notes-brief/README.md) 的檔名跟 09-22 這批一對一，proto5.1 的筆記也連進來；搬了要跟著改的檔在別的領地。
- 已經成串的（重架構、崩潰測試、試玩）本來就在子資料夾；剩下的散檔一天最多十幾份，靠本索引分組就夠。spec 拆完、要再整理時可以重新考慮。
