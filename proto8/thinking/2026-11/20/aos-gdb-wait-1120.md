aos-gdb 施工紀錄（線 aos-gdb-wait-1120）：照使用者 11-20 選項框八點改 a.bp——resume／step／pause 加 wait=（不等回可查的物件 is_done()）、斷點 id 改純數字不重用、add 回斷點物件；做了什麼、施工線自己定的細節、驗收輸出、使用者怎麼試。

← [2026-11-20](README.md)｜問答與裁定：[aos-gdb-問答-1120](aos-gdb-問答-1120.md)｜庫的說明：[apps/gdb/README](../../../py/aos/apps/gdb/README.md)｜昨天：[aos-gdb-動詞-1119](../19/aos-gdb-動詞-1119.md)、[aos-gdb-lib-第二版](../19/aos-gdb-lib-第二版.md)

## 使用者 11-20 的裁定（選項框，答案逐字）

1. 加 wait= 的是「暫停 a.bp.pause()」。
2. 不等時回什麼：「回一個可以查的物件。用is_done()」。
3. resume／step 要不要跟著加：「三個都加」（取代昨天「a.resume()就是a.resume()，他的args不應該有東西」；只開 `wait=` 這一個參數）。
4. 斷點 id：「不能純數字，然後搭配id、屬性(hook點種類)嗎？」——頂層的解讀（已跟他講過）：id 是純數字，種類放在屬性。
5. 號碼：「不重用」。
6. `a.bp.add.<種類>(...)` 回什麼：「回物件、帶屬性」。
7. 物件屬性：「每次讀都重新查」。
8. 扣在斷點上時下 `a.ctl.stop()`：「這次不動」——gdb_trigger 的扣住邏輯沒改。

## 改完寫起來的樣子

```python
b = a.bp.add.before_tool("write")     # b.id == 1、b.kind == "before_tool"
a.say("hi"); a.bp.resume()            # stopped at breakpoint 1 (before_tool: write)
b.fired                               # 1（每次讀都重新查）
p = a.bp.step(wait=False)             # 放行就回
p.is_done()                           # False → 停了之後 True
p.wait()                              # 跟 a.bp.step() 回的一樣：stopped after one step, before think
a.bp.rm(b); b.fired                   # Failed: breakpoint 1: it is gone from ann (removed); a.bp.ls() lists the ones there are
a.bp.add.after_tool().id              # 2（1 刪了也不再用）
```

## 做了什麼

- `proto8/py/aos/gdb/__init__.py`：`resume`／`step`／`pause` 收 `wait=True`（只收 True／False，別的值 `ArgumentsBad`）；`wait=False` 時指令照原樣送出（送的那一小段照舊不理 Ctrl-C），等它停的那段丟給背景執行緒跑，回 `Pending`。`add` 回 `Breakpoint`；`rm`／`set`／`get`／`replace=` 收物件、號碼、數字字串或名字。列的 `kind` 改成種類（`before_tool`、`tool_error`…、觀察者 `watch`），`on` 拿掉。`a.bp` 的列印每行多一欄種類；`stopped at …` 改成 `stopped at breakpoint 1 (before_tool: write)`、`stopped at breakpoint 2 (after_tool: write), before think`、`stopped at breakpoint 3 (watch: ann), before think`。
- 新檔 `proto8/py/aos/gdb/handles.py`：`Breakpoint`、`Pending` 兩個物件。
- `proto8/py/aos/gdb/trigger.py`：號碼計數器 `take_id`（拿號碼）、`give_back`（下斷點失敗時還回去），檔 `<agent stack>/gdb/next_id.json`（`{"next": N}`），鎖 `gdb/next_id.lock`（flock）。
- `proto8/py/aos/gdb/watcher.py`：觀察者的號碼從它看的每一隻的計數器一起拿，掛不上表就還回去；`proc_of(id)`＝`gdbw_<id>`；`ls` 的 name 是整好的 id。
- `proto8/py/aos/gdb/look.py`：`bp_id()` 認號碼（回 int）與名字（回 str）；`Why` 的 docstring。
- `proto8/py/aos/apps/gdb/__init__.py`（`aos-gdb --help`）、`proto8/py/aos/py/breakpoint.py` 的說明字串。
- 文件：`proto8/py/aos/apps/gdb/README.md`（「不等：wait=False」、「id 與斷點物件」兩節、表與範例）、教學 `docs/tutorial/06-接著開發-3-除錯與腳本.md`（輸出字句、兩點說明）、知識庫 `knowledge/aos/cli/gdb.json`。
- 測試：`py/tests/apps/gdb/test_gdb_trigger.py`（新 `Ids` 三支、`test_pending`，既有的改新 id）、`test_gdb_live.py`（新 test_18、test_19，既有的改新 id 與新句子）。
- 沒碰：gdb_trigger 的扣住邏輯（裁定 8）、hook 引擎、daemon、aos-agent 指令、`agent_spec.py` 的 `--help`、`a.ctl.stop`。proto8 當沒有舊版：沒寫遷移、舊 id（`before_tool_1` 這種小格與 hook）不認。

