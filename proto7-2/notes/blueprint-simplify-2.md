# 回頭審第二輪：重複、殘留副作用、重造（r4 RV）

← [r4 計畫](plan-2026-10-09-r4.md)｜[意圖卡](intents/README.md)｜[錯誤藍圖](blueprint-errors.md)｜分線 [blueprint-simplify-2-teams.json](blueprint-simplify-2-teams.json)

Opus 10-09 18:30。astra-high ×2 唯讀（甲：13 包對卡逐條；乙：重複與副作用）、sol 核引用。路徑相對 `proto7-2/`。**只審不改**；改卡由頂層。

## 1. 重複功能（每組一個處置）

| 組 | 證據 | 判斷 | 建議 | 代價 |
|---|---|---|---|---|
| usage ↔ metrics | `packs/usage/aos7_usage.py:79-104` 分模型／holder／時段＋帳差；metrics 「不是帳的彙總」（`modules/metrics/ADVANCED.md` 契約卡）。**usage 讀不了真資料**：讀 `request.request.model`、數字 `at`（`aos7_usage.py:30-33,59-62`），真 llmcall 寫 `request.litellm.model`、ISO 時間；實跑 `aos7-usage modules/metrics/baseline/r1/loop-gpt-6-sol/llm` → `groups:[]`、`bad_json`，metrics 同夾 2590 token | 部分重疊；usage 獨有分組與帳差，但壞了 | **併入 metrics**：`job PATH --by model\|holder\|day\|hour`（只寫 ADVANCED）、`--detail` 加「帳差」；usage 進 archive、留轉址 stub 一輪 | metrics ＋約 60 行與測試；`job` 預設輸出一字不改（S3／EF 用它量） |
| llmdiag ↔ diag | `modules/llmdiag/aos7_llmdiag.py:31-72` 看 node 的 LLM 待辦；`modules/diag/aos7-diag:1-8` 看 root 的核心槽 | 不重疊、同是「唯讀診斷」 | **併入 diag**：`aos7-diag --llm NODE`，JSON 照舊；llmdiag 進 archive＋stub | diag 加一個旗標；diag 補進 `tests/error_path.json`（現在 diag、usage、llmdiag 三個都**不在**一致性清單） |
| events `read --ack` ↔ `ack` | 兩者共用 ack_main（`modules/events/aos7_events_read.py:150-156`、`aos7_events_cli.py:79`）；mail 已改用 `ack`（`modules/mail/aos7_mail_ack.py:51`） | 完全涵蓋 | 照代定：本輪 `read --ack` 照做但 stderr 加一行「改用 aos7-events ack」，r5 移除 | 改 1 個 parser、1 測試、`packs/author/examples/events-request/README.md`、`modules/mail/INTERNALS.md` |
| mail audit ↔ events must | audit＝信與回信對帳，看「辦完沒」（`modules/mail/aos7_mail.py:160`）；must＝seq＋ack，看「能不能丟」 | 分工不同，**保留** | 不併；但見 §2 第 1 條（共用 must 的真衝突） | — |
| audit 包 ↔ mail audit | `modules/audit/aos7-audit` 記寫入；mail audit 查欠回信 | 同名不同事 | 保留；ADVANCED 各加一句區分 | 文件一句 |
| 其他（乙查過） | control／once_retry／subd、step／llmcall、adapt／prompt 各管各；adapt 的回合鐘抄 budget 是 spec 明定不共用（`packs/adapt/spec.md:49`） | 不重複 | 保留 | — |

## 2. 殘留副作用與卡沒照做的（甲＋乙）

1. **共用 must 通道會互相踩**：author intake 遇外來 kind 記 ignored 後照樣 ack（`packs/author/aos7_author_pub.py:215,278,290`），mail 遇外來 kind 停（`modules/mail/aos7_mail_ack.py:37`），events 一條通道只有一個累積確認值。同 node 兩者都用 → mail 的請求可能被 author 提前確認。→ RV-fix 線 C。
2. **events 夾仍可被函式入口自動建**：CLI `pub` 已擋（`modules/events/aos7_events_pub.py:94-102`），但 author `send` 直接呼叫 publish（`aos7_author_pub.py:190`）→ store 經 `lib/aos7_fs` 建夾。違反「跨包副作用歸 up」。→ 線 C（只改 author 端，不動 events store 凍結介面）。
3. usage／llmdiag 錯誤不是統一一行格式（usage 用 argparse 預設訊息，`aos7_usage.py:108-111`；llmdiag `--help` 退 2，`aos7_llmdiag.py:75-79`），併掉就消失。→ 線 A／B。
4. 卡與現況不符、要**改卡不改程式**（頂層）：skills 卡 ④「錯誤改說用 aos7-up」，但已上線的是「直接附起帳指令」（decisions 203、210）；compact 卡 ③「不摘現役／open」，但 `forget`、`--include-open` 是人明講才做（`modules/compact/aos7_compact.py:319-324,459-481`）；events 卡 ③「不集中多 node」對 `--src` 可重複（`modules/events/aos7-events:104,142`）要說清楚是取樣多個來源；up 卡 ②「預設一列 routines」沒做（`modules/up/aos7_up.py:37-77`）；author 卡 ③「不跳關」對任務型要寫清「兩層＋發布後驗答案」是設計。
5. 交 B5（不歸 RV-fix）：brain 每回合把非 REQUEST 的信整批 `done`（`modules/up/aos7_up_brain.py:138-142`），與 up 卡「每回合最多一封」字面不合；多回合時要決定這是不是想要的。
6. 保留不修：`__pycache__`（.gitignore 已擋）；skills `bank.py` 自己起帳（題庫腳本、暫存 node、ADVANCED 已標）；compact 段落狀態變了才寫 state（`aos7_compact.py:405-414`，屬必要）。

