# 整套 Python 庫三刀施工（線 aos-pylib-cut-1119）：install.py 改成抄完刪孤兒、新增入口 aos.py（通用代理＋把手 a = agent.attach(名)）、把手接上 a.bp 與 a.look 並把建斷點改成 a.bp.add.<種類>(...)；aos-agent、daemon、cpp 一行沒動

← [2026-11-19](README.md)｜設計稿：[aos-pylib-1119](aos-pylib-1119/README.md)（[03 版面與細則表](aos-pylib-1119/03-版面設計.md)、[06 Argon 採納](aos-pylib-1119/06-Argon審與採納.md)、[07 使用者裁定](aos-pylib-1119/07-使用者裁定.md)）｜前一版斷點介面：[aos-gdb-lib-第二版](aos-gdb-lib-第二版.md)｜用法：[aos-gdb README](../../../py/aos/apps/gdb/README.md)、[入口檔頭](../../../py/aos/py/__init__.py)、[通則檔頭](../../../py/aos/py/_shell.py)

## 授權與使用者原話

- 開工：頂層問「整套 Python 庫的三刀（修 install、入口、把手接斷點）要開工嗎？」，使用者答：「開工」。
- 已裁（選項框，逐字在 [07](aos-pylib-1119/07-使用者裁定.md)）：入口 `aos.py`、把手式 `a = agent.attach("ann")`、建斷點 `a.bp.add.before_tool("x")` 回 id（沒選「兩種都留」→ 字串式拿掉）、讀 stack 的檔收進 `a.look`；隨手 `python3` 暫照推薦只靠入口。
- 施工途中改了寫定義的名字。使用者原話：「from aos.py import ag，這個ag應該是agent的縮寫吧」；頂層解釋 `ag` 是 agent_spec 的縮寫、跟 `agent` 容易混，他答：「改from aos.py.agent import defs。就是說這個defs不只會在agent，其他地方也會有，所以歸到agent下」；接著想過「啊，還是aos.py.defs，或是aos.py.std.defs」，最後定：「就 aos.py.agent.defs 吧」。所以入口頂層**不轉出 `ag`**，寫定義的是 `from aos.py.agent import defs`（＝`aos.agent_spec`，檔不搬）。骨架與既有測試裡的 `ag.` 改名不在本線（另一條改名線做）。
- 一路守的原話：「a.xxx這塊，感覺就是aos-agent xxxx」「以斷點為核心，增刪改查」「a.resume()…他的args不應該有東西」「不要看的出來，兩者解耦合」「感覺是個大工程，應該只需要把必要的搞進來就好」。

## 三刀各做了什麼

| 刀 | commit | 做了什麼 |
|---|---|---|
| 第零刀 | `3c4cc4c52` | `install.py` 不再一開頭整夾 rmtree：逐檔抄（一樣的不動、變了的寫暫存檔再 rename），全部抄完才刪「上次裝的、這次來源已沒有的」（py/ 刪掉的模組與空夾、entries.json 不列的入口、沒了的標頭、Makefile 不再做的 C++ 產物、lib 裡的 `__pycache__`）。哪些是 C++ 產物從 `make -B -n` 讀；dry run 沒列 bin 的東西、或 make 完少了列出的產物＝`BuildBad` 不刪；make 失敗＝舊的原封不動。最後一行多報 `removed N left over` |
| 第一刀 | `ee96fd190` | 新增 `py/aos/py/`：`__init__`（什麼都不先載入）、`_shell.py`（通用代理、`Text`、`Failed`、`Timeout`、`sh`，不 import `aos.gdb`）、`agent/`（套件：模組層薄殼＋把手 `Agent`＋`defs` 轉匯出）、`daemon_ctl.py`。現有檔 0 個改動 |
| 第二刀 | `1b1e108cc` | `a.bp`、`a.look` 接上 `aos.gdb`；建斷點改 `a.bp.add.<種類>(...)`；`aos.gdb` 拿掉 `Agent`／`attach`／`echo`／`sh`，例外與跑指令改用入口那份；`aos-gdb` 改放入口的名字、NAME 可省；新增 `aos.py.breakpoint`；文件與知識庫跟上 |

