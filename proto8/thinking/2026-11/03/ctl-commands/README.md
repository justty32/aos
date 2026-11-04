# 2026-11-03 loop 的 ctl.json 改成下指令（動作），不是寫期望狀態；不用信箱、誰能寫就能控制

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜出發點：[11-03 procs § 0 名詞表](../procs/03-規劃-fable-照原則定的細節-可翻案.md#0-名詞表代定)（動作 add／rm／start／stop／pause／resume）｜條文：[N-06、N-07、N-08、N-11、N-14](../../../../docs/NORMS/05-基礎設施-窗.md)（loop 的 ctl 那半）、[C-54 命名方法 R4](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)；不動的：[N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md) daemon 管別人的 `procs_ctl.json`（仍是宣告的名單）、[N-09](../../../../docs/NORMS/05-基礎設施-窗.md) state 只有自己寫｜程式：[aos-loop](../../../../impls/aos-loop/README.md)、[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../bin/README.md)

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**已實作**（使用者「可以，派人做」，4b2d6d86）。跟 [11-03 procs](../procs/README.md) 同一天、它的 § 2c（daemon 怎麼停／起子 loop）靠本檔。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-03-逐字](01-使用者原文-11-03-逐字.md) | 使用者原文（11-03，逐字）；決定（11-03，使用者）；規劃 › 1. 指令長什麼樣 |
| [02-2-loop-怎麼知道這道是新的-沒有信](02-2-loop-怎麼知道這道是新的-沒有信.md) | 規劃 › 2. 怎麼知道這道是新的（比內容、基準線）、3. 三個動詞、4. 暫停中記在哪（代定）、5. 跟 daemon 的關係 |
| [03-6-條文只加-11-03-註](03-6-條文只加-11-03-註.md) | 規劃 › 7. 改哪（已實作）；要使用者看的；實作時代定 |
