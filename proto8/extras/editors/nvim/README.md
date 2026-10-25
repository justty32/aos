# proto8/extras/editors/nvim — 在 nvim 裡用 aos

aos_nvim - 在 nvim 裡跑 aos 程式、看 trace、對 agent 丟題、跳到 `檔#/指標`、預覽 Lua 編出的 JSON（嘗試，2026-10-24）

← [proto8](../../../README.md)｜設計與代定：[thinking 2026-10-24-lua-nvim](../../../thinking/2026-10-24-lua-nvim.md)｜Lua 寫 aos：[langs/lua](../../langs/lua/README.md)｜測試 `tests/smoke.lua`（`proto8/tests/test_lua_aos.py` 叫它）

| 檔 | NAME |
|---|---|
| `lua/aos_nvim/init.lua` | aos_nvim - 指令、面板、叫子行程 |
| `lua/aos_nvim/pointer.lua` | aos_nvim.pointer - 在 JSON 原文裡找 `#/指標` 指到第幾行第幾欄 |
| `init_min.lua` | 不碰你的設定、單獨試用：`nvim --clean -u init_min.lua` |
| `tests/smoke.lua` | headless 把每個指令走一遍 |

## 指令

| 指令 | 做什麼 |
|---|---|
| `:AosWs [資料夾]` | 看／設工作區（`setup{ws=}` ＞ `vim.g.aos_ws` ＞ nvim 的 cwd；`init_min.lua` 拿 `$AOS_WS` 當 `ws`） |
| `:AosExec [目標 args...]` | `aos-exec --ws 工作區 目標`，輸出一行行進下方面板，跑完印結束碼和 trace 最後 20 格。沒給目標＝目前檔案往上找、第一個有 `_entry` 的資料夾 |
| `:AosExec!` | 跑目前這個檔本身（例 `fsm.json` 帶 `_entry`＝fsm 只走一格，一步一步看） |
| `:AosTrace` | 看 `工作區/.stack/trace.jsonl`，一格一行（時間、格名、結束碼、毫秒） |
| `:AosSay 話` | 放一題到 `工作區/new/`、等 `out/` 的答案印在面板；有 `aos-say`／`aos-listen`（[proto8/extras/human](../../human/README.md)）就用它們，沒有就自己寫檔、輪詢 |
| `:AosSay! 話` | 同上，放完順便替你跑一次目前的 agent（同 `:AosExec`） |
| `:AosGoto [檔#/指標]` | 跳過去：資料夾＝它的 `_entry`、沒副檔名又不在＝補 `.json`（同 aos-exec）、`#/…` 開頭＝目前這個檔。沒給＝游標下那串字 |
| `:AosLuaPreview [路徑[#/指標]]` | 目前的 `.lua` 用 aos-lua 編一次、在面板看 JSON |
| `:AosLuaBuild [輸出]` | 編成資料夾（預設＝原始檔旁邊去掉 `.lua` 的同名資料夾），面板列出寫了哪些檔 |

面板是同一個 `aos://panel`，重複叫只換內容不疊視窗，按 `q` 關。叫子行程時 PATH 前面接上這個 repo 的 `impls/*/bin`、`bin`、`human/bin`、`langs/lua/bin`，nvim 自己的 PATH 不改（`setup{bins=}` 可以換）。

## 裝進你的 LazyVim（不用改別的檔）

新增 `~/.config/nvim/lua/plugins/aos.lua`（也就是 `~/notes/projects/my_lazyvim_settings/lua/plugins/aos.lua`）：

```lua
return {
  { dir = "~/repo/simple_tools/aos/proto8/extras/editors/nvim", name = "aos_nvim",
    cmd = { "AosExec", "AosTrace", "AosSay", "AosGoto", "AosLuaPreview", "AosLuaBuild", "AosWs" },
    config = function() require("aos_nvim").setup({}) end },
}
```

鍵要不要綁、綁哪個自己定；`init_min.lua` 裡有一組試用的（`,ax` 跑、`,a1` 走一格、`,at` trace、`,ag` 跳、`,ap` 預覽、`,ab` 編）。

## 先不動設定試

```sh
cd ~/code/try/lua-aos && python3 try.py          # 先編出 build/ 與假腦跑過的 ws-dan/
AOS_WS=$PWD/ws-nvim nvim --clean -u ~/repo/simple_tools/aos/proto8/extras/editors/nvim/init_min.lua build/agent_dan/fsm.json
```

進去後：`:AosSay! 17*23 是多少？` → 面板出答案；`:AosTrace`；游標放在 `"idle"` 上 `,ag` 跳到 `idle/_entry`；開 `~/repo/simple_tools/aos/proto8/extras/langs/lua/examples/agent_dan.lua` 按 `,ap` 看編出來的 JSON。
