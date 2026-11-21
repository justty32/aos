# aos-gdb — 在 Python REPL 裡對一隻已在跑的 agent 下斷點：條件成立就把它停下來，看完再續（入口 `aos.py`、遙控器 `a = agent.attach(名)`；斷點全在 `a.bp` 底下，以斷點為核心增刪改查）

← [cmd](../../../docs/05-commands.md)｜入口：[py/aos/py](../../py/__init__.py)｜斷點與讀檔：[py/aos/gdb](../../gdb/__init__.py)｜handler：[gdb_trigger](../../../tools/agent/gdb_trigger/_entry)｜觀察者本體：[gdb_watch](../../../tools/agent/gdb_watch/_entry)｜圖紙：[aos-gdb-1119](../../../../thinking/2026-11/19/aos-gdb-1119/README.md)、[第一版紀錄](../../../../thinking/2026-11/19/aos-gdb-lib-第一版.md)、[第二版紀錄](../../../../thinking/2026-11/19/aos-gdb-lib-第二版.md)、[整套 Python 庫](../../../../thinking/2026-11/19/aos-pylib-1119/README.md)、[施工紀錄](../../../../thinking/2026-11/19/aos-pylib-施工.md)、[控制動作紀錄](../../../../thinking/2026-11/19/aos-gdb-動詞-1119.md)

使用者 11-19 的定義：斷點＝「特定條件發生時，暫停loop或fsm，停下來等待檢閱」，「能把他停下來的都可以」，「hook不用動」；第二版：「stop_before_tool不就是在工具開始前停下嗎？丙可以繼續」。hook 機制、daemon、aos-agent 都沒改。

介面（使用者 11-19「斷點這塊，我覺得他的架構就是以斷點為核心， 增刪改查。然後a.xxx這塊，感覺就是aos-agent xxxx」；整套 Python 庫的選項框裁定：入口 `aos.py`、遙控器式、建斷點 `a.bp.add.before_tool("x")`、讀檔收進 `a.look`，見 [aos-pylib-1119/07](../../../../thinking/2026-11/19/aos-pylib-1119/07-使用者裁定.md)）：

- **`a.xxx`＝`aos-agent xxx`**，一個呼叫＝一條指令，由入口的通用代理翻（`a.X.Y(ARG, flag=v)`＝`aos-agent --daemon D --target 名 X Y --flag v ARG`；`a.say`、`a.listen`、`a.ctl.state(json=True)`、`a.tools.add(…)`、`a.hook.ls()`…，`aos-agent` 以後加的子指令自動有）。
- **兩個延伸**（不是 `aos-agent` 子指令，只在庫裡）：`a.bp` 斷點、`a.look` 讀 stack 的檔（`where`、`history(n)`、`observed(n)`、`request`、`queue`、`stderr(n)`、`file(rel)`）。`a` 上其他不是子指令的名字當場 `AttributeError`。
- 斷點：增 `a.bp.add.<種類>(...)`（**回斷點物件**）、刪 `rm`、改 `set`、查 `ls`／`get`，每個斷點一個 **id：純數字、刪了不再用**，種類放在屬性 `.kind`；控制 `resume`（繼續跑）、`step`（走一格）、`pause`（現在停）——三個**預設都等到停下才回**、回停在哪，給 `wait=False` 就送出馬上回一個可以查的物件（`is_done()`）；停在哪、為什麼 `why`／`held`／`stopped`。觸發器與觀察者是兩種斷點，同一條號碼。

## 控制：`resume`、`step`、`pause`（照 IDE／gdb）

使用者 11-19：「我記得有step into還是啥的，參考那些ide」；選項框選「resume/step 自己等到停」（像 gdb 的 continue：放行後卡著，等到下次停下才回來、印出停在哪；不再有 wait 這個方法（11-20 起要不等，是三個動作的 `wait=False`，見下面）；Ctrl-C 只是不等了，agent 照跑）；「放行但那次工具不跑」那個方法「不該有這個方法」（拿掉了）；「現在停」選「改 a.bp.pause() (Recommended)」（VS Code 的「停一下」叫 Pause；aos 的 `ctl stop` 是把整隻停掉）。紀錄：[aos-gdb-動詞-1119](../../../../thinking/2026-11/19/aos-gdb-動詞-1119.md)。

