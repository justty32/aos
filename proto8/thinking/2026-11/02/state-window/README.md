# 2026-11-02 state 窗改「啟動寫一次、有變動才更新」、daemon 的 state 改名 `daemon_state.json`、每次的紀錄進 log

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜出發點：使用者 11-02 看試驗場 daemon 的 `.stack/`（[11-02 試驗場 daemon](../playground-daemon.md)）｜條文：[N-09、N-13、N-14、N-17、N-32、N-33](../../../../docs/NORMS/05-基礎設施-窗.md)、[N-28](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-39](../../../../docs/NORMS/07-基礎設施-組合子.md)（fsm 的 `trace.jsonl`）、[P-38](../../../../docs/CONVENTION/06-巢狀.md)｜實作：[impls/aos-loop](../../../../impls/aos-loop/README.md)（`src/engine/window.cpp`、`loop.cpp`）、[impls/aos-daemon](../../../../impls/aos-daemon/README.md)（`src/daemon/windows.cpp`）｜同天的另兩份規劃：[11-02 stack-tools](../stack-tools/README.md)（隊長正在落地）、[11-02 daemon-env](../daemon-env/README.md)（控制口，命名未定）

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、要使用者看的衝突與方向題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。規劃節是 fable 的原規劃，**以決定節為準**（log 檔、心跳進 log 等沒做）；11-02 已實作，結論在文末「實作結論」。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md#拆檔做法) 按 `##` 標題逐字拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段在下列分檔（2026-11-04 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-02-逐字](01-使用者原文-11-02-逐字.md) | 使用者原文（11-02，逐字）；決定（11-02，使用者）；決定（11-02 晚，使用者；實作中陸續裁的）；通稱統一 mailbox_warning（11-02 晚，使用者） |
| [02-現況-查清的-不是規劃](02-現況-查清的-不是規劃.md) | 現況（查清的，不是規劃） |
| [03-規劃-fable-照原則定的細節-可翻案](03-規劃-fable-照原則定的細節-可翻案.md) | 規劃（fable，照原則定的細節，可翻案） |
| [04-要使用者看的衝突與方向題](04-要使用者看的衝突與方向題.md) | 要使用者看的衝突與方向題 |
| [05-實作步驟表-給隊長-每步都要先-pull](05-實作步驟表-給隊長-每步都要先-pull.md) | 實作步驟表（給隊長；每步都要先 pull） |
| [06-實作結論-11-02](06-實作結論-11-02.md) | 實作結論（11-02） |

<a id="使用者原文11-02逐字"></a>
<a id="決定11-02使用者"></a>
<a id="決定11-02-晚使用者實作中陸續裁的"></a>
<a id="通稱統一-mailbox_warning11-02-晚使用者"></a>
<a id="現況查清的不是規劃"></a>
<a id="規劃fable照原則定的細節可翻案"></a>
<a id="要使用者看的衝突與方向題"></a>
<a id="實作步驟表給隊長每步都要先-pull"></a>
<a id="實作結論11-02"></a>
