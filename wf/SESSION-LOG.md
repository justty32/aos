# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 09-25（晚上，整理鏈收尾）：**main**（WAIT_USER 拆檔→wf 六區拆檔→sandbox 封存→brief 補篇→wf／proto5 兩輪 tidy→proto5/lib 19 支拆母模組＋子模組共 145 支）；astra 唯讀審 lib 拆檔必修 0、建議 4 全採納；lint 前後：wf oversize 61→39、proto5 broken 299→0；全套測試 **2874 條全綠**。待董事：評分 [brief/2026-09-25.md](../brief/2026-09-25.md)、WAIT_USER 40～75（74、75 是新題）。下一輪：`lessons.md`／`catalog.md` 先改 lib 再拆、`agent_access`／`agent_talk`／`kernel_check`／`kernel_ledger` 沒拆、wf 還有超標檔、09-24 notes 三份一組的收攏。[→](session_logs/2026-09/2026-09-25.md#2026-09-25)
- 09-24：**已推 main**：重架構收線→tool-era 三波（第一波 T1/T3/L2/S/T4/T2/K2、P 隊 one-boot、T5 收尾、第二波 A/B/C 造工具＋牆接線＋申請類）全落地，試玩多輪過；A.21～A.39 逐條裁決／代裁。測試 94 檔 2605 條全綠。[→](session_logs/2026-09/2026-09-24.md#2026-09-24)
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
