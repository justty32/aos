**有落差，尚不能判定四邊完全對齊。** 主要功能已接上，但設定檔驗證、鎖的錯誤清理、診斷提示與部分測試仍有缺口。全程未改檔、未連模型端點。

**1. 逐條核對**

「測試」欄表示測試內容涵蓋什麼，不代表本次跑綠。

| 編號 | 規範 | 程式 | README | 測試 | 結論 |
|---|---|---|---|---|---|
| 0 | 三支皆寫明 `--target` 與預設來源 | 找家邏輯符合 | 上手說明符合 | 有來源、舊位置參數拒絕測試 | 對齊 |
| 1 | 已用新名，但正文仍有舊名註記 | 新寫入用新名；仍讀舊 tick.json 的 `AOS_K` | 日常指令用新名 | 有舊鍵遷移測試 | 有落差：未達「所有出現處」清除，保留相容分支 |
| 2 | 每個 K 可省略，錯誤須說來源 | 解析符合；`check` 退錯漏來源 | 宣稱錯誤會附來源 | 來源測試集中在 `ls` | 有落差：見必修 5 |
| 3 | 九個子命令、秒數、預設 300 秒皆有 | 一般輸入符合；巨大秒數會 traceback | 指令與預設符合 | 有一般用法測試，漏溢位 | 有落差：見必修 4 |
| 4 | 三模式、互斥、等待条件都有 | 共用 `wait_reply`，判定順序符合 | 使用方式符合 | 有真 follow、等待成功與早退；部分條件測試失效 | 有落差：見必修 8 |
| 5 | 兩種暫停與解除都有 | pause／continue／status 主流程符合 | 日常操作符合 | 有停住、雙重解除、暫停照收測試 | 對齊；提示指令另見必修 6 |
| 6 | 併發來源、kernel 不重派、flock 都有 | 正常與競爭路徑符合；異常漏 fd，非 agent 家也可能建鎖 | lib 有說明 | 有真正雙程序；漏鎖 I/O 失敗與其他類型的家 | 有落差：見必修 3、9 |
| 7 | 裸 daemon 退 2、cwd 預設都有 | 符合；check／boot 共用 daemon 找法 | 符合 | 有裸指令、來源與預設測試 | 對齊 |
| 8 | config 必填；省略退 2；先驗後建 | `null` 誤建家；指示詞池判斷錯 | heredoc 範例形狀可用 | 有一般壞設定測試，漏這兩種 | 有落差：見必修 1、2 |
| 9 | 統一 `--daemon-target` | boot／check 符合，舊縮寫也拒絕 | 符合 | 有來源、重複旗標、舊旗標拒絕 | 對齊 |
| 10 | 三支位置參數可省略 | 都預設 `.` | lib 仍寫 `aos-cpu DIR` | 三支都有省略參數相關測試 | 有落差：README 漏更新 |
| 11 | 新檔名與入口已改 | CLI 舊檔移除，think 工作改跑 `aos-llm call` | 連結與指令已改 | 測新入口、裸指令、舊檔不存在 | 對齊；殘留主要是改名註記 |
| 12 | kernel `halt` | 已改，原停機行為保留 | 新版指令正確，升級順序寫錯 | 有 halt／拒絕 stop 測試 | 有落差：見必修 7 |
| 13 | daemon `boot／halt` | 已改 | 同上 | 有 boot／halt／裸指令測試 | 有落差：見必修 7 |

六份規範的**標頭版本句與檔尾〈沿革〉都有補 fix-r4**。

**2. 真問題清單**

**必修**

1. **JSON `null` 會繞過 config 驗證，建立錯誤的預設家。**  
   在 [aos_kernel_info.py:117](../../lib/aos_kernel_info.py)。CLI 讀到 `null` 後傳入 `config=None`，被當成 lib 呼叫時「沒給 config」，建立 `k＋0／1／2` 並退 0。規範要求非物件退 1、不建任何東西。應區分「參數省略」與「JSON null」；現有壞設定測試沒有 null。已用完全攔截寫入的 mock 確認。

2. **合法的指示詞設定會被 `init --config` 拒絕。**  
   在 [aos_kernel_info.py:98](../../lib/aos_kernel_info.py)。程式在解指示詞前，以原始值判斷有沒有 kernel 池。例如 `scheduler.pool={"$env":"POOL"}`、`POOL=kernel`，會先多加 `k`，解完變兩顆 kernel cpu 而退錯；`cpus` 本身的指示詞也被額外禁止。規範說沿用 info 的指示詞與讀驗規則，應按解析結果決定補不補 `k`。已用純記憶體呼叫確認同份內容作 info 合法、作 config 失敗。

3. **tick 鎖在 I/O 錯誤路徑漏關 fd。**  
   在 [aos_agent_runtime.py:37](../../lib/aos_agent_runtime.py)。只有競爭失敗會關 fd；其他 flock 錯誤、`ftruncate`／`write` 失敗都直接拋出。呼叫端尚未拿到 fd，`finally` 無法清理。CLI 結束會由 OS 回收，但同一 Python 行程再次呼叫 tick 可能被自己留下的鎖擋住。應在未成功交出 fd 的所有異常路徑關閉；目前測試未覆蓋。mock 已確認漏關。

