頂層 agent `eca-aos` 自己的筆記：正在做什麼、還開著什麼、決定了什麼；壓縮後先讀這份。

# eca-aos 筆記

← [地盤 README](README.md)｜規矩：[wf/ws](../README.md)、[AGENTS.md](../../../AGENTS.md)

## 我是誰、在哪

- `eca-aos`：範本 `proto8/templates/eca-claude`，工作區 `~/repo/aos`，stack `~/repo/aos/.stack/procs/eca-aos`，掛在子 daemon `repo-aos` 底下；用第二帳號（`CLAUDE_CONFIG_DIR=~/.claude-alt`）。
- 這台是公司 WSL（Ubuntu）。樹：根 `~/aos-home/.stack`（`_clock`、`_sweeper`、`llm`、`repo-aos`、`eca_main`），底下 `~/repo/aos/.stack`（`_clock`、`_sweeper`、`eca-aos`）。
- aos 工具只有 json、index、mailbox、math、peek、self_state、self_tools 這幾包；檔案與指令用 Claude Code 自己的。
- 這台沒有 `~/.aos/user/`（使用者專區沒建）：要問使用者的題目放 `wf/user`（使用者 11-23「沒有~/.aos/user，那就放wf/user。」，已抄進 `common/user.md` 與規矩卡）。
- 根 daemon 上的 `eca_main`（工作區 `~`）、`mine_arena`（子 daemon，工作區 `/mnt/c/code/mine/arena_cheater`，底下 agent `main`）是使用者自己開的，不是我的東西，不碰。

## 2026-11-23 上午（第一個 session）

- 使用者第一句：「嗨，請先大致掌握aos體系。」→ 只讀、沒動任何東西。
- 讀過：AGENTS.md、知識庫 `_description`／`world`／`body`／`rules`／`eca_reading`／`cli/eca`／`user_zone`、`common/user.md`、規矩卡、aos-teams 短卡、WORKFLOWS、HANDOFF、proto8/README、`wf/ws` 與 `wf/user` 的 README、`wf/user/待答-1122.md`、progress 的標題。
- 三軸：信箱空、`wf/inbox` 空；progress 31 條 open（多半「等使用者」）；`wf/user` 沒有沒交的改動，讀到 `d5e9a39e4`（記在 `user-seen.json`）。
- 發現：本地 `origin/main` 跟 HEAD 同一個 commit（`d5e9a39e4`），HANDOFF 寫的「都沒 push」看來已經過時（沒 fetch 驗過遠端）。

## 2026-11-23 上午：滾輪調查

- 使用者：「我剛剛用aos-agent新開了一個claude eca 互動畫面，然後滑鼠滾輪又不能用了。」「那個eca的位置是在~/aos-home/.stack/proc/mine_arean/proc/main」（實際路徑 `~/aos-home/.stack/procs/mine_arena/procs/main`）。
- 派了一隻 opus 的 Claude 子 agent 做只讀調查（查舊紀錄、起 tmux 的程式、活的 tmux 選項）；派的時候還不知道是 `mine_arena/main`，任務書寫的是「多半是 eca_main，自己確認」。回來後要對它有沒有查到對的那個畫面。

