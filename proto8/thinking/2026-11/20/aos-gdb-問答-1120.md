aos-gdb 11-20 問答：使用者問 a.stop() 是不是阻塞、斷點 id 為什麼是 xxxx_1；只讀程式的快查結論、選項框四題與他的答案（逐字）、還沒問的題。

← [2026-11-20](README.md)｜昨天的材料：[aos-pylib-1119](../19/aos-pylib-1119/README.md)、[aos-gdb-動詞-1119](../19/aos-gdb-動詞-1119.md)、[aos-gdb-lib-第二版](../19/aos-gdb-lib-第二版.md)

## 使用者原話（11-20 上午，逐字）

> 還有，關於aos-gdb：1.a.stop()這塊，因為我們跑這個的時候，他可能還在某個fsm的狀態尚未結束，所以它是阻塞的吧？我在想，或許可以加上a.stop(wait=?)來選擇說是否要阻塞等待，如果不等的話就是返回一些東西讓你定期查詢他到底好了沒。2.為何產出了break point後，他是xxxx_1，而非直接給id，然後搭配屬性？3.

（訊息停在「3.」，第 3 點他沒打完。）

## 快查的結論

頂層派一隻 opus 只讀查證：**只讀程式與文件，沒有實跑**；行號以 HEAD `3a9b21d44` 的 `proto8/` 為準。標「推測」的是照程式推的。

### 第 1 點：a.stop() 與阻塞

- **把手上沒有 `a.stop`**，打了會報 AttributeError。把手 `Agent.__getattr__` 只認 `aos-agent` 的頂層子指令（`py/aos/py/agent/__init__.py:64-74`）；頂層子指令表裡沒有 stop／start（`py/aos/apps/agent/__init__.py:55-58`）。`a.start()`、`a.state` 也一樣不存在。
- **暫停是 `a.bp.pause()`**（11-19 從 `a.stop()` 改名來的）：送 `ctl pause --no-wait`，等到真的停下才回；已經停著就直接回；不收參數（`py/aos/gdb/__init__.py:423-431`）。
- **停掉是 `a.ctl.stop()`**（＝`aos-agent ctl stop`，「這一輪做完就停、stack 留著」，`apps/agent/ctl/phase.py:26-45`）：預設會等，等到 daemon 表上變成 `stopped`（`phase.py:181-186`），上限 `timeout_s` 預設 30 秒（`ctl/shared.py:9`）；逾時報 `WaitFailed`，那道 stop 不撤回（`shared.py:146-147`）。不等的版本已經有：`a.ctl.stop(no_wait=True)`，只回一行字 `stop accepted; X stops when this round ends`（`phase.py:176-180`），不回可以拿來查的東西。走 kernel 時（設了 `$AOS_KERNEL`、沒給 `--daemon`）本來就只看回信、不等表（`phase.py:165-168`）。
- **正在跑的那一格不會被打斷**：`aos-loop` 只在每一格的開頭讀 ctl（`cpp/aos-loop/src/engine/loop.cpp:171`、`:183-184`），身體跑的時候不看（`:218`）。daemon 的 stop 只是往 `ctl.json` 寫一道 `{"cmd":"stop"}`，沒有時間上限（`cpp/aos-daemon/src/daemon/tend.cpp:120-138`、`:161`）；會送訊號強制收掉的是 `sleep`／`rm`／daemon 收工（`tend.cpp:22`、`110-118`）。
  - 問腦（wait 格）：每拍一下就退，很快停（`templates/agent-fsm/wait.py:3`）。
  - 跑工具（act 格）：要等工具跑完或工具自己逾時。
  - **扣在斷點上（hold）：永遠停不了。** `gdb_trigger` 的 `hold()` 只認放行單或比扣住時間新的 `resume`，daemon 寫的 `stop` 它不理（`py/tools/agent/gdb_trigger/_entry:78-99`）；`ctl stop` 會一直等到 30 秒逾時。要先 `a.bp.resume()` 放行，或改用 `ctl sleep`。已寫在 `py/aos/apps/gdb/README.md:69`；設計稿 `aos-pylib-1119/05` 第 23 條記「不特別處理」，這是設計者定的，不是使用者。
- 重複下 stop：已經 `stopped` 的印 `already stopped`、退 0（`phase.py:171-173`）；還在 `stopping` 的不再寄信、只再等一次（`phase.py:184-185`）。

### 把手上「會等」的動作

