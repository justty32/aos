# 2026-10-24 LLM kernel 第一版：問腦變成請求、kernel 排隊跑

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-15 kernel 截流](2026-10-15-kernel-intercept.md)（閘門／信箱、六題照建議）、[10-15 LLM kernel](2026-10-15-llm-kernel.md)（priority、排序六條）、[10-19 重寫順序 § ⑤、第 3 題](2026-10-19-rewrite-order.md)、[10-21 計畫 § 1.2](2026-10-21-plan.md)、[10-23 agent 與 kernel](2026-10-23-agent-kernel.md)、[10-24 exec 直接放單子](2026-10-24-exec-relative.md)、[10-24 `_metainfo`](2026-10-24-metainfo.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。相關條文：[C-09～C-12、C-38、C-47](../docs/CONCEPTS/04-kernel.md)、[C-20](../docs/CONCEPTS/05-agent.md)、[N-42](../docs/NORMS/09-kernel.md)、[N-14、N-16](../docs/NORMS/05-基礎設施-窗.md)、[N-60](../docs/NORMS/10-基礎設施-定義與工作區.md)、C-54。程式：[aos-kernel-llm](../impls/aos-llm-kernel/README.md)、[aos-gate](../impls/aos-llm-send/README.md)、[demo/kernel-llm](../demo/README.md)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](2026-10-24-llm-kernel/01-使用者原文.md) | 使用者原文（10-24，逐字）、決定、結論：照推薦定、可翻案（使用者 10-24「都按建議做」） |
| [02-邊緣狀況](2026-10-24-llm-kernel/02-邊緣狀況.md) | 邊緣狀況（挖出來的；多數已照上面處理，剩的寫在 aos-kernel-llm README 已知限制）、接點、token 回報與額度（10-24 下午） |

<a id="使用者原文10-24逐字"></a>
<a id="決定"></a>
<a id="結論照推薦定可翻案使用者-10-24都按建議做"></a>
<a id="邊緣狀況挖出來的多數已照上面處理剩的寫在-aos-kernel-llm-readme-已知限制"></a>
<a id="接點"></a>
<a id="token-回報與額度10-24-下午"></a>
<a id="結論照推薦定可翻案使用者-10-24都按建議做-1"></a>
<a id="邊緣狀況挖出來的"></a>
