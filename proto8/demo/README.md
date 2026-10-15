# proto8/demo — daemon 跑一遍

← [proto8](../README.md)

一支腳本把 [daemon](../lib/README.md) 從起到收走一遍，每條控制指令和回覆都印出來。

```
python3 proto8/demo/run.py
```

從哪裡跑都行，約 8 秒。只用 Python 標準庫和 `sh`、`date`。

另一個 demo：**fsm**（`demo/fsm` 本身是一個 agent 定義資料夾：在暫存 frame 裡跑它的 loop.json，idle → thinking（內層 fsm：ask → review）→ tool → … → done，ask 照思考介面叫腦、tool 跑 inst 工具（其中 clerk＝另一個 agent）；預設假腦，換真 LLM＝`python3 proto8/demo/fsm/run.py brain/lmstudio.json`）——`python3 proto8/demo/run.py fsm`，說明在 [fsm/README.md](fsm/README.md)。

三個 agent 的 demo 都要 PATH 上有 `proto8/bin`（`aos`）與 `demo/bin`（[`aos-demo`](bin/aos-demo)：`aos-demo fsm/brain/fake.py`＝從 demo 資料夾算的腳本、其他指令照跑並多給 `AOS_DEMO`＝demo 資料夾）；各 `run.py` 自己會接上。

再一個：**畫家**（使用者 10-11 舉的例子：畫家 agent 透過工具叫畫筆 agent；看 frame 巢狀、同 frame 續聊、frame 放 brain.json 換腦）——`python3 proto8/demo/paint/run.py [腦設定.json]`，說明在 [paint/README.md](paint/README.md)。

再一個：**LLM kernel**（daemon 底下的 loop 每拍跑 kernel；呼叫者經閘門叫同一顆睡 1 秒的假腦：low 最後、deadline 快到插隊、過期丟掉、aging、報時員巢狀只包腦一格就夠）——`python3 proto8/demo/run.py kernel`，說明在 [lib kernel.md](../lib/kernel.md)、腳本 `kernel/run.py` 檔頭。

再一個：**通用 kernel**（判官是一張 inst；假腦 llm、假 cpu 活、問人 human 三種同時搶，格數 1／2／1；第二段判官壞掉→每次都退回規則（kernel 不數連錯））——`python3 proto8/demo/run.py kernel2`，說明在 [lib kernel2.md](../lib/kernel2.md)、腳本 `kernel2/run.py` 檔頭；agent 判官（LM Studio）`python3 proto8/demo/kernel2/run.py judge-agent.json`。

## 裡面有什麼

- `once/inst.json`：跑一次就結束，印一行、結束碼 3。`once/loop.json` 用 `$ref` 指它（跑 1 次）。
- `tick/inst.json`：每跑一次往 `tick.out` 追加一行時間、往 `tick.exit` 追加一行結束碼。`tick/loop.json` 用 `$ref` 指它，外層寫 5 次、每次隔 1 秒。
- `daemon.json`：daemon 的 config。`control_dir` 寫成 `{"$env": "DEMO_CTL"}`，自己的 ctl／state 窗（必填，N-19）也用 `$env` 指到暫存資料夾；daemon 替兩個 loop 放的 ctl、state 窗與它們的 stderr（`err.json`；stdout 丟掉，結果看 state 窗）在暫存資料夾的 `loops/N/` 底下；daemon 沒 inst，自己的 stdout 只在收工時吐一份總結（直接印在畫面上）。
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
