← [回入口 README.md](../README.md)｜段落：hook｜上一份：[05-gitignore指南](05-gitignore指南.md)

# hook：事件發生時，跑你指定的 aos 函數

**一句話**：在 agent 身上掛「某件事發生時跑這支」——信要進對話、工具要跑／跑完、腦叫失敗、多了工具、起來／停下、每一格前後、時鐘走到了；被跑的那支從 stdin 收到一份事件 JSON，想的話還能改掉或攔下那件事。

使用者 11-10 晚：「還有self_hook，用於在有東西進到queue，或是一些事件發生，比如呼叫了某特定工具，比如brain呼叫失敗，或是新增了某些特定工具之類時，執行指定aos函數。」設計在 [圖紙](../../../../../thinking/2026-11/10/self-family/hook/01-圖紙.md)；讀清單、挑、跑、解回話全從 [py/aos/agentlib/hooks.py](../../../agentlib/hooks.py) 進去，四個格、aos-eca-turn、aos-mcp、`aos-agent hook` 共用它；挑、跑、解回話那段是共用引擎 [py/aos/hook_run.py](../../../hook_run.py)（框架站的 hook 也用同一份），`hooks.py` 自己管清單怎麼讀怎麼疊、`on_clock`、`tool_added`。

## 事件

每個事件什麼時候發、帶哪些欄位，以各身體的宣告檔為準（使用者 11-20 待裁第 4 題「事件欄位以宣告為唯一來源」選「要」）：agent-fsm 四格 [templates/agent-fsm/hook_points.json](../../../../../templates/agent-fsm/hook_points.json)、起來與停下、每一格前後 [py/aos/apps/hook/loop_points.json](../../hook/loop_points.json)，eca 見下面「eca（縮水版）」。下表是手抄的 agent-fsm 版，[py/tests/test_hook_points_match.py](../../../../tests/test_hook_points_match.py) 比對點名與欄位名有沒有漏。

| 事件 | 什麼時候（agent-fsm） | 事件 JSON 多的欄位 | `condition` 比什麼 | 能改 |
|---|---|---|---|---|
| `before_queue` | idle：信從 queue 拿出來、進 history 之前（`/compact` 信先被挑走，不過這裡） | `letter`、`content` | 不收 condition | 改 `content`、丟掉這封 |
| `after_queue` | idle：信進 history 之後 | `letter`、`content` | 不收 condition | 不能 |
| `before_tool` | act：工具要跑之前 | `name`、`id`、`arguments`（解開的 JSON） | 工具名 | 改 `arguments`、攔下不跑 |
| `after_tool` | act：工具跑完、結果進 history 之前（被攔下的不觸發） | 上面三個＋`content`、`code`（逾時＝null）、`timed_out` | 工具名 | 改 `content` |
| `brain_failed` | wait：`LlmKernelMissing`／`SendFailed`／`BudgetMissing`（額度拒絕，11-14 AK17）／`BrainFailed`／`ReplyBad` 那一刻 | `name`（代號）、`reason`（一句話）；解到 kernel 的 error 物件時多 `error`（`BudgetMissing`、`BrainFailed`）；只有 `BrainFailed` 帶 `retry`（true＝等一下重送同一份、false＝agent 停）、`attempt`（連續第幾次失敗），kernel 的 error 有才帶 `code`（kernel 的代號）、`status`（HTTP 狀態），`retry` 為 true 才帶 `wait_s`（幾秒後再試） | 代號 | 不能 |
| `tool_added` | think：工具清單多了名字（一個名字一次；第一次只記不觸發） | `name`、`path` | 工具名 | 不能 |
| `after_start` | loop 起來、第一次之前（loop.json 的 `on_start` → `aos-hook fire --agent`） | — | 不收 condition | 不能 |
| `after_stop` | loop 要退時（`on_stop`：stop、sleep、rm、daemon 收工、出錯停；kill -9 不跑） | `code`（要退的碼）、`signal`（收到的訊號，沒有＝null）、`cause`（為什麼停：`stop`／`sleep`／`remove`／`shutdown`／`stuck`／`signal`／`max`／`body_exit`／`error`，aos-loop 給什麼照抄，空的或沒給＝null；給程式比的代號，不是表上給人看的 `reason`） | 不收 condition | 不能 |
| `before_run` | 每跑一格之前（loop.json 的 `on_before_run` → `aos-hook fire`；讀過 ctl、等過 `interval_ms` 之後；暫停中不發；只在旗標檔 `hook_before_run.flag` 在時跑，見下面「每一格前後」） | `counter_runs`（這會是第幾次）、`stage`（要跑的那一格；第一圈還沒有 stage.txt 時用 fsm.json 的起始格） | 格名 | 攔下（退 10＝跳過這一圈：這格不跑、不算一次、不發 `after_run`，過 `interval_ms` 再問一次） |
| `after_run` | 每跑完一格之後（`on_after_run`；身體起不來、loop 收到訊號的那圈不發；旗標檔 `hook_after_run.flag`） | `counter_runs`（跟 before_run 同一個數）、`code`（那格的結束碼）、`signal`（結束它的訊號，沒有＝null）、`elapsed_ms`（跑了多久）、`next_stage`（表現在停在哪一格） | 不收 condition | 不能 |
| `on_clock` | 每格開頭（idle、think、wait、act）看一次時鐘，條件到了才跑（見下面「時鐘」） | `clock`、`cycle`、`interval_ms`、`first`、`last_cycle`、`missed`；格裡寫了 `config` 才多 `config`（原樣） | 不收 condition（條件寫 `every_cycles`／`every_ms`） | 不能 |

