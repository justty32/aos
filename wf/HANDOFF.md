# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-23 上午（公司機）——公司 WSL 重建好了、stack 改名 `.stack` 不跟機器搬；樹現在是停的，使用者自己開

**使用者換 session 前的話（逐字）**：「把樹停掉，我自己開。然後你這邊收尾，我要換session了。順便告訴我怎麼起樹」。

**授權（11-23 當場）**：派工照「普通工作交給opus，簡單工作或雜活交給sonnet」「agent做事前都要讀過wf/規矩，簡單工作或雜活除外」「agent可以再派子agent，模型隨意」。**push 還沒給**：他說「我今天五點下班，下班前再統一push」，要他本人再說一次才推。刪檔只給了換機工具與殼設定備份（「換機工具那幾個檔、幾份 .bak-1123* 備份。 <- 都刪掉。」，已刪）。頂層是 Windows 上的 Claude Code，不在 aos 樹裡；實際工作在 WSL 的 `~/repo/aos`，Windows 那份 clone 不動。

**這台現況**（線 `two-trees-1123` 改過）：
- 一棵樹，根在 `~/aos-home`（根定義 `~/aos-home/root/`、stack `~/aos-home/.stack`，普通 Claude 設定檔），表上四列：`_clock`、`_sweeper`、`llm`、`repo-aos`。
- `llm`：llm kernel，定義 `~/aos-home/llm`、stack `~/aos-home/.stack/procs/llm`（＝`AOS_LLM_KERNEL`），端點指 `localhost:4000/v1`（多加了一包 `sol-high`）。
- `repo-aos`：repo 那棵（子 daemon），定義 `wf/tree/root`（沒改）、stack 照舊 `~/repo/aos/.stack`，這一列帶 `CLAUDE_CONFIG_DIR="$HOME/.claude-alt"`（第二個帳號，他已登入）與 `AOS_LLM_KERNEL`。底下掛了 `eca-aos`（範本 `eca-claude`，筆記 `wf/ws/eca-aos/notes.md`），**從沒開過畫面、沒問過話**。
- 全停了，沒有 aos 行程。登入殼是 zsh（`~/.zshrc`、`~/.bashrc` 都有 aos 段；`AOS_LLM_KERNEL` 改指新路徑；`.bak-1123*` 備份 11-23 已刪）。舊的 `~/aos-home/.llm-stack/` 不用了，沒刪。
- LiteLLM 用他自己開的 `~/repo/llm_proxy` 根那套（1.87.5、不用 key），不是 pinned；**4000 埠一直沒在聽，真模型沒驗過**。

