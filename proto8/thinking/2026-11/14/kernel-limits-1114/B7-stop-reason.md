# B7 after_stop 帶停止原因（wf/advices「after_stop 事件分不出是 stop、sleep 還是 rm」）

← [kernel-limits-1114](../kernel-limits-1114.md)

ok-limits 11-14 設計。頂層派的工作是修 wf/advices 的 daemon 類小條，這是其中一條（提出者 ok-kf）。

## 0. 現況

- `ctl stop`：daemon 寫子項的 ctl 窗（`halt`），loop 看到 `stopping_` 就以 `end(0,"stopped")` 收工。
- `ctl sleep`、`ctl rm`、daemon 收工、卡住重起：daemon 一律走 `term(c)`，送 SIGTERM。loop 收到後以 `end(128+15,"stopped")` 收工。
- on_stop 的環境變數只有 `AOS_LOOP_CODE` 和 `AOS_LOOP_SIGNAL`，所以 hook 分不出 sleep 和 rm，也分不出 stop 和「跑滿 max」。

## 1. 做法：daemon 先寫一個原因檔，再送 SIGTERM

不用 sigqueue 帶值。原因有二：
- loop 收訊號的地方有好幾處（folder.cpp 的 signalfd、inline、aos-util 的 take_signal、nap 的 sigtimedwait），要每處都改；
- 中間隔著 sudo 這類會轉送訊號的程式時，帶的值會丟掉。

### 1.1 新窗：`<stack>/stop_reason.json`

- 放在 `aos/loop.hpp`，比照 CtlWindow 定一個 `StopReasonWindow`：`default_name = "stop_reason.json"`，名字固定，不開設定鍵。
- 內容：`{"reason": "<值>", "at_ms": <epoch 毫秒整數>}`。
- 由 daemon 寫，loop 只讀。誰都不刪（鐵律不刪檔），舊檔靠 `at_ms` 判斷失效（見 1.3）。

### 1.2 daemon：`term(c)` 改成 `term(c, reason)`

- `c.stack` 底下有 loop 設定檔（`names_.loop`）時，才寫 stop_reason.json（用 write_window 或同等的原子寫法），然後照舊送 SIGTERM。
- 沒有 loop 設定檔的 exec 列不寫，免得在別人的 stack 留下多的檔。
- 寫不了：印一行 warning `cannot write the stop reason of NAME (CODE msg)`，SIGTERM 照送。原因只是資訊，不擋收工。
- 各呼叫處給的 reason：

| 呼叫處 | 情況 | reason |
|---|---|---|
| reconcile.cpp `!in` | 從表上拿掉（ctl rm、daemon.json 沒了它） | `remove` |
| reconcile.cpp `nap` | ctl sleep | `sleep` |
| reconcile.cpp stop 途中又收到 sleep 或 rm | 升級成 SIGTERM | `!in` 時給 `remove`，否則給 `sleep` |
| tend.cpp `finish()` | daemon 收工 | `shutdown` |
| stuck.cpp | 卡住重起 | `stuck` |
| adopt.cpp 接回 stopping 的列 | 照 stop_mode | `sleep` 給 `sleep`；其他走 term 的給 `remove` |

- `remove`、`sleep` 和表上 `stop_mode` 的值同名。stop_mode 的 `stop` 不走 term，不用寫原因檔，loop 自己知道。

### 1.3 aos-loop：收工時判斷原因

- `main_loop` 一開始，在 on_start 之前，記下 `started_ms_`（epoch 毫秒）。
- 在 `end()` 和 `serve()` 的錯誤路徑裡，`stop_side` 之前，算出 reason，交給 run_side 設成 `AOS_LOOP_REASON`（跟 CODE、SIGNAL 一樣，跑完還原）：

| 怎麼結束 | reason |
|---|---|
| 收到訊號（`got_ != 0`，或 `128+N` 那幾條路），而且 stop_reason.json 可讀、reason 是 `remove`／`sleep`／`shutdown`／`stuck` 之一、`at_ms >= started_ms_` | 檔裡的值 |
| 收到訊號，但上一格不成立（人手 kill、檔是舊的、壞的、值不認得） | `signal` |
| `stopping_`（ctl 窗的 stop） | `stop` |
| 跑滿 max（有身體或沒有身體都算） | `max` |
| 身體退 10 | `body_exit` |
| 身體退其他非 0、run_once 丟錯、tend 丟錯、serve 接到例外 | `error` |

