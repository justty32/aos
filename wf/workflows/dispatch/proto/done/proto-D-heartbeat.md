# 任務：heartbeat on aos——`core/tick`、`every_ms`、登記 CLI、這個 repo 自己當第一個世界

> 交接書是唯一契約。協定 [PROTOCOL](../PROTOCOL.md)；前三隊報告在 [reports](../reports/)。前置：隊 C（[proto-C-consolidate](proto-C-consolidate.md)）已落地——`.aos/every/`、cwd 即世界、`aos say/listen/state` 頂層指令、舊小專案已刪。

## 背景與唯一目標

使用者 2026-08-30：「先把 wf 的 kernel 實現，先以 heartbeat 為目標」。heartbeat flavor 原文在
`~/repo/workflows/flavors/heartbeat/`（README、tick.md、routines.md、schedule.md，**先全部讀完**），
本 repo 的實例是 `wf/workflows/{tick,routines,schedule}.md` 與 `.claude/commands/wf-tick.md`。
它自己寫「本包不是排程器，引擎一律外借」——放到 aos 上這句要消失：**`aos run` 就是引擎、`every/` 就是心跳、資料夾裡的 agent 就是 tick 醒來的那個人。**
使用者已拍板：(1) 到期但要判斷的事丟給資料夾裡的 agent（`aos say`）；(2) **這個 repo 自己當第一個世界 dogfood**。
**唯一目標**：在 aos repo 根目錄 `aos heartbeat init && aos run --step 0` 後，登記的常規事務與一次性行程會**到期自動投遞執行**、log 有紀錄；`wf/workflows/{tick,routines,schedule}.md` 改為以 aos 為引擎與清單真源。

## 團隊（你是 Opus 隊長）

