# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-06 下午 15:05 公司（compact 前；同一 session 接著做）

1. **授權與隊形**（11-06 使用者）：今天隨意 push；公司 Windows＋WSL，一律在 WSL 主 clone `~/repo/simple_tools/aos` 改（Windows 工作樹只 pull）。頂層只交流派隊；每隊 opus 自家 subagent 隊長＋兩隊員（codex `gpt-6.1-sol` 帶 `/goal`、WSL claude `--model claude-opus-5-5` 另一帳號＝公司帳號），隊員可無上限派子 agent（codex 普通 sol／簡單 terra；claude 普通 opus／簡單 sonnet）；**盡量派 CLI**——使用者 14:30「我現在沒在處理別的事。都用cli吧。而且我們自己的token額度也...」，Claude 子 agent 少開。**fable**：預設照舊自家 fable subagent、盡量少開；使用者說「走 wsl claude」才走 WSL（[01-公司WSL](workflows/dispatch/aos-teams/01-公司WSL.md#fable-走-wsl-claude使用者說了才走)）。**不准繞沙箱**：`codex exec resume` 沒 `-s`，帶 `-c sandbox_mode` 會被標警告，要續跑就開新 exec（[gotchas 04](workflows/common/gotchas/04-使用aos與改文件與公司Windows.md)）。WSL pts 終端的互動 claude／codex（`--dangerously-skip-permissions`，早上 8:46～9:43 開）是**使用者自己的，絕不碰**。共用 index：`git commit -- <路徑>`。建置：`flock /tmp/aos-build.lock nice -n 15 cmake --build … -j2`，同時只一個建置。有方向題用選項框問。
2. **效能上限**：使用者有在做事＝全機 CLI ≤3（有 C++ 建置 ≤2）；**使用者閒著（14:30 起）放寬到 ≤6、load 警報 8**——他回去做事時要調回 3。初步分析在 scratchpad `perf-report.md`（`C:\Users\WG-GUA~1\AppData\Local\Temp\claude\a5755c4eb10ca875\f74999ae-9c2a-4581-87e0-39959b509b43\scratchpad\perf-report.md`）：瓶頸是 CPU、每程序約 300 MiB；使用者 13:40「分不乾淨沒關係，我在公司就是一邊做我的事情，你這邊就是附帶」——上限前提＝他的工作優先。**收工時**補下午資料、寫進 [01-公司WSL](workflows/dispatch/aos-teams/01-公司WSL.md)（附原話），停兩支記錄器（WSL pid 198864、Windows typeperf pid 39196）。Monitor 每 30 分重開。
3. **今天全做完並 push**：
   - **大重構 S1～S11 全部完成**（S5、S7 公司重做，家機兩條分支作廢；只剩**家機重裝**）。S9 改名 inst→aos-inst、util 標頭進 `aos/util/`、`InputExtra→InputBad`、`DaemonRunning→DaemonExists`、`DeadlineMissed→DeadlineBad`；C-54 補第六種結尾 `…Rejected`。
   - no-pid P1～P6（P6 照使用者「子daemon對他來說就只是一個普通的proc。不要耦合」改成通用 `auto_restart`，[no-pid 15](../proto8/thinking/2026-11/05/no-pid/15-P6去耦合.md)；`restart_on_stuck` 名不改）；P5 沙箱正式支援、預設帶 `AOS_KERNEL`／`AOS_MEMORY`／`AOS_TICK`。
   - json-argv J1～J8；S8 help 分層、九短名、`-y`；寄信者自設 `--timeout-s`（第一個 commit）；T 線 T1～T4（[tick-time 04](../proto8/thinking/2026-11/05/tick-time/04-T線實作結果.md)）。
   - 條文：lift-to-norms 兩輪（C-76～C-83、N-65～N-67 等）；可遷移性 C-83＋N-67（加⑦⑧⑨）；C-52 例外 ⑤。
   - 規劃已裁：os-concepts、os-impl（判官排隊做選項、寄信者自設逾時＋判官「窗＋代為到期」）、env-portability（金鑰歸小 proc：端點小定義 `_entry` 寫 `--key-env`，kernel 不經手；url／model 不搬；aos-tools 登記檔照現況，使用者理由「用${HOME}/...，本來就是在命令行這個階段展開」）、mailbox-naming（不改名，但 llm kernel `mailbox/` 現在改 `requests/`；C-54 R14）、special-cases（C-52 讀成「不認身份、可認公開介面」、K1 判準＋現行表、K3、K7、第 3 次升格；`_` 開頭等撞名）。
   - 桌面新說明頁兩份：`aos-入門-ELI5.html`、`aos-詳細參考.html`（午間快照）。試驗場已刷新（備份 `~/code/playground.bak-1106h`）。
4. **還在跑（compact 後等回報、核對、轉告）**：T 隊 T7（daemon.json `tick` 展開成普通 proc＋`auto_restart`，照 no-pid 15）；I 隊 git 當 image 的膨脹評估＋.gitignore 建議（`proto8/thinking/2026-11/06/git-image/`）；K 隊把六題裁定寫進條文＋修 8 處條文矛盾＋改程式項排進 apply-ideas 02；L 隊 llm kernel `mailbox/`→`requests/`＋C-54 R14＋用語；J 隊補記 url／model 裁定與 aos-tools 理由。各隊 16:15 前停在建得過的 commit、寫交棒檔。
5. **收工前（約 16:30）**：效能標準寫進 01-公司WSL＋停記錄器；更新 claude.ai 本日進度頁 https://claude.ai/artifact/HazekvnmhUAgG8pwDr3Khd 與說明頁（aos-agent 用法頁跟 S8／timeout 改）；收工交接；問桌面「三扇門」頁加「已修」註或標過時。**今晚家機**：刪作廢 S5／S7 分支、`git pull`、重裝（S11 最後一步）。**之後排程**：P7（要照 C-52 新讀法重設計、不讀子 ctl 信箱）、P8、P9、T5／T6／T8、判官排隊＋寄信者逾時第二步、env 修補 E1～E4（apply-ideas 02 序 2c）、W 線、aos-serve。

提醒：設計題先讀相關 NORMS／CONCEPTS；說「已寫進」前先查。

## 2026-11-05 夜 22:00 前 家機（大重構第一波＋四份規劃裁定；明天開新 session 接）

1. **授權**：今晚隨意 push（origin main）；普通事 opus、雜活與純搬移 sonnet（碰程式碼不派 sonnet）；在家（家機 Manjaro）；並行用 worktree、ff-merge 與清 worktree 由隊長在主 repo 做。LM Studio 只載 `google/gemma-4-e4b`、不換。殺程序只用自己記的 pid。使用者：「今天的工作不用趕着做，晚上是思緒沉澱的好時候……以規劃爲主」。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。
2. **今晚做完並 push**：大重構七題照推薦（[arch-refactor](../proto8/thinking/2026-11/05/arch-refactor/README.md)、排程 [06](../proto8/thinking/2026-11/05/arch-refactor/06-工作量與排程.md)）；S0 殘渣刪除、S1 甲代封存 `archive/aos-v1/` `e3bc282f`、S2 甲代文件封存與入口改寫 `c0396b1c`、S3 impls 頂層一次建 `efcb5658`（11 支 bin）、S4 code map 改生成 `2d69a4f1`（`wf/tools/codemap_gen.py --apply`；鐵律 3 已改）；五題「剩下都照推薦」、K7「知識庫這塊都按照推薦」、no-pid 方向與補充都落進 thinking；試驗場 README 與桌面 html 第 0 步改成頂層一行建置，main 上建置＋試驗場複本最短路（假腦、gemma）過。
3. **明天要接**（順序見 [06 § 明天剩什麼](../proto8/thinking/2026-11/05/arch-refactor/06-工作量與排程.md#明天剩什麼11-05-收尾改成實際)）：⓪ 使用者 22:30 後提的兩個想法（信封與 body、暫停時間＝檔案系統 image、時間回到 tick：推薦 tick 回合數、`AOS_TICK` 指參照的時鐘、`AOS_TICK_INTERVAL` 一次 tick 的默契）原文在 [fs-image](../proto8/thinking/2026-11/05/fs-image/README.md)，明天先接著聊；① 審併兩條**本機** worktree 分支（沒 push；11-05 夜唯讀審查已做完、先看 [審查報告](workflows/refactor/reports/2026-11-05-S5-S7-審查/README.md)：S5 先修沙箱 `py/` 綁定、S7 可直接併只補紀錄）：S5 搬夾 `worktree-agent-a6238359e64b1a123`、S7 C++ 去重 `worktree-agent-aef456b36f04f15d3`（worktree 在 `.claude/worktrees/` 下；併 S5 後照 06 改使用者試驗場 env.sh 與教學路徑、重跑 install.sh）；② no-pid P1～P9（明天和 S6 一起做，P3＝S6；P1 先修 daemon `lock_fd_` 被不 exec 子行程繼承；規劃行號是 S5 前路徑）；使用者今晚聊的**監管樹方向已定**（[no-pid](../proto8/thinking/2026-11/05/no-pid/README.md)）；aos-lock 名牌改 flock 檔（使用者已裁）；json-argv 已回（[07](../proto8/thinking/2026-11/05/json-argv/07-使用者回覆-11-05晚.md)，P-44 照改「aos_flags 包 tool_io」），J 步排在 S5 後；③ S8～S11；④ 排在大重構後：`--env-file FILE`＋`--envs K=V` 並存、五題裁定（寄件人額度相對 kernel、`aos-agent tools add` 帶 env、沙箱先不支援 thought 等、stupid-fast 維持 qwen3-1.7b）、K7 已裁（W1～W3 主幹可做，W7～W10 照裁定：多庫用捷徑、不做 lock op、不記 `_meta`；[knowledge-write](../proto8/thinking/2026-11/05/knowledge-write/README.md)）、CONVENTION 草稿定稿編號。
4. **說明頁**（從刪掉的 11-05 收工條搬來）：每日進度頁「本日進度」https://claude.ai/artifact/HazekvnmhUAgG8pwDr3Khd （每天更新同一份，用 `url`）；新功能說明 https://claude.ai/artifact/LoFTkSuuFREyGksrEzfpqy 、aos-agent 用法 https://claude.ai/artifact/9joBCStEMXvNMXadMGXqCT 、工具箱與腦設定參考 https://claude.ai/artifact/HLMpsX3T76ndC7E8VQ8Nit ；S5 併進後這幾頁的路徑（bin／extras／demo）要改；artifact 一律「圖多、只講結論、細節摺疊、白話」。
