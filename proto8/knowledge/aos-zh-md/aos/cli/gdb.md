# `knowledge/aos/cli/gdb.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/gdb.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-gdb 與 aos.py：從 Python 操控一個在跑的 agent，條件成立時讓它停下，看一看，再繼續

`aos.py` 是 aos 給人用的 Python 介面（agent 不需要它：你用工具）。`aos-gdb NAME` 會打開 Python，`agent`、`daemon_ctl`、`std` 和 `defs` 都已備好（`from aos.py import agent, daemon_ctl, std`；`from aos.py.agent import defs`），還有 `a = agent.attach(NAME)`（`--daemon D`，或 `$AOS_DAEMON`）。沒有 NAME 時只備好那些模組。每次呼叫都會在 stderr 印出它背後的 aos 指令（`$ ...`）。

一條規則：`aos-agent --daemon D --target N X Y --flag v ARG` 就是 `agent.attach(N, daemon=D).X.Y(ARG, flag=v)`；一次呼叫剛好就是一個指令。`a.say("hi")` 傳回信的名字；`json=True` 會加上 `--json` 並傳回解析好的 JSON（JSON lines 變成一個 list，空的是 None）；否則你拿到原樣的 stdout（空的是 None）。`True` 是單獨的旗標，`False`/`None` 會把它省略，list 會重複那個旗標，結尾的 `_` 會被去掉（`from_=`）。`ctl add / rm / ls / set-def / who` 不收 `--target`：在模組上呼叫它們（`agent.ctl.ls()`）。`daemon_ctl.X(...)` 就是 `aos-daemon-ctl X ...`。唯一的錯誤是 `Failed`：指令自己的錯誤行，帶有 `e.code`、`e.argv`、`e.exit`。

`a` 底下的名字是 `aos-agent` 的子指令，再加上兩個只存在函式庫裡的擴充：`a.bp`（中斷點）和 `a.look`（讀 stack 的檔案：`where()`、`history(n)`、`observed(n)`、`request()`、`queue()`、`stderr(n)`、`file(rel)`）。其他任何名字都是 AttributeError。

中斷點的功能都繞著中斷點本身：add、rm、set、ls、get。`a.bp.add.<kind>(...)` 傳回中斷點物件：`b.id` 是它的號碼（從 1 起的 int；移除掉的號碼不會再用，重開 REPL 之後也不會：計數器在 agent 的 stack 裡，`gdb/next_id.json`），`b.kind` 是它的種類（before_tool、tool_error、watch、...），而 `a.bp.get(b)` 的其他每個欄位（`b.enabled`、`b.fired`、`b.here`、...）每次讀都會重新讀取；`a.bp.rm(b)` 之後讀欄位會失敗（`BreakpointGone`）。`rm`、`set` 和 `get` 收物件、號碼（`3` 或 `"3"`），或你用 `id="mine"` 取的名字（名字不能全是數字）。用 `a.bp.add.<kind>(...)` 加一個；種類有 hook 事件（before_tool、after_tool、before_queue、after_queue、brain_failed、tool_added、after_start、after_stop）、`tool_error` 和 `watch`。每個種類的形狀都一樣：一個可有可無的第一個參數（工具名；brain_failed 是錯誤代號；沒有名字的種類不收），接著是關鍵字 `sh=`、`py=`、`times=`、`once=`、`id=`、`replace=`（watch 還有 `every_ms=`、`also=`）。打 `a.bp.add` 會把它們列出來。

兩種中斷點，共用一排號碼。觸發器（trigger）是那個 agent 身上一個普通的 hook（名字是 `gdb_<id>`，號碼補零到 4 位，例如 `gdb_0003`，所以名字列出來和 hook 執行都照號碼順序；`b.id` 還是 `3`；處理程式 `lib/tools/agent/gdb_trigger`）。監看器（watcher，`a.bp.add.watch(...)`）是 daemon 表上一個獨立的 proc（名字 `gdbw_<id>`，例如 `gdbw_0004`），它看 agent 的檔案並讓它暫停；它的號碼取自它監看的每個 agent 的計數器，所以絕不會跟它們的觸發器撞號。

