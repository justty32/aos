# 2026-11-03 eca 接 aos 工具：`cli.json` 指登記檔、cli_session 自己接 aos-mcp，工作區與 stack 跟著實例走

← [thinking README](../../../README.md)｜月份表 [2026-11](../../README.md)｜前情：[10-28 aos-tools](../../../2026-10/28/aos-tools/README.md)（一份登記檔、aos-mcp 包在 aos-tools 上）、[11-02 playground-cathy](../../02/playground-cathy/README.md)（bob 串 aos-mcp 的 `mcp.json`；aos-mcp 改給登記檔）、[11-02 stack-tools](../../02/stack-tools/README.md)（小格 `tools/<名>/`、`--enable-logs`）、[10-30 eca](../../../2026-10/30/eca/README.md)（eca＝平級 agent、`cli.json`；[10 固定名字判準](../../../2026-10/30/eca/10-10-31-使用者原文-turn-的定義檔只認固.md#10-31-使用者原則固定名字可以但限縮範圍判準)）、[11-03 procs](../procs/README.md)（每隻 eca 的 stack＝daemon 表上那一列）｜條文：[P-15、P-43](../../../../docs/CONVENTION/02-題目stack停錯腦.md)、[N-50、N-55、N-59](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[C-51、C-52、C-54、C-56](../../../../docs/CONCEPTS/01-設計理念.md)｜程式：[cli_session](../../../../lib/agent/cli_session.py)、[aos-eca-turn](../../../../bin/aos-eca-turn)、aos-eca、[aos-mcp](../../../../extras/ai_tools/README.md)、[aos-tools](../../../../bin/README.md)

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、原則推不出答案的衝突與方向題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**11-03 已實作**（方向題 1 使用者選 (a)；實作時代定見[檔末](04-要使用者看的.md#實作時代定11-03實作者照原則定的可翻案)）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md#拆檔做法) 按 `##` 標題逐字拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段在下列分檔（2026-11-04 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](01-使用者原文.md) | 使用者原文；今天的樣子（查清的，不是規劃）；決定（11-03，使用者）；規劃（fable，照原則定的細節，可翻案） › 1. 登記檔放哪、怎麼指、2. MCP 設定由誰、何時產生、放哪 |
| [02-3-工作區與-stack-怎麼給-aos](02-3-工作區與-stack-怎麼給-aos.md) | 規劃（fable，照原則定的細節，可翻案） › 3. 工作區與 stack 怎麼給 aos-mcp、4. allowedTools 怎麼來、5. codex 怎麼接、6. 畫面那條路（open／tmux）、7. log 與 aos-mcp 的其他旗標、8. 錯誤代號 |
| [03-9-aos-eca-的入口檢查與-sta](03-9-aos-eca-的入口檢查與-sta.md) | 規劃（fable，照原則定的細節，可翻案） › 9. aos-eca 的入口檢查與 `state`、10. demo、11. 不動的；實作步驟表（不實作；給隊長） |
| [04-要使用者看的](04-要使用者看的.md) | 要使用者看的；實作時代定（11-03，實作者照原則定的，可翻案） |

<a id="使用者原文"></a>
<a id="今天的樣子查清的不是規劃"></a>
<a id="決定11-03使用者"></a>
<a id="規劃fable照原則定的細節可翻案"></a>
<a id="實作步驟表不實作給隊長"></a>
<a id="要使用者看的"></a>
<a id="實作時代定11-03實作者照原則定的可翻案"></a>
