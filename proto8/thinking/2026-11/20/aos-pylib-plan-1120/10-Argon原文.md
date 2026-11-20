Argon（agy -p，Gemini 4 Argon High，plan 模式）11-20 對本線設計稿與施工計劃的審查與提案原文，一字未改；逐點採不採在 [11-採納表](11-採納表.md)。

← [README](README.md)｜上一份：[09-原型](09-原型.md)｜下一份：[11-採納表](11-採納表.md)

送審的是 00～09（含 07b、07c、07d）當時的版本，約 10 萬位元組，放在只裝這一份提示檔的新空夾裡；送審後設計稿與計劃照採納表改過，所以原文裡引的句子有些已經不是現在的字。

## (A) 審查

---

### 一、「抽出來」的規則（03、04、07b、07c）

#### A1【一定要改】`from __future__ import annotations` 搬進產物時會引發 `SyntaxError`，且執行時不載入 `inspect` 會使型別註記全部變成字串
- **位置**：`03-函數當工具與hook.md`「抽出來的檔」「說明與參數」；`07b-施工計劃-第0到2刀.md`「第 1 刀 `fn` 與工具骨架」（`fn_mark.py` 與驗收）；`09-原型.md`「沒驗到的」。
- **問題**：
  1. `03` 規定抽出來的 `fn/add.py` 開頭依序是：檔頭 docstring、`# ---- setup: find the aos package ----`、`from aos.py import fn`，**之後**才放「（函數用到的 import，照原文搬）」。如果原始碼有 `from __future__ import annotations`，若把它當普通 import 放在 `from aos.py import fn` 後面，Python 會直接報 `SyntaxError: from __future__ imports must occur at the beginning of the file`；若因為函數本體沒直接引用名字 `__future__` 而不搬它，抽出的檔在舊版或特定型別寫法下語意又跟原檔不同。
  2. `07b` 第 1 刀規定 `fn_mark.py`「不載入 `inspect`」且驗收要過 `from __future__ import annotations`。但開啟 `__future__.annotations` 時，`fn.__annotations__` 裡的值不再是型別物件（`float`、`list[str]`），而是**純字串**（`'float'`、`'list[str]'`）。若 `fn_mark.py` 只比對 `{str: "string", int: "integer", ...}` 或 `typing.get_origin`，遇到字串註記會全部掉進 `SpecBad: parameter x needs a type`。
- **怎麼出事（操作順序）**：
  1. 在 `tool.py` 或 `agent.py` 第一行加上 `from __future__ import annotations`，並寫 `@fn.tool def tags(items: list[str], count: int = 1) -> list[str]: ...`。
  2. 執行 `python3 tool.py --tooldef` 或 `python3 agent.py --compile`：編譯期檢查 `fn.__annotations__["items"]` 拿到字串 `'list[str]'` 而非 `GenericAlias`，誤報 `SpecBad`；若硬搬 `from __future__` 到 `from aos.py import fn` 之後，執行 `fn/tags.py` 直接 `SyntaxError`。
- **怎麼改**：
  1. `fn_mark.py` 解析 `__annotations__` 時，統一把型別物件與字串都正規化（例如對型別取名稱或字串去空白後比對 `"str"`..`"dict"` 及 `"list[str]"`..`"list[dict]"`）。
  2. `fn_spec.py` 抽檔時，若原檔有 `from __future__ import annotations`，必須插在 `fn/<名>.py` 的檔頭 docstring 緊接下一行（所有 setup 程式碼之前）。

---

#### A2【一定要改】執行時從函數重算說明書（`--tooldef`）與「掃原始碼裡的 `fn.fail` 進 `errors`」在架構上互相矛盾
- **位置**：`03-函數當工具與hook.md`「抽出來的檔」「說明與參數」；`07b-施工計劃-第0到2刀.md`「第 1 刀 `fn` 與工具骨架」。
- **問題**：
  - `03` 規定兩件事：(1) 說明書不另存 JSON，`fn/add.py --tooldef`（及 `tool.py --tooldef`）**執行時當場從函數算出來**；(2) 錯誤代號要「掃抽出的那段原始碼裡的 `fn.fail("代號", …)`」放進說明書的 `errors`。
  - 但 `07b` 第 1 刀只有 `fn_mark.py` 與 `fn_run.py`（讀原始碼與 `ast` 的 `fn_spec.py` 要到第 3 刀才存在），且明定 `fn_mark.py`「不載入 `inspect`」，同時第 1 刀驗收卻要求 `fn.fail 的代號進 errors`。
  - 在不載入 `inspect`、也沒有 `fn_spec.py` 的第 1 刀，`fn_mark.py` 怎麼拿到函數的原始碼去掃 `fn.fail("代號", ...)`？（`09-原型.md` 實測表也完全沒測這一條。）若在 `fn_mark.py` 裡用 `co_filename` 讀檔跑 `ast.parse`，一來跟第 3 刀的 `fn_spec.py` 重複，二來若在 `@fn.tool` 裝飾當下就讀檔 parse AST，每次工具被呼叫（不只 `--tooldef`）都會多一次讀檔＋AST 解析。
- **怎麼出事（操作順序）**：
  1. 第 1 刀施工時，為了過 `test_fn.py` 的「`fn.fail` 的代號進 `errors`」，施工者在 `fn_mark.py` 裡自己開 `fn.__code__.co_filename` 跑 `ast.parse`（或用字串硬掃而誤把註解 `# fn.fail("X", ...)` 當真）。
  2. 若放在裝飾器執行時跑，每次 `aos-exec` 叫工具都多跑一次 `ast.parse`。
- **怎麼改**：
  - **最佳解**見提案 **B2**（直接拿掉「自動掃 `fn.fail`」，`errors=[...]` 一律明寫）。
  - 若堅持要自動掃：**只在 `--tooldef`／`--compile`／`--dry-run` 時**才讀 `fn.__code__.co_filename` 用 `ast` 掃 `fn.fail`（普通執行工具時絕不讀原始碼），且這段邏輯在第 1 刀就放進 `fn_mark.py`（第 3 刀 `fn_spec.py` 共用同一個 AST helper，不寫兩套）。

---

#### A3【一定要改】旁邊模組 `helpers.py` 在 `defs.load` 與 `--compile 別的夾` 時會直接爆 `ModuleNotFoundError` 或誤報 `SpecBad`
- **位置**：`04-函數-依賴與互動.md`「函數用到外面的東西」；`07c-施工計劃-第3到5刀.md`「第 3 刀 函數進 agent」（`fn_names.py`）。
- **問題**：
  1. `04` 教的寫法是：在定義夾放 `helpers.py`，`agent.py` **最上層**寫 `import helpers`。
  2. 當衍生定義 `child/agent.py` 呼叫 `base = defs.load("../base")` 時，使用者執行的是 `python3 child/agent.py --compile`。此時 Python 的 `sys.path[0]` 是 **`child/`**，根本沒有 `base/`！
  3. `defs.load("../base")` 一執行 `base/agent.py` 的第一行 `import helpers`，Python 當場拋出未捕捉的 **`ModuleNotFoundError: No module named 'helpers'`**（若 `child/` 剛好也有一支 `helpers.py`，`base/agent.py` 甚至會靜靜 import 到 `child/helpers.py`！），根本走不到第 3 刀 `fn_names.py` 預期的 `SpecBad`。
  4. 同理，就算沒有 `defs.load`，只要有人執行 `python3 defs/ann/agent.py --compile /tmp/out`（編譯到新資料夾），或用建置腳本 `build.py` 編譯，因為 `helpers.py` 在原始碼 `defs/ann/` 旁而不在目標夾 `/tmp/out` 裡，`fn_names.py` 檢查「檔在不在編譯進去的那一夾」就會報 `SpecBad`，導致含 `helpers.py` 的 `agent.py` 無法 `--compile` 到任何新資料夾。
