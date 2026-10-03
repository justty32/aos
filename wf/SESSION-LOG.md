# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 10-03（proto6，分層討論：四條評估線都收齊）：使用者想法的正本在 [aos 分層筆記](../proto6/notes/2026-10-03-aos-layering.md)（最重要原則：操作與協議用 JSON／文字、LLM 可讀；使用者說核心理論已 OK，daemon 與 tick-tock 剩技術選型）。收齊的四份：thread 與程序評估（[thread-vs-process](../proto6/notes/proposals/2026-10-03-thread-vs-process/README.md)，artifact：https://claude.ai/artifact/FCr539iF7dxE9L3nV6hq74 ，它的五題待使用者答）；時空四層推演（[spacetime](../proto6/notes/proposals/2026-10-03-spacetime/README.md)，Fable 起草途中卡死，01～05 由新線改到最新筆記、06／07／README 由 Claude 改寫；結論是沒有方向題，唯一硬衝突是 tick 跑完所有任務才結束）；[astra-spacetime](../proto6/notes/reviews/2026-10-03-astra-spacetime.md)（照最新筆記與 LLM 可讀原則，也沒有新方向題）；[astra-layering](../proto6/notes/reviews/2026-10-03-astra-layering.md)（評的是較早版本，開頭加了註）。使用者已說 kill／restart、訊息交流、權限、agent 細節、管轄範圍與十條技術問題之後再談。
- 10-03（proto6，待使用者挑）：astra 六條線對三份提案另想完了，收斂點、方向題與建議實驗順序見 [astra-alt 總覽](../proto6/notes/reviews/2026-10-03-astra-alt/README.md)；等使用者選先做哪個實驗。
- 10-02（proto6，擱置待使用者想）：停格檔只記未來方向；node（使用者預感 node 概念會消失，tick 與 daemon 都不做 node 模組）；`peers` 先不做；系統級任務怎麼改用 hooks（[清單](../proto6/notes/2026-10-01-tick-system-tasks.md)）；C++11 等 Python POC 玩過再開。各段狀態見 [plan](../proto6/plan/README.md#各段狀態)。
- 10-02（proto6，超標檔）：排除封存後 proto6 還有 15 份、wf 44 份 Markdown 超過 8 KiB；先刪過時內容再考慮拆，見 [astra 結構審查「建議」](../proto6/notes/reviews/2026-10-02-astra/10-structure.md#建議)。
- 09-25（proto5 整理鏈收尾後還開著）：待董事評分 [brief/2026-09-25.md](../brief/2026-09-25.md)、WAIT_USER 40～73；下一輪：`lessons.md`／`catalog.md` 先改 lib 再拆、`agent_access`／`agent_talk`／`kernel_check`／`kernel_ledger` 沒拆、09-24 notes 三份一組的收攏。[→](session_logs/2026-09/2026-09-25.md#2026-09-25)
- 09-22：09-21 ④⑤ 仍在（① backlog 已於 09-24 清光） [→](session_logs/2026-09/2026-09-22.md#2026-09-22)
- 09-21：④ aos-inst 兩題 ⑤ thinking/ 草案 ④ WSL 沒 lms／jq [→](session_logs/2026-09/2026-09-21.md#2026-09-21)
- 09-13：① 試玩 r1 修 ② LLM cpu 下一段 ③ 提醒 compact [→](session_logs/2026-09/2026-09-13.md#2026-09-13)
- 09-09：① kernel v1 缺項等使用者 [→](session_logs/2026-09/2026-09-09.md#2026-09-09)
- 09-06～08：預算、dev 模型、qa、push、proto4-2 等 [→](session_logs/2026-09/2026-09-06.md#2026-09-06)
- 09-05：① 裁決單 ③ 升格裁決 ⑨⑪ 互動台 [→](session_logs/2026-09/2026-09-05.md#2026-09-05)
- 08-28：批 header、decode 層 [→](session_logs/2026-08.md#2026-08-28-拷問)

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
