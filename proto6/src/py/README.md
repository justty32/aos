# proto6/src/py

← [proto6 plan](../../plan/README.md)

inst 與 `aos-exec` 直接從 proto5 複製（proto5 `470f5a04`，即 `git log -1 --format=%h -- proto5/lib proto5/cli`），不重寫。說明文件看 proto5 的 [lib/docs/exec.md](../../../proto5/lib/docs/exec.md)、[directives.md](../../../proto5/lib/docs/directives.md)。

| 這裡 | 來源 | 內容改了什麼 |
|---|---|---|
| `bin/aos-exec` | `proto5/cli/aos-exec` | 沒改（它本來就找 `../lib`）。repo 的 `.gitignore` 擋 `bin/`，這檔是 `git add -f` 進來的 |
| `lib/aos_directives.py` | `proto5/lib/` 同名檔 | 沒改 |
| `lib/aos_exec.py`、`aos_exec_run.py`、`aos_exec_spawn.py` | `proto5/lib/` 同名檔 | 改動 2、改動 3、改動 4 |
| `lib/aos_dirname.py` | 新寫 | 改動 3：`AOS_DIRNAME`，aos-exec 與 aos-tick 共用 |
| `lib/aos_inst.py` | `proto5/lib/aos_inst.py` | 沒改（改動 1 已撤回，2026-10-01） |
| `tests/test_inst.py`、`test_directives.py` | `proto5/lib/test/` 同名檔 | 沒改 |
| `tests/test_exec.py`、`test_exec_full.py` | `proto5/lib/test/` 同名檔 | 跟著改動 2、3、4 改，另加一條「頂層 `user` 忽略」（標「proto6 改／新增」） |
| `tests/test_exec_spawn.py` | `proto5/lib/test/` 同名檔 | 只加改動 3 的一條（標「proto6 新增」） |
| `tests/_util.py` | `proto5/lib/test/_util.py` | 只改 `LIB`、`EXEC` 兩行路徑 |
| ~~`tests/test_user.py`~~ | ~~新寫~~ | 2026-10-01 跟改動 1 一起刪掉 |
| `bin/aos-daemon`、`lib/aos_daemon.py`、`tests/test_daemon.py` | 新寫 | 第三段最核心 daemon，見下面 [aos-daemon](#aos-daemon第三段最核心-daemon) |
| `lib/aos_daemon_ctl.py`、`bin/aos-ctl`、`lib/aos_ctl.py`、`tests/test_ctl.py` | 新寫 | daemon 的控制模組與送指令的小工具，見下面 [控制模組與 aos-ctl](#控制模組與-aos-ctlm3n)。`bin/aos-ctl` 一樣被 `.gitignore` 擋，要 `git add -f` |
| `lib/aos_daemon_reload.py`、`lib/aos_daemon_state.py`、`tests/test_daemon_reload.py`、`tests/test_daemon_state.py` | 新寫 | daemon 的重讀設定、記住狀態兩個模組，見下面 [重讀設定與記住狀態](#重讀設定與記住狀態m3m) |

現在跟 proto5 不同的只剩改動 2（資料夾目標找 inst 的位置）、改動 3（那個位置的 `.aos` 照 `AOS_DIRNAME`）與改動 4（用法錯回 1）。

## ~~改動 1：認得頂層 `user`~~（2026-10-01 撤回）

使用者 2026-10-01（原話「aos-exec應該也不需要認得頂層user吧。」，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-exec-不認得頂層-user待統一更新-spec)）：`lib/aos_inst.py` 換回 proto5 原檔，`user` 當不認得的鍵照 inst 規則忽略、照目前身分跑；`UserNotGranted`／`UserInvalid`、`test_user.py`（7 條）一併拿掉。aos-tick 原本「交給 `load_obj` 前先拿掉 `user`」因此多餘，也拿掉了。

~~原本：`aos_inst._check_user()` 在解任何指示詞之前看原始頂層的 `user` 字面值；跟目前身分不同 `UserNotGranted`、型別錯等 `UserInvalid`，都是 125。~~

## 改動 2：資料夾目標怎麼找 inst

照 [inst.md「inst 目標」](../../spec/base/inst.md)：

- 目標是資料夾：先找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json`；兩個都有跑前者；都沒有＝用法錯（~~2~~ 1，見改動 4）。base 是 `xxx` 自己。
- 拿掉 proto5 的 `--dir-target` 旗標、`run_target`／`run_target_full`／`spawn_target` 的 `dir_target` 參數與 `DEFAULT_DIR_TARGET` 常數（改成 `DIR_TARGETS` 兩個位置）。給 `--dir-target` 現在是用法錯。
- 檔案目標照 proto5 不動。~~tick 那條「`.aos/inst.json`／`inst.json` 路徑正規化成資料夾」不在這裡做。~~（2026-10-01：tick 不再做這個正規化，目標（原 `--node`、`--target`，現在是位置參數）怎麼認見下面 aos-tick 一節）

## 改動 3：`AOS_DIRNAME`（2026-10-01）

使用者 2026-10-01（[verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos_dirname-狀態資料夾的名字待統一更新-spec)，待統一更新 spec）：環境變數 `AOS_DIRNAME` 決定狀態資料夾的名字，之後 aos 所有程式都照它。判斷只在 `lib/aos_dirname.py` 一處（`name()`、`error()`）。

- 三態（同日再改）：**沒設**＝`.aos`；**設了但空字串**＝不用子資料夾、直接用資料夾本身（`name()` 回 `""`）；其他值＝這個名字。含 `/`、或是 `.`、`..` 算不合法（空字串合法）。
- aos-exec：資料夾目標改成先找 `xxx/<名字>/inst.json`、再找 `xxx/inst.json`（`aos_exec_run._dir_targets()`；`DIR_TARGETS` 常數留著當預設名字的樣子）；空字串時只找 `xxx/inst.json`。名字不合法：資料夾目標算用法錯，~~照 aos-exec 現有的碼回 2~~ 回 1（改動 4）；`spawn_target` 丟 `SpawnFailed`。直接給檔、`.json` 目標不受影響。

## 改動 4：結束碼慣例，用法錯回 1（2026-10-01）

使用者 2026-10-01 改版的 aos 結束碼慣例（[verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)，待統一更新 spec）：0＝預料之中、非 0＝要額外處理、1＝通用錯誤，沒特別指定碼的錯都 1。aos-exec 的用法錯由 proto5 的 2 改 1（`aos_exec_run.EXIT_USAGE`；argparse 的用法錯也改回 1，見 `aos_exec._Parser`）。`run_target()` 回的 `(code, "usage")` 的 code 也是 1。

aos-exec 現在的碼：

| 狀況 | 回 |
|---|---|
| 子程式跑完一次：它的碼原樣（含 0、128+N、找不到程式 127、沒執行權 126） | 原碼 |
| aos-exec 自己失敗、那次沒跑（inst 壞、`.json` 不存在、mkdir／cwd／重導向失敗） | 125 |
| 用法錯（argv、`--timeout-ms` 負數、目標不存在、資料夾找不到 inst、inst 目標給 `--`、`AOS_DIRNAME` 不合法） | 1 |
| 沒接住的例外 | 1（Python 預設） |
| `-h`／`--help` | 0 |

## aos-tick（第一段 tick 核心，新寫）

照 [plan 第一段](../../plan/m1-tick-core.md) 寫的，不是從 proto5 複製。最小例子：

```sh
mkdir -p /tmp/n/.aos
echo '{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[{"id":"t","argv":["true"]}]}' > /tmp/n/.aos/tasks.json
proto6/src/py/bin/aos-tick /tmp/n; echo $?            # 0
cat /tmp/n/.aos/tick/current/record.json              # {"version":1,"seq":1,...,"ran":{"$ref":"ran.json"},...,"ended":true,"exit":0}
PYTHONPATH=proto6/src/py/lib python3 -c 'import aos_tick_record as r; print(r.read_record("/tmp/n/.aos/tick/current"))'   # 展開後的完整紀錄
cd /tmp/n && proto6/src/py/bin/aos-tick               # 不給目標用目前目錄（相對路徑也行）
proto6/src/py/bin/aos-tick /tmp/n/.aos/tasks.json; echo $?   # 1，stderr usage:（目標要是資料夾）
```

**目標怎麼認（使用者 2026-10-01，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick---node-怎麼認待統一更新-spec)、[plan 待問 10、16、17](../../plan/m1-tick-core.md#待問)，待統一更新 spec；同日 `--node` 改名 `--target`，再改成位置參數 `aos-tick [<目標>]`（跟 aos-exec 一樣），`--target` 旗標不留，給了算用法錯；目標多於一個也是）**：省略用 `./`，相對路徑轉成絕對。目標只能是資料夾，任務表只有 `<目標>/.aos/tasks.json` 一個位置（不看 `.aos/inst.json`），沒有回 1、stderr `no_tasks:`。給的是檔回 1、stderr `usage:`（說明目標要是資料夾），什麼都不建。不存在回 1、stderr `no_target:`（原 `no_node:`）。~~是檔：拿這個檔當這一格的任務表、它所在的資料夾當工作資料夾；檔在 `.aos/` 裡時取 `.aos` 的上一層。~~（使用者 2026-10-01 撤回）

**工作資料夾與給任務的環境變數（使用者 2026-10-01，見 [plan 待問 16](../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：「工作資料夾」＝這一格 aos-tick 的 cwd（目標指的資料夾）。每項任務的環境多三個變數：`AOS_TICK_CWD`（工作資料夾的絕對路徑，原 `AOS_NODE_DIR`）、`AOS_TASK_ID`、`AOS_TASK_INDEX`（hooks 的項改給 `AOS_HOOK_*`，見下面「hooks」一節；繼承來的 `AOS_TASK_*`／`AOS_HOOK_*` 先拿掉再放這一項的，`aos_tick_run.RUN_VARS`）。~~`AOS_TICK_RECORD`~~ 拿掉：任務要看紀錄就讀 `$AOS_TICK_CWD/<狀態資料夾>/tick/current/`（`AOS_DIRNAME` 空字串時是 `$AOS_TICK_CWD/tick/current/`；第九批拆檔，見下面「結束碼紀錄」）。node 是之後 aos-tick 的 node 模組的事，tick 這層不談。

| 檔 | 內容 |
|---|---|
| `bin/aos-tick` | 命令列薄殼（`.gitignore` 擋 `bin/`，`git add -f` 進來的） |
| `lib/aos_tick.py` | argv、`AOS_DIRNAME` 檢查、認工作資料夾與任務表 `resolve_target()`、取鎖 `take_lock()`、擋板、tasks-blocked `tasks_blocked()`／`clear_tasks_blocked()`、整格順序 `run_tick()` |
| `lib/aos_tick_record.py` | 結束碼紀錄資料夾 `tick/current/`／`last/`：開格換紀錄（整個資料夾 rename）、每項寫 `ran.json`、不是 0 才寫 `task-exits.json`／`hook-exits.json`、收尾寫 `record.json`（使用者 2026-10-01 第八、九批）；`read_record()` 讀展開 `$ref` 後的完整紀錄 |
| `lib/aos_tick_table.py` | 讀任務表（`.aos/tasks.json`）、開格整份展開（第二十批）、頂層預設、極簡檢查 `check_table()`、每項的 `id`、跑到時合併預設交給 inst 規則 `load_inst()` |
| `lib/aos_tick_run.py` | 跑一項：照 inst 開串流、這一項的 `AOS_*`（先拿掉繼承來的 `AOS_TASK_*`／`AOS_HOOK_*`）、分 exit／signal |
| `lib/aos_tick_hooks.py` | hooks（外掛掛點，m1h；第十七批四個掛點）：`run_point()` 跑一個掛點的一串、`run_after_task()` 在每項之後跑 `after_task.<id>` 與 `after_every_task`（讀表與極簡檢查在 `aos_tick_table.check_table()`，結果是 `Table.before_all`／`after_task`／`after_every_task`／`after_all`） |
| `tests/test_tick.py` | plan 各步的驗收，一個類別一步；結束碼慣例另成 `ExitCodes` |
| `tests/test_tick_hooks.py` | hooks 的驗收（m1h） |

**任務表的頂層預設與展開時機（使用者 2026-10-01，待統一更新 spec）**：頂層可放 inst 的七個欄位 `argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit` 當每一項的預設；頂層 `_metainfo`（整份表的格式標記，可省）、`id`、`kind` 不是預設，其他鍵當陌生鍵忽略。頂層也可選 `modules`（比照 daemon 設定檔，放 tick 模組的設定；目前沒有模組，核心照收不理、不當預設）。頂層還可選 `hooks`（外掛掛點，不是模組，見下面「hooks」一節）。

〔使用者裁定 2026-10-01，[verdicts 11 第三批](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)〕頂層 `_metainfo` 可省；每項 `_metainfo` 照 inst 規則（沒寫＝posix 第 1 版，寫了跑到那一項才由 `aos_inst` 驗，驗不過自然丟錯回 1）。`modules` 讀表時整個展開（跟 daemon 設定檔的 `expand()` 同做法），展開失敗＝`bad_table:`、回 1。

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

**同資料夾互斥與讀表時機（使用者 2026-10-01，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick-最簡互斥與讀表時機待統一更新-spec)、[plan 待問 12](../../plan/m1-tick-core.md#待問)）**：一格照「認工作資料夾與任務表 → 取鎖 → 擋板 → 讀表 → 換紀錄 → 刪停格檔 → 照表跑」。鎖是 `.aos/tick.lock` 的非阻塞 `flock`（不存在就建），拿不到 `busy:`、回 ~~2~~ 0（結束碼慣例改版）；鎖 fd 不傳給任務（`os.open` 預設不可繼承）。表壞在換紀錄之前，不算開過一格。

**`AOS_DIRNAME`（使用者 2026-10-01，見上面改動 3、[plan 待問 13、15](../../plan/m1-tick-core.md#待問)）**：本節所有 `.aos` 都是這個名字；不合法 stderr `usage:`、回 1。設成空字串時 `tasks.json`、`tick.lock`、`tick-blocked`、`tick/tasks-blocked`、`tick/current/`／`last/` 都直接在工作資料夾下（`take_lock()` 不建資料夾）。

**POC 默認一切正常（使用者 2026-10-01，見 [plan 第一段待問 8](../../plan/m1-tick-core.md#待問)）**：~~不取鎖（不回 75、沒有 `AOS_TICK_LOCK_FD`）、~~（同日加回最簡互斥，見上段；仍不回 75、沒有 `AOS_TICK_LOCK_FD`）不驗表（不回 2、沒有 `config_invalid`）、不看 `user`（不回 125、沒有 `user_mismatch`）、不判上下層、不做 `--firstdo-fsync`、不處理紀錄讀不懂或寫不進。出事就讓 Python 自然丟錯（traceback、回 1）。~~整格只回 0／1；argv 用法錯回 2。~~（10-01 再改，見下段）

**結束碼照 aos 體系慣例（使用者 2026-10-01，同日改版，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)、[plan 待問 9、15](../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：0＝預料之中（含正常中斷）、非 0＝要額外處理、1＝通用錯誤（~~0 正常結束、1 錯誤結束、2 正常中斷~~）。`aos-tick` 的碼只講 tick 自己，現在只回 0／1：

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
6. `tests/test_tick.py`：`Step1Target`、`Step1Lock`…`Step4Defaults`（頂層預設）…`Step9Whole`、`DirName`、`EmptyDirName`，對著 plan 各步的驗收讀。

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
- 任務表極簡檢查（使用者 2026-10-01，[verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick-讀任務表的極簡檢查待統一更新-spec)）：合法 JSON、頂層物件有 `tasks` 陣列、每項（解一層後）是物件、合併頂層預設後有 `argv`（讀表那層解不開也算）；不過 stderr 一行 `bad_table:`、回 1。~~檢查在換紀錄之後，表壞仍佔 `seq`、紀錄停在 `ended:false`。~~（使用者 2026-10-01 改：在換紀錄之前，表壞不換紀錄、不加 `seq`）每項沒寫 `_metainfo` 照跑（`aos_inst` 當 posix 第 1 版）；寫錯了跑到那項時 `aos_inst` 自然丟錯回 1。
- 沒 `id` 的項（使用者 2026-10-01）：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串，紀錄、`AOS_TASK_ID`、`blocked_before` 都用它；跟別項撞了不管。`id` 不是字串時 `AOS_TASK_ID` 用 `str()`（我自己定的）。
- ~~目標給的檔在 `.aos/` 裡時工作資料夾取 `.aos` 的上一層；目標給檔時，項目裡的相對檔名以工作資料夾為中心。~~（使用者 2026-10-01 撤回「目標給檔就當任務表」，兩條跟著作廢；給檔現在是用法錯）

## hooks：外掛掛點（m1h）

照 [plan m1h](../../plan/m1h-hooks-module.md) 寫的，spec 正本 [B-635](../../spec/settled/tick/hooks.md)。在任務表頂層寫 `hooks`（跟 `tasks` 同層；不當模組）。2026-10-01 第十七批起四個掛點：

```json
{
  "tasks": [{"id": "build", "argv": ["make"]}, {"argv": ["./report.sh"]}],
  "hooks": {
    "before_all": [{"id": "recover", "argv": ["./recover.sh"]}],
    "after_task": {"build": [{"id": "notify", "argv": ["./notify.sh"]}], "1": [{"argv": ["./after-report.sh"]}]},
    "after_every_task": [{"id": "log", "argv": ["sh", "-c", "echo \"$AOS_TASK_ID $AOS_TASK_EXIT\" >> tasks.log"]}],
    "after_all": [{"argv": ["sh", "-c", "date >> ticks.log"]}]
  }
}
```

| 掛點 | 什麼時候 | 另給的環境變數 |
|---|---|---|
| `before_all` | 開格後、第一項（含 tasks-blocked 的檢查）之前 | `AOS_HOOK_*` |
| `after_task.<任務 id>` | 那一項跑完（沒寫 id 的任務用位置字串當鍵；不存在的 id 不跑、不報錯） | `AOS_HOOK_*`＋剛跑完那一項的 `AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`（被訊號 N 殺＝128+N） |
| `after_every_task` | 每一項跑完；同一項也有 `after_task` 時排在它後面 | 同上 |
| `after_all` | 照表跑完或被 tasks-blocked 擋下之後 | `AOS_HOOK_*` |

- 寫法與指示詞展開都比照 `tasks`（開格整份展開，第二十批）：每項一個 inst 物件，`id` 可省（沒寫＝在自己那個陣列的位置字串）、吃頂層預設、跑法跟任務一樣。`AOS_HOOK_INDEX` 是在自己那個陣列的位置（`after_task` 每個任務 id 各自從 0 數）。
- 跑每一項前，`AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`、`AOS_HOOK_*` 一律先從繼承的環境拿掉（`aos_tick_run.RUN_VARS`），所以 `AOS_TASK_EXIT` 只有那兩個掛點有。`aos_tick_hooks.run_point()`、`run_after_task()` 組變數。
- 不看 tasks-blocked；被它擋下沒跑的任務不觸發 `after_task`、`after_every_task`。每項的碼照實記、接著跑下一項；不影響 tick 的結束碼（照舊 0）。擋板、busy、表壞時一個都不跑。
- 格式錯（`hooks` 不是物件、陣列的掛點不是陣列、`after_task` 不是物件或某個值不是陣列、某項不是物件、合併後沒 `argv`）＝`bad_table:`、回 1，開格前就擋。`hooks` 裡其他鍵照收不理。寫在 `modules.hooks` 底下的不會跑。
- 紀錄：任務表寫了哪幾個掛點，**開格**時就把 `hook-exits.json`（各掛點 `[]`）寫好、`record.json` 帶 `hooks` 的 `$ref`；每跑完一個**結束碼不是 0** 的 hook 加一筆，格式同 `tasks`（`id`、`index`、`exit` 或 `signal`），`after_task`、`after_every_task` 另帶 `task_index`；0 的不記，hooks 不記 `ran`；下一格跟著進 `last/`。
- 某個 hook 沒跑成時 stderr 是 `exec_failed: <掛點>/<id>: …`（`after_task` 是 `after_task/<任務 id>/<id>`）。
- 用 hooks 加普通 git 指令取代 `aos-git`（第十七批暫緩）的寫法見 [B-635 範例](../../spec/settled/tick/hooks.md#範例用-hook-加普通-git-指令管版本)。

## tick 模組 `modules["tasks-blocked"]`（B-636）

使用者 2026-10-01 第十六批，spec [B-636](../../spec/settled/tick/tasks-blocked.md)、格式 P-214。任務表 `modules` 底下寫：

```json
"modules": {"tasks-blocked": {"insts": [{"id": "notify", "argv": ["sh", "-c", "echo $AOS_TASK_ID >> blocked.log"]}]}}
```

- 某一項之前發現 `<狀態資料夾>/tick/tasks-blocked`：先依序跑 `insts`（全部跑完、不看彼此的碼），再看一次——檔被刪了就放行這一項與後面的，還在就照預設擋下（`blocked_before`）。同一項之前只跑一次；放行後又被擋，那一項之前再跑。
- 碼不記進紀錄、非 0 沒影響。環境照任務：`AOS_TASK_ID`／`AOS_TASK_INDEX`＝被擋下的那一項、`AOS_TICK_CWD`；沒有 `AOS_HOOK_*`。
- 寫法與展開比照 `tasks`（開格整份展開；〔第二十批〕模組鍵由 `tasks_blocked` 改名 `tasks-blocked`，跟檔名一樣）。開不起來印 `exec_failed: tasks-blocked/<id>`。
- 沒掛＝看到就擋下。整格最後照樣刪 tasks-blocked。

測試 `tests/test_tick.py` 的 `TasksBlockedModule`（7 條）。

## aos-daemon（第三段最核心 daemon）

照 [plan 第三段 m3](../../plan/m3-daemon-core.md) 寫的，新寫。就是「一個叫 `aos-exec` 的 cron」：讀設定檔裡的 inst 清單，每項照自己的週期叫一次同一個 `bin/` 裡的 `aos-exec <inst 字面值>`，等它結束、stdout 印一行。沒有 socket、登記、收屍；daemon 不認得 node（node 就是一份 `argv` 寫 `aos-tick` 的 inst）。核心也沒有「id」這個概念（使用者 2026-10-01）：一項就是它的 `inst` 字面值，印出來也是 `inst=…`。

```sh
proto6/src/py/bin/aos-daemon --config daemon.json     # Ctrl-C／SIGTERM 直接退出、回 0，不殺正在跑的子程序
```

設定檔：

```json
{
  "cwd": "/home/u/nodes",
  "interval_ms": 60000,
  "stop_on_nonzero": false,
  "exec_out_path": "<inst>/out.log",
  "exec_err_path": "<inst>/err.log",
  "insts": {
    "a": {},
    "jobs/report.json": {"interval_ms": 5000, "stop_on_nonzero": true}
  }
}
```

| 鍵 | 意思 |
|---|---|
| `insts` | 物件（使用者 2026-10-01 改；陣列寫法撤掉、不相容）。**鍵＝inst 字面值**，**原樣**當 aos-exec 的參數（資料夾或檔都行），印出來也照字面；**值＝該項設定**（`interval_ms`、`stop_on_nonzero` 蓋過頂層；`{}`＝全用頂層預設）。第幾項照鍵的順序（JSON 讀入保序）從 0 數；同一個鍵寫兩次時 JSON 讀入只留後面那個 |
| `cwd`（頂層） | 起點：aos-exec 子程序的工作目錄、相對路徑的基準。沒寫＝daemon 啟動時的工作目錄；相對的也以它為準 |
| `interval_ms` | 上一次結束後隔多久再叫（剛開時每項先立刻跑一次）。頂層是預設、每項可蓋過；兩邊都沒有＝設定錯、回 1 |
| `stop_on_nonzero` | 碼不是 0 時這一項就不再叫、多印一行 `stopped`。頂層是預設、每項可蓋過；都沒有＝`false`。所有項都停了 daemon 照樣開著 |
| `exec_out_path`（頂層） | aos-exec 的 stdout 接到哪個檔（接在檔尾、父資料夾不在就建）。相對以起點為準；`<inst>` 換成 inst 字面值，inst 是檔時換成它字面上的 dirname（空的用 `.`）。~~沒寫＝daemon 自己的 stdout~~ 沒寫＝丟掉（`/dev/null`，使用者 2026-10-01）；寫 `/dev/stdout` 接回 daemon 的 stdout |
| `exec_err_path`（頂層） | aos-exec 的 stderr 接到哪個檔，規則同 `exec_out_path`。~~沒寫＝daemon 自己的 stderr~~ 沒寫＝丟掉（`/dev/null`，使用者 2026-10-01）；寫 `/dev/stderr` 接回 daemon 的 stderr |
| `modules`（頂層） | 可選，要是物件（不是＝設定錯、回 1）。一個模組一個鍵；目前只有 `control`（[控制模組](#控制模組與-aos-ctlm3n)，有寫就開），其他鍵照收、不看 |

**整份設定檔先經 aos 指示詞展開再讀**（使用者 2026-10-01；跟 inst 同一套 `lib/aos_directives.py`，`$ref`／`$fmt`／`$env`）。順序與兩種起點：

1. **先展開**：整份從根一路走進物件與陣列，每一格解到底。`$ref` 的相對檔名**一律以設定檔所在的資料夾**為準（`os.path.abspath`，不解符號連結；被引進來的檔裡再 `$ref` 也照這個資料夾，中心路徑不換）。`$opt` 物件原樣留著、不走進去（核心沒有吃選項的位置，留給模組）。引到自己的祖先＝`ReferenceCycle`。
2. **展開完才讀鍵**：頂層 `cwd`（可以是 `$ref` 引進來的值）照上表的規則算起點——**相對的 `cwd` 以 daemon 啟動時的工作目錄為準，不是設定檔的資料夾**；`inst` 值、`exec_out_path`、`exec_err_path` 再以起點為準。

所以同一份設定檔裡，`$ref` 的檔名跟 `inst`／`cwd` 的值起點不同：前者看設定檔放哪，後者看 daemon 從哪開（或 `cwd`）。例：設定檔在 `conf/daemon.json`、daemon 從 `/w` 開：

```json
{"interval_ms": {"$ref": "defaults.json#/interval_ms"}, "insts": {"$ref": "list.json"}}
```

讀的是 `conf/defaults.json`、`conf/list.json`；`list.json` 裡寫 `{"x.json": {}}` 跑的是 `/w/x.json`。指示詞錯（讀不到、循環、位置找不到…）stderr 一行 `aos-daemon: config: <代號>: …`、回 1。

stdout 每次一行（時間是印出那刻的本地時間，ISO 8601 帶時區）：

```text
2026-10-01T15:04:05+08:00 inst=a exit=0 ms=812
2026-10-01T15:04:05+08:00 inst=jobs/report.json exit=3 ms=23
2026-10-01T15:04:05+08:00 inst=jobs/report.json stopped
```

aos-exec 的 stdout、stderr（使用者 2026-10-01：兩條都由頂層鍵決定、沒寫就丟到 `/dev/null`，不再接到 daemon 自己的 stdout／stderr；沒寫的那條直接開成 `DEVNULL`、不經 pipe）：有寫路徑的那條每次收齊（`communicate()`，讀到 pipe 底）再一次寫出，有內容才寫，前面一律加一行標頭（時間、`stdout`／`stderr`、第幾項＝`insts` 鍵的順序從 0 起、inst 字面值；寫到 `<inst>` 個別檔也加，使用者 2026-10-01 同意）；同一次兩條都有就先 stdout 段再 stderr 段，跟 daemon 自己那一行共用一把鎖，多項同時結束也不交錯：

```text
== 2026-10-01T15:04:05+08:00 stdout index=1 inst=jobs/report.json ==
done 3 rows
== 2026-10-01T15:04:05+08:00 stderr index=1 inst=jobs/report.json ==
boom
```

inst 裡任務自己的 stdout／stderr 照 inst 規則（預設 `/dev/null`，寫 `{"$opt": "inherit"}` 才會跟著 aos-exec 進來）。被訊號殺的碼印成 `128+N`。結束碼：用法錯（沒給 `--config`、多給參數）、設定錯、設定檔讀不到、指示詞錯都 1；SIGINT／SIGTERM 0。daemon 退出後還在跑的 aos-exec 再寫有設路徑的那條（pipe）會吃 SIGPIPE，照默認一切正常不處理（使用者 2026-10-01 同意）；沒設的那條是 `/dev/null`，不會。

| 函式（`lib/aos_daemon.py`） | plan 步驟 |
|---|---|
| `main()`、`_Parser`、`read_config()`、`expand()`、`load_config()`、`err_path_for()` | 1 讀設定檔（先展開指示詞） |
| `run_once()`、`write_outputs()`、`_block()`、`say()`、`now()` | 2 叫一次、印一行 |
| `loop()` | 3 週期、4 非 0 停不停 |
| `_quit()` | 5 Ctrl-C 與 SIGTERM |

測試 `tests/test_daemon.py`：`Step1Config`～`Step6Tick`，一個類別一步（步驟 1 另有 `Step1Directives`：指示詞與 `modules`），整檔約 6 秒。

## 控制模組與 aos-ctl（m3n）

照 [plan m3n](../../plan/m3n-control-module.md) 寫的，新寫。設定檔多寫一段就掛上；沒寫時 daemon 跟上面一模一樣（不建 socket、不傳環境變數）：

```json
{"interval_ms": 60000, "modules": {"control": {"socket": "./aos.sock"}}, "insts": {"a": {}, "jobs/report.json": {}}}
```

- `socket` 必填（沒寫＝設定錯、回 1），相對以起點（`cwd`）為準，算成絕對路徑。開的時候路徑上有舊檔先刪；SIGINT／SIGTERM 退出前刪掉。
- daemon 開每一次 aos-exec 都在環境加 `AOS_DAEMON_SOCKET=<socket 絕對路徑>`、`AOS_DAEMON_INST=<這一項的 inst 字面值>`。inst 的任務、`aos-tick` 的任務、下層 `aos-tick <下層>` 的任務都繼承得到，所以**任何一層跑 `aos-ctl wake` 叫醒的都是頂層那一項**。
- 協議：一連線一請求，一行 JSON 進、一行 JSON 出。指令名當鍵、inst 字面值當值：`{"wake":"a"}`、`{"wake":"a","skip_while_running":true,"keep_schedule":true}`、`{"pause":"a"}`、`{"resume":"a"}`、`{"status":"a"}`。回 `{"ok":true}`（status 多帶狀態）或 `{"ok":false,"error":"unknown_inst|stopped|bad_request","detail":…}`。收到就回，不等那一項跑完。每條連線 1 秒逾時；壞請求只影響那一條。

| 指令 | 做什麼 |
|---|---|
| `wake` | 現在跑一次。正在跑：跑完補一次（叫幾次都只補一次）；帶 `skip_while_running` 就作廢。跑完後週期從這次結束重算；帶 `keep_schedule` 就不動原本排程（原本那次已被蓋過去才從這次結束重算）。暫停中：跑一次、跑完照樣暫停。被 `stop_on_nonzero` 停掉：回 `stopped`、不跑 |
| `pause` | 不再照週期跑；正在跑的不殺，待補的取消。stdout 印 `inst=<inst> paused` |
| `resume` | 清掉暫停與已停，馬上跑一次。stdout 印 `inst=<inst> resumed` |
| `status` | `{"ok":true,"inst":…,"running":…,"pending":…,"paused":…,"stopped":…,"last_exit":…,"last_end":…,"next":…}`；還沒跑完過時 `last_exit`／`last_end` 是 `null`，正在跑、暫停、已停時 `next` 是 `null` |

「暫停中 wake 跑一次」「停掉的 wake 回 `stopped`」「resume 一律跑一次」三條是 m3n 待問 1 照建議先做的，使用者可改。暫停只在記憶體，重開 daemon 就沒了（掛了[記住狀態](#重讀設定與記住狀態m3m)時例外）。

`aos-ctl`（socket 從 `AOS_DAEMON_SOCKET` 拿，`--socket <路徑>` 改連別的 daemon〔第二十一批，這時要明寫 `<inst>`〕；沒給 `<inst>` 用 `AOS_DAEMON_INST`）：

```sh
aos-ctl wake [--skip-while-running] [--keep-schedule] [<inst>]
aos-ctl pause|resume|status [<inst>]
AOS_DAEMON_SOCKET=./aos.sock aos-ctl status jobs/report.json    # 人在 shell 手打
```

成功回 0（status 把回應那一行原樣印到 stdout，其他不印）；其餘回 1、stderr 一行 `代碼: 說明`：`usage`（指令名錯、多給參數、旗標給錯指令）、`no_daemon`（沒 `AOS_DAEMON_SOCKET`）、`no_inst`、`connect`（連不上），或照 daemon 回的 `unknown_inst`／`stopped`／`bad_request`。

| 函式 | plan 步驟 |
|---|---|
| `aos_daemon.load_setup()`（`load_config()` 照舊回兩個值） | 1 設定檔 |
| `aos_daemon.loop()`、`_next_run()`、`Item` 的狀態與 `cond` | 2 叫得醒、停得住的迴圈 |
| `aos_daemon_ctl.serve()`、`_accept_loop()`、`_one()`、`parse()`、`handle()`、`status()` | 3 socket 與協議（4 指令都在 `handle()`） |
| `aos_daemon.main()` 設 `item.env`、`run_once()` 帶 `env=` | 4 往下傳環境變數 |
| `aos_ctl.main()`、`bin/aos-ctl` | 5 aos-ctl |
| `aos_daemon_ctl.serve()` 先刪舊檔、`aos_daemon._quit()` 刪 socket | 6 socket 檔的開與收 |

測試 `tests/test_ctl.py`：`Step1Config`～`Step6SocketFile`，一個類別一步，整檔約 18 秒。任務量週期用 `/proc/uptime` 寫時間、不用 `date`：WSL 的牆上時鐘偶爾被校時往前跳好幾秒，`test_keep_schedule` 約十次錯一次就是這個（2026-10-01 改）。

## 重讀設定與記住狀態（m3m）

照 [plan m3m](../../plan/m3m-daemon-modules.md) 模組一、三寫的（2026-10-01 第十一批）。各自有寫才掛，沒寫時 daemon 跟上面一模一樣。

```json
{"interval_ms": 60000,
 "modules": {"control": {"socket": "./aos.sock"}, "reload": {}, "state": {"$ref": "aos-state.json"}},
 "insts": {"a": {}, "jobs/report.json": {}}}
```

**重讀設定**（`modules.reload`，`lib/aos_daemon_reload.py`，spec [B-642](../../spec/settled/daemon/reload.md)）：改了設定檔就 `kill -HUP <pid>`，daemon 重讀同一份（照樣整份展開指示詞）：

- 新的鍵：立刻跑一次，stdout `inst=<inst> added`；不見的鍵：不再排，正在跑的那次跑完照樣印 `exit=`，之後控制指令回 `unknown_inst`，stdout `inst=<inst> removed`；還在的鍵：換新設定，暫停、已停、待補照留，`interval_ms` 改了下一次＝上次結束＋新週期（過了就立刻跑）。最後一行 `reloaded`。
- 頂層 `cwd`、`modules`、`exec_out_path`、`exec_err_path` 改了不套用，stdout `reload: need restart: <鍵名>`（後兩個 2026-10-01 第十二批從「照新的」改成警告；新加的項的輸出路徑也照開起來時的設定算）。
- 設定壞了：整份不套用、stderr `aos-daemon: reload: <說明>`、舊的照跑。
- 沒掛時 SIGHUP 照 Python 預設殺掉 daemon。掛了時用 `signal.set_wakeup_fd` 收（不會漏），主執行緒讀 pipe、重讀。

```text
2026-10-01T16:45:49+08:00 reload: need restart: cwd
2026-10-01T16:45:49+08:00 inst=c.json removed
2026-10-01T16:45:49+08:00 inst=b.json added
2026-10-01T16:45:49+08:00 reloaded
```

**記住狀態**（`modules.state`，`lib/aos_daemon_state.py`，spec [B-643](../../spec/settled/daemon/state.md)）：原始設定檔的 `modules.state` 必須寫成 `{"$ref": "<檔>"}`（以設定檔所在資料夾為準、不帶 `#`），那個檔就是狀態檔：`{"insts": {"a": {"paused": true}, "jobs/report.json": {"stopped": true}}}`，只列不正常的項。

- pause、resume、`stop_on_nonzero` 停掉、重讀拿掉項時當場寫整份（暫檔 → rename），內容沒變不寫；檔不在＝全部正常，沒異常就不建。
- 開起來時照檔恢復：暫停、已停的項不先跑那一次，stdout 先印 `inst=<inst> paused`／`stopped`；檔裡有、設定沒有的鍵丟掉。
- 跟重讀設定一起掛時，重讀以記憶體為準，不重讀狀態檔。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon.load_full()`、`Setup`、`_state_ref()` | 讀設定；先把 `modules.state` 的 `$ref` 拿出來（檔不在不算錯），其餘照整份展開 |
| `aos_daemon._items`、`_items_lock`、`snapshot()`、`give_env()`、`start_item()` | 共用的清單（控制模組查的也是它），重讀時原地改 |
| `aos_daemon._catch_hup()`、`main()` 的主迴圈 | 收 SIGHUP |
| `aos_daemon_reload.reload()`、`_update()` | 比對清單、套用 |
| `aos_daemon.state_changed()`、`aos_daemon_state.StateFile.save()`、`restore()`、`dump()` | 寫檔、讀回 |

測試 `tests/test_daemon_reload.py`（15 條，約 11 秒）、`tests/test_daemon_state.py`（11 條，約 4 秒）。

## 收屍／cgroup（m3m 模組二）

照 [plan m3m](../../plan/m3m-daemon-modules.md) 模組二寫的（2026-10-01 第十二批，C1～C4 照建議），`lib/aos_daemon_cgroup.py`，spec [B-644](../../spec/settled/daemon/cgroup.md)、格式 [P-124](../../spec/settled/protocol/daemon/cgroup.md)。設定檔寫 `modules.cgroup` 才掛，沒寫時 daemon 跟上面一模一樣。

```json
{"interval_ms": 60000,
 "modules": {"cgroup": {}},
 "insts": {"a": {"cgroup": {"memory.max": "512M", "pids.max": "200"}}, "b": {}}}
```

要在委派好的 cgroup v2 子樹裡開，例如 `systemd-run --user --scope -p Delegate=yes bin/aos-daemon --config F`；沒有就照 Python 預設丟 traceback、回 1，不退回別的做法。

- 子樹根＝daemon 自己所在的 cgroup（自己已經在 `.../daemon` 裡就取上一層）。開起來先建 `<根>/daemon`、把根上所有程序搬進去，再開 `cpu`、`memory`、`pids` 裡根上有的。
- 每項一個葉框 `i-<inst 字面值 sha256 前 16 hex>`，開框時 stdout 印 `inst=<inst> cgroup=i-<h>`；框已經在（上次留下的）就先清空。那一項的 `cgroup` 物件原樣寫進框裡，不翻譯、不檢查。
- 每次跑：`sh -c 'echo $$ > 框/cgroup.procs && exec aos-exec …'` 先進框再變成 `aos-exec`（daemon 有很多執行緒，不用 `preexec_fn`）。`aos-exec` 結束時 `ms=` 停錶；框裡還有程序就寫 `cgroup.kill`（直接 SIGKILL）、等 `cgroup.events` 的 `populated 0`，才印 `exit=`、排下一次。有清到東西時接著印 `inst=<inst> reaped`。
- 殘留程序可能還拿著輸出的 pipe：掛了模組時 pipe 另開執行緒讀，清完框才讀得到結尾，輸出照樣收齊。
- 跟重讀設定一起掛：新加的項建框、寫上限，`added` 之後印對照；還在的項上限改了就重寫新設定寫的檔（拿掉的鍵不還原）；拿掉的項由自己的執行緒在最後一次跑完、清完後刪框（又被加回來就不刪）。建框、寫上限出錯算重讀出錯，但出錯前已經寫進去的不還原。

```text
2026-10-01T17:07:03+08:00 inst=a.json cgroup=i-6025a12236ee54ba
2026-10-01T17:07:06+08:00 inst=a.json exit=0 ms=2032
2026-10-01T17:07:06+08:00 inst=a.json reaped
```

| 函式 | 做什麼 |
|---|---|
| `aos_daemon_cgroup.Tree()` | 找根、建 `daemon` 子框、搬程序、開 controller |
| `Tree.make()`、`limits()`、`announce()` | 建（或接手）一項的框、寫上限、印對照 |
| `Tree.argv()`、`aos_daemon.run_once()` | 子程序先進框再 exec；結束後 `clear()`、回 `(碼, 毫秒, 有沒有收屍)` |
| `aos_daemon_cgroup.clear()`、`populated()` | `cgroup.kill`、等清空 |
| `aos_daemon._gone()`、`Tree.remove()` | 重讀拿掉的項跑完後刪框 |
| `aos_daemon_reload._apply()` | 重讀時先建框、寫上限，出錯就整份不套用 |

測試 `tests/test_daemon_cgroup.py`（15 條，約 9 秒）：每條用 `systemd-run --user --scope -p Delegate=yes` 包 daemon，拿不到委派的 scope 時整組跳過；`NotDelegated` 一條在測試自己所在的 cgroup 寫得進去時跳過（模擬不了沒委派）。2026-10-01 晚在家裡 Manjaro 實跑 14 過、1 跳過。

## 訊息與 aos-mq（m3m 模組四）

照 [plan m3m](../../plan/m3m-daemon-modules.md) 模組四寫的（2026-10-01 第十二批，M1～M4 照建議），`lib/aos_daemon_mq.py`、`lib/aos_mq.py`、`bin/aos-mq`。設定檔寫 `modules.mq` 才掛，沒寫時 daemon 跟上面一模一樣。

```json
{"interval_ms": 60000, "modules": {"mq": {"socket": "./aos-mq.sock"}}, "insts": {"a": {}, "b": {}}}
```

- 另開一個 unix socket（`socket` 相對以起點為準；不走控制 socket），一連線一請求、一行 JSON 來回，伺服器那套跟控制模組共用（`aos_daemon_ctl.serve()` 多收一個 `answer`）。
- **每項一個信箱**（`Item.mailbox`），記憶體裡、先進先出，daemon 重開就丟。重讀設定時還在的項信箱照留，拿掉的項連信箱一起丟，加回來從空的開始。
- 掛了之後每次開 `aos-exec` 多放 `AOS_DAEMON_MQ_SOCKET`；`AOS_DAEMON_INST` 掛了控制或訊息任一個就放（M2）。
- **急件**（`--urgent`）：信放進信箱後照控制模組 `wake`（不帶選項）叫醒收件那一項：正在跑就補一次、暫停中跑一次、已停不跑（信照收）。不用掛控制模組。

```text
aos-mq send [--urgent] [--socket <對方訊息 socket>] <收件 inst> <JSON|->
                                                # from 自動填 AOS_DAEMON_INST、from_socket 自動填自己的 socket（沒有＝null）
aos-mq take [--from [<寄件 inst>…]]…            # 只取自己（AOS_DAEMON_INST）的信箱；每封一行 {"from":…,"from_socket":…,"msg":…}
aos-mq peek [--from [<寄件 inst>…]]…            # 同上，但不取走
```

結束碼照 `aos-ctl`：成功 0；`usage:`（含 `<JSON>` 不是 JSON）、`no_inst:`、`no_daemon:`、`connect:`、`unknown_inst:`、`bad_request:` 一律 1，stderr 一行。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon_mq.serve()`、`parse()`、`handle()` | 收 send／take／peek、放信取信看信、急件叫醒 |
| `aos_daemon.give_env()` | 放 `AOS_DAEMON_SOCKET`／`AOS_DAEMON_MQ_SOCKET`／`AOS_DAEMON_INST` |
| `aos_daemon._quit()` | 退出前刪兩個 socket 檔 |
| `aos_mq.main()`、`bin/aos-mq` | 小工具 |

- **取信只能取自己的信箱**（2026-10-01 第十四批）：`take` 不收 `<inst>`、只用 `AOS_DAEMON_INST`；`--from` 只取那個寄件人的、其他照順序留著。socket 不驗身分，這是 `aos-mq` 那一側擋的（第十五批：照「能連就能做」，daemon 不核對）。
- **`peek` 與多個寄件人**（2026-10-01 第十五批）：`peek` 跟 `take` 一樣但不取走。`--from a c d` 收到下一個 `--` 開頭的參數為止；`--from` 不接＝寄件人是 null 的信；可以重複寫、疊加。socket 上 `from` 是非空陣列（元素字串或 null）。

- **跨 daemon**（2026-10-01 第二十一批）：收件地址的前綴是對方 daemon 的訊息 socket 路徑。`send --socket <路徑>` 直接連對方寄（相對路徑以呼叫者 cwd 為準，有 `--socket` 就不需要 `AOS_DAEMON_MQ_SOCKET`）；信裡自動帶 `from_socket`（自己的 `AOS_DAEMON_MQ_SOCKET` 的絕對路徑），收件方回信 `send --socket <from_socket> <from>`。daemon 不轉送、只是多存一欄。`take`／`peek` 不收 `--socket`；`--from` 只比 `from`。`aos-ctl --socket <控制 socket>` 同理，但要明寫 `<inst>`。peers（暱稱→socket 路徑）先不做。

測試 `tests/test_mq.py`（23 條，約 6 秒；`CrossDaemon` 三條開兩個 daemon）。

## 帳號（m3m 模組五）

照 [plan m3m](../../plan/m3m-daemon-modules.md) 模組五寫的（2026-10-01 第十二、十三批），`lib/aos_daemon_account.py`（主程式那側）、`lib/aos_daemon_root.py`＋`bin/aos-daemon-root`（root 端），spec [B-646](../../spec/settled/daemon/account.md)、格式 [P-126](../../spec/settled/protocol/daemon/account.md)。設定檔寫 `modules.account` 才掛，沒寫時 daemon 跟上面一模一樣（每項的 `account` 照不認得的鍵忽略）。

```json
{"interval_ms": 60000,
 "modules": {"account": {"user": "lorkhan", "allow": ["agent-*", "bob"], "deny": ["agent-admin"]}},
 "insts": {"a.json": {}, "jobs/bob.json": {"account": {"user": "bob"}}}}
```

要用 root 開：`sudo bin/aos-daemon --config F`。開起來的順序：

1. 讀設定（root）→ `Policy` 核預設帳號（`user`，沒寫用 `SUDO_USER`；不准是 root、要查得到）、名單（`*` 只能在結尾、`deny` 比得到預設帳號＝錯）、每一項的帳號（名單准、`getpwnam` 查得到）。不合 stderr `aos-daemon: account: <說明>`、回 1；沒用 root 開也是。
2. 掛了 cgroup 模組：照常建子樹、建框，然後 `chown_tree()` 整棵交給預設帳號。
3. `Account()`：開一條 `SOCK_SEQPACKET` socketpair，fork＋exec `aos-daemon-root <fd>`（另一個 session），第一個封包送名單。
4. `Account.drop()`：`initgroups`／`setgid`／`setuid` 永久降成預設帳號，`HOME`／`USER`／`LOGNAME` 換掉，起收回應的執行緒。
5. 之後才 `give_env()`、開控制／訊息 socket（掛了帳號模組時 chmod 666）、起各項。

跑一項：帳號是預設帳號（或沒寫）的，照舊自己開；別的帳號的走 `run_via_root()`——主程式開好 stdout／stderr 的 pipe（沒設路徑就交 `/dev/null`），連同請求 `{"id","user","argv","cwd","env","frame"}` 交給 root 端；root 端再核一次名單與 `getpwnam`，fork：`setsid`、有框先寫 `cgroup.procs`、切帳號、chdir、exec `aos-exec`，結束回 `{"id","exit"}`。查不到帳號回 `{"id","error"}`，主程式 stderr `aos-daemon: account: no such user <名字>`、那一次 `exit=1`。root 端不見了（EOF）：stderr 一行、刪 socket 檔、回 1。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon_account.Policy`、`match()`、`lookup()`、`item_user()` | 預設帳號、名單比對、每項的帳號 |
| `Policy.check_items()` | 開起來與重讀時核每一項（重讀照開起來時的名單） |
| `chown_tree()` | cgroup 子樹交給預設帳號 |
| `Account`、`Account.drop()`、`Account.run()`、`_replies()` | 開 root 端、降權、送請求、照 id 收回應 |
| `run_via_root()`、`aos_daemon.run_once()` | 別的帳號的那一項：pipe、等碼、清框、收齊輸出 |
| `aos_daemon._die()` | 刪 socket 檔、直接退出（SIGINT／SIGTERM 回 0，root 端不見了回 1） |
| `aos_daemon_root.main()`、`check()`、`child()` | root 端：單執行緒 select＋SIGCHLD、核帳號、fork 切帳號 exec |

測試 `tests/test_account.py`（21 條，約 2 秒）：名單比對、設定錯、沒 root 回 1 用一般帳號跑；其餘用 `unshare --user --map-root-user --map-auto` 當假 root（namespace 裡 UID 1～65536 對到 /etc/subuid，系統帳號 http、daemon、nobody 切得過去），把 src/py 複製到 /tmp 底下跑（別的 UID 進不了 /home/lorkhan）；拿不到就跳過。跟 cgroup 模組一起的一條用 `systemd-run --user --scope -p Delegate=yes` 再包 unshare。真 root、真帳號的整套要手動驗（plan m3m 模組五驗收草稿）。

## daemon 跑 daemon：輸出上限、鎖檔、kill／restart（第十九批）

〔使用者 2026-10-01 第十九批〕上層 daemon 把下層 daemon 當一項跑（inst 的 argv 是 `aos-daemon --config …`）時要的三件事。spec：[B-640](../../spec/settled/daemon/core.md)「輸出」「鎖檔」、[B-641](../../spec/settled/daemon/control.md)「kill 與 restart」，格式 [P-120](../../spec/settled/protocol/daemon/core.md)、[P-121](../../spec/settled/protocol/daemon/control.md)、[P-126](../../spec/settled/protocol/daemon/account.md)（root 端送訊號）。

```json
{"interval_ms": 5000, "exec_out_path": "<inst>/daemon.log", "exec_output_max_bytes": 65536,
 "modules": {"control": {"socket": "./aos.sock", "kill_grace_ms": 3000}},
 "insts": {"daemons/lorkhan.json": {}}}
```

- **輸出上限**：頂層 `exec_output_max_bytes`（預設 1048576，各項共用、每項不能覆蓋）。`run_once()` 對 stdout／stderr 各開一條執行緒跑 `drain()`：讀一段就接上、超過上限就從前面丟，所以一直印的下層 daemon 記憶體也只到上限。寫出時標頭多 `dropped=<bytes>`（有丟才加）。帳號模組經 root 端的那條路（`run_via_root()`）也用 `drain()`。
- **鎖檔**：`main()` 讀完設定就對 `lock_path`（預設 `<設定檔>.lock`，相對以設定檔資料夾為準）取 `flock(LOCK_EX|LOCK_NB)`；拿不到 stderr `aos-daemon: lock: another aos-daemon holds <鎖檔>`、回 1——在開 socket、建 cgroup、開 root 端、降權之前，所以不會搶走第一個 daemon 的 socket。fd 握到程序結束（`os.open` 開的不可繼承）。重讀設定時鎖檔路徑變了只警告 `reload: need restart: lock_path`。
- **kill／restart**：`aos_daemon_ctl._kill()` 另開執行緒跑 `aos_daemon.kill_run()`：先 `signal_run(item, False)`（SIGTERM），等 `kill_grace_ms` 那一次（`Item.run_seq`）還沒結束就 `signal_run(item, True)`（SIGKILL），掛 cgroup 再寫那一項框的 `cgroup.kill`。對象由 `kill_targets()` 從 /proc 算：aos-exec 把任務開在另一個 session，所以 TERM 送給 aos-exec 底下所有後代的程序群組（不含 aos-exec，讓它照常回任務的碼；沒有後代才送它），KILL 再加上 aos-exec 自己。別的帳號的項（帳號模組）`signal_run()` 改請 root 端送（`Account.signal()` → `{"signal": id, "final": …}`，root 端 `targets()` 是同一套規則的另一份）。restart：先記一次待補（像 wake）、記下 `Item.restart_seq`，被殺的那次非 0 不算 `stop_on_nonzero`。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon.drain()`、`write_outputs()`、`_block()` | 邊讀邊丟、寫出加 `dropped=` |
| `aos_daemon.main()` 開頭 | 鎖檔 |
| `aos_daemon.kill_targets()`、`signal_run()`、`kill_run()` | 算要送的程序群組、送 TERM／KILL、寬限 |
| `aos_daemon_ctl._kill()`、`grace_of()`、`set_grace()` | kill／restart 指令、`kill_grace_ms` |
| `aos_daemon_account.Account.signal()`、`aos_daemon_root.targets()` | 別的帳號的項經 root 端送訊號 |

測試 `tests/test_daemon_kill.py`（20 條）：輸出上限（含一直印 20 MB）、鎖檔、kill／restart；掛 cgroup 的一條要委派的 scope、帳號模組的一條要 namespace 假 root，拿不到就跳過。

## 跑測試

```sh
cd proto6/src/py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests
```