- **怎麼出事（操作順序）**：
  1. `base/agent.py` 頂層寫 `import helpers`（`base/helpers.py` 存在），定義 `@fn.tool def f(): return helpers.x()`。
  2. `child/agent.py` 寫 `base = defs.load("../base")`，即使 `child` 立刻 `defs.drop("f")` 不用 `f`。
  3. 跑 `python3 child/agent.py --compile` → 在 `defs.load` 載入 `base/agent.py` 時直接崩潰 `ModuleNotFoundError: No module named 'helpers'`。
- **怎麼改**：
  1. `fn_names.py` 查某個非標準庫／非已安裝套件的本地模組 `m` 時，**不要靠 `sys.modules`** 去找，而是直接在「定義該函數的那支 `.py` 所在夾」與「目標定義夾 `folder`」找 `<模組名>.py`（或 `<模組名>/__init__.py`）。
  2. `defs.load("../base")` 載入 `base/agent.py` 的期間，若 `base/agent.py` 頂層有 `import helpers`，`defs.load` 需暫時把 `base/` 加進 `sys.path`（載完即移出，且不留快取在 `sys.modules["helpers"]` 以免污染 `child`），否則連 `defs.load` 都走不完。
  3. 更乾淨的做法見提案 **B3**。

---

#### A4【一定要改】抽出來的 `fn/<名>.py` 住在子夾 `fn/`，若照抄 `tool.py` 的「往上找 `aos` 套件」檔頭會差一層目錄，且盲砍 `sys.path[0]` 會在 `-P` 或匯入時誤刪路徑
- **位置**：`03-函數當工具與hook.md`「抽出來的檔」；`04-函數-依賴與互動.md`「函數用到外面的東西」；`07c-施工計劃-第3到5刀.md`「第 3 刀」；`07d` 意見 6。
- **問題**：
  1. **找套件路徑差一層**：`03` 說 `fn/add.py` 開頭 `# ---- setup: find the aos package ----` 是「同工具骨架那幾行」。我不確定目前 `tool.py` 骨架那幾行是只讀 `$AOS_HOME/lib` 還是有從 `__file__` 往上算 `..` 的 fallback；如果有從 `__file__` 往上算相對路徑，`fn/add.py` 住在定義夾的**子夾 `fn/`**（比 `agent.py`／`tool.py` 深一層），照抄 `tool.py` 的層數會算錯一層。
  2. **盲刪 `sys.path[0]`**：`07c` 與 `07d` 意見 6 寫「先拿掉 `sys.path[0]`（`fn/` 自己）」。若執行環境設了 `PYTHONSAFEPATH=1`（或 `python3 -P`），或測試程式碼直接 `import` 該檔，`sys.path[0]` 並不是 `fn/`，直接 `sys.path.pop(0)` 會把真正需要的路徑刪掉。
  3. **把定義夾排進 `sys.path` 最後一格的副作用**：定義夾裡有 `agent.py`。一旦把定義夾放進 `sys.path`，若函數或它用到的第三方套件嘗試 `import agent`，就會在工具執行時把定義夾裡的 `agent.py` 當模組載入並執行。
- **怎麼出事（操作順序）**：
  1. 在 `PYTHONSAFEPATH=1` 下執行 `fn/add.py`，`sys.path.pop(0)` 刪掉的不是 `fn/` 而是標準路徑或 `$AOS_HOME/lib`，導致 `ModuleNotFoundError: No module named 'aos'`。
- **怎麼改**：
  1. 移除 `fn/` 時必須比對路徑：
     ```python
     _fn_dir = os.path.dirname(os.path.abspath(__file__))
     if sys.path and os.path.abspath(sys.path[0]) == _fn_dir:
         sys.path.pop(0)
     ```
  2. 若 setup 區塊有從 `__file__` 往上找套件的邏輯，必須注意 `fn/add.py` 比 `agent.py` 多一層 `fn/`。

---

#### A5【一定要改】檔名硬綁 `fn/<Python 函數名>.py`，與 `@fn.tool(name=...)` 及 `base.pack(prefix=..., rename=...)` 衝突
- **位置**：`03-函數當工具與hook.md`「抽出來的檔」「說明與參數」；`04-函數-依賴與互動.md`「跟已有機制的互動」。
- **問題**：
  1. `03` 規定：抽出的檔名一律是 `fn/<Python 函數名>.py`（工具與 hook 同夾），而 `tools.json` 的鍵則優先用明寫的 `name=`；`04` 又規定：`base.pack(prefix=, rename=)` 改的是工具名，檔名仍是函數名；底與衍生各有一個同名函數＝`SpecBad`。
  2. 這會造成三個不合理的碰撞與漏洞：
     - **漏洞一（`base.pack(prefix=...)` 失效）**：底定義了 `@fn.tool def run(...): ...`，衍生用 `base.pack(prefix="base_")` 把它改名為 `"base_run"`，然後衍生自己定義 `@fn.tool def run(...): ...`（工具名 `"run"`）。兩支工具在 `tools.json` 名字完全不同（`"base_run"` 與 `"run"`），卻因為 Python 函數都叫 `run`，搶同一個 `fn/run.py` 而報 `SpecBad`！
     - **漏洞二（從不同模組匯入同名函數＋`name=` 失效）**：`from look_helpers import check as look_check`（`@fn.tool(name="look_check") def check...`）與 `from mail_helpers import check as mail_check`（`@fn.tool(name="mail_check") def check...`），兩個函數的 `__name__` 都是 `"check"`，明寫了 `name=` 卻還是因為搶 `fn/check.py` 報 `SpecBad`。
     - **漏洞三（不同函數名、相同 `name=`）**：`@fn.tool(name="add") def add_v1(...)` 與 `@fn.tool(name="add") def add_v2(...)`，Python 函數名不同（`fn/add_v1.py`、`fn/add_v2.py`），若只檢查「兩個函數同名＝`SpecBad`」，`tools.json` 的 `"add"` 鍵會被後者靜靜蓋掉，且留下孤兒檔 `fn/add_v1.py`。
- **怎麼出事（操作順序）**：
  1. `base/agent.py` 有 `@fn.tool def check(x: str) -> str: ...`。
  2. `child/agent.py` 寫 `base = defs.load("../base")`，並在 `tools=[base.pack(prefix="base_"), check]` 放進自己的 `@fn.tool def check(y: int) -> int: ...`。
  3. 跑 `python3 child/agent.py --compile` → 報 `SpecBad`（兩個函數 Python 名都叫 `check`），讓 `base.pack(prefix=...)` 的隔離命名功能形同虛設。
- **怎麼改**：
  - 見提案 **B4**：抽出來的檔名改用**最終登記名**（工具用最終工具名、hook 用最終 hook 名，或工具放 `fn/<工具名>.py`、hook 若撞名報 `SpecBad`），且「同名衝突」統一檢查最終登記名。

---

