設計之三：Python 函數當工具與 hook——裝飾器寫法、抽出來的檔長什麼樣與放哪、說明與參數「自動抽與明寫都收、明寫的贏」的精確規則、hook 回話的記號。

← [README](README.md)｜上一份：[02](02-去留對照與kernel接口.md)｜下一份：[04-函數的依賴與互動](04-函數-依賴與互動.md)

## 先講結論

- **寫法**：`@fn.tool`（或 `@fn.tool(明寫的東西)`）、`@fn.hook(事件, 條件與選項)`；函數本身放進 `tools=[…]`、`hooks=[…]`。不自動登記——放進哪隻 agent 由你明寫。
- **抽出來**：編譯時每個函數各寫成定義夾裡的 `fn/<工具名或 hook 名>.py`，一支可執行的檔；`tools.json`／`hooks.json` 用相對路徑指到它。之後跟 `agent.py` 無關，能手改，下次編譯整份蓋。
- **抽出的檔＝一支照 `fn` 寫法手寫的工具檔**（裝飾器那行也照搬）。所以執行時只有一條路：`fn.main(函數)`。
- **hook 的回話**：`return None`＝放行；`return {鍵: 值}`＝改那些鍵；`return fn.block("原因")`＝攔下（結束碼 10）。

## 裝飾器

```python
@fn.tool                                         # 全部自動抽
@fn.tool(meta={"side_effect": True})             # N-68 的 metainfo，同今天的 META
@fn.tool(name="sum", description="…", params=[fn.param("b", "integer", "…", enum=[1, 2])], errors=["TooBig"])

@fn.hook("before_tool")                                              # 事件名；同 hooks.json 那格的 event
@fn.hook("before_tool", condition="ws_write", timeout_ms=5000)       # 其餘關鍵字＝那格的鍵，照字面寫進去
@fn.hook("on_clock", every_cycles=10, name="tidy")                   # name＝hook 名，預設是函數名
```

- 那格的 `async` 是 Python 的保留字，寫成 `async_=True`。
- 裝飾器只在函數上做個記號、回原函數（函數照樣能在 `agent.py` 或測試裡直接叫）；什麼都不驗，驗在編譯時。

## 抽出來的檔

`fn/add.py`（權限 755）：

```python
#!/usr/bin/env python3
"""add - Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5"""
# ---- setup: find the aos package ----
...（找 aos 套件：只認 `$AOS_HOME/lib`；並把 `fn/` 自己從找模組的路徑拿掉，見 04）
from aos.py import fn
（函數用到的 import，照原文搬）

@fn.tool
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5
    ...
    """
    return a + b


fn.main(add)
```

| 項 | 定法 | 理由 |
|---|---|---|
| 放哪、叫什麼 | 定義夾的 `fn/<最後登記的名字>.py`：工具用 `tools.json` 那格的鍵（經 `name=`、`base.pack(prefix=, rename=)` 之後的），hook 用 hook 名；工具與 hook 同一夾 | 檔名跟腦看到的名字、錯誤行開頭的名字是同一個；改了名的兩支不會因為 Python 函數同名而撞（Argon A5）。兩格搶同一個檔名（兩支工具同名、或一支工具與一個 hook 同名）＝`SpecBad` |
| `tools.json` 那格 | `"<工具名>": {"path": "fn/<工具名>.py"}`（工具名預設＝函數名） | 相對路徑從 `tools.json` 那一夾算，就是定義夾；這是今天「可執行檔工具」那一種，aos 問它 `--tooldef` 拿說明書 |
| `hooks.json` 那格 | `"<hook 名>": {"event": …, "handler": "fn/no_secrets.py", …}` | handler 的相對路徑同樣從 `hooks.json` 那一夾算 |
| 檔頭第一行 | `"""名 - 說明的第一行"""`；**不寫**「從哪支 agent.py 編來」 | 產物不記原始碼（C 與 .o；昨天裁定拿掉了「Generated from…」那種記號） |
| 說明書（tooldef）存哪 | 不另存一份 json；`fn/add.py --tooldef` 當場從函數算出來 | 手改 `fn/add.py` 的 docstring＝改了說明書，兩者不會不同步 |
| 拿掉函數後留下的舊 `fn/x.py` | 不刪 | 同昨天定的「編譯不刪檔」；沒人指到它就不會被叫 |

**原型踩到的坑（把編譯庫的 import 抄進產物）怎麼沒了**：`fn` 這個模組本身就是「執行時也要用」的那一半，很小、不載入 `defs` 那一套（`agent_spec`、讀包、`defs.load`）；產物只 import `fn`。函數裡用到 `defs` 或 `std`＝編譯時報錯（[04](04-函數-依賴與互動.md)）。

