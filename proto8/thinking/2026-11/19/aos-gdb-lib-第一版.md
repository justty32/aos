# aos-gdb 第一版（乙案，11-19）：`aos-gdb NAME` 開一個接上 agent 的 Python REPL，`aos.gdb` 庫下條件觸發器（一個普通 hook：條件成立就 ctl pause 並留字條）、看為什麼停、檢閱、續；hook 機制與 cpp 都沒動，假腦實跑 6 個情境過

← [2026-11-19](README.md)｜調查：[aos-gdb-1119](aos-gdb-1119/README.md)｜Argon 審：[08-Argon審與採納](aos-gdb-1119/08-Argon審與採納.md)｜用法：[py/aos/apps/gdb/README](../../../py/aos/apps/gdb/README.md)

線 `aosgdb-lib-1119`。使用者原話：「等aos gdb差不多了之後，就要來做相關的下斷點(觸發器)的py lib了」；開發體驗「先用python產出一份粗定義，然後進入python repl，用aos-gdb庫，下斷點，然後跑」；斷點＝「特定條件發生時，暫停loop或fsm，停下來等待檢閱」，條件主要由 hook 承載、「hook不用動」。

## 先講結論

1. **做好了，你可以在 REPL 裡試。** `aos-gdb -d .stack ann` 進去就有 `a`（那隻 agent）：`a.stop_before_tool("write")`、`a.stop_on_tool_error(times=2)`、`a.stop_when("after_tool", sh=...)`／`py=lambda ev: ...`，然後 `a.say(...)`、`a.wait_paused()`、`a.why()`、`a.where()`、`a.history()`、`a.resume()`。最短試法在[用法頁](../../../py/aos/apps/gdb/README.md)。
2. **觸發器就是一個普通 hook。** handler 一律是新的 `lib/tools/agent/gdb_trigger`：讀自己小格的設定、判條件，成立就叫 `aos-agent ctl pause --no-wait`，再往 `<stack>/gdb/log.jsonl` 加一張字條（哪個觸發器、什麼事件、工具名與參數、ctl seq）。hook 機制、daemon、aos-agent 一個字都沒改。
3. **停在哪**：照 07 實測，pause 是「這一格做完才停」——`before_tool` 觸發時那次工具照跑，停在下一格（think）開頭。要「工具還沒跑就攔住」給 `block=True`：停的那一次 handler 退 10，那個工具不跑、腦收到「被 hook 擋下」。
4. **防呆**：條件或 handler 壞了，agent 只多一行 warning，不停、不掛、不連環重起（掛的時候一律 `on_error: continue`、不讀回話）；「連續 N 次」是連著的 N 個同類事件，中間別的工具會歸零；Python 條件用到外層變數或不認得的名字，下斷點那一刻就拒。
5. **Argon 審到了**，沒有一條推翻先乙或你的定義；照它改了五件、多收一件（block），沒收的四件寫了理由（[08](aos-gdb-1119/08-Argon審與採納.md)）。

## 檔

| 檔 | 是什麼 |
|---|---|
| `py/aos/gdb/__init__.py` | 庫本體：`attach`、`Agent`（下／列／拿掉觸發器、`is_paused`、`wait_paused`、`why`、`say`、`listen`、`pause`、`resume`、萬用 `agent(*args)`） |
| `py/aos/gdb/trigger.py` | 庫與 handler 共用：`trigger.json` 的形狀、條件怎麼判、連續次數、Python 條件的打包與檢查、字條讀寫 |
| `py/aos/gdb/look.py` | 檢閱薄殼（`where`、`history`、`observed`、`request`、`queue`、`stderr`、`file`、`state`、`notes`）、跑指令、`why()` 的顯示 |
| `py/tools/agent/gdb_trigger/_entry` | hook handler（不是給腦的工具） |
| `py/aos/apps/gdb/`、`py/entries.json` 一行 | `aos-gdb` 指令：接上一隻、開 `code.interact` 的 REPL（提示字 `gdb> `） |
| `py/tests/apps/gdb/test_gdb_trigger.py` | 不起 daemon：15 個（計數、篩法、sh／py、handler 用假 aos-agent） |
| `py/tests/apps/gdb/test_gdb_live.py` | 抄一棵 start-api 樹、假腦實跑：6 個 |
| `knowledge/aos/cli/gdb.json`＋`cli/_index.json` 一列、`py/docs/05-commands.md` 一列、`wf/tools/index_gen_desc.json` 四列 | 給 agent 與人查 |

