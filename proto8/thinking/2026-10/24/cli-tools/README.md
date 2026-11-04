# 2026-10-24 claude／codex CLI 當工具，人可以接進去（agent-fay）

← [thinking](../../../README.md)｜月份表 [2026-10](../../README.md)｜前情：[腦的工具呼叫](../../23/tool-calls/README.md)（agent-dan、P-41）、[agent 當工具](../agent-as-tool.md)、[say／listen](../say-listen/README.md)

規矩見 [thinking/README](../../../README.md)：只留使用者原文、決定、結論。程式：工具在 [lib/agent](../../../../lib/README.md) 的 claude、codex 與 `cli_session.py`，測試 `proto8/tests/test_cli_tools.py`（原 test_fay）。

> **11-03 晚 demo/agent-fay 刪了**（頂層問到它，使用者逐字）：「我沒聽過這東西，刪掉。」→ 刪的是 demo 那隻範本（brain／act、`attach`）；`lib/agent/claude`、`codex` 與 `cli_session.py` 的工具形是 eca 的一半，留著，測試改成直接測它們。下文講 agent-fay、它的 `attach` 的地方是當時的現況。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md#拆檔做法) 按 `##` 標題逐字拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段在下列分檔（2026-11-04 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文-10-24](01-使用者原文-10-24.md) | 使用者原文（10-24）；結論（照推薦定、可翻案） |
| [02-已知限制](02-已知限制.md) | 已知限制；未決（選項） |

<a id="使用者原文10-24"></a>
<a id="結論照推薦定可翻案"></a>
<a id="已知限制"></a>
<a id="未決選項"></a>
