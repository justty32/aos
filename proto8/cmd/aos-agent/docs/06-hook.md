← [回入口 README.md](../README.md)｜段落：hook（11-10 晚）｜上一份：[05-gitignore指南](05-gitignore指南.md)

# hook：事件發生時，跑你指定的 aos 函數

**一句話**：在 agent 身上掛「某件事發生時跑這支」——信要進對話、工具要跑／跑完、腦叫失敗、多了工具、起來／停下、時鐘走到了（後兩組 11-11）；被跑的那支從 stdin 收到一份事件 JSON，想的話還能改掉或攔下那件事。

使用者 11-10 晚：「還有self_hook，用於在有東西進到queue，或是一些事件發生，比如呼叫了某特定工具，比如brain呼叫失敗，或是新增了某些特定工具之類時，執行指定aos函數。」設計在 [圖紙](../../../thinking/2026-11/10/self-family/hook/01-圖紙.md)；讀清單、挑、跑、解回話全在 [lib/agent/hooks.py](../../../lib/agent/hooks.py)，四個格、aos-eca-turn、aos-mcp、`aos-agent hook` 共用它。

## 事件

| 事件 | 什麼時候（agent-fsm） | 事件 JSON 多的欄位 | `condition` 比什麼 | 能改 |
|---|---|---|---|---|
| `before_queue` | idle：信從 queue 拿出來、進 history 之前 | `letter`、`content` | 不收 condition | 改 `content`、丟掉這封 |
| `after_queue` | idle：信進 history 之後 | `letter`、`content` | 不收 condition | 不能 |
| `before_tool` | act：工具要跑之前 | `name`、`id`、`arguments`（解開的 JSON） | 工具名 | 改 `arguments`、攔下不跑 |
| `after_tool` | act：工具跑完、結果進 history 之前（被攔下的不觸發） | 上面三個＋`content`、`code`（逾時＝null）、`timed_out` | 工具名 | 改 `content` |
| `brain_failed` | wait：`BrainFailed`／`SendFailed`／`ReplyBad` 那一刻 | `name`（代號）、`reason` | 代號 | 不能 |
| `tool_added` | think：工具清單多了名字（一個名字一次；第一次只記不觸發） | `name`、`path` | 工具名 | 不能 |
| `after_start` | loop 起來、第一次之前（loop.json 的 `on_start` → `lib/agent/hook_fire`；11-11） | — | 不收 condition | 不能 |
| `after_stop` | loop 要退時（`on_stop`：stop、sleep、rm、daemon 收工、出錯停；kill -9 不跑；11-11） | `code`（要退的碼）、`signal`（收到的訊號，沒有＝null） | 不收 condition | 不能 |
| `on_clock` | 每格開頭（idle、think、wait、act）看一次時鐘，條件到了才跑（11-11，見下面「時鐘」；事件名先代定 `clock_due`，使用者改裁 `on_clock`） | `clock`、`cycle`、`interval_ms`、`first`、`last_cycle`、`missed` | 不收 condition（條件寫 `every_cycles`／`every_ms`） | 不能 |

每份事件 JSON 都有 `event`、`hook`（這個 hook 的名字）、`stack`（agent 的 stack 絕對路徑）。同一事件多個 hook＝照名字排序一個一個跑，前一個改過的後一個看得到，被攔下就不往下。連鎖（hook 寄信給自己又觸發）不檢測，自行承擔。

## 起來與停下（11-11）

使用者 11-11 選「起來與停下」、掛哪層選「aos-loop 自己加」、sleep 算停下（「算。然後hook這邊可以細分出更多細類。目前就先這樣就好。」；[thinking clock-hook](../../../thinking/2026-11/11/clock-hook/README.md)）。aos-loop 只認通用的 `on_start`／`on_stop` 鍵（[aos-loop 01](../../../impls/aos-loop/docs/01-用法.md)），範本的 loop.json 把它們指到 [`lib/agent/hook_fire`](../../../lib/agent/hook_fire/_entry)（`hook_fire after_start|after_stop 定義資料夾`），由它照 hooks.json 發事件。

- 跑得到：起來（`ctl add`／`start`、開門 wake、auto_restart 重起都是新起一支）；停下（`ctl stop`＝`code` 0、`sleep`／`rm`／daemon 收工＝SIGTERM `code` 143 `signal` 15、身體失敗＝那個碼）。
- 跑不到：kill -9（之後 auto_restart 重起會有一次 `after_start`、中間沒有 `after_stop`）；daemon 被 kill -9 後 adopt 接回的 loop 沒重起，不會再跑 `after_start`。pause 不算停下（loop 還活著）。
- 期限：loop 給這兩格 `on_timeout_ms`（預設 5000）——daemon 收工只等子項 10 秒；hook 自己的 `timeout_ms` 要更短，範本例子寫 5000 以內。hook 失敗只讓 hook_fire 印錯誤行、aos-loop 印一行 warning，agent 照起、照停。