| 動作 | 背後 | 阻塞？等什麼 | 逾時 | 回什麼 |
|---|---|---|---|---|
| `a.say(x)` | `aos-agent say` | 不等回答，只寄信（`apps/agent/say.py:3-9`） | 無 | 信名 str（`py/agent/__init__.py:37-40`） |
| `a.listen(...)` | `aos-agent listen` | 等回答 | `timeout_s=`，預設不限（`listen.py:22`） | 回答文字 |
| `a.ctl.stop()` | `ctl stop` | 等表上 `stopped` | `timeout_s=` 預設 30 秒；`no_wait=True` 只等 daemon 收下 | 一行字 |
| `a.ctl.start()` | `ctl start` | 等表上不是 `stopped`（`phase.py:140-151`） | 30 秒 | 一行字 |
| `a.ctl.pause()` | `ctl pause` | 等 loop 套用，上限 5 秒（寫死），到了只印 warning（`daemon_ctl/ctl.py:60,164-179`）；`no_wait=True` 寫了就回 | 5 秒 | 一行字 |
| `a.bp.resume()` | 放行或 `ctl resume` | 等「下一次停下」 | 屬性 `a.bp.timeout_s`，預設不限；閒著連續 `idle_s`（1 秒）或行程不在就回「沒停」 | `Why` 物件，`.outcome` 是 stopped／idle／gone／interrupted（`gdb/__init__.py:387-399, 664-710, 775-783`） |
| `a.bp.step()` | `ctl pause --no-wait` | 等走完一格停下 | 同上 | 同上（`:401-421`） |
| `a.bp.pause()` | `ctl pause --no-wait` | 等真的停下 | 同上 | 同上（`:423-431`） |
| `a.bp.rm(watch id)` | `aos-daemon-ctl rm` | 等表上沒了 | 10 秒 | 指令輸出（`:298-305`） |

`wait_stopped`、`skip` 已拿掉。

現成能查「好了沒」的：`agent.ctl.ls(json=True)`（每列有 phase 與 `busy`）、`a.ctl.state("state", json=True)`；`a.bp.stopped()` 只認暫停或扣住，不認 `stopped` phase（`gdb/__init__.py:438-441`）。

### 哪些是使用者裁的、哪些是施工線自己定的（第 1 點）

- **使用者裁的**：resume 不收參數——原話「a.resume()就是a.resume()，他的args不應該有東西」；resume／step 等到停才回——選項框選「resume/step 自己等到停」（出處 [aos-gdb-動詞-1119](../19/aos-gdb-動詞-1119.md)）。
- **施工線自己定的**：pause（原名 stop）也等、也不收參數；等待設定做成屬性 `idle_s`／`report_s`／`timeout_s` 而不是參數。使用者後來只點頭「1 秒、10 秒可以」與選了改名「改 a.bp.pause()」。

### 第 2 點：斷點 id 為什麼是 xxxx_1

- **回什麼**：`a.bp.add.before_tool("write")` 回普通字串 `"before_tool_1"`，觀察者回 `"watch_1"`（`gdb/__init__.py:252, 291`）；`id="mine"` 可以自己取名（`:170, 200`）。
- **怎麼編**：`_free(on, have)` 從 1 往上找第一個沒人用的「種類_N」（`:843-847`）。沒有存計數器，每次當場掃這隻 agent 的觸發器小格加上整個 daemon 上的觀察者（`:248, 273, 491-512`）。被 `rm` 的只標成 `removed`、掃的時候不算（`:306-309`、`:503`），所以**刪掉的號碼會被重用**，計數也歸零（`:282`）。這個洞設計稿已記（`aos-pylib-1119/01` 第 4 節第 10 點、`05` 第 28 條）。
- **id 用在哪**：hook 名＝`gdb_` + id（`gdb/trigger.py:48`、`gdb/__init__.py:528`）；小格在 `<agent stack>/hooks/gdb_<id>/`（`trigger.json`、`count.json`，`:462-463`）；觀察者的 proc 名是 `gdbw_<id>`。
- **使用者裁的**：回字串——原話「a.stop(), a.stop.before_tool()，像這種，他會返回一個斷點id(string)」（[aos-gdb-lib-第二版](../19/aos-gdb-lib-第二版.md) 第 131 行）；參數名 `id=`——選項「可以，叫 id= (Recommended)」。
- **施工線自己定的**：「種類_N」這個格式。第一版 commit `2173a4ecc`（線 aosgdb-lib-1119）就寫了，沒有講理由，查不到問過使用者的紀錄。
- **程式上的限制**（都不是非「種類_N」不可）：hook 名只要求非空、不含 `/`、不以 `.` 開頭（`apps/agent/hook.py:224`）；hook 照名字的字典順序跑（`hook_run.py:191, 198`），所以名字決定同一事件上誰先扣，`_10` 排在 `_2` 前面；觀察者是整個 daemon 一份、觸發器是一隻 agent 一份，編號要躲開兩邊。
- **屬性現在怎麼查、怎麼改**：`a.bp.ls()` 一個斷點一列（`id, kind, on, how, about, enabled, times, once, seen, streak, fired, spent, last_error, here`，`:364-370, 541-557`）；`a.bp.get(id)` 多 `tools`、`condition`（`:372-384`）；`a.bp.set(id, enabled=, times=, once=)` 只能改這三樣（`:318-361`）。
- （推測）改格式只動 `aos.gdb` 這一層，hook 機制、daemon、`aos-agent` 不用動；文件、教學 06 之三、README、測試寫著現在的格式，要跟著改。

