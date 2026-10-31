# 2026-10-28 aos-hub 下一步：常駐 aos-kernel 管所有 CLI 實例、pause 與 stop

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-27 aos-hub（demo）](2026-10-27-claude-switch.md)、[10-26 playground](2026-10-26-playground.md)（`_entry` 叫 claude、經 aos-mcp 接工具）｜使用者筆記：[user-advice/20261027](../user-advice/20261027.md)（使用者的資料夾，不改）｜程式：[extras/cli_hub](../extras/eca_hub/README.md)（10-28 下午照這裡的決定改完）｜後續：[10-28 hub-adapter](2026-10-28-hub-adapter.md)（say／listen 協議、適配表、副產物、實作與實跑）

> 10-30 起 aos-hub 改做 aos-eca-hub，見 [eca](2026-10-30-eca.md)。

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](2026-10-28-hub-kernel/01-使用者原文.md) | 使用者原文 |
| [02-決定](2026-10-28-hub-kernel/02-決定.md) | 決定（10-28）、未決、跟原則的對照（10-28） |
| [03-現有-aos-hub-跟新方向的差異](2026-10-28-hub-kernel/03-現有-aos-hub-跟新方向的差異.md) | 現有 aos-hub 跟新方向的差異（之後要改的） |

<a id="使用者原文"></a>
<a id="10-27-晚的筆記整理版全文見-user-advice20261027"></a>
<a id="10-28逐字"></a>
<a id="決定10-28"></a>
<a id="未決"></a>
<a id="跟原則的對照10-28"></a>
<a id="現有-aos-hub-跟新方向的差異之後要改的"></a>
