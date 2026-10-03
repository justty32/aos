# proto7-1 檔案格式與行為（細部 spec）

← [proto7-1](README.md)｜要合的是 [proto7 核心 spec](../proto7/spec/core.md)（條號 S-）

這份是 proto7-1 自己定的技術選型，全部取「最簡單」。每節標它落實哪幾條 S-。照做遇到的問題記在 [notes/problems.md](notes/problems.md)。

## 0. 共同約定（S-01）

- 所有狀態與控制都是 **JSON 檔**，能用 `cat` 看懂、用寫檔操作。寫檔一律「寫暫存檔再 rename」（原子），讀不到或壞掉當作不存在。
- 流水帳用 JSON Lines（`*.jsonl`，一行一個 JSON 物件）。
- 時間欄位 `at` 是 ISO 8601 字串（本機時間，到毫秒）；只給人看，邏輯不依賴牆鐘。
- 每支程式是 `bin/` 下一個 Python 檔（薄入口），本體在 `lib/aos7_*.py`。純標準庫，Python 3.11+。

## 1. 空間與 node（S-07、S-13～S-15）

- `aos7-daemon <root>` 的 `<root>` 是空間根。`<root>/.aosd/` 是 daemon 自己的地方。
- **node**＝含 `.aos/timeline.json` 的資料夾。node id＝相對 root 的路徑，用 `/` 分隔；根本身是 `.`。
- 掃描：從 root 往下走，跳過以 `.` 開頭的資料夾；遇到**含 `.aosd/` 的子資料夾**（別的 daemon 的根）整棵不進去（S-15 最基本的重疊）。巢狀 node（`team` 與 `team/agents/amy`）各是各的時間線。
- FUSE 不做。

`<node>/.aos/timeline.json`（人或別的程式寫，daemon 只讀）：

```json
{"interval_ms": 100}
```

沒寫 `interval_ms` 當 1000。

## 2. daemon（S-03～S-06、S-18、S-21）

`aos7-daemon <root>`：常駐。主迴圈每 ~20 ms：讀控制檔 → 重掃 node（新的起迴圈、消失的收迴圈）→ 寫 status。

**每條時間線一個迴圈**（daemon 內用 thread 管迴圈；每個動作都是獨立程序，S-04）：

1. 若此 node 被 pause → 等，不開新回合。
2. 跑 `aos7-tick <root> <node-id>`（程序，很快結束），從它 stdout 讀回本回合起了哪些任務。
3. 等到「本回合 tick 起的任務都結束」或「離 tick 已過 interval」，二者先到（S-09：tock 可能提前進場）。
4. 跑 `aos7-tock <root> <node-id>`（程序）。
5. 等到離本回合 tick 滿 interval，回 1。

pause 在回合中途下：本回合照常 tock 完才停。pause 的 node 清單存在 `<root>/.aosd/paused.json`（`{"paused": [...]}`），daemon 重開照樣有效。

stop：回合中途的時間線不等 interval，（`kill` 時先 kill 本 node 所有活任務）立刻 tock 收回合再結束；daemon 等所有時間線結束才退出。

同一個 root 只能有一個 daemon：`<root>/.aosd/daemon.lock` 用 `flock` 鎖，鎖不到就 stderr 說明、退出碼 1。

**控制檔**（S-18、S-21 路二）：任何人寫 `<root>/.aosd/ctl/<任意名>.json`：

```json
{"op": "pause", "node": "team/agents/bob", "by": "team:kernel-r1"}
```

| op | 意思 |
|---|---|
| `pause` | 該 node 不再開新回合（跑著的任務不動、收不到 tock） |
| `resume` | 恢復 |
| `stop` | 整個 daemon 結束；`"kill": true` 時先 kill 所有活著的任務 |
| `rescan` | 立刻重掃 node |

daemon 讀到後執行，把檔案搬到 `<root>/.aosd/ctl-done/<同名>.json`，內容加上 `"result": {"ok": true, "msg": "...", "at": "..."}`。讀不懂的也搬過去，`ok: false`。

daemon 收到 SIGTERM／SIGINT＝`stop` 加 `kill: true`（路一：子 daemon 被父時間線 kill 時，帶走自己的任務）。

**狀態** `<root>/.aosd/status.json`（daemon 寫，每圈覆寫）：

```json
{"pid": 123, "root": "/abs/root", "at": "...", "stopping": false,
 "nodes": {"team": {"round": 7, "phase": "running", "paused": false, "live": ["kernel-r1"]}}}
```

