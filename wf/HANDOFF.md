# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-07 傍晚 家機 alt 帳號頂層（使用者要 compact；第二輪收完就停）

1. **授權與隊形**：本 session 隨意 push。opus 隊長＋subagent＋最多一個 codex；gpt 只施工／文件／網頁／雜活、不做設計，「能交給gpt的就交給gpt」；fable 只做頂層規劃、只讀 opus 備的簡報，輪間輪中皆可、次數不限（[aos-teams](workflows/dispatch/aos-teams.md)）。本機 LM Studio 一次只載一個模型；模型下限 10B；LiteLLM 有 `chatgpt-gpt-terra*`。家機 codex 連 LiteLLM 時不帶 `-s`（沙盒待辦見 SESSION-LOG）。另一帳號 aos-b0 已關，不要再寄信給它。
2. **使用者規矩（今天新定，都已進 wf）**：改條文時舊句可直接刪、靠 git 找回（user/03「11-07 檢討」）；「很多東西都可以靈活改進」——判準、門檻、階段、審視標準本身都可被改進（kb-ideas 想法 15）；單任務指標＝(token in＋out)÷(原文 bytes×2)，只套在一個地點／人物／事件那級（想法 14）。
3. **今天做完並 push**：sol 審查全收（[10](workflows/refactor/reports/2026-11-07-sol審查/10-修正結果.md)、[11](workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)）；daemon 不分類 B＋失敗留表＋`aos-daemon-ctl prune`；edge-1107 四項；晚審必修全修（[06](workflows/refactor/reports/2026-11-07-晚審/06-修正結果.md)）；aos-b0 交回 7 份設計（`proto8/thinking/2026-11/07/` 的 evolve-design、tool-evolve、kb-scale、kernel-nest、agent-diversity、lift-to-norms、arknights-kb-audit）；使用者 40 題已裁（桌面 `aos-1107傍晚-待你裁.json`）。
4. **還在跑／停點**：① 40 題裁定收進各 README＋lift-to-norms 草稿貼進條文（opus 線，完成會回報）；② arknights 第二輪（第四任隊長）：收完 B8 就收輪、**準備好第二輪總結簡報但不開 fable、不開第三輪**，停在 [交棒](../proto8/thinking/2026-11/07/arknights-kb/交棒.md)「等使用者第三輪建議」。使用者說第三輪 fable 規劃前他有建議，且第二輪後要「稍微停下來，讓大家喘口氣」。
5. **待辦**：互動頁抽成工作流（SESSION-LOG 第一行；已試用兩次：sol 審查頁、傍晚 40 題頁，資料格式見 json）；晚審剩一個判官「墓碑」設計題待問使用者；5 份設計的程式實作待排；桌面 `~/Desktop/aos-arknights/` 每地點更新（交棒固定步驟）；負載監看是 session 內 Monitor，換 session 要重開。

## 2026-11-07 午 家機 alt 帳號頂層（額度剩約 8%，等重置或 compact）

1. **授權**同下一條（隨意 push；11-07 隊形：opus 隊長＋subagent＋最多一個 codex，gpt 只施工／文件／網頁／雜活，能交 gpt 就交 gpt）。家機 codex 要連 LiteLLM 得拿掉 `-s`（照用使用者 `~/.codex/config.toml`），見 [arknights-kb 交棒](../proto8/thinking/2026-11/07/arknights-kb/交棒.md)。額度約 13:30 重置。
2. **上午做完並 push**：sol 審查 34 列——「翻」項全修（[10](workflows/refactor/reports/2026-11-07-sol審查/10-修正結果.md)）、使用者網頁裁定 32 題全落實（[11](workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md)；第 7、35 題試驗場那半等刷新 `~/code/playground` 時補）；arknights 第一輪跑通（[04](../proto8/thinking/2026-11/07/arknights-kb/04-第一輪實跑.md)；4.7 萬 token／條、重跑一致 0%、14 個 aos 不足；`memory_write` W1～W4 進 main）；使用者對隊長六題已裁（arknights-kb README 末段：節點英文、內文照語料原文、給人看走白話附屬庫或問答 agent）。
3. **接手先做**：第二輪起照 aos-teams 11-07 午的 fable 分工：fable 只做頂層規劃且只讀備好的資材（opus 計劃→gpt 收集→opus 匯總），opus 據此設計架構並主導、審 gpt，gpt 施工；fable 只在輪與輪之間總覽與總建議。開新 opus 隊長跑 arknights 第二輪，照 [交棒](../proto8/thinking/2026-11/07/arknights-kb/交棒.md)＋使用者六題裁定（內文照原文 → LLM 只做切分／對位，不改寫）；先修 aos 不足：agent 歷史越長越貴、kernel 轉交 token 計數歸零。互動頁抽工作流（SESSION-LOG 第一行）等使用者說。頂層負載監看（80%）要重開。
4. 桌面：`aos-sol審查-待你裁.html`（已回）、`aos-arknights第一輪總結.html`（codex 做，頂層沒細驗）。

