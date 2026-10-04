# astra-4 QA 分工與邊界

基準 HEAD：`b8568cdbf8122b1aaa11b9e67c49228e0e145d2c`。
使用者授權最多四條 subagent 線；不修改產品／既有測試／既有文件、不 commit／push，不動 scratchpad、不呼叫 LLM。各線只寫下列自己的 evidence 子目錄，測試使用自建 /tmp，自己回收 PID、清自己的根。

| 線 | 唯一可寫領地 | 可觀察驗收 |
|---|---|---|
| stress | stress/ | 三次完整測試結果；10 次 G3 與全套重疊、PID／回合證據；清場 |
| core | core/ | A4-01/02/05/06 修後探針；birth／移項 SIGKILL 與槽刪除時點；F47 history／once_retry；清場 |
| step | step/ | A4-03/04/07；F47 step；450 回合與同階段檔數；清場 |
| contracts | contracts/ | 核心卡 grep 零匹配、spec 引用抽查、七包卡程式對照；account 草稿意見獨立 |

主線彙整報告、核對證據與基準雜湊；不改來源。舊 evidence 只能讀或複製到本輪後調整。
