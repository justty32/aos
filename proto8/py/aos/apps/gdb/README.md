# aos-gdb — 在 Python REPL 裡對一隻已在跑的 agent 下「條件觸發器」：條件成立就把它停下來，看完再續（庫本體 `aos.gdb`，第一版＝乙案）

← [cmd](../../../docs/05-commands.md)｜庫：[py/aos/gdb](../../gdb/__init__.py)｜handler：[gdb_trigger](../../../tools/agent/gdb_trigger/_entry)｜圖紙：[aos-gdb-1119](../../../../thinking/2026-11/19/aos-gdb-1119/README.md)、[Argon 審與採納](../../../../thinking/2026-11/19/aos-gdb-1119/08-Argon審與採納.md)、[第一版紀錄](../../../../thinking/2026-11/19/aos-gdb-lib-第一版.md)

使用者 11-19 的定義：斷點＝「特定條件發生時，暫停loop或fsm，停下來等待檢閱」，條件主要由 hook 承載、「hook不用動」。所以觸發器就是一個普通 hook：handler 一律是 `lib/tools/agent/gdb_trigger`，它判條件，成立就叫 `aos-agent ctl pause --no-wait` 並在 stack 留一張字條（誰、為了什麼停）。hook 機制、daemon、aos-agent 都沒改。

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
ann is paused by a trigger
  2026-11-19T09:33:58.756+08:00 hook gdb_before_tool_1: tool peek_now_time is about to run
      name="peek_now_time" arguments={}
gdb> a.where(); a.history(2)                      # 'think'; the tool call and its result
gdb> a.remove("before_tool_1"); a.resume(); a.listen()
FAKE ANSWER to: hello (tool said: ...)
```

收樹：`aos-daemon-ctl -d .stack shutdown`、`aos-daemon-ctl -d llms/stacks/llm shutdown`（分兩句打）。

## 能做什麼

| 方法 | 背後是 | 說明 |
|---|---|---|
| `g.attach(name, daemon=None)` | `aos-agent ctl state --json who`、`hook ls` | daemon 預設 `$AOS_DAEMON`；定義沒宣告 hooks＝當場 `HooksMissing` |
| `a.stop_before_tool(tool=None, block=False, ...)` | `aos-agent hook add --event before_tool ...` | 某工具（不給＝任何工具）要被叫；**這一格做完才停**（那次工具照跑）。`block=True`＝停的那一次不讓它跑，腦收到「被 hook 擋下」 |
| `a.stop_on_tool_error(tool=None, ...)` | 同上，`after_tool` | 工具退出碼不是 0 或逾時（看 agent-fsm 交給 hook 的 `code`／`timed_out`）；不指名＝後來才加的工具也算 |
| `a.stop_on_brain_failed(code=None)` | 同上，`brain_failed` | 問腦失敗（代號如 `BrainFailed`、`BudgetMissing`） |
| `a.stop_when(event, tool=, sh=, py=, error=, times=1, once=False, block=False, name=, replace=False)` | 同上 | 通用形。`sh`＝一段 shell（事件 JSON 在 stdin，退 0＝算、退 10＝不算、其他＝條件壞了）；`py`＝函式 `f(event)` 或運算式字串（變數 `ev`），看得到 `json`、`re`、`os` 與內建，外層變數要當預設值傳（`lambda ev, x=x: ...`）；`times`＝連續幾次才算（中間別的工具的同類事件會歸零）；`once`＝只停一次 |
| `a.triggers()`、`a.remove(name)`、`a.clear()` | `hook ls --json`／`hook rm gdb_NAME` | 只管 `gdb_` 開頭的 hook；`triggers()` 帶看過幾次、連續幾次、停過幾次、條件最後一次壞掉的原因 |
| `a.is_paused()`、`a.wait_paused(timeout_s=30)` | 讀 `state.json` 的 `paused` | 等的是 loop 真的停住，不是字條出現 |
| `a.why()` | 讀 `gdb/log.jsonl`、`ctl.json` | 上次 `a.resume()` 之後的字條；最後一張的 ctl seq 跟現在的對不上＝之後有人在 shell 下過 ctl，會說字條可能是舊的 |
| `a.where()`、`a.history(n)`、`a.observed(n)`、`a.request()`、`a.queue()`、`a.stderr(n)`、`a.file(rel)`、`a.state(*parts)`、`a.notes()` | 讀 stack 的檔／`aos-agent ctl state` | 停住時檢閱 |
| `a.say(text)`、`a.listen()`、`a.pause()`、`a.resume()`、`a.agent(*args)`、`g.sh(cmd)` | `aos-agent ...`、`sh -c` | `resume()` 成功後在字條記一筆 resume；`a.agent("tools", "add", ...)` 可以停著時加東西（邊跑邊長） |

每個方法先印出背後那條指令（`$ aos-agent ...`）；`g.echo = False` 關掉。觸發器掛在 agent 的 stack，REPL 關了照樣在；停住的那隻用 shell `aos-agent ctl resume` 也續得了。不用 `aos-gdb` 也行：任何 `python3` 把 `$AOS_HOME/lib` 放上 `sys.path` 就能 `import aos.gdb`。

## 檔與防呆

- 設定：`<stack>/hooks/gdb_<名>/trigger.json`；計數：同夾 `count.json`；字條：`<stack>/gdb/log.jsonl`（只往後加；`by` 是 `hook` 或 `repl`，將來外面的觀察者寫 `watch`）。
- 掛的時候一律 `--on-error continue`、`--no-intercept`（`block` 的才開 intercept）、逾時 15 秒（sh／py 條件 40 秒）：條件或 handler 壞了，agent 只多一行 warning，不會掛掉、不會被 daemon 連環重起。
- `times == 1` 且有指名工具時，工具名交給 hook 的 condition 篩（別的工具不起行程）；`times > 1` 時由 handler 自己篩，才數得出「連著」。
- 沒做：外面的觀察者（丙）、一包現成觸發器（丁）、`on_clock`、擋信（`before_queue` 的 block）。