## 說明與參數：兩種都收，明寫的贏

| 東西 | 自動抽 | 明寫 | 兩個都有時 |
|---|---|---|---|
| 工具名（`tools.json` 那格的鍵） | 函數名 | `name=` | 明寫的 |
| 錯誤行開頭的名字（`名: error: …`） | 照今天的規矩看檔名：`tool.py`＝夾名，其他＝檔名去 `.py`（抽出的 `fn/add.py`＝`add`） | `name=` | 明寫的 |
| 說明 | docstring 裡 `Args:` 那一行之前的全部文字（去頭尾空白） | `description=` | 明寫的整段取代 |
| 每個參數的型別 | 型別註記：`str`／`int`／`float`／`bool`／`list`／`dict` → JSON 的 string／integer／number／boolean／array／object；`list[str]` 這種多帶 `items` | `fn.param("名", 型別, 說明, enum=, items=)` | **一個參數一個參數算**：明寫了的那個參數整格用明寫的，沒明寫的照自動抽 |
| 每個參數的說明 | docstring 的 `Args:` 段，一行 `名: 說明`，縮得更深的下一行算接續 | 同上 | 同上 |
| 必填與預設值 | 函數簽名：沒預設值＝必填；有＝選填，預設值寫進說明書 | 不能明寫（一律看簽名） | — |
| 錯誤代號 | 掃那支檔裡的 `fn.fail("代號", …)`（同今天 `tool_spec` 的掃法）；**只在印說明書或編譯時掃**（`--tooldef`、`--compile`、`--dry-run`），平常執行不讀原始碼 | `errors=[…]` | 兩邊合起來 |
| metainfo | N-68 的預設值 | `meta={…}` | 明寫的鍵蓋預設 |

docstring 的格式（只認這一種）：

```
第一段起就是說明，可以很多行、可以有空行。

Args:
  a: the first number
  b: the second number,
     continued on a deeper line
Returns:（這種「一個詞加冒號」的行＝Args 段結束；之後的不讀）
```

編譯時報 `SpecBad`（訊息寫成怎麼改）的情形：

| 情形 | 訊息大意 |
|---|---|
| 沒有說明（沒 docstring 也沒 `description=`） | `tool add has no description: write a docstring, or description=` |
| 某個參數沒有型別註記、或註記不是那六種，也沒明寫 | `parameter b needs a type (str, int, float, bool, list, dict), or fn.param("b", ...)` |
| 某個參數沒有說明 | `parameter b has no description: add "b: ..." under Args: in the docstring, or fn.param("b", ...)` |
| `Args:` 或 `params=` 提到函數沒有的參數 | `… the function has no parameter c` |
| 簽名有 `*args`、`**kwargs`、只能照位置或只能照名字的參數 | `plain named parameters only` |

型別註記是字串時（檔頭有 `from __future__ import annotations`）照名字認，結果一樣；抽出的檔若原檔有那一行，把它放在產物的最前面（Python 規定它要在檔頭）。

不支援、也不打算教的：`typing.Annotated[str, "說明"]`、Sphinx 或 NumPy 風格的 docstring。hook 函數不需要 docstring（有的話第一行當檔頭那句）。

## hook 的回話

hook 函數收一個參數 `event`（那次事件的 JSON，就是今天 handler 從 stdin 讀到的那份）。

| 函數回 | 抽出的程式做 | 引擎看到 |
|---|---|---|
| `None`（或沒寫 return） | 不印、退 0 | 照常 |
| 一個 dict，例 `{"arguments": {...}}` | 印成一行 JSON、退 0 | 改那些鍵（只認那個事件能改的鍵，照舊由引擎管） |
| `fn.block("原因")` | 印原因、退 10 | 攔下；原因就是引擎回的 `text` |
| 別的東西（字串、數字…） | 一行 `名: error: ReplyBad …`、退 1 | hook 失敗，照 `on_error` |
| 丟例外 | 一行 `名: error: RunFailed 例外名: 訊息 (檔 行號)`、退 1 | 同上 |

- 想印除錯訊息寫到 stderr（`print(..., file=sys.stderr)`）；stdout 是回話。
- 工具函數裡用 `fn.block`＝編譯時 `SpecBad`（工具沒有「攔下」）。
- 工具函數：回字串照印、回別的印成 JSON、回 `None` 不印；要報自己的錯 `fn.fail("代號", "原因")`（同今天的 `ts.fail`）；其他例外＝`RunFailed` 帶行號。參數照說明書先驗過才叫函數（`ArgumentsBad`）。
