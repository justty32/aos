# proto6 — Linux agent 架構規劃

proto6 承接 2026-09-28 的 Linux 身分、資源管理與萬 agent 討論。**目前有 [notes](notes/README.md)、[規格草案](spec/README.md) 與可重跑隔離探針，還不是可執行的 agent 產品。** 沒有新增 CLI、daemon、lib 或 CMake 子專案。

先讀 [spec 入口](spec/README.md)：可實作的欄位、狀態、交接與驗收，現行以它為準。再從 [notes 入口](notes/README.md) 看最新方向、裁定紀錄與背景；要看歷史，再讀 09-28 的[三大概念](notes/concepts.md)（用語已被 node／kernel 樹取代）與封存的交接來源。現行程式仍在 [proto5](../proto5/README.md)。
