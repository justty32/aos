# aos-gdb — 在 Python REPL 裡對一隻已在跑的 agent 下斷點：條件成立就把它停下來，看完再續（庫本體 `aos.gdb`；第二版＝工具前真的停住＋外面的觀察者）

← [cmd](../../../docs/05-commands.md)｜庫：[py/aos/gdb](../../gdb/__init__.py)｜handler：[gdb_trigger](../../../tools/agent/gdb_trigger/_entry)｜觀察者本體：[gdb_watch](../../../tools/agent/gdb_watch/_entry)｜圖紙：[aos-gdb-1119](../../../../thinking/2026-11/19/aos-gdb-1119/README.md)、[第一版紀錄](../../../../thinking/2026-11/19/aos-gdb-lib-第一版.md)、[第二版紀錄](../../../../thinking/2026-11/19/aos-gdb-lib-第二版.md)

使用者 11-19 的定義：斷點＝「特定條件發生時，暫停loop或fsm，停下來等待檢閱」，「能把他停下來的都可以」，「hook不用動」；第二版：「stop_before_tool不就是在工具開始前停下嗎？丙可以繼續」。hook 機制、daemon、aos-agent 都沒改。

## 兩種停法（由事件決定，不是選項）

| 事件 | 停法 | 停在哪 | 續 |
|---|---|---|---|
| `before_tool`、`before_queue`（事件還沒發生） | **扣住**（hold）：觸發器的 hook handler 自己不回、等人放行 | 腦已決定叫工具、**工具還沒跑**（信還沒進 history） | `a.resume()`＝那次**照原樣跑**；`a.resume(skip=True)`＝那次工具不跑，腦收到一句「被跳過」（只有 before_tool）；shell 的 `aos-agent ctl resume` 也放行（照跑） |
| 其他（`after_tool`、`brain_failed`…，事件已經發生） | **暫停**（pause）：handler 叫 `aos-agent ctl pause --no-wait` | 那一格做完、下一格開頭（after_tool＝結果已進 history、腦還沒看到） | `a.resume()`＝`ctl resume` |
| 觀察者（另一支 proc） | 暫停：看到時 `ctl pause` 目標 | 晚一格（輪詢檔，約 every_ms＋一格） | 同上 |

扣住時要知道的（都實測過，見[第二版紀錄](../../../../thinking/2026-11/19/aos-gdb-lib-第二版.md)）：
- 表上照寫 `running`（它卡在 act 那一格裡，`stage.txt`＝act）；`a.is_paused()`、`a.why()`、`a.held()` 認得。信照收進信箱，續了再處理。
- 扣著時別人下 `ctl pause`：放行後工具照跑，這一格做完才停（`why()` 會說「then it pauses」）；`ctl stop` 一樣要等放行後才真的停（這段時間表上是 `stopping`，`ctl stop` 本身會一直等到它預設的 30 秒；要馬上停用 `ctl sleep`）。
- 扣著時 `ctl sleep`、`rm`、daemon 收工（都是 TERM）：那一格被收掉，**工具沒跑**，字條記 `hold_ended`；醒來重跑同一個工具呼叫時**直接再扣住**（不再判條件，`once` 也照扣），放行後只跑一次。
- 拿掉觸發器（`a.remove`）不影響正扣著的那一次。

## 最短試法（假腦）

```sh
cp -r $AOS_HOME/templates/start-api /tmp/t && cd /tmp/t && source env.sh
aos-exec root &                                   # 根
(cd llms && aos-exec --stack stacks/llm def &)    # llm kernel（假腦）
aos-agent -d .stack ctl add --auto-restart -w . agents/ann
aos-gdb -d .stack ann                              # 進 REPL：g＝aos.gdb、a＝ann
```

