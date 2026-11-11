# 02 todo：待辦清單（設計稿，未施工）

← [new-tools](README.md)｜上一份：[01 grep／glob](01-grep-glob.md)｜下一份：[03 MCP client](03-mcp-client.md)

## 一句話結論

做**一支**工具 `todo`，用 `op` 分 `ls`／`set`／`add`／`mark` 四種動作；清單存在這支工具自己的小格 `<agent stack>/tools/todo/todo.json`（第一次寫才建，照 tool-cells-lazy）。每次寫完都把整張清單印回來，腦一定看得到現況。**history 被摘要之後還看得到**的關鍵是「每輪開場自動帶進 prompt」——這會動到 fsm 範本的 `brain.py`，列成待裁 T1，推薦照 `--knowledge` 的做法加一個 `--todo NAME`、清單非空才帶。子 agent、`do_task`（現 `thought`）各有自己的 stack，所以清單**天生各自獨立**，不另做共用。

## 現況

- 長任務現在只能靠腦自己在回話裡記步驟；`self_history summarize` 把舊訊息換成一句摘要後，步驟就跟著沒了（摘要是腦自己寫的，常漏）。`brain.py --history task` 也只帶「最後一則 user 之後」的訊息。
- stack 是 agent 的私有狀態、不被 history 操作碰到——清單放這裡就不會被摘要摘掉，但**放著不等於看得到**：腦得記得去叫 `ls`，或由開場帶進去。

## 參考市面

| 市面 | 做法 | 取 | 不取、為什麼 |
|---|---|---|---|
| Claude Code `TodoWrite` | 一支、每次整張重寫（`content`、`status`、`activeForm`）；狀態存在 session；compact 後、以及清單閒置太久時，harness 用 system-reminder 把清單塞回 context | 狀態三種 `pending`／`in_progress`／`completed`（模型訓練時最常見）；「自動帶回 context」的想法 | 只能整張重寫——小模型重寫 10 項常漏掉一兩項，所以另給 `add`、`mark`；`activeForm`（給 UI 的進行式）不要 |
| Codex `update_plan` | 一支、整張重寫（`step`、`status`）＋一句 `explanation`；計畫顯示在 UI，不另外塞回 prompt，靠它本來就在 history 裡 | 「一次最多一個 in_progress」寫進說明 | `explanation` 不要（那是給人看 UI 的；aos 的腦要說話直接說）；只靠 history 正是要解決的問題 |
| OpenHands | 有 task tracker 類工具（清單存檔、可 view／plan） | 存成檔、讀寫分開成動作 | — |

## 介面草稿

一支 `todo`，stdin 一份 `{"op": …}`：

| op | 參數 | 做什麼 |
|---|---|---|
| `ls` | — | 印清單 |
| `set` | `items`：字串陣列，或 `[{"text", "status"?}]` | 整張換掉（`[]`＝清空）；沒寫 status＝`pending` |
| `add` | `text`（必要）、`after`（選填，接在第幾項後面；沒給＝最後） | 加一項 |
| `mark` | `n`（第幾項，從 1）、`status` | 改一項的狀態 |

狀態：`pending`、`in_progress`、`completed`。拿掉一項＝`set` 整張（不另做 `rm`，避免編號錯位刪錯）。

stdout（每個 op 都印整張）：

```
1 [x] read the config format
2 [>] write the parser
3 [ ] add tests
... 1 of 3 completed
```

`[x]` completed、`[>]` in_progress、`[ ]` pending；空的＝`... empty (use set or add)`。`ls` 加 `"json": true`＝`{"items": [{"n", "text", "status"}], "counter_completed", "updated_at"}`（同 `ls`／`agents_ctl` 的口徑）。

錯誤代號：`ArgumentsBad`、`OpUnknown`、`ItemMissing`（`n` 超出範圍；訊息帶現有幾項）、`StatusUnknown`、`ListBad`（`todo.json` 壞了；訊息說「`set` 會整張重寫」）、`WriteFailed`、`StackMissing`。

存檔 `$AOS_STACK/todo.json`（＝經 `aos-tools call` 時的 `<agent stack>/tools/todo/todo.json`）：`{"items": [{"text", "status"}], "updated_at": "ISO 8601 UTC 到毫秒"}`；寫法照規則 6（暫存檔＋改名）、寫前 `mkdir -p "$AOS_STACK"`；不在＝空清單。

tooldef description 草稿：

