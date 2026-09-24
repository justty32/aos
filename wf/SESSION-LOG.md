# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 09-24：**已推 main**（細節見 [session_logs 09-24](session_logs/2026-09.md#2026-09-24)）：fix-r4／fix-r5、tidy、spec 拆檔、proto5-2 併回 proto5、四份提案裁決（H／I／J／tools-base）、N／P／K／M／O／L 六案、tool-era 第一波（T1／T3／L2／S）、T4 記憶、T2 郵差心跳、K2 停車喚醒。**晚四後合併鏈**（都已推）：P 隊 one-boot（`aos up`／`aos down`、kernel cpu 拿掉、kernel 帳本換 sqlite、`aos-kernel proc`、`ls --json` 第 3 版）→試玩 5/4/4/4/4→P 追加試玩七件→T5 收尾（score、人格定稿、routes、教程 08、真跑例子 1～3、試玩兩輪）→P 修 test_kernel_recovery 偶發→第二波 A 隊（造工具 tools new／test／wrap-py、wf_fill、importer 模板、route try；astra 必修 12 修 12）→T2 修 test_team_beat 偶發（測試端）→第二波 B 隊（牆接線：門房 tool 規則與驗收員關牢、cmd_ok、逃逸測試 19 條全擋，`spec/team/wall.md`）→第二波 C 隊（申請類：`T-lock`／`T-access-req`／`T-persona`／`_pool`、`routine_propose`、`aos-agent persona show/set/append`、審查子單編號修正、`handoff` 自動補 `wf_lint_strict`；astra 必修 8 修 8，`tool-era/w2c/`）。測試 **86 檔 2370 條**（全綠）。**使用者裁決**：A.21～A.33、A.36 已裁決／已做；A.34（導入預設交給 importer？）、A.35（郵差投信算不算邊界扣分？）、A.37（access_request／persona_propose 借 ask 混進一般問題要不要加前綴？）待裁。**還在跑**：無；第二波三隊全落地，等使用者拍 WAIT_USER 34／35／37 與下一步。**open**：① 試玩 r5 八條痛點待 fix-r6 ② token 用量／計費留新版 aos-agent 再做 ③ [WAIT_USER](WAIT_USER.md) A.14／A.15／A.19／A.20 ④ 使用者打遊戲中：不碰 LM Studio／ollama，走 LiteLLM；agent 無上限；每 commit 直接 push；頂層只派隊＋ff-merge＋push；codex 現況只剩 gpt-6-astra。[→](session_logs/2026-09.md#2026-09-24)
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
