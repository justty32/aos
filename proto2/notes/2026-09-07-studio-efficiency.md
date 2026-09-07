# 2026-09-07 工作室提效：讓 LLM 少做事

← [play/README](play/README.md)｜對照 [studio-3](play/2026-09-07-studio-3.md)、[studio-4](play/2026-09-07-studio-4.md)

## 量出來的浪費（4b 這局，qwen2.5:14b＋qwen3:32b，600k 預算）

| 角色 | LLM 輪 | 平均一輪 prompt | 工具數 | schema 字數 | 真正在做事的輪 |
|---|---:|---:|---:|---:|---|
| pm | 26 | 8,176 tok | 50 | 13,439 | 5 輪派工；16 輪讀信／等信；4 輪撥額度 |
| chief | 21 | 8,776 tok | 64 | 17,895 | 12 輪寫／改檔；3 輪讀信；2 輪跑測試 |
| owner | 11 | 5,707 tok | 47 | 12,579 | 0；全在讀信、6 次讀錯 id |
| sales | 3 | 3,498 tok | 32 | 7,862 | 1 輪轉信、1 輪回甲方 |

- **prompt 占 96% 的 token**，回答只占 4%。prompt 裡一半以上是工具 schema，其餘是人格＋包的說明＋越滾越長的對話史。
- **讀一封信要 2～3 輪**（通知→inbox_list→inbox_read），一封信 ≈ 20k token。
- **撥一次額度要 4 輪**（chief 喊→PM 讀→PM grant→PM 回信確認），≈ 35k token，而且小模型常把 grant 寫成文字沒真的做。
- **mail_send 之後另一輪 mail_wait**：PM 6 次。
- 首席用 thinking 模型，一輪 60～90 秒，一輪只做一個 edit，edit 還常對不上原文。

## 原則

**LLM 只做要判斷的事；能寫死的流程全部做成工具，一個工具一次做完一串動作。** 每個角色只拿它那幾個工具，信直接進 prompt，額度自動撥，回報、驗收、交付都是固定格式的工具。

## 要做的事（分四包，可以並行）

### A. 核心（Claude 主線自己做；動 `aos_agent.py`／`aos-agent`／`presets/studio/team.json`）

1. **工具白名單**：`tools.json` 加 `"only": ["inbox_read_all", "mail_send", …]`，只有列到的工具才送給模型（其他仍可載入、不送 schema）。preset 每個成員給自己的 `only`。
2. **信直接進 prompt**：`tools.json` 加 `"inline_mail": ["*"]`（或列來源）。列到的來源的信不再只通知「你有新信」，而是像 `user` 一樣整封接進記憶、當場搬進 `read/`。工作室全員 `"*"`。
3. **額度自動撥**：`team.json` 加 `"auto_grant": {"from": "pm", "tokens": 50000, "max_per_member": 300000}`。成員凍住而且有工作在等時，閘門直接從 `from` 的額度撥一筆給他、記一筆 `kind: auto`，當格解凍，不寄信不叫模型。撥不出來（`from` 也不夠、或到了 `max_per_member`）才走原本的喊主管。
4. **mail_send 順便等**：`mail_send` 加 `wait: true`（或 `expect_reply`），寄完直接睡到回信，不必再一輪 `mail_wait`。
5. preset 重排：每人只掛用得到的包，`only` 精簡到 6～12 個工具。owner 只留升級用（不在主鏈上）。

### B. `studio` 流程包（opus agent；新檔 `packs/studio.py`、`tests/studio_flow.sh`、`docs/studio-flow.md`，不動別的檔）

單子與任務都是檔案，狀態機寫死在工具裡：

```
team/orders/<order_id>.json   {id, task, budget, acceptance, status, plan, tasks:[task_id…], history:[…]}
team/tasks/<task_id>.json     {id, order, title, spec, owner, files, status, report, tests, qa}
status：order = received → planned → in_progress → qa → delivered | failed
        task  = assigned → done → passed | failed
```

