← [回入口 README.md](../README.md)｜段落：hook｜上一份：[05-gitignore指南](05-gitignore指南.md)

# hook：事件發生時，跑你指定的 aos 函數

**一句話**：在 agent 身上掛「某件事發生時跑這支」——信要進對話、工具要跑／跑完、腦叫失敗、多了工具、起來／停下、每一格前後、時鐘走到了；被跑的那支從 stdin 收到一份事件 JSON，在能改、能攔的點上還能改掉或攔下那件事。

使用者 11-10 晚：「還有self_hook，用於在有東西進到queue，或是一些事件發生，比如呼叫了某特定工具，比如brain呼叫失敗，或是新增了某些特定工具之類時，執行指定aos函數。」設計在 [圖紙](../../../../../thinking/2026-11/10/self-family/hook/01-圖紙.md)；11-21 使用者把整套簡化成「第四層」（[現在怎麼寫](../../../../../thinking/2026-11/21/hook-新格式施工-1121/01-現在怎麼寫.md)）：

- **引擎**（[py/aos/hook_run.py](../../../hook_run.py)）只做一件事：照名字一個一個起 handler、交回各自的退出碼與 stdout。框架站、`aos-hook fire` 用的同一份。
- **agent 一家自己的規矩**（哪些點能攔、能改哪些鍵、`condition` 比什麼、失敗怎麼算）寫在程式 [py/aos/agentlib/hooks.py](../../../agentlib/hooks.py) 的 `POINTS`；agent-fsm 四格、aos-eca-turn、aos-mcp、`aos-agent hook` 共用它。
- **宣告**（`hooks.json`）只是參考：給人和工具看「有哪些點、handler 收到什麼」，沒有任何程式因為「沒宣告」而不跑、不給掛。

## 事件

每個事件什麼時候發、事件 JSON 帶哪些欄位，寫在各身體的宣告檔：agent-fsm 四格 [templates/agent-fsm/hooks.json](../../../../../templates/agent-fsm/hooks.json)、起來與停下、每一格前後 [py/aos/apps/hook/loop_hooks.json](../../hook/loop_hooks.json)，eca 見下面「eca（縮水版）」。下表是手抄的 agent-fsm 版，[py/tests/test_hook_points_match.py](../../../../tests/test_hook_points_match.py) 比對點名與欄位名有沒有漏。

