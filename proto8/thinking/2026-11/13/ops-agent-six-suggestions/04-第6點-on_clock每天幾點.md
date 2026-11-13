# 第 6 點：on_clock 的「每天幾點」範例、閒著時跑不跑、這棵樹的 AOS_CLOCK——事實查核、實測、可用範例（11-13，只調查沒施工）

← [ops-agent-six-suggestions](../ops-agent-six-suggestions.md)｜上一份 [03-第2到5點](03-第2到5點.md)｜下一份 [05-回信草稿](05-回信草稿.md)

看的檔是 commit `2fb2c4b5e` 當下的；實測在 `~/code/ops-try-1113/tree/` 自己起的一棵暫存樹（根 daemon＋一隻 `eca-claude` 範本的 `bob`，模型 haiku），另外唯讀看了 `~/aos-home` 現場行程的環境變數與 hook 狀態檔。

## 另問的確定答案：eca 閒著沒有新信時，on_clock 照樣定時檢查

**會。閒著時大約每 0.3 秒看一次時鐘，到了你設的間隔就跑。** 不需要有新信。

機制（讀碼）：eca 的身體是 `aos-loop` 反覆叫 `aos-eca-turn`（範本 `loop.json`：`--on-empty idle`、`interval_ms` 300）。`aos-eca-turn` 每次被叫起來，**第一件事**就是 `hooks.clock_tick`（`cmd/aos-eca/aos_eca/turn.py` `one_turn` 開頭；冷卻中、退讓的那次也看），然後才看 queue；queue 空就退 0，loop 隔 0.3 秒再叫一次。所以知識庫說的「each turn」指的是「`aos-eca-turn` 每跑一次」，不是「腦每答一輪」——**`body.json` 那句寫得不準，會讓人以為沒信就不檢查**（ops-agent 就是這樣讀的）。

實測（暫存樹，掛一個每 5 秒的 on_clock hook 把事件記進 log，queue 一直是空的）：

| 牆上時間 | 事件 | 說明 |
|---|---|---|
| 11:11:58 | `first: true` | 剛掛上，立刻跑一次 |
| 11:12:08 | `missed: 1` | 中間 10 秒腦在答一封信（下面那封 daily），這段沒檢查；答完補跑**一次** |
| 11:12:13、:19、:24、:29 | `missed: 0` | 閒著、沒有任何信，照樣每 5 格跑 |
| 11:12:31～11:12:43 | 沒有 | `aos-agent ctl sleep bob`，睡著不跑 |
| 11:12:43 | `first: true`、`last_cycle: null` | `ctl wake`，醒來立刻跑一次 |
| 11:12:43 之後兩分多鐘 | 沒有 | 腦在答信（haiku 跑了一個很久的指令），整段沒檢查 |

現場旁證（唯讀）：`~/aos-home` 的 ops-agent 自己的 `hooks/mail_notify/on_clock.json` 在 11:05:33 更新（cycle 7839），`hooks/timer/on_clock.json` 在 11:01:16 更新——它閒著時就一直在跑。

**三個「不跑」的時候**（規劃試點要知道）：

1. **aos 正在等 CLI 答一封 queue 的信時**：`aos-eca-turn` 卡在等回答，這段不檢查；答完後下一次檢查補跑一次，`missed` 寫錯過幾次。一輪最長可以到 `cli.json` 的 `timeout_ms`（範本 10 分鐘）。人自己在畫面上打字讓 CLI 跑的那種不算——那時 `aos-eca-turn` 沒在等，照樣檢查（這句是讀碼，沒實測）。
2. **睡著時**（`ctl sleep`、daemon shutdown、機器關機）：不跑。醒來第一次檢查一定跑一次，`first: true`、`last_cycle: null`、`missed: 0`——**框架不會告訴你睡了多久、錯過幾次**。
3. **沒有時鐘時**：見下一節。

間隔的算法：`every_ms` 是換成時鐘格數算的（`ceil(every_ms ÷ AOS_CLOCK_INTERVAL)`，預設一格 1000 毫秒），不是牆上時間；根 daemon 的 `_clock` 列每秒走一格，[N-65](../../../../docs/NORMS/02-設計理念-時空.md) ④「只會慢」，所以實際間隔只會比寫的長、不會短。

## 「這棵樹沒有 AOS_CLOCK」：不對，但它看到的現象是真的——是一個 bug

