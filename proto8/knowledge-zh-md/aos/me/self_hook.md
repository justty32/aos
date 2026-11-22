# `knowledge/aos/me/self_hook.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/me/self_hook.md`，跟到正本 commit `c7bc08dae`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/me/self_hook.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Hooks: run a program of yours when something happens to you`**

# Hooks：有事發生在你身上時，跑一個你的程式

工具 `self_hook` 就是對準你的 `aos-agent hook`。hook 是一個工具資料夾或可執行檔，在某個事件發生時執行。它在 stdin 收到一個 JSON 物件，就是那個事件。只有你自己的 hook 清單會變，從下一個事件起生效。它在 events 工具包裡，沒有任何現成範本有這個工具包（agent-fsm 或 eca）：先用 `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_hook"}}` 加上它。

每次呼叫一個 op：

- 列出：`{"op": "ls"}`（加 `"long": true` 可以看條件、逾時，以及你關掉的 hook）
- 看一個：`{"op": "get", "name": "guard"}`
- 加入：`{"op": "add", "event": "before_tool", "path": "hooks/guard", "condition": "peek_now_time"}`
- 移除：`{"op": "rm", "name": "guard"}`
- 回到你原本的 hook：`{"op": "reset"}`

事件和它們的欄位：`aos/me/self_hook.md#/Hook events`（on_clock：`aos/me/self_hook.md#/The on_clock hook`）。add 的選項和 hook 怎麼回覆：`aos/me/self_hook.md#/Hook options and answers`。寫程式：`aos/me/self_hook.md#/Writing the hook program`；例子：`aos/me/self_hook.md#/Hook examples`。在某個牆上時間做的工作（每天 09:00）：`aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`。
hook 不會被檢查有沒有迴圈：一個寄訊息給你的 hook，會再次觸發你的 queue hook。

錯誤：ArgumentsBad、OpUnknown、PathMissing、HookExists（加 `"replace": true`）、HookMissing、HooksMissing、HooksBad、NameBad、DaemonMissing、DaemonFailed、InstanceMissing。

**`#/Hook events`**

# Hook 事件

事件和它們的欄位（每個事件也都有 `event`、`hook`、`stack`）：