- 判斷 `at_ms >= started_ms_`：上一輪留下的舊檔一定比這一輪的 loop 早寫，所以不會被拿來用。不比 pid，因為 bwrap 有自己的 pid namespace，pid 對不上。
- 只有「收到訊號」時才讀這個檔。loop 自己退的時候，就算 daemon 剛好寫了檔，也照 loop 自己的原因。
- 讀檔失敗不印 warning，直接當 `signal`。

### 1.4 hook_fire

- after_stop 事件多一欄 `reason`：取 `$AOS_LOOP_REASON`，去掉頭尾空白；空的或沒設就是 null，舊的 aos-loop 也相容。
- 值不檢查，照抄。說明裡列出可能的值。

## 2. 文件

- `impls/aos-loop/include/aos/loop.hpp`、`docs/01-用法.md`、README：新窗和 AOS_LOOP_REASON。
- `impls/aos-daemon` 的 docs：term 之前先寫原因檔。只補一兩行，放在講 stop_mode 或 sleep／rm 的那節。
- `lib/agent/hook_fire/_entry`：檔頭、HELP。
- `lib/agent/self_hook/_tooldef.json`：after_stop 的欄位寫成 `(code, signal, reason: stop|sleep|remove|shutdown|stuck|signal|max|body_exit|error, or null)`。
- `lib/docs/03-索引-agent等.md`：hook_fire 那列。
- `templates/docs/02-agent-fsm.md`、`templates/agent-fsm/README.md`：有寫 after_stop 欄位的地方。
- 不動 screen_linger（ok-kf 的消費者）。用不用 reason 由 ok-kf 決定，我在信裡告訴他們。

## 3. 測試（暫存樹，經 clean.sh 跑）

- aos-loop `tests/test_on_start_stop.py`，加 6 項：
  - ctl 窗 stop → `stop`；
  - max → `max`；
  - 身體退 10 → `body_exit`；
  - 身體退 3 → `error`；
  - 寫一份 `at_ms` 是現在的 stop_reason.json（reason sleep），再 SIGTERM → `sleep`；
  - 寫一份 `at_ms` 是 0 的舊檔，再 SIGTERM → `signal`；
  - 外加一項：沒有檔，直接 SIGTERM → `signal`。
- aos-daemon：用一隻 on_stop 會把 `$AOS_LOOP_REASON` 寫進檔的小 loop：
  - ctl sleep → `sleep`；
  - ctl rm → `remove`；
  - ctl stop → `stop`；
  - daemon 收工 → `shutdown`。
  放進 test_lifecycle.py 或新的 test_stop_reason.py。
- hook_fire：`templates/tests` 裡已經有 after_stop 的測試就加在那裡，沒有就新開：設了 AOS_LOOP_REASON → 事件有 reason；沒設 → null。
- 回歸：aos-loop、aos-daemon 全套，lib/agent 和 templates 的相關測試。

## 4. 不做

- 不做「表的列記 parent」，那是 ok-astra 的。
- 不改 screen_linger。
- 不做 SIGKILL 之後的原因：on_stop 根本跑不到。
- 不碰 aos-post、aos-mailbox。

## 6. Argon 審後的修正（11-14，原文在 /tmp/ok-limits-argon5/argon.out；以本節為準，跟 1～3 節衝突的地方照這裡）

### 6.1 認人改用行程的啟動 ticks 和 boot_id，不用 wall clock（Argon 1、5、6）

wall clock 有三個問題：daemon 可能在 loop 記下時間之前就寫檔，同一毫秒重起會判斷錯，NTP 調時間也會亂掉。所以改成這樣：

- 檔內容改為：`{"reason": R, "pid": c.pid, "started_at_ticks": c.started_at_ticks, "at_ticks": <現在，CLOCK_BOOTTIME 換成 clock ticks>, "boot_id": <aos::boot_id()>}`。
  - `started_at_ticks` 是表上那個值（`/proc/<pid>/stat` 第 22 欄）。
  - `at_ticks` 用 `clock_gettime(CLOCK_BOOTTIME)` 乘上 `sysconf(_SC_CLK_TCK)`，跟第 22 欄同一個基準。