```
gdb> a.stop_before_tool("peek_now_time")        # fake brain calls peek_now_time on every message
gdb> a.say("hello"); a.wait_paused()
gdb> a.why()
ann is held at a breakpoint (trigger gdb_before_tool_1): tool peek_now_time has not run yet; a.resume() lets it go on as it was, a.resume(skip=True) skips that call
  ... hook gdb_before_tool_1: tool peek_now_time is about to run [held before it]
gdb> a.history(1)                                 # the call the brain asked for; no tool result yet
gdb> a.remove("before_tool_1"); a.resume(); a.listen()
FAKE ANSWER to: hello (tool said: 2026-...)       # the tool really ran
gdb> w = a.watch(py=lambda t: len(t.history(0)) > 6)   # another proc looks every 0.5 s
gdb> a.say("again"); a.wait_paused(); a.why()      # "ann is paused by watcher gdbw_w1"
gdb> a.unwatch(w); a.resume()
```

收樹：`aos-daemon-ctl -d .stack shutdown`、`aos-daemon-ctl -d llms/stacks/llm shutdown`（分兩句打）。

## 能做什麼

| 方法 | 背後是 | 說明 |
|---|---|---|
| `g.attach(name, daemon=None)` | `aos-agent ctl state --json who`、`hook ls` | daemon 預設 `$AOS_DAEMON`；定義沒宣告 hooks＝當場 `HooksMissing` |
| `a.stop_before_tool(tool=None, ...)` | `aos-agent hook add --event before_tool ...`（timeout 0、讀回話） | 某工具（不給＝任何工具）**要跑之前扣住** |
| `a.stop_after_tool(tool=None, ...)` | 同上，`after_tool`（`--no-intercept`） | 某工具跑完就停：結果已進 history，腦還沒看到 |
| `a.stop_on_tool_error(tool=None, ...)` | 同上，`after_tool` | 工具退出碼不是 0 或逾時；停的位置同 `stop_after_tool` |
| `a.stop_on_brain_failed(code=None)` | 同上，`brain_failed` | 問腦失敗（代號如 `BrainFailed`、`BudgetMissing`），那一格做完停 |
| `a.stop_when(event, tool=, sh=, py=, error=, times=1, once=False, name=, replace=False)` | 同上 | 通用形；停法照上表由 event 定。`sh`＝一段 shell（事件 JSON 在 stdin，退 0＝算、**退 10＝不算**、其他＝條件壞了，所以 `grep -q x \|\| exit 10`）；`py`＝函式 `f(event)` 或運算式字串（變數 `ev`），看得到 `json`、`re`、`os` 與內建，外層變數要當預設值傳；`times`＝連續幾次才算；`once`＝只停一次 |
| `a.triggers()`、`a.remove(name)`、`a.clear()` | `hook ls --json`／`hook rm gdb_NAME` | 只管 `gdb_` 開頭的 hook；`triggers()` 帶 how、看過幾次、連續幾次、停過幾次、`last_error` |
| `a.watch(py=, sh=, also=(), times=1, once=False, every_ms=500, name=, replace=False)`、`g.watch(targets, daemon=, ...)` | `aos-daemon-ctl add --name gdbw_<名> ...` | 起觀察者（下一節） |
| `a.watchers()`、`g.watchers(daemon)`、`a.unwatch(name)`、`g.unwatch(name, daemon)` | `aos-daemon-ctl ls -j`／`rm gdbw_<名>` | 列出（phase、pid、每個目標停過幾次、`last_error`）／拿掉（先停、等行程退出、再從表上拿掉） |
| `a.held()`、`a.is_paused()`、`a.wait_paused(timeout_s=30)` | 讀 `gdb/hold.json`（handler 活著才算）、`state.json` 的 `paused` | 停著＝暫停已套用或扣住；等的是真的停住，不是字條 |
| `a.why()` | 讀 `gdb/log.jsonl`、`gdb/hold.json`、`ctl.json` | 上次續之後的字條（觸發器 by `hook`、觀察者 by `watch`）；扣在哪、能不能 skip；扣住後又來的 ctl pause／stop；字條的 ctl seq 跟現在對不上＝之後有人在 shell 下過 ctl，會說字條可能是舊的 |
| `a.resume(skip=False, text=None)` | 扣住：寫 `gdb/release.json`；暫停：`ctl resume` | 扣住時等 handler 收到才回；`text`＝skip 時給腦的那句 |
| `a.where()`、`a.history(n)`、`a.observed(n)`、`a.request()`、`a.queue()`、`a.stderr(n)`、`a.file(rel)`、`a.state(*parts)`、`a.notes()` | 讀 stack 的檔／`aos-agent ctl state` | 停住時檢閱 |
| `a.say(text)`、`a.listen(timeout_s, letter=)`、`a.pause()`、`a.agent(*args)`、`g.sh(cmd)` | `aos-agent ...`、`sh -c` | `say` 回信名，交給 `listen(letter=...)` 等那一封的回答 |

