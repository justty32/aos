← [proto4-3](../proto4-3/README.md)（inst.json 與 kernel）｜[逐步 lisp](../proto4-4/README.md)

# proto4-6 — 逐步 JSON、Python、Lua

三支工具都把一份程式拆成 0 起算的格子，每叫一次只跑下一格。成功格回 0；失敗不推進；
用法或程式形狀錯回 2；最後一格仍回 0，下一次開始固定回 100。共同選項：

```sh
aos-step-json job.json --status       # 印狀態 JSON
aos-step-py job.py --reset            # 刪進度，從第 0 格重來
aos-step-lua job.lua --stderr -       # aos.call 的子程式錯誤送到目前 stderr
```

狀態都在程式旁的 `<PROG 去掉副檔名>.state.json`，先寫 `.tmp` 再 rename；`pc` 是下一格，
`last` 是上次成功結果，`history` 留最近 50 次。`pc > 0` 後程式變動會警告但照跑。
三支都沒有鎖、自動重試、分支或排程，同一份程式不要同時跑兩次。

### 等一個檔

- 一格可宣告一個要等的檔；相對路徑以程式資料夾 `here` 為準，狀態一律存絕對路徑。
- 宣告的格算成功、`pc` 加一並回 0；之後檔不在就只把 `checks` 加一、回 0，不跑格。
- 檔出現時會清掉 `waiting`、在 `history` 加一筆 `(wait)`，同一次呼叫接著跑下一格。
- 最後一格也能等：檔出現前不回 100，出現後下一次呼叫才回 100。
- 沒有逾時、一次只等一個檔、kernel 不會叫醒；`--reset` 會清掉等待。

等待時的狀態多一欄；`--status` 也會在 stderr 印一行「在等…」：

```json
"waiting":{"for":"/abs/out.json","since":"2026-09-13T07:00:00+00:00","after_pc":0,"checks":1}
```

Python 可把 kernel LLM 排程拆成兩格；`llm_submit` 不帶 `--wait`，下一格才讀結果：

```python
def submit(state):
    state["r"] = aos.llm_submit(K, {"messages":[{"role":"user","content":"hi"}]}, "q1")
    return aos.wait_for(state["r"])

def consume(state):
    state["text"] = __import__("json").load(open(state["r"]))["text"]
```

放上 kernel 時，inst 只需把 argv 換成所選工具；工具回 100 後 kernel 會把行程收工：

```json
{"argv":["/abs/proto4-6/aos-step-lua","job.lua"],"cwd":"/abs/工作資料夾","stderr":"err.txt"}
```

## 逐步 JSON

`aos-step-json` 的程式是 JSON 陣列，每格就是一份 proto4-3 inst。把下面存成 `job.json`：

```json
[
  {"note":"寫資料","argv":["sh","-c","printf 'hello\\n' > message.txt"]},
  {"note":"轉大寫","argv":["sh","-c","tr a-z A-Z < message.txt > result.txt"]},
  {"note":"清理","argv":["rm","message.txt"]}
]
```

```sh
/abs/proto4-6/aos-step-json job.json
/abs/proto4-6/aos-step-json job.json --status
```

`note` 只給人看，執行前拿掉；其餘是 inst 的 `argv`、`cwd`、`stdin`、`stdout`、`stderr`、
`exit`、`envs`，另可加 `"wait_for":"out.json"`，在 inst 成功後才開始等。沒寫 `cwd` 就用程式資料夾，相對 `cwd` 也從那裡算。子程式非 0 原碼退回，
`aos-exec` 自己失敗回 125。狀態例：

```json
{"pc":2,"n":3,"done":false,"src":{"n":3,"sha256":"..."},"last":{"pc":1,"exit":0,"kind":"child","at":"...","ms":2},"history":[]}
```

## 逐步 Python

`aos-step-py` 把普通 `.py` 裡每個公開頂層 `def` 當一格，照定義行號排序；`_` 開頭的是 helper。
每格收一個 `state` dict，只有它會跨格並存 JSON。完整例子：

```python
from pathlib import Path

FACTOR = 2
def _double(xs): return [x * FACTOR for x in xs]

def load(state):
    state["values"] = [int(x) for x in Path(here, "input.txt").read_text().split()]

def compute(state):
    state["values"] = _double(state["values"])

def ask_tool(state):
    state["tool"] = aos.value(aos.call_dir("tool", read="tool/result.json", json=True))

def write(state):
    Path(here, "result.json").write_text(__import__("json").dumps(state) + "\n")
```