每份事件 JSON 都有 `event`、`hook`（這個 hook 的名字）、`stack`（agent 的 stack 絕對路徑）。同一事件多個 hook＝照名字排序一個一個跑，前一個改過的後一個看得到，被攔下就不往下。連鎖（hook 寄信給自己又觸發）不檢測，自行承擔。

## 起來與停下

使用者 11-11 選「起來與停下」、掛哪層選「aos-loop 自己加」、sleep 算停下（「算。然後hook這邊可以細分出更多細類。目前就先這樣就好。」；[thinking clock-hook](../../../../../thinking/2026-11/11/clock-hook/README.md)）。aos-loop 只認通用的 `on_start`／`on_stop` 鍵（[aos-loop 01](../../../../../cpp/aos-loop/docs/01-用法.md)），範本的 loop.json 把它們接到 [`aos-hook fire`](../../hook/README.md)（`aos-hook fire -q --agent $AOS_CD after_start|after_stop`；11-21 起，線 top-1121-hookfire，使用者「可以」），由它照這隻的 `hook_points` 與 hooks.json 發事件；`after_stop` 的 `code`、`signal`、`cause` 照宣告從 `AOS_LOOP_CODE`、`AOS_LOOP_SIGNAL`、`AOS_LOOP_CAUSE` 取。

- 跑得到：起來（`ctl add`／`start`、開門 wake、auto_restart 重起都是新起一支）；停下（`ctl stop`＝`code` 0、`sleep`／`rm`／daemon 收工＝SIGTERM `code` 143 `signal` 15、身體失敗＝那個碼）。
- 跑不到：kill -9（之後 auto_restart 重起會有一次 `after_start`、中間沒有 `after_stop`）；daemon 被 kill -9 後 adopt 接回的 loop 沒重起，不會再跑 `after_start`。pause 不算停下（loop 還活著）。
- 期限：loop 給這兩格 `on_timeout_ms`（預設 5000）——daemon 收工只等子項 10 秒；hook 自己的 `timeout_ms` 要更短，範本例子寫 5000 以內。
- hook 失敗（`on_error` stop）＝agent 跟著停（使用者 11-20 待裁第 2 題「四個點都跟著停」，aos-loop 11-20 起）：`after_start` 的 hook 失敗＝agent 起不來（表上 `aos-loop: error: PointFailed on_start …`）；`after_stop` 的 hook 失敗而本來要退 0＝改退它的碼。

## 每一格前後（before_run／after_run）

使用者 11-20 選「在 loop 層加通用的點」、「能攔」、「before_run / after_run」、「用旗標檔」。aos-loop 每跑一次身體的前後各跑一次 loop.json 的 `on_before_run`／`on_after_run`，範本把它們接到 `aos-hook fire --agent 定義資料夾 before_run|after_run`（[py/aos/apps/hook](../../hook/README.md)）。agent-fsm 的一次＝一格，eca 的一次＝一輪。