工具（`run(name, args, ctx)`，全部回短 JSON；找不到單／越權就回 `{"ok": false, "error": …}`）：

| 工具 | 誰用 | 一次做完 |
|---|---|---|
| `order_accept(order_id?, note?)` | sales | 把 `inbox/user/` 最新那張訂單（或指定 id）開成 `team/orders/` 的單、整張單一封信寄給 pm、對甲方回一張固定格式的確認單（`ctx.reply`：單號、範圍、預算、下一步）。 |
| `plan_set(order_id, architecture, tasks=[{title, spec, owner, files}])` | chief | 寫入單子的 plan、每個 task 建一個 `team/tasks/` 檔（status assigned）、寄一封摘要給 pm。 |
| `task_assign(task_id, to?, spec?, tokens?)` | pm | 把任務交給某成員：先確定他有額度（呼叫 `team_grant`，不夠就從自己撥 `tokens` 或 50000），把整份 spec 一封信寄給他，單子 status → in_progress。 |
| `task_report(task_id, summary, files=[…], test_cmd?)` | chief／dev | 任務做完：記 files、有 `test_cmd` 就在 `team/projects/<order_id>/` 跑一次把結果存進任務檔，status → done，寄摘要（含測試結果）給 pm 與 qa。 |
| `qa_run(task_id 或 order_id, command)` | qa／pm | 在專案目錄跑指令，把 exit／stdout 尾巴存進任務檔的 `tests`，回結果。 |
| `qa_verdict(task_id, passed: bool, evidence)` | qa | task status → passed／failed，寄 pm；整張單所有 task 都 passed 就把單 status → qa。 |
| `deliver(order_id, summary)` | pm | 把所有 task 的 files 複製到 `team/files/final/<order_id>/`，單 status → delivered，寄 sales 一封固定格式交付單（檔案清單、測試結果、花了多少 token——從 `team_status_of` 拿）。 |
| `order_status(order_id?)` | 全員 | 單子＋任務的精簡現況（狀態、負責人、檔案、最近三條 history）。 |
| `order_fail(order_id, reason)` | pm | 單 status → failed，寄 sales。 |

- `on_system_prompt(ctx)`：把「你手上的單／任務」壓成 2～3 行放進 prompt（單號、狀態、你負責的 task 與它的 spec 前 200 字），模型不必再去讀檔。
- `on_idle` 不做事（不要像 review 包那樣自己寄信給自己）。
- sales 收到 pm 的交付信後只要 `ctx.reply` 給甲方；`deliver` 已經把交付單文字準備好放在信裡，sales 照抄即可。
- 測試用 `test.sh` 的假 server（user 訊息寫 `CALL 工具 {json}` 就會照做），走完 order_accept → plan_set → task_assign → task_report → qa_run → qa_verdict → deliver 一整條，每一步查檔案狀態。
- 文件大白話，README 表加一行。

### C. 人格重寫（sonnet agent；只動 `presets/studio/*/system-prompt.json`）

每個人格縮到 6～10 行大白話，只講：你是誰、你收到什麼就做什麼（用哪個工具，一句話一步）、不要做什麼。工具名照上面 B 的表。固定五行回報那段刪掉（回報改由工具產生）。

### D. 包的說明與工具描述瘦身（sonnet agent；只動 `packs/*.py` 的 `PROMPT`／`TOOLS` 字串與 `docs/`）

- 每個包的 `PROMPT` 縮到一兩句（或空字串——工具描述本身就夠）。
- 每個工具 `description` 一句話、參數 `description` 十個字內；schema 別放 `oneOf`、例子、長句。
- 目標：全部 16 包的 `TOOLS` JSON 總字數減半。不改工具名、參數名、行為。`bash proto2/test.sh` 要全綠。

## 預期

PM 一張單從 26 輪降到 ≤ 8 輪（接單 1、派工 1～3、收回報 1～2、交付 1）；每輪 prompt 從 8k 降到 3k 以下。整張 todo.py 單目標 < 100k token。
