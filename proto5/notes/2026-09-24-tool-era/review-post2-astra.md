五題中，**①間隔、③ `once` 已做到；②身分大致完整；④檢查器壞、⑤只報異常仍有必修漏口。**

只審 `c56044d..HEAD -- proto5` 的兩個 commit，沒有重列第一輪問題。未改檔、未跑模型或 daemon／kernel。追加單元測試被唯讀沙盒擋在建立暫存目錄；以下關鍵分支已用不落檔的記憶體模擬確認，不能視為整套測試通過。

**必修**

- **M1｜檢查器壞了，期限仍會把隊員判失敗。**  
  檔：`proto5/lib/aos_team_post.py`，`checker_broken()`／`watch()`；`proto5/lib/aos_team_task.py`，`due_deadlines()`。  
  **觸發：**有 `deadline` 的任務收到 `broken`，停在 `verifying`；期限一到，`due_deadlines()` 仍產生 `expire`，單子變 `failed`。例行接著可能重派，違反「停著等人修」。模擬已確認。停滯檢查會略過 `verifying`，但期限檢查不會。  
  **建議：**在任務上持久記錄「等人修檢查器」，期限判定明確略過；重驗時處理期限恢復，避免修好立即逾時。不要一律豁免正常驗收中的任務。

- **M2｜例行回報 BLOCKED，等的是人，人卻收不到信。**  
  檔：`proto5/lib/aos_team_task.py`，`apply()` 的 `BLOCKED`／`NEEDS-USER` 分支；`proto5/lib/aos_team_post.py`，`deliver()`。  
  **觸發：**負責人照派工信回 `BLOCKED` 給 `beat`。狀態變成 `blocked`、`waiting_on=human`，但後續動作是空清單；原信寄給 `beat` 又只記錄、不投遞。心跳視為在途，停滯檢查也略過。沒有期限就能永久等下去。直接回 `NEEDS-USER` 給 `beat` 也有同類問題；`ask_human` 則有自己的通知流程。  
  **建議：**例行進入這兩種等待狀態時，補一封含原因的通知給人；原信已寄給人時去重。

- **M3｜done_when 缺參數，仍可能被算成隊員沒過。**  
  檔：`proto5/lib/aos_team_verify.py`，`check_contains()`／`check_not_contains()`、`check_table_filled()`／`_columns()`。  
  **觸發：**`contains` 的 `args` 只有 `path`、缺 `text`，而檔案也不存在。程式先讀檔，先丟出 `NotMet`，根本沒走到缺參數的 `CheckError`。模擬得到 `result=fail`，會扣隊員次數。表格參數錯誤也可能被前面的檔案／表頭錯誤遮住。  
  **建議：**先完整驗證檢查條目的參數，再讀交付物。只要條目本身寫錯，就應先回 `error`，不能取決於交付物當時長什麼樣。

- **M4｜結果漏掉 broken，就把 error 當成一般不過。**  
  檔：`proto5/lib/aos_team_post.py`，`check_result()`／`collect_job()`。  
  **觸發：**結果逐條含 `result: "error"`、`pass: false`，但沒有頂層 `broken`。`check_result()` 接受，`collect_job()` 因 `res.get('broken')` 為假而送出 `verified`，扣掉一次機會。更新前已啟動的驗收程式所產生的舊格式結果，就可能走到這裡。模擬已確認。  
  **建議：**由逐條結果推導是否 broken；若要求新格式，缺欄位就拒收。並核對每條的 `result` 與 `pass` 一致，不能只驗頂層總和。

- **M5｜過期驗收的 broken 仍會寄「等你修」，通知可能失真。**  
  檔：`proto5/lib/aos_team_post.py`，`collect_job()`／`checker_broken()`。  
  **觸發：**驗收尚未回來，人先取消或改派；舊工作之後回 `broken`。一般結果會經任務狀態機核對 `rev/attempt/status`，新增的 broken 分支卻直接寄信，宣稱單子「停在 verifying」。多份 `--again` 並行時，也可能新工作已成功、舊工作才寄壞掉通知。  
  **建議：**寄通知前核對目前任務的版本、交件次數與狀態；過期結果只留紀錄並結清執行，不再發出要求人修復的通知。

**建議**

- **S1｜重驗的冪等要區分「同申請重播」與「重下指令」。**  
  `on_reverify()`／`submit_verify()` 對已記錄的同一申請，以申請 ID 建固定 job，這條可去重；但每次 `--again` 都產生新 ID，且只要求 `verifying`，正常驗收尚在跑也能追加多份。建議綁定欲重驗的 `rev/attempt`，對已有重驗在途的同一次交件合併或拒絕。權限部分有雙重檢查：成員與 `beat` 都不能替人要求重驗。

- **S2｜規範還有幾句沒同步。**  
  `spec/team/beat.md` 仍寫「catalog 寫 `at`」，現在 catalog 已改 `once`；`spec/team/verify.md` 的 JSON 範例漏了 `broken`，收件說明仍概括寫「對＝verified」，應列出 broken 分支；`spec/team/post.md` 的「信最多晚 5 秒到」不是可保證上限，自訂間隔、排程與積壓都會拉長，宜改成預設巡查週期的說明。

**確認沒問題的**

- **①間隔：**預設 5 秒，限定整數 1～3600；布林、字串、小數及越界值會拒絕。`start()` 讀名冊換成毫秒登記；改後須 `stop` 再 `start` 的說法符合實作。
- **②身分：**`read_outbox_file` 核對寄件格、檔名及 `from`；普通成員冒充 `beat` 的模擬被拒。`may_send` 只給 `handoff/cancel`，取消還限自己的單；不能替人答題。`on_handoff`、`render_handoff`、信頭與 `team_say` 已接上。固定 routes 不能派给 `beat`，動態代入後也會經申請驗證拒絕。
- **③欄位：**程式、CLI 與 catalog 使用 `once`；申請的 `at` 繼續代表寄出時間，沒有混用。
- **④正常 broken 收尾：**先保存 broken 狀態與通知動作，再寄信；後續輪次不重新追加同一通知，仍等待各次 kernel 回音結清。缺檢查器、載入失敗及檢查器例外分類為 `error` 的方向合理。
- **⑤通知：**例行機械驗收及審查成功均經 `_notify()` 抑制給人的 DONE。驗收次數用完、負責人 FAILED、期限失敗、重派用完、漏跑與檢查器壞都有通知路徑；主要漏報是 M2。
- **共用契約：**舊名冊省略 `post` 仍可讀；一般人／領隊開單的完成通知保留。routes 範例四條測試均通過。除上述問題與新增保留名 `beat` 的預期限制，未見這次改動另行破壞隊 1 的正常路徑。