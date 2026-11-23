# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-23 下午 14:50（公司機）——eca-aos 接手當頂層；wf/org 工作室定案、三個位子真的掛上了；使用者專區可用

**寫這條的是 `eca-aos`**（樹裡的頂層 eca，使用者在它的畫面上直接對話）。細節全在它的筆記 [`wf/ws/eca-aos/notes.md`](ws/eca-aos/notes.md)（今天每一段的原話、信名、雜湊）；compact 後先讀那份，再回來看這條。

**使用者換 compact 前的話（逐字）**：「你這邊我想compact」。

**授權（11-23 當場）**
- **push 還沒給**：早上他說「我今天五點下班，下班前再統一push」。本地 main 比 origin 多 11 個以上 commit，五點前問他，要他本人說才推。
- 刪檔：只給過滾輪調查留下的那幾個痕跡（已刪）。
- 派工：普通 opus、簡單與雜活 sonnet、規劃 fable；寫程式與重要的施工一律 Claude、蒐集雜活給 fsm gpt（這台掛不起來前由 sonnet 補位）。
- `eca_main`（根 daemon 上使用者的中心 agent）派來的普通工作算他的授權；push、刪檔不算。
- 使用者專區的回信用 `aos-user verify` 驗過才算（今天第一次整條走通）。
- 掛位子：他說「這麼多的需求，可以試試看」，所以掛了三隻。再掛新的、收掉、重啟 repo 這一列，照舊先問。