| 事件 | 什麼時候（agent-fsm） | 事件 JSON 多的欄位 | `condition` 比什麼 | 退 10／能改 |
|---|---|---|---|---|
| `before_queue` | idle：信從 queue 拿出來、進 history 之前（`/compact` 信先被挑走，不過這裡） | `letter`、`content` | 不收 condition | 攔（丟掉這封）；改 `content`（非空字串） |
| `after_queue` | idle：信進 history 之後 | `letter`、`content` | 不收 condition | — |
| `before_tool` | act：工具要跑之前 | `name`、`id`、`arguments`（解開的 JSON） | 工具名 | 攔（工具不跑）；改 `arguments` |
| `after_tool` | act：工具跑完、結果進 history 之前（被攔下的不觸發） | 上面三個＋`content`、`code`（逾時＝null）、`timed_out` | 工具名 | 改 `content`（字串） |
| `brain_failed` | wait：`LlmKernelMissing`／`SendFailed`／`BudgetMissing`（額度拒絕，11-14 AK17）／`BrainFailed`／`ReplyBad` 那一刻 | `name`（代號）、`reason`（一句話）；解到 kernel 的 error 物件時多 `error`（`BudgetMissing`、`BrainFailed`）；只有 `BrainFailed` 帶 `retry`（true＝等一下重送同一份、false＝agent 停）、`attempt`（連續第幾次失敗），kernel 的 error 有才帶 `code`（kernel 的代號）、`status`（HTTP 狀態），`retry` 為 true 才帶 `wait_s`（幾秒後再試） | 代號 | — |
| `tool_added` | think：工具清單多了名字（一個名字一次；第一次只記不觸發） | `name`、`path` | 工具名 | — |
| `after_start` | loop 起來、第一次之前（loop.json 的 `on_start` → `aos-hook fire --def`） | —（只有共通三欄） | 不收 condition | — |
| `after_stop` | loop 要退時（`on_stop`：stop、sleep、rm、daemon 收工、出錯停；kill -9 不跑） | —（要退的碼、訊號、原因在環境變數 `AOS_LOOP_CODE`、`AOS_LOOP_SIGNAL`、`AOS_LOOP_CAUSE`：`stop`／`sleep`／`remove`／`shutdown`／`stuck`／`signal`／`max`／`body_exit`／`error`，空的＝沒給；給程式比的代號，不是表上給人看的 `reason`） | 不收 condition | — |
| `before_run` | 每跑一格之前（loop.json 的 `on_before_run` → `aos-hook fire`；讀過 ctl、等過 `interval_ms` 之後；暫停中不發；loop.json 要有接這條線，見下面「每一格前後」） | —（第幾次在 `AOS_LOOP_RUNS`；要跑的那一格在 `<stack>/stage.txt`，第一圈還沒有這個檔＝fsm.json 的起始格） | 不收 condition | 退 10＝跳過這一圈：這格不跑、不算一次、不發 `after_run`，過 `interval_ms` 再問一次 |
| `after_run` | 每跑完一格之後（`on_after_run`；身體起不來、loop 收到訊號的那圈不發） | —（環境變數 `AOS_LOOP_RUNS`（跟 before_run 同一個數）、`AOS_LOOP_RUN_CODE`（那格的結束碼）、`AOS_LOOP_RUN_SIGNAL`（結束它的訊號，沒有＝空）、`AOS_LOOP_RUN_MS`（跑了多久）；表現在停在哪一格在 `<stack>/stage.txt`） | 不收 condition | — |
| `on_clock` | 每格開頭（idle、think、wait、act）看一次時鐘，條件到了才跑（見下面「時鐘」） | `clock`、`cycle`、`interval_ms`、`first`、`last_cycle`、`missed`；格裡寫了 `config` 才多 `config`（原樣） | 不收 condition（條件寫 `every_cycles`／`every_ms`） | — |

每份事件 JSON 都有 `event`、`hook`（這個 hook 的名字）、`stack`（agent 的 stack 絕對路徑）。同一事件多個 hook＝照名字排序一個一個跑；agent 自己發的點（表上前七個）前一個改過的後一個看得到，被攔下就不往下；經 `aos-hook fire` 發的四個 loop 點每個 handler 拿同一份事件。連鎖（hook 寄信給自己又觸發）不檢測，自行承擔。

## 起來與停下

使用者 11-11 選「起來與停下」、掛哪層選「aos-loop 自己加」、sleep 算停下（「算。然後hook這邊可以細分出更多細類。目前就先這樣就好。」；[thinking clock-hook](../../../../../thinking/2026-11/11/clock-hook/README.md)）。aos-loop 只認通用的 `on_start`／`on_stop` 鍵（[aos-loop 01](../../../../../cpp/aos-loop/docs/01-用法.md)），範本的 loop.json 把它們接到 [`aos-hook fire`](../../hook/README.md)：`aos-hook fire -q --stop-on-nonzero --def $AOS_CD after_start|after_stop`，照這隻 `interfaces.json` 的 `hookeds` 跑。事件 JSON 只有共通三欄；`after_stop` 的碼、訊號、原因 handler 自己讀環境變數 `AOS_LOOP_CODE`、`AOS_LOOP_SIGNAL`、`AOS_LOOP_CAUSE`。

- 跑得到：起來（`ctl add`／`start`、開門 wake、auto_restart 重起都是新起一支）；停下（`ctl stop`＝`AOS_LOOP_CODE` 0、`sleep`／`rm`／daemon 收工＝SIGTERM、碼 143、訊號 15、身體失敗＝那個碼）。
- 跑不到：kill -9（之後 auto_restart 重起會有一次 `after_start`、中間沒有 `after_stop`）；daemon 被 kill -9 後 adopt 接回的 loop 沒重起，不會再跑 `after_start`。pause 不算停下（loop 還活著）。
- 期限：loop 給這兩格 `on_timeout_ms`（預設 5000）——daemon 收工只等子項 10 秒；hook 自己的 `timeout_ms` 要更短，範本例子寫 5000 以內。
- hook 的退出碼經 `--stop-on-nonzero` 原樣交給 aos-loop（使用者 11-20 待裁第 2 題「四個點都跟著停」）：非 0＝agent 跟著停。`after_start` 的 hook 退非 0＝agent 起不來（表上 `aos-loop: error: PointFailed on_start …`）；`after_stop` 的 hook 退非 0 而本來要退 0＝改退它的碼。

