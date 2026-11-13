# 公司 WSL：跑著的樹與任務書必貼的硬規則

← [入口](../aos-teams.md)｜涵蓋：現況、任務書必貼的硬規則、停樹換檔的做法｜上一份 [05-同機session與Argon](05-同機session與Argon.md)｜下一份 [07-預設流程與agent-fsm](07-預設流程與agent-fsm.md)

## 現況

- 使用者的樹住 `~/aos-home`，整天在用（下面叫「活樹」）；repo 是 `~/repo/aos`，只有 `main`。
- **頂層 session 是樹裡的一隻 agent**，名字 `repo-aos`（工作區 `~/repo/aos`、stack `~/aos-home/ws/.stack/procs/repo-aos`；[main-session-in-aos](../../../../proto8/thinking/2026-11/13/main-session-in-aos.md)）。它派出去的每個子 agent，Bash 都帶著活樹的 `AOS_*` 變數。
- `~/.local/bin` 的 `aos-*` 連到 repo：`proto8/cmd/`、`proto8/py/`、被指令直接 import 的 `proto8/lib/agent/*.py` 存檔即生效；活樹的 `lib`／`templates`／`knowledge`／`py` 是複本，重抄才生效；`proto8/impls/*/bin/` 的執行檔就是跑著的那幾支。
- 各條為什麼、踩過什麼 → [gotchas/05](../../common/gotchas/05-在跑著的樹旁邊做事.md)。

## 任務書必貼的硬規則

會跑程式、跑測試或改 `proto8/` 的線，任務書開頭整段照貼（`<…>` 由調度者填；隊長往下派時原樣帶進子任務書，codex 也一樣）。純改文件的線貼第 1、7 條。

```
## 硬規則（這台的 ~/aos-home 有一棵使用者正在用的樹；你的 shell 繼承了它的環境）
1. 活樹不碰：不寫 ~/aos-home 底下任何檔、不對它的 daemon 與 agent 下任何指令、不寄信進去。唯讀查看只限本任務書點名的，與第 9 條的核對。
2. 先清環境：你的 Bash 帶著活樹的 AOS_STACK、AOS_DAEMON、AOS_HOME、AOS_WS 等。起任何 aos 行程、跑任何測試或 aos 指令，一律經一支 bash 腳本：開頭「不是 bash 就拒絕」、逐一 unset 所有 AOS_*、「還有殘留就拒絕」，再 exec 你的指令。不在 zsh 裡 source 環境檔、不用 `env -u $VARS`（在 zsh 都等於沒清）。
3. 暫存樹：要起樹，起在 repo 外獨一無二的暫存夾 <~/code/線名-日期/>；tmux 只用 `tmux -S <暫存夾內的 socket>`。
4. 收行程只准兩種：(a) `aos-daemon-ctl -d <自己暫存樹 stack 的絕對路徑> shutdown`，下之前 echo 那個路徑、確認在自己的暫存夾下；(b) kill 起的時候自己記下的 pid，kill 前 `readlink /proc/<pid>/cwd` 確認在自己的暫存夾裡。禁止 pkill、killall、`kill $(pgrep …)` 與任何按名字或命令列字串收行程的寫法。
5. 改 repo＝改活樹：proto8/cmd、proto8/py、被指令直接 import 的 proto8/lib/agent/*.py，存檔當下活樹就在用。新碼先放新檔／新函式、測到綠；接到既有路徑的那一步放在最後一個 commit，動手前先回報調度者、等放行。改既有檔：先寫暫存檔再改名，存完立刻 import 驗一次。不在 repo 裡 build C++（執行檔寫回 impls/*/bin＝換掉活樹的 daemon）；要編就把原始碼抄到 repo 外的 build 夾。
6. 測試：全套測試在 `git archive <commit>` 抄到 repo 外的乾淨複本上跑；定向測試也先照第 2 條清環境。
7. git：只 `git commit -F <訊息檔> -- <逐一點名的檔>`，不 `git add -A`、不 `git add .`；commit 前 `git diff -- <那些檔>` 確認裡面只有自己寫的字。只動領地清單上的檔：<領地>。
8. 叫真模型測試時只給它真的小工作；不編理由、不繞它講明的限制。
9. 開工前與收尾各跑一次、把指令與輸出貼進回報：`pgrep -u "$USER" -af aos-daemon`（活樹的 daemon 一台不少、你起的一台不剩）、`ls -la <活樹裡頂層那一格 stack>`（跟開工前的清單一樣）。對不上立刻停手回報，不自己重起、不自己清。
```

## 停樹換檔的做法

要重抄複本、換 C++ 執行檔時，停樹與起樹由使用者下指令；要把停的時間壓短（步驟表：[kernel-framework 開工「停樹時照做」](../../../../proto8/thinking/2026-11/13/kernel-framework-開工.md#十二下午接手線己二使用者中午的裁定與停樹)）：

- 事先在暫存樹把整套腳本預演到過（含「樹還在跑時被擋下」的紅燈與退回），量好每段時間。
- 腳本自己不含任何 kill／shutdown；每段先確認「cwd 在 `~/aos-home` 底下的 aos 行程一個都不在」才動。
- 停 daemon 不會關 agent 畫面（`aos-agent open` 開的 tmux 與裡面的 claude、aos-mcp 是獨立行程，腳本會 RED）：換前要另外關（`tmux -S <sock> kill-server`），先單跑 `check` 到沒 RED 再 `all`，起樹後重開畫面（11-13 晚實戰栽過）。
- 先備份再換；換檔是「先抄到旁邊再改名」。附退回腳本。
- 抄的來源是一個釘住、且在乾淨複本上跑過全套的 commit，用 `git archive <hash>` 抄，不抄工作樹；C++ 事先在 repo 外編好，停樹時只換檔。
- 有停樹時刻的日子，每條線要有一個「趕不上就還原乾淨」的時刻（[lessons 17](../lessons/03-坑14-20.md#17-有截止點的日子每條線要有趕不上就還原乾淨的時刻)）。
