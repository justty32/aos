# 庚設計稿與第一刀程式送 Argon（Gemini 4 Argon High）事後審的原文：兩次送件各一份回覆，未改字

← [12-Argon審與採納](12-Argon審與採納.md)（逐點採納表在那份；這份只存原文，裡面的判斷未經核實，以 12 為準）

線 geng-argon-1119，11-19 早。送法：Windows 的 agy，在暫存空夾跑，--model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s；提示太長（6.3 萬、4.9 萬字）超過 Windows 命令列上限，改用 --input-format stream-json 從 stdin 送一則 {"event":"user","message":{...}}（搭 --output-format stream-json 與 --print=）。兩次各一輪、沒叫任何工具。第一次貼 HEAD 的設計稿 README、01～08、10、11（09 略，已併在 10）；第二次貼第一刀施工紀錄、骨架 agent.py、HEAD 的 agent_spec.py（cat -n）。兩次都把「C 與 .o」與六題裁定寫成不能推翻的前提。

## 第一次：設計稿

以下是在「C 與 .o」前提與六題裁定下，對設計稿「庚」的審查意見、範圍切法提案，以及因未見程式碼原文而最沒把握的三點。

---

## (A) 審查：漏洞、盲點與會出事的邊緣狀況

### A1（一定要改）：只用 `ag.pack()` 時生出的 `tools.json` 結構，可能直接被 `defs check` 判 `DefBad`
* **位置**：`04-agent-py-兩個例子.md`「最小例子」表格、`03-agent-py-長相.md`「宣告與生成檔的對照」vs `02-現況-定義夾與agent_def.md`「check（查一份定義）」
* **會發生什麼**：
  1. 稿 `02` 寫明 `defs/catalog.py` 查工具檔時要求 **`tools must contain an object`**（即 `tools.json` 內必須有 `"tools": {...}` 這個字典）。但稿 `04` 最小例子的表格卻寫：`tools.json` 內容為 `{"$override": [look、mailbox、json 三包的指示詞]}`（沒有 `"tools": {}`）。由於最小例子就是第一刀的 `templates/agent-python/agent.py`，若沒生出 `"tools": {}`，**第一刀驗收第 1 條（跑 `agent_def check` 回 `{"problems": []}`）極可能當場失敗**（推測，視 `catalog.py` 是否在有 `$override` 時仍強制檢查 `"tools"` 鍵而定）。
  2. 稿 `03` 允許 `ag.no("名")`（從包裡拿掉工具），也規定「TOOLS：每個工具有路徑、名字不重複」。但：
     - `ag.no("名")` 在 `tools.json` 裡必然沒有路徑（推測是寫成 `"tools": {"名": null}` 或類似結構），若 `catalog.py` 先跑 `each tool must declare a path` 才跑 `aos-tools ls -l` 合併，或使用者在沒寫 `ag.pack()` 時單寫了 `ag.no("名")`，檢查就會炸開。
     - 若同一個 `TOOLS` 串列裡同時出現 `ag.tool("foo", ...)` 與 `ag.no("foo")`，或重複 `ag.pack("look")` 兩次，稿 `03` 未定義這算不算名字重複（`SpecBad`）。
     - 若 `ag.pack("不存在的包名")` 寫錯包名，`agent.py` 生成時若不檢查包名是否合法，生完跑 `agent_def check` 會在 `aos-tools ls -l` 合併時報 `cannot merge …`，違反稿 `03`「lib 先查的 ⊇ `defs check` 查的」。
* **怎麼改**：
  1. `tools.json` 無論有沒有單獨宣告 `ag.tool()`，一律固定帶 `"tools": {}`（有 `$override` 時再加 `"$override": [...]`）。
  2. 在 `agent_spec` 生成前檢查：`ag.tool` 與 `ag.no` 不可同名（同名報 `SpecBad`）；`ag.no` 不能在完全沒有 `ag.pack` 時單獨出現；`ag.pack` 若是內建包短名，先驗該包名格式（或在 `$AOS_HOME` 存在時驗路徑可解）。

---

### A2（一定要改）：多檔寫入的暫存與 `os.replace` 順序沒定，會讓正在跑的 agent 或檢查工具讀到「有索引、沒目標檔」或「磁碟滿留半套」
* **位置**：`01-現況-工具版tool_spec.md`「怎麼重生」、`05-打架規則-總則.md`「寫檔的兩條保證」、`07-邊緣狀況.md`「一、重生到一半失敗」與「二、定義正被跑著的 agent 使用時重生」
* **會發生什麼**：
  1. 稿 `01` 說沿用 `tool_spec` 的 `_write_file`（每寫完一個 `.tmp-<pid>` 就立刻 `os.replace` 一個），但稿 `07` 第二節又說「所有改名排在最後連著做」。這兩種做法在磁碟滿（`ENOSPC`）時結果完全不同：如果是寫一個換一個，寫到第 4 份磁碟滿就會留下「3 份新、5 份舊」；而且失敗時留下的 `.<名>.tmp-<pid>` 隱藏檔，下次被 `agent_def new` 整夾複製時會一起被抄走（稿 `02` 寫明 `new` 只略過 `__pycache__`）。
  2. **改名（`os.replace`）的先後順序有嚴重 race**：在 `aos` 中，`interfaces.json` 是所有工具與執行中 agent 找檔的「總索引」（`def_edit.py`、每次問腦、`defs check`、`agent_def new` 認範本都先讀 `interfaces.json`）。如果在空夾第一次重生、或改了介面時，**先把 `interfaces.json` 換上去，後換 `tools.json`／`llm.json`／`system.txt`**，在兩次 `os.replace` 之間剛好問腦或跑 `defs check`，就會讀到 `interfaces.json` 已經指過去、但目標檔還不存在（或還是舊版）。`_entry` → `body.json` → `loop.json` → `fsm.json` 的指涉鏈同理。
* **怎麼改**：
  1. **嚴格兩階段寫檔**：
     - 第一階段（Stage）：把所有要寫的檔全部先寫成 `.<名>.tmp-<pid>` 並 flush。若這一階段任何一檔失敗（如磁碟滿、權限不足），在 `except` 把已建好的 `.tmp-<pid>` 全數 `unlink` 刪乾淨，再報 `WriteFailed`。這樣連磁碟滿都能保證「夾裡原本的 json 一份都不會壞」。
     - 第二階段（Commit）：所有 `.tmp-<pid>` 都寫成功後，才集中跑一輪 `os.replace`。
  2. **定死 `os.replace` 順序（由被指的葉節點往索引節點換）**：
     - 先換內容與肉的目標檔：`system.txt`、`tools.json`、`llm.json`、`fsm.json`、（第三刀的 `FILES`、`hooks.json`）。
     - 再由下往上換執行骨架：`loop.json` → `body.json` → `_entry`。
     - **最後才換總索引與說明**：`interfaces.json` → `_metainfo.json` → `README.md`。

---

### A3（一定要改）：各份 json 的 `"description"` 欄位在稿 `03` 與稿 `04` 互相矛盾，且會讓第三刀的 `reviewer` 等價驗收永遠過不了
* **位置**：`03-agent-py-長相.md`「宣告與生成檔的對照」（`DESCRIPTION` 列）vs `04-agent-py-兩個例子.md`「最小例子」與「完整例子：reviewer」
* **會發生什麼**：
  1. 稿 `03` 表格寫：`DESCRIPTION` 會生出「`_metainfo.json` 的 `summary`；**各份 json 的 `description`**；`README.md` 不在時種一份」。
  2. 但稿 `04` 卻寫：「每份 json 帶一個 `description`（**照 reviewer 範本的慣例，說這份檔是做什麼的**）」，而且稿 `04` 與稿 `08` 都把「`reviewer` 重生出來的 8 份 json 跟今天手寫的那 8 份等價」當作第三刀驗收。
  3. 矛盾在於：`reviewer` 的 `agent.py` 裡只有**一個** `DESCRIPTION` 字串（描述這隻 agent 做什麼），而手寫的 `templates/reviewer/*.json` 裡每份檔的 `"description"` 寫的是**那份檔自己的用途**（例如 `llm.json`、`fsm.json`、`loop.json` 各自不同）。如果把 `DESCRIPTION` 塞進每份 json 的 `"description"`，8 份檔的 `"description"` 全都變成 agent 的簡介，既不是「說這份檔是做什麼的」，也跟手寫的 `templates/reviewer/` 對不上；反之，如果由 lib 寫死每種檔的固定英文說明，稿 `03` 的表格就寫錯了，而且 `agent-fsm` 範本的 `llm.json` 今天是 `{}`（完全沒有 `"description"` 鍵，見稿 `02`）。
