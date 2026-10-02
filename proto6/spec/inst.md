# inst：一次 POSIX 執行的描述檔

← [規格](README.md)｜[慣例](conventions.md)｜[tick](tick.md)｜[daemon](daemon/README.md)｜格式：[tick 協議 P-201](protocol/tick.md)

inst（`inst.json`，posix 第 1 版）只描述**一次** POSIX 執行：程式、參數、串流、工作目錄、環境。排程、資源框、tick 任務、git 提交都不在其中。**程式與測試就是正本**：`proto6/src/py/lib/aos_inst.py`（讀、驗、解）、`aos_directives*.py`（指示詞機制）、`aos_exec.py`／`aos_exec_run.py`（找目標、怎麼跑）；測試 `tests/test_inst_*.py`、`tests/test_directives_*.py`、`tests/test_exec_*.py`；格式 schema 是 [inst.schema.json](protocol/schemas/inst.schema.json)，說明 [docs/changes.md](../src/py/docs/changes.md)。

`aos-exec` 就是跑一份 inst 的程式；任務表（`tasks.json`）的每一項是 inst 的超集，所以 `aos-tick` 的核心本質上是加了功能的 `aos-exec`（B-620、B-626）。

## 形狀與版本

只有 `argv`（非空字串陣列）必填；其餘 `stdin`、`stdout`、`stderr`、`exit`、`cwd`、`envs` 沒寫就走預設（串流 `/dev/null`、`cwd` 是 inst 的 base、`envs` 疊在 runner 的環境上，只加不減）。`_metainfo` 預設 `{"_type":"posix","_version":1}`，不吃指示詞。陌生頂層鍵忽略，`_` 開頭的鍵留給格式資訊；**沒有 `user`**（見 C-07）。

## 找目標：檔案或資料夾

凡是「給一個目標交給 `aos-exec`」（命令列、daemon 設定檔 `insts` 的一項、人手直接跑）都照同一張表：

| 目標是 | 用哪份 inst | base（相對路徑起點） |
|---|---|---|
| `.json` 結尾的檔 | 就是它，當 inst JSON 讀 | 檔案所在的資料夾 |
| 其他檔案 | 不是 inst：直接當執行檔跑，`--` 之後的參數原樣給它 | — |
| 資料夾 | 先 `<目標>/.aos/inst.json`，沒有再 `<目標>/inst.json` | 目標資料夾自己（不是 `.aos/`） |

- `.aos` 是 `AOS_DIRNAME` 沒設時的名字（C-09）；設成空字串就只找 `<目標>/inst.json`。資料夾裡兩處都沒有＝用法錯，回 1。細節（不存在的 `.json`、名字叫 `x.json` 的資料夾…）以 `lib/aos_exec.py` 的 `run_target()` 與 `tests/test_exec_targets.py` 為準。
- daemon 核心沒有 id：`insts` 的鍵就是 inst 字面值，原樣交給 `aos-exec`（B-640）。
- `aos-tick` 的目標只能是**資料夾**，看的是 `tasks.json` 不是 `inst.json`；給檔是用法錯（這點跟 `aos-exec` 不同，B-620）。任務表頂層可放 inst 欄位當每一項的預設（C-11）。

## 指示詞與選項

值可以「從別處來」：`$env`、`$fmt`、`$ref`（可帶 `$at`）、`$opt`，同一個物件只跑優先順序最高的一個（`$opt > $ref > $fmt > $env`）。機制由 `aos_directives.py` 負責，它是純函式庫、不認得 inst；機制說明沿用 [proto5 directives](../../proto5/spec/directives/README.md)。inst 這個宿主只決定幾件事：

- 哪些位置要解、順序：整份頂層 → `cwd` → `argv` → `envs` → 四個路徑欄；key 與 `_metainfo` 不解。`$ref` 的相對路徑，頂層與 `cwd` 以 base 為中心，其餘以解出來的 `cwd` 為中心。
- 解完才驗型別；每個位置認得哪些 `$opt`（`inherit`、`append`、`mkdir`、`merge`、`clear`）看 `aos_inst.OPTIONS`，放在不吃選項的位置（`argv` 元素、`envs` 值…）就是 `UnknownOption`。
- 不自動呼叫 shell，不拆參數、不展開萬用字元；要就明寫 `["sh","-c","…"]`。`argv[0]` 用最後的 `PATH` 找。

## 怎麼跑

- **驗完才跑**：解析驗證與前置（建目錄、開檔）失敗，stderr 印「代號: 白話」、回 **125**，且**不寫 `exit`**。
- 開始跑之後：找不到程式回 127、無執行權回 126，這兩種算跑完一次，有 `exit` 就照寫；子程式正常退出用它的碼，被訊號 N 殺掉用 **128+N**。子程式自己也可能退出 125，要不要當啟動失敗得看別的證據。
- `exit` 檔寫十進位加換行，寫完 fsync 檔與父目錄。
- 子程式另開 session（`setsid`）；逾時先對整組 TERM，2 秒後還在就 KILL。這 2 秒只指 inst 自己的逾時，daemon 收尾另有寬限，兩者不混用。
- runner **不替你收輸出**（沒寫的串流一律 `/dev/null`）、**不注入 `AOS_*`**：環境變數靠繼承與 `envs`，`clear` 會一併清掉繼承來的。
- 結束碼慣例照 C-08：用法錯 1、`-h` 回 0。

## 錯誤代號

`InstError(code, msg)`，`str(e)` 是「代號: 白話」；指示詞機制丟的 `DirectiveError` 在 `load()` 包成同形狀。代號全表在 `aos_inst.py` 與 [directives errors](../../proto5/spec/directives/errors.md)：`ReadFailed`、`JsonSyntax`、`NotAnObject`、`MetainfoInvalid`、`UnsupportedInstType`、`UnsupportedInstVersion`、`EmptyArgv`、`FieldTypeMismatch`、`EnvKeyInvalid`、`OptionConflict`、`UnknownOption` 等。
