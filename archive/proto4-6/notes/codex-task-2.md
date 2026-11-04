# 任務書 2（改版）：proto4-6 `aos-step-py`——逐函數的逐步 Python（一支普通 .py、每個頂層 def 一格、只有 state 這個 dict 跨格、存 JSON）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准新增／修改 `proto4-6/` 底下的檔案**。**不要 git commit、不要 push。** 不要開其他 agent。不要打真網路（`aos.llm` 的測試用 `proto4-5/test/_fake_openai.py` 起假 server）。

## 先讀

`proto4/notes/23-step-json-python.md` 的 §23.1、§23.5（**照 §23.5 做，§23.4 已作廢**）；`proto4-6/aos_step_json.py`、`README.md`、`test/`（狀態檔形狀、改動偵測、退出碼、訊息口吻**全部沿用**，能共用的抽到 `step_common.py`，既有 15 條測試不能壞）；`proto4-4/README.md`「函式庫怎麼用」＋`src/aos.janet`（`aos.call` 那組要做 Python 版）；`proto4-5/README.md` 第一層 `aos-llm call`。

## 使用者原話

> 要最簡單的方式：狀態儲存於檔案，並且是 json，最重要的是 ai 容易看懂，容易產出。
> 不用太嚴格，可以是逐 python 函數，或逐 python 檔案或 module，來做執行。

## 定案（KISS，不要多做）

- 檔案：`proto4-6/aos-step-py`（薄殼）、`aos_step_py.py`（執行器）、`aos_py.py`（程式裡用的 `aos` 模組）、`step_common.py`（共用）。每檔 300 行內。
- 用法：`aos-step-py PROG.py`（跑下一格）、`--status`、`--reset`、`--stderr -|PATH`（透過環境變數 `AOS_STEP_STDERR` 給 `aos_py` 底下的 aos-exec 用）。
- **格＝頂層函式**：用 `importlib.util.spec_from_file_location` 每次重新載入 `PROG.py`（`__name__` 設成 `"__aos_step__"`），取模組裡「在這支檔案定義的頂層函式」（`inspect.isfunction` 且 `__module__` 相同），**照定義順序**（用 `__code__.co_firstlineno` 排），名字以 `_` 開頭的跳過。這串就是格，`n`＝長度。載入時如果模組頂層有副作用那是使用者自己的事，README 講一句「頂層只放 import、常數、def」。
- **每格做什麼**：讀狀態（沒有＝`pc 0`、`state {}`）→ 載入模組 → 呼叫 `steps[pc](state)`（只傳這一個參數；函式可以回傳東西但忽略）→ `json.dumps(state, ensure_ascii=False)` 成功才算成功：pc+1、state 寫回、退出 0。
  - 模組裡另外可用的名字：執行前把 `here`（程式所在資料夾絕對路徑）、`pc`、`aos`（aos_py 模組）塞進模組命名空間（`setattr`），所以函式裡直接寫 `aos.call(...)`、`here` 就好，不必 import。
  - 格丟例外 → stderr `aos-step-py: 第 k 格 <函式名>（0 起算，PROG 第 L 行）失敗：<例外第一行>（全文：.aos-step-py/error 或 --status）`，traceback 全文寫 `.aos-step-py/error`，pc 不動、**state 不寫回**，退出 1。
  - `state` 放不進 JSON → 同上，訊息說「state 裡有 JSON 放不進的東西：<型別>」。
  - 檔案載不起來（語法錯、import 不到）→ 退出 2、pc 不動、訊息說原因。
  - pc == n → 不跑、`done:true`、退出 100。
  - 改動偵測：sha256 對不上且 pc>0 → 警告一行照跑（跟 aos-step-json 同一句）；另外若第 pc 格的**函式名**跟狀態檔記的下一格名字對不上，也警告。
- **狀態檔** `<PROG 去掉 .py>.state.json`：`{"state":{…},"pc":2,"n":5,"done":false,"steps":["load","compute",…],"src":{…},"last":{"pc":1,"step":"compute","exit":0,"at":"…","ms":12},"history":[…]}`——`state` 放最前面，`steps` 是格的名字清單（AI 打開就知道流程）。
- **`aos_py` 模組**：
  - `aos.call(target, dir_target=None, timeout_ms=None, stdin=None, capture=False, read=None, read_err=None, json=False) -> dict`：底下 `subprocess.run([AOS_EXEC, target, …])`，`AOS_EXEC` 預設 `<repo>/proto4-3/aos-exec`、環境變數可蓋；回 `{"code","kind","out","err","value"}`，`kind` 判法照 Janet 版（125→aos、2 且 stderr 以 `aos-exec:` 開頭→usage）；`read` 相對路徑以呼叫者 cwd 為準。
  - `aos.call_dir(dir, **opts)`、`aos.call_json(path, **opts)`、`aos.ok(r)`、`aos.value(r)`。
  - `aos.llm(endpoint, req: dict, out: str, timeout_ms=None) -> dict`：req 寫到 `out + ".req.json"`，`subprocess.run([AOS_LLM, "call", endpoint, reqfile, out])`（`AOS_LLM` 預設 `<repo>/proto4-5/aos-llm`），讀 `out` 回 dict（讀不到回 `{"ok":False,"error":{"kind":"no_result"}}`）；`aos.llm_text(r)`。
- **README** 加一節「逐步 Python」（總長 200 行內，「逐步 JSON」那節保留）：一份完整範例 `job.py`（頂上 import 與一個 `_helper`，四格：`load` 讀檔進 state、`compute` 用 helper 算、`ask_tool` 用 `aos.call_dir` 叫個資料夾拿 JSON 存進 state、`write` 寫結果檔；每個 def 上一行註解說這格幹嘛）、怎麼跑、狀態檔長什麼樣（含 `state`、`steps`）、規則（什麼算格、只有 state 活著、放不進 JSON 就失敗、頂層只放 import／常數／def）、`aos.` 一覽表、想逐檔案就 `aos.call("./other.py")`、放上 kernel、沒做什麼。

## 測試（`proto4-6/test/test_step_py.py`，unittest，至少 15 條；既有 15 條不能壞）

`_helper` 不算格、`steps` 順序照定義；`state` 跨格；狀態檔 `state` 與 `steps` 欄；格丟例外 → 1、pc 不動、state 沒變、error 檔有 traceback、訊息含函式名與行號；state 塞 set → 失敗 pc 不動；語法錯 → 2；做完 → 100、再叫 100；`--reset`；改檔警告（sha256）；函式名對不上的警告；`here`／`pc` 可用；`aos.call_dir`＋`read`＋`json`；`aos.call` 回 3 → `code 3 kind child`；`aos.llm` 對假 server `echo:hi` → `llm_text` 是 `hi`；端到端：`proto4-3/aos-exec` 跑一份 argv 指到 aos-step-py 的 inst.json 五次，最後 100。

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-6 && python3 -m unittest discover -s test 2>&1 | tail -2
```

## 回報（十行以內，大白話）

檔案與行數；測試數與最後一行；自己決定的事、坑、沒做到的。