* **怎麼改**：
  從兩條路選一條定死（建議選 1）：
  1. **只把 `DESCRIPTION` 寫進 `_metainfo.json` 的 `"summary"` 與種子 `README.md`**，其他生成的 json（`llm.json`、`body.json` 等）**不要塞 `"description"` 廢話鍵**（或只在骨架固定檔放固定的單行角色說明，不拿 `DESCRIPTION` 去填）。第三刀比對 `reviewer` 等價時，明講比對的是語意欄位（或忽略 `"description"` 註解鍵）。
  2. 若真要在每份 json 放固定說明，請修正稿 `03` 表格，明講各份 json 的 `"description"` 是 lib 內建的各檔用途固定字串，不是 `DESCRIPTION` 常數。

---

### A4（一定要改）：`_metainfo.json` 與 `README.md` 依賴目標夾既有檔案，與「`--defs` 純計算／寫檔分離」矛盾，且缺了壞檔的型別檢查與錯誤代號
* **位置**：`03-agent-py-長相.md`「重生時每份檔怎麼寫」與「命令列與函式兩種用法」、`05-打架規則-總則.md`「錯誤代號」、`07-邊緣狀況.md`「五、另外挖到的 第 2 條」
* **會發生什麼**：
  1. 稿 `03` 規定 lib 分成「算出全部內容（回 `{"檔名": 內容}`）」與「寫進某個夾」兩個函式，且 `--defs` 不帶資料夾參數、只印出會生成的全部內容。但 `_metainfo.json` 的規則是「只設自己的鍵，其他鍵（如 `lineage`）原樣留著」，`README.md` 是「不在的時候才寫」。
     - 如果「算出全部內容」不讀目標夾，它算出來的 `_metainfo.json` 就沒有目標夾既有的 `lineage`，且永遠包含 `README.md`；
     - 如果留到「寫進某個夾」才去讀目標夾的 `_metainfo.json`，一旦目標夾的 `_metainfo.json` 壞掉（稿 `07` 五之 2），就會在「開始寫檔的階段」才報錯，這時若前面已經寫了別的檔，就違反稿 `05`「全部算好、驗完才動筆，夾裡一個字都沒動」。
  2. 稿 `07` 五之 2 說「`_metainfo.json` 壞掉（不是合法 json）：重生時報錯、不覆蓋它」，但：
     - **如果 `_metainfo.json` 是合法 JSON，但不是 JSON object**（例如裡面寫了 `[]` 或 `"abc"` 或 `null`），只抓 `JSONDecodeError` 會在後面設 `meta["summary"]` 時噴 Python 原生 `TypeError` traceback。
     - **這時該報什麼錯誤代號？** 稿 `05` 說「錯誤代號只有一個新的：`SpecBad`（結尾 fix the declaration in agent.py），寫檔失敗沿用 `WriteFailed`」。但 `_metainfo.json` 壞掉不是 `agent.py` 宣告寫錯（報 `SpecBad` 會誤導人去改 `agent.py`），也不是寫不進磁碟（`WriteFailed`），稿 `07` 提到 `agent_def new` 用的是 `DefBad`，但稿 `05` 沒把 `DefBad` 列進 `agent.py` 可出的代號。
* **怎麼改**：
  1. 在「寫進某個夾」動筆建任何暫存檔**之前**，先檢查目標夾是否存在且為資料夾、以及既有的 `_metainfo.json`（若存在）是否能 parse 成 `dict`。檢查不過一律在動筆前退出。
  2. 補齊既有檔案壞掉的錯誤代號（建議沿用 `DefBad` 並在稿 `05` 補列：當目標夾的既有 `_metainfo.json` 不是合法 JSON object 時報 `DefBad`）。
  3. 明定「算出全部內容」函式可選收 `target_dir=None`（或 `--defs [資料夾]`）：有給夾就連既有 `_metainfo.json` 的保留鍵與 `README.md` 是否已存在一起反映；沒給夾就回傳純粹由 `agent.py` 宣告算出的基準內容。
  4. `META` 字典裡應禁止使用者手寫 `"summary"` 鍵（報 `SpecBad` 請他寫在 `DESCRIPTION`），以免 `META` 把 `DESCRIPTION` 蓋成空字串。

---

### A5（一定要改）：`DESCRIPTION` 含換行或既有 `README.md` 首行為空時，生成會過但 `agent_def check` 會紅燈
* **位置**：`02-現況-定義夾與agent_def.md`「check（查一份定義）」、`03-agent-py-長相.md`「三個設計決定 → 三」、`08-範圍切法.md`「驗收看什麼 第 1 條」
* **會發生什麼**：
  1. 稿 `03` 說生成前只驗「`DESCRIPTION` 非空」。如果使用者寫了多行字串或開頭換行：
     ```python
     DESCRIPTION = """
     Look things up in the workspace.
     """
     ```
     `DESCRIPTION` 非空檢查會過，但拿它去種 `README.md` 時，**`README.md` 的第一行會是空行**。接著跑 `agent_def check` 就會報 `README.md first line must be nonempty`（見稿 `02`），違反稿 `03`「lib 先查的 ⊇ `defs check` 查的」。
  2. 同理，如果使用者在空夾先 `touch README.md`（0 bytes 空檔），再跑 `python3 agent.py --write-defs`，因為「`README.md` 在了就不碰」，重生完跑 `agent_def check` 一樣會報 `README.md first line must be nonempty`。
  3. 稿 `02` 寫明 `defs check` 第一條就是查夾名 `definition folder name … must match [a-z0-9_-]+`，稿 `03` 的生成前檢查表卻沒提夾名。
* **怎麼改**：
  1. 生成前檢查要求 `DESCRIPTION` 必須是 `str`、`strip()` 後非空、且**不可包含換行符號 `\n` 或 `\r`**（或開頭不得為空白／換行），否則報 `SpecBad`。
  2. `README.md` 的種子規則改為：「不在，**或雖然在但檔案為 0 bytes（全空）** 時，用 `DESCRIPTION + "\n"` 寫入；已有非空內容就不碰」。

---

### A6（一定要改）：`FSM` 與路徑小工具的生成前檢查漏了 5 個 Python／JSON 邊緣陷阱
* **位置**：`03-agent-py-長相.md`「宣告與生成檔的對照」與「三個設計決定 → 三」、`04-agent-py-兩個例子.md`「完整例子：reviewer」
* **會發生什麼**：
  1. **重複的格名（State name）**：`ag.fsm("idle", [ag.state("idle", ...), ag.state("idle", ...)])` 若同一個列表裡宣告了兩個同名格，轉成 `fsm.json` 字典時後者會無聲吃掉前者。
  2. **Python 的 `bool` 是 `int` 的子類別**：在 Python 中 `isinstance(True, int)` 為 `True`，且 `True == 1`、`False == 0`。如果檢查結束碼只寫 `isinstance(k, int) and 0 <= k <= 255`，或檢查 `timeout_ms` 只寫 `isinstance(t, int) and t >= 0`，使用者誤傳 `True`/`False` 會通過檢查並變成 `1`/`0`。
  3. **結束碼 `0`（int）與 `"0"`（str）撞鍵**：在 Python 裡 `{0: "think", "0": "idle"}` 是兩個不同的鍵，但序列化成 JSON object 時鍵一律是字串 `"0"`，會無聲覆蓋或行為未定義。
  4. **`ag.state` 的 `argv` 與 `timeout_ms` 未列進稿 `03` 檢查表**：稿 `04` 出現了 `timeout_ms=0`，但稿 `03` 的檢查表沒寫要驗 `timeout_ms`（必須為非負整數）與 `argv`（必須為非空 list，且每個元素必須為非空字串或合法的 `$env`/`$path` 指示詞 dict），寫錯要到 `aos-fsm` 起跑才報 `CfgBad`。
  5. **`ag.home()` 與 `ag.env()` 的 `$path` 漏寫開頭斜線 `/`**：稿 `03` 舉例 `ag.home("/lib/tools/base/read")` 吐 `{"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}`。若使用者少打斜線寫成 `ag.home("lib/tools/base/read")`，`aos` 解指示詞時（見稿 `02` `DirectiveBad`）極可能報錯或拼出錯誤路徑。
