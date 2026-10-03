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
- FUSE 不做。跨 node 用掛載（第 4 節 `mounts`，S-23）。

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

`phase`：`idle`（等下回合）／`tick`／`running`（回合中）／`tock`／`paused`／`stopped`。另有 `kill_on_stop`。`round` 以 tick 印的結果為準，tick 沒印（失敗）時讀 round.json。tick／tock 退出碼非 0 時，該 node 多一欄 `last_error`：`{"prog", "rc", "round", "at", "err"}`（stderr 末段），留著直到下次出錯覆寫。

**流水帳** `<root>/.aosd/log.jsonl`：daemon 每個 tick、tock、ctl、node 出現消失寫一行。

daemon 給 tick／tock 的環境：`PATH` 前面加上 proto7-1 的 `bin/`。

## 3. 回合（S-08、S-11）

`<node>/.aos/round.json`（tick、tock 寫）：

```json
{"round": 3, "open": true, "tick_at": "...", "tock_at": null}
```

tick 把 round +1、`open: true`，並記下本回合的 `started`、`ctl`、`mounts`（加掛審核結果 `[{"tid","name","path","ok","msg"}]`；給 tock 寫總結用）；tock 設 `open: false` 與 `tock_at`。第一次 tick 的回合是 1。daemon 重開後接著數（讀這個檔）。

`<node>/.aos/rounds.jsonl`（tock 寫，一回合加一行總結；`tail -1` 是最近一回合，`grep '"round": 3,'` 找第 3 回合）：

```json
{"round": 3, "tick_at": "...", "tock_at": "...",
 "started": ["agent-r1"], "alive": ["kernel-r1"],
 "ended": [{"tid": "stuck-r2", "code": -15}], "ctl": [{"tid": "x", "op": "kill", "ok": true}], "mounts": []}
```

`ended`＝上次 tock 之後才看到結束的任務；`ctl`＝本回合 tick 與 tock 執行的任務控制。

原本一回合一個 `rounds/<N>.json`；長跑時小檔佔掉的磁碟是內容的 9 倍（astra-3 長跑、R-10），改成同一個檔一行一回合（P-12）。

## 4. 任務表與 tick（S-09、S-10、S-12）

`<node>/.aos/tasks.json`（人或 kernel 寫）：

```json
{"tasks": [
  {"name": "kernel", "mode": "keep", "argv": ["aos7-kernel"]},
  {"name": "job", "mode": "each", "argv": ["python3", "job.py"], "from_round": 3},
  {"name": "x", "mode": "keep", "inst": "x.inst.json", "mounts": {"bob": "team/agents/bob/inbox"}}
]}
```

- `argv`：直接跑；相對路徑以 node 為 cwd。argv 裡的 `$AOS7_TASK`、`${AOS7_NODE}` 這類 `AOS7_*` 變數由 aos7-run 展開（其他 `$` 原樣），用來指到掛載點。`inst`：一份 inst JSON（相對 node 的路徑），用搬來的 `aos-exec` 跑（S-12）。二選一。
- `mode`：`each`＝每回合起一個；`keep`＝本 node 沒有同名活任務才起（常駐用）。預設 `each`。
- `from_round`：從第幾回合起才生效（預設 1）。
- `mounts`：**掛載**（S-23）。`{"名字": "空間裡的路徑"}`，路徑相對空間根、跟 node id 同一套（根的 daemon 資料夾是 `.aosd`）。tick 起任務時在任務資料夾建 `mnt/<名字>`，是指向目標的相對符號連結；目標不存在先建成資料夾。名字不能含 `/`、不能以 `.` 開頭；路徑不能是絕對、不能跑出空間根（沿符號連結走到的實際位置也算，realpath 後要在空間根內），不合的不掛、在 birth.json 記 `error`。任務要碰別的 node 或 daemon 的資料夾，一律經過掛載點（第 5 節「只碰給的資料夾」）。**不強制**（沒有 FUSE），靠寫入紀錄檢查。

- `mount_allow`（tasks.json 頂層，可選）：執行中加掛請求的允許清單，空間路徑前綴（`["team/agents/", ".aosd"]`；`"."`＝全部）。比對時請求路徑與每一項都接空間根再 realpath，比**實際位置**（problems.md M-13）；跑出空間根的一律不給。沒寫＝全給（仍要在空間根內）。只管執行中的請求，不管 `mounts` 宣告。