```sh
/abs/proto4-6/aos-step-py job.py
/abs/proto4-6/aos-step-py job.py --status
```

每格重新載入整支檔，可用 `state`、`here`、`pc`、`aos`。例外或不可 JSON 化的 state 讓該格
回 1，全文放 `.aos-step-py/error`。`aos` 有 `call`、`call_dir`、`call_json`、`ok`、`value`、
`llm`、`llm_text`、`wait_for`、`llm_submit`；工具路徑可用 `AOS_EXEC`／`AOS_LLM`／`AOS_KERNEL` 覆蓋。
`aos.call(target, args=["a", "b c"])` 只對普通檔案有效；`.json` 或資料夾目標給了 `args` 就拋錯。

`bytes`／`bytearray` 自動存成只有 `$b64` 的物件，讀回時自動還原成 `bytes`；這也表示一般 JSON
裡恰好只有 `$b64` 一個 key 的物件會被視為 binary。手動轉換可用 `aos.b64(b)`／`aos.unb64(s)`。

狀態故意把 `state` 放最前，並明列步驟名：

```json
{"state":{"values":[2,4]},"pc":2,"n":4,"done":false,"steps":["load","compute","ask_tool","write"],"src":{"n":4,"sha256":"..."},"last":{"pc":1,"step":"compute","exit":0,"at":"...","ms":1},"history":[]}
```

## 逐步 Lua

`aos-step-lua` 用 `/usr/bin/lua5.4`，不靠第三方庫。完整的 `job.lua`：

```lua
local json = require "json"
local FACTOR = 2

local function doubled(xs)
  local out = {}
  for i, x in ipairs(xs) do out[i] = x * FACTOR end
  return out
end

local function load(state)
  state.values = {1, 2, 3}
end

local function compute(state)
  state.values = doubled(state.values)
end

local function keep_binary(state)
  state.raw = "\0\255\1" -- 存檔時自動成 {"$b64":"AP8B"}
end

local function write(state)
  local f = assert(io.open(here .. "/result.json", "w"))
  f:write(json.encode(state), "\n"); f:close()
end

return {
  {name="load", fn=load},
  {name="compute", fn=compute},
  {name="keep_binary", fn=keep_binary},
  {name="write", fn=write},
}
```

```sh
/abs/proto4-6/aos-step-lua job.lua
/abs/proto4-6/aos-step-lua job.lua --status
/abs/proto4-6/aos-step-lua job.lua --reset
```

Lua 抓不到頂層函式的可靠定義順序，因此最後明寫 `return {{name=..., fn=...}, ...}`；沒回陣列、
元素缺 `name`／`fn` 都回 2。每格 `fn(state)`，並可直接用全域 `state`、`here`、`pc`、`aos`；
`require "aos"` 也行。載入失敗回 2；格內錯誤或 state 不可 JSON 化回 1，全文放
`.aos-step-lua/error`。Lua 沒內建 SHA-256，改動偵測用檔案大小、mtime、步驟名字。

自帶的 JSON 支援物件、陣列、UTF-8／`\uXXXX`、數字、布林與 `json.null`；空 table 編成 `{}`。
非合法 UTF-8 的 Lua 字串自動存成只有 `$b64` 的物件，讀回時自動還原位元組；這也表示一般 JSON
裡恰好只有 `$b64` 一個 key 的物件會被視為 binary。手動轉換可用 `aos.b64(s)`／`aos.unb64(s)`。

Lua 的 `aos` 一覽：`call(target, opts)`、`call_dir(dir, opts)`、`call_json(path, opts)`、`ok(r)`、
`value(r)`、`llm(endpoint, req, out, timeout_ms)`、`llm_text(r)`、`b64`、`unb64`。`call` 的 opts 是
`dir_target`、`timeout_ms`、`args`、`stdin`、`capture`、`read`、`read_err`、`json`；`args={"a","b c"}` 只能給普通檔案目標；回傳
`{code,kind,out,err,value}`。`llm` 會保留 `out.req.json`。底層工具可由 `AOS_EXEC`／`AOS_LLM` 覆蓋。
Lua 格可 `return aos.wait_for(path)`；`aos.llm_submit(K, req, name)` 會回 kernel 結果檔的絕對路徑。

## 出處

定案與原話在 [proto4 筆記 §23](../proto4/notes/23-step-json-python.md)；inst 完整語意見
[proto4-3 exec 文件](../proto4-3/docs/exec.md)。
