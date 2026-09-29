# 完整性與驗收入口

← [規格入口](README.md)

## V-01．何時算拆到可實作

〔主編補〕每個末端條款有明確責任、輸入輸出或引用共用型別、前置條件、合法狀態、持久交接、失敗處理與 Given／When／Then。不要求每節重複所有共用字段；引用正本即可。新增實作時，按節ID命名驗收，不能只測happy path就宣稱整篇完成。這份文件不代表測試已執行。

驗收：Given 待實作功能，When 找到其所屬葉條款，Then 可由資料與轉移寫出測試；遇未命名資料或互相衝突的狀態先修規格，不自行猜測兩套行為。

## 概念到末端規格

**基底六塊：** 工作描述對應 [B-101～103](base/work.md)，執行器對應 [B-201～204](base/execution.md)，身分與資源對應 [B-301～304](base/identity-resources.md)，儲存對應 [B-401～404](base/storage.md)，通訊交接對應 [B-501～505](base/transport.md)，生命週期對應 [B-601～604](base/lifecycle.md)。

**Agent 五塊：** 設定人格對應 [A-101～103](agent/configuration.md)，輸入對話對應 [A-201～203](agent/input.md)，記憶context對應 [A-301～303](agent/memory.md)，能力工具對應 [A-401～404](agent/tools.md)，tick推進對應 [A-501～505](agent/tick.md)。

**任務與排程六塊：** 任務輪次對應 [S-101～104](scheduling/runs.md)，ready／wait與准入對應 [S-201～203](scheduling/admission.md)，公平對應同篇 S-204，LLM額度對應 [S-301～306](scheduling/llm.md)，粗預算對應 S-203與基底 B-303，觀測人工控制對應 [S-401～404](scheduling/operations.md)。共用資料由 [C-01～06](contracts.md) 定義，名詞與責任由 [T-01～05](terms.md) 定義。

## V-02．先測閉合，再測規模

〔建議預設，未拍板〕第一層只用假工具／mock LLM檢查所有條款的JSON、狀態、去重、提交與unknown；不啟動真實模型。第二層在可丟棄Linux環境以兩個真UID驗證身份、資源、quota（若啟用）與工具後代取消；外牆profile選定後另段驗收，不是這層的完成門檻。第三層才以一萬筆metadata、少量活躍工作測索引與恢復；這不等於一萬真帳號部署已驗證。

三層均記錄版本、配置、測試環境及原始結果。GPU／本機模型不是此驗收前提；FUSE、分散式kernel、父子demo不在首版完成條件。

驗收：Given mock的UID標籤測試通過，When 發布驗收結論，Then 只能說協定測試通過，不能說Linux DAC／cgroup強制或可選quota記帳已通過；quota不宣稱是安全邊界。

## V-03．跨層必要故障場景

〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 B4、B5；依 [WSL 查證](../notes/2026-09-29-wsl-machine-check.md)二・5、6 與[裁定](../notes/2026-09-29-verdicts.md) 7、附 WSL、附排隊先後〕以下是一條整合測試鏈，不替代各節局部驗收。先讓agent A接件、排tool job、啟動attempt；在「blob發布／帳本提交／回收結果／提案commit」各窗口分別中斷，另測新訊息與最後一次tick提交競爭，依 [S-201](scheduling/admission.md) 重算ready，不要求提交後一律觀測為idle。重啟後只允許一個狀態寫入者，輸入不消失，未知attempt不自動再執行，已提交的工具意圖不重複。另測暫停與提案競爭：屏障持久化後不得派新工，查詢仍顯示未解決的unknown；phase觀測值不授權派工或宣告run成功，省略僅供顯示的think／act持久轉移也不遺失可恢復的決策。

在同鏈加入B冒名A、舊generation提交、同request不同內容、主程序退出但孫程序存活、已啟用的agent quota滿、control磁碟滿、OOM、LLM429、送出後斷線、拒絕公開result.ack、拒絕stream=true、部分內容不得當final及重複usage（串流邊界依 [S-305](scheduling/llm.md)）。應產生各篇明定錯誤／等待狀態，不以無限重試掩蓋問題。清空程序只證明本機已停，不證明遠端副作用撤銷。

〔建議預設，未拍板〕〔09-29 精簡，依冗餘審查 B2、A1 claim 部分〕另測 tick 無定期 heartbeat 時，程序退出與 deadline 仍觸發 [B-602](base/lifecycle.md) 收尾；舊受管範圍或 home 鎖未釋放時，即使新通知到達也不重派。確認清空並核對結果後才釋放 claim，排程依 [S-103](scheduling/runs.md) 重查條件；未提交過的遲來舊 generation 或過期 checkpoint revision 提案不得推進 checkpoint、消費輸入或發新工作；已提交提案的相同重送依 [C-05](contracts.md) 回原收據，不重做增量。控制端重啟仍按 B-603 全殺，無可信已發布結果的在途工作變 unknown，不自動重做未知工具／LLM。

另加兩個整合故障場景：

- **Given** 工具／LLM 有在途 attempt；**When** 控制端或 VM 在 10 秒內整個消失，來不及完成停機寬限；**Then** 下次啟動依 [B-603](base/lifecycle.md) 對帳，無可信已發布結果且不能證明從未放行者變 unknown，不自動重做；已持久結果與已提交 checkpoint 保留，清空舊受管範圍後才重派，不把寬限未滿當成成功或安全重試證據。
- **Given** 睡眠期間 VM 暫停，monotonic 沒算睡掉的時間；**When** 睡醒牆鐘大跳，大批工作同時到期；**Then** 運行中逾時仍按 [C-01](contracts.md) 的經過時間判斷，不因牆鐘跳動就全部判逾時；到期工作依 [S-201](scheduling/admission.md) 進入 ready，先後照 S-204 的持久序號，依 S-203 全局與每 agent 准入名額分批放行，其餘保留等待，不一次全放，也不因到期而重做 unknown 工作。

驗收：Given 任一故障注入點，When 系統恢復並查詢，Then 可從agent/run/job/attempt追溯原因，沒有跨owner工作、無證據成功、雙重usage結算或遺失已接納請求。

## V-04．萬級穩態與冷啟動分開

〔使用者方向 2026-09-28，見[工作負載](../notes/2026-09-28-linux-resources-and-task-scheduling.md)〕目標10,000 agent、一小時活躍不到100、雲端LLM；這不是固定併發上限。

〔建議預設，未拍板〕用同一台記錄配置的家用測試機，依1,000→10,000筆冷登記且相同少量active比較：控制層穩態CPU／RSS、每輪查詢列數、history讀取、程序數、ready到啟動時間、佇列年齡、恢復掃描量。以無排隊下wake-to-start p95約0.5秒作起始參考，不把滿載或雲端等待算作同一延遲指標；其他數值先做基線，不虛構已達標。

驗收：Given cold資料增加十倍但active不變，When 量測穩態，Then 無逐冷agent程序或history讀取，SQL熱路徑不全量解碼所有登記；冷啟動可分批全量核對，成本另列，不能每輪重新付出。

## V-05．規格自身查核

〔主編補〕交付前檢查所有本地鏈結存在、主概念有葉規格、ID／狀態／BlobRef使用單一正本、每個規範節有來源和驗收。跨篇再敘述只解釋，不得另定相同欄位；機械式長記錄表用資料檔。文件通過不等於產品通過。

驗收：Given 其中一篇把started_at_ms改成未定義started_at，When 自審，Then 視為跨篇不一致修正，不能以兩者意思差不多放行。
