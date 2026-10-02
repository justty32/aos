# 通用慣例：時間、版本、結束碼、狀態資料夾、環境變數、設定檔頂層

← [規格](README.md)｜[tick](tick.md)｜[daemon](daemon/README.md)

細節以程式與測試為準：[proto6/src/py](../src/py/README.md)。這裡只留原則。

## C-01：時間以 tick 為基準

- **aos 內部自己決定的時長算格數**（保留期、重試間隔、預算…）；**外部世界規定的才用毫秒**（逾時、daemon 叫醒 tick 的週期 `interval_ms`）。算誰的格：算安排它的那一層的格，上下層週期不同造成的落差不管。
- 起算點記「第幾格」，不另留毫秒版；格數就是 `seq`（紀錄裡，跨重啟接著數，見 [B-633](tick.md)），所以牆鐘倒退不影響。
- 欄位命名：時長 `*_ticks`、第幾格 `*_seq`、毫秒時長 `*_ms`、毫秒時間點 `*_at_ms`。型別在 [common.schema.json](protocol/schemas/common.schema.json)。
- 用作檔名的 ID 用 `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`；逾時用經過時間，不靠牆鐘。

## C-07：版本與陌生欄位

- **小改不升版**：加可選欄位、放寬值域、在寫明「開放」的列舉加值。讀的一方遇到不認得的欄位**直接忽略**（inst、`tasks.json`、daemon 設定檔、控制 socket 的請求都是）。
- **不相容的大改才升版**：刪欄位、改意思、改必填、收窄值域。inst 與任務表的每一項升 `_metainfo._version`（照 inst 規則只認 `posix`／`1`，不合就拒絕；任務表頂層的 `_metainfo` 不看）；自己的持久 JSON 檔帶 `"version": 1`。新程式讀目前版與前一版、寫目前版，遇到比自己新的拒絕。
- 程式改寫整份持久檔時，原樣保留不認得的欄位。例外：daemon 的 state 檔沒有 `version`、每次重建，陌生欄位下次寫檔就不見（[P-123](protocol/daemon/state.md)）。
- 任務表與 inst 都**沒有 `user`**：寫了當陌生鍵忽略，照 tick 自己的帳號跑；要換帳號只能在 daemon 設定檔的帳號模組做（B-646）。
- 沒有 `aos migrate`；舊檔轉版目前沒有程式。

程式：`lib/aos_inst.py`（`_metainfo`）、`lib/aos_tick_table.py`、`lib/aos_daemon_config.py`；測試：`tests/test_inst_reject.py`、`tests/test_tick_table.py`。

## C-08：結束碼

- **0＝預料之中，非 0＝要處理。** 正常的中斷（被擋、busy、有擋板）也是 0；正常機制結束 stderr 不印，唯一例外是 `busy` 印一行 `busy:`，讓人知道這格沒跑。
- **1＝通用錯誤**：沒有特別指定碼的錯一律 1，含用法錯（不用 2）。
- 特別指定的碼（`aos-exec` 的 125／126／127、子程式碼原樣傳出）寫在各程式自己那條。
- 讀別人的結束碼只分 0 與非 0；要記就照實記原碼。
- **任務出錯不算 tick 的錯**：`aos-tick` 只管自己，任務回幾都不改它的結束碼。
- 外部程式不懂這套（`grep` 回 1 是「沒找到」）；要照 aos 意思判讀，使用者自己包一層。

程式：`lib/aos_exec.py`、`lib/aos_tick.py`、`lib/aos_ctl.py`；測試：`tests/test_exec_status.py`、`tests/test_tick_run.py`、`tests/test_ctl_protocol.py`。

## C-09：狀態資料夾 `AOS_DIRNAME`

aos 放自己狀態檔的資料夾預設叫 `.aos`，環境變數 `AOS_DIRNAME` 可換名。三態要分清：**沒設**＝`.aos`；**空字串**＝不用子資料夾、直接放在資料夾本身；**其他值**＝換個名字。含 `/`、或剛好是 `.`／`..` 算用法錯（回 1）。規格裡寫的 `.aos/…` 都是沒設時的樣子。

