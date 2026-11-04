# proto8/extras/langs — 用別的語言寫 aos 程式

← [proto8](../../README.md)

**一句話：用一般的程式語言寫一段，編成 aos 的資料夾＋JSON（`_entry`、`loop.json`、`fsm.json`…）。**
編出來的就是普通的檔，跟手寫的一樣，可以直接看、直接手改；跑的時候照舊 `aos-exec`，跟原本用哪個語言寫的無關。兩種都是嘗試性質。

## Janet（[janet/](janet/README.md)）

`aos-janet [--force] 原始檔.janet 輸出資料夾`：原始檔最後 `(def program (dir …))`，編成那個資料夾；另有 seq／par／if 組合子。要裝 Janet。
設計與代定：[thinking 2026-10-24-janet-compile](../../thinking/2026-10/24/janet-compile.md)。

## Lua（[lua/](lua/README.md)）

`aos-lua build 原始檔.lua 輸出`：原始檔 `return` 一個 table（資料夾就是 table），編成資料夾；`json`、`ls` 只印不寫。lua 5.x、luajit、`nvim -l` 都能跑。
設計與代定：[thinking 2026-10-24-lua-nvim](../../thinking/2026-10/24/lua-nvim/README.md)。

nvim 外掛封存在 `proto8/archive/nvim/`。
