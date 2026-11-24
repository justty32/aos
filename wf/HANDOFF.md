# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-24 上午 10:10（公司機）——templates 三分切換中：醒來先讀這條

**寫這條的是 `eca-aos`**。細節在 [`wf/ws/eca-aos/notes.md`](ws/eca-aos/notes.md) 的 11-24 各節。

**切換**：補丁在 `~/.aos/scratch/tri-split-1124/` 做好、測過（底 `f263b12b6`，複本 HEAD `d34fba370`，全套新紅 0）。照打清單在 `~/.aos/scratch/tri-split-1124/out/RUNBOOK.md`（不在 git 裡），由使用者開的樹外 Claude Code 視窗照打、每步他點頭（11-23 晚家機答第 ③ 題 b）。停樹時 eca-aos 也停；**醒來（樹重起後）先看**：`git log --oneline -3` 有沒有 `tri-split-1124` 的 commit、`git status --short` 乾淨嗎、`subagent ls`、`mailbox_peek`。

**授權（11-24 當場）**
- **push：使用者「下午五點我關機下班前一起推」**——17:00 前推一次 `origin main`，只這一次。
- `install.py` 常設許可（11-23「想跑就跑，隨便跑」）照舊；其餘照 11-23 那條（git 歷史）：派工模型、eca_main 的普通工作算授權、專區回信要 verify、掛新位子先問。

**切完要接的**
1. 家機也要照 06f「家機照做」：停樹、pull、跑 `stack_paths.py`（家機的 `repo-aos/main` 也直接掛 `templates/eca-claude`）。
2. 各專案協調者在自己的 repo 交第 10 步的定義改動（arena_cheater 七份、ops-notes 的 patrol）；`templates/reviewer/tools.json` 第 1 行；知識庫三句；各位子讀一遍腳本改過的句子；CONVENTION P-27 等句子派 opus 逐句看（使用者 11-23 晚「1.可以」）。
3. progress `eca-main-obs-1124`（eca_main 六點：文件派 kb、小程式派 core；範本 llm kernel 預設值、閒置輪詢的方向、`eca-aos-sol-1`／`-2` 的 stack 刪不刪要問使用者）、`mine-arena-dir-1123`（①②③ 開工）。