#### A6【一定要改】AST 抽原始碼與掃 `fn.block`／import 的三個靜默錯誤邊界
- **位置**：`03-函數當工具與hook.md`「抽出來的檔」；`04-函數-依賴與互動.md`「函數用到外面的東西」「編譯時怎麼知道事件」；`07c-施工計劃-第3到5刀.md`「第 3 刀」。
- **問題**：
  1. **怎麼切出函數原始碼**：`07c` 說「用 `__code__.co_filename`／`co_firstlineno` 加 `ast`，找到最上層那個 `def`…函數原文（裝飾器那行照搬）」。注意在 Python 3.8+，被裝飾函數的 `co_firstlineno` 是**第一個裝飾器那一行**（等於 `node.decorator_list[0].lineno`），不是 `def` 那一行（`node.lineno`）。若用 `node.lineno == co_firstlineno` 去比對 AST 節點，**永遠找不到有裝飾器的函數**！必須比對 `min([node.lineno] + [d.lineno for d in node.decorator_list]) == co_firstlineno`，且要確認該 `FunctionDef` 是 `ast.Module.body` 的直接子節點（`col_offset == 0`），否則寫在 `if True:` 裡的 `def` 抽出來會帶縮排而 `IndentationError`。
  2. **多名稱 import 與別名**：若 `agent.py` 頂層寫 `import os, defs` 或 `from mymod import good_fn, bad_const`，只搬用到的名字時不能「那一行 import 照原文搬」，否則會把沒用到甚至不該進產物的 `defs` 一併搬進 `fn/x.py`；應該對用到的別名重建單獨的 `import ...`／`from ... import ...`（或拒絕與 `defs` 同行的多名稱 import）。
  3. **`fn.block` 檢查**：`04` 說「函數的原始碼裡有 `fn.block(`，事件卻不能攔 → `SpecBad`」。必須查 AST 的 `ast.Call`（呼叫 `fn.block`），**不能用字串 `in` 掃原始碼**，否則 docstring 或註解裡寫到 `fn.block(` 就會誤判 `SpecBad`。
- **怎麼出事（操作順序）**：
  1. `fn_spec.py` 用 `node.lineno == fn.__code__.co_firstlineno` 找 `ast.FunctionDef`。
  2. 任何掛了 `@fn.tool` 的函數，`co_firstlineno` 是 `@fn.tool` 的行號，`node.lineno` 是 `def` 的行號（相差 1 行以上），直接找不到 AST 節點。
- **怎麼改**：
  1. 找 AST 節點時只在 `tree.body` 頂層找 `ast.FunctionDef`，行號取 `node.decorator_list[0].lineno`（無裝飾器才取 `node.lineno`），結尾取 `node.end_lineno`。
  2. `fn.block` 與 `fn.fail` 一律透過 AST `ast.Call` 節點檢查，不掃原始字串。

---

### 二、symlink 版 `extern`（05、07b、07c）

#### A7【一定要改】已存在連結檔時，「繞回連結自己」若用 `realpath`／`samefile` 比對連結位置，第二次重新編譯會誤報「連到自己」；反之若只比字串，兩跳循環連結會漏抓
- **位置**：`05-extern-symlink.md`「逐項」（目標不存在、目標是資料夾或繞回連結自己）；`07c-施工計劃-第3到5刀.md`「第 4 刀 extern 連結版」。
- **問題**：
  - 假設 `defs/ann/agent.py` 寫 `system=defs.extern("../shared/system.txt")`。
  - **第一次編譯**後，`defs/ann/system.txt` 已經是一個指向 `../shared/system.txt` 的 symlink。
  - **第二次重新編譯**時，如果程式用 `os.path.realpath("defs/ann/system.txt") == os.path.realpath("defs/ann/../shared/system.txt")`（或 `os.path.samefile`）來檢查「有沒有繞回連結自己」，因為舊的 `defs/ann/system.txt` 已經連過去了，兩邊 `realpath` 都會解到 `.../shared/system.txt` 而相等！導致**第二次重新編譯必敗**，誤報 `"system.txt" is the link itself`。
  - 反過來說，如果只比對字面字串 `target == "system.txt"`，那麼：
    1. `defs.extern("./system.txt")` 或 `defs.extern("../ann/system.txt")` 抓不到；
    2. 若 `../shared/system.txt` 本身是一個指回 `../ann/system.txt` 的 symlink，第一次編譯前因為 `ann/system.txt` 還是普通檔，`os.path.exists("../shared/system.txt")` 為 `True`，編譯器一旦把 `ann/system.txt` 換成 symlink，兩邊就形成無限循環（`ELOOP`），執行時靜靜沒有 system 文字！
- **怎麼出事（操作順序）**：
  1. `agent.py` 寫 `system=defs.extern("../shared/system.txt")`。
  2. 第一次 `python3 agent.py --compile` 成功，`system.txt` 變成 symlink。
  3. 不改任何東西，再跑一次 `python3 agent.py --compile` → 若對 `link_path` 做了 `realpath`/`samefile`，當場報 `SpecBad: "system.txt" is the link itself`。
- **怎麼改**：
  - 連結本身的位置**只對所在資料夾解 `realpath`，不對檔名解 `realpath`**：
    ```python
    link_logical = os.path.join(os.path.realpath(folder), link_filename)
    target_real = os.path.realpath(os.path.join(folder, target))
    if target_real == link_logical:
        raise SpecBad(...)  # 精準抓到指自己、./system.txt、../ann/system.txt 以及多跳指回自己的循環連結，且重編譯不會誤報
    ```
  - 接著再檢查 `os.path.exists(target_real)` 與 `not os.path.isdir(target_real)`。

---

#### A8【一定要改】`defs.load` 的 `extern` 相對路徑若在 `defs.load()` 當下換算，遇到 `--compile 別的夾` 或建置腳本會算錯基準夾；且底用「同夾連結」時會讓衍生指回底夾（違反 P2 / N-70）
- **位置**：`05-extern-symlink.md`「逐項」「哪些欄位能用」；`07c-施工計劃-第3到5刀.md`「第 4 刀」（`agent_spec_load.py`）；`08-待裁題.md` 第 1 題。
- **問題**：
  1. **換算時機錯了**：`07c` 寫「改 `py/aos/agent_spec_load.py:155-202`：底有 extern 時照樣交出，相對目標換算成從衍生那夾算」。但呼叫 `defs.load("../base")` 的當下，**還不知道最終要 `.compile(folder)` 到哪個資料夾**！如果使用者跑 `python3 child/agent.py --compile /tmp/out` 或由頂層建置腳本呼叫 `child.compile("build/defs/child")`，在 `defs.load` 時用 `child/agent.py` 的目錄去換算相對路徑，寫進 `/tmp/out/system.txt` 的相對連結就會斷掉。
  2. **同夾連結＋`defs.load` 違反 N-70 且 `fsm` 會炸**：`05`（第 558 行）與 `08` 第 1 題推薦用「同夾連結」`system=defs.extern("system.hand.txt")` 來取代昨天「手寫不蓋」的 `defs.extern("system.txt")`（`07c` 第 4 刀還把教學 06-2 的 `bob` 改成這樣）。一旦另一支 `child` 對 `bob` 做 `defs.load("../bob")`：
     - `system` 被換算成 `../bob/system.hand.txt`——衍生編出的定義夾**直接指回底那一夾 `bob/`**，違反 **P2（N-70：編出的是完整一份、不記上一層）**！
     - 若 `bob` 的 `fsm` 也用同夾連結 `fsm=defs.extern("fsm.hand.json")`，換算後變成 `"../bob/fsm.hand.json"`，因為含有 `/`，衍生編譯時直接踩中 `fsm`「目標不含 `/`」的禁令而 `SpecBad`！