- **沒人掛時不多起行程**：`on_before_run_if`／`on_after_run_if` 指到 stack 裡的 `hook_before_run.flag`／`hook_after_run.flag`，檔在才跑。旗標檔由改清單的指令對：`aos-agent hook add／rm／reset`（`self_hook`、gdb 下斷點都經它）改完清單就照生效的那串建或刪；`aos-hook check --agent 定義資料夾 --stack STACK` 手動對一次。讀清單、發事件都不動旗標。
- **手改 hooks.json 的**（定義那份或 stack 那份）：旗標不會自己跟上，跑一次 `aos-hook check --agent … --stack …`。範本的起來（`on_start`＝`aos-hook fire … after_start`）也會照清單對一次，所以定義那份 hooks.json 一開始就掛了 before_run／after_run 的，起來就有旗標。
- `before_run` 退 0 之後 loop 會再讀一次 ctl：扣在 before_run 期間下的 stop／pause 會生效，那一格不跑。
- 成本：有人掛的點每次起一支 `aos-hook`（約 36 毫秒起跳，加 handler 自己的）；閒著的 agent-fsm 每 300 毫秒就跑一格 idle，掛了 `before_run` 等於每秒多 3 個行程。要定時做事用 `on_clock`。
- 失敗：同上「四個點都跟著停」，`before_run`／`after_run` 的 hook 失敗＝agent 停下（`PointFailed`）。

## 時鐘（on_clock）

使用者 11-11：「就是說，因為現在hook本來就綁在loop上，所以hook就可以添加一個類型，就是loop每次exec前和exec後。然後這個exec前觸發的，就可以添加一個aos函數，使其去看指定的clock proc……每隔十個cycle就幹嘛，或是透過cycle換算，若超過十秒就幹嘛」；「時間到了沒」選「hook 格裡寫條件」。

```json
{"event": "on_clock", "every_ms": 300000, "handler": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_noop"}, "on_error": "continue", "timeout_ms": 5000}
```

