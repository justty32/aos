Argon 審本線報告初稿的回覆全文（逐字，只加這一行與下面兩行）；採納與否見 04。

← [04-Argon審與採納](04-Argon審與採納.md)

## (1) 事實可能錯（證據或推論站不住、跟附的程式或文件矛盾）

### A1
- **哪一份哪一條**：`README.md`「不用拍板、可以直接修的文件錯」第 2 點、`01-對照總表.md`「三、連結與庫 → 靜態連結」、`02-缺口清單.md` G2（跟已裁的關係）
- **說法**：報告稱骨架 README 只寫了「a tool added to the pack later shows up only after you recompile」，**「沒說工具本身（程式、說明）仍是執行時從 `$AOS_HOME` 讀」**。這是事實錯誤：骨架 README 開頭第三點已經白紙黑字寫了工具程式本身與 `std.fsm()` 的狀態格都只是在編譯產物裡記名字、執行時才讀，像動態連結的 `.so`。另外，同一段最後一句也寫了「A change there shows up at the agent's next start without recompiling」，報告在 G6 抓「next start」文件錯時只抓了下半篇「Linking tool packs」，漏了開頭這一句。
- **根據**：附 `templates/agent-python/README.md` 開頭第 3 個圓點（第 424 行）：`Other things are only named in the compiled files and read when the agent runs, like a library linked dynamically (a .so loaded at start): the tool programs themselves, the state machine cells of std.fsm(), and the packs you link dynamically (--dynamic, see "Linking tool packs" below). A change there shows up at the agent's next start without recompiling.`
- **把握**：高

### A2
- **哪一份哪一條**：`README.md`「最值得看的五條」第 3 條、`01-對照總表.md`「二、編譯 → 可重現：產物不夾帶本機路徑」、`02-缺口清單.md` G3
- **說法**：報告有兩處推論失準：
  1. 報告稱 `defs.load` 會把底裡的相對工具路徑改寫成**本機絕對路徑**（`/home/…/base2/mytool`）。實際上 `_moved(value, root)` 只在 `defs.load` 收到字串路徑（如 `defs.load("../base2")`）時才會算出本機絕對路徑；若照骨架 README 寫法傳入指示詞 `defs.load(defs.env("AOS_WS", "/agents/base2"))`，`root` 是 `dict`，`_moved` 算出來的是 `{"$env": "AOS_WS", "$path": "/agents/base2/mytool"}` 指示詞，不會夾帶本機絕對路徑。
  2. 報告稱「README 說『底那夾之後不必在』只在底全用 `defs.home`／`defs.env` 時成立」。其實就算底改用 `defs.env("AOS_WS", "/agents/base2/mytool")`，只要工具實體檔放在底那夾裡，把底那夾刪了工具一樣會 `PathMissing`。骨架 README 說「the base folder does not have to be there later」是在講 N-70 編譯期繼承（產物不寫 `extends`、執行期不去讀底的定義檔），不是說底夾裡若兼放了工具或腳本實體檔也可以把底夾刪掉。
- **根據**：附 `py/aos/agent_spec_load.py` 第 1202–1208 行 `_moved(value, root)`（`if isinstance(root, dict): return {"$env": root["$env"], "$path": ...}`）；附 `templates/agent-python/README.md` 第 535、538、544 行；附 `docs/NORMS N-70` 第 1346–1347 行。
- **把握**：高

### A3
- **哪一份哪一條**：`01-對照總表.md`「二、編譯 → 可重現：同一份編兩次」、`03-不適用與刻意不同.md`「刻意不同 → 編譯產物跟原始碼的關係」
- **說法**：報告說編譯產物「同輸入同產物」「直接蓋、手改的下次就沒了」，這只對 `defs.compile()`（`--dry-run`）成立，對 `defs.write()`（`--compile`）不完全成立。`write()` 有三處不會「直接蓋」：
  1. `_metainfo.json` 若已存在，會先讀舊檔再 `old.update(value)`，保留所有新宣告沒寫的鍵（因此以前在 `META` 寫過、後來從 `agent.py` 拿掉的鍵，或手改加進 `_metainfo.json` 的鍵，重編後永遠留在裡面）。
  2. `README.md` 若已存在就整份跳過不寫（改了 `agent.py` 的 `DESCRIPTION` 再 `--compile`，`README.md` 不會更新）。
  3. 舊版 `agent.py` 宣告過、新版拿掉的檔案（例如原本有 `HOOKS` 編出了 `hooks.json`，後來拿掉 `HOOKS`；或從 `FILES` 拿掉某個檔），重編時不會刪掉。