- **怎麼出事（操作順序）**：
  1. `bob/agent.py` 照 `07c` 寫 `system=defs.extern("system.hand.txt")`。
  2. `child/agent.py` 寫 `base = defs.load("../bob")`，沿用 `base.system`。
  3. 編譯 `child` 後，`child/system.txt -> ../bob/system.hand.txt`（把 `bob` 刪掉或改動，`child` 就跟著壞，違反 N-70）；或者跑 `python3 child/agent.py --compile /tmp/test_child`，因為 `agent_spec_load.py` 用 `child/` 而非 `/tmp/test_child` 換算相對路徑，`/tmp/test_child/system.txt` 當場變斷鏈。
- **怎麼改**：
  1. `Extern` 物件只記 `(target, origin_folder)`，換算相對路徑必須延後到 `Agent._files(folder, ...)` 知道目標 `folder` 時才算。
  2. 若 `defs.load` 的底有 `extern`，且該 `extern` 指的是**底定義夾自己裡面的檔**（同夾手寫檔，如 `bob/system.hand.txt`），建議維持昨天的規矩：在 `defs.load` 取用該欄位時報 `SpecBad`（叫衍生自己給 `system=` 或在編譯時直接把當時的文字內容抄進衍生），不要產生指回底定義夾 `../bob/` 的 symlink。

---

#### A9【一定要改】`agent_def check` 遇到斷鏈時，若只在 `refs_check.py` 結尾「多叫一行」，前面的檢查會先把它當「缺檔」或開檔炸 `FileNotFoundError`
- **位置**：`05-extern-symlink.md`「逐項」；`07c-施工計劃-第3到5刀.md`「第 4 刀」（`links_check.py`、`refs_check.py`）。
- **問題**：
  - 在 Python 裡，對一個**斷掉的 symlink** 呼叫 `os.path.exists(p)` 或 `os.path.isfile(p)`，回傳的是 **`False`**（只有 `os.path.islink(p)` 與 `os.path.lexists(p)` 是 `True`）；對它 `open(p)` 會拋 `FileNotFoundError`。
  - `07c` 規劃在 `refs_check.py:299-304` 結尾「多叫一行 `links_check.py`」，驗收要求「目標被手刪時，`agent_def check` 報**一條** problem」。
  - 但如果 `tools.json`、`fsm.json`、`hooks.json` 或 `system.txt` 是斷鏈，`refs_check.py` 前面原本的檢查看到 `os.path.exists(p) == False` 就會先報一條「檔案不存在」（或 `open()` 拋 `FileNotFoundError`），最後 `links_check.py` 再報一條「斷掉的連結」，變成報**兩條**互相矛盾的 problem 或直接崩潰。
- **怎麼出事（操作順序）**：
  1. `system=defs.extern("../shared/system.txt")`（或 `tools=defs.extern("../shared/tools.json")`）編譯成功。
  2. 手刪 `../shared/system.txt`（或 `../shared/tools.json`）。
  3. 跑 `agent_def check` → 原本的檢查先報 `system.txt` missing，接著 `links_check` 又報 `system.txt` broken symlink，共兩條 problem，驗收不過。
- **怎麼改**：
  - 斷鏈檢查必須在 `refs_check.py`／`catalog.py` 檢查檔案存在與讀檔**之前**先做（或把存在檢查統一改為：先查 `os.path.islink(p) and not os.path.exists(p)`，若是斷鏈就記一條 broken link problem 並跳過後續對該檔的「缺檔」與「開檔讀內容」檢查）。

---

#### A10【一定要改】`spec_base.py` 寫暫存連結＋改名的殘留與失敗清理細節
- **位置**：`05-extern-symlink.md`「逐項」（寫檔）；`07b-施工計劃-第0到2刀.md`「第 0 刀 共用的底」。
- **問題**：
  1. 建立普通暫存檔可以用 `NamedTemporaryFile`，但 `os.symlink(target, tmp_path)` 若 `tmp_path` 已存在（包含**斷掉的舊暫存連結**，此時 `os.path.exists(tmp_path)` 是 `False`，但 `os.path.lexists(tmp_path)` 是 `True`！）會拋 `FileExistsError`。
  2. `07b` 第 0 刀驗收要求：「寫到一半失敗夾裡不變也不留暫存檔」。清理暫存檔時若用 `if os.path.exists(tmp): os.remove(tmp)`，當 `tmp` 是指向不存在目標的相對連結時，`os.path.exists(tmp)` 為 `False`，**暫存連結就會沒被刪掉而留在夾裡**！
  3. 當 `write_files` 要寫 `fn/add.py` 時，若 `fn/` 原本不存在，先 `os.makedirs("fn")` 後寫檔到一半失敗，空資料夾 `fn/` 也會留下來。
- **怎麼出事（操作順序）**：
  1. `test_spec_base.py` 測試「寫入一個連結＋一個後續會失敗的項目」以驗證「寫到一半失敗夾裡不變也不留暫存檔」。
  2. 若該暫存連結是斷鏈或 cleanup 用了 `os.path.exists`，清理後夾裡仍殘留暫存 symlink（`os.listdir(folder)` 多出一個檔），測試失敗。
- **怎麼改**：
  1. 暫存連結檔名帶 `os.getpid()` 與計數／隨機碼（或建之前先 `if os.path.lexists(tmp): os.unlink(tmp)`）。
  2. `write_files` 的 `try...except` 失敗清理一律用 `os.path.lexists(tmp)` 判斷並 `os.unlink(tmp)`；若本次新建了子夾（如 `fn/`）且失敗時子夾為空，一併 `os.rmdir`。

---

#### A11【建議】`hooks.json` 用 `extern` 指到夾外時的 handler 相對路徑起算點沒列，且 `fsm` 禁 `/` 會誤殺 `./xxx.json`
- **位置**：`05-extern-symlink.md`「哪些欄位能用」；`07c-施工計劃-第3到5刀.md`「第 4 刀 第一步：實測」。
- **問題**：
  1. `05` 指出 `tools.json` 連到夾外時，裡面的相對路徑「從目標那一夾算，不是從定義夾」；但把 `hooks` 跟 `system`、`llm` 歸在同一列說「讀的程式都是普通開檔，會跟著連結走」。問題是 `hooks.json` 裡面也有相對路徑 `"handler": "fn/no_secrets.py"`！我不確定 `hook_run` 找 `handler` 相對路徑時是從「定義夾」算還是對 `hooks.json` 解 `realpath` 後從「目標那一夾」算，`05` 與 `07c` 的實測清單都漏了 `hooks.json`。
  2. `05` 寫 `fsm`「只能指同一夾裡的檔（目標不含 `/`）」。若有人寫 `defs.extern("./fsm.hand.json")`，雖然在同一夾卻因含 `/` 被誤殺；另外若有人在 `tools=[defs.extern(...)]` 或 `hooks=[defs.extern(...)]` 把 `extern` 包在 list 裡（因為這兩欄平常收 list），需要明確的 `SpecBad` 提示「extern 要直接給 `tools=defs.extern(...)`，不要包在 `[...]` 裡」。
- **怎麼改**：
  1. 第 4 刀第一步實測加上 `hooks.json` 連到夾外且帶相對 `handler` 的情況，並在 `05` 表格寫明 `hooks` 的相對路徑起算點。
  2. `fsm` 若維持同夾限制，判斷條件改為 `os.path.dirname(os.path.normpath(target)) in ("", ".")` 且不含 `..`，而非「字串不含 `/`」。

