# wf/public/pitfalls — 踩坑與解法（總頁）

← [wf/public](README.md)｜交 commit 與搬補丁的坑另見 [patch-and-commit](patch-and-commit.md)、[交件與放行](交件與放行.md)；帶 sol 的坑見 [sol-crew](sol-crew.md)

11-14 收尾整理時照主題拆開（原本一頁 8.1 KB），本頁只留導航。投稿加到對應那一頁。

| 頁 | 收哪些坑 |
|---|---|
| [pitfalls-shell](pitfalls-shell.md) | 隊長的 shell（zsh 不分詞、指令卡到逾時、別 pkill -f）、zsh 其他會吃字的寫法、Read／Glob 在工作區外被擋、`pgrep -af aos-daemon` 多列的是看顧子行程 |
| [pitfalls-建置與複本](pitfalls-建置與複本.md) | 暫存樹編 C++ 要用 `<名字>_main`、乾淨複本要帶齊依賴、乾淨複本的標準跑法、暫存 git 吃進 `.orig`、試真東西別碰原件 |
| [交件與放行](交件與放行.md) | 封存或搬檔預設留指標頁不帶 `--rm`（原本在本頁）、claim 的坑、放行 |
| [活樹旁邊](活樹旁邊.md) | 存檔即生效的檔、唯讀查看的界線、查祕密不落地、換樹 pin |
| [等隊員與讀信](等隊員與讀信.md) | 等隊員不帶逾時、長回合讀不到信、信交錯、時刻記錯 |

## 隊長的 shell（Bash 工具）

這一節搬到 [pitfalls-shell「隊長的 shell（Bash 工具）」](pitfalls-shell.md#隊長的-shellbash-工具)；標題留在這裡，是因為 07 的連結指到本頁這個錨點。三句話版：zsh 的 `$VAR` 不分詞，要分詞的包 `bash -c`；指令結尾不要放裸的 `ls`、heredoc 寫檔和後續指令分開；不 `pkill -f`，只 kill 自己記下的 pid。