* **怎麼改**：
  在 `agent_spec.py` 補齊這 5 條 `SpecBad` 檢查：
  1. `ag.fsm` 內 state 名字不得重複、必須是非空字串。
  2. 凡檢查 `int` 處一律加 `and not isinstance(x, bool)`。
  3. 結束碼只接受 `int`（`0 <= k <= 255`）或字串 `"*"`（若也允許數字字串 `"0"`～`"255"`，必須先轉字串再檢查是否撞鍵）。
  4. `argv` 驗非空串列與元素型別；`timeout_ms` 若有傳，驗 `int >= 0`。
  5. `ag.home(path)` 與 `ag.env(var, path)` 驗 `path` 必須以 `"/"` 開頭（或自動補 `"/"`，建議不一致就報 `SpecBad` 講清楚）。

---

### A7（一定要改）：`ag.by_hand()` 的適用範圍在稿 `03` 與稿 `06` 寫法不一致，且未擋 `../` 路徑穿越
* **位置**：`02-現況-定義夾與agent_def.md`「check」、`03-agent-py-長相.md`「宣告與生成檔的對照」與「三個設計決定 → 二」、`06-打架規則-逐條.md`「第 5 條」
* **會發生什麼**：
  1. 稿 `03` 對照表裡，只有 `SYSTEM` 一欄寫了「字串；或 `ag.by_hand("system.txt")`」。但稿 `06` 第 5 條卻寫：「原本手寫的 `tools.json`、`fsm.json` 等會被整份換掉，不問……不想被蓋的檔用 `ag.by_hand("檔名")`」，README 第 7 點也這樣寫。
     - 如果有人真的寫 `FSM = ag.by_hand("fsm.json")` 或 `TOOLS = ag.by_hand("tools.json")`：請問 `FSM = ag.by_hand("fsm.json")` 算不算「有宣告 `FSM`」？要不要生 `_entry`、`body.json`、`loop.json`、`interfaces.json`？（`loop.json` 裡面寫死了跑 `fsm.json`，若寫 `ag.by_hand("my_fsm.json")` 則 `loop.json` 也得跟著改！）
  2. 稿 `02` 寫明 `defs check` 要求 `aos-agent.system must name a text file by a relative path inside the definition`。如果有人寫 `ag.by_hand("../system.txt")` 或 `ag.by_hand("/etc/passwd")`，生成時不擋，`agent_def check` 就會報 `DefBad`。同理，第三刀的 `FILES = {"../foo.json": {}}` 若不擋 `..` 與絕對路徑，更會直接把檔案寫到定義夾外面去。
* **怎麼改**：
  1. **明確界定 `ag.by_hand()` 能放在哪幾個宣告**：
     - 最乾淨的做法：第一刀 `ag.by_hand` **只開放給 `SYSTEM`、`TOOLS`、`LLM`**（它們在 `interfaces.json` 的 `aos-agent` 裡都有對應的檔名欄位，轉手把檔名填進 `interfaces.json` 並跳過不寫該檔即可），**不開放給 `FSM`**（或若開放給 `FSM`，明定仍生骨架、`loop.json` 指到該檔名）。稿 `03` 與稿 `06` 寫法要統一。
  2. `ag.by_hand(filename)`（以及第三刀 `FILES` 的鍵）強制檢查：必須是定義夾內的相對路徑（非空、不可為 `.` 或 `..`、不可含 `..` 路徑段、不可為 `/` 開頭的絕對路徑），否則報 `SpecBad`。

---

### A8（一定要改）：`INTERFACES` 字典合併的保護欄未定義，容易洗掉 `aos-agent` 必填鍵或與 `LLM` 檢查打架
* **位置**：`03-agent-py-長相.md`「宣告與生成檔的對照」與「三個設計決定 → 三」、`04-agent-py-兩個例子.md`「完整例子：reviewer」
* **會發生什麼**：
  稿 `04` 的 `reviewer` 寫了：`INTERFACES = {"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}`，並說明 `"history": None` 表示把預設有的鍵拿掉。這裡有三個潛在 bug：
  1. **必須是對第二層 dict 做合併（不能直接 `dict.update`）**：如果對頂層 dict 直接 `.update(INTERFACES)`，`"aos-agent"` 整格會變成 `{}`，把預設的 `entry`、`tools`、`llm`、`llm_keys`、`system` 全部洗掉。
  2. **把必填鍵設成 `None` 或改了檔名**：如果使用者寫 `INTERFACES = {"aos-agent": {"tools": None}}` 或 `{"aos-agent": None}`，生出來的 `interfaces.json` 過不了 `defs check`（`aos-agent must be an object`、`aos-agent.tools must name a file`）。又如果使用者寫 `INTERFACES = {"aos-agent": {"tools": "my_tools.json"}}`，但 `agent.py` 卻還是寫往 `tools.json`，`my_tools.json` 就不存在。
  3. **`llm_keys` 的檢查順序**：稿 `03` 說要驗「`LLM` 的 key 在 `interfaces.json` 的 `llm_keys` 裡」。若使用者透過 `INTERFACES` 擴充或修改了 `aos-agent.llm_keys`，`LLM` 必須對著**合併後的 `llm_keys`** 檢查，而不是對著預設的 `llm_keys` 檢查。
* **怎麼改**：
  1. `INTERFACES` 合併採兩層字典合併，值為 `None` 時刪除該鍵。
  2. 合併完成後，對最終的 `interfaces.json` 結構做生成前檢查：`aos-agent` 必須仍為 dict，且 `tools`、`llm`、`system`、`llm_keys` 等核心鍵不得被刪掉；`LLM` 的鍵對著合併後的 `llm_keys` 驗證。

---

### A9（建議）：「寫錯先記著、等 `main` 報 `SpecBad`」若用模組全域串列，會在 Python REPL（稿 11）與測試裡跨次污染
* **位置**：`01-現況-工具版tool_spec.md`「怎麼宣告」、`03-agent-py-長相.md`「三個設計決定 → 三」與「命令列與函式兩種用法」、`11-跟除錯那條線的接點.md`「庚這邊可能要預留的」
* **會發生什麼**：
  `tool.py` 永遠是一支腳本作為單一 subprocess 跑完就退出，所以就算 `tool_spec.py` 用模組全域變數 `_errors = []` 記住 `ts.param()` 的錯也不會出事。但稿 `03` 與稿 `11` 特意要求：`agent_spec.py` 的「算出全部內容」與「寫進某個夾」要能當成一般函式在 **Python REPL（`>>>`）** 裡直接呼叫，而且 `test_agent_spec.py` 也會在同一個 Python 行程裡連續測好幾組正確與錯誤的宣告。
  如果 `ag.state()`、`ag.tool()` 把錯誤記在 `agent_spec` 模組的全域 list 裡，使用者在 REPL 打錯一次 `ag.tool(...)` 得到 `SpecBad` 後，接下來打的所有正確呼叫都會一直報上一次留下的 `SpecBad`！
* **怎麼改**：
  - **不要用模組全域變數累積錯誤**。讓 `ag.tool()`、`ag.state()`、`ag.fsm()`、`ag.home()`、`ag.by_hand()` 在參數有錯時，把錯誤訊息包在它回傳的物件／dict 裡（例如 `{"$spec_error": "..."}` 或小 dataclass），最後由「算出全部內容」的函式掃描傳入的 `DESCRIPTION, SYSTEM, TOOLS, LLM, FSM...` 樹，收集所有錯誤並報出（或丟出帶 `SpecBad` 的例外由 `ag.main` 印一行退 1）。這樣在 REPL 與單元測試中完全無狀態、零污染。
  - 順帶注意：在 REPL 呼叫「寫進某個夾」時，`sys.argv[0]` 是 `""` 或 `"-c"`，所以單獨呼叫的寫檔函式**必須強制要求傳入目標資料夾路徑**，只有 `ag.main()` 的 `--write-defs` 才拿 `sys.argv[0]` 所在資料夾當預設值。

---

