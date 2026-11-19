# aos-gdb 第二版（11-19）：`stop_before_tool` 改成真的在工具跑之前停住、續了照原樣跑（觸發器在 hook 裡自己扣住等放行），另做了丙（掛在 daemon 表上的觀察者 proc）；hook 機制與 cpp 都沒動，假腦實跑 12 個情境過

← [2026-11-19](README.md)｜上一版：[aos-gdb-lib-第一版](aos-gdb-lib-第一版.md)｜調查：[aos-gdb-1119](aos-gdb-1119/README.md)｜用法：[py/aos/apps/gdb/README](../../../py/aos/apps/gdb/README.md)

線 `aosgdb-lib2-1119`。使用者原話（被問「stop_before_tool 預設要不要直接擋下那次工具？」「丙要不要接著做？」）：「stop_before_tool不就是在工具開始前停下嗎？丙可以繼續」；斷點＝「特定條件發生時，暫停loop或fsm，停下來等待檢閱」，「能把他停下來的都可以」，條件也可以「另外開個proc，觸發之後直接把要debug的那個proc停下來」，「hook不用動」。

## 先講結論

1. **做到了，沒改 hook 機制、aos-agent、daemon、cpp。** 方法：`before_tool` 的觸發器條件成立時，handler 自己**不回**（hook 本來就是同步跑、`timeout_ms 0` 就不限時），把自己「扣住」的事寫進 `<stack>/gdb/hold.json`，每 0.2 秒看有沒有放行單。工具這時還沒跑；`a.resume()` 放行＝退 0，**那次工具照原樣跑**；`a.resume(skip=True)`＝退 10，那次不跑、腦收到「skipped at a breakpoint」。在 shell 打 `aos-agent ctl resume` 也放行（照跑）。
2. **名字對齊意思，一個名字一種停法、由事件決定**：`before_tool`、`before_queue`（事件還沒發生）＝扣住；其他（`after_tool`、`brain_failed`…）＝第一版的 ctl pause（那一格做完停）。第一版的 `block=True` 拿掉（改成續的時候選 skip）；「工具跑完才停」改名 `stop_after_tool`（停在結果進了 history、腦還沒看到）。`stop_on_tool_error`、`stop_on_brain_failed` 本來就名副其實（事件已發生、停在下一格開頭），沒改。
3. **丙做好了**：觀察者是一支掛在 daemon 表上的普通 proc（`gdbw_<名>`，就是一個 aos-loop、每圈跑一次 `gdb_watch`），輪詢目標的檔，條件成立就 `ctl pause` 目標、留字條 `by: watch`；`why()` 認得「paused by watcher gdbw_w1」。條件可以是 Python 函式（拿到目標的檢閱物件 `t`，`t.mem` 跨圈留著，看得到跨好幾格的事）或 shell；一個觀察者可以看好幾隻；`times` 連續幾圈才算、停過要先看到一次不成立才會再停（防誤報）。
4. **限制**（都實測）：扣住時 daemon 表與 `ctl state` 照寫 `running`（它卡在 act 那一格裡），只有 `aos.gdb` 認得是停在斷點；扣住時 `ctl stop` 要等放行才停（`ctl stop` 指令一直等）；觀察者晚一格。

## (一) 怎麼查出做得到（實測，`~/.aos/scratch/aosgdb-lib2-1119/exp1.sh`）

先用一支十行的 bash hook（等一個檔出現才結束）掛 `before_tool`、`timeout_ms 0`，在 start-api 樹假腦實跑：

| 情境 | 結果 |
|---|---|
| 扣住時看 | `stage.txt`＝act；`state.json` running、不 paused；`aos-agent ctl ls` 與 daemon 表都 running；history 最後一則是腦要叫工具的那則、沒有工具結果 |
| 扣住時再 say | 信進 `queue/new`，放行後照處理 |
| 放行（退 0） | 工具真的跑（結果是當下時間），答案正常 |
| 放行（退 10、印一句） | 工具不跑，腦收到那句（hook 預設讀回話，所以退 10 擋得下） |
| 扣住時 `ctl pause` | 照扣；放行後工具跑完、這一格做完才停（stage think） |
| 扣住時 `ctl stop` | 表上 `stopping`，`ctl stop` 一直等（被 15 秒逾時收掉）；放行後工具跑完才 stopped |
| 扣住時 `ctl sleep`（TERM） | hook 行程被收掉、**工具沒跑**；`wake` 後 act 重跑、同一個工具呼叫（同一 id）再叫一次 `before_tool` |
| 扣住時 daemon `shutdown` 再起 | 同 sleep |

