# Argon（Gemini 4 Argon High，agy -p plan 模式、檔案法）11-19 審本線 00～05 稿的回覆逐字

← [06-Argon審與採納](06-Argon審與採納.md)｜提示＝不准用工具的檔頭＋00～05 全文＋aos-gdb REPL 說明前 40 行＋agent.py 骨架，約 8 萬位元組，家目錄換成 /home/USER；第一次就過、沒要登入。

## (A) 審查

### A1. 通用代理假設所有子指令都用 `--target NAME`，與 `aos-agent` 實際參數格式衝突
- **出處**：`03-版面設計.md` 第三節「一句話」、`02-一天的流程.md` 第 5、7、18 步、`01-現況盤點.md` 第 4 節第 8 點。
- **為什麼（失敗情境）**：稿中定下通則 `aos-agent --daemon D --target N X Y --flag v ARG` ↔ `a.X.Y(ARG, flag=v)`（在 `03` 第二節甲與細則表 `repr` 又寫成子指令後才放 `--target ann`）。但 `01` 第 4 節第 8 點已盤點出各指令指定對象有 `-t`、**位置參數**、`-s STACK` 幾種：
  1. `02` 第 18 步明寫 shell 是 `aos-agent ctl stop bob`（`bob` 是位置參數，非 `--target bob`）。若 `a.ctl.stop()` 由代理盲加 `--target bob`，要嘛報 `FlagUnknown`，要嘛缺位置參數。
  2. 在已綁定 `a` 上叫 `a.ctl.ls()` 或 `a.ctl.add("agents/bob")`（對象不是 `ann`），代理仍會硬塞 `--target ann` 而失敗。
  3. `--target` 放在子指令前（`03` 一句話）或子指令後（`03` 細則表 `repr`）在稿內自相矛盾；若頂層 `aos-agent` 不收 `--target`（由各子指令自己的 parser 收），放在子指令前直接報錯。
- **嚴重度**：一定要改
- **最小修法**：先查清 `aos-agent` 頂層與各子指令對 `--target` 的實際收法：若由頂層統一收 `--target`（且 `ctl stop` 等子指令在無位置參數時退回吃頂層 `--target`），先在 `aos-agent` 補齊這個協定；不收 `--target` 的全表指令（`ctl ls`、`ctl add`）規定從模組 `agent.ctl.*` 呼叫，或在把手上明列排除。

---

### A2. 通用代理的旗標／型別轉換細則有多處歧義與互撞
- **出處**：`03-版面設計.md` 第三節「細則」表、`05-邊緣狀況與要拍板的題.md` 第 16～18 條。
- **為什麼（失敗情境）**：
  1. **單字母布林旗標**：細則規定「`名=值` → 單一字母是短旗標（`w="."` → `-w .`）」，但「`名=True` → 只有 `--名`」沒寫單字母規則。打 `a.ctl.ls(j=True)` 會翻成 `--j` 而非 `-j`，指令報 `FlagUnknown`。
  2. **`bool` 是 `int` 的子類**：在 Python 中 `isinstance(True, int)` 為真。若實作先判數字轉字串才判 `is True / False`，`auto_restart=True` 會變 `--auto-restart 1`、`auto_restart=False` 會變 `--auto-restart 0`。
  3. **`名=[v1, v2]`、`名_json=dict` 與位置參數型別規則不一致**：位置參數傳 `dict/list` 自動轉 JSON，但關鍵字參數傳 `list` 卻是「旗標重複（`--envs A=1 --envs B=2`）」，要轉 JSON 反而得在名字後硬接 `_json`（`名_json=dict`）。若某旗標原本就叫 `--config-json` 且值是一個 JSON array（`config_json=[1, 2]`），會先撞到 `名=[v1, v2]` 被拆成 `--config-json 1 --config-json 2`；若某旗標不叫 `*-json` 卻收 JSON dict（直接傳 `meta={"a": 1}`），細則表根本沒定義會變什麼（`str(dict)` 印出單引號 `'a'` 的非合法 JSON）。
  4. **保留字與內建名混為一談**：`05` 第 16 條寫「旗標名是 Python 保留字或內建名（`--from`、`--async`、`--json`）：保留字後面加底線」，但 Python 內建名（如 `id=`、`type=`、`set=`、`open=`、`format=`）當關鍵字參數完全合法，不需要加底線。若代理只對 `keyword.iskeyword` 去底線，使用者照說明打 `id_="x"` 會變成 `--id- x`；反之若子指令名碰到保留字（如 `in`、`from`、`async`），細則表的「點下去的名字」那一列卻漏了去尾底線規則。
  5. **位置參數含 `-` 開頭**：`05` 第 18 條說「`say`、`ask` 這兩支手寫的，在文字前面自動加 `--`」，但 `02` 第 8 步與 `03` 第七節搬改清單都寫「手寫只剩 `attach`、`say`、`listen`、`look`、`bp`」，`ask` 根本不是手寫；且 `goal.set("- item")`、`mailbox.send` 同樣會傳 `-` 開頭字串。
