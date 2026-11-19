# Argon（Gemini 4 Argon High，agy -p plan 模式）對繼承深挖設計稿 00～06 的審查與提案原文，11-19，未改字

← [README](README.md)｜採納表：[07-Argon審與採納](07-Argon審與採納.md)

送審材料：本夾 README、00～06 全文，加 `py/aos/agent_spec.py`、`agent_spec_parts.py` 第 55～190 行、`agent_spec_lib.py`、`templates/agent-python/agent.py`、`py/aos/apps/tools/registry.py` 第 80～175 行（約 125 KB，家目錄換成 /home/USER）；提示檔第一行明寫除了讀那一檔不准用工具。一次就過，沒有要登入。原文裡的「第 N 行」是它對送審拼接檔的行號，不是 repo 檔的行號。

---

### (A) 審查意見（Review）

---

#### A1. `[MUST-FIX]` 菱形繼承中「刪除（`ag.no`／`None`）」會被悄悄蓋回，與筆記主打賣點自相矛盾
* **位置**：`README.md` 結論 3、`04-設計選項.md`（乙、`ag.base`、菱形與多個底）、`06-邊緣狀況與要拍板的題.md` (a) 第 14 條；對照 `py/aos/agent_spec_parts.py` 第 94～106 行（`tools_json`）、第 169～171 行（`hooks_json`）。
* **問題**：
  筆記批評 `$override` 在菱形繼承時會把中間層的修改蓋回（`02` 結論 2），並宣稱乙的 `ag.base` 可解決菱形問題。但看 `agent_spec_parts.py`：
  1. `tools_json` 第 95～96 行處理 `ag.no(name)` 時，是 `if name in nos: continue`，即展開後的 `out` 字典裡**直接沒有該鍵**（不留墓碑／tombstone）。
  2. 當 `d1`、`d2` 皆衍生自 `base`，而 `d1` 照 `04` 主例寫了 `ag.no("write")`（拿掉 `write`）、`d2` 沒動 `write` 時，`ag.base(d1.TOOLS, "d1")` 算出的工具表只是「不含 `write`」，而 `ag.base(d2.TOOLS, "d2")` 的工具表仍含 `base` 的 `write`。
  3. 頂層寫 `[ag.base(d1.TOOLS, "d1"), ag.base(d2.TOOLS, "d2")]` 時，`tools_json` 的 `packed["write"]` 只會收到來自 `d2` 的一筆（`rest` 為空），不會觸發第 102～104 行的 `other != entry` 檢查，結果 **`d1` 拿掉的 `write` 在頂層被 `d2` 悄悄復活，且完全不報 `SpecBad`**。
  4. `hooks_json` 同理：第 170 行 `if entry is None: table.pop(name, None)` 直接把鍵刪掉，`d1` 用 `None` 拿掉的 hook 在 `[d1.HOOKS, d2.HOOKS]` 菱形中一樣會被 `d2` 悄悄蓋回。

---

#### A2. `[MUST-FIX]` `HOOKS` 宣稱「串列收巢狀、兩個來源撞名報錯，自己寫的那層才是蓋」，在 Python 資料結構上無法分辨
* **位置**：`04-設計選項.md`（菱形與多個底、代價與分刀的刀 2）、`06-邊緣狀況與要拍板的題.md` (c) 第 4 條；對照 `py/aos/agent_spec_parts.py` 第 155～185 行（`hooks_json`）。
* **問題**：
  1. 在 `agent_spec_parts.py` 第 161～165 行，`HOOKS` 的圖層除了 `std.hooks()`（`kind == "stock_hooks"`）外，使用者在 `agent.py` 自己寫的覆蓋層就是**普通 Python `dict`**（如 `{"timer": {...}}`）。
  2. 若 `d1` 與 `d2` 都在自己的 `HOOKS` 寫了 `dict`（或 `d1.HOOKS = [std.hooks(), {"timer": ...}]`），當頂層寫 `HOOKS = [d1.HOOKS, d2.HOOKS]` 時，若照刀 2 僅做「hook 串列收巢狀」，展平或走訪時 `d1` 裡的 `dict` 與頂層自己明寫的 `dict` 型別完全相同，Python 的 `dict` 不帶出處標籤。
  3. 因此 `hooks_json` **根本無從區分** `[{"timer": A}, {"timer": B}]` 究竟是「`d1.HOOKS` 與 `d2.HOOKS` 兩個底互撞（應報 `SpecBad`）」還是「底 `d1.HOOKS` 加上頂層自己明寫的覆蓋（應合法蓋過）」。`TOOLS` 之所以能分，是因為 `TOOLS` 用了 `ag.base(...)` 把底包成 `"kind": "pack"` 與頂層的 `"kind": "tool"` 區隔；`HOOKS` 沒包就宣稱能分，邏輯不成立。
  4. 此外，`hooks_json` 第 161～163、182～184 行對 `stock_hooks` 的 `stock.append(layer["template"])` 沒有去重（不若 `tools_json` 第 73 行檢查 `packs`），多層或菱形衍生若都含 `std.hooks()`，`hooks.json` 的 `description` 會重複印出多次 `templates/agent-fsm/hooks.json`。