## 選項框四題與答案（11-20 上午）

題目、選項標籤、後果說明是選項框當時的原文；「使用者答」是他選的標籤或他在 Other 打的字，逐字。

### 第 1 題

題目：「你說想加 wait= 的 a.stop()，指的是哪一個？（把手上現在沒有 a.stop；暫停是 a.bp.pause()，昨天從 a.stop() 改名來的；停掉是 a.ctl.stop()，已經有 no_wait=True）」

| 選項 | 後果說明 |
|---|---|
| 暫停 a.bp.pause() | 給 pause 加 wait=。會碰到你昨天那句「args不應該有東西」（那句講的是 resume）；resume、step 要不要跟著加得一起定。 |
| 停掉 a.ctl.stop() | 它已經有 no_wait=True，只是不等的時候只回一行字。要做的只剩「不等時回什麼」。 |
| 兩個都要 | 暫停與停掉都能選等或不等，寫法一致；改動最多，resume、step 要不要跟著加也要定。 |
| 先不動 | 維持現狀，只留紀錄。 |

**使用者答：「暫停 a.bp.pause()」**

### 第 2 題

題目：「選「不等」的時候，要回什麼給你？」

| 選項 | 後果說明 |
|---|---|
| 回一個可以查的物件 | 例如有 .done() 可以定期問好了沒。要另外定它查的是什麼，以及最後沒停成時（扣在斷點上、工具卡住）怎麼說。 |
| 照舊回一行字 | 要查好了沒，自己用現成的 a.ctl.ls(json=True) 或 a.bp.stopped() 看。不用改程式。 |
| 先不定 | 等上一題定了再說。 |

**使用者答：「回一個可以查的物件。用is_done()」**

### 第 3 題

題目：「斷點的 id 要長什麼樣？（現在是「種類_流水號」的字串，例 before_tool_1；這個格式沒問過你，而且刪掉的號碼會被重用）」

| 選項 | 後果說明 |
|---|---|
| 純數字、不重用 | 像 gdb。要存一份計數器；hook 名會變成 gdb_3，從名字看不出是哪一種；文件、教學、測試要跟著改。 |
| 維持字串、改成不重用 | 格式照舊，一看就知道是哪一種；只補上「刪了不再拿來用」，也要存一份計數器。 |
| 維持現狀 | 什麼都不改；刪掉的號碼照舊會被重用、計數歸零。 |

**使用者答（在 Other 打的，是一句反問）：「不能純數字，然後搭配id、屬性(hook點種類)嗎？」**

頂層的解讀：他要純數字 id，種類放在屬性；刪了重不重用他沒說，待確認。

### 第 4 題

題目：「a.bp.add.<種類>(...) 要回什麼？（現在回字串，出處是你昨天的話「他會返回一個斷點 id (string)」）」

| 選項 | 後果說明 |
|---|---|
| 回物件、帶屬性 | 例如 bp.id、bp.kind、bp.enabled。要定它是當下的快照還是每次重讀；rm、set、get 也要能收這個物件。 |
| 照舊回 id | 屬性用 a.bp.get(id) 查。不用改。 |

**使用者答：「回物件、帶屬性」**

## 還沒問的

- `a.bp.resume()`／`a.bp.step()` 要不要跟著 `pause` 加 `wait=`（會碰到「args不應該有東西」那句）。
- 扣在斷點上時下 stop 怎麼辦（現在永遠停不了，要先放行）。
- `a.bp.add` 回的物件是當下的快照，還是每次重讀。
- 純數字 id：刪了重不重用、計數器存哪、跟 `id=` 自己取的名字怎麼共存。
- `proto8/py/aos/agent_spec.py:60` 的 `--help` 還寫動態連結的包多加的工具「shows up at the agent's next start」，骨架 README（`templates/agent-python/README.md:150`）已改成每次問腦前讀；這句沒改。
- 以上都還沒派線施工。
