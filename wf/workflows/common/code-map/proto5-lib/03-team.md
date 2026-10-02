← [proto5/lib 模組](../proto5-lib.md)（分檔 3/3）｜[上一份](02-llm-agent.md)

| 模組 | 職責 |
|------|------|
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