### A10（建議）：跨平台／雙機 git「一字不差」與 `_metainfo.json` 刪鍵殘留的細節
* **位置**：`03-agent-py-長相.md`「重生時每份檔怎麼寫」、`07-邊緣狀況.md`「四、兩台機器經 git 同步」、`08-範圍切法.md`「驗收看什麼 第 4、5、7 條」
* **會發生什麼**：
  1. 稿 `07` 要求兩台機器生成結果一字不差，但沒規定寫檔時的 `encoding="utf-8"`、`newline="\n"` 與檔尾單一 `\n`。若有人在 Windows / WSL 混用或不同 locale 下跑，換行符或檔尾有無 `\n` 會造成整份檔 git diff。
  2. 新建檔案若用 `tempfile` 預設權限是 `0600`，而 git 裡現有範本 json 是 `0644`（受 umask 控制）；稿 `01` 說「沿用舊檔的權限位」，但**空夾第一次生成時沒有舊檔**，若沒給 `0644`（扣 umask），生出來的 json 權限會過嚴。
  3. 稿 `03` 規定 `_metainfo.json`「只設自己的鍵（`summary`、`META` 給的），其他鍵原樣留著」。這有一個必然後果稿裡沒提：**如果使用者原本在 `agent.py` 寫了 `META = {"cost": ...}` 並重生過，後來把 `agent.py` 的 `META` 刪掉再重生，`_metainfo.json` 裡的 `"cost"` 會永遠留在裡面刪不掉**（因為不記帳，lib 分不出 `"cost"` 是上次 `META` 生的還是別人手寫的）。
* **怎麼改**：
  1. 寫檔統一 `encoding="utf-8", newline="\n"`，`json.dumps(..., indent=2, ensure_ascii=False) + "\n"`。新建檔案沒舊檔時預設權限用 `0o666 & ~umask`。
  2. 在骨架 `README.md` 或稿 `07` 第五節「拿掉宣告後留下的舊檔」旁補一句：從 `META` 拿掉的鍵也跟拿掉的檔案一樣，不會自動從 `_metainfo.json` 刪除，要刪自己刪。

---

## (B) 提案：更好的範圍切法與第三刀以後的注意事項

### B1（一定要改）：把第二刀「`agent_def check` 順手重生」直接砍掉（移進「明講不做」），不要留「待定」
* **位置**：`08-範圍切法.md`「之後幾刀 → 二」與「明講不做的」、`10-使用者裁定.md`「裁定之後冒出來的一件事」
* **理由**：
  1. 稿 `10` 末節已經發現：若 `agent_def check` 順手重生，那用 `agent_def tools add` 加完工具後一跑 `agent_def check`，剛加的工具就無聲被蓋掉。
  2. 更根本的原因是：**`agent_spec` 跟 `tool_spec` 的前提不同**。在 `tool_spec`（稿 `01`），`tools_def add_tooldef` 看到檔案已存在會報 `PathExists` 拒絕修改，所以 `tool.py` 是唯一寫入者，`tools_def check` 順手重生不會覆蓋任何正規指令的改動；但在 `agent_spec`（稿 `10` 第 2 題），負責人已裁定 **`agent_def tools/llm/system` 照常直接改 `.json`（即允許直接改 `.o`）**。既然允許正規工具直接改 `.o`，那麼身為**唯讀檢查工具**（稿 `02` 明寫 `defs` 所有 op 唯讀）的 `check` 就**絕對不能偷跑編譯器把 `.o` 蓋掉**，而且 `check` 偷跑任意 `agent.py` 也有副作用風險。
* **怎麼改**：
  把稿 `08` 的第二刀直接刪除，放進「明講不做的」表格（理由：檢查工具應保持唯讀，且與第 2 題裁定 `agent_def tools/llm/system` 可改 json 直接衝突；重生永遠是明講的 `python3 agent.py --write-defs`）。

---

### B2（建議）：第一刀再瘦身——把 `INTERFACES`（以及 `META`）移到第三刀跟 `FILES` 及 `reviewer` 驗收一起做
* **位置**：`08-範圍切法.md`「第一刀的範圍說明」與「之後幾刀 → 三」、`04-agent-py-兩個例子.md`
* **理由**：
  1. 第一刀的目的是「空夾放一支二十來行的 `agent.py` → 打一行 → 掛上去」（最小例子 / `templates/agent-python/`）。最小例子根本沒用到 `INTERFACES` 與 `META`，連稿 `08` 第一刀的 7 條驗收標準裡也完全沒測 `INTERFACES` 與 `META`！
  2. `INTERFACES`（含兩層合併、`"history": None` 刪鍵語意、`aos-observed`）與 `META` 唯一出場的地方，是稿 `04` 的 **`reviewer` 完整例子**。但 `reviewer` 需要 `FILES = {"ladder.json": ...}`，而 `FILES` 與「重写 `reviewer` 比對等價當驗收」本來就排在**第三刀**！
  3. 把 `INTERFACES` 留在第一刀，等於在第一刀多寫一套複雜的兩層字典合併與刪鍵檢查（見 A8），卻要等到第三刀才有真正的驗收對象（`reviewer`）。若第一刀已經施工完成，則至少在第一刀測試（`test_agent_spec.py`）必須補上 `INTERFACES`（含 `"history": None`）與 `META` 的驗收測試；若還在收尾，移到第三刀會讓第一刀更乾淨。

---

### B3（一定要改）：第三刀「不宣告 `FSM` 的模式（eca 版）」不要做成「重生時去讀目標夾既有的 `interfaces.json` 找檔名」
* **位置**：`03-agent-py-長相.md`「三個設計決定 → 一」、`04-agent-py-兩個例子.md`「eca 版會長怎樣」、`02-現況-定義夾與agent_def.md`「定義夾有哪些檔」
* **會發生什麼**：
  稿 `03` 設計決定一寫道：「沒宣告 `FSM`＝骨架照舊手寫或用 `agent_def new` 抄來，`agent.py` 只寫它宣告的那幾份內容檔，**檔名照既有的 `interfaces.json` 找**」。這個設計在第三刀施工時會撞上三個大洞：
  1. **跟 `--defs` 及「純計算函式」衝突**：如果不先去目標資料夾讀 `interfaces.json`，就連要生成哪幾個檔名都不知道！那 `python3 agent.py --defs`（不寫檔、不給目標夾）或己案（總覽吃 `--defs` 的輸出）在沒 `interfaces.json` 的地方就完全跑不動。
  2. **`eca-claude` 與 `eca-pi` 沒有 `system.txt`**：稿 `02` 表格寫明 `eca-claude` 與 `eca-pi` 的 `system.txt` 是「沒有檔（＝空）」。如果 `eca-claude` 的 `interfaces.json` 裡根本沒有宣告 `"system"` 這個鍵（或宣告了但沒檔），而稿 `04` 的 eca 例子寫了 `SYSTEM = """..."""` 且「`interfaces.json` 重生不碰」，那 `agent.py` 去讀 `interfaces.json` 找不到 `"system"` 欄位時，會像 `def_edit.py` 一樣報 `SystemMissing` 而無法寫入 `system.txt`！
  3. **在空夾跑沒 `FSM` 的 `agent.py`**：因為沒有既有的 `interfaces.json` 可讀，會直接失敗。
* **怎麼改**：
  第三刀做無 `FSM` 模式時，不要去讀磁碟上的 `interfaces.json` 猜檔名：
  - `TOOLS`、`LLM`、`SYSTEM` 要寫的檔名一律固定為標準的 `"tools.json"`、`"llm.json"`、`"system.txt"`（除非使用者顯式傳參數改名）。
  - 當 `SYSTEM` 為空字串或 `None` 時不生 `system.txt`；若 `SYSTEM` 有字而既有 `interfaces.json` 的 `aos-agent` 沒指 `"system": "system.txt"`，要嘛報錯提醒、要嘛順手把 `"system": "system.txt"` 補進 `interfaces.json`。這樣 `--defs` 純計算函式就完全不需要讀磁碟上的 `interfaces.json`。

---

### B4（建議）：在 `ag.tool()` 與 `ag.state()` 直接禁止 `../` 逃出定義夾外的相對路徑
* **位置**：`06-打架規則-逐條.md`「第 7 條（`agent_def new`）」、`07-邊緣狀況.md`「三、整夾複製之後 `agent.py` 跟著走」
* **理由**：
  稿 `06` 第 7 條與稿 `07` 第三節都已經看出一個隱患：`agent_def new` 的 `rebase_tools` 只會改 `tools.json` 裡的相對路徑，改不到 `agent.py`；一旦有人在 `agent.py` 裡寫了 `../別處/工具`，抄到新位置後第一次重生，就會把 `rebase_tools` 算好的路徑蓋回錯的 `../別處/工具`。稿裡目前的解法是「骨架與說明一律教 `ag.home(...)`、`ag.env("AOS_WS", ...)` 或定義夾內的路徑」。
