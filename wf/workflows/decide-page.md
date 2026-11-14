# decide-page：離線互動頁已停用（2026-11-14）

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

**這個工作流不用了**（使用者 11-14 專區「q2:retire」）。要使用者裁的題目一律寄使用者專區，會出現在全景頁：

- 寄法：`aos-user send --kind decide`，一封最多 7 題，超過就分封；實際指令與回信怎麼驗見 [aos-teams 入口第 2 件](dispatch/aos-teams.md)、[user-zone-mail](../public/user-zone-mail.md)。
- 裁定落回各線：出題線的紀錄加「使用者裁定（日期）」段，回信原文逐字貼上。

原本的全文（題目資料檔格式、出頁、收回答、跟看板怎麼分）在 `common/archive/decide-page.md`。`wf/tools/decide_page/` 的產生程式留著沒刪，只是不再叫人用。