## 使用者現在會打的 Python（從 import 到收工）

```python
# 在任何 python3（$AOS_HOME/lib 在 sys.path 上；或直接 aos-gdb，下面這些已放好、echo 已開）
from aos.py import agent, daemon_ctl, std
from aos.py.agent import defs                # 寫定義（agent.py 裡用）：defs.tool、defs.state、defs.fsm、defs.main…
import aos.py; aos.py.echo = True            # 每條指令先在 stderr 印「$ ...」（aos-gdb 預設開）

agent.ctl.add("agents/ann", w=".", auto_restart=True, daemon=".stack")   # $ aos-agent --daemon .stack ctl add -w . --auto-restart agents/ann
a = agent.attach("ann", daemon=".stack")     # 不跑指令
a.say("hello"); a.listen(timeout_s=30)       # 回信名；回答原樣
a.ctl.state(json=True); a.tools.ls(); a.hook.ls()
b = a.bp.add.before_tool("write")            # "before_tool_1"
x = a.say("write a note"); a.bp.wait_stopped()
a.bp.why(); a.look.where(); a.look.history(3)
a.bp.resume()                                # 不收參數；a.bp.skip() 放行但工具不跑
a.listen(timeout_s=30, letter=x)
a.bp.rm(b); a.bp.ls()
a.bp.clear()                                 # 收工前：斷點不清會留在 agent 身上
daemon_ctl.shutdown(daemon=".stack"); daemon_ctl.shutdown(daemon="llms/stacks/llm")
```

## 建斷點各種類的最終寫法

形狀只有一個：`a.bp.add.<種類>([主詞], *, sh=None, py=None, times=1, once=False, id=None, replace=False)` → id（str）；watch 另有 `every_ms=500`、`also=()`。

| 種類 | 寫法例 | 主詞 | 停法 |
|---|---|---|---|
| before_tool | `a.bp.add.before_tool("write")` | 工具名 `tool`（也收 list；不給＝任何工具） | 扣住 |
| after_tool | `a.bp.add.after_tool("write", sh="grep -q x \|\| exit 10")` | `tool` | 暫停 |
| tool_error | `a.bp.add.tool_error(times=2)` | `tool` | 暫停 |
| before_queue | `a.bp.add.before_queue()` | 沒有 | 扣住 |
| after_queue | `a.bp.add.after_queue(py="...")` | 沒有 | 暫停 |
| brain_failed | `a.bp.add.brain_failed("BrainTimeout")` | 錯誤代號 `code` | 暫停 |
| tool_added | `a.bp.add.tool_added("grep")` | `tool` | 暫停 |
| after_start、after_stop | `a.bp.add.after_start()` | 沒有 | 暫停 |
| watch（觀察者） | `a.bp.add.watch(py=lambda t: ..., every_ms=200, also=["bob"])` | 沒有（一定要 sh 或 py） | 暫停（晚一格） |

- 種類表從 hook 事件表長出來（`aos.agentlib.hooks.EVENTS`，`on_clock` 不收），以後 hook 加事件這裡自動多一種。
- tab 補得出（`dir(a.bp.add)`）；打錯種類＝`AttributeError` 列出全部；多給參數、給沒主詞的種類位置參數＝當場 `Failed`（`ArgumentsBad`）；`a.bp.add("before_tool")` 直接叫＝`Failed`，說要寫種類；打 `a.bp.add` 印出每一種與參數。
- **沒有 `a.bp.add.on("事件", ...)`**：hook 的事件是固定表、沒有自訂事件，每個事件都已經是一個種類；多一條字串入口就是又把字串式帶回來。
- 刪改查不變：`rm(id)`、`set(id, enabled=, times=, once=)`、`ls()`、`get(id)`、`clear()`；`stop()`／`resume()`（不收參數）／`skip(text=None)`；`why()`、`held()`、`stopped()`、`wait_stopped()`、`notes()`。
- shell 提案（`aos-gdb bp add …` 或 `aos-bp`）沒做；若做，照同一個形狀：`aos-bp --target ann add before_tool write --times 2`。