**要重建什麼**：已經掛著 `gdb_before_tool_1` 這類舊名 hook 的 agent，新版 `a.bp` 列得出它（當成名字 `before_tool_1`）但號碼從 1 起；要乾淨就 `a.bp.clear()` 後重下。舊的 `gdbw_watch_1` 觀察者同理。

## 施工線自己定的細節（替使用者做的選擇標★）

1. ★**自己取名 `id="mine"` 照留**：使用者沒裁，選最不破壞的。名字是 str，不能全是數字（全是數字的字串一律當號碼看）；不吃號碼；`ls` 號碼在前、名字在後。
2. ★**號碼不能自己挑**：`id=7` 只能拿來 `replace=True` 已經有的 7；沒有的號碼報錯（說「numbers are given out in order and never used again」）。理由：自己挑號碼會跟「不重用」打架。
3. ★**觀察者的號碼**：跟觸發器同一條數列。觀察者從「它看的每一隻」的計數器一起拿（取最大的、每一隻都推過去），再躲開這個 daemon 上觀察者用過的號碼（表上的、`procs/gdbw_<號碼>` 留著的夾）；觸發器也躲開表上觀察者的號碼。所以在每隻的 `a.bp` 裡觸發器和觀察者不撞、刪了不重用，daemon 上 `gdbw_N` 也不撞。代價：一隻的號碼會因為別隻的觀察者跳號（只會跳，不會撞）。沒另開 daemon 層的計數器檔。
4. ★**id 型別**：號碼是 `int`；也收數字字串 `"3"`（`rm`／`set`／`get`／`replace=`）。
5. ★**不等物件 `Pending` 的其餘方法只多一個 `wait()`**：好了就馬上回、沒好就等，回的跟 `wait=True` 一樣（`.outcome`、`.head`、印出來同一段）；背景的錯（`Timeout` 等）在 `wait()` 丟；`wait()` 裡 Ctrl-C 只是這次不等，背景照等。另有 repr（`still waiting`／`done: …`）。沒有 cancel：要停用 `a.bp.pause()`。
6. 背景不印「still waiting」那一行（`report_s` 只管 `wait=True`；印在 REPL 中間會亂）；`idle_s`、`timeout_s` 照用。
7. 已經停著時 `pause(wait=False)` 回一個一拿到就好了的 `Pending`。
8. 同一隻同時兩個沒好的 `Pending`（或一個 `Pending` 加一個等的動作）不擋，誰先看到停誰先好；README 寫「別這樣用」。
9. `Breakpoint` 的屬性＝`a.bp.get(id)` 那一列的每一欄，唯讀（改用 `a.bp.set(b, ...)`）；`.id` 固定，刪了也讀得到；刪了讀別的屬性丟 `Failed`（code `BreakpointGone`，句子 `breakpoint 1: it is gone from ann (removed); a.bp.ls() lists the ones there are`）；repr 印 `<breakpoint 1 of ann: before_tool, tool write is about to run (enabled, fired 0)>`，刪了印 `<breakpoint 1 of ann: gone>`；`b == 1` 比 id（所以 `a.bp.why().breakpoint == b` 成立）。
10. 下斷點失敗＝號碼還回去（計數器還停在 n+1 才改回 n；昨天 aos-bpfix「id 不跳號」照守）。
11. hook 照名字的字典順序跑：同一事件上 `gdb_10` 排在 `gdb_2` 前面（誰先扣住）。沒補零，README 寫明「要定先後就自己取名」。

## 待裁小題（沒問，留給使用者）

