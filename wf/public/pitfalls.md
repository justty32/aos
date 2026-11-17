# wf/public/pitfalls — 踩坑與解法：隊長的 shell、建置與乾淨複本

← [wf/public](README.md)｜交 commit 與搬補丁的坑見 [patch-and-commit](patch-and-commit.md)；帶 sol 的坑見 [sol-crew](sol-crew.md)；其他主題看 [README 的主題表](README.md#主題)

## 隊長的 shell（Bash 工具）

eca 隊長用 Bash 工具（實際是 zsh）驅動暫存樹、派隊員時：

- **zsh 不分詞：`$VAR`、`$(…)` 都是一整個字**。`for f in $(cat list)` 只跑一圈；`for p in "a b" "c d"; do set -- $p; …` 切不開，`$1` 拿到整串 `a b`；`F="a b"; git status -- $F`、`commit-request claim … $F`、`submit --files $F` 都把整串當一個檔名（寄錯對象、claim 成怪檔名要 release 重做、submit 回 `RequestBad`／`does not exist`）。**要分詞的一律包在 `bash -c '…'` 裡，或寫成 bash 腳本**；留在 zsh 就用陣列 `F=(a b)`。逐行讀用 `bash -c 'mapfile -t F < list; for f in "${F[@]}"; do …; done'`。清環境也是同一個坑（[06 第 2 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)）。
- **指令偶爾卡到逾時、被丟到背景**（檔其實已寫好）：
  - 最常見是 heredoc 後面接 `ls`／`cat` 的長指令。這台的 `ls` 是別名（eza）、`cat` 是 bat：結尾不放裸的 `ls`，列檔用 `/usr/bin/ls`、`/usr/bin/stat`、`ls 路徑 | head` 或 `find`；要原樣內容寫 `command cat`。
  - 每個指令明給 `< /dev/null`；heredoc 寫檔和後續指令分兩次呼叫；一條指令只做一兩件事並帶 timeout（一條串 cat、迴圈、ls、grep 的會撞 120 秒）。
  - 卡住後先用另一條短指令確認檔在不在，**不要重跑整條**（`>>` 的內容會接兩次）。
- **不要 `pkill -f <字串>`**：自己那個 shell 的命令列也含那個字串，會先殺掉自己（退 144）。只 kill 自己記下的 pid。

## zsh 其他會吃字的寫法

- `"$n原文"`：變數名後直接接中文字，整串被當成變數名、展開成空字串。寫 `"${n}原文"`。
- `python3 -c "…"` 的雙引號裡寫反引號，會被當成指令替換、字不見。含反引號的文字用 Write／Edit 工具寫，或用單引號 heredoc。
- `echo ====` 會報 `=== not found`（`=字` 是 zsh 的展開）。分隔線加引號。
- 花式展開（例 `${(k)parameters[(I)AOS_*]}`）會被權限模式整行擋下。清 `AOS_*` 寫成一支小 bash 腳本，每次經它跑。
- 用程式 `str.replace` 改句子 0 次命中，常是原句帶反引號而你抄的沒帶：先 grep 原句再抄，並 `assert count == 1`。

## Read／Glob／Edit 在工作區外被擋

eca 的工作區是 `wf/temp/<線>`，必讀檔在 repo 別處；Claude 子 agent 也一樣。don't ask 模式下 Read、Glob 讀工作區外的檔被拒，Edit 又要求先 Read；子 agent 被擋後有的不回報、停在那裡（[claude子agent](claude子agent.md)）。改用 Bash 的 `cat` 讀；要改檔用 python 寫同目錄暫存檔再改名；派子 agent 時任務書寫明「讀檔用 bash，不要用 Read 讀暫存樹」。

## `pgrep -af aos-daemon` 會多列幾行，不一定是多了 daemon

開工或收尾用 `pgrep -u "$USER" -af aos-daemon` 核對時，行數常比你知道的多、每次不一樣：daemon 替每隻 agent-fsm 這類 proc fork 出看顧子行程，命令列沿用 `aos-daemon`，pid 跟著 proc 起落；別線的測試 daemon 也來來去去。所以開工記的 pid 清單收尾一定對不上。

- `ps -o pid,ppid,args -p <pid>` 看 PPID：PPID 是另一個 aos-daemon 的就是看顧子行程。只比主 daemon 的 pid；要報的是主 daemon 不見，或出現不是它的子行程、卻指向活樹 daemon.json 的新行程。也可以 `readlink /proc/<pid>/cwd` 看它在哪棵樹。
- 隊員只要保證「自己沒起、沒寫活樹」；sol 的任務書直接寫「行程檢查不用做」，由隊長核。
- 不因為「多了一個 daemon」就 kill；不按名字收行程（不准 pkill、killall）。

## 暫存樹編 impls 的 C++：make 目標要用 `<名字>_main`

在暫存樹的 build 夾（`~/.aos/scratch/<線名-日期>/build`，使用者 11-15 裁「4.a」起不放 `~/code`；CMake 指向暫存的 `src/proto8/impls`）改了 aos-exec、aos-loop、aos-llm 這類 C++、要編好再跑 `impls/*/tests` 時：`make aos-exec` 只編出靜態庫 `lib/lib<名字>.a`，`impls/<名字>/bin/<名字>` 不會重編；測試把那個 bin 放在 PATH 最前面，跑到舊的，看起來像改壞了。

```
cd ~/.aos/scratch/<線名-日期>/build
make help | grep <名字>      # 會看到 <名字> 和 <名字>_main 兩個目標
make -j8 aos-exec_main aos-loop_main aos-llm_main
ls -la ../src/proto8/impls/<名字>/bin   # 時間要是剛剛
```

測試紅了、錯誤訊息卻還是改之前的字，先看 bin 的修改時間。這是試編；要換進活樹的 C++ 照 [06 第 5 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md) 走 `build.sh`。

## 乾淨複本要帶齊依賴：wf/tools 測試連 proto8 一起抄，impls 測試連 lib 一起抄

在 repo 外的乾淨複本跑測試，只紅一兩支、又是 ModuleNotFoundError 或找不到檔，先懷疑複本抄得不夠全：只抄 `wf/tools` 時 test_quiet 借不到 `proto8/lib/agent/kernel_gate/tests` 的 test_kernel_gate；只抄 `impls` 和 `knowledge` 時 aos-llm 的 test_full 找不到 `proto8/lib/base/llm_fake`。wf/tools 的測試用 `git archive HEAD wf/tools proto8/lib proto8/py proto8/cmd | tar -x -C <複本>`；impls 的測試整個 `proto8` 一起抄；再經清環境腳本跑（06 第 2 條）。

## 乾淨複本的標準跑法：git archive＋疊檔、執行檔自己編、PATH 不撿到活樹的

交 commit 前驗自己的改動（main 已往前走、暫存樹落後時尤其要）：

1. `git archive HEAD proto8 | tar -x -C <新夾>`，再只把要交的檔 cp 上去；別人沒交的改動不會混進來。
2. `env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONDONTWRITEBYTECODE=1 TMPDIR=<新夾>/tmp python3 -m unittest discover -s <tests>`，或經自己的 clean.sh（它會換 cwd，`-s`、`-t` 一律給絕對路徑）。
3. 乾淨複本不帶 `impls/*/bin`（06 第 6 條）。要 bin 就用複本自己的原始碼編：`cmake -S <複本>/proto8/impls -B <新夾>`，再 `make <名字>_main`；**不從別處抄 bin 進去**，交件信寫明 bin 從哪來。沒編的話改前改後都紅同一批，只看差異。
4. PATH 不撿到 `~/.local/bin` 的舊執行檔：run.sh 把 PATH 換成「暫存樹各 `impls/*/bin`、`cmd/*/bin`＋`/usr/bin:/bin`」；會把 `~/.local/bin` 排最前的測試（wf 測試、test_daily）再給一個假 HOME，它的 `.local/bin` 連到暫存樹的 bin。
5. `templates/tests` 從上層 discover 不會進 `agent-fsm` 子夾，要另外跑。
6. 改前、改後各一份複本，用同一支腳本逐夾跑、各出一份 SUMMARY，`diff` 兩份看多紅哪幾支；一個 commit 動幾十個檔時只接受「測試數變多且 OK」這種差異。
7. commit 訊息裡的測試數字，在「真的要交的那個 commit」的 archive 上再跑一次才寫。

## 資料列多了新鍵：既有斷言連新鍵的值一起比，不要剝掉再比

資料列多了一個鍵（例：history 列的 `aos`）、既有測試斷言整列相等時：斷言改成連新鍵的正確值一起比，不寫「先 pop 掉再比」，既有測試順便鎖住新行為。

## 暫存 git 的 commit 會吃進 `.orig`、`__pycache__`

在暫存樹用 `git add -A` 留存檔點、之後從那裡匯出補丁或點名檔案交件時，`patch` 留下的 `.orig`、測試產生的 `.pyc` 會被夾帶：跑測試帶 `PYTHONDONTWRITEBYTECODE=1`；交件只點名真正的檔；匯出補丁照 [patch-and-commit「匯出補丁」](patch-and-commit.md) 排除 `__pycache__`。

## 試真東西別碰原件

要在使用者的試驗場（或任何活的 stack）上驗某個改動（例如換身體）：`cp -a` 整份到暫存夾；把複本裡用不到的 stack 改名成 `.orig`，只起要驗的那隻；驗完 `aos-daemon-ctl -d <複本>/.stack shutdown`。原件一行不動。