* **怎麼改**：
  既然外部路徑都應該用 `ag.home(...)` 或 `ag.env(...)` 指示詞、內部路徑都是定義夾內的相對路徑（不含 `..`），不如直接在 `ag.tool()`（與 `ag.state()`、`ag.by_hand()`）裡**把含有 `..` 路徑段的相對路徑擋成 `SpecBad`**，訊息直接教他改用 `ag.home(...)` 或 `ag.env("AOS_WS", ...)`。一行檢查就能把 `cp -r` 與 `agent_def new` 路徑失步的坑徹底封死。

---

### B5（建議）：第四刀除錯線（`aos-gdb`）的「執行中插指令／下斷點」，應區分「落進單一 agent 的 stack」與「改共用定義夾」
* **位置**：`11-跟除錯那條線的接點.md`「要攤給使用者的邊緣狀況」與 `02-現況-定義夾與agent_def.md`「還有誰會改定義夾裡的檔」
* **理由**：
  稿 `11` 假設：「在 aos 裡，『插進新指令』落到檔案上，就是去改定義夾的 json（例如在 `fsm.json` 多加一格）」，並因此推導出「插進 json 的東西下次從 `agent.py` 重生就沒了」的衝突。
  但對照稿 `02` 與稿 `07` 第二節：
  1. **定義夾是所有掛載該定義的 agent 共用的**——如果 `aos-gdb` 為了除錯某隻正在跑的 agent 而直接改定義夾的 `fsm.json` 或 `hooks.json`，所有共用同一份定義的其他 agent 下一拍也會一起踩到斷點或跑進新插的格！
  2. `aos` 今天已經有 `stack`（「自己那份」：`--kit`、`self_tools`、`self_llm`、`self_system`、`self_hook` 都寫在 stack，不改定義夾）。
* **怎麼改**：
  在稿 `11` 給除錯線的接點裡補充這個架構選項：
  - **編譯期除錯（`--debug` / `debug=True`）**：走庚的 `agent.py` 重生，像 `cc -g`。
  - **執行期動態插斷點／插指令**：若只針對正在除錯的那隻 agent instance，應像 `self_hook` / `kit` 一樣落在該 agent 的 `stack`（如此根本不會跟定義夾的 `agent.py` 重生打架）；只有當使用者明確要把實驗成功的改動「定稿（promote）回定義」時，才回寫 `agent.py` 並重生。

---

## 最沒把握的三點（因只看得到稿、看不到程式原文而可能推錯的）

1. **`defs/catalog.py` 對 `tools.json` 含 `$override` 時的實際檢查順序（關聯 A1）**：
   稿 `02` 列出 `defs check` 會查 `tools must contain an object`、`each tool must declare a path`、以及「有 `$override` 時交給 `aos-tools ls -l` 合併」。因為看不到 `catalog.py` 原文，**推測**有兩種可能：① `catalog.py` 先把整份 `tools.json` 交給 `aos-tools ls -l` 展開合併後才檢查 `tools` object（若是這樣，稿 `04` 最小例子只寫 `{"$override": [...]}` 不寫 `"tools": {}` 也能過）；② `catalog.py` 先在 Python 端檢查 `tools.json` 頂層必須有 `"tools"` dict、且裡面的項必須有 `path`，然後才叫 `aos-tools ls -l`（若是這樣，最小例子只寫 `$override` 或用了 `ag.no("名")` 就會直接在 `catalog.py` 失敗）。
2. **`templates/agent-fsm/` 的四支格程式（`idle.py`、`brain.py`、`wait.py`、`act.py`）在沒有 `hooks.json`（無 `on_start`）但 `interfaces.json` 保留 `history` 時能不能正常跑（關聯稿 `02`、`04`、`08`）**：
   稿 `02` 顯示 `agent-fsm` 有 `hooks.json`（含 `loop.json` 的 `on_start`）且 `interfaces.json` 有 `history`；而 `reviewer` 借了 `agent-fsm` 的四格，但拿掉了 `hooks.json`（無 `on_start`）**同時也把 `interfaces.json` 的 `history` 拿掉了**（`"history": None`）。第一刀的 `templates/agent-python/` 借用 `agent-fsm` 的四格，卻是一個「**沒有 `hooks.json`／`on_start`（第三刀才做），但 `interfaces.json` 留著 `history`**」的混血組合。因為看不到 `idle.py`／`brain.py` 與 `agent-fsm` 的 `on_start` hook 原文，我不確定 `brain.py` 在讀寫 `history` 時是否依賴 `on_start` hook 預先在 stack 建立好歷史檔或目錄。這一點必須靠稿 `08` 驗收第 3 條（實跑 `ctl add` 問假腦一句）實測確認。
3. **`ag.stock_fsm()` 生出的 `fsm.json` 究竟是照 `agent-fsm/fsm.json` 還是照 `reviewer/fsm.json`（關聯稿 `04`）**：
   稿 `04` 最小例子用 `FSM = ag.stock_fsm()`，表格旁註明「跟 reviewer 今天的寫法一樣」；但緊接著在稿 `04` 的 `reviewer` 完整例子裡，卻不用 `ag.stock_fsm()`，而是手寫了 8 行 `ag.fsm("idle", [ag.state(...), ...])`（其中 `act` 格帶了 `timeout_ms=0`）。因為看不到 `templates/agent-fsm/fsm.json` 與 `templates/reviewer/fsm.json` 的原文，我無法確認這兩份 `fsm.json` 除了格的路徑（相對路徑 vs `$AOS_HOME` 指示詞）之外，轉移表與 `timeout_ms=0` 是否完全相同。如果完全相同，稿 `04` 的 `reviewer` 例子其實直接寫 `FSM = ag.stock_fsm()` 即可；如果有細微差異（例如 `timeout_ms` 或結束碼不同），`stock_fsm()` 以哪一份為準會影響第三刀 `reviewer` 的等價驗收。


## 第二次：第一刀程式（agent_spec.py 行號是第一刀 4fc030f47 那版）

以下根據您提供的施工紀錄、`templates/agent-python/agent.py` 與 `py/aos/agent_spec.py` 逐行審查。

---

## (A) 審查：`proto8/py/aos/agent_spec.py`

### A1｜【一定要改】`_is_directive` 漏查 `$path` 必填與非空、`$env` 合法變數名，以及多餘鍵（第 61–66、69–76 行）

- **會發生什麼**：
  第 62 行寫成：
  ```python
  return isinstance(v, dict) and isinstance(v.get("$env"), str) and bool(v["$env"]) and isinstance(v.get("$path", ""), str)
  ```
  因為 `v.get("$path", "")` 的預設值是 `""`（本身就是 `str`），且沒有檢查 `bool(v.get("$path"))`：
  1. `ag.home("")` 或 `ag.env("AOS_HOME", "")`（空路徑）會通過 `_is_path`。
  2. 手寫 dict `ag.tool("t", {"$env": "AOS_HOME"})`（根本沒 `"$path"`）或 `ag.tool("t", {"$env": "AOS_HOME", "$path": "/x", " bad_key": 1})` 也會通過 `_is_directive`。
  3. `ag.env("123-BAD!", "/x")` 的 `$env` 未用第 29 行現成的 `ENV_KEY_RE` 檢查，也能過關。
  這些錯誤在 `agent.py --write-defs` 時都不會報 `SpecBad`，等到 `defs check`、`aos-tools` 或 `aos-fsm` 展開指示詞時才會失敗，違反「lib 先查的 ⊇ `defs check` 查的」。
- **怎麼改**：
  ```python
  def _is_directive(v):
      return (isinstance(v, dict) and set(v) == {"$env", "$path"}
              and isinstance(v["$env"], str) and bool(ENV_KEY_RE.match(v["$env"]))
              and isinstance(v["$path"], str) and bool(v["$path"].strip()))
  ```
  同時第 66 行 `_is_path` 對純字串也建議查 `bool(v.strip())`，避免 `"   "`（全空白路徑）過關。

---

