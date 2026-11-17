# wf/public/pitfalls — 踩坑與解法（總頁）

← [wf/public](README.md)｜交 commit 與搬補丁的坑見 [patch-and-commit](patch-and-commit.md)；帶 sol 的坑見 [sol-crew](sol-crew.md)；其他主題看 [README 的主題表](README.md#主題)

| 頁 | 收哪些坑 |
|---|---|
| [pitfalls-shell](pitfalls-shell.md) | zsh 不分詞、指令卡到逾時、別 `pkill -f`、zsh 其他會吃字的寫法、Read／Glob 在工作區外被擋、`pgrep -af aos-daemon` 多列的是看顧子行程 |
| [pitfalls-建置與複本](pitfalls-建置與複本.md) | 暫存樹編 C++ 要用 `<名字>_main`、乾淨複本要帶齊依賴、乾淨複本的標準跑法、資料列多了新鍵的斷言、暫存 git 吃進 `.orig`、試真東西別碰原件 |

## 隊長的 shell（Bash 工具）

全文在 [pitfalls-shell「隊長的 shell（Bash 工具）」](pitfalls-shell.md#隊長的-shellbash-工具)。三句話版：zsh 的 `$VAR` 不分詞，要分詞的包 `bash -c`；指令結尾不要放裸的 `ls`、heredoc 寫檔和後續指令分開；不 `pkill -f`，只 kill 自己記下的 pid。