- **條件**二擇一：`every_cycles`（正整數）＝時鐘從上次跑到現在走了 N 格；`every_ms`＝同上，毫秒換成格數 `ceil(every_ms ÷ AOS_CLOCK_INTERVAL)`（沒設＝1000 ms 一格；看時鐘的格數、不看牆鐘）。只有 `on_clock` 收這三個鍵（別的事件寫了＝`HooksBad`）。
- **看哪個時鐘** `clock`：沒寫＝`$AOS_CLOCK`；有 `/` 或 `.` 開頭＝路徑（檔＝它、資料夾＝裡面的 `clock`，daemon 的 stack 就是這種佈局；相對＝從 agent 的 stack 算）；沒有 `/`＝`$AOS_DAEMON` 表上那一列的 stack 裡的 `clock`（那個 proc 要有 clock 檔；根的 `_clock` 列寫的是 daemon 自己 stack 的 `clock`，看根的鐘＝不寫或寫 daemon 的 stack）。
- **在哪判**：agent-fsm 四格、aos-eca-turn 每輪的最開頭呼叫 hook 遙控器的 `clock_tick`（`agentlib/agent_hooks.py` → `agentlib/hook_clock.py`）——讀時鐘檔、比 `$AOS_STACK/hooks/<名>/on_clock.json` 記的 cycle，到了才起 handler；沒有這種 hook＝只讀清單（實測約 20 µs），一個沒到的 hook 約 40 µs。不是 aos-loop 每拍另起一支（那樣每 300 ms 多一支 aos-exec＋程式）。act 跑長工具時 loop 沒有拍，回來下一格才判。
- **到了怎麼算**：上次之後走了 ≥ N 格＝跑一次，把上次記成現在的 cycle（不補跑，`missed`＝中間錯過幾次）；忙完、pause 結束都只跑一次；睡著時 loop 不在、不判。
- **第一次立刻跑**（使用者 11-11 選「起來就先觸發一次」：「一起來立刻跑一次，之後照間隔。每次睡醒、重起也都會先跑一次。」）：沒有狀態檔、時鐘換了、cycle 倒退（根重起、換台）＝馬上跑一次並記基準，事件 `first: true`、`last_cycle: null`、`missed: 0`。loop 每次起來（`aos-hook fire --agent … after_start`：ctl add／start、開門 wake、auto_restart，含 kill -9 之後的重起）先把各 hook 的狀態檔清掉，所以起來後第一次看時鐘一定跑一次；loop.json 沒有 `on_start` 的定義只有第一次與倒退會。範本的 `timer` 因此每次起來都跑一次 hook_noop（什麼都不做，無害）。
- **時鐘不在**（`AOS_CLOCK` 沒設、檔不在、內容壞、proc 不在表上）＝不跑、不讓 agent 停；warning 只在原因變了時印一次（記在狀態檔）。
- handler 不讓腦看到任何東西（history 不多一則）；要叫腦就自己往事件 `stack` 的 `queue` 寄信（`aos-post send STACK/queue`，body `{"role": "user", "content": "…"}`）。沒有回話可看（`intercept` 不讀）；`async`、`on_error`、`timeout_ms` 照通用語意。先記再跑：handler 失敗也不會每拍重跑。
- 兩個 hook 看同一個時鐘＝各記各的狀態檔。範本 agent-fsm、eca-claude 預設帶一格 `timer`（每 300000 ms、[hook_noop](../../../../tools/agent/hook_noop/_entry) 什麼都不做）當掛點，用同名蓋過去就換成自己的；另帶一格 `mail_notify`（每 60000 ms＝每 1 分鐘、[mail_notify](../../../../tools/agent/mail_notify/_entry)：有還沒通知過的新信才往 queue 寄一則 `[aos] new_mail: …`；`first`（起來、睡醒、重起那次）照 `notified.json` 比：睡前提醒過的不再提、睡著時新到的提醒一次，全新起來（沒有 `notified.json`，且 agent stack 的 `history.jsonl` 不在或是空的）＝只把信箱裡已經在等的記成已知；跑過的 stack（有非空 history）當睡醒，在等的提醒一次；[mail-notify](../../../../../thinking/2026-11/11/mail-notify.md)，間隔與 `first` 照使用者 11-11「每 1 分鐘」「只提醒新到的」「睡著時新到的要提」，[backlog-rulings](../../../../../thinking/2026-11/11/backlog-rulings.md)）。同一隻掛幾個 on_clock 都行，各自的間隔、各自的狀態檔（daemon 的時鐘是基礎間隔，每個 hook 各自除頻）；`hook rm mail_notify`＝免打擾、`hook add --replace -n mail_notify --event on_clock --every-ms N …`＝改間隔。

## 回話協定

`intercept` **預設開**（[tonight-rulings](../../../../../thinking/2026-11/10/tonight-rulings/README.md) 題 3，使用者 11-10「3.幫我改成預設是開」）：能改的三個事件（`before_queue`、`before_tool`、`after_tool`）看 hook 的回話；寫 `intercept: false`（`--no-intercept`）＝純通知、stdout 丟掉。不能改的事件、`async: true` 的 hook 本來就沒回話可看，`intercept` 開著也不讀、不報錯。所以掛在那三個事件上、只想記一筆的 hook，stdout 要嘛不印、要嘛加 `--no-intercept`，不然印了不是 JSON 的東西＝hook 失敗。

| 結束碼 | 意思 |
|---|---|
| 0 | 放行。`intercept` 開著而且 stdout 非空＝stdout 是一個 JSON 物件，認得的鍵（`content`／`arguments`）拿來改；stdout 空＝不改 |
| 10 | 攔下（`before_queue`＝這封信收掉；`before_tool`＝工具不跑，腦看到的結果＝hook 的 stdout，空就給 `[aos] hook: tool NAME blocked by hook HOOK.`；`before_run`＝跳過這一圈）；別的事件的 10＝當 0 |
| 其他、逾時、起不來、該是 JSON 卻不是 | hook 自己失敗：`on_error` 決定 |

## 選項

**鍵名與事件名**照 C#／Java 的 hook 慣例（[tonight-rulings](../../../../../thinking/2026-11/10/tonight-rulings/README.md)；頂層照慣例擬兩組，使用者 11-10「hook這塊，主要走A, 但filter改condition。」）。