- `before_queue`：一則訊息即將進入你的對話（`letter`、`content`）。可以改 `content`，可以丟掉這則訊息。在 agent-fsm 上 `/compact` 訊息不經過這裡；在 eca 上每則訊息都經過，斜線訊息也是。
- `after_queue`：一則訊息進入了你的對話（`letter`、`content`）。
- `before_tool`：你的某個工具即將執行（`name`、`id`、`arguments`）。可以改 `arguments`，可以擋下這次呼叫。在 eca 上只有透過 aos-mcp 呼叫的 aos 工具經過這裡（不包括 CLI 自己的工具），而失敗的 hook 只會讓那一次呼叫變成錯誤結果，不會讓你停下。
- `after_tool`：一個工具做完了，在你看到結果之前（`name`、`id`、`arguments`、`content`、`code`、`timed_out`）。可以改 `content`。
- `brain_failed`：你的腦呼叫失敗了（`name` = 錯誤代號、`reason`；有 kernel 的錯誤物件時 `error` = 它）。預算拒絕會以 `name` `BudgetMissing` 加上 kernel 的原因出現（不是 `BrainFailed`）；你繼續等，冷卻後重試。其他 kernel 錯誤以 `name` `BrainFailed` 出現，帶 `code`（kernel 的代號，有給的話）、`retry`（true：你繼續等並重試；false：你停下）、`attempt`（連續失敗次數）、`status`（HTTP 狀態，如果有）以及重試時的 `wait_s`（到下一次嘗試的秒數）。`LlmKernelMissing`、`SendFailed` 和 `ReplyBad` 只帶 `name` 和 `reason`。對 eca claude，`name` 是 `CliFailed` 或 `ReplyMissing`，帶 `code`、`retry`、`attempt`、`dropped`，重試時帶 `wait_s`，有的話還有 `status`／`cause`。暫時性的 print API 錯誤會讓信保持待處理，冷卻後用一個接續提示（continuation prompt）再送；永久性錯誤會停下並丟掉它們。暫時性的斜線錯誤只丟掉那一封斜線信，不動先前的重試紀錄。Codex 保留舊的 `name`／`reason` 事件，沒有重試欄位。
- `tool_added`：你的工具箱裡出現了一個新的工具名（`name`、`path`）。
- `before_compact`：你的對話即將被壓縮（`asked` = /compact 後面的字，`instructions` = 你可以改的額外摘要指示，空字串表示沒有，`restore` = null，你可以給一段文字，在摘要之後加回去）。結束碼 10 擋下這次壓縮。在 agent-fsm 上（一個有足夠內容可以摺疊的 /compact，在清掉舊的工具輸出之前）還有 `letters`、`mid_turn`、`foldable`、`clear`（true；設成 false 就保留舊的工具輸出）和 `summary`（null；給一個，就不會問你，它會立刻被摺進去）；被擋下的 /compact 會得到回覆 `compact blocked by hook ...`（在一輪中間時，它會等這一輪結束再問一次）；失敗的 hook 只是一個警告。在用 claude 的 eca 上（它的 cli.json 接上範本的 compact_hook；由 Claude Code 壓縮）還有 `trigger` = `manual`（/compact）或 `auto`；那裡的 `instructions` 是 compact_hook 交給 Claude Code 的東西，`restore` 在壓縮後立刻加上，而 hook 不能寫摘要。
- `after_compact`：摘要好了（`summary`）。在 agent-fsm 上它還沒進你的對話歷史：還有 `letters`、`by`（`brain`，或給了摘要的那個 before_compact hook）、`mid_turn`、`cleared`（舊的工具輸出清掉了）和 `restore`（before_compact 給的東西，不然是 null）；hook 可以改 `summary` 和 `restore`（非空的 `restore` 會以一則使用者訊息 `[aos] restored after compact: ...` 放在摘要的正後面）。在用 claude 的 eca 上它只是告知（`trigger`、`summary` = Claude Code 寫的東西）。
- `after_start`：你的迴圈啟動了（重新啟動或醒來後也算）。`after_stop`：你的迴圈即將結束（停止、睡眠、移除、失敗）；硬殺之後不會有。這個事件只有 `event`、`hook`、`stack`；程式去讀環境變數：`AOS_LOOP_CODE`（迴圈結束時的代碼）、`AOS_LOOP_SIGNAL`（它收到的訊號，或空的）、`AOS_LOOP_CAUSE`：一個可以拿來比對的代碼，`stop`、`sleep`、`remove`、`shutdown`、`stuck`、`signal`、`max`、`body_exit` 或 `error`，沒給時是空的（不是表上的 `reason`，那是給人看的一句話）。
- `before_run`：你的迴圈每跑一次之前：狀態機 agent 的每個狀態、eca 的每一輪。只有在你定義的 loop.json 接上它時才有（編譯時有掛 hook，或手動加了那個鍵）；在沒有它的 loop.json 上加一個，會得到警告：它需要重新編譯並重新啟動。這個事件只有 `event`、`hook`、`stack`；跑的次數在 `AOS_LOOP_RUNS`，狀態機即將跑的狀態在 `STACK/stage.txt`（第一次跑時沒有：就是起始狀態）。沒有 `condition`：只想對某一個狀態動作，就讓程式去讀 stage.txt。結束碼 10 跳過那一次（那個狀態不跑，過一個迴圈間隔後你再問一次）。只要接著，每跑一次就花一個程序；要定時做事，用 `on_clock`。
- `after_run`：每跑一次之後（接法一樣）。環境變數：`AOS_LOOP_RUNS`、`AOS_LOOP_RUN_CODE`（這一次的結束碼）、`AOS_LOOP_RUN_SIGNAL`（或空的）、`AOS_LOOP_RUN_MS`；狀態機現在的狀態在 `STACK/stage.txt`。
- 在四個迴圈事件（`after_start`、`after_stop`、`before_run`、`after_run`）上，程式的結束碼原樣交給你的迴圈：任何非零代碼都會停下你的迴圈，除了 `before_run` 上的 10（跳過那一次）。
- `on_clock`：一個時鐘往前走了；見 `aos/me/self_hook.md#/The on_clock hook`。

**`#/The on_clock hook`**

# on_clock hook

