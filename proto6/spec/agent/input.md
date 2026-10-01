# 輸入與回覆

← [Agent](README.md)｜[投件](../base/transport.md)｜[儲存](../base/storage.md)

## A-201 收件與消費

〔使用者方向 2026-09-29〕有投件權限就能把訊息放進 node 的收件區；人與 agent 使用相同入口。請求 ID 用來定址及去重，完整發布、同 ID 衝突、授權與保留期限依[投件規則](../base/transport.md)。

消費、提交及還原依 [B-623](../settled/tick/mq.md)（Q1），派出與投件依 [B-624](../settled/tick/mq.md)（Q2）；訊息與工具／LLM 結果適用同一規則。收件成功只代表內容已存妥，不代表 agent 已閱讀或完成。

〔使用者方向 2026-09-29〕一般訊息與回覆都用 `agent.say`，一律收進 history；回覆 payload 加可省的 `in_reply_to` 指原句 ID。〔使用者方向 2026-09-29，第十六批〕**帶 `in_reply_to` 的是回話：只記進 history（`in_reply_to` 原樣保存），不建待處理的 input、不觸發 LLM、不再回話**，免得兩邊（或自己對自己）互回無限循環。kernel 收到的 `agent.say` 同樣只記進它自己的 history。〔第十八批，本條為 `in_reply_to` 配對的正本〕這種只記錄的訊息怎麼清，見 [P-716](../protocol/agent-tasks.md)。格式與大小依[訊息協議](../protocol/messages.md)（欄位見 [P-705](../protocol/agent-tasks.md)），錯誤或存不下不假稱成功。

〔使用者方向 2026-09-30，第十九批，補通道收件；第十八批 P-705 的收件行為從協議篇搬上〕**agent 有兩條收件路**：檔案收件（`requests/`，[B-623](../settled/tick/mq.md)）與 daemon 通道上的暫存訊息（[B-614](../settled/deferred/daemon/messaging.md)）。agent module 是 `agent.say`、工作結果的收件任務（任務表宣告，[B-620](../settled/tick.md)），標準配備的收件不代它取通道訊息，所以由 module 自己做：

- **每格先收再推進**：開格後先列一次 `requests/`，最多處理 64 件；同格新回來的件等下格。有通道時（daemon 開的格，[B-612](../settled/deferred/daemon/channel.md)）再用 `node.take` 取暫存訊息，`limit` 用「64 減去這格已列到的件數」，用完就不取，免得取走了又裝不下（取走的 daemon 就刪了）。取到 `more:true` 而額度沒滿就再取。
- **取來的訊息跟檔案件同格式、同規則**：那是一份 `FileRpcRequest`（[P-301](../protocol/messages.md)），module 照請求 bytes 存成 `state/messages/requests/<id>.json` 當消費證據，之後的去重、同 ID 不同內容留事項不覆蓋、提交後才算數，都沿 B-503、B-623；回應仍照回址走檔案投件（B-614）。
- **取走到提交之間當機，訊息就丟了**：通道不保證送達，寄件方要不要補寄自己決定；已提交的不會重吃。沒有通道的格（人手、cron 跑的）只收檔案。
- 「投件權就是執行權」同樣適用：能經通道送進來的，是寄件帳號對本 node `requests/` 有寫權的人（B-614）。
- **接件**：`agent.say` 的 params 是 inst，argv 對應 `aos agent say`，stdin 指向可讀的輸入 JSON。接件後保存回址、原文與附件引用，建 queued input 及 user history；附件只存引用，要內容就用普通讀檔工具。指令結果沿 work-result，收件確認放指令 stdout。帶 `in_reply_to` 的回話依上面的規則只記進 history。收工具／LLM 結果見 [A-403](tools.md)。序號在鎖內遞增、同組提交，首次從 0 開始；不靠牆鐘排輸入，清理不倒退序號；`input_id` 就是原 `agent.say` 的 RPC id。

〔使用者方向 2026-09-30，第十八批〕agent 之間的問答機制、agent 的請求被對方拒收、卡在 unknown 的使用者輸入怎麼收，都延後（[P-008](../protocol/README.md#p-008)）；現行照上面的規則。

驗收：收件中斷場景見 [V-03](../conformance.md)。

## A-202 普通訊息的輪次邊界

（09-29 重寫：已刪；輪次併入[工作分組](../scheduling/runs.md)，結果配對併入 [A-403](tools.md)，消費提交併入[通用 tick](../settled/tick.md)。）

## A-203 暫停、取消與輸出

〔建議預設，未拍板〕本地回覆檔保留輸出 ID、`input_id` 與 `progress`／`final`；正式讀端只讀已 commit 的版本，`final` 條件見 [agent 任務](README.md)。〔使用者方向 2026-09-29〕回傳給傳訊者也用 `agent.say`；`aos agent listen` 依 `in_reply_to` 分組讀 history 中的回覆。

〔第十八批，P-708 從協議篇搬上〕**正式回覆的行為**：進度（progress）沒有結果、終局（final）的結果是 succeeded／failed／canceled／unknown；unknown 的回話只說結果不明，原工作仍保持 unknown；取消要完成本機收尾才算 canceled。回覆跟輸入的關係：

- 同一組提交保存本地 reply、更新 input，並建一份新 ID 的 `agent.say` 請求（`{text, in_reply_to:原 input_id}`），目標是原 input 的回址；本地的 progress／final 不另變成線上欄位。tick 提交後由標準配備投件（[B-624](../settled/tick/mq.md)）。
- 自己回自己也是下格才收，收到時因為帶 `in_reply_to` 只記錄；原 `agent.say` 的回應不改。
- 有終局回話才把 input 記 done 並填完成時間。回話被對方拒收時怎麼辦，延後（[P-008](../protocol/README.md#p-008)）。
- 模型原話不重存 history；程式產生的進度／失敗另建 assistant 事件、指回 reply。`pending_requests` 只記 LLM／工具結果，回話交付另記；本地已提交的 final 可查，不表示對方已接納。

暫停、取消及恢復用[共通操作](../scheduling/operations.md)，不另設 agent 控制入口。操作已受理不等於工作已停止，也不等於任務已完成。

驗收：回答寫入後、commit 前中斷，讀端不顯示這份未提交回答；只有已提交輸出可當正式回覆。
