# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> 完成的記日誌 [session_logs](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜介質的概念討論（10-29，進行中，等使用者繼續講）**：已定納入管理靠介質、daemon 手把與狀態窗各拆兩個、投遞／鎖／請求格式要正規化（實作是後續）；再定有順序的投遞另成一層、時間差不處理、回信各自處理、鎖是約定；管線／檔案串流／訊號都不寫進標準；條文已改口（N-43 等）、hub 定薄標準（N-63）；鎖留待實作（原則用 Linux 原子動作）；已定窗跟投遞並列（決定 19）、ctl 與投遞信箱並存是兩套模式由程式設計者定（決定 20）、請求格式／資料夾佈局／流程留待後續規劃（決定 21）；開著：父子交代與組合的分法 → [thinking 10-28 medium](../proto8/thinking/2026-10-28-medium.md)
- **open｜agent 一輪 round 實作完第一版（10-28 晚）**：§ 7 第 0～11 步都做了（aos-parts、endpoint fake／openai、queue、history、compact、act、round、範本 agent-nia、aos-ai spawn 認 parts.json、ask_round 外部接口；第 10 步照設計不用做）；條文 P-23、P-41、P-25、C-61、P-20、P-33、C-52、N-43、N-53、C-25 已加註；代定 1～47 在 agent-round 文末（含「必要的格找不到不退 lib 標準件、報 PartMissing」）；**剩**：等使用者親手試（LiteLLM 真腦、Claude Code 經 aos-mcp 問 agent-nia，見 WAIT_USER）、on_error 讀 endpoint 的 stderr 跟 C-52／P-21「不讀下層 stderr」字面上的緊張等使用者看、`code-map/proto8/12-agent-round.md` 超過 8 KB 待拆、proto8 全套有一案本來就紅（test_topdown_galtxt_a SuggestT.test_before_tree_lists_candidates，沒追） → [thinking 10-28 agent-round](../proto8/thinking/2026-10-28-agent-round.md)、[agent-ops](../proto8/thinking/2026-10-28-agent-ops.md)
- **open｜aos-tools 做完第一版（10-28）**：後續兩件——topdown 的 agent 還照舊掃 `tools/*/_tooldef.json`、沒換成 tools.json；10-26 playground（家機 `~/code/try/playground/agent/`）的 mcp 設定還是舊寫法（給工具資料夾），要改成給 agent 資料夾＋`aos-tools add` → [thinking 10-28 aos-tools § 結論](../proto8/thinking/2026-10-28-aos-tools.md#結論10-28-實作照原則代定可翻案)
- **open｜playground 一步一步重來（10-26 起）**：節點只有 `_entry`→`main.py` 叫 `claude -p`＋經 aos-mcp 接 clock／math／read；aos-hub 10-28 照新方向重寫完（常駐 aos-hub-kernel、`AOS_HUB`、pause／stop、Ctrl-] 只跳出、aos-say／listen 可對 claude／codex 說話，WSL 實跑過）；信箱放進 `.stack/`（使用者「放Stack比較好。」，已改）；等使用者親手試；pi coding agent 沒裝、只有適配表 → [thinking 10-26 playground](../proto8/thinking/2026-10-26-playground.md)、[10-28 hub-kernel](../proto8/thinking/2026-10-28-hub-kernel.md)、[10-28 hub-adapter](../proto8/thinking/2026-10-28-hub-adapter.md)、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
- **open｜10-25 galtxt 由上而下兩隊：都已收線，等使用者想完說他抓到的問題點**（再動之前先問）：兩隊沒做的見 [甲隊 HANDOFF](../proto8/topdown/galtxt-a/HANDOFF.md)、[乙隊 HANDOFF](../proto8/topdown/galtxt-b/HANDOFF.md)；統整頁 https://claude.ai/artifact/9sj3ZkRhK4ZYomb8WeSzrA ；代定清單與今天做了哪些 → [session log 10-25](session_logs/2026-10/2026-10-25.md)
- **open｜10-24 其餘下一步**（代定可翻案）：代定落條文、沙箱殘項（`accept` 跟「純靠 Linux」衝突待使用者，[sandbox S18](../proto8/thinking/2026-10-24-sandbox.md)）、compact 與 P-41 → [session log 10-24](session_logs/2026-10/2026-10-24.md#下一步open)
- **open｜還是草稿的條文**：N-14 窗總則、N-15 鎖、N-16 信箱、N-34 tasks（都沒有實作可對） → [NORMS 待定](../proto8/docs/NORMS/08-待定.md)
- **待照新做法重寫**：還沒做的 tasks、通用 kernel 都是方向題，留給使用者（[plan § 1.2](../proto8/thinking/2026-10-21-plan.md)）；loop／daemon／fsm、tick（9d618174）、腦的工具呼叫（10-23）、LLM kernel（10-24）已做；[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)、[NORMS 待定](../proto8/docs/NORMS/08-待定.md)。
- **open｜LLM kernel 下一步**：`_metainfo` 第二步 → [session log 10-24 § LLM kernel 下一步](session_logs/2026-10/2026-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **open｜agent-dan artifact**：https://claude.ai/artifact/4mhycShcVdr7jJskGWc92V ，agent-dan 改了就跟著更新（使用者 10-23「之後我們慢慢做好，這個artifact也會跟着更新」；改法：Artifact `read` 拿最新版、改完同網址重發）→ [demo README § agent-dan](../proto8/demo/README.md#agent-dan真腦工具10-23)
- **KISS 批次 2～6 暫停**（批次 1 已做完；10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)。
- **10-15 剩的兩個候選題**（只有標題、沒展開過）：對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10-24-intent-context.md)）、規範草稿定稿（NORMS 多數條文還標草稿）→ [10-15](session_logs/2026-10/2026-10-15.md)。其餘 10-15 動工自定點與總原則四條已隨 10-19 刪舊程式作廢或併入現行規範（10-21 清點，使用者同意清掉）。
- **proto8（主線）**導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)、[bin README](../proto8/bin/README.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了他停在半路的幾處。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰（原本的合併腳本 `aos-wt/merge.sh` 10-23 已刪、作廢，照一般 git）。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