**執行中加掛**（S-23，M-6 使用者選 (b)）：任務寫 `$AOS7_TASK/mount-req/<名字>.json`＝`{"name", "path"（空間路徑）, "why"}`（`name` 可省，由路徑推：路徑只有英數、`-`、`/` 時把 `/` 換成 `_`，例如 `team/agents/bob/inbox` → `team_agents_bob_inbox`；其他（含 `_`、`.`）再接 `-` 與路徑 sha1 前 8 碼，所以不同路徑一定推出不同名字）。下一個 tick 審核：路徑不合、不在 `mount_allow`、名字已掛了別的 → 拒絕；否則建 `mnt/<名字>`、加進 birth.json 的 `mounts`。`name`／`path` 不是字串、請求不是物件、或處理時出任何例外，都寫失敗回條，不影響同一輪其他請求與 tick 的其他工作。請求檔刪掉，回條寫 `$AOS7_TASK/mount-done/<同名>.json`＝請求內容加 `{"result": {"ok", "msg", "at"}}`。被拒的回條留著，`aos7_mount.request` 看到就不再重請（要重請就刪回條）。restart 把加掛的一起帶到新任務。卸掛不做。

`<node>/.aos/spawn/<任意名>.json`：別人請求「下個 tick 起一個任務」，格式同 tasks.json 的一項（多一個可選 `restart_of`）。tick 起完就刪掉。restart 靠它。

`aos7-tick <root> <node-id>`，依序：

1. round +1，寫 `round.json`。
2. 執行任務控制（第 6 節），再審核活任務的加掛請求（上面）。
3. 起任務：先 `spawn/*.json`（檔名排序），再 tasks.json 各項（`keep` 的檢查會算進剛起的）。
4. stdout 印一行 JSON `{"round": N, "started": [tid...]}`，結束。**不等任務。**

## 5. 任務（S-10、S-11、S-16）

tid＝`<name>-r<回合>`，同回合撞名加 `-2`、`-3`。任務資料夾 `<node>/.aos/tasks/<tid>/`：

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `birth.json` | tick | `{"tid","name","node","round","argv"或"inst","mounts","at","restart_of"}`；`mounts`＝`{名字: {"to": 空間路徑, "at": 掛載點絕對路徑}}`（壞的宣告是 `{"error"}`） |
| `mnt/<名字>` | tick | 掛載點（符號連結） |
| `writes.jsonl` | 任務（audit hook） | 開了寫入紀錄才有，見下 |
| `mount-req/<名字>.json` | 任務 | 執行中加掛的請求（第 4 節） |
| `mount-done/<名字>.json` | tick | 加掛回條 |
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

**只碰給的資料夾**（S-10、S-23）：任務能寫的是自己的 node（**扣掉裡面巢狀的別的 node 與 daemon 根**）加上掛載點的目標。程式碰別的 node 一律用 `lib/aos7_mount.py` 的 `resolver(taskdir)`：把空間裡的路徑換成掛載點下的路徑，沒掛到回 None（不寫）。

**寫入紀錄**（檢查用，只記不擋）：起 daemon 的環境有 `AOS7_AUDIT`（任何非空值）時，tick 把 `lib/audit_site/` 放進任務的 `PYTHONPATH`，Python 任務啟動時載入 audit hook，把空間根底下每個寫入動作（開檔寫、rename／replace、remove、mkdir、rmdir、symlink）記一行到 `$AOS7_TASK/writes.jsonl`：`{"op", "path"（實際位置）, "ok", "pid", "via"（經過連結時寫的路徑）}`。`ok`＝實際位置在上面說的範圍內；掛載點的範圍取 birth.json 宣告的 `to`（接空間根再 realpath），不看連結現在指哪（任務自己改指連結不算）；判不過時重讀 birth.json，算進執行中加掛的。帶 `dir_fd` 的 mkdir／rmdir／remove／rename／replace／symlink／link 以那個 fd 指的資料夾為起點；`open` 的 audit 事件不帶 dir_fd，看不到（M-12）。`lib/aos7_audit.py` 的 `scan(root)` 把整個空間的紀錄拼起來挑出 `ok: false` 的。只看得到 Python 程序（problems.md M-3）。

## 6. 任務控制（S-17）

任何人寫 `<taskdir>/ctl.json`。**tick 與 tock 時刻**才執行（S-17「在 tick-tock 時」）：

