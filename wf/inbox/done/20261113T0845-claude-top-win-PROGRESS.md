---
from: claude-top-win（公司 Windows 頂層，11-13 早）
to: 公司 WSL 的下一個頂層 session（aos 體系）
status: PROGRESS
at: 2026-11-13T08:45:00+08:00
reply-to: 不需回信
---
# 11-13 早交接：公司 WSL 已改住 ~/aos-home、工作 repo 換成 ~/repo/aos，重整都做完了；Windows 頂層要關，之後由你接

## 做了什麼

使用者 11-13 早在公司 Windows 開 session，中途決定整個遷到 WSL、把 Windows 那個 session 關掉，並說「哈哈，下個session，就會是aos體系了！」——你是 aos 體系裡的 session。

**今天的授權與工作方式（使用者原話）**：「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」——不逐次 push，五點下班前統一推一次，推之前跟他說一聲。

**今天使用者的裁定（原話，依序）**：

- 「幫我把現有的WSL遊樂場重刷一次，包括裡面的知識庫。」（後來被下面幾句取代）
- 「要的，整個重弄好」（答：WSL 那份要不要 pull、重 build、重裝、跑全套測試）
- 「等等，應該說，我要遷移到WSL那邊去。所以WSL那邊，可能就不會是遊樂場了。可能...~/aos-home？」
- 「住~/aos-home，我自己搭的都清掉，我們整個重新來過。然後~/repo/simple_tools/aos就是最新的。」
- 「直接~/repo/aos好了」（答：用哪份 repo）
- 「好了之後弄一分我可以照著做的手冊到桌面」
- 「這些舊的都直接刪」（指舊 `~/aos-home`、`~/repo/aos-tools`、`~/repo/simple_tools/aos`）
- 「連同~/repo/simple tools一起刪掉。遊樂場也都刪掉」
- 「/tmp可以清掉，別占用記憶體」

**現況（Windows 頂層 08:40 實查過的）**：

- 工作 repo：`~/repo/aos`，HEAD `e1cb4fc33`（origin 的 `2e8eb6736` ＋ 1 個今早文書 commit，未 push）。`~/.local/bin` 的 25 條 `aos-*` 指令連結全指這份。
- `~/aos-home`：從零重搭的新樹（根 `_clock`、`_sweeper`、`foreman`；領班；一隻 `eca_main`＝opus、花費無上限、26 支 aos 工具、system 指 knowledge；沒建問腦總機），樹停著。存檔一份在 `~/aos-saves/aos-home-1113-0825`。
- 已刪：舊 `~/aos-home`、`~/repo/aos-tools`、`~/repo/simple_tools/aos`、`~/code/playground*` 八夾（含全部備份）。
- 沒有殘留的 `aos-` 行程。
- 桌面手冊：Windows 桌面 `aos-home-手冊.html`，原稿在 `proto8/thinking/2026-11/13/aos-home-手冊.html`。

**子 agent 回報、頂層沒逐項重驗的**：全套測試 66 夾 1354 例只紅既有 4 支（aos-agent `test_daemon_down` 2 支、box_check 2 支）；opus 真問一句、存檔讀檔、加一隻再拿掉都實跑過。細節在今天的 thinking 夾與日誌。

## 產出（檔案路徑 / commit / 分支）

`~/repo/aos` main `e1cb4fc33`（未 push）。Windows 那份 `C:\code\mine\simple_tools\aos` 停在 `2e8eb6736`、乾淨，沒有新 commit。

## 沒做到、或證據不足的部分

- `/tmp` 清理：寫這封信時子 agent 才剛被補派去清（它的測試留下很多 `judge-test.*`、`aos-daemon-b.*`、`ft1113`、`ftb`）；開場請 `ls /tmp` 看清了沒，沒清完就接著清（只清自己帳號名下、沒人在用的工作殘留，系統的不動）。
- 沒驗：`aos-agent open` 的畫面、實際叫一次子 agent（那台應是唯讀 9 支，沒數）、外部 MCP、重抄 py／templates 那段。
- 舊遊樂場裡 eca_opus 11-12 自己寫的 `ws/notes/` 筆記四檔與 `ws/new_tools/aos_cache/` 已跟著刪掉，沒帶到新家。
- 那個文書 commit 的結尾署名寫 Opus 5.5（實際做事的是 opus 子 agent）。

## 需要對方或使用者決定的事

1. `~/repo/simple_tools` 沒刪：它的 main 有 8 個沒推的 commit，全在 `freepy/`（`57da41f`～`14a0a8f`），遠端 `justty32/simple_tools` 沒有。要使用者定：推上去再刪，或確定不要了直接刪。（WAIT_USER 04 有一行）
2. `~/.claude.json`（2 處 `~/repo/simple_tools`）與 `~/.codex/config.toml`（`[projects."…/simple_tools/aos"]`、`[projects."…/aos-tools"]`）還留著舊路徑的信任紀錄，沒改，要不要清由使用者定。
3. repo 裡還有示範舊路徑 `~/repo/aos-tools/proto8` 的地方（幾份 `.env` 註解、`templates/tests/test_paths_move.py` 的斷言、兩份 docs），沒改；要改得連測試一起改。
4. `~/.local/lib` 一帶有改名留著的 `aos-proto8.pth.bak-1113-aos-tools`，可刪。
5. 下班前的 push。
6. 之後可以接的（昨晚 HANDOFF 的順序，使用者還沒挑）：① 主 session 接 aos（`proto8/thinking/2026-11/12/wf-to-aos/02-寄信給人與主session.md`）② 外部 MCP 接真的別人寫的 stdio server（要下載、先問）③ `wf/wait-user/01-要你裁的.md` 待裁各題（可用選項框一題一題問）④ eca_tidy 剩兩件。

本信辦完照規矩 `mv` 進 `wf/inbox/done/`。

## 補（08:50，Windows 頂層關前）

- /tmp 已清完（40M → 572K；只留 `claude-1000`、`node-compile-cache` 與系統夾），上面「/tmp 清理」那條不用再接。
- `~/repo/aos` main 現在是 `aa7eab4dc`，比 origin 多 2 個 commit（`e1cb4fc33`、`aa7eab4dc`），未 push。
- `~/repo/simple_tools` 已照使用者「不要了直接刪」整夾刪掉（8 個沒推的 freepy commit 一併放棄），上面「需要決定的事」第 1 點結案；`~/repo/aos` main 多一個文書 commit、未 push。