```
b = a.bp.add.before_tool("write")
a.say("write a note")
a.bp.resume()      # 等到停在斷點才回來
# stopped at breakpoint 1 (before_tool: write)
a.bp.step()        # 走一格，又停
a.bp.resume()      # 繼續，等下一次停
```

**不等：`wait=False`**（使用者 11-20 選項框：加 wait= 的是「暫停 a.bp.pause()」、不等時「回一個可以查的物件。用is_done()」、resume／step「三個都加」；紀錄 [aos-gdb-wait-1120](../../../../thinking/2026-11/20/aos-gdb-wait-1120.md)）。三個動作都只收這一個參數，預設 `wait=True`＝上面那樣等；`wait=False`＝動作送出去就回一個 `Pending`，等它停下的那段在背景（同一個 Python 行程裡的一條執行緒）跑：

```
p = a.bp.resume(wait=False)   # 放行就回
p.is_done()                   # False：還在等它停
p                             # <a.bp.resume(wait=False) on ann: still waiting; .is_done() asks, .wait() waits, .cancel() stops waiting>
p.is_done()                   # True：停了（或確定不會停、或等出錯了）
p.wait()                      # 回的跟 a.bp.resume() 一樣：.outcome、.head、印出來同一段
q = a.bp.step(wait=False)
q.cancel()                    # True：不等了（不收回任何東西：step 送的 pause 照留，這一格做完它照樣停）
q.wait()                      # stopped waiting (cancel()); nothing is taken back: what a.bp.step() sent stays sent
```

- `p.wait()` 好了就馬上回，還沒好就等到好；背景裡丟的錯（`a.bp.timeout_s` 到了的 `Timeout` 等）在 `wait()` 丟。`wait()` 裡按 Ctrl-C 只是這次不等了，背景照等。
- `p.cancel()`（使用者 11-20 選「Pending 加 cancel()」）：叫背景不再等，等它真的停了才回（通常不到 0.1 秒）。**只是不等了，已經送出的放行、`ctl resume`、`ctl pause` 一樣都不收回**（跟 Ctrl-C 不同：Ctrl-C 會收回 step 送出還沒套用的 pause）；要它停用 `a.bp.pause()`。回 `True`＝是這次 cancel 讓它好的，之後 `is_done()` 是 `True`、`wait()` 回 `.outcome == "cancelled"` 那一句；回 `False`＝早就好了（剛好停了、或已經是好的），`wait()` 照回原本的結果。
- 背景不印「still waiting」那一行（`report_s` 只管 `wait=True`）；`idle_s`、`timeout_s` 照用。已經停著時 `a.bp.pause(wait=False)` 回一個已經好了的。
- 同一隻同時有兩個沒好的 `Pending`（例如 `resume(wait=False)` 還沒好又下 `step()`）不擋，誰先看到停誰先好；別這樣用。

| 動作 | 停著時（扣住／暫停） | 沒停著時 | 回什麼 |
|---|---|---|---|
| `a.bp.resume()` | 扣住＝放行那一次（照原樣跑）；暫停＝`ctl resume` | 什麼都不送，只等 | 下一次停下時的 `why()`，第一行說停在哪 |
| `a.bp.step()` | 暫停＝`ctl resume`，loop 一套用就 `ctl pause --no-wait`；扣住＝先 `ctl pause --no-wait` 再放行（工具照跑，act 這一格做完才停） | `ctl pause --no-wait`（這一格做完就停） | 同上，第一行 `stopped after one step, before think` 之類 |
| `a.bp.pause()` | 什麼都不送 | `ctl pause --no-wait` | 同上（`stopped before idle (a.bp.pause())`）；停著時 `already stopped ...` |