所以「hook 自己等」這條路成立，限制只有「外面看不出它停了」（hook 機制沒有回報「我在等」的地方，要改就得動 aos-agent 或 hook 機制，沒動）。

## (一) 做法細節

- handler（`lib/tools/agent/gdb_trigger`）扣住時：寫 `gdb/hold.json`（token、自己的 pid、事件摘要、當下 ctl seq、能不能 skip），字條記 `how: hold`；每 0.2 秒看 ① `gdb/release.json` 的 token 對得上（`run`／`skip`），② `ctl.json` 出現比扣住時新的 `resume`，③ 父行程換人（那一格死了）；收到 TERM／HUP／INT＝那一格被收掉。②③與訊號都不算放行：留一張 `hold_ended`，`count.json` 的 `pending` 留著那次的工具呼叫 id——**同一個 id 再來時直接再扣住**（不再判條件、`once` 也照扣），放行後才清掉。所以 sleep／重起之後工具不會不經檢閱就跑掉，也只跑一次（實測）。
- 掛 hook：扣住型 `--timeout-ms 0`、讀回話（skip 的退 10 才有用；handler 平常什麼都不印）、`--on-error continue`；暫停型照第一版（有上限、`--no-intercept`）。
- `before_queue` 也扣住（信還沒進 history），但不給 skip（跳過＝那封信丟了）；給了 skip 會照收、stderr 一行 warning。
- 庫：`a.held()`（讀 hold.json，handler 活著才算）、`a.is_paused()`／`wait_paused()` 都把扣住算停著、`a.why()` 說扣在哪個工具、能不能 skip、扣住後有沒有人下 ctl pause／stop（「放行後這一格做完它會停」）。`a.resume()` 扣住時寫放行單並等 handler 收到；`say` 回信名、`listen(letter=...)` 等那一封。
- 拿掉觸發器（`a.remove`）不影響正扣著的那一次。

## (二) 觀察者：為什麼選「掛在 daemon 表上」

| | 掛在表上（選這個） | REPL 外的背景程式 |
|---|---|---|
| REPL 關了 | 照樣在 | 要自己 daemonize、記 pid |
| 看得到、停得掉 | `aos-daemon-ctl ls`、`rm`（先停、等退出、再拿掉） | 要另寫 pid 檔與收法 |
| daemon 收工／重起 | 一起睡、一起醒 | 變孤兒或要自己偵測 |
| 自己壞了 | 表上那一列 stopped 帶原因；條件壞了只記 `last_error` | 默默消失 |
| 代價 | 每圈起一次 python（約 0.1～0.3 秒），所以「每 0.2 秒」實際一圈約 0.3～0.5 秒 | 同一個行程裡迴圈，便宜 |

小坑（已避開）：proc 的 stack 裡 `loop.json` 是 daemon 自己寫的那份，自己的設定要另取名（`watch_loop.json`），不然會被蓋掉、起不來。

## 介面改了哪些名字

| 第一版 | 第二版 |
|---|---|
| `stop_before_tool(tool, block=False)`：那一格做完才停（工具照跑） | `stop_before_tool(tool)`：**工具跑之前扣住**；`block` 拿掉 |
| `block=True` | `a.resume(skip=True, text=None)`（續的時候選） |
| （沒有） | `stop_after_tool(tool)`：工具跑完、腦看到結果之前停 |
| `stop_when(..., block=)` | `stop_when(...)`：停法由事件定（trigger.json 多 `how`） |
| `is_paused()`＝ctl paused | 加上扣住；新 `held()` |
| `listen(timeout_s)` | `listen(timeout_s, letter=None)` |
| 字條 `blocked` | 字條 `how`、`again`；新種類 `hold_ended`；`by` 多 `ctl`、`watch` |
| （沒有） | `a.watch()`／`g.watch(targets, daemon=)`、`watchers()`、`unwatch()`；新模組 `aos.gdb.watcher`、新本體 `lib/tools/agent/gdb_watch` |

## 測試（公司 WSL，`git archive` 乾淨複本疊改動、清 `AOS_*`、install 後跑；暫存 `~/.aos/scratch/aosgdb-lib2-1119/`）