## 時鐘（on_clock，11-11）

使用者 11-11：「就是說，因為現在hook本來就綁在loop上，所以hook就可以添加一個類型，就是loop每次exec前和exec後。然後這個exec前觸發的，就可以添加一個aos函數，使其去看指定的clock proc……每隔十個cycle就幹嘛，或是透過cycle換算，若超過十秒就幹嘛」；「時間到了沒」選「hook 格裡寫條件」。

```json
{"event": "on_clock", "every_ms": 300000, "handler": {"$env": "AOS_HOME", "$path": "/lib/agent/hook_noop"}, "on_error": "continue", "timeout_ms": 5000}
```

- **條件**二擇一：`every_cycles`（正整數）＝時鐘從上次跑到現在走了 N 格；`every_ms`＝同上，毫秒換成格數 `ceil(every_ms ÷ AOS_CLOCK_INTERVAL)`（沒設＝1000 ms 一格；看時鐘的格數、不看牆鐘）。只有 `on_clock` 收這三個鍵（別的事件寫了＝`HooksBad`）。
- **看哪個時鐘** `clock`：沒寫＝`$AOS_CLOCK`；有 `/` 或 `.` 開頭＝路徑（檔＝它、資料夾＝裡面的 `clock`，daemon 的 stack 就是這種佈局；相對＝從 agent 的 stack 算）；沒有 `/`＝`$AOS_DAEMON` 表上那一列的 stack 裡的 `clock`（那個 proc 要有 clock 檔；根的 `_clock` 列寫的是 daemon 自己 stack 的 `clock`，看根的鐘＝不寫或寫 daemon 的 stack）。
- **在哪判**：agent-fsm 四格、aos-eca-turn 每輪的最開頭呼叫 `hooks.clock_tick`——讀時鐘檔、比 `$AOS_STACK/hooks/<名>/on_clock.json` 記的 cycle，到了才起 handler；沒有這種 hook＝只讀清單（實測約 20 µs），一個沒到的 hook 約 40 µs。不是 aos-loop 每拍另起一支（那樣每 300 ms 多一支 aos-exec＋程式）。act 跑長工具時 loop 沒有拍，回來下一格才判。
- **到了怎麼算**：上次之後走了 ≥ N 格＝跑一次，把上次記成現在的 cycle（不補跑，`missed`＝中間錯過幾次）；忙完、pause 結束都只跑一次；睡著時 loop 不在、不判。
- **第一次立刻跑**（使用者 11-11 選「起來就先觸發一次」：「一起來立刻跑一次，之後照間隔。每次睡醒、重起也都會先跑一次。」）：沒有狀態檔、時鐘換了、cycle 倒退（根重起、換台）＝馬上跑一次並記基準，事件 `first: true`、`last_cycle: null`、`missed: 0`。loop 每次起來（`hook_fire after_start`：ctl add／start、開門 wake、auto_restart，含 kill -9 之後的重起）先把各 hook 的狀態檔清掉，所以起來後第一次看時鐘一定跑一次；沒有 `on_start` 的舊定義只有第一次與倒退會。範本的 `timer` 因此每次起來都跑一次 hook_noop（什麼都不做，無害）。
- **時鐘不在**（`AOS_CLOCK` 沒設、檔不在、內容壞、proc 不在表上）＝不跑、不讓 agent 停；warning 只在原因變了時印一次（記在狀態檔）。
- handler 不讓腦看到任何東西（history 不多一則）；要叫腦就自己往事件 `stack` 的 `queue` 寄信（`aos-post send STACK/queue`，body `{"role": "user", "content": "…"}`）。沒有回話可看（`intercept` 不讀）；`async`、`on_error`、`timeout_ms` 照通用語意。先記再跑：handler 失敗也不會每拍重跑。
- 兩個 hook 看同一個時鐘＝各記各的狀態檔。範本 agent-fsm、eca-claude 預設帶一格 `timer`（每 300000 ms、[hook_noop](../../../lib/agent/hook_noop/_entry) 什麼都不做）當掛點，用同名蓋過去就換成自己的；另帶一格 `mail_notify`（每 60000 ms＝每 1 分鐘、[mail_notify](../../../lib/agent/mail_notify/_entry)：有還沒通知過的新信才往 queue 寄一則 `[aos] new_mail: …`；`first`（起來、睡醒、重起那次）不提醒、只把信箱裡已經在等的記成已知；11-11 [mail-notify](../../../thinking/2026-11/11/mail-notify.md)，間隔與 `first` 同日使用者翻案「每 1 分鐘」「只提醒新到的」，[backlog-rulings](../../../thinking/2026-11/11/backlog-rulings.md)）。同一隻掛幾個 on_clock 都行，各自的間隔、各自的狀態檔（daemon 的時鐘是基礎間隔，每個 hook 各自除頻）；`hook rm mail_notify`＝免打擾、`hook add --replace -n mail_notify --event on_clock --every-ms N …`＝改間隔。

