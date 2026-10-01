# 查詢與待處理事項

← [node 樹與資源](README.md)｜[整體驗收](../conformance.md)

讀狀態、處理問題與改設定沿用[入口通則](../README.md)。

## S-401．結果不明就放著

〔使用者方向 2026-09-29〕結果不明的工作保持 unknown，沒人處理就隨定期清理清掉；不自動重做。重啟、逾時、換 boot、登記消失都不是重做的理由；已送出而沒有可靠結果、也不能證明尚未送出的，就是 unknown。這條管 kernel 代掛的 once、agent 自掛的 once、LLM 嘗試與跨 kernel 轉交。〔使用者方向 2026-09-30，第十九批〕once 屬標準配備，經通道掛到 daemon 跑（[B-613](../settled/deferred/daemon/channel.md)）；下面的證據判斷是標準配備（git 提交加 once）的保證。

〔工程預設；第十八批自 P-807、P-402 搬上；第十九批改成掛行程〕**once 有沒有開始，照下面的證據判斷**（檔案位置見 [P-402](../protocol/work.md)、[P-807](../protocol/kernel-tasks.md)）：

- 第一次掛之前：材料已提交（沒 git 時是有完成紀錄，[B-632](../settled/tick.md)），而且 ignored 的啟動標記 `launch-started` 還不存在，才可以掛；先原子排他建立標記、同步檔案與父目錄，再經通道 `node.mount` 掛上。標記已存在就先查證，不重掛。
- 〔第十九批〕`node.mount` 一步就開跑，沒有「已登記、還沒開始」這個中間狀態；掛載行程不存檔，daemon 重啟後不接回（[B-613](../settled/deferred/daemon/channel.md)）。
- 標記已存在：依序核對 daemon 的掛載紀錄（`node.show`：還在跑，或結束後留下的診斷，[B-610](../settled/deferred/daemon/channel.md)）、完整結果與 `.err` 旁檔（[B-613](../settled/deferred/daemon/channel.md)，格式見 [P-110](../settled/deferred/protocol/daemon/provision-and-runner.md)）。
  - 還在跑：等著收，不重掛。
  - 讀到 `.err`：先核對它是本次目標的旁檔、由可信的 daemon 寫出，才合成 `started:false`、failed、`start_failed`；工具自己寫的旁檔不算證據。
  - LLM 的外層程序沒啟動，可以合成 failed、`not_sent`。
  - 其他情況只看 `result.json`：有完整結果就照結果收；已開始、還沒結果就等著收。外層程序 exec 失敗（126／127）、崩潰、自己回 125 卻沒結果，都不能只靠登記消失推定內層沒跑。
  - 其餘（查不到掛載紀錄、換 boot、逾時、沒有可信結果）：unknown，不重掛。〔暫定，交接疑點 a〕標記建好、`node.mount` 還沒送出就當掉的，下一格同樣查不到，也照 unknown 處理（寧可不做，不重做）。
- 證據以啟動標記、`.err`、結果檔與 daemon 的掛載紀錄為主；掛載行程的診斷紀錄會被淘汰（[B-610](../settled/deferred/daemon/channel.md)），查不到不能證明「從未開始」。兩份證據互相矛盾時都保留，並寫一件事項（S-405）。
- 原請求與回件可補投同 ID、同 bytes，只補交付、不重做外部工作（[B-503](../base/transport.md)）。

〔使用者方向 2026-09-30，第十九批；步驟為建議預設，第十九批依方案 A 由 kernel P-806 搬來〕**預設 kernel 範本代掛工具的步驟**（格式見 [P-806](../protocol/kernel-tasks.md)、掛載參數見 [P-402](../protocol/work.md)）：

