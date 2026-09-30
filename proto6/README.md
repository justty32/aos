# proto6 — Linux agent 架構規劃

proto6 承接 2026-09-28 的 Linux 身分、資源管理與萬 agent 討論。**目前有 [notes](notes/README.md)、[規格草案](spec/README.md)、可重跑隔離探針，以及可跑的第一段原型 [proto/](proto/README.md)，還不是完整的 agent 產品。**

**現行方向（第十九批，09-30，spec 正依它改寫中）**：三層架構——tick 核心（互斥鎖、照任務表跑、上下層）、標準配備（git 提交、needs、收件、切換使用者、cgroup 框、once 等，跟核心同一支 aos-tick、必須全掛，需要 cgroup v2 與 git）、其他掛載（kernel、agent、clock、自訂任務）；詳見[第十九批方向](notes/verdicts/10-tick-minimal-core.md)。

先讀 [spec 入口](spec/README.md)：可實作的欄位、狀態、交接與驗收，現行以它為準。再從 [notes 入口](notes/README.md) 看最新方向、裁定紀錄與背景；要看歷史，再讀 09-28 的[三大概念](notes/concepts.md)（用語已被 node／kernel 樹取代）與封存的交接來源。現行程式仍在 [proto5](../proto5/README.md)。
