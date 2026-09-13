← [proto4-3](../proto4-3/README.md)（inst.json 與 kernel）｜[逐步 lisp](../proto4-4/README.md)

# proto4-6 — 逐步 JSON 與逐步 Python

`aos-step-json` 是給 AI 寫、給人看的最簡逐步程式：一個 JSON 陣列，每個元素是一份 inst，每叫一次只跑下一份。

## 一份完整程式

把下面存成 `job.json`：

```json
[
  {
    "note": "第一格：寫一份資料",
    "argv": ["sh", "-c", "printf 'hello\\n' > message.txt"]
  },
  {
    "note": "第二格：讀它，再留下結果",
    "argv": ["sh", "-c", "tr a-z A-Z < message.txt > result.txt"]
  },
  {
    "note": "第三格：清理中間檔",
    "argv": ["rm", "message.txt"]
  }
]
```

`note` 只給人和 AI 看，執行前會拿掉。其餘七欄完全就是 proto4-3 的 inst.json：`argv` 必填，另有 `cwd`、`stdin`、`stdout`、`stderr`、`exit`、`envs`。

## 怎麼跑

```sh
/abs/proto4-6/aos-step-json job.json   # 跑第 0 格
/abs/proto4-6/aos-step-json job.json   # 跑第 1 格
/abs/proto4-6/aos-step-json job.json   # 跑第 2 格
/abs/proto4-6/aos-step-json job.json   # 已做完，不再執行；回 100
echo $?                                # 100

/abs/proto4-6/aos-step-json job.json --status
/abs/proto4-6/aos-step-json job.json --reset
```

看不到子程式的錯誤時，加 `--stderr -`；也能給路徑，原樣轉給 aos-exec：

```sh
/abs/proto4-6/aos-step-json job.json --stderr -
```

## 狀態檔

`job.json` 的狀態放在同資料夾的 `job.state.json`：

```json
{"pc":2,"n":3,"done":false,"src":{"n":3,"sha256":"..."},"last":{"pc":1,"exit":0,"kind":"child","at":"2026-09-13T12:00:00+00:00","ms":12},"history":[{"pc":0,"exit":0,"kind":"child","at":"...","ms":3}]}
```

`pc` 是下一格的 0 起算編號；`last` 是上一次結果；`history` 只留最近 50 次。狀態與送給 aos-exec 的 `.aos-step-json/current.json` 都先寫 `.tmp` 再 replace，不會露出半份 JSON。還沒有狀態檔時，`--status` 會印 `{"pc":0,"n":3,"done":false}`。

## 規則

- 子程式回 0：`pc` 加一。最後一格仍回 0，但狀態已是 `done:true`；下一次呼叫開始回 100。
- 子程式回非 0：`pc` 不動，原碼退回；修好後再叫就是重跑同一格。
- aos-exec 自己失敗回 125；用法或逐步 JSON 格式錯回 2；兩種都不推進。
- 沒寫 `cwd` 就用 `job.json` 所在資料夾；相對 `cwd` 也從那裡算。其他相對路徑仍照 inst 規則，以轉完的 cwd 為準。
- 每次都重讀整份程式。`pc > 0` 時內容的 SHA-256 對不上會警告，但仍照目前 `pc` 跑；確定要重來才用 `--reset`。
- `--reset` 只刪狀態檔，不刪程式產物，也不刪 `.aos-step-json/current.json`。

## 放上 kernel

行程 inst.json 可以這樣寫：

```json
{"argv":["/abs/proto4-6/aos-step-json","job.json"],"cwd":"/abs/那個資料夾","stderr":"err.txt"}
```

kernel 每格叫一次；全部完成後 `aos-step-json` 回 100，kernel 就把行程收進 `procs/done/`。

## 逐步 Python

`aos-step-py PROG.py` 把普通 Python 檔裡每個公開的頂層 `def` 當一格；一次只跑下一格。
只有傳入的 `state` dict 會跨格活著，並存進 JSON。完整的 `job.py`：

```python
from pathlib import Path

FACTOR = 2

def _helper(values):
    return [value * FACTOR for value in values]

# 第一格：讀檔進 state。
def load(state):
    state["values"] = [int(x) for x in Path(here, "input.txt").read_text().split()]

# 第二格：用 helper 計算。
def compute(state):
    state["values"] = _helper(state["values"])

# 第三格：叫資料夾工具，讀回 JSON。
def ask_tool(state):
    result = aos.call_dir("tool", read="tool/result.json", json=True)
    state["tool"] = aos.value(result)

# 第四格：寫出結果。
def write(state):
    Path(here, "result.json").write_text(
        __import__("json").dumps(state, ensure_ascii=False) + "\n")
```

執行、看狀態與重來：

```sh
/abs/proto4-6/aos-step-py job.py
/abs/proto4-6/aos-step-py job.py --status
/abs/proto4-6/aos-step-py job.py --reset
/abs/proto4-6/aos-step-py job.py --stderr -
```

`job.py` 的狀態是旁邊的 `job.state.json`，`state` 故意排第一，`steps` 直接列出流程：

```json
{"state":{"values":[2,4]},"pc":2,"n":4,"done":false,"steps":["load","compute","ask_tool","write"],"src":{"n":4,"sha256":"..."},"last":{"pc":1,"step":"compute","exit":0,"at":"...","ms":1},"history":[{"pc":1,"step":"compute","exit":0,"at":"...","ms":1}]}
```

規則很少：只有這支檔案定義、名字不以 `_` 開頭的頂層函式算格，照定義行號排序，固定只收
一個 `state` 參數；回傳值忽略。每格都重新載入整支檔，所以頂層只放 import、常數與 def；
載入副作用由程式作者負責。函式可直接用 `here`（程式資料夾絕對路徑）、`pc` 和 `aos`。
只有 `state` 跨格；它若放不進 JSON，該格失敗、pc 與磁碟狀態不動。例外全文在
`.aos-step-py/error`，也可由 `--status` 看。成功格回 0，做完後再叫回 100。

`aos` 提供：`call(target, ...)`、`call_dir(dir, ...)`、`call_json(path, ...)`、`ok(r)`、
`value(r)`、`llm(endpoint, req, out, timeout_ms=None)`、`llm_text(r)`。`call` 可用
`dir_target`、`timeout_ms`、`stdin`、`capture`、`read`、`read_err`、`json`；底下呼叫
`aos-exec`。`llm` 同步呼叫 `aos-llm call`，並保留 `out.req.json`。兩支工具路徑可由
`AOS_EXEC`／`AOS_LLM` 覆蓋。想逐檔案就在一格裡寫 `aos.call("./other.py")`；想逐 module
就正常 import 後呼叫。

放上 kernel 的 inst 與逐步 JSON 相同，只把 argv 換成
`["/abs/proto4-6/aos-step-py","job.py"]`；最後的 100 會讓 kernel 收工。

## 沒做什麼

兩種執行器都沒有鎖，同一份程式不要同時叫兩次。Python 版沒有保存 module、區域變數、
物件或執行堆疊，也沒有自動重試、分支排程、非同步等待；跨格資料只有 JSON `state`。

## 出處

定案與使用者原話在 [proto4 筆記 §23](../proto4/notes/23-step-json-python.md)；inst 的完整語意見 [proto4-3 exec 文件](../proto4-3/docs/exec.md)。
