# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-28 晚（家中 Manjaro；新 session 開場）

1. **授權**：可隨意 push。分工：普通事 opus、雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩；agent 可再派 agent、模型隨意。
2. **狀態**：開場只看了狀況、還沒動工；設計已定等實作的是 agent-round（[SESSION-LOG](SESSION-LOG.md) 第一條）。
3. **新規**：無。

## 2026-10-27（家中 Manjaro；playground 重來、aos-mcp、aos-hub）

1. **授權**：可隨意 push。分工：普通事 opus、雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩。
2. **狀態**：playground（`~/code/try/playground`）10-26 砸掉一步一步重來：`_entry` 一行轉 `main.py`（ELI5 注解），`claude -p` 經 aos-mcp 叫 aos 工具；aos-hub 管多個 claude，使用者說是 demo、以後再完善。下一步等使用者說 → [SESSION-LOG](SESSION-LOG.md) 第一條、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
3. **新規**：無；代定在 [thinking 10-26 playground](../proto8/thinking/2026-10-26-playground.md)、[10-27 claude-switch](../proto8/thinking/2026-10-27-claude-switch.md)。

## 2026-10-26（家中 Manjaro；整理與精簡全部完成）

1. **授權**：可隨意 push（commit 後直接 push origin main）。分工：普通事 opus、雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩。
2. **狀態**：今天 proto8 頂層整理與文件內容精簡全部完成，經過見 [session log 10-26](session_logs/2026-10/2026-10-26.md)。使用者還在改 `proto8/user-advice/README.md`，等他說好再動，不碰該資料夾。10-25 的「問題點」仍待使用者說（見 [WAIT_USER](WAIT_USER.md)），說之前不要自己續做兩隊。
3. **新規**：日誌每日檔每條一行、結論只連過去（[user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)）；wf-lint 改可選。

