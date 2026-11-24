# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-24 晚 22:30（家機）——家機建好組織；23:00 推一次；使用者要 compact 後切 fable 聊 aos 的目標

**寫這條的是家機 repo-aos 樹裡的 `main`**（家機工作室的負責人，對應公司的 eca-aos）。細節在 [`wf/ws/main/notes.md`](ws/main/notes.md)。上一條（公司 11-24 上午）在 git 歷史 `be448758e`，它「切完要接的」第 2、3 項照抄在下面。

**使用者 compact 前的話（逐字）**：「Hmmm，我想compact，然後我要切到fable，來聊一聊一些我的想法，關於整個aos的目標。」——compact 後他換 fable 模型來談 aos 的目標：**這是聊想法，不是派工**；聽、整理、擺選項，方向他定（鐵律 5），談出來的要記就記進 thinking 或 progress，別自己開工。

**授權（11-24 晚當場）**
- **push**：「晚上十一點統一推」——23:00 推一次 `origin main`，只這一次。鐘 `push-2300` 已登記（clock_register，到時寄進 main 的 queue）；推前看工作樹乾淨、沒有位子在交件。推完就沒有 push 授權了。
- 家機組織五題「1.a,2.a,3,a,4.a,5.a」：負責人沿用 `main`、三位子現在就掛（沒活就睡）、主帳號 eca-claude、位子筆記兩台共用 `wf/ws/eca-aos/<位子>/`、**家機只接使用者在家機當場交代的**（記在 [wf/org「家機」](org/README.md#成員表)）。

**今晚做完的（都已交，23:00 一起推）**
- 家機三分已就位（19:05 重起、`.bak` 刪了、舊範本夾刪了）；根的 AOS_LLM_KERNEL 對了，repo-vc 兩封、narr-amber 一封都回了 DONE。
- 組織：`main` 加了 `subagent`、`agent_def`、`clock_register`；掛了 `eca-aos-kb`、`-templates`、`-core`（各自 `system.txt`、`notes_path`），現在三個都睡著。
- kb：家機文件跟上（`4936939e5`、`e392793d6`）、git clean 規矩換理由（`bb9f51818`）、知識庫 source.md（`e8439c021`）、listen 那批跟上（`37a101e9a`、`e7a73061f`）。
- core：`.gitignore` 註解（`4b17a8341`）；narr-amber 回報三件（`aa8bd9cef` aos-mcp 同時跑多個呼叫、`bc8938198` listen／ask 也認子回的信、`255d6da30` observed 記 effort），repo 已 install.py。
- `wf/advices/feedback/` 四份意見收進 git（`6e4f82bfb`）。

**還開著**
- progress `narr-amber-fb-1124`：已在跑的 session 要重開才吃新 aos-mcp；重開後實地試一次「listen 等著時叫 mailbox_peek」，過了刪那條。
- 公司那條留下的（第 2、3 項）：各專案協調者交定義改動（arena_cheater 七份、ops-notes 的 patrol）；`templates/agents/reviewer/tools.json` 第 1 行；知識庫三句；各位子讀一遍腳本改過的句子；CONVENTION P-27 等句子派 opus 逐句看；progress `eca-main-obs-1124`、`mine-arena-dir-1123`。照 5.a 這些留給公司做。

**坑**
- 家機的 `ls` 是 `eza --git`，接管線用 `/usr/bin/ls`。
- 位子睡著時別的位子寄信給它不會叫醒它：要 `subagent wake` 再 `say` 提醒它看信箱。
- commit-request：progress 用 `--ops-file` 的 `progress_upsert`／`progress_delete`，不列 `--files`。
- 不跑 `git stash`、`reset --hard`、`checkout -- .`、`clean -fdx`；別棵樹的 stack、信箱、`/proc/*/environ` 不讀。
