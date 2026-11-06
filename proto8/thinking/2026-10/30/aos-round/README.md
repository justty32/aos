# 2026-10-30 aos-round：round 化作 aos-loop／fsm 上的薄殼、fsm 的 `next` 照結束碼分岔（fable 規劃）

> **11-01 晚使用者裁刪 aos-round**（「aos round這東西還沒刪掉嗎」「這應該整個都不需要吧」「刪掉」）→ 刪法與對照見 [playground-bob 03 § 刪掉 aos-round](../../../2026-11/01/playground-bob/03-旋鈕改-argv-與檔-實作.md#刪掉-aos-round11-01-晚)。

← [thinking](../../../README.md)｜月份表 [2026-10](../../README.md)｜出發點：[10-30 eca § 翻案](../eca/11-10-31-使用者想法-turn-改名-把-tu.md#翻案round-化作-aos-round-薄殼10-30使用者澄清)（使用者原文與決定）、[10-30 map-review 第 2 點](../map-review/01-使用者原文.md#決定10-30)｜隊長查過的五個難點：10-30 agent-lifecycle § round 能不能放在 aos-loop／fsm 下｜round 現況：[10-28 agent-round](../../28/agent-round/README.md)（[§ 2 一輪本身](../../28/agent-round/02-2-round-一輪本身.md#2-round一輪本身)、[§ 3 掛勾](../../28/agent-round/02-2-round-一輪本身.md#3-掛勾hook)、[做 round 時再代定的 27～38](../../28/agent-round/08-實作時代定.md#做-round-時再代定的10-28-晚第-5-步代定可翻案)）｜aos-loop 的定位：[10-28 medium 決定 2](../../28/medium/03-決定與結論-10-28-晚.md#決定與結論10-28-晚)｜條文：[N-36、N-38、N-39](../../../../docs/NORMS/07-基礎設施-組合子.md)、[N-43](../../../../docs/NORMS/01-總則.md)、[N-53](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-07](../../../../docs/NORMS/05-基礎設施-窗.md)、[P-19、P-20](../../../../docs/CONVENTION/02-題目stack停錯腦.md)、[P-35、P-36、P-38](../../../../docs/CONVENTION/06-巢狀.md)、[C-54](../../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)｜實作：[impls/aos-fsm](../../../../impls/aos-fsm/README.md)、[impls/aos-loop](../../../../impls/aos-loop/README.md)、`lib/agent/round/`、[demo/agent-nia、agent-dan-q](../../../../templates/README.md)

規矩見 [thinking/README](../../../README.md)。**這份整份是 fable 照原則代定的細節設計，可翻案**；使用者定的在 eca § 翻案（三條決定）。使用者 10-30「都照建議」：衝突七條、方向題三條全照建議，見 [§ 決定](07-決定.md#決定10-30)；實作第 1～7 步做完、條文落正文。

**11-01 改**（[10-31 parts-round § 決定](../../31/parts-round/README.md#決定11-01-使用者)、[05 § 實作計畫](../../31/parts-round/05-方向題與實作計畫.md#實作計畫) A 題）：queue 空的停法是 argv `aos-round --on-empty stop|idle`（沒給＝stop、壞值 `ArgumentsBad`），不讀環境變數與 round 槽；`aos-parts` 刪了；`parts.json` 是 aos-exec 格式。下文講 round 槽、`ROUND_ON_EMPTY`、`aos-parts which` 的地方照這條讀。

**11-03 晚使用者刪掉整條線**（頂層說 `lib/agent/round/` 還在、被 agent-nia、ask_round、測試用到之後，逐字）：「封存這條線，1.該刪的都刪光刪乾淨」；再問到 aos-ai 也靠 agent-nia 時：「一起刪，剛剛那些說會整合到aos-agent的，也都可以刪一刪。只需要留下他們的概念就好，也就是不用留程式碼，留文檔就好。我沒有要用他們」→ `lib/agent/round/`、parts、queue、history、act、compact、`lib/endpoint/`、`lib/aos/ask_round`、`demo/agent-nia`、aos-ai 與它們的測試都刪了；下文講到的程式都已不存在，概念收在 proto8/archive/agent-round-concepts/。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-前提](01-前提.md) | 前提（引用哪些決定） |
| [02-A-N-36-分岔的格式](02-A-N-36-分岔的格式.md) | A. N-36 分岔的格式（結論） |
| [03-B-aos-round-長什麼樣](03-B-aos-round-長什麼樣.md) | B. aos-round 長什麼樣（結論） |
| [04-C-換過去的路](04-C-換過去的路.md) | C. 換過去的路（結論）、D. 「拆散放進每一格」那條路（一段話）、條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文） |
| [06-衝突](06-衝突.md) | 衝突（跟既有原則、實作對不上的；寫給使用者看）、方向題（原則推不出的，附背景例子） |
| [07-決定](07-決定.md) | 決定（10-30）、實作時代定（10-30，隊長與工人照原則定的細節，可翻案） |
| [08-10-31-使用者想法-控制流不拉-seq／if](08-10-31-使用者想法-控制流不拉-seq／if.md) | 10-31 使用者想法：控制流不拉 seq／if 拼、整合成單檔；tasks／seq／if 之後順便做（先記、之後處理） |

<a id="前提引用哪些決定"></a>
<a id="a-n-36-分岔的格式結論"></a>
<a id="b-aos-round-長什麼樣結論"></a>
<a id="c-換過去的路結論"></a>
<a id="d-拆散放進每一格那條路一段話"></a>
<a id="條文草稿草稿待使用者看不改-normsconvention-正文"></a>
<a id="norms-組合子-n-36-改口next-兩種寫法"></a>
<a id="norms-組合子-n-39-加註trace-加-next"></a>
<a id="norms-總則-n-43-加註"></a>
<a id="convention-p-20p-35-加註"></a>
<a id="thinking-舊紀錄"></a>
<a id="實作步驟分步每步可驗都在-proto8linuxwsl-跑測試通讀-wf-規矩後派-opus每步一個-commitctest-與-pytest-全綠"></a>
<a id="衝突跟既有原則實作對不上的寫給使用者看"></a>
<a id="方向題原則推不出的附背景例子"></a>
<a id="決定10-30"></a>
<a id="實作時代定10-30隊長與工人照原則定的細節可翻案"></a>
<a id="10-31-使用者想法控制流不拉-seqif-拼整合成單檔tasksseqif-之後順便做先記之後處理"></a>