- `on_clock`：一個時鐘往前走了（`clock`、`cycle`、`interval_ms`、`first`、`last_cycle`、`missed`）。給 `every_cycles` 或 `every_ms`（ms 是用時鐘週期算的，不是牆上時間：`every_ms` 會變成 ceil(`every_ms` / `interval_ms`) 個週期，至少 1，所以實際間隔可能比寫的長，不會更短）；`clock` 可省略（預設：`AOS_CLOCK`；或一個 proc 名字／一個路徑）。`config`（任何 JSON，可省略）會以事件欄位 `config` 交給程式。在你每一步開始時檢查；到期時跑一次，不管你忙的時候錯過了幾次（`missed` 說錯過幾次），你睡著時不跑。在你啟動、醒來或重新啟動後也會立刻跑一次（欄位 `first`：true、`last_cycle`：null、`missed`：0）。
- 在 eca 上，一步是你的迴圈走一圈（現成範本：大約一秒三次，queue 空著也一樣），不是一次回覆。aos 等 CLI 回覆一則 queue 訊息的期間，什麼都不檢查；之後的下一次檢查會跑那個 hook 一次。
- 睡過之後，事件不會告訴你睡了多久，或錯過了幾次。需要補做的處理程式自己記紀錄：`aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`。
- 沒有時鐘（沒設 `AOS_CLOCK` 也沒有 `clock` 鍵）：這個 hook 永遠不跑。你的紀錄會有一行警告 `hook NAME (event on_clock) is not checked: AOS_CLOCK is not set ...`。不會改用牆上時間。

`on_clock` hook 不會給你看任何東西：你的對話從它那裡什麼都得不到。想知道它的事，就讓它的程式寄一封信到你的 queue：`aos-post send STACK/queue`，內容 `{"role": "user", "content": "..."}`（STACK = 事件的 `stack`）。你的定義可能已經有一個 `timer` hook（每 5 分鐘，什麼都不做）：用同一個名字換成你自己的程式。它也有 `mail_notify`（每分鐘，只在有新信來時發一則訊息（你睡著時來的也算）；`aos/mailbox.md#/Hearing about new letters`）。

**`#/A job at a wall time (every day at 09:00)`**

# 在某個牆上時間做的工作（每天 09:00）

`on_clock` 算的是時鐘週期，不是牆上時間。要做到「每天 09:00」或「每 3 天」，就讓 hook 每分鐘跑一次，讓它的程式自己看牆上的時鐘。只有在有工作到期時，它才寄一封信到你的 queue；不然什麼都不會進你的對話歷史，也不花一輪腦。

檔案 `hooks/daily`（然後 `chmod +x hooks/daily`）：

```python
#!/usr/bin/env python3
# daily - on_clock hook: jobs at a local wall time; one letter to my queue when one is due
import datetime, json, os, subprocess, sys
JOBS = [{"name": "patrol", "at": "09:00", "every_days": 1, "text": "Morning patrol is due."},
        {"name": "status", "at": "09:00", "every_days": 3, "text": "The 3-day status update is due."}]
ev = json.load(sys.stdin)
state = os.path.join(os.environ["AOS_STACK"], "done.json")      # $AOS_STACK = this hook's own folder
try:
    with open(state) as f:
        done = json.load(f)                                     # {"patrol": "2026-11-13"} = the day it last ran
except (OSError, ValueError):
    done = {}
now = datetime.datetime.now()                                   # local wall time
due = []
for job in JOBS:
    last = done.get(job["name"])
    if last and (now.date() - datetime.date.fromisoformat(last)).days < job["every_days"]:
        continue                                                # ran recently enough
    if now.strftime("%H:%M") < job["at"]:
        continue                                                # too early today
    due.append(job)
if not due:
    sys.exit(0)                                                 # no letter: your history does not grow
text = "[daily] " + now.strftime("%Y-%m-%d %H:%M") + "".join(
    "\n- %s: %s (last ran: %s)" % (j["name"], j["text"], done.get(j["name"], "never")) for j in due)
r = subprocess.run(["aos-post", "send", os.path.join(ev["stack"], "queue")],
                   input=json.dumps({"role": "user", "content": text}), text=True, capture_output=True)
if r.returncode != 0:
    sys.stderr.write("daily: cannot send: %s\n" % r.stderr.strip())
    sys.exit(1)                                                 # done.json not written: tried again at the next check
for j in due:
    done[j["name"]] = now.date().isoformat()
with open(state + ".tmp", "w") as f:
    json.dump(done, f)
os.replace(state + ".tmp", state)
```

加上它：`self_hook` `{"op": "add", "event": "on_clock", "every_ms": 60000, "name": "daily", "path": "hooks/daily", "timeout_ms": 10000}`。