---

#### A3. `[MUST-FIX]` `ag.load` 在模組最外層執行，與 `agent_spec.py` 的「延遲報 `SpecBad`、單行錯誤輸出、`--help` 不崩潰」契約衝突
* **位置**：`04-設計選項.md`（甲、乙程式碼範例）、`06-邊緣狀況與要拍板的題.md` (a) 第 3、4 條；對照 `py/aos/agent_spec.py` 第 8、51、55～56、318～333 行、`py/aos/agent_spec_lib.py` 第 8、44～46、204～205 行。
* **問題**：
  1. `agent_spec.py` 的核心架構是：最外層宣告函式（`ag.tool`、`std.pack`、`ag.lib` 等）寫錯時**不在當下 raise `SpecBad`**，而是回傳 `{"kind": "bad", "bad": msg}`（或 `Lib.bad`），直到最後一行 `ag.main(...)` 進到第 328～331 行的 `try: out = defs(...) except SpecBad:` 才統一用 `flags.die` 印出單行 `"NAME: error: SpecBad ..."` 並 `exit 1`（第 51 行規範）。
  2. 但在乙的寫法中，`base = ag.load("../reviewer")` 緊接著就是最外層的 `SYSTEM = base.SYSTEM + ...`、`LLM = {**base.LLM, ...}`（在 `ag.main` 被呼叫之前）：
     * 若 `ag.load` 遇到找不到路徑、循環載入（`06` 第 3 條）而在 `ag.load` 內直接 `raise SpecBad`，當時根本還沒進 `ag.main` 的 `try...except SpecBad`，Python 會直接印出未捕捉的 Traceback，違反第 51 行單行錯誤規範；且若在 `ag.load` 內直接 `flags.die`，則在 REPL（`04` 第 312 行）呼叫 `ag.load` 時會把整個 REPL 行程殺掉。
     * 反之，若 `ag.load` 回傳 `{"kind": "bad"}` 假物件，下一行 `base.SYSTEM + ...` 或 `{**base.LLM, ...}` 會在模組最外層直接炸 `AttributeError` / `TypeError` Traceback。
     * 更糟的是，執行 `python3 agent.py --help` 時（`--help` 在 `ag.main` 第 318 行才處理），只要底的路徑不在或環境變數未設，連 `--help` 都會在頂層 `ag.load` 崩潰。
  3. 對照 `06` (a) 第 4 條：「底用的庫根變數沒設……訊息要帶上是哪一支的」——實際上 `agent_spec_lib.py` 第 56～58、78 行在環境變數未設時**不會在 `base` 執行當下報錯**，而是把 `{"kind": "bad", ...}` 塞進 `base.TOOLS` 串列裡，等到衍生那支跑 `defs()` 時才由 `parts.raise_bad` 拋出；`ag.load` 執行當下根本攔不到這個錯誤，除非 `ag.load` 或 `ag.base` 主動掃描並改寫 `base` 內所有 `"kind": "bad"` 的訊息。

---

