# proto6/src/py — aos-tick

← [proto6/src/py README](../README.md)｜上一份：[改動 1–4](changes.md)｜下一份：[hooks 與 tasks-blocked](hooks.md)

## aos-tick（第一段 tick 核心，新寫）

照 [plan 第一段](../../../plan/m1-tick-core.md) 寫的，不是從 proto5 複製。行為以程式與測試為準；格式與結束碼見 spec [tick 核心](../../../spec/tick.md)、[tick 協議](../../../spec/protocol/tick.md)（任務表 P-202、命令列與環境變數 P-203、紀錄與 tasks-blocked P-213）。這份只放怎麼跑、檔在哪、怎麼讀程式。

最小例子（在 repo 根目錄執行）：

```sh
tick_bin="$PWD/proto6/src/py/bin/aos-tick"
mkdir -p /tmp/n/.aos
echo '{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[{"id":"t","argv":["true"]}]}' > /tmp/n/.aos/tasks.json
"$tick_bin" /tmp/n; echo $?                           # 0
cat /tmp/n/.aos/tick/current/record.json              # {"version":1,"seq":1,...,"ran":{"$ref":"ran.json"},...,"ended":true,"exit":0}
PYTHONPATH=proto6/src/py/lib python3 -c 'import aos_tick_record as r; print(r.read_record("/tmp/n/.aos/tick/current"))'   # 展開後的完整紀錄
(cd /tmp/n && "$tick_bin")                            # 不給目標用目前目錄（相對路徑也行）
"$tick_bin" /tmp/n/.aos/tasks.json; echo $?           # 1，stderr usage:（目標要是資料夾）
```

目標只能是資料夾（省略＝`./`），任務表只看 `<目標>/.aos/tasks.json`。「工作資料夾」＝目標資料夾，也是這一格 aos-tick 的 cwd；鎖、紀錄都在它的 `.aos/`。給任務的 `AOS_TICK_CWD`、`AOS_TASK_ID`、`AOS_TASK_INDEX` 見 P-203 與 `aos_tick_run.RUN_VARS`。

| 檔 | 內容 |
|---|---|
| `bin/aos-tick` | 命令列薄殼（`.gitignore` 擋 `bin/`，`git add -f` 進來的） |
| `lib/aos_tick.py` | argv、`AOS_DIRNAME` 檢查、認工作資料夾與任務表 `resolve_target()`、取鎖 `take_lock()`、擋板、tasks-blocked `tasks_blocked()`／`clear_tasks_blocked()`、整格順序 `run_tick()` |
| `lib/aos_tick_record.py` | 結束碼紀錄資料夾 `tick/current/`／`last/`：開格換紀錄（整個資料夾 rename）、每項寫 `ran.json`、不是 0 才寫 `task-exits.json`／`hook-exits.json`、收尾寫 `record.json`；`read_record()` 讀展開 `$ref` 後的完整紀錄 |
| `lib/aos_tick_table.py` | 讀任務表、開格整份展開、頂層預設、極簡檢查 `check_table()`、每項的 `id`、跑到時合併預設交給 inst 規則 `load_inst()` |
| `lib/aos_tick_run.py` | 跑一項：照 inst 開串流、這一項的 `AOS_*`（先拿掉繼承來的 `AOS_TASK_*`／`AOS_HOOK_*`）、分 exit／signal |
| `lib/aos_tick_hooks.py` | hooks（m1h）：`run_point()` 跑一個掛點的一串、`run_after_task()` 在每項之後跑相關掛點；讀表在 `aos_tick_table.check_table()`。見 [hooks](hooks.md) |
| `tests/test_tick_target.py`、`test_tick_table.py`、`test_tick_blocked.py`、`test_tick_run.py`、`test_tick_dirname.py`（共用 `_tick_util.py`） | plan 各步的驗收，一個類別一步；結束碼慣例另成 `ExitCodes`（在 `test_tick_run.py`） |
| `tests/test_tick_hooks_after_all.py`、`test_tick_hooks_points.py`（共用 `_tick_hooks_util.py`） | hooks 的驗收（m1h） |

**任務表的預設與展開時機**：頂層的七個 inst 欄位是每一項的預設，淺層合併（項寫了的鍵整個蓋過，`envs` 也整包換）。展開分兩段：

- **開格時展開整份表**：頂層預設鍵、`modules`、`hooks` 各掛點、`tasks` 每一項的已知鍵都一路展開到底；`$ref:""`／`#…` 指整份 tasks.json，相對檔名以工作資料夾為中心。頂層與每項的陌生鍵、`_metainfo` 不解。任何一處解不開＝`bad_table:`、不開格。見 `aos_tick_table.read_table()`、`_items()`、`_expand()`。
- **跑到某一項時只合併**（預設＋這一項），交給 `aos_inst.load_obj` 驗與換算路徑，見 `aos_tick_table.load_inst()`。

所以值在開格那一刻就定了：前面的任務改了被 `$ref` 的檔，後面的項看不到；指向前面任務才會產生的檔，開格就 `bad_table`。測試見 `tests/test_tick_table.py` 的 `test_values_fixed_at_open`。

