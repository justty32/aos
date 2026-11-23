# 公司 WSL 重建 aos、repo aos 的樹改用第二個 Claude 帳號、`_stack` 改名 `.stack` 不跟機器搬（11-23 上午定）

← [這天的索引](README.md)｜每台怎麼設、怎麼起樹 [03-換機](../../../../wf/workflows/dev-env/03-換機.md)｜前一天的規劃 [工作區與stack-1122](../22/工作區與stack-1122/README.md)｜進度 `wf/progress.json` 的 `workspace-stack-alloc`、`company-wsl-1123-verify`、`sol-high-pack`

## 使用者原話（逐字，照時間）

1. 「早安，這是在公司windows電腦。請先通讀wf/規矩，看看狀況。事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。先git pull吧。」
2. 「是這樣的，我想要重建這台的WSL的aos-home，之後用aos體系來跑。舊的aos-home就可以刪掉了。先處理這個，然後我們再來」（後半句沒打完）
3. 「這台的llm kernel放~/aos-home/llm」
4. 「litellm proxy我開好了」「litellm proxy感覺有點怪怪的...」「啊？pinned是啥」「就用我剛開的」
5. 「我想掛。但是想用另一個帳號掛。就是用CLAUDE_CODE_CONFIG=xxx/alt-... 這個另一個設定」（實際的變數是 `CLAUDE_CONFIG_DIR`）→「只這隻 eca」→「啊，應該說repo aos的都用」→「我已經登入好了」→「喔不過~/aos-home的這個root daemon仍然是用普通設定檔」
6. 「喔我覺得很簡單啦，就是proto8/template中提供一個eca-claude-alt就好」「後續掛agent都用那個」「不用想太多」「不過你這個方法也不錯」→ 問要不要把活樹換成新範本，先按「換過去」，又立刻改口：「啊不，其實還是用環境變數起活樹，會更靈活。」
7. 「Hmmm，我要把_stack改為.stack，因為我發現，把stack一起隨機器搬遷，不是一個好主意。這塊之後我會細說。」「就是說，直接變成.stack，然後把它git ignore，就這樣。換機那一套就不用了。」問退場的換機工具要不要刪：「先留著」
8. 「把樹停掉，我自己開。然後你這邊收尾，我要換session了。順便告訴我怎麼起樹」
9. 「應該說，我預期會有兩棵樹，一棵是這台的，在~/aos-home，底下掛著llm kernel。另一棵是repo aos的，啟動的時候會是CLAUDE_CONFIG_DIR=alt AOS_LLM_KERNEL=...」

## 定了什麼

- **這台的 llm kernel 放 `~/aos-home/llm`**（第 3 句），stack `~/aos-home/.llm-stack`。11-22 線 8 的第 4 題就此答了。
- **LiteLLM 用他自己開的那套**（第 4 句「就用我剛開的」）：`~/repo/llm_proxy` 根那套（uv run 1.87.5、`litellm.yaml`、不用 key），不是 `pinned_1.109.1`。長期是不是都這樣，他沒說。
- **repo aos 的樹用第二個 Claude 帳號**（第 5 句）：`CLAUDE_CONFIG_DIR="$HOME/.claude-alt"`。`~/aos-home` 的 llm kernel 照用普通設定檔。
- **做法：起根那行帶環境變數**（第 6 句最後「還是用環境變數起活樹，會更靈活」）。新範本 `proto8/templates/eca-claude-alt` 留著，可選，活樹不換。
- **stack 改名 `.stack`、被 git 忽略、每台各有各的、不跟機器搬；換機那一套不用了**（第 7 句）。換機工具 `wf/tools/stack-commit`、`wf/tools/home-move-1122/` 先留著、不刪。為什麼不搬，他說「之後我會細說」。
- **兩棵樹**（第 9 句）：`~/aos-home` 是這台的一棵樹，有根 daemon，llm kernel 掛在它底下（今天做成的是 llm kernel 自己一台）；repo aos 是另一棵，起的時候帶 `CLAUDE_CONFIG_DIR` 與 `AOS_LLM_KERNEL`。由線 `two-trees-1123` 改 `~/aos-home` 與 `03-換機.md`。
- **授權**：派工普通 opus、雜活 sonnet、子 agent 模型隨意（第 1 句）；push 要等「下班前再統一push」那時他本人再說；刪檔沒給。

