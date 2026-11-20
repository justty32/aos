編譯程式庫第 2 刀（`defs.Agent` 物件、`.dry_run()`／`.compile(夾)`、fsm 單獨編譯、`defs.load` 回物件、agent 骨架改寫）施工紀錄（11-20，線 aos-pylib-k2-1120）：做了什麼、寫起來前後對照、驗收、對不上處、HANDOFF 要改的字、第 3、4 刀開工前要知道的事。

← [2026-11-20](README.md)｜設計稿：[aos-pylib-plan-1120](aos-pylib-plan-1120/README.md)（第 2 刀在 [07b](aos-pylib-plan-1120/07b-施工計劃-第0到2刀.md#第-2-刀-agent-物件)）｜使用者答案：[12-使用者已答](aos-pylib-plan-1120/12-使用者已答.md)｜上一刀：[第 0 刀](aos-pylib-k0-1120.md)

使用者 11-20 選項框：第 2 題選「.compile(夾) 寫檔、.dry_run() 只算」、第 3 題選「小寫」、開哪幾刀選「第 1、2 刀都開」（三題逐字加進 12 末節，本線順手記）。第 1 刀（`fn`）是另一條線 aos-pylib-k1-1120，同時在做。

## 一句話

寫 `agent.py` 的介面換成一個物件：`a = defs.Agent("說明", system=…, tools=[…], llm={…}, fsm=…, hooks=…)`、最後 `defs.main(a)`；物件有 `.dry_run()`（只算）與 `.compile(夾)`（寫進夾），`defs.fsm(...)` 回的狀態機也能單獨 `.compile(夾)`；`defs.load` 回一隻新的 Agent、欄位小寫。**骨架、教學與測試裡的例子改寫後，編譯產物與各旗標的輸出跟改寫前逐 byte 相同**（只有 `--help` 文字、和一行本來就印方法名的 warning 變了）。`defs.compile`／`defs.write`、大寫常數的收法拿掉，不留舊名提示。

## 寫起來的前後對照（骨架）

改寫前：

```python
DESCRIPTION = "Look things up in the workspace and answer by mail."
SYSTEM = """You are an assistant that looks things up in the workspace. ..."""
std = defs.std
TOOLS = [std.pack("look"), std.pack("mailbox"), std.pack("json")]
LLM = {}
FSM = std.fsm()
HOOKS = {}
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=HOOKS)
```

改寫後：

```python
std = defs.std
agent = defs.Agent(
    "Look things up in the workspace and answer by mail.",
    system="""You are an assistant that looks things up in the workspace. ...""",
    tools=[std.pack("look"), std.pack("mailbox"), std.pack("json")],
    llm={},
    fsm=std.fsm(),
    hooks={},
)
defs.main(agent)
```

衍生：`TOOLS = [base.TOOLS, defs.drop("grep")]`、`LLM = base.LLM`、`base.tools(prefix="r_")` → `tools=[base.tools, defs.drop("grep")]`、`llm=base.llm`、`base.pack(prefix="r_")`。建置腳本：`for n in ("ann", "bob"): defs.Agent(...).compile("defs/" + n)`；狀態機：`defs.fsm("idle", [...]).compile("machines/x")` 只寫 `fsm.json`。

## 動了哪些檔

| 檔 | 做什麼 |
|---|---|
| `py/aos/agent_spec_agent.py`（新，257 行） | `Agent`：建構只收不驗（說明位置參數、其餘只收關鍵字）；`_files` 是原本 `compile()` 的本體加 `_names`，算法一字未改，最後 json 來回一次，不動傳進來的串列與表；`_write` 是原本 `write()` 的兩條政策；`.pack(prefix=, rename=, exclude=)`（原本 `Base.tools(...)`，每隻 Agent 都有）；`events()`；讀不到的欄位（extern）與寫錯的名字（讀、寫都擋）報清楚。`Fsm(dict)`：`.dry_run()`／`.compile(夾, name="fsm.json")`。`_Loop`：寫 `loop.json` 那段原樣搬來 |
| `py/aos/spec_unit.py`（新，84 行） | `Unit`（`.dry_run()`、`.compile(夾)`、`events()`、`_files`／`_write`）與命令列殼 `main(物件, …)`：旗標、用法、錯誤行跟原本 `agent_spec.main` 逐字相同；`--static`／`--dynamic` 只有 `LINKS=True` 的（Agent）收 |
| `py/aos/agent_spec.py`（441 → 285） | 拿掉 `compile`、`write`、`_names`、`HOOK_FIRE`、`RENAME_LAST`；`main(物件)`（收到的不是一個物件＝一行 SpecBad）；`fsm()` 回 `Fsm`；模組層 `__getattr__`：沒有的名字報 `defs has no X (it has …)`；改寫 `HELP` 與檔頭 |
| `py/aos/agent_spec_load.py` | `hand_over` 收物件；`Base` 類別換成 `_based()`：交回一隻新的 Agent（欄位小寫、底裡相對路徑照舊換算、tools 是一個包）；底交的不是 Agent＝SpecBad；「沒叫 defs.main」的訊息補一句「只叫 .compile 的交不出東西」 |
| `py/aos/agent_spec_parts.py`、`agent_spec_lib.py` | 訊息裡的大寫欄位名改小寫（`tools must be …`、`hooks: hook …`、`files: …`、`llm key …`、`interfaces …`）；檔頭一句 |
| `py/aos/gdb/__init__.py`、`py/tests/apps/gdb/test_gdb_live.py`、`test_gdb_trigger.py` | `HOOKS_FIX` 改成 `give hooks={} to defs.Agent(...) in agent.py, and recompile (python3 agent.py --compile)`（設計稿意見 15） |
| `py/aos/py/agent/__init__.py` | 檔頭註解多 `defs.Agent`、一句「跟把手 Agent 同名不同物」 |
| `templates/agent-python/agent.py` | 改成上面那份 |
| `py/tests/test_agent_spec.py`（1107 → 288）＋`agent_spec_helpers.py`（新，134）＋`test_agent_spec_script.py`（新，223）＋`test_agent_spec_objects.py`（新，247）＋`test_agent_spec_lib.py`（新，264）＋`test_agent_spec_load.py`（新，294） | 換寫法、拆開（設計稿排三支，三支仍有一支 836 行，再拆成五支加一支共用 helper，每支都在 300 行內）；新測試見「驗收」 |
| 文件 | 骨架 `README.md`（欄位表、選填欄位、不給 fsm、Build on、從 Python 編譯／建置腳本、fsm 單獨編譯、同名不同物）；教學 04、05、06-2、06-3、07、08、教學 `README.md`；`templates/README.md`、`py/README.md`、`py/aos/apps/gdb/README.md` |

## 驗收（實際做法與結果）

環境：`git archive HEAD proto8`（HEAD＝`b1c075f60`）抄到 `~/.aos/scratch/aos-pylib-k2-1120/src`，複本裡 `install.py`；一律經 bash 腳本先 unset 所有 `AOS_*`，`env -i PATH=<複本>/bin:/usr/bin:/bin HOME=… AOS_HOME=<複本> AOS_WS=<工作夾>/ws`。改動前跑一輪留底（`cap-base`，agent.py 用舊寫法）；把本線的檔（只本線的，工作樹裡第 1 刀與 hook 線的改動不疊）疊上同一份複本、重裝，同一個工作路徑用新寫法再跑一輪（`cap-new1`）。工作夾每輪跑完整夾搬進留底夾（不刪）。

**產物與輸出逐 byte 相同**（`cmp` 每份 stdout／stderr／結束碼，`git diff --no-index` 比寫出的整棵樹，另比權限清單）：

- 骨架：`--dry-run`、`--dry-run --static`、`--dry-run --dynamic`、不給參數、`--dry-run x`、`--dry-run --static --dynamic`、`--bogus`、`--compile --bogus`、`--compile`、`--compile 另一夾`、`--compile --dynamic 另一夾`。
- 例子八隻，各 `--dry-run`、`--dry-run --dynamic`、`--compile`：教學 04 的 ann、教學 06-2 的 ann（加 `defs.lib` 與 shout）與 bob（`defs.load`＋`defs.extern("system.txt")`，另加 `--compile 另一夾`）、測試的 reviewer／strict-reviewer（`std.hooks()` 與改一格 hook）、`base.pack(prefix=, exclude=)`＋`defs.fsm(base.fsm, …)` 換一格、`templates/reviewer` 寫成一支（meta、interfaces、files、自己的 fsm、extern）、eca 版（不給 fsm、填 eca-claude 抄本）。
- 結果：111 份輸出 109 份相同；不同的兩份是預期的：`--help`（文字改寫），與 `base.pack(...)` 那隻的 `--dry-run --dynamic` warning——那行本來就印方法名，`defs.load('../reviewer').tools(prefix='r_', …)` 變成 `.pack(prefix='r_', …)`。寫出的樹只有原始碼 `agent.py` 與骨架的 `README.md`（文件改了、編譯時夾裡已有不寫）不同；權限清單相同；重新編譯的骨架跟 repo 提交的那份無差。

**測試**（逐夾 `python3 -m unittest discover`，改動前／改動後，同一份複本）：

| 夾 | 改動前 | 改動後 |
|---|---|---|
| `py/tests`（含 `test_agent_spec*.py`、`test_spec_base.py`、`test_aos_py.py`、`test_hook_points_match.py`） | 640 OK（skip 1、expected failure 1） | 651 OK（同；多的 11 條是新測試） |
| `templates/tests/tool-python` | 4 OK | 4 OK |
| `py/tools/agent/tools_def/tests` | 12 OK | 12 OK |
| `py/tools/aos/defs/tests`（`defs.load`、check） | 27 OK | 27 OK |
| `py/tools/agent/agent_def/tests` | 30 OK | 30 OK |
| `py/tests/apps/gdb`（HooksMissing 那句） | 58 OK | 58 OK |
| `py/tests/apps/agent` | 213，1 failure | 213 OK |
| 其餘 `py/tests/apps/*` 十四夾 | 除 feedback 外全 OK | 同左 |

- `apps/agent` 改動前那條 failure 是 `test_reply_match.NewBody.test_one_batch_one_answer_to_everyone`（跟編譯無關，改動後同一條過了，看起來是時間上的不穩）。
- `apps/feedback` 兩邊都是 18 條 error：要讀 repo 的 `wf/advices/feedback/raters.json`，乾淨複本只抄 `proto8/`，跟本線無關。
- `test_agent_spec*.py` 共 64 條：舊的 53 條換寫法照過（`Linking`、`Reviewer.test_same_as_the_template`、`Skeleton.test_committed_files_match_agent_py` 都在內），新 11 條。
- 最後一輪之後只改了 `py/aos/py/agent/__init__.py` 的檔頭註解（兩行註解，不影響執行）與教學 06-1 兩行。
- 第 1 刀那條線途中交件（`d1e54abb1`、`f6b30bf9a`），所以再拿本線交件前的 HEAD（`f23727981`，含第 1 刀）抄一份、疊本線的檔再跑一次：`py/tests` 665 OK（skip 1、expected failure 1）、`templates/tests/tool-python` 5 OK、`tools_def` 12、`defs` 27、`agent_def` 30、`apps/gdb` 58 全 OK。兩刀疊在一起沒有撞。

**新加的測試**（`test_agent_spec_objects.py`）：fsm 單獨 `.compile(夾)` 只寫 `fsm.json`、等於放進 Agent 編出的那份、`name=` 可換、壞檔名 SpecBad，並真的拿 `aos-fsm` 跑兩步（`aos-fsm` 沒有只驗不跑的旗標）；一支建置腳本編兩夾；`.dry_run()` 等於 `.compile()` 寫出的；寫錯建構不丟、到 `.dry_run()`／`.compile()` 才丟（Agent、Fsm 各一）；eca 版不給夾＝SpecBad；同一張 fsm、同一串 tools（含 `defs.load` 的）、同一組 hooks 放進兩個 Agent，第二個不受第一個影響、物件編完沒被改；`defs.main(Fsm)` 給 `--static`＝FlagUnknown、`--compile` 只寫 fsm.json；`defs.main` 收到的不是一個物件＝一行 SpecBad、什麼都沒寫，被載入時載入方報 SpecBad；`defs.compile`／`defs.write`／`base.TOOLS` 是 AttributeError、`agent.TOOLS = …` 也擋；`defs.load` 回的物件自己 `.compile(夾)` 跟底一樣。

**舊寫法 grep**（設計稿 07b 的樣式，加 `^(TOOLS|LLM|SYSTEM|FSM|HOOKS) = `，`proto8/`＋`wf/`，排除 `proto8/thinking/` 與 `wf/HANDOFF.md`）：零命中（教學 06-1 的兩行等第 1 刀那條線交件放掉 claim 後改了，見「對不上處」第 6 條）；其餘命中都是無關的同名常數（`frontend`、`apps/mcp`、`agent-fsm/act.py` 等）。

## 跟設計稿對不上、或邊界有疑問的地方（都選最小的做法）

1. **`Unit` 與 `main(物件)` 的殼沒放進 `spec_base.py`，另開 `spec_unit.py`**：設計稿 07b 排在 `spec_base`（+約 40 行），但任務書定「`spec_base.py` 兩邊（第 1、2 刀）只用不改」。內容照設計稿；之後要併回 `spec_base` 只是搬檔。
2. **`events()` 兩種身體回同一張表**（`aos.agentlib.hooks.EVENTS`）：任務書定「hook 的檢查這一刀仍用現在程式實際用的事件表，不改接到宣告」，今天有沒有 fsm 實際都照這張驗；方法留著，照身體分開由 hook 線接 `hook_point.for_definition` 時做。驗 hook 的程式照舊直接叫 `validate_entry`，沒改走 `events()`。
3. **`defs.Agent` 的 `system`、`tools`、`llm` 是必給的關鍵字、其餘選填，說明以外都只收關鍵字**：設計稿寫 `system=, tools=, …`，沒說能不能照位置給；只收關鍵字可避開「hooks 跟 meta 順序跟以前 main 不同」的誤用。
4. **`defs.load` 回的 `base.tools` 是一個包（dict），不是串列**：才能照教學寫 `tools=[base.tools, defs.drop("grep")]`；所以 `defs.Agent(tools=…)` 也收單獨一個包，`base.compile(夾)` 才編得出。
5. **骨架的變數叫 `agent`**：照 07b「改成 `agent = defs.Agent(...)`」；設計稿 01 的邊緣說變數別叫 `agent`（會蓋掉 `from aos.py import agent`）。骨架本身不 import 那個模組，README 寫了一句提醒；要改名只改骨架兩行、產物不變。
6. **跟鄰線共用的檔**：教學 06-1 起先被第 1 刀那條線 claim；它交件（`f6b30bf9a`）放掉後，本線才改那章 agent.py 的兩行（`tools=` 尾巴加 shout、`llm={"model": "fake-shout"}`），第 1 刀改的工具那段沒碰。`py/docs/04-共用模組.md` 到交件時仍被 hook 線（aos-hook-k4-1120）claim，**沒改**：要在 `aos/spec_base.py` 那列後面加一列「`aos/spec_unit.py`｜能編譯的東西的底 `Unit`（`.dry_run()`／`.compile(夾)`）與 `main(物件)` 的命令列殼（線 aos-pylib-k2-1120）」，第 7 行「`defs`＝`aos.agent_spec`」後可補「（`defs.Agent` 的本體在 `aos.agent_spec_agent`）」——交頂層排。`py/aos/py/__init__.py` 與入口沒動（第 1 刀改了它，本線不需要）。
7. **`HELP` 順手改了一處錯字**：`--dynamic` 說「a tool added to a pack later shows up at the agent's next start」改成「next brain call」（aos-vs-c-1119 G6 已改 README、沒改 `--help`）。
8. **`.dry_run()`／`.compile()` 直接叫（不經 `defs.main`）時 warning 印成 `defs: warning: …`**：沒有腳本名可用；經 `defs.main` 照舊是 agent.py 那夾的名字。
9. **底交的是 `Fsm`（不是 Agent）時 `defs.load` 報 SpecBad**：設計稿沒提，衍生只對 agent。
10. **骨架 README「不給 fsm」那節的標題**從 Without FSM 改成 Without a state machine；`templates/README.md`、`py/README.md` 兩段歷史敘述直接改成現在的寫法，沒寫「舊名改新名」。

## 拿掉的名字

`defs.compile(...)`、`defs.write(...)`、`defs.HOOK_FIRE`、`defs.RENAME_LAST`（搬進 `agent_spec_agent`）；`defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, …)` 的收法；`defs.load` 回的 `DESCRIPTION`／`SYSTEM`／`TOOLS`／`LLM`／`FSM`／`META`／`INTERFACES`／`HOOKS`／`FILES` 與 `base.tools(prefix=…)` 方法（→ 小寫欄位與 `base.pack(...)`）；內部的 `agent_spec_load.Base` 類別。名字不變：`defs.main`、`defs.load`、`defs.drop`、`defs.lib`、`defs.tool`、`defs.extern`、`defs.home`、`defs.env`、`defs.state`、`defs.fsm`、`std.*`、所有旗標。

## HANDOFF 要改的字（交頂層；本線不碰 `wf/HANDOFF.md`）

- 名字那段（約 :28）：`defs.compile(...)`／`defs.write(...)` → 「物件的 `.dry_run()`（只算）／`.compile(夾)`（寫進夾）」；寫法改成 `a = defs.Agent("說明", system=…, tools=[…], llm={…}, fsm=…, hooks=…)`＋`defs.main(a)`；`base.TOOLS` 等 → `base.tools` 等小寫、`base.tools(prefix=…)` → `base.pack(prefix=…)`；`defs.fsm(...)` 回的能單獨 `.compile(夾)`。
- 約 :31「骨架自帶 `HOOKS = {}`」→「骨架的 `defs.Agent(...)` 自帶 `hooks={}`」。

## 第 3、4 刀開工前要知道的

- 第 3 刀（函數進 `tools=[…]`／`hooks=[…]`）：入口在 `Agent._files`（`agent_spec_agent.py`），`tools`／`hooks` 串列的疊法還在 `agent_spec_parts.stack_tools`／`stack_hooks`；抽檔寫 `fn/<名>.py` 用 `spec_base.write_files` 的 `Program` 與子夾。`agent_spec_parts.py` 仍 337 行（設計稿排第 3 刀拆 hook 那塊）。`events()` 是現成的方法，照事件表驗函數 hook 時接它。
- 第 4 刀（extern 連結版）：`defs.extern` 這刀沒動；教學 06-2 的 bob 用的正是 `system=defs.extern("system.txt")`，第 4 刀改意思時那章要再改一次（意見 16）。`.dry_run()` 不給夾時要報 SpecBad 的路已有（`_names` 的「give its folder」），連結版照同一條路。
- 第 3、4 刀都改 `agent_spec_agent.py` 與 `agent_spec_load.py`（07「不並行」）。
- `agent_spec_load._prog()`（第三份推名字）這刀仍沒收：它從 `sys.argv[0]` 推，換掉會動錯誤行開頭。
- 改的是 `py/`：**活樹要在 `~/repo/aos/proto8` 跑 `install.py` 才吃到**，要使用者點頭；本線沒跑。已經用舊寫法寫的 `agent.py`（使用者教學夾 `~/code/aos-tut` 若有）要照新寫法改寫才能再編譯；已編好的定義夾不受影響（產物一字不差，不用重編）。
