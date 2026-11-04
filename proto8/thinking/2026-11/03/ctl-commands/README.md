# 2026-11-03 loop 的 ctl.json 改成下指令（動作），不是寫期望狀態；不用信箱、誰能寫就能控制

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜出發點：[11-03 procs § 0 名詞表](../procs/03-規劃-fable-照原則定的細節-可翻案.md#0-名詞表代定)（動作 add／rm／start／stop／pause／resume）與頂層攤開的「宣告式（今天）vs 指令式」｜被本條改口的：[N-06、N-07、N-08、N-11、N-14](../../../../docs/NORMS/05-基礎設施-窗.md)（loop 的 ctl 那半）、[C-54 命名方法 R4](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)（ctl 的 key 用狀態詞）、[11-02 state 窗](../../02/state-window/README.md)（「ctl 有變才算變動」照舊、形狀換）｜不動的：[N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md) daemon 管別人的 `procs_ctl.json`（仍是宣告的名單）、[N-09](../../../../docs/NORMS/05-基礎設施-窗.md) state 只有自己寫、[P-36](../../../../docs/CONVENTION/06-巢狀.md)、[C-52](../../../../docs/CONCEPTS/01-設計理念.md)｜程式：[aos-loop](../../../../impls/aos-loop/README.md)（`src/engine/window.cpp` `read_ctl`、`loop.cpp` `serve`）、[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../bin/README.md)、[aos-eca](../../../../extras/eca/README.md)、[ai_tools](../../../../extras/ai_tools/README.md)、[aos_ws／aos-listen](../../../../extras/human/README.md)｜場地 `~/code/playground/`（不在 git）

本檔只記使用者原文（逐字）、決定、查清的現況、fable 照原則定的規劃（可翻案）、原則沒講清楚要使用者一句話的衝突與方向題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**只規劃、沒實作。** 跟 [11-03 procs](../procs/README.md) 同一天、它的 § 2c（daemon 怎麼停／起子 loop）靠本檔。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md#拆檔做法) 按 `##` 標題逐字拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段在下列分檔（2026-11-04 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-03-逐字](01-使用者原文-11-03-逐字.md) | 使用者原文（11-03，逐字）；決定（11-03，使用者）；現況（查清的，不是規劃）；規劃（fable，照原則定的細節，可翻案） › 1. 指令長什麼樣 |
| [02-2-loop-怎麼知道這道是新的-沒有信](02-2-loop-怎麼知道這道是新的-沒有信.md) | 規劃（fable，照原則定的細節，可翻案） › 2. loop 怎麼知道這道是新的（沒有信箱）、3. 三個動詞各做什麼（冪等）、4. 「現在暫停中」記在哪、再起時怎麼辦（代定）、5. 跟 daemon 的關係（procs 規劃 § 2c 照本檔改） |
| [03-6-條文只加-11-03-註](03-6-條文只加-11-03-註.md) | 規劃（fable，照原則定的細節，可翻案） › 6. 條文只加 11-03 註、7. 改哪；要使用者看的；實作時代定（11-03，實作者照原則定的，可翻案） |

<a id="使用者原文11-03逐字"></a>
<a id="決定11-03使用者"></a>
<a id="現況查清的不是規劃"></a>
<a id="規劃fable照原則定的細節可翻案"></a>
<a id="要使用者看的"></a>
<a id="實作時代定11-03實作者照原則定的可翻案"></a>
