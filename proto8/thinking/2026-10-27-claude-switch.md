# 2026-10-27 很多 claude 在跑：一個地方看全部、cd 過去接入、收起與叫回（aos-hub）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-24 claude／codex 當工具、人可以接進去](2026-10-24-cli-tools.md)（attach、小格、hook）｜程式：[extras/cli_hub](../extras/eca_hub/README.md)，測試 `proto8/tests/test_hub.py`｜後續：[10-28 常駐 aos-kernel、pause 與 stop](2026-10-28-hub-kernel.md)、[10-28 實作（程式已照新方向重寫，下面的指令多半已換）](2026-10-28-hub-adapter.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](2026-10-27-claude-switch/01-使用者原文.md) | 使用者原文（10-27）、結論、10-27 晚：用起來的疑問（先不改）、代定（可翻案） |
| [02-跟原則的衝突與方向題](2026-10-27-claude-switch/02-跟原則的衝突與方向題.md) | 跟原則的衝突與方向題、已知限制 |

<a id="使用者原文10-27"></a>
<a id="結論"></a>
<a id="1-延伸-10-24-的小格不另起一套"></a>
<a id="2-六件事各怎麼做"></a>
<a id="3-實跑haiku總共不到-001"></a>
<a id="4-claude-code-內建的背景-session查過沒選"></a>
<a id="10-27-晚用起來的疑問先不改"></a>
<a id="代定可翻案"></a>
<a id="跟原則的衝突與方向題"></a>
<a id="已知限制"></a>
