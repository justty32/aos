# 2026-11-17 CONVENTION 精簡：純條文拆成上下兩份（各 <8 KB），例子、細節、原話、出處留在分檔；本檔是驗證數字與條號對照

← [tidy](../README.md)｜線 convention-1117（opus）｜範本：[2026-11-17-concepts精簡](2026-11-17-concepts精簡.md)

## 結果

- 純條文兩份：`proto8/docs/CONVENTION.md`（上：保證的底、佈局、命名、入口與 loop／fsm、題目與答案、stack，7985 B）、`proto8/docs/CONVENTION/00-慣例-下.md`（下：停與錯、腦與工具、shell 版與 inst 版、巢狀、命令列、慣例不管的，8104 B）。每條一兩句、帶條號；每組一行粗體連結指到既有分檔。
- 入口原有的前言（六個環境變數那段、依據寫法）、實作說明、命名、腦的工具呼叫摘要逐字搬到新檔 `CONVENTION/00-前言-命名-實作.md`（連結重算）；入口的分檔導航表由兩份純條文的組標題取代。
- 既有分檔一個字都沒動（不搬、不改名、錨點不動）；分檔內的沿革與多餘例子照 content-trim 第 2 步另開 commit。
- `proto8/docs/README.md` 講條文分工那句補「CONVENTION 同一種寫法」。

## 驗證

- 原文檢查（HEAD 的 CONVENTION 入口＋整夾裡每句「…」，在現在的入口＋整夾裡找）：364 句，LOST 1，是舊導航表的段名「範例：同一隻 agent 的三種寫法」（分檔標題，不是使用者原話；分檔 04 的標題仍在）；16 句換了檔（入口前言、命名搬家）。
- 條號：HEAD 出現的 48 個條號（P-01～P-48，含移除的 P-32、空號 P-46）在兩份純條文裡都有，缺 0。
- `check_anchors.py proto8`：0；`check_anchors.py wf`：1（`public/pitfalls.md` → `public/README.md#主題`，public-1117 那條線在整理 `wf/public`，不是本線）。
- 連結檢查（proto8＋wf）：42 條壞、28 檔；指到 CONVENTION 的 0。其中 proto8/docs 的 2 條指 `NORMS/00-規範-3-…`（NORMS 那邊正在改的），其餘在 thinking、session_logs、reports。
- CONVENTION.md 原本的錨點（`#分檔`）全 repo 沒有人連，拿掉。

## 條號對照（條號｜純條文檔：行｜細節分檔，路徑從 `proto8/docs/` 起）

| 條號 | 純條文檔：行 | 細節分檔 |
|---|---|---|
| P-01～P-04 | CONVENTION.md:10 | 升成 NORMS N-57～N-60；CONVENTION/01-保證佈局入口/01-一-aos-保證的與二-佈局.md |
| 佈局、時鐘、命名（無號） | CONVENTION.md:11～13 | 同上；命名原文 CONVENTION/00-前言-命名-實作.md |
| P-05～P-10 | CONVENTION.md:18～23 | CONVENTION/01-保證佈局入口/02-三-入口-loop-fsm.md |
| 入口檔不在頂層（無號） | CONVENTION.md:24 | CONVENTION/05-不管落實待決.md（十一） |
| P-11～P-14 | CONVENTION.md:29～32 | CONVENTION/02-題目stack停錯腦/01-P-11～P-14.md |
| P-42 | CONVENTION.md:35 | CONVENTION/02-題目stack停錯腦/02-P-42.md |
| P-43 | CONVENTION.md:36 | CONVENTION/02-題目stack停錯腦/03-P-43-本文.md、03-P-43續-11-04-aos-agent.md |
| P-48 | CONVENTION.md:37 | CONVENTION/02-題目stack停錯腦/10-P-48.md |
| P-15 | CONVENTION.md:42 | CONVENTION/02-題目stack停錯腦/04-五-stack續-P-15.md |
| P-16～P-18 | CONVENTION.md:43～45 | CONVENTION/02-題目stack停錯腦/04-五-stack與六-停與錯.md |
| P-19、P-20 | 00-慣例-下.md:8、9 | CONVENTION/02-題目stack停錯腦/04-五-stack與六-停與錯.md |
| P-21、P-22 | 00-慣例-下.md:10、11 | CONVENTION/02-題目stack停錯腦/04-六-停與錯續-P-21～P-22.md |
| P-23～P-26 | 00-慣例-下.md:16～19 | CONVENTION/02-題目stack停錯腦/05-P-23～P-26.md |
| P-41 | 00-慣例-下.md:22 | CONVENTION/02-題目stack停錯腦/06-P-41.md |
| P-47 | 00-慣例-下.md:23 | CONVENTION/02-題目stack停錯腦/09-P-47.md |
| P-27～P-31 | 00-慣例-下.md:28～32 | CONVENTION/03-shell版與inst版.md（範例 04-範例三種寫法.md） |
| P-33、P-34 | 00-慣例-下.md:37、38 | CONVENTION/06-巢狀/01-P-33～P-34.md |
| P-35 | 00-慣例-下.md:39 | CONVENTION/06-巢狀/02-P-35～P-36.md |
| P-36 | 00-慣例-下.md:40 | CONVENTION/06-巢狀/02-P-36.md |
| P-37～P-40 | 00-慣例-下.md:41～44 | CONVENTION/06-巢狀/03-P-37～P-40.md |
| P-44 | 00-慣例-下.md:49 | CONVENTION/02-題目stack停錯腦/07-P-44.md、07-P-44續-11-10-旗標位置.md |
| P-45 | 00-慣例-下.md:50 | CONVENTION/02-題目stack停錯腦/08-P-45.md |
| 慣例不管的（無號） | 00-慣例-下.md:55 | CONVENTION/05-不管落實待決.md（九） |
| P-32（移除）、P-46（空號） | 00-慣例-下.md:57 | P-32 記錄在 CONVENTION/06-巢狀/01-P-33～P-34.md |