- **根據**：附 `py/aos/agent_spec.py` 第 363–385 行 `write(folder, files)`（第 371–373 行 `README.md` 存在則 `continue`；第 374–383 行 `_metainfo.json` 讀舊檔做 `old.update(value)`）；附 `templates/agent-python/README.md` 第 446 行。
- **把握**：高

### A4
- **哪一份哪一條**：`01-對照總表.md`「一、語言本身 → 可見性 `static`／`extern`」
- **說法**：報告以「`lib2.tool("t2")` 拿得到一支不在任何包裡的工具」推論「庫裡沒有『內部』」，並漏了 `agent.py` 真正對應 C 編譯單元內部 `static` 的機制：
  1. 庫的固定結構是 `packs/<name>.json` 與 `tools/<folder>/`，`lib.tool()` 本來就是供使用者單支取用庫內工具的公開 API，不在 pack 裡不代表它是私有工具。
  2. 在 `agent.py` 這一層，寫在 `agent.py` 裡的輔助函式、區域變數與 import 的模組，在被 `defs.load` 載入時完全不會暴露給衍生方——`Base` 只交出九個大寫欄位，而且 `defs.load` 結束時會還原 `sys.path` 與 `sys.modules`。這才是 aos 對應 C translation unit 內 `static`（不匯出符號）的地方。
- **根據**：附 `templates/agent-python/README.md` 第 472–475、545、576 行；附 `py/aos/agent_spec_load.py` 第 1192–1195 行（還原 `sys.path` 與 `sys.modules`）及第 1211–1270 行 `class Base`。
- **把握**：高

### A5
- **哪一份哪一條**：`01-對照總表.md`「一、語言本身 → 常數與設定層」與「二、編譯 → warning 一級」、`02-缺口清單.md` G8、`README.md` 拍板第 5 題
- **說法**：報告把 `INTERFACES={"aos-loop":{"interval_ms":50}}` 被收下當成「沒人讀的 INTERFACES 鍵靜靜過」，並提議在編譯時對「沒人讀的 INTERFACES 鍵」印警告。但看 `interfaces_json()` 的實作，`interfaces.json` 的頂層本來就是開放給各子系統放設定的字典（例如 `"aos-observed": {"file": "observed.jsonl"}`），編譯器只列管 `"aos-agent"` 這一格（禁止改 `entry`／`tools`／`llm`／`system`／`hooks`，並讀取其中的 `llm_keys`），頂層其餘鍵原樣寫出。`agent_spec` 根本沒有、也不該寫死「全系統有哪些外部工具會讀 `interfaces.json` 的哪個頂層鍵」。這裡真正的問題是 `loop.json` 的 `interval_ms: 300` 在 `agent_spec.py` 寫死、且 `loop.json` 在 `RESERVED` 裡不能用 `FILES` 或 `extern` 改，而不是 `INTERFACES` 少擋了未知頂層鍵。
- **根據**：附 `py/aos/agent_spec_parts.py` 第 18–20 行（`SKELETON`、`RESERVED` 含 `loop.json`）、第 216–247 行 `interfaces_json()`；附 `py/aos/agent_spec.py` 第 312–315、333 行。
- **把握**：高

---

## (2) 漏掉的（C 生態有、aos 真有同一個問題而報告沒列的；或報告列了但 aos 其實沒有這個問題的）

### A6（報告沒列、aos 真有）
- **哪一份哪一條**：`01-對照總表.md`「二、編譯」與 `02-缺口清單.md`（漏列：編譯產物夾的殘留物與 `README.md`／`_metainfo.json` 不同步）
- **說法**：C 編譯 `.c → .o` 是單一檔案整份替換；但 aos 編譯 `agent.py` 是寫進同一個資料夾的多個檔案，且沒有 `clean` 或清孤兒檔機制。這在 aos 造成三個真問題：
  1. **刪宣告不刪舊檔**：`agent.py` 原本有 `HOOKS` 或 `FILES={"a.json": ...}`，編譯後拿掉 `HOOKS` 或 `"a.json"` 再 `--compile`，舊的 `hooks.json` 與 `a.json` 會無聲留在定義夾裡（骨架 README 雖有提及要人自己刪，但無警告也無 `--clean`）。
  2. **`META` 的鍵只能加不能刪**：因為 `write()` 對 `_metainfo.json` 做 `old.update(value)`，只要曾經編進 `META` 的鍵，之後從 `agent.py` 的 `META` 刪掉再重編，該鍵永遠留在 `_metainfo.json` 裡。
  3. **改 `DESCRIPTION` 後 `README.md` 與 `_metainfo.json` 分家**：改了 `DESCRIPTION` 再 `--compile`，`_metainfo.json` 的 `summary` 更新了，但 `README.md` 因已存在而被跳過不寫；然而報告 01 第 248 行指出 `agent_def check` 會查 `README.md` 第一行與 `summary`。
