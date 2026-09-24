← [w2c 報告](README.md)｜[回報](review-astra.md)

# 審查任務書：第二波 C 隊（申請類）（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／`lms`／localhost:1234／ollama。** 可以讀檔、跑單元測試：
`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_team_lock.py'`、
`-p 'test_agent_persona.py'`、`-p 'test_team_init.py'`（`ToolUnitTests`、`InitTests`；`TeamIntegrationTests` 開真 kernel＋bwrap，可略過）、
`-p 'test_agent_home.py'`、`-p 'test_agent_tick.py'`、`-p 'test_kernel_check.py'`（都只跑本地、不叫模型）。

**只審這次的改動**：`git diff 12d67d4 HEAD -- proto5`（第二波 C 隊的改動；基底是第一波收尾隊合進 main 之後）。前幾隊的審查已修，不用重提。

## 這次做了什麼（catalog.md〈T-access-req〉〈T-persona〉〈T-lock〉〈T-pool〉、plan.md 第二波表格 C 那列）

1. **T-lock**：新的申請種類 `kind: lock`（`lib/aos_team_lock.py` 的 `on_lock`，登記在 `aos_team_requests.KINDS`）。`team/locks/<名>.json` 只有郵差寫；`acquire`／`release`／`ls` 三種操作**全部非同步**（跟 `ask_human` 同路，寫 outbox → 郵差處理 → 回信），不是 catalog 草案設想的「立即回」。拿不到＝`TeamError('Busy', …)`，郵差照共同規則退信；逾時自動放（`expires_at`，過期後誰都能拿走／放掉）；同一持有者可以續租。工具 `tools/task/lock`；人的指令 `aos-team lock ls／acquire／release`（`aos_team_cli.COMMANDS` 多一行）。規範：`spec/team/lock.md`（新）、`spec/team/layout.md` 加一列。
2. **T-access-req**、**T-persona**：**不開新 kind**，直接借用既有的 `kind: ask`——`tools/task/access_request`、`tools/task/persona_propose` 把申請組成一句 `question`（含人同意後要跑的指令），走 `aos-team wait／answer`。**答案本身不會自動生效**：access 由既有的 `aos-agent access set` 套用；persona 由新的 `lib/aos_agent_persona.py`（`aos-agent persona show／set／append`，讀寫 `prompts/system.json` 的 `content`，不叫模型、不進牢）套用。規範：`spec/team/ask.md`〈借用〉一節（新）、`spec/agent/persona.md`（新）。
3. **T-pool**：工具檔加 `_pool`（`aos_agent_home.py._check_tool`：可省、非空字串）；`aos_agent_batch.py` 送件時 `pool = (tool or {}).get('_pool', run.info['tool_pool'])`；`aos_kernel_check.py.agent_tools` 多查每支工具的 `_pool` 在不在 K 的池裡、不是 kernel 池。規範：`spec/agent/info.md §3.3`、`spec/aos-agent/send.md §5.2`。這段照 [priority-and-shared-cpu 提案](../../2026-09-24-priority-and-shared-cpu/README.md) 做，kernel 派工／daemon 沒動。
4. **模型端 `routine_propose`**（T2 的 `on_routine` 郵差端本來就支援成員提案，缺模型工具）：`tools/task/routine_propose` 寄 `kind: routine, op: add|rm`；伺服器端邏輯沒改，走既有「成員提的開一題問人、人批准才授權」那條路。`spec/team/beat.md` 補一節。
5. **F 審查子單編號 bug**：`aos_team_task.render_review`／`on_review_result`、`tools/task/board`、`tools/task/review_result` 四處改成用**父單的原編號**（`review_of.indices`），不是子單裡從 0 重編（t5 試玩兩輪都踩到這個 bug）。連帶改了既有測試裡跟這個編號有關的 `i` 值（`test_team_format.py`、`test_team_post.py`、`test_team_init.py`、`test_team_t5.py`）。
6. **G 自動補 `wf_lint_strict`**：`tools/task/handoff` 在送件前，若 `goal／facts／workflow` 合起來的文字同時有 `.md` 與一個改寫用詞（白話、改寫、更好懂、更易讀、講白話），且 `done_when` 還沒有 `wf_lint_strict`，就機械補一條。**代裁**：選在這裡（handoff 工具層）而不是改門房規則——理由與取捨寫在 `tools/task/README.md` 最後一段。
7. 四個成員模板（`templates/lead`、`templates/worker`）的 `may`／`tools.only`／`system.md` 各加了新工具；`tools/task/task.json` 加了 4 支工具定義。

