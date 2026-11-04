← [回入口 2026-11-03-收斂.md](../2026-11-03-收斂.md)｜段落：round 刪掉後沒實作撐的條文（11-04，給使用者裁）、明天怎麼接（11-03 晚使用者收工時中斷）｜上一份：[03-round刪掉後的條文之一](03-round刪掉後的條文之一.md)｜下一份：[05-11-04晚-P2-P3-P4續](05-11-04晚-P2-P3-P4續.md)

- 刪掉的使用者原文：都還在 thinking，沒有要搬的（逐字 grep 過）。

刪掉的段（原文找法：`git log -S '<標題字>' -- <檔>`，或看本 commit 的 diff）：

| # | 檔 | 刪了什麼（段標題） | 段裡的使用者原文在哪 |
|---|---|---|---|
| 4 | NORMS/07 | N-39 子項「10-30 加註：trace 加 `next`」（頂層代定） | 無原文 |
| 5 | NORMS/08 | 待定【agent】「agent 的一輪（round）與各格」 | 無原文 |
| 6 | NORMS/10 | N-53 子項「10-28 補：一格一次用 aos-loop、一輪用 round，看 `_entry`」（含 11-01 加註） | 「一個行程跑完一整輪...是這樣的…看_entry是設定要哪個。」「喔不，還是零件庫吧。…加上一些東西去實現。」→ [thinking 10-28 agent-ops/01](../../../../../proto8/thinking/2026-10/28/agent-ops/01-使用者原文.md) |
| 10 | CONVENTION/02 | P-20 子項「10-28 起改成『預設』停」 | 「照新做法」→ agent-ops/01、02 |
| 11 | CONVENTION/02 | P-23 子項「10-28 起 endpoint 是 aos 函數」（不另留一句） | 「各種單位都要跟aos函數對上，也就是aos-exec可以跑的單位目標。包括endpoint」「跟規範不一樣...就是要這樣，我覺得我們現在這樣比較先進。」「要，這個確實需要處理」→ agent-ops/01、02（第一句也在 proto8/archive/agent-round-concepts/README.md） |
| 13 | CONVENTION/02 | P-41 子項「10-28 起腦拆成格、history 只有 compact 可以改寫」 | 「跟規範不一樣...就是要這樣，我覺得我們現在這樣比較先進。」「對的對的」「照新做法」→ agent-ops/01、02 |

動到語意的地方：刪掉的 6 段都只講 round（沒有程式撐）；P-20、P-23、P-41 本文與 N-53 本文「每次被叫只走一次」「agent 自己不數連錯」照舊，沒照 round 拆格的 agent 原本就照本文。

## 明天怎麼接（11-03 晚使用者收工時中斷）

- （11-04：下面 12 份已在 6c960429 進 main、11-04 補完對讀；「還沒動」的檔仍是 P4-D／E 剩下的工作）工作樹裡留下**沒 stage、沒 commit、沒驗收**的 thinking 精簡 12 份：
  - P4-D（6 份）：`2026-10-30-map-review/01-使用者原文.md`、`02-結論.md`，`2026-10-30-agent-lifecycle/01-前提.md`、`02～04-各題結論.md`。還沒動：agent-lifecycle 入口與 05～09、`2026-10-30-aos-round*`、`2026-10-30-eca*`、`2026-10-31-aos-var*`、`2026-10-31-parts-round*`。注意 agent-lifecycle 02～04 的連結已改指 `07-衝突.md#決定10-30`，收 07 時「決定（10-30）」「實作時代定」兩個標題要原文保留。
  - P4-E（6 份）：`2026-11-02-loop-stdio.md`、`2026-11-02-exec-inheritance.md`、`2026-11-02-playground-daemon.md`、`2026-11-01-playground-bob.md`、`2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md`、`03-旋鈕改-argv-與檔-實作.md`。還沒動：`2026-11-02-playground-cathy`、`stack-tools`、`ctl-state-names`、`state-window`、`daemon-env`、`resident-bob`。
- P2（CONVENTION 摺疊）收工時還沒在 repo 留下改動；若明天看到 `proto8/docs/CONVENTION*` 有未 commit 的改動，就是 P2 中斷殘留，丟掉重做。
- 接法：先對上面 12 份跑 `git diff` 看一眼、跑 content-trim 的原文檢查（`git show HEAD:<檔>` 對現檔）與 wf-lint，再派工人把 P4-D、P4-E 剩下的做完、一起 commit；P2 重新派，做完要另一個 opus 逐句對讀，刪掉的原文與語意變動照上面 N-28、P1-1 的格式記進本報告才 commit。交接書照 [content-trim](../../content-trim.md) 收斂段與本報告的紀錄格式寫。
- P2 重派時先知道（上一個工人讀完沒動手）：沒有連結錨進 CONVENTION 的標題；要摺的條比清單多（另有 P-16、P-17、P-24、05 的 P-36 10-28 改口、01 第二節 trace 註）；01 佈局圖、P-27、P-34 還寫 `trace.jsonl`，比照 P1-1 拿掉並記語意變動；P-41 的 round 子項移到條末後原文「下面『對話』…照這條讀」方向會錯，要記；摺完要改的範圍外引用：`CONCEPTS/03-基礎設施.md:58`、`NORMS/05-基礎設施-窗.md:49`、`NORMS/08-待定.md:7` 的「P-11 的 10-30 改口」→「P-11」，`CONCEPTS/附錄1-名詞.md:59` →「見 P-17」。
- 待使用者判的整份 AI 產出檔再加一份：`2026-11-01-playground-bob/01-環境變數盤點.md`。
- thinking 裡待使用者判的整份 AI 產出檔：`2026-10-15-paint-live.md`、`2026-10-28-hub-kernel/03-現有-aos-hub-跟新方向的差異.md`、`2026-10-28-aos-tools/02-跟原則的對照.md`（要不要整份刪）；agent-round 01～08、`2026-10-24-ai-tools/*`（程式已刪，要不要再大幅縮）。
- thinking 的減量比原估小：10 月中以前的檔 10-12 夜起就照規矩寫，前三段合計只少約 108 KB；原估 1.8 → 1.2 MB 改為約 1.6 MB。