## 2026-11-07 上午 家機 alt 帳號頂層（額度剩約 17%）

1. **授權**：本 session 隨意 push；使用者出門吃早午餐（約 10:30 起一兩小時），大小決策頂層先做、記代定清單。隊形照 [aos-teams](workflows/dispatch/aos-teams.md) 11-07 版：opus 隊長＋subagent＋最多一個 codex；gpt 系只施工／寫文件／網頁／雜活、不做設計；「能交給gpt的就交給gpt」。本帳號（`CLAUDE_CONFIG_DIR=~/.claude-alt`）五小時額度剩約 17%：到 99% 時各線暫停不結束、寫本檔。
2. **今早做完並 push**：aos-95 交接信辦完歸檔；C++ 家機重建；sol 審查報告（[README](workflows/refactor/reports/2026-11-07-sol審查/README.md)、09 總表 34 列）＋「翻」項全修（[10-修正結果](workflows/refactor/reports/2026-11-07-sol審查/10-修正結果.md)）；os-impl 09 直掛 agent 不上表（使用者選 A、已落實）；user-advice 20261106 入庫。桌面互動頁 `~/Desktop/aos-sol審查-待你裁.html`，使用者已回（原話在 11-使用者裁定.md）。
3. **還在跑的兩條線**：① opus 隊長落實使用者裁定 → `wf/workflows/refactor/reports/2026-11-07-sol審查/11-使用者裁定.md`（逐題結果記檔末）；② arknights 歸納進 aos 知識庫（opus 隊長＋fable 規劃＋opus 審＋codex；playground 另開 `~/code/playground-ak/`，`~/repo/narratives/arknights` 唯讀）→ `proto8/thinking/2026-11/07/arknights-kb/`（交棒.md、代定清單、得失、不足清單）。接手者先看這兩個檔再決定續跑。
4. **待辦**：互動頁抽成工作流（SESSION-LOG 第一行）；第 35 題 LITELLM_KEY 等裁定落實結果看 11 檔；頂層負載監看（超 80% 才通知）是本 session 的 Monitor，換 session 要重開。

## 2026-11-06 夜 收工 家機（明早接）

1. **授權**：本 session 隨意 push；普通工作 opus、雜活 sonnet；本週 Claude 額度緊（公司時剩約 7%），隊長 opus＋寫碼盡量派 codex `gpt-6.1-sol`；在家機。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問 push。
2. **今晚做完並 push**：家機清作廢 S5／S7 分支與殘渣、重裝、試驗場刷新（`9241be909`）；kernel `smart-high` 模型名改 `claude-haiku`（`79d736b4c`）；代號自由取名＝現況已支援、不改程式（[alias-names](../proto8/thinking/2026-11/06/alias-names/README.md)）；no-pid P7（`e588b8c69`，父只看子活著；使用者「子daemon管好自己…盡量解耦合」）、K-5、P8（根 daemon、試驗場三層）、P9（`30c3d5ee8`…`98518bd44`）；tick 線 T5／T6／T8 全做完（`2f4e2dc3`、`a858fe1a`；三個時鐘使用者選「留著」`5ae47106e`）；判官排隊＋寄信者逾時第二步＋K-3＋C5 留格＋E2 kernel 半（`3e8ac15d4`、`b19f844cb`、`5ffa76567`，結果 [os-impl 06](../proto8/thinking/2026-11/06/os-impl/06-判官排隊第二步實作結果.md)、[07](../proto8/thinking/2026-11/06/os-impl/07-C5留格與AOS_KERNEL提醒實作結果.md)）；桌面 `~/Desktop/aos-試驗場教學.html` 換三層新版（舊的 `.bak-1105.html`，沒人看過畫面）。
3. **明天要接**：① 家機 C++ 重建（使用者玩完才建：`(cd proto8/impls && nice -n 15 cmake --build build -j4)`），留格與 AOS_KERNEL 提醒才生效；② 試驗場 README 小瑕疵（範例輸出是 11-05 的、第 6 節順序、crash 沒給 kill 指令）與 repo 文件不符（`proto8/cmd/aos-agent/docs/04-搬家/01-六段食譜.md` 建議只根開 tick vs 使用者選三層各留；04-搬家.md 目錄序 01、03、02；03-重建root 範例路徑名跟試驗場不同）；③ 判官隊長說有一個假腦 fixture 接法本來就壞（改前就失敗），要派人修；④ 排程剩：K-1、知識庫 W 線（W1～W3）、aos-serve、CONVENTION 草稿定稿、`--env-file`＋`--envs`。另：頂層轉題前要先對過使用者以前的裁定（今晚 T 隊把已定的「近的贏」又當方向題丟上來）。