#### A4. `[MUST-FIX]` `06` (a) 第 5 條誤以為「還原 `sys.path`」就能解決 `import helper` 撞名，忽略了 Python 的 `sys.modules` 快取
* **位置**：`04-設計選項.md`（跟舊裁定的關係：`import helper`）、`06-邊緣狀況與要拍板的題.md` (a) 第 5 條；對照 `templates/agent-python/agent.py` 第 6～10 行。
* **問題**：
  `06` 第 5 條說：「載了底之後底的夾也留在裡面，之後 `import helper` 可能拿到底那夾的同名檔。`ag.load` 載完要把它還原。」
  這在 Python 匯入機制下**不成立**：當底的 `agent.py` 執行了 `import helper`，Python 會把底那夾的 `helper.py` 放進全域的 **`sys.modules["helper"]`**。之後就算 `ag.load` 把 `sys.path` 還原，當衍生那支（或第二個底 `d2`）執行 `import helper` 時，Python 會先命中 `sys.modules["helper"]`，完全不查 `sys.path`，直接拿到底那夾的 `helper` 模組。在 `04` 的「甲（純 Python）」連 `ag.load` 都沒有，更連 `sys.path` 都不會還原。

---

#### A5. `[MUST-FIX]` 筆記宣稱「生出的 json 每格全路徑、跑的時候不需要底那一夾還在」，與 `agent_spec.py` 允許相對路徑的程式碼事實不符
* **位置**：`README.md` 結論 3、`04-設計選項.md`（乙範例第 291 行、生出來的東西第 338 行、跟舊裁定的關係第 361 行）；對照 `py/aos/agent_spec.py` 第 63～64、86、91、121～122 行、`py/aos/apps/tools/registry.py` 第 163、168 行。
* **問題**：
  1. `agent_spec.py` 的 `_is_path(v)`（第 63 行）接受**任何非空字串**（不限於絕對路徑或 `ag.home`/`ag.env` 指示詞）。只有透過 `ag.lib`／`std` 載入的庫工具才會被 `Lib._full`（`agent_spec_lib.py` 第 64 行）轉成全路徑。
  2. 使用者在 `agent.py` 直接寫 `ag.tool("t", "./my_tool", env_file="a.env")` 或 `ag.state("think", ["python3", "think_cached.py"], ...)`（這正是 `04` 第 291 行乙自己的範例與 `agent_spec.py` 第 122 行 docstring 的寫法！）時，`tools.json` 與 `fsm.json` 寫入的就是**相對路徑字串**。
  3. 執行期 `registry.py` 第 163、168 行是相對於「寫有該 `path` 的 `tools.json` 所在資料夾」去解析相對路徑；`aos-fsm` 也是在該定義夾下跑。一旦 `strict-reviewer` 透過 `ag.load("../reviewer")` 抄入 `base.TOOLS`、`base.FSM` 或 `base.HOOKS` 中的相對路徑，寫進 `strict-reviewer/*.json` 後，基準目錄就變成 `strict-reviewer/` 而非 `reviewer/`，執行時就會找不到檔案。

---

#### A6. `[MUST-FIX]` `ag.base(TOOLS, 名)` 缺少 `prefix=`／`rename=`／`exclude=`，導致撞名時錯誤訊息教的解法無法使用，且與 `06` 第 15 條矛盾
* **位置**：`04-設計選項.md`（乙、`ag.base` 規格表第 300 行）、`06-邊緣狀況與要拍板的題.md` (a) 第 15 條；對照 `py/aos/agent_spec_parts.py` 第 103～104 行、`py/aos/agent_spec_lib.py` 第 119 行。
* **問題**：
  1. `agent_spec_parts.py` 第 103～104 行在兩個包工具撞名時報錯訊息寫死為：
     `tool %s comes from both %s and %s, and they differ: rename one (prefix= or rename=), leave one out (exclude=), or pick one with ag.tool(...)`。
  2. `std.pack` 與 `my.pack`（`agent_spec_lib.py` 第 119 行）都有 `prefix=None, rename=None, exclude=None` 三個參數；但 `04` 定義的 `ag.base(TOOLS, 名)` 卻**沒有** `prefix=`、`rename=`、`exclude=`。
  3. `06` (a) 第 15 條說：「兩個 `my_read` 不同＝SpecBad。庫名只在各自那支檔裡有效，撞了由下游 `prefix=` 改。」錯在：若 `d1` 與 `d2` 各自用了不同路徑的 `ag.lib("my", ...)`，`my_read` 這個名字在 `d1.TOOLS` 與 `d2.TOOLS` 宣告當下就已經烤死在字典鍵裡了；下游載入 `d1`、`d2` 時根本不會再呼叫 `ag.lib("my", ...)`，若 `ag.base` 本身不支援 `prefix=`／`rename=`／`exclude=`，下游根本沒地方傳 `prefix=`。
  4. 另外，`tools_json` 第 72 行把包名格式化寫死為 `label = "%s.pack(%r)" % (t["lib"], t["name"])`，若不改 `tools_json`，`ag.base` 也不會如 `04` 第 300 行所言印出 `base('reviewer')`。

