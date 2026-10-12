# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫。

## 指示詞 lib（`aos_directives.py`）

讓 JSON 裡某一格的值「從別處來」。一個檔、一個入口：

```python
from aos_directives import resolve, DirectiveError
out = resolve(doc, base_dir)   # doc＝parse 好的 JSON；base_dir＝相對檔名的基準路徑
                               # 選填 ident＝doc 從哪來（檔案的 realpath），錯誤訊息用它指出是哪份檔
```

整份 JSON 一層層全部解掉，回一份新的（原本那份不動）。`base_dir` 整趟都用它，進了別的檔也不換。

兩種指示詞（兩個都寫了只看 `$ref`，其餘 key 忽略）：

```jsonc
{"$ref": "other.json#/a/0"}          // 讀一份 JSON 的某一格；"" 是目前這份；位置也可寫成 "$at": "/a/0"
{"$ref": "#../x"}                    // ./ ../ 從這個指示詞所在的位置算
{"$env": "HOME"}                     // 讀環境變數
```

取回來的東西裡如果還有指示詞，照它所在的那份檔、那個位置接著解。繞回自己（指到正在解的位置或它的上層）＝`ReferenceCycle`。
錯了一律丟 `DirectiveError`，代號七種，寫在檔頭。

## inst（`aos_inst.py`）

讀一份 JSON → 用指示詞 lib 解好 → 挑認得的 key（其他忽略）→ 跑一次。

```
python3 proto8/lib/aos_inst.py TARGET
```

- TARGET：`.json` 檔，或資料夾（找 `.aos/inst.json`，沒有再找 `inst.json`）。`find()` 回 realpath，同一份檔永遠得到同一個字串（daemon 拿它當 id）。
- 基準一律是呼叫者的 cwd：指示詞的檔名、`cwd` 這個 key 從這裡算。
- `cwd` 沒寫＝呼叫 aos_inst 時的 cwd；`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算。
- key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`，加上布林的 `cwd_mkdir`、`envs_clear`、`*_inherit`、`*_append`、`*_mkdir`、`stderr_merge`。完整說明在檔頭。
- 理念：aos_inst 跑起來就「變成」那個子程式。JSON 只寫跟呼叫者不一樣的地方，其他從 aos_inst 繼承——子程式留在 aos_inst 的行程群組與 session。限時、清孫程式由啟動 aos_inst 的人決定（例如 `timeout -k 2 5 aos_inst.py x`）。
- `run(inst, timeout_ms=None, grace_ms=2000, forward_signals=False, stop=None, stop_poll_ms=50, new_session=False)`：只有非在 run() 裡做不可的事才當參數——限時、停止鈕（`stop`，例如 threading.Event，別的執行緒按下去就收掉子程式；`stop_poll_ms` 幾毫秒看一次）、把收到的訊號轉給子程式。收掉＝SIGTERM，過 grace 再 SIGKILL。命令列就是 `run(..., forward_signals=True)`：收到 SIGINT／SIGTERM／SIGHUP 自己不死，轉給子程式，照樣等它結束、寫 exit。`new_session=True`（kill_leftover，給 daemon 用）：子程式自成一個 session／群組，訊號整群送，收掉或自己結束都對整群補 SIGKILL，孫程式一起清（自己 setsid 出去的清不到）；子程式沒有控制終端，所以命令列不開。
- 結束碼：自己結束＝子程式的碼，被訊號停掉＝128＋訊號號碼。`run()` 回它、`exit` 檔寫它（十進位＋換行；沒起來不寫；寫不進去不管）、**命令列的退出碼也是它**（aos_inst 變成子程式）。
- aos_inst 自己出錯、子程式沒跑：`run()` 丟 `InstError`；命令列照 Unix 包裝程式（env、timeout）的慣例回 **127＝找不到程式、126＝不能執行、125＝其他**（`exit_code(err)`），stderr 一行「代號: 白話」。所以子程式自己最好只用 1～123：124 以上都有慣例意思（124＝timeout 指令的時間到、125～127 如上、128＋N＝被訊號 N 停掉、255＝超出範圍）。
- API：`load(target)`、`parse(doc, base_dir, ident="<input>")`（ident＝錯誤訊息裡的檔名，load 給 inst.json 的 realpath）、`run(inst, ...)`（回子程式的結束碼，同 exit 檔那個數；出錯丟 `InstError`）、`exit_code(err)`。


## loop（`aos_loop.py`）

daemon 的 lib，不碰檔案。一張實例表，每個實例自己一條執行緒，照執行方式一次次呼叫 `aos_inst.run()`：等暫停解除 → 重讀 inst.json、跑一次 → 剩餘次數減一 → 等間隔 → 再來。

```python
from aos_loop import Loop, LoopError
loop = Loop(stop_poll_ms=50, error_wait_ms=1000)
loop.add("/srv/job", {"times": 3, "interval_ms": 1000})      # 回 id＝inst.json 的 realpath
loop.pause("/srv/job/inst.json", wait=False)                 # id 要是絕對路徑；wait=False＝當場收掉這次
```

