# 2026-11-02 state 窗改「啟動寫一次、有變動才更新」、拿掉心跳與 `kind`／`recorded_at`、加 `updated_at`

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜出發點：使用者 11-02 看試驗場 daemon 的 `.stack/`（[11-02 試驗場 daemon](../playground-daemon.md)）｜條文：[N-09、N-13、N-14、N-17、N-32、N-33](../../../../docs/NORMS/05-基礎設施-窗.md)、[N-28](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-39](../../../../docs/NORMS/07-基礎設施-組合子.md)、[P-38](../../../../docs/CONVENTION/06-巢狀.md)｜實作：[impls/aos-loop](../../../../impls/aos-loop/README.md)（`src/engine/window.cpp`、`loop.cpp`）、[impls/aos-daemon](../../../../impls/aos-daemon/README.md)（`src/daemon/windows.cpp`）｜同天：[11-02 stack-tools](../stack-tools/README.md)、[11-02 daemon-env](../daemon-env/README.md)

本檔只記使用者原文（逐字）、決定、結論、代定（可翻案）（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。11-02 已實作；**以 01 的決定與 06 的實作結論為準**，02～05 是 fable 的現況盤點、規劃、方向題與步驟表（AI 產出，部分被決定推翻，待使用者判要不要整份刪）。

> daemon 自己的窗 11-02 晚改叫 `ctl.json`／`state.json`（不加前綴），見 [ctl-state-names](../ctl-state-names/README.md)；名單與管別人的窗 11-03 起合成 `procs`，見 [11-03 procs](../../03/procs/README.md)。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-02-逐字](01-使用者原文-11-02-逐字.md) | 使用者原文（11-02，逐字）；決定（11-02，使用者）；決定（11-02 晚，使用者；實作中陸續裁的）；通稱統一 mailbox_warning（11-02 晚，使用者） |
| [02-現況-查清的-不是規劃](02-現況-查清的-不是規劃.md) | 改之前的現況盤點（AI 產出） |
| [03-規劃-fable-照原則定的細節-可翻案](03-規劃-fable-照原則定的細節-可翻案.md) | fable 的原規劃（AI 產出，部分被推翻） |
| [04-要使用者看的衝突與方向題](04-要使用者看的衝突與方向題.md) | 衝突與方向題的題目（AI 產出；答案在 01） |
| [05-實作步驟表-給隊長-每步都要先-pull](05-實作步驟表-給隊長-每步都要先-pull.md) | 實作步驟表（AI 產出） |
| [06-實作結論-11-02](06-實作結論-11-02.md) | 實作結論（11-02）；代定；帶給使用者的 |

<a id="使用者原文11-02逐字"></a>
<a id="決定11-02使用者"></a>
<a id="決定11-02-晚使用者實作中陸續裁的"></a>
<a id="通稱統一-mailbox_warning11-02-晚使用者"></a>
<a id="現況查清的不是規劃"></a>
<a id="規劃fable照原則定的細節可翻案"></a>
<a id="要使用者看的衝突與方向題"></a>
<a id="實作步驟表給隊長每步都要先-pull"></a>
<a id="實作結論11-02"></a>
