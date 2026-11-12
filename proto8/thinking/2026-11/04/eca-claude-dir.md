# 2026-11-04 eca 掛在 daemon 底下跑 claude：工作區的 .claude 會怎樣

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜程式：[cli_session.py](../../../lib/agent/cli_session.py)、[aos-eca-turn](../../../cmd/aos-eca/bin/aos-eca-turn)、eca｜相關：[11-03 stack-where](../03/stack-where.md)、[aos-agent 06](aos-agent/06-衝突與方向題.md)

本檔只記使用者原文、調查結論、決定（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。結論來自 11-04 WSL 實驗（E1～E3；claude 2.1.318）與官方 Claude Code 文件。

## 使用者原文（11-04，逐字）

> 工作區這塊，你知道的，claude code會吃其cwd的.claude，後續在這個資料夾工作的另外的claude code也會吃這個。

> 啊，claude code讀cwd的.claude，這需要去看看，在daemon,eca的共同作用下會發生啥事。

## 結論

**cwd＝工作區**（`AOS_WS`，add 的 `--ws`，沒給＝下指令時的 cwd）：非互動 `claude -p` 由 `run_claude_stream(cwd=ws)` 起，畫面由 `tmux new-session -c ws` 起。不是 stack。

**會讀到什麼、誰蓋誰**：

| 東西 | 非互動 -p | 畫面 | 跟 eca 的旗標 |
|---|---|---|---|
| `CLAUDE.md` | cwd 往上每層都讀（E1） | 同 | 沒擋 |
| `.claude/settings.json` | 只讀 cwd 那層；**hooks 照跑、`env` 照套，不用信任**（E1） | 答了信任才跑 | 畫面的 `--settings` hooks 跟它**合併、都跑**（E2） |
| `.claude/settings.local.json` | 從 git 根讀 | 同 | 權限合併；`--tools` 已收窄 |
| `.claude/agents`、`commands`、`skills` | 都載入（E1） | 同 | 沒擋 |
| `.mcp.json` | **不問就連**（E1b） | 先問 | cli.json 的 `--strict-mcp-config` 擋掉，只剩 aos-mcp |
| `~/.claude` | settings、skills、plugins 都載入（E1） | 同 | — |

`--model`、`--permission-mode` 這類 CLI 旗標高於所有設定檔；`--setting-sources` 可只留某幾層；`CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` 可不讀 CLAUDE.md；`--bare` 全不讀但要 API key、不能用訂閱登入。

### 各狀況（細節在 [01-各狀況](eca-claude-dir/01-各狀況.md)）

1. 畫面開在沒信任過的工作區、有人 say：字貼進信任提問、Enter 選到 No → claude 退出、信丟、這隻從 daemon 表掉下來（高）。
2. 工作區自己的 hooks、CLAUDE.md、agents／commands／skills 都進 eca；工作區是 aos repo 時 eca 會照 wf 規矩做事、長對話 compact 時跑 compact_reload.sh（中）。
3. eca 自己不在工作區建檔；會寫進 `.claude/` 的只有人在畫面上選「don't ask again」、`/init`、或給它 Write；stack 在 `ws/.stack/` 時兩隻讀得到彼此的 history（低）。
4. 同工作區兩隻（或一隻＋人）session 不撞；auto memory 是同 repo 共用的（低）。
5. 環境：CLAUDECODE 之類會被 claude 自己蓋掉；`AOS_STACK`＝eca 自己的 stack，給了 Bash 就可能寄信給自己（中）。
6. codex：讀 `~/.codex` 與 git 根到 cwd 的 AGENTS.md；WSL 上預設模型被拒、現在一定 CliFailed。

## 決定（11-04 使用者）

> .claude調查這塊。全部都是自己要承擔的風險

上面各狀況**都不改程式**，算使用者自己要承擔的風險；eca 照吃工作區的 Claude 設定（CLAUDE.md、hooks、agents、skills）、stack 照舊預設放工作區（11-03「預設還是要放工作區」，[stack-where](../03/stack-where.md)）。
