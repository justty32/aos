# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-21 17:00（公司下班關機，交接給新 session）

1. **授權**：這個 session 是「可隨意 push」，新 session 開頭照 user.md 再問一次。分工：普通工作 opus、簡單與雜活 sonnet、fable 只在使用者點名時用；頂層只跟使用者交流；派出去做事的 agent 先通讀 wf/ 規矩。使用者說「windows不管，反正就是要WSL」。
2. **今天定的**（原話與決定全在 [ideas 10-21](../proto8/thinking/2026-10-21-ideas.md) § 1～§ 9、[plan 10-21](../proto8/thinking/2026-10-21-plan.md)）：aos-exec 收旗標、`.env`、一路往下、JSON `.env` key、AOS_CO，都已經 push；loop、daemon、fsm 照 plan 第 1～3 段改寫，已經 push（c1ffcf4e 為止）。
3. **關機時還沒做完、也沒 commit 的那一輪**（工作目錄裡應該有一批 ` M`）：三支程式改成 `程式 [旗標] 設定檔`（拿掉 `--cfg` 和命令列 XXX），設定檔可寫 `檔#/指標`，`run`／`val` 可以是陣列，daemon 改成經 aos-exec 起子 loop；`$path` 改成字串拼接（開頭是 `#` 就直接接，其他情況補剛好一個 `/`；寫絕對路徑不再整個取代），不做 `$at`；`$ref` 指到資料夾維持報錯。原話要記進 ideas § 9，那個 agent 不一定寫完了。**新 session 先 `git status`、`git diff` 看做到哪，派 opus 接手：補完、在 WSL 跑全套測試、commit、push。**
4. **open**：[WAIT_USER](WAIT_USER.md) 有一條：代定翻案確認，以及 tasks、腦呼叫工具、兩種 kernel 三個方向題；tick（plan 第 4 段）沒做；impls 還沒對齊。使用者留意：`$path` 和 `$ref` 的 `at` 以後可能統一成一個名字，現在先這樣。

## 2026-10-21（公司 Windows，交接給新 session）

1. **授權**：push 照 [user.md](workflows/common/user.md) 規矩，新 session 開頭要再問使用者一次（上個 session 是「可隨意 push」，不沿用）。分工照 user.md 10-20 版：普通工作 opus、簡單與雜活 sonnet、fable 少用；頂層只跟使用者交流；派出去的 agent（雜活除外）先通讀 wf/ 規矩。公司這台：python／wf-lint 走 WSL（`wsl -e bash -lc 'cd /mnt/c/code/mine/simple_tools/aos && …'`），`git add` 加 `-c core.ignorecase=false`（[gotchas](workflows/common/gotchas.md)）。
2. **現況**：現行以 proto8 的 CONCEPTS／NORMS／CONVENTION 為準（proto8-2 已併入，10-16 那套已作廢，舊 lib 在 git aa2fec1f）。指示詞 D1～D15（含 `$path`、`$prefix`、寫法寬容；[ideas 10-20](../proto8/thinking/2026-10-20-ideas.md) § 8）與 daemon 重寫五點（[ideas § 25](../proto8/thinking/2026-10-19-ideas.md)）`proto8/bin` 與 `proto8/impls` 都已做完對齊（impls 10-21 對齊，細節 [session log 10-21](session_logs/2026-10/2026-10-21.md)）。`$fmt` 未決（[ideas 10-20 § 9](../proto8/thinking/2026-10-20-ideas.md)）。tidy 第二輪 7 條已裁定處理完。
3. **open**：[WAIT_USER](WAIT_USER.md) 現為「（無）」；[SESSION-LOG](SESSION-LOG.md) 剩「待照新做法重寫」（兩種 kernel、tasks、tick、`tool_calls`，使用者說之後再說，不主動提）、KISS 批次 2～6 暫停、10-15 等使用者看的幾項。
4. **規矩提醒**：`proto8/impls/` 是使用者自己做的 C／C++ 實作，git 未追蹤——不 add、不刪；備份在 `proto8/impls/backup/`。aos 的程式都不動 PATH，demo／測試由呼叫端自己放。aos-fsm 的 bin 測試在 Windows 直接跑會 WinError 193，要走 WSL。沒有還在跑的子 agent。
