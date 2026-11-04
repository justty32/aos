# 2026-11-04 eca 掛在 daemon 底下跑 claude：工作區的 .claude 會怎樣

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜程式：[cli_session.py](../../../lib/agent/cli_session.py)、[aos-eca-turn](../../../bin/aos-eca-turn)、[eca](../../../extras/eca/README.md)｜相關：[11-03 stack-where](../03/stack-where.md)、[aos-agent 06](aos-agent/06-衝突與方向題.md)

本檔只記使用者原文、結論、要帶給使用者的方向題（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。11-04 調查＋WSL 實驗（claude 2.1.318、haiku、每次有花費上限；暫存資料夾做完已刪、無殘留行程）；只讀不改程式。

## 使用者原文（11-04，逐字）

> 工作區這塊，你知道的，claude code會吃其cwd的.claude，後續在這個資料夾工作的另外的claude code也會吃這個。

> 啊，claude code讀cwd的.claude，這需要去看看，在daemon,eca的共同作用下會發生啥事。

## 結論

**cwd＝工作區**（`AOS_WS`，add 的 `--ws`，沒給＝下指令時的 cwd）：非互動 `claude -p` 由 `run_claude_stream(cwd=ws)` 起，畫面由 `tmux new-session -c ws` 起。不是 stack。實驗 init 事件 `cwd /tmp/…/ws`、hook 看到 `CLAUDE_PROJECT_DIR=<ws>`。

**會讀到什麼、誰蓋誰**（實驗 E1 的 init 事件＋官方文件 settings／memory／mcp／permissions 頁）：

| 東西 | 非互動 -p | 畫面 | 跟 eca 的旗標 |
|---|---|---|---|
| `CLAUDE.md` | cwd 往上每層都讀（E1） | 同 | 沒擋 |
| `.claude/settings.json` | 只讀 cwd 那層；**hooks 照跑、`env` 照套，不用信任**（E1） | 答了信任才跑 | 畫面的 `--settings` hooks 跟它**合併、都跑**（E2） |
| `.claude/settings.local.json` | 從 git 根讀 | 同 | 權限合併；`--tools` 已收窄 |
| `.claude/agents`、`commands`、`skills` | 都載入（E1） | 同 | 沒擋 |
| `.mcp.json` | **不問就連**（E1b） | 先問 | cli.json 的 `--strict-mcp-config` 擋掉，只剩 aos-mcp |
| `~/.claude` | settings、skills、plugins 都載入（E1） | 同 | — |

`--model`、`--permission-mode` 這類 CLI 旗標高於所有設定檔；`--setting-sources` 可只留某幾層；`CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` 可不讀 CLAUDE.md；`--bare` 全不讀但要 API key、不能用訂閱登入（文件 headless 頁）。

### 各狀況（細節與證據在 [01-各狀況](eca-claude-dir/01-各狀況.md)）

1. 畫面開在沒信任過的工作區、有人 say：字貼進信任提問、Enter 選到 No → claude 退出、信丟、這隻從 daemon 表掉下來（高）。
2. 工作區自己的 hooks、CLAUDE.md、agents／commands／skills 都進 eca；工作區是 aos repo 時 eca 會照 wf 規矩做事、長對話 compact 時跑 compact_reload.sh（中）。
3. eca 自己不在工作區建檔；會寫進 `.claude/` 的只有人在畫面上選「don't ask again」、`/init`、或給它 Write；stack 在 `ws/.stack/` 時兩隻讀得到彼此的 history（低）。
4. 同工作區兩隻（或一隻＋人）session 不撞；auto memory 是同 repo 共用的（低）。
5. 環境：CLAUDECODE 之類會被 claude 自己蓋掉；`AOS_STACK`＝eca 自己的 stack，給了 Bash 就可能寄信給自己（中）。
6. codex：讀 `~/.codex` 與 git 根到 cwd 的 AGENTS.md；WSL 上預設模型被拒、現在一定 CliFailed。

### 建議（細節，照原則可以直接做）

- `cli_session.start` 等畫面穩了以後，畫面上有信任提問（`Accessing workspace`／`trust this folder`）就不放行：`open -d` 報 `TrustPending`、叫人接進去答；`live()` 送字前也先檢查。這樣不會把信貼進提問。
- cli_session 起 CLI 前把 `AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO` 從 claude／codex 的環境拿掉（aos-mcp 本來就用 `--stack` 傳），`AOS_WS` 留著。
- 試驗場 README 第 4 節加一行：工作區是 git repo 時 `.stack/` 會出現在 `git status`、claude 也讀得到。

## 要帶給使用者的方向題

1. **eca 要不要吃工作區的 Claude 設定？**（甲）照現在：跟人在那個資料夾開 Claude Code 一樣，CLAUDE.md、hooks、agents、skills 全吃——好處是 repo 的規矩自動生效；壞處是工作區是 aos 這種「給頂層 agent 用」的 repo 時，eca 會照那套規矩做事。（乙）隔離：cli.json 預設加 `--setting-sources user`（不讀工作區的 settings 與 hooks）＋環境 `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`（不讀 CLAUDE.md），要吃的那隻自己拿掉。判準：你掛 eca 的工作區，多半是「有 CLAUDE.md 寫給人用的 repo」就選乙，多半是「專門給 eca 的空資料夾」就甲乙沒差。
2. **stack 預設放工作區，跟「工作區是 git repo」打架**：11-03 你定「預設還是要放工作區」（[stack-where](../03/stack-where.md)）。工作區是 git repo 時，`.stack/` 是未追蹤的雜訊、裡面的 history 也被 claude 讀得到。要不要（甲）照舊、靠 `.gitignore`；（乙）工作區是 git repo 時預設放別處（例如 daemon 的 stack 不在工作區起）？

## 決定（11-04 使用者）

> .claude調查這塊。全部都是自己要承擔的風險

調查列的狀況（信任提問時送字丟信、工作區 hooks／CLAUDE.md 照吃、AOS_STACK 傳進 claude、stack 放工作區、WSL codex 預設模型不能用等）**都不改程式**，算使用者自己要承擔的風險；兩題方向題照現況（eca 照吃工作區設定、stack 照舊放工作區）。