---

#### A7. `[MUST-FIX]` 骨架預設沒有 `HOOKS`（及 `META`、`INTERFACES`、`FILES`、無 `FSM` 的 ECA 模式），使 `04` 乙與 `05` 選項 3 的範例直接壞掉或漏欄位
* **位置**：`04-設計選項.md`（乙範例第 290 行、REPL 範例第 313 行）、`05-執行中長出來與定義衍生.md`（選項 3 範例第 419～428 行）、`06-邊緣狀況與要拍板的題.md` (a) 第 6、7 條；對照 `templates/agent-python/agent.py` 第 24～38 行、`py/aos/agent_spec.py` 第 21～25、170～187、238～241 行。
* **問題**：
  1. **骨架預設不定義 `HOOKS`**：`00` 第 71 行明載「骨架不帶 hook（庚 10 末節）」，`templates/agent-python/agent.py` 第 24～38 行只有 `DESCRIPTION`、`SYSTEM`、`TOOLS`、`LLM`、`FSM` 五個變數。但 `04` 乙的主範例第 290 行直接寫 `HOOKS = ag.change(base.HOOKS, "timer", every_ms=60000)`——拿骨架長出來的 agent 當底時，第一時間就會撞 `AttributeError`（`06` 第 6 條雖有提到，但未處理）。
  2. **衍生時靜默遺失 `HOOKS`、`META`、`INTERFACES`、`FILES`**：`05` 選項 3 自動倒出的 `agent.py`（第 419～428 行）：
     * 最後一行**漏寫了 `ag.main(...)`**，執行 `python3 agent.py --write-defs` 什麼都不會做。
     * 完全沒帶 `base` 的 `HOOKS`、`META`、`INTERFACES`、`FILES`。若底原本有 `HOOKS`，倒出來的新定義不僅丟失 `hooks.json`，連 `loop.json` 裡的 `on_start`／`on_stop`（`agent_spec.py` 第 238～241 行：`if hooks is not None:` 才掛 `HOOK_FIRE`）也會整組消失！
  3. **完全漏看無狀態機（`fsm=None`，ECA 版）的 `agent.py`**：
     * `agent_spec.py` 第 22～23、45～47、170～187 行支援不宣告 `FSM` 的 ECA 定義（`ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM)`）。
     * 這類底連 `base.FSM` 變數都沒有（`04` 第 313 行 REPL 與 `05` 第 427 行寫 `base.FSM` 會炸 `AttributeError`）。
     * 且 `fsm=None` 時，`ag.defs(...)` 強制要求傳入已有 `interfaces.json` 的 `folder`（`agent_spec.py` 第 173～175 行），所以 `04` 第 313～315 行 REPL 先對空夾跑 `ag.defs(...)` 再 `ag.write_defs(...)` 在 ECA 模式下必定報 `SpecBad: FSM is not declared ... give its folder`。
  4. **`by_hand` 只想到 `TOOLS`**：`06` 第 7 條只列了「底的 `TOOLS` 是 `ag.by_hand`」，但 `agent_spec.py` 第 19 行明講 `SYSTEM`／`TOOLS`／`LLM`／`FSM`／`HOOKS` 全部都可以是 `ag.by_hand(檔名)`。若底的 `SYSTEM` 是 `ag.by_hand("system.txt")`，`04` 乙寫 `base.SYSTEM + "\n..."` 會直接因 `dict + str` 拋出 `TypeError`；底的 `LLM`、`FSM`、`HOOKS` 為 `by_hand` 時，`{**base.LLM, ...}`（會把 `{"kind": "by_hand", "file": "llm.json"}` 展開混進 `LLM` 字典裡觸發 `SpecBad: LLM key 'kind' is not one of llm_keys`！）、`ag.refit(base.FSM, ...)`、`ag.change(base.HOOKS, ...)` 都會出事。

