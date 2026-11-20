設計之二：昨天定名的每樣東西在程式庫裡的去留與對應（逐項表）、loop 與 fsm 的地位、kernel 以後怎麼接上（只留接口與示意，不設計 kernel 本身）。

← [README](README.md)｜上一份：[01](01-程式庫長相.md)｜下一份：[03-函數當工具與 hook](03-函數當工具與hook.md)

## 先講結論

- **名字不動的**：`from aos.py.agent import defs`、`defs.main`、`--compile [--static|--dynamic] [夾]`、`--dry-run`、`--help`、`defs.load`、`defs.drop`、`defs.lib`、`defs.tool(名, 路徑)`、`defs.home`／`defs.env`、`defs.state`／`defs.fsm`、`std.pack`／`std.tool`／`std.fsm`／`std.hooks`、`tool.py` 的四個旗標。
- **寫法換了的四處**（都是「整套是一個程式庫」那個選項帶出來的，列在 [06「要帶給使用者的衝突」](06-對照與衝突.md#要帶給使用者的衝突)）：大寫常數不再是介面、`defs.compile`／`defs.write` 兩個函式變成物件的方法、`defs.load` 回的欄位名變小寫、工具骨架從 `ts.main(run, DESCRIPTION, PARAMS, META)` 變成 `@fn.tool`＋`fn.main`。
- **意思換了的一處**：`defs.extern`（使用者今天定的，[05](05-extern-symlink.md)）。

## 逐項

| 昨天（11-19）的 | 程式庫裡 | 說明 |
|---|---|---|
| `from aos.py.agent import defs` | 不變 | |
| 大寫常數 `DESCRIPTION`／`SYSTEM`／`TOOLS`／`LLM`／`FSM`／`HOOKS`（＋`META`／`INTERFACES`／`FILES`） | 變成 `defs.Agent(...)` 的參數（第一個位置參數是說明，其餘用小寫關鍵字） | 大寫常數不再有特別意思；要先放進變數再傳進去照樣可以（長的 system 文字這樣寫比較好讀） |
| `defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=HOOKS)` | `defs.main(agent)` | 名字不變、收的東西變成一個物件；舊的收法不留（proto8 當沒有舊版） |
| `python3 agent.py --compile [--static \| --dynamic] [夾]`、`--dry-run`、`--help` | 不變 | 輸出的格式也不變；`--dry-run` 多兩種內容（程式檔印成字串、連結印成 `{"$symlink": "目標"}`） |
| `defs.compile(...)`（算出不寫）、`defs.write(夾, 結果)` | `物件.dry_run()`、`物件.compile(夾)` | **`compile` 這個字的意思變了**：昨天是「只算」，今天照選項框那句「編譯＝物件.compile(夾)」是「算完寫進夾」；「只算」那個改叫 `dry_run`，跟旗標同名 |
| `defs.load("../reviewer")` | 名字不變；回那支 `agent.py` 交給 `defs.main` 的那個物件（一份新的） | 欄位 `base.TOOLS`、`base.HOOKS`、`base.FSM`… 變 `base.tools`、`base.hooks`、`base.fsm`…；`base.tools(prefix=, rename=, exclude=)` 這個方法改叫 `base.pack(...)`（`tools` 這個名字讓給欄位） |
| `defs.drop("grep")`、`defs.fsm(base.fsm, [...], drop=[...])` | 不變 | |
| `defs.lib("my", 路徑)`、`std.pack(...)`、`std.tool(...)`、`std.fsm()`、`std.hooks()` | 不變 | pack 與 tool 兩種寫法維持（使用者 11-20「這沒差」） |
| `defs.tool(名, 路徑, **其他)` | 不變 | 登記一支現成的工具；函數工具是另一個東西（`@fn.tool`） |
| `defs.home`、`defs.env`、`defs.state` | 不變 | |
| `defs.extern("system.txt")`（這份檔手寫、不編不蓋） | `defs.extern(目標)`：這一欄編成連結 | 使用者今天定；同樣的寫法意思不同了，`defs.extern("system.txt")` 會變成「連到自己」，編譯時報錯並說明（[05](05-extern-symlink.md)） |
| `from aos import tool_spec as ts`；`ts.main(run, DESCRIPTION, PARAMS, META)`；`ts.param`、`ts.fail` | `from aos.py import fn`；`@fn.tool`＋`fn.main(函數)`；`fn.param`、`fn.fail` | `run(args)`（收一個 dict）變成普通的具名參數；`tool_spec` 留作內部零件 |
| `python3 tool.py --compile [位置]`、`--dry-run`、`--tooldef`、`--metainfo`、沒旗標＝執行 | 不變 | |

新增的名字：`defs.Agent`、`.compile`／`.dry_run` 兩個方法、`fn`（`tool`、`hook`、`param`、`fail`、`block`、`main`）。

## loop 與 fsm 在庫裡的地位

| | 今天 | 程式庫裡 |
|---|---|---|
| fsm | `defs.fsm(...)` 回驗好的表，只能交給 `defs.main` 才變成 `fsm.json` | 回的東西自己就能 `.compile(夾, name="fsm.json")`；放進 `defs.Agent(fsm=…)` 也照舊 |
| loop | 沒有宣告，內容寫死在 `compile()` 裡（`interval_ms` 300） | **內部**有一塊「loop」（算出 `loop.json` 的那幾行獨立成一個小類別，agent 用它、以後 kernel 也用它）；**要不要讓人寫** `defs.loop(every_ms=…)`、`defs.Agent(loop=…)` 取決於 A3，沒裁之前不開放，產物一字不變 |

「一塊東西單獨編譯時寫進哪一夾、叫什麼名」：都由呼叫的人明寫在 `.compile(夾, name=…)` 上，庫不猜、不找。這跟「資料夾即命名空間」「別的庫明寫路徑」是同一個方向，不必另立規則。

## kernel 以後怎麼接上（只留接口）

要讓一種新東西能編譯，只要寫一個類別、實作一個方法：

```python
class Unit:                                   # 在 aos/spec_base.py（內部）
    def events(self):                         # 這個物件收哪些 hook 事件（回一張事件表）；None＝不收 hook
        return None                           # 是方法不是固定的表：同是 Agent，有沒有 fsm 收的事件不同
    def _files(self, folder, link, warn):     # ← 新東西只寫這個：回 {夾裡的相對檔名: 內容}
        ...
    def dry_run(self, folder=None, link="static"): ...      # 底座給
    def compile(self, folder, link="static"): ...           # 底座給（暫存檔＋改名、直接蓋）
```

底座另外給的：`main(物件)` 的旗標殼、`SpecBad`、推名字、`defs.extern`、函數的抽出（`fn/…`）、照 `events()` 回的表驗 hook。

示意（**不是設計**，鍵名照今天的 `kernel.json`；入口名取決於 A2）：

```python
from aos.py import fn
from aos.py.kernel import defs                # A2 沒裁：也可能是同一個 defs

@fn.hook("before_verdict")                    # 同一個 fn；事件照 kernel 那張表驗
def prio(event): ...

k = defs.Kernel("Main llm kernel", knobs={"slots": 2}, hooks=[prio])
defs.main(k)                                  # python3 kernel.py --compile
```

[aos-compile-base-1120/03](../aos-compile-base-1120/03-A-kernel與loop-fsm.md) 數的六個卡點，在這個形狀下的去處：

| 卡點 | 去處 |
|---|---|
| 1、2、4（`_entry`、`loop.json`、`interfaces.json` 寫死成 agent 的） | 那幾行在 `Agent._files` 裡，kernel 寫自己的 `_files` |
| 3（`system`／`tools`／`llm` 必填） | 是 `Agent` 的參數，跟 kernel 無關 |
| 5（hook 用 agent 的事件表驗） | 每種東西自己的 `events()` |
| 6（`kernel.json` 一份裝很多種） | kernel 自己的 `_files` 決定，屬於 kernel 的設計 |

kernel 本身長什麼樣（幾件、哪些可選）等 [aos-init-kernel-1120](../aos-init-kernel-1120/README.md) 的八題；本線不排它的刀。
