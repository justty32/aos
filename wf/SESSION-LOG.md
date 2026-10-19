# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡，細節看 git log。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔過大就拆進 **`session_logs/`**，按類別拆檔＋index（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔 ① 連各工作流自己的 session-log，② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態＋細節連結**（決策落到該工作流文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即刪。

## 最新進度

- **entry／aos-exec 新規則待落實**（10-19 下班前口述）：[ideas § 14～§ 19](../proto8/thinking/2026-10-19-ideas.md)——entry 四種格式、`aos-exec XXX` 找入口與補 `.json`、`js[$AOS_ENTRY]` 可為字串路徑、有 `argv`＝inst、檔就 cd 到所在資料夾、aos-exec 自己偵測循環、加 `AOS_CF`／`AOS_CD`、`檔#/a/b` 尋址；只記錄，CONCEPTS／NORMS（N-57、N-60、P-28）與 bin/aos-exec 未改，等使用者說動工。
- **待照新做法重寫（10-19 併入後）**：daemon、兩種 kernel、tasks（seq／par／if）、tick、腦的工具呼叫（`tool_calls`）現無實作（舊版在 git aa2fec1f）；概念與規範留著、標「現無實作」；等使用者說要哪個。細節 [NORMS 待定](../proto8/NORMS/08-待定.md)、[session log 10-19 併入](session_logs/2026-10/2026-10-19.md)。fable 排的重寫順序與五題在 [rewrite-order](../proto8/thinking/2026-10-19-rewrite-order.md)；使用者 10-19「這些都是實作細節，之後再說沒關係。我還在高空飛。」→ 擱著，他回到實作前不主動提。
- **KISS 批次 1「純刪」已做完、已推**（10-15 深夜，使用者「C-50 選 a，其他都按照推薦」、PLAN「刪掉」）：彙整總表 1.1～1.18 與 6.10 全做（四個 commit cb20249a、fa6629ee、7d833687、a0c7214d），C-50 改成「一張 inst 是正本」、PLAN 刪、proto8-1 併進 proto8/lib；lib 測試 173→169、ctest 全綠。自定點 8 條在 [10-15 § KISS 批次 1](session_logs/2026-10/2026-10-15.md#kiss-批次-1純刪照做10-15-深夜fable)（最要看的：`aos-demo` 的 AOS_DEMO 留到批次 2）。~~下一步批次 2～6~~ **暫停**（10-16 使用者撤回「都照推薦」，見上一條）。
- **compact 後自動讀回**：`.claude/settings.json` SessionStart(compact) hook → [wf/tools/compact_reload.sh](tools/compact_reload.sh)，交接寫 [HANDOFF](HANDOFF.md)（10-15 深夜）。
- **意見 1～7 程式兩批都做完**（＋格沒輸出、同 frame 續聊、第二批 6 個自定點都已拍板並照做，N-44 新增）；真腦已用本機 LiteLLM 實跑（畫家 demo 見 [paint-live](../proto8/thinking/2026-10-15-paint-live.md)；LM Studio 未跑）→ [10-15 § 拍板](session_logs/2026-10/2026-10-15.md#第二批自定點的拍板10-15使用者派去處理吧都按照推薦45-用主控的推薦)。
- **10-15 收工**：使用者說「先大致到這邊……接下來是我要來做理解」→ 下一步等使用者讀完再開口。今日成果：主題分檔、fsm 規範＋實作、agent（工具＝inst、思考介面、系統提示、函數＋binding、當工具）、C-47／N-42 兩種 kernel 原型、C-48 JSON 規矩＋同像性；五份網頁已更新（https://claude.ai/artifact/<id>）：概念 QJjGNnKFhKeS7r1f5bHzu7、實作 ATizWpsmAa2qutXWZ2owjm、58 題 DKBifn39yRtYDGjwGEAzC5、inst/loop/daemon HGkzKJKAsEAwhv1dQPQX8d、aos-llm與fsm K2aQ7KCad1u3dFTfDvArda。等使用者看：各 thinking 的「動工自定點」（[llm-kernel](../proto8/thinking/2026-10-15-llm-kernel.md#動工自定點)、[general-kernel](../proto8/thinking/2026-10-15-general-kernel.md#動工自定點)、[json-families](../proto8/thinking/2026-10-15-json-families.md)、[topics/04-agent當函數](../proto8/thinking/2026-10-15-topics/04-agent當函數.md)、[judge-live2](../proto8/thinking/2026-10-15-judge-live2.md)）。open 候選：對話太長、agent 收信、標準實作、規範草稿定稿。細節 → [10-15](session_logs/2026-10/2026-10-15.md)。
- **總原則（10-15）**：C-56 KISS 最高原則、C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的已寫進設計理念；盤點第 1、3、8、9 條與「正常退出」S1～S5、新的待定 A～C 已拍板並照做（10-15 晚）；第 2、4、5、6 條深夜使用者**跟推薦相反**拍板「切乾淨」並已照做（daemon add 不驗子項裡面、fsm 不讀格 stderr、`next: null`＝留原狀態讓外層不必知道格是 fsm、agent 只看到工具清單；[thinking 原則 § 深夜拍板](../proto8/thinking/2026-10-15-principles.md#10-15-深夜使用者拍板切乾淨kiss)，[§ 實作](session_logs/2026-10/2026-10-15.md#切乾淨kiss-最高原則10-15-深夜使用者拍板跟推薦相反)）。open：稿裡「自定的小地方」四條等使用者看；工具叫 agent 的寫法留給 inst-exec 稿；「kernel 評估納入錯誤路徑」記在 NORMS 待定。
- **命名（10-15）**：C-54、C-55、[縮寫表 abbr.json](../proto8/CONCEPTS/abbr.json)；盤點 P1～P7、M1～M9 與原值 `val` 使用者「都按照推薦」，10-15 晚全照做（4 個 commit）；改名批次 AI 自定的 5 個小地方使用者「都走推薦」（維持現狀）→ [盤點 § 拍板與實作](../proto8/thinking/2026-10-15-naming/盤點.md#拍板與實作10-15-晚)。
- **proto8（主線）**：細節在 git log、[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/CONCEPTS.md)、[NORMS](../proto8/NORMS.md)、[bin README](../proto8/bin/README.md)。PLAN 已刪（10-15 深夜使用者「刪掉」）。**「先做 demo」已開工**：畫家 demo demo/paint（使用者 3g.10 的例子），自定點與 LiteLLM 實跑 5 題已拍板並做完 → [10-15 § 畫家 demo](session_logs/2026-10/2026-10-15.md#畫家-demo10-15-晚使用者先做-demo開工)；restart §4 列了他停在半路的幾處。圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。
- 已搬走（open 已解）：10-14 收工交棒、10-13 `檔#/位置`／kernel-agent、10-12 thinking 精簡與清帳 → [10-14](session_logs/2026-10/2026-10-14.md)、[10-13](session_logs/2026-10/2026-10-13.md)、[10-12](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
