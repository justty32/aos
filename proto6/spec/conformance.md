# 完整性與驗收入口

← [規格入口](README.md)

## V-01．何時算拆到可實作

〔主編補〕有效規則須能找到責任、輸入輸出、失敗處理及驗收；共用定義用連結，未裁選擇保持標記。以下**不是已執行的產品測試**。

## 概念與正本

| 概念 | 規格正本 |
|---|---|
| node 與兼任角色、兩張註冊表 | [T-02](terms.md) |
| node 登記、喚醒、全殺重啟、逐層重建 | [daemon](daemon.md) |
| 任務順序、group／needs、互斥、git、Q1／Q2 | [tick](tick.md) |
| 身分額度、可選 helper；inst 欄位與解析 | [身分](base/identity-resources.md)、[inst](base/inst.md) |
| 工作材料、可信結果、後代收尾 | [work](base/work.md)、[execution](base/execution.md) |
| 追蹤／ignored 區、完整發布、去重與清理 | [storage](base/storage.md)、[transport](base/transport.md) |
| kernel 樹、資源 module 與 LLM 池 | [scheduling](scheduling/README.md) |
| 可選 run、unknown 與待辦彙整 | [runs](scheduling/runs.md)、[operations](scheduling/operations.md) |
| agent 任務、設定、context、工具、完成證據 | [agent](agent/README.md) |
| 跨篇 ID、時間、結果與錯誤 | [contracts](contracts.md) |

## V-02．先測行為，再測規模

〔建議預設，未拍板〕先用假工具／mock LLM 驗檔案交接、git、授權及結果。再在可丟棄的 Linux／WSL 環境，驗無 helper 通用 user、有 helper 兩個真 UID、已裝 module 與後代清理；最後測萬級冷 node。

保存版本、配置、環境與結果；mock 不代表 OS 隔離已驗證，磁碟記帳不算硬限制。範圍依[平台邊界](README.md)，須涵蓋同機 node 樹。

## V-03．跨篇故障場景

〔建議預設，未拍板〕以下測試交叉覆蓋已裁規則與各篇工程預設；具體預設仍依正本來源。

### node、登記與身分

驗兼任 kernel／agent、只有收信任務及空成員表，角色須依任務判定。正常重開讀回登記、pause 與 wake，意外重開最多丟最後一個存檔間隔的 pause；無快照也自動 tick 頂層，boot id 變更後逐層補登記，壞成員留待辦、不擋其餘成員；漏通知可補查，重複叫醒不並行同 node 的兩格。

測 socket 冒名、超額授予／宣告 user、不懂 user 語意、無 helper 繼承與切 UID 後開檔。超額須 125、不啟動、不寫 `exit` 並留待辦；整份 `$ref` 可用但不能偷換身分，搬資料夾也不能取得新身分。

### group、收件與派出

前組成功、後組失敗：前組保留，後組修改／新增檔還原，ignored 收件不丟；改 `.gitignore` 不能躲還原。失敗組不能滿足跨組 needs，獨立組可繼續；壞表整格不跑，無變動不 commit。

在複製收件、commit、刪原件各窗口中斷，不遺失或重吃；同 ID 異內容報衝突。請求與回應未 commit 不送，tick 只重投相同 ID／bytes，執行不明仍 unknown、不自動重做；還原不撤銷外部效果，跨 repo／submodule 無共同交易。

### 程序與結果

daemon 或 VM 突然消失後，全殺舊 tick 與受管後代才重開；主程序已退、孫程序仍活也不能報清空。已 commit 狀態與完整結果保留，未 commit 還原；無可信結果的在途工作不能自動再跑。取消與完成競爭只發布一次結果，晚到舊結果不覆寫新嘗試，同一結果與用量不重複採計；沒有 OOM 證據不能只憑 SIGKILL 猜原因。

### 分層資源與 LLM

父層分給子層的範圍不能被子層加大；子層未裝某 module 不另記或另限，但父層限制仍有效。兩個 kernel 可各有 endpoint 池，各池核對真正共享的 provider 限制。測 429 退避、送出後斷線及部分內容；部分回覆不能冒充完成，unknown 不因一般 retryable 標記而重試。

分開驗證 key 部署：無 helper 且代發／agent 同帳號時，文件須明說 key 不受保護；採獨立服務帳號保護時，node 與工具不可讀 key。上層查詢只取下層摘要，未授權者不能因猜 ID 讀內容。

### 設定、清理與待辦

驗重要設定暫停手改、確認提交再恢復；普通設定由任意可讀路徑經持同一把鎖的工具匯入，下格可讀；tick 內改設定不檢查或阻擋。滿碟或 commit／還原失敗不得假成功、刪原件或開新格。

清理依 [B-404](base/storage.md) 驗間隔、保留與去重證據；到期 unknown 可清，不認得的資料不碰也不回報。node 事項存 ignored `.aos/attention/`，daemon 自己事項才走 IPC；沿樹彙整清單。寫不進 node 只警告到 stdout，daemon 自己錯誤才到 stderr；啟停核對兩份 pid 檔，舊檔不拿來殺程序。show 只顯示建議，done 只將事項標完成。牆鐘大跳時到期工作仍依本 kernel 序號及額度分批放行，不重做 unknown。

## V-04．萬級穩態與冷啟動分開

〔建議預設，未拍板〕負載目標依 [T-05](terms.md)。同一台有配置紀錄的測試機，以 1,000→10,000 筆冷 node、相同少量活動量比較 daemon／kernel CPU、RSS、程序數、檔案與 history 讀取量、佇列等待、喚醒到啟動時間。

穩態不應每格掃全樹、讀全部 history 或替冷 node 開程序。冷啟動重建登記可以走完整棵樹，但成本另列；再分開量多層 kernel 的端到端喚醒延遲。無排隊時 p95 約 0.5 秒僅作起始參考，不當已裁門檻，也不混入雲端等待。

## V-05．規格自身查核

〔主編補〕檢查路徑／錨點、正本、來源及故障場景；舊條款只留殘根，protocol 舊材料不當新主規格。

從 repo 根目錄跑 `bash wf/tools/wf-lint.sh proto6`，其中 spec 的 broken 須為 0。文件通過與產品運行時驗收分開回報。
