# 2026-10-30 agent 的 queue、外部 coding agent 的生命週期、session 檔接管（fable 規劃）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜出發點：[10-29 agent-bob § 決定（10-30）](2026-10-29-agent-bob/04-頂層對八題的再想.md#決定10-30)（決定 33～35）｜前一份規劃：[10-29 medium-plan](2026-10-29-medium-plan.md)｜相關條文：[N-14～N-16](../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-63、N-64](../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-11～P-14、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[C-65～C-67](../docs/CONCEPTS/03-基礎設施.md#資料夾程式工作區與-stack10-19)、[C-75](../docs/CONCEPTS/03-基礎設施.md#proc-之間的交流10-29)｜程式（只翻、沒改）：[lib/agent](../lib/README.md) 的 queue／history／round、[extras/human](../extras/human/README.md)、[extras/cli_hub](../extras/eca_hub/README.md)、[impls/aos-daemon](../impls/aos-daemon/README.md)、[impls/aos-post](../impls/aos-post/README.md)

規矩見 [thinking/README](README.md)。**這份整份是 fable 照原則代定的細節設計，可翻案**；使用者定的在 agent-bob 的決定 33～35。條文草稿標「草稿、待使用者看」，**NORMS／CONVENTION 正文沒動、程式沒動**。衝突與方向題寫在文末，寫給不看 CS 術語的人。**10-30 使用者「都照建議」→ [§ 決定（10-30）](2026-10-30-agent-lifecycle/07-衝突.md#決定10-30)**。**10-30 第 10 步落正文（縮小範圍）**：只落跟第 1～5、7、8 步直接相關的條文，hub 那部分暫緩；每條的狀態標在[條文草稿](2026-10-30-agent-lifecycle/04-各題結論.md#條文草稿草稿待使用者看不改-normsconvention-正文)各條上。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-前提](2026-10-30-agent-lifecycle/01-前提.md) | 前提（引用哪些決定）、各題結論（每條標照哪條原則／決定） |
| [02-各題結論](2026-10-30-agent-lifecycle/02-各題結論.md) | 各題結論（每條標照哪條原則／決定） › A. agent 層的 queue |
| [03-各題結論](2026-10-30-agent-lifecycle/03-各題結論.md) | 各題結論（每條標照哪條原則／決定） › B. 納管外部 coding agent 的生命週期 |
| [04-各題結論](2026-10-30-agent-lifecycle/04-各題結論.md) | 各題結論（每條標照哪條原則／決定） › C. 外部 agent 的 session 檔接管、各題結論（每條標照哪條原則／決定） › D. 其餘三題照隊長建議（決定 35）、條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文）、條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文） › CONVENTION 四、題目與答案、條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文） › NORMS 窗 N-16 加註 |
| [05-條文草稿](2026-10-30-agent-lifecycle/05-條文草稿.md) | 條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文） › NORMS loop 與 daemon N-28、N-54 加註（exec 型子項，②）、條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文） › CONCEPTS C-65 例子改口、條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文） › hub 的說明（extras/cli_hub、CONVENTION adapter 那段） |
| [06-實作步驟](2026-10-30-agent-lifecycle/06-實作步驟.md) | 實作步驟（分步、每步可驗；都在 proto8，Linux／WSL 跑測試） |
| [07-衝突](2026-10-30-agent-lifecycle/07-衝突.md) | 衝突（跟既有原則、實作對不上的；寫給使用者看）、方向題（原則推不出的，附背景例子）、決定（10-30）、實作時代定（10-30，隊長與工人照原則定的細節，可翻案） |
| [08-實作時代定](2026-10-30-agent-lifecycle/08-實作時代定.md) | 實作時代定（10-30，隊長與工人照原則定的細節，可翻案） › 第 1～5 步、實作時代定（10-30，隊長與工人照原則定的細節，可翻案） › 第 7、8 步與 aos-daemon-ctl、實作時代定（10-30，隊長與工人照原則定的細節，可翻案） › 第 10 步條文 |
| [09-實作時代定](2026-10-30-agent-lifecycle/09-實作時代定.md) | 實作時代定（10-30，隊長與工人照原則定的細節，可翻案） › 改名、實作時代定（10-30，隊長與工人照原則定的細節，可翻案） › 使用者問：round 能不能放在 aos-loop／fsm 的框架下實現（10-30，只查、沒改） |

<a id="前提引用哪些決定"></a>
<a id="各題結論每條標照哪條原則決定"></a>
<a id="a-agent-層的-queue"></a>
<a id="b-納管外部-coding-agent-的生命週期"></a>
<a id="c-外部-agent-的-session-檔接管"></a>
<a id="d-其餘三題照隊長建議決定-35"></a>
<a id="條文草稿草稿待使用者看不改-normsconvention-正文"></a>
<a id="convention-四題目與答案"></a>
<a id="norms-窗-n-16-加註"></a>
<a id="norms-loop-與-daemon-n-28n-54-加註exec-型子項2"></a>
<a id="concepts-c-65-例子改口"></a>
<a id="hub-的說明extrascli_hubconvention-adapter-那段"></a>
<a id="實作步驟分步每步可驗都在-proto8linuxwsl-跑測試"></a>
<a id="衝突跟既有原則實作對不上的寫給使用者看"></a>
<a id="方向題原則推不出的附背景例子"></a>
<a id="決定10-30"></a>
<a id="實作時代定10-30隊長與工人照原則定的細節可翻案"></a>
<a id="第-15-步"></a>
<a id="第-78-步與-aos-daemon-ctl"></a>
<a id="第-10-步條文"></a>
<a id="改名"></a>
<a id="使用者問round-能不能放在-aos-loopfsm-的框架下實現10-30只查沒改"></a>
