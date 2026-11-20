編譯程式庫第 1 刀（新模組 `fn`、工具骨架換成函數寫法、`tools_def` 跟著）施工紀錄（11-20，線 aos-pylib-k1-1120）：做了什麼、新舊寫法對照、驗收、跟設計稿對不上處、替使用者選的、HANDOFF 要改的字、第 3 刀開工前要知道的。

← [2026-11-20](README.md)｜設計稿：[aos-pylib-plan-1120](aos-pylib-plan-1120/README.md)（第 1 刀在 [07b](aos-pylib-plan-1120/07b-施工計劃-第0到2刀.md#第-1-刀-fn-與工具骨架)）｜使用者答案：[12-使用者已答](aos-pylib-plan-1120/12-使用者已答.md)｜上一刀：[第 0 刀](aos-pylib-k0-1120.md)

使用者 11-20 答待裁第 4 題「新名字 fn」；被問施工時答「第 1、2 刀都開」。第 2 刀是同時開工的另一條線（aos-pylib-k2-1120），兩邊的檔排開見末節。

## 一句話

寫工具從「大寫常數＋`ts.main(run, DESCRIPTION, PARAMS, META)`」換成「一個函數加 `@fn.tool`＋最後一行 `fn.main(函數)`」：說明取 docstring、參數型別取型別註記、參數說明取 docstring 的 `Args:`，也收明寫的（`description=`、`fn.param`），明寫的贏、一個參數一個參數算。**骨架改寫後重新編譯的 `_tooldef.json`、`_metainfo.json` 跟提交的那份逐 byte 相同，四個旗標、`--help`、直接執行與 `aos-exec` 的 stdout／stderr／結束碼都跟改寫前逐 byte 相同**。`@fn.hook` 的回話（`None`／dict／`fn.block` 退 10）也做了，手寫一支 hook 掛進暫存定義夾，經 agent 的 hook 引擎實叫攔得下。舊寫法不留；`tool_spec` 照設計留作內部零件。

## 新舊寫法對照（骨架 `templates/tool-python/tool.py` 的下半段）

舊（11-19 以前）：

```python
DESCRIPTION = 'Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5'

PARAMS = [
    ts.param("a", "number", "the first number"),
    ts.param("b", "number", "the second number"),
]

META = {"side_effect": False}


def run(args):
    return args["a"] + args["b"]


ts.main(run, DESCRIPTION, PARAMS, META)
```

新：

```python
@fn.tool(meta={"side_effect": False})
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5

    Args:
      a: the first number
      b: the second number
    """
    return a + b


fn.main(add)
```

開頭找套件那幾行只換了一行：`from aos import tool_spec as ts` → `from aos.py import fn`。明寫的寫法：`@fn.tool(description="…", params=[fn.param("b", "integer", "…", enum=[1, 2])], errors=["TooBig"], name="sum")`。

## 動了哪些檔

| 檔 | 做什麼 |
|---|---|
| `py/aos/py/fn.py`（新，23 行） | 公開的名字，只轉出 `tool`、`hook`、`param`、`fail`、`block`、`main`（和 `Fail`、`Block` 兩個類別）；設計稿意見 5 |
| `py/aos/fn_mark.py`（新，202 行） | 裝飾器只做記號、回原函數；`tool_spec_of(函數, 掃到的代號)` 算出（工具名, `_tooldef`, `_metainfo`）：docstring 拆說明與 `Args:`、型別註記（含字串註記）→ JSON 型別、簽名從 code 物件拿（不載入 `inspect`）、逐參數合併，組裝交給 `tool_spec.tooldef`／`metainfo` |
| `py/aos/fn_run.py`（新，170 行） | `fn.main`：工具的四個旗標與執行（原 `tool_spec.main()`、`_print_result()` 搬來）；hook 的執行與回話；`fn.fail`／`Fail`、`fn.block`／`Block` |
| `py/aos/tool_spec.py`（284 → 205） | 拿掉 `main`、`_print_result`、`fail`／`Fail`；`_errors_in` 改名 `errors_in`（`fn_run` 要叫，不叫別支的私有函式，同意見 2）；檔頭改成「內部零件」 |
| `py/aos/py/__init__.py` | `SUBMODULES` 加 `fn`；檔頭範例加一行 |
| `templates/tool-python/tool.py`、`README.md` | 改成新寫法；README 改「寫什麼」「完整例子」「幫你做了什麼」三節，補說明書快取一句（意見 17） |
| `py/tools/agent/tools_def/_entry`（652 → 660，不拆，意見 1） | `new` 的 `description` 塞成第一個 `@fn.tool(...)` 的 `description=`（意見 3）；認不認得腳本改看有沒有 `fn.main(`；訊息裡的 `tool_spec`、`DESCRIPTION`、`run(args)` 改掉 |
| `py/tools/agent/tools_def/_tooldef.json` | 三處教舊寫法的字改掉 |
| `py/tests/test_fn.py`（新，236 行）、`py/tests/test_fn_run.py`（新，198 行） | 一支 250 會超過 300 行，拆兩支：記號與說明書（03 的兩張表）／`fn.main` 的工具與 hook 執行 |
| `py/tests/test_tool_spec.py` | `main()` 的測試搬去 `test_fn_run.py`，剩說明書零件的測試；`as ts` 拿掉 |
| `templates/tests/tool-python/test_skeleton.py` | 加一條：抄出去 `--compile`，兩份檔跟提交的逐 byte 相同 |
| `py/tools/agent/tools_def/tests/test_tools_def.py` | 測試裡的舊寫法跟著換（`return a + b`、`a: float` 等） |
| `knowledge/aos/tools_def.json`、`_index.json`、`cli/tool_flags.json` | `#/tool_spec` 那一節改名 `#/fn`、內容改成新寫法；`_description` 指到 `#/fn`；另兩份各改一句 |
| 教學 06-1、`py/docs/01-分層等.md`、`01-分層等/02-規則5a至11與引用.md`、`03-索引-agent等.md` | 舊寫法改掉；01 的模組清單加 `fn.py`、`fn_mark.py`、`fn_run.py` 三行 |

## repo 裡用舊寫法的工具

- **換了**：只有骨架 `templates/tool-python/tool.py`（`git grep 'tool_spec as ts\|ts\.main('` 在交件前只有它與測試、文件）。
- **留著（內部零件）**：`tool_spec` 的 `param`、`tooldef`、`metainfo`、`write`、`split_location`、`errors_in`、兩個 `*_problems`：`fn_mark`／`fn_run` 與 `tools_def`（分階段 `add_tooldef` 用 `tool_spec.param(**p)` 組手給的參數、`check` 用兩個 `*_problems`）在用。
- **舊寫法 grep**（07b 的樣式 `ts\.main\(|tool_spec\.main\(|tool_spec as ts|def run\(args\)`，`proto8/`、`wf/`，排除 `proto8/thinking/`）：前三個零命中；`def run\(args\)` 命中 4 處，都不是 tool_spec 寫的工具，是各自的內部函式剛好同名（`py/tools/aos/defs/catalog.py:233`、`review_round/round_runner.py:93`、`watch/watch_state.py:167`、`base/peek_now_time/tests/test_peek_now_time.py:14`），沒動。

## 驗收（實際指令與結果）

環境：`git archive HEAD proto8`（HEAD＝`b1c075f60`）抄到 `~/.aos/scratch/aos-pylib-k1-1120/src`，複本裡 `install.py`；每支腳本先 unset 所有 `AOS_*`，再 `env -i PATH=<複本>/bin:/usr/bin:/bin HOME=… PYTHONDONTWRITEBYTECODE=1 AOS_HOME=<複本>`；TMPDIR 用預設。改動前跑一次留底（`cap-base`、`tests-base`），把本線的檔（只本線的，工作樹裡別線的改動不抄）疊上去、再 `install.py`，同一支腳本、同一個路徑再跑一次（`cap-new`、`tests-new`）。

**產物與輸出一字不差**（`sh/capture.sh`，18 種情況）：

- 在複本的骨架夾裡 `tool.py --compile`；抄一份叫 `add` 的：`--compile`、`--dry-run`、`--tooldef`、`--metainfo`、`--help`、`--compile a b`（多給）、`--dry-run x`（多給）、`--compile obj.json#/tools/x`、`--compile 另一夾`、餵 `{"a":2,"b":3}`（印 `5`）、`{"a": 2, "b": 0.5}`、缺 `b`、型別錯、不認得的鍵、用旗標 `--a 4 --b 5`、`aos-exec add` 兩種。
- 每種的 stdout、stderr、結束碼，加上寫出的 `_tooldef.json`／`_metainfo.json`（骨架夾、`add`、另一夾）、`obj.json`、權限清單，共 63 份，`cmp` **63 份全同、0 份不同**。
- 複本骨架夾裡重新編譯出的兩份檔跟 repo 提交的那份 `git diff --no-index` 無差；repo 裡這兩份檔本線沒改（`git diff HEAD` 無差）。
- 新加的 `test_skeleton.py` 那條（抄出去 `--compile`、`read_bytes()` 比）也過。

**測試**（逐夾 `python3 -m unittest discover`，改動前／改動後）：

| 夾 | 改動前 | 改動後 |
|---|---|---|
| `py/tests`（含 `test_tool_spec`、`test_spec_base`、`test_aos_py`、`test_agent_spec*`） | 640 OK（skip 1、expected failure 1） | 654 OK（同）：多 `test_fn.py` 10 條、`test_fn_run.py` 9 條，`test_tool_spec.py` 搬走 5 條 |
| `templates/tests/tool-python` | 4 OK | 5 OK（多逐 byte 比那條） |
| `py/tools/agent/tools_def/tests` | 12 OK | 12 OK（第一輪 1 條紅：測試裡還有一處舊寫法的字串取代，改掉後重跑 12 OK） |
| `py/tools/aos/defs/tests` | 27 OK | 27 OK |
| `py/tools/agent/agent_def/tests` | 30 OK | 30 OK |
| `py/tests/apps/*` 十六夾 | 除 feedback 外全 OK | 同左，每夾條數相同 |

- `py/tests/apps/feedback` 兩邊都是 18 條 error：要讀 repo 的 `wf/advices/feedback/raters.json`，乾淨複本只抄 `proto8/`，跟本線無關。
- `tools_def` 的 `new`（資料夾、JSON 物件兩種）加 `check` 對新骨架全過，在 `test_tools_def.py` 裡。
- 沒在 `~/repo/aos/proto8` 跑 `install.py`（活樹要吃到新寫法，要使用者點頭後在 repo 跑）。只用假腦（這一刀其實沒起任何 agent）。

## 跟設計稿對不上、或沒定的地方（都選最小的做法）

1. **`fn.fail`／`Fail` 也從 `tool_spec` 搬走**：07b 只列了 `main()`、`_print_result()`；但 `ts.fail` 本身就是舊寫法的一部分，留著等於留舊名。搬進 `fn_run`。
2. **`--help` 也掃 `fn.fail` 代號**：03 寫「只在 `--tooldef`、`--compile`、`--dry-run` 掃」（還有 `--metainfo`）。但 `--help` 最後一行會列錯誤代號，不掃的話用了 `fn.fail` 的工具 `--help` 會少印代號、跟今天不同。`--help` 不是平常執行，加進去。
3. **工具函數丟例外的錯誤行**：今天是 `RunFailed run() raised …`；沒有 `run` 了，改成 `RunFailed <函數名>() raised …`（骨架是 `add() raised …`）。骨架的四個旗標與正常執行不受影響。hook 照 03 的表：`RunFailed 例外名: 訊息 (檔 行號)`。
4. **`fn.param` 的參數**：照 03「`fn.param("名", 型別, 說明, enum=, items=)`、必填與預設值不能明寫」；型別寫 JSON 的名字（`"integer"`、`"number"`…），同今天的 `ts.param`。
5. **工具函數裡用 `fn.block` 的判法**：意見 11 定「編譯時 `SpecBad`」。我看函數的 code 物件（連裡面的巢狀函數、推導式）同時用到 `fn` 與 `block` 兩個名字就報，不讀原始碼、不找字串（A6 那條是講第 3 刀抽原始碼）。說明書每次執行前都會算，所以平常執行也會報這一行（同今天宣告寫錯的行為）。極少見的誤判：工具裡另有別的東西叫 `.block`、同時又用了 `fn`。
6. **docstring 的 `Args:` 段**：03 只寫了大意，我定的細節——第一個參數行的縮排是基準；比它深＝接上一行；比它淺、或「一個詞加冒號」（`Returns:`）、或不是「名: 說明」的行＝段結束；空行跳過。
7. **型別註記**：六種加 `list[X]`（X 是那六種之一，帶 `items`）。另外 `dict[...]` 當 object、`typing.List[str]` 也認（不教）；`list[list[int]]` 這種＝不認、要明寫。
8. **hook 這一刀做到哪**：`@fn.hook(事件, 鍵=值…, name=, async_=)` 只記著（`async_` 記成 `async`）；`fn.main(hook 函數)` 讀 stdin 的事件、照 03 的回話表退 0／10／1；只收 `--help`，其他參數＝`ArgumentsBad`。**事件名對不對事件表、那些鍵寫進 `hooks.json` 都是第 3 刀**，這一刀不驗。`@fn.hook` 沒給事件名＝`fn.main` 時 `SpecBad`；hook 函數不是恰好一個參數＝`SpecBad`。
9. **「掛進暫存定義，實叫時攔得下」的做法**：測試在暫存夾做一個定義夾（`interfaces.json` 宣告 `hooks.json`，handler 指到一支用 `@fn.hook` 寫的可執行檔），直接叫 agent 的 hook 模組 `aos.agentlib.hooks.fire`（agent-fsm 的格、aos-eca-turn 叫的就是它，經 `aos-exec` 跑 handler）：攔下、改 `arguments`、condition 不合不跑三種都對。**沒有起一隻用假腦跑的 agent**；引擎那一段是同一支程式。
10. **錯誤行的名字**：照意見 4，`name=` 有給用它，沒有照檔名規則（`tool.py`＝夾名、`mul.py`＝`mul`）；工具名（以後 `tools.json` 的鍵）預設＝函數名，這一刀只用在說明書的訊息裡。
11. **`tools_def` 認不認得腳本**：從「檔裡有 `tool_spec` 這個字」改成「有 `fn.main(` 這串」。`new` 給了 `description` 時改寫第一個 `@fn.tool` 那行（`@fn.tool` 或 `@fn.tool(...)` 都行），docstring 不動——明寫的贏，所以新工具的說明就是給的那句，docstring 留著骨架的字，`check` 不會報「說明還是骨架的」。這是意見 3 推薦的做法；人看 `tool.py` 可能會被留著的 docstring 搞混，記在這裡。
12. **共用的三份文件沒改**（見末節）。

## 替使用者選的（他沒答的照設計稿預設）

- **待裁第 7 題（函數裡的相對路徑從哪算）**：照設計稿預設＝照今天工具的規矩（`aos-exec` 給的工作路徑）。這一刀 `tool.py` 本來就是自己跑，沒有改變任何東西；抽出 `fn/<名>.py` 時才會碰到。
- **待裁第 9、10 題**：這一刀碰不到（kernel、`agent_def new`），沒做任何事。
- **第 5 題「先不定」**：照設計先全部報錯——那是第 3 刀抽函數時查的；這一刀的 `fn` 沒有任何東西會擋到它（工具函數就在自己那支檔裡跑）。

## 要頂層改的字（本線不碰）

- `wf/HANDOFF.md`：grep 過沒有提到 `tool_spec`、`ts.main`、骨架寫法的字，**不用改**。
- `wf/tools/index_gen_desc.json:350-351`（目錄說明，生成 code map 用）兩句還寫著「旁邊放 tool_spec.py」「tool.py 用 py/aos/tool_spec.py 寫」，建議改成：
  - `proto8/templates/tests/tool-python`：「tool-python 骨架的測試：重新編譯的 _tooldef.json／_metainfo.json 跟提交的逐 byte 相同、跟 tool.py 一致，抄到 repo 外只靠 AOS_HOME 或旁邊放 aos 套件也能跑」
  - `proto8/templates/tool-python`：「tool-python：一支工具的骨架（不是 agent 範本），tool.py 用 aos.py.fn 寫（@fn.tool＋fn.main）、編譯出 _tooldef.json 與 _metainfo.json；要做一支新的 Python 工具時用 tools_def new 或 cp -r 它」
- 共用的三份文件（見末節）若本線收尾時還被別線佔著，要加的字列在末節。

## 第 3 刀開工前要知道的

- 抽出的 `fn/<名>.py` 長什麼樣：照 03，就是「骨架開頭那幾行＋`from aos.py import fn`＋函數（裝飾器照搬）＋`fn.main(函數)`」；`fn.main` 已經會跑工具與 hook，第 3 刀只要把檔寫出來（`spec_base.write_files(夾, {"fn/add.py": Program(...)})`）。
- 說明書：`fn_mark.tool_spec_of(函數)` 回（工具名, `_tooldef`, `_metainfo`）；工具名＝`name=` 或函數名，`tools.json` 的鍵用它（再經 `base.pack(prefix=, rename=)`）。
- hook 的記號：`getattr(函數, fn_mark.MARK)`＝`{"kind": "hook", "event": …, "name": …, "entry": {其餘鍵，async_ 已改成 async}}`，第 3 刀照事件表驗、寫進 `hooks.json` 那格。
- 錯誤代號是從**函數所在那支檔**掃的（`co_filename`），抽出之後就是掃 `fn/<名>.py`；`agent.py` 裡別的函數的 `fn.fail` 不會混進來是因為抽出的檔只有那一個函數。
- 第 3 刀抽原始碼時，`fn.block` 用在工具裡的判法（code 物件的名字）可以直接沿用 `fn_mark._names_in`。
- 每次叫多一點時間（說明書每次執行前從函數算一次；不讀原始碼）。

## 跟第 2 刀那條線（與 hook 第 4 刀那條線）的檔

- 沒撞到程式檔：本線動 `tool_spec`、`fn` 三支、工具骨架、`tools_def`；第 2 刀動 `agent_spec*`、agent 骨架。`spec_base.py` 只用不改；`hook_point.py`、各 `hook_points.json`、`agent_spec*` 沒碰。
- 兩邊都要的入口 `py/aos/py/__init__.py`：開工時沒人 claim，本線 claim 後改兩行（`SUBMODULES` 加 `fn`、檔頭範例一行），在第一筆 commit 交掉。
- 教學：本線只改 06-1；第 2 刀改 04、05、06-2、06-3、08 與教學 README，沒有同一份。
- **三份共用文件本線收尾時仍被別線 claim，沒改**（不 `--force`）：`py/README.md`、`templates/README.md`（第 2 刀線）、`py/docs/04-共用模組.md`（hook 第 4 刀線）。要加的字如下，等它們放掉後由本線補一筆、或交給頂層：
  - `py/README.md:13` 開頭那段「給 AI 寫新工具用 [`tool_spec.py`](aos/tool_spec.py)（…）：一支 Python 裡宣告說明、參數（`ts.param`）、特性（`META`）和 `run(args)`，它產 `_tooldef`／`_metainfo`（…）、執行時接 `tool_io` 驗參數；」換成「寫新工具用 [`aos.py.fn`](aos/py/fn.py)（[tools-def](../thinking/2026-11/10/tools-def/README.md)；11-20 起，使用者選「新名字 fn」，線 aos-pylib-k1-1120）：一個函數加 `@fn.tool`、最後一行 `fn.main(函數)`，說明取 docstring、參數取型別註記與 `Args:`，也收明寫的（`description=`、`fn.param`，明寫的贏），它編譯出 `_tooldef`／`_metainfo`（資料夾的兩個檔，或 JSON 物件的兩個鍵）、執行時接 `tool_io` 驗參數；本體在 [`fn_mark.py`](aos/fn_mark.py)、[`fn_run.py`](aos/fn_run.py)，說明書的零件留在 [`tool_spec.py`](aos/tool_spec.py)；」，其後「現有工具不必遷移」那句拿掉（proto8 不留舊版）。
  - `templates/README.md:20`「`tool.py`（用 [`py/aos/tool_spec.py`](../py/aos/tool_spec.py) 寫的加法）」換成「`tool.py`（用 [`aos.py.fn`](../py/aos/py/fn.py) 寫的加法：`@fn.tool` 標一個函數、最後一行 `fn.main(add)`；11-20 起，線 aos-pylib-k1-1120）」。
  - `py/docs/04-共用模組.md`「給人用的那一層在 `aos.py`」那段的 `from aos.py import agent, daemon_ctl, std`、`from aos.py.agent import defs` 後面加「、`from aos.py import fn`（函數當工具／hook：`@fn.tool`、`@fn.hook`、`fn.main`；本體 `aos.fn_mark`、`aos.fn_run`，說明書零件 `aos.tool_spec`；11-20 線 aos-pylib-k1-1120）」；表裡 `spec_base` 那列的「誰 import 它」不變。