怎麼停取決於事件，不是選項：

- `before_tool`、`before_queue`（還沒發生）：觸發器把 agent **扣住**在它的 hook 裡。工具還沒跑；表上還是寫 running，這是故意的：aos-agent 和 daemon 不知道 gdb 的存在（保持解耦），所以要用 `a.bp.why()` / `a.bp.held()` 看中斷點造成的停止。`a.bp.resume()` 讓那個呼叫照原樣執行；從 shell 下 `aos-agent ctl resume` 也會讓它執行。沒有辦法在不執行工具的情況下放它走。
- 其他事件（`after_tool`、`brain_failed`、...）和監看器：`aos-agent ctl pause`；迴圈在目前這一步之後停下（after_tool：結果已在對話歷史裡，腦還沒看到）。`a.bp.resume()` 會送出 `ctl resume`。

三個控制，像除錯器那樣；每一個都會等到 agent 再次停下，然後顯示停在哪裡（第一行讀起來像 `stopped at breakpoint 1 (before_tool: write)`）。它們唯一的參數是 `wait=`（預設 True）。`wait=False` 會送出動作並立刻傳回一個物件：`p.is_done()` 說是否完成（停下了，或確定不會停），`p.wait()` 給出跟等待版呼叫一樣的結果（`Timeout` 之類的錯誤從這裡出來），`p.cancel()` 只是不再等：送出去的東西不會收回（某一步的暫停仍會在那一步結束時讓它停下），之後 `p.wait().outcome` 是 `cancelled`：

- `a.bp.resume()`：繼續。被扣住：讓那個呼叫執行。暫停中：`ctl resume`。沒停（剛 `a.say` 完）：什麼都不送，只等。
- `a.bp.step()`：走 fsm 的一步（idle、think、wait、act 其中一個；腦在想的時候，wait 會一再重跑）然後停。在工具之前被扣住：工具執行，在那個 act 步驟結束時停下。
- `a.bp.pause()`：現在就停，不靠中斷點（`ctl pause`）；已經停了 = 什麼都不送。

```python
b = a.bp.add.before_tool("write")                    # held before write runs; b.id == 1, b.kind == "before_tool"
a.bp.add.after_tool("write"); a.bp.add.tool_error(times=2)
a.bp.add.after_tool(sh="grep -q secret || exit 10")  # event JSON on stdin; exit 0 = hit, 10 = no hit
a.bp.add.before_tool(py=lambda ev: ev["arguments"].get("path", "").endswith(".env"), once=True)
a.bp.add.watch(py=lambda t: len(t.history(0)) > 20, every_ms=500)   # t = the target's files; t.mem = a dict kept between looks
a.bp.add.watch(also=["bob"], sh="test -f flag || exit 10", times=3)  # one watcher, two agents; cwd = each target's stack
a.say("hi"); a.bp.resume()                          # waits; "stopped at breakpoint 1 (before_tool: write)"
a.bp.why(); a.bp.held(); a.look.where(); a.look.history(3)
a.bp.step()                                          # write runs; stops when this step ends
a.bp.resume()                                        # go on, wait for the next stop
p = a.bp.resume(wait=False); p.is_done(); p.wait()   # do not wait; ask later; same result
b.fired                                              # read again every time
a.bp.ls(); a.bp.get(b); a.bp.set(b, enabled=False, times=3, once=True); a.bp.rm(b); a.bp.clear()
a.bp.pause()                                          # stop it now without a breakpoint
```