- **根據**：附 `py/aos/agent_spec.py` 第 351–352、369–384 行；附 `templates/agent-python/README.md` 第 446 行；報告 `01-對照總表.md` 第 248 行。
- **把握**：高

### A7（報告沒列、aos 真有）
- **哪一份哪一條**：`01-對照總表.md`「二、編譯 → 可重現：產物不夾帶本機路徑」與 `02-缺口清單.md` G1、G3（漏列：`defs.load` 改寫 `FSM` 狀態格 `argv` 相對路徑時靠 `os.path.exists` 猜測）
- **說法**：在 C 的重定位（relocation）中，哪些欄位是符號／位址有明確規格；但在 `agent_spec_load.py` 的 `Base.__init__` 中，對 `TOOLS`（`path`、`env_file`）與 `HOOKS`（`handler`）都是無條件呼叫 `_moved()` 改寫相對路徑，唯獨對 `FSM` 狀態格的 `argv`，寫成了 `if ... and os.path.exists(os.path.join(folder, a))` 才呼叫 `_moved(a, root)`。這會造成兩個無聲錯誤：
  1. 若底的 `FSM` 寫了相對路徑格程式（如 `["python3", "mycell.py"]`），而編譯當下底夾裡該檔還沒放好或拼錯名（即 G1 情境），`os.path.exists` 為 False，`_moved` **不會改寫它**，衍生夾編出的 `fsm.json` 就會無聲變成去「衍生夾」找 `mycell.py`，而不是去底夾找。
  2. 反之，若底夾裡剛好有一個檔案或子資料夾跟 `argv` 裡某個普通參數同名（例如底夾下有叫 `run`、`test`、`main` 的檔），`os.path.exists` 為 True，那個普通命令列參數就會被 `_moved` 無聲改寫成指到底夾的路徑。
- **根據**：附 `py/aos/agent_spec_load.py` 第 1233–1236 行（`TOOLS` 無條件 `_moved`）、第 1247–1251 行（`FSM` `argv` 帶 `and os.path.exists(os.path.join(folder, a))`）、第 1266–1268 行（`HOOKS` 無條件 `_moved`）。
- **把握**：高

### A8（報告沒列、aos 真有）
- **哪一份哪一條**：`03-不適用與刻意不同.md`「不適用 → 前處理器的文字替換、header guard、`#pragma once`」（漏列：菱形 `defs.load` 重複執行與 `sys.modules` 卸載副作用）
- **說法**：報告 03 說 `defs.load` 有防互相載入（SpecBad）所以不需要 `#pragma once`。但防互相載入只擋循環（A 載 B、B 載 A），沒擋菱形（A 載 B 與 C，B 與 C 都 `defs.load("../D")`）。在菱形繼承下：
  1. `D/agent.py` 沒有快取，會被完整重跑兩次（它讀的所有 pack JSON 也重讀兩次）。
  2. 更隱蔽的是 `agent_spec_load.py` 每次載完底會執行 `for name in set(sys.modules) - saved_mods: if name != "aos" and not name.startswith("aos."): del sys.modules[name]`。如果底（或底呼叫的標準庫）在載入期間首次 import 了某個非 `aos.*` 的 Python 標準庫或共用模組，離開 `defs.load` 時該模組會被從 `sys.modules` 強行刪掉，下一個底或外層再 import 時就變成兩個不同的 module 實例（若含全域狀態或 C 擴充型別比對就會出事）。
- **根據**：附 `py/aos/agent_spec_load.py` 第 1192–1195 行；附 `templates/agent-python/README.md` 第 541、545 行。
- **把握**：高