---

#### A8. `[MUST-FIX]` `05`「收回成新定義」在 `ctl set-def`、相對基準與欄位殘渣上有三處與程式碼矛盾的漏洞
* **位置**：`05-執行中長出來與定義衍生.md` 第 404、413、418～430、436 行；對照 `py/aos/apps/tools/registry.py` 第 99～107、138～171 行。
* **問題**：
  1. **比對基準錯位（`.o` vs `.c`）**：`05` 第 404 行說倒出時要「先算這隻此刻生效的整套，再跟它現在掛的那份定義比，差的才是差異」，然後選項 3（第 419 行）卻生成 `base = ag.load("/ws/agents/reviewer")`。但「現在掛的那份定義」是定義夾裡的 `*.json`（`.o`），而 `ag.load` 載入的是 `reviewer/agent.py`（`.c`）。照 `04` 第 340 行與 `agent_spec.py` 第 4 行，若 `reviewer/agent.py` 改過但未重生，或有人手改過 `reviewer/*.json`，拿生效狀態減去 `.o` 算出來的差異，疊在 `.c`（`ag.load`）上面就會生出錯誤的定義。
  2. **stack 的逐欄修補無法「一格對一行」倒成 `ag.tool`**：`05` 第 430 行稱差異可「機械地一格對一行」轉成 `ag.tool(...)`。但 stack 的 `tools.json` 走的是 `registry.py` 的 `$override` **逐欄合併**（例如 stack 只幫底既有的 `read` 補了一個 `"env": {"X": "1"}`，未寫 `"path"`）；而 `agent.py` 的 `ag.tool` 是**整格換**。倒出時不能只看 stack 檔案本身，必須把合完後的整格（且需取 `registry.py` 第 165、170 行的 `stored` 原文以保留 `{"$env": ...}` 指示詞，不能取展開後的絕對路徑 `path`）整格倒出。
  3. **`05` 第 436 行對 `ctl set-def` 後果的描述自相矛盾**：第 436 行說若對原 agent 跑 `ctl set-def` 改掛倒出的新定義，「那時 stack 裡的差異會**再疊一次**在已經含差異的新定義上（多半無害……），而且工具那份還指著舊定義」。既然 `stack/tools.json` 的 `$override` 還指著**舊定義**，工具那一欄就**根本不會疊在新定義上**，而是繼續疊在舊定義上，導致新定義日後對工具的任何修改對該隻 agent 完全無效（這一點完全不是「多半無害」）。

---