- `a.bp.set(b, ...)` 也傳回中斷點（跟 `add` 傳回的同一種物件；欄位每次都重新讀取）。
- `a.bp.get(b)` / `a.bp.ls()` 的列（號碼的在前，再來是名字的）：id、kind（加入時的種類；監看器是 watch）、how（hold 或 pause）、about、enabled、times、once、seen、fired、spent、last_error，以及 `here`（它現在正停在這一個）。`set` 只改 enabled、times 和 once；要改條件或事件，就用 `id=b, replace=True` 重新加一次（不是從 add 拿到的號碼不能自己挑）。
- 被扣住時：信照樣排進佇列；這段時間送來的 `ctl pause` 或 `ctl stop` 會在工具跑完之後才生效（`why()` 會這樣說）。`ctl sleep`、`rm` 或 daemon 關機會切斷扣住：工具沒跑，agent 回來時同一個呼叫會再次被扣住。移除或停用中斷點，不會結束已經扣在它上面的扣住。
- 監看器會慢一步（它們是輪詢）。`times` = 連續幾輪；停過一次之後，條件必須先被看到一次為假，才能再讓它停下；暫停中或被扣住的目標不檢查。壞掉的監看器條件會記在 `last_error`；死掉的監看器不會碰它的目標。
- 觸發器是一個普通的 hook，它的處理程式什麼都不印；條件或檔案壞掉時，它印一行警告並以 0 結束：agent 不會停也不會重啟。`why()` 列出上次 resume 以來的附註（`by`：hook、watch、repl、ctl）、它們是否屬於這次停止，以及 `.breakpoint` = 它停在哪個 id（`== b` 可以用）。
- 一直沒停時：閒著（stage idle、佇列裡沒東西、沒有暫停正在路上）達 `a.bp.idle_s` 秒（預設 1）= 呼叫傳回 "did not stop: it is idle"；它的迴圈程序不見了 = "did not stop: it is not running"。等待時，每 `a.bp.report_s` 秒在 stderr 印一行（預設 10，0 = 永不）。`a.bp.timeout_s`（預設 None = 不限）會讓它丟出 `Timeout`（既是 `Failed` 也是 `TimeoutError`）；這些是 `a.bp` 上的設定，不是參數（唯一的參數是 `wait=`；wait=False 時不印 stderr 那一行）。結果有 `.outcome`：stopped、idle、gone 或 interrupted。
- 等待時按 Ctrl-C 只停止等待：agent 繼續，不會留下任何東西（某一步送出、還沒生效的暫停會被收回）。`a.bp.pause()` 之後，暫停就維持送出的狀態。
- Python 條件在另一個程序裡跑：它們看得到 `json`、`re`、`os` 和內建函式；其他值用預設參數傳進去（`lambda ev, x=x: ...`）。用到外層變數或不認得的名字時，會立刻被拒絕。
- 當作參考的 hook 宣告（只在你要的時候）：`aos-gdb --hooks FILE`（可重複；一個 hooks.json：`{point id: {"input": JSON Schema, ...free keys}}`）或 `--def-hooks`（NAME 的定義在它的 interfaces.json 裡 `"hooks"` 底下列的那些檔案）。在 REPL 裡，`hooks` 會列出各個點、中斷點在每個點上怎麼停、主體（subject）和輸入欄位（`hooks.load(FILE)`、`hooks.load_def(a)`、`hooks.clear()`、`hooks.fields(id)`）。gdb 不認得的已宣告點會變成 `a.bp.add.<point>` 種類（它們用暫停）；宣告了 `"condition": "field"`（並以 `"subject"` 當參數名）時，第一個參數就是拿來跟它比對的。點沒有宣告，或 py 條件讀了沒宣告的欄位 `ev["x"]` 時，`a.bp.add` 會印一行警告但照樣加入。`a.bp.event()` 顯示觸發器停下時的整個事件，照宣告的格式排好。讀不了的檔案是一行警告；完全沒有宣告時，一切照舊運作。
- 除非有人叫你去除錯另一個 agent，否則不要在它身上下中斷點：那會讓那個 agent 停下（aos/rules.json）。更多：`aos-gdb --help`、REPL 裡的 `help(a.bp)` 和 `a.bp.add`、proto8/py/aos/apps/gdb/README.md。