有工作到期時，你會收到一則訊息，像 `[daily] 2026-11-13 09:00`，每個工作一行，`- patrol: Morning patrol is due. (last ran: 2026-11-12)`。

睡過之後，以及 `first` 那一次：

- 程式不讀 `first` 或 `missed`。它每次檢查都問同一個問題：現在過了今天的 `at` 沒有，這個工作在最近 `every_days` 天內跑過沒有？它的紀錄是 hook 自己資料夾裡的 `done.json`，睡眠和重新啟動都會留著。
- 你 10:00 醒來，昨天 09:00 那次錯過了：第一次檢查就立刻寄信，`last ran` 會顯示中間的空缺。
- 不管錯過了幾天，每個工作只寄一次，不是每錯過一天寄一次。
- 你在 `at` 之前醒來：到 `at` 之前什麼都不寄。
- `every_days` 從工作真的跑的那天算起：晚跑會把下一次往後推。
- 信寄不出去：結束碼 1，`done.json` 不寫，下一次檢查再試（失敗的 on_clock hook 在你的紀錄裡是一行警告）。
- `done.json` 不見了：每個工作都算從沒跑過，時間到時寄一次。
- 時間是機器的當地時間。這封信像任何訊息一樣在你的 queue 裡等著。

**`#/Hook options and answers`**

# Hook 選項與回覆

add 的選項：`path_json`（代替 `path`：照寫的保留的值，像 `{"$env": "AOS_HOME", "$path": "/lib/x"}`；這時要給 `name`）、`name`（預設：檔名或資料夾名）、`condition`（在 `before_tool`、`after_tool`、`tool_added` 上只針對這個工具名，在 `brain_failed` 上是錯誤代號；在其他事件上會保留但不比對）、`timeout_ms`（預設 60000；0 = 不限）、`replace`（true = 取代同名的 hook；新項目只有你這次給的東西，所以要再給一次 `config`）、`config`（只限 `on_clock`：存在項目裡的任何 JSON；程式以事件欄位 `config` 拿到它；`null` = 沒給。搭配 `replace` 時，先看舊的項目（`{"op": "get", "name": "context_wrap"}`），再把整個 config 重新給一次：agent-fsm 的 context_wrap 有 `"wrap": false`。eca 的例子，context_wrap 上限設在 50%：`{"op": "add", "event": "on_clock", "every_ms": 5000, "name": "context_wrap", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/context_wrap"}, "config": {"percent": 50}, "timeout_ms": 20000, "replace": true}`）。

hook 怎麼回覆：

- 結束碼 0，stdout 什麼都沒有：什麼都不變。
- 結束碼 0，stdout 有一個 JSON 物件，只限 `before_queue`、`before_tool`、`after_tool`（在那裡 stdout 有其他東西 = 失敗）：`{"content": "..."}` 或 `{"arguments": {...}}` 取代那個欄位。在 agent-fsm 的 `before_compact` 上它可以設 `instructions`、`clear`、`summary`、`restore`，在 `after_compact` 上設 `summary`、`restore`；在 eca 的 `before_compact` 上設 `instructions`、`restore`（aos/me/compact.md）。在其他事件上不讀 stdout。
- 在 `before_queue`／`before_tool` 上結束碼 10：擋下它（訊息被丟掉；工具不跑，你拿到 hook 的 stdout 當結果。被擋下的呼叫不會被標成錯誤：結果看起來像一般的回覆，所以讓 hook 清楚印出它擋下了這次呼叫）。在 `before_compact` 上：不壓縮。在 `before_run` 上：跳過那一次。在 after_start、after_stop 和 after_run 上，它就跟其他非零代碼一樣：迴圈停下。在其他事件上 10 算作 0。
- 任何其他結束碼、逾時，或 stdout 不對：hook 失敗。在 `before_queue` 和 `before_tool` 上你會停下（HookFailed；在 eca 上失敗的 `before_tool` hook 只讓那次呼叫變成錯誤結果）；在其他事件上是一行警告；在四個迴圈事件上你的迴圈會停下。
- 一個事件上有好幾個 hook 時，它們照名字順序跑；在你的身體自己觸發的事件上，每一個都看得到前面的改了什麼，agent-fsm 的 `before_compact` 和 `after_compact` 也是（在四個迴圈事件和 eca 的壓縮事件上，每一個拿到的都是同一個事件）。

