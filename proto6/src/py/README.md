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

現在跟 proto5 不同的只剩改動 2（資料夾目標找 inst 的位置）、改動 3（那個位置的 `.aos` 照 `AOS_DIRNAME`）與改動 4（用法錯回 1）。

## ~~改動 1：認得頂層 `user`~~（2026-10-01 撤回）

使用者 2026-10-01（原話「aos-exec應該也不需要認得頂層user吧。」，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-exec-不認得頂層-user待統一更新-spec)）：`lib/aos_inst.py` 換回 proto5 原檔，`user` 當不認得的鍵照 inst 規則忽略、照目前身分跑；`UserNotGranted`／`UserInvalid`、`test_user.py`（7 條）一併拿掉。aos-tick 原本「交給 `load_obj` 前先拿掉 `user`」因此多餘，也拿掉了。

~~原本：`aos_inst._check_user()` 在解任何指示詞之前看原始頂層的 `user` 字面值；跟目前身分不同 `UserNotGranted`、型別錯等 `UserInvalid`，都是 125。~~

## 改動 2：資料夾目標怎麼找 inst

照 [inst.md「inst 目標」](../../spec/base/inst.md)：

- 目標是資料夾：先找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json`；兩個都有跑前者；都沒有＝用法錯（~~2~~ 1，見改動 4）。base 是 `xxx` 自己。
- 拿掉 proto5 的 `--dir-target` 旗標、`run_target`／`run_target_full`／`spawn_target` 的 `dir_target` 參數與 `DEFAULT_DIR_TARGET` 常數（改成 `DIR_TARGETS` 兩個位置）。給 `--dir-target` 現在是用法錯。
- 檔案目標照 proto5 不動。~~tick 那條「`.aos/inst.json`／`inst.json` 路徑正規化成資料夾」不在這裡做。~~（2026-10-01：tick 不再做這個正規化，`--node` 怎麼認見下面 aos-tick 一節）

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
proto6/src/py/bin/aos-tick --node /tmp/n; echo $?     # 0
cat /tmp/n/.aos/tick/current.json                     # {"version":1,"seq":1,...,"ended":true,"exit":0}
cd /tmp/n && proto6/src/py/bin/aos-tick               # 不給 --node 用目前目錄（相對路徑也行）
proto6/src/py/bin/aos-tick --node /tmp/m/t.json       # 給檔：拿它當任務表，/tmp/m 當 node（紀錄在 /tmp/m/.aos/tick/）
```

