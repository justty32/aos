# 2026-11-02 晚 loop 這一系的窗檔名：控制自身的 ctl／state 就叫 `ctl.json`／`state.json`，不加前綴

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜本條取代的同日說法：[11-02 state 窗](../state-window/README.md)（daemon 窗叫 `daemon_ctl.json`／`daemon_state.json`）、[11-02 exec 像繼承 § 結論](../exec-inheritance.md#結論11-02跟使用者討論後)（共用 stack 的常見名字加前綴）在 ctl／state 這件事上、11-02 常駐 bob（控制器窗 `loop_ctl.json`／`loop_state.json`、aos-listen 也認 `loop_state.json`）｜條文：[N-09、N-11、N-13、N-14、N-17](../../../../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[P-17](../../../../docs/CONVENTION/02-題目stack停錯腦.md)、[C-54](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)｜程式：[aos-loop](../../../../impls/aos-loop/README.md)、[aos-daemon](../../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../../bin/README.md)、aos-eca-hub、aos-say／listen、[ai_tools](../../../../extras/ai_tools/README.md)｜場地 `~/code/playground/`（不在 git）

本檔只記使用者原文（逐字）、決定、結論、代定（可翻案）（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。11-02 晚已照決定落地。

> **11-03 補**：loop 的 ctl.json 11-03 改成一道指令（`{"cmd": "stop"}` 取代 `{"stopped": true}`；起來第一次讀到的那份當基準線，殘留的 stop 不用再清，常駐 bob `_entry` 的 `clear_stopped` 拿掉），見 [11-03 ctl-commands](../../03/ctl-commands/README.md)。daemon 管別人的那對窗 11-03 起叫 `procs_ctl`／`procs_state`，見 [11-03 procs](../../03/procs/README.md)。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-11-02-晚-逐字](01-使用者原文-11-02-晚-逐字.md) | 使用者原文（11-02 晚，逐字）；決定；方向題的答案；daemon 的 ctl／state 跟 loop 的格式一樣（結論） |
| [03-同一個-stack-裡有兩對-ctl-s](03-同一個-stack-裡有兩對-ctl-s.md) | 結論：改完每個元件的窗叫什麼、「末端加前綴」目前沒有套用對象；代定 |

<a id="使用者原文11-02-晚逐字"></a>
<a id="決定11-02-晚使用者"></a>
<a id="現況查清的不是規劃"></a>
<a id="規劃fable照原則定的細節可翻案"></a>
<a id="要使用者看的方向題原則沒講清楚的"></a>
<a id="實作步驟表不實作給隊長"></a>
<a id="影響面"></a>
<a id="實作11-02-晚隊長派的-agent時間到-2255-硬期限跟另一輪刪-agent-dan的未-commit-改動重疊的先不碰"></a>