- **一格**＝fsm 的一格（`idle`、`think`、`wait`、`act` 之一跑一次）；停住時 `a.look.where()`／第一行的 `before X`＝下一格。等腦回話時 `wait` 是一格接一格（同一個 wait 走好幾步才到 act）。這一格裡碰到別的斷點（例如同一格 act 裡第二個工具也有 before_tool 斷點）＝停在那裡。
- **它不會停時**（閒著了、斷點都拿掉了）不卡死：閒著（`stage.txt` 是 idle、`queue/new` 與 `queue/cur` 都空、沒有還沒套用的 pause）連續 `a.bp.idle_s` 秒＝回 `did not stop: it is idle`；loop 行程不在（sleep、stop、rm）＝回 `did not stop: it is not running`。等的時候每 `a.bp.report_s` 秒（預設 10）在 stderr 印一行現況（在哪一格、信箱幾封）。`a.bp.timeout_s`（預設 None＝不限）給了才會逾時，丟 `Timeout`。這三個是 `a.bp` 的屬性，不是參數（參數只有 `wait=`）。回的東西有 `.outcome`：`stopped`、`idle`、`gone`、`interrupted`（`wait=False` 的 `cancel()` 之後另有 `cancelled`）。
- **Ctrl-C**：只是不等了，agent 照跑，回 `stopped waiting (Ctrl-C); ann goes on as it was`。送指令的那一小段先不理 Ctrl-C（指令不會送一半）；step 送出還沒套用的 pause 會收回（背景跑一條 `aos-agent ctl resume`）。`pause()` 的 Ctrl-C 例外：pause 已經送出，這一格做完它就停（要停是你要的）。
- **限制**：step 從暫停起是接力（ctl 窗只放得下一道指令）：`ctl resume` 一被套用才寫 `ctl pause`，空檔約 0.04 秒；比這更短的一格（例如閒著時的 idle 一格）可能多走一格。eca 身（沒有 `stage.txt`）認不出閒著，只靠定期那一行與 `timeout_s`。觀察者看著時閒著照樣回「沒停」（觀察者之後才停它的話，再 `resume()` 一次）。

## 建斷點：`a.bp.add.<種類>([主詞], *, 條件, 選項)` → 斷點物件

所有種類同一個形狀；`a.bp.add` 直接打出來會列出每一種與它的參數，tab 補得出，打錯種類當場 `AttributeError`；字串式 `a.bp.add("before_tool")` 不收（`Failed`，說要寫種類）。

| 寫法 | 什麼時候停 | 停法 |
|---|---|---|
| `a.bp.add.before_tool("write")` | 工具 write 要跑之前（不給＝任何工具；也收 list） | 扣住 |
| `a.bp.add.after_tool("write")` | 工具跑完、腦還沒看到結果 | 暫停 |
| `a.bp.add.tool_error("write", times=2)` | 工具跑完而且回錯（退出碼不是 0 或逾時） | 暫停 |
| `a.bp.add.before_queue()` | 一封信要收進來之前 | 扣住 |
| `a.bp.add.after_queue()` | 收了一封信之後 | 暫停 |
| `a.bp.add.brain_failed("BrainFailed")` | 問腦失敗（主詞是錯誤代號，參數名 `code`） | 暫停 |
| `a.bp.add.tool_added("grep")` | 加了工具 | 暫停 |
| `a.bp.add.after_start()`、`a.bp.add.after_stop()` | loop 起來、要退 | 暫停 |
| `a.bp.add.watch(py=…, every_ms=500, also=["bob"])` | 觀察者：另一支 proc 輪詢，條件成立（一定要給 sh 或 py） | 暫停（晚一格） |

- **主詞**（第一個位置參數）只有能篩名字的種類有：工具名（`tool=`），`brain_failed` 是錯誤代號（`code=`）；其他種類不收位置參數。種類表＝agent 一家自己發的點（`aos.agentlib.hooks.POINTS`，`on_clock` 不收）加上經 `aos-hook fire` 發的 eca 壓縮兩點與 loop 四點（寫在 `aos.gdb` 裡；11-21 起宣告只是參考，不從宣告算）。
- **條件**（都是關鍵字）：不給＝事件來了就算；`sh="..."`＝一段 shell（觸發器：事件 JSON 在 stdin；觀察者：cwd＝目標 stack；退 0＝算、**退 10＝不算**、其他＝條件壞了，所以 `grep -q x || exit 10`）；`py=`＝觸發器 `f(ev)`／運算式字串（變數 `ev`），觀察者 `f(t)`／運算式字串（變數 `t`），看得到 `json`、`re`、`os` 與內建，外層變數要當預設值傳。
- **選項**：`times=`＝連續幾次才算；`once=True`＝只停一次；`id="mine"`＝自己取名（不能全是數字；不給＝下一個號碼）；`replace=True`＝同 id 已有就換掉（`id=` 給已有的號碼或斷點物件也行；沒有的號碼不能自己挑）；觀察者另有 `every_ms`、`also`。

