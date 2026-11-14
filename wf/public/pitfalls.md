# wf/public/pitfalls — 踩坑與解法（建置、測試複本、shell、試真東西、認 daemon 行程、封存搬檔）

← [wf/public](README.md)｜交 commit 與搬補丁的坑另見 [patch-and-commit](patch-and-commit.md)；帶 sol 的坑見 [sol-crew](sol-crew.md)

每條：適用、做法、驗過、出處、投稿。**驗過**＝投稿隊實際照做成功；**聽說**＝還沒人照做過。

## 暫存樹編 impls 的 C++：make 目標要用 `<名字>_main`

- **適用**：在暫存樹（`~/code/<線>-1114/build`，CMake 指向暫存的 `src/proto8/impls`）改了 aos-exec、aos-loop、aos-llm-kernel 這類 C++，要編好再跑 `impls/*/tests`。
- **坑**：`make aos-exec` 只編出靜態庫 `lib/lib<名字>.a`，`impls/<名字>/bin/<名字>` 不會重編。測試把 `impls/<名字>/bin` 放在 PATH 最前面，跑到的是舊 bin，看起來像改壞了。
- **做法**：
  ```
  cd ~/code/<線>-1114/build
  make help | grep <名字>      # 會看到 <名字> 和 <名字>_main 兩個目標
  make -j8 aos-exec_main aos-loop_main aos-llm-kernel_main
  ls -la ../src/proto8/impls/<名字>/bin   # 時間要是剛剛
  ```
- **快速判斷**：測試紅了、錯誤訊息卻還是改之前的字，先看 bin 的修改時間。
- **驗過**：ok-misc 11-14，T17。只編 `aos-exec` 時 6 紅，改編 `aos-exec_main` 後全綠。
- **出處**：`proto8/thinking/2026-11/14/misc-1114.md`
- **投稿**：ok-misc（`wf/temp/ok-misc/public-submit/暫存樹編C++要編_main目標.md`）

## 乾淨複本跑 wf/tools 測試，要連 proto8 一起抄

- **適用**：改了 wf/tools（例 index_gen、commit_queue）之後，在 repo 外的乾淨複本跑 `wf/tools/tests`。
- **坑**：只抄 `git archive HEAD wf/tools | tar -x -C <複本>`，`python3 -m unittest discover -s tests` 會有一支 error：`test_a_held_kernel_request_stays_at_the_gate`，`ModuleNotFoundError: No module named 'test_kernel_gate'`。test_quiet 從 repo 根的 `proto8/lib/agent/kernel_gate/tests` 借 test_kernel_gate（test_quiet.py 的 `GATE_TESTS`），複本裡沒有 proto8 就找不到。不是程式壞了。
- **做法**：`git archive HEAD wf/tools proto8/lib proto8/py proto8/cmd | tar -x -C <複本>`，再照 [06 第 2 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md) 經清環境腳本跑。整套驗收的跑法見 [patch-and-commit「驗收跑全套」](patch-and-commit.md)。
- **快速判斷**：只紅這一支、又是 ModuleNotFoundError，先懷疑複本抄得不夠全。
- **驗過**：ok-pilot 11-14，驗 f446f3d86 時：只抄 wf/tools，test_quiet 1 支 error；連 proto8/lib、py、cmd 一起抄，test_quiet 7/7 綠。審稿時對過 `wf/tools/tests/test_quiet.py` 第 13 行（GATE_TESTS）、第 106 行（import test_kernel_gate）。
- **出處**：`wf/tools/tests/test_quiet.py`；commit f446f3d86 的驗收
- **投稿**：ok-pilot（`wf-tools測試要連proto8一起抄.md`）

## 隊長的 shell（Bash 工具）

- **適用**：eca 隊長用 Bash 工具驅動暫存樹、派隊員。
- **zsh 不分詞：`$VAR`、`$(…)` 都是一整個字**：`for f in $(cat list)` 只跑一圈；`for p in "a b" "c d"; do set -- $p; …` 切不開，`$1` 拿到整串 `a b`（寄信會寄錯對象、開線或 claim 時路徑會串錯）。**要分詞的指令一律包在 `bash -c '…'` 裡，或寫成 bash 腳本**：逐行讀用 `bash -c 'mapfile -t F < list; for f in "${F[@]}"; do …; done'`；一次對多隻下指令用 `bash -c 'for n in a b c; do …; done'`。清環境也是同一個坑，見 [06 第 2 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)。
- **指令偶爾卡到逾時、被丟到背景**（heredoc 後面接 ls／cat 的長指令最常見，檔其實已寫好）：疑似有指令在等 stdin。每個指令明給 `< /dev/null`；heredoc 寫檔和後續指令分兩次呼叫。
- **不要 `pkill -f <字串>`**：自己那個 shell 的命令列也含那個字串，會先殺掉自己（退 144）。只 kill 自己記下的 pid。
- **驗過**：ok-kf 11-14，三條都是當天踩到、照解法做過。不分詞那條另有頂層 repo-aos、ok-misc、ok-astra 11-14 各踩一次（寄錯對象、開線失敗、claim 路徑串錯）。heredoc 那條 ok-kb 11-14 開工時也踩到一次（heredoc 寫任務書後接 `ls -la`，檔已寫好、指令被丟到背景）。
- **出處**：`proto8/thinking/2026-11/14/kernel-framework-1114.md`；頂層 11-14 13:14 給 ok-kb 的信
- **投稿**：ok-kf（`wf/temp/ok-kf/public-submit/pitfalls-shell-and-reviewers.md`）；ok-kb（`wf/temp/ok-kb/to-top/02-pitfalls-zsh變數不分詞.md`，不分詞那條擴寫）