- **嚴重度**：一定要改
- **最小修法**：
  1. 順序固定先判 `bool`（`True` 單字母→`-x`、多字母→`--xxx`；`False/None` 略過），再判 `int/float`。
  2. 拿掉 `名_json=` 這種藏在參數名裡的特例：關鍵字參數是 `dict` 一律轉 JSON 字串（與位置參數一致），`list/tuple` 才是重複旗標（若真要傳 JSON list 給旗標，自己傳 `json.dumps(...)`）。
  3. 去尾底線規則統一為「點下去的名字或關鍵字參數名，凡 `name.endswith("_")` 一律去掉最後一個 `_`」，說明只寫 Python 關鍵字（不提內建名）。

---

### A3. `json=True` 遇到「預設已輸出 JSON／JSONL」或「空輸出」的指令會壞
- **出處**：`03-版面設計.md` 第三節「細則」與「回傳值」、`01-現況盤點.md` 第 2 節與第 4 節第 8 點。
- **為什麼（失敗情境）**：
  1. `01` 盤點已寫明：`aos-tools get` 輸出是「每支一行 JSON」（JSONL），C++ 的 `see/show/get` 是「預設 JSON」（沒有 `--json` 旗標）。使用者在 Python 打 `tools.get("read", json=True)` 時，代理一方面會多傳 `--json` 導致指令報 `FlagUnknown`，另一方面就算不報錯，多行 JSONL 丟進 `json.loads(stdout)` 也會炸 `JSONDecodeError: Extra data`。
  2. 若指令支援 `--json` 但某次查詢結果為空（stdout 為空字串），`json.loads("")` 會直接丟 `JSONDecodeError`。
- **嚴重度**：一定要改
- **最小修法**：① `json=True` 解碼前若 `stdout.strip() == ""` 回 `None`；若 `json.loads` 失敗且有多行，退回逐行 `json.loads` 成 `list`。② 預設已輸出 JSON 的指令（如 `aos-tools get`）同樣讓它收 `--json` 當無操作（no-op），維持「給 `json=True` 就加 `--json` 並解開」單一規則。

---

### A4. 把手 `a` 用 `__getattr__` 轉發一切名字，打錯方法名不報 `AttributeError`，且拿掉 `a.agent(*args)` 後缺頂層逃生口
- **出處**：`03-版面設計.md` 第三節「細則」（底線開頭與 `repr`）與第七節搬改清單、`05-邊緣狀況與要拍板的題.md` 第 13～15 條。
- **為什麼（失敗情境）**：
  1. 使用者曾直覺打過 `a.stop()`、`a.resume()`、`a.wait_paused()`（`00-使用者原話.md`）。在把手上掛無差別 `__getattr__` 後，使用者在 REPL 打 `a.resume` 看一眼，`repr` 不報錯，反而印出 `<aos-agent --daemon ... resume --target ann>`，誤導使用者以為有這支方法；打 `a.resume()` 才起子行程失敗。
  2. `03` 第三節說「`a.tools("add", "--no-cache", "x")` 把字串原樣丟過去也行，所以今天的 `a.agent(*args)`、`a.ctl(*args)` 兩支可以拿掉」。`a.ctl(*args)` 確實被 `a.ctl(...)` 取代，但 `a.agent(*args)` 是頂層逃生口（例如傳頂層旗標或任意子指令字串），拿掉後除非 `a(...)` 本身可呼叫（稿中未定義 `a.__call__`），否則頂層沒有對應入口。