### id 與斷點物件

使用者 11-20 選項框：id「不能純數字，然後搭配id、屬性(hook點種類)嗎？」（＝純數字、種類放屬性）；號碼「不重用」；`add`「回物件、帶屬性」；屬性「每次讀都重新查」。

```
b = a.bp.add.before_tool("write")
b.id          # 3：號碼（int），從 1 起，刪了不再拿來用
b.kind        # 'before_tool'（tool_error、watch…＝a.bp.add 後面那個名字）
b.fired       # 0；停過一次之後再讀就是 1（每次讀都重新查 a.bp.get(b)）
b             # <breakpoint 3 of ann: before_tool, tool write is about to run (enabled, fired 0)>
a.bp.set(b, times=2)   # set 也回斷點物件（跟 add 回的同一種）：<breakpoint 3 of ann: before_tool, tool write is about to run (2 times in a row) (enabled, fired 0)>
a.bp.rm(b)    # rm／set／get 收物件，也收號碼（3、"3"）或自己取的名字
b.fired       # Failed: breakpoint 3: it is gone from ann (removed); a.bp.ls() lists the ones there are
```

- 屬性＝`a.bp.get(id)` 那一列的每一欄（`.kind`、`.how`、`.about`、`.enabled`、`.times`、`.once`、`.seen`、`.fired`、`.spent`、`.last_error`、`.here`、`.condition`…；觀察者另有 `.targets`、`.phase`…），每讀一次就查一次（會跑 `hook ls`、讀小格）；唯讀，改用 `a.bp.set(b, ...)`。`b.id` 固定，刪了也讀得到；`b == 3` 比的是 id。
- **號碼不重用**：計數器存在 agent 的 stack（`gdb/next_id.json`），重開 REPL、重新取 `a.bp` 照樣接著數。觀察者的號碼從它看的每一隻的計數器一起拿（也躲開這個 daemon 上觀察者用過的號碼），所以每隻的 `a.bp` 裡觸發器與觀察者不撞；觸發器也躲開表上觀察者的號碼。下斷點失敗＝號碼還回去（不跳號）。計數器跟著 stack 走：換成一個新的 stack 夾就從 1 數起。
- **磁碟上的名字號碼補零到 4 位**（使用者 11-20 選「斷點號碼檔名補零」）：號碼 3 的觸發器 hook 名與小格夾是 `gdb_0003`、觀察者的 proc 名是 `gdbw_0003`，所以 `ls hookeds/`、`aos-agent hook ls`、`aos-daemon-ctl ls` 列出來照號碼排（10 個以上也對），同一事件上的 hook 也照號碼先後跑。`b.id` 照舊是 `3`（int），指令的輸出與 `a.bp.why()` 裡看到的是 `gdb_0003`。過了 9999 就是 5 位，順序從那裡起不保證。
- `a.bp.set(b, ...)` 回斷點物件（使用者 11-20 選「a.bp.set 也回物件」），跟 `add` 回的同一種（屬性每次讀都重新查）；要一份當下的 dict 用 `a.bp.get(b)`。
- 自己取的名字照留（`id="mine"`，str）：hook 名 `gdb_mine`（不補零），不吃號碼；`ls` 號碼在前、名字在後。
- 不用遙控器也行：`from aos.py import breakpoint as bp; bp.attach("ann", daemon=".stack").add.before_tool("write")`（跟 `a.bp` 同一種；別用原名 `breakpoint`，會蓋掉內建的）。

## 兩種停法（由事件決定，不是選項）

| 事件 | 停法 | 停在哪 | 續 |
|---|---|---|---|
| `before_tool`、`before_queue`（事件還沒發生） | **扣住**（hold）：觸發器的 hook handler 自己不回、等人放行 | 腦已決定叫工具、**工具還沒跑**（信還沒進 history） | `a.bp.resume()`／`a.bp.step()`＝那次**照原樣跑**；shell 的 `aos-agent ctl resume` 也放行（照跑）。沒有「放行但不跑」 |
| 其他（`after_tool`、`brain_failed`…，事件已經發生） | **暫停**（pause）：handler 叫 `aos-agent ctl pause --no-wait` | 那一格做完、下一格開頭（after_tool＝結果已進 history、腦還沒看到） | `a.bp.resume()`＝`ctl resume` |
| 觀察者（`a.bp.add.watch(...)`，另一支 proc） | 暫停：看到時 `ctl pause` 目標 | 晚一格（輪詢檔，約 every_ms＋一格） | 同上 |
| `a.bp.pause()`（不靠斷點） | 暫停：`aos-agent ctl pause --no-wait`，等到真的停下 | 這一格做完 | 同上 |

