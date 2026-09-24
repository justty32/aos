審查完成，全程未改檔。H0 在投遞前取得，**已避開「開始等之前回話就到了」的已知坑**；但併發判定、Ctrl-C 與輸出邊界仍有必修問題。

以下行號均以目前 HEAD 為準，路徑省略 `proto5/`。驗證採原始碼追查及不落盤的 Python mock；未執行會建立暫存檔的完整測試套件。

## 必修

1. **`lib/aos_agent_talk.py:141–145, 178–181`：完成判定混用不同時間的記憶、state 與檔案存在狀態，可能提早成立。**

   重現時序：第一句逾時、尚未入記憶，再送相同文字，兩句的 H0 都是 0。第一句完成後，第二句的 waiter 讀到 `[user 同文字, assistant 第一答]`，`collect()` 讀到 idle；接著 tick 才封存第二句。此時 `dropped.exists()` 為假，`_done()` 就把第一答當成第二句已完成。以該組快照呼叫 `_done()`，確實回傳 `True`。

   單一檔輸入另有反向問題：自己的句子已完成，但別人重新占用同一路徑，`exists()` 又變真，自己的等待會被別人的輸入拖住。規範第 74 行「各自的回話判法不受影響」不成立。

   **建議：**以投遞身分／intake 封存紀錄追蹤自己的訊息，搭配可驗證一致性的回合快照；不能只靠文字相等與原路徑消失。

2. **`lib/aos_agent_talk.py:166–167`；`lib/aos_agent_say.py:33–48`：投遞已成功但 pending 尚未登記時，Ctrl-C 會漏提醒。**

   `rename`／`link` 成功後，到 `deliver()` 回傳並設定 `self.pending` 之前，Ctrl-C 會被 `run()` 接住、退 0，但 pending 仍是 `None`，不印「話已投入」。使用者可能以為沒送成而重送。若清除暫存檔時發生 OSError，也可能把已成功的投遞報成失敗。

   **建議：**把「提交投遞、記錄提交結果、登記 pending」做成延後處理 SIGINT 的短臨界區；清理失敗須保留「已投入」資訊。只在 `deliver()` 前先設 pending 會造成相反的誤報，不能直接這樣修。

3. **`lib/aos_agent_talk.py:349–350, 390–399`：啟動階段的 Ctrl-C 不保證退 0。**

   `Talk()` 初始化、載入 readline，以及 `banner()` 都在目前的 `KeyboardInterrupt` 捕捉範圍外。在 banner 的 `collect()` 注入中斷，例外確實直接逸出；CLI 外層也沒有接它，會印 traceback 並以非 0 結束。

   **建議：**將 talk 初始化、banner、主迴圈納入同一個 Ctrl-C 出口。

4. **`lib/aos_agent_talk.py:329–335`；`lib/aos_agent_pause.py:26–30, 38–55`：slash 中的 Ctrl-C 會留下半截操作。**

   `/pause` 在暫存檔寫完、rename 前中斷，留下 `.paused.<pid>.tmp`，沒有暫停成功。`/continue` 在寫入 `resumed` 後、touch 門之前中斷，會留下 resumed 標記但門仍關著；也可能只解除手動暫停，連敗暫停尚未解除。

   外層能接住 Ctrl-C、退 0，但不符合規範第 68 行「不留半截狀態」。

   **建議：**暫存檔加可靠清理；對 pause／continue 的短提交區延後 SIGINT，完成可恢復的一組操作後再退出。

5. **`lib/aos_agent_talk.py:100, 149–153, 354, 393–398`：tty 判斷與 stdout 分流不符規範。**

   - stdin 是 tty 時，`input('> ')` 把提示符寫到 **stdout**。執行 `aos-agent talk > conversation.txt`，紀錄會混入 `> `；記憶體內重現亦確認。
   - stdin 是管線、stderr 仍是 tty 時，仍印等待提示與清行控制碼，違反規範第 27 行「非 tty 不印等待提示」。

   **建議：**提示符明確寫 stderr，讀取使用無提示字串的 `input()`；等待提示需同時要求 stdin、stderr 為 tty。

