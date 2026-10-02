# proto6/src/py — aos-tick

← [proto6/src/py README](../README.md)｜上一份：[改動 1–4](changes.md)｜下一份：[hooks 與 tasks-blocked](hooks.md)

## aos-tick（第一段 tick 核心，新寫）

照 [plan 第一段](../../../plan/m1-tick-core.md) 寫的，不是從 proto5 複製。最小例子：

```sh
mkdir -p /tmp/n/.aos
echo '{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[{"id":"t","argv":["true"]}]}' > /tmp/n/.aos/tasks.json
proto6/src/py/bin/aos-tick /tmp/n; echo $?            # 0
cat /tmp/n/.aos/tick/current/record.json              # {"version":1,"seq":1,...,"ran":{"$ref":"ran.json"},...,"ended":true,"exit":0}
PYTHONPATH=proto6/src/py/lib python3 -c 'import aos_tick_record as r; print(r.read_record("/tmp/n/.aos/tick/current"))'   # 展開後的完整紀錄
cd /tmp/n && proto6/src/py/bin/aos-tick               # 不給目標用目前目錄（相對路徑也行）
proto6/src/py/bin/aos-tick /tmp/n/.aos/tasks.json; echo $?   # 1，stderr usage:（目標要是資料夾）
```

**目標怎麼認（使用者 2026-10-01，見 [verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit.md#aos-tick---node-怎麼認待統一更新-spec)、[plan 待問 10、16、17](../../../plan/m1-tick-core.md#待問)，待統一更新 spec；同日 `--node` 改名 `--target`，再改成位置參數 `aos-tick [<目標>]`（跟 aos-exec 一樣），`--target` 旗標不留，給了算用法錯；目標多於一個也是）**：省略用 `./`，相對路徑轉成絕對。目標只能是資料夾，任務表只有 `<目標>/.aos/tasks.json` 一個位置（不看 `.aos/inst.json`），沒有回 1、stderr `no_tasks:`。給的是檔回 1、stderr `usage:`（說明目標要是資料夾），什麼都不建。不存在回 1、stderr `no_target:`（原 `no_node:`）。~~是檔：拿這個檔當這一格的任務表、它所在的資料夾當工作資料夾；檔在 `.aos/` 裡時取 `.aos` 的上一層。~~（使用者 2026-10-01 撤回）

**工作資料夾與給任務的環境變數（使用者 2026-10-01，見 [plan 待問 16](../../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：「工作資料夾」＝這一格 aos-tick 的 cwd（目標指的資料夾）。每項任務的環境多三個變數：`AOS_TICK_CWD`（工作資料夾的絕對路徑，原 `AOS_NODE_DIR`）、`AOS_TASK_ID`、`AOS_TASK_INDEX`（hooks 的項改給 `AOS_HOOK_*`，見下面「hooks」一節；繼承來的 `AOS_TASK_*`／`AOS_HOOK_*` 先拿掉再放這一項的，`aos_tick_run.RUN_VARS`）。~~`AOS_TICK_RECORD`~~ 拿掉：任務要看紀錄就讀 `$AOS_TICK_CWD/<狀態資料夾>/tick/current/`（`AOS_DIRNAME` 空字串時是 `$AOS_TICK_CWD/tick/current/`；第九批拆檔，見下面「結束碼紀錄」）。node 是之後 aos-tick 的 node 模組的事，tick 這層不談。

| 檔 | 內容 |
|---|---|
| `bin/aos-tick` | 命令列薄殼（`.gitignore` 擋 `bin/`，`git add -f` 進來的） |
| `lib/aos_tick.py` | argv、`AOS_DIRNAME` 檢查、認工作資料夾與任務表 `resolve_target()`、取鎖 `take_lock()`、擋板、tasks-blocked `tasks_blocked()`／`clear_tasks_blocked()`、整格順序 `run_tick()` |
| `lib/aos_tick_record.py` | 結束碼紀錄資料夾 `tick/current/`／`last/`：開格換紀錄（整個資料夾 rename）、每項寫 `ran.json`、不是 0 才寫 `task-exits.json`／`hook-exits.json`、收尾寫 `record.json`（使用者 2026-10-01 第八、九批）；`read_record()` 讀展開 `$ref` 後的完整紀錄 |
| `lib/aos_tick_table.py` | 讀任務表（`.aos/tasks.json`）、開格整份展開（第二十批）、頂層預設、極簡檢查 `check_table()`、每項的 `id`、跑到時合併預設交給 inst 規則 `load_inst()` |
| `lib/aos_tick_run.py` | 跑一項：照 inst 開串流、這一項的 `AOS_*`（先拿掉繼承來的 `AOS_TASK_*`／`AOS_HOOK_*`）、分 exit／signal |
| `lib/aos_tick_hooks.py` | hooks（外掛掛點，m1h；第十七批四個掛點）：`run_point()` 跑一個掛點的一串、`run_after_task()` 在每項之後跑 `after_task.<id>` 與 `after_every_task`（讀表與極簡檢查在 `aos_tick_table.check_table()`，結果是 `Table.before_all`／`after_task`／`after_every_task`／`after_all`） |
| `tests/test_tick_target.py`、`test_tick_table.py`、`test_tick_blocked.py`、`test_tick_run.py`、`test_tick_dirname.py`（原 `test_tick.py`，共用 `_tick_util.py`） | plan 各步的驗收，一個類別一步；結束碼慣例另成 `ExitCodes`（在 `test_tick_run.py`） |
| `tests/test_tick_hooks_after_all.py`、`test_tick_hooks_points.py`（原 `test_tick_hooks.py`，共用 `_tick_hooks_util.py`） | hooks 的驗收（m1h） |

**任務表的頂層預設與展開時機（使用者 2026-10-01，待統一更新 spec）**：頂層可放 inst 的七個欄位 `argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit` 當每一項的預設；頂層 `_metainfo`（整份表的格式標記，可省）、`id`、`kind` 不是預設，其他鍵當陌生鍵忽略。頂層也可選 `modules`（比照 daemon 設定檔，放 tick 模組的設定；目前沒有模組，核心照收不理、不當預設）。頂層還可選 `hooks`（外掛掛點，不是模組，見下面「hooks」一節）。

〔使用者裁定 2026-10-01，[verdicts 11 第三批](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)〕頂層 `_metainfo` 可省；每項 `_metainfo` 照 inst 規則（沒寫＝posix 第 1 版，寫了跑到那一項才由 `aos_inst` 驗，驗不過自然丟錯回 1）。`modules` 讀表時整個展開（跟 daemon 設定檔的 `expand()` 同做法），展開失敗＝`bad_table:`、回 1。

淺層合併：項自己寫了某個鍵就整個蓋過頂層那個（`envs` 也整包換掉，不逐變數合併）。合併後要有 `argv`（項自己有或頂層有），不然 `bad_table:`、回 1。

頂層 `cwd` 不改 tick 自己的 cwd（tick 永遠在工作資料夾跑，鎖、紀錄都在工作資料夾的 `.aos/`），只是任務的預設 cwd，相對以工作資料夾為起點。

讀表時（開格）**整份展開**〔使用者 2026-10-01 第二十批：「tasks.json改成全部解完」「除了陌生鍵和_metainfo」〕：整份是指示詞先解；七個預設鍵、`modules`、`tasks`／`hooks` 各掛點／`modules["tasks-blocked"].insts` 每一元素（整項解一層後）裡的已知鍵（七個 inst 欄位、`id`、`kind`）都一路展開到底；選項物件 `$opt` 原樣留、`$val` 也展開。頂層與每項的陌生鍵、`_metainfo` 不解。相對檔名以工作資料夾為中心，`$ref:""`／`#…` 指整份 tasks.json；任何一個解不開＝`bad_table:`、不開格。

值在開格那一刻就定了：前面的任務改了被 `$ref` 的檔，後面的項看不到；指向前面任務才會產生的檔，開格就 `bad_table`。跑到某一項只合併（預設＋這一項）、交給 `aos_inst.load_obj` 照 inst 規則驗與換算路徑（`cwd` 以工作資料夾為中心，其他路徑以解出的 cwd 為中心）；~~這時才展開、`$ref:""`／`#…` 指合併後的這一項~~（第二十批推翻）。

```json
{
  "cwd": "work",
  "envs": {"LANG": "C.UTF-8"},
  "stdout": {"$opt": "append", "$val": "logs/tasks.log"},
  "tasks": [
    {"id": "build", "argv": ["make"]},
    {"id": "report", "argv": ["./report.sh"], "cwd": "reports"},
    {"$ref": "tasks.d/clean.json"}
  ]
}
```

`build` 在 `<工作資料夾>/work` 跑、輸出接在 `work/logs/tasks.log`；`report` 自己寫了 cwd，在 `<工作資料夾>/reports` 跑（stdout 預設照用，接在 `reports/logs/tasks.log`）；第三項整項從 `<工作資料夾>/tasks.d/clean.json` 讀，再套預設。跟 daemon 設定檔比：頂層 `cwd` 都不影響程式自己、相對路徑起點都是程式自己的 cwd（tick 的是工作資料夾），但 daemon 設定檔整份先展開，tasks.json 只展開到 `tasks` 這層。

**同資料夾互斥與讀表時機（使用者 2026-10-01，見 [verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit.md#aos-tick-最簡互斥與讀表時機待統一更新-spec)、[plan 待問 12](../../../plan/m1-tick-core.md#待問)）**：一格照「認工作資料夾與任務表 → 取鎖 → 擋板 → 讀表 → 換紀錄 → 刪停格檔 → 照表跑」。鎖是 `.aos/tick.lock` 的非阻塞 `flock`（不存在就建），拿不到 `busy:`、回 ~~2~~ 0（結束碼慣例改版）；鎖 fd 不傳給任務（`os.open` 預設不可繼承）。表壞在換紀錄之前，不算開過一格。

**`AOS_DIRNAME`（使用者 2026-10-01，見上面改動 3、[plan 待問 13、15](../../../plan/m1-tick-core.md#待問)）**：本節所有 `.aos` 都是這個名字；不合法 stderr `usage:`、回 1。設成空字串時 `tasks.json`、`tick.lock`、`tick-blocked`、`tick/tasks-blocked`、`tick/current/`／`last/` 都直接在工作資料夾下（`take_lock()` 不建資料夾）。

**POC 默認一切正常（使用者 2026-10-01，見 [plan 第一段待問 8](../../../plan/m1-tick-core.md#待問)）**：~~不取鎖（不回 75、沒有 `AOS_TICK_LOCK_FD`）、~~（同日加回最簡互斥，見上段；仍不回 75、沒有 `AOS_TICK_LOCK_FD`）不驗表（不回 2、沒有 `config_invalid`）、不看 `user`（不回 125、沒有 `user_mismatch`）、不判上下層、不做 `--firstdo-fsync`、不處理紀錄讀不懂或寫不進。出事就讓 Python 自然丟錯（traceback、回 1）。~~整格只回 0／1；argv 用法錯回 2。~~（10-01 再改，見下段）

**結束碼照 aos 體系慣例（使用者 2026-10-01，同日改版，見 [verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)、[plan 待問 9、15](../../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：0＝預料之中（含正常中斷）、非 0＝要額外處理、1＝通用錯誤（~~0 正常結束、1 錯誤結束、2 正常中斷~~）。`aos-tick` 的碼只講 tick 自己，現在只回 0／1：

| 狀況 | 回 |
|---|---|
| 照表跑完（不管任務回幾、成敗） | 0 |
| 被 `.aos/tick/tasks-blocked` 擋下（每一項之前看、只看存不存在、stderr 不印，剩下不跑；整格最後刪，第十六批） | 0 |
| 同資料夾上一格還沒跑完（拿不到 `.aos/tick.lock`，stderr `busy:`），不開格（不寫紀錄、不加 `seq`） | 0（原 2） |
| 有擋板檔 `.aos/tick-blocked`（只看存不存在、stderr 不印、hooks 不跑，第十六批），不開格（不寫紀錄、不加 `seq`） | 0（原 2） |
| argv 用法錯、`AOS_DIRNAME` 不合法、目標給的是檔、目標指的東西不存在、目標資料夾底下沒有 `.aos/tasks.json`、任務表不合極簡檢查（stderr `usage:`／`no_target:`／`no_tasks:`／`bad_table:`；表壞不換紀錄、不加 `seq`） | 1 |
| tick 自用檔（`tick-blocked`、`stop`、`tick/current/`、`tick/last/` 裡的紀錄檔）讀不到／寫不進／格式壞 | 1（自然丟錯，traceback 進 stderr） |

任務回 0、1、2、125～127、被訊號殺都照實記進紀錄、照常跑下一項。紀錄收尾的 `exit` 因此只會是 0。

**結束碼紀錄（B-633、P-213；使用者 2026-10-01 第九批拆檔）**：「把容易被改動的弄成$ref指向其他檔案，不容易被改動的留在current.json」。一格是一個資料夾 `.aos/tick/current/`（上一格 `last/`，同結構），四個檔：

| 檔 | 內容 | 什麼時候寫 |
|---|---|---|
| `record.json` | `version`、`seq`、`started_at_ms`、`ended`、`exit`、`blocked_before`，加上 `"ran":{"$ref":"ran.json"}`、`"tasks":{"$ref":"task-exits.json"}`，有 hooks 時再加 `"hooks":{"$ref":"hook-exits.json"}` | 開格、收尾各一次 |
| `ran.json` | 一個數字：本格跑完幾項 | 開格 `0`，每跑完一項 |
| `task-exits.json` | 結束碼不是 0 的任務 `[{"id","index","exit"\|"signal"}…]` | 開格 `[]`，有失敗才重寫 |
| `hook-exits.json` | `{"before_all":[…],"after_task":[…],"after_every_task":[…],"after_all":[…]}`（寫了哪幾個掛點就有哪幾個），結束碼不是 0 的 hook；跟任務有關的帶 `task_index` | 任務表有 hooks 時**開格**就寫好各掛點的 `[]`（第十七批），有失敗才重寫 |

換紀錄＝刪 `last/`、`current/` 整個 rename 成 `last/`、暫存資料夾 `.current.tmp/` rename 成 `current/`；`$ref` 是相對路徑，改名後仍指得對。`seq` 從 `current/record.json`（沒有就 `last/record.json`）接著數。舊的 `current.json`／`last.json` 不再使用、不遷移。

### review 導讀

讀的順序：

0. `lib/aos_dirname.py`：`AOS_DIRNAME` 的名字與合法判斷（aos-exec 也用）。
1. `lib/aos_tick.py` 的 `run_tick()`／`_run_locked()`：整格照 B-620「一格怎麼走」一行一步，先看它知道全貌。
2. 同檔 `resolve_target()`、`take_lock()`、`state()`、`tasks_blocked()`、`clear_tasks_blocked()`、`run_one()`。
3. `lib/aos_tick_record.py`：`Record.open()`（換檔四步）→ `add_task()`／`finish()` → `_rewrite()`。
4. `lib/aos_tick_table.py`：`read_table()` → `check_table()`（回 `Table`：預設、各項、id）、`merge()`、`load_inst()`。
5. `lib/aos_tick_run.py`：`run_item()`。
6. `tests/test_tick_*.py`（原 `test_tick.py`）：`Step1Target`、`Step1Lock`…`Step4Defaults`（頂層預設）…`Step9Whole`、`DirName`、`EmptyDirName`，對著 plan 各步的驗收讀。

每個函式開頭一行註明對應的 spec 條號。

plan 步驟對到哪：

| 步驟 | 函式 |
|---|---|
| 1 找資料夾、取鎖 | `main()`、`resolve_target()`、`take_lock()` |
| 2 擋板檔、結束碼 | `_run_locked()`（擋板只看 `os.path.lexists`）、`say()` |
| 3 紀錄與格數 | `Record.open()`、`_read_seq()`、`_rewrite()` |
| 4 讀表 | `aos_tick_table.read_table()`、`check_table()` |
| 5 照表跑 | `run_tick()` 迴圈、`run_one()`、`aos_tick_run.run_item()` |
| 6 tasks-blocked（原停格檔，第十六批） | `run_tick()` 迴圈裡每項之前的 `tasks_blocked()`、最後的 `clear_tasks_blocked()` |
| 6b `modules["tasks-blocked"]`（B-636，第十六批） | 讀表 `aos_tick_table._tasks_blocked()`（`Table.on_blocked`）、跑 `aos_tick.run_on_blocked()` |
| 7、8 | 2026-10-01 取消（fsync、上下層） |

我自己做的判斷（spec 沒寫死、照「最小合理」做，都可以改）：

- ~~沒有 `.aos/`：整個交給 `aos_exec.run_target` 跑這個資料夾（不寫紀錄、退出碼照 aos-exec）；連 `inst.json` 也沒有時是 aos-exec 自己的用法錯 2。~~（2026-10-01 作廢：退路拿掉，沒有 `.aos/inst.json` 就 stderr `no_inst:`、回 1；只看在不在，不讀它的內容。）~~見 `aos_tick.run_tick` 開頭。~~（2026-10-01 再改：改看 `.aos/tasks.json`，見 `aos_tick.resolve_target`）
- 新增的 stderr 代碼：`usage`（argv 錯、`AOS_DIRNAME` 不合法、目標給的是檔）、`busy`（拿不到鎖）、~~`no_inst`（沒有 `.aos/inst.json`）~~、`no_tasks`（資料夾沒有 `.aos/tasks.json`）、`no_target`（目標指的東西不存在；原 `no_node`）、`bad_table`（任務表不合極簡檢查）、`exec_failed`（某項沒跑成：mkdir／cwd／重導向失敗、126／127）。
- 某項沒跑成（mkdir、cwd、重導向失敗）記 `exit:125`，跟 aos-exec 命令列一致（inst 的規定，不是帳號判定）。
- ~~項目（合併頂層預設後）是純記憶體文件，所以項目裡的 `$ref:""` 指合併後的這一項~~〔第二十批〕開格整份展開，`$ref:""` 指整份 tasks.json。
- 任務的 id 用開格讀表時拿到的（已展開）；跑到時只做 inst 規則的驗證與路徑換算。
- `envs` 清空時一個 `AOS_*` 都不放。
- 任務表極簡檢查（使用者 2026-10-01，[verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit.md#aos-tick-讀任務表的極簡檢查待統一更新-spec)）：合法 JSON、頂層物件有 `tasks` 陣列、每項（解一層後）是物件、合併頂層預設後有 `argv`（讀表那層解不開也算）；不過 stderr 一行 `bad_table:`、回 1。~~檢查在換紀錄之後，表壞仍佔 `seq`、紀錄停在 `ended:false`。~~（使用者 2026-10-01 改：在換紀錄之前，表壞不換紀錄、不加 `seq`）每項沒寫 `_metainfo` 照跑（`aos_inst` 當 posix 第 1 版）；寫錯了跑到那項時 `aos_inst` 自然丟錯回 1。
- 沒 `id` 的項（使用者 2026-10-01）：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串，紀錄、`AOS_TASK_ID`、`blocked_before` 都用它；跟別項撞了不管。`id` 不是字串時 `AOS_TASK_ID` 用 `str()`（我自己定的）。
- ~~目標給的檔在 `.aos/` 裡時工作資料夾取 `.aos` 的上一層；目標給檔時，項目裡的相對檔名以工作資料夾為中心。~~（使用者 2026-10-01 撤回「目標給檔就當任務表」，兩條跟著作廢；給檔現在是用法錯）
