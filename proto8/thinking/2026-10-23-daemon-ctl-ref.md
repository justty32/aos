# 2026-10-23 daemon 的 ctl 只寫變動、`$ref` 自動切檔、指示詞全面支援

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前一份：[daemon 壓測後的六個問題](2026-10-23-daemon-bench.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。落點：[N-45](../docs/NORMS/06-基礎設施-命令列與指示詞.md)、[N-06、N-08、N-11](../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../docs/NORMS/04-基礎設施-loop與daemon.md)；程式在 `proto8/impls` 的 aos-directive、aos-loop、aos-fsm、aos-daemon（只改 C++ 版）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](2026-10-23-daemon-ctl-ref/01-使用者原文.md) | 使用者原文（整理版） |
| [02-結論](2026-10-23-daemon-ctl-ref/02-結論.md) | 結論（照原則推，細節頂層定） |

<a id="使用者原文整理版"></a>
<a id="10-23-深夜ctl-與大-json"></a>
<a id="指示詞"></a>
<a id="10-23-晚ref-陣列與兩題確認"></a>
<a id="10-23-晚ref-陣列的兩個細節"></a>
<a id="結論照原則推細節頂層定"></a>
<a id="零ref-陣列的細則照-n-45-的兩類錯推"></a>
<a id="一指示詞aos-讀的-json-都解"></a>
<a id="二ctl-只寫變動loops_addedloops_removed"></a>
<a id="三ref-切檔每份-100-個"></a>
