# 「編譯這塊變成整套一個 Python 程式庫」的設計稿與施工計劃（11-20，線 aos-pylib-plan-1120）：只出稿，沒改任何程式、範本、條文、知識庫

← [2026-11-20](../README.md)｜材料：[aos-compile-base-1120](../aos-compile-base-1120/README.md)（調查與四題裁定）、[aos-hook-iface-1120](../aos-hook-iface-1120/README.md)、[aos-init-kernel-1120](../aos-init-kernel-1120/README.md)

使用者 11-20 選了「整套是一個程式庫」「抽出來」「兩種都收，明寫的贏」「一起，同一套寫法」，又把 `defs.extern` 改成「編譯的時候就是只生成symlink…註釋要說別濫用」（原話全文 [00](00-使用者原話.md)）。這一夾是照這些話出的設計與計劃。讀 HEAD `15f6a5bc1`；原型在 repo 外，沒起 aos 行程、沒叫模型。

## 一頁結論

```python
from aos.py import fn                       # 新：把函數標成工具／hook 的那一半
from aos.py.agent import defs               # 不變
std = defs.std

@fn.tool
def add(a: float, b: float) -> float:
    """Add two numbers. Example: {"a": 2, "b": 3} -> 5

    Args:
      a: the first number
      b: the second number
    """
    return a + b

@fn.hook("before_tool", condition="ws_write")
def no_secrets(event):
    if "secret" in str(event.get("arguments", "")):
        return fn.block("the arguments mention a secret")

reviewer = defs.Agent(
    "Look things up in the workspace and answer by mail.",
    system=defs.extern("../shared/system.txt"),          # 編成一個連結（別濫用）
    tools=[std.pack("look"), add],
    llm={}, fsm=std.fsm(), hooks=[std.hooks(), no_secrets],
)
defs.main(reviewer)                         # python3 agent.py --compile／--dry-run，旗標都不變
```

- **程式庫的樣子**：一種東西一個物件，兩個方法——`.dry_run()` 只算、`.compile(夾)` 算完寫進夾；`defs.main(物件)` 只是包一層旗標。fsm 現在就能單獨編譯；kernel 以後寫一個類別、實作一個方法就接上（[01](01-程式庫長相.md)、[02](02-去留對照與kernel接口.md)）。
- **函數當工具／hook**：編譯時每個函數抽成定義夾的 `fn/<名>.py`，長得就是一支手寫的工具檔，之後跟 `agent.py` 無關。說明與參數從 docstring 與型別註記抽，明寫的一個參數一個參數蓋過去。hook 回 `None`＝放行、回 dict＝改鍵、回 `fn.block("原因")`＝攔下（[03](03-函數當工具與hook.md)、[04](04-函數-依賴與互動.md)）。
- **`defs.extern(目標)`**：那一欄編成連結，照你寫的字面存；目標不在＝編譯報錯；fsm 只能指同一夾（讀程式推的，施工先實測）（[05](05-extern-symlink.md)）。
- **跟已定的東西**：二十來條逐條對過，大多合；**六條衝突要帶給使用者**（`compile` 的字義、欄位大小寫、新名字 `fn` 與工具骨架換寫法、連結被寫穿、fsm 的 extern 有限制、`agent_def new` 讓函數工具指回原夾）（[06](06-對照與衝突.md)）。
- **施工六刀**：第 0 刀（共用的底，外面看不出不同）不依賴任何題；第 2、4 刀照今天選項上的字做、只需告知；第 1、3 刀等第 4 題（`fn` 這個名字）。施工仍要使用者另外點頭（[07](07-施工計劃.md)）。
- **跟 hook 介面那條線（[aos-hook-plan-1120](../aos-hook-plan-1120/README.md)）對過**：事件表改成問物件要（方法，照身體回）；兩條線都會動的那段（寫 `loop.json` 的接線、`interfaces.json` 的 `hook_points`）由後開工的那條帶；掛到這隻不會發的事件是擋還是警告，兩種都接得上（[04](04-函數-依賴與互動.md)）。
- **待裁十題**，可直接貼成選項框（[08](08-待裁題.md)）。
- **Argon 審過一次**：19 點審查、6 個提案，採納表在 [11](11-採納表.md)。