### A2｜【一定要改】`META` 含非字串鍵時在第 303 行直接拋出未捕捉的 `TypeError` traceback，沒走 `SpecBad`（第 283–287、303、305–308、374–377 行）

- **會發生什麼**：
  重現宣告：`META = {1: "a"}`。
  - 第 283 行 `if meta is not None and not isinstance(meta, dict):` 放過。
  - 第 303 行 `out["_metainfo.json"] = dict({"summary": description}, **(meta or {}))` **位於第 305 行 `try:` 區塊之外**。在 Python 3 中，`dict(..., **d)` 的 `**` 解包要求所有鍵必為 `str`，當場拋出 `TypeError: keywords must be strings`。
  - `main` 第 376 行只攔 `except SpecBad:`，結果直接印出 Python traceback 崩潰，而非單行 `SpecBad`。
  - 另外，若巢狀 dict 含有 `int`/`bool`/`None` 鍵（如 `META = {"cost": {1: 2}}` 或 `INTERFACES = {"x": {True: 1}}`），第 306 行 `json.dumps` 會無聲把它們轉成字串鍵 `"1"`、`"true"`，不會報錯。
- **怎麼改**：
  在第 283 行驗證 `META` 時一併檢查鍵為字串（或第 303 行改用 `{**{"summary": description}, **(meta or {})}` 並移進 `try:` 內，再加一個遞迴小檢查確保 `out` 內所有 dict 的 key 都是 `str`）。

---

### A3｜【一定要改】`by_hand` 檔名檢查漏洞：可指到 `agent.py`、空白／換行／尾斜線，且多個 `by_hand` 可互搶預設檔名（第 109–113、264–272 行）

- **會發生什麼**：
  1. **指到 `agent.py` 本身**：宣告 `SYSTEM = ag.by_hand("agent.py")` 或 `FSM = ag.by_hand("agent.py")`。第 269 行的 `names` 沒有把 `"agent.py"` 放進去，完全不報錯。當 `FSM = ag.by_hand("agent.py")` 時，`loop.json` 的 `"exec"` 變成 `"agent.py"`，agent 跑起來每 300ms 執行一次不帶參數的 `agent.py` 並報 `ArgumentsBad`。
  2. **互搶別槽的預設檔名**：宣告 `TOOLS = ag.by_hand("llm.json")` 且 `LLM = ag.by_hand("my_llm.json")`。因為 `"llm"` 在 `hand` 裡，第 269 行 `{OWN_FILES[w] for w in OWN_FILES if w not in hand}` 會把 `"llm.json"` 從禁名集合移走，於是 `TOOLS` 搶用 `"llm.json"` 竟不會被第 271 行擋下。
  3. **空白、換行與尾斜線**：`ag.by_hand("   ")`、`ag.by_hand("a\nb.txt")`、`ag.by_hand("system.txt/")` 都會通過第 111 行（`os.path.normpath("system.txt/")` 會把尾斜線吃掉變成 `"system.txt"`）。
- **怎麼改**：
  - 第 111 行：加上 `filename != filename.strip() or "\n" in filename or filename.endswith("/")`（若 `by_hand` 只允許同夾單純檔名、不進子目錄，直接加 `"/" in filename or "\\" in filename` 最乾脆）。
  - 第 269–272 行：把 `"agent.py"` 加入 `names`，且每個 `what` 只豁免自己的 `OWN_FILES[what]`，不豁免其他槽的預設檔名：
    ```python
    base_names = set(SKELETON) | set(RUNTIME_FILES) | {"_metainfo.json", "README.md", "agent.py"}
    for what, name in hand.items():
        clash = base_names | {OWN_FILES[w] for w in OWN_FILES if w != what}
        if name in clash or list(hand.values()).count(name) > 1:
            raise SpecBad(...)
    ```

---

### A4｜【一定要改】`write_defs` 讀 `_metainfo.json` 時把 `OSError` 轉成 `ValueError`，使 I/O 錯誤誤報為 `DefBad`，且漏擋 `NaN` 與鍵順序不決定（第 311–312、317、326–335、384–387 行）

- **會發生什麼**：
  1. **錯誤分類與 docstring 相反**：第 317 行 docstring 明寫「`OSError` 照丟（main 報 `WriteFailed`）；`_metainfo.json` 不是 JSON 物件＝`ValueError`（main 報 `DefBad`）」，但第 330 行卻攔了 `except (OSError, ValueError, UnicodeError) as e: raise ValueError(...)`。若 `_metainfo.json` 是斷掉的 symlink（`lexists` 為真但 `open` 拋 `FileNotFoundError`）、權限不足（`PermissionError`）或是一個資料夾（`IsADirectoryError`），全部會被轉成 `ValueError`，導致 `main` 報 `DefBad` 而非 `WriteFailed`。
  2. **舊檔含 `NaN` 會寫出非法 JSON**：第 329 行 `json.load(f)` 預設允許 `NaN`／`Infinity`，若舊 `_metainfo.json` 被手改出 `NaN`，合併後第 312 行 `_text` 的 `json.dumps` 沒設 `allow_nan=False`，會把非法 JSON 寫回磁碟。
  3. **鍵順序依歷史狀態而變**：第 334–335 行 `old.update(value); value = old` 以舊檔鍵順序為主。全新生成時 `"summary"` 在第一個鍵；若舊檔原本 `"lineage"` 在 `"summary"` 前面，重生後 `"summary"` 就排到後面。
- **怎麼改**：
  - 第 330 行只攔 `except (ValueError, UnicodeError) as e:`，讓 `OSError` 原樣往外丟給 `main` 報 `WriteFailed`（若要補充說明是讀 `_metainfo.json` 失敗，可丟 `OSError("cannot read %s: %s" % (path, e))`）。
  - 第 312 行 `_text` 的 `json.dumps` 加上 `allow_nan=False`（或第 329 行 `json.load` 加 `parse_constant=...` 轉 `ValueError`）。
  - 第 334–335 行改為 `value = dict({"summary": value["summary"]}, **old, **value)`，確保 `"summary"` 永遠在第一格。

---

### A5｜【一定要改】`write_defs` 改名順序顛倒（指標檔比被指的檔先換上）、暫存檔遇到 symlink 與 `finally` 清理的漏洞（第 288–304、338–351 行）

- **會發生什麼**：
  1. **`os.replace` 順序顛倒**：`plan` 的順序即 `defs()` 填入 `out` 的順序：
     `_entry` → `body.json` → **`loop.json`** → `fsm.json` → **`interfaces.json`** → `tools.json` → `llm.json` → `system.txt`。
     `loop.json` 比它指向的 `fsm.json` 先換上；`interfaces.json` 比它指向的 `tools.json`、`llm.json`、`system.txt` 先換上。若線上正在跑的 agent 剛好在改名中途叫腦／tick，或原本某槽用 `ag.by_hand("custom.json")`（夾裡原本沒有 `tools.json`）切回生成檔時在改名中途失敗，`interfaces.json` / `loop.json` 就會指到尚不存在的檔案。
  2. **暫存檔 symlink 與 `finally` 清理**：
     - 第 342 行 `open(tmp, "w")` 若遇到先前殘留的同名 symlink（例如 `.tools.json.tmp-<pid>`），會順著 symlink 覆寫目標。
     - 第 350 行 `finally` 用 `if os.path.exists(tmp): os.unlink(tmp)`：若 `tmp` 是斷掉的 symlink，`os.path.exists` 回 `False` 就不會刪；且若第一個 `os.unlink(tmp)` 因競態（`FileNotFoundError`）或權限拋出 `OSError`，`for` 迴圈直接中斷，後面剩餘的暫存檔全部留在夾裡。
  3. **權限遮罩 `& 0o7777`**：第 345 行用 `os.stat(path).st_mode & 0o7777` 會連 `suid`/`sgid`/`sticky`（`0o7000`）一起複製，在有 `g+s` 的共用目錄下可能造成非預期權限位或 `EPERM`。
- **怎麼改**：
  - **調整順序**：先換被指向的葉節點檔與元資料（`system.txt`、`llm.json`、`tools.json`、`fsm.json`、`_metainfo.json`、`README.md`），再換 `loop.json`、`body.json`，最後才換入口檔 `interfaces.json` 與 `_entry`。
  - **暫存檔建立與清理**：寫 `tmp` 前先 `try: os.unlink(tmp) except FileNotFoundError: pass`；`finally` 改為：
    ```python
    finally:
        for tmp in tmps:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    ```
  - **權限**：第 344–345 行改用 `& 0o777`。

