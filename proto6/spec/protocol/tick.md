# tick 協議：資料夾、任務表、紀錄（P-200～P-214）

← [規格](../README.md)｜[tick 核心](../tick.md)｜[hooks](../tick/hooks.md)｜[tasks-blocked](../tick/tasks-blocked.md)｜[慣例](../conventions.md)｜[daemon 協議](daemon/README.md)

本篇只留「檔案長什麼樣」。正本是 `proto6/spec/protocol/schemas/`（`inst`、`tick-tasks`、`tick-record` 三份 schema）與 `proto6/spec/protocol/examples/tick/` 的正反例（`messages/validate.py` 會驗），行為正本是 `proto6/src/py/lib/aos_tick*.py` 與測試。下面的 JSON 是給人快速看的長相，有出入以 schema 為準。`.aos` 是 `AOS_DIRNAME` 沒設時的名字，空字串就直接放在資料夾本身（C-09）。

## P-200．資料夾布局

工作資料夾 ＝ `aos-tick` 的 cwd，用正規化的絕對路徑認。名稱固定、其他按需才建：

| 路徑 | 用途 |
|---|---|
| `.aos/inst.json`（或 `inst.json`） | 給 `aos-exec` 跑這個資料夾的 inst；`aos-tick` 不看它 |
| `.aos/tasks.json` | 任務註冊表（P-202），唯一位置；`aos-tick` 認資料夾就看它在不在 |
| `.aos/tick.lock` | 核心鎖檔，不存在就建、不刪，不傳給任務 |
| `.aos/tick/current/`、`.aos/tick/last/` | 本格／上一格的結束碼紀錄（P-213） |
| `.aos/tick/tasks-blocked` | 暫時擋板（P-213、P-214），整格最後核心刪掉 |
| `.aos/tick-blocked` | 擋板檔：有它核心不開格（P-213） |
| `config/`、`state/`、`work/`、`public/` | 給任務用，格式由使用它的任務定；不跑 `aos-tick` 的資料夾不必有完整布局 |

暫緩區還有 `requests/`、`responses/`、`.aos/mq/`、`.aos/summary/`、`.aos/attention/`、`.aos/jobs/` 等舊布局，見 [暫緩區協議](../deferred/protocol/tick/01-P-207加入設定與P-212切換帳號.md)。

## P-201．inst 的格式

schema 是 [inst.schema.json](schemas/inst.schema.json)，只驗原始結構；引用、循環、選項值由 runner 驗。沒有 `version`、沒有 `user`（寫了當陌生鍵忽略）。125／126／127 與 `exit` 的訊號編碼照 [inst 正本](../inst.md)。最小例（[inst.minimal.valid.json](examples/tick/inst.minimal.valid.json)）：

```json
{"argv": ["aos-tick"]}
```

## P-202．任務註冊表

檔案 `.aos/tasks.json`，schema [tick-tasks.schema.json](schemas/tick-tasks.schema.json)。每一項是 inst 的超集；頂層可放每一項的預設（項自己寫了就整個蓋過）與 `modules`、`hooks`。指示詞（`$ref`、`$opt`…）開格時整份展開（頂層與每項的陌生鍵、`_metainfo` 除外）。

```json
{"_metainfo": {"_type": "aos-tasks", "_version": 1},
 "cwd": "work", "envs": {"LANG": "C.UTF-8"},
 "stdout": {"$opt": "append", "$val": "logs/tasks.log"},
 "tasks": [
   {"id": "build", "argv": ["make"]},
   {"id": "report", "argv": ["./report.sh"], "cwd": "reports"},
   {"$ref": "tasks.d/clean.json"}],
 "hooks": {"before_all": [{"argv": ["./recover.sh"]}],
           "after_task": {"build": [{"argv": ["./notify.sh"]}]}},
 "modules": {"tasks-blocked": {"insts": [{"argv": ["./check.sh"]}]}}}
```

頂層：