#### A9. `[MUST-FIX]` 與 `00` 所引舊裁定的衝突有漏列與誤判
* **位置**：`04-設計選項.md`（生出來的東西第 339 行、跟舊裁定的關係第 358～368 行）、`06-邊緣狀況與要拍板的題.md` (c) 第 5、6 條；對照 `00-使用者原話.md` 第 62、65、67、70 行。
* **問題**：
  1. **與 C-89 第 4 點（`lineage` 是「原始碼的出處」）的衝突被誤判為「不衝突」**：
     `00` 第 67 行引 C-89：「族譜＝資料夾樹＋出生時寫一次的血緣紀錄（`lineage`），『它是原始碼的出處（像 git 的 fork 紀錄）』」。`02` 第 170 行也指出 `defs/catalog.py` 靠讀 `_metainfo.json` 的 `lineage` 列出定義出處。
     但 `04` 第 339、365 行定調「不碰 `lineage`＝不衝突」，會造成兩種錯亂：
     * 若衍生夾是先用 `agent_def new` 從 `agent-python` 骨架建出、再改 `agent.py` 去 `ag.load("../reviewer")`，因為 `agent_spec.py` 第 277～286 行 `write_defs` 會保留 `_metainfo.json` 既有鍵，`_metainfo.json` 的 `lineage` 會永遠停在錯誤的 `{"template": "agent-python"}`，與 `agent.py` 裡真正的出處 `../reviewer` 打架。
     * 若衍生夾是 `mkdir` 後跑 `agent.py --write-defs`（或 `05` 選項 3 倒出），則 `_metainfo.json` 完全沒有 `lineage`，`defs/catalog.py` 查不到血緣，等於把「原始碼出處」拆成 `_metainfo.json` 與 `grep 'ag.load('` 兩套互不相通的紀錄。
  2. **對 10-14 第 3 題的引文截斷**：
     `00` 第 62 行完整原話為：「不做繼承：沒有 extends、沒有搜尋路徑；**每個 agent 寫整張表，想沿用就一格一格寫範本路徑或 `$ref`；範本資料夾不是父類。**」`04` 第 361 行表格把後半句截掉，宣稱乙「不衝突」。雖然生出的 `fsm.json` 是整張表，但在人寫的 `agent.py` 層，乙的 `ag.refit(base.FSM, ...)` 正是把另一資料夾當父類、不再一格一格寫狀態表（且丁若只用 10-14 原話允許的逐格 `$ref` 其實不違背該句，丁違背的是整張 `fsm.json` 加 `$override`）。
  3. **`ag.change` 用在「工具包」違反 C-56 補充與命名空間第一刀去殘渣的設計**：
     `04` 第 301 行規定 `ag.change`「hook 組、工具包都能用」，第 304 行卻又說「『整格換』是今天唯一的疊法……這樣事實表結論 3 的殘渣不會悄悄發生」。允許對工具包用 `ag.change` 只改 `path`（`06` 第 17 條），正好把 `02` 結論 3 的殘渣問題（留著舊工具的 `cache: false`、`env`、`env_file` 導致 `RegistryBad`）重新引回 `agent.py`（而且生成期 `ag.tool` 只檢查 `cache is not False`，不檢查磁碟上 `path` 是否為資料夾，生成期根本擋不住）。

---

#### A10. `[SUGGEST]` `ag.refit` 與 `ag.change` 粒度不一致：換狀態機一格仍會像 hook 一樣丟掉同格其他設定
* **位置**：`04-設計選項.md` 第 290～291、301～302 行；對照 `py/aos/agent_spec.py` 第 117～141 行（`state`）、`py/aos/agent_spec_lib.py` 第 15～18 行（`STOCK_CELLS`）。
* **問題**：
  筆記在 `01` 第 130 行與 `02` 結論 4 指出 hook「同名整格換會把底那格的 `on_error`、`timeout_ms` 丟掉」，因此為 hook 設計了只改一欄的 `ag.change`。但到了狀態機，`ag.refit(base.FSM, ag.state("think", ...))` 卻要求傳入完整的 `ag.state(name, argv, next, timeout_ms=None)`——也就是**整格換**！若衍生者只想把 `think` 的程式換成 `think_cached.py`（或只想改 `act` 的 `timeout_ms`），用 `ag.refit` 就必須把底那格的 `next` 轉移表（`{0: "wait", 10: "idle"}`）與 `timeout_ms` 全部手動重抄一遍，沒抄就會丟掉或退回 `timeout_ms=None`。

---

### (B) 替代方案與簡化提案（Proposals）

---

