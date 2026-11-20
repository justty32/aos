# 「提供 hook 點」的介面：施工第 2 刀的庫那一半（2a：小函式＝把手，加 aos-hook --agent；呼叫端一支沒換）

← [當天索引](README.md)｜設計 [aos-hook-plan-1120](aos-hook-plan-1120/README.md)（小函式在 [04](aos-hook-plan-1120/04-小函式.md)，刀 2 在 [09b](aos-hook-plan-1120/09b-施工計劃-逐刀.md#刀-2呼叫端收成把手表照舊行為不變)，對不上以 [12 採納表](aos-hook-plan-1120/12-採納表.md) 為準）｜使用者已答 [13](aos-hook-plan-1120/13-使用者已答.md)｜第 1 刀 [aos-hook-k1-1120](aos-hook-k1-1120.md)｜第 4 刀 [aos-hook-k4-1120](aos-hook-k4-1120.md)

線 aos-hook-k2-1120，11-20 公司 WSL。使用者 11-20 說「開工吧」，頂層派、線隊長做。依據：方向第 1 題「宣告式＋小函式都做」、第 2 題「任何子程式，含非 Python」、待裁第 4 題欄位以宣告為唯一來源「要」、第 5 題「照舊不管」、第 10 題「不留舊的，裝新版時一起重新編譯」。

## 結論

- **把手做好了**：`aos.hook_point.open(…)` 開一次，之後每個點一行 `fire`；錯一律交給開的人給的 `fail(代號, 句子)`。照宣告的 `change` 型別在引擎裡逐個 hook 當下驗（A13）；`names()` 加 `fire(only=…)` 給 kernel 一個一個發（A16）。
- **agent 一家的把手** `aos.agentlib.agent_hooks.open(def_folder, stack, fail, warn)`：`fire`、`has`、`names`、`clock_tick`、`take_letter`（丟信三步）、`guard_tool`（被攔的預設字）、`announce_tools`（tool_added 那串）。事件表照舊用 `hooks.EVENTS`，清單照舊經 `hooks.load`（「表照舊」，第 3 刀才讀宣告）。
- **`aos-hook` 改經把手跑，`--agent DEF_DIR` 接上了**；`--points`／`--list` 的行為沒變（第 4 刀的 10 支測試只改了 1 行斷言，見下）。
- **呼叫端一支都沒換**：fsm 格程式、抄本、eca、aos-mcp、kernel、`hook_fire` 全照舊叫舊函式；舊函式全留著。所以 repo 存檔這一刻起，活樹上跑的東西行為不變；install 之後也不變（只多了新模組）。
- 測試：新的 3 支檔 21 支綠；改壞三處各自會紅；全套逐夾比對見「測試」。

## 加了、改了哪些檔

| 檔 | 新／改 | 一句話 |
|---|---|---|
| `py/aos/hook_point.py` | 改 | 加 `open`、`FailReturned`、`call_fail`、`Handle`（後兩者從 hook_handle 帶出）；檔頭寫整套介面。模組自己的 `open` 蓋掉內建的，讀檔改用 `io.open` |
| `py/aos/hook_handle.py` | 新 | 把手本體（只因檔案大小從 hook_point 拆出；程式只叫 `hook_point.open`） |
| `py/aos/hook_lists.py` | 新 | 讀清單（後蓋前、null 關、檔不在＝沒有、`entry_keys` 只准在宣告它的點、再交 `entry_check`）與照宣告驗型別；從第 4 刀的 `apps/hook/lists.py` 搬來，字句一字不改 |
| `py/aos/agentlib/agent_hooks.py` | 新 | agent 的把手（F10：`hooks.py` 已 331 行，另放一檔） |
| `py/aos/agentlib/hooks.py` | 改 | `validate_entry` 的 on_clock 那半抽成 `check_clock`（行為不變，`--agent` 共用）；`_layers` 的路徑那半抽成 `layers`；檔頭「對外」加五行。現 350 行 |
| `py/aos/apps/hook/lists.py` | 改（換職責） | 從「讀清單、驗型別」換成「點與清單從哪來：`--points`／`--list` 或 `--agent`」；檔頭那句跟著換 |
| `py/aos/apps/hook/main.py` | 改 | 經把手跑；`--agent` 的 help 與 after_start 清 on_clock 狀態 |
| `py/aos/apps/hook/README.md` | 改 | `--agent` 一條、Python 提供者直接用把手、測試清單 |
| `py/tests/test_hook_point_open.py` | 新 | 把手 10 支 |
| `py/tests/test_agent_hooks.py` | 新 | agent 把手 6 支（假的 `aos-post` 放 PATH 最前） |
| `py/tests/apps/hook/test_hook_cli_agent.py` | 新 | `aos-hook --agent` 5 支 |
| `py/tests/apps/hook/test_hook_cli.py` | 改 1 行 | 原斷言「`--agent` 給了＝not available yet」換成「`--agent` 與 `--points` 一起給＝ArgumentsBad not both」 |

## 把手長什麼樣

```python
from aos import hook_point
H = hook_point.open([HERE + "/hook_points.json"], lists=[cfg_path], stack=stack, fail=die, warn=warn)
r = H.fire("before_save", {"file": path})        # 讀清單、驗、交引擎；錯交 die
```

- 點從哪來二選一：`points`＝宣告檔路徑的串（叫 `read`）或 `read` 讀好的表；`table`＝現成的引擎表（agent、kernel 在第 3 刀前用，沒有型別可驗）。
- 誰掛了最多一種：`lists`＝每次 fire 重讀的檔；`entries`＝讀好的 `{名: 格}`，或回這種表的函式（每次 fire 叫一次；agent 用這個接它自己的兩層與 on_clock 驗法，kernel 之後可給它每輪解好的表，F13）。
- `fail` 自己丟的例外原樣往外走；`fail` 回來了＝丟 `hook_point.FailReturned`（A12）。給 fail 的代號：`PointsBad`（open 時）、`EventUnknown`、`HooksBad`、`HookFailed`。參數給錯（兩種點都給、stack 空、fail 不是函式）＝`TypeError`，那是寫的人的錯，不走 fail。
- `fire(only=[…])`＝**只跑這幾個名字、不再比 condition**（名單由 `names()` 先比好）。見「替使用者做的選擇」第 2 條。

## 測試

- **新測試**：`test_hook_point_open.py` 10 支（沒人掛、清單每次重讀與 null、只認 change 鍵、`nonempty_string`／`object` 型別壞值不進 data 且下一個 hook 看到原值、`on_error continue` 的 warning、呼叫端 check 排在型別之後、condition／`names`／`only`、`entry_keys` 與 `entry_check`、給 entries 與函式、table 形、fail 丟例外與 fail 回來、參數錯）；`test_agent_hooks.py` 6 支（跟 `hooks.fire` 結果逐鍵相同、stack 那份 null 關掉、content 型別、EventUnknown、on_clock 鍵壞、take_letter 改字／攔下三步〔`done BOX L2`、mailbox_warning 那一行、letters.json 的 dropped〕／aos-post 退 3＝PostFailed、guard_tool 四種、announce_tools 第一次只記與函式只在有人掛時叫、clock_tick、空把手）；`test_hook_cli_agent.py` 5 支（after_stop 從環境變數補欄位且兩層疊、攔下與型別、after_start 清 on_clock 狀態而 after_stop 不清、on_clock 三種壞格與 `check` 的 ok 行、二選一／不是資料夾／StackMissing／沒有 hook_points＝`EventUnknown … (points: none)`／不認得的 provider）。
- **證明會紅**（在複本 q1 改壞再跑、跑完 `cp` 回去並 `cmp` 過；`mutate.sh`）：拿掉宣告型別檢查 → 1 支紅；fail 回來時不丟 → 2 支紅；`only` 照樣比 condition → 1 支紅。
- **第 1 刀「宣告跟程式對得上」**（`test_hook_points_match.py`）與 `test_hook_point.py`、`test_hooks_engine.py`、`test_hook_run.py` 照綠（快跑那輪 61 支 OK，expected failures 1 是原本就有的）。
- **全套逐夾比對**：兩份乾淨複本各自 install、清掉 `AOS_*` 後逐夾跑 unittest，共 79 夾。`base`＝`git archive e1209424b`（開工時 HEAD）；`mine`＝`git archive 82bed567f`（建複本時 HEAD 已前進，多了鄰線 aos-gdb-small 的 gdb 測試）疊本線的檔。差別只有：`py/tests` 665→681（＋本線 16 支）、`py/tests/apps/hook` 10→15（＋本線 5 支）、`py/tests/apps/gdb` 58→66（鄰線加的 8 支，不是本線）；`py/tests/apps/agent`、`apps/gdb` 在 base 各紅 1 支（`test_add_parent_daemon` 的 `took < 2.9` 量到 3.14 秒、`test_gdb_live.test_07`，負載下的時間題），mine 兩夾全綠。其餘 74 夾支數與結果逐夾相同；兩邊都退 5 的 `templates/kernel/tests`、`templates/tests/image-move-check` 是 0 支（不是 unittest，同第 4 刀）。結果在 `suite-base.txt`、`suite-mine.txt`，比對 `cmp.sh`。
- **疊在 1bcde0265 上再跑**（頂層通知：鄰線 aos-hook-drift 拿掉了 `test_hook_points_match.py` 的 expectedFailure）：複本 q2＝`git archive 1bcde0265`＋本線的檔，`test_hook_point_open`、`test_agent_hooks`、`test_hook_point`、`test_hook_points_match`、`test_hooks_engine`、`test_hook_run` 61 支 OK（沒有 expected failure 了）、`py/tests/apps/hook` 15 支 OK。本線沒碰 06-hook.md、`self_hook/_tooldef.json`、知識庫。

## 沒做的與為什麼（＝重裝後才能做的那一半）

照 12 的切法：2a＝`py/aos/` 的庫（加把手、舊函式留著）→ install → 2b。任務書要我保守：**凡是「換成叫新函式」的呼叫端一支都不動**，包括在 `py/` 裡、跟庫一起 install 的 eca、mcp、kernel、`hook_fire`（09b 沒寫它們屬 2a 還是 2b；它們換了就會改到活樹裝好後的行為，例如 F9 的 eca 丟信多一條錯，所以留給下一步一起做、一起驗）。

**install 之後的下一步要動的檔**（09b 刀 2 表）：

| 檔 | 改什麼 |
|---|---|
| `templates/agent-fsm/idle.py`、`act.py`、`wait.py`、`brain.py`、`cell_common.py` | 開一次 `agent_hooks.open(AOS_CD 或 ".", stack, fail=die, warn=…)`；包裝 `fire()` 拿掉；丟信三步換 `take_letter`；before_tool 換 `guard_tool`（沒改＝回原物件，`arguments` 字串照舊不重排）；tool_added 換 `announce_tools`；`cell_common.clock_tick` 拿掉、四格寫 `H.clock_tick()`。**格程式存檔即生效**：必須在 install 之後才存檔（F1） |
| `templates/start-api/agents/ann/` 同五支 | 抄本跟著換（`templates/tests/test_start.py` 比對） |
| `templates/reviewer` | 借 agent-fsm 的格程式（A20），不用改檔，但驗收要包含 |
| `py/aos/apps/eca/hook.py`、`turn.py`、`batch.py`、`midturn.py`、`handoff.py`、`slash.py` | turn 開一次把手、一路傳下去（F8）；`fail` 丟 `Fail`；`before_queue` 換 `take_letter`（**F9：eca 今天不查 aos-post done 的退碼，換過去會多一條 PostFailed**；letters.json 寫不成從丟錯變成 warning）；`tool_added` 換 `announce_tools(函式)` |
| `py/aos/apps/mcp/main.py` | `agent_hooks.open(HOOKS, …)`（沒給 `--hooks`＝`None`＝空把手，取代自己造的空結果）；`fail` 丟 `HookStop`；before_tool 換 `guard_tool` |
| `py/tools/aos/kernel/hooks.py`、`round.py` | `hook_point.open(table=EVENTS, entries=…, fail=ctx.die, check=…)`；`round.py:131-132` 的接錯拿掉；after_verdict 用 `names()`＋`fire(only=[名])`（不再比 condition，今天它手動 pop 掉 condition，意思相同） |
| `py/tools/agent/hook_fire/_entry` | 內部換把手（F11），介面不變；第 5 刀整支換成 `aos-hook fire --agent` |
| 驗收 | 09b 刀 2 那 12 支測試照綠、斷言不改；grep「dropped by hook」「tool … blocked by hook」各只剩把手一處（今天各四處：fsm、ann 抄本、eca／mcp 各一，加把手一處） |

另外這條線也沒做：
- `py/docs/04-共用模組.md` 加 `hook_handle.py`、`hook_lists.py`、`agentlib/agent_hooks.py` 三列：那份是 shared-docs-1120 的領地，沒 claim；要加的字：「`aos/hook_handle.py`｜hook_point.open 回的把手（程式只叫 hook_point.open）」「`aos/hook_lists.py`｜讀 hooks 清單、照宣告驗 change 型別（hook_point.open 用）」「`aos/agentlib/agent_hooks.py`｜agent 一家的 hook 把手：fire、clock_tick、take_letter、guard_tool、announce_tools」。
- 知識庫 `knowledge/aos/cli/hook_points.json` 還寫「`--agent` not available yet」：知識庫存檔即生效，而活樹的 `bin/aos-hook` 要 install 才有，所以留到 install 那時一起改。
- `py/aos/agentlib/hooks.py` 現 350 行、`apps/hook/main.py` 303 行，超過 300：把手已另放一檔；on_clock 那段（約 130 行）要不要拆出是第 3 刀改這檔時順手的事。

## 跟設計對不上處

- 設計 04 寫「agentlib/hooks.py 的把手 `hooks.open(…)`」：做成 `agentlib/agent_hooks.open`。`hooks.py` 一定義 `open` 就蓋掉它檔裡用的內建 `open`（讀清單、寫狀態檔都靠它），而且 F10 本來就建議另放一檔。
- 設計 04 的 `open(points, lists=None, entries=None, stack, fail, warn=None, check=None)`：多了 `table=`（09b 刀 2「收宣告路徑或現成的表」）與 `entry_check=`（provider 自己的格規矩，`--agent` 的 on_clock 要用）；`entries` 也收「回表的函式」。
- `aos-hook --agent` 照設計 05 讀 `interfaces.json` 的 `hook_points`；**今天沒有任何定義夾有這個鍵**（第 3 刀才加），所以對今天的定義夾它發什麼都是 `EventUnknown`。這是照順序（刀 3 在刀 5 之前），沒有替它造退路。

## 替使用者做的選擇（施工層級，設計沒寫到的）

1. **把手的 `fail` 收 `EventUnknown`**（設計只列 HooksBad、HookFailed、PointsBad）：今天 `hooks.fire` 對不認得的事件丟 `ValueError`（寫的人的錯），收進 fail 後 `aos-hook` 與之後的 Python 提供者都有一句一樣的話。
2. **`fire(only=[…])` 不再比 condition**：設計 04「靠 names 拿名單再 fire(…, only=[名])」要的就是名單只比一次（kernel 今天手動 pop condition）；引擎 `hook_run.fire` 的 `only` 會再比，所以把手自己篩。agent 唯一用 only 的是 on_clock，它不收 condition，行為不變。
3. **`guard_tool` 沒人改時回「給的那個物件本身」**：fsm 今天沒改就不重新 `json.dumps`（tool_calls 原字串照送），呼叫端可以用 `is` 分；改了才是新的。
4. **`take_letter` 照 fsm 那一種**（F9 的建議）：letters.json 寫不成＝warning；aos-post 起不來或退非 0＝PostFailed（起不來那句用共用的 `aos.ws.run_post`，字跟 fsm 今天的「aos-post cannot start (must be on PATH)」不一樣：「aos-post failed to start (proto8/bin must be on PATH)」）；mailbox_warning 寫不成＝WriteFailed。
5. **`aos-hook --agent` 沒有 stack 時**：`check`、`points` 只讀定義那份清單（ok 行寫「from 1 lists」）；`fire` 照舊 StackMissing。
6. **`aos-hook --agent` 只在用到時才 import `aos.agentlib`**：一般的 `--points` fire 不多付 import 的時間（第 4 刀量過 import 是主要成本）。
7. **`aos-hook fire` 先讀一次清單（早報 HooksBad，順序跟第 4 刀一樣），再把讀好的交給 `fire(entries=…)`**，不讀兩次。
8. 掛到這隻不會發的事件：照使用者第 5 題「照舊不管」，把手與 `--agent` 都不擋（不在宣告裡的事件名照引擎原本的 `event must be one of …` 報 HooksBad——那是今天就有的行為，不是新擋）。
9. `apps/hook/lists.py` 不刪、換成「點與清單從哪來」：刪檔要使用者點頭，而且 `--agent` 的組裝本來就要一個地方放。

## 收尾

- 交件：見 commit；claim 已放。沒在 `~/repo/aos/proto8` 跑 `install.py`；沒起任何樹、沒叫模型。
- 暫存：`~/.aos/scratch/aos-hook-k2-1120/`（`base`、`mine`、`q1`、`q2` 四份複本，`suite-*.txt`、`logs-*`，腳本 `setup.sh`、`suite.sh`、`quick.sh`、`mutate.sh`、`cmp.sh`）；TMPDIR 在 `/tmp/aos-hook-k2-1120-*`。
