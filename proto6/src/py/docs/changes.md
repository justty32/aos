# proto6/src/py — 改動 1–4

← [proto6/src/py README](../README.md)｜下一份：[aos-tick](tick.md)

## ~~改動 1：認得頂層 `user`~~（2026-10-01 撤回）

使用者 2026-10-01（原話「aos-exec應該也不需要認得頂層user吧。」，見 [verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit/06-1001-互斥-狀態資料夾-user.md#aos-exec-不認得頂層-user已寫入-speccommit-前由我補號)）：`lib/aos_inst.py` 換回 proto5 原檔，`user` 當不認得的鍵照 inst 規則忽略、照目前身分跑；`UserNotGranted`／`UserInvalid`、`test_user.py`（7 條）一併拿掉。aos-tick 原本「交給 `load_obj` 前先拿掉 `user`」因此多餘，也拿掉了。

~~原本：`aos_inst._check_user()` 在解任何指示詞之前看原始頂層的 `user` 字面值；跟目前身分不同 `UserNotGranted`、型別錯等 `UserInvalid`，都是 125。~~

## 改動 2：資料夾目標怎麼找 inst

照 [inst.md「找目標」](../../../spec/inst.md)：

- 目標是資料夾：先找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json`；兩個都有跑前者；都沒有＝用法錯（~~2~~ 1，見改動 4）。base 是 `xxx` 自己。
- 拿掉 proto5 的 `--dir-target` 旗標、`run_target`／`run_target_full`／`spawn_target` 的 `dir_target` 參數與 `DEFAULT_DIR_TARGET` 常數（改成 `DIR_TARGETS` 兩個位置）。給 `--dir-target` 現在是用法錯。
- 檔案目標照 proto5 不動。~~tick 那條「`.aos/inst.json`／`inst.json` 路徑正規化成資料夾」不在這裡做。~~（2026-10-01：tick 不再做這個正規化，目標（原 `--node`、`--target`，現在是位置參數）怎麼認見下面 aos-tick 一節）

## 改動 3：`AOS_DIRNAME`（2026-10-01）

使用者 2026-10-01（[verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit/06-1001-互斥-狀態資料夾-user.md#aos_dirname-狀態資料夾的名字已寫入-speccommit-前由我補號)，待統一更新 spec）：環境變數 `AOS_DIRNAME` 決定狀態資料夾的名字，之後 aos 所有程式都照它。判斷只在 `lib/aos_dirname.py` 一處（`name()`、`error()`）。

- 三態（同日再改）：**沒設**＝`.aos`；**設了但空字串**＝不用子資料夾、直接用資料夾本身（`name()` 回 `""`）；其他值＝這個名字。含 `/`、或是 `.`、`..` 算不合法（空字串合法）。
- aos-exec：資料夾目標改成先找 `xxx/<名字>/inst.json`、再找 `xxx/inst.json`（`aos_exec_run._dir_targets()`；`DIR_TARGETS` 常數留著當預設名字的樣子）；空字串時只找 `xxx/inst.json`。名字不合法：資料夾目標算用法錯，~~照 aos-exec 現有的碼回 2~~ 回 1（改動 4）；`spawn_target` 丟 `SpawnFailed`。直接給檔、`.json` 目標不受影響。

## 改動 4：結束碼慣例，用法錯回 1（2026-10-01）

使用者 2026-10-01 改版的 aos 結束碼慣例（[verdicts 11 篇末](../../../notes/verdicts/11-tick-as-unit/04-1001-結束碼慣例.md#aos-結束碼慣例已寫入-speccommit-前由我補號)，待統一更新 spec）：0＝預料之中、非 0＝要額外處理、1＝通用錯誤，沒特別指定碼的錯都 1。aos-exec 的用法錯由 proto5 的 2 改 1（`aos_exec_run.EXIT_USAGE`；argparse 的用法錯也改回 1，見 `aos_exec._Parser`）。`run_target()` 回的 `(code, "usage")` 的 code 也是 1。

aos-exec 現在的碼：

| 狀況 | 回 |
|---|---|
| 子程式跑完一次：它的碼原樣（含 0、128+N、找不到程式 127、沒執行權 126） | 原碼 |
| aos-exec 自己失敗、那次沒跑（inst 壞、`.json` 不存在、mkdir／cwd／重導向失敗） | 125 |
| 用法錯（argv、`--timeout-ms` 負數、目標不存在、資料夾找不到 inst、inst 目標給 `--`、`AOS_DIRNAME` 不合法） | 1 |
| 沒接住的例外 | 1（Python 預設） |
| `-h`／`--help` | 0 |
