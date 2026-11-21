教學（proto8/docs/tutorial）更新到 2060ee9d5、補一章 05b 起 eca_main，乾淨複本照著走到 eca_main 用真的 claude 回話（線 top-1121-tutorial）。

← [2026-11-21](README.md)｜教學：[docs/tutorial](../../../docs/tutorial/README.md)

## 使用者原話（11-21 下午，逐字）

「然後目前的進度還不錯，我應該晚上會自己來玩aos，所以這邊要請你幫忙準備各種東西。教學稍微更新一下就好，只要弄到第一個eca_main出來就好，剩下的我直接問agent。」

## 結論

- 照改好的教學走得到 eca_main：家機乾淨複本（`git archive` `2060ee9d5`，`~/.aos/scratch/top-1121-tutorial/`）兩趟都通。第一趟 01→05 全做再做 05b；第二趟新夾只做 01→02→05b。eca_main 用真的 `claude`（2.1.330、sonnet）回 `pong`、叫 aos 工具 `peek_now_time` 回時間、板子關機再開後問上一句答什麼仍回 `pong`（對話接著）。
- 現有教學 01～05 照抄**不會卡住**，只有輸出跟檔名對不上（下表）；舊教學根本沒有 eca_main。
- eca_main 不需要 llm kernel、不需要 `agent.py`、不需要 tmux 預先開；要的是 `AOS_HOME`＋`install.py`、一塊開著的板子、`claude` 在 PATH 上且登入過。

## 走現有教學時對不上的地方（2060ee9d5、家機）

| 章 | 哪裡 | 教學寫的 | 現在 |
|---|---|---|---|
| 02 | `ls -A root` | 照字母排 | 家機 locale 排法不同（內容一樣），沒改 |
| 03 | `ls llm` | 6 項 | 多 `kernel_hookeds.json`、`kernel_hooks.json`（hook 新格式） |
| 03 | `aos-llm ls \| head -4` | `fake` 開頭 | `astra` 排第一（範本 11-21 加了 astra 包），`fake-demo-slow` 擠出前四行 |
| 04 | 骨架 `ls`、`--compile` 的 wrote | `hooks.json` | `hookeds.json` |
| 04 | 欄位表 `hooks` 那列「編譯成」 | `hooks.json` | `hookeds.json` |
| 05 | 全部 | — | 跟教學一致（history 位元組數、記憶體這類數字不同） |
| 06 之一 | 6.4 結論 | `tools.json`／`hooks.json` 那格 | `hookeds.json`（順手改） |
| 06 之三 | 刪斷點那行輸出 | `.stack/procs/ann/hooks.json#/hooks/gdb_0001` | 照 `aos-agent hook` 的程式是 `.stack/procs/ann/hookeds.json#/gdb_0001`（讀程式改，沒實跑） |

## 改了哪些

| 檔 | 改什麼 |
|---|---|
| `README.md` | 標題加 eca_main；實跑說明加 11-21 家機 `2060ee9d5`；加「只想最快起一隻 eca_main：01、02 → 05b，03～05、06～08 可跳過」；章節表加 05b；走完的樣子加 `agents/eca_main`；最容易卡住加一條（claude 先登入、第一次 open 要選信任） |
| `01-開始前.md` | 結論加「eca_main 另外要 claude 裝好登入」；整套表加 eca_main 一列；資料夾圖加 `agents/eca_main/`；details 提 start-eca |
| `02-架daemon.md` | 章末加「想直接起 eca_main：板子開著跳 05b，`.env` 那行不影響」 |
| `03-灌kernel.md` | 兩段輸出換成實跑的；腦包那句補「照名字排，真模型的包也列出來」 |
| `04-寫原始碼.md` | `hooks.json` → `hookeds.json`（三處） |
| `05-掛上去跑.md` | 下一章連結改 05b |
| `05b-起eca_main.md` | 新章：要先有什麼、抄 eca-claude 掛上、say／listen、叫一支 aos 工具、ctl state、open 畫面（信任提示）、llm set／reset、stop／start |
| `06-接著開發-1-改與工具.md` | 上一章連結改 05b；`hooks.json` → `hookeds.json` 一處 |
| `06-接著開發-3-除錯與腳本.md` | 刪斷點輸出的路徑一處 |

## 到 eca_main 的最短路（逐步）

```sh
export AOS_HOME=~/repo/aos/proto8            # 一台一次
source $AOS_HOME/env.sh                      # 每個視窗
command -v claude && claude --version        # 要有、要登入過（沒登入：打一次 claude 登入）
mkdir -p ~/code/aos-tut && cd ~/code/aos-tut
cp -r $AOS_HOME/templates/daemon-root root
sed -i 's|^AOS_LLM_KERNEL=.*|AOS_LLM_KERNEL=${AOS_STACK}/procs/llm|' root/.env   # 02 章那行；對 eca_main 沒影響
aos-exec root                                # 視窗 A，前景
# 視窗 B（同樣 source、cd）：
mkdir -p agents
cp -r $AOS_HOME/templates/eca-claude agents/eca_main
aos-agent -d .stack ctl add --auto-restart -w . agents/eca_main
aos-agent -d .stack --target eca_main say "Reply with exactly one word: pong"
aos-agent -d .stack --target eca_main listen --timeout-s 180
aos-agent -d .stack --target eca_main open   # 選看：第一次要選 Yes, I trust this folder；Ctrl-] 跳出
aos-daemon-ctl -d .stack shutdown            # 收
```

