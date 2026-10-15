# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **10-15 主題重排＋fsm 補細則**（[thinking 10-15](../proto8/thinking/2026-10-15-topics.md)）：NORMS／CONCEPTS 分檔改按主題（設計理念含時空暫定、總則、基礎設施含組合子 tasks＋fsm、kernel、agent），入口有條號 → 檔表；N-35～N-41 修字、fsm 補第一拍／error 格／step／結束碼／心跳（Q12 已對齊）。未決：總則與設計理念要不要併、時空歸屬、[待定](../proto8/NORMS/08-待定.md)其餘。
- **10-14 夜收工（明天從 [thinking 15 §44 交接](../proto8/thinking/2026-10-14-json-entry/15-ret與半份JSON.md#44-今晚交接明天從這裡開始) 開始）**：inst／loop／daemon 照 N-12 重做（基礎實作）、N-18～N-34、tasks 讀 stdout 都做完；深夜再定 ret／err 採方案 B（子 loop stdout 丟掉）、半份 JSON 不算（N-12 附註）。**下一步等使用者開口**（候選：aos-fsm 同步版 demo）。
- **proto8（主線）**：細節在 git log、[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[lib README](../proto8/lib/README.md)。PLAN 擱置。**下一步等使用者開口**：他說「先做 demo」但還沒說開始；restart §4 列了他停在半路的幾處。使用者說之後／不做：指定時間跑、Linux 權限、AOS_DIR、非同步啟動、retry／timeout／while／race。圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。
- **proto8 thinking 精簡**：10-12 夜使用者要求 thinking 只留原文整理、決策、結論、未決（規矩見 [user.md](workflows/common/user.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。已刪 13 份 AI 產出、精簡其餘五份（[索引](../proto8/thinking/README.md)）；舊版見 git 22285099。
- **proto8 10-13**：`檔#/位置` 已做（D1；`#/` 統一照檔案系統 D1a）；`_metainfo` 格式自由、inst 的可選 key、通用寫法之後在規範定（D4、D5）；見 [json-path](../proto8/thinking/2026-10-13-json-path.md)。晚上重構拆檔＋tidy，報告 [tidy 10-13](workflows/tidy/reports/2026-10-13-proto8-wf.md)。之後改語音輸入（字可能聽錯，意思不明就確認）。kernel／agent 概念見 [kernel-agent](../proto8/thinking/2026-10-13-kernel-agent.md)，細節等規劃 agent 時說。**下一步等使用者開口。**
- 10-12 清帳（使用者說）：proto7-2 頭腦風暴題（抽屜／選單／32 份文件）忽略、不再追；WAIT_USER 舊帳全清；proto6 不管。10-10 留下的待辦候選屬 proto7-2，不追，原文見 [10-12 封存](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