`phase`：`idle`（等下回合）／`tick`／`running`（回合中）／`tock`／`paused`／`stopped`。另有 `kill_on_stop`。

**流水帳** `<root>/.aosd/log.jsonl`：daemon 每個 tick、tock、ctl、node 出現消失寫一行。

daemon 給 tick／tock 的環境：`PATH` 前面加上 proto7-1 的 `bin/`。

## 3. 回合（S-08、S-11）

`<node>/.aos/round.json`（tick、tock 寫）：

```json
{"round": 3, "open": true, "tick_at": "...", "tock_at": null}
```

tick 把 round +1、`open: true`，並記下本回合的 `started`、`ctl`（給 tock 寫總結用）；tock 設 `open: false` 與 `tock_at`。第一次 tick 的回合是 1。daemon 重開後接著數（讀這個檔）。

`<node>/.aos/rounds/<N>.json`（tock 寫，第 N 回合的總結）：

```json
{"round": 3, "tick_at": "...", "tock_at": "...",
 "started": ["agent-r1"], "alive": ["kernel-r1"],
 "ended": [{"tid": "stuck-r2", "code": -15}], "ctl": [{"tid": "x", "op": "kill", "ok": true}]}
```

`ended`＝上次 tock 之後才看到結束的任務；`ctl`＝本回合 tick 與 tock 執行的任務控制。

## 4. 任務表與 tick（S-09、S-10、S-12）

`<node>/.aos/tasks.json`（人或 kernel 寫）：

```json
{"tasks": [
  {"name": "kernel", "mode": "keep", "argv": ["aos7-kernel"]},
  {"name": "job", "mode": "each", "argv": ["python3", "job.py"], "from_round": 3},
  {"name": "x", "mode": "keep", "inst": "x.inst.json", "dirs": ["../mail"]}
]}
```

- `argv`：直接跑；相對路徑以 node 為 cwd。`inst`：一份 inst JSON（相對 node 的路徑），用搬來的 `aos-exec` 跑（S-12）。二選一。
- `mode`：`each`＝每回合起一個；`keep`＝本 node 沒有同名活任務才起（常駐用）。預設 `each`。
- `from_round`：從第幾回合起才生效（預設 1）。
- `dirs`：除了 node 本身，tick 另外「給」這個任務的資料夾（相對 node）。**只寫進 birth.json 當宣告，不強制**（沒有 FUSE）。

`<node>/.aos/spawn/<任意名>.json`：別人請求「下個 tick 起一個任務」，格式同 tasks.json 的一項（多一個可選 `restart_of`）。tick 起完就刪掉。restart 靠它。

`aos7-tick <root> <node-id>`，依序：

1. round +1，寫 `round.json`。
2. 執行任務控制（第 6 節）。
3. 起任務：先 `spawn/*.json`（檔名排序），再 tasks.json 各項（`keep` 的檢查會算進剛起的）。
4. stdout 印一行 JSON `{"round": N, "started": [tid...]}`，結束。**不等任務。**

## 5. 任務（S-10、S-11、S-16）

tid＝`<name>-r<回合>`，同回合撞名加 `-2`、`-3`。任務資料夾 `<node>/.aos/tasks/<tid>/`：

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `birth.json` | tick | `{"tid","name","node","round","argv"或"inst","dirs","at","restart_of"}`；`dirs` 是絕對路徑，第一個是 node |
| `pid.json` | aos7-run | `{"pid","pgid","runner_pid","at"}` |
| `out.log` | 任務 | stdout＋stderr |
| `exit.json` | aos7-run | `{"code","at","round"}`；code 負數＝被訊號殺（-15）；`round` 是結束時 node 的回合數 |
| `tock.json` | tock | `{"round": N, "at"}`：第 N 回合剛結束（覆寫，只留最新） |
| `ctl.json` | 任何人 | `{"op": "kill"或"restart", "by", "why"}` |
| `ctl-done.json` | tick／tock | ctl.json 搬過來加 `result` |
| `ended.json` | tock | `{"round": N}`：tock 在第 N 回合記下它結束 |

tick 用 `aos7-run <taskdir>` 起任務（新 session，tick 不等它）。aos7-run 讀 birth.json，把真正的任務起在**自己的程序群組**，寫 pid.json，等它結束，寫 exit.json。起不來（找不到程式等）直接寫 exit.json `{"code": 127, "error": "..."}`。

任務的環境變數（找到自己的唯一管道）：`AOS7_ROOT`、`AOS7_NODE`（絕對路徑）、`AOS7_NODE_ID`、`AOS7_TASK`（任務資料夾絕對路徑）、`AOS7_TID`；`PATH` 前面加 `bin/`。cwd＝node。

