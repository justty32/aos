# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 09-24：**已推 main**（細節見 [session_logs 09-24](session_logs/2026-09.md#2026-09-24)）：fix-r4／fix-r5、tidy、spec 拆檔、proto5-2 併回 proto5、四份提案裁決（H／I／J／tools-base）、N／P／K／M／O／L 六案、tool-era 第一波（T1 共用格式／T3／L2／S 收尾）、T4 記憶與紀錄。**晚三後合併鏈**（都已推）：T2 郵差心跳（team_say、郵差兼書記、驗收員、心跳；規範 post／verify／beat）→T4 追加（封存改機械摘要每段 ≤8 KB、自動壓縮預設開上限 32000、events／usage 滿 10 MB 輪換留 3）→K2 停車＋喚醒（agent 閒置／等回音退 102 停車，kernel 出貨後叫醒，`aos-kernel wake`，`park_ms` 預設 300000，status／教程 02 補 102）→T2 追加（郵差間隔 `post.interval_s` 預設 5 秒、心跳用保留身分 `beat`、once、檢查器壞不扣次數、例行完成不寄 DONE）。測試 **72 檔 2068 條**（全綠）。**使用者裁決**：A.21～A.31 全案照預設／裁決；K2 五題新裁（A.32，照預設）。**還在跑**：P 隊（開機合一、家不合一、kernel 帳本換 sqlite，報告在 `proto5/notes/2026-09-24-one-boot/`）、T5 收尾隊（score、人格、routes、README、教程 08、真跑例子 1～3、試玩）。**open**：① 試玩 r5 八條痛點待 fix-r6 ② token 用量／計費留新版 aos-agent 再做 ③ [WAIT_USER](WAIT_USER.md) A.14／A.15／A.19／A.20 ④ 使用者打遊戲中：不碰 LM Studio／ollama，走 LiteLLM；agent 無上限；每 commit 直接 push；頂層只派隊＋ff-merge＋push；codex 現況只剩 gpt-6-astra。[→](session_logs/2026-09.md#2026-09-24)
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