## 每一格前後（before_run／after_run）

使用者 11-20 選「在 loop 層加通用的點」、「能攔」、「before_run / after_run」。aos-loop 每跑一次身體的前後各跑一次 loop.json 的 `on_before_run`／`on_after_run`，接到 `aos-hook fire -q --stop-on-nonzero --def $AOS_CD before_run|after_run`（[py/aos/apps/hook](../../hook/README.md)）。agent-fsm 的一次＝一格，eca 的一次＝一輪。

- **接不接線在編譯時決定**（使用者 11-21「編譯時決定」，沒有旗標檔了）：`aos.py.agent.defs` 編譯時有 hook 掛 `before_run`／`after_run`，loop.json 才寫那一鍵；沒人掛就不寫，閒著不多起行程。手寫的範本預設不接（loop.json 的 description 說怎麼加）。
- **事後才掛的**：`aos-agent hook add`（`self_hook`、gdb 下斷點都經它）掛 `before_run`／`after_run`（或 `after_start`／`after_stop`）而 loop.json 沒接那條線＝照樣寫進清單、多印一行 warning：要重新編譯定義（或照 `on_start` 的樣子手加那一鍵）並重起 agent。
- handler 要知道的東西不在事件裡：第幾次在 `AOS_LOOP_RUNS`；fsm 身體要跑（before_run）／停在（after_run）哪一格讀 `<stack>/stage.txt`（before_run 第一圈還沒有這個檔＝fsm.json 的起始格）；after_run 的結束碼、訊號、耗時在 `AOS_LOOP_RUN_CODE`、`AOS_LOOP_RUN_SIGNAL`、`AOS_LOOP_RUN_MS`。只想在某一格做事，handler 自己比 stage.txt。
- 退出碼原樣給 aos-loop：`before_run` 退 10＝跳過這一圈；其他非 0（四個點都一樣，`after_run` 退 10 也算）＝agent 停下（`PointFailed`）。
- `before_run` 退 0 之後 loop 會再讀一次 ctl：扣在 before_run 期間下的 stop／pause 會生效，那一格不跑。
- 成本：接了線的點每次起一支 `aos-hook`（約 36 毫秒起跳，加 handler 自己的）；閒著的 agent-fsm 每 300 毫秒就跑一格 idle，接了 `before_run` 等於每秒多 3 個行程。要定時做事用 `on_clock`。

## 時鐘（on_clock）

使用者 11-11：「就是說，因為現在hook本來就綁在loop上，所以hook就可以添加一個類型，就是loop每次exec前和exec後。然後這個exec前觸發的，就可以添加一個aos函數，使其去看指定的clock proc……每隔十個cycle就幹嘛，或是透過cycle換算，若超過十秒就幹嘛」；「時間到了沒」選「hook 格裡寫條件」。

```json
{"event": "on_clock", "every_ms": 300000, "handler": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_noop"}, "timeout_ms": 5000}
```

