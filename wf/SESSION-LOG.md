# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜10-25 由上而下拆資料夾樹（galtxt 兩隊）**：甲隊 galtxt-a、乙隊 galtxt-b 在各自 worktree 跑（opus 隊長、fable 規劃），使用者一路補的想法都記在 [thinking 10-25 top-down](../proto8/thinking/2026-10-25-top-down.md) 原文段；人評網頁已上、使用者在外暫不評（見 [WAIT_USER](WAIT_USER.md)）；乙隊 B 段已收線（4d59258d）、甲隊第二任在跑。**甲隊收線後**：派 opus 統整兩隊結果做成 artifact（使用者 10-25「差不多了之後，統整這些結果，弄成artifact，eli5風格，圖多，精簡，只講結論，細節折疊，要有流程，資料夾佈局，一些檔案的格式範例」）
- **open｜真腦實測**：自動項已真跑完（[基礎](session_logs/2026-10/2026-10-24-真腦實測/結果-01-基礎.md)、[組合A](session_logs/2026-10/2026-10-24-真腦實測/結果-02-組合A.md)、[組合B](session_logs/2026-10/2026-10-24-真腦實測/結果-02-組合B.md)、[外部](session_logs/2026-10/2026-10-24-真腦實測/結果-03-外部.md)）；剩使用者四項（say/listen、fay attach、nvim、沙箱 root）見 [WAIT_USER](WAIT_USER.md)
- **open｜10-24 其餘下一步**（代定可翻案）：代定落條文、沙箱殘項（`accept` 跟「純靠 Linux」衝突待使用者，[sandbox S18](../proto8/thinking/2026-10-24-sandbox.md)）、compact 與 P-41 → [session log 10-24](session_logs/2026-10/2026-10-24.md#下一步open)
- **open｜還是草稿的條文**：N-14 窗總則、N-15 鎖、N-16 信箱、N-34 tasks（都沒有實作可對） → [NORMS 待定](../proto8/NORMS/08-待定.md)
- **待照新做法重寫**：還沒做的 tasks、通用 kernel 都是方向題，留給使用者（[plan § 1.2](../proto8/thinking/2026-10-21-plan.md)）；loop／daemon／fsm、tick（9d618174）、腦的工具呼叫（10-23）、LLM kernel（10-24）已做；[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)、[NORMS 待定](../proto8/NORMS/08-待定.md)。
- **open｜LLM kernel 下一步**：`_metainfo` 第二步 → [session log 10-24 § LLM kernel 下一步](session_logs/2026-10/2026-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **open｜agent-dan artifact**：https://claude.ai/artifact/4mhycShcVdr7jJskGWc92V ，agent-dan 改了就跟著更新（使用者 10-23「之後我們慢慢做好，這個artifact也會跟着更新」；改法：Artifact `read` 拿最新版、改完同網址重發）→ [demo README § agent-dan](../proto8/demo/README.md#agent-dan真腦工具10-23)
- **KISS 批次 2～6 暫停**（批次 1 已做完；10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)。
- **10-15 剩的兩個候選題**（只有標題、沒展開過）：對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10-24-intent-context.md)）、規範草稿定稿（NORMS 多數條文還標草稿）→ [10-15](session_logs/2026-10/2026-10-15.md)。其餘 10-15 動工自定點與總原則四條已隨 10-19 刪舊程式作廢或併入現行規範（10-21 清點，使用者同意清掉）。
- **proto8（主線）**導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[bin README](../proto8/bin/README.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了他停在半路的幾處。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰（原本的合併腳本 `aos-wt/merge.sh` 10-23 已刪、作廢，照一般 git）。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
