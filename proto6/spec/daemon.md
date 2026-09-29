# daemon：登記、喚醒與程序生死

← [規格入口](README.md)｜[kernel 樹](scheduling/README.md)｜[通用 tick](tick.md)

依據：[09-29 新架構](../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../notes/2026-09-29-verdicts.md)。kernel 決定成員何時能做事；daemon 是所有 tick 程序的爸爸，負責啟停與收尾。

## B-601：記憶體登記與按需執行

〔使用者方向 2026-09-29〕daemon 在記憶體使用一張登記表，**node 資料夾路徑就是 id**。所有 node 都按需啟動。daemon 不讀訊息、工作狀態或任務註冊表，不排業務工作、不分資源；只用登記與喚醒資料，讀 inst 僅為 `user` 授權。

本機 socket 提供登記、解除、pause／resume、wake 及查詢。pause／resume 是「不再開新格／准許開新格」的開關，不殺正在跑的；wake 是「現在跑一格」，不改 pause。pause 時保留 wake，resume 後才可執行。daemon 也按登記間隔跑 inst；同一 node 的互斥依 [B-602](tick.md)。agent 通常不設定期，由所屬 kernel 判斷何時叫醒、同時准許多少成員執行。kernel 自己那格結束就退出，不等成員完成；LLM／工具先送請求、後續 tick 收結果，見 [tick](tick.md)。

〔建議預設，未拍板〕記憶體登記只保留啟動所需資料：資料夾路徑、父 node 路徑、inst 位置、可選定期間隔、繼承身分及身分額度；另有執行中程序與待喚醒標記。登記可標 `once`，跑一格後自動解除；可信 `parent_id` 記下發起 node，資源歸它。工作可用單一 inst 檔，欄位見[daemon 協議](protocol/daemon.md)。相同授權者重複登記相同資料無害，不重啟正在跑的程序。登記鏈不得成環，也不能藉重複登記搶走別隊的成員；核對由可信父子登記完成，不靠目錄名稱猜測。

### IPC 授權與身分額度

〔使用者方向 2026-09-29〕登記與控制操作都看 **socket 對面的 Linux 帳號**：該 node 的帳號，或其上層 kernel 的帳號。封包自稱的 sender／user 不算呼叫者身分。身分額度與通用 user 以 [B-301](base/identity-resources.md) 為正本；獲准叫醒不代表獲准擴大額度。

### 執行身分與 helper

〔使用者方向 2026-09-29〕daemon 開 tick 前只讀 [inst 的 `user`](base/inst.md) 授權，不解析其他工作內容；不合額度就不跑並寫[待處理事項](scheduling/operations.md)。欄位型別、繼承、125／`exit`、指示詞及切身分後開檔的規則均以 inst 篇為正本。

啟動路徑與可選 helper 依 [B-303](base/identity-resources.md)。

**驗收：**無事 node 不開 tick；重複叫醒不重疊。身分拒絕及無 helper 情境見 [V-03](conformance.md)。

## B-504：通知只是提示

〔使用者方向 2026-09-29〕daemon 可按已登記的時間、IPC 叫醒或新檔通知開 tick，不讀新檔正文。kernel 才核對自己的收件與成員摘要，決定後續要叫醒誰；通知本身不是接件、消費或完成證據。

〔建議預設，未拍板〕執行中的 node 收到叫醒時，daemon 留一個待喚醒標記，收尾後再開下一格。通知合併或遺失後的補查由 kernel 按 [S-202](scheduling/admission.md) 處理，daemon 不代查內容。

**驗收：**漏掉一次通知，完整投件仍能在所屬 kernel 的後續補查被發現；同一 node 連續收到多次提示不會同時跑兩格。內容發布與去重見 [投件](base/transport.md)，互斥見 [B-602](tick.md)。

## B-603：重啟先清空，再讓樹長回來

〔使用者方向 2026-09-29〕daemon 重啟、整機或 WSL VM 關機，都採**在途程序全殺**；不接續孤兒工作。先確認舊 tick 與受管後代清空，才開新 tick；清不掉的 node 不能重開，故障要可見。安全程序識別及後代清空見 [執行器](base/execution.md)，不能拿一個可能重用的 PID 直接 kill。

daemon 設定檔只列頂層 node 及其啟動設定、身分額度。正常退出把登記表、pause、未處理 wake 存進 `state_dir/state.json`，下次開啟先讀回；這份檔不保存或接續執行中的程序。無檔也能從頂層啟動。

**daemon 開啟就自動開始 tick 頂層 node**；已恢復 pause 的頂層保留這次 wake，等 resume。每次啟動換 boot id，頂層發現改變後重新登記直接成員並叫醒子 kernel，逐層重建。平常只在 boot id 或成員清單變動時補登記，不每格重送。壞成員留待辦、跳過，不擋其他子樹。

pause 有變動才批次寫 `state.json`；`pause_save_interval_ms` 建議 1000。正常退出存完整最新狀態；意外退出最多丟最後一個間隔內的 pause 變動，過期登記與未保存 wake 由頂層補查恢復。

〔建議預設，未拍板〕部署可用 systemd 等方式確保 daemon 崩潰也能清空受管範圍。辨識、清理程序由執行器與部署提供，不要求跨重啟保存程序表。

〔使用者方向 2026-09-29〕清空後由 node 按 [tick](tick.md) 恢復檔案，執行器／所屬 kernel 核對工作結果；daemon 不代讀結果或判業務終局。

**驗收：**正常重開讀回 pause／wake，無快照時頂層仍自動跑；pause 批存與全殺、逐層補登記見 [V-03](conformance.md)。

## B-604：停機、停用與退役

〔建議預設，未拍板〕前景 Ctrl-C（SIGINT／SIGTERM）正常停機先停止新啟動，等候可設定的寬限時間，再停止未結束程序並清空受管後代；完成後保存 B-603 的完整 `state.json`；突然被殺則下次依 B-603 恢復。未清空要回報失敗，不能先宣稱停止完成或假裝名額已釋放。具體 TERM／逾時收尾見 [B-203](base/execution.md)。

授權者停用成員時，由所屬 kernel 停止再喚醒／再登記該成員，daemon 阻止新啟動並排空既有程序，再解除登記。停用 kernel 時同樣處理其已登記子樹，不連帶停掉其他隊；只清 daemon 記憶體的一筆資料不能代表持久停用，否則下次父 kernel tick 會把它登記回來。

退役由授權者明示，所屬 kernel 先核對程序已清空、未結工作與資料歸屬；daemon 不另設持久退役表。UID／GID 及 home 都不自動回收或刪除，資料與 Linux 所有權的處置另由有權限者決定；解除登記不會消除舊檔案的 ownership。

**驗收：**停止一個子 kernel 不妨礙別隊運行；受管後代仍在時不回報排空完成；解除登記不刪 home、不把舊 UID 自動發給新成員。