## 使用者一天的流程（新寫法實跑一遍，原樣貼上）

在 `git archive` 乾淨複本 install 後的 start-api 暫存樹（假腦），shell 起好兩台 daemon、`aos-agent -d .stack ctl add --auto-restart -w . agents/ann` 之後，打 `aos-gdb -d .stack ann`，以下是畫面（路徑裡的暫存夾縮成 `$T`；`gdb>` 後補上打的那句；重複的 echo 行與表的其他列用 `...` 略去、兩行的回覆併成一行）：

```
aos-gdb: attached to ann (stack $T/.stack/procs/ann)
  ready: agent, daemon_ctl, std, defs, a = ann, a.bp = its breakpoints, a.look = its files.  Try: a.bp, a.bp.add.before_tool("x"), a.bp.why(), a.look.history(3), help(a.bp)
gdb> daemon_ctl.ls()
$ aos-daemon-ctl ls
_clock	running	421799	-	-	-
_sweeper	running	421801	-	-	-
ann	running	421836	-	$T	-
gdb> agent.ctl.ls()
$ aos-agent ctl ls
ann	running	$T	0	-
gdb> a.say("hello")
$ aos-agent --daemon $T/.stack --target ann say hello
'000000000001.01795064467167468323.421925.1801410'
gdb> a.listen(timeout_s=30)
$ aos-agent --daemon $T/.stack --target ann listen --timeout-s 30
FAKE ANSWER to: hello (tool said: 2026-11-19T05:01:09Z)
gdb> b = a.bp.add.before_tool("peek_now_time")
$ aos-agent --daemon $T/.stack --target ann hook add --event before_tool --name gdb_before_tool_1 --path-json '{"$env": "AOS_HOME", "$path": "/lib/tools/agent/gdb_trigger"}' --on-error continue --timeout-ms 0 --condition peek_now_time --replace
gdb> b
'before_tool_1'
gdb> x = a.say("write a note"); a.bp.wait_stopped()
$ aos-agent --daemon $T/.stack --target ann say 'write a note'
True
gdb> a.bp.why()
ann is held at breakpoint before_tool_1: tool peek_now_time has not run yet; a.bp.resume() lets it go on as it was, a.bp.skip() skips that call
  2026-11-19T13:01:14.451+08:00 hook gdb_before_tool_1: tool peek_now_time is about to run [held before it]
      name="peek_now_time" arguments={}
gdb> a.look.where(); a.look.history(1)[0]["tool_calls"][0]["function"]["name"]
$ aos-agent --daemon $T/.stack --target ann ctl state --json who
# read $T/.stack/procs/ann/stage.txt
...
'act'
'peek_now_time'
gdb> a.hook.ls()
$ aos-agent --daemon $T/.stack --target ann hook ls
brain_notify	brain_failed	{"$env":"AOS_HOME","$path":"/lib/tools/agent/brain_notify"}
gdb_before_tool_1	before_tool	{"$env":"AOS_HOME","$path":"/lib/tools/agent/gdb_trigger"}
...
gdb> a.bp.resume()
$ release gdb_before_tool_1: run (writes $T/.stack/procs/ann/gdb/release.json)
ann: released; going on with peek_now_time (by repl)
gdb> a.listen(timeout_s=30, letter=x)
FAKE ANSWER to: write a note (tool said: 2026-11-19T05:01:15Z)
gdb> a.llm.set("model=fake")
$ aos-agent --daemon $T/.stack --target ann llm set model=fake
gdb> a.bp.rm(b); a.bp.ls()
$ aos-agent --daemon $T/.stack --target ann hook rm gdb_before_tool_1
[]
gdb> a.ctl.stop(); a.ctl.start()
stopped, stack kept (...); started (same stack); 0 queued letter(s) will be answered next
gdb> agent.ctl.rm("ann")
$ aos-agent ctl rm ann
removed ann; stack $T/.stack/procs/ann kept (delete it with aos-agent ctl rm --purge, or by hand)
gdb> daemon_ctl.shutdown()
$ aos-daemon-ctl shutdown
daemon at $T/.stack stopped (ctl seq 1); 2 procs asleep, they wake when it starts again
gdb> daemon_ctl.shutdown(daemon="llms/stacks/llm")
$ aos-daemon-ctl --daemon llms/stacks/llm shutdown
```

