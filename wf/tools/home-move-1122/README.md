家機搬家（線 6）的一次性工具：`home-move` 分段把 eca-aos 與三個 subagent 從舊樹 `~/aos-home/.stack` 搬到 `~/repo/aos/_stack`，出錯自動退回；`rehearse-prep` 替演練備一個假家目錄。

# home-move-1122

← [wf/tools](../)｜規劃：[02-規劃「線 6」](../../../proto8/thinking/2026-11/22/工作區與stack-1122/02-規劃.md#線-6家機搬家使用者在場)｜演練紀錄：[04-線6演練](../../../proto8/thinking/2026-11/22/工作區與stack-1122/04-線6演練.md)｜換機說明書：[03-換機](../../workflows/dev-env/03-換機.md)

## 先講結論

- **一行跑完**：`~/repo/aos/wf/tools/home-move-1122/home-move all`。先只讀核對，再停舊根、抄、改、收舊樹、起 llm kernel、起根、掛回四隻、核對；任何一步失敗就自動退回舊樹、照舊起舊根，然後停下。
- **沒有人在旁邊也能跑**：每一步開頭先查自己的前提，對不上就停，不硬做。log 在 `~/.aos/scratch/home-move-1122/home-move.log`。
- **不刪檔**：要拿掉的檔都搬進 `~/.aos/scratch/home-move-1122/` 底下的備份夾。舊樹搬進 `~/aos-home.old-1122/`，用的是改名，不是抄。
- **不做的**：不改 `~/.zshrc`（使用者的檔，留給他）、不在 `~/aos-home` 寫 README、不做換機 commit、不 push。
- **金鑰**：腳本不讀、不印、不寫。殼裡有 `LITELLM_KEY` 就只交給 llm kernel 那個視窗；沒有也照起，只是真模型的端點不通，`verify` 會印一句。
- 演練（暫存夾、活樹抄本、假 claude）每一段都過了，見 [04-線6演練](../../../proto8/thinking/2026-11/22/工作區與stack-1122/04-線6演練.md)。

## 各段

`home-move STEP`，每段都能單獨跑，重跑已做完的段會說「already done」。

| 段 | 做什麼 | 失敗時 |
|---|---|---|
| `check` | 只讀：六個 commit 在 HEAD、線 3 已 `install.py`、`ls -A ~/aos-home` 跟寫死的清單一字不差、新位置還空著、搬家的 `mv` 是同一顆碟上的改名、這個殼不是舊樹的子孫、誰在跑、哪幾隻的畫面開著 | 什麼都沒動 |
| `stop-old` | 先關還開著的畫面（`aos-agent close`），再 `aos-daemon-ctl -d ~/aos-home/.stack shutdown`，等舊樹的每一支行程都不見（含 cwd 在 `~/aos-home/llm` 的舊 llm） | 退回＝起回舊根 |
| `copy` | 四格 stack `cp -a` 進 `_stack/procs/`，比對檔案清單；抄本的 `claude/env.json` 搬進 `env-json-bak/`。表不抄 | 新的 `_stack` 搬去備份夾 |
| `fix` | eca-aos 的 subagent 帳改成新寫法（`procs/<名>`）；三份 `exec.json` 搬進 `fix-bak/`，重掛時 daemon 會重寫；兩份 `system.txt` 的 `/home/…/repo/aos` 改成 `~/repo/aos`（原檔先備份） | 同上 |
| `retire-old` | `~/aos-home` 裡 llm 以外的九項，照寫死的清單逐一 `mv` 進 `~/aos-home.old-1122/`；搬完只剩 `llm` | 逐項搬回 |
| `start-llm` | 在 tmux 視窗 `llm` 起獨立的 llm kernel（`aos-exec --stack ~/aos-home/.llm-stack ~/aos-home/llm`），等它回 ping | 停掉，等 cwd 在 `llm/` 的行程不見 |
| `start-root` | 在 tmux 視窗 `root` 起 `_stack` 的根（`cd ~/repo/aos && aos-exec --stack _stack wf/tree/root`，帶 `AOS_LLM_KERNEL`、不帶 `LITELLM_KEY`） | 停掉 |
| `reattach` | 先掛三個 subagent，再掛 eca-aos，全部用相對路徑或指示詞。subagent 掛的參數跟 subagent 工具自己 `add` 時一樣，另明給 `--parent`、`--notify-box`。先掛子、後掛父，所以 eca-aos 醒來對帳時三隻都已在表上 | 同上 |
| `verify` | 六列 `running`；表上沒有絕對路徑；三份新 `exec.json` 的 parent 與通知信箱是指示詞；帳對得上表（＝`subagent ls` 3/4）；llm kernel 只有一台；四份 `claude/env.json` 重記成新值；兩邊的 `ls -A`；退路夾裡沒有東西在跑 | 退回 |
| `rollback` | 照現況退：先關新樹開著的畫面 → 停新根 → 停新 llm kernel（等 cwd 在 `llm/` 的不見）→ 逐項搬回 → 新的 `_stack`、`.llm-stack` 與這次的備份夾搬進 `rolled-back-<時刻>/` → 只有 `stop-old` 開始過才起回舊根 | — |
| `all` | `check` 之後照上表順序跑到 `verify`；`check` 不過就停（沒動任何東西），之後任何一步失敗就跑 `rollback` 並停 | — |

`all` 之外另有四段：`start-old`（起回舊根，`rollback` 用它）、`screen`（替 eca-aos 開畫面，不 attach）、`probe`（掛一隻 agent-fsm、腦設成 `fake`、問一句，確認新的 llm kernel 叫得到，問完拿下表、stack 搬進備份夾）、`status`（只看）。

**tmux**：daemon 都在 socket `~/.aos/scratch/home-move-1122/tmux.sock`、session `home-move` 裡跑（視窗 `llm`、`root`，退回時多一個 `old-root`）。看：`tmux -S ~/.aos/scratch/home-move-1122/tmux.sock attach -t home-move`。**不要對這個 socket 下 `kill-server`、不要關那幾個視窗**：daemon 在前台，視窗關了 daemon 就跟著停。要停用 `aos-daemon-ctl … shutdown`，視窗會自己收掉。每個視窗跑的是 `~/.aos/scratch/home-move-1122/run-*.sh`，裡面寫明 export 了哪幾個變數。

**變數**（都有預設值，真跑不用給）：`HM_HOME`（$HOME）、`HM_REPO`、`HM_AOS_HOME`、`HM_OLD`、`HM_RETIRE`、`HM_LLM_DEF`、`HM_LLM_STACK`、`HM_WORK`、`HM_TMUX_SOCK`、`HM_TMUX_SESSION`、`HM_TIMEOUT`（每個等待的上限秒數，120）、`HM_SUBAGENTS`（`add`＝從外面掛回三個 subagent；`hint`＝只印提示，留給 eca-aos 自己 `subagent add`）。只給演練用的三個：`HM_PATH_PREPEND`（假 claude 的夾）、`HM_GIT_REPO`（查 commit 的 repo）、`HM_FAIL_AT`（跑完這一步就故意失敗）。

## 真跑：外面那個 Claude 照這個做

前提：使用者已經點頭搬；外面那個 Claude Code 是從使用者自己的終端機或 tmux 起的，不是 eca-aos 的子行程（`check` 會查，是的話拒絕）。

1. **等 eca-aos 閒下來**：eca-aos 說「可以搬了」之後就不再做事。`stop-old` 會關掉它的畫面，這段對話會在這裡斷掉。它正在答話的話畫面關不掉，等 `HM_TIMEOUT` 秒後 `stop-old` 失敗，自動退回（什麼都沒變）。
2. **先核對**：`bash ~/repo/aos/wf/tools/home-move-1122/home-move check`。全部 `ok` 才往下。有 `error` 就停下、把那幾行回報給使用者，不自己修。
3. **跑全套，放在背景、不受自己的工具逾時影響**：
   ```sh
   setsid -f bash ~/repo/aos/wf/tools/home-move-1122/home-move all </dev/null >/dev/null 2>&1
   ```
   然後每 10～20 秒看一次 `tail -5 ~/.aos/scratch/home-move-1122/home-move.log`，直到出現這三行之一：
   - `all: done`：搬好了，往第 4 步。
   - `rollback: done`：失敗了，已經退回舊樹，舊根在 tmux 視窗 `old-root` 跑著。往第 6 步。
   - `rollback: finished with errors`：退到一半卡住。照 log 的 `error` 行回報使用者，**不要再跑別的**。
   - `all: check failed; nothing was changed`：前提變了（例如舊根或畫面的狀況跟第 2 步不同）。什麼都沒動，回報那幾行 `error`。
   
   不要直接在前台跑 `all`：工具逾時把腳本砍在半路的話，就不會自動退回。
4. **開 eca-aos 的畫面**：`bash ~/repo/aos/wf/tools/home-move-1122/home-move screen`。它會用 `aos-agent -d ~/repo/aos/_stack open -t eca-aos --detach` 開畫面，等 tmux 那一格出現，再印出兩個指令：一個不 attach 就能看畫面（`tmux -S <socket> capture-pane -p -t cli | tail -20`），一個給使用者 attach（`aos-agent -d ~/repo/aos/_stack open -t eca-aos`，按 `Ctrl-]` 離開，畫面留著）。
5. **確認它醒了**：
   - `verify` 已經在 log 裡寫了 `verify: all checks pass`。四隻都 `running`，它們的 `claude/env.json` 也重記成新值：`AOS_DAEMON` 是 `…/repo/aos/_stack`，`AOS_LLM_KERNEL` 是 `…/aos-home/.llm-stack`。
   - 看畫面：`capture-pane` 看得到 Claude Code 的輸入列，就是開好了。
   - 真的問一句（這會叫真模型，只問這一句）：
     ```sh
     bash -c 'for v in $(compgen -e | grep -E "^(AOS_|CLAUDECODE$|CLAUDE_)"); do unset $v; done; export AOS_HOME=~/repo/aos/proto8; . $AOS_HOME/env.sh; aos-agent -d ~/repo/aos/_stack ask -t eca-aos --timeout-s 600 "The move to ~/repo/aos/_stack is done (log: ~/.aos/scratch/home-move-1122/home-move.log). Reply with one line: your stack path and subagent ls count."'
     ```
     回答要提到 `_stack/procs/eca-aos`，以及 `3/4`。
   - 選用：`home-move probe` 確認新的 llm kernel 用 `fake` 端點答得了，不叫真模型。
6. **回報使用者**，寫進專區或留給 eca-aos 轉達：結果（搬好或已退回）、log 路徑，以及他晚上要自己做的三件事：
   - 照[換機說明書](../../workflows/dev-env/03-換機.md#殼設定檔怎麼寫)改 `~/.zshrc`：舊的第 92～93 行還指著已經搬走的 `~/aos-home/env.sh`，搬完之後開的新視窗會找不到 aos 指令。
   - 要叫真模型的話：在一個有 `LITELLM_KEY` 的殼裡，先 `aos-daemon-ctl -d ~/aos-home/.llm-stack shutdown`，再跑 `home-move start-llm`。
   - 第一次換機 commit（規劃第 14 步：停根 → `stack-commit leave` → 再起根），以及要不要 push。

退回之後（第 3 步走到 `rollback: done`）：舊根已經起回來、四隻都醒了。畫面要重開：照上面第 5 步那串 `bash -c '…'` 的寫法清環境，把裡面的指令換成 `aos-agent -d ~/aos-home/.stack open -t eca-aos --detach`。`~/aos-home.old-1122/` 留著一個空夾，刪不刪由使用者決定。再跑一次 `all` 之前先看 log，找出為什麼失敗。

## 演練怎麼做

```sh
R=~/.aos/scratch/<線名-日期>; mkdir -p $R/home/repo/aos
git -C ~/repo/aos archive HEAD | tar -x -C $R/home/repo/aos
(cd $R/home/repo/aos/proto8 && <清掉 AOS_* 的 bash 腳本> python3 install.py)
bash ~/repo/aos/wf/tools/home-move-1122/rehearse-prep $R          # 只讀地抄活樹進 $R/home/aos-home，換掉活樹路徑與開機碼、端點只留 fake*、放假 claude
export HM_HOME=$R/home HM_PATH_PREPEND=$R/stub HM_GIT_REPO=~/repo/aos
bash ~/repo/aos/wf/tools/home-move-1122/home-move start-old       # 起演練用的「舊樹」（eca 那幾列因為開機碼換過會是 stopped，要手動 ctl start）
bash ~/repo/aos/wf/tools/home-move-1122/home-move all
HM_FAIL_AT=start-root bash ~/repo/aos/wf/tools/home-move-1122/home-move all   # 先 rollback 回去才能再跑
```

假 claude 被叫到只會記一行（`$R/stub/claude-calls.log`），然後一直睡，所以 eca 不會真的開對話。收尾時 `aos-daemon-ctl -d <演練的 stack> shutdown`，tmux 視窗會自己收掉。
