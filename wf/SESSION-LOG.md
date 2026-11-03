# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> 完成的記日誌 [session_logs](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜tidy 收斂（11-03 晚起）**：批次與狀態 → [報告](workflows/tidy/reports/2026-11-03-收斂.md)；P4-D／E 半成品在分支 `tidy-p4-wip`
- **open｜aos-post 改版**：步驟 1～8 在分支 `aos-post-rework`，剩 9 條文加註、10 收尾驗證後併 main → [thinking](../proto8/thinking/2026-11-03-aos-post.md)
- **open｜公司 WSL 試驗場 `agents/amy` 待刪**（使用者「刪掉」；不在 git，回公司刪資料夾）
- **open｜介質**：實作八步已做；agent 的輸入是 queue、接單後放 tools（決定 32）那兩題先擱著 → [10-28 medium](../proto8/thinking/2026-10-28-medium.md)、[medium-plan § 實作時代定](../proto8/thinking/2026-10-29-medium-plan.md#實作時代定10-29隊長與工人照原則定的細節可翻案)
- **open｜現況地圖十一點**：剩第 1 點（plan 9 式檔案串流）、第 7 點（post／lock 補指令），使用者「之後有遇到再說」 → [map-review § 結論](../proto8/thinking/2026-10-30-map-review.md#結論10-31-補)
- **open｜playground／eca**：開著停著改 history 再繼續（[eca § 之後再改](../proto8/thinking/2026-10-30-eca.md#之後再改停著時改-history-再繼續10-30使用者先記下)）、aos-eca-turn 定義檔只認固定名字（[eca § 10-31](../proto8/thinking/2026-10-30-eca.md#10-31-使用者原文turn-的定義檔只認固定名字先記之後處理)）、pi coding agent 只有適配表 → [playground](../proto8/thinking/2026-10-26-playground.md)、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
- **open｜固定名字判準（C-51 10-31 加註）**：使用者尚有後續想法 → [eca § 10-31 原則](../proto8/thinking/2026-10-30-eca.md#10-31-使用者原則固定名字可以但限縮範圍判準)
- **open｜10-24 其餘下一步**（代定可翻案）：代定落條文、沙箱 `accept` 跟「純靠 Linux」衝突（[sandbox S18](../proto8/thinking/2026-10-24-sandbox.md)）、compact 與 P-41 → [10-24](session_logs/2026-10-parts/12-10-24.md#下一步open)
- **open｜round 那套 agent 已刪，以下條文沒實作對應，待收斂時給使用者看**（11-03 晚使用者「一起刪」；條文文字沒改，概念在 proto8/archive/agent-round-concepts/）：NORMS [01-總則](../proto8/docs/NORMS/01-總則.md) 10-30「10 是對直接收到它的那層說的」（例子出自 round）、10-28 補「錯誤分類靠 stderr 代號」（引 agent-round § 4 endpoint）；[07-組合子](../proto8/docs/NORMS/07-基礎設施-組合子.md) N-36 分岔與「trace 加 next」（出處 aos-round；trace 11-03 已拿掉）；[08-待定](../proto8/docs/NORMS/08-待定.md)【agent】「agent 的一輪（round）與各格」（整條）；[10-定義與工作區](../proto8/docs/NORMS/10-基礎設施-定義與工作區.md) 10-28「一格一次用 aos-loop、一輪用 round，看 `_entry`」（整條）；CONVENTION [06-巢狀](../proto8/docs/CONVENTION/06-巢狀.md) 10-28「round 與每一格拿 agent 資料夾絕對路徑當第一個參數」（整條）、10-30「接住的 10 到不了 loop」（例子是 aos-round）；[02-題目stack停錯腦](../proto8/docs/CONVENTION/02-題目stack停錯腦.md) 10-30「用 aos-round 的 agent，表上沒接住時才是預設停」、10-28 起「預設停」、「endpoint 是 aos 函數」、「格也走註冊檔」、「腦拆成格、history 只有 compact 可以改寫」（這四條是 round 那套的設計）
- **open｜還是草稿的條文**：N-34 tasks → [NORMS 待定](../proto8/docs/NORMS/08-待定.md)；tasks、seq、if 之後順便做 → [aos-round § 10-31](../proto8/thinking/2026-10-30-aos-round.md#10-31-使用者想法控制流不拉-seqif-拼整合成單檔tasksseqif-之後順便做先記之後處理)
- **待照新做法重寫**：tasks、通用 kernel（10-30 停滯） → [plan § 1.2](../proto8/thinking/2026-10-21-plan.md)、[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)
- **open｜LLM kernel 下一步**：`_metainfo` 第二步 → [10-24 § LLM kernel 下一步](session_logs/2026-10-parts/12-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **KISS 批次 2～6 暫停**（10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10-parts/03-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)
- **10-15 剩的兩個候選題**：對話太長（可用做法 [intent-context](../proto8/thinking/2026-10-24-intent-context.md)）、規範草稿定稿 → [10-15](session_logs/2026-10-parts/03-10-15.md#2026-10-15)
- 導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了停在半路的幾處。10-09 約定：對使用者一律 ELI5、`proto7/user-advice.md` 不碰（[10-09](session_logs/2026-10-parts/01-10-02至10-09.md#2026-10-09)）。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
