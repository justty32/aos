# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **10-15 agent 思考介面＋工具＝inst**（[lib agent.md](../proto8/lib/agent.md)、[thinking 10-15 §5](../proto8/thinking/2026-10-15-topics.md#5-agent-的工具與思考介面)）：`aos_agent_lib.py`（think／tool 兩格的現成格庫，10-15 由 aos_agent.py 改名；設定走 stdin `cfg`，[§6](../proto8/thinking/2026-10-15-topics.md#6-agent-格庫改名設定走-stdin)）、真腦 `aos_brain_openai.py`（只對本機假伺服器測過）與 `aos_brain_ollama.py`（原生 `/api/chat`、num_ctx 4096；10-15 實測 146：gemma3:1b、deepseek-r1:8b 都不支援 tools，[§7](../proto8/thinking/2026-10-15-topics.md#7-試-146-ollama小模型)；qwen2.5:14b 整圈跑通，[§8](../proto8/thinking/2026-10-15-topics.md#8-試-146-ollamaqwen2514b)）；demo/fsm 改用（`python3 proto8/demo/run.py fsm`，假腦）；腦錯每拍重叫已照建議改（last_error 帶原因、連錯 3 次停住）。**146 暫停中，等 ops-notes 的 CPU 保護時段**；open：qwen 帶 tools 時回覆語言亂跳、要不要 system prompt 等使用者定；跑順再升規範；動工自定點見 thinking §5／§6 等使用者看。
- **10-15 主題重排＋fsm 補細則**（[thinking 10-15](../proto8/thinking/2026-10-15-topics.md)）：NORMS／CONCEPTS 分檔改按主題（設計理念含時空暫定、總則、基礎設施含組合子 tasks＋fsm、kernel、agent），入口有條號 → 檔表；N-35～N-41 修字、fsm 補第一拍／error 格／step／結束碼／心跳（Q12 已對齊）。未決：總則與設計理念要不要併、時空歸屬、[待定](../proto8/NORMS/08-待定.md)其餘。
- **proto8（主線）**：細節在 git log、[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[lib README](../proto8/lib/README.md)。PLAN 擱置。**下一步等使用者開口**：他說「先做 demo」但還沒說開始；restart §4 列了他停在半路的幾處。使用者說之後／不做：指定時間跑、Linux 權限、AOS_DIR、非同步啟動、retry／timeout／while／race。圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。
- 已搬走（open 已解）：10-14 收工交棒、10-13 `檔#/位置`／kernel-agent、10-12 thinking 精簡與清帳 → [10-14](session_logs/2026-10/2026-10-14.md)、[10-13](session_logs/2026-10/2026-10-13.md)、[10-12](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
