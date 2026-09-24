# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 09-24：**已推 main**（一句帶過，細節見 git log／session_logs）：fix-r4／fix-r5、tidy、spec 拆檔（九份→86 小檔）、proto5-2 池表／宣告式 daemon 規範草稿、daemon／kernel 崩潰窗口測試；晚上使用者邊試玩邊丟建議（`proto5/advice.md`），先合 advice-r1 A／r5 試玩／advice-r1 B／tools-base／listen 微調／talk REPL／三份提案 H／I／J，晚二再合 N／M／K／O／P／L 六案（cli-agents 提案、工具大開發計畫、agent 不空轉提案、cli-agents 階 0、daemon-split-review、權限牆 access.json＋aos-jail＋tools／access CLI）。測試 40 檔 1366→L 隊落地後 1470。**使用者裁決**：H／I／J／tools-base 照預設（A.21）；N／P／K／M／O／L 六批照裁決（A.22～A.27，L 兩題改現況：檔案工具根改整個 `/work`、無 access.json 的家改拒跑）；C 隊池式實作五題代裁記 A.28；C 隊已合併 main（`ef29b7c`，測試 41 檔 1277 條）。**還在跑未合**：S 隊（proto5-2 納入 proto5＋拆檔＋tidy，Opus，09-24 晚開）、L2（權限牆修前四點）、T1／T3（工具時代第一波）。**open**：① 試玩 r5 八條痛點待 **fix-r6**（併 B 隊九條不符＋G 隊 README 舊字已改）② proto5-2：C 隊已併回 main，S 隊做拆檔重構＋tidy ③ 工具大開發：L 牆已合，T1／T3 已開，T2／T4 等共用格式合進 main 再開、T5 收尾最後 ④ token 用量／計費留給新版 aos-agent 再做 ⑤ [WAIT_USER](WAIT_USER.md) A.14／A.15／A.19／A.20／A.28 ⑥ 使用者打遊戲中：不碰 LM Studio／ollama，真跑走 LiteLLM localhost:4000 `deepseek-chat`；agent 無上限；每 commit 直接 push；頂層只派隊＋ff-merge＋push，其他一律派 agent；codex 現況只剩 gpt-6-astra。[→](session_logs/2026-09.md#2026-09-24)
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
