← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto5/lib 模組

一檔一句（跟 [proto5/lib/README.md](../../../../proto5/lib/README.md) 的模組表同步；新增模組兩邊各插一行）：

| 模組 | 職責 |
|------|------|
| `aos_directives` | 指示詞（`$env`／`$fmt`／`$ref`／`$opt`）解析的純函式庫 |
| `aos_directives_edit` | `aos-directives`：人格分節編輯（ls／show／set／add／rm／export／import／versions／revert）＋指示詞 resolve／check |
| `aos_inst` | inst.json 的讀、驗、解 |
| `aos_exec` | 執行一次的上層：三種目標的解讀（`run_target`／`run_target_full`／`run_inst`）與 `aos-exec` 命令列 |
| `aos_exec_run` | 執行一次的底層：前置檢查、開串流、起子行程、等待／逾時／強停整組、寫 exit 檔 |
| `aos_exec_spawn` | daemon 的非同步入口 `spawn_target`（`launcher` 決定 fd 0／1 怎麼接） |
| `aos_home` | JSON-RPC 信封、原子放單與狀態、ack／stop、開機對帳、`--target` 找家 |
| `aos_client` | 交件者：取名、放單、等回音、ack |
| `aos_exec_cpu` | 長命 exec cpu（`aos-cpu`）：逐件執行、訊號與對帳、回完音丟 `notify` 通知 |
| `aos_daemon` | daemon 的家、info、`is_alive`、給 kernel 讀的池摘要／kids 檔、boot（`run`）與 halt（`stop`） |
| `aos_daemon_pools` | 池的資料形狀（pool.json／kids／summary.json）、檔案動作、拉孩子 |
| `aos_daemon_loop` | daemon 的一圈：收屍、狀態機、退避、節流、fd 預算、批次停機階梯 |
| `aos_daemon_rpc` | daemon 收的單 `scale`／`kill`／`ls`／`tick` 怎麼驗、怎麼判 |
| `aos_daemon_ticks` | （one-boot）daemon 替 kernel 開 tick：登記檔 `D/kernels/`、定時或 `K/requests/` 有新檔就開一格、同時一格、逾時 KILL、連敗退避 |
| `aos_daemon_cli` | `aos-daemon boot／halt／ls／scale／kill` 命令列 |
| `aos_kernel` | kernel 入口（`main`）＋只留測試在用的小匯出層 |
| `aos_kernel_info` | 池表讀驗（info 第 2 版）、成員公式、`init`、初始帳本、`classify`、共用錯誤 |
| `aos_kernel_ledger` | `KernelLedger` 帳本（記憶體裡第 2 版同形）：排隊、syscall、busy／on、四個出貨箱 |
| `aos_kernel_store` | （one-boot）帳本第 3 版 `K/ledger.sqlite`：整份讀、只寫變了的列一筆交易、舊 `state.json` 匯入；`proc`／`peek_proc` 給 `aos-kernel proc`、agent、郵差讀 |
| `aos_kernel_engine` | `Kernel` 一格十步與 `tick` |
| `aos_kernel_pools` | kernel 這邊怎麼增減 cpu（每格第 7 步：scale 回音、重算、送單、搬池） |
| `aos_kernel_boot` | `boot`（寫帳本、向 daemon 登記開 tick）、`status`、halt 等停好 |
| `aos_kernel_cpu` | `aos-kernel cpu add／rm／ls`：只改 `K/info.json` 的池表 |
| `aos_kernel_rows` | 按池摘要與一顆一行的資料與排版（`cpu ls`、`ls`、health、check 共用） |
| `aos_kernel_health` | `health()` 一句話健康判定與 agent 暫停／重試標記；（09-24 tick-gap）有反覆工作 bad 就報 `bad` |
| `aos_hops` | （09-24 tick-gap）`AOS_HOPS` 設了才記的每一跳時間戳；`report` 把一個 agent 的牆上時間切成一跳一跳 |
| `aos_kernel_ls` | `aos-kernel ls`：穩定資料（`--json`）與對齊表 |
| `aos_kernel_check` | `aos-kernel check` 啟動前唯讀檢查（`aos-agent check` 共用前半） |
| `aos_kernel_cli` | `aos-kernel` 參數解析與 `main` |
| `aos_up` | （one-boot，入口 `cli/aos`）`aos up`：daemon 沒在跑就開→`aos-kernel boot`→等第一格；`aos down`：halt→沒人用的 daemon 一起停 |
| `test/test_one_boot.py` | one-boot 的真 daemon＋真 tick 測試：交易中 kill -9 回滾、tick 逾時與連敗、新單觸發、同時一格、`aos up`／`down` 不留行程、舊帳本匯入 |
| `aos_llm_call` | `aos-llm call`：問模型一次 |
| `aos_llm_ask` | （第三波 W3-2）不需要 agent 家的「多問一次模型」：工具的 `--describe-with-llm`／`--summarize`／`--suggest-with-llm` 共用；temperature 0、從回話抽 JSON |
| `aos_agent` | agent 的 tick 三格、批次派工、kernel 排程登記 |
| `aos_agent_cli` | `aos-agent` 各子命令的 argparse 與分派 |
| `aos_agent_home` | agent 家的內容讀驗與 `aos-llm call` 的六格 loader |
| `aos_agent_info` | agent 的 info 設定與 state 讀驗、寫回 |
| `aos_agent_batch` | 批次建立、inst 產生（含 aos-jail 包裝）、交件、結清 |
| `aos_agent_inputs` | waits 門與輸入消費的恢復流程 |
| `aos_agent_results` | 模型與工具結果判定、失敗分類 |
| `aos_agent_runtime` | 持久化、恢復清理、tick 鎖、測試掛鉤 |
| `aos_agent_init` | `aos-agent init` |
| `aos_agent_say` | `aos-agent say` |
| `aos_agent_listen` | `aos-agent listen` |
| `aos_agent_listen_render` | listen 的印法 |
| `aos_agent_talk` | `aos-agent talk` 來回對話 |
| `aos_agent_status` | `aos-agent status` |
| `aos_agent_pause` | `aos-agent pause`／`continue` |
| `aos_agent_check` | `aos-agent check`（kernel 檢查＋agent 家、工具、權限牆） |
| `aos_agent_tools` | `aos-agent tools add` |
| `aos_agent_tools_edit` | `aos-agent tools ls／rm／alias／unalias` 與共用 info 編輯 |
| `aos_agent_tools_dev` | `aos-agent tools new／test／wrap-py`：造工具（骨架、照描述自動跑案例、Python 函式包成工具包），不需要 agent 家；wrap-py 的 `--describe-with-llm`（只寫提案檔）／`--describe`（照人看過的提案產包）（第三波 W3-2） |
| `aos_agent_tools_wrapcli` | （第三波 W3-2）`aos-agent tools wrap-cli CMD`：argparse 腳本靜態讀、其他指令解 `--help` 文字 → 工具包（`run` 把 JSON 組成 argv、不經 shell）；`--describe-with-llm` 只寫提案、`--spec` 照人看過的參數表產包 |
| `aos_agent_access` | 權限牆（access.json）讀驗與快照 |
| `aos_agent_access_cli` | `aos-agent access ls／set／rm／cwd／net` |
| `aos_agent_events` | 事件紀錄：`log/events.jsonl` 追加與去重讀取，`aos-llm call` 的 `log/usage.jsonl` |
| `aos_agent_context` | 送給模型的東西多大：`aos-agent context` 與 `talk /context` 共用的字數／token 粗估 |
| `aos_agent_compact` | 機械壓縮記憶：`aos-agent compact`、tick idle 自動壓縮、compact 申請、`history --archive`；`--summarize`（第三波 W3-2，只給人用）：模型濃縮封存摘要，機械檢查不過退回機械版 |
| `aos_agent_notes` | `aos-agent notes ls／show`：讀 `tools/notes/` 寫的 `wf-table/1` 筆記檔 |
| `aos_agent_persona` | `aos-agent persona show／set／append`：人格是信任資料，讀寫 `prompts/system.json`，不叫模型不進牢 |
| `aos_jail` | `aos-jail`：組 bwrap 參數並 exec |
| `aos_json_cli` | `aos-json`：人用的 JSON Pointer 改檔（get／set／del／append／merge），`--check-directives` 先驗才寫 |
| `aos_team_format` | 團隊共用格式（資料夾佈局、`team.json`、信、申請、任務單、問題讀驗）與共用 id／時間／寫檔 |
| `aos_team_requests` | 申請登記表：`kind → 處理函式`，郵差讀 outbox 帶 kind 的檔就叫 `handle()` |
| `aos_team_task` | 任務單（交接書）與狀態機，只有郵差寫，同一 `src` 重跑冪等 |
| `aos_team_ask` | 問人：成員 `ask_human` 建問題檔，人用 `aos-team answer` 投回答案 |
| `aos_team_cli` | `aos-team` 子命令分派表（模組、函式、哪一隊做、一句話） |
| `aos_team` | `aos-team init／start／stop／ls／rm`：照 team.json 建團隊與成員的家（模板）、列隊、拆隊 |
| `aos_team_ask_cli` | `aos-team wait ls／answer`：人看等他回答的問題、回答一題（往 outbox 放申請） |
| `aos_team_route` | 門房：`aos-team ask` 的前濾網，整句句型比對，命中就不叫模型；`route try` 只印判決；`tool` 規則經 aos-jail 關牢跑；落穿那行 route.log 記 `letter`（第三波 W3-2） |
| `aos_team_crystal` | （第三波 W3-2）`aos-team crystal` 固化建議：從 route.log＋領隊開的單找常落穿句型，機械產候選規則＋回測，只寫提案檔給人批；`--suggest-with-llm` 預設關 |
| `aos_team_mail` | `aos-team mail`：一信一行＋等人回答的題目、`--task` 連落穿給領隊的那封 |
| `aos_team_task_cli` | `aos-team task ls／show／cancel／reassign`：看任務單，取消／改派走申請 |
| `aos_team_post` | 郵差兼書記：`aos-team post` 每輪投信、收驗收工作結果、看停滯與期限、同步 SESSION-LOG／WAIT_USER；讀 outbox 時再驗路徑、cmd_ok 白名單、假信頭（`recheck`） |
| `aos_team_verify` | 驗收員：`aos-team verify` 照任務單 `done_when` 跑固定檢查器，回過／不過／檢查器壞；`wf_lint_strict` 與 `cmd_ok` 經 aos-jail 關牢（專案唯讀） |
| `aos_team_beat` | 心跳：`aos-team beat`／`routine`，照 `team/routines.json` 算誰到期、以開單方式派出 |
| `aos_team_score` | `aos-team score`：把六軸表能自動量的部分讀紀錄填好，只讀不叫模型 |
| `aos_team_lock` | 短期獨佔鎖：`lock` 工具與 `aos-team lock`，`team/locks/<名>.json`，acquire／release／ls 全非同步，逾時自動放 |
| `aos_team_spawn` | 生新成員（第三波 W3-1）：`kind: spawn` 郵差檢查＋開「[成員]」題，`aos-team spawn ls／approve`（改名冊、init、start、回覆） |
| `aos_team_toolsmith` | 模型造工具（第三波 W3-1）：`kind: tool_draft` 郵差生包＋牢裡 `tools test`，`aos-team tool ls／approve`（核 sha256、`tools add`） |