### A9（報告沒列、aos 真有）
- **哪一份哪一條**：`01-對照總表.md`「四、載入與執行 → loader：何時讀哪個檔」與 `02-缺口清單.md`（漏列：跑著重編時狀態改名／刪除導致 `StateUnknown` 停機，以及多檔非原子讀取）
- **說法**：「跑著的 agent 立刻讀到重新編譯後的定義」是已裁特性（不挑戰該特性本身），但正因為每格／每次問腦都重讀定義夾，有兩個 C 動態替換執行期資源時會遇到的同步問題報告沒列：
  1. **狀態改名或刪除使運行中 agent 直接 `StateUnknown` 倒下**：骨架 README 第 444 行明寫，若重編時改名或拿掉 `FSM` 的某個狀態，正停在該狀態的 agent（其 stack `stage.txt` 記著舊狀態名）下一格跑 `aos-fsm` 就會因 `StateUnknown` 失敗停止。
  2. **跨檔撕裂讀取（torn read）**：`agent_spec.py` 的 `write()` 雖對單一檔案用暫存檔加 `os.replace`（並以 `RENAME_LAST` 排序），但一個定義夾有 `interfaces.json`、`fsm.json`、`tools.json`、`system.txt`、`llm.json`、`hooks.json` 多個檔案。running agent 在問腦前依序讀這些檔時沒有跨檔鎖或世代檢查，若剛好在 `os.replace` 迴圈中途讀，會讀到「新 `system.txt`（已叫腦用新工具）＋舊 `tools.json`（新工具還沒換上去）」的半套狀態。
- **根據**：附 `templates/agent-python/README.md` 第 444 行；附 `py/aos/agent_spec.py` 第 386–396 行 `write()`；報告 `01-對照總表.md` 第 214 行。
- **把握**：高

### A10（報告列了、但其實 aos 沒有比 C 差）
- **哪一份哪一條**：`01-對照總表.md`「二、編譯 → 交叉編譯」與 `README.md` 拍板第 1 題 a、b
- **說法**：報告把「編譯時所有庫、包都要在本機讀得到：`defs.env("AOS_WS","/lib2")` 沒設 `AOS_WS` 報 SpecBad」列為交叉編譯的「半套／缺口」，並在拍板第 1 題把「編譯時那台機器要讀得到所有東西」列為代價。但在真實世界的 C 交叉編譯裡，編譯與連結階段**同樣必須在編譯機（build host）上透過 `--sysroot`、`-I`、`-L` 讀得到目標平台的所有 header 與被連結的 library（`.a`／`.so`）**，找不到一樣報錯。aos 編譯時用本機環境變數（`$AOS_HOME`、`$AOS_WS`，即 sysroot）去讀 `defs.lib` 的 pack 與 `defs.load` 的底，並在產物寫出 `{"$env": ..., "$path": ...}` 留待目標機執行時解開，這跟 C 交叉編譯的行為與要求完全對等，不是缺口。
- **根據**：附 `py/aos/agent_spec_lib.py` 第 1307–1318 行 `_where()`、第 1329–1334 行 `pack()`；附 `templates/agent-python/README.md` 第 514、584–585 行。
- **把握**：高

### A11（報告列了、但對照 C 的定性有誤）
- **哪一份哪一條**：`README.md`「最值得看的五條」第 4 條、`02-缺口清單.md` G4
- **說法**：報告把 G4 定性為「`tool.py` 的『標頭』跟實作會分家……這就是 C 裡『標頭和 .c 不一致』，C 靠同一個標頭被兩邊 include 擋住」。這個比喻不對：在 `tool-python` 裡，參數宣告 `PARAMS` 與實作 `run(args)` 寫在**同一支 `tool.py`** 裡，只有單一真相來源，從來沒有分兩份原始碼寫。它會不一致是因為 `_entry.json` 執行時直接跑原始碼 `python3 tool.py`，而腦讀的是編譯產物 `_tooldef.json`。也就是說，G4 其實是 **G7（改了原始碼沒重新編譯產物、沒有 make／過時檢查）在 `tool.py` 上的特例**，而不是 C 的 `.h` 與 `.c` 標頭分家。
- **根據**：附 `templates/tool-python/README.md` 第 645–652、678–690、699 行。
- **把握**：高

---

## (3) 排序、補法、拍板題的問題

