# proto5/lib — team（54 支）

← [proto5/lib README](../README.md)｜上一份：[agent](agent.md)｜下一份：[公司與市場](company.md)

一檔一行（新增模組照這個格式插一行）：

| 檔 | 職責 |
|---|---|
| [`aos_team_format.py`](../aos_team_format.py) | 團隊共用格式（spec/team/）：資料夾佈局、名冊 `team.json`、信、申請、任務單、問題的讀驗，以及共用的 id／時間／寫檔。入口＋匯出層（別的模組一律 `import aos_team_format as fmt`），自己只留命令列驗檔 |
| [`aos_team_format_base.py`](../aos_team_format_base.py) | 團隊格式的底：型別名與保留名、id 規則、上限與預設、`TeamError`／`bad`、資料夾佈局 `Layout`、欄位小驗證 |
| [`aos_team_format_io.py`](../aos_team_format_io.py) | 團隊格式的時間、id 與寫檔：現在時間、解析與短格式、新 id、原子寫／只准新建、讀 JSON、列 JSON 檔 |
| [`aos_team_format_cmd.py`](../aos_team_format_cmd.py) | 名冊裡人寫的設定片段：`cmd_ok` 指令與白名單（pattern、唯讀掛載）、對白名單、spawn 設定、mounts 與工具條目欄位 |
| [`aos_team_format_roster.py`](../aos_team_format_roster.py) | 名冊 `team.json`：讀驗、名冊鎖、讀名冊、專案資料夾、按模板列成員 |
| [`aos_team_format_letter.py`](../aos_team_format_letter.py) | 信、申請、任務單與問題的讀驗：信、`done_when`、各 kind 申請欄位、outbox 檔、信頭與投遞去重、下一個編號 |
| [`aos_team_format_template.py`](../aos_team_format_template.py) | 模板與門房規則：內建模板、模板 may 與 spawn 政策、誰能寄給誰、`template.json` 與 `routes.json` 讀驗 |
| [`aos_team_requests.py`](../aos_team_requests.py) | 申請登記表：`kind → 處理函式`，郵差讀到 outbox 裡帶 `kind` 的檔就叫 `handle()`；別隊新增 kind 在這裡加一行 |
| [`aos_team_task.py`](../aos_team_task.py) | 任務單（交接書）與狀態機：只有郵差寫，處理函式改單子並回「後續動作」清單；同一 `src` 重跑冪等。這支留各 kind 的處理函式（開單、取消／改派、審查、信件對單子、期限） |
| [`aos_team_task_base.py`](../aos_team_task_base.py) | 任務單的底：常數、讀寫與列單、單子的文字（派工信、審查信、驗收結果）與信件效果 |
| [`aos_team_task_machine.py`](../aos_team_task_machine.py) | 任務單的狀態機：`apply` 照事件改單子並回後續動作、重試、`step` 讀單→apply→寫回 |
| [`aos_team_ask.py`](../aos_team_ask.py) | 問人：成員 `ask_human` 寄 `kind=ask` 建問題檔，人用 `aos-team answer` 把答案投回發問者 |
| [`aos_team_cli.py`](../aos_team_cli.py) | `aos-team` 的分派表：子命令 →（模組、函式、哪一隊做、一句話），還沒做的印「還沒做（第 N 隊）」退 1 |
| [`aos_team.py`](../aos_team.py) | `aos-team init／start／stop／ls／rm`：照 team.json 建團隊與成員的家（模板）、列隊、拆隊 |
| [`aos_team_ask_cli.py`](../aos_team_ask_cli.py) | `aos-team wait ls／answer`：人看等他回答的問題、回答一題（往 outbox 放申請） |
| [`aos_team_route.py`](../aos_team_route.py) | 門房：`aos-team ask` 的前濾網，整句句型比對，命中就不叫模型；`route try` 只印判決、什麼都不做（第二波 A 隊）；`tool` 規則經 aos-jail 關牢（專案預設唯讀，第二波 B 隊）；落穿那行記 `letter`（第三波 W3-2） |
| [`aos_team_crystal.py`](../aos_team_crystal.py) | （第三波 W3-2，spec/team/crystal.md）`aos-team crystal` 固化建議：落穿句型統計、機械候選規則＋回測，只寫提案檔；`--suggest-with-llm` 預設關。這支留主體 `crystal`、印法與命令列 |
| [`aos_team_crystal_stats.py`](../aos_team_crystal_stats.py) | crystal 的句型與統計：句子→骨架與正規式、讀門房 log 與信、對上任務單、落穿句型歸類 |
| [`aos_team_crystal_rules.py`](../aos_team_crystal_rules.py) | crystal 的機械候選規則：生規則與開單內容、候選檢查、內建反例篩範圍、組回規則檔並回測 |
| [`aos_team_crystal_llm.py`](../aos_team_crystal_llm.py) | crystal 的 `--suggest-with-llm`：叫模型提候選（預設關），回來照機械規則再篩 |
| [`aos_team_mail.py`](../aos_team_mail.py) | `aos-team mail`（第二波 A 隊從 `aos_team_post.cmd_mail` 接手，讀法與一行印法仍用郵差那份）：多列等人回答的題目（`ASK q-0001`，答完先顯示答案）；`--task` 連落穿給領隊的那封一起列 |
| [`aos_team_task_cli.py`](../aos_team_task_cli.py) | `aos-team task ls／show／cancel／reassign`：看任務單，取消／改派走申請 |
| [`aos_team_post.py`](../aos_team_post.py) | 郵差兼書記（tool-era T2，spec/team/post.md）：`aos-team post` 每輪投信、收驗收工作結果、看停滯與期限、同步 SESSION-LOG／WAIT_USER；崩在任何一步重跑同一行都收得回來，不叫模型。這支留 `Post` 本體（一輪、投遞紀錄、投遞、outbox）、指令與 kernel 登記 |
| [`aos_team_post_base.py`](../aos_team_post_base.py) | 郵差共用常數與小工具：紀錄型別、逾時與次數、崩潰測試點、時區、行程還在不在、動作編號、團隊識別、outbox 搬檔 |
| [`aos_team_post_recheck.py`](../aos_team_post_recheck.py) | 郵差的再驗一次：條目路徑不准跳出專案、工作流入口、`cmd_ok` 白名單、不准假冒信頭 |
| [`aos_team_post_text.py`](../aos_team_post_text.py) | 郵差的字：信的摘要與截斷、一行印法、書記改寫 SESSION-LOG／WAIT_USER 的受管區塊 |
| [`aos_team_post_jobs.py`](../aos_team_post_jobs.py) | 郵差的驗收工作：混入類別 `_PostJobs`（交驗收、起 kernel 工作、收結果）、結果檔格式檢查、申請 `reverify` |
| [`aos_team_post_watch.py`](../aos_team_post_watch.py) | 郵差的停滯與書記：混入類別 `_PostWatch`（停滯與期限、成員健康、通知、書記同步） |
| [`aos_team_verify.py`](../aos_team_verify.py) | 驗收員（tool-era T2，spec/team/verify.md）：`aos-team verify` 照任務單 `done_when` 跑固定檢查器，每條回過／不過／檢查器壞三種；`judge` 條目不歸這裡。第二波 B 隊：`wf_lint_strict` 與新條目 `cmd_ok`（team.json 白名單裡的專案指令）經 aos-jail 關牢、專案唯讀。這支留檢查器登記表 `CHECKS`（字串指回這支）、逐條跑、`verify` 與命令列 |
| [`aos_team_verify_checks.py`](../aos_team_verify_checks.py) | 驗收員的固定檢查器（直接讀專案檔）：三態與錯誤、路徑關在專案裡、file_exists、table_filled、contains 類、max_bytes、wf_residue |
| [`aos_team_verify_jail.py`](../aos_team_verify_jail.py) | 驗收員關牢跑的檢查器：組 aos-jail 參數、牢裡跑收輸出尾巴、`wf_lint_strict`、`cmd_ok` |
| [`aos_team_beat.py`](../aos_team_beat.py) | 心跳（tool-era T2，spec/team/beat.md）：`aos-team beat` 照 `team/routines.json` 算誰到期、以開單方式派出，寄件身分是保留名 `beat`；`aos-team routine ls／add／rm`。這支留心跳本體 `Beat` 與指令 |
| [`aos_team_beat_schedule.py`](../aos_team_beat_schedule.py) | 心跳的時間表：欄位與單位、崩潰測試點、時區、every／daily／once 解析、`Schedule` 算下一次到期 |
| [`aos_team_beat_routines.py`](../aos_team_beat_routines.py) | 心跳的例行表 `team/routines.json`：讀、申請 routine 的驗與處理（`on_routine`）、批准了沒 |
| [`aos_team_score.py`](../aos_team_score.py) | `aos-team score`（tool-era T5，spec/team/score.md）：把六軸表（axes.md §4 團隊欄）能自動量的部分讀 `log/events.jsonl`／`usage.jsonl`／郵差投遞紀錄／任務單填好；只讀、不叫模型、不寫檔。這支留六軸常數、`collect`、印法與命令列 |
| [`aos_team_score_read.py`](../aos_team_score_read.py) | score 的讀檔：時間字串、`Reader`（數跳過的行與檔）、成員 events／usage、任務單、投遞紀錄、真跑紀錄 |
| [`aos_team_score_calc.py`](../aos_team_score_calc.py) | score 的門檻與小算法：各軸分數門檻、任務單起訖與開著的時段、領隊那封信、done_when 條數、時窗與秒數印法 |
| [`aos_team_cost.py`](../aos_team_cost.py) | 財務部（09-25，spec/team/cost.md）：`record()` 掛在 `aos_llm_call.call` 與 `aos_llm_ask.ask`，每次呼叫追加一筆到 `$AOS_COST_HOME/ledger.jsonl`（沒設不記、寫失敗吞掉）；`aos-team cost`（分組表、`budget`、`import` 回填 usage.jsonl）；公司帳戶（`account_open`／`account_grant`／`balances`／`account_of`，花到 0＝倒閉）；郵差 `budget_hold` 與 `ls` 第一行問它超了沒。這支留命令列 `cmd_cost` |
| [`aos_team_cost_ledger.py`](../aos_team_cost_ledger.py) | 財務部的帳本：帳本家、價格表與模型家族、`record` 記一筆、讀帳與篩選、分組加總、`import` 回填 |
| [`aos_team_cost_account.py`](../aos_team_cost_account.py) | 財務部的公司帳戶：開戶、撥款、轉帳、餘額（花到 0＝倒閉）、團隊資料夾屬於哪個帳戶 |
| [`aos_team_cost_budget.py`](../aos_team_cost_budget.py) | 財務部的預算與名額：`budget.json` 讀驗、用量對預算、超了沒（退件理由、`ls` 第一行）、cpu 名額那行 |
| [`aos_team_hr.py`](../aos_team_hr.py) | （HR 部 09-25，spec/team/hr.md）`aos-team hr`：薪資表／政策讀寫、`hr trial`（複製團隊換模型→跑任務集→`score --json`＋可插評分指令→記 `trials.jsonl`→調薪）、`hr set`（改名冊與家的 `llm.model`、重啟）、正式員工人頭與全公司 cpu 計數（init／start／spawn 的擋點）；HR 自己不叫模型。這支留 `trial`、列試用紀錄與命令列 |
| [`aos_team_hr_book.py`](../aos_team_hr_book.py) | HR 家：等級與規模常數、預設政策、家與鎖、`policy.json`、薪資表、試用紀錄 `trials.jsonl` |
| [`aos_team_hr_count.py`](../aos_team_hr_count.py) | HR 的人頭與名額：成員用哪個模型、登記團隊、正式員工人頭與上限、全公司 cpu 計數與上限、擴張理由 |
| [`aos_team_hr_members.py`](../aos_team_hr_members.py) | `aos-team hr ls／set`：列成員的模型、等級與薪資；改名冊與家的 `llm.model`／正式與否並重啟 |
| [`aos_team_commons.py`](../aos_team_commons.py) | 跨團隊公共資料夾 commons（09-25，spec/team/commons.md）：成員投稿經自己團隊的郵差送進 `commons/inbox/`，圖書館員團隊的郵差機械審、像既有條目才叫模型判，入庫寫條目與索引；不叫模型。這支留匯入 playbook（`playbook_items`）與人的指令 `cmd_commons` |
| [`aos_team_commons_base.py`](../aos_team_commons_base.py) | commons 的底：常數與上限、在哪與誰開（名冊設定、圖書館員）、資料夾 `Commons` 與索引印法 |
| [`aos_team_commons_ingest.py`](../aos_team_commons_ingest.py) | commons 的投稿檢查、入庫與查閱：欄位與附檔、內容 sha、像不像、slug、入庫與移除、搜尋 |
| [`aos_team_commons_post.py`](../aos_team_commons_post.py) | commons 的郵差兩端：投稿端（`on_contribute`、收結果）與圖書館員端（`desk`、`on_commons_write`、`post_round`） |
| [`aos_team_lock.py`](../aos_team_lock.py) | `lock` 工具與 `aos-team lock`（第二波 C 隊，spec/team/lock.md）：短期獨佔一個檔或資料夾的名字，申請 `kind: lock`（acquire／release／ls，全部非同步）記在 `team/locks/<名>.json`，逾時自動放 |
| [`aos_team_spawn.py`](../aos_team_spawn.py) | `spawn_member` 工具與 `aos-team spawn`（第三波 W3-1，spec/team/spawn.md）：成員申請生新成員，`kind: spawn`；預設不用人批（郵差查過名冊直接生），名冊可設成要開題問人；`spawn ls／approve`。這支留真的生、郵差端 `on_spawn`、開題與人端指令 |
| [`aos_team_spawn_check.py`](../aos_team_spawn_check.py) | spawn 的紀錄與檢查：紀錄資料夾與讀取、問題狀態與批准字、申請欄位驗、能不能生（名冊、模板、may、人頭）、新成員的 spawn 設定 |
| [`aos_team_toolsmith.py`](../aos_team_toolsmith.py) | `tool_draft` 工具與 `aos-team tool`（第三波 W3-1，spec/team/toolsmith.md）：成員寫工具草稿，`kind: tool_draft`；郵差在牢裡跑附的例子，過了開題，人 `tool approve` 才裝（核 sha256）。這支留生工具包與牢裡試跑、郵差端與人端 |
| [`aos_team_toolsmith_check.py`](../aos_team_toolsmith_check.py) | 工具草稿 `tool_draft` 的欄位驗：名字、參數表（JSON Schema 子集）、程式碼、附的例子、整份申請 |