## 真跑（H）

四種申請各真跑至少一次（隔離的 kernel＋daemon＋`deepseek-chat`，跟共用的 `$HOME/aos-try` 分開，不影響其他並行的隊）：
`access_request`（worker-1 → 問人 → 同意 → 人跑 `access set` → `access ls` 看得到新掛載）、
`persona_propose`（worker-1 → 問人 → 同意 → 人跑 `persona append` → `persona show` 看得到新句子）、
`lock`（worker-1 acquire 成功 → worker-2 acquire 撞到 `Busy` 退信，信裡有持有者與到期時間）、
`routine_propose`（lead 提案 → 人批准 → 心跳照 `every 5m` 派出 → worker-1 做完 → `notes/count.txt` 真的被寫出來）。
**意外發現**：`access_request`／`persona_propose` 的問句裡寫了「你要跑的指令」（給人看的），但 worker-1 自己的模型看到問句裡的指令字串後，**主動想用自己的 `bash` 工具跑那行指令**（失敗，因為 `aos-agent` 不在牢裡的 PATH），最後老實回 BLOCKED 給人。工具本身沒有問題（牢確實擋住了、模型也沒有假裝成功），但問句的措辭可能該更明確地說「這是給**人**看的、不是給你自己跑的」。

## 請回答

1. **T-lock 的邊界**：`_check_lock_name` 的正規式（`[\w.\-/]{1,200}`＋擋 `..` 段、擋開頭 `/`）擋得住用鎖名做別的用途嗎（例如塞很長的字串當簡易留言板）？`ttl_seconds` 的上限 86400（24 小時）合理嗎？「同一持有者續租」會不會被拿來規避「逾時自動放」的設計意圖（例如寫一支自動續租的腳本）——這是不是該算作特性而非漏洞？
2. **T-lock 的非同步設計**：`ls` 也走非同步（不像 `board` 直接讀掛載的資料夾）是不是必要的？如果之後真的要給 `lock ls` 一個同步唯讀掛載（像 `board`），會撞到什麼（新的保留 mount 名字、B 隊的 access.json 契約）？
3. **T-access-req／T-persona 借用 `kind: ask`**：這樣設計會不會讓「一般問題」跟「申請」在 `aos-team wait ls` 裡混在一起、人分不清哪個要接著跑指令？要不要在問句前面加一個固定前綴（例如 `[access_request]`）方便掃描？
4. **F 審查子單編號**：改完之後，`review_result` 工具本地的 `want` 檢查（用 `review_of.indices`）跟伺服器端 `on_review_result` 的 `want`（同樣用 `indices`）有沒有算兩次、算法一致嗎？有沒有漏掉哪個地方還在用舊的 0 起算假設（例如審查完成後父單 `history` 記錄的顯示、`_results_text`）？
5. **G 自動補 lint 的判法**：純文字比對（`.md` ＋ 關鍵字）有沒有明顯的假陽性／假陰性（例如 goal 提到「不要改成更白話」卻被誤判、或改的明明是 `.py` 檔案但 facts 裡提到某個 `.md` 說明文件）？要不要緊一點（例如只看 `workflow` 欄位）？
6. **T-pool**：`aos_kernel_check.py` 新加的 `_pool` 檢查會不會跟既有的 `tool_pool` 檢查重複報錯／漏報？工具檔 `_pool` 寫成 kernel 保留池名時的錯誤訊息夠不夠清楚？
7. 規範（`lock.md`、`persona.md`、`ask.md`、`beat.md`、`info.md`、`send.md`、`tasks.md`）跟程式對不對得上；教程 08 新增的〈申請〉一節的指令跟輸出（如果你想像著跑一遍）合不合理。

## 格式

**必修**（不改會做錯、可被濫用、或規範與程式不符的；每條：檔、函式、怎麼觸發、建議改法；M1、M2…）、**建議**（S1…）、**確認沒問題的**（簡短）。