另跑了一次不給 NAME（`aos-gdb -d .stack`）：REPL 裡 `agent.ctl.add(...)`、`a = agent.attach("ann")` 之後同樣走得通；`a.resume` 當場 `AttributeError`（列出 aos-agent 的子指令與 `a.bp`、`a.look`），`a.bp.add("before_tool")` 當場 `Failed` 說要寫種類。

對照 [02 的 21 步](aos-pylib-1119/02-一天的流程.md)：第 5～14、16～18、21 步都是上面這種一句；第 1、4 步（抄樹、起樹）照設計留 shell；第 15、19、20 步照設計不做。

## 我定的細節（設計稿沒講到、非定不可的）

1. **install.py 怎麼認 C++ 產物**：讀 `make -B -n` 的 dry run（`-o` 後面、`ar rcs` 後面落在 bin/、lib/ 的檔）；不改 Makefile。dry run 一個 bin 的都沒列就停手（免得把 C++ 全當孤兒刪掉）。lib 裡的 `__pycache__` 當孤兒刪（全新裝也不會有）。
2. **以 `-` 開頭的位置參數一律先放 `--`**，所以設計稿說的「`a.tools("add", "--no-cache", "x")` 把字串原樣丟過去」不成立（字串一律是值）；旗標用關鍵字給（`a.tools.add("x", no_cache=True)`），真要原樣打就 `sh("aos-agent …")`。頂層通用殼 `a("peek", "/status")` 照樣能用。位置參數的 `True`／`False` 寫成 `true`／`false`。
3. 指令的 stdin 一律接 `/dev/null`（REPL 裡不會被等輸入的指令卡住）。
4. 手寫的只有 `say`（回信名、去掉換行）；`listen` 走代理就對（`a.listen(timeout_s=20, letter=x)`），沒手寫。
5. `attach` 把 daemon 轉成絕對路徑（之後 `cd` 不會指到別處）；daemon 不給＝庫什麼都不加。`a.stack` 每次問都跑一條 `ctl state --json who`（不快取，照 A6）；`a.bp` 每次取是新的，它裡面第一次用到 stack 問一次、這一個 `a.bp` 用到底。
6. **`a.bp` 要絕對的 daemon**（觀察者與觸發器的字條要記）：把手沒給就用 `$AOS_DAEMON`，再沒有＝`Failed DaemonMissing`（沿用舊 `aos.gdb` 的規則，不自己抄 `./.stack` 那條預設）。`aos-gdb -d D` 會在 REPL 裡設 `AOS_DAEMON=D`，所以模組層 `agent.ctl.ls()`、`daemon_ctl.*` 也對那台。
7. echo 開關是套件屬性 `aos.py.echo`（`from aos.py import echo` 再改它沒用，文件寫 `aos.py.echo = True`）；印在 stderr；讀檔印 `# read 路徑`；`aos.gdb` 內部幾支 quiet 的查詢不印。
8. `Failed(where, why, code=…)`：指令失敗＝它自己的錯誤行原樣、`program`／`code`／`reason` 拆好；庫自己拒絕＝`where: why`。`Timeout` 只給庫自己等的（`wait_stopped`、等放行、等觀察者下表）；指令自己的逾時（例 `listen` 的 `AnswerMissing`）照指令的代號是普通 `Failed`。
9. `aos.gdb` 改 import `aos.py._shell`（方向是延伸→入口；入口的 `_shell` 不 import `aos.gdb`），活的那一邊只有一種 `Failed`。
10. 建斷點自己取名從 `name=` 改 `id=`（`name` 會跟主詞搞混，也跟回傳的 id 同一個詞）；主詞參數名 `tool`，`brain_failed` 用 `code`。
11. `a.look` 讀不到的檔照舊是 `None`／`[]`（觀察者條件靠 `t.history(0)` 回 `[]`）；`request()` 的 JSON 壞了＝`Failed JsonBad`。`Look.state()` 拿掉（`a.ctl.state()` 是指令）。
12. `aos.py.agent` 做成套件（`from aos.py.agent import defs` 才成立）；`defs`、`std` 都是一行轉匯出（`REEXPORT`），要搬位置改一行。`import aos.py.agent.defs`（當子模組 import）不成立，只有 `from … import defs` 與 `agent.defs`。
13. 知識庫沒另開一筆給 agent 看的 `aos.py` 說明：agent 用工具、不開 Python REPL；收進 `cli/gdb.json` 開頭一段。
14. 骨架（已交版本）找套件的寫法遇到 `aos/py/` 夾不受影響：它找的是 `aos` 套件，`aos.py` 是子套件不是檔；「夾裡有一支 `aos.py` 檔」那個坑歸 `aos-inherit-cut1-1119`。