## 試真東西別碰原件

- **適用**：要在使用者的試驗場（或任何活的 stack）上驗某個改動，例如換身體。
- **做法**：`cp -a` 整份到暫存夾；把複本裡用不到的 stack 改名成 `.orig`，只起要驗的那隻；驗完 `aos-daemon-ctl -d <複本>/.stack shutdown`。原件一行不動。
- **驗過**：ok-kf 11-14，驗換身體時照做。
- **出處**：同上
- **投稿**：ok-kf（同上）

## `pgrep -af aos-daemon` 會多列幾行，不一定是多了 daemon

- **適用**：開工或收尾時用 `pgrep -u "$USER" -af aos-daemon` 核對有幾棵樹的 daemon 在跑。
- **坑**：列出來的行數比你知道的 daemon 多（11-14 一次列出三行）。daemon 會替 agent-fsm 這類 agent fork 出看顧子行程，命令列沿用 `aos-daemon`，pgrep 照名字比對就一起列出來。
- **做法**：
  - `ps -o pid,ppid,args -p <pid>` 看 PPID。PPID 是另一個 aos-daemon 的，就是看顧子行程，不是另一棵樹的 daemon。
  - 也可以 `readlink /proc/<pid>/cwd` 看它在哪棵樹底下。
  - 不要因為「多了一個 daemon」就 kill；也不要按名字收行程（不准 pkill、killall，見上面「隊長的 shell」）。
- **驗過**：ok-wake 11-14 收尾核對時遇到，head-front 查明原因。審稿時 `ps -u "$USER" -o pid,ppid,args` 看到一行 aos-daemon 的 PPID 正是另一行 aos-daemon。
- **出處**：ok-wake 收尾核對（11-14）
- **投稿**：ok-wake（`wf/temp/ok-wake/public-submit/pgrep-aos-daemon多一行.md`）

## 封存或搬檔：預設留指標頁，不帶 `--rm`

- **適用**：要把一批現役檔封存進 `archive/`（或任何搬檔），再用 commit-request 交。
- **坑**：真的 `mv` 走之後，交件要把舊路徑列進 `commit-request submit --rm`。帶 `--rm` 的指令，agent 的權限模式會整條擋下（Claude Code 的 don't ask 模式；11-14 線庫 ok-kb 和頂層 repo-aos 都被擋），只能請使用者親手跑。檔已經搬了、還交不進去的這段時間，工作樹是半套狀態，別線也動不了那些檔。
- **做法**（頂層 11-14 定，寫在 [STRUCTURE「archive 規則」](../STRUCTURE.md#archive-規則)）：
  1. **預設：留指標頁，不帶 `--rm`**。全文抄成 `archive/` 底下的新檔（第一行加封存檔頭），原路徑改成幾行的指標頁：為什麼停用、現在怎麼做、全文在哪。別處連進來的錨點在指標頁補 `<a id="…">`。交件只有 `--files`，自己就交得進去，也合使用者「不刪」的偏好。代價是夾裡多一份短檔。
  2. **只有使用者明說要移除舊路徑**，才照 97cda3435、10a75ac53 真的搬走：`mv` 之後 `--files` 列新路徑、`--rm` 列舊路徑，git 會認成改名。這種交件 agent 跑不了，動手前先跟部長講，預先排好請使用者親手跑；交之前逐一確認每個舊路徑在 `archive/` 都有對應的檔。
- **驗過**：ok-kb 11-14。做法 1：c913897a6 把 `dispatch/aos-teams/04-進度回報.md` 改成指標頁、改寫前全文抄進 `dispatch/archive/`，只帶 `--files` 交成。做法 2：10a75ac53（封存 hackathon、workshop）卡在 `--rm`，最後由使用者親跑交成。
- **出處**：`proto8/thinking/2026-11/14/kb-1114.md`；698fa6d94（STRUCTURE 的 archive 規則）
- **投稿**：ok-kb（`wf/temp/ok-kb/to-top/05-封存搬檔的兩種做法與public-README的返回連結.md` 第一節）
