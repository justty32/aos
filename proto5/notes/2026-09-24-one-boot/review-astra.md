← [本輪報告](README.md)｜[任務書](review-task.md)（codex exec -m gpt-6-astra -s read-only 的原文；連結的行號改成連到檔案）

## 必修

1. **[aos_kernel_boot.py:103](../../lib/aos_kernel_boot.py)：舊帳本在舊 tick 停妥之前就讀取，可能匯入過期狀態。**  
   第 108 行才縮掉舊 kernel 池；等待期間，已載入舊程式的 tick 仍可能提交 `state.json`、派工、刪原單。舊版沒有 `.tick.lock`，新鎖擋不住它。結果可能漏登記工作，或把已完成的工作再派一次。**建議：先讀舊池位置、停妥舊執行者，再重讀最終 `state.json` 作為匯入來源。**

2. **[aos_kernel_store.py:61](../../lib/aos_kernel_store.py)：SQLite URI 沒有跳脫 `%`，可能開到另一個家的帳本。**  
   例如路徑中的字面 `%2F` 會被 SQLite 解碼成 `/`；boot 可能持有 K1 的鎖，卻修改 K2 的資料庫，破壞家與鎖的隔離。已用純記憶體 SQLite 驗證百分比解碼會造成名稱別名。**建議：使用 `Path.absolute().as_uri()`，再附加 `mode` 參數。**

3. **[aos_kernel_engine.py:253](../../lib/aos_kernel_engine.py)：`tick off` 通知可能在 daemon 崩潰恢復時永久遺失。**  
   daemon 先保存 `current`，再執行撤登記；若崩在兩者之間，重啟時 `aos_home.reconcile()` 會直接刪掉 notification。此時 kernel 可能已清空 `sends`，而 stopped 分支不會再產生撤登記單，造成 daemon 永久替 stopped K 開空格。**建議：讓撤登記有可重試的完成確認，或對這種冪等操作實作崩潰重播。**

4. **[aos_daemon_ticks.py:149](../../lib/aos_daemon_ticks.py)：撤登記後立即重登記，會繞過 daemon「同一 K 同時一格」的限制。**  
   舊 Ticker 從 `tickers` 移除，但行程仍留在 `tick_pids`；重登記建立的新 Ticker 的 `proc=None`，下一圈就能再開一格。已用無檔案寫入的 mock 驗證此狀態。**flock 仍能防止兩格同時改帳本**，但 daemon 的單格保證不成立。**建議：以 K 身分保留執行中行程，重登記沿用它，收屍後才准開下一格。**

5. **[spec/kernel/boot.md:46](../../spec/kernel/boot.md)：匯入後、改名前的恢復說明與程式相反。**  
   規範說「有 sqlite 就只認它，舊 JSON 不再讀」；實作 `legacy()` 卻只看 `state.json` 是否存在，tick／agent 會拒絕，boot 會重新匯入。`spec/kernel/ledger.md:29` 也有同樣矛盾。**建議：統一成目前的恢復策略，明寫此窗口必須再 boot；不能只憑 SQLite 檔存在就認定匯入完成。**

## 建議

- **[aos_up.py:123](../../lib/aos_up.py)：down 應從帳本取得實際使用中的 daemon。**  
  修改 info 的 daemon、尚未 boot，或池正在搬家時，`_daemons(info)` 會漏掉舊位置。halt 使用帳本停好 K，down 卻可能留下已無其他用途的舊 daemon。建議停機前保存帳本 `ticker` 與池位置，納入撤登記等待及「還有別人使用嗎」的檢查。

- **[aos_kernel_store.py:176](../../lib/aos_kernel_store.py)：補上 COMMIT 失敗後的連線清理。**  
  交易本體失敗會 rollback，COMMIT 失敗卻不會；部分錯誤會留下開啟中的交易，同一 Store 再 save 就失敗。正式 tick 會關連線，因此未見直接壞帳路徑。建議失敗時檢查 `in_transaction` 並 rollback，`orig` 保持原值。

其餘面向：

- **鎖：看過、沒問題。**正常新版 boot、手動 tick、兩個 daemon、重啟後孤兒 tick 共用 flock；kill -9 後會釋放。
- **SQLite 主路徑：看過、沒問題。**交易本體 rollback 不更新 `orig`；匯入／`write()` 有先載入原列。busy 輪轉順序、有效帳本的 `on` 反推，以及 read／proc 的交易快照均合理。
- **提交點：看過、沒問題。**派工與 scale 出貨前已提交 seq；提交前重用 seq 不會撞到已出貨的新工作，ack 重送仍指向同一回音。
- **daemon 一般排程：看過、沒問題。**未見讀 K 檔案內容；時間／新檔觸發、失敗退避、逾時整組 KILL、孤兒鬧鐘及 waitpid／Popen 收屍配合合理，例外如上述撤登記窗口。
- **K2／T2：看過、未見本次改動破壞。**wake、102、park_ms 保留原判定；routine／驗收相關查帳已接 store。
- **agent 相容檢查：看過、沒問題。**舊 JSON 拒絕、已有 chain 卻沒有 park 拒絕、未 boot 放行，符合描述。
- **輸出規範：看過、沒問題。**`ls --json` 第 3 版、`proc --json` 形狀及 health 判定順序相符；匯入恢復文字例外已列必修。

驗證限制：指定 11 條測試全部在 setUp 因唯讀沙箱無法建立暫存目錄而中止，**不能算通過或產品失敗**。另以純記憶體／mock 驗證了上述 URI、撤登記狀態、busy 輪轉及交易本體 rollback。未修改檔案，未接觸模型服務。