- `kill`：對 pid.json 的 pgid **以及該群組成員所有後代所在的群組**送 SIGTERM，等至多 1 秒，還在就 SIGKILL（後代：aos-exec 把 inst 的子程式開在另一個 session）。
- `restart`：kill，再把 birth.json 的定義寫成 `spawn/restart-<tid>.json`（帶 `restart_of`），下回合 tick 起新的（維持「任務一律由 tick 啟動」）。
- 已結束的任務：kill 當成功；restart 照樣寫 spawn（帶原本的 `mounts` 宣告，新任務照樣掛）。
- ctl.json 讀不懂或不是 JSON 物件（例如 `[]`）：不執行，照樣搬成 ctl-done.json，內容 `{"raw": 原內容或 "unreadable", "result": {"ok": false, "msg": "not a JSON object"／"unreadable JSON"}}`（同 daemon ctl；不拖垮 tick／tock）。

執行完把 ctl.json 搬成 ctl-done.json。node 被 pause 時沒有 tick／tock，ctl 會等到 resume。

## 7. tock（S-08、S-11）

`aos7-tock <root> <node-id>`：

1. 執行任務控制（第 6 節）。
2. 掃所有任務：lost 的補 exit.json；新結束的寫 ended.json。
3. 對每個活任務寫 `tock.json`。
4. 在 `rounds.jsonl` 加一行總結、寫 `round.json`（open: false）。
5. stdout 印一行 JSON 總結，結束。

## 8. 小工具（S-01）

`aos7-ctl` 只是「替你寫控制檔」，LLM 用寫檔一樣做得到：

- `aos7-ctl daemon <root> <op> [node] [--kill]`：寫 `<root>/.aosd/ctl/<時間>-<pid>.json`（`--kill` 給 stop 用）。`<root>` 也可以是掛進來的 `.aosd` 或 `.aosd/ctl`（任務裡用掛載點）。
- `aos7-ctl task <taskdir> <kill|restart> [why]`：寫 ctl.json。
- 兩者都可加 `--by WHO`（預設：在任務裡是 `<node-id>:<tid>`，否則 `cli`）；stdout 印一行 `{"wrote": 路徑}`。

## 9. kernel（S-16～S-18）

一個 `keep` 任務 `aos7-kernel`，設定在 `<node>/kernel.json`：

```json
{"members": ["agents/amy", "agents/bob"],
 "stuck_rounds": 3, "budget_tokens": 400, "cool_rounds": 3,
 "max_age": {"subd": 8},
 "llm_stuck_rounds": 200, "cap_tokens": 200000,
 "roles": {"agents/amy": "寫程式", "agents/bob": "審稿"}}
```

後三個可選。

kernel 要看的東西都經過掛載點（S-23）：daemon 的 `.aosd`（讀 status.json、寫 ctl）、每個成員的 `.aos`（讀 round.json、任務；寫任務 ctl.json）。**每輪先對沒掛到的寫加掛請求**（第 4 節），所以 tasks.json 不必寫 mounts，加成員只改 kernel.json；下一個 tick 掛上之前，那個成員當作不存在（快照 `mounted: false`，不下決定），`.aosd` 還沒掛時 pause／resume 寫不出去，decisions.jsonl 記 `skipped`。kernel 自己 node 的任務直接寫。

每收到一次 tock（自己 node 的回合）跑一輪規則，判斷結果寫成控制檔：