- 號碼要不要補零（`gdb_0002`）讓 hook 照號碼順序跑。
- `Pending` 要不要有 cancel（現在要停只能 `a.bp.pause()`）。
- `a.bp.set` 現在回 dict（`get` 那一列）；要不要也回斷點物件。

## 驗收（乾淨複本 `~/.aos/scratch/aos-gdb-wait-1120/repo`，HEAD `15f6a5bc1` 加本線改動，複本裡 `install.py`；假腦）

程式與測試 commit `2e421761c`、文件 commit `ff905b7b0`。輸出摘要見下面各小節。

### gdb 測試

`py/tests/apps/gdb`：`test_gdb_trigger`＋`test_gdb_live` 共 58 支全過（第一次跑 test_18 的 pause 那段錯一次：`until(where()=="act")` 看到 act 時那一格還沒開頭讀 ctl，pause 在 act 前就套用；改成看到 act 後再等 1 秒，跟 test_14 一樣，重跑過）。

### 教學 6.6 的指令

start-api 的 ann（假腦會叫 `peek_now_time`，教學是 `shout`）在 `aos-gdb` 裡照 6.6 的七行打一遍，再加 `wait=False` 與物件屬性幾行；輸出字句跟教學與 README 對上（工具名、路徑、時間除外）：

```
stopped at breakpoint 1 (before_tool: peek_now_time)
ann is held at breakpoint 1: tool peek_now_time has not run yet; a.bp.resume() lets it go on as it was, a.bp.step() runs it and stops after this step
  2026-11-20T08:37:38.881+08:00 hook gdb_1: tool peek_now_time is about to run [held before it]
gdb> <a.bp of ann: 1 breakpoint(s); add.<kind>(...) / rm / set / ls / get, resume / step / pause, why / held / stopped>
  1  before_tool  tool peek_now_time is about to run  <- stopped here
stopped after one step, before think
ann is paused by a.bp.step()
removed gdb_1 (.../.stack/procs/ann/hooks.json#/hooks/gdb_1: deleted)
ann did not stop: it is idle (nothing queued, no step running); give it work (a.say(...)) and a.bp.resume() waits again
gdb> <breakpoint 1 of ann: gone>
aos.py._shell.Failed: breakpoint 1: it is gone from ann (removed); a.bp.ls() lists the ones there are
gdb> <breakpoint 2 of ann: after_tool, tool peek_now_time finished (enabled, fired 0)>
gdb> a.say("again"); p = a.bp.resume(wait=False); p.is_done()   → False
gdb> p.wait()   → stopped at breakpoint 2 (after_tool: peek_now_time), before think
gdb> c.fired    → 1
```

### 整套 py/tests

共用模組 `py/tests` 602 支 OK（skip 1）；`apps/*` 逐夾：agent 213 OK、gdb 58 OK、eca 223 錯 1、feedback 18 錯 1，其餘（asuser、clock_register、comm、daemon_ctl、json_view、mailbox、mcp、mcp_import、sandbox、share、sweeper、tools）全 OK。兩個錯都跟本線無關、不修：

- `feedback` 的 `test_add_preserves_text_and_appends_with_metadata`：本線把 `TMPDIR` 設在 `~/.aos/scratch/…`（家目錄底下），feedback 把 cwd 縮寫成 `~/…`，跟測試比的絕對路徑對不上。`TMPDIR` 照預設（/tmp）重跑＝11 支 OK。
- `eca` 的 `test_history_edit.test_changed_during_turn_new_conversation_next_turn`：`.history_sum` 是 hash 不是 `edited`；同一份複本、`TMPDIR` 照預設重跑＝3 支 OK。看起來是時機或暫存夾位置造成的，沒碰 eca。

收尾 `pgrep -a aos` 沒有行程（開工前也沒有）。

## 使用者怎麼試

1. 點頭後在要用的那份 proto8 跑 `python3 install.py`（本線沒在 `~/repo/aos/proto8` 跑；改 `py/` 要裝了才生效）。
2. 照 README「最短試法」起 start-api 的樹，`aos-gdb -d .stack ann`，打上面「寫起來的樣子」那幾行；`wait=False` 想看到 `is_done()` 是 False，可以先 `a.bp.add.after_tool(sh="sleep 3; exit 10")` 讓 act 那一格拖 3 秒。