---

### 三、物件化（01、02、07b）

#### A12【一定要改】`物件.dry_run(folder=None)` 預設不給 `folder`，碰到 `extern` 或旁邊模組 `helpers.py` 時無法驗證甚至會崩潰
- **位置**：`01-程式庫長相.md`「具體是哪些類別與函式」；`02-去留對照與kernel接口.md`「kernel 以後怎麼接上」；`04`、`05`。
- **問題**：
  - `01` 與 `02` 都定義 `物件.dry_run(folder=None, link="static")`，並承諾「算出 `{檔名: 內容}`，**全部驗完才回**，不寫」「寫錯怎麼報照舊：宣告時不丟，`.dry_run()`／`.compile()` 才丟 `SpecBad`」。
  - 但是以下兩項編譯期驗證**必須知道目標定義夾 `folder` 是哪一夾**才能算：
    1. `05` 的 `defs.extern("../shared/system.txt")`：要從**編譯進去的那一夾**起算，檢查目標存不存在、是不是資料夾、有沒有繞回自己（錯誤訊息還要印 `(seen from 夾)`），以及 `defs.load` 過來的相對路徑要換算成從 `folder` 算！
    2. `04` 的旁邊模組 `import helpers`：要查 `helpers.py` 在不在**編譯進去的那一夾**！
  - 當使用者在腳本或測試裡照 `01` 呼叫 `agent.dry_run()`（沒傳 `folder`，所以 `folder is None`）時，`os.path.join(folder, target)` 會直接拋 `TypeError: expected str, bytes or os.PathLike object, not NoneType`；若因為 `folder is None` 就跳過檢查，又違反「`.dry_run()` 全部驗完才回，等於 `.compile()` 寫的內容」（`07b` 第 2 刀驗收明定：`.dry_run()` 等於 `.compile()` 寫的內容）。
- **怎麼出事（操作順序）**：
  1. 寫 `a = defs.Agent(..., system=defs.extern("../shared/system.txt"), ...)`。
  2. 在測試或腳本呼叫 `a.dry_run()`（不傳 `folder`）→ `folder` 為 `None`，直接 `TypeError` 或無法換算 `defs.load` 的相對連結。
- **怎麼改**：
  - 方案一：`Agent` 在建構時記下宣告它那支腳本所在的資料夾（由呼叫端 stack frame 的 `co_filename` 取得），當 `dry_run(folder=None)` 沒傳 `folder` 時，預設以腳本所在夾當 `folder`。
  - 方案二：若 `folder=None` 時不猜夾，則在用到相對路徑的 `extern`、衍生相對 `extern` 或本地 `helpers` 時，若 `folder is None` 必須明確報 `SpecBad("dry_run requires folder= when extern or local modules are used")`。方案一更符合直覺且與 `defs.main` 一致。

---

#### A13【一定要改】`defs.load` 改回傳「一份新的 `Agent`」後，與 `base.pack(...)` 方法、欄位原地修改、以及來源路徑追蹤的規格有洞
- **位置**：`01-程式庫長相.md`「具體是哪些類別與函式」；`02-去留對照與kernel接口.md`「逐項」；`07b-施工計劃-第0到2刀.md`「第 2 刀 Agent 物件」（`agent_spec_load.py`）。
- **問題**：
  1. `02` 與 `07b` 寫：`defs.load("../reviewer")`「回那支 `agent.py` 交給 `defs.main` 的那個物件（一份新的）」「`Base`（:139 起）改成交回一份新的 `Agent`；`tools(prefix=…)` 改名 `pack(...)`」。
  2. 這產生三個沒交代清楚的互動：
     - **洞一**：如果 `defs.load` 回傳的就是 `Agent`（或 `Base(Agent)`），那普通的 `defs.Agent(...)` 有沒有 `.pack(prefix=, rename=, exclude=)` 方法？如果只有 `Base` 有、或者 `Agent` 也有，把一隻 `Agent` 的 `.pack(...)` 放進另一隻 `Agent(tools=[other_agent.pack(prefix="x_")])`（在同一支建置腳本裡直接拿另一個 `Agent` 物件當底，不經 `defs.load` 讀檔）能不能通？
     - **洞二**：既然 `base = defs.load("../reviewer")` 回傳的是一個 `Agent` 物件，使用者很自然會寫：
       ```python
       base = defs.load("../reviewer")
       base.tools = [base.tools, my_tool]
       defs.main(base)
       ```
       請問直接改 `base` 的屬性再把 `base` 交給 `defs.main(base)`（或 `base.compile(夾)`）合不合法？如果合法，`base` 內部若記著「我是從 `../reviewer` 載入的」以便換算相對路徑，那使用者新塞進 `base.tools` 的 `my_tool`（相對路徑應從衍生夾算）就會被誤當成從 `../reviewer` 算！
     - **洞三**：一支腳本編很多個時（`01` 第 207 行），若共用同一個 `cells = defs.fsm(...)` 或同一個 `tools_list` 傳給多個 `defs.Agent(...)`，`_files()` 若原地修改傳入的 list／dict，編第二隻時就會被第一隻污染。
- **怎麼出事（操作順序）**：
  1. 使用者寫 `base = defs.load("../reviewer")`，直接改 `base.description = "New"`、`base.system = defs.extern("my_sys.txt")`，然後 `defs.main(base)`。
  2. 若 `base` 不是真的 `Agent`（而是 `Base`），`defs.main(base)` 會報 `SpecBad`（不是 `Agent` 物件）；若 `base` 是 `Agent` 且帶著 `origin="../reviewer"`，`my_sys.txt` 會被當成 `../reviewer/my_sys.txt`！
- **怎麼改**：
  1. **來源路徑（`origin_dir`）必須綁在 `defs.load` 拆出來的個別項目上**（例如 `base.tools`、`base.system`、`base.fsm`、`base.hooks` 裡的相對路徑項目在 `defs.load` 完成時就封裝好各自的 `origin_dir`），而不是綁在 `Agent` 物件本身。這樣不管使用者是寫 `defs.Agent(..., tools=[base.tools, my_tool])` 還是直接改 `base.tools` 再 `defs.main(base)`，舊項目的相對路徑從 `../reviewer` 算、新項目從當前夾算，兩條路都通！
  2. `Agent._files()` 絕不原地修改 `self.tools`、`self.llm`、`self.hooks`、`self.fsm`。

---

#### A14【一定要改】`defs.fsm(...)` 的驗證時機與 `Unit` 介面不一致
- **位置**：`01-程式庫長相.md`「一張狀態機單獨編譯」「具體是哪些類別與函式」；`02-去留對照與kernel接口.md`「loop 與 fsm 在庫裡的地位」「kernel 以後怎麼接上」；`07b-施工計劃-第0到2刀.md`「第 2 刀」。
- **問題**：
  1. `01` 說：「寫錯怎麼報照舊：宣告時不丟，`.dry_run()`／`.compile()` 才丟 `SpecBad`」，`07b` 第 2 刀驗收也明寫：「宣告錯到 `.dry_run()` 才丟」。但 `02` 說：「今天：`defs.fsm(...)` 回驗好的表」，`07b` 說：`class Fsm(dict)（照 parts.Hooks，多 .compile(夾, name="fsm.json")、.dry_run()）`。如果 `defs.fsm(...)` 在呼叫當下就驗證並丟 `SpecBad`，就違反「宣告錯到 `.dry_run()` 才丟」；反之如果延後到 `.dry_run()` 才驗，那 `Fsm(dict)` 在宣告當下還沒驗過，若放進 `defs.fsm(base.fsm, [...], drop=[...])` 要怎麼合併？
  2. `01` 表格寫 `defs.fsm` 多了 `.compile(夾, name="fsm.json")`、`.dry_run()`（漏了 `name="fsm.json"` 參數），而 `02` 定義共用底座 `Unit.compile(self, folder, link="static")` 與 `Unit.dry_run(self, folder=None, link="static")`。如果有人寫一支獨立的 `fsm.py`，最後一行寫 `defs.main(cells)`，`Unit` 的旗標殼呼叫 `obj.compile(folder, link=link)` 時，`Fsm.compile(folder, name="fsm.json")` 沒收 `link` 參數就會爆 `TypeError`。
