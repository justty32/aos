# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-25 17:0x（公司）——proto9：小庫＋信箱、daemon、aos-exec 都驗過交件；16:50 推過一次

**寫這條的是公司 repo-aos 樹的 `eca-aos`**（這個畫面用主帳號 `~/.claude`、模型 Fable；答信的 loop 走 `~/.claude-alt`）。細節在 [`wf/ws/eca-aos/notes.md`](ws/eca-aos/notes.md) 最後幾節（14:0x 起）。上一條（11-25 16:2x）在 git 歷史 `de28c59932`。

**接手先讀**：這條 → 筆記「2026-11-25 16:2x：compact 完，daemon 回來了」那節到底 → [proto9/README](../proto9/README.md)、[介面草稿](../proto9/docs/01-aos-proc介面草稿.md)（【定】【擬】【開】三種記號；第 12 節是還沒定的）。使用者原話全在 [9p-proc-1125](../proto8/thinking/2026-11/25/9p-proc-1125.md)（第 10～29 段是今天下午）。

**授權（11-25 當場）**
- **push 已經用掉**：使用者 16:50「好了，看起來都沒事了，現在就push」→ 推到 `243b6a9c5`。那之後的 commit 都沒推；**要再推得他再說**（16:55 的鐘來過，沒再推）。
- 子 agent：proto9 的施工用 Claude Code 的 Agent 工具派 opus（背景），不 commit，回來 eca-aos 自己清 build 重編、跑測試、查殘留再交。
- repo 根那個沒追蹤的檔 `ls`（內容「1」，來源不明）還在，沒問。

**proto9 現在有什麼**（都驗過、交件了）
- `proto9/docs/01`（介面草稿）、`02`（可以抄的現成做法）、`pages/aos-proc.html`（artifact 原始檔，<https://claude.ai/artifact/CaD7a7bwGkh2WxLTRHfMVN>，使用者說通勤時看；頁面還寫 `persist`，改版時一起換成 `persists`）。
- `proto9/cpp/aos-procfs/`：小庫，含 `failed`、`AOS_NAME_PID`、Maildir 式 `mailbox/`（proto8 的 `aos-post send` 原樣寄得進來）。測試 `tests/run.py` 40、`tests/mail.py` 36。
- `proto9/cpp/aos-daemon/`：最小的 daemon，64 條。**已知一條會偶發失敗**：register 組「rm ext」——測試寫完 `procs_ctl` 沒等做完就看表（寫入回來＝收到、不是做完）；單獨跑都過。下一批修，順便查別的測試有沒有同樣的寫法。
- `proto9/cpp/aos-exec/`：從 proto8 抄進來瘦身（拿掉 `AOS_STACK`、inst 單子；其餘照舊；不連 proto8），75 條；`proto9/cpp/third_party/` 是它用的 json 標頭。README 有一張「還能砍的」表（最大：指示詞約 1640 行，其中 `$ref` 指 `.md` 985 行）——**等使用者挑要砍什麼**（他說「可能要大改」）。

**今天下午使用者定的**（全文在草稿與 thinking）
- 「落檔...不算，我們直接起proto9」；基礎用 C++；每隻 proc 用 FUSE 把自己的目錄掛出來。
- phase 五個值；掛載點用 `%` 接名字路；`add` 的可執行檔那種留著；proto9 不給 `AOS_STACK`；proc 的入口先只收可執行檔與 argv 陣列；aos-exec 抄進 proto9 瘦身。
- 外來登記的 proc 在自己的 `settings` 宣告服從程度、要擋冒名；`add` 不能只收絕對路徑（會害搬家）。
- `persist` 改名 `persists`（草稿已改；**程式還沒改**）。
- agent 的身體：不搬 aos-loop／aos-fsm 那一套，就是一支簡單的程式、擺出介面；agent 專用的檔案布局與格式是另一份介面，他之後規劃。
- 自動重起：root daemon 掛 systemd，底下的另外設定（照現在的 auto restart）。
- json 版：以程式裡的 struct 定義為主，衍生 json，再衍生純文字。

**下一批**（都還沒派；小庫與 daemon 是同一批檔，不能同時兩隻改）
1. daemon 的 `add` 改交給 proto9 的 aos-exec（資料夾、JSON、可執行檔）；相對路徑從 daemon 自己的目錄算；daemon 有自己的 `persists`、把表存進去；`auto_restart`；root 重起後照表把還活著的認回來。
2. `settings` 的 `aos_obey`（列 daemon 可以對它用的字；【擬】）；登記時對它自己 `status` 的 `aos_name` 擋冒名。
3. 程式裡 `persist` → `persists`（含 `aos_persists`、`名字.persists`，【擬】）。
4. 修 daemon 測試的競態（上面那條）。
5. 欄位表：每個檔一個 struct、欄位只宣告一次，json 與純文字都從它產生（純文字＝json 攤平，巢狀用 `.` 接）。
6. 之後：plumber 式的 `msg`、socket 上一行一則加回條。
- 1～4 使用者給了方向、細節是我擬的；他沒逐條點頭，派之前在回覆裡再講一次要做什麼。

**還開著的**
- **上網的幫手**（不在 aos 體系）：`tmux -L webref`，`~/.aos/scratch/web-ref-1125/launch.sh` 起的 Claude Code（`~/.claude-alt`、sonnet、dontAsk，放行上網、讀寫、Skill、Artifact）。送話：用 `proto8/lib` 的 `aos.agentlib.cli_a2a.wire` 包信封，寫 `/run/user/1000/cc-socks/<它的 PID>.sock`（PID：`pgrep -f "claude --model sonnet --permission-mode dontAsk"`）。使用者說先留著。改版 artifact：改 repo 的 html → 抄到 `~/.aos/scratch/web-ref-1125/artifact/aos-proc.html` → 請它對同一個檔再發佈。要收：`tmux -L webref kill-server`。
- core：閒置輪詢做到第 3 刀就停（第 4～6 刀不做，已寄信）；1125f；compact 第 3 刀。工作樹裡 `proto8/cpp/aos-idle/` 等改動是它的。kb、templates 空。

**等使用者（不催）**：看 artifact 哪裡要改；aos-exec 要砍什麼；agent 檔案布局那份介面（他規劃）；草稿第 12 節還沒定的（token 檔、`persists` 怎麼擺、sleep／wake、換 Linux 帳號）；小庫與 daemon 挑的保守做法（草稿第 11 節、各自 README）。