## 回話協定

`intercept` **預設開**（11-10 深夜 [tonight-rulings](../../../thinking/2026-11/10/tonight-rulings/README.md) 題 3，使用者「3.幫我改成預設是開」）：能改的三個事件（`before_queue`、`before_tool`、`after_tool`）看 hook 的回話；寫 `intercept: false`（`--no-intercept`）＝純通知、stdout 丟掉。不能改的事件、`async: true` 的 hook 本來就沒回話可看，`intercept` 開著也不讀、不報錯。所以掛在那三個事件上、只想記一筆的 hook，stdout 要嘛不印、要嘛加 `--no-intercept`，不然印了不是 JSON 的東西＝hook 失敗。

| 結束碼 | 意思 |
|---|---|
| 0 | 放行。`intercept` 開著而且 stdout 非空＝stdout 是一個 JSON 物件，認得的鍵（`content`／`arguments`）拿來改；stdout 空＝不改 |
| 10 | 攔下（`before_queue`＝這封信收掉；`before_tool`＝工具不跑，腦看到的結果＝hook 的 stdout，空就給 `[aos] hook: tool NAME blocked by hook HOOK.`）；別的事件的 10＝當 0 |
| 其他、逾時、起不來、該是 JSON 卻不是 | hook 自己失敗：`on_error` 決定 |

## 選項

**名字 11-10 深夜改**（[tonight-rulings](../../../thinking/2026-11/10/tonight-rulings/README.md)；頂層照 C#／Java 的 hook 慣例擬兩組，使用者「hook這塊，主要走A, 但filter改condition。」）：`on`→`event`、`exec`→`handler`、`match`→`condition`、`change`→`intercept`、`wait`→`async`（意思反過來）、`on_fail`→`on_error`、`timeout_ms` 不動；事件 `queue_before`→`before_queue`、`queue_after`→`after_queue`、`tool_before`→`before_tool`、`tool_after`→`after_tool`，`brain_failed`、`tool_added` 不動。不留舊名；**要重建什麼**：舊名寫的 `hooks.json`（定義與 stack 兩份）照新名重寫，或 `aos-agent hook reset -y` 後重加。

| 鍵（`add` 的旗標） | 意思 | 預設 |
|---|---|---|
| `event`（`--event`） | 事件名，必填 | — |
| `handler`（XXX 或 `--path-json`） | 目標：aos-exec 跑得動的東西（工具夾、JSON、執行檔）；相對路徑從寫它的那份檔的資料夾算 | — |
| `condition`（`--condition`，可重複） | 只在工具名／代號完全相等時跑 | 全部 |
| `intercept`（`--no-intercept`＝false） | 看不看它的回話（只有那三個事件有回話可看） | true |
| `async`（`--async`＝true） | true＝不等它跑完、放出去不管、不看回話 | false |
| `on_error`（`--on-error`） | `stop`＝那格印 `agent-fsm: error: HookFailed …`、agent 停下等人；`continue`＝一行 warning、當沒這個 hook | stop |
| `timeout_ms`（`--timeout-ms`） | 等它的上限，到了整群收掉、算失敗 | 60000 |
| `every_cycles`／`every_ms`（`--every-cycles`／`--every-ms`） | `on_clock` 的條件，二擇一（11-11） | — |
| `clock`（`--clock`） | `on_clock` 看哪個時鐘：proc 名稱或路徑（11-11） | `$AOS_CLOCK` |

queue 事件給 `--condition`＝`add` 直接 `ArgumentsBad`（由 `hooks.validate_entry` 說原因）。不能改的事件（`after_queue`、`brain_failed`、`tool_added`）或 `--async` 的 hook 寫 `intercept: true`＝不報錯、自然不看回話（11-10 深夜改，以前是 `ArgumentsBad`）。