1. 接件那一格只核對來源、回址與成員身分，保存原件、材料與序號；照 [S-205](admission.md) 判斷能不能派，不能派記 `queued`，可派記 `prepared`，不在接件那一格掛。
2. 已提交的 `prepared` 工作由下一格掛：建 once inst、照上面建啟動標記，再經通道 `node.mount` 掛上，`parent_id` 填發起成員，資源與額度歸成員（[B-613](../settled/deferred/daemon/channel.md)）。daemon 排空停機中回 `stopping` 時，那件工作留在 `prepared`，下次再掛（[B-604](../settled/deferred/daemon/lifecycle.md)）。找不到 daemon 時同樣留在 `prepared`（功能受限，[P-801](../protocol/kernel-tasks.md)）。
3. 結果或 `.err` 由後面的格讀，照上面的證據規則判斷，核對 request／node／job／attempt 後生成 work-result 回件，交標準配備投回。
4. 結果只給路徑；投遞失敗不重開工具，額度仍歸發起成員。

unknown 的資料保留期依 [B-404](../base/storage.md)；它的估計占用什麼時候釋放，由擁有該資源的 kernel 定，LLM 池見 [S-304](llm.md)。

驗收：啟動標記已建、掛載紀錄還在跑時，不重掛、等結果；daemon 重開後掛載紀錄消失、沒有結果也沒有 `.err`，記 unknown，不再掛。

<a id="s-402查詢回應與拒絕理由建議預設未拍板09-29-精簡依冗餘審查-b2b4"></a>

## S-402．查詢回應與拒絕理由

〔使用者方向 2026-09-29〕查詢直接讀有權限的本地檔案或摘要，不為了查詢啟動 node 的 tick。跨層只取下層摘要；不能靠猜 ID 讀到無權存取的內容。一致查詢依 [儲存](../base/storage.md) 讀同一已提交版本，結果到期與清理也以該篇為準；〔第十九批〕node 走 git 備援時沒有版本可釘，讀目前的檔案，不保證一致快照（[B-632](../settled/tick.md)）。

〔建議預設，未拍板〕顯示至少能分清排隊、等待資源、等結果、執行中、暫停、取消中、unknown 與需要人處理；拒絕執行要能看出原因。摘要附來源與觀測時間，預估等待時間不能當保證，也不能把顯示狀態當成成功證據。

資源 module 的啟用與不足處置依 [S-203](admission.md)；已啟用的要求無法滿足，才報部署不可用並停止相關新工作。身分額度不允許開 tick 等啟動錯誤也要看得到，並進 S-405 待處理事項。

驗收：不啟動 node 的 tick 也能分辨「還在排隊」與「結果不明」；父 kernel 看得到子 kernel 的阻擋摘要，讀不到未授權的成員內容。

## S-403．最小量測與過載

（09-29 重寫：已刪；必要容量與拒收邊界併入 [S-203](admission.md) 與[儲存](../base/storage.md)，具體量測留待實作驗證。）

## S-404．留存

（09-29 重寫：已刪／併入[儲存 B-404](../base/storage.md)；保留期與 `aos-clean` 只在該篇定義。）

<a id="s-405待處理資料夾使用者方向-2026-09-29"></a>

## S-405．待辦清單

〔使用者方向 2026-09-29〕attention 是 aos 自己不該或不能處理、交給人或 agent 手動處理的待辦清單。行為以本條為正本，檔案位置、欄位與 IPC 形狀見 [ops P-601](../protocol/ops.md)。

