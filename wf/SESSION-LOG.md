# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 09-24：**已推 main**（一句帶過，細節見 session_logs）：fix-r4／fix-r5、tidy、spec 拆檔、proto5-2 池表規範草稿、daemon／kernel 崩潰窗口測試、advice-r1 A／B、r5 試玩、tools-base、listen 微調、talk REPL、H／I／J 三提案、N／M／K／O／P／L 六案（cli-agents、工具大開發、agent 不空轉、cli-agents 階 0、daemon-split-review、權限牆）、C 隊 proto5-2 池式實作併回 main。**晚二後合併鏈**（都已推）：T1 共用格式→T3（files／wf 工具＋aos-json／aos-directives）→L2（權限牆四點：檔案工具根＝整個 `/work`、NoAccess 拒跑、init 生預設 access.json）→T1 其餘（aos-team init/start/stop/ls/rm、門房、task/wait/answer）→S（proto5-2 納入 proto5＋拆檔＋tidy）→T1 追加 `rm --purge`→T4（記憶與紀錄：events／context／compact／notes、`aos-agent context/compact/events/history --archive/notes`、自動壓縮、`init --template` 接上）。測試 40 檔 1366→**63 檔 1867 條**（全綠）。**使用者裁決**：H／I／J／tools-base 照預設（A.21）；N／P／K／M／O／L 六批照裁決（A.22～A.27，L 兩題改現況）；C 隊五題代裁（A.28）；晚二四案裁決（A.29：L2／T3／T1／S，詳見 WAIT_USER）。**還在跑未合**：T2（郵差心跳）、K2（閒置停車＋喚醒）。**之後**：T5 收尾、開機合一＋帳本換 sqlite、cli-agents stage 1、fix-r6。**open**：① 試玩 r5 八條痛點待 fix-r6 ② 工具大開發：T2／K2 跑中，T5 收尾最後 ③ token 用量／計費留給新版 aos-agent 再做 ④ [WAIT_USER](WAIT_USER.md) A.14／A.15／A.19／A.20／A.28／A.30 ⑤ 使用者打遊戲中：不碰 LM Studio／ollama，走 LiteLLM；agent 無上限；每 commit 直接 push；頂層只派隊＋ff-merge＋push；codex 現況只剩 gpt-6-astra。[→](session_logs/2026-09.md#2026-09-24)
- 09-22：09-21 ④⑤ 仍在（① backlog 已於 09-24 清光） [→](session_logs/2026-09.md#2026-09-22)
- 09-21：④ aos-inst 兩題 ⑤ thinking/ 草案 ④ WSL 沒 lms／jq [→](session_logs/2026-09.md#2026-09-21)
- 09-13：① 試玩 r1 修 ② LLM cpu 下一段 ③ 提醒 compact [→](session_logs/2026-09.md#2026-09-13)
- 09-09：① kernel v1 缺項等使用者 [→](session_logs/2026-09.md#2026-09-09)
- 09-06～08：預算、dev 模型、qa、push、proto4-2 等 [→](session_logs/2026-09.md#2026-09-06)
- 09-05：① 裁決單 ③ 升格裁決 ⑨⑪ 互動台 [→](session_logs/2026-09.md#2026-09-05)
- 08-28：批 header、decode 層 [→](session_logs/2026-08.md#2026-08-28-拷問)

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