**要改成兩棵樹**（使用者換 session 前又說，逐字）：「應該說，我預期會有兩棵樹，一棵是這台的，在~/aos-home，底下掛著llm kernel。另一棵是repo aos的，啟動的時候會是CLAUDE_CONFIG_DIR=alt AOS_LLM_KERNEL=...」接著又補（逐字）：「家機那塊確實也要變成~/aos-home一套，底下是llm_kernel，不過repo aos這個樹會變成~/aos-home底下的一個proc。這台WSL也可以這樣嗎？」——**可以，已照這樣建好**（線 `two-trees-1123`）：先在暫存樹試通，再動真的；試起過一次（三層的表都 running、fake 回 `FAKE ANSWER to: hello, nested tree`、eca-aos 拿到 alt 帳號與新的 `AOS_LLM_KERNEL`、`~/aos-home` 的根與 llm kernel 沒有 `CLAUDE_CONFIG_DIR`），停、再起、再停也都對。家機還是舊樣子，步驟在 [03-換機「家機照做」](workflows/dev-env/03-換機.md#家機照做從舊樣子改成同一套做一次)。

**這台怎麼起樹**（細節 [03-換機「起樹、停樹」](workflows/dev-env/03-換機.md#起樹停樹)；tmux session `aos` 的 `root` 視窗試過，`llm` 視窗用不到了）：

```sh
cd ~/aos-home && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK -u AOS_KERNEL -u AOS_LLM_KERNEL aos-exec --stack .stack root   # 起（前景，一行全起）
aos-daemon-ctl -d ~/aos-home/.stack ls; aos-daemon-ctl -d ~/repo/aos/.stack ls                                           # 核對：4 列、3 列都 running
CLAUDE_CONFIG_DIR="$HOME/.claude-alt" aos-agent -t eca-aos open                                                          # 開 eca-aos 畫面（另一個視窗）
aos-daemon-ctl -d ~/aos-home/.stack shutdown                                                                              # 停（一行全停）；pgrep -af aos-daemon 沒輸出＝停乾淨
```

只停 repo 那棵用 `aos-daemon-ctl -d ~/aos-home/.stack stop repo-aos`；對 `~/repo/aos/.stack` 下 `shutdown` 會被上面的根馬上再起來。

**今天做完的（都沒 push，WSL 的 main 比 origin 多這些）**：
- `7bf52abd1` 新範本 `proto8/templates/eca-claude-alt`（第二帳號版 eca-claude，可選，活樹沒用它）。
- `1a1de1921` `03-換機.md`：起根那行帶 `CLAUDE_CONFIG_DIR`，範本可選。
- `dfb94ecd2` `_stack` 改名 `.stack`、git 忽略、換機那套退場；`03-換機.md` 改寫成[每台怎麼設、怎麼起樹](workflows/dev-env/03-換機.md)；換機工具標退場；11-23 已刪（使用者原話見上）。
- `34446887a` progress 兩條；`27ed65ae6` 全景頁 systemd 範本路徑改 `.stack`。
- 收尾線 `wrapup-1123-am`：本條、當天紀錄、中文版 `agents.md` 跟上、progress 兩條新的。

**定了什麼**（紀錄 [公司WSL重建與stack改名-1123](../proto8/thinking/2026-11/23/公司WSL重建與stack改名-1123.md)）：
- 「這台的llm kernel放~/aos-home/llm」。
- LiteLLM「就用我剛開的」。
- repo aos 的樹用第二帳號，「~/aos-home的這個root daemon仍然是用普通設定檔」；做法「還是用環境變數起活樹，會更靈活」。
- 「直接變成.stack，然後把它git ignore，就這樣。換機那一套就不用了。」換機工具「先留著」。
- 樹：`~/aos-home` 一棵（普通設定檔），底下掛 llm kernel 與 repo aos 那棵（那一列帶 `CLAUDE_CONFIG_DIR` 與 `AOS_LLM_KERNEL`）；家機也要改成同一套。公司這台線 `two-trees-1123` 做完。

**還開著的**：
- 真模型與 alt 帳號都還沒走過一輪（progress `company-wsl-1123-verify`）。
- `sol-high`：kits 寫 `sol-high`，範本 11-21 起是 `sol` 加 reasoning_effort（progress `sol-high-pack`）。
- `02-模型端點.md`、`01-跨機與外部工具.md` 寫公司用 pinned 那套；今天用根那套，長期怎樣他沒說，**先不改**。
- `install.py` 結尾印的下一步還叫人抄進 `~/aos-home`；這台的使用者專區 `~/.aos/user/` 11-23 建好了（eca-aos 派的子 agent 跑 `aos-user init`；真專區還沒收發過信，tick 的 timer 沒裝、全景頁沒在跑，剩項在 progress `aos-user-home`）。
- `wf/user/待答-1122.md` 第 1、2 題（換機、`_stack` 帶哪些檔）已不適用；那是他的地盤，沒改。
- Windows 那份 clone 的 `wf/HANDOFF.md` 有一段沒交的舊修改（11-20 artifact 備註，早在 `33b0e59b9` 交過）。push 後那份 pull 會撞，要他自己跑 `git checkout -- wf/HANDOFF.md`。

**家機 pull 之後要做的**（照貼；細節在 03-換機「從舊名 `_stack` 改過來」）：
```sh
aos-daemon-ctl -d ~/repo/aos/_stack shutdown
mv ~/repo/aos/_stack ~/repo/aos/.stack
sed -i.bak-1123b 's#repo/aos/_stack#repo/aos/.stack#' ~/.zshrc
cd ~/repo/aos && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK aos-exec --stack .stack wf/tree/root
```
全景頁若是 systemd 起的，`~/.config/systemd/user/aos-frontend.service` 裡的 `_stack` 也要改，再重啟。

**下一個 session 從哪接**：
1. 他會細說「把stack一起隨機器搬遷，不是一個好主意」那塊（「這塊之後我會細說」）。
2. 早上「先處理這個，然後我們再來」後面要做的事，他還沒說。
3. 下班前（五點）問他要不要 push。

**坑**：
- 開畫面的殼要帶跟根一樣的 `CLAUDE_CONFIG_DIR`；`env.json` 不記這個變數。
- 不要在 repo 跑 `git stash`、`reset --hard`、`checkout -- .`、`clean -fdx`（`.stack` 被忽略，會被倒回或刪光）。
- 中文檔名 claim 給真路徑。