## 2026-11-06 收工 16:45 公司（17:05 關機；家機接）

1. **隊形改了（11-06 傍晚）**：使用者「我們的本週額度剩7%了」「盡量用codex」「或是單派codex也可以」——**本週剩下的工作直接派 codex 當隊長**（`codex exec -m gpt-6.1-sol -s workspace-write -C <dir> -o out.md '/goal …' < task.md`，在非 git 資料夾要加 `--skip-git-repo-check`，這不算繞沙箱），不配 Claude 隊長；codex 不 commit，頂層看報告＋diff 後 `git commit -- <路徑>`、push。WSL claude 是公司帳號，不吃這個額度，可當審稿。fable 照舊：使用者說才走 WSL。其餘授權（隨意 push、WSL 主 clone、不碰使用者程序、不繞沙箱）同上一條。
2. **效能**：使用者閒著時同時 7～8 個 codex、load 只有 2～2.5（codex 多在等 API）；使用者 15:55「沒關係的，可以加開，我現在沒在幹嘛。」。兩支記錄器 16:25 已停；效能隊把標準寫進 [01-公司WSL](workflows/dispatch/aos-teams/01-公司WSL.md)（若收工前沒 commit，見第 5 點）。
3. **今天下午到收工做完並 push**：P-32 移除（19acb13c；使用者「移除P-32」，C-42 沒給 ws＝沿用父的改成已定）；E1＋E4 金鑰歸端點小 proc（02edef8f）；E3＋K-4（c1fb18c5）；K-2＋E2 的 AOS_TICK 半（3bada8a0）；K-6 thought 不寫死範本（407ee400）＋`from` 可在工具登記格 `env.AOS_THOUGHT_FROM` 配預設（7cfdccf0，使用者「定義裡配預設」）；`aos-agent ctl add` 沒給 --ws 先讀 AOS_WS（2a0afb06，使用者「改成先讀 AOS_WS」）；git-image 評估（04185730；三題已裁：只留最新一份、**request.json 改成可重建後擋掉**、.trash 擋掉不搬）。
4. **說明頁**：claude.ai 本日進度頁（第 7 版）與 aos-agent 用法頁 https://claude.ai/artifact/9joBCStEMXvNMXadMGXqCT 已更新；桌面 `aos-入門-ELI5.html`、`aos-詳細參考.html` 換新；**桌面新資料夾 `aos-說明/`**（431 頁：ELI5、教學〔概念＋agent 入門，使用者「拆兩塊」「盡量多」〕、案例集 16 例、參考書 6 頁、原始碼 371 頁，離線可開，重建用裡面的 `tools/build_site.py`；沒人看過畫面，要使用者看一眼）。桌面「三扇門」頁使用者說「別管」。
5. **還沒收完的**：Z 隊（git-image 三題落地：agent-fsm wait 格找不到 request.json 退回 think 重組、stack.gitignore 照 git-image 04 加 20 條＋擋 request.json、docs/04-搬家 補「專門 repo、orphan commit＋push --force、要留的打 tag」、修 11-06 日誌壞連結）與效能隊——收工前做完就 commit，沒做完就**留在 WSL 主 clone 的工作樹沒 commit**，報告在 WSL `/tmp/teamZ/out.md`、`/tmp/teamPerf/out.md`（關機後 /tmp 可能清掉，所以明天要先 `git status` 看工作樹、審過再 commit）。
6. **家機 11-06 晚已做完**：作廢 S5／S7 兩條 worktree 分支與 build 殘渣已刪、impls 重建（nice 15、-j4）、`install.sh` 重裝（舊連結先 `--uninstall`）、`~/code/playground` 照新路徑刷新（備份 `playground.bak-1106home`）、LiteLLM 在 :4000。**之後排程**：P7（照 C-52 新讀法重設計、不讀子 ctl 信箱）、P8、P9、T5／T6／T8、判官排隊＋寄信者逾時第二步（K-3、E2 的 AOS_KERNEL 半併這裡）、K-1、K-5（P8 前）、W 線、aos-serve。

