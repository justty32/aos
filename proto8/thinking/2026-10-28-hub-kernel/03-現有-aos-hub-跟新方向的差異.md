← [入口](../2026-10-28-hub-kernel.md)｜涵蓋：現有 aos-hub 跟新方向的差異（之後要改的）｜上一份 [02-決定](02-決定.md)

## 現有 aos-hub 跟新方向的差異（之後要改的）

10-27 的 aos-hub 是 demo（使用者 10-27「以後再完善」），以下照 10-28 的決定，實作時要改。**10-28 下午已照表改完**（使用者「hub也可以開始做」），做法與代定見 [hub-adapter](../2026-10-28-hub-adapter/01-使用者原文.md#結論二aos-hub-照-10-28-決定改完)：

| 項目 | 現在（10-27） | 新方向（10-28） |
|---|---|---|
| 常駐程式 | 沒有；`aos-hub` 每次當場讀格裡的檔，自動收起靠 aos-loop 跑 `reap.json` | `AOS_HUB` 裡跑一個常駐 aos-kernel 管實例，狀態以它記的為準；kernel 沒在跑，指令直接報錯 |
| 位置 | `AOS_HUB` 沒設＝`~/.local/state/aos-hub/` | 一律 `AOS_HUB`；沒設＝報錯 |
| Ctrl-] | 跳出並叫 `aos-hub pick` 換一格 | 只跳出、不結束實例 |
| 停的方式 | 只有 `stop`（＝收起，叫得回來） | 分 `pause`（＝現在的收起）和 `stop`（結束、歸檔、不再叫回） |
| 舊對話 | 留在格裡，沒歸檔 | stop 時歸檔，放在工作區的 `.stack/` 底下（具體路徑實作時定） |
| 指令 | `ls`、`pick`、`attach`、`watch`、`stop`；cd 過去打 `aos-hub` 直接接 | 筆記的 `state`（這裡是不是納管的實例）、`open [資料夾]`（＝現在的 `aos-hub`／`attach`）、`ls`；`state` 現在沒有 |
| 管哪些 CLI | claude、codex（cli_session 用過的格） | 加 pi coding agent 之類 |
| 數量上限 | 沒有 | 實作時再說 |
