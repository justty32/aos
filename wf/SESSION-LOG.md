# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> 完成的記日誌 [session_logs](session_logs/README.md)，寫法見 [user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **open｜整體瘦身：候選已先封存（11-03 晚）**：使用者「瘦身...這些你提到的，其實都是我有一個模糊的概念，然後就交給AI生成了，整個都需要重新手修一遍，所以說瘦身嗎...也不盡然，或者說可以先封存，等之後我們進展到那塊的時候可以拉出來看看。」→ demo/llm-kernel、demo/self-improve（連 lib/aos/try_run）、nvim 外掛、Lua／Janet agent_dan 範例、aos-chat 封存到 `proto8/archive/`（[索引](../proto8/archive/README.md)），demo/agent-fay 刪（使用者「我沒聽過這東西，刪掉。」）；**剩**：`aos_ws.loop_state` 沒封存（extras/ai_tools 的 aos-ai status 還在用），待使用者看要不要連那邊一起動 → [02 § 整體要瘦身](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#整體要瘦身11-01-晚使用者定方向明天再說)
- **open｜公司 WSL 試驗場 `agents/amy` 待刪**（11-02 晚頂層問 amy 要不要留，使用者：「刪掉」；只在公司 WSL `~/code/playground`、不在 git，回公司時刪資料夾即可；11-01 晚「整個都怪怪」不再追）
- **open｜介質：規劃已照「都照建議」定案、條文已落、實作八步做完（10-29）**（10-30 晚回信改走 `reply_to`、重複的代號與信號產生法下放 aos-util 也做了，見實作時代定 14、15），剩：10-29 傍晚又定 agent 的輸入是 queue、接單以後放 tools（agent 做完事自己用 tool 看信箱，決定 32），晚上在試驗場做了最小版（見下 playground 條），看完後兩個使用場景都用不到看信箱、那兩題先擱著 → [10-28 medium 決定 32](../proto8/thinking/2026-10-28-medium.md)、 [thinking 10-29 medium-plan § 實作時代定](../proto8/thinking/2026-10-29-medium-plan.md#實作時代定10-29隊長與工人照原則定的細節可翻案)
- **open｜使用者看現況地圖後的十一點（10-30）**：只剩第 1 點（plan 9 式檔案串流）、第 7 點（post／lock 補指令）開著（使用者「之後有遇到再說」），其餘已做／已定，逐點去向見 → [map-review § 結論](../proto8/thinking/2026-10-30-map-review.md#結論10-31-補)
- **open｜playground（10-26 起）**：aos-hub 10-30 改做 aos-eca-hub（11-03 改名 aos-eca-ctl（同日再改 aos-eca）；建在 aos-daemon 上、`AOS_HUB` 退場），試驗場四隻（bob-1、bob-2、nia-idle、dan-pause）在 WSL `~/code/playground/` 建好、假 CLI 跑過；家機 `~/code/playground` 11-02 晚重建後補 `agents/eca_bob`＋用 `daemons/main` 當 hub 的 daemon（真的 `claude -p`〔haiku〕跑過非互動部分、清回起始狀態），`open` 畫面那段使用者 11-02 晚親手玩完（「好了，我玩完了，體驗不錯。」）；開著：停著改 history 再繼續（外部 agent 要 aos-eca-turn 重開 session，→ [eca § 之後再改](../proto8/thinking/2026-10-30-eca.md#之後再改停著時改-history-再繼續10-30使用者先記下)）、aos-eca-turn 定義檔只認固定名字（10-31 使用者判準：現階段維持固定，→ [eca § 10-31](../proto8/thinking/2026-10-30-eca.md#10-31-使用者原文turn-的定義檔只認固定名字先記之後處理)）、pi coding agent 沒裝只有適配表；aos-round 10-30 晚做完（第 1～7 步；第 8 步只記不做）（queue 空的停法 11-01 已改 argv `aos-round --on-empty`，A 題 → [parts-round](../proto8/thinking/2026-10-31-parts-round.md#決定11-01-使用者)），agent-nia 經 aos-round 接真腦 10-30 晚頂層代跑過了（`aos_ws.py` 失敗判法 11-02 已改）→ [thinking 10-30 aos-round](../proto8/thinking/2026-10-30-aos-round.md) → [thinking 10-30 eca](../proto8/thinking/2026-10-30-eca.md)、[thinking 10-26 playground](../proto8/thinking/2026-10-26-playground.md)、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
- **open｜固定名字判準（C-51 10-31 加註）：使用者尚有後續想法待追究** → [eca § 10-31 原則](../proto8/thinking/2026-10-30-eca.md#10-31-使用者原則固定名字可以但限縮範圍判準)
- **open｜10-24 其餘下一步**（代定可翻案）：代定落條文、沙箱殘項（`accept` 跟「純靠 Linux」衝突待使用者，[sandbox S18](../proto8/thinking/2026-10-24-sandbox.md)）、compact 與 P-41 → [session log 10-24](session_logs/2026-10-parts/12-10-24.md#下一步open)
- **open｜還是草稿的條文**：N-34 tasks（沒有實作可對；N-14 窗總則、N-15 鎖、N-16 信箱 10-29 介質實作後已定） → [NORMS 待定](../proto8/docs/NORMS/08-待定.md)；使用者 10-31：tasks、seq、if 之後順便做；單檔整合指 round、先單體按需析出的方針已記 → [aos-round § 10-31](../proto8/thinking/2026-10-30-aos-round.md#10-31-使用者想法控制流不拉-seqif-拼整合成單檔tasksseqif-之後順便做先記之後處理)
- **待照新做法重寫**：還沒做的 tasks、通用 kernel 停滯（10-30）（[plan § 1.2](../proto8/thinking/2026-10-21-plan.md)）；loop／daemon／fsm、tick（9d618174）、腦的工具呼叫（10-23）、LLM kernel（10-24）已做；[rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)、[NORMS 待定](../proto8/docs/NORMS/08-待定.md)。
- **open｜LLM kernel 下一步**：`_metainfo` 第二步 → [session log 10-24 § LLM kernel 下一步](session_logs/2026-10-parts/12-10-24.md#llm-kernel-下一步從-session-log-逐字搬來)
- **KISS 批次 2～6 暫停**（批次 1 已做完；10-16 使用者撤回「都照推薦」）→ [10-15 § KISS 批次 1](session_logs/2026-10-parts/03-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)。
- **10-15 剩的兩個候選題**（只有標題、沒展開過）：對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10-24-intent-context.md)）、規範草稿定稿（NORMS 多數條文還標草稿）→ [10-15](session_logs/2026-10-parts/03-10-15.md#2026-10-15)。其餘 10-15 動工自定點與總原則四條已隨 10-19 刪舊程式作廢或併入現行規範（10-21 清點，使用者同意清掉）。
- **proto8（主線）**導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)、[bin README](../proto8/bin/README.md)；[restart](../proto8/thinking/2026-10-11-restart.md) §4 列了他停在半路的幾處。
- 10-09 留下的約定（全文 [→](session_logs/2026-10-parts/01-10-02至10-09.md#2026-10-09)）：對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰（原本的合併腳本 `aos-wt/merge.sh` 10-23 已刪、作廢，照一般 git）。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
