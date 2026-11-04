# 2026-11-02 晚 loop 這一系的窗檔名：控制自身的 ctl／state 就叫 `ctl.json`／`state.json`，不加前綴

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜出發點：頂層向使用者說明「eca 範本用 `ctl.json`／`state.json`，常駐 bob 用 `loop_ctl.json`／`loop_state.json`；全統一加 `loop_` 是大工程」｜被本條推翻的同日決定：[11-02 state 窗](../state-window/README.md)（白天：daemon 窗慣用名 `daemon_ctl.json`／`daemon_state.json`）、[11-02 exec 像繼承 § 結論](../exec-inheritance.md#結論11-02跟使用者討論後)（共用 stack 常見名字加前綴 `daemon_*`、`loop_*`）在 ctl／state 這件事上、[11-02 常駐 bob](../resident-bob/README.md)（控制器窗 `loop_ctl.json`／`loop_state.json`、代定「aos-listen 也認 `loop_state.json`」）｜條文：[N-09、N-11、N-13、N-14、N-17](../../../../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[P-17](../../../../docs/CONVENTION/02-題目stack停錯腦.md)、[C-54](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)｜程式：[aos-loop](../../../../impls/aos-loop/README.md)、[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../bin/README.md)、aos-eca-hub、aos-say／listen、[ai_tools](../../../../extras/ai_tools/README.md)｜場地 `~/code/playground/`（不在 git）

本檔只記使用者原文（逐字）、決定、查清的現況、fable 照原則定的規劃（可翻案）、原則沒講清楚要使用者一句話的方向題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**只規劃、沒實作。**

> **11-03 補**：loop 的 ctl.json 11-03 改成一道指令（`{"cmd": "stop"}` 取代 `{"stopped": true}`；起來第一次讀到的那份當基準線，殘留的 stop 不用再清，常駐 bob `_entry` 的 `clear_stopped` 拿掉），見 [11-03 ctl-commands](../../03/ctl-commands/README.md)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md#拆檔做法) 按 `##` 標題逐字拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段在下列分檔（2026-11-04 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-02-晚-逐字](01-使用者原文-11-02-晚-逐字.md) | 使用者原文（11-02 晚，逐字）；決定（11-02 晚，使用者）；現況（查清的，不是規劃） › daemon 的 ctl／state 跟 loop 的格式一樣嗎（決定原則怎麼套） |
| [02-每個窗現在叫什麼-誰定名-誰讀誰寫](02-每個窗現在叫什麼-誰定名-誰讀誰寫.md) | 現況（查清的，不是規劃） › 每個窗現在叫什麼、誰定名、誰讀誰寫、條文現在怎麼寫 |
| [03-同一個-stack-裡有兩對-ctl-s](03-同一個-stack-裡有兩對-ctl-s.md) | 現況（查清的，不是規劃） › 「同一個 stack 裡有兩對 ctl／state」今天發生在哪；規劃（fable，照原則定的細節，可翻案） |
| [04-要使用者看的方向題-原則沒講清楚的](04-要使用者看的方向題-原則沒講清楚的.md) | 要使用者看的方向題（原則沒講清楚的） |
| [05-實作步驟表-不實作-給隊長](05-實作步驟表-不實作-給隊長.md) | 實作步驟表（不實作；給隊長）；影響面；實作（11-02 晚，隊長派的 agent；時間到 22:55 硬期限，跟另一輪「刪 agent-dan」的未 commit 改動重疊的先不碰） |

<a id="使用者原文11-02-晚逐字"></a>
<a id="決定11-02-晚使用者"></a>
<a id="現況查清的不是規劃"></a>
<a id="規劃fable照原則定的細節可翻案"></a>
<a id="要使用者看的方向題原則沒講清楚的"></a>
<a id="實作步驟表不實作給隊長"></a>
<a id="影響面"></a>
<a id="實作11-02-晚隊長派的-agent時間到-2255-硬期限跟另一輪刪-agent-dan的未-commit-改動重疊的先不碰"></a>
