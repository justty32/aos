審查結果：**2 條必修、2 條建議**。全程未改檔；以下路徑均相對 repo 根目錄。

1. **〔必修〕stop／start 後接手舊批，會漏掉回音喚醒。**

   **位置：**`proto5/lib/aos_agent.py:73`、`proto5/lib/aos_kernel_ledger.py:156`。

   **現象：**agent 送出慢工作後 stop，再 start；新一代第一次 tick 看見舊批還沒完成，就退 102。工作稍後完成，回音仍帶舊代 `wake_gen`，kernel 因代數不同不叫醒，新 agent 只能等 `park_ms`。這是正常操作，不需要崩潰；act 批尚未回來的其他件也會遇到。

   **依據：**`proto5/spec/aos-agent/register.md:51` 明定 stop 後當批照跑、start 後接著收；`aos_agent_batch.py:303` 在未收到結果時回 101，再被 `_park` 改成 102。`test_park_wake.py:176` 只驗證「舊代不能叫醒新代」，沒有驗證新代正在接手同一批。記憶體呼叫也確認：舊代喚醒回 `None`，新代仍保持停車。

   **建議改法：**保留代數隔離，但補上接手舊批的處理。最低限度是記錄批的送出代數，接手不同代、或沒有代數資料的批時先維持 101，結清後才允許停車；另一種是提供明確的重新綁定機制。補測「舊批未完成 → stop／start → 新代先跑 → 舊批完成」。

2. **〔必修〕恢復空 `intake` 後直接停車，可能留下已到的新輸入。**

   **位置：**`proto5/lib/aos_agent.py:81`、`proto5/lib/aos_agent_inputs.py:59`。

   **現象：**上次留下未完成的 `intake`，其中舊檔已不存在；此時新輸入 B 已投遞，wake 也已讓 agent 排進 ready。這次 tick 只恢復舊 intake，清掉它後回 101，被轉成 102；它沒有重新掃 B，而喚醒已經用掉，B 因此等到保底。等待中的 compact 申請也可能被拖延，因為這格開始時 `intake` 非空，跳過了自動壓縮。

   **依據：**`aos_agent_inputs.py:38` 只有 intake 為空才列輸入；`:59` 在沒有訊息時寫入 `state.intake_empty`，接著回 101。`aos_agent.py:77` 則以 intake 是否為空決定是否執行壓縮。記憶體呼叫確認此出口**有寫 state，最後仍退 102**；`proto5/spec/aos-agent/idle.md:10` 也跟著寫成 102。

   **建議改法：**清掉空 intake 後退 0，讓下一格重新檢查輸入與壓縮；只有未建立 intake、掃描確實無輸入的出口才停車。同步修規範，補測「恢復空 intake 時，另有新輸入且 wake 已處理」。

3. **〔建議〕「say 崩潰窗口」測試其實只驗證停車期限。**

   **位置：**`proto5/lib/test/test_park_wake.py:431`；`proto5/notes/2026-09-24-idle-wait-impl/README.md:86`。

   **現象：**測試沒有呼叫 say、沒有放輸入，也沒有注入崩潰；只讓假 agent 停車，睡過期限後確認重新派工。因此尚未驗證輸入在窗口中存活、到期後確實被收取。

   **依據：**測試 `:433` 至 `:438` 只有 `park → tick → sleep → tick`，但報告把它列為「輸入放好、wake 尚未投遞」的窗口測試。

   **建議改法：**在真正 `deliver` 放好輸入後、呼叫 wake 前注入 Crash；確認輸入仍在、沒有 wake 單，推進時間後由真正 agent tick 收取一次。現有測試可保留，但改名為期限保底測試。

4. **〔建議〕補齊交錯測試，並精確標示 SIGKILL 的切點。**

   **位置：**`proto5/lib/test/test_park_wake.py:161`、`proto5/lib/test/test_park_crash.py:41`；實作報告 `README.md:80`、`:88`。

   **現象：**`test_woken_cleared_after_any_verdict` 實際只測 code 0；同格收 agent 的 102 與 once 回音、act 多件分批完成，也缺少直接組合測試。另外，SIGKILL 的 `after_put` 是「回音已放、尚未呼叫 wake」，不是「wake 已修改記憶體、尚未提交」。

   **依據：**`test_kernel_crash.py:137` 的閘門仍在 `link_json` 內，而真正 wake 在 `aos_kernel_ledger.py:312`、函式返回後才執行。後一個窗口確實已有 `test_park_wake.py:338` 的 Crash 測試，但報告應區分兩者。`classify` 在 `aos_kernel_info.py:282` 先清 `woken`，我以記憶體呼叫確認 stopped、error、kind=aos、done_exit 分支目前都清得乾淨。

   **建議改法：**補判定分支表格測試、同格雙回音的兩種收取順序，以及 act 多件交錯；再補「提交點 2 已存 woken、提交點 3 前崩潰」的恢復測試。報告分開寫清楚兩個出貨切點。

總評：主要的「出貨後叫醒、喚醒與清出貨箱一起提交」設計成立，但前兩條正常恢復路徑仍會漏到五分鐘保底，建議修完再合併。`discard`、取消／退件回音、wake 去重、相容檢查及 `ls --json` 加鍵承諾，未發現新的直接矛盾；沒有帳本時放行則是報告已明列的限制。效能上沒有新增每格掃全部 agent，但仍有整份帳本讀寫，每次喚醒另有排隊、舊格計數及偶發壓縮成本。本次採靜態追查與不寫檔的記憶體驗證，未重跑會建立檔案的完整測試或 SIGKILL 測試。