6. **`lib/aos_agent_talk.py:352–365, 378–380`：回話在 input 阻塞期間到達，退出時仍誤稱「上一句還沒回」。**

   重現：一句話逾時，回提示符後等它完成，再打 `/quit`、Ctrl-D 或 Ctrl-C。程式沒有重新檢查 pending，直接印舊狀態的提醒；已到的回話也沒有在離開前補印。

   **建議：**退出前做一次不阻塞、可容忍讀取失敗的補印與完成檢查；檢查失敗時使用「尚未確認回話」等準確措辭。

7. **`lib/aos_agent_talk.py:178–191`：記憶讀壞會跳過整個停止原因檢查。**

   等待中若 history／info 持續讀驗失敗，即使 kernel 已停、agent 已暫停或被判 bad，也不會呼叫 `collect()`／`_stopped()`，而是一直等到 timeout，顯示「還在想」。mock 確認 history 拋 `JsonSyntax` 時，`collect()` 呼叫次數為 0。

   **建議：**狀態診斷與記憶讀取分開處理；記憶暫時損壞可以重試，但不能遮掉規範要求立即回報的停止原因。

8. **`lib/aos_agent_talk.py:214–215, 232, 304, 313–335`：部分 slash 完全不驗參數。**

   `/quit garbage` 直接退出；`/pause garbage` 確實執行暫停；`/continue --all` 忽略參數、只解除當前家；没有 pending 時 `/wait nonsense` 也不報錯。這與「參數錯＝Usage、不退出」不符。

   **建議：**先統一驗證參數，再執行指令；無參數指令拒絕多餘內容，`/wait` 不論 pending 是否存在都先驗秒數。

9. **`lib/aos_agent_talk.py:98, 116, 255–277, 280–286`：工具失敗會被印成成功。**

   工具名稱表只從「本次印到的呼叫」累積：
   
   - talk 在工具呼叫已入記憶、結果尚未回來時啟動，之後的失敗結果找不到名稱。
   - 新 session 執行 `/context 1`，最近一則恰為工具結果，也沒有掃到之前的呼叫。

   兩種都會把 `工具 date 失敗（exit 1）：bad` 印成 `[結果 ok 1 行]`，已以 mock 重現。

   **建議：**啟動與產生 context 摘要前，從相關完整記憶建立呼叫名稱表；無法辨識時不能逕稱成功。

10. **`lib/aos_agent_talk.py:59–87, 244–249, 279–289`：幾個輸出格式不符合規範。**

    - `/context` 對 content 與每個呼叫分別截短，再串成一則；一則可遠超過 80 字。重現單則摘要長度為 132。
    - `call_line()` 使用 `_one_line()` 折疊參數空白，`{"text":"a  b"}` 變成 `text=a b`，違反「字串原樣」。
    - 工具失敗的第一行也被折疊並截短，並非規範所列的完整第一行。
    - state 讀不到時，`/status` 整個省略 `batch` 欄位。

    **建議：**context 在組成整則摘要後統一截短；呼叫參數保留字面空白，換行如何轉成單行需明訂；失敗第一行照規範輸出；未知 batch 明確印 `?` 等標記。

11. **`lib/aos_agent_talk.py:110–111, 141–145`：記憶縮短只調整 shown，pending 的 H0 永遠留在舊位置。**

    例如 H0＝10，記憶縮短後保留本次 user 與 assistant、總長度只有 2；shown 更新為 2，但 `_done()` 永遠無法通過 `len(history) > h0`。反覆 `/wait` 仍逾時，之後也可能誤匹配另一則相同文字。

    規範允許不補印被改掉的段落，但目前未處理失效的等待基準。

    **建議：**偵測縮短時同步處理 pending：能可靠重新定位才重建基準，否則明確回報「記憶已變更，無法追蹤原句」，不要繼續宣稱還在想。

