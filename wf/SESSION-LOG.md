# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **2026-09-23（公司 WSL）：proto5 重架構 daemon→kernel→cpu，三份新規範四輪審查定稿、實作進行中**——使用者早上定方向：**cpu 範式**（一個家一個主人、`info`／`state`／`requests`／`responses`、規則一軟性、JSON-RPC 2.0、pipe 只管生死、所有 request 都是 aos-exec、params＝aos-exec 的 argv、kernel 也是一格一格的 exec、daemon 有 `restart`、cpu 的環境＝工作的環境）→ 我寫 [spec/cpu.md](../proto5/spec/cpu.md)、[kernel.md](../proto5/spec/kernel.md)、[daemon.md](../proto5/spec/daemon.md)，codex astra 唯讀審四輪（機制三輪＋措辭一輪，任務書與報告在 [notes/2026-09-23-rearch/](../proto5/notes/2026-09-23-rearch/README.md)），每輪改完 commit；使用者看過三份 §10「我自己選的」33 條全 OK。**下午**派 astra（bypass）照三份實作（任務書 scratchpad `impl-task.md`：四段——範式共用＋exec cpu＋`aos_client`／daemon／kernel／端到端＋文件；不動 `aos_cpu`／llm／tool cpu／agent；`aos_exec` 只加 `run_target_full`），16:33 收尾。同時開兩個 agent：清 [proto5/backlog](../proto5/backlog/README.md)（結論在 notes/2026-09-23-rearch/backlog-cleanup.md）、草擬 agent 線三份新規範（[aos-llm-call.md](../proto5/spec/aos-llm-call.md)、agent.md、aos-agent.md 重寫，程式還沒跟）。**open**：① 實作收到哪一段看當天最後一個 commit 訊息，沒做完的段落明天讓 astra 從工作樹接著做（任務書同一份）；② 規範換血：刪舊十份（run／daemon／kernel／cpu-queue／aos-cpu／llm-cpu／tool-cpu）、proto5 README 規範表換新、三份標頭「草稿」拿掉；③ [aos-exec.md](../proto5/spec/aos-exec.md) 兩處要改（`run_target` 回 `timed_out`、「缺檔之後出現會自然跑」「反覆交給 aos-run」過時）等使用者點頭；④ agent 線三份草稿要使用者看、再重寫 `aos_agent.py`，之後才能刪 `aos_cpu`／`aos_llm_cpu`／`aos_tool_cpu`；⑤ LM Studio 真跑一條龍；⑥ code map 先不補（使用者說的）。

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