- **卡住**：成員 node 的活任務，若有 `progress.json`，它的內容連續 `stuck_rounds` 個**成員 node 的回合**（看成員的 `round.json` 有沒有前進）沒變 → 寫該任務 ctl.json `restart`。沒有 progress.json 的任務不管；成員 node 被 pause 時不數。progress 有 `llm_since`（agent 正在等 LLM）時改用 `llm_stuck_rounds`，沒寫就不管（problems-real.md R-3）。
- **預算**：成員 node 各任務（含已結束的）的 `usage.json`（`{"tokens": int, "calls": int}`）加總，比上一輪多出的量累計超過 `budget_tokens` → 寫 daemon ctl `pause` 該 node；pause 後 `cool_rounds` 個 **kernel 自己 node 的回合** → `resume`，累計歸零（被移出 members 後到期的 resume 也歸零，astra-3 三-1）。第一次看到某 node 時現有用量當基準、不算舊帳。成員是 kernel 自己的 node 時不管（pause 自己就收不到 tock、無法 resume）。**kernel 自己 pause 的，自己負責到期 resume，不管對方還在不在 members**（astra-2 二-7）。
- **總額**：成員 node 的用量總和（不扣基準）超過 `cap_tokens` → `pause`（rule `cap`），冷卻不 resume；人把 `cap_tokens` 調高到總和以上或拿掉後，下一輪 `resume`（理由寫實際的用量與上限）。被移出 members 的成員若是總額 pause 的，一直停著（R-4）。
- **名冊**：每輪把 `{"by": 自己 node id, "members": [{"node", "inbox": "<node>/inbox", "role": roles 裡那句或空字串}]}` 經過 `<成員>/.aos` 掛載點寫到每個成員的 `.aos/roster.json`；內容沒變不寫（R-2、M-15）。寫不進去（成員搬走、掛載斷了）不丟例外：decisions.jsonl 記一行 `{"rule": "roster", "op": "write", "target": 成員, "skipped": 原因}`，跳過那個成員，其他照做（astra-3 三-2、M-16）。
- **壽命**：自己 node 名為 `max_age` 鍵的活任務，活超過（自己 node 回合數 − birth round）那麼多回合 → ctl.json `kill`。
- 對同一任務的指令只下一次；目標已有 ctl.json（別人先下了）就不蓋、不下。
- 每個決定寫一行到 `$AOS7_TASK/decisions.jsonl`：`{"round","rule","target","op","why","at"}`；沒寫出去的多 `skipped`（沒掛載，或寫控制檔丟了 OSError——同樣只記不死）。`target`：任務是 `<node id>:<tid>`，node 是 `<node id>`。
- 每輪重讀 kernel.json（改檔即生效）。規則狀態存 `$AOS7_TASK/kernel-state.json`（含 `round`＝已處理到第幾回合）；新任務資料夾裡沒有時，接 birth.json 的 `restart_of`，否則接同名任務裡 birth round 最大的那份。
- 啟動時跳過 ≤ 狀態 `round` 的 tock；`--rounds N` 收到 N 次 tock 後結束；SIGTERM／SIGINT 乾淨結束。

成員 node id＝自己的 node id 接上成員相對路徑。daemon ctl 經過掛載點寫到（`.aosd` 的）`ctl/kernel-<tid>-r<回合>-<序>-<op>-<node>.json`，內容 `{"op","node","by","why"}`，`by`＝`<node id>:<tid>`。程式：`lib/aos7_kernel.py`（迴圈、套用）、`lib/aos7_kernel_rules.py`（快照＋純函式 `run_rules`）。

## 10. agent（S-16、S-19）

一個 `keep` 任務 `aos7-agent`。狀態 `$AOS7_TASK/state.json`：

```json
{"state": "idle", "round": 4, "steps": 7, "tocks": 9, "plan": null, "pc": 0,
 "letters": [], "goal": null, "last": "...", "from": null}
```

`pc`＝act 做到 plan 第幾步；`letters`＝這輪 idle→think 時抓下的信檔名（之後新到的信留給下一輪）；`goal`＝這輪要先開口的 goal 內容；`from`＝接續的前任 tid。

**每收到一次 tock 換一次狀態**（S-19「依託 tick-tock 換狀態」）。時機：收到 tock 先換狀態、存檔，再做「新狀態的事」（think＝問 LLM、act＝跑工具），所以 state.json 寫 think 表示「這回合在想」。一封信從寄出到回信約 2～4 回合。

- `idle`：看 `<node>/inbox/*.json` 有沒有新信（或 `<node>/goal.json` 要它先開口）；有 → `think`，沒有 → 留在 idle。
- `think`：先寫 progress.json＝`{"round","state":"think","steps","llm_since": 時間}`（給 kernel 分辨「在等 LLM」，R-3），再呼叫 LLM（輸入：persona、信件、`<node>/.aos/roster.json` 有的話帶上），得到 plan（JSON 動作清單）→ `act`。
- `act`：照 plan 做工具動作 → `idle`。處理過的信搬到 `inbox/done/`。
- 下一個 tock：`act` → `idle`（這個 tock 不看信箱，下一個才看）。
- `goal.json` 用掉後改名 `goal.done.json`（不論 plan 成不成功）。
- 重啟：自己的 state.json 沒有時，接同 node 同名任務中回合最新的那份 state.json；停在 think 且沒 plan → 重問一次 LLM；停在 act → 從 `pc` 接著做（`pc` 那步可能重做一次）。
- 單執行緒：LLM 呼叫比回合長時，期間來的 tock 只看最新一個（中間的回合被併掉）。

工具（plan 是 `[{"tool": ...}, ...]`）：