| 鍵（`add` 的旗標） | 意思 | 預設 |
|---|---|---|
| `event`（`--event`） | 事件名，必填 | — |
| `handler`（XXX 或 `--path-json`） | 目標：aos-exec 跑得動的東西（工具夾、JSON、執行檔）；相對路徑從寫它的那份檔的資料夾算 | — |
| `condition`（`--condition`，可重複） | 只在工具名／代號／格名（`before_run`）完全相等時跑 | 全部 |
| `intercept`（`--no-intercept`＝false） | 看不看它的回話（只有那三個事件有回話可看；`before_run` 的退 10 也要它開著才算攔） | true |
| `async`（`--async`＝true） | true＝不等它跑完、放出去不管、不看回話 | false |
| `on_error`（`--on-error`） | `stop`＝那格印 `agent-fsm: error: HookFailed …`、agent 停下等人；`continue`＝一行 warning、當沒這個 hook | stop |
| `timeout_ms`（`--timeout-ms`） | 等它的上限，0＝不限時；到了整群收掉、算失敗 | 60000 |
| `every_cycles`／`every_ms`（`--every-cycles`／`--every-ms`） | `on_clock` 的條件，二擇一 | — |
| `clock`（`--clock`） | `on_clock` 看哪個時鐘：proc 名稱或路徑 | `$AOS_CLOCK` |
| `config`（`--config JSON`） | `on_clock` 才收：任意 JSON，原樣放進事件的 `config` 給 handler 讀（例 context_wrap 的 `{"percent": 50}`；11-16 ok-small，以前只能手寫格） | 不帶 |

queue 事件給 `--condition`＝`add` 直接 `ArgumentsBad`（由 `hooks.validate_entry` 說原因）。不能改的事件（`after_queue`、`brain_failed`、`tool_added`）或 `--async` 的 hook 寫 `intercept: true`＝不報錯、自然不看回話。

## 兩份檔怎麼疊

- **宣告**：定義的 `interfaces.json` 寫 `{"aos-agent": {"hooks": "hooks.json"}}`。沒宣告＝這隻沒有 hook（`aos-agent hook` 說 `HooksMissing`）。
- **這隻會發哪些點**：同一個 `aos-agent` 裡的 `hook_points`（11-20 hook 第 3 刀），一個清單，每項是一份 `hook_points.json` 的路徑（從定義夾算）或 `{"provider": "aos-loop"}`（`aos-loop`、`agent-fsm`、`eca`、`mcp` 是 aos 自己帶的）。agent-fsm 範本寫 `[{"provider": "aos-loop"}, "hook_points.json"]`；eca-claude、eca-pi 寫 `aos-loop`、`eca`、`mcp` 三個；編譯（有 fsm 又有 hooks）寫 `aos-loop`、`agent-fsm`。有 hook 卻沒寫 `hook_points`＝`HooksBad`。看一隻有哪些點、帶哪些欄位：`aos-hook points --agent 定義夾`。清單的事件名照 aos 自己帶的四份合起來驗：掛到這隻不會發的點＝掛得上、不跑、不報錯。
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
- agent 自己改用工具 [self_hook](../../../../tools/agent/self_hook/_entry)（`aos-agent hook --target 自己` 的純包裝）。

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

## eca 畫面延後關

範本有 `screen_linger_start`／`screen_linger_stop` 兩格 after_start／after_stop handler，前者排第一撤掉舊到期單，後者寫單並交 tmux 計時（on_error continue、4000 ms）。定義 cli.json 的 screen_close_after_s 非負整數秒，預設 600，0 寫單後當場核身分關畫面。handler 用事件 stack，不是自己的 AOS_STACK；處理 claude、codex 小格。

start／wake 撤單，新活 loop 或新畫面不關；鎖忙 30 秒後再試、最多 10 次。有人接著看照關；stop／sleep／rm 或 daemon shutdown 有 after_stop 都會排，pause 不排。兩格在 stack 設 null 可停用，SIGKILL／OOM 與停著才開畫面第一批不補排。stack hooks 覆蓋須另外核對。`aos-agent ctl stop` 自己不關畫面（C′ B 包），全靠這兩格；`ctl rm`、`ctl set-def` 照舊當場關。

