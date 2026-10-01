# node 樹與資源

← [規格入口](../README.md)｜[術語](../terms.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

## 一棵逐層管理的樹

〔使用者方向 2026-09-29〕node 與角色定義見[術語](../terms.md)。kernel 管直接成員的排程與資源；成員也是 node。下層在父層眼中是一件工作，上層只看它提供的摘要，不讀下層成員內容。

〔使用者方向 2026-09-30，第十九批〕誰是誰的上層，預設看資料夾包含、可經 daemon 登記覆蓋（[B-628](../settled/tick.md)）；覆蓋只改管理關係，管轄權仍跟著資料夾。node 的登記、路徑 id、叫醒與重啟重建由 [daemon](../settled/daemon/README.md) 定義；身分額度見[身分與 OS 資源](../base/identity-resources.md)。各 node 自己推進狀態，提交與恢復依 [tick](../settled/tick.md) 的標準配備，不承諾跨 node 一起提交。

〔使用者方向 2026-09-30，第十八批；第十九批改寫〕**aos 只給框架**：tick 核心與標準配備（含切換帳號與 cgroup 框，[B-626](../settled/tick.md)、[B-629](../settled/deferred/template.md)）與登記框架；任務種類、資源與隔離政策由各 kernel 自己定，上下層不必對齊（[T-06](../terms.md)）。本篇寫的排程、資源六類、LLM 三檔、份額、窗口與重試，除了標明屬框架的部分，都是 aos 附的**預設 kernel 範本**的規則；範本的檔案、argv 與欄位見 [kernel 預設範本](../protocol/kernel-tasks.md)。只有 cgroup 上限與身分額度照 Linux 維持巢狀（[S-203](admission.md)；cgroup 走備援時上限不巢狀，見同條）。本篇的保證以標準配備全掛為前提（[T-01](../terms.md)）。

## 本篇地圖

- [排程與資源 module](admission.md)：成員摘要、新格判斷、通知補查與成員登記、逐層分配、套用與故障、中間層卡住。
- [LLM module 與池](llm.md)：三檔（自己排／交給 endpoint／直連）、池 node、份額、key 保護邊界、限流與串流。
- [工作與可選 run](runs.md)：輪次、取消、恢復、重試與遲到結果。
- [查詢與待處理事項](operations.md)：摘要、unknown 與從未開始的證據、待辦清單與 `aos-attend`、給 kernel 的一般回話。
