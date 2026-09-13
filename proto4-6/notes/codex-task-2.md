# 任務書 2：proto4-6 `aos-step-py`——逐步 Python（一支普通 .py、一格一個頂層 statement、只有 state 這個 dict 跨格、存 JSON）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准新增／修改 `proto4-6/` 底下的檔案**。**不要 git commit、不要 push。** 不要開其他 agent。不要打真網路（`aos.llm` 的測試用 `proto4-5/test/_fake_openai.py` 起假 server）。

## 先讀

`proto4/notes/23-step-json-python.md`（使用者原話＋§23.4 定案，**照 §23.4 做**）；`proto4-6/aos_step_json.py`、`README.md`、`test/`（你上一輪做的：狀態檔形狀、改動偵測、退出碼、訊息口吻，**全部沿用**，能共用的程式抽到 `step_common.py`）；`proto4-4/README.md`「函式庫怎麼用」＋`src/aos.janet`（`aos.call` 那組要做成 Python 版，語意一樣：`:dir-target`→`dir_target`、`:read`→`read`、`:json`→`json`、`:capture`→`capture`、`:stdin`→`stdin`、`:timeout-ms`→`timeout_ms`；回 dict `{"code","kind","out","err","value"}`）；`proto4-5/README.md` 第一層 `aos-llm call`（`aos.llm(endpoint, req, out)` 就是把 req 寫檔、叫 `aos-llm call`、讀回結果 dict）。

## 定案

- 檔案：`proto4-6/aos-step-py`（薄殼）、`aos_step_py.py`（執行器）、`aos_py.py`（給程式用的 `aos` 模組）、`step_common.py`（跟 aos-step-json 共用：狀態檔讀寫、sha256、訊息）。每檔 300 行內。
- 用法：`aos-step-py PROG.py`（跑下一格）、`--status`、`--reset`、`--stderr -|PATH`（給 `aos.call` 底下的 aos-exec 用，存進狀態檔？**不要**，就只是這次的旗標，透過環境變數 `AOS_STEP_STDERR` 傳給 `aos_py`）。
- **切格**：`ast.parse(PROG)`，頂層 `Import`／`ImportFrom`／`FunctionDef`／`AsyncFunctionDef`／`ClassDef` 是「定義」，**不算格**；其餘頂層 statement 依序編號 0、1、2…（`n` 是格數）。用 `ast.get_source_segment` 取每段原始碼，`compile(segment, PROG, "exec")` 執行。
- **每格做什麼**：讀狀態（沒有＝`pc 0`、`state {}`）→ 建一個新的命名空間 `{"state": state, "here": 程式資料夾絕對路徑, "pc": pc, "aos": aos_py 模組, "__name__": "__aos_step__"}` → **先依序執行所有定義段** → 執行第 pc 格 → `json.dumps(state)`（`ensure_ascii=False`）成功才算成功：pc+1、state 寫回、退出 0。
  - 格丟例外 → stderr `aos-step-py: 第 k 格（0 起算，PROG 第 L 行）失敗：<例外第一行>（全文：.aos-step-py/error 或 --status）`，traceback 全文寫 `.aos-step-py/error`，pc 不動、**state 不寫回**（那格等於沒發生），退出 1。
  - `state` 放不進 JSON → 同上，訊息說「state 裡有 JSON 放不進的東西：<型別／key>」。
  - 定義段本身丟例外（例如 import 不到）→ 一樣失敗、pc 不動。
  - pc == n → 不跑、`done:true`、退出 100。
  - 程式改過（sha256 對不上、pc>0）→ 警告一行照跑，跟 aos-step-json 同一句。
  - 語法錯 → 退出 2、pc 不動。
- **狀態檔** `<PROG 去掉 .py>.state.json`：跟 aos-step-json 同形，多一個 `"state": {...}` 欄放在最前面（AI 打開先看到資料）：`{"state":{…},"pc":2,"n":5,"done":false,"src":{…},"last":{…},"history":[…]}`。
- **`aos_py` 模組**（給程式裡 `aos.` 用）：
  - `aos.call(target, dir_target=None, timeout_ms=None, stdin=None, capture=False, read=None, read_err=None, json=False) -> dict`：底下 `subprocess.run([AOS_EXEC, target, …])`，`AOS_EXEC` 預設 `<repo>/proto4-3/aos-exec`（照 Janet 版的解法，環境變數可蓋）。回 `{"code":int,"kind":"child"|"aos"|"usage","out":str|None,"err":str,"value":any}`；`kind` 的判法照 Janet 版（125→aos、2 且 stderr 以 `aos-exec:` 開頭→usage）。`read` 的相對路徑以呼叫者 cwd 為準（同 Janet 版）。
  - `aos.call_dir(dir, **opts)`、`aos.call_json(path, **opts)`、`aos.ok(r)`、`aos.value(r)`。
  - `aos.llm(endpoint, req: dict, out: str, timeout_ms=None) -> dict`：把 req 寫到 `out + ".req.json"`，`subprocess.run([AOS_LLM, "call", endpoint, reqfile, out])`（`AOS_LLM` 預設 `<repo>/proto4-5/aos-llm`），讀 `out` 的 JSON 回 dict（讀不到回 `{"ok":False,"error":{"kind":"no_result",…}}`）；`aos.llm_text(r)`。
  - 沒有 pipe（Python 自己會）。
- **README** 加一節「逐步 Python」（總長 200 行內；「逐步 JSON」那節保留）：一份完整範例 `job.py`（有 import、一個 def、四五格：讀檔進 state、用 def 算、`aos.call_dir` 叫個資料夾拿 JSON、寫結果檔；每格上面一行註解說這格幹嘛）、怎麼跑、狀態檔長什麼樣（含 `state`）、規則（哪些不算格、只有 state 活著、放不進 JSON 就失敗）、`aos.` 一覽表、放上 kernel、沒做什麼（沒有 image、函式不跨格只重放、沒有非同步等待）。

## 測試（`proto4-6/test/test_step_py.py`，unittest，至少 16 條；既有 15 條不能壞）

切格：import／def／class 不算格、`n` 對；每格重放定義（第 2 格用第 0 格前定義的函式）；`state` 跨格（第 0 格 `state["x"]=1`，第 1 格讀到）；狀態檔有 `state` 欄且是合法 JSON；格丟例外 → 退出 1、pc 不動、state 沒變、`.aos-step-py/error` 有 traceback、訊息含行號；state 塞一個 set → 失敗、pc 不動；語法錯 → 2；做完 → 100、再叫還是 100；`--reset`；改動偵測警告；`here`、`pc` 值對；`aos.call_dir`＋`read`＋`json` 拿到 JSON（fx 資料夾放一份 inst.json）；`aos.call` 對回 3 的腳本 → `code 3 kind child`；`aos.llm` 對假 server（`echo:hi`）→ `llm_text` 是 `hi`；一條端到端：用 `proto4-3/aos-exec` 跑一份 inst.json（argv 指到 aos-step-py）四次，最後退出 100。

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-6 && python3 -m unittest discover -s test 2>&1 | tail -2
```

## 回報（十行以內，大白話）

檔案與行數；測試數與最後一行；自己決定的事、坑、沒做到的。
