# 「提供 hook 點」的介面：施工第 3 刀（切到宣告：一隻 agent 會發哪些點，以它定義夾 interfaces.json 的 hook_points 為唯一來源；kernel 三個點搬成宣告）

← [當天索引](README.md)｜設計 [aos-hook-plan-1120](aos-hook-plan-1120/README.md)（格式 [01](aos-hook-plan-1120/01-宣告格式.md)、刀 3 在 [09b](aos-hook-plan-1120/09b-施工計劃-逐刀.md#刀-3切到宣告)，對不上以 [12 採納表](aos-hook-plan-1120/12-採納表.md) 為準）｜使用者已答 [13](aos-hook-plan-1120/13-使用者已答.md)｜前幾刀 [k2](aos-hook-k2-1120.md)、[k2b](aos-hook-k2b-1120.md)、[k4](aos-hook-k4-1120.md)、[k5](aos-hook-k5-1120.md)

線 aos-hook-k3-1120，11-20 下午公司 WSL。頂層派、線隊長做。依據（13 逐字）：第 4 題欄位以宣告為唯一來源「要」；第 14 題 kernel 三個點「一起搬」；第 5 題掛到不會發的事件「照舊不管」；第 10 題「不留舊的，裝新版時一起重新編譯」；使用者 11-20「舊的教學我都沒在用，現有的aos體系我也都沒在用。所以放心弄。」（不顧相容、不寫遷移）。

## 結論

- **agent 的 hook 遙控器改讀宣告**：`agent_hooks.open` 開遙控器時點＝`hooks.points(定義夾)`（`hook_point.for_definition`，讀 `interfaces.json` 的 `hook_points`）；宣告的 `change` 型別先驗，`hooks._check`（content 的規矩）接著驗。模組函式 `hooks.fire` 也改用這隻自己的表（`hooks.table(定義夾)`）。
- **有 hook 生效卻沒寫 `hook_points`＝`HooksBad`**（`hooks.load` 擋；句子說加什麼）。沒有 hook 又沒寫＝照舊什麼都不做（reviewer 這種、`aos-mcp` 沒給 `--hooks`）。不留「沒寫就當九種」。
- **`hooks.EVENTS` 不再寫死**：由 aos 自己帶的 `aos-loop`、`agent-fsm`、`eca`、`mcp` 四份宣告合起來、去掉 `not_fired_yet` 的點算出（12 採納表：EVENTS 留到第 6 刀 gdb 改讀宣告才拿掉）。它現在只拿來驗清單的事件名（`validate_entry`、`aos-agent hook add`、編譯）與給 gdb 列種類。照第 5 題「照舊不管」，清單驗事件名用這張合起來的、不照這隻自己的 hook_points 縮小。
- **kernel 三個點搬成宣告**：`py/tools/aos/kernel/hooks.py` 的 `EVENTS` 由同夾 `hook_points.json` 算出、遙控器用 `hook_point.open(POINTS, …)` 開（宣告的型別先驗、kernel 自己的 `check` 接著驗）。kernel_llm 經同一份 `hooks.load`／`round`，不用改。
- **六份有 hooks 的定義補上 `hook_points`**（reviewer 沒有 hooks，不加，見「跟設計對不上處」）；編譯（有 fsm 又有 hooks）寫 `[{"provider": "aos-loop"}, {"provider": "agent-fsm"}]`。

## 改了哪些檔

| 檔 | 改什麼 |
|---|---|
| `py/aos/agentlib/hooks.py` | `EVENTS` 改由宣告算（`AGENT_PROVIDERS`、`_shipped()`）；新 `points(def_folder)`（PointsBad 轉 HooksBad）、`table(def_folder)`；`load` 有 hook 沒 hook_points＝HooksBad；`fire` 用 `table(def_folder)`；檔頭「對外」 |
| `py/aos/agentlib/agent_hooks.py` | `open`：有宣告＝`hook_point.open(points, …)`；沒寫＝`table=EVENTS`（沒人能掛）；宣告壞＝fail `PointsBad`；檔頭 |
| `py/tools/aos/kernel/hooks.py` | `POINTS_FILE`、`POINTS`、`EVENTS` 由宣告算；`open` 用 `points` |
| `py/aos/agent_spec_parts.py` | `HOOK_POINTS`；`interfaces_json` 有 hooks 時寫 `hook_points`（在 `hooks` 後面）；要別的用 `interfaces=` 蓋 |
| `py/aos/agent_spec_agent.py` | `events()` 的 docstring（仍回 `hooks.EVENTS`，見「替使用者做的選擇」） |
| `templates/agent-fsm`、`start-api/agents/ann` 的 `interfaces.json` | `"hook_points": [{"provider": "aos-loop"}, "hook_points.json"]` |
| `templates/eca-claude`、`eca-pi`、`start-eca/agents/ann` 的 `interfaces.json` | `aos-loop`、`eca`、`mcp` 三個 provider |
| `templates/agent-python/interfaces.json` | 照編譯的新輸出（`test_agent_spec` 的「產物跟 agent.py 相同」綠） |
| `py/aos/apps/agent/docs/06-hook.md` | 「兩份檔怎麼疊」加一條 `hook_points` |
| 測試夾具（20 支檔） | 自己寫 `interfaces.json` 又有 hooks 的夾具加 `hook_points`（fsm 的給 aos-loop＋agent-fsm、eca 的給三個）：`py/tests/apps/eca/` 的 `test_slash_hook_once`、`test_retry`、`test_hooks`、`test_reply_match`、`test_compact_wrap`；`py/tests/apps/agent/test_hook`；`py/tests/` 的 `test_on_clock_kernel`、`test_hooks_engine`、`test_fn_run`、`test_agent_hooks`；`py/tools/agent/agent_def/tests/test_agent_def`；`templates/tests/agent-fsm/` 的 `test_hooks`、`test_reply_match`、`test_compact_short`、`test_compact`、`test_cooldown`、`test_selfheal`；`py/tests/apps/agent/test_state_parts`（兩處）；`py/tests/apps/mcp/test_hooks`；`cpp/aos-daemon/tests/test_stop_cause`（只給 `aos-loop`）。斷言沒動 |
| `py/tests/test_agent_hooks.py` | 另：`EventUnknown` 那句改用 `before_save`（`before_run` 現在是這隻宣告的點）；新 `test_points_come_from_hook_points` |
| `py/tests/test_agent_spec.py` | 編出的 `aos-agent` 鍵多 `hook_points`，並比它的值 |
| `py/tests/test_hook_points_match.py` | 新 `test_definitions_declare_their_points`：六份定義的宣告（去掉 not_fired_yet）＝`hooks.EVENTS`、`hooks.table` 跟宣告算的相同 |

## 測試

- **改前**（`base`＝`git archive f522b5570`，install 後，`suite.sh` 逐夾 79 夾）：跑完，`suite-base.txt`。
- **改後**（`m5`＝同一份 archive 疊本線 claim 的檔，install 後）：全套逐夾在交件時跑到第 18 夾（cpp 十夾、`py/tests`、`py/tests/apps/` 的 agent、asuser、clock_register、comm、daemon_ctl 等），跟 base 逐夾相同，只有 `py/tests` 721 → 723（本線新加兩支：`test_points_come_from_hook_points`、`test_definitions_declare_their_points`），全綠。比對 `cmp.py base m5`。
- 其餘跟 hook 有關的夾另外單跑（複本 m3／m5，install 後），全綠：`py/tests/apps/eca` 227、`apps/hook` 15、`apps/mcp` 17、`apps/agent` 213、`templates/tests/agent-fsm` 215（第一輪 `test_selfheal` 一支紅＝夾具沒 hook_points，補上後 20 支綠）、`templates/tests` 29、`py/tools/agent/agent_def/tests` 32、`self_hook/tests` 6、`fork/tests` 14、`py/tools/aos/defs/tests` 28、`kernel/tests` 122、`kernel_llm/tests` 80。
- 途中抓到的（都已修）：自己寫 `interfaces.json` 又掛 hook 的夾具（共 20 支檔）沒 `hook_points`＝HooksBad；`test_agent_spec_load.Reviewer`（reviewer 範本要跟編譯產物相同，所以 reviewer 不加 hook_points）；`test_fn_spec_more`（錯誤句列事件的順序，見選擇第 6 條）；`test_agent_hooks` 的 `before_run` 現在是宣告的點、不再 EventUnknown（改用 before_save）。
- **沒跑完的**：m5 全套剩下 61 夾（`py/tests/apps/` 其餘、`py/tools/*/tests`、`templates/tests/*`）交件時還在跑；其中跟 hook 有關的都在上一點單跑過。

## 實跑（假腦＋真 daemon，暫存樹 `tree1`，複本 m3）

`live.sh`：抄 start-api 成一棵樹；ann（agent-fsm）的定義那份 `hooks.json` 多掛 `up`＝before_queue（改成大寫）、`deny`＝before_tool（`condition: ["peek_now_time"]`、退 10）、`aq`＝after_queue、`start`＝after_start；llm kernel 的 `kernel.json` 多掛 `bv`＝before_verdict、`av`＝after_verdict、`br`＝before_reply（handler 都先記一行）。起根、掛 llm 與 ann、`say hello`、`shutdown`：

```
== say hello
FAKE ANSWER to: HELLO (tool said: time is secret)
== hook events
{'start': 1, 'up': 1, 'aq': 1, 'bv': 2, 'av': 2, 'br': 2, 'deny': 1}
start after_start {}
up before_queue {'content': 'hello', 'letter': '000000000001.…'}
aq after_queue {'content': 'HELLO', 'letter': '000000000001.…'}
bv before_verdict {'letter': '01795161478246083817.…', 'body': '...'}
av after_verdict {'letter': '01795161478246083817.…', 'verdict': 'pass', 'body': '...'}
br before_reply {'letter': '01795161478246083817.…', 'body': '...'}
deny before_tool {'name': 'peek_now_time'}
bv / av / br 第二封（工具結果後那一問）各一次
== shutdown
daemon at …/tree1/.stack stopped (ctl seq 1); 4 procs asleep …
root exited
```

history 裡 user 那則是 `HELLO`、tool 那則是 hook 的 stdout `time is secret`。kernel 三個點每問一次各發一次（兩問＝各 2）。

## `aos-hook points --agent`／`check --agent`（六份定義，複本 m3 的 templates）

`points` 只貼點那行（欄位與句子略）。fsm 三份（agent-fsm、agent-python、start-api/agents/ann）：

```
after_start  after
after_stop  after
before_run  before  condition stage  can block
after_run  after
before_queue  before  change content (nonempty_string)  can block
after_queue  after
before_tool  before  condition name  change arguments (any)  can block
after_tool  after  condition name  change content (string)
brain_failed  after  condition name
tool_added  after  condition name
on_clock  on
exit 0
```

eca 三份（eca-claude、eca-pi、start-eca/agents/ann）同樣十一個點，順序是 loop 四個、eca 五個、mcp 兩個（before_tool、after_tool 在最後）。`check --agent`：

```
agent-fsm             ok: 11 points from 2 declarations, 4 hooks from 1 lists
agent-python          ok: 11 points from 2 declarations, 0 hooks from 1 lists
start-api/agents/ann  ok: 11 points from 2 declarations, 4 hooks from 1 lists
eca-claude            ok: 11 points from 3 declarations, 6 hooks from 1 lists
eca-pi                ok: 11 points from 3 declarations, 4 hooks from 1 lists
start-eca/agents/ann  ok: 11 points from 3 declarations, 6 hooks from 1 lists
```

（第 2 刀時對這六份是 `EventUnknown … (points: none)`。）

## 跟設計對不上處

- 09b 刀 3 說「EVENTS 與舊模組函式拿掉」：照 12 採納表，EVENTS 留著、改成由宣告算出；模組函式 `hooks.fire`／`has` 也留著（`hook_clock` 還走 `hooks.fire`；`test_hooks.py`、`test_fn_run.py`、`test_hooks_engine.py`、`test_cli_linger.py`、`test_on_clock_kernel.py` 在用），改成讀這隻自己的表。
- 09b「有 hook 沒 `hook_points`＝HooksBad」照做；「`validate_entry` 收表」沒做：照第 5 題「照舊不管」，驗事件名用合起來的 EVENTS，簽名不變（`agent_spec_hooks`、`apps/agent/hook.py`、幾支測試照舊叫）。
- 09b 的 `aos-agent hook events` 子指令、`self_hook` 的 `events` op 與拿掉 enum、`hooks.json` 的 description 改寫、`refs_check` 查 `hook_points` 的檔、知識庫 `me/self_hook.json` 等：這刀沒做（見「沒做的」）。看一隻有哪些點已經有 `aos-hook points --agent`（第 4 刀）。
- 09b 說 kernel_llm 的 `_entry`「跟著新簽名」：`hooks.load(table, path)` 簽名沒變，不用動。
- 設計 01 的表 reviewer 寫 `aos-loop`＋`agent-fsm`：**沒加**。reviewer 沒有 hooks，它的 `interfaces.json` 要跟 `agent.py` 編出來的逐字相同（`test_agent_spec_load.Reviewer.test_same_as_the_template`），而編譯只在有 hooks 時寫 `hook_points`；加了反而紅。沒 hooks 的定義不用 `hook_points`。

## 替使用者做的選擇（施工層級，設計沒寫到的）

1. **`hooks._check` 與宣告的型別檢查兩個都留**：宣告的先驗（型別），`_check` 接著驗（before_queue 的 content 不能是空的那類同義重複也無妨）。拿掉 `_check` 要先確定宣告的 `nonempty_string` 跟它一字一字同義，今天沒核對完，留著行為不變。
2. **沒寫 `hook_points`、也沒有 hook 的定義：遙控器照 EVENTS 認點、什麼都不跑**，不報錯（reviewer、自己寫格程式又沒掛 hook 的 agent 照常跑）。只有「有 hook 卻沒寫」才 HooksBad。
3. **`hooks.EVENTS` 去掉 `not_fired_yet` 的點**（before_run／after_run 還不能寫進清單）：等範本 loop.json 接上、宣告拿掉 `not_fired_yet`，它們自動進表。這隻自己的遙控器表（`hooks.table`）則照宣告全收（含 before_run／after_run），`aos-hook --agent` 也是。
4. **編譯只在有 fsm 又有 hooks 時寫 `hook_points`**（跟 `hooks` 鍵同進同出），值固定 `aos-loop`＋`agent-fsm`；要別的用 `interfaces={"aos-agent": {"hook_points": [...]}}` 蓋（那條路本來就收）。`Agent.events()` 仍回 EVENTS（編譯時不知道定義夾的宣告、也照第 5 題不縮小）。
5. **`hooks.points` 把 `PointsBad` 轉成 `HooksBad`**（清單那條錯誤路徑都認 HooksBad）；`agent_hooks.open` 開的時候宣告壞＝fail 收 `PointsBad`。
6. **合起來的 EVENTS 照 agent-fsm、eca、mcp、aos-loop 的順序**：錯誤句「event must be one of …」照舊從 before_queue 開始（`test_fn_spec_more` 比開頭），after_start／after_stop 排到 on_clock 後面（原本在 on_clock 前）。

## 沒做的（留給下一刀；接點都在）

- 範本 loop.json 接 `before_run`／`after_run`、旗標檔維護、刪 `hook_fire`、`loop_points.json` 拿掉 `not_fired_yet`（第 5 刀後半）。接點：遙控器的表已收 before_run／after_run（這隻宣告了就有），`aos-hook fire --agent` 讀同一份宣告；拿掉 `not_fired_yet` 後 `hooks.EVENTS` 自動多這兩個（`test_hook_points_match` 的 `fired()` 也跟著）。
- kernel 接 loop 層的點（kernel 夾沒有 interfaces.json 的 hook_points；設計 01 說 kernel 不加鍵）。
- gdb 斷點種類從宣告讀（第 6 刀；`gdb/__init__.py` 照舊讀 `hooks.EVENTS`，沒碰）。
- 09b 刀 3 的 `aos-agent hook events`、`self_hook {"op": "events"}`、拿掉 `_tooldef.json` 的 enum、五份 `hooks.json` description 改寫、`refs_check` 查 `hook_points` 的檔、`hook_clock` 改走遙控器、`hooks.fire`／`has` 模組函式拿掉。
- 文件與知識庫：`knowledge/aos/me/self_hook.json`、`cli/hook.json`、`definition.json`；`templates/docs/01-eca-claude.md`、`02-agent-fsm.md`、`templates/agent-fsm/README.md`、`py/aos/apps/eca/README.md`、`kernel/README.md`（別線 aos-kllm-round-1120 claim 著）、`hook_point.py` 檔頭第 4～7 行（還寫「until cut 3」）。附錄 4 的 interfaces.json 列加 `hook_points`（條文，不動）。
- 教學（`docs/tutorial/`）與條文照任務書不動；過時處：提到「interfaces.json 只寫 hooks 就能掛」的地方都缺 `hook_points`。

## 第 4 刀之後（下一刀）開工前要知道的

- 自己寫 `interfaces.json` 又掛 hook 的定義夾，現在一定要寫 `hook_points`；公司機活樹 `~/aos-home` 裡的舊定義夾裝新版後會 HooksBad，要照第 10 題一起重新編譯或手補（本線沒碰活樹）。
- `hooks.load` 每次讀清單都多讀一次宣告（`points`）；遙控器 `open` 時也讀一次。今天沒量到慢。
- `test_hook_points_match.fired()` 與 `hooks._shipped()` 兩處都認 `not_fired_yet`。

## 收尾

- 交件：一筆，見 commit；claim 交件時放（claim 了沒改的 `hook_point.py`、`templates/reviewer/interfaces.json` 另 release）。沒在 `~/repo/aos/proto8` 跑 `install.py`；沒叫真模型；沒碰活樹。
- 同時有別線 aos-kllm-round-1120 在改 `kernel/round.py`、`kernel_llm/llm_rules.py`、`kernel/README.md` 等：沒碰、沒抄進複本；我改的 `kernel/hooks.py` 不在它的 claim 裡。
- 行程：暫存樹 `tree1` 用 `aos-daemon-ctl -d … shutdown` 收了，根自己退出；收尾 `pgrep -a aos` 對過。
- 暫存：`~/.aos/scratch/aos-hook-k3-1120/`（複本 `base`、`m1`、`m2`〔install 沒跑完，建錯的〕、`m3`、`m4`〔抄檔失敗、沒 install，建錯的〕、`m5`；暫存樹 `tree1`；`suite-*.txt`、`logs-*`；腳本 `setup.sh`、`mine.sh`、`suite.sh`、`quick.sh`、`live.sh`、`six.sh`、`cmp.py`、`add_points.py`、`fix_fixtures*.py`、`mylist.py`、`mkops.py`、`submit.sh`）；TMPDIR 在 `/tmp/aos-hook-k3-1120-*`。