> Your to-do list for a long task; it is kept outside your conversation history, so it survives when the history is summarized. Use it when a task has 3 or more steps: write the steps first, mark one in_progress when you start it, completed when it is done; keep at most one in_progress. One op per call; every op prints the whole list:
> - {"op": "ls"}
> - {"op": "set", "items": ["read the config", "write the parser", "add tests"]}  (replaces the whole list; [] clears it)
> - {"op": "add", "text": "update the docs"}  ("after": 2 puts it after item 2)
> - {"op": "mark", "n": 2, "status": "completed"}  (status: pending, in_progress, completed)
> Errors: ItemMissing (n is not on the list: ls first), StatusUnknown, ListBad (the saved list is broken: set a new one).

_metainfo：`resource: disk`、`side_effect: true`（寫自己的 stack）、`idempotent: false`（`add`）、`deterministic: true`、`interrupt: safe`、`parallel: false`（同時兩個 `add` 會搶寫）、`cost.time_ms: 30`、`timeout_ms: 2000`。

## 實作路線

- **新增**：`lib/agent/todo/`（`_entry`、`_tooldef.json`、`_metainfo.json`、`tests/`），純標準庫，走 `tool_io`。放 `lib/agent/` 而不是 `base`：它要 stack（規則 8「要跨呼叫留東西的工具（中層以上）才寫那裡」）。
- **包**：新開 `lib/packs/todo.json`（一支），兩範本 `tools.json` 的 `$override` 加一項（代定 D1）。
- **要動的既有檔（只做工具時）**：`lib/packs/README.md`、兩範本 `tools.json` 與 README 支數、`lib/docs/03-索引-agent等.md`、知識節點（跟線 C 的格式）、codemap。
- **做 T1 甲（開場帶清單）時另動**：`templates/agent-fsm/brain.py`（加 `--todo NAME`：工具清單裡有 NAME 才叫 `aos-tools call NAME '{"op": "ls"}'`，清單非空才把輸出包成 `[aos] todo: your to-do list (from tool todo):` 接在 system 最後；叫失敗＝warning 一行、照樣問腦，比照 `--knowledge` 的 `knowledge_root()`；逾時 10 秒）、`templates/agent-fsm/fsm.json`（think 格 argv 加 `--todo todo`）、`templates/reviewer` 若也走 brain.py 同改、`templates/tests/agent-fsm` 加一支整合測試、`templates/docs/02` 一段。brain 只叫工具、不讀檔，不知道清單存在哪（C-52）。
- **測試**：四個 op 的正常路徑；`n` 越界、狀態打錯、`set` 收字串陣列與物件陣列混用；檔壞＝`ListBad` 而 `set` 照寫；沒 `AOS_STACK`＝`StackMissing`；小格不在時第一次 `add` 會建、`ls` 不建；用 `aos-tools call` 叫兩次確認存在同一格。T1 甲另測：清單空時 system 不多字、非空時帶、工具拿掉時不叫、工具壞時 warning 照問腦。
- **工作量**：工具本身約 200 行＋測試 150 行，**半天**；T1 甲另加 brain.py 約 40 行＋測試，**再半天**（要用假腦整合測試跑一次）。

## history 被摘要後怎麼確保看得到

| 做法 | 看得到嗎 | 代價 |
|---|---|---|
| 只靠工具（腦自己叫 `ls`） | 要腦記得；摘要後最容易忘 | 零 |
| tooldef 說明裡寫「summarize 之後先 ls」 | 稍好；小模型常不照做 | 零 |
| `self_history summarize` 的結果尾巴加一句 `[aos] note: you have a to-do list; call todo ls` | 摘要那一刻提醒 | self_history 要知道 todo 存在＝跨工具耦合，不推 |
| **開場自動帶（T1 甲）** | 每一輪都在、不靠記性 | 動 brain.py；清單一變 system 就變，**prompt 前綴快取會失效**（本機 lmstudio 影響小、雲端按 token 計費的會多花） |

## 子 agent 與 do_task

- `subagent` 生的子、`thought`（之後 `do_task`）的一次性小幫手，都是 daemon 上另一隻 agent、有自己的 stack，叫 `todo` 時小格在**它自己的** `tools/todo/`——清單天生各自獨立，什麼都不用做。
- 父要看子的清單：子的清單在子的 stack 裡，父可以叫子的 `todo ls`？目前 `subagent` 能轉的只有 self_* 那幾類（`tools`、`llm`、`history`、`hook`、`system`），不含任意工具；要的話是 subagent 那邊加一個 op，**這次不做**（代定 D4）。
- `thought` 用完即刪（預設 `--purge`），它的清單跟著消失，正是要的。