| 欄位 | 約束 |
|---|---|
| `_metainfo` | 可省；整份表的格式標記，核心不看 |
| `tasks` | 必填，陣列（可空）；順序就是跑的順序 |
| `argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit` | 可省；每一項的預設，格式照 inst |
| `hooks` | 可省；物件。掛點 `before_all`、`after_every_task`、`after_all` 是 inst 陣列；`after_task` 的鍵是任務 id、`before_kind`／`after_kind` 的鍵是 kind，值都是 inst 陣列。不合＝`bad_table`。行為見 [hooks](../tick/hooks.md) |
| `modules` | 可省；目前只認 `tasks-blocked`（P-214），其他鍵忽略 |

每一項：

| 欄位 | 約束 |
|---|---|
| `id` | 可省，字串；沒寫＝它在陣列的位置轉字串（`"0"`、`"3"`）。紀錄與 `AOS_TASK_ID` 都用它 |
| `_metainfo` | 可省，照 inst；跑到那一項才驗 |
| `kind` | 可省，任意非空字串（自己取名）；只拿來比對 `hooks.before_kind`／`after_kind` 與 tasks-blocked 的 `kinds`，核心不驗值 |
| 其餘 | inst 的欄位（`argv` 合併預設後必須有）；不認得的鍵照收、忽略。任務沒有 `user` |

範例檔（都在 `proto6/spec/protocol/examples/tick/`）：正例 `tasks.minimal`、`tasks.no-id`、`tasks.no-metainfo`、`tasks.defaults`、`tasks.defaults-argv`、`tasks.reference`（整項 `$ref`）、`tasks.directive`、`tasks.modules`、`tasks.unknown-key`、`tasks.custom-kind`、`tasks.hooks`、`tasks.hooks-points`、`tasks.hooks-kind`；反例 `tasks.no-argv`、`tasks.hooks-no-argv`、`tasks.hooks-not-array`、`tasks.hooks-after-task-array`、`tasks.hooks-kind-array`（檔名後接 `.valid.json`／`.invalid.json`）。`tasks.template*`、`tasks.as`、`tasks.methods*` 是暫緩區舊範本的紀錄。

## P-203．aos-tick 與任務程式

argv、結束碼、stderr 代碼詳見 `aos-tick --help` 或 `proto6/src/py/lib/aos_tick*.py`。摘要：

`aos-tick [<目標>]`：目標只能是資料夾（沒給＝cwd），底下要有 `.aos/tasks.json`。多給參數、`-` 開頭參數、目標是檔、`AOS_DIRNAME` 不合法都是用法錯。

| 結束碼 | 意思 |
|---|---|
| 0 | 預料之中：照表跑完（任務成敗不影響）、被擋下、`busy`、有擋板檔 |
| 1 | tick 自己出錯：`usage`、`no_target`、`no_tasks`、`bad_table`、自用檔讀寫壞 |

stderr 一行 `代碼: 說明`：`usage`、`no_target`、`no_tasks`、`bad_table`（回 1）、`busy`（拿不到鎖，回 0）、`exec_failed`（某項沒跑成，附該項 id，不影響下一項）。stdout 不寫。

任務環境變數（先清掉繼承來的同名變數，再放這些，再套 `envs`）：

| 變數 | 值 |
|---|---|
| `AOS_TICK_CWD` | 工作資料夾絕對路徑；本格紀錄在 `$AOS_TICK_CWD/.aos/tick/current/` |
| `AOS_TASK_ID`、`AOS_TASK_INDEX` | 這一項的 id、在 `tasks` 陣列的位置（從 0 起） |
| `AOS_HOOK_POINT`、`AOS_HOOK_INDEX`、`AOS_HOOK_ID` | 只有 hook 有：掛點名、在自己陣列的位置、hook 的 id |
| `AOS_TASK_EXIT` | 只有 `after_task`、`after_kind`、`after_every_task` 有：剛跑完那項的結束碼（被訊號 N 殺＝128+N） |

`before_all`／`after_all` 沒有 `AOS_TASK_*`；`before_kind` 有 `AOS_TASK_ID`、`AOS_TASK_INDEX`、沒有 `AOS_TASK_EXIT`。這些變數不是授權證據。全部環境變數見 C-10（[慣例](../conventions.md)）。

## P-204．aos-tick-check-task

暫緩，整條在 [暫緩區 tick 協議](../deferred/protocol/tick/02-P-204檢查任務與P-205-git.md)。條號保留、不重用。

