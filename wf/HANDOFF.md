# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-13 23:30 家機收工、換樹前

1. **授權與工作方式**：家機（Manjaro）。使用者原話：「事情盡量交給agent做，普通工作交給opus，簡單工作交給sonnet。agent做事前要讀過wf/規矩，簡單工作除外。」fable 照 user.md「盡量少用」。新題寄使用者專區（`aos-user send`／`user_send`），不再加進 WAIT_USER。頂層是樹外的 Claude Code 或樹裡的 `repo-aos`，看起樹了沒。
2. **現役線**：無（`aos-json-view` 上色那條線若還在跑，先看它有沒有 commit，別碰 `proto8/cmd/aos-json-view/`）。
3. **push**：未 push（使用者說「晚上十一點睡覺前再push。」；數量看 `git log origin/main..main`，若使用者已推，下個 session 會看到 origin/main 跟上）。
4. **換樹**：使用者今晚照桌面手冊換（釘 `54789088d`，預演第六輪 12 段全綠；備份預設在 `~/.aos/saves/tree-swap`）。換後收尾清單在手冊與 [tree-swap-1113](../proto8/thinking/2026-11/13/tree-swap-1113.md)。
5. **下一步**：新 session 先確認樹起來了（沒起就問使用者，起樹由他下）→ 做換後收尾（含專區段 2 的計時器、notify on、door 重建）→ 派線接 5 處 Python `--at`（`directive_value.py`、`cmd/aos-agent/aos_agent/tools.py`、`py/aos_clock_register.py`、`lib/mcp_server_file.py`、`lib/hook_run.py`）→ 接完再換一次樹（連同 `user_verify` 與之後的 lib 改動）。
6. **明天開工**：astra 當 kernel 施工（[astra-kernel-plan](../proto8/thinking/2026-11/13/astra-kernel-plan.md)，Q1～Q8 已裁）、kernel 限資源施工（[kernel-limits-plan](../proto8/thinking/2026-11/13/kernel-limits-plan.md)，K1～K18 已裁）。
7. **wf 搬遷剩**：段 2b SESSION-LOG 轉 json、段 9 收尾（見 [SESSION-LOG](SESSION-LOG.md)）。
8. **段 0 驗**：這次 compact／新 session 讀到這條就算 `compact_reload.sh` 補驗過（驗完補 user/02 那句，見 SESSION-LOG「主 session 接 aos」）。