空字串的代價：狀態檔與使用者檔混在一起，之後若用 git 管版本，使用者的檔也會被提交、還原。要保住使用者的檔就別用空字串。

程式：`lib/aos_dirname.py`；測試：`tests/test_tick_dirname.py`。

## C-10：環境變數

命名分工：整格共用 `AOS_TICK_*`、某一項專屬 `AOS_TASK_*`、hook 專屬 `AOS_HOOK_*`、daemon 給的 `AOS_DAEMON_*`。**新加變數要來這裡登一筆。**

| 變數 | 誰給 | 意思 |
|---|---|---|
| `AOS_DIRNAME` | 使用者 | 見 C-09 |
| `AOS_TICK_CWD` | tick | 工作資料夾絕對路徑；本格紀錄在其下 `<狀態資料夾>/tick/current/` |
| `AOS_TASK_ID`／`AOS_TASK_INDEX` | tick，給任務與跟任務有關的 hook（`before_kind`、`after_task`、`after_kind`、`after_every_task`） | 這一項的 id 與陣列位置 |
| `AOS_TASK_EXIT` | tick，只給任務跑完後的 hook（`after_task`、`after_kind`、`after_every_task`） | 剛跑完那項的結束碼（被訊號 N 殺＝128+N） |
| `AOS_HOOK_POINT`／`_INDEX`／`_ID` | tick，只給 hook | 掛點名、在該掛點的位置、hook id |
| `AOS_DAEMON_CTL_SOCKET` | daemon 控制模組 | 控制 socket 路徑 |
| `AOS_DAEMON_INST` | daemon（控制或訊息模組） | 這次跑的是 `insts` 的哪一項 |
| `AOS_DAEMON_MQ_<門名>` | daemon 訊息模組 | 該扇門的 socket 路徑 |

原則：tick 跑每一項前，先把繼承來的 `AOS_TASK_*`、`AOS_HOOK_*` 全拿掉再放這一項該有的，外層的值不外漏；其他變數一路往下傳（所以同一個 daemon 底下任何一層的 `aos-ctl` 找到的都是那個 daemon）；daemon 開 `aos-exec` 前先拿掉繼承來的所有 `AOS_DAEMON_*`，再照自己掛的模組重設，所以跨進下一層 daemon 就換成下一層的。已撤回、改名的舊名（`AOS_NODE_DIR`、`AOS_TICK_RECORD`、`AOS_DAEMON_SOCKET`、`AOS_DAEMON_MQ_SOCKET`）不再使用；暫緩的 `AOS_TICK_LOCK_FD`、`AOS_TICK_FIRSTDO_FSYNC`、`AOS_TICK_TOKEN` 見[暫緩區](deferred/README.md)。

## C-11：設定檔頂層 `cwd` 與指示詞展開

daemon 設定檔與任務表 `tasks.json` 都是「頂層放預設、底下一項一項」。共同原則：

- 頂層 `cwd` **不改程式自己的工作目錄**，只是底下各項的起點；相對路徑起點，daemon 是啟動時的 cwd、tick 是工作資料夾。
- 指示詞（`$ref`、`$fmt`、`$env`、`$opt`）都在讀檔時一次展開，展開失敗就整份不採用：
  - daemon 設定檔：認得的頂層欄位整個展開，`modules` 裡面全部展開；頂層陌生鍵與 `_metainfo` 不解。
  - 任務表：開格時展開已知的鍵（頂層預設、`modules`、`hooks`、每一項的 inst 欄位與 `id`、`kind`）；頂層與每一項的陌生鍵、`_metainfo` 不解。不認得的模組照樣展開，只是沒人執行。跑到某一項時只合併、不再展開。
- 任務表頂層能當預設的只有 inst 的七個欄位，淺層合併、項自己寫了就整個蓋過。

程式：`lib/aos_directives*.py`、`lib/aos_tick_table.py`、`lib/aos_daemon_config.py`；測試：`tests/test_tick_table.py`、`tests/test_daemon_config.py`、`tests/test_directives_*.py`。
