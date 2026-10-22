# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-21 晚（在家）

1. **授權**：本 session 使用者說「可以隨意 push」，在家。分工：普通工作 opus、簡單雜活 sonnet、fable 只在點名時用；頂層只跟使用者交流；做事的 agent（雜活除外）先通讀 wf/ 規矩。
2. **今晚完成並 push**：aos-tick（9d618174、72e9eb26）；10-21 下午代定 11 條使用者確認（7600357a）；impls 對齊 bin 10-21 全部改動，含 aos-exec 的 `--ws`／`.env`／AOS_CO（impls 未追蹤，備份在 `proto8/impls/backup/2026-10-21-night/`），規範的「impls 尚未對齊」字樣已清（6ee07ce0）；七份 proto8 相關 artifact 已更新到現況。
3. **open**：[WAIT_USER](WAIT_USER.md) 剩三個方向題（tasks、tool_calls、兩種 kernel）＋ aos-tick 8 條代定；待問使用者：impls 要不要補 C++ 版 aos-tick。
4. **注意**：下面 17:00 那條第 3、4 點描述的「tick 沒做、impls 沒對齊」已過時，以本條為準。

## 2026-10-21 17:00（公司下班關機，交接給新 session）

1. **授權**：這個 session 是「可隨意 push」，新 session 開頭照 user.md 再問一次。分工：普通工作 opus、簡單與雜活 sonnet、fable 只在使用者點名時用；頂層只跟使用者交流；派出去做事的 agent 先通讀 wf/ 規矩。使用者說「windows不管，反正就是要WSL」。
2. **今天定的**（原話與決定全在 [ideas 10-21](../proto8/thinking/2026-10-21-ideas.md) § 1～§ 9、[plan 10-21](../proto8/thinking/2026-10-21-plan.md)）：aos-exec 收旗標、`.env`、一路往下、JSON `.env` key、AOS_CO，都已經 push；loop、daemon、fsm 照 plan 第 1～3 段改寫，已經 push（7ea8792c 為止）。
3. **關機時還沒做完、也沒 commit 的那一輪**（工作目錄裡應該有一批 ` M`）：三支程式改成 `程式 [旗標] 設定檔`（拿掉 `--cfg` 和命令列 XXX），設定檔可寫 `檔#/指標`，`run`／`val` 可以是陣列，daemon 改成經 aos-exec 起子 loop；`$path` 改成字串拼接（開頭是 `#` 就直接接，其他情況補剛好一個 `/`；寫絕對路徑不再整個取代），不做 `$at`；`$ref` 指到資料夾維持報錯。原話要記進 ideas § 9，那個 agent 不一定寫完了。**新 session 先 `git status`、`git diff` 看做到哪，派 opus 接手：補完、在 WSL 跑全套測試、commit、push。**
- **opus 停手時的進度（10-21 傍晚）**：其實在收到停手通知前，這一輪已經**全部做完、驗證過、commit 並 push**——commit `0c9ea3da`（接在 0ea2a82e 之後）。已改：三支程式、run／val 陣列、daemon 經 aos-exec、`$path` 字串拼接（不做 `$at`）、`$ref` 指到資料夾維持報錯＋測試；demo；規範與文件（N-11、N-28、N-36、N-45、NORMS/10 開頭第七處差異、C-36、P-05～P-07、P-27、P-31、bin／demo README、code map、plan 加註）；ideas § 9（原話 1～7 逐字、決定 H1～H8、頂層自定 9 點，含使用者留意 `$path` 與 `at` 日後可能統一）、session log 10-21 補一節、WAIT_USER 那條加註。改到一半：無。測試：WSL 上 proto8 213 個全綠、demo/run.sh 三段結果同改前、repo 根 ctest 8/8 綠、wf-lint broken 只剩原本的 1 個；新測試在舊程式上會紅。沒寫進別處的自定點：無（都在 ideas § 9.3 與 session log）。接手第一步：`git pull`，工作目錄應該是乾淨的（除了未追蹤的 impls），上面第 3 點描述的那批 ` M` 已不存在；讀 ideas § 9 跟使用者報告即可。
4. **open**：[WAIT_USER](WAIT_USER.md) 有一條：代定翻案確認，以及 tasks、腦呼叫工具、兩種 kernel 三個方向題；tick（plan 第 4 段）沒做；impls 還沒對齊。使用者留意：`$path` 和 `$ref` 的 `at` 以後可能統一成一個名字，現在先這樣。