4. **`--wait` 的巨大數值會直接 traceback。**  
   在 [aos_agent_cli.py:58](../../lib/aos_agent_cli.py)。`listen --wait 1e309` 或 `--wait inf` 通過目前判斷，轉整數時丟 `OverflowError`；say 共用同段。應檢查有限值及換算溢位，以用法錯 2 清楚拒絕。已唯讀重現。

5. **家的來源診斷沒有涵蓋所有入口。**  
   在 [aos_kernel_check.py:160](../../lib/aos_kernel_check.py) 與 [aos_agent.py:70](../../lib/aos_agent.py)。`kernel check` 自己印 bad、回 1，繞過 CLI 附來源的處理；agent tick 自己攔住 `NotAnAgent`，同樣漏掉來源。實際都有路徑，但沒有說來自旗標、環境變數或 cwd，違反規範與 README。應統一補來源；現有測試未涵蓋這些入口。已用不存在路徑確認。

6. **部分提示照抄會操作目前目錄，沒有操作剛才指定的家。**  
   在 [aos_agent_listen.py:56](../../lib/aos_agent_listen.py)、`aos_agent_status.py:194`、`aos_agent_say.py:41`、`aos_kernel_check.py:91`。例如從 repo 執行 `listen --target /abs/bob`，警告仍叫人打裸 `aos-agent continue`／`status`；check 的環境警告只印裸 `aos-kernel halt`。應帶回原本的 `--target`，並對路徑做 shell quoting。否則照抄會失敗，或碰到另一個家。README 第 117 行的裸 continue 也有同樣問題。

7. **README 升級步驟要求舊版執行新版才有的指令。**  
   在 [README.md:118](../../README.md)。寫「先 halt，換版後再重開」，但 `8172a68` 沒有 halt。換版前應使用舊版 `aos-kernel stop K`、`aos-daemon stop --home D`，換版後才用 boot／halt。這段照抄會退用法錯；現有測試沒有驗升級流程。

8. **部分等待條件測試沒有真的走到待驗分支。**  
   在 [test_agent_daily_edges.py:59](../../lib/test/test_agent_daily_edges.py) 與第 84 行。測試列出 batch、intake、未消費輸入、TEXT 不符、H0 前的 user 等反例，但家未登記，全部先走 `unregistered` 退 101；即使拿掉那些完成條件，測試仍可能通過。應先建立登記，再確認確實因目標條件未滿而等待／逾時。其他 r3 測試確實有驗成功回話、暫態壞檔與連敗早退，問題是這組反例覆蓋失效。

9. **「非 agent 家不建鎖」只涵蓋完全沒有 info.json。**  
   在 [aos_agent.py:41](../../lib/aos_agent.py)。只要有 info.json，就先建立／改写鎖；因此 kernel、cpu 的家也會被留下 `.tick.lock` 才報 `NotAnAgent`。若同時有 `paused`，甚至直接退 0、完全不驗身分。應區分其他類型的家與允許暫停的壞 agent 設定，並同步細化規範；目前測試只有「沒有 info」那種非 agent 家。控制流程已用 mock 確認。

**可以之後**

- [lib/README.md:296](../../lib/README.md) 仍寫 `aos-cpu DIR`，應改 `[DIR]` 並註明 cwd。現有寫法可跑，但漏了本輪新增行為。
- [daemon.md:227](../../spec/daemon/README.md) 與第 50 行仍稱 daemon 鎖是「整個系統唯一的一把鎖」，已與 agent tick 鎖矛盾，應限縮措辭。
- `-h` 的 usage 仍顯示 `say [TEXT ...]`、`init [--config FILE]`，但實際要求恰好一段 TEXT、config 必填。說明內文有補，usage 仍應同步。
- 舊字串未完全清零：正文有改名註記，`aos-agent.md:472` 還保留舊位置參數形狀；`aos_agent_status.py:20` 則是真的讀取舊 `AOS_K` 鍵。後者已有規範及測試，是明寫的相容行為；不能把它算成「所有出現處已改完」。

tick 的**正常返回與被另一個 tick 擋住時都有關 fd**；正常同程序連叫不會自己卡住。雙程序測試也確實檢查第二個 tick 的退出碼、持有者 PID、檔案內容與 mtime 未改。

**3. 測試結果**

執行了指定 unittest 指令：**1083 條，未綠，1083 errors**。全部在初始化暫存目錄時被唯讀沙箱擋住，訊息為 `No usable temporary directory found`；沒有進入實際測試行為，不能据此判定產品失敗或通過。

另完成唯讀 CLI help／裸指令檢查與上述記憶體 mock 驗證。未啟動 daemon、cpu 或任何模型連線。