**`--node` 怎麼認（使用者 2026-10-01，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick---node-怎麼認待統一更新-spec)、[plan 待問 10](../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：省略用 `./`，相對路徑轉成絕對。是資料夾：要有 `.aos/tasks.json`（不看 `.aos/inst.json`），沒有回 1、stderr `no_tasks:`。是檔：拿這個檔當這一格的任務表（跟資料夾模式同一套極簡檢查，不過回 1、stderr `bad_table:`），它所在的資料夾當 node，擋板檔、停格檔、紀錄都在那裡的 `.aos/`（不在就建資料夾）；檔在 `.aos/` 裡時 node 取 `.aos` 的上一層。不存在回 1、stderr `no_node:`。

| 檔 | 內容 |
|---|---|
| `bin/aos-tick` | 命令列薄殼（`.gitignore` 擋 `bin/`，`git add -f` 進來的） |
| `lib/aos_tick.py` | argv、`AOS_DIRNAME` 檢查、認 node 與任務表 `resolve_node()`、取鎖 `take_lock()`、擋板、停格檔、整格順序 `run_tick()` |
| `lib/aos_tick_record.py` | 結束碼紀錄 `current.json`／`last.json`：開格換檔、每項重寫 |
| `lib/aos_tick_table.py` | 讀任務表（預設 `.aos/tasks.json`，`--node` 給檔時讀那個檔）、極簡檢查 `check_table()`、每項的 `id`、跑到時展開成 inst |
| `lib/aos_tick_run.py` | 跑一項：照 inst 開串流、四個 `AOS_*`、分 exit／signal |
| `tests/test_tick.py` | plan 各步的驗收，一個類別一步；結束碼慣例另成 `ExitCodes` |

**同資料夾互斥與讀表時機（使用者 2026-10-01，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick-最簡互斥與讀表時機待統一更新-spec)、[plan 待問 12](../../plan/m1-tick-core.md#待問)）**：一格照「認 node 與任務表 → 取鎖 → 擋板 → 讀表 → 換紀錄 → 刪停格檔 → 照表跑」。鎖是 `.aos/tick.lock` 的非阻塞 `flock`（不存在就建），拿不到 `busy:`、回 ~~2~~ 0（結束碼慣例改版）；鎖 fd 不傳給任務（`os.open` 預設不可繼承）。表壞在換紀錄之前，不算開過一格。

**`AOS_DIRNAME`（使用者 2026-10-01，見上面改動 3、[plan 待問 13、15](../../plan/m1-tick-core.md#待問)）**：本節所有 `.aos` 都是這個名字；不合法 stderr `usage:`、回 1。設成空字串時 `tasks.json`、`tick.lock`、`tick-blocked`、`tick/stop`、`tick/current.json`／`last.json` 都直接在 node 資料夾下，檔案模式「檔在 `.aos/` 裡就往上取一層」不適用（`take_lock()` 不建資料夾）。

**POC 默認一切正常（使用者 2026-10-01，見 [plan 第一段待問 8](../../plan/m1-tick-core.md#待問)）**：~~不取鎖（不回 75、沒有 `AOS_TICK_LOCK_FD`）、~~（同日加回最簡互斥，見上段；仍不回 75、沒有 `AOS_TICK_LOCK_FD`）不驗表（不回 2、沒有 `config_invalid`）、不看 `user`（不回 125、沒有 `user_mismatch`）、不判上下層、不做 `--firstdo-fsync`、不處理紀錄讀不懂或寫不進。出事就讓 Python 自然丟錯（traceback、回 1）。~~整格只回 0／1；argv 用法錯回 2。~~（10-01 再改，見下段）

**結束碼照 aos 體系慣例（使用者 2026-10-01，同日改版，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)、[plan 待問 9、15](../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：0＝預料之中（含正常中斷）、非 0＝要額外處理、1＝通用錯誤（~~0 正常結束、1 錯誤結束、2 正常中斷~~）。`aos-tick` 的碼只講 tick 自己，現在只回 0／1：

| 狀況 | 回 |
|---|---|
| 照表跑完（不管任務回幾、成敗） | 0 |
| 看到停格檔 `.aos/tick/stop`，剩下不跑（不算中斷，暫定） | 0 |
| 同資料夾上一格還沒跑完（拿不到 `.aos/tick.lock`，stderr `busy:`），不開格（不寫紀錄、不加 `seq`） | 0（原 2） |
| 有擋板檔 `.aos/tick-blocked`（stderr `blocked:`），不開格（不寫紀錄、不加 `seq`） | 0（原 2） |
| argv 用法錯、`AOS_DIRNAME` 不合法、`--node` 指的東西不存在、`--node` 資料夾底下沒有 `.aos/tasks.json`、任務表不合極簡檢查（stderr `usage:`／`no_node:`／`no_tasks:`／`bad_table:`；表壞不換紀錄、不加 `seq`） | 1 |
| tick 自用檔（`tick-blocked`、`stop`、`current.json`、`last.json`）讀不到／寫不進／格式壞 | 1（自然丟錯，traceback 進 stderr） |

任務回 0、1、2、125～127、被訊號殺都照實記進紀錄、照常跑下一項。紀錄收尾的 `exit` 因此只會是 0。

### review 導讀

讀的順序：

0. `lib/aos_dirname.py`：`AOS_DIRNAME` 的名字與合法判斷（aos-exec 也用）。
1. `lib/aos_tick.py` 的 `run_tick()`／`_run_locked()`：整格照 B-620「一格怎麼走」一行一步，先看它知道全貌。
2. 同檔 `resolve_node()`、`take_lock()`、`state()`、`read_reason()`、`remove_stop_file()`、`run_one()`。
3. `lib/aos_tick_record.py`：`Record.open()`（換檔四步）→ `add_task()`／`finish()` → `_rewrite()`。
4. `lib/aos_tick_table.py`：`read_table()` → `check_table()`、`load_inst()`。
5. `lib/aos_tick_run.py`：`run_item()`。
6. `tests/test_tick.py`：`Step1Node`、`Step1Lock`…`Step9Whole`、`DirName`、`EmptyDirName`，對著 plan 各步的驗收讀。

每個函式開頭一行註明對應的 spec 條號。

plan 步驟對到哪：

| 步驟 | 函式 |
|---|---|
| 1 找資料夾、取鎖 | `main()`、`resolve_node()`、`take_lock()` |
| 2 擋板檔、結束碼 | `run_tick()`、`read_reason()`、`say()` |
| 3 紀錄與格數 | `Record.open()`、`_read_seq()`、`_rewrite()` |
| 4 讀表 | `aos_tick_table.read_table()`、`check_table()` |
| 5 照表跑 | `run_tick()` 迴圈、`run_one()`、`aos_tick_run.run_item()` |
| 6 停格檔 | `remove_stop_file()`、`run_tick()` 迴圈裡的 `read_reason(STOP)` |
| 7、8 | 2026-10-01 取消（fsync、上下層） |

我自己做的判斷（spec 沒寫死、照「最小合理」做，都可以改）：

- ~~沒有 `.aos/`：整個交給 `aos_exec.run_target` 跑這個資料夾（不寫紀錄、退出碼照 aos-exec）；連 `inst.json` 也沒有時是 aos-exec 自己的用法錯 2。~~（2026-10-01 作廢：退路拿掉，沒有 `.aos/inst.json` 就 stderr `no_inst:`、回 1；只看在不在，不讀它的內容。）~~見 `aos_tick.run_tick` 開頭。~~（2026-10-01 再改：改看 `.aos/tasks.json`，見 `aos_tick.resolve_node`）
- 新增的 stderr 代碼：`usage`（argv 錯、`AOS_DIRNAME` 不合法）、`busy`（拿不到鎖）、~~`no_inst`（沒有 `.aos/inst.json`）~~、`no_tasks`（資料夾沒有 `.aos/tasks.json`）、`no_node`（`--node` 指的東西不存在）、`bad_table`（任務表不合極簡檢查）、`exec_failed`（某項沒跑成：mkdir／cwd／重導向失敗、126／127）。
- 某項沒跑成（mkdir、cwd、重導向失敗）記 `exit:125`，跟 aos-exec 命令列一致（inst 的規定，不是帳號判定）。
- 項目是純記憶體文件（跟 `load_obj` 一樣），所以項目裡的 `$ref:""` 指這一項自己，不是整份 tasks.json。
- 任務的 id 用開格讀表時拿到的；跑到時只展開 inst 部分。
- `envs` 清空時一個 `AOS_*` 都不放。
- 任務表極簡檢查（使用者 2026-10-01，[verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick-讀任務表的極簡檢查待統一更新-spec)）：合法 JSON、頂層物件有 `tasks` 陣列、每項（`$ref` 展開後）是物件且有 `argv`；不過 stderr 一行 `bad_table:`、回 1。~~檢查在換紀錄之後，表壞仍佔 `seq`、紀錄停在 `ended:false`。~~（使用者 2026-10-01 改：在換紀錄之前，表壞不換紀錄、不加 `seq`）每項沒寫 `_metainfo` 照跑（`aos_inst` 當 posix 第 1 版）；寫錯了跑到那項時 `aos_inst` 自然丟錯回 1。
- 沒 `id` 的項（使用者 2026-10-01）：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串，紀錄、`AOS_TASK_ID`、`stopped_after` 都用它；跟別項撞了不管。`id` 不是字串時 `AOS_TASK_ID` 用 `str()`（我自己定的）。
- `--node` 給的檔在 `.aos/` 裡（例如 `yyy/.aos/tasks.json`）時 node 取 `yyy`，不照字面當 `yyy/.aos`（否則紀錄會寫進 `yyy/.aos/.aos/tick/`）。所以舊用法 `--node yyy/.aos/inst.json` 現在是「拿 inst.json 當任務表」，沒有 `tasks` 陣列、過不了極簡檢查回 1。
- `--node` 給檔時，任務項目裡的相對檔名照舊以 node 根（檔所在的資料夾，或 `.aos` 的上一層）為中心，不是以那個檔為中心。

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
  "exec_err_path": "<inst>/err.log",
  "insts": [
    {"inst": "a"},
    {"inst": "jobs/report.json", "interval_ms": 5000, "stop_on_nonzero": true}
  ]
}
```

| 鍵 | 意思 |
|---|---|
| `insts[].inst` | 必填，**原樣**當 aos-exec 的參數（資料夾或檔都行），印出來也照字面 |
| `cwd`（頂層） | 起點：aos-exec 子程序的工作目錄、相對路徑的基準。沒寫＝daemon 啟動時的工作目錄；相對的也以它為準 |
| `interval_ms` | 上一次結束後隔多久再叫（剛開時每項先立刻跑一次）。頂層是預設、每項可蓋過；兩邊都沒有＝設定錯、回 1 |
| `stop_on_nonzero` | 碼不是 0 時這一項就不再叫、多印一行 `stopped`。頂層是預設、每項可蓋過；都沒有＝`false`。所有項都停了 daemon 照樣開著 |
| `exec_err_path`（頂層） | aos-exec 的 stderr 接到哪個檔（接在檔尾、父資料夾不在就建）。相對以起點為準；`<inst>` 換成 inst 字面值，inst 是檔時換成它字面上的 dirname（空的用 `.`）。沒寫＝daemon 自己的 stderr |
| `modules`（頂層） | 可選，要是物件（不是＝設定錯、回 1）。之後一個模組一個鍵（例如 `"modules": {"control": {...}}`）；**目前沒有任何模組**，核心照收、不看裡面 |

**整份設定檔先經 aos 指示詞展開再讀**（使用者 2026-10-01；跟 inst 同一套 `lib/aos_directives.py`，`$ref`／`$fmt`／`$env`）。順序與兩種起點：

1. **先展開**：整份從根一路走進物件與陣列，每一格解到底。`$ref` 的相對檔名**一律以設定檔所在的資料夾**為準（`os.path.abspath`，不解符號連結；被引進來的檔裡再 `$ref` 也照這個資料夾，中心路徑不換）。`$opt` 物件原樣留著、不走進去（核心沒有吃選項的位置，留給模組）。引到自己的祖先＝`ReferenceCycle`。
2. **展開完才讀鍵**：頂層 `cwd`（可以是 `$ref` 引進來的值）照上表的規則算起點——**相對的 `cwd` 以 daemon 啟動時的工作目錄為準，不是設定檔的資料夾**；`inst` 值、`exec_err_path` 再以起點為準。

所以同一份設定檔裡，`$ref` 的檔名跟 `inst`／`cwd` 的值起點不同：前者看設定檔放哪，後者看 daemon 從哪開（或 `cwd`）。例：設定檔在 `conf/daemon.json`、daemon 從 `/w` 開：

```json
{"interval_ms": {"$ref": "defaults.json#/interval_ms"}, "insts": {"$ref": "list.json"}}
```

讀的是 `conf/defaults.json`、`conf/list.json`；`list.json` 裡寫 `{"inst": "x.json"}` 跑的是 `/w/x.json`。指示詞錯（讀不到、循環、位置找不到…）stderr 一行 `aos-daemon: config: <代號>: …`、回 1。

stdout 每次一行（時間是印出那刻的本地時間，ISO 8601 帶時區）：

```text
2026-10-01T15:04:05+08:00 inst=a exit=0 ms=812
2026-10-01T15:04:05+08:00 inst=jobs/report.json exit=3 ms=23
2026-10-01T15:04:05+08:00 inst=jobs/report.json stopped
```

aos-exec 的 stderr 每次收齊（讀到 pipe 底）再一次寫出，有內容才寫，前面一律加一行標頭（第幾項從 0 起、inst 字面值；寫到 `<inst>` 個別檔也加，使用者 2026-10-01 同意）；stdout 那一行跟它共用一把鎖，多項同時結束也不交錯：

```text
== 2026-10-01T15:04:05+08:00 index=1 inst=jobs/report.json ==
boom
```

inst 裡任務自己的 stderr 照 inst 規則（預設 `/dev/null`，寫 `"stderr": {"$opt": "inherit"}` 才會跟著 aos-exec 進來）。被訊號殺的碼印成 `128+N`。結束碼：用法錯（沒給 `--config`、多給參數）、設定錯、設定檔讀不到、指示詞錯都 1；SIGINT／SIGTERM 0。daemon 退出後還在跑的 aos-exec 再寫 stderr 會吃 SIGPIPE，照默認一切正常不處理（使用者 2026-10-01 同意）。

| 函式（`lib/aos_daemon.py`） | plan 步驟 |
|---|---|
| `main()`、`_Parser`、`read_config()`、`expand()`、`load_config()`、`err_path_for()` | 1 讀設定檔（先展開指示詞） |
| `run_once()`、`write_err()`、`say()`、`now()` | 2 叫一次、印一行 |
| `loop()` | 3 週期、4 非 0 停不停 |
| `_quit()` | 5 Ctrl-C 與 SIGTERM |

測試 `tests/test_daemon.py`：`Step1Config`～`Step6Tick`，一個類別一步（步驟 1 另有 `Step1Directives`：指示詞與 `modules`），整檔約 6 秒。

## 跑測試

```sh
cd proto6/src/py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests
```