---

### A6｜【一定要改】`INTERFACES` 與 `LLM` 驗證漏洞：可刪掉必填鍵、`llm_keys: None` 造成驗證與產出脫鉤、對 `entry` 報錯誤導可用 `by_hand`（第 223–228、239–256、278–282 行）

- **會發生什麼**：
  1. **刪掉或弄壞 `description`**：`INTERFACES = {"description": None}` 會把 `interfaces.json` 頂層的 `"description"` 刪掉；`INTERFACES = {"description": 123}` 或 `LLM = {"description": 123}` 會把 `"description"` 改成整數（第 224 行 `if k != "description"` 跳過了型別檢查，第 228 行卻把 `llm["description"]` 蓋上去）。
  2. **`llm_keys: None` 造成脫鉤**：若宣告 `INTERFACES = {"aos-agent": {"llm_keys": None}}` 且 `LLM = {"temperature": 0.5}`：
     - 第 249 行 `agent.pop("llm_keys", None)` 把 `interfaces.json` 的 `llm_keys` 刪了；
     - 第 279 行 `face.get("aos-agent", {}).get("llm_keys", LLM_KEYS)` 因為鍵已不在，又 fallback 回預設 `LLM_KEYS`，於是 `_llm_json` 放行了 `"temperature"`，生出來的 `interfaces.json` 卻沒有 `"llm_keys"`。
     - 同理，`INTERFACES = {"aos-agent": {"history": None}}` 會把 `"history"` 刪掉。
  3. **錯誤訊息不實**：當 `INTERFACES = {"aos-agent": {"entry": "my_body.json"}}` 時，第 247 行報：
     `INTERFACES aos-agent entry is set by agent.py; to point it at a file you write yourself use ag.by_hand(...)`
     但 `agent.py` 根本沒有 `ENTRY` 參數可以傳 `ag.by_hand(...)`。
- **怎麼改**：
  - 在 `_interfaces` 擋下 `key == "description"`（既然 `interfaces.json` 的 `description` 由 `DESCRIPTION` 給，不應由 `INTERFACES` 刪改，就跟 `META` 擋 `"summary"` 一樣）；在 `_llm_json` 若 `"description" in llm` 需檢查為非空字串。
  - 在 `_interfaces` 對 `k == "entry"` 單獨報錯（不提 `ag.by_hand`），並禁止將 `"llm_keys"`、`"history"` 設為 `None`。

---

### A7｜【一定要改】`main` 旗標處理漏洞：`--write-defs --help` 會把 `--help` 當成資料夾名寫檔（第 365–381 行）

- **會發生什麼**：
  1. 重現指令：`python3 agent.py --write-defs --help`（或 `python3 agent.py --write-defs --defs`、`python3 agent.py --write-defs -f`）。
     第 370–373 行只檢查 `argv[0] == "--write-defs"` 且 `len(argv) <= 2`，第 381 行直接 `folder = argv[1]`，把 `"--help"` 當成目標資料夾名！若當前目錄下剛好有 `--help` 資料夾就直接寫進去，否則報 `WriteFailed: cannot write the definition into --help: --help is not a folder`。
  2. 重現指令：`python3 agent.py --help foo bar`。
     第 365 行寫 `if argv[:1] in (["--help"], ["-h"]):`，只看第一個參數，後面多塞任何參數都無聲退 0。
  3. 重現指令：`python3 agent.py some_folder`。
     `some_folder` 不是以 `-` 開頭的旗標，第 371 行卻報 `FlagUnknown: some_folder` 而非 `ArgumentsBad`。
- **怎麼改**：
  - 第 365 行改為 `if argv in (["--help"], ["-h"]):`。
  - 若 `not argv[0].startswith("-")`，報 `ArgumentsBad`。
  - 當 `argv[0] == "--write-defs"` 且 `len(argv) == 2` 時，若 `argv[1].startswith("-")`，報 `FlagUnknown`（或若 `argv[1]` 為 `""` 報 `ArgumentsBad`）。

---

### A8｜【建議】`main` 用 `os.path.realpath(sys._getframe(1).f_code.co_filename)` 決定預設寫入夾與程式名的風險（第 360–362、381 行，及骨架 `agent.py` 第 14 行）

- **會發生什麼**：
  1. **Symlink 陷阱**：若某夾 `agents/my_bot/agent.py` 是指向另一處共用 `agent.py` 的 symlink，`os.path.realpath` 會解開 symlink，使 `python3 agents/my_bot/agent.py --write-defs` 預設把生成檔寫回 symlink 目標夾（甚至蓋掉範本夾），且 `prog` 也會變成目標夾的名字。
  2. **Helper 包裝陷阱**：若有人寫了共用函式庫 `my_base.run()` 在裡面呼叫 `ag.main(...)`，`sys._getframe(1)` 取到的是 `my_base.py` 的路徑，第 381 行 `os.path.dirname(script)` 會把定義檔寫進 `my_base.py` 所在的目錄。
  3. **骨架 `templates/agent-python/agent.py` 第 14 行**：`if _e.name != "aos": raise`。若有人把 `aos/` 資料夾抄到旁邊但裡面漏了 `agent_spec.py`，Python 拋出的 `ModuleNotFoundError` 其 `_e.name` 是 `"aos.agent_spec"` 而非 `"aos"`，會直接噴 traceback 而非印出第 17 行的 `ModuleMissing`。
- **怎麼改**：
  - `main` 取目標路徑時，建議優先看 `sys.argv[0]`（若非空且非 `"-c"`），並用 `os.path.abspath`（不把最後一層 symlink 解回來源夾）來決定預設 `folder` 與 `prog`。
  - 骨架 `agent.py` 第 14 行改為 `if not (_e.name == "aos" or (_e.name or "").startswith("aos.")): raise`。

---

### A9｜【建議】`AOS_HOME` 有無時對 `ag.pack` 行為不同，且 `os.listdir` 未攔 `OSError`（第 199–203、374–377 行）

- **會發生什麼**：
  1. 設了 `AOS_HOME` 時，`ag.pack("no_such_pack")` 會查 `$AOS_HOME/lib/packs/no_such_pack.json` 並報 `SpecBad`；但若沒設 `AOS_HOME`（例如照骨架提示把 `aos` 套件抄到 `agent.py` 旁邊跑），`ag.pack("no_such_pack")` 會完全放行。
  2. 第 201 行在組錯誤訊息時呼叫 `os.listdir(os.path.join(home_dir, "lib", "packs"))`，若該目錄因權限不足拋出 `PermissionError`（`OSError`），因為 `main` 第 376 行只攔 `SpecBad`，會直接爆出未處理的 traceback。
- **怎麼改**：
  - 第 201 行把 `os.listdir` 包在 `try ... except OSError: have = []` 裡。
  - 若 `AOS_HOME` 未設，也可嘗試由 `os.path.dirname(os.path.dirname(os.path.realpath(__file__)))` 推算同棵樹下的 `packs` 目錄（因為 `agent_spec.py` 本身就在 `$AOS_HOME/lib/aos/agent_spec.py`），如此就算使用者沒 `export AOS_HOME`、只要用的是樹裡的 `lib/aos`，行為就會一致。

---

## (B) 提案：瘦身與第三刀施工注意事項

### B1｜【建議】現有 `agent_spec.py` 可砍掉約 45–55 行，先壓回 340 行以內

目前 391 行已超過「單檔 300 行考慮拆」的門檻，在不動功能的前提下有四處可以直接收緊：
1. **檔頭 docstring（第 1–17 行）**：與 `HELP`（第 39–50 行）及各函式 docstring 高度重複，且把施工背景寫進模組 docstring；只留 3–4 行模組職責與公開函式列表，可省約 12 行。
2. **`_interfaces`（第 231–256 行）**：頂層與 `aos-agent` 的 `None` 刪除／覆寫邏輯可合併，省約 10 行。
3. **`defs` 中 `by_hand` 與 `_pick` 的兩段式檢查（第 264–277、176–183 行）**：讓 `_pick(value, what, kinds)` 直接處理 `bad`、`by_hand` 與型別檢查，就不用在 `defs` 開頭先巡一輪、後面又各叫一次 `_pick`，可省約 10 行並消除 `bad` 與 `by_hand` 分流的死角。
4. **`write_defs` 的 `README.md` 統計（第 323–325、352–355 行）**：目前用 `if "README.md" in files and len(plan) < len(files):` 隱式推斷 `README.md` 被跳過，既繞又會在第三刀新增其他略過條件時誤判；直接用 `kept = []` 記錄更短也更準。