**樹有時鐘。** 唯讀看現場行程的環境：根 daemon、領班 daemon、ops-agent 的 `aos-loop`（pid 652279）都有 `AOS_CLOCK=~/aos-home/.stack//clock`，時鐘檔每秒在走。所以 on_clock（在 loop 那邊跑）一直正常。

**但 ops-agent 在自己的 Bash 裡看不到它，`clock_register`、`peek_clock` 也真的用不了。** 原因：它現在的 CLI 是人用 `aos-agent open` 開的畫面，畫面裡的 claude（pid 870843）與它帶起來的 `aos-mcp`（pid 871256）繼承的是**開畫面那個人的殼**的環境，不是這隻 proc 在 daemon 底下的環境；而 `~/aos-home/env.sh` 明寫 `unset AOS_DAEMON AOS_KERNEL AOS_CLOCK`。現場那兩個行程的環境裡有 `AOS_HOME`、`AOS_DAEMON`、`AOS_STACK`、`AOS_WS`（`aos-agent open` 補的），就是沒有 `AOS_CLOCK`。暫存夾實測：沒有 `AOS_CLOCK` 時 `peek_clock`、`clock_register` 都回 `ClockMissing`。

後果：同一隻 agent，畫面沒開時（aos 從 loop 起 `claude -p`）工具看得到時鐘，人一開畫面就看不到；`AOS_KERNEL`、`AOS_LLM_KERNEL`、`AOS_CLOCK_INTERVAL` 同理。

- **分類：bug。** claude 身的 `mcp.json` 不帶環境（讀碼：`lib/agent/cli_mcp.py` 的 `MCP_ENV` 只在 codex 身明寫帶進去），整個靠繼承；人開的畫面繼承不到。
- **最小修法**：開畫面時把這隻 proc 的那幾個變數（`cli_mcp.MCP_ENV` 列的）帶進去，來源用它在 daemon 底下實際的環境，不用開畫面那個人的殼。做法之一：`aos-eca-turn` 每次起來把這幾個值記進小格一個小檔（值變了才寫），`cli_screen.start` 開 tmux 時讀它、用 `new-session -e` 帶進去，claude 身的 `mcp.json` 也照 codex 那樣明寫 `env`。動 `cmd/aos-eca/aos_eca/turn.py`、`lib/agent/cli_screen.py`、`cli_mcp.py`、測試。一人半天。邊緣：畫面比 loop 先開（小檔還沒有）＝照舊繼承、提醒一行。
- **現在的避法**：`clock_register` 給 `daemon`（指到有時鐘檔的那台，這棵樹是根 daemon 的 stack `~/aos-home/.stack`），不靠 `AOS_CLOCK`（照知識庫 `clock.json#/wake_me` 的寫法，這次沒實測）。ops-agent 要做的「每天幾點」不需要 `clock_register`，用下面的 on_clock 就好。

## 沒有時鐘時 on_clock 怎麼算：不算，直接不跑

`world.json` 的 Time 段寫「No clock (`AOS_CLOCK` not set): cycles fall back to wall time」——這句講的是**等待的期限**（N-65 ①「期限寫 cycle 時……沒有就退牆上時鐘」），對 on_clock 不成立。on_clock 找不到時鐘＝**不跑**，只在 log 寫一次提醒（`lib/agent/hooks.py` `clock_tick`；11-11 [clock-hook](../../11/clock-hook/README.md) 施工時定的「找不到時鐘＝不跑、warning 只說一次」）。

實測：暫存樹掛第二隻、`AOS_CLOCK` 給空值，`stderr.txt` 出現
`aos-eca-turn: warning: hook mail_notify (event on_clock) is not checked: AOS_CLOCK is not set (no clock: not under a daemon tree with one)`，hook 一次都沒跑，連 `mail_notify` 也不通知了。知識庫沒寫這個後果＝文件缺。

## 其他它說的事實

| 它說的 | 對不對 |
|---|---|
| on_clock 只有 `every_ms`、`every_cycles`，沒有牆上時間 | 對（讀碼：`hooks.py` `CLOCK_KEYS`） |
| `clock.json#/choose` 只舉了 `mail_notify` | 對（讀檔） |
| `body.json` 寫「each turn」 | 對，而且這句不準（見上） |

## 分類