- **條件**二擇一：`every_cycles`（正整數）＝時鐘從上次跑到現在走了 N 格；`every_ms`＝同上，毫秒換成格數 `ceil(every_ms ÷ AOS_CLOCK_INTERVAL)`（沒設＝1000 ms 一格；看時鐘的格數、不看牆鐘）。只有 `on_clock` 收這三個鍵（別的事件寫了＝`HooksBad`）。
- **看哪個時鐘** `clock`：沒寫＝`$AOS_CLOCK`；有 `/` 或 `.` 開頭＝路徑（檔＝它、資料夾＝裡面的 `clock`，daemon 的 stack 就是這種佈局；相對＝從 agent 的 stack 算）；沒有 `/`＝`$AOS_DAEMON` 表上那一列的 stack 裡的 `clock`（那個 proc 要有 clock 檔；根的 `_clock` 列寫的是 daemon 自己 stack 的 `clock`，看根的鐘＝不寫或寫 daemon 的 stack）。
- **在哪判**：agent-fsm 四格、aos-eca-turn 每輪的最開頭呼叫 hook 遙控器的 `clock_tick`（`agentlib/agent_hooks.py` → `agentlib/hook_clock.py`）——讀時鐘檔、比 `$AOS_STACK/hookeds/<名>/on_clock.json` 記的 cycle，到了才起 handler；沒有這種 hook＝只讀清單（實測約 20 µs），一個沒到的 hook 約 40 µs。不是 aos-loop 每拍另起一支（那樣每 300 ms 多一支 aos-exec＋程式）。act 跑長工具時 loop 沒有拍，回來下一格才判。
- **到了怎麼算**：上次之後走了 ≥ N 格＝跑一次，把上次記成現在的 cycle（不補跑，`missed`＝中間錯過幾次）；忙完、pause 結束都只跑一次；睡著時 loop 不在、不判。
- **第一次立刻跑**（使用者 11-11 選「起來就先觸發一次」：「一起來立刻跑一次，之後照間隔。每次睡醒、重起也都會先跑一次。」）：沒有狀態檔、時鐘換了、cycle 倒退（根重起、換台）、或是換了一次 loop（狀態檔記著當時 `<stack>/state.json` 的 `boot_id`、`pid`、`started_at_ticks`，對不上＝ctl add／start、開門 wake、auto_restart，含 kill -9 之後的重起）＝馬上跑一次並記基準，事件 `first: true`、`last_cycle: null`、`missed: 0`。所以不管 loop.json 有沒有接 `on_start`，起來後第一次看時鐘一定跑一次；範本的 `timer` 因此每次起來都跑一次 hook_noop（什麼都不做，無害）。
- **時鐘不在**（`AOS_CLOCK` 沒設、檔不在、內容壞、proc 不在表上）＝不跑、不讓 agent 停；warning 只在原因變了時印一次（記在狀態檔）。
- handler 不讓腦看到任何東西（history 不多一則）；要叫腦就自己往事件 `stack` 的 `queue` 寄信（`aos-post send STACK/queue`，body `{"role": "user", "content": "…"}`）。stdout 不讀；失敗＝一行 warning（`on_clock` 不能攔）；`timeout_ms` 照通用語意。先記再跑：handler 失敗也不會每拍重跑。
- 兩個 hook 看同一個時鐘＝各記各的狀態檔。範本 agent-fsm、eca-claude 預設帶一格 `timer`（每 300000 ms、[hook_noop](../../../../tools/agent/hook_noop/_entry) 什麼都不做）當掛點，用同名蓋過去就換成自己的；另帶一格 `mail_notify`（每 60000 ms＝每 1 分鐘、[mail_notify](../../../../tools/agent/mail_notify/_entry)：有還沒通知過的新信才往 queue 寄一則 `[aos] new_mail: …`；`first`（起來、睡醒、重起那次）照 `notified.json` 比：睡前提醒過的不再提、睡著時新到的提醒一次，全新起來（沒有 `notified.json`，且 agent stack 的 `history.jsonl` 不在或是空的）＝只把信箱裡已經在等的記成已知；跑過的 stack（有非空 history）當睡醒，在等的提醒一次；[mail-notify](../../../../../thinking/2026-11/11/mail-notify.md)，間隔與 `first` 照使用者 11-11「每 1 分鐘」「只提醒新到的」「睡著時新到的要提」，[backlog-rulings](../../../../../thinking/2026-11/11/backlog-rulings.md)）。同一隻掛幾個 on_clock 都行，各自的間隔、各自的狀態檔（daemon 的時鐘是基礎間隔，每個 hook 各自除頻）；`hook rm mail_notify`＝免打擾、`hook add --replace -n mail_notify --event on_clock --every-ms N …`＝改間隔。

