# node 樹與資源

← [規格入口](../README.md)｜[術語](../terms.md)

## 一棵逐層管理的樹

〔使用者方向 2026-09-29〕node 與角色定義見[術語](../terms.md)。kernel 管直接成員的排程與資源；成員也是 node。下層在父層眼中是一件工作，上層只看它提供的摘要，不讀下層成員內容。

node 的登記、路徑 id、叫醒與重啟重建由 [daemon](../daemon.md) 定義；身分額度見[身分與 OS 資源](../base/identity-resources.md)。各 node 自己推進狀態，提交與恢復依 [tick](../tick.md)，不承諾跨 node 一起提交。

〔使用者方向 2026-09-30，第十八批〕**aos 只給框架**：tick 基底、Linux 隔離（帳號、cgroup）與登記框架；任務種類、資源與隔離政策由各 kernel 自己定，上下層不必對齊（[T-06](../terms.md)）。本篇寫的排程、資源六類、LLM 三檔、份額、窗口與重試，除了標明屬框架的部分，都是 aos 附的**預設 kernel 範本**的規則；範本的檔案、argv 與欄位見 [kernel 預設範本](../protocol/kernel-tasks.md)。只有 cgroup 上限與身分額度照 Linux 維持巢狀（[S-203](admission.md)）。

## 本篇地圖

- [排程與資源 module](admission.md)：成員摘要、新格判斷、通知補查與成員登記、逐層分配、套用與故障、中間層卡住。
- [LLM module 與池](llm.md)：三檔（自己排／交給 endpoint／直連）、池 node、份額、key 保護邊界、限流與串流。
- [工作與可選 run](runs.md)：輪次、取消、恢復、重試與遲到結果。
- [查詢與待處理事項](operations.md)：摘要、unknown 與從未開始的證據、待辦清單與 `aos-attend`、給 kernel 的一般回話。