- **怎麼出事（操作順序）**：
  1. 測試寫 `bad_fsm = defs.fsm("missing", [])` 預期宣告時不丟、`Agent(..., fsm=bad_fsm).dry_run()` 才丟 `SpecBad`（照 `07b` 驗收「宣告錯到 `.dry_run()` 才丟」），結果在 `defs.fsm(...)` 那一行就丟了；或者在 `fsm.py` 呼叫 `defs.main(cells)`，執行 `python3 fsm.py --compile` 因 `link=` 參數不合爆 `TypeError`。
- **怎麼改**：
  1. 明確規定：`defs.Agent(...)` 建構時只收不驗；至於 `defs.fsm(...)`／`defs.state(...)` 這類組件建構函式，若維持呼叫當下就驗（或統一延後到 `_files()` 才驗），在 `01` 與 `07b` 驗收條文要寫清楚是「`defs.Agent(...)` 宣告錯到 `.dry_run()` 才丟」，避免驗收標準自相矛盾。
  2. `Fsm.dry_run(self, folder=None, name="fsm.json", link="static")` 與 `Fsm.compile(self, folder, name="fsm.json", link="static")` 都補齊相容 `Unit` 的簽名。

---

#### A15【建議】`defs.main` 被叫兩次的檢查在正常命令列執行時抓不到第二次呼叫
- **位置**：`07b-施工計劃-第0到2刀.md`「第 2 刀 驗收」（`defs.main` 收到的不是物件或被叫兩次＝`SpecBad`）。
- **問題**：
  - 當使用者在同一個 `agent.py` 寫了兩行 `defs.main(ann)` 與 `defs.main(bob)` 時：
    - 被 `defs.load` 載入時，`defs.main` 不會 `sys.exit`，所以會執行到第二行 `defs.main(bob)` 並抓到「被叫兩次」。
    - 但直接跑 `python3 agent.py --compile` 時，如果第一行 `defs.main(ann)` 寫完檔就直接 `sys.exit(0)`，程式根本不會執行到第二行 `defs.main(bob)`！結果直接跑 `--compile` 時靜靜只編了 `ann`、漏掉 `bob`，完全沒報錯。
- **怎麼改**：
  - `defs.main(obj)` 在正常命令列執行時**不要在成功時呼叫 `sys.exit(0)`**（只在報錯或 `--help` 時 `sys.exit`），而是讓函式正常 return，並在模組級變數記 `_main_called = True`。這樣若同一支腳本後面還有第二句 `defs.main(bob)`，立刻會在第二次呼叫時丟出 `SpecBad("defs.main called more than once; use .compile(folder) in a build script")` 并 `sys.exit(1)`。

---

### 四、施工計劃（07、07b、07c、07d）

#### A16【一定要改】第 1 刀與第 2 刀刪掉舊介面時沒做全域 grep，把全域 grep 延到第 5 刀會打破「每一刀做完 repo 都是一致、能用的狀態」
- **位置**：`07-施工計劃.md`「先講結論」「共通的驗收做法與硬規則」；`07b-施工計劃-第0到2刀.md`「第 1 刀」「第 2 刀」；`07c-施工計劃-第3到5刀.md`「第 5 刀 文件收尾」。
- **問題**：
  - `07` 硬規則明定：「每一刀做完 repo 都是一致、能用的狀態，後面不做也不會留半套」「**改欄位、改名、改訊息要全域 grep，同一個 commit 改完**（程式、測試、README、教學、知識庫）」。
  - 然而：
    1. 第 1 刀刪掉了 `tool_spec.main()`，第 2 刀刪掉了 `defs.compile()`、`defs.write()`、大寫常數版 `defs.main(DESCRIPTION, ...)` 及 `base.TOOLS`／`base.tools(...)`。
    2. 只有第 0 刀的驗收有寫 `git grep`，**第 1 刀與第 2 刀的驗收完全沒有 `git grep` 舊介面名稱**，而是把 `git grep` 放到了最後的**第 5 刀**！
    3. 更危險的是，第 5 刀的 grep 竟然寫「**排除 `proto8/thinking/`、`proto8/lib/`**」！我不確定 `proto8/lib/`（或 `proto8/py/tools/`、`proto8/templates/`）裡有沒有現成工具或測試直接 import `tool_spec as ts` 並呼叫 `ts.main(...)` 或 `defs.compile(...)`；如果有，第 1 刀一刪 `tool_spec.main()`，那些工具在第 1 刀就壞了，而且第 5 刀排除了 `proto8/lib/` 還永遠不會發現！
- **怎麼出事（操作順序）**：
  1. 第 1 刀照 `07b` 拿掉 `tool_spec.py` 的 `main()`，只跑 `07` 列的幾支測試，沒跑全域 grep。
  2. repo 裡（特別是被第 5 刀排除的 `proto8/lib/` 或其他工具／測試／文件）若有地方叫 `ts.main(...)`，從第 1 刀起就直接壞掉。
- **怎麼改**：
  1. 把第 5 刀的 `git grep` **拆回第 1、2、4 刀各自的驗收條件**裡：
     - 第 1 刀驗收必跑：`git grep 'ts\.main(\|tool_spec\.main(' proto8/`（**不可排除 `proto8/lib/` 的程式碼**，只排除歷史紀錄 `proto8/thinking/`）。
     - 第 2 刀驗收必跑：`git grep 'defs\.compile(\|defs\.write(\|defs\.main(DESCRIPTION\|base\.TOOLS\|base\.HOOKS\|base\.FSM\|base\.SYSTEM\|base\.LLM\|base\.tools(' proto8/`。
     - 第 4 刀驗收必跑：`git grep 'extern("system\.txt")' proto8/`。
  2. 如此一來，第 1～4 刀每一刀交件時就已經 grep 乾淨，**第 5 刀甚至可以直接砍掉**（只留 C-87 那一句條文加註跟著第 3 刀問使用者即可）。

---

#### A17【一定要改】第 3 刀單檔行數與複雜度被低估（`fn_names.py` 手寫 AST 作用域分析極易漏邊角）
- **位置**：`07c-施工計劃-第3到5刀.md`「第 3 刀 函數進 agent（抽出來）」。
- **問題**：
  - `07c` 預估 `fn_names.py` 約 130 行，用來「算函數（含裝飾器那行與預設值）用到哪些外面的名字，照 04 的表分成沒事／搬 import／`SpecBad`」。
  - 在 Python 裡若用 `ast.NodeVisitor` 手寫變數作用域分析（區分區域變數與外部自由變數），有大量語法節點會綁定區域名字：一般賦值、序列解包 `a, (b, c) = ...`、`for` 目標、`with ... as v:`、`except E as e:`、串列／字典／集合／產生器推導式 `[x for y in z for x in y]`（注意第一個 `z` 是外部作用域，後面的 `y`、`x` 是推導式內部區域作用域！）、海象運算子 `(n := len(a))`、巢狀 `def`／`class`、函式內部 `import`。
  - 手寫 AST visitor 要把上述作用域全部算對，不但容易超過預估行數，更極易在推導式或 `with/except` 變數上誤把區域變數當成「未定義的外部名字」或漏掉真正的外部名字（`09-原型.md` 的 `extract.py` 只有 100 行，顯然沒有處理完整 Python 作用域語法）。