每個方法先印出背後那條指令（`$ aos-agent ...`）；`g.echo = False` 關掉。不用 `aos-gdb` 也行：任何 `python3` 把 `$AOS_HOME/lib` 放上 `sys.path` 就能 `import aos.gdb`。

## 觀察者（丙）

一支掛在 daemon 表上的普通 proc（名字 `gdbw_` 開頭；就是一個 aos-loop，每圈跑一次 `lib/tools/agent/gdb_watch`），每隔 `every_ms` 看一次每個目標，條件成立就 `ctl pause` 目標、在目標的 `gdb/log.jsonl` 留字條（`by: watch`）。完全不碰目標的定義與 hook。

- **為什麼掛在表上、不是 REPL 外的背景程式**：REPL 關了照樣在；`aos-daemon-ctl ls` 看得到、`rm` 停得掉；daemon 收工一起睡、重起一起醒；它自己壞了＝表上那一列 stopped 帶原因，目標照跑。
- **條件**：`py`＝函式 `f(t)` 或運算式字串（變數 `t`）。`t` 是那個目標的檢閱物件（`t.name`、`t.stack`、`t.history(n)`、`t.observed(n)`、`t.where()`、`t.file(rel)`、`t.queue()`…），`t.mem` 是跨圈留著的 dict（存成 JSON），拿來看跨好幾格的事，例：

  ```python
  def new_tool_result(t):                 # only results that came after the last look
      h = t.history(0); seen = t.mem.get("n", len(h)); t.mem["n"] = len(h)
      return any(m.get("role") == "tool" for m in h[seen:])
  a.watch(py=new_tool_result, every_ms=200)
  ```
  `sh`＝cwd 是目標的 stack、環境有 `GDB_TARGET`、`GDB_STACK`；退 0＝算、退 10＝不算。py 條件 20 秒沒回＝壞了。
- **一個看好幾隻**：`g.watch(["ann", "bob"], sh=...)`（同一個 daemon），每隻各自數。
- **防誤報**：`times`＝連續幾圈都成立才停；停過一次之後要先看到一次不成立才會再停（不然一個一直成立的條件會在每次續了之後馬上又停）；目標停著（暫停或扣住）的那幾圈不判。
- **壞了不拖垮目標**：條件丟例外／sh 退 1＝那圈不算、`watchers()` 的 `last_error`、觀察者照跑；觀察者行程整個死掉＝表上那一列不是 running，目標照跑（實測）。
- **晚一格**：看到時事情已發生，停在下一格開頭；要「事前」停用觸發器（`stop_before_tool`）。

## 檔與防呆

- 觸發器：`<stack>/hooks/gdb_<名>/trigger.json`（`how` 由事件定）、`count.json`（`pending`＝扣住被打斷的那一次）；字條：`<stack>/gdb/log.jsonl`（只往後加；`by` 是 `hook`、`repl`、`ctl`、`watch`）；扣住時 `<stack>/gdb/hold.json`、放行單 `gdb/release.json`。
- 觀察者：`<daemon>/procs/gdbw_<名>/watch.json`、`watch_state.json`、`watch_loop.json`（交給 `aos-daemon-ctl add` 的那份；同夾的 `loop.json` 是 daemon 自己寫的）。
- 觸發器一律 `--on-error continue`：條件或 handler 壞了，agent 只多一行 warning，不會掛掉、不會被 daemon 連環重起。扣住型不限時（等人）；暫停型 15 秒（sh／py 條件 40 秒）、`--no-intercept`。
- 沒做：一包現成觸發器（丁）、`on_clock`、eca 身（claude、codex 當腦）上的扣住沒測（before_tool 在 aos-mcp 裡跑，扣太久 CLI 那邊可能自己逾時）。
