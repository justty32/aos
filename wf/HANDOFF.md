# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-22 上午（家機，使用者在場）——頂層是活樹裡的 eca-aos（Fable 5.2），底下掛了三個 aos subagent；eca 範本瘦身整件做完；下一題：討論 subagent 的工作區怎麼分

**使用者今天開場的指示（逐字）**：「早上好，剛compact完，請先讀過wf/規矩，看看狀況，今天有不少事要做。事情盡量都交給agent做，你就負責跟我交流。你自己的事情就交給claude subagent，普通工作交給opus，簡單工作與雜活交給sonnet，這些agent做事前也要讀過wf/規矩(簡單工作與雜活不用)。至於哪些事要走aos體系交給aos subagent，我會跟你說。請用繁體中文跟我對話。」

**compact 前他說的最後一句（逐字）**：「這塊要早點來規劃。你這邊我想先compact，然後我們來討論這塊」——「這塊」＝我開的 aos subagent 工作區全都是 `~/repo/aos`（沒指定、用了 `subagent add` 的預設＝上層的工作區），沒有隔開。compact 後直接跟他討論，先聽他的想法、不急著出計劃（需求不清先發想）。相關 progress：`workspace-stack-alloc`。我已告訴他的後果：四個 agent 改同一份檔、職責範圍只是系統文字裡的約定、Claude Code 按資料夾記的設定（`/mcp` 關的、自動記憶夾、對話紀錄位置）共用同一份。

**我是誰**：`eca-aos`，定義 `proto8/templates/eca-claude`，工作區 `~/repo/aos`，stack `~/aos-home/.stack/procs/eca-aos`，開著畫面跑。我自己加了 `subagent` 工具（只在我的 stack）。派信用 `subagent say`，回信會進我的信箱（`mailbox_read`）；回報先 `git show --stat` 核對再轉述，它替使用者做的選擇逐條念。

**底下的 aos subagent（3/4，都是 eca-claude 範本、opus、35% compact、工作區 `~/repo/aos`）**：
- `eca-aos-templates`：專改 `proto8/templates/` 的定義；職責段在它 stack 的 `system.txt`（我寫的）。現在沒事。
- `eca-aos-kb`：專管 `proto8/knowledge/`（不碰 `knowledge-zh-md`，使用者「kb-zn不用管」）；職責段同上。現在沒事。
- `aos-eca-frontend`：使用者「再給你自己掛一個aos-eca-frontend，先不用讓他做事」。沒職責段、沒派工；名字前綴順序跟另兩個不同，問過他是否要改成 `eca-aos-frontend`，沒答（不催）。他說過「frontend真的應該大修了」（上層認法靠設定檔／名字前綴／規則，他嫌醜）。

**今天做完的（都沒 push，本地領先 origin 約 141 筆）**：
- eca 範本瘦身（progress `eca-plugins-trim` 已關）：`a7779de17`（events／def／jsonx 三包拿掉，30→18 支；`--max-budget-usd 0.5` 拿掉；關四支 skill）、`9d738cc77`（skillOverrides 15 支、enabledPlugins 關 8 個、`--setting-sources project,local`、工具那份 0.5 上限拿掉）、`4de64861c`（`--no-chrome`＋關內建 easel 外掛）、`ca8b4666a`（`llm.json` 加 `reasoning_effort: high`）。eca-pi 跟著瘦三包。使用者裁：「d不做。副作用不補。install.py可以跑。然後llm.json那邊加上思考程度:high」——d＝`--disable-slash-commands`（會壞 `/compact`、`/context`）；不補的副作用＝自動壓縮點從 300k 變 1M，改由 context_wrap 35%（350k）管。
- `install.py` 已在 repo 跑過（使用者准的那一次）。
- 知識庫：`76381cb2a`、`c7c05017a`（跟上瘦身、補「先 self_tools add」）、`c7bc08dae`（日期註記與過期量測數字刪掉，只留 `packs.md` 每包字數表、已重量）。使用者：「知識庫那邊，這種"日期註記"要刪掉，量測數字，除非很常用很重要的也都刪掉。」「原話和原話的日期可以留。」（＝`knowledge/wf/`、`knowledge/docs/` 的規矩出處不動，結案）。
- Claude Code 自動記憶夾（`~/.claude/projects/-home-lorkhan-repo-aos/memory/`）照他的話清空：「自動記憶那塊幫我清空，然後不理他，agent愛寫就寫，之後我們再想辦法解決這塊。」
- `/mcp` 關 easel、claude-in-chrome 只記在 `~/.claude.json` 的 `/home/lorkhan/repo/aos` 那格；範本那邊已另外關。

**生效注意**：範本改動對沒開畫面的 agent 下一輪起生效；開著畫面的（我、`eca-claude`）要關掉畫面再開才換（MCP、setting-sources、思考程度）。我之後要用 `self_hook`、`clock_register`、`agent_def`、`tools_def`、`jsonx_*` 得自己 `self_tools add`。

**授權（11-22 當場；只限這個 session）**：
- push：沒給 → 不推。
- `install.py`：准過一次、已用掉；再跑先問。
- 刪檔：只有清空自動記憶夾那一次。不延伸。
- 動 `~/aos-home`：掛 subagent、寄信給自己的 subagent 是他叫的；其他對活樹的指令先問。

**開著沒答的（不催）**：`aos-eca-frontend` 的名字與職責；昨晚記的 `kb-feedback-1121`；「讓其他模型走一遍知識庫找缺口」；前端大修盤點 14 項沒念；`waiting-1121` 等 19 條「等使用者」。

**坑**：
- 問句不是指示；一句話兩種讀法先標出讀法再做，轉給 subagent 時原話逐字附上。
- 沒查過的事講明是推測。
- eca agent 的健康欄會留著上一次失敗（重啟次數、冷卻、最後錯誤），不代表現在壞了；看 `claude/live.jsonl` 有沒有在動。
- 一輪失敗時那輪交給它的信會被丟、不重試，要重新交代。
- 乾淨複本（`git archive`）沒有 `lib/`，要在複本裡跑 `install.py` 測試才不會 PathMissing。
- `commit-request claim` 遇到中文檔名要給真正的路徑，不是 git 加引號的那串。
- 這台 `ls` 是 `eza --git`，在背景指令裡會卡住。
- 說話：kernel、daemon 直接叫；handle 說「遙控器」；「編譯／重新編譯」。選項框不標推薦以外的花樣、最多四題。