stack 裡多出來的（都是這隻自己的、用的時候才建）：`hooks.json` 裡 `gdb_` 開頭的格（經 `aos-agent hook add` 寫）、`hooks/gdb_<名>/trigger.json`、`count.json`、`gdb/log.jsonl`。

## 測試（公司 WSL，`git archive` 的乾淨複本裝好後跑，暫存在 `~/.aos/scratch/aosgdb-lib-1119/`）

- `test_gdb_live.py` 6 個全過（約 45 秒）：
  1. 停→看→續：`stop_before_tool("peek_now_time")`、say → 停住，`why()` 說「paused by a trigger」、字條有工具名，`where()`＝think、history 最後一則是工具結果（那次工具跑了），resume 後答完。
  2. `block=True, once=True`：工具沒跑（history 是被擋的字樣），觸發器顯示 spent；續了答完，再問一次不再停。
  3. 工具連錯兩次才停：第一次錯照答、不停，第二次停，字條有 `math`、code 1。
  4. 條件壞了（Python 丟 KeyError、shell 退 3）：照答完、沒停，表上 running、沒有 reason，`triggers()` 有 `last_error`。
  5. 在 shell `ctl resume` 再 `ctl pause`：`why()` 認得字條是舊的（「may be old」）。
  6. 同一個事件兩個觸發器都成立：兩張字條都在、不互蓋。
- `test_gdb_trigger.py` 15 個全過；順手跑了既有的 `test_install`、`templates/tests/test_paths_move`、`test_hooks_engine`、`apps/agent/test_hook`，全過。
- `aos-gdb` 本身：把幾行餵進它的 stdin 跑過一輪（下觸發器、say、listen、why、clear）；不給名字＝`ArgumentsBad`、名字不在表上＝`AttachFailed`，`--help` 是英文。

## 要重建什麼

新檔與一行 `entries.json`；任何一棵樹要有 `aos-gdb`，在那份 proto8 重跑 `python3 install.py`（活樹 `~/aos-home` 這條線沒碰、沒裝）。持久格式沒改。

## 沒做的

- **丙（外面的觀察者 proc）**：任務書說這版不做。介面留好了：字條是一份只往後加的檔、每張帶 `by`（觀察者寫 `watch`），`why()` 不管是誰寫的都讀；檢閱方法在 `aos.gdb.look.Look`，觀察者的條件函式可以直接拿同一個物件。
- **丁（一包現成觸發器）、只記不停**：Argon 建議砍，照砍；等用過乙、丙再看哪些值得收。
- `on_clock` 觸發器、擋信（`before_queue` 的 block：擋了那封信就不收了）。
- 沒測「停著時加一個新工具、續了被不指名的觸發器攔到」：要另寫劇本腦；照 hook 的篩法推想會成立。
- eca 身（claude、codex 當腦）只攔得到經 aos-mcp 的 aos 工具（調查稿 04 第 13 條），沒另測。

## 要你拍板的（不急，試過再說）

1. **`stop_before_tool` 預設要不要直接擋下那一次工具？**
   - a（現在）：預設不擋，那次工具照跑、這一格做完才停；要事前攔住自己給 `block=True`。好處是不改 agent 的行為，停下來看到的就是它真的做了什麼。
   - b：預設擋。好處是「工具要被叫之前」名副其實；代價是每次停腦都會收到一句「被 hook 擋下」，續了之後它可能換個做法，跟沒下斷點時走的路不一樣。
2. **丙（外面的觀察者）要不要接著做？** 任務書說這版不做。要做的話，是新開一條線（照規矩要你點頭）。
