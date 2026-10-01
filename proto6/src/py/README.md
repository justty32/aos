# proto6/src/py

← [proto6 plan](../../plan/README.md)

inst 與 `aos-exec` 直接從 proto5 複製（proto5 `470f5a04`，即 `git log -1 --format=%h -- proto5/lib proto5/cli`），不重寫。說明文件看 proto5 的 [lib/docs/exec.md](../../../proto5/lib/docs/exec.md)、[directives.md](../../../proto5/lib/docs/directives.md)。

| 這裡 | 來源 | 內容改了什麼 |
|---|---|---|
| `bin/aos-exec` | `proto5/cli/aos-exec` | 沒改（它本來就找 `../lib`）。repo 的 `.gitignore` 擋 `bin/`，這檔是 `git add -f` 進來的 |
| `lib/aos_directives.py` | `proto5/lib/` 同名檔 | 沒改 |
| `lib/aos_exec.py`、`aos_exec_run.py`、`aos_exec_spawn.py` | `proto5/lib/` 同名檔 | 改動 2 |
| `lib/aos_inst.py` | `proto5/lib/aos_inst.py` | 改動 1 |
| `tests/test_inst.py`、`test_directives.py`、`test_exec_spawn.py` | `proto5/lib/test/` 同名檔 | 沒改 |
| `tests/test_exec.py`、`test_exec_full.py` | `proto5/lib/test/` 同名檔 | 跟著改動 2 改（標「proto6 改／新增」） |
| `tests/_util.py` | `proto5/lib/test/_util.py` | 只改 `LIB`、`EXEC` 兩行路徑 |
| `tests/test_user.py` | 新寫 | 測改動 1 |

## 改動 1：認得頂層 `user`

proto6 inst 第 1 版多了頂層 `user`（[inst.md](../../spec/base/inst.md)）。`aos_inst._check_user()` 在解任何指示詞之前看原始頂層的 `user` 字面值：

- 沒寫或空字串：照跑。
- 名稱或 UID 解析後跟目前行程的 euid 相同：照跑。**不切換身分。**
- 不同：`UserNotGranted`；型別錯、放指示詞、負數、查不到帳號：`UserInvalid`。都是 125、不跑、不寫 `exit`，stderr 一行「aos-exec: 代號: 白話」。

整份 `$ref` 引進來的 `user` 不看（照 proto5 忽略）。

## 改動 2：資料夾目標怎麼找 inst

照 [inst.md「inst 目標」](../../spec/base/inst.md)：

