# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **2026-09-24（家裡 Manjaro）：proto5 重架構收線＋agent 線規範三輪審查**——cli 補執行位元（WSL 那邊 644）；規範換血（刪 8 份舊、README 表新）；astra 審實作→T5 修（SpawnFailed／控制 pipe 驗信封／cpu 家半成品補齊、新 CLI `aos-daemon stop`／`aos-kernel ack`／`init --cpu`／`ls` 摘要、883→917 綠）；LM Studio gemma 真跑一條龍兩回都通（[lmstudio-run](../proto5/notes/2026-09-23-rearch/lmstudio-run.md)）；使用者拍三件（同步工具全拿掉、`aos-agent start`＝進現有池、llm.json 放 llm cpu 家）→ agent 線三份改三輪、astra 審三輪（[rearch notes](../proto5/notes/2026-09-23-rearch/README.md)）。**open**：① agent 線第 4 輪（最後 3 條）改完標定稿→派隊重寫 `aos_agent.py`（照 agent.md／aos-agent.md／aos-llm-call.md），落地後刪 `aos_cpu`／`aos_llm_cpu`／`aos_tool_cpu`／`aos_llm_ask` 與四份舊 spec；② 實作審查跳過的崩潰窗口測試 C-2／C-3／C-7／C-8（[impl-fix-round1](../proto5/notes/2026-09-23-rearch/impl-fix-round1.md)）；③ [WAIT_USER](WAIT_USER.md) A.14 六題；④ 日常 CLI（`init <template>`／`say`／`pause`／`continue`／`tools`，[thinking/aos-agent.md](../thinking/aos-agent.md)）還沒做。

- 09-22：① backlog 八件 ② 09-21 ④⑤ 仍在 [→](session_logs/2026-09.md#2026-09-22)
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
