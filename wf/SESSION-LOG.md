# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜回家第一件事**：家裡那台的 aos clone 是改寫前的舊歷史（10-22 已把公司帳號 commit 改寫並強推，新 main 2cd76e2d，對照表 [hashmap](session_logs/2026-10/2026-10-22-author-rewrite-hashmap.csv)）——先 `git fetch` 然後 `git reset --hard origin/main`，**不要 pull/merge**（會把舊歷史併回來），未追蹤的 proto8/impls 不受影響；上層 simple_tools 也要 pull（gitlink 已更新到 2cd76e2d，commit 7ecd5309）。接著 impls 要同步 10-22 bin 版的小毛病修正（060a99b3 改寫後對應新 hash 請查對照表；fsm USAGE 補 `[旗標]` 等；impls 照 10-22 .env 改：格式基礎子集、預設不蓋、`--dotenv-override`，見 [ideas 10-22 § 3](../proto8/thinking/2026-10-22-ideas.md#3-env-基礎子集與---dotenv-override10-22)），10-22 起凡要碰 impls 的事都等回家 → [10-22](session_logs/2026-10/2026-10-22.md#使用者-10-22-裁定)
- **open｜回家照 impls 補錯誤代號**：使用者 10-22「錯誤訊息多代號也遵循」，bin 版錯誤一行要照 impls 加代號；追蹤檔查不齊代號清單，整條暫停 → [10-22](session_logs/2026-10/2026-10-22.md#python-版-aos-inst-刪寬鬆度照-c錯誤代號暫停10-22opus)
- **open**：10-21 晚教學發現 4 點（fsm 檔頭過時等）維持原樣 → [10-21](session_logs/2026-10/2026-10-21.md)
- **待照新做法重寫**：loop／daemon／fsm、tick 已照 10-21 計畫改寫（[plan](../proto8/thinking/2026-10-21-plan.md)；tick 是第 4 段，commit 9d618174，代定見 [session log 10-21](session_logs/2026-10/2026-10-21.md#使用者不在時代定aos-tick計畫第-4-段10-21-晚)）；還沒做的：tasks、腦的工具呼叫（`tool_calls`）、兩種 kernel——三項都是方向題，留給使用者（plan § 1.2）；[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)、[NORMS 待定](../proto8/NORMS/08-待定.md)。
- **KISS 批次 2～6 暫停**（批次 1 已做完；10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)。
- **10-15 剩的兩個候選題**（只有標題、沒展開過）：對話太長、規範草稿定稿（NORMS 多數條文還標草稿）（原第三題「標準實作」10-21 晚使用者定了說法，見 [N-18](../proto8/NORMS/01-總則.md)）→ [10-15](session_logs/2026-10/2026-10-15.md)。其餘 10-15 動工自定點與總原則四條已隨 10-19 刪舊程式作廢或併入現行規範（10-21 清點，使用者同意清掉）。
- **proto8（主線）**導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[bin README](../proto8/bin/README.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了他停在半路的幾處。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