### A12
- **哪一份哪一條**：`README.md` 拍板第 2 題、`02-缺口清單.md` G2
- **說法**：這題有三個問題：
  1. **選項 c 碰到已裁事項**：`00-使用者原話.md` 已裁「編譯產物不記帳、直接蓋」，而選項 c（「編譯時把版本戳寫進 `_metainfo.json`」）連報告自己都寫「碰到『不記帳』的精神，同一份 `agent.py` 在不同版上編出來不再一字不差」（同時破壞可重現編譯），不應再列為拍板選項。
  2. **選項綁死成單向累加**：報告把 b 寫成 `a＋...`、c 寫成 `b＋...`。若使用者只想要 `install.py` 在 `$AOS_HOME` 寫一個版本戳（b 的後半），不想多養一支掃描表上 agent 的工具（a），在 a/b/c/d 裡無法單選。
  3. **漏掉真正對應「靜態連結」的合理選項**：G2 的問題是「`--static` 只靜態了工具名單，工具 `_tooldef.json`、工具程式、狀態格仍在執行時從 `$AOS_HOME` 讀，升級一格 9 隻全倒」，但選項 a/b/c 全是「版本戳與掃描」，沒有一個選項去補靜態連結本身。少了一個合理選項：**提供真正的靜態封裝選項（例如 `--bundle`／vendor，編譯時把用到的格程式、工具或至少 `_tooldef.json` 抄進定義夾）**——這個選項也能同時解 G3 搬家問題。
- **根據**：報告 `00-使用者原話.md` 第 146 行；報告 `README.md` 第 58–63 行；報告 `02-缺口清單.md` 第 282–288 行。
- **把握**：高

### A13
- **哪一份哪一條**：`README.md` 拍板第 4 題選項 a 與 d、`02-缺口清單.md` G7（最小補法）
- **說法**：選項 a（`agent.py --check`：重新算一次、跟夾裡比、不同退 1）與選項 d（靠 `--dry-run` 手比）的後果寫錯了——**照現有 `compile()` 與 `write()` 的行為，直接拿 `--dry-run` 的結果跟夾裡現有檔比，在正常的定義夾上會永遠退 1（永遠報不同）**。原因：
  1. `compile()`（`--dry-run`）算出的 `README.md` 永遠只有一行 `description + "\n"`，但 `write()`（`--compile`）遇到已存在的 `README.md`（例如骨架的 180 行 README）會保留不改。
  2. `compile()` 算出的 `_metainfo.json` 只有 `summary` 與 `META`，但 `write()` 會保留夾裡原有的 `lineage`（`agent_def new` 寫的）等其他鍵。
  3. 反過來，若只比 `compile()` 有算出的鍵／檔，又抓不到舊版 `agent.py` 留下來的孤兒檔（如拿掉 `HOOKS` 後殘留的 `hooks.json`）。
  因此 `--check` 不能只是「`--dry-run` 跟夾裡現有檔比」，必須模擬 `write()` 對 `README.md` 與 `_metainfo.json` 的保留規則，這點在補法與選項後果中都沒點出。
- **根據**：附 `py/aos/agent_spec.py` 第 351–352 行（`compile` 產出 ` _metainfo.json` 與 `README.md`）對比第 371–384 行（`write` 跳過已存在的 `README.md`、合併已存在的 `_metainfo.json`）；附 `templates/agent-python/README.md` 第 446 行。
- **把握**：高

### A14
- **哪一份哪一條**：`README.md` 拍板第 3 題、`02-缺口清單.md` G4（最小補法）
- **說法**：第 3 題的選項 a、b 後果沒寫對，且少了一個更合理的選項：
  1. **選項 a（「工具執行時比對，不同就在錯誤行加一句 `run --compile`」）有兩個致命盲點**：第一，工具退 1 印出的錯誤行（`名: error: CODE 原因`）是**原樣回給腦（LLM）看的**（見報告 01 第 234 行 `perror`），不是給人看的；在回給腦的錯誤訊息裡叫腦 `run --compile`，腦既不見得有權限改 `$AOS_HOME` 的工具，還可能被誤導去亂跑指令。第二，如果 `tool.py` 改的是選填參數、`default` 值、描述文字或刪掉一個參數，腦照舊說明呼叫時**不會報 `ArgumentsBad` 錯誤（退 0）**，根本不會印錯誤行，也就完全抓不到。
  2. **選項 b（「`aos-tools` 比檔案時間，`tool.py` 較新時印 warning」）會在 `git` 操作後誤報**：`git clone`／`git checkout`／`cp -r` 不保證 `tool.py` 與 `_tooldef.json` 的 mtime 順序，只要 `tool.py` 晚寫幾毫秒就會假警報。
  3. **少了一個合理選項**：**`aos-tools` 讀工具時（或 `agent_def check`／`tools_def check` 掃描時），若夾裡有 `tool.py` 就比對內容（或比對算出的 tooldef 與 `_tooldef.json`）**，在把工具清單交給腦之前就把 warning 印到 `stderr.txt` 給人看，既不靠不可靠的 mtime，也不必等腦叫錯了才把提示塞進回給腦的錯誤行。
