# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-25 白天（家中 Manjaro；使用者外出中）

1. **授權**：使用者 10-25「可以隨意push」——每個 commit 後直接 push。分工照 [user.md](workflows/common/user.md)：普通 opus、雜活 sonnet、規劃 fable（這次使用者點名 fable 規劃）；做事的 agent（雜活除外）先讀 wf 規矩與 proto8 原則。使用者外出、不便評：小決定頂層代定、記代定清單，回來白話報告。context 約 30% 就換手（[user/02](workflows/common/user/02-交接與收工.md#compact-前先寫交接2026-10-15-定)）。LiteLLM 開著，腦只用 gpt 系列。
2. **正在跑**：galtxt 由上而下兩隊（甲 `proto8/topdown/galtxt-a`、乙 `galtxt-b`，各自 worktree，opus 隊長＋fable 規劃）；使用者一路補的想法（單一性格單一場景、樹中有樹、按子樹貢獻優化、節點從 agent 抽工具逐漸固化、梯度是任意結構、判斷器／優化器也是樹、錨）全在 [thinking 10-25 top-down](../proto8/thinking/2026-10-25-top-down.md) 原文段，已逐條轉給兩隊。隊長到 30% 會寫各自 `HANDOFF.md` 收線，頂層開新隊長接手（任務書範本在 scratchpad `team_a.md`／`team_b.md`，接手時以隊伍 HANDOFF＋thinking 為準）。人評網頁 https://claude.ai/artifact/ENDqGGkxBpydhsh6YcxGT9 （現放乙隊 round 0 六筆；重建：scratchpad `rating/build.py`，新樣本要新 id），使用者有空才評（WAIT_USER）。
3. **今天定的**：state.json `runs`→`counter_runs`、`at`→`recorded_at`；C-54 改：計數 `counter_*`、上限 `max_*`、時間 `<事件>_at`（55bb334a、55f541f7，「都好」代定可翻案）；agent-gus 小念頭不搬進 lib（代定）。

## 2026-10-24 收工（家中 Manjaro，下一個 session 重開）

1. **授權**：使用者 10-24「我隨便說，你隨便做，反正只是嘗試」「我現在沒空管這些小事，都按建議做」——今天的「代定」「照推薦定」一律可翻案；這次收工准 push 到 origin main。分工照 [user.md](workflows/common/user.md)（普通 opus、雜活 sonnet、fable 點名才用；頂層只跟使用者交流）。git 在這台直接用 `git -C ~/repo/simple_tools/aos`。
2. **下一個 session 要做的**（使用者原話「我要重開session，到時候我會開litellm，然後實際測試，開始打磨這些想法，讓他們可用」）：先 `curl localhost:4000/v1/models`，再照 [真腦實測交接](session_logs/2026-10/2026-10-24-真腦實測/README.md) 的順序跑（agent-dan → pip → json_edit → liv → kernel-llm → Janet／Lua／grow → say/listen → meg、hal → eve、gus → talk → kai → self-improve → aos-ai、fay → nvim、沙箱 root）。kernel-llm 要先改 daemon `max`；self-improve 跑前先定「預設關沙箱」那題。
3. **還掛著**：代定落條文（NORMS 08-待定 五行）、沙箱兩個洞（kernel 信箱後門、環境變數帶進沙箱）、compact 與 P-41 擦邊、方向題 tasks／通用 kernel → [SESSION-LOG](SESSION-LOG.md)、[WAIT_USER](WAIT_USER.md)。公司那台 WSL 的 `stash@{0}`（10-22 半截 rebase 的 autostash）仍由使用者決定要不要 drop。