## 實測

- 假腦：03～05（llm kernel `fake`、ann 回 `FAKE ANSWER to: hello (tool said: …)`、ctl state、stop／start）。
- 真模型（claude 2.1.330、sonnet，共 4 次小呼叫）：`pong`；`peek_now_time` → `2026-11-21T07:08:39Z`；第二趟新夾 `pong`；關機再開後「上一句答什麼」→ `pong`。
- `llm set model=opus`／`reset`、`ctl stop`／`start` 實跑（不叫模型）。
- `open`：在暫存的 tmux 裡開，畫面出現 Claude Code 的「信任這個資料夾嗎」提示，預設游標在 `No, exit`；我按 Enter（＝No）退出，沒按信任（不想替使用者在 `~/.claude.json` 加信任紀錄），之後未實跑。
- 沒試：`claude` 沒登入時的樣子、codex／pi 版。

## 替使用者做的選擇

1. 新章放在 05 後面叫 `05b`，不改既有檔名；README 標「01、02 → 05b」為最短路。
2. 新章用 `eca-claude` 範本（不是整棵 `start-eca`），接在教學同一塊板子上，`-w .`（跟 05 章 ann 一樣），並寫明 Write／Edit／Bash 不問就准、要換工作區就改 `-w`。
3. 02 章那行 `.env` 的 sed 在最短路上照做（不影響 eca_main，省得兩套說法）。
4. 05b 的範例話用英文單字 `pong`（好比對），另說中文也行。
5. 06 之一、06 之三只改 `hooks.json` 字眼與上一章連結，其餘不動。

## 沒改但對不上的（必經之路以外）

- 07 換成真模型：表少 `astra`；luna 那包樣子少了今天加的 `"api": "responses"`、`reasoning_efforts`；整章仍未實跑。
- 06 之一～三、08：這次沒重跑（只照程式改了上面兩處字眼），其他輸出可能有差。
- 網站頁 `docs/zh/tutorials/first-tree.html`：是生成物，來源 `wf/temp/ok-release/drafts/v3/docs/zh/tutorials/first-tree.md`，用 `wf/temp/ok-release/drafts/tools/build-draft.py` 轉。跟教學差在：擺法是 `llms/` 與 `tree/` 兩夾並排（kernel 不掛在板子上，`.env` 指 `${AOS_WS}/../llms/stacks/llm`）、`defs/`＋`stacks/root` 的夾名、ann 抄 `agent-fsm` 範本（不是 `agent-python` 寫 `agent.py`）、指令用 `-t`；沒有 eca_main。檔名（`hookeds.json`／`hooks.json`）已對上新格式。這次沒動。

## 程式或範本的問題

- 沒有讓路走不通的；`ctl state` 列 6 個 hook、stderr.txt 是空的。
- 要注意的不是 bug：第一次 `aos-agent open` 會碰到 Claude Code 自己的「信任這個資料夾嗎」提示（`claude -p` 那條路不問），游標預設在 No。

## 活樹（`~/aos-home`）

- 現況（只 `ls`、`pgrep` 看，沒下 aos 指令）：start-api 樹，`agents/` 只有 `ann`（sol）、另有 `llm/`、`perm/`；沒有 eca_main；沒有它的行程在跑。
- repo 的 `proto8/lib/` 已經跟 HEAD 的 `py/` 一樣（`diff -rq py/aos lib/aos` 沒差、`lib/aos/gdb/decl.py` 在、`hook_handle.py` 已不在；檔時間 11-21 14:14～14:26，有人在 repo 跑過 install.py）。`97d4abc16..HEAD` 動到 py／templates 的四個 commit（hook 總文件、compact 第 4 刀、刪 hook_handle／hook_flags、gdb 參考宣告）都跟 eca 這條路無關。
- 兩條路：甲＝在 `~/aos-home` 加（`cd ~/aos-home && source env.sh`、視窗 A `aos-exec root`、視窗 B `cp -r $AOS_HOME/templates/eca-claude agents/eca_main`、`aos-agent -d .stack ctl add --auto-restart -w <工作夾> agents/eca_main`、say／listen）；乙＝照教學另起 `~/code/aos-tut`（01、02、05b）。

## 收尾

- 暫存夾 `~/.aos/scratch/top-1121-tutorial/`（`repo/` 複本、`tut/`、`tut2/` 兩棵樹、腳本與 log）留著。
- 兩棵樹都 `aos-daemon-ctl shutdown`，記下的 pid 全不在。
- tmux：這台開工時沒有 tmux server；我在預設 socket 開 `top1121tut-open` 測畫面，使用者的 tmux-continuum 隨 server 起來自動復原了 9 個 session（aos-rc、arcagi、cx-zm2-a/b/c、guigu、longyin、talk-decide、world-talk，都是閒著的 zsh）。我的那個已用名字關掉；那 9 個不是我的、沒動，tmux server 因它們還活著。