提醒：設計題先讀相關 NORMS／CONCEPTS；說「已寫進」前先查。

## 2026-11-05 夜 22:00 前 家機（大重構第一波＋四份規劃裁定；明天開新 session 接）

1. **授權**：今晚隨意 push（origin main）；普通事 opus、雜活與純搬移 sonnet（碰程式碼不派 sonnet）；在家（家機 Manjaro）；並行用 worktree、ff-merge 與清 worktree 由隊長在主 repo 做。LM Studio 只載 `google/gemma-4-e4b`、不換。殺程序只用自己記的 pid。使用者：「今天的工作不用趕着做，晚上是思緒沉澱的好時候……以規劃爲主」。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。
2. **今晚做完並 push**：大重構七題照推薦（[arch-refactor](../proto8/thinking/2026-11/05/arch-refactor/README.md)、排程 [06](../proto8/thinking/2026-11/05/arch-refactor/06-工作量與排程.md)）；S0 殘渣刪除、S1 甲代封存 `archive/aos-v1/` `e3bc282f`、S2 甲代文件封存與入口改寫 `c0396b1c`、S3 impls 頂層一次建 `efcb5658`（11 支 bin）、S4 code map 改生成 `2d69a4f1`（`wf/tools/codemap_gen.py --apply`；鐵律 3 已改）；五題「剩下都照推薦」、K7「知識庫這塊都按照推薦」、no-pid 方向與補充都落進 thinking；試驗場 README 與桌面 html 第 0 步改成頂層一行建置，main 上建置＋試驗場複本最短路（假腦、gemma）過。
3. **明天要接**（順序見 [06 § 明天剩什麼](../proto8/thinking/2026-11/05/arch-refactor/06-工作量與排程.md#明天剩什麼11-05-收尾改成實際)）：⓪ 使用者 22:30 後提的兩個想法（信封與 body、暫停時間＝檔案系統 image、時間回到 tick：推薦 tick 回合數、`AOS_TICK` 指參照的時鐘、`AOS_TICK_INTERVAL` 一次 tick 的默契）原文在 [fs-image](../proto8/thinking/2026-11/05/fs-image/README.md)，明天先接著聊；① 審併兩條**本機** worktree 分支（沒 push；11-05 夜唯讀審查已做完、先看 [審查報告](workflows/refactor/reports/2026-11-05-S5-S7-審查/README.md)：S5 先修沙箱 `py/` 綁定、S7 可直接併只補紀錄）：S5 搬夾 `worktree-agent-a6238359e64b1a123`、S7 C++ 去重 `worktree-agent-aef456b36f04f15d3`（worktree 在 `.claude/worktrees/` 下；併 S5 後照 06 改使用者試驗場 env.sh 與教學路徑、重跑 install.sh）；② no-pid P1～P9（明天和 S6 一起做，P3＝S6；P1 先修 daemon `lock_fd_` 被不 exec 子行程繼承；規劃行號是 S5 前路徑）；使用者今晚聊的**監管樹方向已定**（[no-pid](../proto8/thinking/2026-11/05/no-pid/README.md)）；aos-lock 名牌改 flock 檔（使用者已裁）；json-argv 已回（[07](../proto8/thinking/2026-11/05/json-argv/07-使用者回覆-11-05晚.md)，P-44 照改「aos_flags 包 tool_io」），J 步排在 S5 後；③ S8～S11；④ 排在大重構後：`--env-file FILE`＋`--envs K=V` 並存、五題裁定（寄件人額度相對 kernel、`aos-agent tools add` 帶 env、沙箱先不支援 thought 等、stupid-fast 維持 qwen3-1.7b）、K7 已裁（W1～W3 主幹可做，W7～W10 照裁定：多庫用捷徑、不做 lock op、不記 `_meta`；[knowledge-write](../proto8/thinking/2026-11/05/knowledge-write/README.md)）、CONVENTION 草稿定稿編號。
4. **說明頁**（從刪掉的 11-05 收工條搬來）：每日進度頁「本日進度」https://claude.ai/artifact/HazekvnmhUAgG8pwDr3Khd （每天更新同一份，用 `url`）；新功能說明 https://claude.ai/artifact/LoFTkSuuFREyGksrEzfpqy 、aos-agent 用法 https://claude.ai/artifact/9joBCStEMXvNMXadMGXqCT 、工具箱與腦設定參考 https://claude.ai/artifact/HLMpsX3T76ndC7E8VQ8Nit ；S5 併進後這幾頁的路徑（bin／extras／demo）要改；artifact 一律「圖多、只講結論、細節摺疊、白話」。
