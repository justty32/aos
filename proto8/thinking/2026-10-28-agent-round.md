# 2026-10-28 agent 的一輪（round）：掛勾點、單位、endpoint 介面、引用、落地步驟

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-28 agent-ops](2026-10-28-agent-ops.md)（決定 1～10：各單位都是 aos 函數、六題的回答；本份是它的「結論／代定」）、[10-28 hub-kernel](2026-10-28-hub-kernel.md)（決定 11 prompt＝queue、13 插話不訂死）、[10-28 aos-tools](2026-10-28-aos-tools.md)、[10-28 hub-adapter](2026-10-28-hub-adapter.md)（信箱協議）、[10-24 compact](2026-10-24-compact.md)（agent-hal 的土法 compact）、[10-24 tool-lib](2026-10-24-tool-lib.md)（捷徑指到庫）｜相關條文：[CONVENTION P-11～P-26、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32～P-39](../docs/CONVENTION/06-巢狀.md)、[C-61](../docs/CONCEPTS/05-agent.md)、[N-43](../docs/NORMS/01-總則.md)、[N-57～N-61](../docs/NORMS/10-基礎設施-定義與工作區.md)

規矩見 [thinking/README](README.md)。這份**全部是照原則代定、可翻案**，使用者定的在 agent-ops 的「決定」；文末原本要使用者看的七條，使用者 10-28 回「照新做法」，已定（agent-ops 決定 11）；之後再定粒度看 `_entry`、round 是零件庫的語法糖、aos 歸 aos、round 列入外部接口（決定 12～15）、格全部走註冊檔、捷徑只是方便用（決定 16），對應的結論已改。只寫文件、程式沒改、這次不動手做。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-白話版](2026-10-28-agent-round/01-白話版.md) | 白話版、1. 佈局 |
| [02-2-round-一輪本身](2026-10-28-agent-round/02-2-round-一輪本身.md) | 2. round：一輪本身、3. 掛勾（hook）、4. 單位介面 |
| [03-4-單位介面](2026-10-28-agent-round/03-4-單位介面.md) | 4. 單位介面 › queue（對到 P-11～P-14 的信箱，`$AOS_WS/new cur out done`）、4. 單位介面 › history（`$AOS_STACK/history.jsonl`，一行一則 OpenAI message，P-41）、4. 單位介面 › endpoint（腦；假腦、LiteLLM、直連 OpenAI 都是這種資料夾）、4. 單位介面 › act（照腦的決定跑工具）、4. 單位介面 › tools 生效時間點（使用者六題之 1：「變成掛在哪個點」） |
| [04-5-stack-裡有什麼](2026-10-28-agent-round/04-5-stack-裡有什麼.md) | 5. stack 裡有什麼、6. 外部指令對內部單位、7. 怎麼落地：做一隻新範本 agent（10-28 晚實作中） |
| [05-已定](2026-10-28-agent-round/05-已定.md) | 已定（原本要使用者看的七條，10-28）、實作時代定（10-28 晚，照原則代定、可翻案）、實作時代定（10-28 晚，照原則代定、可翻案） › 做 aos-parts 時再代定的（10-28 晚，第 0 步，代定、可翻案） |
| [06-實作時代定](2026-10-28-agent-round/06-實作時代定.md) | 實作時代定（10-28 晚，照原則代定、可翻案） › 做 endpoint、act 時再代定的（10-28 晚，第 1、4 步，代定、可翻案） |
| [07-實作時代定](2026-10-28-agent-round/07-實作時代定.md) | 實作時代定（10-28 晚，照原則代定、可翻案） › 做 queue、history、compact 時再代定的（10-28 晚，第 2、3 步，代定、可翻案） |
| [08-實作時代定](2026-10-28-agent-round/08-實作時代定.md) | 實作時代定（10-28 晚，照原則代定、可翻案） › 做 round 時再代定的（10-28 晚，第 5 步，代定、可翻案）、實作時代定（10-28 晚，照原則代定、可翻案） › 做範本 agent-nia 時再代定的（10-28 晚，第 6 步，代定、可翻案）、實作時代定（10-28 晚，照原則代定、可翻案） › 做 aos-ai spawn 時再代定的（10-28 晚，第 7、8 步，代定、可翻案） |
| [09-實作時代定](2026-10-28-agent-round/09-實作時代定.md) | 實作時代定（10-28 晚，照原則代定、可翻案） › 做「問 agent」工具時再代定的（10-28 晚，第 11 步，代定、可翻案）、10-31 使用者原文：parts 的定位 |

<a id="白話版"></a>
<a id="1-佈局"></a>
<a id="格怎麼找註冊檔--固定名字--預設決定-16"></a>
<a id="2-round一輪本身"></a>
<a id="3-掛勾hook"></a>
<a id="4-單位介面"></a>
<a id="queue對到-p-11p-14-的信箱aos_wsnew-cur-out-done"></a>
<a id="historyaos_stackhistoryjsonl一行一則-openai-messagep-41"></a>
<a id="endpoint腦假腦litellm直連-openai-都是這種資料夾"></a>
<a id="act照腦的決定跑工具"></a>
<a id="tools-生效時間點使用者六題之-1變成掛在哪個點"></a>
<a id="5-stack-裡有什麼"></a>
<a id="6-外部指令對內部單位"></a>
<a id="7-怎麼落地做一隻新範本-agent這次不做"></a>
<a id="7-怎麼落地做一隻新範本-agent10-28-晚實作中"></a>
<a id="要使用者看的只這一節"></a>
<a id="已定原本要使用者看的七條10-28"></a>
<a id="實作時代定10-28-晚照原則代定可翻案"></a>
<a id="做-aos-parts-時再代定的10-28-晚第-0-步代定可翻案"></a>
<a id="做-endpointact-時再代定的10-28-晚第-14-步代定可翻案"></a>
<a id="做-queuehistorycompact-時再代定的10-28-晚第-23-步代定可翻案"></a>
<a id="做-round-時再代定的10-28-晚第-5-步代定可翻案"></a>
<a id="做範本-agent-nia-時再代定的10-28-晚第-6-步代定可翻案"></a>
<a id="做-aos-ai-spawn-時再代定的10-28-晚第-78-步代定可翻案"></a>
<a id="做問-agent工具時再代定的10-28-晚第-11-步代定可翻案"></a>
<a id="10-31-使用者原文parts-的定位"></a>
