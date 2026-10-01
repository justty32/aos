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
| `lib/aos_tick.py` | argv、`AOS_DIRNAME` 檢查、認工作資料夾與任務表 `resolve_target()`、取鎖 `take_lock()`、擋板、停格檔、整格順序 `run_tick()` |
| `lib/aos_tick_record.py` | 結束碼紀錄資料夾 `tick/current/`／`last/`：開格換紀錄（整個資料夾 rename）、每項寫 `ran.json`、不是 0 才寫 `task-exits.json`／`hook-exits.json`、收尾寫 `record.json`（使用者 2026-10-01 第八、九批）；`read_record()` 讀展開 `$ref` 後的完整紀錄 |
| `lib/aos_tick_table.py` | 讀任務表（`.aos/tasks.json`）、只解到 `tasks` 這層、頂層預設、極簡檢查 `check_table()`、每項的 `id`、跑到時合併預設再展開成 inst `load_inst()` |
| `lib/aos_tick_run.py` | 跑一項：照 inst 開串流、這一項的 `AOS_*`（先拿掉繼承來的 `AOS_TASK_*`／`AOS_HOOK_*`）、分 exit／signal |
| `lib/aos_tick_hooks.py` | hooks（外掛掛點，m1h）：收尾後依序跑 `after_all` 的 `run_after_all()`（讀表與極簡檢查在 `aos_tick_table.check_table()`，結果是 `Table.after_all`） |
| `tests/test_tick.py` | plan 各步的驗收，一個類別一步；結束碼慣例另成 `ExitCodes` |
| `tests/test_tick_hooks.py` | hooks 的驗收（m1h） |

**任務表的頂層預設與展開時機（使用者 2026-10-01，待統一更新 spec）**：頂層可放 inst 的七個欄位 `argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit` 當每一項的預設；頂層 `_metainfo`（整份表的格式標記，可省）、`id`、`kind` 不是預設，其他鍵當陌生鍵忽略。頂層也可選 `modules`（比照 daemon 設定檔，放 tick 模組的設定；目前沒有模組，核心照收不理、不當預設）。頂層還可選 `hooks`（外掛掛點，不是模組，見下面「hooks」一節）。

〔使用者裁定 2026-10-01，[verdicts 11 第三批](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)〕頂層 `_metainfo` 可省；每項 `_metainfo` 照 inst 規則（沒寫＝posix 第 1 版，寫了跑到那一項才由 `aos_inst` 驗，驗不過自然丟錯回 1）。`modules` 讀表時整個展開（跟 daemon 設定檔的 `expand()` 同做法），展開失敗＝`bad_table:`、回 1。

淺層合併：項自己寫了某個鍵就整個蓋過頂層那個（`envs` 也整包換掉，不逐變數合併）。合併後要有 `argv`（項自己有或頂層有），不然 `bad_table:`、回 1。

頂層 `cwd` 不改 tick 自己的 cwd（tick 永遠在工作資料夾跑，鎖、紀錄都在工作資料夾的 `.aos/`），只是任務的預設 cwd，相對以工作資料夾為起點。

讀表時（開格）只解到 `tasks` 這層：整份是指示詞先解；`modules` 整個展開；`tasks` 與七個預設鍵的值各解一層（跟著 `$ref`／`$fmt`／`$env` 走到不是指示詞為止，`$opt` 選項物件原樣留）；`tasks` 每一元素解一層（整項 `$ref`）。這層的相對檔名以工作資料夾為中心，`$ref:""`／`#…` 指整份 tasks.json；解不開＝`bad_table:`。

值的內部（`envs` 裡的 `$env`、`argv` 元素的 `$fmt`、`cwd` 的 `$opt mkdir`…）讀表時不解（`modules` 例外，整個展開）。跑到某一項才合併（預設＋這一項），合併結果當一份獨立的記憶體 inst 照 inst 規則展開（`cwd` 先解、以工作資料夾為中心，其他欄位以解出的 cwd 為中心）；這時 `$ref:""`／`#…` 指合併後的這一項，不是整份 tasks.json，也不是預設原本來自的那個檔。沒跑到的項內部壞了不影響這一格；跑到時解不開就自然丟錯回 1。

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

