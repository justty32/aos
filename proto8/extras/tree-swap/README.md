# tree-swap：停樹後把一棵樹的程式複本與 C++ 執行檔換成某個 commit 的版本

← [extras](../README.md)｜規格：[aos-teams/06「停樹換檔的做法」](../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)｜11-13 晚預演與給使用者的單子：[tree-swap-1113](../../thinking/2026-11/13/tree-swap-1113.md)

三支 bash，**都不含 kill／shutdown**；停樹、起樹由使用者自己下。每段動手前先確認這棵樹沒有任何行程活著，有就印出那些行程、`RED:` 退 3、什麼都不改。

| 檔 | 做什麼 |
|---|---|
| [build.sh](build.sh) | `--ref <commit>`：`git archive` 該 commit 到 repo 外（預設 `~/.aos/scratch/tree-swap/src`；使用者 11-15 裁「4.a」以前是 `~/code/swap-1113/src`），編九支 C++，寫 `BUILD_REF`。加 `--install`＝九支都編成功才把每支用 rename 換進 `$TS_BIN_ROOT/<p>/bin/<p>`，樹在跑也行：換之前看 `/proc/*/exe`，有行程正在用的印 `warning:`（只警告、不擋、不殺），跑著的行程留在舊檔上照跑、下次起來才用新版；編失敗什麼都不換（使用者 11-15「樹還在跑的時候不能在repo裏面編，我希望可以，這就是使用者自己承擔風險。或是編譯的時候走腳本，腳本會稍微檢查一下」） |
| [swap.sh](swap.sh) | `--ref <commit> all`＝六段：`check`（樹停了？build 的 impls 跟 ref 同？樹裡有沒有「只在樹裡有」的檔會被丟掉？）→`backup`→`copy`（解到旁邊、兩次改名換上）→`stamp`（用該 commit 的 [copy_tree.py](../aos-home/copy_tree.py) `--stamp-only` 寫每夾的 `.aos-source.json`）→`bin`（九支各自 `cp` 到旁邊再 `mv`）→`verify` |
| [rollback.sh](rollback.sh) | 還原最近一次（或 `--backup <夾>`）的備份，`all`／`tree`／`bin`；還原後逐檔比對 |
| [common.sh](common.sh) | 預設路徑、「樹在跑」偵測、計時 |

- **換什麼**：樹裡已經有的 `lib templates knowledge py kernel`（沒有的夾不建），與 `$TS_BIN_ROOT/<p>/bin/<p>` 九支（`aos-daemon directive exec fsm json llm lock loop post`；`~/.local/bin/aos-*` 指的就是 repo 的 `proto8/impls/<p>/bin/<p>`，gitignore 著）。
- **不碰**：`agents defs teams kernels ws root daemon .stack env.sh`、`~/.aos` 裡除了備份夾 `saves/tree-swap` 以外的東西（專區 `~/.aos/user` 等）。
- **「樹在跑」怎麼算**：自己的行程裡，環境的 `AOS_STACK`／`AOS_DAEMON` 落在樹底下，或 cwd 在樹底下且是 aos／claude／python／node。不看 `AOS_HOME`（`.zshrc` 每個殼都設）。從某隻 agent 的殼裡下（殼裡有 `AOS_STACK` 等）直接拒絕。
- **停 daemon 不會關 agent 畫面**：`aos-agent open -t <名>` 開的 tmux（含裡面的 claude、aos-mcp）是獨立行程，停樹後還活著，`check` 會 RED。換前要另外 `tmux -S /run/user/<uid>/aos-tty-<uid>/<sock> kill-server`（sock 名看 RED 列出的行程，或 `ls` 該夾）。建議順序：停樹 → 關畫面 → 先單跑 `swap.sh --ref <hash> check` 到沒 RED → `all` → 起樹 → `aos-agent open -t <名>` 重開畫面。
- **路徑**用環境變數改：`TS_TREE`（預設 `~/aos-home`）、`TS_REPO`、`TS_BUILD`、`TS_BIN_ROOT`、`TS_BACKUP_ROOT`（預設 `~/.aos/saves/tree-swap`，`LAST` 記最近一份）。
- **不刪任何東西**（使用者 11-14「不刪，連自己剛建的暫存也不刪」）：三支裡沒有 `rm`。`check`／`stamp`／`verify` 解出來的暫存夾、`copy` 換下來的舊夾（`old/`）、`rollback` 換下來的那份（`rb-old/`）都留在 `$TS_BACKUP_ROOT/run-<時間>-<pid>-<swap|rollback>/`；每次結束（含 RED）印 `kept ...` 列出留下哪些夾、各多大。一次 `swap.sh all` 約多留四份程式夾（活樹約 5 MB 一份）加 `backup` 那份；刪不刪由使用者收工時決定。
- **釘 pin 時查帳的格式**：查這次要換的 commit 有沒有改到存在 stack 裡的帳或名冊的格式（例：`subagents.json`）。有的話，換樹前先收子或重建帳，並列成步驟表的一步。腳本不換 stack，所以不會替你做這件，也擋不下來。例：c3c1877ea（線框批 6）把 subagents.json 的 stack 從相對路徑改成絕對路徑，明寫「舊帳不認、不遷移，升級前先收子或重建帳」。11-14 換樹的步驟表漏了這一步，換完 ok-release 第一次呼叫 subagent，4 隻子的名冊就被清掉。子還在表上照跑，父卻管不到它們（11-14 的步驟表：[tree-swap-1114](../../thinking/2026-11/14/tree-swap-1114.md)）。
- 換完之後 repo 的 `impls/*/build` 比執行檔舊；之後在 repo 重 build 會從已 commit 的原始碼編出等價的檔。
- **樹在跑時也可以換 C++**：`build.sh --ref <commit> --install`（約 1 分半）。樹在跑時直接在 repo 裡 build 也可以，風險使用者自己承擔；建議走這支，它用 rename 換、會列出哪些正在跑。
