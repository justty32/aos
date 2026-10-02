← [tick：工作資料夾、任務表與一格 tick](../tick.md)（分檔 3/6）｜[上一份](02-P-202-任務註冊表.md)｜[下一份](04-P-203結束碼與P-204-P-212.md)

## P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕

### argv

`aos-tick [<目標>]`

- 目標是位置參數，跟 `aos-exec` 一樣；沒有 `--node`、`--target` 這類旗標。`-h`／`--help` 印用法、回 0。
- **沒給**：用目前目錄。相對路徑一律轉成絕對路徑；不往上層目錄找。
- **是資料夾**：要有 `.aos/tasks.json`，它就是任務表；不看 `.aos/inst.json`。沒有：`no_tasks`、回 1。
- **是檔**：用法錯，`usage`、回 1，什麼都不建〔使用者 2026-10-01：拿掉「目標給檔就當任務表」，原規則記在[暫緩區撤回表](../../deferred/tick/04-已撤回與被取代.md#已撤回被取代)〕。
- **不存在**：`no_target`、回 1。
- `-` 開頭的參數（`-h`／`--help` 除外，含舊的 `--node`、暫緩的 `--firstdo-fsync`）、多給一個目標，都算用法錯：`usage`、回 1。目標本身以 `-` 開頭時寫成 `./-x`。`AOS_DIRNAME` 不合法（含 `/`、是 `.` 或 `..`，[C-09](../../conventions.md)）也是 `usage`、回 1。
- 行為正本：[B-620](../../tick.md)「認哪個資料夾」。tick 在工作資料夾裡跑，cwd 就是管轄區；它不看自己在哪個 cgroup（[B-627](../../tick.md)）。
- 經 `aos-exec` 跑時：資料夾目標的 inst 只要 `{"argv":["aos-tick"]}`，預設 cwd 正好是那個資料夾。直接執行 `.aos/inst.json` 檔時 base 不同，要明寫 `cwd:".."` 或在 argv 給目標。
- 第十九批的 `--check`（全掛檢查）撤。

### tick 自己的介面

| 介面 | 約定 |
|---|---|
| stdin | 不讀；inst 預設 `/dev/null` |
| stdout | tick 自己不寫。任務的輸出照各自 inst 走（預設 `/dev/null`，明寫 inherit 才會跟 tick 共用） |
| stderr | tick 自己只印 `代碼: 說明` 一行（下表），或沒接住的錯的 traceback |
| 讀寫 | 讀任務表、持鎖、寫 `.aos/tick/` 的紀錄、每一項前看 tasks-blocked、整格最後刪它（P-213）。送收訊息是系統級任務的事（[B-629](../../deferred/template.md)）；任務自己直接讀寫檔案 |
| 身分 | tick 自己不切 UID；直接呼叫也不會替你取得 inst 的身分 |

核心自己的 stderr 代碼：

| 代碼 | 什麼時候 | 回 |
|---|---|---|
| `usage` | argv 用法錯（含目標是檔）、`AOS_DIRNAME` 不合法 | 1 |
| `no_target` | 目標不存在 | 1 |
| `no_tasks` | 目標是資料夾，底下沒有 `.aos/tasks.json` | 1 |
| `busy` | 拿不到 `.aos/tick.lock`：同資料夾上一格還沒跑完（[B-602](../../tick.md)） | 0 |
| `bad_table` | 任務表沒過極簡檢查（[B-620](../../tick.md)） | 1 |
| `exec_failed` | 某項沒跑成：mkdir／cwd／重導向失敗（記 `exit:125`）、沒執行權（126）、找不到程式（127）；附那一項的 id（hook 寫成 `<掛點>/<id>`，`after_task` 是 `after_task/<任務 id>/<id>`；`modules["tasks-blocked"]` 是 `tasks_blocked/<id>`） | 不影響，照常跑下一項 |

舊碼表的 `config_invalid`、`user_mismatch`、`record_unreadable`、`record_unwritable` 不再有；它們的來由見 [tick 暫緩區](../../deferred/tick.md)。

### 每項任務怎麼跑

| 介面 | 約定 |
|---|---|
| 身分 | 沿用 tick 的有效 UID、群組與資源範圍；任務沒有 `user`（寫了照陌生鍵）。tick 不切帳號；要換帳號在 daemon 設定檔拆成另一項（帳號模組；`aos-as` P-212 暫緩） |
| cwd／argv | 頂層預設＋本項合併成 inst、展開後執行（P-202）；合併後還是沒有 cwd 時是工作資料夾 |
| stdin | 預設 `/dev/null`；可用合併後 inst 的 stdin 重導向 |
| stdout／stderr | 照 inst 預設 `/dev/null`，可明寫 inherit 或重導向；tick 不把輸出文字當完成證據 |
| 環境 | 繼承 tick 的環境（含 `AOS_DIRNAME`，經 daemon 控制模組跑時還有 `AOS_DAEMON_CTL_SOCKET`（第二十五批改名）、`AOS_DAEMON_INST`，掛了訊息模組還有 `AOS_DAEMON_MQ_<門名>`），先拿掉繼承來的 `AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`、`AOS_HOOK_POINT`、`AOS_HOOK_INDEX`、`AOS_HOOK_ID`，加上下表這一項該有的變數，再照 inst 套用 `envs`；`envs` 清空時下表的也不放。這些變數都不是授權證據 |

tick 給任務的環境變數。整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`（hook 是 `AOS_HOOK_*`，見下）（aos 全部的環境變數見 [C-10](../../conventions.md)）：

| 變數 | 值 |
|---|---|
| `AOS_TICK_CWD` | 工作資料夾的絕對路徑，也就是這一格 tick 的 cwd。本格紀錄在 `$AOS_TICK_CWD/.aos/tick/current/`（`record.json` 加上它 `$ref` 的檔，P-213；狀態資料夾名照 `AOS_DIRNAME`；空字串時是 `$AOS_TICK_CWD/tick/current/`） |
| `AOS_TASK_ID` | 這一項的 id：任務表寫的 `id`；沒寫時是位置字串；不是字串時轉成字串 |
| `AOS_TASK_INDEX` | 這一項在 `tasks` 陣列的位置，十進位，從 0 起 |

hooks 的項（[B-635](../../tick/hooks.md)）跑法跟任務一樣，環境變數不同〔使用者 2026-10-01 第十批〕：有 `AOS_TICK_CWD`，改給：

| 變數 | 值 |
|---|---|
| `AOS_HOOK_POINT` | 掛點名：`before_all`、`before_kind`、`after_task`、`after_kind`、`after_every_task`、`after_all`（`*_kind` 是第二十四批加的） |
| `AOS_HOOK_INDEX` | 這個 hook 在它自己那個陣列的位置，十進位，從 0 起（`after_task` 每個任務 id、`*_kind` 每個 kind 各自從 0 數） |
| `AOS_HOOK_ID` | 這個 hook 的 id；沒寫時是位置字串；不是字串時轉成字串 |

- `before_all`、`after_all`：**沒有** `AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_TASK_EXIT`。
- `after_task`、`after_every_task`〔使用者 2026-10-01 第十七批〕：另有剛跑完那一項的 `AOS_TASK_ID`、`AOS_TASK_INDEX`，加上 **`AOS_TASK_EXIT`**＝它的結束碼（十進位；被訊號 N 殺＝128+N）。〔[第二十四批](../../../../notes/verdicts/11-tick-as-unit/25-1002-第二十四批.md#2026-10-02-第二十四批kind)〕`after_kind` 同樣有這三個；`before_kind` 有那一項（還沒跑）的 `AOS_TASK_ID`、`AOS_TASK_INDEX`，沒有 `AOS_TASK_EXIT`（AI 隊定）。`AOS_TASK_EXIT` 只有 `after_task`、`after_kind`、`after_every_task` 有。

一般任務沒有 `AOS_HOOK_*`、也沒有 `AOS_TASK_EXIT`。

其他：

- 沒有設定需求的程式不必讀任何環境變數，也不必寫回應封套；`true`、腳本與既有程式都能直接當任務。
- 任務直接開檔讀設定；改設定的時機與「tick 裡不改 `config/`」的軟性原則見 [A-102](../../../agent/configuration.md)。
- key 不由 tick 放進 argv 或任務環境；inst 的 `envs` 照正本。
- 鎖 fd 不傳給任務，沒有 `AOS_TICK_LOCK_FD`（[B-602](../../tick.md)）；每項一框現在是 daemon 收屍模組（[B-644](../../daemon/cgroup.md)）；`aos-cg`（P-211、[B-634](../../deferred/cg.md)）第二十三批暫緩。
