# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> 完成的記日誌 [session_logs](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜`AOS_BRAIN_*` 改放哪**：使用者「AOS_BRAIN_URL，我不喜歡這個環境變數」「我再想想」 → [aos-agent 06/03](../proto8/thinking/2026-11/04/aos-agent/06-衝突與方向題/03-新題-tools-llm.md)
- **open｜tidy 收斂（11-03 晚起）**：批次與狀態 → [報告](workflows/tidy/reports/2026-11-03-收斂.md)；剩 P1-2、P1-3（NORMS）、P2 尾巴、P3 的 C-52／C-54（[05](workflows/tidy/reports/2026-11-03-收斂/05-11-04晚-P2-P3-P4續.md)）
- **open｜介質**：實作八步已做；agent 的輸入是 queue、接單後放 tools（決定 32）那兩題先擱著 → [10-28 medium](../proto8/thinking/2026-10/28/medium/README.md)、[medium-plan § 實作時代定](../proto8/thinking/2026-10/29/medium-plan/README.md#實作時代定10-29隊長與工人照原則定的細節可翻案)
- **open｜現況地圖十一點**：剩第 1 點（plan 9 式檔案串流）、第 7 點（post／lock 補指令），使用者「之後有遇到再說」 → [map-review § 結論](../proto8/thinking/2026-10/30/map-review/README.md#結論10-31-補)
- **open｜playground／eca**：開著停著改 history 再繼續（[eca § 之後再改](../proto8/thinking/2026-10/30/eca/09-方向題.md#之後再改停著時改-history-再繼續10-30使用者先記下)）、pi coding agent 只有適配表 → [playground](../proto8/thinking/2026-10/26/playground.md)、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
- **open｜固定名字判準（C-51 10-31 加註）**：使用者尚有後續想法 → [eca § 10-31 原則](../proto8/thinking/2026-10/30/eca/10-10-31-使用者原文-turn-的定義檔只認固.md#10-31-使用者原則固定名字可以但限縮範圍判準)
- **open｜10-24 其餘下一步**（代定可翻案）：代定落條文、沙箱 `accept` 跟「純靠 Linux」衝突（[sandbox S18](../proto8/thinking/2026-10/24/sandbox/README.md)）、compact 與 P-41 → [10-24](session_logs/2026-10-parts/12-10-24.md#下一步open)
- **open｜還是草稿的條文**：N-34 tasks → [NORMS 待定](../proto8/docs/NORMS/08-待定.md)；tasks、seq、if 之後順便做 → [aos-round § 10-31](../proto8/thinking/2026-10/30/aos-round/README.md#10-31-使用者想法控制流不拉-seqif-拼整合成單檔tasksseqif-之後順便做先記之後處理)
- **待照新做法重寫**：tasks、通用 kernel（10-30 停滯） → [plan § 1.2](../proto8/thinking/2026-10/21/plan/README.md)、[rewrite-order](../proto8/thinking/2026-10/19/rewrite-order.md)
- **open｜LLM kernel 下一步**：`_metainfo` 第二步 → [10-24 § LLM kernel 下一步](session_logs/2026-10-parts/12-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **KISS 批次 2～6 暫停**（10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10-parts/03-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)
- **10-15 剩的兩個候選題**：對話太長（可用做法 [intent-context](../proto8/thinking/2026-10/24/intent-context/README.md)）、規範草稿定稿 → [10-15](session_logs/2026-10-parts/03-10-15.md#2026-10-15)
- 導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)；[restart](../proto8/thinking/2026-10/11/restart/README.md) §4 列了停在半路的幾處。10-09 約定：對使用者一律 ELI5、`proto7/user-advice.md` 不碰（[10-09](session_logs/2026-10-parts/01-10-02至10-09.md#2026-10-09)）。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