- **文件寫得不準**：`body.json` 的「each turn」。
- **文件缺**：沒有牆上時間的範例；沒寫「睡醒那次不知道錯過多久」；沒寫「沒時鐘＝on_clock 不跑」。
- **bug**：人開的畫面沒有 `AOS_CLOCK`（上一節）。
- 「on_clock 要不要內建牆上時間（例如 `at: "09:00"`）」不立題：[N-01](../../../../docs/NORMS/02-設計理念-時空.md)「aos 內部互相約的時間看時鐘……對人……用牆上時鐘」，對人的時間由 handler 自己看牆鐘，正是下面範例的做法（C-56 KISS）。

## 可用範例：`hooks/daily`（暫存樹實跑過）

做的事：照**當地牆上時間**排工作（每天幾點、每幾天一次、限星期幾、太晚就不補），到期才往自己的 queue 寄**一封**信；沒到期什麼都不做，history 不長、不花腦。

```python
#!/usr/bin/env python3
# daily - on_clock hook: jobs at a local wall time ("every day at 09:00", "every 3 days"); one letter to my queue when due
import datetime, json, os, subprocess, sys

JOBS = [  # at/until = local time HH:MM; every_days counts calendar days; weekdays 0 = Monday
    {"name": "patrol", "at": "09:00", "until": "18:00", "every_days": 1, "weekdays": [0, 1, 2, 3, 4],
     "text": "Morning patrol is due. Follow notes/patrol.md."},
    {"name": "repo-status", "at": "09:00", "every_days": 3,
     "text": "The 3-day repo status update is due."},
]

def hhmm(text):
    h, m = text.split(":")
    return datetime.time(int(h), int(m))

ev = json.load(sys.stdin)                                  # event, hook, stack, cycle, first, missed ...
jobs = JOBS
if os.environ.get("DAILY_JOBS"):                           # optional: a JSON file with the same list
    with open(os.environ["DAILY_JOBS"], encoding="utf-8") as f:
        jobs = json.load(f)
state_path = os.path.join(os.environ["AOS_STACK"], "done.json")   # AOS_STACK here = this hook's own folder
try:
    with open(state_path, encoding="utf-8") as f:
        done = json.load(f)                                # {"patrol": "2026-11-13", ...} = last day it ran
except (OSError, ValueError):
    done = {}
now = datetime.datetime.now()                              # local wall time
today = now.date()
due = []
for job in jobs:
    last = done.get(job["name"])
    last = datetime.date.fromisoformat(last) if last else None
    if last and (today - last).days < job.get("every_days", 1):
        continue                                           # ran recently enough (also: already ran today)
    if "weekdays" in job and today.weekday() not in job["weekdays"]:
        continue
    if now.time() < hhmm(job["at"]):
        continue                                           # too early today
    if "until" in job and now.time() > hhmm(job["until"]):
        continue                                           # too late today: skip, try again tomorrow
    late = "" if last is None else " (last ran %s, %d days ago)" % (last, (today - last).days)
    due.append((job, late))
if not due:
    sys.exit(0)                                            # nothing due: no letter, history does not grow
text = "[daily] %s\n" % now.strftime("%Y-%m-%d %H:%M") + "\n".join("- %s: %s%s" % (j["name"], j["text"], l) for j, l in due)
r = subprocess.run(["aos-post", "send", os.path.join(ev["stack"], "queue")],
                   input=json.dumps({"role": "user", "content": text}), text=True, capture_output=True)
if r.returncode != 0:
    sys.stderr.write("daily: cannot send: %s\n" % r.stderr.strip())
    sys.exit(1)                                            # done.json not written: tried again at the next check
for job, _ in due:
    done[job["name"]] = today.isoformat()
tmp = state_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(done, f)
os.replace(tmp, state_path)
```

掛上去（每分鐘看一次就夠；`on_error: continue`＝它壞了只多一行提醒、不拖垮 agent）：

```json
{"op": "add", "event": "on_clock", "every_ms": 60000, "name": "daily", "path": "hooks/daily", "on_error": "continue", "timeout_ms": 10000}
```

給 `self_hook` 用；人從殼裡掛是 `aos-agent hook -t <名> add --event on_clock --every-ms 60000 --on-error continue --timeout-ms 10000 -n daily hooks/daily`。檔要 `chmod +x`；工作區在 `/mnt/c` 上、執行位元不可靠時，改用知識庫 `me/self_hook.json#/handler` 寫的 JSON 入口（`{"argv": ["python3", "daily.py"]}`，不用 chmod）。`aos-post` 要在 PATH 上（daemon 底下本來就在）。

### 睡一晚醒來，`first` 那次怎麼處理前一天沒跑到的