## 兩份檔怎麼疊

- **宣告**：定義的 `interfaces.json` 寫 `{"aos-agent": {"hooks": "hooks.json"}}`。沒宣告＝這隻沒有 hook（`aos-agent hook` 說 `HooksMissing`）。
- **定義那份** `<定義>/hooks.json`、**這隻自己那份** `<stack>/hooks.json`，形狀一樣：`{"hooks": {"名字": {格} 或 null}}`。讀法＝定義那份疊上自己那份：同名的蓋過去、`null`＝關掉定義裡那一個。
- `aos-agent hook` **只寫自己那份**（先寫暫存再改名），定義不動；每次事件都重讀，改了下一個事件就生效。改定義＝直接編 `<定義>/hooks.json`。

## 指令

```
aos-agent hook -t bob                       # = ls：NAME TAB EVENT TAB HANDLER
aos-agent hook -t bob ls -l                 # 多 CONDITION ASYNC ON_ERROR INTERCEPT TIMEOUT_MS FROM，也列被設成 null 的
aos-agent hook -t bob ls --json             # 一個 JSON 陣列（補完預設、帶 name 與 from）
aos-agent hook -t bob get guard             # 一格的 JSON
aos-agent hook -t bob add --event before_tool --condition agents_ctl hooks/guard
aos-agent hook -t bob add --event brain_failed --on-error continue --async -n ping --path-json '{"$env": "AOS_HOME", "$path": "/lib/x"}'
aos-agent hook -t bob add --event on_clock --every-ms 600000 --on-error continue -n check hooks/check
aos-agent hook -t bob rm guard              # 定義裡有的＝寫 null；自己加的＝刪掉那格
aos-agent hook -t bob reset -y              # 刪自己那份，回到定義的
```

- 名字預設＝XXX 的檔名／夾名；`--path-json` 時一定要 `--name`。名字不能空、不能有 `/`、不能 `.` 開頭（`NameBad`）。
- XXX 相對目前資料夾、不存在＝`PathMissing`；存法：絕對存絕對、相對存成「相對 stack 那份檔的資料夾」。
- 同名已在生效清單裡＝`HookExists`（加 `--replace`）；`rm`／`get` 沒這個名字＝`HookMissing`；清單壞＝`HooksBad`。
- agent 自己改用工具 [self_hook](../../../lib/agent/self_hook/_entry)（`aos-agent hook --target 自己` 的純包裝）。

## 最小 hook 範例

擋掉腦叫 `agent_def` 工具時 `op` 是 `new` 的呼叫（造新定義）（`add --event before_tool --condition agent_def hooks/no_spawn`；`intercept` 預設開，結束碼 10 就算數）：

```python
#!/usr/bin/env python3
# no_spawn - before_tool hook: block agent_def {"op": "new"}
import json, sys
ev = json.load(sys.stdin)
if isinstance(ev["arguments"], dict) and ev["arguments"].get("op") == "new":
    print("making new agents is turned off by hook %s" % ev["hook"])   # what the brain sees as the tool result
    sys.exit(10)
sys.exit(0)                                                  # empty stdout = no change
```

只想記一筆、不改什麼的（`after_queue` 沒回話可看；掛在能改的事件上就加 `--no-intercept`）：

```sh
#!/bin/sh
# log_letters - after_queue hook: append each letter to a log
cat >> "$HOME/letters.jsonl"
```

## eca（縮水版）

eca 的腦是外面的 CLI，aos 只看得到經過自己手的東西（圖紙 § 6）：

| 事件 | eca | 在哪 |
|---|---|---|
| `before_queue`／`after_queue` | 有 | aos-eca-turn 讀信、交給 CLI 之前／信接進 history 之後 |
| `before_tool`／`after_tool` | 只有經 aos-mcp 叫的 aos 工具 | aos-mcp 的 tools/call |
| `brain_failed` | 有（`name`＝`CliFailed`／`ReplyMissing`） | aos-eca-turn |
| `tool_added` | 有（看 aos 登記檔的名單） | aos-eca-turn 每輪開頭 |
| `after_start`／`after_stop` | 有 | loop.json 的 `on_start`／`on_stop`（hook_fire） |
| `on_clock` | 有（冷卻中、退讓的那輪也判） | aos-eca-turn 每輪最開頭 |
| CLI 自帶工具（Read、Bash…）、人在畫面上自己打的話 | 沒有 | 沒經過 aos |
