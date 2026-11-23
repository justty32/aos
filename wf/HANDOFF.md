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

**授權（11-23 當場）**：派工照「普通工作交給opus，簡單工作或雜活交給sonnet」「agent做事前都要讀過wf/規矩，簡單工作或雜活除外」「agent可以再派子agent，模型隨意」。**push 還沒給**：他說「我今天五點下班，下班前再統一push」，要他本人再說一次才推。刪檔沒給（換機工具他說「先留著」）。頂層是 Windows 上的 Claude Code，不在 aos 樹裡；實際工作在 WSL 的 `~/repo/aos`，Windows 那份 clone 不動。

**這台現況**：
- llm kernel：定義 `~/aos-home/llm`、stack `~/aos-home/.llm-stack`，端點指 `localhost:4000/v1`（多加了一包 `sol-high`）。用普通 Claude 設定檔。
- 根：daemon `~/repo/aos/.stack`，根定義 `wf/tree/root`，帶 `CLAUDE_CONFIG_DIR="$HOME/.claude-alt"`（第二個帳號，他已登入）。底下掛了 `eca-aos`（範本 `eca-claude`，筆記 `wf/ws/eca-aos/notes.md`），**從沒開過畫面、沒問過話**。
- 兩台都 shutdown 了，沒有 aos 行程。登入殼是 zsh（`~/.zshrc`、`~/.bashrc` 都加了 aos 段，備份 `.bak-1123`）。
- LiteLLM 用他自己開的 `~/repo/llm_proxy` 根那套（1.87.5、不用 key），不是 pinned；**4000 埠一直沒在聽，真模型沒驗過**。

**要改成兩棵樹**（使用者換 session 前又說，逐字）：「應該說，我預期會有兩棵樹，一棵是這台的，在~/aos-home，底下掛著llm kernel。另一棵是repo aos的，啟動的時候會是CLAUDE_CONFIG_DIR=alt AOS_LLM_KERNEL=...」也就是 `~/aos-home` 要是一棵真的樹（有根 daemon，llm kernel 掛在它底下），不是現在這樣 llm kernel 自己一台。

**這台怎麼起樹**：看 [03-換機](workflows/dev-env/03-換機.md)；`~/aos-home` 正由線 `two-trees-1123` 改成一棵樹（根底下掛 llm kernel），做完那條線會回來補這段。開 `eca-aos` 畫面的殼要帶跟根一樣的 `CLAUDE_CONFIG_DIR`。

**今天做完的（都沒 push，WSL 的 main 比 origin 多這些）**：
- `7bf52abd1` 新範本 `proto8/templates/eca-claude-alt`（第二帳號版 eca-claude，可選，活樹沒用它）。
- `1a1de1921` `03-換機.md`：起根那行帶 `CLAUDE_CONFIG_DIR`，範本可選。
- `dfb94ecd2` `_stack` 改名 `.stack`、git 忽略、換機那套退場；`03-換機.md` 改寫成[每台怎麼設、怎麼起樹](workflows/dev-env/03-換機.md)；換機工具標退場、沒刪。
- `34446887a` progress 兩條；`27ed65ae6` 全景頁 systemd 範本路徑改 `.stack`。
- 收尾線 `wrapup-1123-am`：本條、當天紀錄、中文版 `agents.md` 跟上、progress 兩條新的。

**定了什麼**（紀錄 [公司WSL重建與stack改名-1123](../proto8/thinking/2026-11/23/公司WSL重建與stack改名-1123.md)）：
- 「這台的llm kernel放~/aos-home/llm」。
- LiteLLM「就用我剛開的」。
- repo aos 的樹用第二帳號，「~/aos-home的這個root daemon仍然是用普通設定檔」；做法「還是用環境變數起活樹，會更靈活」。
- 「直接變成.stack，然後把它git ignore，就這樣。換機那一套就不用了。」換機工具「先留著」。
- 兩棵樹：`~/aos-home` 一棵（底下掛 llm kernel），repo aos 一棵（起的時候帶 `CLAUDE_CONFIG_DIR` 與 `AOS_LLM_KERNEL`）。線 `two-trees-1123` 在做。

**還開著的**：
- 真模型與 alt 帳號都還沒走過一輪（progress `company-wsl-1123-verify`）。
- `sol-high`：kits 寫 `sol-high`，範本 11-21 起是 `sol` 加 reasoning_effort（progress `sol-high-pack`）。
- `02-模型端點.md`、`01-跨機與外部工具.md` 寫公司用 pinned 那套；今天用根那套，長期怎樣他沒說，**先不改**。
- `install.py` 結尾印的下一步還叫人抄進 `~/aos-home`；這台 `aos-user init` 沒查；`commit_queue.py` 的 `--stack-commit` 配套沒收。
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