- **嚴重度**：建議
- **最小修法**：讓把手 `a` 本身實作 `__call__(*args, **kw)` 當頂層通用殼；或者把手 `a` 只暴露已知頂層名字（`say`、`listen`、`ask`、`ctl`、`tools`、`llm`、`hook`、`system`、`history`、`goal`、`open`、`close`、`watch`、`peek`、`bp`、`look`），子層（如 `a.ctl.*`）才放開任意 `__getattr__`（頂層僅十幾個固定名字，在 `a` 上打 `a.resume` 當場就能報 `AttributeError` 並支援 Tab 補全）。

---

### A5. 「整個 `aos.py` 只有一種例外 `Failed`」與 `TimeoutError`、`SpecBad`、`a.look` 讀檔實況不合
- **出處**：`03-版面設計.md` 第三節「錯誤」。
- **為什麼（失敗情境）**：
  1. 今天 `wait_stopped` 丟的是 Python 內建 `TimeoutError`（`01` 第 1 節）。若改成自訂 `Timeout(Failed)` 且沒多重繼承內建 `TimeoutError`，原本 `except TimeoutError:` 的標準寫法會接不到。
  2. `a.look.file("不存在")`、`a.look.observed()` 是 Python 直接讀 stack 檔（不跑子行程），檔案尚未生成時 Python 丟的是 `FileNotFoundError`（`OSError`）；`json=True` 遇到壞輸出丟的是 `json.JSONDecodeError`。若不包成 `Failed`，就違反「整個 `aos.py` 只有一種例外 `Failed`」；若包成 `Failed`，稿中沒定義這時的 `program/code/reason/argv/exit` 填什麼。
  3. `ag.SpecBad` 是延遲報錯（`defs()` 一次報出多處宣告錯誤），既沒有 `argv` 也沒有 `exit`，硬塞進子行程專用的 `Failed` 欄位結構並不自然。
- **嚴重度**：建議
- **最小修法**：① `class Timeout(Failed, TimeoutError): pass`。② 明定 `a.look.*` 讀不到檔或 `json.loads` 失敗時也轉成 `Failed(code="FileMissing" / "JsonBad", argv=None, exit=None)`。

---

### A6. 「薄殼當硬規則」在 `agent` 模組內自己破功四次，尤其 `a.tools.add(std.pack(...))` 破壞解耦與原子性
- **出處**：`03-版面設計.md` 第二節、第三節「薄殼當硬規則」、第六節「工具包」、第七節搬改清單。
- **為什麼（失敗情境）**：
  稿中宣稱「硬規則：`agent`、`daemon_ctl`、`tools`、`mailbox` 裡每個公開的呼叫＝剛好一條 aos 指令，不多做、不自己記狀態、不解讀輸出……違反的東西不准放進這四個模組」，但隨即在 `agent` 裡放了四個破例：
  1. **`a.bp` 與 `a.look` 就掛在 `agent.attach()` 回傳的 `a` 上**（且 `Look` 直接寫進 `py/aos/py/agent.py`）。
  2. **`say` 與 `listen` 只在把手 `a` 上手寫整形**：`03` 第七節寫「`agent.py` 的把手（手寫只剩 `attach`、`say`、`listen`、`look`、`bp`）」，那照 `03` 第三節不 `attach` 直接叫模組 `agent.say("hi", target="ann")` 時，走的是通用代理而非把手上的手寫方法——同一句 `say`，透過 `a.say` 回信名 ID、自動加 `--`，透過 `agent.say` 卻回整段 `Text`、不加 `--`。
  3. **`a.stack` 屬性（`03` 第二節、`05` 第 27 條）偷跑查詢並快取狀態**：agent 的 stack 路徑要問 daemon 才知道。若 `agent.attach("ann")` 當下就查 daemon 並快取 `a.stack`，那 `attach` 就不是純記名字的薄物件（daemon 還沒起或 `ann` 還沒 `ctl add` 時 `attach` 就會失敗，且 `rm` 重掛後 `a.stack` 過期）。
  4. **`a.tools.add(std.pack("json"))` 在代理層展開工具包（`03` 第六節）**：
     - `std.pack(...)` 與 `ag.lib("my", ...).pack(...)` 回傳的是編譯期的宣告 dict（含 `kind`、庫前綴 `my_`、`path_json={"$env": ...}` 等內部結構）。要讓通用代理把這張單子展開成多條 `aos-agent tools add`，`_shell.py` 就必須懂得解析 `agent_spec` 的宣告格式與環境變數展開——直接打破「活側與寫定義互不依賴」以及「加在 Python 庫裡的聰明，Lisp 那邊都要重寫一遍（`03` 第五節）」！
     - 更嚴重的是**非原子性**：一個包有 5 支工具，跑了 3 條 `aos-agent tools add` 後第 4 條失敗丟 `Failed`，活 agent 身上已經殘留半包工具，且 `Failed.argv` 只看得到第 4 條。