- **怎麼出事（操作順序）**：
  1. 使用者在 `@fn.tool` 函數裡寫 `return [item.strip() for item in text.splitlines() if (n := len(item)) > 0]`，而 `agent.py` 頂層剛好也有一個無關變數叫 `item` 或 `n`。
  2. 手寫的簡易 AST visitor 沒分出推導式與 `:=` 的區域作用域，看到 `item` 或 `n` 在 `agent.py` 頂層有同名變數，就誤報 `SpecBad: function uses item from agent.py`！
- **怎麼改**：
  - 見提案 **B1**：直接用 Python 標準庫內建的 **`symtable`** 模組算作用域（CPython 編譯器自己的符號表，10 行搞定且 100% 精準）。

---

### 五、「要帶給使用者的衝突」與「待裁題」（06、08）

#### A18【一定要改】`agent_def new` 把新定義夾的 `tools.json` 改指回「舊定義夾的 `fn/add.py`」，違反 P1／P3／N-70，不應只寫進文件放著不管
- **位置**：`04-函數-依賴與互動.md`「跟已有機制的互動」（`agent_def new` 抄一份定義）；`07c-施工計劃-第3到5刀.md`「第 3 刀 文件」。
- **問題**：
  - `04` 發現：`agent_def new` 抄一份定義夾時，`fn/add.py` 已經跟著整夾抄進新夾了，但 `agent_def new` 的 `rebase_tools` 會把新夾 `tools.json` 裡的 `"path": "fn/add.py"` 改寫成**指回舊夾**（例如 `"../orig/fn/add.py"`），導致新夾自己的 `fn/add.py` 沒人用，而 `hooks.json` 的 `"handler": "fn/no_secrets.py"` 卻指新夾自己那份！
  - `04` 卻決定：「原夾還在就都能跑；本計劃不動 `agent_def`，只寫進文件」。
  - 這有三個嚴重後果：
    1. 使用者照 P1（「產物誰都能手改」）去手改新夾的 `fn/add.py`，執行時跑的卻還是舊夾的 `fn/add.py`（完全靜默跑錯程式！）。
    2. 刪掉舊夾後，新夾的工具就壞了，但 hook 卻還能跑（同一夾的 `fn/` 行為分裂）。
    3. `rebase_tools` 的本意是當工具路徑指到**定義夾外面**時，抄到新位置後要換算相對路徑；對於指在**定義夾自己裡面**（已被 `copytree` 一併抄過去）的相對路徑，本來就不該改指回舊夾！
- **怎麼出事（操作順序）**：
  1. `agent_def new` 從 `defs/ann` 抄出 `defs/ann2`。
  2. 使用者手改 `defs/ann2/fn/add.py`（或刪掉 `defs/ann`）。
  3. 跑 `ann2` 時叫 `add`，執行的卻還是 `defs/ann/fn/add.py`（或報找不到檔）。
- **怎麼改**：
  - 見提案 **B5**：在第 3 刀順手改 `agent_def` 的 `rebase_tools`（約 3 行：若工具相對路徑解析後位於原定義夾內部，就保持原相對路徑不改寫），或將此列給使用者確認。

---

#### A19【建議】`08-待裁題.md` 有多題其實已由 P5／P6 定案或屬於別條線，不該拿來擋住第 1～4 刀
- **位置**：`06-對照與衝突.md`；`07-施工計劃.md`「總表」；`08-待裁題.md` 第 1～9 題。
- **問題**：
  1. **不必再問且不該擋刀的題**：
     - **第 2 題（`compile` 字義）**：使用者今天選的選項（P6）原文就寫明「編譯＝`物件.compile(夾)`」，且與 `--compile` 旗標一致。再問一次「要不要反過來讓 `.compile()` 只算不寫」是多餘的。
     - **第 3 題（欄位大小寫）**：P5 明定「proto8 一律當沒有舊版」，`defs.Agent(description, system=..., tools=...)` 既已用小寫關鍵字，屬性自然就是小寫 `base.tools`。
     - **第 5 題（同檔常數與函式要不要跟著抽）**：使用者今天選「抽出來」時（P6 / `00` 第 42 行），選項說明已經寫明「函數不能用 `agent.py` 裡的常數和別的函式（編譯時就報錯）」。已經裁過的事不必重問。
     - **第 8 題（`loop.json`）與第 9 題（kernel 的 `defs`）**：`08` 自己都標了「不擋本線任何一刀」，且已有 `aos-init-kernel-1120` 等專線，混進本線只會分散注意力。
  2. **真正該問但漏列或沒講透的衝突**：
     - **`defs.load` 遇到底的「同夾 `extern`」時要不要指回底夾**（見 **A8**）：`08` 第 1 題推薦用同夾連結 `defs.extern("system.hand.txt")` 代替「手寫不蓋」，卻沒告訴使用者「一旦這樣做，照 05 的規則，`defs.load` 衍生那支會產生指回底夾 `../bob/system.hand.txt` 的連結（違反 N-70）」。
     - **`agent_def new` 的 `rebase_tools` 要不要對夾內的 `fn/add.py` 不改寫**（見 **A18**）。
- **怎麼改**：
  - 見提案 **B6**：把第 2、3、4、5 題改為「照今日裁定直接定案（列在摘要告知即可）」，解除第 1～3 刀的封鎖；待裁題只留真正未決的 3 題。

---

## (B) 提案

以下提案均嚴格遵守 **P1～P8**，目標是砍掉多餘的程式碼與規則、消除靜默出錯的邊界。

---

#### B1：用 Python 標準庫內建的 `symtable` 取代手寫 130 行 AST 作用域分析，並將 `fn_spec.py` 與 `fn_names.py` 合併成一支檔
- **為什麼**：手寫 AST visitor 來算 Python 的自由變數（排除推導式、`with/except as`、海象運算子 `:=`、巢狀解包等區域變數）既囉嗦又容易有 bug（見 **A17**）。Python 標準庫內建的 **`symtable`** 是 CPython 編譯器自己的符號表（C 實作、零額外啟動成本）。
- **怎麼做**：
  1. 對檔案原始碼呼叫 `st = symtable.symtable(src, filename, "exec")`，找到該函數的 `Function` 子表 `fn_st`。
  2. 在 `fn_st.get_symbols()` 中，凡是 `s.is_global()` 或 `s.is_free()` 的名字，加上裝飾器與參數預設值 AST 裡的 `ast.Name(ctx=Load)`，就是該函數用到的全部外部名字！一行都不必自己算區域變數綁定規則。
  3. 再對照 `ast.Module.body` 頂層的 `Import`／`ImportFrom`，立刻能分成「內建／`fn`／頂層 import／同檔禁用名字（`SpecBad`）」。
  4. 這能把 `fn_names.py`（原估 130 行）縮減到約 40 行，直接與 `fn_spec.py` 合為單一檔 `py/aos/fn_spec.py`（合計約 180 行，遠低於 P8 的 300 行上限），少一支模組、少一套 AST 作用域 bug。

