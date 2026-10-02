# 完整性與驗收入口

← [規格入口](README.md)

> **〔2026-10-01 殘留註記〕本篇整理區以外的段落（指向 `settled/` 的各條以整理區為準）是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md)）：
> - `aos-as`（任務自己換帳號）：第十三批暫緩（[P-212](settled/deferred/protocol/tick/01-P-207加入設定與P-212切換帳號.md#p-212aos-as切換帳號建議預設未拍板)）；現行切帳號只在 daemon 設定檔做（帳號模組 [B-646](settled/daemon/account.md)）。
> - `aos-git`（開格、存檔點、收尾）與有 git 版範本：第十七批暫緩（[B-630](settled/deferred/git.md)）；要提交、還原改用 hook 加普通 git 指令（範例在 [B-635](settled/tick/hooks.md)）。
> - 標準任務表範本（[B-629](settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](settled/deferred/mq.md)）、`aos-clean`（[B-404](base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](settled/daemon/mq.md)）。
> - `aos-tick-check-task`（原 `aos-needs`）：第十六批暫緩（[暫緩區 B-621](settled/deferred/tick/03-B-624與B-621.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）。
> - 停格檔 `tick/stop`：第十六批改名 `tick/tasks-blocked`（每項任務之前看、整格最後由 tick 刪；紀錄欄位 `stopped_after` 改 `blocked_before`）；擋板檔 `tick-blocked` 只看存不存在、不讀原因、存在就靜靜回 0（[B-620](settled/tick.md)、[B-636](settled/tick/tasks-blocked.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](settled/terms.md)、[node 模組方向](../notes/verdicts/11-tick-as-unit/08-1001-node模組與統一更新.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](settled/daemon/core.md)）。

## 分檔目錄

> 2026-10-02 整理：原檔約 74 KB 超過 8 KB 門檻，按標題逐字拆進 `conformance/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-V-01-正本規則與概念.md](conformance/01-V-01-正本規則與概念.md) | V-01．何時算拆到可實作 |
| 2 | [02-V-01-正本表.md](conformance/02-V-01-正本表.md) | 正本表 |
| 3 | [03-V-01-新條號.md](conformance/03-V-01-新條號.md) | 新條號 |
| 4 | [04-V-02與V-03開頭.md](conformance/04-V-02與V-03開頭.md) | V-02．先測行為，再測規模；V-03．跨篇故障場景 |
| 5 | [05-V-03-資源LLM與第十八批場景.md](conformance/05-V-03-資源LLM與第十八批場景.md) | 分層資源與 LLM；第十八批新增場景 |
| 6 | [06-V-03-第十九批場景.md](conformance/06-V-03-第十九批場景.md) | 第十九批新增場景 |
| 7 | [07-V-03-第二十批場景.md](conformance/07-V-03-第二十批場景.md) | 第二十批新增場景 |
| 8 | [08-V-03-1001場景.md](conformance/08-V-03-1001場景.md) | 2026-10-01 新增場景 |
| 9 | [09-V-03收尾與V-04-V-05.md](conformance/09-V-03收尾與V-04-V-05.md) | V-04．萬級穩態與冷啟動分開；V-05．規格自身查核 |