- **結果（12:15 回來，關鍵幾項我自己對過）**：不是 tmux 的問題。範本 `proto8/templates/eca-claude/cli.json` 的 flags 從 11-22 的 `9d738cc77` 起帶 `--setting-sources project,local`，claude 不讀 `~/.claude/settings.json`；主帳號那份的 `"tui": "fullscreen"` 被跳過，主帳號預設是舊式畫法，不跟終端要滑鼠，滾輪沒人接。第二帳號 `~/.claude-alt` 沒設也是全螢幕（原因不明，推測是帳號層級的開關）。`mine_arena/main` 11:50 用主帳號開（壞），11:58 用第二帳號重開（好）；根 daemon 那棵不帶 `CLAUDE_CONFIG_DIR`，所以不特別帶就是主帳號。
- 修法選項：① 範本 `cli.json` 的 `settings` 加 `"tui": "fullscreen"`（推薦；子 agent 在暫存 tmux 用 `--settings '{"tui":"fullscreen"}'` 驗過會變全螢幕、能捲）；② `cli_screen.py` 的 `TMUX_CONF` 加 `set -g mouse on`（要 `install.py`，會搶滑鼠選字，沒實測）；③ 都做。使用者 11-23 選「1」：三份 `cli.json`（`eca-claude`、`eca-claude-alt`、`start-eca/agents/ann`）的 `settings` 加了 `"tui": "fullscreen"`，`test_cli_settings.py` 放行這一鍵，兩份 README 與 `templates/docs/01-eca-claude.md` 補了說明；在乾淨複本跑 `test_cli_settings`、`test_eca_claude_alt`、`test_start` 都過，`claude -p` 帶這項照常回答。**還沒在真的畫面驗**：要使用者用主帳號重開一個畫面試滾輪。
- 沒找到「上次」的紀錄（repo、git log、兩個帳號的對話都搜過）。
- 子 agent 留下的：`~/.claude/.claude.json`（998 bytes，12:04，實驗時帶 `CLAUDE_CONFIG_DIR=~/.claude` 生出來的，平常不會被讀）、`~/.claude/backups/` 一份 84 bytes、兩個帳號 `projects/-home-guanyu-repo-aos/` 可能多幾段短對話；scratch 在 `…/scratchpad/wheel/`。刪不刪要使用者說。
- **痕跡刪了**（使用者 11-23「滾輪可以用了，那幾個痕跡刪掉吧」）：`~/.claude/.claude.json`、那份 84 bytes 的備份、六段實驗對話（主帳號 4、第二帳號 2，在 `projects/-home-guanyu-repo-aos/`）與它們的 `session-env/` 夾。兩份 `history.jsonl` 裡六行 `!seq 1 300` 沒動（活著的畫面一直在寫那兩個檔）。子 agent 說「沒叫模型」不對：六段對話各跑了一小輪模型（讀 AGENTS.md，一段還跑了唯讀的 ls／cat／git status），沒寫任何檔。
- 滾輪：使用者 11-23 回報「滾輪可以用了」，真畫面驗過。

## 2026-11-23 上午：建這台的使用者專區

- 使用者接著說：「然後~/.aos/user看起來還是必要的，開一個claude subagent去弄吧」。
- 派了第二隻 opus 的 Claude 子 agent：照 `aos-user init` 建 `~/.aos/user/`、驗 `door`、不寄測試信進真專區；`aos-user tick` 的 timer、全景頁、殼設定檔只查不做，回來報選項。只准寫 `~/.aos/user/` 與 scratch。
- **建好了**（子 agent 回報，我 `ls`、`aos-user door` 對過）：`~/.aos/user/` 在，`aos-user` 在 PATH（`proto8/frontend/bin/aos-user`）。真專區沒收發過信；整條只在假專區跑通。
- 我的 stack 原本沒有 `mailbox/`，`aos-user send` 會報 `MailboxMissing`；已跑 `aos-post init $AOS_STACK/mailbox` 補上。
- **這台要問使用者的題目改回寄專區**（`aos-user send --kind decide`，回信 `aos-user verify`）；`common/user.md` 那句「沒有專區的機器放 wf/user」是通則，照留。
- 沒做、等使用者說：tick 的 timer（子 agent 推薦先不裝，跟家機 11-22 選的一樣；這台沒有 `notify-send`）；全景頁沒在跑（他要看題目得自己起 `AOS_DAEMON=~/repo/aos/.stack aos-frontend serve`，或用 `aos-user ls`／`show N`／`answer N q1:a`）。
- 文件漏寫「寄件人自己的 `mailbox/` 要先存在」：`eca-aos-kb` 這台沒掛，沒地方寄，記在 progress `aos-user-home` 第 ④ 件。
- HANDOFF 那句與 progress `aos-user-home` 已更新。

## 還開著的（從 HANDOFF 接的）

1. 使用者要細說「把stack一起隨機器搬遷，不是一個好主意」那塊。
2. 早上「先處理這個，然後我們再來」後面要做的事，他還沒說。
3. progress `company-wsl-1123-verify`（真模型端點、第二帳號沒驗）、`sol-high-pack`。
4. 家機還是舊樣子，pull 之後要照 03-換機「家機照做」。
