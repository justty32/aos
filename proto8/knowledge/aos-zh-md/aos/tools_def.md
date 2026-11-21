# `knowledge/aos/tools_def.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools_def.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 做一個新工具：tools_def

工具是一個位置，有三個部分：entry（跑什麼）、`_metainfo`（它對自己的說明：供參考，不是規則；可省略）和 `_tooldef`（模型看到的東西）。在資料夾裡，它們是檔案 `_entry` 或 `_entry.json`、`_metainfo.json`、`_tooldef.json`；在 JSON 物件裡，它們是鍵 `_entry`、`_metainfo`、`_tooldef`。`_tooldef` 也可以寫成 `_metainfo` 裡的 `tooldef` 鍵；`tools_def` check 和 `aos-tools` 兩種都算，兩個都有時，同一個最上層鍵以獨立的 `_tooldef` 為準。

- 從 Python 骨架做一個新工具並檢查它：`tools_def`（見 `aos/tools_def.json#/tools_def`）。
- 一步一步做（entry 和一個小腳本，然後 `_metainfo`，然後 `_tooldef`）：`tools_def` add_entry、add_metainfo、add_tooldef。
- 用 `fn` 把工具寫成一個 Python 函式（`@fn.tool` 和 `fn.main`；見 `aos/tools_def.json#/fn`）。
- 把它加進你自己的工具：`self_tools` 加上 `{"op": "add", "path": "..."}`（見 `aos/me.json#/self_tools`）。

---

**`#/tools_def`**

# tools_def

一次呼叫一個 op：

- new：`{"op": "new", "path": "my_tools/mul"}` 把骨架（一個能用、把兩個數字相加的工具）抄到新資料夾。`path` 必須還不存在；相對路徑從你的工作區開始，絕對路徑在你能寫的任何地方都行。可選的 `"description"` 填入工具做什麼。`path` 也可以是 `FILE.json#/POINTER`（像 `my_tools/box.json#/tools/mul`）：工具會放進那個 JSON 物件（`_entry`、`_tooldef`、`_metainfo` 鍵），它的腳本 `mul.py` 放在 JSON 檔旁邊；兩個工具可以共用一個 JSON 檔。
- check：`{"op": "check", "path": "my_tools/mul", "sample": {"a": 6, "b": 7}}`。每個項目一行：`ok`、`bad`（附怎麼修）、`made`（它從 `tool.py` 重新編譯了 `_tooldef.json` 和 `_metainfo.json`）、`note`、`example`（它跑描述裡寫的 `Example: {...} -> result` 並比對）、`try`（用 `sample` 呼叫一次）。最後一行是階段：`stage 3 of 3 ... a tool: add it with self_tools ...`。只要有任何 `bad` 行，回覆就以 `tools_def: error: ToolBad ...` 結尾。

新工具的步驟：

1. `tools_def` new。
2. 用 `edit` 只改 `tool.py` 裡 new 印出來的那部分（`@fn.tool` 底下的函式：它的名字、docstring、有型別的參數和函式本體）；它上面的行保留。骨架裡的 `README.md` 有完整範例。
3. 帶 `sample` 跑 `tools_def` check。修好每一行 `bad` 再檢查一次。
4. `self_tools` `{"op": "add", "path": "my_tools/mul"}`。它立刻生效：在你下一次回覆（這一輪）裡直接用它的名字（資料夾名稱，或指標的最後一段）呼叫它，就像任何其他工具。

check 的 `path` 也可以是一個 JSON 檔，或物件裡有 `_entry` 鍵（像 `["python3", "tool.py"]`，從 JSON 檔的資料夾跑）的 `FILE.json#/POINTER`。`self_tools` add 三種都收：資料夾、JSON 檔或 `FILE.json#/POINTER`。

一步一步做，適用於資料夾、JSON 檔或 `FILE.json#/POINTER`（每一步都會說做完之後的階段；已經存在的部分 = `PathExists`）：

1. `{"op": "add_entry", "path": "my_func"}` 寫 entry（資料夾裡是 `_entry.json`，JSON 物件裡是 `_entry` 鍵），並在它旁邊放一個小 Python 腳本（骨架的那個，除非 `"script": "name.py"` 已經在了）：現在 aos-exec 可以跑它。
2. `{"op": "add_metainfo", "path": "my_func"}` 寫 `_metainfo`：腳本是用 `fn` 寫的就從腳本來，否則給 `"description"`（和 `"meta"`）。
3. `{"op": "add_tooldef", "path": "my_func"}` 寫 `_tooldef`：從腳本來，或給 `"description"` 和 `"params": [{"name": "a", "type": "number", "description": "the first number"}]`。

錯誤：`ArgumentsBad`、`OpUnknown`、`PathExists`（換一個路徑）、`PathMissing`、`FileBad`、`PointerMissing`、`MkdirFailed`、`WriteFailed`、`ToolBad`。

---

**`#/fn`**

# fn（把工具寫成一個 Python 函式）

在 `tool.py` 裡，`# ---- your tool` 底下：

```python
@fn.tool
def mul(a: float, b: float) -> float:
    """Multiply two numbers and return the product. Example: {"a": 6, "b": 7} -> 42

    Args:
      a: the first number
      b: the second number
    """
    return a * b


fn.main(mul)
```

- docstring 到 `Args:` 為止是描述。範例寫成 `Example: {...} -> result`：`tools_def` check 會跑它。
- `Args:` 每個參數一行 `name: what it is`。每個參數都要有型別：`str`、`int`、`float`、`bool`、`list`、`dict`（string、integer、number、boolean、array、object），字串清單用 `list[str]`。有預設值（`times: int = 1`）的參數是可省略的。
- 缺描述、型別或參數行 = `SpecBad`，一行說明要加什麼。
- 改成明寫（明寫的勝出，一個參數一個參數算）：`@fn.tool(description="...", params=[fn.param("a", "number", "the first number", enum=[...], items="string")], errors=["CityMissing"], meta={...})`。
- `meta`：只寫跟預設不同的（`side_effect` False、`deterministic` True、`timeout_ms` 10000 ……；0 = 不限）。
- 函式拿到的是檢查過、預設值已填好的參數。回傳字串（原樣印出），或數字、dict 或 list（印成 JSON）。錯誤：`fn.fail("CityMissing", "no such city")`。
- 參數錯在函式跑之前就是 `ArgumentsBad`；函式裡當掉是 `RunFailed`，附行號。
- `python3 tool.py --compile [LOCATION]` 編譯 `tool.py` 並寫出 `_tooldef` 和 `_metainfo`（資料夾得到兩個檔案；`FILE.json#/POINTER` 得到兩個鍵）；`--dry-run` 把兩者印成一個 JSON 物件，什麼都不寫；`--tooldef` / `--metainfo` 印出其中一個。


在 agent.py 裡，同一個函式可以直接放進 `tools=[..., add]`（而 `@fn.hook("before_tool", ...)` 函式放進 `hooks=[...]`）：編譯時會把每一個拉出來，放到定義夾的 `fn/<name>.py`，並讓 `tools.json` / `hookeds.json` 指向它。它只能用內建函式、它自己的變數、`fn` 和 agent.py 最上面 import 的模組；它裡面的相對路徑從 `fn/` 開始。見 templates/agent-python/README.md，"Functions as tools and hooks"。