## 3. 新手面概念與指令數

甲數：QUICKSTART 只 1 個指令名、3 個操作、5 詞（達標）。現存 `aos7-*` 入口 27 個（sol 數）；甲按 README 詞表去重概念 87，其中底層 32 個來自 adapt、step、control、subd、audit、once_retry——新手不會碰。
- 線 A＋B 後：入口 27→25、概念 −2（帳差、inflight 搬進 ADVANCED）；`read --ack` 的操作 −1 在 r5 移除時才算。
- 建議 I5（modules/README 是它的領地）：總覽表分「新手會用」（up、mail、metrics、diag）與「底層／給 AI 用」兩段，不改任何程式。

## 4. 重造候選

- **不重造**：沒有一個包整個走錯路；最大問題是「學徒寫的工具過了三關卻讀不了真資料」——**題目的 fixture 不是真 llmcall 的檔形**（`packs/author/examples/aos-tool-usage/fixture/llmcall/llm/c1/request.json:11-12` 用 `request.model`，檢查器 `check_answer.py:30-38` 照它寫死期望）。→ **轉 S3**：三連題的 fixture 要從真 llmcall 證據複製，不手捏；之後三關加一關「對 `modules/metrics/baseline/r1/` 跑一次不得全是 bad」（改 author 由頂層另開）。
- **該拆（不在本輪）**：author 主檔 985 行混驗證／編譯／驗收／CLI（`packs/author/aos7_author.py:340,509,700,868`）。EF2／EF3／S3 本輪都在 author，**等 S3 交後再拆**。
- **小到該併**：usage→metrics、llmdiag→diag（線 A／B）。control 併 tools 收益小（新手看不到），不做。

## 5. RV-fix 分線（細節與 done 在 json）

| 線 | 領地 | 一句 done |
|---|---|---|
| A 量尺合一 | `modules/metrics/**`、`packs/usage/**`、`archive/usage/`（新） | `aos7-metrics job --by model` 在真 baseline 出正確分組與帳差；`job` 預設輸出不變；`aos7-usage` 印一行轉址退 1 |
| B 診斷合一 | `modules/diag/**`、`modules/llmdiag/**`、`archive/llmdiag/`（新）、`tests/error_path.json` 加 diag 一列 | `aos7-diag --llm NODE` JSON 與舊 llmdiag 逐字相同；diag 過一致性測試 |
| C must 通道收口 | `packs/author/aos7_author_pub.py`、`packs/author/tests/test_author_pub*`、`modules/events/aos7_events_read.py`＋其測試、`modules/mail/INTERNALS.md`、`packs/author/examples/events-request/README.md` | 同 node 混 mail＋author 的 must 測試綠（誰都不替對方 ack）；author `send` 對沒 events/ 的 node 退 1 不建夾；`read --ack` 印轉址行 |

不重疊：A、B、C 互不碰；避開 B5（`modules/up/**`）、EF2（`aos7_author.py`）、EF3（`aos7_author_llm.py`）、S3（`examples/aos-tool-*`）、I5（modules/README、INDEX）。modules/README 與 INDEX 的列由 I5 改，各線交棒信寫明。

## 6. 要頂層代定

1. A 用 `--by` 併進 `job`（建議）還是另開子命令 `usage`？（前者指令數不增）
2. B 用 `aos7-diag --llm NODE`（建議）還是 up `status` 多一行？（status 是 U3／EF2 領地）；diag 沒卡，開線前頂層補一張
3. C：author 遇外來 kind **停下不 ack**（建議，安全、可能卡住→stderr 說是哪個 kind 擋住）vs 由 up 規定「一個 node 只准一個 must 消費者」。
4. §2 第 4 條五張卡改字。
5. archive 放 `proto7-2/archive/<包>/`（git mv，保歷史）。