---

### B2｜【一定要改】第三刀加 `FILES` 時，暫存檔路徑組法、碰撞檢查與執行權限要注意

1. **子目錄暫存檔路徑會炸**：若 `FILES` 允許子目錄相對路徑（如 `FILES = {"cells/idle.py": "..."}`），現行第 340 行：
   ```python
   tmp = os.path.join(folder, ".%s.tmp-%d" % (name, os.getpid()))
   ```
   會組出 `<folder>/.cells/idle.py.tmp-1234`，因 `.cells` 目錄不存在而直接 `FileNotFoundError`。必須改為：
   ```python
   tmp = os.path.join(os.path.dirname(path), ".%s.tmp-%d" % (os.path.basename(path), os.getpid()))
   ```
   並在寫暫存檔前先確保子目錄存在（或明定 `FILES` 只收單層檔名）。
2. **`FILES` 檔名正規化與碰撞**：`FILES` 的每個 key 都必須先正規化（擋 `""`、`..`、絕對路徑、`"./tools.json"`），且不得與 `SKELETON`、`OWN_FILES`、`RUNTIME_FILES`、`_metainfo.json`、`README.md`、`agent.py` 及 `by_hand` 檔名撞名；否則 `out.update(files_decl)` 會無聲蓋掉 `interfaces.json` 或 `tools.json`。
3. **新生成腳本的 `+x` 權限**：現行第 344 行只在「舊檔已存在」時沿用舊檔權限。若第三刀用 `FILES` 或 `HOOKS` 生出直接執行的腳本（非 `["python3", "x.py"]`），首次在空夾 `--write-defs` 時生出的檔案沒有 `+x`（`0o755`）。第三刀需決定 `FILES` 是否支援標記執行權限，或規定生成腳本一律在 `argv` 帶解釋器（如 `["python3", ...]`）。

---

### B3｜【一定要改】第三刀加 `HOOKS` 時，`_interfaces` 第 246 行的禁改清單必須同步加入 `"hooks"`

施工紀錄第 4 點提到第一刀預設 `interfaces.json` 的 `aos-agent` 沒有 `"hooks"`，第三刀才加。屆時第 246 行：
```python
if k in ("entry", "tools", "llm", "system"):
```
必須同步把 `"hooks"` 加進去，否則使用者可以一邊宣告 `HOOKS = ...`、一邊在 `INTERFACES = {"aos-agent": {"hooks": "other.json"}}` 覆寫，導致生成的 hooks 檔與 `interfaces.json` 指到的檔名脫鉤。

---

### B4｜【一定要改】第三刀做「不宣告 FSM 的 eca 模式」時，參數簽名、`SKELETON` 與殘留舊檔的問題

1. **函式簽名相容性**：目前 `defs(description, system, tools, llm, fsm, meta=None, interfaces=None)` 與 `main(...)` 把 `fsm` 當成必填位置參數。第三刀支援不宣告 `FSM` 時，應給預設值 `fsm=None`（同時區分：`fsm is None`＝eca 無狀態機模式；`fsm == ag.by_hand("fsm.json")`＝有狀態機且手寫 `fsm.json`）。
2. **`SKELETON` 與 `RUNTIME_FILES` 隨模式變化**：目前第 32 行 `SKELETON` 寫死含 `"loop.json"`，第 290–292 行寫死 `body.json` 跑 `["aos-loop", "loop.json"]`。若 eca 模式不跑 `fsm.json`（或甚至不經 `loop.json`），`out` 要生的骨架檔與 `by_hand` 的禁名集合要依模式調整。
3. **從 FSM 改成 eca 模式時的殘留檔**：因為前提定調「不宣告的檔不碰也不刪」，若使用者先從 `agent-python` 骨架（有 `fsm.json`、`loop.json`）開始改，改成 eca 模式後跑 `--write-defs`，舊的 `fsm.json` 仍會留在夾裡。施工時務必實測 `agent_def check` 對夾裡殘留未被引用的 `fsm.json` 是否會報錯。

---

### B5｜【建議】第三刀拆檔時維持 `from aos import agent_spec as ag` 單一公開入口

第三刀加上 `HOOKS`、`FILES` 與 eca 模式後，總行數勢必逼近 450–500 行。拆檔時請注意：
1. **不要破壞 `from aos import agent_spec as ag`**：所有給 `agent.py` 與測試呼叫的函式（`pack`、`tool`、`no`、`home`、`env`、`state`、`fsm`、`stock_fsm`、`by_hand`、`defs`、`write_defs`、`main`、`SpecBad`，以及第三刀新增的宣告函式）都必須繼續留在 `agent_spec` 命名空間下。
2. **建議切法**：將驗證與 JSON 組裝細節拆到同套件的私有模組（例如 `py/aos/_agent_defs.py`：放 `_tools_json`、`_llm_json`、`_interfaces`、`fsm` 檢查、以及第三刀的 `HOOKS`/`FILES` 檢查），`py/aos/agent_spec.py` 只留薄薄的宣告建構子、`write_defs` 與 `main`。兩支檔都能輕鬆控制在 220 行以內。
3. **檢查 `install.py`**：確認拆出的私有模組會被 `install.py` 一併安裝到 `$AOS_HOME/lib/aos/`。

---

## 最沒把握的三點（因看不到 `aos-fsm`／`aos-tools`／`defs` 原文而可能推錯的）

1. **`ag.no(name)` 搭了 `ag.pack(...)`，但 `name` 其實不在任何一個所選的 pack 裡時，`aos-tools`／`defs check` 會怎麼處理**：
   施工紀錄提到獨立審查抓出「`ag.no` 沒搭任何 `ag.pack` 會生出 `{"tools": {"b": null}}`，`defs check` 會報 `each tool must declare a path`」。**推測**若 `aos-tools` 合併 `$override` 時，只會把「原本在底層 pack 裡存在、且被覆寫為 `null`」的工具刪掉，而對底層 pack 裡根本沒有的 `"typo": null` 留在原處（或直接報錯），那麼當使用者寫 `TOOLS = [ag.pack("look"), ag.no("typo_name")]` 時，`agent_spec.py` 目前因為 `packs` 非空就放過了，到 `defs check` 仍會失敗。若是如此，在有 `AOS_HOME` 時 `agent_spec` 應順手載入所選的 pack JSON，確認 `ag.no(name)` 的 `name` 確實存在於其中至少一個 pack。
2. **`ag.tool(name, path, **more)` 的 `**more` 是否允許任意未知鍵**：
   第 92–99 行只檢查了 `env`、`env_file`、`cache` 三個鍵，其餘 `**more` 原樣塞進 `tools.json` 的工具格。**推測** `aos-tools` 的 `registry.finish` 或 `defs check` 對工具格可能有允許欄位的白名單（或對其他欄位有型別要求）；若 `aos-tools` 會拒絕未知欄位，那使用者拼錯字如 `ag.tool("t", "/p", env_files="x")` 在 `agent_spec` 不會報 `SpecBad`，要到 `defs check` 才會爆。
3. **`aos-fsm` 與 `defs check` 對 `state` 的 `argv` 空字串參數、孤立 state（unreachable states）與空 `SYSTEM = ""` 的規定**：
   - 第 124 行 `all(_is_path(a) for a in argv)` 要求 `argv` 每一項（含第 1 項以後的旗標參數）都必須是非空字串或指示詞，若某支格程式需要傳空字串參數 `""` 會被擋下（**推測** `aos-fsm` 可能只要求 `argv[0]` 非空、其餘為字串或指示詞）。
   - 第 147–167 行 `fsm()` 只檢查了 `start` 與 `next` 的目標在 `table` 裡，沒檢查是否有從 `start` 永遠走不到的死格（**推測** `aos-fsm`／`defs check` 也許不擋死格，若會擋則 `fsm()` 需補 BFS 可達性檢查）。
   - 第 273 行允許 `SYSTEM = ""`（生出 0 bytes 的 `system.txt`），**推測** `defs check` 允許空的 `system.txt`；若 `defs check` 要求 `system.txt` 非空，則第 273 行需像 `DESCRIPTION` 一樣擋空字串。
