← [T1 報告](README.md)｜任務書：[review-task.md](review-task.md)

# astra（gpt-6-astra）唯讀審查：第一波第 1 隊

原文照貼（檔案連結改成相對 repo 根的路徑）；每條怎麼修在 [README](README.md#astra-審查) 的表。

---

**必修**

1. **[P1] 投遞契約漏掉「已被收走」的去重規則。**  
   位置：[mail.md:34](/proto5/spec/team/mail.md:34)、`aos_agent_say.drop_new`。  
   `link` 只能防止覆蓋仍在 input 的信。若投完、agent 收走、郵差尚未記帳就崩潰，重跑會再投一次。`catalog.md` T-post 原本要求查 `input/done/` 與 `state.intake.files`，共用規範卻沒保留。  
   **改法：**把完整去重順序、封存憑據保留條件、巢狀後續動作的固定 id 寫進共用契約。不能讓第 2 隊只照 `drop_new=False` 判斷投過。

2. **[P1] `open_review` 不符合「同 src 回同一份動作」。**  
   位置：[aos_team_task.py:341](/proto5/lib/aos_team_task.py:341)。  
   函式忽略動作裡的 rev／attempt，改讀父單「目前」版本；也沒先按 src 找已開的子單。已開 r1 後父單改派，再重播同 src，會開 r2，甚至父單仍 queued 就開始審查。純記憶體驗證已重現。  
   **改法：**先按 src 找原結果；新動作必須攜帶並核對原 rev／attempt，且父單須為 reviewing。過期動作也要留下可重播的忽略結果。

3. **[P1] 逾期處理有漏通知窗口。**  
   位置：[aos_team_task.py:442](/proto5/lib/aos_team_task.py:442)。  
   `check_deadlines` 先把單子寫成 failed，再回通知清單。若郵差在保存清單前崩潰，下次掃描跳過終態單，原通知永遠不再回傳。已驗證第一次回一筆、第二次回空。  
   **改法：**先持久化到期事件，再呼叫 `step`；或提供掃描未完成 history effects 的恢復流程，直到郵差確認完成。

4. **[P1] 回答問題可以錯誤恢復另一件等待。**  
   位置：[aos_team_ask.py:43](/proto5/lib/aos_team_ask.py:43)、同檔 71 行；`aos_team_task.py:202–209`。  
   非負責人可把問題的 `reply_to` 指向別人的單；`needs_user` 雖會擋，但人回答後仍無條件產生 resume。另一個情境是：舊負責人的問題尚未回答，任務已改派、新負責人在等另一題；舊答案會清掉新的等待。  
   **改法：**問題保存關聯任務的 rev、負責人；回答只恢復相符版本，且 `waiting_on` 必須是該 q-id。沒有有效關聯的問題只寄答案，不改任務。

5. **[P1] 額外掛點沒有團隊層級的保護，能破壞身分牆。**  
   位置：[aos_agent_init.py:66](/proto5/lib/aos_agent_init.py:66)、`aos_agent_access.py:339`。  
   預設三掛點合理，但額外 mounts 只限制名字；現有信任集合主要保護「自己這個家」。例如工人額外掛入 `team/outbox/human`、`team/tasks` 或另一成員的家為 rw，不會因它們屬於團隊而被擋。工人便能用 bash 冒充 human、改單或改別人的設定。這需要人先配置該掛點，**不是預設配置直接可逃逸**。  
   **改法：**增加團隊保護集合，驗證實際路徑與符號連結；自己的 outbox 以外，團隊控制資料不得 rw。自訂模板及其 `may` 來源也須納入保護，避免放在工人可寫的專案內。

6. **[P1] init 有兩個無法正確補完的崩潰窗口。**  
   位置：[aos_agent_init.py:158](/proto5/lib/aos_agent_init.py:158)、同檔 128 行；`aos_agent_tools.py:201`。  
   - 建目錄／marker 後、`info.json` 寫出前崩潰：重跑走非空目錄檢查，直接 `NotEmpty`，沒有讀 marker 恢復。
   - 工具 manifest 寫出後、`info.tools` 更新前崩潰：重跑看到 manifest 已在就跳過，最後還會標 complete；工具實際沒掛進 agent。  
   **改法：**無論 info 是否存在都辨識初始化階段；逐項核對必需檔案、工具引用與設定後才標 complete。不能用「manifest 存在」代替「安裝完成」。

7. **[P2] 投遞／收件事件沒有綁定真正的派工信。**  
   位置：[aos_team_task.py:432](/proto5/lib/aos_team_task.py:432)。  
   `_mail_event` 只核對收件人，沒核對 REQUEST、來源或派工 id，也沒傳 attempt。同 rev 的舊信，甚至一般 PROGRESS 信，只要 `reply_to` 指向任務，就能把 queued 推成 sent；已重現。舊派工信的收件事件也可能冒充下一次修正已被接手。  
   **改法：**任務保存本次派工 id；delivered／picked_up 必須匹配該 id、rev、attempt，不能從任意關聯信推進。

8. **[P2] 驗收／審查事件缺版本仍被接受，與規格矛盾。**  
   位置：[aos_team_task.py:146](/proto5/lib/aos_team_task.py:146)、同檔 213、227 行。  
   規格要求 rev、attempt 對上；程式卻把 `None` 當通配。純記憶體驗證中，完全不帶兩者的 verified 仍把 verifying 推成 reviewing。這會讓第 2 隊漏欄位時靜默接受錯代結果。  
   **改法：**verified／reviewed 必須具有合法整數 rev、attempt 並嚴格相等；缺欄位直接報格式錯。

9. **[P2] 審查子單失敗／取消後，父單沒有收尾事件。**  
   位置：[aos_team_task.py:193](/proto5/lib/aos_team_task.py:193)、同檔 240、379 行。  
   子單進 failed／cancelled 時只處理自身；父單仍 reviewing。後續 `review_result` 又被 Closed 擋下。沒有 deadline 時只能靠人另行取消／改派父單，流程不會自己收尾。  
   **改法：**定義子單終止如何通知父單並轉 blocked／failed，或開替代審查；共用規格也要明訂恢復入口。

10. **[P2] rm 搬家與更新名冊之間沒有恢復紀錄。**  
    位置：[aos_team.py:225](/proto5/lib/aos_team.py:225)。  
    家搬走後、名冊寫回前崩潰，名冊仍指向不存在的家。重跑 rm 可完成，但若先跑 init，就會按舊名冊重新生出成員，偏離原本移除意圖。  
    **改法：**先寫移除意圖與固定目的地，讓 rm／init 都辨識並完成該操作；完成後才清除紀錄。

**建議**

- **權限主幹基本正確。**正常配置下，工具拒收 `from`／outbox 等額外參數；寄件身分取自工具設定與 outbox 目錄。`may_send`、cancel／reassign 的開單人檢查、human-only answer、子單負責人檢查都有做。舊 rev、錯負責人的 report、審查子單的 DONE，以及父單已改派後收到舊 reviewed，也都有防線。上述額外掛點缺口補好後，這些防線才完整。
- **門房比對符合要求。**有 fullmatch、多重命中／否定詞落穿、使用前驗例句。`fill` 是單次替換，群組值中的 `{}` 不會再展開，也沒有 shell 拼接；路徑仍須由最終使用者驗證。`run` 走固定 CLI 分派表；`tool` 可選到 `base/bash`，因此**人寫的 routes 可以配置任意主機命令**。這不是模型參數注入，但應明確寫成「具有主機執行權的設定」，不能只用「限定工具包」描述邊界。T1 報告已有揭露牢外執行。
- **測試要補真正的中斷點。**現有 init crash 測試是在完整初始化後刪工具、改 marker，沒有覆蓋必修第 6 點。應補逐寫入窗口、收件後未記帳、父單改派後重播、舊問題答案、子單終止，以及額外掛點／跨家寫入的負向測試。將 `TeamIntegrationTests` 移出純單元測試集合，避免唯讀審查命令意外啟動服務。
- **格式與維運再收緊。**`validate_request` 遇到 `kind: []` 等錯型別會在字典查找時拋 `TypeError`，應統一轉成 `TeamError`；failed 任務改派仍保留已過期 deadline，容易立刻再次 failed，應定義如何重設。重跑 init 若更換模板，應核對 marker 並拒絕不一致，避免新 `may` 搭配舊工具／舊 access。

總評：骨架正常路徑清楚，但目前還不能把「任意窗口崩潰皆可重跑、不漏做」當成已成立的共用契約；建議先修必修項再交第 2、4 隊依賴。本次未修改檔案、未跑模型或啟動 daemon／kernel。指定測試共 60 項，57 項因唯讀沙箱無法建立暫存目錄而在 setup 報錯，不能宣稱全綠；另以不寫檔的記憶體驗證確認了審查重播、逾期通知、錯誤恢復、投遞事件及缺版本驗收問題。