12. **`README.md:69, 115, 143, 147`：本輪 README 回退到已移除的指令。**

    上手流程三度要求 `aos-kernel check --agent $W/bob`；現行 `aos_kernel_cli.py:138–140` 明確拒絕此旗標。照文件操作會得到用法錯誤。

    **建議：**全部改回 `aos-agent check --target $W/bob`，連同解說文字一起更新。

## 建議

1. **`lib/test/test_agent_talk.py:45–67, 108–113`：假 agent 與測試名稱掩蓋了重要覆蓋缺口。**

   `answer()` 一次寫入全部工具與回話，沒有驗證「中途陸續印」；`test_two_turns_no_reprint` 實際只有一輪問答加 `/history`。

   **建議補測：**

   - 真正兩輪相同文字；頭尾空白；兩個輸入同次 intake。
   - 工具呼叫、工具結果、最後答案分三次到達。
   - 逾時後直接送下一句，舊回話在送出前／後到達。
   - 控制 history、state、封存先後，重現必修第 1 條；另測單一輸入路徑被他人重用。
   - history 暫時壞掉後恢復、不重印；壞掉同時出現 paused／bad。
   - 在暫存檔寫入、rename／link 前後、collect、sleep、banner、pause／continue 各點注入 Ctrl-C。
   - stdin／stdout／stderr 的 tty 組合；重導 stdout 的紀錄必須沒有提示符。
   - `/`、空白前綴、`//`、`/status  -v`、大小寫、全形斜線、路徑文字及各種錯誤參數。
   - `/context` 精確字數、長摘要、多工具呼叫、跨 session 的失敗結果。
   - 秒數邊界、NaN／Infinity、EOF 前晚到回話及退出提醒。

2. **`lib/aos_agent_talk.py:106`：每次 history() 都完整讀驗設定，再重讀一次記憶。**

   `collect()` 又讀一次完整 info。記憶成長後，每 200 ms 重複解析多份資料，可能讓輪詢與 Ctrl-C 回應變慢。

   **建議：**在保留設定更新語意的前提下，減少同一輪重複讀取；同時讓快照一致性更容易驗證。

## 其餘核對

| 項目 | 結果 |
|---|---|
| 等待開始前已到的回話 | **無問題**：H0 在 deliver 前取得，shown 獨立追蹤輸出。 |
| 一般逐步追加、同輪多則輸入 | **無問題**：intake 保留各則 user，沒有串成另一個 content；正常追加下不漏、不重印。 |
| 頭尾空白、一般順序重送相同文字 | **無問題**：投遞與 pending 使用同一份處理後文字；併發例外見必修 1。 |
| history 讀到半截後恢復 | **無問題**：先完整讀驗再印，讀驗失敗不推進 shown。停止原因被遮蔽另見必修 7。 |
| slash 與模型輸入邊界 | **無問題**：前導空白先去掉；`/`、`/STATUS`、`/usr/bin 是什麼` 均屬未知指令、不送；`//` 移除一個 `/` 後送出；全形 `／` 當一般文字；`/status  -v` 可用。 |
| 一般 wait 的清行 | **無問題**：回話、工具行、停止原因、逾時及正常中斷路徑都有清行。 |
| 非 tty readline、正常 EOF | **無問題**：非 tty 不載 readline；EOF 退 0。提醒準確性見必修 6。 |
| `/context` 字數算法 | **無問題**：content 加工具 arguments，system 取字串長度，工具使用去除私有欄位後的 JSON；不是 token 數。 |
| CLI 旗標、預設值、進入前讀驗 | **無問題**：120 秒、秒數範圍、小數、拒絕 `--json`、用法錯 2、非 agent／info 錯退 1 均對得上。 |
| say 失敗時混入整段 status 的舊痛點 | **無問題**：talk 未沿用該 stdout 路徑，停止原因走 stderr。 |