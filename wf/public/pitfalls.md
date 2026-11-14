# wf/public/pitfalls — 踩坑與解法（建置、shell、試真東西）

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

## 隊長的 shell（Bash 工具）

- **適用**：eca 隊長用 Bash 工具驅動暫存樹、派隊員。
- **zsh 的 for 不切字**：`for f in $(cat list)` 在 zsh 只跑一次。要逐行就用 `bash -c 'mapfile -t F < list; … "${F[@]}"'`。
- **指令偶爾卡到逾時、被丟到背景**（heredoc 後面接 ls／cat 的長指令最常見，檔其實已寫好）：疑似有指令在等 stdin。每個指令明給 `< /dev/null`；heredoc 寫檔和後續指令分兩次呼叫。
- **不要 `pkill -f <字串>`**：自己那個 shell 的命令列也含那個字串，會先殺掉自己（退 144）。只 kill 自己記下的 pid。
- **驗過**：ok-kf 11-14，三條都是當天踩到、照解法做過。
- **出處**：`proto8/thinking/2026-11/14/kernel-framework-1114.md`
- **投稿**：ok-kf（`wf/temp/ok-kf/public-submit/pitfalls-shell-and-reviewers.md`）

## 試真東西別碰原件

- **適用**：要在使用者的試驗場（或任何活的 stack）上驗某個改動，例如換身體。
- **做法**：`cp -a` 整份到暫存夾；把複本裡用不到的 stack 改名成 `.orig`，只起要驗的那隻；驗完 `aos-daemon-ctl -d <複本>/.stack shutdown`。原件一行不動。
- **驗過**：ok-kf 11-14，驗換身體時照做。
- **出處**：同上
- **投稿**：ok-kf（同上）