## eca 那邊

- eca 經 aos-mcp 拿 aos 工具，`todo` 照樣叫得到；清單在 eca 那隻的 stack，`claude` 換新對話、codex 開新 session 都還在——這反而比 CLI 自帶的強（Claude Code 的 TodoWrite 跟著 session 走；eca 範本 `--tools Read,Glob,Grep` 本來就沒開 TodoWrite）。codex 自帶 `update_plan`，兩個都在無妨。
- **開場自動帶**在 eca 做不到同一套：aos-mcp 的 `instructions` 只在 initialize 給一次。要每輪帶得靠 claude 的 `UserPromptSubmit` hook 回 `additionalContext`，codex 沒有對應機制——這次只做 fsm（代定 D5），eca 靠工具本身。

## 邊緣狀況

1. **登記名不是 `todo`**（人用 `--name plan` 登記）：小格跟著變成 `tools/plan/`，清單跟原本那份分家；`--todo NAME` 也要跟著寫 `plan`。文件寫明，不另處理。
2. **同一輪平行叫兩個 `add`**：act 依序跑 tool_calls（目前不平行），不會撞；aos-mcp 那邊 Claude 可能平行叫——寫檔是「讀、改、暫存改名」，可能後蓋前少一項。`parallel: false` 寫在 metainfo；真要擋再加檔鎖（不先做）。
3. **清單很長**：上限 50 項、每項 300 字元，超過＝`ArgumentsBad`（不偷偷截，KISS「寫什麼就做什麼」）；開場帶的時候整張帶（50×300 最多約 15KB，實際遠小於）。
4. **全部 completed**：清單照留（腦看得到「做完了」）；開場帶時全部完成的清單只帶一行 `... all N completed`？——代定 D6：照樣整張帶，下一個任務腦自己 `set` 新的。
5. **兩個 in_progress**：不擋（說明裡說最多一個）；輸出最後多一行 `... note: 2 items are in_progress`。
6. **`todo.json` 被人手改壞**：`ls`／`add`／`mark`＝`ListBad`，`set` 照寫（整張換掉就修好了）。
7. **agent 被 `aos-agent tools reset`**：工具登記回定義，stack 裡的清單檔不動、還在。
8. **`self_state` 要不要順便顯示清單摘要**：不做（代定 D7），避免 self_state 知道 todo。
9. **持久檔**：`todo.json` 是 stack 裡的持久資料，要登記進 [NORMS 附錄 4](../../../../docs/NORMS/附錄4-持久檔.md)（施工時一併）。

## 代定

- D1 名字 `todo`（市面的 TodoWrite／todo list、一看就懂；避開 `task`，免得跟之後的 `do_task` 混）。備選：`plan`（Codex 用語）、`todo_list`。
- D2 一支工具、四個 op（不拆 `todo_read`／`todo_write`：清單是自己的，不需要唯讀那一包的權限切法）。
- D3 狀態用 `pending`／`in_progress`／`completed`（跟 Claude Code、Codex 同字，模型最熟），不用 `done`。
- D4 父看子的清單這次不做。
- D5 開場自動帶只做 fsm；eca 只靠工具。
- D6 全部完成的清單照樣帶，不自動清。
- D7 `self_state` 不顯示清單。
- D8 新包 `todo.json`（一支），兩範本預設開；備選：放進 `self` 包或 `gadgets` 包。
- D9 上限 50 項、每項 300 字元；新代號 `ItemMissing`、`StatusUnknown`、`ListBad`。

## 待裁

**T1 清單要不要每輪自動帶進 prompt（fsm）**
- 甲 要：brain.py 加 `--todo todo`，清單非空才接在 system 最後（推薦）：摘要後一定看得到；清單一改 system 就變，雲端模型的前綴快取會失效。
- 乙 要，但接在 history 最後一則之後（不存）：快取比較省；有些後端會把後面的 system 訊息併到最前面，效果跟甲一樣。
- 丙 不要，只靠腦自己叫 `ls`：不動 loop、零成本；摘要後常忘記清單存在。

**T2 子 agent／do_task 的清單**
- 甲 各自獨立（各自的 stack，推薦）：什麼都不用做；父看不到子的清單。
- 乙 do_task 的小幫手開場帶父的清單（唯讀）：小幫手知道整體計畫；要動 thought 的開場文，父子耦合。
- 丙 父子共用一份：要另外傳路徑、會互相蓋寫，不推。