任務狀態判斷：有 exit.json＝結束；有 pid.json 且任務程序或 aos7-run（`runner_pid`）還在＝活；有 pid.json、兩者都不在、又沒 exit.json＝**lost**（tock 替它寫 `exit.json` `{"code": null, "lost": true}`）；只有 birth.json＝剛起（算活）。

任務自己知道時間的方法：輪詢 `$AOS7_TASK/tock.json`（S-11）。

## 6. 任務控制（S-17）

任何人寫 `<taskdir>/ctl.json`。**tick 與 tock 時刻**才執行（S-17「在 tick-tock 時」）：

- `kill`：對 pid.json 的 pgid **以及該群組成員所有後代所在的群組**送 SIGTERM，等至多 1 秒，還在就 SIGKILL（後代：aos-exec 把 inst 的子程式開在另一個 session）。
- `restart`：kill，再把 birth.json 的定義寫成 `spawn/restart-<tid>.json`（帶 `restart_of`），下回合 tick 起新的（維持「任務一律由 tick 啟動」）。
- 已結束的任務：kill 當成功；restart 照樣寫 spawn。

執行完把 ctl.json 搬成 ctl-done.json。node 被 pause 時沒有 tick／tock，ctl 會等到 resume。

## 7. tock（S-08、S-11）

`aos7-tock <root> <node-id>`：

1. 執行任務控制（第 6 節）。
2. 掃所有任務：lost 的補 exit.json；新結束的寫 ended.json。
3. 對每個活任務寫 `tock.json`。
4. 寫 `rounds/<N>.json`、`round.json`（open: false）。
5. stdout 印一行 JSON 總結，結束。

## 8. 小工具（S-01）

`aos7-ctl` 只是「替你寫控制檔」，LLM 用寫檔一樣做得到：

- `aos7-ctl daemon <root> <op> [node] [--kill]`：寫 `<root>/.aosd/ctl/<時間>-<pid>.json`（`--kill` 給 stop 用）。
- `aos7-ctl task <taskdir> <kill|restart> [why]`：寫 ctl.json。
- 兩者都可加 `--by WHO`（預設：在任務裡是 `<node-id>:<tid>`，否則 `cli`）；stdout 印一行 `{"wrote": 路徑}`。

## 9. kernel（S-16～S-18）

一個 `keep` 任務 `aos7-kernel`，設定在 `<node>/kernel.json`：

```json
{"members": ["agents/amy", "agents/bob"],
 "stuck_rounds": 3, "budget_tokens": 400, "cool_rounds": 3,
 "max_age": {"subd": 8}}
```

每收到一次 tock（自己 node 的回合）跑一輪規則，判斷結果寫成控制檔：

- **卡住**：成員 node 的活任務，若有 `progress.json`，它的內容連續 `stuck_rounds` 個**成員 node 的回合**（看成員的 `round.json` 有沒有前進）沒變 → 寫該任務 ctl.json `restart`。沒有 progress.json 的任務不管；成員 node 被 pause 時不數。
- **預算**：成員 node 各任務（含已結束的）的 `usage.json`（`{"tokens": int, "calls": int}`）加總，比上一輪多出的量累計超過 `budget_tokens` → 寫 daemon ctl `pause` 該 node；pause 後 `cool_rounds` 個 **kernel 自己 node 的回合** → `resume`，累計歸零。第一次看到某 node 時現有用量當基準、不算舊帳。成員是 kernel 自己的 node 時不管（pause 自己就收不到 tock、無法 resume）。
- **壽命**：自己 node 名為 `max_age` 鍵的活任務，活超過（自己 node 回合數 − birth round）那麼多回合 → ctl.json `kill`。
- 對同一任務的指令只下一次；目標已有 ctl.json（別人先下了）就不蓋、不下。
- 每個決定寫一行到 `$AOS7_TASK/decisions.jsonl`：`{"round","rule","target","op","why","at"}`。`target`：任務是 `<node id>:<tid>`，node 是 `<node id>`。
- 每輪重讀 kernel.json（改檔即生效）。規則狀態存 `$AOS7_TASK/kernel-state.json`（含 `round`＝已處理到第幾回合）；新任務資料夾裡沒有時，接 birth.json 的 `restart_of`，否則接同名任務裡 birth round 最大的那份。
- 啟動時跳過 ≤ 狀態 `round` 的 tock；`--rounds N` 收到 N 次 tock 後結束；SIGTERM／SIGINT 乾淨結束。