扣住時要知道的（都實測過，見[第二版紀錄](../../../../thinking/2026-11/19/aos-gdb-lib-第二版.md)）：
- 表上照寫 `running`（它卡在 act 那一格裡，`stage.txt`＝act），**這是刻意的**：aos-agent 與 daemon 不知道 gdb 的存在，兩者解耦合（使用者 11-19 裁定，之後也不讓它們讀 `gdb/` 的檔）。要看是不是停在斷點，用 `a.bp.why()`、`a.bp.held()`（`a.bp.stopped()` 也認得）。信照收進信箱，續了再處理。
- 扣著時別人下 `ctl pause`：放行後工具照跑，這一格做完才停（`a.bp.why()` 會說「then it pauses」）；`ctl stop` 一樣要等放行後才真的停（這段時間表上是 `stopping`，`ctl stop` 本身會一直等到它預設的 30 秒；要馬上停用 `ctl sleep`）。
- 扣著時 `ctl sleep`、`rm`、daemon 收工（都是 TERM）：那一格被收掉，**工具沒跑**，字條記 `hold_ended`；醒來重跑同一個工具呼叫時**直接再扣住**（不再判條件，`once` 也照扣），放行後只跑一次。
- 拿掉或停用斷點（`a.bp.rm`、`a.bp.set(id, enabled=False)`）不影響正扣著的那一次。

## 最短試法（假腦）

```sh
cp -r $AOS_HOME/templates/start-api /tmp/t && cd /tmp/t && source env.sh
aos-exec root &                                   # 根
aos-daemon-ctl -d .stack add --auto-restart llm  # llm kernel（假腦）掛在根上一列
aos-agent -d .stack ctl add --auto-restart -w . agents/ann
aos-gdb -d .stack ann                              # 進 REPL：agent、daemon_ctl、std、defs、a＝ann
```

```
gdb> b = a.bp.add.before_tool("peek_now_time")    # fake brain calls peek_now_time on every message
$ aos-agent --daemon /tmp/t/.stack --target ann ctl state --json who
$ aos-agent --daemon /tmp/t/.stack --target ann hook add --event before_tool --name gdb_0001 ...
gdb> b.id, b.kind
(1, 'before_tool')
gdb> a.say("hello"); a.bp.resume()               # waits until it stops
stopped at breakpoint 1 (before_tool: peek_now_time)
ann is held at breakpoint 1: tool peek_now_time has not run yet; a.bp.resume() lets it go on as it was, a.bp.step() runs it and stops after this step
gdb> a.look.history(1)                            # the call the brain asked for; no tool result yet
gdb> a.bp                                         # every breakpoint, one line each; "<- stopped here"
gdb> a.bp.step()                                  # the tool runs; stops when this step ends
stopped after one step, before think
gdb> a.bp.set(b, enabled=False); a.bp.resume()
ann did not stop: it is idle (nothing queued, no step running); ...
gdb> a.listen()
FAKE ANSWER to: hello (tool said: 2026-...)       # the tool really ran
gdb> w = a.bp.add.watch(py=lambda t: len(t.history(0)) > 6)   # another proc looks every 0.5 s; w.id == 2, w.kind == 'watch'
gdb> a.say("again"); a.bp.resume()                # "stopped at breakpoint 2 (watch: ann), before ..."
gdb> a.bp.rm(w); a.bp.resume()
gdb> a.bp.pause(); a.bp.resume()                   # stop it now without a breakpoint, then go on
gdb> a.say("once more"); p = a.bp.pause(wait=False); p.is_done()   # returns at once; False until it has stopped
gdb> p.wait()                                      # same as a.bp.pause(): "stopped before ..."
```