**`AOS_DIRNAME`（使用者 2026-10-01，見上面改動 3、[plan 待問 13、15](../../plan/m1-tick-core.md#待問)）**：本節所有 `.aos` 都是這個名字；不合法 stderr `usage:`、回 1。設成空字串時 `tasks.json`、`tick.lock`、`tick-blocked`、`tick/stop`、`tick/current.json`／`last.json` 都直接在工作資料夾下（`take_lock()` 不建資料夾）。

**POC 默認一切正常（使用者 2026-10-01，見 [plan 第一段待問 8](../../plan/m1-tick-core.md#待問)）**：~~不取鎖（不回 75、沒有 `AOS_TICK_LOCK_FD`）、~~（同日加回最簡互斥，見上段；仍不回 75、沒有 `AOS_TICK_LOCK_FD`）不驗表（不回 2、沒有 `config_invalid`）、不看 `user`（不回 125、沒有 `user_mismatch`）、不判上下層、不做 `--firstdo-fsync`、不處理紀錄讀不懂或寫不進。出事就讓 Python 自然丟錯（traceback、回 1）。~~整格只回 0／1；argv 用法錯回 2。~~（10-01 再改，見下段）

**結束碼照 aos 體系慣例（使用者 2026-10-01，同日改版，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)、[plan 待問 9、15](../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：0＝預料之中（含正常中斷）、非 0＝要額外處理、1＝通用錯誤（~~0 正常結束、1 錯誤結束、2 正常中斷~~）。`aos-tick` 的碼只講 tick 自己，現在只回 0／1：

| 狀況 | 回 |
|---|---|
| 照表跑完（不管任務回幾、成敗） | 0 |
| 看到停格檔 `.aos/tick/stop`，剩下不跑（不算中斷，暫定） | 0 |
| 同資料夾上一格還沒跑完（拿不到 `.aos/tick.lock`，stderr `busy:`），不開格（不寫紀錄、不加 `seq`） | 0（原 2） |
| 有擋板檔 `.aos/tick-blocked`（stderr `blocked:`），不開格（不寫紀錄、不加 `seq`） | 0（原 2） |
| argv 用法錯、`AOS_DIRNAME` 不合法、目標給的是檔、目標指的東西不存在、目標資料夾底下沒有 `.aos/tasks.json`、任務表不合極簡檢查（stderr `usage:`／`no_target:`／`no_tasks:`／`bad_table:`；表壞不換紀錄、不加 `seq`） | 1 |
| tick 自用檔（`tick-blocked`、`stop`、`tick/current/`、`tick/last/` 裡的紀錄檔）讀不到／寫不進／格式壞 | 1（自然丟錯，traceback 進 stderr） |

任務回 0、1、2、125～127、被訊號殺都照實記進紀錄、照常跑下一項。紀錄收尾的 `exit` 因此只會是 0。

**結束碼紀錄（B-633、P-213；使用者 2026-10-01 第九批拆檔）**：「把容易被改動的弄成$ref指向其他檔案，不容易被改動的留在current.json」。一格是一個資料夾 `.aos/tick/current/`（上一格 `last/`，同結構），四個檔：

| 檔 | 內容 | 什麼時候寫 |
|---|---|---|
| `record.json` | `version`、`seq`、`started_at_ms`、`ended`、`exit`、`stopped_after`，加上 `"ran":{"$ref":"ran.json"}`、`"tasks":{"$ref":"task-exits.json"}`，有 hooks 時再加 `"hooks":{"$ref":"hook-exits.json"}` | 開格、收尾各一次 |
| `ran.json` | 一個數字：本格跑完幾項 | 開格 `0`，每跑完一項 |
| `task-exits.json` | 結束碼不是 0 的任務 `[{"id","index","exit"\|"signal"}…]` | 開格 `[]`，有失敗才重寫 |
| `hook-exits.json` | `{"after_all":[…]}`，結束碼不是 0 的 hook | 任務表有 `hooks.after_all` 時收尾先寫 `{"after_all":[]}`，有失敗才重寫 |

換紀錄＝刪 `last/`、`current/` 整個 rename 成 `last/`、暫存資料夾 `.current.tmp/` rename 成 `current/`；`$ref` 是相對路徑，改名後仍指得對。`seq` 從 `current/record.json`（沒有就 `last/record.json`）接著數。舊的 `current.json`／`last.json` 不再使用、不遷移。

### review 導讀

讀的順序：

0. `lib/aos_dirname.py`：`AOS_DIRNAME` 的名字與合法判斷（aos-exec 也用）。
1. `lib/aos_tick.py` 的 `run_tick()`／`_run_locked()`：整格照 B-620「一格怎麼走」一行一步，先看它知道全貌。
2. 同檔 `resolve_target()`、`take_lock()`、`state()`、`read_reason()`、`remove_stop_file()`、`run_one()`。
3. `lib/aos_tick_record.py`：`Record.open()`（換檔四步）→ `add_task()`／`finish()` → `_rewrite()`。
4. `lib/aos_tick_table.py`：`read_table()` → `check_table()`（回 `Table`：預設、各項、id）、`merge()`、`load_inst()`。
5. `lib/aos_tick_run.py`：`run_item()`。
6. `tests/test_tick.py`：`Step1Target`、`Step1Lock`…`Step4Defaults`（頂層預設）…`Step9Whole`、`DirName`、`EmptyDirName`，對著 plan 各步的驗收讀。

每個函式開頭一行註明對應的 spec 條號。

plan 步驟對到哪：

| 步驟 | 函式 |
|---|---|
| 1 找資料夾、取鎖 | `main()`、`resolve_target()`、`take_lock()` |
| 2 擋板檔、結束碼 | `run_tick()`、`read_reason()`、`say()` |
| 3 紀錄與格數 | `Record.open()`、`_read_seq()`、`_rewrite()` |
| 4 讀表 | `aos_tick_table.read_table()`、`check_table()` |
| 5 照表跑 | `run_tick()` 迴圈、`run_one()`、`aos_tick_run.run_item()` |
| 6 停格檔 | `remove_stop_file()`、`run_tick()` 迴圈裡的 `read_reason(STOP)` |
| 7、8 | 2026-10-01 取消（fsync、上下層） |

我自己做的判斷（spec 沒寫死、照「最小合理」做，都可以改）：

- ~~沒有 `.aos/`：整個交給 `aos_exec.run_target` 跑這個資料夾（不寫紀錄、退出碼照 aos-exec）；連 `inst.json` 也沒有時是 aos-exec 自己的用法錯 2。~~（2026-10-01 作廢：退路拿掉，沒有 `.aos/inst.json` 就 stderr `no_inst:`、回 1；只看在不在，不讀它的內容。）~~見 `aos_tick.run_tick` 開頭。~~（2026-10-01 再改：改看 `.aos/tasks.json`，見 `aos_tick.resolve_target`）
- 新增的 stderr 代碼：`usage`（argv 錯、`AOS_DIRNAME` 不合法、目標給的是檔）、`busy`（拿不到鎖）、~~`no_inst`（沒有 `.aos/inst.json`）~~、`no_tasks`（資料夾沒有 `.aos/tasks.json`）、`no_target`（目標指的東西不存在；原 `no_node`）、`bad_table`（任務表不合極簡檢查）、`exec_failed`（某項沒跑成：mkdir／cwd／重導向失敗、126／127）。
- 某項沒跑成（mkdir、cwd、重導向失敗）記 `exit:125`，跟 aos-exec 命令列一致（inst 的規定，不是帳號判定）。
- 項目（合併頂層預設後）是純記憶體文件（跟 `load_obj` 一樣），所以項目裡的 `$ref:""` 指合併後的這一項，不是整份 tasks.json（使用者 2026-10-01 頂層預設時確認）。
- 任務的 id 用開格讀表時拿到的；跑到時只展開 inst 部分。
- `envs` 清空時一個 `AOS_*` 都不放。
- 任務表極簡檢查（使用者 2026-10-01，[verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick-讀任務表的極簡檢查待統一更新-spec)）：合法 JSON、頂層物件有 `tasks` 陣列、每項（解一層後）是物件、合併頂層預設後有 `argv`（讀表那層解不開也算）；不過 stderr 一行 `bad_table:`、回 1。~~檢查在換紀錄之後，表壞仍佔 `seq`、紀錄停在 `ended:false`。~~（使用者 2026-10-01 改：在換紀錄之前，表壞不換紀錄、不加 `seq`）每項沒寫 `_metainfo` 照跑（`aos_inst` 當 posix 第 1 版）；寫錯了跑到那項時 `aos_inst` 自然丟錯回 1。
- 沒 `id` 的項（使用者 2026-10-01）：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串，紀錄、`AOS_TASK_ID`、`stopped_after` 都用它；跟別項撞了不管。`id` 不是字串時 `AOS_TASK_ID` 用 `str()`（我自己定的）。
- ~~目標給的檔在 `.aos/` 裡時工作資料夾取 `.aos` 的上一層；目標給檔時，項目裡的相對檔名以工作資料夾為中心。~~（使用者 2026-10-01 撤回「目標給檔就當任務表」，兩條跟著作廢；給檔現在是用法錯）

## hooks：外掛掛點（m1h）

照 [plan m1h](../../plan/m1h-hooks-module.md) 寫的，spec 正本 [B-635](../../spec/settled/tick/hooks.md)。在任務表頂層寫 `hooks`（跟 `tasks` 同層；使用者 2026-10-01 同日改：不當模組、直接當頂層鍵），裡面寫 `after_all`，`aos-tick` 照表跑完（含被停格檔停下）之後就依序跑那一串。

```json
{
  "envs": {"LANG": "C.UTF-8"},
  "tasks": [{"id": "build", "argv": ["make"]}],
  "hooks": {"after_all": [
    {"id": "notify", "argv": ["./notify.sh"]},
    {"argv": ["sh", "-c", "date >> ticks.log"]}
  ]}
}
```

- 寫法與指示詞展開時機都比照 `tasks`（`hooks`、`after_all`、每一元素讀表時各解一層，內部跑到時才展開）：每項一個 inst 物件，`id` 可省（沒寫＝在 `after_all` 的位置字串）、吃頂層預設、跑法跟任務一樣。
- 環境變數（使用者 2026-10-01 第十批）：`AOS_TICK_CWD` 跟任務一樣；另給 `AOS_HOOK_POINT`（掛點名，`after_all`）、`AOS_HOOK_INDEX`（在 `after_all` 的位置）、`AOS_HOOK_ID`（hook 的 id，沒寫＝位置字串），**不給** `AOS_TASK_ID`／`AOS_TASK_INDEX`（tick 繼承來的也拿掉）；任務也拿不到 `AOS_HOOK_*`。`aos_tick_hooks.hook_vars()` 組、`aos_tick.run_one()` 收 `run_vars`。
- 不看停格檔；每項的碼照實記、接著跑下一項；不影響 tick 的結束碼（照舊 0）。擋板、busy、表壞時不跑。
- 格式錯（`hooks` 不是物件、`after_all` 不是陣列、某項不是物件、合併後沒 `argv`）＝`bad_table:`、回 1，開格前就擋。只開 `after_all`，`hooks` 裡其他鍵照收不理。寫在 `modules.hooks` 底下的不會跑。
- 紀錄：收尾（`ended:true`）那次先寫 `hook-exits.json`（`{"after_all":[]}`）、`record.json` 加 `hooks` 的 `$ref`，每跑完一個**結束碼不是 0** 的 hook 在 `hook-exits.json` 加一筆，格式同 `tasks`（`id`、`index`、`exit` 或 `signal`）；0 的不記，hooks 不記 `ran`；下一格跟著進 `last/`。例（展開後；`build`、`notify` 都回 0 不記，第 2 個 hook 回 3）：

  ```json
  {"version":1,"seq":7,"started_at_ms":1790000000000,
   "ran":1,"tasks":[],"ended":true,"exit":0,
   "hooks":{"after_all":[{"id":"1","index":1,"exit":3}]}}
  ```

- 某個 hook 沒跑成時 stderr 是 `exec_failed: after_all/<id>: …`。

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

「暫停中 wake 跑一次」「停掉的 wake 回 `stopped`」「resume 一律跑一次」三條是 m3n 待問 1 照建議先做的，使用者可改。暫停只在記憶體，重開 daemon 就沒了。

`aos-ctl`（socket 只從 `AOS_DAEMON_SOCKET` 拿；沒給 `<inst>` 用 `AOS_DAEMON_INST`）：

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

## 跑測試

```sh
cd proto6/src/py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests
```