- **嚴重度**：一定要改
- **最小修法**：
  1. 刪掉「通用代理收到宣告物件自動展開成 N 條指令」的特例；將來若真有「執行中整包加工具」的需求，照本稿自己的原則加在 CLI 上（如 `aos-agent tools add --pack ...`），Python 與 Lisp 代理自然同時擁有，且由指令保證原子性。
  2. `a.stack` 不在 `attach` 時預查快取，改為需要時才查（或只留 `a.look.where()`）。
  3. `say`/`listen` 若要手寫，模組層 `agent.say` 與把手 `a.say` 必須走同一支函式。

---

### A7. `sys.path` 與 `install.py` 遺留問題：骨架 `except` 攔錯名字、`_d` 順序反置、`install.py` 刪除空窗
- **出處**：`01-現況盤點.md` 第 4 節第 2 點、`03-版面設計.md` 第七節、`05-邊緣狀況與要拍板的題.md` 第 2、9、10 條、`CODE: templates/agent-python/agent.py:690-705`。
- **為什麼（失敗情境）**：
  1. **骨架 `agent.py` 攔不到 `aos.py` 的 `ModuleNotFoundError`**：看 `templates/agent-python/agent.py:696-699`，目前寫的是 `if _e.name != "aos": raise`。第三刀改成 `from aos.py import ag, std` 後，若機器上的 `$AOS_HOME/lib/aos/` 是舊版（有 `aos/` 但還沒裝 `aos/py/`），Python 丟出的 `ModuleNotFoundError.name` 是 `"aos.py"` 而非 `"aos"`，骨架會直接噴原始 traceback 而非一行友善錯誤。
  2. **骨架把 `_d` 插在 `$AOS_HOME/lib` 前面**：`agent.py:691-694` 寫 `_found = [_d, "$AOS_HOME/lib"]`。這表示只要工作夾或 agent 夾裡有一支叫 `aos.py` 的檔案，連已經設好 `$AOS_HOME` 的 `agent.py` 都會優先抓到那支 `aos.py` 而炸 `'aos' is not a package`（`05` 第 2 條以為只有自己寫的腳本會中，其實連官方骨架都會中）。
  3. **`install.py` 先整夾刪 `lib/aos/` 會讓活樹瞬間斷糧**：`05` 第 9、10 條說第二刀讓 `install.py` 抄之前先清 `lib/aos/`。若對著有活樹在跑的 `$AOS_HOME` 執行 `shutil.rmtree("lib/aos")` 再 `copytree`，中間那幾十毫秒內任何觸發到的 `gdb_trigger` 或 Python 工具（`import aos.json` 等）都會 `ModuleNotFoundError`。而且 `01` 第 4 節第 2 點已指出**當下 `lib/aos/` 就缺 `agent_spec_lib.py`**，把 `install.py` 的修補拖到第二刀，等於第一刀期間裝好的 `lib/` 依然是壞的。
- **嚴重度**：一定要改
- **最小修法**：
  1. `install.py` 立刻先修，且不要「先 `rmtree` 再慢抄」：改為抄進暫存夾再交換，或先 `copytree(dirs_exist_ok=True)` 再巡迴刪掉 `py/` 已不存在的多餘檔／夾。
  2. `agent.py` 骨架把 `$AOS_HOME/lib` 排在 `_d` 前面，且 `except ModuleNotFoundError` 改判 `if not (_e.name == "aos" or (_e.name or "").startswith("aos.")): raise`。

---