## 回話協定

agent 自己發的點（表上前七個）照 `agentlib/hooks.py` 的 `POINTS` 讀 handler 的回話：

| 結束碼 | 意思 |
|---|---|
| 0 | 放行。能改的三個點（`before_queue`、`before_tool`、`after_tool`）stdout 非空＝stdout 要是一個 JSON 物件，認得的鍵（`content`／`arguments`）拿來改；stdout 空＝不改。別的點 stdout 不讀 |
| 10 | 攔下（`before_queue`＝這封信收掉；`before_tool`＝工具不跑，腦看到的結果＝hook 的 stdout，空就給 `[aos] hook: tool NAME blocked by hook HOOK.`）；別的點的 10＝當 0 |
| 其他、逾時、起不來、stdout 不合（不是 JSON 物件、改的值型別不對） | hook 失敗：能攔的點（`before_queue`、`before_tool`）＝這個事件停（那格印 `agent-fsm: error: HookFailed …`、格程式退 1、agent 停下等人；aos-mcp 那次工具回 isError）；其他點＝一行 warning、下一個照跑 |

所以掛在能改的點上、只想記一筆的 hook，stdout 不要印東西（印了不是 JSON 物件的東西＝hook 失敗）。四個 loop 點的退出碼規矩見上面兩節（經 `--stop-on-nonzero` 原樣給 aos-loop）；`before_compact`／`after_compact` 見下面「eca」。

## 選項

**鍵名與事件名**照 C#／Java 的 hook 慣例（[tonight-rulings](../../../../../thinking/2026-11/10/tonight-rulings/README.md)；使用者 11-10「hook這塊，主要走A, 但filter改condition。」）。引擎只看 `event`、`handler`、`timeout_ms`；其餘是 agent 一家自己的鍵。

| 鍵（`add` 的旗標） | 意思 | 預設 |
|---|---|---|
| `event`（`--event`） | 事件名，必填；不驗（宣告只是參考，掛到這隻不會發的事件＝掛得上、不跑） | — |
| `handler`（XXX 或 `--path-json`） | 目標：aos-exec 跑得動的東西（工具夾、JSON、執行檔）或指示詞；相對路徑從寫它的那份檔的資料夾算 | — |
| `condition`（`--condition`，可重複） | 只在工具名／代號完全相等時跑（`before_tool`、`after_tool`、`tool_added`、`brain_failed`；使用者 11-21「1.對。」agent 一家保留這個寫法） | 全部 |
| `timeout_ms`（`--timeout-ms`） | 等它的上限，0＝不限時；到了整群收掉、算失敗 | 60000 |
| `every_cycles`／`every_ms`（`--every-cycles`／`--every-ms`） | `on_clock` 的條件，二擇一 | — |
| `clock`（`--clock`） | `on_clock` 看哪個時鐘：proc 名稱或路徑 | `$AOS_CLOCK` |
| `config`（`--config JSON`） | `on_clock` 才收：任意 JSON，原樣放進事件的 `config` 給 handler 讀（例 context_wrap 的 `{"percent": 50}`） | 不帶 |

queue 事件給 `--condition`＝`add` 直接 `ArgumentsBad`（由 `hooks.check_entry` 說原因）。以前的 `intercept`、`async`、`on_error` 拿掉了：格裡寫了也不讀。

## 兩份檔怎麼疊