## P-205．aos-git

暫緩，同上。

## P-206．系統訊息佇列 aos-mq 與發摘要

暫緩，在 [暫緩區](../deferred/protocol/tick/03-P-206-mq與P-211-cg.md)。現行收發信是 daemon 訊息模組的 `aos-mq`（P-125，[daemon 協議](daemon/README.md)）。

## P-208～P-210．已撤

沒有現行內容，條號不重用：

- P-208：收件區權限（舊內容在暫緩區）
- P-209：待決與跨篇（見 [README P-008](../../notes/archive/spec-2026-10-02/protocol/readme/03-P-007-P-008-schema與待決.md)）
- P-210：預設範本與恢復前驗證（見暫緩區 [B-625](../deferred/tick/05-B-625-當機恢復設定與清理.md)）

## P-211．aos-cg

暫緩，在 [暫緩區](../deferred/protocol/tick/03-P-206-mq與P-211-cg.md)。收殘留現在是 daemon 收屍模組。

## P-212．aos-as

暫緩，在 [暫緩區](../deferred/protocol/tick/01-P-207加入設定與P-212切換帳號.md)。現行切帳號只在 daemon 設定檔做（帳號模組）。

## P-213．每項結束碼紀錄、tasks-blocked 與擋板檔

### 結束碼紀錄

位置：資料夾 `.aos/tick/current/`（本格）、`.aos/tick/last/`（上一格，同結構）。只有核心寫，每個檔整份重寫。`record.json` 的 `ran`、`tasks`、`hooks` 是 `$ref`（相對 `record.json` 所在資料夾），讀法是把 `$ref` 展開（Python：`aos_tick_record.read_record(資料夾)`）：

| 檔 | 內容 |
|---|---|
| `record.json` | 開格寫一次、收尾寫一次；任務表有寫 hooks 時開格就帶 `hooks` 的 `$ref` |
| `ran.json` | 一個非負整數 |
| `task-exits.json` | 下面 `tasks` 陣列；開格寫 `[]` |
| `hook-exits.json` | 下面 `hooks` 物件；只有任務表寫了 hooks 的格才有 |

`record.json` 本體（[tick-record-file.open](examples/tick/tick-record-file.open.valid.json)）：

```json
{"version": 1, "seq": 1237, "started_at_ms": 1790000120000,
 "ran": {"$ref": "ran.json"}, "tasks": {"$ref": "task-exits.json"},
 "hooks": {"$ref": "hook-exits.json"},
 "ended": false}
```

展開後的完整紀錄（schema [tick-record](schemas/tick-record.schema.json) 的根；`?` 表示可省）：

```json
{"version": 1, "seq": N, "started_at_ms": 毫秒, "ran": 跑了幾項,
 "tasks": [{"id": …, "index": 位置, "exit": 非0碼} | {"id": …, "index": 位置, "signal": 號}],
 "ended": bool, "exit"?: 0, "blocked_before"?: "<id>",
 "skipped"?: [{"id": …, "index": 位置}],
 "hooks"?: {"before_all"?: [{"id": …, "index": 位置, "exit": 非0碼} | {…, "signal": 號}],
            "before_kind"?: [同 after_task],
            "after_task"?: [{"id": …, "index": 位置, "task_index": 任務位置, "exit": 非0碼} | {…, "signal": 號}],
            "after_kind"?: [同 after_task],
            "after_every_task"?: [同 after_task],
            "after_all"?: [同 before_all]}}
```