## 分檔

| 份 | 內容 |
|---|---|
| [00-使用者原話](00-使用者原話.md) | 11-20 的話逐字、頂層的解讀、還沒問的 |
| [01-程式庫長相](01-程式庫長相.md) | agent、工具、fsm 各自寫起來的樣子；類別與函式 |
| [02-去留對照與 kernel 接口](02-去留對照與kernel接口.md) | 昨天定名的每樣東西去哪了；loop、fsm 的地位；kernel 的接口 |
| [03-函數當工具與 hook](03-函數當工具與hook.md) | 裝飾器、抽出的檔、說明與參數的規則、hook 回話 |
| [04-函數的依賴與互動](04-函數-依賴與互動.md) | 用到外面的東西怎麼辦；事件表的接點；跟連結選項、`defs.load`、同名的互動 |
| [05-extern 的 symlink 版](05-extern-symlink.md) | 語意、搬動時會怎樣、被寫穿、「別濫用」文字草稿 |
| [06-對照與衝突](06-對照與衝突.md) | 逐條對照；要帶給使用者的衝突 |
| [07-施工計劃](07-施工計劃.md)、[07b](07b-施工計劃-第0到2刀.md)、[07c](07c-施工計劃-第3到5刀.md)、[07d](07d-施工-給設計的意見.md) | 總表與共通驗收；逐刀細節；細化時對設計提的 18 條意見與處理 |
| [08-待裁題](08-待裁題.md) | 九題：選項、後果、擋第幾刀 |
| [09-原型](09-原型.md) | repo 外小原型的結果與沒驗到的 |
| [10-Argon 原文](10-Argon原文.md)、[11-採納表](11-採納表.md) | 審查原文；逐點採不採、為什麼 |
| [12-使用者已答](12-使用者已答.md) | 11-20 選項框答的四題逐字（第 1、4、5、6 題）、第 2、3 題已告知未明確裁、還沒問的；「兩邊都開工」 |

## 這條線自己定的設計選擇（不是使用者說的）

1. 裝飾器放在新模組 `fn`（`from aos.py import fn`），不叫 `@defs.tool`。
2. 抽出的檔保留裝飾器那一行、結尾 `fn.main(函數)`，執行時當場算說明書；不另存一份 tooldef 的 json。
3. 抽出的檔放 `fn/<工具名或 hook 名>.py`，工具與 hook 同一夾；`tools.json` 登記成「可執行檔工具」。
4. 「明寫的贏」是一個參數一個參數算；docstring 只認 `Args:` 這一種格式。
5. 攔下的記號是 `fn.block("原因")`；回字串、數字算回話寫錯。
6. 函數只能用標準庫與裝好的套件；同檔的名字、旁邊的模組都報錯（三種更鬆的做法列成待裁第 5 題）。用到哪些外面的名字交給 Python 自帶的 `symtable` 算。
7. `defs.load` 的底有函數時，衍生那夾重抽一份；底的 extern 指到底那夾裡面的檔時不給接（報錯）。
8. `物件.compile(夾)` 寫、`物件.dry_run()` 只算；類別叫 `defs.Agent`（跟把手的類別同名不同物）；欄位小寫；`base.tools(...)` 改叫 `base.pack(...)`。
9. `defs.extern` 只收一個參數（目標）；連結照字面存；目標不存在是錯誤不是提醒；`--dry-run` 印 `{"$symlink": …}`；`defs.load` 的底有 extern 時能接；`agent_def check` 多查斷鏈；編譯時不另外印提醒。
10. fsm 的 extern 只准指同一夾（待實測）。
11. 內部檔怎麼分（`spec_base`、`fn_mark`、`fn_run`、`fn_spec`…）與六刀的切法。

## 暫存

公司 WSL `~/.aos/scratch/aos-pylib-plan-1120/`（原型，可丟）。