- 方法：`add(id, how)`、`set(id, how)`、`remove(id, wait)`、`pause(id, wait)`、`resume(id)`、`add_times(id, delta)`、`state(id)`、`get(id)`、`list()`、`snapshot()`／`restore(items)`（daemon 的 save／load 用）、`shutdown()`；出錯丟 `LoopError`。`id` 要是絕對路徑（inst.json 或它所在的資料夾；相對＝`FieldType`），一律先用 `aos_inst.find()` 轉成 realpath。
- 執行方式 `how`：`times`（預設 1，None＝不限）、`interval_ms`（預設 0）、`timeout_ms`（預設不限）、`grace_ms`（預設 2000）。
- run() 一律 `new_session=True`：每次跑自成一群，收掉或跑完都連孫程式一起清。
- aos_inst 自己出錯（子程式沒跑，記進 `last_error`）的那次，下一次至少隔 `error_wait_ms`（`Loop(stop_poll_ms=50, error_wait_ms=1000)`），免得 inst.json 壞了又不限次數時空轉。
- set／resume／add_times 回改完的狀態物件；pause／remove 回 `ready()`：還沒停回 None，停了回狀態物件。
- 狀態：`state`（waiting／running／paused／done／removing）、剩餘 `times`、`runs`、`last_code`（上一次子程式的結束碼；還沒跑過或子程式沒跑＝null）、`last_error`。被收掉的那次也算一次；次數跑完留在表上（done），加次數再跑。

## daemon（`aos_daemon.py`）

```
python3 proto8/lib/aos_daemon.py CONFIG
```

- CONFIG（JSON，先解指示詞，基準＝啟動時的 cwd）：`control_dir`（必填）、`control_poll_ms`（預設 200）、`stop_poll_ms`（預設 50）、`load`（選填：起來後先 load 這個檔，失敗＝起不來）、`save`（選填：收到 SIGTERM 結束前先 save 到這個檔，SIGINT 不存；存不了退出碼 1）。
- 控制：往 `control_dir` 放 `名字.json`；daemon 每輪照檔名順序讀進來、交給 loop，處理完改成 `名字.json.done`，內容是一問一答：`{"request": 原指令, "ok": true, "result": …}` 或 `{"request": …, "ok": false, "error": {"code", "msg"}}`。不合法的 JSON 也當場變 `.done`（回 `BadCommand`）。怎麼寫不規定，但寫到一半被讀到＝BadCommand，寫的人自己負責；`.` 開頭的檔不讀。兩邊都不 fsync；`.done` 由讀回覆的人清。
- 指令一律 `{"op", "id", ...}`，`id` 要是絕對路徑：`add`（result＝id）／`set`（`how`）、`remove`／`pause`（`wait` 預設 true）、`resume`、`add_times`（`delta`）、`state`（result＝狀態字串）、`get`、`list`（result＝陣列）、`save`／`load`（`path`）；set／remove／pause／resume／add_times／get 的 result＝狀態物件。**pause／remove 等子程式真的停了才回**（remove 回最後的狀態，state＝`removed`）；這段時間指令檔留在原地，回了之後再 add 同一個 id 不會撞到 Exists。
- 實例表只在記憶體，起來時是空的。`save` 把現有實例（id、how 含剩餘次數、paused、runs、last_code、last_error）存成一份 JSON；`load` 從這種檔一次載入、開始跑，全有全無（某個 inst.json 不在、某個 id 已在表上、格式不對……任何一點不對就回 error，一個都不載）。跑到一半的那次不存，load 回來會重跑。收到 SIGINT／SIGTERM 就把所有實例當場收掉再結束（SIGTERM 且有 config `save` 才先存）。
- 跑起來之後出意外不結束，往 stderr 印一行（同一件事印一次）：控制資料夾看不了（`ScanFailed`，不建回來）、回覆寫不了（`ReplyFailed`：改把指令改名成 `.done`；改名也不行就放著不管、之後不再讀它）、指令處理出了沒料到的錯（error.code＝`Internal`）。實例那邊沒料到的錯記進 `last_error`，照常繼續。

## 測試（`tests/`）

```
python3 -m unittest discover -s proto8/lib/tests
```

只用標準庫，約 3 秒。一個檔 `test_lib.py` 分四組，daemon 那組起真的 daemon 行程、走控制資料夾；每個測試用 mktemp 的暫存資料夾，跑完刪掉。改 lib 就跑一次，新行為補一個測試。

## 多執行緒的規矩

loop 一個實例一條執行緒，子程式都從這些執行緒裡起。fork 只複製呼叫它的那條執行緒，別條握著的鎖在子行程裡永遠打不開——只要 fork 到 exec 之間不跑 Python 程式碼就沒事。所以：

1. 起子程式只用 `subprocess.Popen`，不用 `os.fork()`。
2. 不用 `preexec_fn`（它在 fork 與 exec 之間跑 Python）。
3. daemon 裡不 `chdir`、不改 `os.environ`（整個行程共用）；cwd、環境變數一律經 `Popen(cwd=, env=)` 只給子程式。
4. 換使用者身分用 Popen 的 `user=`、`group=`、`extra_groups=`，不在 `preexec_fn` 裡 `setuid`。