**這支程式完全不看 `first`、`missed`**——因為醒來那次框架給的是 `first: true`、`missed: 0`，看不出睡了多久。它靠自己記的 `done.json`（每個工作上次是哪一天跑的，放在 hook 自己的小格 `<stack>/hooks/daily/`，睡、重起都還在）加上牆上日期來判：

- 醒來的第一次檢查（醒來後立刻）就問同一個問題：「今天輪到了嗎、時間過了嗎、今天跑過了嗎」。昨天 09:00 沒跑到、今天 10:00 醒來＝今天該跑的那次立刻補上，信裡帶一句 `(last ran 2026-11-12, 1 days ago)` 讓腦知道隔了多久。
- **不管錯過幾天，每個工作只補一次**，不會一口氣補三封。
- 醒來時還沒到 `at`＝不跑，等到了再跑。醒來時已經超過 `until`（例如晚上才開機）＝今天跳過、明天照常；沒寫 `until` 的工作再晚都會補。
- 「每三天」是從**上次真的跑的那天**起算：晚兩天才跑，下一次就順延。
- 信寄不出去（queue 不在）＝退 1、`done.json` 不寫，下一次檢查再試。
- `done.json` 沒了（stack 重建、`ctl rm --purge`）＝當成從沒跑過，時間到了就各跑一次。

實測：

- 暫存樹：11:11:58 掛上（已過 09:00、星期五）→ 立刻寄一封列兩個工作，`done.json` 兩個都記今天，haiku 接到並回答；之後每 5 秒檢查都不再寄。睡著、把 `done.json` 兩個都改成昨天、叫醒 → 醒來那次（`first: true`）只寄 `patrol`（帶 `(last ran 2026-11-12, 1 days ago)`），`repo-status`（每三天）沒寄。
- 手跑各分支：還沒到 `at`、過了 `until`、不是指定星期、同一天第二次、每三天但才隔兩天——都不寄、退 0；隔五天——寄一次、帶「5 days ago」；queue 不在——退 1、`done.json` 沒動。

兩個使用上的提醒：信進 queue 之後跟一般訊息一樣排隊——腦正在忙就等這輪完；有人接在畫面上而且 `loop.json` 是 `--on-busy yield`（範本預設）時，等人離開才送（ops-agent 自己那份是 `answer`，會直接送）。還有，這封信是機器寄的：今天 a2a 的裁定施工之後，它會被標成「不是使用者打的」，所以巡檢裡需要使用者批准的動作不會因為這封信就被當成已批准——這是對的。

## 文件怎麼改（純文件，可以馬上做；正本在 `proto8/knowledge/aos/`，改完要重抄到 `~/aos-home/knowledge`）

1. `body.json#/brain_tools` 最後一句（跟[第 1 點](02-第1點-hook看不到CLI工具.md)改同一段），現在是：
   > `on_clock` is checked at the start of each cell (agent-fsm) or of each turn (eca).

   改成：
   > `on_clock` is checked at the start of each cell (agent-fsm). On eca it is checked about three times a second while you are idle, new messages or not; it is not checked while the CLI is answering a queue message, nor while you sleep.

2. `me/self_hook.json#/clock` 第一段，「Checked at the start of each of your steps;」那句後面加：
   > On eca a step is one pass of your loop (about three a second, also with an empty queue), not one answer. After a sleep the event says `first`: true and `missed`: 0: it does not tell you how long you slept; a handler that must catch up keeps its own record (`aos/me/self_hook.json#/daily`). No clock (`AOS_CLOCK` not set and no `clock` key): the hook never runs; your log gets one warning line.

3. `me/self_hook.json` 加一個 key `daily`（`_description` 的清單加一行指過去）：標題「A job at a wall time (every day at 09:00)」，放上面那支程式、掛法那一行、以及「睡醒怎麼補」那六點的英文版。`#/examples` 最後加一行指到它。
4. `clock.json#/choose` 第 3 種做法的例子後面加：
   > Another example: a job at a wall time (every day at 09:00, every 3 days): `aos/me/self_hook.json#/daily`.
5. `world.json` Time 段「No clock…cycles fall back to wall time…」那句後面加：
   > This is for waits; an `on_clock` hook needs a clock and does not run without one.
6. `templates/eca-claude/hooks.json` 的 description 不用動。

（另一種收法：把這支做成出廠的 hook 程式 `lib/agent/daily_notify`，工作清單放工作區一個 json，比照 `mail_notify`。這算新功能，先不提；等 ops-agent 的試點跑過再看值不值得收。）
