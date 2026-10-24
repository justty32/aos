# proto8/langs/lua — 用 Lua 寫 aos

aos-lua - 把一份 Lua 原始檔編成 aos 的資料夾＋JSON（嘗試，2026-10-24）

← [proto8](../../README.md)｜設計、對照表、代定：[thinking 2026-10-24-lua-nvim](../../thinking/2026-10-24-lua-nvim.md)｜nvim 外掛 [editors/nvim](../../editors/nvim/README.md)｜測試 `proto8/tests/test_lua_aos.py`

使用者 10-24：「再來是lisp/lua編譯成我們這套的方式。……但其實lua也不錯，可以的話接入nvim也挺好」。aos 把資料夾當成 Lua 的 table（C-71），所以「Lua 寫 aos」就是：寫一個 table，編成資料夾。編完就只剩檔案，跑的時候照舊 `aos-exec`，跟 Lua 無關。

| 檔 | NAME |
|---|---|
| `aos.lua` | aos - 建構子（dir、file、script、inst、loop、fsm、daemon、env、ref…）＋JSON 編碼＋攤平成檔案清單 |
| `bin/aos-lua` | aos-lua - 命令列：`build`（寫出來）、`json`（印一個檔或一段 `#/指標`）、`ls`（列出會寫哪些檔） |
| `examples/agent_ann.lua` | 全內嵌的 agent-ann（loop＋fsm＋三張單子），編出來跟 [demo/agent-ann](../../demo/README.md) 一樣 |
| `examples/agent_dan.lua` | 會用工具的 agent-dan，工具與 agent 都是 Lua 函數，編出來跟 demo/agent-dan 一樣 |
| `examples/clocks.lua` | 一個 daemon 顧三個時鐘 loop，子項用 `for` 迴圈產生 |

## 用法

```sh
R=~/repo/simple_tools/aos/proto8
$R/langs/lua/bin/aos-lua build $R/langs/lua/examples/agent_dan.lua /tmp/dan   # 寫成資料夾
$R/langs/lua/bin/aos-lua json  $R/langs/lua/examples/agent_dan.lua 'fsm.json#/states/think'
nvim -l $R/langs/lua/bin/aos-lua ls $R/langs/lua/examples/clocks.lua          # 沒有 lua 時用 nvim 跑
```

lua 5.x、luajit、`nvim -l` 三種都能跑，編出來逐位元組一樣（測試有比）。原始檔裡 `require("aos")` 就拿得到，`aos.read("相對路徑")` 從原始檔所在資料夾算。

## 一段例子

```lua
local aos = require("aos")
return aos.dir {
  _entry = aos.script("#!/bin/sh\nexec aos-loop loop.json\n"),
  ["loop.json"] = aos.loop { exec = "fsm.json", max = 40 },
  ["fsm.json"] = aos.fsm {
    _entry = aos.self_entry("aos-fsm"),
    start = "idle",
    states = {
      { "idle",  exec = "idle", next = "think" },
      { "think", exec = aos.inst { argv = { "python3", "brain.py" }, timeout_ms = 120000 }, next = "act" },
      { "act",   exec = aos.inst { argv = { "python3", "act.py" }, timeout_ms = 60000 }, next = "idle" },
    },
  },
}
```

編出來的 `fsm.json`：

```json
{
  "_entry": ["aos-fsm", {"$env": "AOS_CF"}],
  "start": "idle",
  "states": {
    "idle": {"exec": "idle", "next": "think"},
    "think": {
      "exec": {"argv": ["python3", "brain.py"], "timeout_ms": 120000},
      "next": "act"
    },
    "act": {
      "exec": {"argv": ["python3", "act.py"], "timeout_ms": 60000},
      "next": "idle"
    }
  }
}
```

## 規則（照寫什麼編什麼，不偷加）

- 資料夾裡的值：`aos.dir{}`＝子資料夾、`aos.script(文字)`＝可執行檔（755）、`aos.file(文字)` 或一般字串＝純文字檔（644）、一般 table 或建構子＝JSON 檔。檔名照字面，不補 `.json`。
- 建構子回的就是原樣的物件，只在寫的當下查形狀，錯了指到原始檔那一行：`aos.inst` 要非空 `argv`；`aos.loop` 要 `exec`；`aos.fsm` 查 `start`、每格的 `exec`、`next` 在表上、`next` 頭尾沒空白（同 aos-fsm 開跑時的查法，N-36）；`aos.env`／`aos.ref` 只收 `path`、`prefix` 兩個修飾。
- JSON 的 key 順序：`_entry`、`start`、`states`、`exec`、`next`、`argv`… 這些常用的在前，其餘字母序；`aos.obj{{k, v}, ...}` 或 fsm 的陣列寫法照寫的順序。空 table＝`{}`，空陣列寫 `aos.array()`，`null` 寫 `aos.null`。
- `build` 的輸出已經在：清單上的檔覆寫、權限照設，清單外的不動不刪。
- 錯：stderr 一行 `aos-lua: 代號 原因`、退 1；代號 `ArgumentsBad`、`SourceBad`、`PathMissing`、`WriteFailed`。