### A8. 分刀計畫失實：第一刀既非「刪掉夾就還原」，也直接依賴 `aosgdb-api-1119` 正在改的檔案
- **出處**：`03-版面設計.md` 第七節「分刀」、`05-邊緣狀況與要拍板的題.md` 第 9、11 條。
- **為什麼（失敗情境）**：
  1. **不是刪夾就還原**：第一刀驗收明寫「`install.py` 之後，在暫存樹的 `aos-gdb ann` 裡打 `from aos.py import agent`……不喜歡＝刪掉 `py/aos/py/` 這個夾，什麼都沒壞」。但因為 `install.py` 只加不刪（且稿中把清 `lib/aos/` 排在第二刀），跑過一次 `install.py` 後 `$AOS_HOME/lib/aos/py/` 就留在機器上了，刪掉原始碼 `py/aos/py/` 根本清不掉已安裝的 `lib/aos/py/`。
  2. **第一刀直接依賴 `aos.gdb.look` 且規格對不上**：第一刀說「`_shell.py` 的 `run`／`Text`／`Failed` 先直接從 `aos.gdb.look` 拿，不抄一份……不碰 `aosgdb-api-1119` 正在改的任何檔」。但：① `aosgdb-api-1119` 正在改 `py/aos/gdb/`；② 現有 `aos.gdb.look` 的 `Failed` 沒有 `program/code/reason/argv/exit` 五個欄位、`run` 不會處理 `json=True`、echo 預設是開且印在 `stdout`（新版規定預設關且印在 `stderr`）。直接從 `aos.gdb.look` 拿，連第一刀自己的細則表單元測試都過不了。
  3. **第一刀驗收需要第二刀才有的東西**：第一刀驗收要跑 `x.ctl.state(json=True)` 與 `x.say("hi")`，但把手 `Agent` 與手寫 `say`、`--json` 長名補齊在表格裡都列在第二刀。
- **嚴重度**：一定要改
- **最小修法**：`_shell.py` 的 `run/Text/Failed`（不到 40 行）直接在 `_shell.py` 自己寫好，不 import `aos.gdb.look`；`install.py` 清理孤兒檔在第一刀之前就單獨修掉。

---

### A9. 五道拍板題的設計缺陷：把正交題綁成單選、漏問擅改的斷點 API、選項後果失真
- **出處**：`05-邊緣狀況與要拍板的題.md` 第二節「要你拍板的五題」、`03-版面設計.md` 第一～三節與第八節。
- **為什麼（失敗情境）**：
  1. **第 1 題（入口名 `aos.py` vs `aos`）對選項 b 的代價誇大，且把使用者的隨口舉例當硬規格**：
     使用者原話寫 `from aos.py.agent import breakpoint as a.bp`（在 Python 語法中 `as a.bp` 根本不合法），明顯是口頭示意「從 aos 的 python 庫匯入」，而非堅持子套件非叫 `.py` 不可。而稿中否定 `import aos`（選項 b）的理由是「必須把三十幾支內部模組搬進 `aos/_internal/`」，這並不屬實：即使開了 `aos/py/`，那三十幾支內部模組**照樣**留在 `aos.*` 可以被外部 import，根本沒有多出任何真正的封裝邊界！反之取名 `aos.py` 卻帶來真真實實的 `.py` 撞名陷阱、違反 C-54（`py/aos/py/` 兩個 `py` 不同義）。
  2. **第 2 題把兩個正交維度綁在同一題互斥**：
     甲（把手式 `a = agent.attach("ann")`）與乙（目前這隻 `a.use("ann")`）是「活側怎麼指定對象」；丙（「寫定義的 `agent_spec` 不搬，只替活側開入口」）則是「編譯側要不要搬家」。把丙列成第 2 題的第三個互斥選項，讓使用者無法選「**甲＋丙**（活側用把手式、寫定義維持今天剛交的 `from aos import agent_spec as ag` 不折騰）」。且稿中反對丙的理由「`a.tools.add(std.pack("json"))` 會變成兩行 import」根本不成立（`std.pack` 回傳的只是普通 dict，誰 import 的毫無影響）。
  3. **第 3 題（斷點要不要有 shell 指令）不該問**：
     使用者在 11-19 講完 `aos-agent breakpoint` 後，**同一天後續已裁定「兩者解耦合（aos-agent 不知道 gdb）」**（`00-使用者原話.md`）。選項 a 與 b 現在都完全不用動程式碼，拿已裁定的事再問一次只是增加決策負擔。
  4. **第 4 題（一般 `python3` 找套件）跟 `02` 結論自相矛盾**：
     `02-一天的流程.md` 結論 1 才剛說第一批必做的四樣之首是「**找得到套件（現在一般 `python3` 連 `import aos` 都不行）**」，結果第 4 題卻推薦選項 a（一般 `python3` 照樣 `ModuleNotFoundError`，每支腳本開頭要自己貼十幾行 `sys.path`）。而反對選項 b（`env.sh` 設 `PYTHONPATH=$AOS_HOME/lib`）的理由說「會改到 daemon 底下每一支工具的搜尋路徑」也是假議題——daemon 底下的工具本來就自己把 `$AOS_HOME/lib` 放上 `sys.path` 了，`env.sh` 設 `PYTHONPATH` 跟 `.pth` 跨目錄殘留的問題完全不同。
  5. **第 5 題（`a.look`）漏講對 `watch(py=...)` 的破壞，卻又在沒問使用者的情況下擅改 `aosgdb-api-1119` 的斷點 API**：
     - 看 `CODE: py/aos/apps/gdb/__init__.py:668`，另一條線正在交的斷點庫寫法是 `a.bp.add("watch", py=lambda t: len(t.history(0)) > 20)`，若把 `history` 搬進 `a.look.history`，`watch` 的 `t.history(0)` 怎麼辦隻字未提。
     - 更嚴重的是：使用者在 `00-使用者原話.md` 第二段已修正想法為「**以斷點為核心，增刪改查……`a.bp.stop()`, `a.bp.resume()`**」，因此 `aosgdb-api-1119` 實作成 `a.bp.add("before_tool", ...)` 與 `a.bp.stop()`（立刻暫停）。本稿卻在第八節不列方向題，單方面決定改成 `a.bp.stop.before_tool(...)`——這讓 `a.bp.stop` 既是「立刻暫停（不建斷點）」的函式，又是「建立斷點（= `add`）」的命名空間，一詞兩義（違反 C-54），且直接推翻 `aosgdb-api-1119` 即將提交的介面。
