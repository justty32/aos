# aos-gdb 的控制動作改成 IDE 那一組（11-19）：`a.bp.resume()`、`a.bp.step()`、`a.bp.stop()` 都不收參數、都等到停下才回並說停在哪；`wait_stopped`、`skip` 拿掉；aos-agent、daemon、hook 機制、cpp 沒動

← [2026-11-19](README.md)｜前一刀：[aos-pylib-施工](aos-pylib-施工.md)｜前兩版：[aos-gdb-lib-第二版](aos-gdb-lib-第二版.md)｜用法：[py/aos/apps/gdb/README](../../../py/aos/apps/gdb/README.md#控制resumestepstop照-idegdb)

線 `aosgdb-verbs-1119`。

## 使用者原話（11-19 選項框，逐字）

1. 題「「等 agent 停下來」這個方法要叫什麼？（現在是 a.bp.wait_stopped()）」→ 他自己寫：「我記得有step into還是啥的，參考那些ide」
2. 頂層接著問「參考 IDE 除錯器的話，斷點的控制動作我理解成這組：resume（繼續跑）、step（只走一格就再停）、stop（現在停）。那「等它停下來」要怎麼處理？」→ 選「resume/step 自己等到停」（選項說明：「像 gdb 的 continue：a.bp.resume() 放行後卡著，等到下次停下才回來，順便印出停在哪。不再有 wait 這個方法；按 Ctrl-C 只是不等了，agent 照跑。」），他選中的示意：
   ```
   b = a.bp.add.before_tool("write")
   a.say("write a note")
   a.bp.resume()      # 等到停在斷點才回來
   # stopped at before_tool_1 (write)
   a.bp.step()        # 走一格，又停
   a.bp.resume()      # 繼續，等下一次停
   ```
3. 題「「放行，但那次工具不跑」這個方法要叫什麼？（現在是 a.bp.skip()）」→ 他自己寫：「不該有這個方法。」
4. 題「建斷點時自己指定 id 的參數叫 id= 可以嗎？」→「可以，叫 id= (Recommended)」
5. 題「std 要不要留在入口頂層」→「留在頂層 (Recommended)」（現況就是，沒改）

稍早的原話仍有效：「a.resume()就是a.resume()，他的args不應該有東西」；「以斷點為核心，增刪改查」；「不要看的出來，兩者解耦合」（所以沒改 aos-agent／daemon）。

## 先講結論

| 動作 | 停著時（扣在斷點／暫停） | 沒停著時 | 回什麼 |
|---|---|---|---|
| `a.bp.resume()` | 扣住＝放行那一次（照原樣跑）；暫停＝`aos-agent ctl resume` | **什麼都不送**，只等 | 下一次停下時的 `why()`，第一行說停在哪：`stopped at before_tool_1 (write)` |
| `a.bp.step()` | 暫停＝`ctl resume`，loop 一套用就 `ctl pause --no-wait`；扣住＝先 `ctl pause --no-wait` 再放行（工具照跑、act 這一格做完才停） | `ctl pause --no-wait`（這一格做完就停） | 同上，第一行 `stopped after one step, before think` |
| `a.bp.stop()` | 什麼都不送，回 `already stopped ...` | `ctl pause --no-wait`，等到真的停下 | 同上，`stopped before idle (a.bp.stop())` |

三個都不收參數。回的是 `Why`（跟 `a.bp.why()` 同一種），多兩個欄：`.outcome`（`stopped`／`idle`／`gone`／`interrupted`）與 `.head`（第一行）。REPL 裡直接印出來就是「停在哪」加上原本 `why()` 的內容。

- **它不會停時**：閒著（`stage.txt` 是 `idle`、`queue/new` 與 `queue/cur` 都空、沒有還沒套用的 pause）連續 `a.bp.idle_s` 秒（預設 1）＝回 `ann did not stop: it is idle ...`；loop 行程不在（state.json 的 pid 死了：sleep、stop、rm）連續 `idle_s` 秒＝回 `did not stop: it is not running`。另外等的時候每 `a.bp.report_s` 秒（預設 10，0＝不印）在 stderr 印一行 `# a.bp.resume: still waiting for ann to stop (20 s): at wait, 0 letter(s) queued; Ctrl-C stops waiting, ann goes on`。`a.bp.timeout_s`（預設 None）給了才逾時、丟 `Timeout`，逾時前先把 step 自己送的 pause 收回。這三個是 `a.bp` 的屬性（類別上有預設、每個 `a.bp` 可以自己改），不是參數。
- **Ctrl-C**：只是不等了，agent 照跑，回 `stopped waiting (Ctrl-C); ann goes on as it was`。不留殘局：送指令那一小段先不理 Ctrl-C（記下來、送完再算不等了；送的指令另開 session，終端機的 Ctrl-C 打不到它），所以不會有「pause 送一半」；step 送出還沒套用的 pause 會收回（背景跑一條 `aos-agent ctl resume`）。`stop()` 例外：pause 已經送出、這一格做完它就停（要它停是使用者要的），回的話講明。
- **拿掉**：`a.bp.wait_stopped()`、`a.bp.skip()`；底層只為 skip 存在的都拿掉了：放行單 `release.json` 只剩 `token`（沒有 `go`、`text`）、`hold.json` 沒有 `skippable`、`trigger.SKIPPABLE` 沒了、handler 裡「印一句被跳過、退 10」那條路與 `skip_text`、`count.json` 的 `decided` 只剩 `key`（放行過的同一次再來＝照跑、不再扣）。扣住型的 hook 也改成 `--no-intercept`（本來讀回話只為了 skip 的退 10 擋得下工具；現在 handler 只退 0、什麼都不印，hold 照樣是同步的，實測扣得住）。`trigger.NO`（10）留著：sh 條件「退 10＝不算」還在用。全庫 grep 過，沒有別人用這些。

## 自己定的細節（照任務書「你定」）

1. **agent 不停時選「閒著就回來」為主、定期一行為輔**。理由：最常見的「不會停了」是做完事閒著（斷點拿掉、once 用完、條件不成立），這時馬上回來並說「沒停，已閒置」最不讓人卡住；但「還在跑、只是很久」（真模型想很久、工具跑很久）不能當成不會停，所以另印定期一行讓人知道它在哪一格、可以 Ctrl-C。兩者不衝突，都留。閒著要「連續 1 秒」才算：實測 `a.say` 之後有約 10 毫秒信已經從 new 搬到 cur、stage 還寫 idle，只看一瞬間會誤判；cur 也要空就分得開，再加 1 秒保險。
2. **沒停著叫 step＝送 `ctl pause --no-wait`、跑到這一格做完就停**（不報錯）。IDE 在跑的時候 step 按鈕是灰的；這裡跑著時「這一格做完就停」正是一格的意思，比叫人先 stop 再 step 少一步。
3. **stop 也等到真的停下才回、回停在哪**（跟 resume／step 一致）。改用 `ctl pause --no-wait` 自己等，不用 `ctl pause` 內建的 5 秒等：長的一格（工具跑很久）時也照樣等、能 Ctrl-C、有定期那一行。
4. **step 怎麼拼**（用現有機制，沒改 aos-agent、daemon）：
   - 暫停著：ctl 窗（`ctl.json`）一次只放得下一道指令，resume 跟 pause 不能一起寫。所以背景跑 `aos-agent ctl resume`，自己每 5 毫秒看 `state_flux.json` 的 `ctl_seq`，一追上 resume 的 seq（loop 已讀到 resume、這一格開始了）就馬上 `ctl pause --no-wait`。實測 `ctl pause --no-wait` 約 0.04 秒；loop 在一格開頭讀 ctl，所以 pause 在這一格中間到、下一格開頭套用＝剛好一格。
   - 扣在 before_tool：先 `ctl pause --no-wait`（扣著時寫 pause 不會放行，handler 只認 resume），再寫放行單；工具跑、act 這一格做完、下一格開頭停。這就是第二版紀錄的「扣著時被別人 pause：放行後工具照跑，那一格做完才停」。已經有一個還沒套用的 pause（先前的 step 或別人）就不再多送。
   - 跑著：`ctl pause --no-wait`。
   - **限制**：比 pause 送達還短的一格（約 0.04 秒內做完的，例如閒著時 idle 的一格）可能多走一格；跑著時 step 剛好碰上兩格交界（`stage.txt` 已寫下一格、loop 正在讀 ctl）＝pause 馬上套用、等於剛做完的那一格算一步（實測：看到 stage 變 act 就 step，回 `stopped after one step, before act`）；等腦時 `wait` 是一格接一格（`before wait` 會連著出現好幾次才到 `act`）；這一格裡碰到別的斷點（同一個 act 裡第二個工具也有 before_tool 斷點）＝停在那裡，step 送的 pause 還沒套用。那個 pause 之後才套用時，接著叫 `resume()` 會認出是自己先前送的（記在 `a.bp` 裡的 seq）、自動 `ctl resume` 收回、接著等，不會多停一次。
5. **怎麼認「新的一次停」**：開始時記 (扣住的 token, paused, `state_flux` 套用到的 ctl seq)，之後停著而且這三樣不一樣＝新的一次。所以「扣住→放行→同一格又被 pause」「暫停→resume→又被觸發器 pause」都認得出，不會把開始時那一次當成已經停了。
6. **step／stop 自己停下的留字條**（`by: step`／`by: stop`、`trigger: null`、帶那個 pause 的 ctl seq），`why()` 說 `ann is paused by a.bp.step()`；之前 `a.bp.stop()` 停的 `why()` 只會說「paused, with no note」。字條在停下之後才寫（放行時 handler 會寫一張 resume，字條要排在它後面才算這一次）。
7. **第一行的寫法**：扣住＝`stopped at <id> (<工具名或信名>)`；暫停型斷點與觀察者＝`stopped at <id> (<工具名／錯誤代號／信名／目標>), before <下一格>`；step＝`stopped after one step, before <下一格>`；stop＝`stopped before <下一格> (a.bp.stop())`；別人的 pause＝`stopped before <下一格> (paused, not by a breakpoint)`。暫停時 `stage.txt` 寫的是下一格，所以說 before。
8. `_shell.call` 多一個 `detach=`（指令另開 session）；`trigger._alive` 改公開成 `alive`（`a.bp` 拿來看 loop 行程在不在）。
9. **設定記在哪**：`a.bp` 每次取都是新的物件（把手的寫法，stack 每次重問），所以 `a.bp.idle_s = 5` 若只記在物件上，下一行的 `a.bp` 就看不到（實測第一次跑測試就踩到）。改成記在 `aos.gdb` 模組裡、以 (daemon, 名字) 為鍵：同一隻的每個 `a.bp`（含 `bp.attach("ann")`）共用設定，也共用「自己送出的 pause 的 seq」。設定值不對（`idle_s` 不是正數、`report_s` 負的、`timeout_s` 不是 None 或正數）當場 `Failed ArgumentsBad`。只活在這個 Python 行程裡，REPL 關了就沒了。

## IDE／gdb 的說法對照（只提案，沒改）

| 現在 | IDE／gdb 的說法 | 提案 |
|---|---|---|
| `a.bp.stop()` | VS Code 的 **Stop** 是結束除錯（殺掉被除錯的程式），「現在停」叫 **Pause**；gdb 是 `interrupt`（或 Ctrl-C） | **最值得改**：改叫 `a.bp.pause()`。用 IDE 的人按 stop 會以為是結束；而且 aos 自己的 `ctl stop` 也是「把 loop 停掉」，跟這裡的意思不同 |
| `a.bp.resume()` | VS Code Continue／gdb `continue` | 維持（使用者自己的字）；`continue` 是 Python 保留字也用不了 |
| `a.bp.stopped()` | gdb「程式停著」、DAP 的 `stopped` 事件 | 維持（跟 DAP 一致） |
| `a.bp.held()` | 沒有對應；IDE 叫「停在斷點上的那一個 frame」 | 可以不改；或改叫 `a.bp.hit()`（「斷點命中」是 IDE 的說法） |
| `a.bp.why()` | gdb `info program`（為什麼停）、`where`／`bt`（停在哪） | 維持；`where` 已經是 `a.look.where()`（停在哪一格） |
| `a.bp.rm(id)`、`a.bp.set(id, enabled=False)`、`a.bp.ls()` | gdb `delete`、`disable`／`enable`、`info breakpoints` | 維持（「增刪改查」是使用者的框；`set` 比 gdb 多改 times／once） |
| `a.bp.notes()` | 偵錯主控台的 log | 維持 |

## step into／step out（使用者提到、沒說對應 aos 的什麼，這刀不做）

可能的對應，給他挑要不要：
- **step into**：(甲) 進到這一格裡面：act 這一格有好幾個工具呼叫時一次走一個工具（每個工具跑之前停），用 before_tool 的扣住就做得到；(乙) 進到子 agent：這一格叫了 `subagent ask`，就跟進去停在子 agent 的下一格（要接上子 agent 的把手）。
- **step over**：就是現在的 `step`（一格當一步，不管格裡有幾個工具）。
- **step out**：(甲) 跑到這一輪結束（回到 idle、答完這封信）才停；(乙) 從子 agent 回到叫它的那一隻的下一格。
- 也可能他心裡的「一步」是「一次問腦到下一次問腦」（think→wait→act 一整圈），那是另一種 step。

## 測試

都在 `git archive` 乾淨複本（HEAD 疊上改動）install 後跑，暫存與測試樹都在 `~/.aos/scratch/aosgdb-verbs-1119/`（`TMPDIR` 指過去），環境先 unset 所有 `AOS_*`。四份合跑 **64 支全過**（約 180 秒）：

- `test_gdb_trigger` 29 支（不起 daemon）：handler 放行只退 0、不印東西；token 對不上不理；放行過的同一次再來不再扣；`before_queue` 扣住後放行照收信；`hold.json` 沒有 `skippable`、`trigger.SKIPPABLE` 沒了；`a.bp` 沒有 `skip`、`wait_stopped`，`resume`／`step`／`stop` 都只有 `self`；設定是屬性、同一隻共用、壞值當場擋；回的 `Why` 印出來第一行是停在哪；說明字串有三個動作、沒有舊名。
- `test_gdb_live` 18 支（假腦）：原本 13 支全改新寫法（`wait_stopped()` 換成 `resume()`，`skip` 那支換成 step），新增 5 支——`test_11` 沒停著時 resume 不送東西、只等到停（ctl seq 只多觸發器自己那一個）；`test_12` 不會停時：閒著回 idle、`timeout_s` 丟 Timeout、`ctl sleep` 後回 gone；`test_13` 另起子行程 `resume()`、送 SIGINT：回 interrupted、agent 照跑、沒有留下還沒套用的 pause；`test_14` act 這一格拖 6 秒時子行程 `step()`、送 SIGINT：pause 收回、agent 不停、答完信；`test_15` 一格一格 step 走完一輪（每一步都只往 fsm 下一格或 wait 自己再一格，最後停在 idle 前）。
- `test_aos_py` 13 支、`test_aos_py_live` 4 支（`_shell.call` 多了 `detach=`）照過。

親手在 `aos-gdb -d .stack ann`（假腦）打的幾行與畫面（指令回顯省略）：

```
gdb> b = a.bp.add.before_tool("peek_now_time")
gdb> a.say("write a note")
gdb> a.bp.resume()
stopped at before_tool_1 (peek_now_time)
ann is held at breakpoint before_tool_1: tool peek_now_time has not run yet; a.bp.resume() lets it go on as it was, a.bp.step() runs it and stops after this step
gdb> a.bp.step()
stopped after one step, before think
ann is paused by a.bp.step()
gdb> a.bp.step()
stopped after one step, before wait
gdb> a.bp.resume()
ann did not stop: it is idle (nothing queued, no step running); give it work (a.say(...)) and a.bp.resume() waits again
gdb> a.bp.stop()
stopped before idle (a.bp.stop())
gdb> a.bp.resume()
ann did not stop: it is idle (nothing queued, no step running); ...
```

施工中途（約 13:50）本線的暫存夾被刪掉（先是 `~/.aos/scratch/` 只剩 `aos-base-audit-1119`，幾分鐘後 `~/.aos` 整個不見），連同一棵正在跑的測試樹；不是本線刪的，誰刪的沒查到。本線留下的行程（cwd 指向已刪的夾）照自己的 pid 收掉，重建暫存重跑，上面是重跑的結果。

## 沒做的

- step into／out（見上）；`stop` 改名（見對照表）。
- eca 身（claude、codex 當腦）沒有 `stage.txt`，認不出閒著：只靠定期那一行與 `timeout_s`；eca 身上的 step 沒測。
- 觀察者看著時閒著照樣回「沒停」（觀察者之後才停它的話再 `resume()` 一次）；沒做「有觀察者就不認閒著」，因為條件可能永遠不成立、會一直卡著。
- 沒在 `~/repo/aos/proto8` 跑 `install.py`。

## 要使用者拍板的

1. `a.bp.stop()` 要不要改叫 `a.bp.pause()`（IDE 的 Stop 是結束除錯；aos 的 `ctl stop` 也是停掉 loop）？
2. step into／step out 要不要做、對應哪一種（上面甲乙）？
3. 閒著多久算「不會停了」先定 1 秒、定期那一行 10 秒一次，可以嗎？

## 使用者 11-19 下午的裁定（選項框，逐字）與跟著改的

1. 題「a.bp.stop() 是「現在讓 agent 停一下」。但在 VS Code 裡 Stop 是結束整個除錯，「停一下」叫 Pause；aos 自己的 ctl stop 也是把整隻停掉。要改名嗎？」→ 選「改 a.bp.pause() (Recommended)」。
   → `a.bp.stop()` 改名 `a.bp.pause()`，舊名不留（`a.bp.stop` 不存在）；字條 `by: pause`、`why()` 說 `ann is paused by a.bp.pause()`、第一行 `stopped before idle (a.bp.pause())`；README、help、banner、`knowledge/aos/cli/gdb.json`、`py/docs/05-commands.md`、測試一起改。只改這個動作的名字：`a.bp.stopped()`、`why`、`held`、輸出的 `stopped at …` 都沒動。上文各節保留當時的寫法（`stop`），以這一節為準。
2. 題「step into／out 要不要做？現在的 a.bp.step() 等於 IDE 的 step over（走一格）。」→ 選「先不做」。→ 不做；上面「step into／step out」一節的甲乙留作日後參考。
3. 題「等停下時的兩個數字：…閒著滿 1 秒…每 10 秒印一行狀態。可以嗎？」→ 選「可以 (Recommended)」。→ 維持 `idle_s` 1、`report_s` 10。

另：中途 `~/.aos` 被刪，是使用者本人刪的（他說反正之後要重建），不是事故。

