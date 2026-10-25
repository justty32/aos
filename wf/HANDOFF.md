# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-25 晚收尾（家中 Manjaro；兩隊已收線、等使用者思考）

1. **授權**：使用者 10-25「可以隨意push」——commit 後直接 push origin main。分工照 [user.md](workflows/common/user.md)：普通 opus、雜活 sonnet、規劃 fable（盡量少用；這次使用者點名 fable 規劃）；做事的 agent（雜活除外）先讀 wf 規矩。使用者白天外出時小決定由頂層代定，清單在 [session log 10-25 § 代定清單](session_logs/2026-10/2026-10-25.md#代定清單)（都可翻案）。context 約 30% 就換手（[user/02](workflows/common/user/02-交接與收工.md#compact-前先寫交接2026-10-15-定)）。LiteLLM 開著時腦只用 gpt 系列。
2. **狀態**：galtxt 由上而下兩隊（甲 `proto8/topdown/galtxt-a`、乙 `galtxt-b`）**都已收線**，沒做的各在 [甲隊 HANDOFF](../proto8/topdown/galtxt-a/HANDOFF.md)、[乙隊 HANDOFF](../proto8/topdown/galtxt-b/HANDOFF.md)；結論在 [thinking 10-25 top-down](../proto8/thinking/2026-10-25-top-down.md)。統整頁 https://claude.ai/artifact/9sj3ZkRhK4ZYomb8WeSzrA ；人評頁 https://claude.ai/artifact/ENDqGGkxBpydhsh6YcxGT9 （只有乙隊六筆，甲隊沒交真腦樣本；重建：scratchpad `rating/build.py`，新樣本要新 id）。使用者說「我抓到了一些問題點」「這次我應該會思考挺久」，還沒說是什麼。
3. **下次開場先問他抓到的問題點**，聽完再決定兩隊要不要續做、怎麼改；不要自己先開工。今天定的命名：C-54 計數 `counter_*`、上限 `max_*`、時間 `<事件>_at`（「都好」代定）。`.claude/worktrees/` 底下今天四個 worktree 與分支已刪（使用者准，內容都在 main）。
