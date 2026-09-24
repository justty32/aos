# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **2026-09-24（家裡 Manjaro）：proto5 重架構收線→agent 線定稿實作→試玩 r1～r4 四輪**——細節見 git log 與 [rearch notes](../proto5/notes/2026-09-23-rearch/README.md)、[play](../proto5/notes/play/README.md)。今日已推 main 多筆（fix-r3、3.12 實跑、daemon 崩潰窗口測試、r4 試玩）。**使用者打遊戲中不碰 LM Studio／ollama，走 LiteLLM；每 commit 直接 push。****open**：① **fix-r4** 十三條 CLI 改版在 worktree 跑中，收線後核署名、ff-merge、推。② **fix-r5**（r4 兩份共同痛點八條）待 fix-r4 合完再開。③ **cpu 動態增減（使用者 09-24 拍板，spec 拆檔後與 fix-r5 一起開）**：kernel 將來上千上萬顆 cpu、很多池，init 綁死 cpu 表不對。介面定案：`aos-kernel cpu add [--target K] --pool P [--count N] [--name X] [--env K=V]`（kernel 每格重讀 info，下一格叫 daemon 拉起，不用 boot）、`cpu rm NAME|--pool P --count N`（先收孩子再拿掉表）、`cpu ls` 與 `ls` 預設按池摘要（幾顆／忙／dead），`--pool P` 才展開；envs 掛在池上、入池的 cpu 繼承；`init --config` 只剩 kernel 參數＋池定義，cpu 可空。**一個池一個 daemon**（daemon.md、kernel.md 的 cpu 表要記池→daemon 家）。每格成本要從 O(cpu 數) 變 O(有事的 cpu 數)（例如 cpu 回音時往 kernel 家丟通知檔）。④ **spec 拆檔重構**：`proto5/spec/` 過大待拆，等 fix-r4 合完才開，拆完才開 fix-r5。⑤ 崩潰窗口 C-7／C-8 還沒補。⑥ [WAIT_USER](WAIT_USER.md) A.14＋A.15。⑦ `tools`／`init --template` 還沒做。

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
