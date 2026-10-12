# proto8/demo — daemon 跑一遍

← [proto8](../README.md)

一支腳本把 [daemon](../lib/README.md) 從起到收走一遍，每條控制指令和回覆都印出來。

```
python3 proto8/demo/run.py
```

從哪裡跑都行，約 8 秒。只用 Python 標準庫和 `sh`、`date`。

## 裡面有什麼

- `once/inst.json`：跑一次就結束，印一行、結束碼 3。`once/loop.json` 用 `$ref` 指它（跑 1 次）。
- `tick/inst.json`：每跑一次往 `tick.out` 追加一行時間、往 `tick.exit` 追加一行結束碼。`tick/loop.json` 用 `$ref` 指它，外層寫 5 次、每次隔 1 秒。
- `daemon.json`：daemon 的 config。`control_dir` 寫成 `{"$env": "DEMO_CTL"}`；daemon 替兩個 loop 生的包裝檔（ctl.json、state.json）在暫存資料夾的 `loops/` 底下。
- `run.py`：用 mktemp 建一個暫存資料夾，裡面 `ctl/` 當控制資料夾、`out/` 放子程式的輸出（inst.json 的 `cwd` 寫成 `{"$env": "DEMO_OUT"}`）。指令裡的 `id` 寫絕對路徑（印的時候把本資料夾的路徑省掉）。跑完整個暫存資料夾刪掉，repo 裡不留東西。

## 它做了什麼

1. 起 daemon。
2. `add` once、`add` tick（id 是 loop.json；次數、間隔寫在檔裡，不在指令裡）。每個 loop 是 daemon 起的一支 `aos_loop.py`。
3. `list`、`state`：once 已經 done（last_code 3，讀它的 exit 檔），tick 跑了兩次。
4. `pause` tick（daemon 改它的 ctl.json，等它讀到、停了才回），等 2.5 秒：`tick.out` 沒有變長，state 是 paused。
5. `add_times` +2（總數 5→7）、`resume`，等 2.5 秒，`get`：runs 往上加了。
6. `remove` tick（等這次跑完、行程結束才回，state＝stopped），再問它的 state：NotFound。
7. 兩條錯的指令：不認得的 op（UnknownOp）、不是 JSON（BadCommand）。
8. 送 SIGTERM，daemon 對剩下的 loop 送 SIGTERM、收掉，退出碼 0。最後印出 `out/` 裡的四個檔。

每條指令寫成 `NN-op.json`（先寫 `.` 開頭的檔再改名，daemon 不會讀到寫一半的），等 `NN-op.json.done` 出現就讀回覆、刪掉。

## 會看到什麼

```
[ 0.2s] → 02-add.json  {"op": "add", "id": "tick/loop.json"}
[ 0.2s]      ok   "tick/loop.json"
[ 1.8s] → 03-list.json  {"op": "list"}
[ 1.8s]      ok   {"id": "once/loop.json", "state": "done", ..., "runs": 1, "skipped": 0, "last_code": 3, ...}
[ 1.8s]      ok   {"id": "tick/loop.json", "state": "waiting", ..., "times": 5, ..., "runs": 2, ...}
[ 4.6s]    tick.out：暫停時 2 行，2.5 秒後 2 行
[ 8.3s] → 12-jump.json  {"op": "jump", "id": "once/loop.json"}
[ 8.3s]      錯   UnknownOp: 不認得的 op 'jump'
[ 8.5s] out/tick.out  22:49:56 22:49:57 22:50:01 22:50:02 22:50:03
[ 8.5s] out/tick.exit 0 0 0 0 0
```

左邊是從開始算的秒數；`→` 那行是送出去的指令，下一行是回覆（`ok` 後面是 result，`錯` 後面是 error 的代號和白話）。路徑裡 demo 資料夾那段省掉了。`tick.out` 中間那段空檔就是暫停。