`aos-gdb` 不給 NAME 也行：只放好 `agent`、`daemon_ctl`、`std`、`defs`，自己 `a = agent.attach("ann")`。給了 `-d D`：REPL 裡 `AOS_DAEMON` 設成它，模組層的 `agent.ctl.ls()`、`daemon_ctl.ls()` 也對那台。收樹：`aos-daemon-ctl -d .stack shutdown`（一句全關，llm kernel 是根上一列；REPL 裡是 `daemon_ctl.shutdown()`）。

**觸發器掛在 agent 的 hook 上，定義要宣告被勾清單**（`interfaces.json` 最外層的 `hookeds`）。上面 start-api 的 ann 有；`agent-python` 骨架抄出來的也有——骨架的 `defs.Agent(...)` 帶 `hooks={}`（空的，不帶任何現成的 hook；使用者 11-19 下午選「骨架帶一行空的 HOOKS」），什麼都不改就下得了斷點。沒宣告的定義（拿掉 `hooks=` 的 `agent.py`、自己手寫的夾）下斷點＝`HooksMissing`，錯誤行後面補一句怎麼修：

```
aos-agent: error: HooksMissing bob does not declare hooks (...); to fix it in an agent.py definition: give hooks={} to defs.Agent(...) in agent.py, and recompile (python3 agent.py --compile)
```

照做、重新編譯後同一個 REPL 裡再下一次就行（不用重起 agent）。下斷點失敗什麼都不留：`a.bp` 列不出它、id 不跳號（重下 `replace=True` 失敗＝原本那個照舊）。

## 能做什麼

`a.xxx`（`aos-agent xxx`；通則與回傳值見 [py/aos/py](../../py/_shell.py) 檔頭）：

| 寫法 | 背後是 | 說明 |
|---|---|---|
| `agent.attach(name, daemon=None)` | （不跑指令） | 只記名字與 daemon（轉絕對路徑）；daemon 不給＝指令自己的預設（`$AOS_DAEMON`，再沒有 `./.stack`）。`a.bp` 要絕對的 daemon：不給就用 `$AOS_DAEMON` |
| `a.say(text)` | `aos-agent say` | 回信名（str），交給 `listen(letter=...)` 等那一封的回答 |
| `a.listen(timeout_s=20, letter=None)` | `aos-agent listen --timeout-s 20 [--letter L]` | |
| `a.ctl.where()`、`a.ctl.state(json=True)`、`a.tools.ls()`、`a.hook.ls()`… | `aos-agent ... ctl where` 等 | 沒給 `json=True`＝stdout 原樣（REPL 印得跟 shell 一樣），空＝None；給了＝解好的 dict／list |
| `agent.ctl.ls()`、`agent.ctl.add(...)`、`agent.ctl.rm(name)` | `aos-agent ctl ls` 等 | 這幾支不吃 `--target`，在模組層叫；在遙控器上叫會被指令擋下，錯誤原樣成 `Failed` |
| `a.stack` | `aos-agent ctl state --json who` | 每次問都跑一次（不快取） |
| `a.look.where()`、`a.look.history(n)`、`a.look.observed(n)`、`a.look.request()`、`a.look.queue()`、`a.look.stderr(n)`、`a.look.file(rel)` | 讀 stack 的檔 | 停住時檢閱；檔不在＝None／[]；echo 開著印 `# read 路徑` |
| `sh(cmd)` | `sh -c` | REPL 裡順手打 shell |

`a.bp.xxx`（斷點，以斷點為核心；收斷點物件，也收 id：號碼或自己取的名字）：