## 測試

都在 `git archive` 乾淨複本（疊上改動）install 後跑，暫存樹在 `~/.aos/scratch/aos-pylib-cut-1119/`，收尾 `pgrep` 核對沒有自己留下的行程。

- 第零刀：`test_install` 15 支過（新 4 支）；真的跑 `install.py`：全新裝 29 支指令（9 C++、20 Python）、重裝 `removed 0`、py 刪 `swap.py` 再裝 `removed 1` 且 `lib/aos/swap.py` 沒了、bin 29 支與 12 個 libaos 都在。
- 第一刀：`test_aos_py` 13 支（不起 daemon，假 `aos-agent`／`aos-daemon-ctl` 印回 argv）、`test_aos_py_live` 4 支（假腦）。
- 第二刀：`test_gdb_trigger` 30 支、`test_gdb_live` 13 支全照新寫法；四份合跑 58 支全過（約 220 秒）。

## 沒做的與為什麼

- `py/README.md`：被 `aos-inherit-cut1-1119` claim 住，本線沒改；等它交完再補一段（見回報）。
- 骨架與既有測試、文件裡的 `ag.` → `defs.`：頂層另派改名線。
- 起樹與抄樹、`aos-tools`／`aos-mailbox` 等其他指令的模組、在庫裡展開工具包、執行中加的東西寫回 `agent.py`、斷點的 shell 指令：設計稿明講不做。
- 縮寫表 `docs/CONCEPTS/abbr.json` 補 `bp`（03 第一節提過，C-54）：不在任務範圍，沒動。
- 沒在 `~/repo/aos/proto8` 跑 `install.py`：要用的那份要重跑才生效（新的裝法與 `aos.py` 都要），這一步換活樹，先等使用者說。

## 要使用者拍板的

1. `from aos.py import std` 放在入口頂層是頂層暫定（`defs.std` 也拿得到）；要不要留在頂層？
2. 建斷點的參數名：自己取名 `id=`、主詞 `tool`（`brain_failed` 是 `code`）可以嗎？`skip`、`wait_stopped` 兩個名字仍是暫定（03 建議 `wait`）。
3. 什麼時候在要用的那份 proto8 跑 `install.py`。