- `test_gdb_trigger.py` 22 個全過（不起 daemon）：多了放行過的同一呼叫回來照上次決定、扣住前就在的舊 resume 不放行、 hold 放行 run／skip、token 對不上不理、shell ctl resume 放行（別人的 pause 不放行）、TERM 留 pending 且同一次再來照扣（once 也扣、別的呼叫不扣）、信不能 skip。
- `test_gdb_live.py` 12 個全過（約 90 秒，假腦真 daemon）：
  - 01 扣住→看（工具結果不在、stage act、表 running、信照收）→拿掉觸發器→續→**工具真的跑了**（結果是時間）、兩封都答。
  - 02 skip＋once：腦收到 skipped、之後不再停。
  - 03 扣著時別人 `ctl pause`：`why()` 說放行後會停；放行後工具跑了、停住、`why()` 說「沒有字條」（是別人停的）；shell resume 答完。
  - 04 扣著時 `ctl sleep`：handler 沒了、工具沒跑、字條 hold_ended；`wake` 後同一呼叫再扣住（`again`）；放行後只跑一次。
  - 05 shell `ctl resume` 放行：照跑，字條 by ctl。
  - 06 `stop_after_tool`：停在 think、結果已在 history。07 連錯兩次才停。08 條件壞了不停不掛。09 shell 續了又停＝字條舊了。
  - 20 觀察者（py，用 `t.mem` 記上次看到幾則、只看新的工具結果）停住 ann：字條 by watch、trigger gdbw_w1、`why()`「paused by watcher」、`aos-agent ctl ls` 顯示 paused。
  - 21 條件壞了：目標照答、觀察者照跑、`last_error` 有字；SIGKILL 觀察者行程（測試自己起的那支）：目標照答；另起一支再 `unwatch`：行程沒了、表上沒了。
  - 22 一個觀察者看 ann、bob（sh，cwd＝目標 stack）、`times=3`：只停 bob、約 0.6 秒以上才停；續了條件還成立不再停，看到一次不成立後再成立才又停。
- 順手跑既有的 `test_install`、`test_hooks_engine`、`templates/tests/test_paths_move`、`apps/agent/test_hook`：全過。
- `aos-gdb` 本身：stdin 餵一輪（扣住、why、history、remove＋resume、listen、watch、why、watchers、unwatch）照預期；`--help` 英文。

## Argon 審（做完後送一次，A1～A10）與採納

提示＝設計摘要＋handler 扣住段、觀察者一圈、庫的 resume／why 原文（Windows agy 檔案法，一次過）。沒有一條推翻「在 hook 裡扣住」或「觀察者掛在表上」；照它改了下面這些，改完單元與實跑測試重跑全過。

| 點 | 它說 | 採納 |
|---|---|---|
| A1 一定要改 | skip 放行後寫檔失敗會走 die（退 1）→ on_error continue → 工具照跑；skip 後那一格被收掉，重跑同一呼叫時 pending 已清，工具真的跑 | 採納：放行後寫檔失敗只 warning、skip 一定退 10；count.json 記 `decided`（key＋run／skip），同一呼叫回來照上次的決定（skip 再退 10、run 不再扣） |
| A2 一定要改 | 由 REPL 事後補寫 resume 字條會排在下一個觸發器的 stop 後面、把它吃掉；handler 被收掉時 a.resume() 誤報放行成功 | 採納：resume 字條由 handler 自己寫（帶 token），寫完才刪 hold.json；a.resume() 只認同 token 的 resume，看到 hold_ended＝丟 Failed |
| A3 一定要改 | 扣住被收掉後 once 已用掉；pending 的那次沒再回來就永遠卡著 | 採納：沒放行＝fired 減回去；pending 跟這次的 key 不同＝清掉。「扣著時 remove 觸發器」維持現行（小格留著，那一次照扣到放行，已寫進 README） |
| A4 一定要改 | 跑條件時父行程就死了，getppid 記到 1、永遠不放；寫字條到接訊號之間有空窗 | 採納：main 一開頭就記父行程，是 1 或已換人就不扣；先接訊號再寫字條與 hold.json |
| A5 一定要改 | ① 讀不到 seq0 時舊的 resume 會誤放行；② 扣住前就有沒套用的 pause，pending 漏報；③ 暫停型用 shell resume 不會寫 resume 字條 | ①採納：改看 ctl.json 的修改時間要晚於扣住；②採納：pending 改成「ctl.json 的 seq 比 state_flux 已套用的新」；③不採納：要攔 shell 指令才寫得了字條，維持第一版的「字條可能是舊的」提示 |
| A6 一定要改 | 觀察者 pause 失敗也先算 fired、armed=false，之後不再試 | 採納：pause 成功才算 |
| A7 一定要改 | 發了 pause、那一格還沒做完時觀察者還在判，會重複發 pause、提早上膛 | 採納：目標有沒套用的 pause／stop 也當停著、不判 |
| A8 一定要改 | stack 快取不更新，目標 rm 又加回來會看舊 stack、停新的 | 部分採納：每 20 次判斷或 stack 夾不見時重核，換了就重置該目標的數與 mem（不每圈重核：每圈多一支 aos-agent 太貴） |
| A9 建議 | 字條的 stage 是 pause 之後才讀的 | 採納：判中那一刻記下 |
| A10 建議 | stop_after_tool 是「那一格做完」，腦一次叫多個工具時後面的照跑；扣住時有沒套用的 pause，一次 resume 解不開 | 採納：docstring 寫清楚；a.resume() 的回話會說「then it pauses」 |

