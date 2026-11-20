# 「提供 hook 點」的介面：施工第 2 刀的後半（發事件的程式全部改用 hook 遙控器；lists.py 刪掉；hooks.py 拆到 207 行）

← [當天索引](README.md)｜設計 [aos-hook-plan-1120](aos-hook-plan-1120/README.md)（小函式 [04](aos-hook-plan-1120/04-小函式.md)、刀 2 在 [09b](aos-hook-plan-1120/09b-施工計劃-逐刀.md#刀-2呼叫端收成把手表照舊行為不變)，對不上以 [12 採納表](aos-hook-plan-1120/12-採納表.md) 為準）｜使用者已答 [13](aos-hook-plan-1120/13-使用者已答.md)｜前半 [aos-hook-k2-1120](aos-hook-k2-1120.md)｜第 4 刀 [aos-hook-k4-1120](aos-hook-k4-1120.md)

線 aos-hook-k2b-1120，11-20 公司 WSL。頂層派、線隊長做。依據：方向第 1 題「宣告式＋小函式都做」；使用者 11-20「lists.py可以刪掉」「舊的教學我都沒在用，現有的aos體系我也都沒在用。所以放心弄。」（＝不顧相容）。前半（`b5d09fa71`）已 install，所以這一半的格程式存檔時 lib 裡已有 `agent_hooks`（F1 的順序守住了）。

## 結論

- **發事件的程式全部經 hook 遙控器**：agent-fsm 四格（與 start-api 的 ann 抄本，逐 byte 相同）、aos-eca-turn、aos-mcp、kernel（`py/tools/aos/kernel/`，kernel_llm 經同一份 round）、`hook_fire`。各自的 `fire()` 包裝、三段重抄（丟信三步、被攔的預設字、tool_added 那串）、`cell_common.clock_tick`、mcp 自己造的空結果、kernel round 的接錯都拿掉了。
- grep（程式，不含測試與文件）：「dropped by hook」「tool … blocked by hook」各只剩 `agentlib/agent_hooks.py` 一處（09b 刀 2 的驗收）。
- `py/aos/apps/hook/lists.py` 刪掉：`--points`／`--list` 那半併進 `apps/hook/main.py`，`--agent` 那半成為 `agent_hooks.source`。
- `agentlib/hooks.py` 350 → 207 行：on_clock 的看時鐘（`clock_tick`、`clock_restart` 與它們的小函式）搬到新檔 `agentlib/hook_clock.py`（155 行），一字不改；格的鍵（`CLOCK_EVENT`、`CLOCK_KEYS`）與驗法（`check_clock`）留在 hooks.py。
- 行為沒變：全套逐夾比對見「測試」；假腦＋真 daemon 的暫存樹在新舊兩份複本跑同一支腳本，輸出相同（見「實跑」）。唯一設計就說會變的是 eca 的 F9（見「行為變了的一處」）。

## 改了哪些檔

| 檔 | 改什麼 |
|---|---|
| `templates/agent-fsm/idle.py`、`act.py`、`brain.py`、`wait.py` | 每格在 stack 確定後開 `H = agent_hooks.open(AOS_CD 或 ".", stack, fail=die, warn=…)`、`H.clock_tick()`；idle `H.take_letter`（回 None＝被攔下、已收掉）、`H.fire("after_queue")`；act `H.guard_tool`（回的 arguments `is not` 原物件＝改過，才重 `json.dumps`）、`H.fire("after_tool")`；brain `H.announce_tools([...])`；wait `H.fire("brain_failed")`。檔頭註解跟著改 |
| `templates/agent-fsm/cell_common.py` | `clock_tick` 拿掉，檔頭那句換 |
| `templates/start-api/agents/ann/` 同五支 | 抄本，`cmp` 全同（`templates/tests/test_start.py` 綠） |
| `py/aos/apps/eca/hook.py` | 改成 `open_hooks(template, stack)`（fail 丟 `Fail`）、`before_queue(hooks, box, sig, body)`（`take_letter`）、`tool_added(hooks, cfg)`（`announce_tools(函式)`：有人掛才叫 aos-tools） |
| `py/aos/apps/eca/turn.py`、`batch.py`、`midturn.py`、`handoff.py`、`slash.py`、`common.py` | `one_turn` 開一次、一路傳下去（F8）：`redo_turn`、`pick_one`、`before_queue`、`tool_added`、`Handoff(hooks, stack, …)`（定義夾取 `hooks.def_folder` 給 cli_ask）、`More(hand, stack, box)`（用 `hand.hooks`）、`slash_turn(…, hooks, …)`（原本 `template` 的位置）；common 不再 import `agentlib.hooks` |
| `py/aos/apps/eca/main_turn.py` | 檔頭 ⑪⑫ 兩句 |
| `py/aos/apps/mcp/main.py` | `main` 開一次 `H = agent_hooks.open(HOOKS, stack, fail=hook_stop, …)`（`HOOKS` None＝空遙控器）；`fire()` 與空結果拿掉；before_tool 換 `guard_tool` |
| `py/tools/aos/kernel/hooks.py`、`round.py` | `hooks.open(ctx)`＝`hook_point.open(table=EVENTS, entries=lambda: ctx.cfg["hooks"], fail=ctx.die, warn=ctx.warn, check=…)`，`round.run` 設 `ctx.hooks`；三個時機經它發；after_verdict 用 `names()`＋`fire(only=[名])`；round.py 的 `try … except HookFailed: ctx.die(…)` 拿掉（整段縮排退一層，內容沒動） |
| `py/tools/agent/hook_fire/_entry` | `agent_hooks.open(DEF_DIR, stack, fail=die, warn=warn).fire(…)`、`hook_clock.clock_restart`；介面不變（F11） |
| `py/aos/agentlib/hooks.py` | on_clock 那段搬走；檔頭「對外」改寫（發事件的都經遙控器；`fire`、`has` 留到第 3 刀） |
| `py/aos/agentlib/hook_clock.py` | 新：`clock_tick`、`clock_restart`、`CLOCK_STATE` 與小函式，從 hooks.py 原樣搬來 |
| `py/aos/agentlib/agent_hooks.py` | `clock_tick` 叫 `hook_clock`；加 `source(def_dir, stack, fail)`（原 lists.py 的 `--agent` 那半） |
| `py/aos/apps/hook/main.py` | `declared()` 自己做 `--points`／`--list`，`--agent` 交 `agent_hooks.source`（照舊只在用到時才 import agentlib）；after_start 清狀態叫 `hook_clock` |
| `py/aos/apps/hook/lists.py` | **刪** |
| `py/aos/apps/hook/__init__.py`、`README.md`、`py/aos/hook_point.py` 檔頭 | 跟著改 |
| `py/aos/apps/agent/hook.py` | 只有一句 docstring（`hooks.clock_tick` → `hook_clock.clock_tick`） |
| `templates/tests/agent-fsm/test_clock_hook.py`、`py/tests/test_on_clock_kernel.py` | 只改 import 與叫法（`hooks.clock_tick` → `hook_clock.clock_tick`、`patch.object(hooks.subprocess, …)` → `hook_clock.subprocess`）；斷言沒動 |
| `templates/tests/agent-fsm/test_clock_hook_daemon.py` | 一行註解 |
| `py/tools/aos/kernel/tests/test_refuse_extra.py` | 假的 `hooks.fire` 改成假的 `ctx.hooks`（見「測試」）；斷言沒動 |
| `knowledge/aos/cli/hook_points.json` | 拿掉「`--agent DEF_DIR` is not available yet」，改寫 `--agent` 做什麼；加一句 Python 提供者直接 `aos.hook_point.open`（暫存檔再改名） |
| `py/aos/apps/agent/docs/06-hook.md`、`templates/docs/02-agent-fsm.md` | 「`hooks.clock_tick`」改成遙控器的 `clock_tick`（`agentlib/hook_clock.py`） |
| `py/docs/04-共用模組.md` | `hook_point` 那列的「執行時現在只有 aos-hook 用它」改寫；加 `hook_handle`／`hook_lists`、`agentlib/agent_hooks`、`agentlib/hook_clock` 三列（前半紀錄留下的字一併補上） |

## 測試

**全套逐夾比對**：兩份乾淨複本各自 install、清掉 `AOS_*` 後逐夾跑 unittest，共 79 夾。`base`＝`git archive 726c30ba1`（開工時 HEAD）；`m2`＝同一份 archive 去掉 `apps/hook/lists.py`、疊本線的檔。結果（`suite-base.txt`、`suite-m2.txt`，比對 `cmp.sh`）：

- 77 夾支數與結果逐夾相同；兩邊都退 5 的 `templates/kernel/tests`、`templates/tests/image-move-check` 是 0 支（不是 unittest，同前幾刀）。
- `py/tests/apps/gdb` 66 支：base 紅 1（`test_gdb_live.test_15_step_goes_one_cell_at_a_time`，兩輪全套同時跑時的時間題），m2 全綠。
- `py/tools/aos/kernel/tests` 122 支：m2 第一輪 9 個 error，全在 `test_refuse_extra.AfterVerdictExtraTest`——它用 `mock.patch.object(hooks, "fire", 假的)` 換掉 kernel 的 `hooks.fire`，而這刀 kernel 改經 `ctx.hooks` 發、`hooks.fire` 拿掉了。照 09b「只准改 import 與叫法」改成給 `ctx.hooks` 一個假遙控器（`names` 回 `["h"]`、`fire` 交給原本那個假 fire），斷言沒動；重跑 122 支 OK。

快跑（複本 m1，HEAD `726c30ba1`＋本線的檔，install 後）09b 刀 2 驗收清單那 12 支與相關的全綠、斷言沒改：`py/tests/test_hook_*.py` 50、`test_hooks_engine` 5、`test_agent_hooks` 6、`test_on_clock_kernel` 2、`apps/agent/test_hook` 12、`apps/eca/test_hooks` 14、`test_screen_slash` 16、`test_reply_match` 13、`apps/mcp/test_hooks` 7、`apps/hook/*` 15、`templates/tests/agent-fsm/test_hooks` 21、`test_clock_hook` 13、`test_hook_retry_later` 1、`kernel/tests/test_kernel_*` 51、`kernel/tests/test_hook_retry_later` 3、`kernel_llm/tests/test_hooks` 5、`templates/tests/test_start` 4。

## 實跑（假腦＋真 daemon，暫存樹）

`live.sh`：抄 start-api 成一棵樹，ann 的定義那份 `hooks.json` 多掛六個（handler 都先把事件記一行）：`up`＝before_queue（內容有 drop 就退 10，否則改成大寫）、`deny`＝before_tool（`condition: ["peek_now_time"]`，印一句退 10）、`aq`＝after_queue、`added`＝tool_added、`start`＝after_start、`tick`＝on_clock（`every_cycles: 1`）。起根、掛 llm 與 ann、`say hello`、`say "please drop this"`、`shutdown`。新（m2）舊（base）兩份複本各跑一次，輸出逐行相同（信名除外）：

```
== say hello
FAKE ANSWER to: HELLO (tool said: time is secret)
== say drop
aos-agent: error: LetterDropped … will not be answered: ann dropped it (blocked: a before_queue hook blocked it); say it again for a new answer
== mailbox_warning
letter 000000000002.… dropped by hook up
== hook events
{'start': 1, 'tick': 8, 'up': 2, 'aq': 1, 'deny': 1}
first ticks: [('on_clock', True, 1), ('on_clock', False, 2)]
== shutdown
daemon … stopped (ctl seq 1); 4 procs asleep …
```

history 裡 user 那則是 `HELLO`（改過的字）、tool 那則是 hook 的 stdout `time is secret`（工具沒跑）；tool_added 第一次只記不發（0 次，照舊）。第一次跑（tree1）handler 腳本是我寫壞的（語法錯），剛好看到錯的路徑也照舊：before_queue 的 hook 失敗＝`agent-fsm: error: HookFailed hook up (event before_queue) failed: exited 1`、退 1；on_clock 的 `on_error: continue`＝一行 warning；after_start 經 hook_fire 失敗＝`hook_fire: error: HookFailed …`、aos-loop 只記 warning。

## 行為變了的一處（設計 04 就寫了）

- **eca 的 before_queue 攔信從此查 `aos-post done` 的退碼**（F9）：非 0＝`PostFailed`、這輪退 1（fsm 本來就這樣）。eca 原本不查。
- fsm 這邊 aos-post 起不來時的那句換成共用的「aos-post failed to start (proto8/bin must be on PATH)」（前半紀錄替使用者做的選擇第 4 條，這一半真的用上了）；只有被 before_queue 攔下那封的 done 走這條，其他 done 照舊是 idle 自己的 `post()`。
- kernel：引擎在發事件時若丟 `HooksBad`（清單在讀設定時已驗過，照理不會），以前會變成 traceback，現在是 `kernel: error: HooksBad …`。

## 跟設計對不上處

- 09b 刀 2 說「`cell_common` 的 `clock_tick` 拿掉；四格寫 `H.clock_tick()`」：照做；遙控器在每格 `stack` 確定之後、原本 `clock_tick` 那一行的位置開（idle 是在 `post()` 定義之前開、在建好 queue 之後才 `clock_tick`，順序跟原本一樣）。
- 設計 04 寫把手「`hooks.open(…)`」：照前半，用 `agent_hooks.open`。
- 09b 沒寫 `hooks.py` 要拆；任務書要拆到 300 行上下：拆出 on_clock（前半紀錄就指這段）。`apps/hook/main.py` 因併進 `--points` 那半從 303 變 319 行，略超過，沒再拆（HELP 字串佔一半）。
- kernel 的 `hooks.open` 給 `entries=lambda: ctx.cfg["hooks"]`（設計 04 說 kernel 給「每輪解好的表」）：給函式是為了包若在一輪裡換了 `cfg["hooks"]` 也跟得上；今天沒有包這樣做，結果相同。

## 替使用者做的選擇（施工層級，設計沒寫到的）

1. **eca 的遙控器放進 `Handoff`，定義夾從遙控器拿**（`Handoff(hooks, stack, …)`，`self.template = hooks.def_folder`）：一路傳下去最少改簽名的做法；`slash_turn` 的 `template` 參數位置直接換成 `hooks`（它只拿 template 去開 Handoff 與發 after_queue），`test_screen_slash.py` 照位置傳的參數不用改。
2. **`More` 不另收遙控器**，用 `hand.hooks`（同一輪那個）。
3. **mcp 的遙控器是模組層的 `H`**，`main` 開一次（跟既有的 `HOOKS`、`OWN`、`LOGS_PATH` 同一種寫法），`run_tool` 不加參數。
4. **kernel 把遙控器掛在 `ctx.hooks`**，`hooks.py` 的模組函式 `open(ctx)` 開它；`hooks.fire` 拿掉（沒有別人叫）。
5. **on_clock 拆成 `agentlib/hook_clock.py`**，不是拆別段：它自成一塊、只有遙控器與 `hook_fire`／`aos-hook` 叫；`hook_clock` 照舊經模組函式 `hooks.fire(…, only=[名], entries=…)` 發（不改走遙控器，免得動到 `test_on_clock_kernel.py` 的 `patch.object(hooks, "fire")`）。
6. **`agent_hooks.source` 放 `--agent` 的組裝**（lists.py 刪掉後要有地方放）；`--points` 那半只有十來行，留在 main.py。
7. `hooks.fire`、`hooks.has` 這兩個模組函式照設計「舊模組函式留到刀 3」留著（`hook_clock` 與 `templates/tests/agent-fsm/test_hooks.py` 還在用）。

## 第 3 刀開工前要先知道的

- **今天沒有任何定義夾有 `hook_points`**：宣告了 `hooks` 的有 `templates/agent-fsm`、`agent-python`、`eca-claude`、`eca-pi`、`start-api/agents/ann`、`start-eca/agents/ann` 六份；`templates/reviewer` 借 agent-fsm 的格程式（A20）。`aos-hook --agent` 對它們發什麼都是 `EventUnknown … (points: none)`。
- 開遙控器的地方都還給 `table=`：`agent_hooks.open`（`table=hooks.EVENTS, entries=lambda: hooks.load(…), check=hooks._check`）、kernel `hooks.open`（`table=EVENTS`）。第 3 刀改成 `points=`（`hook_point.for_definition` 或 kernel 自己夾的 `hook_points.json`）時，`hooks._check`（content 是字串、before_queue 的不能空）跟宣告的 `change` 型別會重疊，要決定留哪個。
- `hook_clock.clock_tick` 走的是模組函式 `hooks.fire`，不經遙控器：第 3 刀若拿掉 `hooks.fire`，這裡要改走遙控器（`test_on_clock_kernel.py` patch 的是 `hooks.fire`，要跟著改叫法）。
- 還直接讀 `hooks.EVENTS` 的：`apps/agent/hook.py`（`add` 的錯誤句）、`agent_spec_agent.py`、`gdb/__init__.py`、`hook_point.py` 檔頭、測試 `test_hook_points_match.py`、`test_gdb_trigger.py`；`hooks.validate_entry` 還有 `agent_spec_hooks.py`、`apps/agent/hook.py` 與幾支測試在用。
- kernel_llm 的 `_entry` 經 kernel 的 `hooks.load` 驗清單（表＝kernel 的 `EVENTS`）。

## 收尾

- 交件：見 commit；claim 交件時放。沒在 `~/repo/aos/proto8` 跑 `install.py`（頂層收線後統一裝）；沒叫真模型。
- `apps/hook/lists.py` 照任務書的放寬在工作樹刪掉、交件 `--rm`。
- 行程：暫存樹 tree1～3 都 `aos-daemon-ctl -d … shutdown` 收了，根自己退出；收尾 `pgrep -a aos` 對過。
- 暫存：`~/.aos/scratch/aos-hook-k2b-1120/`（複本 `base`、`m1`〔多帶一份沒人 import 的 lists.py，建錯的〕、`m2`；暫存樹 `tree1`〔handler 寫壞那次〕、`tree2`〔m2〕、`tree3`〔base〕；`suite-*.txt`、`logs-*`；腳本 `setup.sh`、`mine.sh`、`suite.sh`、`quick.sh`、`live.sh`、`cmp.sh`、`submit.sh`、`mkops.py` 等）；TMPDIR 在 `/tmp/aos-hook-k2b-1120-*`。
- 另：開工時在 repo 的 `templates/agent-fsm/` 用 `py_compile` 驗語法，留下一個 `__pycache__/`（gitignore 擋著、不進 commit）；照「不刪任何檔」沒刪，交給頂層決定。
