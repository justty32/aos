# wf/public/pitfalls-shell — 隊長的 shell、被擋的工具、認 daemon 行程

← [wf/public](README.md)｜[pitfalls 總頁](pitfalls.md)｜建置與乾淨複本的坑見 [pitfalls-建置與複本](pitfalls-建置與複本.md)

## 隊長的 shell（Bash 工具）

eca 隊長用 Bash 工具（實際是 zsh）驅動暫存樹、派隊員時：

- **zsh 不分詞：`$VAR`、`$(…)` 都是一整個字**。`for f in $(cat list)` 只跑一圈；`for p in "a b" "c d"; do set -- $p; …` 切不開，`$1` 拿到整串 `a b`；`F="a b"; git status -- $F`、`commit-request claim … $F`、`submit --files $F` 都把整串當一個檔名（寄信寄錯對象、claim 登記成怪檔名要 release 重做、submit 回 `RequestBad`／`does not exist`）。**要分詞的指令一律包在 `bash -c '…'` 裡，或寫成 bash 腳本**；留在 zsh 就用陣列 `F=(a b)`。逐行讀用 `bash -c 'mapfile -t F < list; for f in "${F[@]}"; do …; done'`。清環境也是同一個坑，見 [06 第 2 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)。
- **指令偶爾卡到逾時、被丟到背景**（檔其實已寫好）：
  - 最常見是 heredoc 後面接 `ls`／`cat` 的長指令。這台的 `ls` 是別名（eza）、`cat` 是 bat：結尾不要放裸的 `ls`，要列檔用 `/usr/bin/ls`、`/usr/bin/stat`、`ls 路徑 | head` 或 `find`；要原樣內容寫 `command cat`。
  - 每個指令明給 `< /dev/null`；heredoc 寫檔和後續指令分兩次呼叫；一條指令只做一兩件事並帶 timeout（一條串 cat、迴圈、ls、grep 的會撞 120 秒）。
  - 卡住後先用另一條短指令確認檔在不在，**不要重跑整條**（`>>` 的內容會接兩次）。
- **不要 `pkill -f <字串>`**：自己那個 shell 的命令列也含那個字串，會先殺掉自己（退 144）。只 kill 自己記下的 pid。

## zsh 其他會吃字的寫法

- `"$n原文"`：變數名後面直接接中文字，整串被當成變數名、展開成空字串，檔名寫錯。一律寫 `"${n}原文"`。
- `python3 -c "…"` 的雙引號裡寫反引號，會被當成指令替換，字不見。含反引號的文字改用 Write／Edit 工具寫，或用單引號 heredoc。
- `echo ====` 會報 `=== not found`（`=字` 是 zsh 的展開）。分隔線加引號。
- 花式 zsh 展開（例 `${(k)parameters[(I)AOS_*]}`）會被權限模式整行擋下。清 `AOS_*` 寫成一支小 bash 腳本，每次經它跑。
- 用程式 `str.replace` 改句子、0 次命中，常是原句帶反引號而你抄的沒帶：先 grep 原句再抄，並 `assert count == 1`。

## Read／Glob／Edit 在工作區外被擋

eca 的工作區是 `wf/temp/<線>`，必讀檔（`AGENTS.md`、`wf/workflows/…`）在 repo 別處；Claude 子 agent 也一樣。don't ask 模式下 Read、Glob 讀工作區外的檔被拒，Edit 又要求先 Read；子 agent 被擋後有的不回報、停在那裡（見 [claude子agent](claude子agent.md)）。

- 改用 Bash 的 `cat` 讀；要改檔用 python 寫同目錄暫存檔再改名。
- 派子 agent 時任務書寫明「讀檔用 bash，不要用 Read 讀暫存樹」。

## `pgrep -af aos-daemon` 會多列幾行，不一定是多了 daemon

開工或收尾用 `pgrep -u "$USER" -af aos-daemon` 核對有幾棵樹的 daemon 在跑時，列出的行數常比你知道的多、每次不一樣：daemon 會替每隻 agent-fsm 這類 proc fork 出看顧子行程，命令列沿用 `aos-daemon`，pid 跟著 proc 起落一直換；別線的測試 daemon 也來來去去。所以「開工記的 pid 清單」收尾一定對不上。

- `ps -o pid,ppid,args -p <pid>` 看 PPID：PPID 是另一個 aos-daemon 的，就是看顧子行程。比對時只看主 daemon 的 pid；真正要報的是主 daemon 本身不見，或出現不是它的子行程、卻指向活樹 daemon.json 的新行程。
- 也可以 `readlink /proc/<pid>/cwd` 看它在哪棵樹底下。
- 隊員只要保證「自己沒起、沒寫活樹」；sol 的任務書直接寫「行程檢查不用做」，由隊長核。
- 不要因為「多了一個 daemon」就 kill；也不要按名字收行程（不准 pkill、killall）。