#### B1. 偷 Lisp Macro／Nix `overrideAttrs`：不要用 `if __name__ == "__main__":` 跳過 `ag.main`，改由 `ag.main` 在 `ag.load` 時直接攔截整包規格
* **針對**：`04-設計選項.md`（甲、乙）、`templates/agent-python/agent.py` 第 38 行、`py/aos/agent_spec.py` 第 311 行（`main`）。
* **做法**：
  筆記之所以冒出 A3、A7 等一堆邊緣狀況（底沒定義 `HOOKS`／`META`／`INTERFACES`／`FILES` 會 `AttributeError`、ECA 模式沒 `FSM`、行內寫 `ag.main(..., hooks=std.hooks())` 拿不到變數），根源在於讓 `ag.load` 回傳**未結構化的 Python 模組全域變數**，並要求骨架加上 `if __name__ == "__main__":` 跳過 `ag.main`。
  **反過來做更簡單、更強**：
  1. **骨架維持最後一行直接呼叫 `ag.main(...)`，不加 `if __name__ == "__main__":`**。因為 `ag.main(description, system, tools, llm, fsm=None, meta=None, interfaces=None, hooks=None, files=None)` 正是底那支 `agent.py` 把所有 9 個規格欄位交出來的唯一收斂點！
  2. 當 `ag.load("../reviewer")` 執行底的 `agent.py` 時，在 `agent_spec` 內部設一個載入堆疊（`_loading` stack）。當底跑到最後一行 `ag.main(...)` 時，`ag.main` 發現目前處於 `_loading` 中，**不解析 `sys.argv`、不寫檔、不 `sys.exit`**，而是把收到的 9 個參數連同底的資料夾路徑封裝成一個正規化的 `Spec` 物件存入 `_loading`，即可返回。
  3. **好處**：
     * 舊的 `agent.py` 一行都不用改就能當底。
     * `base` 保證擁有全部 9 個正規化屬性（底沒傳 `hooks` 時 `base.HOOKS` 為 `None` 或 `{}`、不會炸 `AttributeError`；`base.META`、`base.INTERFACES`、`base.FILES`、`base.FSM` 皆齊全）。
     * 更可偷 Nix 的 `overrideAttrs`：提供 `base.derive(system=..., tools=..., ...)` 或讓 `ag.main` 接受 `base=`，**沒寫的欄位（如 `HOOKS`、`META`、`INTERFACES`、`FILES`、`FSM`）自動沿用 `base`**，不必像 `04` 乙或 `05` 選項 3 那樣每次手動把 9 個變數全傳一遍還漏掉後四個。

---

#### B2. 四個小幫手可以縮減為 **1 個**（只留 `ag.load`）：把 `ag.base`、`ag.change`、`ag.refit` 折進現有語法與 Python 原生操作
* **針對**：`04-設計選項.md` 的四個幫手（`ag.load`、`ag.base`、`ag.change`、`ag.refit`）；對照 `py/aos/agent_spec.py` 第 144 行、`py/aos/agent_spec_parts.py` 第 61、155 行、`py/aos/agent_spec_lib.py` 第 157 行。
* **做法**：
  1. **拿掉 `ag.base`（讓 `TOOLS` 直接收巢狀串列或 `base.tools(...)`）**：
     * 在 `agent_spec_parts.py` 的 `tools_json(tools)`（第 66 行）中，現在遇到串列裡的項目是 `list`/`tuple` 會報 `SpecBad`。只要讓 `tools_json` 遇到子串列（例如 `TOOLS = [base.TOOLS, ag.no("write"), ag.tool("read", ...)]`）時，自動把該子串列先遞迴解成一張底表（一個隱含的 pack），就完全不需要 `ag.base(base.TOOLS, "reviewer")` 這個多餘的函式與手動填的名字字串！
     * 若搭配 B1 的 `base` 物件，需要改前綴或排除工具時直接呼叫 `base.tools(prefix=..., rename=..., exclude=...)`，簽名與 `std.pack`（`agent_spec_lib.py` 第 119 行）完全一致，順手解決 A6。
  2. **拿掉 `ag.change`（讓 `std.hooks()` 與 `base.HOOKS` 本身就是可索引的 `dict`）**：
     * `04` 甲的第 274 行之所以寫出醜陋的 `std.hooks()["hooks"]["timer"]`，唯一原因是 `agent_spec_lib.py` 第 178 行把 `std.hooks()` 包成了 `{"kind": "stock_hooks", "template": ..., "hooks": table}`。
     * 只要讓 `std.hooks()` 回傳一個繼承自 `dict` 的小類別（本身就是 `{hook名: 格}` 的字典，僅多帶一個 `.template` 屬性供 `hooks_json` 寫 description），且 `base.HOOKS` 在 `ag.load` 時已展開為 `{hook名: 格}` 的字典，那麼在純 Python 裡改一欄就是直覺的 `{**base.HOOKS["timer"], "every_ms": 60000}`（就像 `04` 改 `LLM` 寫 `{**base.LLM, "model": "luna"}` 一樣！），完全不必為 hook 發明 `ag.change`，也不會把 `ag.change` 誤開給工具包而重新引入欄位殘渣（A9-3）。
  3. **拿掉 `ag.refit`（讓 `ag.fsm` 直接像 `HOOKS` 一樣收底的 `FSM`）**：
     * 在 `agent_spec.py` 第 144 行，目前 `ag.fsm(start, states)` 只收 `(起點字串, [ag.state...])`。
     * 只要讓 `ag.fsm` 的 `states` 串列也能像 `HOOKS` 收 `std.hooks()` 一樣，接受一張既有的 `FSM`（如 `ag.fsm(base.FSM, [ag.state("think", ...)], drop=())`，第一參數若給 `base.FSM` 則沿用其 `start`，若給字串則換 `start`），並在 `ag.state` 允許對底的同名格只覆蓋有傳的參數（如 `next=None` 時沿用底那格的 `next`，解決 A10），就能直接複用 `ag.fsm`，不必多記一個 `ag.refit`。