**這台現況**
- 樹：根 `~/aos-home/.stack`，表上 `_clock`、`_sweeper`、`llm`、`repo-aos`、`eca_main`、`mine_arena`、`guanyu`、`mine_paper`（後四個是使用者或 eca_main 掛的，不是我的，不碰）。repo 這棵 `~/repo/aos/.stack`：`_clock`、`_sweeper`、`eca-aos`、`eca-aos-kb`、`eca-aos-templates`、`eca-aos-core`。
- 起停指令沒變（細節 [03-換機「起樹、停樹」](workflows/dev-env/03-換機.md#起樹停樹)）：
  ```sh
  cd ~/aos-home && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK -u AOS_KERNEL -u AOS_LLM_KERNEL aos-exec --stack .stack root   # 起（前景，一行全起）
  CLAUDE_CONFIG_DIR="$HOME/.claude-alt" aos-agent -t eca-aos open                                                          # 開 eca-aos 畫面
  aos-daemon-ctl -d ~/aos-home/.stack shutdown                                                                              # 停（一行全停）
  ```
- 使用者專區 `~/.aos/user/` 建好、可用；全景頁沒起，他用 `aos-user ls`／`answer` 回。tick 的 timer 他答不裝。
- 127.0.0.1:4000 我看的時候沒在聽（別棵樹的 gpt 腦卻有在答話，實際端點沒查清，core 位子正在查）。

**組織（[wf/org](org/README.md)，使用者 11-23 答七題定案）**
- 負責人 `eca-aos`；位子 kb（`proto8/knowledge`）、templates（`proto8/templates`）、core（`proto8/py`、`cpp`）、frontend（`proto8/frontend`，大修開工才掛）；打雜工是 sol 的 agent-fsm，這台還掛不起來。
- 我只親手寫三樣：活狀態（progress、HANDOFF、筆記）、抄他的話進規矩、`wf/org`；其餘照派。位子在自己範圍內先交後報。
- **三個位子是真的掛著的 eca**（`subagent` 工具掛的，定義直接指範本 `eca-claude`，各自 stack 有 `system.txt` 與 `notes_path`）：`subagent ls` 看、`mailbox_send {to: 名}` 派工、它們的 DONE 進我的信箱。每隻都吃第二帳號的額度。沒開 auto_restart。

**還在跑、回來要收的**
1. `eca-aos-templates`：`daemon-root/README.md` 加指到 `daemon-sub` 的一句、兩份起手範本抄本跟上（工作樹已有它改的三份 README，等它自己交件、回 DONE）。之後要轉給它：`templates/kits/gather/tools.json`（review 那份相同）description 寫「cannot lift its own limits」說得比事實強。
2. `eca-aos-core`：gpt 腦把選填參數當必填那件——先用最小的真模型呼叫實證 strict，成立才在 llm_http 補 `"strict": false` 並交件；**不跑 `install.py`**，它回信後我要問使用者什麼時候裝（裝＝換掉活樹的 `lib/`）。
3. 拿掉 `wf/tree/root` 的 `_clock`（使用者「可以拿，不用馬上重啟」）：**定義與文件已交**（`wf/tree/root/*`、`wf/tree/README.md`、03-換機）。**活樹上那一列還在跑**：daemon 只在起來時讀一次 `daemon.json`，表上已有的列重起也會接回，要另外下 `aos-daemon-ctl -d ~/repo/aos/.stack rm _clock` 才會走（不用重起；這是對活樹下的指令，問過使用者才做）。暫存樹留在 `~/.aos/scratch/tree-noclock-1123/`。還沒跟上的文件（把 `wf/tree/root` 叫「根定義」或寫家機單獨起）：aos-teams/06 第 8、28 行、`wf/public/活樹旁邊.md` 第 5 行、`aos-teams.md` 第 62 行。
4. `mine_arena/main` 的第二封信（六題「請 aos 考慮」）：事實部分已回（PROGRESS），**方向部分等使用者來談**，談完回它一封 DONE。使用者說過會親自找我談「上層怎麼約束下屬」與「agent 之間的資源分配」。

**今天交了什麼**（都沒 push；每個的來龍去脈在筆記）：範本 `cli.json` 加 `"tui": "fullscreen"`（滾輪）；`wf/org` 與舊文件對齊；`aos-user` 的 send 自建信箱、逐題留言、公告；知識庫與 `wf/public` 跟上；新範本 `daemon-sub`；kb 位子自己交的 `74bedc157`。

**還開著的**（progress：`org-1123`、`aos-user-home`、`findings-1123`、`company-wsl-1123-verify`、`sol-high-pack`）
- 今天查出、還沒修的 aos 問題記在 progress `findings-1123`。
- 使用者早上說要細說「把stack一起隨機器搬遷，不是一個好主意」那塊，還沒說。
- `wf/user/README.md` 有一句「不把這裡當信箱用」跟他 11-23「沒有~/.aos/user，那就放wf/user」相反；那是他的地盤，沒動。

**家機 pull 之後要做的**
1. 先停舊樹、改名（還叫 `_stack` 的話）：`aos-daemon-ctl -d ~/repo/aos/_stack shutdown`；`mv ~/repo/aos/_stack ~/repo/aos/.stack`；殼設定檔裡的 `repo/aos/_stack` 改成 `repo/aos/.stack`。
2. **不要再單獨起 `wf/tree/root`**（11-23 起它不帶鐘，單獨起整棵樹沒有時鐘）：照 [03-換機「家機照做」](workflows/dev-env/03-換機.md#家機照做從舊樣子改成同一套做一次)改成 `~/aos-home` 那一套（根底下掛 llm kernel 與 repo 這棵）再起。 掛好之後下一次 `aos-daemon-ctl -d ~/repo/aos/.stack rm _clock`（舊表上的 `_clock` 列不會自己消失）。
3. 全景頁若是 systemd 起的，unit 裡的 `_stack` 也要改。

**坑**
- 開畫面的殼要帶跟根一樣的 `CLAUDE_CONFIG_DIR`；不帶就是主帳號。
- 不要在 repo 跑 `git stash`、`reset --hard`、`checkout -- .`、`clean -fdx`（`.stack` 被忽略，會被倒回或刪光）。
- 位子與子 agent 同時在同一個工作樹改檔：交件前 `git status` 看到別人範圍的改動是正常的，`--files` 只點自己的。
- 樹上有兩隻叫 `main` 的（`mine_arena`、`mine_paper`），通知只寫「from main」，看信的 sender 路徑分。
- 派 Claude 子 agent 查別棵樹的事時，任務書要寫死：別棵樹的 stack、信箱、`/proc/*/environ` 不讀（今天有一隻讀了）。