- loop 在 `main()` 一開頭先取自己的啟動 ticks（`aos::proc_started_at_ticks(getpid())`）和 `aos::boot_id()`。第 22 欄是開機以來的 ticks，在 pid namespace 裡也一樣，bwrap 也能用。
- loop 接受這個檔的條件：`boot_id` 相同，而且下面兩種情況之一：
  1. `started_at_ticks == 自己的啟動 ticks`：daemon 起的就是 loop 本身，這是平常的情況，不會有啟動時序的問題；
  2. `started_at_ticks < 自己的啟動 ticks <= at_ticks`：daemon 起的是外殼（sudo、bwrap），loop 是它底下的子孫，而且檔是在 loop 起來之後才寫的。
- 其他情況都不接受，回 `signal`。`started_ms_` 和 `at_ms` 拿掉。
- 已知漏洞，只寫進文件、不修：外殼情況下，daemon 在 loop 本身還沒 exec 之前就寫了檔，會回 `signal`。

### 6.2 第一個原因不被覆寫（Argon 2、7-1）

- daemon 寫檔之前先讀舊檔。舊檔的 `boot_id` 和 `started_at_ticks` 都跟這隻 child 一樣時，就不再寫，只送 SIGTERM。所以同一次啟動，第一個原因就是最後的原因。
  - 情況一：已經 sleep 中，又遇到 daemon 收工，仍然是 `sleep`。
  - 情況二：adopt 接回、重送 term，不會把 stuck 改成 remove。
- 唯一的例外：`ctl stop` 走 halt，不寫檔；之後升級成 sleep、rm 或 stuck 時，才第一次寫。這本來就是這樣，不用另外處理。

### 6.3 判斷順序寫死（Argon 3、4）

loop 收工時，照這個順序判斷，第一條成立就停：

1. 收到的訊號是 SIGTERM（`got_ == SIGTERM`），而且原因檔有效（6.1）→ 用檔裡的 reason。不管 `stopping_` 是否成立，也不管身體之後怎麼退。
2. 收到任何訊號（`got_ != 0`）：`stopping_` 成立就是 `stop`，否則是 `signal`。SIGINT、SIGHUP 這類不讀原因檔。
3. `stopping_` 成立 → `stop`。
4. 跑滿 max → `max`。
5. 身體退 10 → `body_exit`。
6. 其他情況 → `error`。身體自己被 SIGSEGV、SIGABRT 殺掉的情況，loop 的 `got_` 是 0，會落在這一條。

### 6.4 其他

- **認得的值放寬**（Argon 9-2）：reason 符合 `[a-z_]{1,32}` 就照抄，不寫死四個值，以後 daemon 加新原因，舊的 loop 也能照傳。
- **讀檔失敗**（Argon 8-1）：檔不在（ENOENT）就靜默；其他錯誤（EACCES、壞 JSON、少欄位）印一行 warning `stop reason file unusable: ...`，然後照 6.3 往下判斷。
  - 寫檔用 write_window，權限和 ctl 窗一樣，都是 0666 再套 umask。
- **環境殘留**（Argon 9-1）：loop 在 `main()` 開頭 `unsetenv("AOS_LOOP_REASON")`，只在 on_stop 期間才設。
- **要不要寫檔**（Argon 7-2）：保留「`c.stack` 底下有 loop 設定檔才寫」的做法。exec 列和 loop 共用同一個 stack 的情況目前不存在，只在 docs 寫一句。

### 6.5 測試補充（Argon 10）

- **aos-loop**：在第 3 節之外再補——
  - 壞 JSON → `signal`，stderr 有 warning；
  - `boot_id` 不同 → `signal`；
  - `started_at_ticks` 不同、也不在外殼的區間內 → `signal`；
  - 不認得但格式合法的 reason（`future_x`）→ 照抄；
  - `stopping_` 期間收到 SIGTERM，有有效檔（remove）→ `remove`；
  - 同樣情況但沒有檔 → `stop`；
  - SIGINT 加上有效檔 → `signal`；
  - 外層環境帶著 `AOS_LOOP_REASON=junk` 起 loop、由 max 收工 → `max`，而且 on_start 時看不到 junk。