- **interfaces.json 最外層**的兩鍵（值是檔名、指示詞，或它們的陣列；相對＝從定義夾算）：`hooks`＝有哪些鉤子（hook 點的宣告，只是參考）；`hookeds`＝有哪些被勾著（掛上去的 handler 清單）。agent-fsm 範本寫 `"hooks": [{"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_hooks.json"}, "hooks.json"], "hookeds": "hookeds.json"`；eca-claude、eca-pi 的 `hooks` 是 `loop_hooks.json`、`eca/hooks.json`、`mcp/hooks.json` 三個指示詞。沒寫 `hookeds`＝這隻沒有 hook（`aos-agent hook` 說 `HooksMissing`）。
- **定義那份** `<定義>/hookeds.json`、**這隻自己那份** `<stack>/hookeds.json`（跟 `hookeds` 寫的相對檔名同名），形狀一樣：`{"description": "一句話", "名字": {格} 或 null}`。讀法＝定義那份疊上自己那份：同名的蓋過去、`null`＝關掉定義裡那一個、檔不在＝沒有 hook。
- `aos-agent hook` **只寫自己那份**（先寫暫存再改名），定義不動；每次事件都重讀，改了下一個事件就生效（loop 點要 loop.json 有接線，見上面）。改定義＝直接編 `<定義>/hookeds.json`。
- handler 的工作夾：`<stack>/hookeds/<名>/`（事件 JSON 存成那裡的 `event.json` 從 stdin 給它；它自己的 `AOS_STACK` 就是這個夾）。

## 指令

```
aos-agent hook -t bob                       # = ls：NAME TAB EVENT TAB HANDLER
aos-agent hook -t bob ls -l                 # 多 CONDITION TIMEOUT_MS FROM，也列被設成 null 的
aos-agent hook -t bob ls --json             # 一個 JSON 陣列（帶 name 與 from）
aos-agent hook -t bob get guard             # 一格的 JSON
aos-agent hook -t bob add --event before_tool --condition agents_ctl --timeout-ms 5000 hooks/guard
aos-agent hook -t bob add --event brain_failed -n ping --path-json '{"$env": "AOS_HOME", "$path": "/lib/x"}'
aos-agent hook -t bob add --event on_clock --every-ms 600000 -n check hooks/check
aos-agent hook -t bob rm guard              # 定義裡有的＝寫 null；自己加的＝刪掉那格
aos-agent hook -t bob reset -y              # 刪自己那份，回到定義的
```

- 名字預設＝XXX 的檔名／夾名；`--path-json` 時一定要 `--name`。名字不能空、不能有 `/`、不能 `.` 開頭、不能叫 `description`（`NameBad`）。
- XXX 相對目前資料夾、不存在＝`PathMissing`；存法：絕對存絕對、相對存成「相對 stack 那份檔的資料夾」。
- 同名已在生效清單裡＝`HookExists`（加 `--replace`）；`rm`／`get` 沒這個名字＝`HookMissing`；清單壞＝`HooksBad`。
- agent 自己改用工具 [self_hook](../../../../tools/agent/self_hook/_entry)（`aos-agent hook --target 自己` 的純包裝）。

## 最小 hook 範例

擋掉腦叫 `agent_def` 工具時 `op` 是 `new` 的呼叫（造新定義）（`add --event before_tool --condition agent_def hooks/no_spawn`；結束碼 10 就算數）：

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

只想記一筆、不改什麼的（stdout 不印東西）：

```sh
#!/bin/sh
# log_letters - after_queue hook: append each letter to a log
cat >> "$HOME/letters.jsonl"
```

## eca 畫面延後關

範本有 `screen_linger_start`／`screen_linger_stop` 兩格 after_start／after_stop handler，前者排第一撤掉舊到期單，後者寫單並交 tmux 計時（4000 ms；以前的 `on_error: continue` 拿掉了，它輸入壞、讀寫失敗時退 1＝跟其他 loop 點一樣讓 loop 停）。定義 cli.json 的 screen_close_after_s 非負整數秒，預設 600，0 寫單後當場核身分關畫面。handler 用事件 stack，不是自己的 AOS_STACK；處理 claude、codex 小格。

start／wake 撤單，新活 loop 或新畫面不關；鎖忙 30 秒後再試、最多 10 次。有人接著看照關；stop／sleep／rm 或 daemon shutdown 有 after_stop 都會排，pause 不排。兩格在 stack 設 null 可停用，SIGKILL／OOM 與停著才開畫面第一批不補排。stack 的 hookeds 覆蓋須另外核對。`aos-agent ctl stop` 自己不關畫面（C′ B 包），全靠這兩格；`ctl rm`、`ctl set-def` 照舊當場關。

## eca（縮水版）

