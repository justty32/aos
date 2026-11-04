唯讀靜態審查完成；未執行測試、未修改或 commit，也未碰模型服務。**閘門位置正確，但還不能據此宣稱 C-7／C-8 全部封住。** 以下路徑均相對 repo 根目錄。

- **真 bug／中：spawn 回音可能永久遺留。** `proto5/lib/aos_kernel_engine.py:62`、`:83`：收到回音至 ack 寫帳本前崩潰，舊 request 名沒有持久紀錄；下格若孩子仍活著會直接跳過 spawn，若需重拉則用新 seq，兩者都不會 ack 舊回音。現有閘門未涵蓋此窗。

- **真 bug／中（已知 B-10）：stop 確實會同名重投。** `proto5/lib/aos_kernel_ledger.py:133`、`proto5/lib/test/test_kernel_crash.py:620`：接收者刪掉通知後，`EEXIST` 已無法去重；測試明確接受兩次 `ok`。這算重複投遞，雖非兩份同時存在，仍會停止下一代 cpu，應列待修，不能當「無雙份 request」通過。

- **測試漏洞／高：stop 只驗工作 cpu，漏掉 kernel cpu。** `proto5/lib/test/test_kernel_crash.py:601`：固定卡 cpu `0`；若卡在 `k` 的 stop 已放、未清帳窗口，`k` 可消化 stop 後退出，下一格根本不開始，`kill_tick(..., hold="next")` 的等待前提不成立；也沒驗舊 stop 讓新 kernel cpu 在接鏈前退出的情況。

- **測試漏洞／中：沒有驗失敗計數的崩潰恢復。** `proto5/lib/test/test_kernel_crash.py:182`、`:351`、`:440`：工作全是成功退出，`fails=0` 無法抓「漏加 fails」、重複累加、錯誤清零或錯誤退件；應補非零退出與 `error/Interrupted`。

- **測試漏洞／中：「同名只成功一次」不是全面檢查。** `proto5/lib/test/test_kernel_crash.py:326`：只查 `op="post"`、排除 stop，漏 `op="reply"`；BOOT 程序也沒有安裝 TICK 的 trace。個別回音案例有補斷言，但此 helper 的保證範圍比名稱窄。

- **測試漏洞／中：syscall 重做可能被既有回音遮住。** `proto5/lib/test/test_kernel_crash.py:583`：只數成功回音和工作副作用；重做具名 `add` 若得到 `AlreadyExists`、回音放檔又遇 `EEXIST`，仍可能通過。需直接核對套用次數，或加入會暴露重做的 syscall 情境。

- **Flaky／低：settle 不是完成屏障。** `proto5/lib/test/test_kernel_crash.py:321`、`proto5/lib/aos_kernel_engine.py:145`：`last_seq` 在一格開頭更新，達標時該格尚未完成；四格觀察有用，但不能保證所有出貨與接收者已收斂。

- **Flaky／低：活躍 JSONL 讀取與固定期限。** `proto5/lib/test/test_kernel_crash.py:305`、`:310`：鏈仍在 append 時直接解析整檔，沒有尾行未完成的容錯；6～10 秒期限另會受慢機排程影響，`tick_ms=5` 不代表實際每格只需 5ms。

- **收尾風險／低：有清理，但沒有證明零殘留。** `proto5/lib/test/test_daemon_crash.py:64`、`proto5/lib/test/test_kernel_crash.py:207`：HUB 反覆殺直接孩子及收養孤兒的設計合理，但四秒耗盡仍可正常退出，外層未斷言後代清空；不能說「一定不留行程」。

其餘判定：

- **閘門／沒有發現錯位。** `proto5/lib/test/test_kernel_crash.py:92`、`:136`、`:145`、`:159`：`_put` 會動態查 `aos_home.post_request`，繼承的 `flush_outboxes` 替換也有效；before／after 均位於宣稱的存帳、投遞、清帳邊界。正常單鏈下，下一格確實等目前工作退出才開始。
- **ack 換 seq／允許。** `proto5/spec/kernel/ledger.md:47`、`:53` 與 `impl-notes.md:14` 允許此命名；digest 區分不同回音，沒有要求跨格同一回音只能有一則 ack。
- **discard 空洞／條件成立會卡住，但未找到正常可達路徑。** `proto5/lib/aos_kernel_engine.py:20` 會永久保留 slot；然而 `aos_kernel_ledger.py:80` 在兩檔皆無時直接清 slot，已送工作則依協定保留原單或回音，因此不能僅憑此分支認定 C-7／C-8 真 bug。
- **證據遺失／不只工作結果。** `proto5/lib/aos_kernel_ledger.py:153`、`proto5/lib/aos_kernel_engine.py:160`：舊 tick 的錯誤回音也可能先被 ack、其 `tick_error` 尚未寫 log 就再崩潰；派工事件亦可能缺失。規範宜明說，不能承諾只缺一格工作結果紀錄。