- **嚴重度**：一定要改
- **最小修法**：
  1. 刪掉第 3 題；把第 2 題拆開（「把手式 vs 目前這隻」與「今天剛交的 `agent_spec` 要不要再搬一次家」分開問）。
  2. 斷點介面尊重 `aosgdb-api-1119` 已照使用者第二段原話做好的 `a.bp.add(...)` / `a.bp.stop()`，不在本設計稿另起爐灶改成 `a.bp.stop.before_tool()`。
  3. 第 4 題誠實列出 `env.sh` 加 `PYTHONPATH=$AOS_HOME/lib` 並無 `.pth` 搬家殘留問題，或直接讓 `aos-gdb [NAME]` 的 `NAME` 可省略。

---

### A10. 違反「只把必要的搞進來／第二次遇到才加」原則，過度規劃跨線大搬家
- **出處**：`00-使用者原話.md`、`02-一天的流程.md` 第 2、20 步、`03-版面設計.md` 第四節與第七節、`05-邊緣狀況與要拍板的題.md` 第三節第 6 點。
- **為什麼（失敗情境）**：
  1. 稿中在 `03` 第四節定下鐵則：「門檻：有人在 REPL 第二次用 `sh("aos-xxx …")` 打同一支……沒有第二次的不加」。但第一批卻「順便」把 `aos-tools`（`from aos.py import tools`）跟 `aos-mailbox`（`from aos.py import mailbox`）包進來。尤其 `aos.py.tools` 操作的是離線登記檔（`--file`），跟活 agent 的 `a.tools`（`aos-agent tools`）及寫定義的 `ag.tool` 擺在一起，保證讓人搞混「加工具到底叫 `tools.add` 還是 `a.tools.add`」。
  2. `agent_spec`（`ag`、`std`）與骨架 `templates/agent-python/agent.py` 今天（11-19）才剛由命名空間線定案交出，`aos-inherit-1119` 也正在動它；`aos.gdb` 則有 `aosgdb-api-1119` 正在改、還沒交。這份規劃卻排了四刀要把這兩邊全部拆掉搬進 `py/aos/py/`，所有 import、README、測試、知識庫重改一輪——完全違背使用者說的「感覺是個大工程，應該只需要把必要的搞進來就好」與 11-14「自然長出來」。