| 方法 | 背後是 | 說明 |
|---|---|---|
| `a.bp.add.<種類>(...)` | 觸發器：`aos-agent hook add --event ... --name gdb_ID`；觀察者：`aos-daemon-ctl add --name gdbw_ID ...` | **增**，回斷點物件（`b.id`＝號碼，例 `3`；`b.kind`＝種類；`id=` 自己取名）。寫法見上一節。失敗（`HooksMissing`、表上掛不上…）＝什麼都不留：觸發器的小格不留、號碼還回去，重下失敗放回原本的設定與計數；觀察者新建的 stack 夾不留 |
| `a.bp.rm(id)`、`a.bp.clear()` | `hook rm gdb_ID`／`aos-daemon-ctl rm gdbw_ID` | **刪**。觸發器的小格留著給人看（標 removed）；觀察者也看別隻的話別隻也不看了。`clear`＝這隻身上全部 |
| `a.bp.set(id, enabled=None, times=None, once=None)` | 改 `trigger.json`／`watch.json`，`hook add --replace`／`hook rm`；觀察者 `aos-daemon-ctl stop／start gdbw_ID` | **改**，回斷點物件（跟 `add` 回的同一種）。停用＝觸發器的 hook 拿下、設定與計數留著（啟用＝裝回去）；觀察者 stop（啟用＝start）。計數不歸零。觸發器裝不上／拿不下＝`trigger.json` 放回原本的。**改不了**：種類、條件（sh／py）、主詞、every_ms、看誰——同一個 id 重下 `a.bp.add.<種類>(..., id=ID, replace=True)` |
| `a.bp.ls()`、`a.bp.get(id)`、`a.bp`（REPL 裡直接打） | `hook ls --json`、讀小格與 `aos-daemon-ctl ls -j` | **查**。一列（號碼小的在前、自己取名的在後）：`id`、`kind`（種類：`before_tool`、`tool_error`…，觀察者是 `watch`）、`how`（hold／pause）、`about`、`enabled`、`times`、`once`、`seen`、`streak`、`fired`、`spent`、`last_error`、`here`（現在是不是停在它這裡）；`get` 另有 `condition`（sh 原文／py）、`tools`，觀察者另有 `targets`、`every_ms`、`phase`、`pid`、`per_target` |
| `a.bp.resume(wait=True)` | 扣住：寫 `gdb/release.json`；暫停：`ctl resume`；沒停著：不送 | 繼續跑，等到下一次停下才回（見「控制」一節）；`wait=False`＝送出就回 `Pending`（`is_done()`、`wait()`、`cancel()`） |
| `a.bp.step(wait=True)` | `ctl resume`＋`ctl pause --no-wait`／`ctl pause --no-wait`＋放行 | 走 fsm 一格就停，等到停下才回；`wait=False` 同上 |
| `a.bp.pause(wait=True)` | `aos-agent ctl pause --no-wait` | 現在停（不靠斷點），等到真的停下才回；已經停著＝不送；`wait=False` 同上 |
| `a.bp.idle_s`、`a.bp.report_s`、`a.bp.timeout_s` | （屬性） | 上面三個怎麼等：閒著多久算不會停（1）、每幾秒印一行現況（10，0＝不印）、最多等幾秒（None＝不限，過了丟 `Timeout`） |
| `a.bp.why()`、`a.bp.held()` | 讀 `gdb/log.jsonl`、`gdb/hold.json`、`ctl.json` | 為什麼停：上次續之後的字條（觸發器 by `hook`、觀察者 by `watch`、`step`／`pause` 自己停的 by `step`／`pause`）、`.breakpoint`＝停在哪個 id、扣在哪、扣住後又來的 ctl pause／stop；字條的 ctl seq 跟現在對不上＝之後有人在 shell 下過 ctl，會說字條可能是舊的 |
| `a.bp.stopped()` | 讀 `gdb/hold.json`（handler 活著才算）、`state.json` 的 `paused` | 停著＝暫停已套用或扣住（看的是真的停住，不是字條） |
| `a.bp.notes()` | 讀 `gdb/log.jsonl` | 全部字條 |

錯誤只有一種 `Failed`（`from aos.py import Failed`）：指令失敗＝它自己的錯誤行原樣，`e.code`、`e.argv`、`e.exit` 拆好；庫自己拒絕＝一行說明。`aos-gdb` 裡每個呼叫先在 stderr 印出背後那條指令（`$ aos-agent ...`）；`aos.py.echo = False` 關掉。不用 `aos-gdb` 也行：任何 `python3` 把 `$AOS_HOME/lib` 放上 `sys.path` 就能 `from aos.py import agent`（那裡 echo 預設關）。

## 觀察者（丙）

`a.bp.add.watch(...)` 起的斷點：一支掛在 daemon 表上的普通 proc（名字 `gdbw_<id>`，號碼補零到 4 位，例 `gdbw_0002`；就是一個 aos-loop，每圈跑一次 `lib/tools/agent/gdb_watch`），每隔 `every_ms` 看一次每個目標，條件成立就 `ctl pause` 目標、在目標的 `gdb/log.jsonl` 留字條（`by: watch`）。完全不碰目標的定義與 hook。