eca 的腦是外面的 CLI，aos 只看得到經過自己手的東西（圖紙 § 6）。事件名跟 agent-fsm 一樣，但有幾個意思不同（使用者 11-20 待裁第 3 題選「各自寫清楚就好」：不改行為、不改名，各身體寫清楚）；宣告檔：[py/aos/apps/eca/hooks.json](../../eca/hooks.json)（aos-eca-turn、compact_hook）、[py/aos/apps/mcp/hooks.json](../../mcp/hooks.json)（aos-mcp），起停與每輪前後同上面的 loop_hooks.json。

| 事件 | eca | 在哪 | 跟 agent-fsm 不同的地方 |
|---|---|---|---|
| `before_queue` | 有：每封好信交給 CLI 之前，**slash 信也過**；等回答時又來的信也過；每封只過一次（等回答時來的 slash 信當下不過、留到下一輪才過，使用者 11-20「修：只過一次」） | aos-eca-turn | agent-fsm 的 `/compact` 信不過 |
| `after_queue` | 有：信交給 CLI、接進 history、收掉之後；slash 那一輪也跑 | aos-eca-turn | 同（hook 失敗＝一行 warning） |
| `before_tool`／`after_tool` | 只有經 aos-mcp 叫的 aos 工具；欄位同上，但 `id`＝JSON-RPC 的 id 轉成字串（沒有＝空字串），`after_tool` 的 `content`＝各段文字併成一段 | aos-mcp 的 tools/call | CLI 自帶工具看不到；`before_tool` 的 hook 失敗＝那次工具呼叫回 isError、CLI 照樣往下，agent 不停；`after_tool` 的失敗＝一行 warning |
| `brain_failed` | 有：交給 CLI 之後 CLI 失敗；`name`＝`CliFailed`／`ReplyMissing`、`reason`；claude 另帶 `code`（同代號）、`retry`（true＝冷卻後重送）、`attempt`（連續第幾次）、`dropped`（丟掉幾封信）、`retry` 為 true 才帶 `wait_s`（冷卻幾秒），知道時帶 `status`（HTTP 狀態）、`cause`（CLI 自己說的失敗原因）；codex 只有 `name`、`reason` | aos-eca-turn | 代號與欄位不同，沒有 `error` 物件 |
| `tool_added` | 有（看 aos 登記檔的名單） | aos-eca-turn 每次交給 CLI 之前 | |
| `after_start`／`after_stop` | 有 | loop.json 的 `on_start`／`on_stop`（`aos-hook fire --def`） | 同 |
| `before_run`／`after_run` | 有：每一輪的前後（loop.json 接了線才有） | loop.json 的 `on_before_run`／`on_after_run`（aos-hook） | 一圈＝一輪；沒有 stage.txt |
| `on_clock` | 有（冷卻中、退讓的那輪也判） | aos-eca-turn 每輪最開頭 | 每輪看一次（agent-fsm 每格看一次） |
| `before_compact`／`after_compact` | 只有 claude 身、定義的 `cli.json` 掛了範本的 `compact_hook`（Claude Code 自己的 `PreCompact`／`PostCompact` hook）才有；pi、codex 沒有。`before_compact`：`trigger`（`manual`＝/compact、`auto`＝CLI 自己壓）、`asked`（/compact 後面的字）、`instructions`（compact_hook 給 CLI 的摘要指示，可改，空字串＝不給）、`restore`（null，可交一段字，壓完經 SessionStart 接進對話）；退 10＝攔下不壓（/compact 那封的回答是 CLI 說被誰攔下）。`after_compact`：`trigger`、`summary`（CLI 寫好的摘要），只告知 | `compact_hook`（經 `aos-hook fire --def $AOS_CLI_DEF`，自己讀結果：第一個退 10 的攔下；退 0 的 stdout 物件依名字順序設 `instructions`／`restore`，每個 handler 拿同一份事件；失敗的一行 warning） | agent-fsm 還沒有這兩個點（規劃在 thinking/2026-11/21/compact-改進規劃-1121/03）；壓縮本身是 CLI 的，摘要內容改不了 |
| CLI 自帶工具（Read、Bash…）、人在畫面上自己打的話 | 沒有 | 沒經過 aos | |