頂層 `cwd` 只是任務的預設 cwd（相對以工作資料夾為起點），不改 tick 自己的 cwd。頂層 `modules` 放 tick 模組的設定，現有的是 [`tasks-blocked`](hooks.md#tick-模組-modulestasks-blockedb-636)（P-214），其他鍵照收不理。頂層 `hooks` 見 [hooks](hooks.md)。範例（同 P-202）：

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

`build` 在 `<工作資料夾>/work` 跑、輸出接在 `work/logs/tasks.log`；`report` 自己寫了 cwd，在 `<工作資料夾>/reports` 跑（stdout 預設照用，接在 `reports/logs/tasks.log`）；第三項整項從 `<工作資料夾>/tasks.d/clean.json` 讀，再套預設。

**一格的順序**（`aos_tick.run_tick()`／`_run_locked()`）：認工作資料夾與任務表 → 取鎖 → 看擋板檔 → 讀表 → 換紀錄 → `before_all` → 照表跑（每項前看 tasks-blocked）→ `after_all` → 收尾寫紀錄 → 刪 tasks-blocked。所以開格前就放好的 tasks-blocked 照樣有效。鎖是 `.aos/tick.lock` 的非阻塞 `flock`（不存在就建），拿不到 `busy:`、回 0；鎖 fd 不傳給任務。表壞在換紀錄之前，不算開過一格。

**`AOS_DIRNAME`**：本節所有 `.aos` 都是這個名字，見 [改動 3](changes.md)。設成空字串時 `tasks.json`、`tick.lock`、`tick-blocked`、`tick/tasks-blocked`、`tick/current/`／`last/` 都直接在工作資料夾下（`take_lock()` 不建資料夾）。

**POC 默認一切正常**：不驗表（只做極簡檢查）、不看 `user`、不判上下層、不做 fsync、不處理紀錄讀不懂或寫不進。出事讓 Python 自然丟錯（traceback、回 1）。結束碼只回 0／1，對照見 P-203；任務回什麼都照實記、照跑下一項，不影響 tick 的碼。

**結束碼紀錄**：一格一個資料夾 `.aos/tick/current/`（上一格 `last/`），四個檔的內容與時機見 P-213。換紀錄＝刪 `last/`、`current/` 整個 rename 成 `last/`、暫存資料夾 `.current.tmp/` rename 成 `current/`；`$ref` 是相對路徑，改名後仍指得對。`seq` 從 `current/record.json`（沒有就 `last/record.json`）接著數。

### review 導讀

讀的順序：

0. `lib/aos_dirname.py`：`AOS_DIRNAME` 的名字與合法判斷（aos-exec 也用）。
1. `lib/aos_tick.py` 的 `run_tick()`／`_run_locked()`：整格一行一步，先看它知道全貌。
2. 同檔 `resolve_target()`、`take_lock()`、`state()`、`tasks_blocked()`、`clear_tasks_blocked()`、`run_one()`。
3. `lib/aos_tick_record.py`：`Record.open()`（換檔四步）→ `add_task()`／`finish()` → `_rewrite()`。
4. `lib/aos_tick_table.py`：`read_table()` → `check_table()`（回 `Table`：預設、各項、id）、`merge()`、`load_inst()`。
5. `lib/aos_tick_run.py`：`run_item()`。
6. `tests/test_tick_*.py`：`Step1Target`、`Step1Lock`…`Step4Defaults`…`Step9Whole`、`DirName`、`EmptyDirName`，對著 plan 各步的驗收讀。

每個函式開頭一行註明對應的 spec 條號。

plan 步驟對到哪：

| 步驟 | 函式 |
|---|---|
| 1 找資料夾、取鎖 | `main()`、`resolve_target()`、`take_lock()` |
| 2 擋板檔、結束碼 | `_run_locked()`（擋板只看 `os.path.lexists`）、`say()` |
| 3 紀錄與格數 | `Record.open()`、`_read_seq()`、`_rewrite()` |
| 4 讀表 | `aos_tick_table.read_table()`、`check_table()` |
| 5 照表跑 | `run_tick()` 迴圈、`run_one()`、`aos_tick_run.run_item()` |
| 6 tasks-blocked | `run_tick()` 迴圈裡每項之前的 `tasks_blocked()`、收尾後的 `clear_tasks_blocked()` |
| 6b `modules["tasks-blocked"]`（B-636） | 讀表 `aos_tick_table._tasks_blocked()`（`Table.on_blocked`）、跑 `aos_tick.run_on_blocked()` |
| 7、8 | 2026-10-01 取消（fsync、上下層） |

spec 沒寫死、照「最小合理」做的判斷（都可以改）：

- 某項沒跑成（mkdir、cwd、重導向失敗）記 `exit:125`，跟 aos-exec 命令列一致。
- 任務的 id 用開格讀表時拿到的（已展開）；沒 `id` 的項用它在 `tasks` 陣列的位置轉字串，跟別項撞了不管；`id` 不是字串時 `AOS_TASK_ID` 用 `str()`。
- `envs` 清空時一個 `AOS_*` 都不放。
- 每項沒寫 `_metainfo` 照跑（`aos_inst` 當 posix 第 1 版）；寫錯了跑到那項時 `aos_inst` 自然丟錯回 1。
