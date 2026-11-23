# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-23 晚 23:00 前後（家機）——家機的 main 收工：今晚答完四題、三分準備在家機做好並 push

**寫這條的是家機 repo-aos 樹裡的 `main`**（eca-claude、opus；家機沒有 eca-aos 與三個位子，那些在公司那台）。公司那台的 eca-aos 明早讀到這條時，**先讀這條，再讀自己的筆記 [`wf/ws/eca-aos/notes.md`](ws/eca-aos/notes.md)**（上一條 HANDOFF 在 git 歷史 `90994593a`）。

**使用者換 compact 前的話（逐字）**：「沒了，先這樣，你弄好後我compact」。

**授權（11-23 晚當場）**
- **push**：使用者「2.好」→ 推了一次 `origin main`（到 `90994593a`）。之後的 commit（含這條 HANDOFF）沒推，要他再說。
- 派工照舊：普通 opus、雜活 sonnet、規劃 fable；寫程式與重要施工 Claude。
- `install.py`：家機今晚由代班跑過一次（arbexec 那隻，22:xx），`lib/` 等於當時 HEAD 的 `py/`。

**今晚使用者定的（都已進 progress，原話在各條）**
1. **templates 三分的三題**：「那三題都按照推薦」「Hmmm，可以」＝ ① a 13 列只改路徑 ② a 別專案 6 份定義由切換腳本直接改字 ③ b 他開樹外 Claude Code 視窗代打、每步等他點頭。
2. **三分準備改成今晚家機先做**（「好」）：成果在規劃夾 [`06-switch/`](../proto8/thinking/2026-11/23/org範本與templates分層-1123/06-switch/README.md)（`69509c2fc` 補丁材料 split.py＋moves.tsv＋H1～H6＋測試腳本；`e6241c047` stack_paths.py＋rehearsal.md）。全套 83 夾 3,362 支新紅 0、預演交件 DONE DryRun、暫存樹改表與退回都過。06-switch 的四件「1.可以」：多改的 `docs/zh/*.html` 與 `wf/ws` 提案留著；CONVENTION P-27 等句子切完再派 opus 逐句看；`--rm` 由樹外視窗打（被擋就他本人打）；不寫 switch.sh。
3. **mine_arena 六題**：隔離「甲，先只防失誤」；六題排法「可以」（progress `mine-arena-dir-1123`，內含要寄給 mine_arena/main 的 DONE 大意，**明早 eca-aos 寄**）。⑤ 已做（知識庫 `aos/rules.md`、`kits.md`，`cf17b55e2`）。
4. **arbitrary_exec**：「可以」→ fork、screen_linger 改 false，agent_def、measure、review_round、promote 改 true（`d20cc7d34`），C-22 補「只算直接執行、不算經由寫檔」（`19d8ef838`）。剩 `templates/reviewer/tools.json` 第 1 行等三分切完。
5. **archive/ 失效連結**：「先去把連結拿掉」「好」「可以」→ 拿掉了（`b51f8745c`、`36f8984a4`、`b1cf2f60c`）。
6. **stack 跟著機器搬**：「只是我初步的想法，先不管」——不追、不列題。

**11-24 早上公司的順序**
1. 起樹前 `git pull`（拿到 `90994593a`；這條 HANDOFF 若沒再推就拿不到，內容 progress 都有）。
2. eca-aos 讀這條與 progress `org-template-1123`、`mine-arena-dir-1123`。
3. 寄 mine_arena/main 的 DONE。
4. 照 `06-switch/README.md`：在新 main 上重跑 split.py、`git am` H1～H6（**H5 也改 index_gen_desc.json，`e6241c047` 又改過，起衝突就 `-3` 或手合**）、重驗 → 使用者說停 → 他開樹外視窗照 06e 切換（每步他本人授權）→ push 要他說。
5. 切完：reviewer 那一行、CONVENTION 句子（帶給使用者看）、mine_arena ①③②。

**家機還開著的**
- **根 daemon 的 `AOS_LLM_KERNEL` 是錯值**（`.stack/proc/llm` 少 s；根 20:25 起時殼裡是舊值，`~/.zshrc` 20:31 才改對）：整棵家機樹的 agent-fsm 問不到腦。使用者「明天再說。」——下次在家機問他何時從新殼重起根，重起後回 repo-vc 的 main DONE（progress `home-llm-env-1123`）。
- 家機三分：等公司切完 push 後，照 06f「家機照做」停樹、pull、`stack_paths.py`（家機的 repo-aos/main 直接掛 templates/eca-claude；家機沒有別專案定義）。
- 家機根上現在有：`_clock`、`_sweeper`、`llm`、`repo-aos`、`mod_skyrim`、`repo-vc`、`narr-amber`（後三棵是使用者的，不碰）。

**坑**
- 家機的 `ls` 是 `eza --git`，接管線會卡，用 `/usr/bin/ls`。
- commit-request：`wf/progress.json`、日索引不能列 `--files`，用 `progress_upsert`／`day_upsert` op；zsh 不拆變數裡的空白，檔名逐個列；新夾裡沒第一行的檔（如 .patch）要在 `index_gen_desc.json` 補說明。
- 不要在 repo 跑 `git stash`、`reset --hard`、`checkout -- .`、`clean -fdx`。
- 派 Claude 子 agent 查別棵樹的事時，任務書寫死：別棵樹的 stack、信箱、`/proc/*/environ` 不讀。
