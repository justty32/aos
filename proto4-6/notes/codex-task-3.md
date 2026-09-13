# 任務書 3：proto4-6 `aos-step-lua`——Lua 版逐步程式（跟 Python 版同一套約定；binary 走 base64）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准新增／修改 `proto4-6/` 底下的檔案**。**不要 git commit、不要 push。** 不要開其他 agent。不要打真網路。Lua 用 `/usr/bin/lua5.4`（`lua -v` 是 5.5，也能跑；shebang 寫 `#!/usr/bin/env lua5.4`）；**沒有任何 Lua 第三方庫**，JSON 與 base64 要自己帶。

## 先讀

`proto4/notes/23-step-json-python.md` §23.1、§23.5、§23.6（照 §23.6 做）；`proto4-6/aos_step_py.py`、`aos_py.py`、`step_common.py`、`README.md`、`test/test_step_py.py`（**Python 版剛做好，行為、狀態檔形狀、退出碼、訊息口吻一模一樣照搬**）；`proto4-3/README.md`（aos-exec 退出碼）。

## 定案

- 檔案：`proto4-6/aos-step-lua`（Lua 腳本本體，shebang `#!/usr/bin/env lua5.4`，可執行）、`proto4-6/lua/json.lua`（純 Lua JSON encode／decode：物件、陣列、字串（含 `\uXXXX` 與 UTF-8）、數字、true／false／null；**空 table 編成 `{}`**，陣列判定＝1..n 連續整數 key；`null` 用一個哨兵 `json.null`）、`proto4-6/lua/base64.lua`、`proto4-6/lua/aos.lua`（程式裡用的 `aos` 模組）。每檔 300 行內。`aos-step-lua` 用自己所在目錄找 `lua/`（`arg[0]` 解出來，`package.path` 加進去）。
- **程式長什麼樣**（`PROG.lua`）：普通 Lua 檔，最後 `return { {name="load", fn=load}, {name="compute", fn=compute}, … }`。每格 `fn(state)`；`state` 是 table。頂層放 `local` helper、常數、`require` 都行。沒 `return` 陣列、或元素缺 `name`／`fn` → 退出 2、pc 不動、訊息說清楚。
- 用法：`aos-step-lua PROG.lua`、`--status`、`--reset`、`--stderr -|PATH`（給 `aos.call` 底下的 aos-exec）。
- **每格**：讀狀態（沒有＝pc 0、state `{}`）→ `dofile`／`loadfile` 重新載入 PROG 拿到 steps → `n`＝#steps、`steps` 名字清單 → `pcall(steps[pc+1].fn, state)`（Lua 1 起算，但**對外 pc 一律 0 起算**，跟其他兩支一致）→ 成功就把 state 編成 JSON 寫回、pc+1、退出 0。
  - 程式裡可用的全域名字：`state`（也當參數傳）、`here`、`pc`、`aos`（`require "aos"` 也行）。
  - 格失敗 → stderr `aos-step-lua: 第 k 格 <名字>（0 起算）失敗：<錯誤第一行>（全文：.aos-step-lua/error 或 --status）`，`debug.traceback` 全文寫 `.aos-step-lua/error`，pc 不動、state 不寫回、退出 1。
  - state 編不成 JSON（函式、userdata、循環、key 不是字串或整數）→ 同上，訊息說是哪種。
  - 載入失敗（語法錯、require 不到）→ 2。
  - pc == n → 不跑、`done:true`、退出 100。
  - 改動偵測：PROG 的 sha256——Lua 沒內建 hash，**改用「檔案大小＋mtime＋步驟名字清單」**（跟 Janet 版一樣的退路）；對不上且 pc>0 → 警告一行照跑。
- **狀態檔** `<PROG 去掉 .lua>.state.json`，形狀跟 Python 版一模一樣（`state` 最前、`pc`、`n`、`done`、`steps`、`src`、`last`、`history`）；先 `.tmp` 再 `os.rename`。
- **binary／base64**（§23.6）：編 JSON 時，字串若**不是合法 UTF-8** → 編成 `{"$b64":"<base64>"}`；解 JSON 時，只有一個 key 且 key 是 `$b64` 的物件 → 還原成位元組字串。`aos.b64(s)`／`aos.unb64(s)` 也給。測試要真的塞 `"\0\255\1"` 進 state、存了再讀回來一樣。
- **`aos.lua`**：`aos.call(target, opts)`（opts 表：`dir_target`、`timeout_ms`、`stdin`、`capture`、`read`、`read_err`、`json`）→ 回表 `{code=, kind=, out=, err=, value=}`；底下用 `io.popen`／`os.execute` 叫 `AOS_EXEC`（環境變數，預設 `<repo>/proto4-3/aos-exec`，路徑由 `aos-step-lua` 所在目錄推）。Lua 5.4 的 `os.execute` 回 `(true|nil, "exit", code)`，`io.popen(...):close()` 一樣。`stdin` 要餵的話：寫暫存檔再 `< 檔` 重導（不要搞 pipe）。`capture` 用 `io.popen` 讀 stdout；stderr 要抓 kind 的話 `2>暫存檔`。shell 引號用一個 `shquote` 函式包好每個參數。`aos.call_dir`、`aos.call_json`、`aos.ok`、`aos.value`、`aos.llm(endpoint, req, out)`（req 表 → 寫 `out..".req.json"` → 叫 `AOS_LLM call` → 讀 out 解 JSON）、`aos.llm_text`。
- **README** 加一節「逐步 Lua」（總長 250 行內；三節：JSON、Python、Lua）：完整範例 `job.lua`（頂上 `local` helper，四格，含一格把 binary 塞進 state 展示 `$b64`）、怎麼跑、`return {…}` 那個形狀為什麼（Lua 抓不到頂層函式順序，所以名字明寫）、狀態檔、binary 規則、`aos.` 一覽、放上 kernel、沒做什麼。三節共通的東西（狀態檔、退出碼、放上 kernel）合成一段「三支共通」放最上面，別寫三遍。

## 測試（`proto4-6/test/test_step_lua.py`——用 Python unittest 開子行程測 Lua 腳本，跟其他兩支同風格；至少 14 條）

steps 順序與名字；state 跨格；狀態檔形狀（`state`、`steps`）；binary 往返（`"\0\255\1"` 存成 `$b64`、下一格讀回相等）；`aos.b64`／`unb64`；格失敗 → 1、pc 不動、state 沒變、error 檔有 traceback、訊息含名字；state 放函式 → 失敗 pc 不動；語法錯 → 2；沒 `return` 陣列 → 2；做完 → 100、再叫 100；`--reset`；改檔警告；`here`／`pc`；`aos.call_dir`＋`read`＋`json`；`aos.call` 回 3；端到端 `proto4-3/aos-exec` 跑 argv 指到 aos-step-lua 的 inst.json 到 100。另外 `lua/json.lua` 單獨 4 條（往返：巢狀、空物件、`\u` 與中文、null）。

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-6 && python3 -m unittest discover -s test 2>&1 | tail -2
```
既有 Python／JSON 的測試一條都不能壞。

## 回報（十行以內，大白話）

檔案與行數；測試數與最後一行；自己決定的事、坑、沒做到的。