工作量押給 codex（`codex exec -m gpt-5.6-sol -C /home/lorkhan/repo/simple_tools/aos --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；sol／terra／luna 皆可，最多 4 條、量力而為）。**先派 Fable 規劃者**（`Agent(model="fable")`）用一輪把 §資料格式 與 `aos tick` 的判定規則落成 `core/tick/README.md`（含逐欄定義、時機分區怎麼表達、錯過很久的規則），你核過再派 codex 四線：① loop `every_ms`；② `core/tick` 核心（tick 判定＋投遞＋log）；③ 登記 CLI（routine／schedule add/ls/rm、heartbeat init）；④ markdown 端＋dogfood。③④ 可等②的介面定了再開。隊長寫任務書、審 diff、跑 ctest、commit；不親自寫實作。

## 資料格式（調度者代裁，Fable 可細化、不可推翻）

- 清單住 `<folder>/.aos/heartbeat/`：`routines.json`、`schedule.json`（**`wf-table/1` 契約**，見 `wf/workflows/common/data-files.md`，`wf/tools/tabledb.py` 要讀得到）、`log.md`（append-only，一次心跳一行）。
- routines 一列：`id`、`kind`（`interval`｜`slot`）、`every`（interval 用，如 `7d`／`30m`）、`slot`（slot 用：`HH:MM` 起點＋星期遮罩，最小可行即可）、`last_run`（ISO8601 或空）、`run`（`{"argv":[...]}` 或 `{"ask":"一句給 agent 的話"}`）、`note`。
- schedule 一列：`id`、`at`（絕對時刻含日期，時區 Asia/Taipei）、`run`（同上）、`note`。
- `every/*.json` 新增可選欄 `every_ms`（整數）：loop 只在「距該檔上次被投遞 ≥ every_ms」時才投；上次投遞時間記在 `state.json` 或 `.aos/every/.last/<stem>`（你裁，記進隊長裁決）。沒有此欄＝每回合投（維持隊 C 行為）。

## 工作

1. 讀 heartbeat 原文四檔、本 repo 三個工作流檔、PROTOCOL、`core/loop`／`core/agent` README、`wf/workflows/common/data-files.md`。
2. Fable 出 `core/tick/README.md` 規格。
3. ① `core/loop`：`every_ms`；`aos run` 摘要行標出 every 投了幾條。
4. ② `core/tick`：`aos tick [folder]`——判當地時間（`TZ=Asia/Taipei`，可由 `.aos/heartbeat/config.json` 覆寫）→ 掃兩張表 → 到期項：`argv` 投 inbox（id `hb-<id>-<turn>`）、`ask` 走 `aos say`（沒有 agent 時 log 記「無 agent，跳過」）→ interval 項更新 `last_run`、schedule 項刪列 → log 一行。**錯過很久**（schedule 的 `at` 早於現在超過 `config.missed_after`，預設 6h）：不自動做，改成 `ask` agent「這項錯過了，補做還是跳過」並刪列（沒 agent 就 log 記下、刪列）。`aos tick --dry-run` 只印會做什麼。**tick 本身不叫 LLM。**
5. ③ 登記面：`aos heartbeat init [--interval 30m]`（建 heartbeat/ 與 `every/tick.json`，argv `["aos","tick"]`）、`aos routine add --every 7d [--ask "…" | -- argv…] [--note]`／`ls`／`rm <id>`、`aos schedule add --at "2026-09-01 17:00" [--ask|-- argv] `／`ls`／`rm`。`ls` 印表給人看（含「下次到期」）。
6. ④ markdown 端與 dogfood：
   - `wf/workflows/routines.md`／`schedule.md`：「A. 登記」改成呼叫 `aos routine add`／`aos schedule add`；live 清單段改為指向 `.aos/heartbeat/*.json`（`aos routine ls` 看）；「B. 執行」改為「`aos tick` 機械判定並投遞；agent 收到 `ask` 才動腦」。**原意不變**（鐵律 2 授權來源那幾句保留）。
   - `wf/workflows/tick.md`：主體改為 `aos tick`，說明引擎就是 `aos run`。
   - `.claude/commands/wf-tick.md`：改成薄殼——確認本 repo 的 `aos run` 在跑（`state.json` 有 `turn` 且最近更新），沒在跑就告訴使用者怎麼開；不再自己 `/loop`。
   - **dogfood**：`.gitignore` 加 `/.aos/`；在 repo 根 `aos heartbeat init --interval 30m`，把 routines.md 現有那條「每 7 天跑 `wf/tools/wf-lint.sh --strict wf .claude/commands`」用 `aos routine add` 登記（`last_run` 填 2026-08-30），並在 `docs/usage.md` 或 `core/tick/README.md` 寫「怎麼開這個 repo 的心跳」三行。**不要**把 `aos run` 留著常駐——驗完就停，開常駐是使用者的事。
7. code map、各 README；測試：every_ms 至少一案、tick 判定（到期／未到期／錯過）至少三案（時間可注入，不 sleep）、schedule 做完刪列一案。
8. commit 到 main（可分多個）。

## 硬性限制

- **禁區**：`reference/`、`app/`、`core/llm/`、`core/agent/`（只讀；要 `aos say` 就 exec 子行程或連 `aos::agent` 既有 API，不改它）、`wf/` 除下列外不碰：`wf/workflows/{tick,routines,schedule}.md`、`.claude/commands/wf-tick.md`、`wf/workflows/common/code-map.md`、`wf/WORKFLOWS.md`（若派發表那三列要改一個字）、本資料夾。
- **`git add` 只加明確路徑**；**不 push**；不取鎖、不開 GUI、不 load／unload LM Studio。
- 相對時間解析（「今晚 8 點」）**不做**；只收 `YYYY-MM-DD HH:MM` 與 `Nd/Nh/Nm`。
- 邊緣狀況跳過；小裁決記「隊長裁決」。只有本檔或 PROTOCOL 矛盾才 BLOCKED。

## 交付

| 產物 | 路徑 |
|---|---|
| tick 小專案 | `core/tick/`（README、tests） |
| loop 擴充 | `core/loop/`、`PROTOCOL.md` §1 every 那列補 `every_ms` |
| markdown 端 | `wf/workflows/{tick,routines,schedule}.md`、`.claude/commands/wf-tick.md` |
| dogfood | `.gitignore`、本 repo `.aos/heartbeat/`（不進版控）、開心跳三行說明 |
| 回報 | `wf/workflows/dispatch/proto/reports/D.md` |

## 驗收（就這 7 條）

1. 根目錄 build＋ctest 全綠。
2. 空資料夾 `W`：`aos heartbeat init --interval 1s` → `.aos/every/tick.json` 含 `every_ms: 1000`、`.aos/heartbeat/{routines,schedule}.json` 存在且 `wf/tools/tabledb.py` 讀得到。
3. `W` 內 `aos routine add --every 2s -- sh -c 'date +%s >> /tmp/hb-r'`，`aos run --step 40 --interval 100`（4 秒）：`/tmp/hb-r` 有 **2 行**（±1），`routines.json` 的 `last_run` 被更新，`log.md` 有對應行。
4. `aos schedule add --at "<現在+2秒>" -- touch /tmp/hb-s` → 跑 3 秒 → `/tmp/hb-s` 存在且 `schedule.json` 該列已刪。
5. `W` 內 `aos agent init` 後 `aos routine add --every 2s --ask "報一次時間"` → 跑 3 秒 → `.aos/agents/<name>/say/` 或 log.md 出現那句話（LLM 有沒有回不驗）。
6. `aos tick --dry-run` 對一條 `at` 早於現在 7 小時的 schedule 印出「錯過→ask」而非執行。
7. 本 repo 根：`aos routine ls` 列出 wf-lint 那條、下次到期 2026-09-06；`git status` 不出現 `.aos/`。

## 回報

最後一則訊息＝ `reports/D.md` 摘要（≤ 30 行）＋終局 STATUS。

## 隊長裁決

（隊長追加）