**`#/Writing the hook program`**

# 寫 hook 程式

程式（add 裡的 `path`）可以是：

- 一個可執行檔（`chmod +x`；腳本以 `#!/usr/bin/env python3` 或 `#!/bin/sh` 開頭）；
- 一個 JSON 檔 `{"argv": ["python3", "x.py"]}`，旁邊放 `x.py`（不用 chmod）；
- 一個有 `_entry` 的工具資料夾。

不可執行的一般檔案會失敗（你的紀錄裡出現 `EntryBad`）。

它拿到什麼：

- stdin：一個 JSON 物件：`event`、`hook`（它的名字）、`stack`（你的 stack），以及事件的欄位（`aos/me/self_hook.md#/Hook events`）。
- `$AOS_STACK` = hook 自己的資料夾 `<your stack>/hookeds/<name>/`。它寫在那裡的檔案會留到下一次跑。你自己的 stack 是 `stack` 欄位，不是 `$AOS_STACK`。
- `$AOS_WS` = 你的工作區。目前的資料夾 = 程式所在的資料夾。你其他的 `AOS_*` 變數也都有設（`AOS_DAEMON`、`AOS_CLOCK` ...）。
- 它的 stderr 跟你的去同一個地方（在 daemon 底下：你 stack 裡的 `stderr.txt`）。它的 stdout 只在 `before_queue`、`before_tool`、`after_tool` 上才算數；它在迴圈事件上的結束碼會交給你的迴圈（`aos/me/self_hook.md#/Hook options and answers`）。

要聯絡你的腦，就寄一封信到你的 queue：`aos-post send STACK/queue`，stdin 給 `{"role": "user", "content": "..."}`。完整的程式：`$AOS_HOME` 底下的 `lib/tools/agent/mail_notify`（`aos/mailbox.md#/The mail_notify hook`）。短的：`aos/me/self_hook.md#/Hook examples`。

**`#/Hook examples`**

# Hook 例子

- 記下每次停止和啟動。檔案 `hooks/up_down`（然後 `chmod +x hooks/up_down`）：

```
#!/bin/sh
cat >> "$AOS_WS/up_down.log"
echo " code=$AOS_LOOP_CODE signal=$AOS_LOOP_SIGNAL cause=$AOS_LOOP_CAUSE" >> "$AOS_WS/up_down.log"
```

  `self_hook` `{"op": "add", "event": "after_stop", "name": "down", "path": "hooks/up_down", "timeout_ms": 5000}`，再用 `after_start` 和名字 `up` 做一次一樣的（在那裡這三個變數是空的）。停止會記 `code=0 signal=`；睡眠、移除或 daemon 關機會記 `code=143 signal=15`。硬殺（kill -9）什麼都不記。讓它以 0 結束：在這些事件上非零結束會停下你的迴圈。
- `after_start`／`after_stop` 的 `timeout_ms` 保持在 5000 以下：迴圈最多等它們 5 秒。
- 擋下一個工具：一個帶 `"condition": "shell"` 的 `before_tool` 程式，印出原因並以 10 結束。工具不跑；你拿到那個原因當結果。
- 每 10 分鐘，單獨跑一個程式：`{"op": "add", "event": "on_clock", "every_ms": 600000, "path": "hooks/backup"}`。
- 每天 09:00，或每 3 天（牆上時間）：`aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`。

**`#/Eca screen lifecycle hooks`**

# Eca 畫面生命週期 hook

現成的 eca hook screen_linger_start（after_start，排第一）和 screen_linger_stop（after_stop）會取消或排定延遲關閉畫面。它們用事件的 stack，不是處理程式的 AOS_STACK。兩個都有 4000 ms 逾時；它們自己的錯誤只是一行警告（它們以 0 結束），所以永遠不會停下你的迴圈。cli.json 的 screen_close_after_s 是以秒為單位的非負整數（預設 600，0 立刻關閉）。在你 stack 的複本裡把兩個 hook 名字都設成 null，畫面就會一直留著。啟動或醒來會取消待執行的指令；暫停不會排一個新的。新的活迴圈即使啟動 hook 失敗也受保護。到期時，連著的觀看者會被斷線。硬殺以及停止後才打開的畫面，沒有後備處理。細節：`aos/cli/eca.md#/Delayed screen closure`。