- 目標是資料夾：先找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json`；兩個都有跑前者；都沒有＝用法錯（2）。base 是 `xxx` 自己。
- 拿掉 proto5 的 `--dir-target` 旗標、`run_target`／`run_target_full`／`spawn_target` 的 `dir_target` 參數與 `DEFAULT_DIR_TARGET` 常數（改成 `DIR_TARGETS` 兩個位置）。給 `--dir-target` 現在是用法錯。
- 檔案目標照 proto5 不動。~~tick 那條「`.aos/inst.json`／`inst.json` 路徑正規化成資料夾」不在這裡做。~~（2026-10-01：tick 不再做這個正規化，`--node` 怎麼認見下面 aos-tick 一節）

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
| `lib/aos_tick.py` | argv、認 node 與任務表 `resolve_node()`、擋板、停格檔、整格順序 `run_tick()` |
| `lib/aos_tick_record.py` | 結束碼紀錄 `current.json`／`last.json`：開格換檔、每項重寫 |
| `lib/aos_tick_table.py` | 讀任務表（預設 `.aos/tasks.json`，`--node` 給檔時讀那個檔）、極簡檢查 `check_table()`、每項的 `id`、跑到時展開成 inst（拿掉 `user`） |
| `lib/aos_tick_run.py` | 跑一項：照 inst 開串流、四個 `AOS_*`、分 exit／signal |
| `tests/test_tick.py` | plan 各步的驗收，一個類別一步；結束碼慣例另成 `ExitCodes` |

**POC 默認一切正常（使用者 2026-10-01，見 [plan 第一段待問 8](../../plan/m1-tick-core.md#待問)）**：不取鎖（不回 75、沒有 `AOS_TICK_LOCK_FD`）、不驗表（不回 2、沒有 `config_invalid`）、不看 `user`（不回 125、沒有 `user_mismatch`）、不判上下層、不做 `--firstdo-fsync`、不處理紀錄讀不懂或寫不進。出事就讓 Python 自然丟錯（traceback、回 1）。~~整格只回 0／1；argv 用法錯回 2。~~（10-01 再改，見下段）

**結束碼照 aos 體系慣例（使用者 2026-10-01，見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)、[plan 待問 9](../../plan/m1-tick-core.md#待問)，待統一更新 spec）**：0 正常結束、1 錯誤結束、2 正常中斷。`aos-tick` 的碼只講 tick 自己：

| 狀況 | 回 |
|---|---|
| 照表跑完（不管任務回幾、成敗） | 0 |
| 看到停格檔 `.aos/tick/stop`，剩下不跑（不算中斷，暫定） | 0 |
| 有擋板檔 `.aos/tick-blocked`，不開格（不寫紀錄、不加 `seq`） | 2 |
| argv 用法錯、`--node` 指的東西不存在、`--node` 資料夾底下沒有 `.aos/tasks.json`、任務表不合極簡檢查（stderr `usage:`／`no_node:`／`no_tasks:`／`bad_table:`） | 1 |
| tick 自用檔（`tick-blocked`、`stop`、`current.json`、`last.json`）讀不到／寫不進／格式壞 | 1（自然丟錯，traceback 進 stderr） |

任務回 0、1、2、125～127、被訊號殺都照實記進紀錄、照常跑下一項。紀錄收尾的 `exit` 因此只會是 0。

### review 導讀

讀的順序：

1. `lib/aos_tick.py` 的 `run_tick()`：整格照 B-620「一格怎麼走」一行一步，先看它知道全貌。
2. 同檔 `resolve_node()`、`read_reason()`、`remove_stop_file()`、`run_one()`。
3. `lib/aos_tick_record.py`：`Record.open()`（換檔四步）→ `add_task()`／`finish()` → `_rewrite()`。
4. `lib/aos_tick_table.py`：`read_table()` → `check_table()`、`load_inst()`。
5. `lib/aos_tick_run.py`：`run_item()`。
6. `tests/test_tick.py`：`Step1Node`…`Step9Whole`，對著 plan 各步的驗收讀。

每個函式開頭一行註明對應的 spec 條號。

plan 步驟對到哪：

| 步驟 | 函式 |
|---|---|
| 1 找資料夾 | `main()`、`resolve_node()` |
| 2 擋板檔、結束碼 | `run_tick()`、`read_reason()`、`say()` |
| 3 紀錄與格數 | `Record.open()`、`_read_seq()`、`_rewrite()` |
| 4 讀表 | `aos_tick_table.read_table()`、`check_table()` |
| 5 照表跑 | `run_tick()` 迴圈、`run_one()`、`aos_tick_run.run_item()` |
| 6 停格檔 | `remove_stop_file()`、`run_tick()` 迴圈裡的 `read_reason(STOP)` |
| 7、8 | 2026-10-01 取消（fsync、上下層） |

我自己做的判斷（spec 沒寫死、照「最小合理」做，都可以改）：

- ~~沒有 `.aos/`：整個交給 `aos_exec.run_target` 跑這個資料夾（不寫紀錄、退出碼照 aos-exec）；連 `inst.json` 也沒有時是 aos-exec 自己的用法錯 2。~~（2026-10-01 作廢：退路拿掉，沒有 `.aos/inst.json` 就 stderr `no_inst:`、回 1；只看在不在，不讀它的內容。）~~見 `aos_tick.run_tick` 開頭。~~（2026-10-01 再改：改看 `.aos/tasks.json`，見 `aos_tick.resolve_node`）
- 新增的 stderr 代碼：`usage`（argv 錯）、~~`no_inst`（沒有 `.aos/inst.json`）~~、`no_tasks`（資料夾沒有 `.aos/tasks.json`）、`no_node`（`--node` 指的東西不存在）、`bad_table`（任務表不合極簡檢查）、`exec_failed`（某項沒跑成：mkdir／cwd／重導向失敗、126／127）。
- 某項沒跑成（mkdir、cwd、重導向失敗）記 `exit:125`，跟 aos-exec 命令列一致（inst 的規定，不是帳號判定）。
- 項目是純記憶體文件（跟 `load_obj` 一樣），所以項目裡的 `$ref:""` 指這一項自己，不是整份 tasks.json。
- 任務的 id 用開格讀表時拿到的；跑到時只展開 inst 部分。
- `envs` 清空時一個 `AOS_*` 都不放。
- 任務表極簡檢查（使用者 2026-10-01，[verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md#aos-tick-讀任務表的極簡檢查待統一更新-spec)）：合法 JSON、頂層物件有 `tasks` 陣列、每項（`$ref` 展開後）是物件且有 `argv`；不過 stderr 一行 `bad_table:`、回 1。檢查在換紀錄之後，表壞仍佔 `seq`、紀錄停在 `ended:false`。每項沒寫 `_metainfo` 照跑（`aos_inst` 當 posix 第 1 版）；寫錯了跑到那項時 `aos_inst` 自然丟錯回 1。
- 沒 `id` 的項（使用者 2026-10-01）：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串，紀錄、`AOS_TASK_ID`、`stopped_after` 都用它；跟別項撞了不管。`id` 不是字串時 `AOS_TASK_ID` 用 `str()`（我自己定的）。
- `--node` 給的檔在 `.aos/` 裡（例如 `yyy/.aos/tasks.json`）時 node 取 `yyy`，不照字面當 `yyy/.aos`（否則紀錄會寫進 `yyy/.aos/.aos/tick/`）。所以舊用法 `--node yyy/.aos/inst.json` 現在是「拿 inst.json 當任務表」，沒有 `tasks` 陣列、過不了極簡檢查回 1。
- `--node` 給檔時，任務項目裡的相對檔名照舊以 node 根（檔所在的資料夾，或 `.aos` 的上一層）為中心，不是以那個檔為中心。

## 跑測試

```sh
cd proto6/src/py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests
```
