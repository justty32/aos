# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-06 上午 公司（compact 前；同一 session 接著做）

1. **授權**：今天隨意 push；公司 Windows＋WSL，一律在 WSL 主 clone `~/repo/simple_tools/aos` 改（Windows 工作樹只 pull）。隊形（使用者 11-06 定，寫在 [aos-teams](workflows/dispatch/aos-teams.md)、[01-公司WSL](workflows/dispatch/aos-teams/01-公司WSL.md)）：頂層只交流派隊；每隊 opus 自家 subagent 當隊長＋兩隊員（codex `gpt-6.1-sol` 帶 `/goal`、WSL claude `--model claude-opus-5-5` 另一帳號），隊員可無上限派子 agent（codex 普通 sol／簡單 `gpt-5.6-terra`；claude 普通 opus／簡單 sonnet）；盡量派 codex；fable 規劃者可再派 fable。**使用者的公司工作高負載、絕不能動**；重指令 `nice -n 15`、git grep `--threads 2`；共用 index：`git commit -- <路徑>`。有方向題就用選項框問（Windows 會跳提醒）。LM Studio 使用者開了（qwen3-1.7b，localhost:1234），別長時間連跑。效能整天記錄：`C:\Users\WG-Guanyu\aos-perf\` 兩份 CSV（WSL pid 198864、Windows typeperf pid 39196），收工前分析訂「公司最多同時幾個 codex／claude」，記得把使用者自己的工作負載分開看（09:48 起常 7～11）；保險絲（95% 砍）之後再做。
2. **今天已做完並 push**：no-pid P1～P4、P5b 條文（85d9bc6d；要使用者看的概念 7 條在 [no-pid 12](../proto8/thinking/2026-11/05/no-pid/12-P5b條文結果.md)，其中 N-17「不從檔案判斷」↔ P7 用 `responded_at` 判 stuck 要在 P7 前問）；S5 公司重做（b0adec7f，家機 S5 分支作廢）；J1、J2；試驗場刷新＋`~/.local/bin` 重裝；說明頁三份 artifact 與桌面兩頁換新路徑；舊版 codex 刪除（`~/.local/bin/codex`→nvm 原生執行檔 0.166.0）。fable 規劃全部已裁：[body-protocol](../proto8/thinking/2026-11/06/body-protocol/README.md)（一箱一函數；不要與 aos-post 耦合太深）、[apply-ideas](../proto8/thinking/2026-11/06/apply-ideas/README.md)（排程；D1 先只有硬凍）、[tick-time 03](../proto8/thinking/2026-11/05/tick-time/03-11-06-裁定與新設計.md)（daemon.json 自帶 `tick`、沒 tick 退牆鐘、N1／N2 照推薦）、[daemon-board](../proto8/thinking/2026-11/06/daemon-board/README.md)（板子比喻 6 題；暫停目的＝能遷移、SIGSTOP 不採）、[human-cli](../proto8/thinking/2026-11/06/human-cli/README.md)（九個共用短名、終端問非終端不問＋`--yes`、不可逆只三個）。
3. **還在跑（compact 後等它們回報、核對、轉告使用者）**：A 隊 S8-0／S8-a／S8-b（aos_flags 短名＋confirm、aos-agent 拆套件、help 分層）；B 隊 S8-c／S8-d＋拆 `py/daemon_ctl.py`（等 A 隊 S8-0 push 再接短名）；條文隊「最近幾天 thinking 提取進 CONCEPTS／NORMS」（[lift-to-norms](../proto8/thinking/2026-11/06/lift-to-norms/)；已定未實作寫成「已定、實作排 X」，頂層代定）；fable「RTOS／嵌入式 Linux／韌體概念與很多核」（`proto8/thinking/2026-11/06/os-concepts/`）。
4. **之後**：今晚家機——刪作廢 S5 分支、S7 疊到新 main（S5＋P1；同檔 daemon.cpp／common.hpp）、S8 的 C++ 部分（S8-e、C++ 大檔拆）、S9～S11；json-argv 09 的 S8 邊緣（`py/cli_session.call_main` 的 `AOS_WS=.`）B 隊若沒收要接。收工前：效能標準、本日進度頁 https://claude.ai/artifact/HazekvnmhUAgG8pwDr3Khd 更新、aos-agent 用法頁跟 S8 改、HANDOFF 收工條。三扇門那頁（桌面）有幾段描述已修掉，加「已修」註或標過時待問使用者。

## 2026-11-05 夜 22:00 前 家機（大重構第一波＋四份規劃裁定；明天開新 session 接）

1. **授權**：今晚隨意 push（origin main）；普通事 opus、雜活與純搬移 sonnet（碰程式碼不派 sonnet）；在家（家機 Manjaro）；並行用 worktree、ff-merge 與清 worktree 由隊長在主 repo 做。LM Studio 只載 `google/gemma-4-e4b`、不換。殺程序只用自己記的 pid。使用者：「今天的工作不用趕着做，晚上是思緒沉澱的好時候……以規劃爲主」。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。
2. **今晚做完並 push**：大重構七題照推薦（[arch-refactor](../proto8/thinking/2026-11/05/arch-refactor/README.md)、排程 [06](../proto8/thinking/2026-11/05/arch-refactor/06-工作量與排程.md)）；S0 殘渣刪除、S1 甲代封存 `archive/aos-v1/` `e3bc282f`、S2 甲代文件封存與入口改寫 `c0396b1c`、S3 impls 頂層一次建 `efcb5658`（11 支 bin）、S4 code map 改生成 `2d69a4f1`（`wf/tools/codemap_gen.py --apply`；鐵律 3 已改）；五題「剩下都照推薦」、K7「知識庫這塊都按照推薦」、no-pid 方向與補充都落進 thinking；試驗場 README 與桌面 html 第 0 步改成頂層一行建置，main 上建置＋試驗場複本最短路（假腦、gemma）過。
3. **明天要接**（順序見 [06 § 明天剩什麼](../proto8/thinking/2026-11/05/arch-refactor/06-工作量與排程.md#明天剩什麼11-05-收尾改成實際)）：⓪ 使用者 22:30 後提的兩個想法（信封與 body、暫停時間＝檔案系統 image、時間回到 tick：推薦 tick 回合數、`AOS_TICK` 指參照的時鐘、`AOS_TICK_INTERVAL` 一次 tick 的默契）原文在 [fs-image](../proto8/thinking/2026-11/05/fs-image/README.md)，明天先接著聊；① 審併兩條**本機** worktree 分支（沒 push；11-05 夜唯讀審查已做完、先看 [審查報告](workflows/refactor/reports/2026-11-05-S5-S7-審查/README.md)：S5 先修沙箱 `py/` 綁定、S7 可直接併只補紀錄）：S5 搬夾 `worktree-agent-a6238359e64b1a123`、S7 C++ 去重 `worktree-agent-aef456b36f04f15d3`（worktree 在 `.claude/worktrees/` 下；併 S5 後照 06 改使用者試驗場 env.sh 與教學路徑、重跑 install.sh）；② no-pid P1～P9（明天和 S6 一起做，P3＝S6；P1 先修 daemon `lock_fd_` 被不 exec 子行程繼承；規劃行號是 S5 前路徑）；使用者今晚聊的**監管樹方向已定**（[no-pid](../proto8/thinking/2026-11/05/no-pid/README.md)）；aos-lock 名牌改 flock 檔（使用者已裁）；json-argv 已回（[07](../proto8/thinking/2026-11/05/json-argv/07-使用者回覆-11-05晚.md)，P-44 照改「aos_flags 包 tool_io」），J 步排在 S5 後；③ S8～S11；④ 排在大重構後：`--env-file FILE`＋`--envs K=V` 並存、五題裁定（寄件人額度相對 kernel、`aos-agent tools add` 帶 env、沙箱先不支援 thought 等、stupid-fast 維持 qwen3-1.7b）、K7 已裁（W1～W3 主幹可做，W7～W10 照裁定：多庫用捷徑、不做 lock op、不記 `_meta`；[knowledge-write](../proto8/thinking/2026-11/05/knowledge-write/README.md)）、CONVENTION 草稿定稿編號。
4. **說明頁**（從刪掉的 11-05 收工條搬來）：每日進度頁「本日進度」https://claude.ai/artifact/HazekvnmhUAgG8pwDr3Khd （每天更新同一份，用 `url`）；新功能說明 https://claude.ai/artifact/LoFTkSuuFREyGksrEzfpqy 、aos-agent 用法 https://claude.ai/artifact/9joBCStEMXvNMXadMGXqCT 、工具箱與腦設定參考 https://claude.ai/artifact/HLMpsX3T76ndC7E8VQ8Nit ；S5 併進後這幾頁的路徑（bin／extras／demo）要改；artifact 一律「圖多、只講結論、細節摺疊、白話」。