## 要重建什麼

`py/` 的改動與兩個新檔（`py/aos/gdb/watcher.py`、`py/tools/agent/gdb_watch/_entry`）；任何一棵樹要用，在那份 proto8 重跑 `python3 install.py`（活樹 `~/aos-home` 沒碰、沒裝）。持久格式：`trigger.json` 多 `how`、少 `block`（proto8 當沒有舊版：第一版下的觸發器要重下）。

## 沒做的

- 丁（一包現成觸發器）：任務書說不做。
- 讓表上看得出「停在斷點」：要改 aos-agent 或 hook 機制，沒動；使用者 11-19 裁定不做（兩者解耦合，見下面「已裁」）。
- eca 身（claude、codex 當腦）上的扣住沒測：before_tool 在 aos-mcp 裡跑，扣太久 CLI 那邊的 MCP 呼叫可能自己逾時。
- 扣著時 daemon 重起只用第一輪 bash hook 測過（同 sleep 的路），正式測試只測 sleep／wake。
- `on_clock` 觸發器。

## 要你拍板的（不急，試過再說）——兩題 11-19 都已裁，見下一節

1. **（已裁：a 不動）扣住時表上要不要看得出來？** 現在 `aos-agent ctl ls`、daemon 表寫 `running`，只有 `aos.gdb`（`a.why()`、`a.is_paused()`）認得。
   - a（現在）：不動。好處是 hook 機制、aos-agent 一個字沒改；代價是只用 shell 的人看不出它停在斷點（`stage.txt` 是 act、一直不動）。
   - b：讓 `aos-agent ctl state`／`ctl ls` 讀 `gdb/hold.json`，顯示 held。代價是 aos-agent 要多認一個 aos-gdb 的檔（小改，不動 hook 機制與 cpp）。
2. **（已裁：a 維持）sh 條件「不成立要退 10」要不要放寬成「退 1 也算不成立」？** 現在照 N-43：0＝算、10＝不算、其他＝條件壞了（只 warning、不算）。所以 `grep -q x`、`test -f x` 不成立時退 1 會被當成「壞了」，要寫 `|| exit 10`。
   - a（現在）：照 N-43，寫錯一眼看得到（`last_error`）。
   - b：退 1 也算不成立。好寫，但真的壞掉（例如指令打錯退 127 以外的 1）會被當成「沒中」。

## 已裁（使用者 2026-11-19）

原話：「卡在斷點時，表上要不要看得出來？ <- 不要看的出來，兩者解耦合。2.維持。」

1. **第 1 題＝a 不動。** 理由是「兩者解耦合」：aos-agent 與 daemon 不知道 gdb 的存在，扣住時 `aos-agent ctl ls`、`ctl state`、daemon 表寫 `running` 是**刻意的**，不是缺漏；要看是不是停在斷點，用 `aos.gdb` 的 `a.why()`／`a.held()`。之後的線也守這條：不讓 aos-agent、daemon 去讀 `gdb/` 底下的檔。已寫進[用法](../../../py/aos/apps/gdb/README.md)與知識庫 `knowledge/aos/cli/gdb.json`。
2. **第 2 題＝a 維持 N-43**：sh 條件退 0＝成立、退 10＝不成立、其他＝條件壞了（只 warning、記 `last_error`）。`grep -q`、`test -f` 照舊要寫 `|| exit 10`。

目前沒有待使用者拍板的題。