| tool | 參數 | 做什麼 |
|---|---|---|
| `send` | `to`（node id）、`body` | 經過掛載點寫一封信到 `<to>/inbox/<時間>-<自己>.json`：`{"from","to","round","body"}`。對方的 inbox 沒掛：寫加掛請求，信先放 `<node>/outbox/`；之後每個 tock 一開始先清 outbox（掛上了就寄，加掛被拒就搬到 `outbox/failed/`）。被拒過的對象直接失敗。已掛但收件夾不在（被刪、被搬走）或寫不進去：這封失敗，信放 `outbox/failed/`，信裡加 `failed: {"why","at"}`（M-14） |
| `write` | `path`（相對自己 node）、`text` | 寫檔 |
| `save` | `letter`（收到的信的檔名）、`path`（相對自己 node）、可選 `code` | **不經 LLM**，把 `inbox/` 或 `inbox/done/` 裡那封信原樣寫成檔：`code: true` 時只取 body 第一段 ``` 程式碼（沒有圍欄取整段），否則整段 body（R-15 (b)）。找不到信、檔名含 `/` 就那步失敗 |
| `none` | — | 什麼都不做 |

每次 LLM 呼叫把用量累加到 `$AOS7_TASK/usage.json`（`{"tokens","calls"}`，每個任務自己從 0 起算，不接前任）。**每處理完一個 tock** 覆寫 `$AOS7_TASK/progress.json`＝`{"round","state","steps"}`（給 kernel 判斷卡住：idle 等信也會更新，只有卡在 LLM 呼叫、收不到 tock 時才連續不變）。

設定在 `<node>/agent.json`：`{"name": "amy", "persona": "...", "llm": "fake"}`；`llm` 可為 `fake`（決定性、離線）或 `{"url": "http://localhost:1234/v1", "model": "..."}`（OpenAI 相容）。可選：`max_ping`（fake 用，預設 6）；`llm` 物件可加 `timeout_s`（預設 120）、`temperature`（預設 0）、`max_tokens`、`api_key`。

- fake：`goal.json` 的 `{"say_first": {"to", "body"}}` 讓它先開口；收到 body 為 `ping N` 的信回 `ping N+1` 給寄件者，N ≥ `max_ping` 改成 `write work/done.txt`、不再回。tokens＝prompt 字元數 // 4。
- 任何工具丟例外都當成那一步失敗（state.last 記「工具失敗：…」），agent 不退出。
- OpenAI 相容：system＝規則（四個工具）＋persona，user＝`{"roster"（有名冊才有）,"goal","letters"}` 的 JSON，每封信帶 `file`（信檔名，給 save 用）；要模型只回 JSON 陣列。解不出就當 `[{"tool":"none"}]`，原因寫進 state.last。tokens＝回應的 `usage.total_tokens`。
- `send` 的 `to` 必須是空間裡的路徑（不能絕對、不能跑出根）；`write`、`save` 的 `path` 不能跑出自己的 node。不合就跳過該步並記在 last。

**真模型用的補充**（`demo/real.py` 用到；不設就跟上面一樣）：

- `agent.json` 的 `"memory": N`：think 的 user JSON 多一個 `memory`＝`{"recent_letters": 最近 N 封往來的信（收：inbox/done/，帶 `file`；寄：<node>/sent.jsonl，依 at 排；視窗外的每個往來對象再補它最近一封，R-13）, "my_files": 自己 work/ 底下的檔（每檔截 4000 字）}`。`send` 一律把信多記一行到 `<node>/sent.jsonl`。**只讀尾端**（astra-3 三-3）：inbox/done/ 依檔名（時間開頭）取最後 max(N, 200) 封、sent.jsonl 從檔尾往回讀最後 max(N, 200) 行，不隨歷史變慢；「每個對象補一封」也只在這範圍內找。
- `agent.json` 的 `"wake": {"rounds": N, "unless": "相對 node 的路徑"}`：idle 且沒信沒 goal、離上次開始 think 已 N 個回合、`unless` 的檔又不在 → 自己 think 一次，goal＝`{"wake": "…"}`（不改名 goal.json）。
- `llm` 物件的 `retry`（預設 1）：plan 解析不出時，把原回應接一句更正再問，最多 retry 次；每次都算進 usage 的 `calls`。
- 每次真模型 think 在 `$AOS7_TASK/llm.jsonl` 記一行：`{"at","round","round_before","round_after"（node 的回合，呼叫前後）,"ms","calls","tokens","note","letters","raw"（原文前 4000 字）}`。
- 每處理一個 tock，在 `$AOS7_TASK/trace.jsonl` 記一行 `{"round","state","steps","at"}`（跟 progress.json 同時寫）。

agent 的進出流水印在 stdout（一行一個 JSON，aos7-run 收進 out.log）。`aos7-agent --rounds N`：處理 N 次 tock 後自行結束；SIGTERM／SIGINT 乾淨結束（code 0）。
