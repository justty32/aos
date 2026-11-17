# 公司 WSL：跑著的樹與任務書必貼的硬規則

← [入口](../aos-teams.md)｜涵蓋：現況、任務書必貼的硬規則、停樹換檔的做法｜上一份 [05-同機session與Argon](05-同機session與Argon.md)｜下一份 [07-預設流程與agent-fsm](07-預設流程與agent-fsm.md)

## 現況

- 使用者的樹住 `~/aos-home`，整天在用（下面叫「活樹」）；repo 是 `~/repo/aos`，只有 `main`。
- **頂層 session 是樹裡的一隻 agent**，名字 `repo-aos`（工作區 `~/repo/aos`、stack `~/aos-home/ws/.stack/procs/repo-aos`；[main-session-in-aos](../../../../proto8/thinking/2026-11/13/main-session-in-aos.md)）。它派出去的每個子 agent，Bash 都帶著活樹的 `AOS_*` 變數。
- `~/.local/bin` 的 `aos-*` 連到 repo：`proto8/cmd/`、被指令直接 import 的 `proto8/lib/agent/*.py` 存檔即生效；活樹的 `lib`／`templates`／`knowledge` 是複本，重抄才生效；`proto8/impls/*/bin/` 的執行檔就是跑著的那幾支。
- 各條為什麼、踩過什麼 → wf/public 的 [活樹旁邊](../../../public/活樹旁邊.md)、[行程與環境](../../../public/行程與環境.md)。

## 任務書必貼的硬規則

會跑程式、跑測試或改 `proto8/` 的線，任務書開頭整段照貼（`<…>` 由調度者填；隊長往下派時原樣帶進子任務書，codex 也一樣）。純改文件的線貼第 1、7 條。

```
## 硬規則（這台的 ~/aos-home 有一棵使用者正在用的樹；你的 shell 繼承了它的環境）
1. 活樹不碰：不寫 ~/aos-home 底下任何檔、不對它的 daemon 與 agent 下任何指令、不寄信進去（任務書點名的回報對象與使用者專區除外）。唯讀查看只限本任務書點名的，與第 9 條的核對。
2. 先清環境：你的 Bash 帶著活樹的 AOS_STACK、AOS_DAEMON、AOS_HOME、AOS_WS 等。起任何 aos 行程、跑任何測試或 aos 指令，一律經一支 bash 腳本：開頭「不是 bash 就拒絕」、逐一 unset 所有 AOS_*、「還有殘留就拒絕」，再 exec 你的指令。不在 zsh 裡 source 環境檔、不用 `env -u $VARS`（在 zsh 都等於沒清）。其他要靠分詞的寫法也一樣（隊長的 shell 是 zsh，`$VAR` 不分詞）：多字迴圈、`set -- $p`、`for f in $(cat list)` 一律包在 `bash -c '…'` 或寫成 bash 腳本。
3. 暫存樹：要起樹，起在 ~/.aos/scratch/<線名-日期>/ 這個獨一無二的暫存夾；不放 ~/code（那是使用者自己的空間）。tmux 只用 `tmux -S <暫存夾內的 socket>`。
4. 收行程只准兩種：(a) `aos-daemon-ctl -d <自己暫存樹 stack 的絕對路徑> shutdown`，下之前 echo 那個路徑、確認在自己的暫存夾下；(b) kill 起的時候自己記下的 pid，kill 前 `readlink /proc/<pid>/cwd` 確認在自己的暫存夾裡。禁止 pkill、killall、`kill $(pgrep …)` 與任何按名字或命令列字串收行程的寫法。
5. 改 repo＝改活樹：proto8/cmd、被指令直接 import 的 proto8/lib/agent/*.py，存檔當下活樹就在用。新碼先放新檔／新函式、測到綠；接到既有路徑的那一步放在最後一個 commit，動手前先回報調度者、等放行。改既有檔：先寫暫存檔再改名，存完立刻 import 驗一次。要編 C++ 先回報調度者：直接在 repo 裡 `cmake --build` 會把執行檔寫回 impls/*/bin＝換掉活樹的 daemon（舊的 `build.sh` 在 repo 外編、11-17 封存在 `proto8/archive/tree-swap/`）。只想試編不換，就把原始碼抄到自己暫存夾（第 3 條）裡的 build 夾（使用者 11-15 經全景頁答「可以」放寬本條）。
6. 測試：全套測試在 `git archive <commit>` 抄到自己暫存夾（第 3 條）裡的乾淨複本上跑（乾淨複本不帶 impls/*/bin）；定向測試也先照第 2 條清環境。
7. git：家機 11-14 起改用 `~/repo/aos/wf/tools/commit-request`（開工 `claim`，交件 `submit --line <線名> --files 檔… --msg-file 訊息檔`；共用索引檔走 `--op`，不手改、不自己跑 index_gen；用法見 [07](07-預設流程與agent-fsm.md)）；沒有 commit-request 的機器才用 `git commit -F <訊息檔> -- <逐一點名的檔>`。一律不 `git add -A`、不 `git add .`；commit 前 `git diff -- <那些檔>` 確認裡面只有自己寫的字。只動領地清單上的檔：<領地>。
8. 叫真模型測試時只給它真的小工作；不編理由、不繞它講明的限制。
9. 開工前與收尾各跑一次、把指令與輸出貼進回報：`pgrep -u "$USER" -af aos-daemon`（活樹的 daemon 一台不少、你起的一台不剩）、`ls -la <活樹裡頂層那一格 stack>`（跟開工前的清單一樣）。對不上立刻停手回報，不自己重起、不自己清。
```

暫存夾放哪（使用者 11-15 裁「4.a」）：以後的暫存樹、乾淨複本、C++ build 夾一律放 `~/.aos/scratch/<線名-日期>/`，不再放 `~/code/<線名-日期>/`。`~/code` 是使用者自己的空間；11-15 已清掉 53 個 aos 的舊暫存夾（留 `view-1114` 等）。舊文件裡寫的 `~/code/<x>-1114` 路徑多半已不存在。`~/.aos/scratch` 用完怎麼收，使用者之後自己定，目前沒有規則。

## 停樹換檔的做法

11-17 起不抄樹（路徑-6 A，使用者裁定）：樹裡的程式直接指 repo，`AOS_HOME` 就是 repo 的 `proto8`，不抄 lib／templates／knowledge 進樹、不用 git worktree。換版本的做法（停樹與起樹由使用者下指令；重建步驟單：[重建步驟單](../../../../proto8/thinking/2026-11/17/重建步驟單.md)）：

1. 停樹：`aos-daemon-ctl -d <樹的 stack> shutdown`。
2. 換 repo：`git -C ~/repo/aos pull`（或 checkout 要的 commit）；有改 C++ 就 `cmake --build`。
3. 重新起樹。

舊做法（抄樹、換樹、退回）的腳本封存在 `proto8/archive/tree-swap/`（[README](../../../../proto8/archive/tree-swap/README.md)），不再維護。

- 釘 pin 時查這次要換的 commit 有沒有改到存在 stack 裡的帳或名冊的格式（例：`subagents.json`）；有就在停樹前收子或重建，並列成步驟表的一步（例子：[舊 tree-swap README](../../../../proto8/archive/tree-swap/README.md)）。
- 有停樹時刻的日子，每條線要有一個「趕不上就還原乾淨」的時刻（[派線與任務書](../../../public/派線與任務書.md#有截止點的日子每條線要有趕不上就還原乾淨的時刻)）。
