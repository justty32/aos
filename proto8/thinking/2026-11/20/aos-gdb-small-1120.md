aos-gdb 三個小加強施工紀錄（線 aos-gdb-small-1120）：Pending 加 cancel()、a.bp.set 也回斷點物件、磁碟上的斷點名字號碼補零到 4 位；做了什麼、替使用者做的選擇、測試前後、暫存樹實跑 12 個斷點與 cancel 的輸出。

← [2026-11-20](README.md)｜前一條：[aos-gdb-wait-1120](aos-gdb-wait-1120.md)（「待裁小題」與檔尾答案）｜問答：[aos-gdb-問答-1120](aos-gdb-問答-1120.md)｜庫的說明：[apps/gdb/README](../../../py/aos/apps/gdb/README.md)

## 依據

使用者 11-20 上午在選項框「gdb 三小題，要加哪些？（可複選）」選「Pending 加 cancel(),a.bp.set 也回物件,斷點號碼檔名補零」（[aos-gdb-wait-1120 檔尾](aos-gdb-wait-1120.md#留的三小題使用者-11-20-上午已答)），之後說「開工吧」。三題的背景是那份紀錄的「待裁小題」：hook 照名字的字典順序跑（`gdb_10` 排在 `gdb_2` 前）、`Pending` 要停只能 `a.bp.pause()`、`a.bp.set` 回 dict。

## 改完寫起來的樣子

```python
b = a.bp.add.before_tool("write")    # b.id == 1；磁碟上是 hooks/gdb_0001、hook 名 gdb_0001
s = a.bp.set(b, times=2)             # 回斷點物件（跟 add 回的同一種）：s == b、s.times == 2
p = a.bp.step(wait=False)
p.cancel()                           # True：不等了；step 送的 pause 不收回，這一格做完照停
p.is_done(); p.wait()                # True；stopped waiting (cancel()); nothing is taken back: what a.bp.step() sent stays sent
```

## 做了什麼

- `py/aos/gdb/handles.py`：`Pending.cancel()`。背景那段改成收一個 `threading.Event`；`cancel()` 設它、等背景真的停了才回（實測不到 0.1 秒）。回 `True`＝這次 cancel 讓它好的；`False`＝早就好了。repr 多一句 `.cancel() stops waiting`。
- `py/aos/gdb/__init__.py`：`_wait` 多 `cancel=`，每一圈先看停了沒、再看 cancel，設了就回 outcome `cancelled`（不叫 `_take_back`）。`a.bp.set` 兩個分支（觸發器、觀察者）都回 `Breakpoint(self, id)`。`_hook(id)` 走補零。
- `py/aos/gdb/look.py`：新 `bp_name(id)`、常數 `DIGITS = 4`：號碼補零到 4 位，名字原樣。`bp_id("gdb_0012")` 本來就回 `12`，沒改。`Why` 說明的 outcome 加 `cancelled`。
- `py/aos/gdb/watcher.py`：`proc_of` 走 `bp_name`（`gdbw_0002`）。
- `py/aos/apps/gdb/__init__.py`：`aos-gdb --help` 加 cancel 與「set 也回物件、磁碟上 gdb_0003」一行。
- 文件：`py/aos/apps/gdb/README.md`、教學 `docs/tutorial/06-接著開發-3-除錯與腳本.md`（輸出裡的 `gdb_1` 改 `gdb_0001`，兩點補字）、知識庫 `knowledge/aos/cli/gdb.json`。
- 測試：新檔 `py/tests/apps/gdb/test_gdb_handles.py`（cancel 四支、補零兩支、set 一支；假的 aos-agent 借 `test_gdb_trigger` 的 AddFails）；`test_gdb_live.py` 新 `test_23`（真的 `step(wait=False)` 後 cancel、pause 照停、hook 名補零），`test_10` 改成 set 回物件；既有測試裡寫死的 `gdb_1`、`gdbw_5`、`gdbw_%d` 改補零。
- 沒碰：hook 機制、daemon、aos-agent、`gdb_trigger`／`gdb_watch` handler（它們用小格夾名與 spec 裡的 proc 名，名字怎麼取跟它們無關）、`py/aos/py/breakpoint.py` 的說明字串（不在領地；那句只講 `is_done()`，沒說錯）。proto8 當沒有舊版：已經掛著 `gdb_1` 這種舊名的 agent 不處理：照程式推，新版 `a.bp.ls()` 列得出號碼 1，但讀設定時找的是 `gdb_0001` 夾，讀不到；`a.bp.rm(1)`／`clear()` 會報 `BreakpointMissing`（沒實測）。要乾淨就在 shell 下 `aos-agent hook rm gdb_1`（舊小格夾留著不影響），再用新版重下。

## 替使用者做的選擇

1. ★**cancel 只是不再等、不撤回**：已經送出的放行、`ctl resume`、`ctl pause` 一樣都不收回。跟 Ctrl-C 不一樣（Ctrl-C 會收回 `step` 送出還沒套用的 pause）；所以 `step(wait=False)` 之後 cancel，這一格做完它照樣停。要它停用 `a.bp.pause()`；要它不停就 `a.bp.resume()`。
2. ★**cancel 之後**：`is_done()` 是 `True`；`wait()` 回一個 outcome `cancelled` 的結果，第一行 `stopped waiting (cancel()); nothing is taken back: what a.bp.step() sent stays sent`（`step` 換成那個動作）。剛好已經停了或早就好了（含背景已經出錯）：cancel 什麼都不變、回 `False`，`wait()` 照回原本的結果或丟原本的錯。
3. ★**`cancel()` 的回傳值**：`True`／`False`（是不是這次 cancel 讓它好的），不是結果本身；結果照樣用 `wait()` 拿。
4. ★**`cancel()` 會等背景真的停**（每 0.1 秒看一次，背景每 0.05 秒看一次 cancel），所以回來之後 `is_done()` 一定是 `True`。
5. ★**補 4 位**：照前一份紀錄寫的例子 `gdb_0002`。過了 9999 就是原樣的 5 位以上，從那裡起順序不保證（README 寫了）。
6. ★**補零的範圍**：觸發器的 hook 名＝小格夾名（`hooks/gdb_0003/`）與觀察者的 proc 名（`gdbw_0003`，也是 `procs/gdbw_0003/` 夾）都補；`.id`、`a.bp.ls()` 的 `id`、`stopped at breakpoint 3 (...)` 這類句子照舊是純數字。自己取的名字（`id="mine"`）不補，排在全部號碼後面（字母在數字後）。
7. ★**`a.bp.set` 回物件後不再回 dict**：要一份當下的 dict 用 `a.bp.get(b)`。給號碼或數字字串 `set("1", ...)` 回的物件 `.id` 是 int。

## 驗收

程式與測試 commit `b611ae18c`、文件 commit `b55dd4b63`。

乾淨複本：`git archive e1209424b proto8`（開工時的 HEAD）各抄一份，`base` 不動、`new` 疊本線 11 個檔，兩份各自在複本裡 `install.py`；`TMPDIR=/tmp/aos-gdb-small-1120`；假腦。

### gdb 測試前後

`py/tests/apps/gdb`（`test_gdb_trigger`、`test_gdb_live`，改後加 `test_gdb_handles`）：

| | 支數 | 結果 |
|---|---|---|
| 改動前（`base`） | 58 | 56 過；`test_07_tool_error_twice_in_a_row`（字條的 `code` 是 None）、`test_15_step_goes_one_cell_at_a_time`（回「沒停：閒著」）兩支 FAIL |
| 改動前重跑那兩支 | 2 | 都過（71 秒）——機器很忙（load average 34，別線同時在跑測試），兩支看起來是時機不穩，跟本線無關 |
| 改動後（`new`） | 66 | 全過（713 秒）：原本 58 支＋`test_gdb_handles` 7 支＋`test_23` |

只跑不起 daemon 的兩檔（`test_gdb_handles`＋`test_gdb_trigger`）：43 支 14 秒全過。

### 暫存樹實跑（12 個斷點、set、cancel）

`~/.aos/scratch/aos-gdb-small-1120/tree`（start-api 抄一份、假腦，用 `new` 那份裝好的 aos），`aos-gdb -d .stack ann` 從 stdin 餵 `try-input.py`；echo 關掉。左邊是打的那行，`→` 後面是輸出原樣（路徑縮成 `…`）：

```
bs = [a.bp.add.after_tool(sh="exit 10") for _ in range(12)]
[b.id for b in bs]          → [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
a.bp                        → <a.bp of ann: 12 breakpoint(s); add.<kind>(...) / rm / set / ls / get, resume / step / pause, why / held / stopped>
                                1  after_tool  tool any finished and sh `exit 10` exits 0
                                2  after_tool  tool any finished and sh `exit 10` exits 0
                                …（3～9 同樣一行一個，照號碼）
                                10  after_tool  tool any finished and sh `exit 10` exits 0
                                11  after_tool  tool any finished and sh `exit 10` exits 0
                                12  after_tool  tool any finished and sh `exit 10` exits 0
print(sh("ls " + a.stack + "/hooks"))
                            → context_wrap
                              gdb_0001
                              gdb_0002
                              gdb_0003
                              gdb_0004
                              gdb_0005
                              gdb_0006
                              gdb_0007
                              gdb_0008
                              gdb_0009
                              gdb_0010
                              gdb_0011
                              gdb_0012
                              mail_notify
                              timer
[r["name"] for r in a.hook.ls(json=True)]
                            → ['brain_notify', 'context_wrap', 'gdb_0001', 'gdb_0002', 'gdb_0003', 'gdb_0004', 'gdb_0005', 'gdb_0006', 'gdb_0007', 'gdb_0008', 'gdb_0009', 'gdb_0010', 'gdb_0011', 'gdb_0012', 'mail_notify', 'timer']
s = a.bp.set(bs[1], times=2)
(type(s).__name__, s.id, s.kind, s.times, s == bs[1], type(s.id).__name__)
                            → ('Breakpoint', 2, 'after_tool', 2, True, 'int')
s                           → <breakpoint 2 of ann: after_tool, tool any finished and sh `exit 10` exits 0 (2 times in a row) (enabled, fired 0)>
a.bp.set(bs[1], enabled=False).enabled
                            → False
a.bp.rm(bs[9]); a.bp.add.before_tool("peek_now_time").id
                            → removed gdb_0010 (…/tree/.stack/procs/ann/hooks.json#/hooks/gdb_0010: deleted)
                              13
a.bp.clear(); a.bp.ls()     → []
b = a.bp.add.before_tool("peek_now_time", once=True)
slow = a.bp.add.after_tool(sh="sleep 3; exit 10")
x = a.say("hi"); a.bp.resume()
                            → stopped at breakpoint 14 (before_tool: peek_now_time)
                              ann is held at breakpoint 14: tool peek_now_time has not run yet; a.bp.resume() lets it go on as it was, a.bp.step() runs it and stops after this step
                                2026-11-20T12:05:15.894+08:00 hook gdb_0014: tool peek_now_time is about to run, once [held before it]
                                    name="peek_now_time" arguments={}
p = a.bp.step(wait=False); p.is_done()
                            → False
p                           → <a.bp.step(wait=False) on ann: still waiting; .is_done() asks, .wait() waits, .cancel() stops waiting>
p.cancel()                  → True
p.is_done()                 → True
p.wait()                    → stopped waiting (cancel()); nothing is taken back: what a.bp.step() sent stays sent
a.bp.stopped()              → False                （act 那一格還在跑 sleep 3）
import time; time.sleep(6); a.bp.stopped()
                            → True                 （step 送的 pause 沒收回：這一格做完照停）
a.look.where()              → 'think'
q = a.bp.pause(wait=False); q.cancel()
                            → False                （已經停著：拿到就是好的，cancel 什麼都不變）
q.wait().outcome            → 'stopped'
a.bp.resume()               → ann did not stop: it is idle (nothing queued, no step running); give it work (a.say(...)) and a.bp.resume() waits again
a.listen(letter=x)          → FAKE ANSWER to: hi (tool said: 2026-11-20T04:05:18Z)
a.bp.clear(); a.bp.ls()     → []
```

看得到的：12 個斷點 `ls hooks/` 與 `hook ls` 都照號碼排（`gdb_0010` 在 `gdb_0009` 後）；刪掉 10 再下拿到 13（不重用），clear 之後再下是 14。`a.bp` 的列印號碼兩位數時欄位多一格、沒對齊（只是好看與否，沒改）。

收尾：兩台 daemon 用 `aos-daemon-ctl -d … shutdown` 收；自己記的兩個 pid 都已不在。`pgrep -a aos` 開工前沒有行程；收尾時有一批，全是別線的（`~/.aos/scratch/aos-kinit-tpl-1120/…`、`/tmp/aos-hook-k2-1120-base/…`、`/tmp/gdb-live-*`（別線用預設 TMPDIR 跑 gdb 測試）、`/tmp/aos-reviewer-*`、`/tmp/aos-daily-*`），本線的 TMPDIR（`/tmp/aos-gdb-small-1120`）與暫存樹底下沒有，沒去碰。

## 跟別線

- 只動領地內的 11 個檔加這份紀錄；開工時都沒人 claim。工作樹裡別線沒交的改動（hook、編譯程式庫、start-api 樣板等）沒碰、沒抄進複本（複本是 `git archive`）。
- 機器很忙（別線同時跑整套測試），live 測試會因時機不穩偶爾紅，見上表改動前那兩支。

## 使用者怎麼試

1. 點頭後在要用的那份 proto8 跑 `python3 install.py`（本線沒在 `~/repo/aos/proto8` 跑）。
2. 起 start-api 的樹，`aos-gdb -d .stack ann`，打上面「寫起來的樣子」；12 個斷點：`[a.bp.add.after_tool(sh="exit 10") for _ in range(12)]`，再 `sh("ls " + a.stack + "/hooks")` 看夾名照號碼排。已經掛著舊名 `gdb_1` 的 agent 先在 shell 下 `aos-agent hook rm gdb_1`。
