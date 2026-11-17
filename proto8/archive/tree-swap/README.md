# tree-swap：停樹後把一棵樹的程式複本換成某個 commit 的版本；C++ 平常樹在跑時就換

← [archive](../README.md)｜規格：[aos-teams/06「停樹換檔的做法」](../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)｜11-13 晚預演與給使用者的單子：[tree-swap-1113](../../thinking/2026-11/13/tree-swap-1113.md)

11-17 封存（路徑-6 A）：樹裡的程式直接指 repo，不再抄樹；這裡不測、不維護。

四支 bash，**都不含 kill／shutdown**；停樹、起樹由使用者自己下。swap／rollback 每段動手前看這棵樹的 aos daemon／loop 停了沒，沒停就印出來、`RED:` 退 3、什麼都不改。

**換樹步驟**（使用者 11-15 換樹兩次被擋（編譯中開了畫面、剩兩個 wl-copy）：「乾，好煩喔，到底爲啥要檢查這麼多啊」，同意「好，就這樣改。」）：

1. 平常（樹在跑也行）：`build.sh --ref <commit> --install` 把 C++ 換好，約 1 分半，每支印開始／結束與秒數。
2. 停 daemon：`aos-daemon-ctl -d ~/aos-home/.stack shutdown`。畫面（tmux、claude）、wl-copy、全景頁都不用關；開著的 claude 畫面還是舊的那份程式和設定，要新的就重開那個畫面。
3. `swap.sh --ref <commit> all`，約 1 秒。
4. 起樹。退回：停 daemon → `rollback.sh` → 起樹。

| 檔 | 做什麼 |
|---|---|
| [build.sh](build.sh) | `--ref <commit>`：`git archive` 該 commit 到 repo 外（預設 `~/.aos/scratch/tree-swap/build-<時間>-<pid>`），編九支 C++，寫 `BUILD_REF`，編譯輸出在該夾 `log/<p>.log`。加 `--install`＝九支都編成功才把每支用 rename 換進 `$TS_BIN_ROOT/<p>/bin/<p>`，樹在跑也行：換之前看 `/proc/*/exe`，有行程正在用的印 `warning:`（只警告、不擋、不殺），跑著的行程留在舊檔上照跑、下次起來才用新版；編失敗什麼都不換（使用者 11-15「樹還在跑的時候不能在repo裏面編，我希望可以，這就是使用者自己承擔風險。或是編譯的時候走腳本，腳本會稍微檢查一下」） |
| [swap.sh](swap.sh) | `--ref <commit> all`＝五段：`check`（daemon 停了？樹裡有沒有「只在樹裡有」的檔會被丟掉？）→`backup`→`copy`（解到旁邊、兩次改名換上）→`stamp`（用該 commit 的 [copy_tree.py](../aos-home/copy_tree.py) `--stamp-only` 寫每夾的 `.aos-source.json`）→`verify`。不換 C++ |
| [rollback.sh](rollback.sh) | 還原最近一次（或 `--backup <夾>`）的備份；還原後逐檔比對。11-15 以前的備份裡有 `bin/`（那時 swap 也換 C++），遇到就連 C++ 一起還原；新備份只有四夾，C++ 要退就 `build.sh --ref <舊 commit> --install` |
| [common.sh](common.sh) | 預設路徑、「樹在跑」偵測（只看 daemon／loop）、計時 |

- **換什麼**：`swap.sh` 換樹裡已經有的 `lib templates knowledge py kernel`（沒有的夾不建）。C++ 九支（`aos-daemon directive exec fsm json llm lock loop post`）由 `build.sh --install` 換進 `$TS_BIN_ROOT/<p>/bin/<p>`：`~/.local/bin/aos-*` 指的就是 repo 的 `proto8/impls/<p>/bin/<p>`（gitignore 著），也就是活樹用的那份，所以換樹時不用再碰。
- **不碰**：`agents defs teams kernels ws root daemon .stack env.sh`、`~/.aos` 裡除了備份夾 `saves/tree-swap` 以外的東西（專區 `~/.aos/user` 等）。
- **「樹在跑」怎麼算**：樹裡每個 `.stack` 底下的 `state.json`（root、ws 的 daemon 和每隻 agent 的 loop 都有）記著 `pid`＋`started_at_ticks`＋`boot_id`，三樣對得上 `/proc` 且不是殭屍＝還活著；判法跟 `aos-daemon-ctl` 的 `check_alive`（[poke.py](../../py/daemon_ctl/poke.py)）一樣。tmux、claude、wl-copy、全景頁、殼的環境變數和 cwd 都不看（原話見上方換樹步驟）。
- **路徑**用環境變數改：`TS_TREE`（預設 `~/aos-home`）、`TS_REPO`、`TS_BACKUP_ROOT`（預設 `~/.aos/saves/tree-swap`，`LAST` 記最近一份）；`build.sh` 另吃 `TS_BUILD`、`TS_BIN_ROOT`。
- **不刪任何東西**（使用者 11-14「不刪，連自己剛建的暫存也不刪」）：四支裡沒有 `rm`。`check`／`stamp`／`verify` 解出來的暫存夾、`copy` 換下來的舊夾（`old/`）、`rollback` 換下來的那份（`rb-old/`）都留在 `$TS_BACKUP_ROOT/run-<時間>-<pid>-<swap|rollback>/`；每次結束（含 RED）印 `kept ...` 列出留下哪些夾、各多大。一次 `swap.sh all` 約多留四份程式夾（活樹約 6 MB 一份）加 `backup` 那份；`build.sh` 每次的編譯夾也留著；刪不刪由使用者收工時決定。
- **釘 pin 時查帳的格式**：查這次要換的 commit 有沒有改到存在 stack 裡的帳或名冊的格式（例：`subagents.json`）。有的話，換樹前先收子或重建帳，並列成步驟表的一步。腳本不換 stack，所以不會替你做這件，也擋不下來。例：c3c1877ea（線框批 6）把 subagents.json 的 stack 從相對路徑改成絕對路徑，明寫「舊帳不認、不遷移，升級前先收子或重建帳」。11-14 換樹的步驟表漏了這一步，換完 ok-release 第一次呼叫 subagent，4 隻子的名冊就被清掉。子還在表上照跑，父卻管不到它們（11-14 的步驟表：[tree-swap-1114](../../thinking/2026-11/14/tree-swap-1114.md)）。
- **在 repo 裡直接 build**：樹在跑時也可以，風險使用者自己承擔；建議走 `build.sh --install`，它編在 repo 外、九支都成功才用 rename 換、會列出哪些正在跑。
