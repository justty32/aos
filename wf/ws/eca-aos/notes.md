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

## 還開著的（從 HANDOFF 接的）

1. 使用者要細說「把stack一起隨機器搬遷，不是一個好主意」那塊。
2. 早上「先處理這個，然後我們再來」後面要做的事，他還沒說。
3. progress `company-wsl-1123-verify`（真模型端點、第二帳號沒驗）、`sol-high-pack`。
4. 家機還是舊樣子，pull 之後要照 03-換機「家機照做」。
