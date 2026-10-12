# proto8/demo — daemon 跑一遍

← [proto8](../README.md)

一支腳本把 [daemon](../lib/README.md) 從起到收走一遍，每條控制指令和回覆都印出來。

```
python3 proto8/demo/run.py
```

從哪裡跑都行，約 8 秒。只用 Python 標準庫和 `sh`、`date`。

## 裡面有什麼

- `once/inst.json`：跑一次就結束，印一行、結束碼 3。
- `tick/inst.json`：每跑一次往 `tick.out` 追加一行時間、往 `tick.exit` 追加一行結束碼。
- `daemon.json`：daemon 的 config。`control_dir` 寫成 `{"$env": "DEMO_CTL"}`。
- `run.py`：用 mktemp 建一個暫存資料夾，裡面 `ctl/` 當控制資料夾、`out/` 放子程式的輸出（inst.json 的 `cwd` 寫成 `{"$env": "DEMO_OUT"}`）。指令裡的 `id` 寫絕對路徑（印的時候把本資料夾的路徑省掉）。跑完整個暫存資料夾刪掉，repo 裡不留東西。

## 它做了什麼

1. 起 daemon。
2. `add` once（預設跑 1 次）、`add` tick（`how`：5 次、每次隔 1 秒）。
3. `list`、`state`：once 已經 done，tick 跑了兩次。
4. `pause` tick，等 2.5 秒：`tick.out` 沒有變長，state 是 paused。
5. `add_times` +2、`resume`，等 2.5 秒，`get`：runs 往上加了。
6. `remove` tick，再問它的 state：NotFound。
7. 兩條錯的指令：不認得的 op（UnknownOp）、不是 JSON（BadCommand）。
8. 送 SIGTERM，daemon 收掉剩下的實例、退出碼 0。最後印出 `out/` 裡的四個檔。

每條指令寫成 `NN-op.json`（先寫 `.` 開頭的檔再改名，daemon 不會讀到寫一半的），等 `NN-op.json.done` 出現就讀回覆、刪掉。

## 會看到什麼

```
[ 0.2s] → 02-add.json  {"op": "add", "id": "tick", "how": {"times": 5, "interval_ms": 1000}}
[ 0.2s]      ok   "tick/inst.json"
[ 1.8s] → 03-list.json  {"op": "list"}
[ 1.8s]      ok   {... "id": "once/inst.json", "state": "done", "runs": 1, ...}
[ 1.8s]      ok   {"id": "tick/inst.json", "state": "waiting", "times": 3, ..., "runs": 2, ...}
[ 4.5s]    tick.out：暫停時 2 行，2.5 秒後 2 行
[ 8.0s] → 12-jump.json  {"op": "jump", "id": "once"}
[ 8.0s]      錯   UnknownOp: 不認得的 op 'jump'
[ 8.2s] out/tick.out  13:57:40 13:57:41 13:57:45 13:57:46 13:57:47
[ 8.2s] out/tick.exit 0 0 0 0 0
```

左邊是從開始算的秒數；`→` 那行是送出去的指令，下一行是回覆（`ok` 後面是 result，`錯` 後面是 error 的代號和白話）。路徑裡 demo 資料夾那段省掉了。`tick.out` 中間那段空檔就是暫停。