- **為什麼掛在表上、不是 REPL 外的背景程式**：REPL 關了照樣在；`aos-daemon-ctl ls` 看得到、`rm` 停得掉；daemon 收工一起睡、重起一起醒；它自己壞了＝表上那一列 stopped 帶原因，目標照跑。
- **條件**：`py`＝函式 `f(t)` 或運算式字串（變數 `t`）。`t` 是那個目標的檢閱物件（跟 `a.look` 同一種：`t.name`、`t.stack`、`t.history(n)`、`t.observed(n)`、`t.where()`、`t.file(rel)`、`t.queue()`…），`t.mem` 是跨圈留著的 dict（存成 JSON），拿來看跨好幾格的事，例：

  ```python
  def new_tool_result(t):                 # only results that came after the last look
      h = t.history(0); seen = t.mem.get("n", len(h)); t.mem["n"] = len(h)
      return any(m.get("role") == "tool" for m in h[seen:])
  a.bp.add.watch(py=new_tool_result, every_ms=200)
  ```
  `sh`＝cwd 是目標的 stack、環境有 `GDB_TARGET`、`GDB_STACK`；退 0＝算、退 10＝不算。py 條件 20 秒沒回＝壞了。
- **一個看好幾隻**：`a.bp.add.watch(also=["bob"], sh=...)`（同一個 daemon），每隻各自數；`b.bp.ls()` 也看得到同一個 id。
- **防誤報**：`times`＝連續幾圈都成立才停；停過一次之後要先看到一次不成立才會再停（不然一個一直成立的條件會在每次續了之後馬上又停）；目標停著（暫停或扣住）的那幾圈不判。
- **壞了不拖垮目標**：條件丟例外／sh 退 1＝那圈不算、`a.bp.get(id)` 的 `per_target` 記 `last_error`、觀察者照跑；觀察者行程整個死掉＝表上那一列不是 running，目標照跑（實測）。
- **晚一格**：看到時事情已發生，停在下一格開頭；要「事前」停用觸發器（`a.bp.add.before_tool(...)`）。

## 檔與防呆

- 觸發器：`<stack>/hookeds/gdb_<id>/trigger.json`（`<id>` 是補零到 4 位的號碼，例 `gdb_0003`，或自己取的名字）（`how` 由事件定）、`count.json`（`pending`＝扣住被打斷的那一次、`decided`＝放行過的那一次）；字條：`<stack>/gdb/log.jsonl`（只往後加；`by` 是 `hook`、`repl`、`ctl`、`watch`）；扣住時 `<stack>/gdb/hold.json`、放行單 `gdb/release.json`；號碼計數器 `<stack>/gdb/next_id.json`（`{"next": N}`，鎖檔 `next_id.lock`）。
- hook 照名字的字典順序跑；號碼補零，所以同一事件上 `gdb_0002` 排在 `gdb_0010` 前面（號碼小的先扣住）。自己取的名字排在全部號碼後面（字母在數字後）。
- 觀察者：`<daemon>/procs/gdbw_<id>/watch.json`、`watch_state.json`、`watch_loop.json`（交給 `aos-daemon-ctl add` 的那份；同夾的 `loop.json` 是 daemon 自己寫的）。
- 觸發器是一個普通 hook（11-21 起 hook 沒有 `on_error`、`intercept` 這兩個選項）：handler `gdb_trigger` stdout 什麼都不印、自己壞了（讀不到設定、寫不了檔）只印一行 warning 並退 0，所以條件或 handler 壞了，agent 只多一行 warning，不會掛掉、不會被 daemon 連環重起；handler 什麼都擋不下工具。扣住型不限時（等人）；暫停型 15 秒（sh／py 條件 40 秒）。
- shell 這邊沒有對應的 `a.bp.*` 指令（要 `aos-bp ...` 還是 `aos-gdb bp ...` 待使用者裁，見[第二版紀錄末節](../../../../thinking/2026-11/19/aos-gdb-lib-第二版.md)；照 C-86 兩者都不進 `aos-agent`）。
- 沒做：一包現成觸發器（丁）、`on_clock`、eca 身（claude、codex 當腦）上的扣住沒測（before_tool 在 aos-mcp 裡跑，扣太久 CLI 那邊可能自己逾時）。