## eca（縮水版）

eca 的腦是外面的 CLI，aos 只看得到經過自己手的東西（圖紙 § 6）。事件名跟 agent-fsm 一樣，但有幾個意思不同（使用者 11-20 待裁第 3 題選「各自寫清楚就好」：不改行為、不改名，各身體寫清楚）；以 eca 的宣告檔為準：[py/aos/apps/eca/hook_points.json](../../eca/hook_points.json)（aos-eca-turn）、[py/aos/apps/mcp/hook_points.json](../../mcp/hook_points.json)（aos-mcp），起停同上面的 loop_points.json。

| 事件 | eca | 在哪 | 跟 agent-fsm 不同的地方 |
|---|---|---|---|
| `before_queue` | 有：每封好信交給 CLI 之前，**slash 信也過**；等回答時又來的信也過；每封只過一次（等回答時來的 slash 信當下不過、留到下一輪才過，使用者 11-20「修：只過一次」） | aos-eca-turn | agent-fsm 的 `/compact` 信不過 |
| `after_queue` | 有：信交給 CLI、接進 history、收掉之後；slash 那一輪也跑 | aos-eca-turn | hook 失敗等回答接進 history 才報（agent-fsm 當場退 1） |
| `before_tool`／`after_tool` | 只有經 aos-mcp 叫的 aos 工具；欄位同上，但 `id`＝JSON-RPC 的 id 轉成字串（沒有＝空字串），`after_tool` 的 `content`＝各段文字併成一段 | aos-mcp 的 tools/call | CLI 自帶工具看不到；hook 失敗（`on_error` stop）＝那次工具呼叫回 isError、CLI 照樣往下，agent 不停 |
| `brain_failed` | 有：交給 CLI 之後 CLI 失敗；`name`＝`CliFailed`／`ReplyMissing`、`reason`；claude 另帶 `code`（同代號）、`retry`（true＝冷卻後重送）、`attempt`（連續第幾次）、`dropped`（丟掉幾封信）、`retry` 為 true 才帶 `wait_s`（冷卻幾秒），知道時帶 `status`（HTTP 狀態）、`cause`（CLI 自己說的失敗原因）；codex 只有 `name`、`reason` | aos-eca-turn | 代號與欄位不同，沒有 `error` 物件 |
| `tool_added` | 有（看 aos 登記檔的名單） | aos-eca-turn 每次交給 CLI 之前 | |
| `after_start`／`after_stop` | 有 | loop.json 的 `on_start`／`on_stop`（`aos-hook fire --agent`） | 同 |
| `before_run`／`after_run` | 有：每一輪的前後 | loop.json 的 `on_before_run`／`on_after_run`（aos-hook） | 一圈＝一輪；沒有 `stage`／`next_stage`（不帶） |
| `on_clock` | 有（冷卻中、退讓的那輪也判） | aos-eca-turn 每輪最開頭 | 每輪看一次（agent-fsm 每格看一次） |
| `before_compact`／`after_compact` | 只有 claude 身、定義的 `cli.json` 掛了範本的 `compact_hook`（Claude Code 自己的 `PreCompact`／`PostCompact` hook）才有；pi、codex 沒有。`before_compact`：`trigger`（`manual`＝/compact、`auto`＝CLI 自己壓）、`asked`（/compact 後面的字）、`instructions`（compact_hook 給 CLI 的摘要指示，可改，空字串＝不給）、`restore`（null，可交一段字，壓完經 SessionStart 接進對話）；退 10＝攔下不壓（/compact 那封的回答是 CLI 說被誰攔下）。`after_compact`：`trigger`、`summary`（CLI 寫好的摘要），只告知 | `compact_hook`（經 `aos-hook fire --agent $AOS_CLI_DEF`，11-21） | agent-fsm 還沒有這兩個點（規劃在 thinking/2026-11/21/compact-改進規劃-1121/03）；壓縮本身是 CLI 的，摘要內容改不了 |
| CLI 自帶工具（Read、Bash…）、人在畫面上自己打的話 | 沒有 | 沒經過 aos | |