- **aos-daemon**：在第 3 節之外再補——
  - stop 途中又收到 rm → `remove`；
  - sleep 中 daemon 收工 → 仍然是 `sleep`（6.2）；
  - exec 列（stack 底下沒有 loop 設定檔）→ 不會產生 stop_reason.json；
  - 有現成 fixture 的話，加測 adopt：kill -9 daemon、重開，接回 stopping 的列。沒有就在回報裡寫「沒測、只讀程式」。
  - stuck 不測，回報裡寫「只讀程式」。
- **hook_fire**：
  - `""`、`"  \t\n"` → null；
  - `" sleep\n"` → `"sleep"`。

## 7. ok-devt 初步意見（11-14 13:40，還不是定稿）

- **欄位名**：ok-devt 傾向改叫 `cause`，對應的環境變數是 `AOS_LOOP_CAUSE`，檔名是 `stop_cause.json`。原因是 `reason` 在 aos 裡已經固定是「給人看的一句話」，例如 daemon 表的 reason 欄、brain_failed 的 name／reason。等它定稿再改名。
  - 為了改名便宜，三個名字現在各只在一處定成常數：檔名在 `aos/loop.hpp` 的 `StopReasonWindow::default_name`，環境變數名在 `aos/loop.hpp` 的常數，事件欄位名在 `hook_fire/_entry` 的模組常數。
- **取值**：九個值照收，小寫加底線。stop、sleep、remove 跟 stop_mode 同名，這一點要保住。
- **limits 超限**：這一輪不加獨立的值，照舊算 `error`。文件補一句：「是不是撞到 limits，看表上的 `limit_hit`」。`limit` 這個名字先保留給以後的 daemon 用。
- **其他事件**：只有 after_stop 加這一欄。

## 8. 定稿後的名字（以本節為準，1～6 節的 reason 一律讀成 cause）

照 ok-devt [05-定稿](../ok-devt-1114/05-定稿.md) 2.2～2.4：檔名 `stop_cause.json`、檔裡的鍵 `cause`、環境變數 `AOS_LOOP_CAUSE`、after_stop 事件欄 `cause`。6.2「第一個原因不覆寫」多一個例外（定稿 2.3）：原因檔已經是同一次啟動的 `sleep`，收的途中使用者明下 rm＝改寫成 `remove`，不重送 SIGTERM、期限照舊（reconcile.cpp，`Child::recaused` 每次啟動只看一次）。三個名字各只在一處定成常數：`aos/loop.hpp` 的 `StopCauseWindow::default_name`、`cause_env`，`hook_fire/_entry` 的 `CAUSE_KEY`、`CAUSE_ENV`。

## 9. 11-15 交件（Claude 線 claude-b7 接手 ok-limits，使用者 11-15「能做的先做」）

11-14 碼已完成，只因換樹凍結沒交；ok-limits 收樹時留下六件待補（wrapup-1114 交接（`wf/temp/ok-limits/wrapup-1114/交接.md`，暫存區、不進版控））。本節是六件的結果。

- **乾淨複本**：`~/code/claude-b7-1115/`。先在 `src/`（main 7f50a8b7c 的 git archive）套 `~/code/limits-1114/ws/claude-b7-2/b7.diff`（21 檔）。lib/docs/03 與 templates/docs/02 的上下文在 main 動過（mailbox_read、goal 那幾列），改的那一行本身沒變，照原樣換掉；templates/agent-fsm/README 在 b1f72a0a6 多了兩行，同樣只換那一行。交件前 main 又進了幾筆（guard、subagent、gitignore，都沒動到 B7 的檔），再開一份 `final/`（main b8f8e7335 的 git archive 加 B7 的 21 檔），重編、重跑，下面的數字是 `final/` 的。impls 用複本自己的原始碼 `cmake -B build -G Ninja && cmake --build build` 編，bin 只在複本裡，沒裝進 `~/.local/bin`、沒碰活樹。
- **測試**（`env -i`，PATH 只有複本的 `impls/*/bin`、`cmd/*/bin` 與系統目錄，前景跑）：aos-loop 33、aos-daemon 114（skip 1）、self_hook 5、hooks_engine 5、test_clock_hook 13、test_clock_hook_daemon 1、tool_spec 10、tool_io_metainfo 6、tool_io_keys 7、templates/tests/agent-fsm 153（含新加的 test_hook_fire_cause），全部 OK。
- **順手修的測試**：test_on_start_stop 的 B7 那幾項，身體是 `trap "exit 0" TERM INT; sleep 30 & wait`，身體退了背景的 `sleep 30` 還拿著 stderr 管子，每項讀 stderr 都要等滿 30 秒（aos-loop 全套 421 秒）。trap 改成先 `kill $!` 再退，整檔 27 項 1.7 秒。