- **根據**：附 `templates/tool-python/README.md` 第 647–652、697–699 行；報告 `01-對照總表.md` 第 234 行；報告 `02-缺口清單.md` 第 302–308 行。
- **把握**：高

### A15
- **哪一份哪一條**：`README.md` 拍板第 1 題、`02-缺口清單.md` G1
- **說法**：第 1 題把三件性質與代價完全不同的檢查（「LLM 值型別」「工具路徑」「狀態格 `argv` 程式」）綁在同一個 a/b/c/d 開關裡，導致選項後果失真、少了一個合理選項：
  1. **`LLM` 值型別檢查**（如 `{"temperature": "hot", "max_tokens": -5}`）是純記憶體內的靜態型別檢查，跟現有 `agent_spec_parts.py` `llm_json()` 查 `model` 必須是非空字串、`fsm` 查 `timeout_ms` 必須是整數完全同類，**不需要讀本機任何外部檔案，對交叉編譯零代價**。把它跟檔案路徑檢查綁在一起，並寫「代價：編譯時那台機器要讀得到所有東西」，會讓使用者若為交叉編譯選 b/c/d 時，連零代價的 `LLM` 值型別檢查都被放掉。
  2. **狀態格 `argv` 程式檢查**的後果沒寫：狀態格的 `argv` 是任意命令列陣列（如 `["python3", "-u", "script.py", "--mode", "fast"]`），除非某元素是 `{"$env": ..., "$path": ...}` 指示詞，否則編譯器無法通則判斷哪個字串元素是「應該存在的檔名」、哪個是「系統指令或旗標值」。
  3. **少了一個合理選項**：**拆開處理——`LLM` 值型別在 `--compile` 直接擋（`SpecBad`，零代價）；工具路徑與格檔存在性放 `agent_def check` 或 `--compile` warning**。
- **根據**：附 `py/aos/agent_spec_parts.py` 第 207–214 行 `llm_json()`；附 `templates/agent-python/README.md` 第 481–493 行；附 `py/aos/agent_spec_load.py` 第 1247–1251 行。
- **把握**：高

### A16
- **哪一份哪一條**：`README.md` 拍板第 5 題、`02-缺口清單.md` G6、G8、G13
- **說法**：拍板第 5 題問「要不要加警告層（`-Wall`）？」並列出五個候選警告（寫進本機絕對路徑、走不到的狀態、沒人讀的 INTERFACES 鍵、**動態包執行時撞名**、**工具描述過長**），選項 b 是「加警告，也加 `--werror`（警告當錯，像 `-Werror`）」。這把三個不同工具、不同生命週期的事混為一談，導致選項 b 在技術上自相矛盾：
  1. 「動態包執行時撞名」（G6）只發生在**編譯之後、agent 執行期問腦前**（`aos-tools` 疊 `$override` 時）。因為如果是編譯當下兩個包就撞名，不論靜態或動態，現有 `agent_spec_parts.py` 的 `stack_tools()` 第 129–133 行**已經直接丟 `SpecBad`**（骨架 README 第 566 行也明寫 `Either way the pack is read when you compile, and the same checks run`）。在編譯期跑 `agent.py --compile --werror` 根本不可能抓到「編譯後動態包才長出同名工具」；而在執行期若把動態包撞名當 error 停掉，那是 runtime loader 行為，不是編譯器的 `-Werror`。
  2. 「工具描述過長」（G13）是 `tool.py --compile` 或 `tools_def check` 的事；`agent.py --compile` 根本不讀 `_tooldef.json`（報告 01 第 168 行自己寫了「`_tooldef` 編譯不讀」），`agent.py` 的 `-Wall`／`--werror` 也管不到它。