成員 node id＝自己的 node id 接上成員相對路徑。daemon ctl 寫到 `$AOS7_ROOT/.aosd/ctl/kernel-<tid>-r<回合>-<序>-<op>-<node>.json`，內容 `{"op","node","by","why"}`，`by`＝`<node id>:<tid>`。程式：`lib/aos7_kernel.py`（迴圈、套用）、`lib/aos7_kernel_rules.py`（快照＋純函式 `run_rules`）。

## 10. agent（S-16、S-19）

一個 `keep` 任務 `aos7-agent`。狀態 `$AOS7_TASK/state.json`：

```json
{"state": "idle", "round": 4, "steps": 7, "tocks": 9, "plan": null, "pc": 0,
 "letters": [], "goal": null, "last": "...", "from": null}
```

`pc`＝act 做到 plan 第幾步；`letters`＝這輪 idle→think 時抓下的信檔名（之後新到的信留給下一輪）；`goal`＝這輪要先開口的 goal 內容；`from`＝接續的前任 tid。

**每收到一次 tock 換一次狀態**（S-19「依託 tick-tock 換狀態」）。時機：收到 tock 先換狀態、存檔，再做「新狀態的事」（think＝問 LLM、act＝跑工具），所以 state.json 寫 think 表示「這回合在想」。一封信從寄出到回信約 2～4 回合。

- `idle`：看 `<node>/inbox/*.json` 有沒有新信（或 `<node>/goal.json` 要它先開口）；有 → `think`，沒有 → 留在 idle。
- `think`：呼叫 LLM（輸入：persona、信件），得到 plan（JSON 動作清單）→ `act`。
- `act`：照 plan 做工具動作 → `idle`。處理過的信搬到 `inbox/done/`。
- 下一個 tock：`act` → `idle`（這個 tock 不看信箱，下一個才看）。
- `goal.json` 用掉後改名 `goal.done.json`（不論 plan 成不成功）。
- 重啟：自己的 state.json 沒有時，接同 node 同名任務中回合最新的那份 state.json；停在 think 且沒 plan → 重問一次 LLM；停在 act → 從 `pc` 接著做（`pc` 那步可能重做一次）。
- 單執行緒：LLM 呼叫比回合長時，期間來的 tock 只看最新一個（中間的回合被併掉）。

工具（plan 是 `[{"tool": ...}, ...]`）：

| tool | 參數 | 做什麼 |
|---|---|---|
| `send` | `to`（node id）、`body` | 寫一封信到 `<root>/<to>/inbox/<時間>-<自己>.json`：`{"from","to","round","body"}` |
| `write` | `path`（相對自己 node）、`text` | 寫檔 |
| `none` | — | 什麼都不做 |

每次 LLM 呼叫把用量累加到 `$AOS7_TASK/usage.json`（`{"tokens","calls"}`，每個任務自己從 0 起算，不接前任）。**每處理完一個 tock** 覆寫 `$AOS7_TASK/progress.json`＝`{"round","state","steps"}`（給 kernel 判斷卡住：idle 等信也會更新，只有卡在 LLM 呼叫、收不到 tock 時才連續不變）。

設定在 `<node>/agent.json`：`{"name": "amy", "persona": "...", "llm": "fake"}`；`llm` 可為 `fake`（決定性、離線）或 `{"url": "http://localhost:1234/v1", "model": "..."}`（OpenAI 相容）。可選：`max_ping`（fake 用，預設 6）；`llm` 物件可加 `timeout_s`（預設 120）、`temperature`（預設 0）、`max_tokens`、`api_key`。

- fake：`goal.json` 的 `{"say_first": {"to", "body"}}` 讓它先開口；收到 body 為 `ping N` 的信回 `ping N+1` 給寄件者，N ≥ `max_ping` 改成 `write work/done.txt`、不再回。tokens＝prompt 字元數 // 4。
- OpenAI 相容：system＝規則＋persona，user＝`{"goal","letters"}` 的 JSON；要模型只回 JSON 陣列。解不出就當 `[{"tool":"none"}]`，原因寫進 state.last。tokens＝回應的 `usage.total_tokens`。
- `send` 的 `to` 必須是空間裡已存在的資料夾；`write` 的 `path` 不能跑出自己的 node。不合就跳過該步並記在 last。

agent 的進出流水印在 stdout（一行一個 JSON，aos7-run 收進 out.log）。`aos7-agent --rounds N`：處理 N 次 tock 後自行結束；SIGTERM／SIGINT 乾淨結束（code 0）。