---

#### B2：砍掉「自動掃原始碼裡的 `fn.fail("代號", ...)` 進 `errors`」，錯誤代號一律由 `@fn.tool(errors=[...])` 明寫
- **為什麼**：
  1. **P6** 只要求「**說明與參數**『自動抽與明寫都收，明寫的贏』」，並沒有要求自動掃函數本體裡的 `fn.fail` 呼叫來湊 `errors` 清單。
  2. 為了自動掃 `fn.fail`，執行時跑 `tool.py --tooldef` 或 `fn/add.py --tooldef` 的 `fn_mark.py` 被迫要去找原始碼檔並跑 `ast.parse`（見 **A2**），打破了「`fn_mark.py` 只看記憶體裡的函數物件（`__doc__`、`__annotations__`、`__code__`、`__defaults__`），只在編譯抽檔時才由 `fn_spec.py` 讀原始碼與 AST」的乾淨分界。
- **怎麼做**：
  - 拿掉 `03` 表格裡「掃抽出的那段原始碼裡的 `fn.fail("代號", …)`」這一條；需要宣告 `errors` 時就像 `meta=` 一樣明寫 `@fn.tool(errors=["TooBig"])`（預設 `[]`）。
  - 好處：`fn_mark.py` 100% 不碰檔案系統、不 import `ast`、不 import `inspect`，執行時算說明書又快又單純。

---

#### B3：本地輔助模組（`helpers.py`）在編譯時跟著抄進目標定義夾的 `fn/`（或乾脆不開放本地模組特例），解決 `defs.load` 與 `--compile 別的夾` 的死結
- **為什麼**：`04` 目前的設計要求「使用者自己手動把 `helpers.py` 放進目標定義夾，編譯器只檢查它在不在目標夾」，結果造成 `defs.load("../base")` 直接爆 `ModuleNotFoundError`、`python3 agent.py --compile /tmp/new_dir` 直接爆 `SpecBad`（見 **A3**）。
- **兩種更乾淨的替代做法（二選一，都守 P1、P2/N-70、P6）**：
  - **做法甲（最推薦：編譯器自動把本地 `helpers.py` 抄進 `fn/`）**：
    - `helpers.py` 是放在原始碼 `agent.py` 旁邊的輔助模組。
    - 編譯時，若函數 `import helpers`，且 `helpers.py` 在定義該函數的那支 `agent.py` 所在夾裡，編譯器就把 `helpers.py` 當作編譯產物一併寫進目標定義夾的 **`fn/helpers.py`**（同時檢查 `helpers.py` 不能 import `defs` 或原夾的 `agent.py`）！
    - 這樣一來：(1) `fn/add.py` 與 `fn/helpers.py` 同在 `fn/`（或定義夾），甚至不必動 `sys.path` 把定義夾排進去找；(2) `python3 agent.py --compile /tmp/new_dir` 一次就編出完整可跑的新夾；(3) `defs.load("../base")` 衍生編譯時，自動把 `base/helpers.py` 抄一份進衍生夾的 `fn/helpers.py`，完全符合 **P1（C 與 .o，重新編譯整份蓋）** 與 **P2（N-70：編出的是完整一份、不指回底夾）**！
  - **做法乙（極簡砍法：只准 import 標準庫與已安裝套件）**：
    - 嚴格照 P6 選項原文，函數只能 import 標準庫與環境已安裝的套件（含 `$AOS_HOME/lib`）；拿掉「旁邊放 `helpers.py`、把定義夾塞進 `sys.path` 最後一格、把 `fn/` 從 `sys.path[0]` 拿掉」整套規則與第 3 刀相關測試。

---

#### B4：抽出來的檔名改用「最終登記名」（或分 `fn/tool_<名>.py`、`fn/hook_<名>.py`），消除 `base.pack` 與 `name=` 的假性撞名
- **為什麼**：把檔名硬綁成 `fn/<Python 函數名>.py`，會讓 `@fn.tool(name="...")` 與 `base.pack(prefix="...", rename={...})` 在 Python 函數同名時無端報 `SpecBad`，也讓工具函數與 hook 函數無端搶同一支檔名（見 **A5**）。
- **怎麼做**：
  - 工具抽出來的檔名用它在 `tools.json` 的**最終工具名**：`fn/<工具名>.py`（經 `name=` 或 `base.pack(prefix=, rename=)` 決定後的名字），且抽出的檔內 `fn.main(函數)` 照常跑。
  - 若要讓工具與 hook 名字也互不干擾，或是在同夾發現 `fn/<名>.py` 被同一隻 agent 的另一個函數重複佔用時才報 `SpecBad`：這樣 `base.pack(prefix="base_")` 後衍生再定義同名 `def check` 會分別編成 `fn/base_check.py` 與 `fn/check.py`，自然跑通、零衝突。

---

#### B5：第 3 刀順手修 `agent_def new` 的 `rebase_tools`（3 行），別讓新定義夾的 `tools.json` 指回舊夾的 `fn/add.py`
- **為什麼**：抄一份定義夾卻讓 `tools.json` 指回舊夾的 `fn/add.py`，既違反直覺也違反「資料夾＝程式」的自足性（見 **A18**）。
- **怎麼做**：
  - 在 `agent_def` 的 `rebase_tools` 裡加一個判斷：當工具的相對路徑 `p` 解析後位於**原定義夾內部**（例如 `fn/add.py`），因為整個定義夾已經原封不動抄到新夾了，直接保留原相對路徑 `"fn/add.py"` 不改寫；只有指向原定義夾**外部**（例如 `"../shared/my_tool.py"`）的相對路徑才做 rebase。

---

#### B6：把施工計劃從「六刀＋九題待裁」瘦身成「五刀＋三題待裁」，且第 1～3 刀不必被已定案的題目卡住
- **為什麼**：
  1. 將全域 `git grep` 放回第 1、2、4 刀各自的驗收後，**第 5 刀（文件收尾）已經沒有獨立存在的必要**（見 **A16**）；C-87 加註那一句在第 3 刀交件時一併列出請使用者點頭即可。
  2. `08-待裁題.md` 的第 2、3、4、5 題其實都已由使用者今日的 P5、P6 裁定直接推出，第 8、9 題屬於別條線且不擋本線（見 **A19**）。
- **怎麼做**：
  1. **施工切五刀（第 0～4 刀）**，每刀自帶全域 `git grep` 驗收，刪掉第 5 刀。
  2. **待裁題精簡為 3 題**（其餘在設計摘要中直接告知預設走法即可）：
     - **題 1（原題 1＋A8）**：有了 symlink 版 `extern` 後，還要不要「設定檔列不產出的檔」？（並註明：若用同夾連結 `defs.extern("system.hand.txt")` 頂替，為了守 N-70，`defs.load` 遇到底的同夾 `extern` 應像昨天一樣報錯不繼承，避免衍生夾指回底夾。）
     - **題 2（原題 6）**：`agent_def llm set`／`tools add` 遇到 `extern` 連結會「寫穿」改到共用目標檔，要「接受並寫進警告」「先換成普通檔再改」還是「拒絕並叫人改目標」？
     - **題 3（原題 7 / B4）**：抽出的函數住在 `fn/`，執行時的當前目錄（相對路徑起點）要維持「`fn/`（照舊規矩）」「先切到定義夾」還是「先切到工作區」？
