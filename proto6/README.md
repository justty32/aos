# proto6 — Linux agent 架構規劃

proto6 承接 2026-09-28 的 Linux 身分、資源管理與萬 agent 討論。**目前有 [notes](notes/README.md)、[規格草案](spec/README.md)、可重跑隔離探針，以及可跑的第一段原型 [proto/](proto/README.md)，還不是完整的 agent 產品。**

**現行方向（第二十批，09-30，spec 正在依它改寫中）**：tick 是 aos 的衡量基準（排程以 tick 為單位、整個體系基於 tick）；tick 核心只有四樣（鎖、照表跑、上下層、每項結束碼紀錄）；git 開格／收尾、收件、投件、發摘要、清理等是掛在任務表上的系統級任務（`kind:"system"`），`aos-cg`、`aos-as`、`aos-needs` 是普通程式（2026-10-01：`aos-needs` 改寫成 `aos-tick-check-task`、發摘要搬暫緩區，見 [B-621](spec/settled/deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）；tick–daemon 通道是唯一逃生口；不再有標準配備、全掛、兩級。詳見[第二十批方向](notes/verdicts/11-tick-as-unit.md)。

**前一輪（第十九批，已被第二十批取代標準配備結構，僅供對照）**：三層架構——tick 核心（互斥鎖、照任務表跑、上下層）、標準配備（git 提交、needs、收件、切換使用者、cgroup 框、once 等，跟核心同一支 aos-tick、必須全掛；cgroup v2 與 git 是「完整保證」的條件，沒有時走標準配備內建備援，仍算全掛、只是保證較弱）、其他掛載（kernel、agent、clock、自訂任務）；詳見[第十九批方向](notes/verdicts/10-tick-minimal-core.md)。

**開始實作**（09-30 起，先由 AI 隊寫 Python POC，最後才換 C++11）：六段規劃與第一段細部見 [plan/](plan/README.md)，程式放 `src/`。

先讀 [spec 入口](spec/README.md)：可實作的欄位、狀態、交接與驗收，現行以它為準。再從 [notes 入口](notes/README.md) 看最新方向、裁定紀錄與背景；要看歷史，再讀 09-28 的[三大概念](notes/concepts.md)（用語已被 node／kernel 樹取代）與封存的交接來源。現行程式仍在 [proto5](../proto5/README.md)。