## 各線結論與 commit

- **pull**：Windows 與 WSL 兩份 clone 都到 `75d3020a3`。WSL 原本就沒有 `~/aos-home`（第 2 句說的舊的不用刪），`~/.bashrc` 也沒有 aos 的行。
- **線 `ws-stack-1123-wsl`（opus）**：跑 `install.py`；llm kernel 從範本抄到 `~/aos-home/llm`，端點指 `localhost:4000/v1`，多加一包端點 `sol-high`（配給包 kits 寫 `sol-high`，範本 11-21 起改成 `sol` 加 reasoning_effort，兩邊對不上，repo 沒改）；aos 殼設定段加進 `~/.bashrc`（備份 `.bak-1123`）；tmux session `aos` 兩個視窗 `llm`、`root`；用假端點驗過會回。這台的登入殼是 zsh。
- **線 `eca-alt-1123`（opus）**：`~/.zshrc` 加 aos 段（備份 `.bak-1123`）。暫存樹用假 claude 驗出三件事：根的殼帶 `CLAUDE_CONFIG_DIR`，底下每隻答話都用它；**開畫面用的是開畫面那個殼的值**，不一樣就會用主帳號、清掉 `session.txt`、對話斷掉；`env.json` 不記這個變數。活樹：根帶 `CLAUDE_CONFIG_DIR="$HOME/.claude-alt"` 重起，掛 `eca-aos`（範本 `eca-claude`，`-w . -s <stack>/procs/eca-aos`），stack 裡寫了 `notes_path`（`wf/ws/eca-aos/notes.md`）與 `system.txt`（範本原文加一段叫它記筆記；頂層也走筆記路徑是線替使用者選的，家機頂層是讀 HANDOFF）。新範本 `eca-claude-alt`（整夾抄 eca-claude，加頂層與 `screen/` 兩份 `.env`，加同步測試）：`7bf52abd1`。
- **雜活線 `doc-alt-env-1123`（sonnet）**：`03-換機.md` 那句改成「起根那行帶環境變數，範本可選」：`1a1de1921`。
- **線 `dot-stack-1123`（opus）**：`_stack` 改名 `.stack`、`.gitignore` 加 `/.stack/`（舊的 `/_stack/` 那行留著）、`03-換機.md` 改寫成「每台怎麼設、怎麼起樹」、規矩與 kits 的路徑跟著改、換機工具檔頭標明退場（沒刪）：`dfb94ecd2`；progress 兩條：`34446887a`；全景頁 systemd 範本的路徑：`27ed65ae6`。這台的活樹已改名並重起過，`eca-aos` 不用重掛。
- **收尾**：照第 8 句把根與 llm kernel 都 shutdown 了，起樹留給他自己。

## 驗到的、沒驗到的

- 驗到：假端點會回；假 claude 下 `CLAUDE_CONFIG_DIR` 的傳法（上面三件）；改名後的活樹起得來。
- **沒驗到**：真模型端點——LiteLLM 行程在，但幾次唯讀去看，4000 埠都沒在聽；真的 claude 與 alt 帳號——`eca-aos` 從頭到尾沒開過畫面、沒問過話。
- 坑：沒設 `AOS_DAEMON` 時，aos 指令找 cwd 的 `./.stack`。

## 還開著的

- `~/aos-home` 改成一棵樹（第 9 句）：線 `two-trees-1123` 在做。
- stack 為什麼不跟機器搬、之後怎麼做：等他細說（第 7 句）。
- 第 2 句「然後我們再來」後面要做的事，他還沒說。
- `sol-high` 與範本對不上（progress `sol-high-pack`）。
- `02-模型端點.md`、`01-跨機與外部工具.md` 寫公司 WSL 用 pinned 那套，今天用的是根那套；他沒說長期怎樣，文件先不改。
- `install.py` 結尾印的下一步還叫人抄進 `~/aos-home`；這台 `aos-user init` 沒查（progress `aos-user-home`）；`commit_queue.py` 的 `--stack-commit` 配套沒收。
- 11-22 排給今天的「查 `_stack` 換台哪些檔要帶」因換機退場，不用做了。