| 欄位 | 約束 |
|---|---|
| `seq` | 本資料夾的格數，從 1 起；沒有紀錄的格（`busy`、擋板檔、`bad_table`）不佔號 |
| `ran` | 本格已跑完幾項 tasks（含結束碼非 0 的；被擋掉沒跑的不算）；開格 0 |
| `tasks` | 已跑完**而且結束碼不是 0** 的項，照順序；結束碼 0 的不記。`index` 是在 `tasks` 陣列的位置；`exit`（1～255）與 `signal`（1～64）二選一，照實記原碼 |
| `ended` | 照表跑完或被擋下、所有 hooks 跑完後為 true，此時必有 `exit`；false 時不得有 `exit`、`blocked_before`、`skipped` |
| `exit` | 只會是 `0`（有紀錄收尾時 tick 一定回 0） |
| `blocked_before` | 被 tasks-blocked「全部擋」時，被擋下沒跑那一項的 id；只在 `ended:true` 時有 |
| `skipped` | 被 tasks-blocked 的 `kinds` 跳過（後面照跑）的項，每筆 `{"id","index"}`；只在 `ended:true` 時有；不算 `ran`、不進 `tasks` |
| `hooks.<掛點>` | 該掛點已跑完而且結束碼非 0 的 hook，格式同 `tasks`；`index` 是在自己那個陣列的位置；`after_task`、`after_every_task`、`before_kind`、`after_kind` 每筆另有 `task_index`（觸發它的任務位置）。hooks 不記 `ran` |
| `started_at_ms` | 只給人看 |

schema 管不到、由 [validate.py](examples/messages/validate.py) 補查：`tasks`、`before_all`、`after_all`、`skipped` 的 `index` 嚴格遞增；`tasks` 的 `index` 小於 `ran`＋`skipped` 筆數；帶 `task_index` 的各掛點 `task_index` 不遞減且小於該數。

範例檔（`examples/tick/`）：正例 `tick-record.minimal`（跑到一半）、`done`、`blocked-exit-0`、`blocked-first`、`exit-0-with-failure`、`position-id`、`hooks`、`hooks-points`、`hooks-running`、`hooks-kind`、`skipped`、`tick-record-file.open`、`tick-record-file.hooks`、`tick-record-file.hooks-running`；反例見同資料夾 `tick-record*.invalid.json`（exit 與 signal 並存、ended 沒 exit、記了結束碼 0、缺 `ran`／`index`／`task_index`、整格回 1／2／3、`ran` 直接寫數字等）。

### tasks-blocked 與擋板檔

| 檔 | 內容與行為 |
|---|---|
| `.aos/tick/tasks-blocked` | 每一項前重讀。內容是 JSON 物件且有 `"kinds":["字串",…]`＝按 kind 擋（只跳過 `kind` 在清單內的項，後面照跑，記 `skipped`；`[]` 一個都不擋）；其他形狀（空檔、非 JSON、資料夾、沒 `kinds`）＝全部擋（這項與後面都不跑，記 `blocked_before`）。兩種 stderr 都不印、`after_all` 照跑；整格最後核心刪掉 |
| `.aos/tick-blocked`（擋板檔） | 核心只看存不存在、不讀內容；有就不開格、hooks 不跑、stderr 不印、回 0，紀錄與 `seq` 都不動 |

## P-214．tick 模組 `tasks-blocked`

寫法（行為見 [tasks-blocked](../tick/tasks-blocked.md)；schema 是 tick-tasks 的 `modules["tasks-blocked"]`）：

```json
{"tasks": [...],
 "modules": {"tasks-blocked": {"insts": [
   {"id": "notify", "argv": ["sh", "-c", "echo \"$AOS_TASK_ID 被擋下\" >> blocked.log"]},
   {"$ref": "clear-if-ok.json"}]}}}
```

| 位置 | 約束 |
|---|---|
| `modules["tasks-blocked"]` | 物件（可 `$ref`）；有寫就掛上，不是物件＝`bad_table`；裡面陌生鍵不解 |
| `.insts` | 必填，陣列（可 `$ref`、可為空）；不是陣列或沒寫＝`bad_table` |
| `insts` 每一項 | 寫法與展開同 `tasks` 每一項（inst 物件或整項 `$ref`；合併頂層預設後要有 `argv`；`id` 可省，沒寫＝位置字串） |

環境變數照任務（`AOS_TASK_ID`、`AOS_TASK_INDEX`＝被擋下那一項、`AOS_TICK_CWD`；沒有 `AOS_HOOK_*`）；結束碼不進紀錄。舊鍵名 `tasks_blocked` 是陌生鍵、不掛。範例 `examples/tick/tasks.tasks-blocked.valid.json`；反例 `tasks.tasks-blocked-no-insts`、`tasks.tasks-blocked-no-argv`。