- **兩處**：node 事項放自己的 `.aos/attention/`（ignore、不隨 group 還原）。node 自己寫自己的問題；runner 沒開始、tick 壞掉自動停格（[B-607](../settled/deferred/daemon/registration.md)）、程序清不乾淨、任務表壞（[B-620](../settled/tick.md)），由 daemon 或標準配備寫到該 node；〔第十九批〕標準配備本身不能跑、又沒有終端機可問時（沒全掛，[B-630](../settled/tick.md)），標準配備寫 `reason:"standard_incomplete"`、`issue_id:"standard-incomplete"`，已有就不再寫；單檔掛載行程沿用 `.err`（[B-613](../settled/deferred/daemon/channel.md)）。寫不進去就不管，daemon 在 stdout 警告一行。helper 不見、state 存不下等 daemon 自己的事，走 `daemon.attention.ls/show/done`；`state_dir/attention/` 供重開接續。daemon 要寫的事項先放記憶體、批次寫出，寫完就清掉，重開不讀回（間隔見 [B-607](../settled/deferred/daemon/registration.md)）。
- **內容**：每件事項有白話 `message`，可附 `suggestion`（建議處理文字，可含建議指令，不會自動執行）。事項永遠不帶 `argv`（禁止鍵，[C-07](../contracts.md)），也不夾憑證、key 或完整工作。
- **ID**：同一個還沒解決的問題沿用同一個 `issue_id`，最新細節留在來源自己的狀態檔，不是每格另生一件；不同內容不覆蓋。標完成後再發生，用新 ID。設定檢查的問題照這條寫（`reason:"config_invalid"`，格式見 [P-609](../protocol/ops.md)）。
- **設定錯了**〔第十九批依方案 A 由 P-609 搬來〕：設定檢查由用那份設定的來源程式負責（kernel 的 [P-805](../protocol/kernel-tasks.md)、agent 的 [A-102](../agent/configuration.md)），由它寫自己 node 的 `config_invalid` 事項，message 說檔案、欄位與原因，不夾設定全文或 key。設定錯只停依賴它的新工作，已派工作的結果照收、取消照處理（範本做法見 [S-205](admission.md)）。inst 身分或任務表錯則照 node／daemon 契約拒絕啟動：任務表壞到檢查任務跑不了時由標準配備寫事項（[B-620](../settled/tick.md)），tick 自己停格時由 daemon 寫（[B-607](../settled/deferred/daemon/registration.md)）。
- **保留**：標完成的留一段時間（預設 30 日），還被引用就留，清理依 [B-404](../base/storage.md)。

`aos-attend` 只做三件事，用呼叫者自己的權限，不取得 N 的身分，不改工作結果、不提交 git；實際修理由人或 agent 自己下指令：

- `aos attend ls`：〔第十九批〕沿上下層樹（有效上層，[B-628](../settled/tick.md)）彙整 node 與 daemon 的待辦。
- `aos attend show N ID`：顯示出了什麼事與建議處理。
- `aos attend done N ID`：人或 agent 處理完後標完成；node 事項由 `.aos/attention/open/` 搬到 `done/`，daemon 事項走 `daemon.attention.done`；已完成的再標一次不變。

驗收：兩個 node 同名事項不覆蓋，group 還原不碰事項；daemon 寫不進 node 只警告、不接管。show 只顯示文字，done 只標完成。同一個沒解決的設定錯誤連跑多格只有一件事項；帶 `argv` 的事項整份拒收。

## S-406．給 kernel 的一般回話

〔使用者方向 2026-09-29，第十七批〕別人投給 kernel 的一般回話（`agent.say`）由任務表中宣告 `agent.say` 的那項任務收（預設 kernel 範本是 schedule，[P-803](../protocol/kernel-tasks.md)）：**只記錄**，不裝 LLM、不建待處理輸入、不再回話；帶 `in_reply_to` 的也只記錄（[P-705](../protocol/agent-tasks.md)）。收下後回一個確認回件，交標準配備投出、清原件（[B-623](../settled/tick.md)、[B-624](../settled/tick.md)）。

〔審稿必-4〕記錄照 agent history 的形狀寫進 kernel 自己的 history，序號放 kernel 自己的序號檔，在 node 鎖內遞增、跟 history 同組提交，重啟不倒退。人手 `aos agent listen` 讀的是**同一個 commit 裡任務表宣告 `agent.say` 的那項任務**對應的 history（〔第十九批〕沒有 git 時讀目前的任務表與 history，不保證一致快照，[B-632](../settled/tick.md)）：宣告它的是 agent 任務就讀 agent 的，是 kernel 任務就讀 kernel 的（[P-713](../protocol/agent-tasks.md)）。

只記錄的訊息沒有待處理輸入可以結案，清理以接件確認提交的時間起算、套一般保留期，還被引用就留（[B-404](../base/storage.md)、[P-716](../protocol/agent-tasks.md)）；序號檔不清，清理不能讓序號倒退。agent 之間的問答機制延後（[P-008](../protocol/README.md#p-008)）。

驗收：投給 kernel 的 `agent.say` 留在 kernel 的 history、序號遞增，`aos agent listen` 對這個 kernel 讀得到；kernel 不回第二則話。