### 9.1 真 daemon 的事件輸出（第 1 件）

aos-daemon 的 test_stop_cause 在複本跑一次，scratch 留在 `~/code/claude-b7-1115/evidence/daemon-run2/`，摘錄在 `evidence/five-cases.txt`。每種情況的 after_stop 事件（hook 收到的 JSON）與小格的 stop_cause.json：

| 情況 | 事件的 code／signal／cause | stop_cause.json 的 cause |
|---|---|---|
| ctl sleep | 143／15／`sleep` | `sleep` |
| ctl rm | 143／15／`remove` | `remove` |
| ctl stop | 0／null／`stop` | 沒有這個檔（stop 走 ctl 窗） |
| daemon 收工 | 143／15／`shutdown` | `shutdown` |
| 先 sleep、收的途中 rm | 143／15／`remove` | `remove`（定稿 2.3 的例外，at_ticks 比 sleep 那次晚） |
| 先 stop、收的途中 rm | 143／15／`remove` | `remove` |
| 先 sleep、收的途中 daemon 收工 | 143／15／`sleep` | `sleep`（不覆寫） |
| sleep 中 kill -9 daemon 再開（adopt 重送） | 143／15／`sleep` | `sleep`，檔一字不改 |
| exec 列 rm | 沒有 on_stop | 沒有這個檔 |

檔裡另有 `pid`、`started_at_ticks`（表上那個值）、`at_ticks`、`boot_id`，例：`{"cause": "sleep", "pid": 658255, "started_at_ticks": 945368, "at_ticks": 945374, "boot_id": "204be8e2-…"}`。

### 9.2 沒測到的（第 2 件）

- **stuck**（卡住重起寫 `stuck`）：沒有現成 fixture 能讓 ctl 窗逾時三次，只讀程式：stuck.cpp 的 `term(name, c, StopCauseWindow::stuck)`，之後走同一個 note_cause。
- **sudo／bwrap 外殼**：沒在真的 sudo、bwrap 底下跑。外殼那條認法（`started_at_ticks` < 自己 <= `at_ticks`）只用 aos-loop 測試裡的 `sh` 外殼測過（test_cause_under_a_wrapper）。已知漏洞照 6.1 寫進文件、不修：daemon 在 loop 本身 exec 之前就寫檔，回 `signal`。
- 撞 limits 被收掉：不是 B7 的值（定稿：看表上的 `limit_hit`），沒另測。

### 9.3 hook_fire 在活樹怎麼連（第 3 件）

沒看活樹（本線不碰 `~/aos-home`）。範本 loop.json 的 on_stop 是 `{"$env": "AOS_HOME", "$path": "/lib/agent/hook_fire/_entry"}`，所以活樹用的是 `$AOS_HOME/lib` 那份；那份是不是複本、何時換，由換樹決定。兩邊新舊混用都不會壞：新的 aos-loop 配舊的 hook_fire＝環境變數多一個、事件沒有 `cause` 欄；舊的 aos-loop 配新的 hook_fire＝`cause` 是 null。所以 bin 與 lib 不必同一刻換。

### 9.4 其他

- **第 4 件**（乾淨複本跑全套）：見上面「測試」。
- **第 5 件**（claim）：21 檔加這兩份紀錄由 claude-b7 claim；templates/agent-fsm/README 原本是 claude-daily 在 claim，它 b1f72a0a6 交完放掉之後才 claim。
- **第 6 件**（通知 ok-sec、ok-kf）：兩條線 11-15 已收樹（retire-1115），沒有收信的人。要用 `cause` 的是 ok-kf 的 screen_linger，接手的人看本節與 aos-loop docs/01 的值表就好。
- **測試的既有問題（不是 B7）**：aos-daemon 的 test_two_machines 跑完會留下一支 `python3 /tmp/aos-daemon-tm-*/a/body_a.py`（父是 init、暫存夾已經不在）。沒套 B7 的複本照樣留，跑完照 pid 收掉。沒修，留給下次動那支測試的人。
