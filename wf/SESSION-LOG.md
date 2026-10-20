# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **impls（C／C++）待對齊 10-20 的 bin 版**：daemon 重寫（[ideas § 25](../proto8/thinking/2026-10-19-ideas.md)，計畫 `proto8/impls/aos-daemon/PLAN-2026-10-19.md`）與指示詞／argv 拍板（[ideas 10-20 D1～D8](../proto8/thinking/2026-10-20-ideas.md)），以及指示詞改版 `$path`／`$prefix`／寫法寬容（同檔 D9～D15；對齊前 demo 在 impls 版跑不動）；bin 版、條文已做完已推（測試 141），impls 只在家中 Manjaro（未追蹤），回家照 [bin README](../proto8/bin/README.md) 10-20 兩段對齊 → [10-20](session_logs/2026-10/2026-10-20.md)。
- **待照新做法重寫**：兩種 kernel、tasks、tick、`tool_calls` 現無實作（舊版 git aa2fec1f），使用者「之後再說」→ 他回到實作前不主動提；[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)、[NORMS 待定](../proto8/NORMS/08-待定.md)。
- **KISS 批次 2～6 暫停**（批次 1 已做完；10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)。
- **10-15 等使用者看**：各 thinking 的「動工自定點」（[llm-kernel](../proto8/thinking/2026-10-15-llm-kernel.md#動工自定點)、[general-kernel](../proto8/thinking/2026-10-15-general-kernel.md#動工自定點)、[json-families](../proto8/thinking/2026-10-15-json-families.md)、[topics/04](../proto8/thinking/2026-10-15-topics/04-agent當函數.md)、[judge-live2](../proto8/thinking/2026-10-15-judge-live2.md)）；open 候選：對話太長、agent 收信、標準實作、規範草稿定稿 → [10-15](session_logs/2026-10/2026-10-15.md)。
- **總原則（10-15）剩的**：[principles](../proto8/thinking/2026-10-15-principles.md#10-15-深夜使用者拍板切乾淨kiss)「自定的小地方」四條等使用者看；工具叫 agent 的寫法留給 inst-exec 稿；「kernel 評估納入錯誤路徑」在 NORMS 待定。
- **proto8（主線）**導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[bin README](../proto8/bin/README.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了他停在半路的幾處。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
