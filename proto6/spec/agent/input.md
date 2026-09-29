# 輸入與回覆

← [Agent](README.md)｜[投件](../base/transport.md)｜[儲存](../base/storage.md)

## A-201 收件與消費

〔使用者方向 2026-09-29〕有投件權限就能把訊息放進 node 的收件區；人與 agent 使用相同入口。請求 ID 用來定址及去重，完整發布、同 ID 衝突、授權與保留期限依[投件規則](../base/transport.md)。

消費、提交及還原依[通用 tick 的 Q1](../tick.md)；訊息與工具／LLM 結果適用同一規則。收件成功只代表內容已存妥，不代表 agent 已閱讀或完成。

〔使用者方向 2026-09-29〕一般訊息與回覆都用 `agent.say`，一律收進 history；回覆 payload 加可省的 `in_reply_to` 指原句 ID。格式與大小依[訊息協議](../protocol/messages.md)，錯誤或存不下不假稱成功。

驗收：收件中斷場景見 [V-03](../conformance.md)。

## A-202 普通訊息的輪次邊界

（09-29 重寫：已刪；輪次併入[工作分組](../scheduling/runs.md)，結果配對併入 [A-403](tools.md)，消費提交併入[通用 tick](../tick.md)。）

## A-203 暫停、取消與輸出

〔建議預設，未拍板〕本地回覆檔保留輸出 ID、`input_id` 與 `progress`／`final`；正式讀端只讀已 commit 的版本，`final` 條件見 [agent 任務](README.md)。〔使用者方向 2026-09-29〕回傳給傳訊者也用 `agent.say`；`aos agent listen` 依 `in_reply_to` 分組讀 history 中的回覆。

暫停、取消及恢復用[共通操作](../scheduling/operations.md)，不另設 agent 控制入口。操作已受理不等於工作已停止，也不等於任務已完成。

驗收：回答寫入後、commit 前中斷，讀端不顯示這份未提交回答；只有已提交輸出可當正式回覆。
