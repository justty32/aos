編譯程式庫第 3 刀（agent.py 裡 `@fn.tool`／`@fn.hook` 的函數編譯時抽成定義夾的 `fn/<名>.py`，寫進 `tools.json`／`hooks.json`）施工紀錄（11-20，線 aos-pylib-k3-1120）：做了什麼、寫起來的樣子、驗收、跟設計稿對不上處、替使用者選的、要頂層改的字。

← [2026-11-20](README.md)｜設計稿：[aos-pylib-plan-1120](aos-pylib-plan-1120/README.md)（第 3 刀在 [07c](aos-pylib-plan-1120/07c-施工計劃-第3到5刀.md#第-3-刀-函數進-agent抽出來)、[03](aos-pylib-plan-1120/03-函數當工具與hook.md)、[04](aos-pylib-plan-1120/04-函數-依賴與互動.md)）｜使用者答案：[12-使用者已答](aos-pylib-plan-1120/12-使用者已答.md)｜上一刀：[第 1 刀](aos-pylib-k1-1120.md)、[第 2 刀](aos-pylib-k2-1120.md)

使用者 11-20 說「開工吧」。依據的原話：「抽出來」「兩種都收，明寫的贏」「一起，同一套寫法」；第 5 題「先不定」（→ 照設計先全部報錯）；第 7 題「照今天工具的規矩」；hook 線的題「掛到這隻 agent 不會發的事件：照舊不管」。

## 一句話

`agent.py` 裡寫一個 `@fn.tool` 的函數放進 `tools=[…]`、一個 `@fn.hook("事件", …)` 的函數放進 `hooks=[…]`，`--compile` 就在定義夾多寫一支可執行的 `fn/<名>.py`（找 aos 的幾行＋用到的 import＋函數原文＋`fn.main(名)`），`tools.json` 寫 `"add": {"path": "fn/add.py"}`、`hooks.json` 寫 `"no_secrets": {"event": …, "handler": "fn/no_secrets.py", 其餘鍵}`。**沒用函數的 agent 編出來逐 byte 相同**；用假腦在暫存樹實際起一隻：腦叫 `add` 拿到 `5`，含 secret 的 `ws_write` 被 hook 攔下、history 有原因、檔沒寫出來，`agent_def check` 回 `{"problems": []}`。

## 寫起來

```python
from aos.py import fn
import re


@fn.tool
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5

    Args:
      a: the first number
      b: the second number
    """
    return a + b


@fn.hook("before_tool", condition="ws_write")
def no_secrets(event):
    """Stop a ws_write that mentions a secret."""
    if re.search("secret", str(event.get("arguments"))):
        return fn.block("the arguments mention a secret")


agent = defs.Agent("...", system="...", tools=[std.pack("ws-write"), add], llm={}, fsm=std.fsm(), hooks=[no_secrets])
defs.main(agent)
```

抽出來的 `fn/no_secrets.py`（755）：

```python
#!/usr/bin/env python3
"""no_secrets - Stop a ws_write that mentions a secret."""
# ---- setup: find the aos package under $AOS_HOME/lib (keep these lines as they are) ----
import os as _os, sys as _sys
...（sys.path 第一格真的是 fn/ 才拿掉；AOS_HOME 沒設＝HomeMissing 一行；只認 $AOS_HOME/lib）
from aos.py import fn
...
# ---- the function ----
import re


@fn.hook("before_tool", condition="ws_write")
def no_secrets(event):
    ...


fn.main(no_secrets)
```

## 動了哪些檔

| 檔 | 做什麼 |
|---|---|
| `py/aos/fn_spec.py`（新，293 行） | 只在編譯時用。`tool_item`（tools 裡的函數→一支自己寫的工具，那格帶 `$fn` 指回函數）、`hook_entry`（hooks 裡的函數→一格）、`programs`（`tools.json`／`hooks.json` 算完後把帶 `$fn` 的格換成真路徑、產出 `{"fn/<名>.py": Program}`）。找函數用語法樹＋`co_firstlineno`（第一個裝飾器那行）；外面的名字用 `symtable` 問（函數本體），裝飾器、預設值、型別註記各自用 `symtable` 的 eval 模式問；`fn.block(` 看語法樹的呼叫節點 |
| `py/aos/agent_spec_hooks.py`（新，107 行） | 從 `agent_spec_parts.py` 拆出 hook 那塊（`Hooks`、`no_hooks`、`stack_hooks`、`hooks_json`、`HOOKS_SHAPE`），加函數 hook；兩個函數同一個 hook 名＝SpecBad |
| `py/aos/agent_spec_parts.py`（337 → 258） | hook 那塊搬走；`stack_tools` 收函數（`fn_spec.tool_item`） |
| `py/aos/agent_spec_agent.py`（257 → 268） | `_files` 最後叫 `fn_spec.programs(…, self.events())`，程式檔不經 `_plain`（那會變回普通字串、權限不是 755）；程式檔跟別的檔／extern 撞名＝SpecBad |
| `py/aos/agent_spec_load.py` | 底的函數那格（帶 `$fn`）不做相對路徑換算，衍生那支在自己的夾重抽；改叫 `agent_spec_hooks` |
| `py/aos/agent_spec_lib.py` | `std.hooks` 回的 `Hooks` 改從 `agent_spec_hooks` 拿（一行 import、一行呼叫、一處註解） |
| `py/aos/agent_spec.py` | 檔頭一段、`HELP` 加兩行（函數會被抽成 `fn/<名>.py`） |
| `py/tests/test_fn_spec.py`（新，197 行） | 04「用到外面的東西」表每列一條，加：裝飾器那行與預設值、推導式／`with`／`:=`、字串裡的 `fn.block(`、`import os, re` 只寫 `import re`、叫 `json` 的工具、相對路徑從 `fn/` 算（經 `aos-exec`）、03 的說明書報錯在編譯時就報、產物自己跑 |
| `py/tests/test_fn_spec_more.py`（新，134 行） | hook（事件拼錯、不收條件的事件寫 `condition=`、`after_tool` 用 `fn.block`、沒給事件、參數不是一個、`handler=`、`async_`／`name=`、同名後蓋前、兩函數同名、工具與 hook 搶檔名）；互動（靜態／`--dynamic`、蓋掉包裡同名、`defs.drop`、`defs.load` 衍生重抽＋`base.pack(prefix=)` 改名、eca 版、舊 `fn/x.py` 不刪、建置腳本 `.compile(夾)`） |
| `py/tests/test_fn_spec_live.py`（新，152 行） | 實掛：抄 start-api、總機加一個劇本假腦 `fake-fn`、編譯、`agent_def check`、掛上去、`say`／`listen`、讀 history |
| `templates/agent-python/README.md` | 新一節「Functions as tools and hooks」；檔案表多 `fn/<名>.py`；`tools`、`hooks` 兩處各一行；「Linking tool packs」補一句（函數工具不在包裡、`fn` 從 `$AOS_HOME/lib` 讀） |
| 教學 06-1 | 6.2 末尾加一小節「工具或 hook 也能直接寫在 agent.py 裡」 |
| `knowledge/aos/tools_def.json` | `fn` 那節末尾加一段：同一個函數也能直接放進 agent.py 的 `tools=[…]`／`hooks=[…]` |

骨架 `agent.py` 不加函數範例（設計稿：範例放 README）。

## 驗收（實際做法與結果）

環境：`git archive` 抄 `e1209424b`（開工時的 HEAD，含第 0、1、2 刀）到 `~/.aos/scratch/aos-pylib-k3-1120/base`，複本裡 `install.py`；同一個 commit 再抄一份 `new`，只疊本線的檔（工作樹裡別線的改動不抄）、`install.py`。腳本一律先 unset 所有 `AOS_*`，`env -i PATH=<複本>/bin:/usr/bin:/bin HOME=… AOS_HOME=<複本>`。

**1. 沒用函數的 agent 逐 byte 相同**（做法照第 2 刀：骨架 12 種旗標＋八隻例子各 `--dry-run`、`--dry-run --dynamic`、`--compile`，bob 另編到別夾；例子是第 2 刀的 `cases/new.py`）：111 份 stdout／stderr／結束碼 **110 份相同**，不同的 1 份是 `--help`（`HELP` 多兩行，預期）。寫出的整棵樹 `diff -r` 只差抄進去的骨架 `README.md`（文件本身改了，編譯時夾裡已有、不寫）；權限清單相同；骨架重新編譯跟提交的那份無差。

**2. 實掛**（`py/tests/test_fn_spec_live.py`，在 `new` 複本跑）：抄 start-api、總機加劇本假腦 `fake-fn`（add 2+3 → ws_write 帶 secret → 結束句）。編譯出 `fn/add.py`、`fn/no_secrets.py`、`tools.json` 的 `{"path": "fn/add.py"}`、`hooks.json` 的 `{"event": "before_tool", "handler": "fn/no_secrets.py", "condition": "ws_write"}`；`agent_def check` 回 `{"problems": []}`；掛上去 `say`／`listen` 拿到結束句；history 的兩則 tool：第一則 `5`、第二則含 `the arguments mention a secret`；工作區沒有 `note.txt`。2 條 OK（25 秒）。

**3. 報錯情況**：`test_fn_spec.py` 15 條、`test_fn_spec_more.py` 8 條（加 live 2 條＝`py/tests` 多的 25 條）（內容見「動了哪些檔」）。

**4. 全套測試逐夾**（同一份 commit，base／new）：

| 夾 | base | new |
|---|---|---|
| `py/tests` | 665 OK（skip 1、expected failure 1） | 690 OK（同；多 25 條是本線三支新測試） |
| `templates/tests/tool-python`、`tools_def`、`defs`、`agent_def` | 5／12／27／30 OK | 同 |
| `py/tests/apps/*`（feedback、gdb 以外十六夾） | 全 OK | 同，每夾條數相同 |
| `py/tests/apps/feedback` | 18 error | 18 error（讀不到 `wf/`，已知） |
| `py/tests/apps/gdb` | 58，3 failure（test_13、14、15） | 58，1 failure（test_15） |
| `templates/tests/agent-fsm`、`reviewer` | 209 有 1 failure／1 有 1 failure | 209 OK／1 OK |
| `templates/tests` judge-llm、kits、image-move-check | 4 OK、8 OK、0 條 | 同 |

- 紅的幾條在 base 也紅、或只在 base 紅（gdb test_15 兩邊都是 `('wait', 'think')` 不在它列的轉移裡；當時同機有別線在跑 gdb live），跟編譯無關。
- 沒在 `~/repo/aos/proto8` 跑 `install.py`。

## 跟設計稿對不上、或沒寫到的（都選最小的做法）

1. **事件名檢查照舊**：設計稿 07c 寫「照 `Agent.events()` 驗事件在不在」。任務書定「維持今天 agent_spec 對 hooks 的既有行為」，所以事件名、`condition` 照舊由 `validate_entry` 驗（今天就是這張表、這句訊息）；`events()` 只拿來查 `fn.block` 能不能用（`block` 那格）。沒有新增「這隻身體不會發」的檢查。
2. **`fn.fail(` 不在編譯時掃**：設計稿說 `fn.block(`／`fn.fail(` 看語法樹。`fn.fail` 在工具與 hook 都合法，編譯時沒有要擋的；錯誤代號由抽出的 `fn/<名>.py --tooldef` 照第 1 刀的做法從那支檔掃，所以不掃。
3. **`agent.py` 沒定義也沒 import 的名字＝SpecBad**：04 的表沒寫這一列。執行時一定是 `NameError`，選報錯（`uses X, which agent.py neither defines nor imports at the top`）。`__file__`、`__name__` 放行（產物自己也有，`__file__` 就是 `fn/<名>.py`）。
4. **`import aos.…`（aos 套件本身）不算「旁邊的模組」**：骨架允許把 aos 套件抄在 `agent.py` 旁邊；產物照樣從 `$AOS_HOME/lib` 找得到 aos，所以不擋。編譯庫那幾支（`aos.py.agent.defs`、`aos.agent_spec*`、`aos.spec_unit`、`aos.spec_base`）照設計報「the compile library」。
5. **`from __future__ import …` 放在檔頭那句之後**：設計稿寫「放在產物最前面」。Python 允許 docstring 在 future 之前，放在 docstring 之後可以守「新檔第一行（跳過 shebang）寫一句話」，效果一樣。
6. **產物的 setup 幾行用 `_os`、`_sys`**：避免蓋掉函數自己 import 的 `os`／`sys`。`AOS_HOME` 沒設＝一行 `HomeMissing`、找不到 aos＝一行 `ModuleMissing`，stdout、stderr 各一行（同工具骨架），退 1。
7. **工具名不合 `TOOL_RE`（例如 `fn.tool(lambda …)` 的 `<lambda>`）**先報名字不對，不是「要是普通 def」。給了合法的 `name=` 的 lambda 才報後者。
8. **函數 hook 的名字**照 `hook_run.validate_name`（同手寫的格），檔名就是 hook 名；工具名照 `TOOL_RE`。
9. **`base.hooks["x"]` 拿到的拷貝帶著 `$fn`**：`{**base.hooks["x"], "timeout_ms": 1}` 寫回去仍是函數 hook，衍生那支照樣重抽程式。手寫 `$fn` 這個鍵（不是從函數來的）＝SpecBad。
10. **eca 版（不給 fsm）的路徑**：`fn/` 一律在定義夾，`tools.json`／`hooks.json` 那格寫「從那份檔所在的夾算」的相對路徑（`interfaces.json` 把它們放在子夾時仍對）。
11. **live 測試同時認兩種 start-api 長相**：同時在跑的 aos-kinit-tpl-1120 正在把總機從 `llms/def` 改成根上一列 `llm/`；測試看 `llm/kernel.json` 在不在決定怎麼起總機，兩種都接得上。

## 替使用者選的（他沒答或說「先不定」的照設計預設）

- **第 5 題「先不定」**：照設計「全部報錯」——函數只能用內建、自己的參數與變數、`fn`、`agent.py` 最上層 import 的模組；常數、函式、類別、別的 `@fn.tool` 函數、`defs`／`std`、旁邊的模組都報 SpecBad，訊息說出路（搬進函數裡）。之後要開放「同檔常數跟著抽」或「旁邊模組」只是在 `fn_spec._allowed` 多一個分支，不會弄壞已編的。
- **第 7 題「照今天工具的規矩」**：沒做任何切目錄；`aos-exec` 跑程式時 cwd 是程式所在的夾，就是 `fn/`。測試經 `aos-exec` 實跑確認；README、教學寫明「從 `fn/` 算，工作區用 `$AOS_WS`」。
- **第 10 題**：不是本線的事（aos-defnew-cp-1120），`agent_def` 沒碰，文件沒寫「函數工具會指回原夾」。
- **hook 線「掛到這隻 agent 不會發的事件：照舊不管」**：沒加檢查。

## 要頂層或別線補的字（本線不碰）

- `py/docs/01-分層等.md`（模組清單，不在本線領地）：`py/aos/fn_run.py` 那行後面加一行「`py/aos/fn_spec.py               編譯時把 agent.py 的 @fn.tool／@fn.hook 函數抽成定義夾的 fn/<名>.py（找外面的名字用 symtable）`」；`agent_spec` 那幾支若要列，加「`py/aos/agent_spec_hooks.py     agent_spec 的 hook 那塊（hooks=… 怎麼疊、驗、算出 hooks.json；收函數 hook）`」。
- `py/README.md`（shared-docs-1120 的檔）：寫 `aos.py.fn` 那段末尾可補「11-20 第 3 刀起，同一個函數也能直接放進 `agent.py` 的 `tools=[…]`／`hooks=[…]`，編譯時抽成定義夾的 `fn/<名>.py`（本體 `aos/fn_spec.py`；線 aos-pylib-k3-1120）」。
- `py/docs/04-共用模組.md`（shared-docs-1120 的檔）：表裡可加一列「`aos/fn_spec.py`｜編譯時抽函數成 `fn/<名>.py`｜`agent_spec_parts`、`agent_spec_hooks`、`agent_spec_agent`」。
- `wf/HANDOFF.md`：名字那段可加一句「函數工具／hook：`tools=[…, add]`、`hooks=[…, no_secrets]` 放 `@fn.tool`／`@fn.hook` 的函數，編譯時抽成 `fn/<名>.py`（第 3 刀）」。
- C-87 的 11-19 加註補一句（07c 第 5 刀列的，要使用者點頭）：「函數工具的程式在定義夾裡，但它 import 的 `fn` 從 `$AOS_HOME/lib` 讀」。

## 第 4、5 刀開工前要知道的

- 第 4 刀（extern 連結版）也改 `agent_spec_agent.py`／`agent_spec_load.py`：本線在 `_files` 尾巴加了 `programs` 那段、`_based` 加了兩處 `FN_KEY not in entry`；extern 指到 `fn/…` 的撞名檢查已有一行。
- 程式檔寫進子夾 `fn/` 用的是 `spec_base.write_files` 的子夾功能（第 0 刀留的），`Link` 還沒人用。
- 函數在 `defs.load` 時活在同一個行程（`fn_spec._FUNCS` 按「真路徑:行:qualname」記），衍生編譯時從底的原始碼重抽，所以底那支的 `agent.py` 一定要在（今天 `defs.load` 本來就要它在）。
- 每次問 hook 都起一支 Python（D10），README 寫了一句。
