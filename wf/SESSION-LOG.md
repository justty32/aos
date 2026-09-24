# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 09-24：已推 main（一句帶過，細節見 git log／session_logs）：fix-r4（13 條 CLI 改版）、tidy、spec 拆檔（九份→86 小檔，[spec 導航](../proto5/spec/README.md)）、proto5-2 規範草稿、kernel C-7／C-8 崩潰窗口測試（程式不用改）、fix-r5（r4 八條，1153 條綠）。open：① **試玩 r5 還沒開**（fix-r5 之後，Opus＋astra 只拿 README 玩，LiteLLM deepseek-chat；任務書照 [r4 任務書](../proto5/notes/play/2026-09-24-r4-task.md) 改；重點驗新指令 `--target`／`listen`／`pause`／`continue --all`／`check --probe`／health 三階段）② proto5-2 池表／宣告式 daemon：規範草稿在 proto5-2/，使用者 09-24 說規模三題先不動（A.19 的 1～3），其餘六題仍等拍，未實作 ③ [WAIT_USER](WAIT_USER.md) A.14、A.15、A.19（六題）、A.20（新）④ `tools`／`init --template` 還沒做 ⑤ fix-r5 沒做的三小件（路徑 shell quoting、`--wait`／`--follow` 沒印回話時間、不帶 `--wait` 的 `say` 在 K 壞時不警告）⑥ 使用者打遊戲中：不碰 LM Studio／ollama，真跑走 LiteLLM localhost:4000 `deepseek-chat`；agent 無上限；每 commit 直接 push；頂層只派隊＋ff-merge＋push，其他一律派 agent。[→](session_logs/2026-09.md#2026-09-24)
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