- **根據**：附 `py/aos/agent_spec_parts.py` 第 123–133 行 `stack_tools()`；附 `templates/agent-python/README.md` 第 566、572 行；報告 `01-對照總表.md` 第 168、249 行；報告 `02-缺口清單.md` 第 318–323、373 行。
- **把握**：高

### A17
- **哪一份哪一條**：`README.md`「要使用者拍板的題」對照 `02-缺口清單.md` G3、G5、G9、G10、G11、G12
- **說法**：`02-缺口清單.md` 開頭寫「做不做由使用者定」，但 `README.md` 的拍板題只列了 5 題（涵蓋 G1、G2、G4、G7，以及 G3/G6/G8 的警告），替使用者漏掉或預先跳過了其餘會改動架構、介面或已裁邊界的項目：
  1. **G11（core dump 留定義雜湊或副本）**：02 第 362 行自己寫「鄰近那個裁定（不做快照），**請使用者判斷算不算同一件事**」，結果 README 拍板題裡完全沒有 G11。而且 G11 最小補法（「phase 轉 stopped 且碼非 0 時，把當時定義夾幾個檔的雜湊或副本寫進 stack」）本身有邏輯漏洞：因為「跑著讀到新定義」是已裁特性，若有人在 agent 跑著時重編導致下一格 crash、或在 crash 格執行中途重編，轉 `stopped` 那一刻夾裡的檔案已經是新版（且 `loop.json` 是啟動時讀的，更早就不一樣了），死時才抄定義夾並不能保證抄到的是出事那格讀到的那一版。
  2. **G3 的「庫根放一個小清單檔（名字、要的 aos 戳記、用到的 std 工具），`defs.lib` 編譯時讀它查」**：這會改變庫的固定形狀（原本只有 `packs/` 與 `tools/`）並引入版本戳檢查，卻沒放進拍板題（第 5 題只問了 G3 的「絕對路徑警告」）。
  3. **G9（act 格連續 N 次同名同參數失敗就自動塞 `[aos]` 提醒給腦或觸發 hook）**、**G10（`llm.json` 加劇本欄）**、**G12（新增 `aos-agent stats` 子指令）**：都涉及執行期行為或定義檔欄位變更，在 README 裡都沒有拍板題。
- **根據**：報告 `README.md` 第 47–86 行；報告 `02-缺口清單.md` 第 268、299、347、354、356–362、369 行；附 `templates/agent-python/README.md` 第 576 行。
- **把握**：高

### A18
- **哪一份哪一條**：`README.md`「最值得看的五條」與 `02-缺口清單.md` 排序（G4、G5 vs G7）
- **說法**：`02-缺口清單.md` 開頭定下排序原則：「**無聲**的排前面（壞了沒人說，比壞了會報錯痛）；**一次倒一片**的排前面；只是不方便的排後面」。但實際排序卻把 G4、G5 排在 G7 前面（甚至放進 README 最值得看的五條，而 G7 沒進前五）：
  1. **G4（`tool.py` 改了必填參數沒重編）是有聲的，且照標準流程不會發生**：附的 `templates/tool-python/README.md` 明寫改完 `tool.py` 要跑 `tools_def check`（它會自動重編 `_tooldef.json` 並實跑範例）；就算人跳過沒跑，執行時也會立刻回 `ArgumentsBad`（有聲報錯）。
  2. **G5（`tools ls` 用叫它的人的 `AOS_HOME` 解）只在罕見的雙 `AOS_HOME` 混掛情境發生**，且不影響 agent 本身執行。
  3. 反觀 **G7（改了 `defs.load` 的底或庫的 pack，下游靜態連結的 agent 沒重編）是完全無聲的**：因為預設靜態連結與編譯期繼承（N-70）都是拍板定案的主流用法，日常只要改了底的 `agent.py` 或 pack，就算對底跑了 `--compile` 與 `agent_def check`，所有衍生／引用它的 agent 都會**無聲繼續跑舊定義**，`agent_def check` 也完全不報。照報告自己的排序原則，G7 的痛感與無聲程度明顯高於 G4 與 G5。
- **根據**：報告 `02-缺口清單.md` 第 272、302–331 行；報告 `README.md` 第 37–46 行；附 `templates/tool-python/README.md` 第 652、693、699 行；附 `docs/NORMS N-70` 第 1348 行。
- **把握**：中