- **嚴重度**：一定要改
- **最小修法**：第一批只做「通用代理＋把手 `a`（含 `a.bp`）」，不動今天剛交的 `agent_spec`，也不預包還沒在 REPL 用到的 `aos-tools` 與 `aos-mailbox`。

---

## (B) 提案

### B1. 砍掉 `aos.py.tools`、`aos.py.mailbox` 與 `a.tools.add(std.pack(...))` 展開特例
- **做法**：第一批只提供 `agent`（含把手 `a`）與 `daemon_ctl` 兩個代理模組；拿掉代理層自動展開 `std.pack(...)` 的特例規則。
- **後果**：
  - 消除 `aos.py.tools`（離線登記檔）與 `a.tools`（活 agent 工具）、`ag.tool`（定義宣告）三者撞名的混亂。
  - 代理層（`_shell.py`）徹底保持「1 呼叫 ＝ 1 條指令」的純粹薄殼，完全不必認識 `agent_spec` 的 dict 結構與 `$env`，也不會有「半包工具加到一半失敗」的殘留狀態。
  - 真有執行中整包加工具的需求時，給 `aos-agent tools add` 加 `--pack`，Python 與未來的 Lisp 一次到位。

### B2. 寫定義（`ag`、`std`）留在原地或僅做一行轉匯出，不搬動 `agent_spec*.py`
- **做法**：採用「活側用把手式（甲）＋寫定義檔案不搬家（丙）」。若希望統一入口，只需在新入口 `__init__.py` 寫兩行 `from aos import agent_spec as ag; std = ag.std` 轉匯出即可，**不要**把 `py/aos/agent_spec*.py` 搬進子資料夾，也**不要**去改今天剛交的 `templates/agent-python/agent.py` 骨架與命名空間線的測試。
- **後果**：
  - 零檔案搬移、不跟今天剛交的命名空間線與正在跑的 `aos-inherit-1119` 撞車。
  - 使用者在 REPL 或腳本裡依然可以從統一入口拿到 `ag, std`，而現有所有 `agent.py` 與測試一行都不用改。

### B3. 直接在 `py/aos/gdb/` 原地加上通用代理，不拆不搬 `aos.gdb`，等 `aosgdb-api-1119` 交完一刀收工
- **做法**：
  1. 等 `aosgdb-api-1119` 提交後，直接在它已經改好的 `Agent` 把手與模組上掛上 40 行的通用代理（把原本手寫的 `a.ctl(*args)`、`a.agent(*args)` 升級為可點下去的 `a.ctl.stop()`、`a.tools.add(...)`、`agent.ctl.ls()`）。
  2. 斷點寫法完全沿用 `aosgdb-api-1119` 已實作的 `a.bp.add("before_tool", ...)`、`a.bp.stop()`、`a.bp.resume()`，不另改 `a.bp.stop.before_tool()`。
- **後果**：
  - 原本規劃的四刀（新增殼 → 搬 `aos.gdb` 與改兩支 hook 本體 `gdb_trigger`/`gdb_watch` → 搬 `agent_spec` → 加特例）直接縮成**一刀（約 50 行程式碼）**。
  - 不必動 `py/tools/agent/gdb_trigger` 與 `gdb_watch`，活樹上的斷點在更新時完全不受影響。

### B4. `env.sh` 直接加 `PYTHONPATH=$AOS_HOME/lib`，並讓 `aos-gdb [NAME]` 的 `NAME` 可省略
- **做法**：
  1. 在 `env.sh` 補一行 `export PYTHONPATH="$AOS_HOME/lib${PYTHONPATH:+:$PYTHONPATH}"`。
  2. `aos-gdb` 不給 `NAME` 時照樣開 REPL（預放好 `agent`、`daemon_ctl`、`ag`、`std`、`sh`，只是不預跑 `a = agent.attach(NAME)`）。
- **後果**：
  - 真正落實 `02` 結論 1「一般 `python3` 找得到套件」：在已 `source env.sh` 的視窗裡，無論跑 `python3`、`aos-gdb`（尚無 agent 時先進去 `agent.ctl.add(...)`），還是自己寫小腳本，都直接 `import` 得到，不必每支腳本開頭抄十幾行 `sys.path`。
  - 跟著 `env.sh` 的 `$AOS_HOME` 走，只在該 shell 視窗有效，完全沒有 `.pth` 搬目錄後指到舊路徑的問題。
