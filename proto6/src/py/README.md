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
- 檔案目標照 proto5 不動。tick 那條「`.aos/inst.json`／`inst.json` 路徑正規化成資料夾」不在這裡做。

## aos-tick（第一段 tick 核心，新寫）

照 [plan 第一段](../../plan/m1-tick-core.md) 寫的，不是從 proto5 複製。最小例子：

```sh
mkdir -p /tmp/n/.aos
echo '{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[{"id":"t","argv":["true"]}]}' > /tmp/n/.aos/tasks.json
proto6/src/py/bin/aos-tick --node /tmp/n; echo $?     # 0
cat /tmp/n/.aos/tick/current.json                     # {"version":1,"seq":1,...,"ended":true,"exit":0}
```

| 檔 | 內容 |
|---|---|
| `bin/aos-tick` | 命令列薄殼（`.gitignore` 擋 `bin/`，`git add -f` 進來的） |
| `lib/aos_tick.py` | argv、認資料夾、取鎖、擋板、停格檔、整格順序 `run_tick()`、預設上層 `default_parent()` |
| `lib/aos_tick_record.py` | 結束碼紀錄 `current.json`／`last.json`：開格換檔、每項重寫、舊紀錄讀不懂、fsync |
| `lib/aos_tick_table.py` | 讀 `.aos/tasks.json`、只驗四件事、每項的 `id`／`user`／inst |
| `lib/aos_tick_run.py` | 跑一項：照 inst 開串流、鎖 fd 傳給任務、五個 `AOS_*`、分 exit／signal |
| `tests/test_tick.py` | plan 步驟 1～9 的驗收，一個類別一步 |

### review 導讀

讀的順序：

1. `lib/aos_tick.py` 的 `run_tick()`：整格照 B-620「一格怎麼走」一行一步，先看它知道全貌。
2. 同檔 `take_lock()`、`read_reason()`、`remove_stop_file()`、`run_one()`、`node_dir_from_arg()`、`default_parent()`。
3. `lib/aos_tick_record.py`：`Record.open()`（換檔四步）→ `add_task()`／`finish()` → `_rewrite()`。
4. `lib/aos_tick_table.py`：`read_table()`（四件事）→ `task_id()`、`check_user()`、`load_inst()`。
5. `lib/aos_tick_run.py`：`run_item()`。
6. `tests/test_tick.py`：`Step1Lock`…`Step9Whole`，對著 plan 各步的驗收讀。

每個函式開頭一行註明對應的 spec 條號。

plan 步驟對到哪：

| 步驟 | 函式 |
|---|---|
| 1 找資料夾、取鎖 | `main()`、`node_dir_from_arg()`、`run_tick()` 開頭、`take_lock()` |
| 2 擋板檔、結束碼 | `run_tick()`、`read_reason()`、`say()` |
| 3 紀錄與格數 | `Record.open()`、`_read_seq()`、`_rewrite()` |
| 4 讀表驗四件事 | `aos_tick_table.read_table()` |
| 5 照表跑 | `run_tick()` 迴圈、`run_one()`、`aos_tick_run.run_item()` |
| 6 停格檔 | `remove_stop_file()`、`run_tick()` 迴圈裡的 `read_reason(STOP)` |
| 7 fsync（紀錄寫不進的處理依待問 7 拿掉） | `Record._write_tmp()`、`_fsync_dir()`；舊紀錄讀不懂在 `open()` |
| 8 上下層 | `default_parent()` |

我自己做的判斷（spec 沒寫死、照「最小合理」做，都可以改）：

- 沒有 `.aos/`：照 aos-exec 找檔（使用者裁定 09-30 晚）。有 `inst.json` 就用 `aos_exec.run_target` 跑一次（不取鎖、不寫紀錄、退出碼照 aos-exec）；兩個都沒有回 2、印 `config_invalid:`（碼是我選的）。見 `aos_tick.run_bare_inst`。
- 新增的 stderr 代碼：`usage`（argv 錯）、`lock_unavailable`（鎖檔開不了，回 75）、`exec_failed`（某項沒跑成：mkdir／cwd／重導向失敗、126／127、跑到時重新展開失敗）、`stop_unremovable`。鎖被占時什麼都不印。
- 紀錄寫不進（唯讀、滿碟）不另處理（待問 7 裁定默認寫得進去）：OSError 照常丟出，tick 印 traceback、回 1。
- 某項沒跑成（mkdir、cwd、重導向失敗，或跑到時重新展開壞了）記 `exit:125`，跟 aos-exec 命令列一致。
- `id` 要是非空字串，否則表壞；ID 的字元規則不驗（完整 schema 的事）。
- `user` 型別錯（負數、布林、指示詞）算表壞；帳號名稱查不到**不算**表壞，跑到時當成「跟 tick 不同」回 125（範例表的 `aos-a0042` 在別台機器本來就可能不存在）。
- 項目是純記憶體文件（跟 `load_obj` 一樣），所以項目裡的 `$ref:""` 指這一項自己，不是整份 tasks.json。
- 任務的 id 用開格驗表時讀到的；跑到時只重新展開 inst 部分（待問 6：驗表後假設檔案不變）。
- 五個 `AOS_*` 先拿掉外面繼承的同名變數再放（tick 本身是上層 tick 的一項時不會漏進舊值）；`envs` 清空時只留 `AOS_TICK_LOCK_FD`。
- 舊紀錄「在的那幾份全讀不懂」就算 `record_unreadable`（spec 寫兩份都壞；一份壞、一份不在也照辦，免得 seq 從 1 重數）；這時本格沒有紀錄、任務不設 `AOS_TICK_RECORD`。

## 跑測試

```sh
cd proto6/src/py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests
```
