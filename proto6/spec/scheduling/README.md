# node 樹與資源

← [規格入口](../README.md)｜[術語](../terms.md)

## 一棵逐層管理的樹

〔使用者方向 2026-09-29〕node 與角色定義見[術語](../terms.md)。kernel 管直接成員的排程與資源；成員也是 node。下層在父層眼中是一件工作，上層只看它提供的摘要，不讀下層成員內容。

node 的登記、路徑 id、叫醒與重啟重建由 [daemon](../daemon.md) 定義；身分額度見[身分與 OS 資源](../base/identity-resources.md)。各 node 自己推進狀態，提交與恢復依 [tick](../tick.md)，不承諾跨 node 一起提交。

## 本篇地圖

- [排程與資源 module](admission.md)：成員摘要、通知補查、逐層分配與序號。
- [LLM module 與池](llm.md)：份額、代發、key 保護邊界與限流。
- [工作與可選 run](runs.md)：輪次、取消、恢復、重試與遲到結果。
- [查詢與待處理事項](operations.md)：摘要、unknown 與 `aos-attend`。
