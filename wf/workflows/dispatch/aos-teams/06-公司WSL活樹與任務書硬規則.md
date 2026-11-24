# 公司 WSL：跑著的樹與任務書必貼的硬規則

← [入口](../aos-teams.md)｜涵蓋：現況、任務書必貼的硬規則、停樹換檔的做法｜上一份 [05-同機session與Argon](05-同機session與Argon.md)｜下一份 [07-預設流程與agent-fsm](07-預設流程與agent-fsm.md)

## 現況

- 使用者正在用的樹下面叫「活樹」；兩台的 repo 都是 `~/repo/aos`，只有 `main`。
- **活樹（repo 那棵）的 stack：家機是 `~/repo/aos/.stack`，公司那台 11-24 起是 `~/aos-home/.stack/procs/repo-aos`**（公司那台 repo 裡已經沒有 `.stack`）：每台各有各的，不跟著 git 搬（使用者 11-23「直接變成.stack，然後把它git ignore，就這樣。換機那一套就不用了。」；11-22～11-23 叫 `_stack`）。它的定義 `wf/tree/root/` 進 git、兩台共用；資料夾名字還叫 `root`，但 11-23 起它不是根定義，是掛在 `~/aos-home` 根底下的子 daemon，拿掉了 `_clock` 列、不帶鐘（[wf/tree](../../../tree/README.md)）。
- **家機（11-22 14:12 搬好）**：eca-aos 與三個 subagent（eca-aos-templates、eca-aos-kb、aos-eca-frontend）住在這裡；工作區（cwd）照舊是 `~/repo/aos`，私有地盤在 `wf/ws/<上層>/<名>/`（[wf/ws](../../../ws/README.md)）。llm kernel 自己一台：定義 `~/aos-home/llm`、stack `~/aos-home/.llm-stack`，`~/aos-home` 只剩這兩樣（11-23 還是這樣；方向已定要改成跟公司那台同一套，步驟在說明書「家機照做」）；舊樹其他東西在 `~/aos-home.old-1122/`（退路，不刪、不在那裡起東西）。殼怎麼設、怎麼起樹見[每台設定說明書](../../dev-env/03-換機.md)；搬家經過見 [04-線6演練](../../../../proto8/thinking/2026-11/22/工作區與stack-1122/04-線6演練.md)。
- **公司 WSL（11-23 起樹）**：表上掛 eca-aos（範本 `eca-claude`，工作區 `~/repo/aos`），用另一個 Claude 帳號。11-23 起樹根在 `~/aos-home`（stack `~/aos-home/.stack`），鐘只在這個根；表上掛著 `llm`（llm kernel，stack `~/aos-home/.stack/procs/llm`）與 `repo-aos`（repo 那棵的子 daemon，stack 11-24 起是 `~/aos-home/.stack/procs/repo-aos`、公司那台 repo 裡已經沒有 `.stack`，這一列帶 `CLAUDE_CONFIG_DIR="$HOME/.claude-alt"` 與 `AOS_LLM_KERNEL`），另外還有使用者自己掛的別的專案的子 daemon（台數會變，不是我們的，不碰）；起停只對 `~/aos-home` 的根（[說明書](../../dev-env/03-換機.md#起樹停樹)）。那裡以前的舊樹已不在（以前頂層 session 是那棵樹裡的 `repo-aos`，[main-session-in-aos](../../../../proto8/thinking/2026-11/13/main-session-in-aos.md)）。樹裡的 agent 派出去的每個子 agent，Bash 都帶著活樹的 `AOS_*` 變數。
- 活樹的 `AOS_HOME` 是 `~/repo/aos/proto8`（照[重建步驟單](../../../../proto8/thinking/2026-11/17/重建步驟單.md)建）：跑的是那裡 `install.py` 產的 `bin/`（指令）、`lib/`（工具與共用套件），**改 `py/`、`cpp/` 存檔不會動到活樹，在那份 proto8 跑 `install.py` 才換**（11-18 S3 起；以前「存檔即生效」的說法作廢）。`knowledge/`、`frontend/` 不經 install.py、活樹直接讀，存檔即生效；`templates/` 要重抄進樹才生效。`~/.local/bin` 不再放 aos 的東西（舊 `cmd/install.sh` 11-18 S5 收掉）。
- 各條為什麼、踩過什麼 → wf/public 的 [活樹旁邊](../../../public/活樹旁邊.md)、[行程與環境](../../../public/行程與環境.md)。

## 任務書必貼的硬規則

會跑程式、跑測試或改 `proto8/` 的線，任務書開頭整段照貼（`<…>` 由調度者填；隊長往下派時原樣帶進子任務書，codex 也一樣）。純改文件的線貼第 1、7 條。

```
## 硬規則（這台有一棵使用者正在用的樹＝活樹：家機 ~/repo/aos/.stack、公司那台 ~/aos-home/.stack 底下全部；你的 shell 繼承了它的環境）
1. 活樹不碰：不寫活樹底下任何檔、不對它的 daemon 與 agent 下任何指令、不寄信進去（任務書點名的回報對象與使用者專區除外）。活樹是 repo 那棵的 stack（家機 ~/repo/aos/.stack，公司那台 ~/aos-home/.stack/procs/repo-aos）與它的定義 ~/repo/aos/wf/tree/，同樣不碰的還有 ~/aos-home（公司那台 11-23 起是整棵樹的根，底下除了 llm kernel 與 repo 這棵，還掛著使用者自己別的專案的子 daemon；家機還沒改成同一套之前放的是 llm kernel）與家機的 ~/aos-home.old-1122/（舊樹退路）。清掉 AOS_* 之後站在 ~/repo/aos 不帶 -d 下 aos-daemon-ctl、aos-mailbox 這類指令，會找到 ./.stack＝活樹。唯讀查看只限本任務書點名的，與第 9 條的核對。
2. 先清環境：你的 Bash 帶著活樹的 AOS_STACK、AOS_DAEMON、AOS_HOME、AOS_WS 等。起任何 aos 行程、跑任何測試或 aos 指令，一律經一支 bash 腳本：開頭「不是 bash 就拒絕」、逐一 unset 所有 AOS_*、「還有殘留就拒絕」，再 exec 你的指令。不在 zsh 裡 source 環境檔、不用 `env -u $VARS`（在 zsh 都等於沒清）。其他要靠分詞的寫法也一樣（隊長的 shell 是 zsh，`$VAR` 不分詞）：多字迴圈、`set -- $p`、`for f in $(cat list)` 一律包在 `bash -c '…'` 或寫成 bash 腳本。
3. 暫存樹：要起樹，起在 ~/.aos/scratch/<線名-日期>/ 這個獨一無二的暫存夾；不放 ~/code（那是使用者自己的空間）。tmux 只用 `tmux -S <暫存夾內的 socket>`。
4. 收行程只准兩種：(a) `aos-daemon-ctl -d <自己暫存樹 stack 的絕對路徑> shutdown`，下之前 echo 那個路徑、確認在自己的暫存夾下；(b) kill 起的時候自己記下的 pid，kill 前 `readlink /proc/<pid>/cwd` 確認在自己的暫存夾裡。禁止 pkill、killall、`kill $(pgrep …)` 與任何按名字或命令列字串收行程的寫法。
5. 改 py/、cpp/ 要 install.py 之後才生效：活樹只跑 proto8/bin、proto8/lib（install.py 從 py/、cpp/ 產的），在 repo 改程式存檔不會動到它。在 repo 裡跑 `python3 proto8/install.py` 會先清再重填 bin/ lib/ include/＝當場換掉活樹的 daemon、指令、工具與共用模組，要跑先回報調度者、等放行（舊的 `build.sh` 在 repo 外編、11-17 封存在 `proto8/archive/tree-swap/`）。只想試編、試裝，就把整份 repo 抄到自己暫存夾（第 3 條）、在那份裡跑 `install.py`（使用者 11-15 經全景頁答「可以」放寬本條）。proto8/knowledge、proto8/frontend 不經 install.py，存檔當下活樹就在用：改既有檔先寫暫存檔再改名；新東西先放新檔、測到綠，接到既有路徑的那一步放在最後一個 commit。
6. 測試：全套測試在 `git archive <commit>` 抄到自己暫存夾（第 3 條）裡的乾淨複本上跑（乾淨複本不帶 bin/ lib/ include/：先在複本的 proto8 跑一次 install.py，再 `export AOS_HOME=<複本的 proto8>` 後 source 它的 env.sh）；定向測試也先照第 2 條清環境。
7. git：家機 11-14 起改用 `~/repo/aos/wf/tools/commit-request`（開工 `claim`，交件 `submit --line <線名> --files 檔… --msg-file 訊息檔`；共用索引檔走 `--op`，不手改、不自己跑 index_gen；用法見 [07](07-預設流程與agent-fsm.md)）；沒有 commit-request 的機器才用 `git commit -F <訊息檔> -- <逐一點名的檔>`。一律不 `git add -A`、不 `git add .`；不在共用工作樹跑 `git stash`、`git reset --hard`、`git checkout -- .`、`git clean -fdx`（會蓋掉別線還沒交的字；.stack 被根 .gitignore 忽略，`git clean -fdx` 會連活樹一起刪）；commit 前 `git diff -- <那些檔>` 確認裡面只有自己寫的字。只動領地清單上的檔：<領地>。
8. 叫真模型測試時只給它真的小工作；不編理由、不繞它講明的限制。
9. 開工前與收尾各跑一次、把指令與輸出貼進回報：`pgrep -u "$USER" -af aos-daemon`（活樹的 daemon 一台不少、你起的一台不剩：開工前把當時的清單原樣記下，收尾拿同一份來對；台數不要用記的，使用者隨時會加掛或拿掉。公司那台的根在 ~/aos-home（cwd 在 ~/aos-home/root），底下有 llm kernel（cwd 在 ~/aos-home/llm）、repo 那棵（cwd 在 ~/repo/aos/wf/tree/root）、它表上的 agent（家機 cwd 在 ~/repo/aos/.stack/procs/ 底下，公司那台在 ~/aos-home/.stack/procs/repo-aos/procs/ 底下），還有使用者自己掛的別的專案的子 daemon；家機還沒改成同一套之前，repo 那棵與 llm kernel 各自單獨一台。不是你起的一律不要動）、`ls -la <活樹裡頂層那一格 stack>`（家機 ~/repo/aos/.stack/procs/eca-aos，公司那台 ~/aos-home/.stack/procs/repo-aos/procs/eca-aos；跟開工前的清單一樣）。對不上立刻停手回報，不自己重起、不自己清。
```

暫存夾放哪（使用者 11-15 裁「4.a」）：以後的暫存樹、乾淨複本、C++ build 夾一律放 `~/.aos/scratch/<線名-日期>/`，不再放 `~/code/<線名-日期>/`。`~/code` 是使用者自己的空間；11-15 已清掉 53 個 aos 的舊暫存夾（留 `view-1114` 等）。舊文件裡寫的 `~/code/<x>-1114` 路徑多半已不存在。`~/.aos/scratch` 用完怎麼收，使用者之後自己定，目前沒有規則。

## 停樹換檔的做法

11-17 起不抄樹（路徑-6 A，使用者裁定）：樹裡的程式直接指 repo，`AOS_HOME` 就是 repo 的 `proto8`，不抄 lib／templates／knowledge 進樹、不用 git worktree。換版本的做法＝[重建步驟單](../../../../proto8/thinking/2026-11/17/重建步驟單.md)的「更新五步」（停樹與起樹由使用者下指令）：

1. 停樹：`aos-daemon-ctl -d <樹的 stack> shutdown`（有 llm kernel 的再關那台）。公司那台 11-23 起只要 `aos-daemon-ctl -d ~/aos-home/.stack shutdown` 一行，llm kernel 與 repo 那棵跟著停。
2. 換 repo：`git -C ~/repo/aos pull`（或 checkout 要的 commit）。
3. 重裝：`python3 ~/repo/aos/proto8/install.py`（不管改的是 C++ 還是 Python 都要；先清再裝）。
4. 範本改了的，把樹裡過時的抄本重抄（`diff -r` 範本與樹自己比；commit 訊息會寫要重抄哪些）。
5. 重新起樹。

舊做法（抄樹、換樹、退回）的腳本封存在 `proto8/archive/tree-swap/`（[README](../../../../proto8/archive/tree-swap/README.md)），不再維護。

- 釘 pin 時查這次要換的 commit 有沒有改到存在 stack 裡的帳或名冊的格式（例：`subagents.json`）；有就在停樹前收子或重建，並列成步驟表的一步（例子：[舊 tree-swap README](../../../../proto8/archive/tree-swap/README.md)）。
- 有停樹時刻的日子，每條線要有一個「趕不上就還原乾淨」的時刻（[派線與任務書](../../../public/派線與任務書.md#有截止點的日子每條線要有趕不上就還原乾淨的時刻)）。
