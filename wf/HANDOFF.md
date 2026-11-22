# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-22 傍晚（家機，使用者在外面玩、用 Remote Control）——搬家已完成：eca-aos 住 `~/repo/aos/_stack`；小工作室照推薦施工的四件都做完了

**使用者 compact 前的話（逐字）**：「我人還在外面玩，總之先按推薦做」「你這邊抓個斷點，我幫你compact」。

**我是誰／在哪**：`eca-aos`，stack `~/repo/aos/_stack/procs/eca-aos`（14:12 從 `~/aos-home/.stack` 搬來），daemon `~/repo/aos/_stack`，根定義 `wf/tree/root/`；llm kernel 獨立跑（定義 `~/aos-home/llm`、stack `~/aos-home/.llm-stack`，沒有 `LITELLM_KEY`，真模型的 agent-fsm 會失敗）；舊樹在 `~/aos-home.old-1122/`（退路，不刪、不起）。`~/.zshrc` 已改（備份 `~/.zshrc.bak-1122`）。我的 `tools.json` 的 `$override` 已改成 `$env AOS_HOME`；程式也修了（`89caf5117`，已 install）。底下三個 subagent（3/4）：`eca-aos-templates`、`eca-aos-kb`、`aos-eca-frontend`，系統文字都加了「讀自己的 notes.md」一段（frontend 新設了職責段：管 `proto8/frontend/`、職責未正式定）；`notes_path` 已寫在三格 stack（內容 `wf/ws/eca-aos/<名>/notes.md`，相對 AOS_WS）。

**照推薦施工的四件（都已完成，都沒 push）**：
- `eca-aos-templates`：線 `eca-aos-templates-1122-notes-hook-a`，已完成（`774fec243`）。範本 `templates/eca-claude/compact_hook` 壓完叫 subagent 先讀自己的筆記（stack 的 notes_path），ann 抄本一起改了。
- `eca-aos-kb`：線 `eca-aos-kb-1122-feedback-apply`，已完成（`65bb2891f`）。body.md 換新寫法，新增 `eca_reading.md`、`troubleshooting.md`。它要加的規矩句已由線 `wf-rule-kb-troubleshoot-1122` 加進規矩卡「回報怎麼寫」第 4 條（`919104d50`）。
- `aos-eca-frontend`：線 `aos-eca-frontend-1122-parents-b`，已完成（`f3e2581d7`）。全景頁上層只信 subagent 紀錄加 aide.json，拿掉設定檔 parents／名字前綴／parent_rules 三種猜法，孤兒平鋪最上層，拿掉寫死的 repo-aos 與 `~/aos-home/ws/tools`。活的全景頁（pid 9460）還是舊程式，見下面「使用者回家要做的」第 1 項。
- Claude Code 背景 subagent 線 `notes-reload-1122`：已完成（`e5903dc7a`）。`wf/tools/compact_reload.sh` 在 subagent 裡不貼頂層 HANDOFF，改指向自己的 notes_path；`wf/ws/README.md` 地盤規矩第 4 條已補。

**使用者照推薦定的（11 題）**：kb 1c、2c＋2a、3c、4c；frontend 乙現在做丙以後接、孤兒平鋪 a、aide.json 先留 a；compact 提醒 A、只印路徑、A＋b、notes_path 由上層寫 a。沒按推薦做的：公司體制 7 題（`proto8/thinking/2026-11/22/公司體制-1122/03-要問的.md`，第 1 題是使用者的想法、沒推薦）、筆記調查 5 題（`筆記調查-1122/`，多半已被上面蓋過）。

**今天做完的（都沒 push）**：工作區與 `_stack` 全線（線 1～7、9；規劃 `proto8/thinking/2026-11/22/工作區與stack-1122/`；搬家腳本 `wf/tools/home-move-1122/`；換機說明書 `wf/workflows/dev-env/03-換機.md`；換機工具 `wf/tools/stack-commit`）；progress 整理（42→32 條，`$ref` 搬 md 到 `wf/progress/`，`a540a0db7`、`b2013cc84`；`workspace-stack-alloc` 只剩線 8 公司那台＋題 4）；輸入成本調查與 A 實驗（無效，`907ddecc9`、`22501d7af`）；eca 範本瘦身、知識庫日期註記（上午）。Artifact 四頁由 aos 體系外的 tmux session `artifacts` 發佈（kernel 攔截、權限零件、小工作室筆記、公司體制）。

**使用者回家要做的**：1. 關掉／重開停在舊 `~/aos-home` 的終端機分頁，用新的 `AOS_DAEMON` 重起 `aos-frontend serve`（`aos-frontend.service` 已改指 `_stack`；現在活的全景頁 pid 9460 還是舊程式，重開後才會用上 `f3e2581d7` 的新版）；2. 要真模型時設 `LITELLM_KEY`（`aos-daemon-ctl -d ~/aos-home/.llm-stack shutdown` 後從有金鑰的殼 `home-move start-llm`）；3. 第一次換機 commit（`stack-commit leave`，`_stack` 以外有沒交的檔要加 `--leave-dirty`）與要不要 push（換機 commit 含四隻 eca 的對話紀錄與信）。

**授權（11-22 當場）**：「可以開工，去吧也可以動活樹」「zshrc可以動」「先按推薦做」。push 沒給。刪檔沒給。`install.py` 今天跑過三次（都先講一聲再跑）。

**一般 tmux 裡還開著的兩個 aos 體系外 claude**：`artifacts`（cwd `~/.aos/scratch/artifacts-1122/`）、`home-move-run`（搬家執行員，已做完、閒著）。用 `env -i PATH=/usr/bin tmux …` 操作。

**坑**：
- Agent 工具派的背景 subagent 叫不停、它起的行程不會自己收；子 agent 用不了 aos 信箱，回報在它最後一則訊息。
- 不要在 repo 跑 `git stash`、`reset --hard`、`checkout -- .`、`clean -fdx`（`_stack` 被忽略，會被倒回或刪光）。
- Remote Control 裡 `/mcp` 要寫 `/mcp reconnect all`。我不能替自己下斜線指令，要使用者打。
- 一句話兩種讀法先標出讀法；語音輸入錯字照錄附讀法；沒查過的講明是推測。
- 乾淨複本先跑 `install.py`；中文檔名 claim 給真路徑；`ls` 是 `eza`，背景指令會卡。