---

#### B3. 偷 Docker Whiteout（墓碑標記）：修補菱形刪除被蓋回的漏洞，並支援跨資料夾相對路徑改寫
* **針對**：`py/aos/agent_spec_parts.py` 第 61～110 行（`tools_json`）、第 155～185 行（`hooks_json`）。
* **做法**：
  1. **保留刪除墓碑（Whiteout）**：在 `03-別人怎麼做.md` 第 206 行提到了 Docker 的 whiteout 檔，但乙沒有採用。在把底（`base.TOOLS` 或 `base.HOOKS`）解成來源表時，被 `ag.no("write")` 或 `{"timer": None}` 刪除的項目**不要從來源表直接 `pop` 消失，而是記為 `{"write": None}`（墓碑）**，直到最頂層輸出最終 `tools.json`／`hooks.json` 前才把值為 `None` 的鍵濾掉。
     這樣在菱形 `[d1, d2]` 中，`d1` 的 `"write"` 是 `None`，`d2` 的 `"write"` 是 `{"path": ...}`，`tools_json` 第 102 行的 `if other != entry:` 就能立刻抓出「一邊刪了 `write`、一邊留著 `write`」的衝突並報 `SpecBad`，頂層明寫 `ag.no("write")` 或 `ag.tool("write", ...)` 即可消歧。
  2. **跨夾載入時正規化相對路徑**：比照 `agent_spec_lib.py` 第 64～71 行的 `Lib._full`，當 `ag.load(路徑)` 從別的資料夾載入底時，自動將底裡寫的相對路徑（或對未用 `ag.env`／`ag.home` 的裸相對路徑報 `SpecBad` 提示改用指示詞）按底的資料夾換算，徹底消除 A5 的「生出 JSON 含相對路徑、換夾就壞」。

---

#### B4. 偷 Docker Writable Layer／Smalltalk Image：修掉 `stack/tools.json` 寫死舊定義路徑的根因，讓執行期疊層與 `05` 收回真正對齊
* **針對**：`02-現況事實表.md` 結論 1 與 D1／G1、`05-執行中長出來與定義衍生.md` 第 404、436 行。
* **做法**：
  1. `02` 與 `05` 反覆提到一個大坑：`ctl set-def` 換定義後，`stack/llm.json` 與 `stack/hooks.json` 都會自動疊在新定義上，唯獨 `stack/tools.json` 因為在第一次 `tools add` 時寫死了 `{"$override": ".../舊定義/tools.json"}` 絕對路徑，導致換定義後工具還借舊定義。
  2. 與其在 `05` 倒出工具裡繞過這個坑，不如直接讓 stack 的 `tools.json` 跟 `hooks.json`、`llm.json` 一致：**stack 的 `tools.json` 只存差異（或用指向「當前掛載定義夾」的符號／由讀表的 `brain.py` 自動把當前定義的 `tools.json` 當底疊上 `stack/tools.json`）**，不再把建立當下的舊定義絕對路徑寫死在 `stack/tools.json` 裡。
  3. 這樣一來：
     * `ctl set-def` 後工具會自然疊在新定義上（消滅 `02` 結論 1 的第三項與 `05` 第 404、436 行的坑）。
     * `stack/` 下的四份檔案（`tools.json`、`hooks.json`、`llm.json`、`system.txt`）就成為純粹的 **Docker 可寫層（純差異／Smalltalk change set）**：`05` 的選項 1（看跟定義差在哪）與選項 3（倒成幾行 `agent.py`）只需直接讀取 `stack/` 這幾份差異檔（取其未展開指示詞的原文，並將欄位修補合入底的對應格），不需反推整份展開後的表。
