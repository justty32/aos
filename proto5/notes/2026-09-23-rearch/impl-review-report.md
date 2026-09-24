總評：主幹可算照規範落地，但還不能宣稱三份規範與實作完全一致。cpu 對帳、kernel 十步與出貨箱、daemon 握手及交接的主要順序吻合；另有合理修正尚未回寫規範。最先處理三件：cpu 家初始化半途失敗後無法恢復、daemon 缺失目標的錯誤碼、控制 pipe 的信封驗證。883 條全綠是使用者提供的結果；本次僅靜態審查，未改檔、未跑測試。以下路徑皆相對 `proto5/`。

## A／規範與程式的偏差

**A-1【要修：程式】daemon 把部分缺失目標回成 Usage。**  
規範 `spec/daemon.md:103`、`spec/daemon.md:127` 明定目標消失、讀不到回 `SpawnFailed`；`lib/aos_exec.py:112`、`lib/aos_exec.py:117` 卻將資料夾缺 `dir_target`、不存在的非 `.json` 目標丟成 Usage，再由 `lib/aos_daemon.py:149` 回 `-32602`。daemon 的明確特殊規則應優先於同步 aos-exec 的用法錯分類。

**A-2【要修：程式】控制 pipe 未驗合法信封。**  
規範 `spec/cpu.md:105` 規定 id 型別，`spec/cpu.md:200`、`spec/cpu.md:218` 要求 stop notification；`lib/aos_exec_cpu.py:63` 只驗物件及 `jsonrpc`。因此帶 `id:{}` 的 go／stop 仍會放行／停機，帶合法 id 的 stop 也會執行。應驗控制通知，非法控制行忽略。

**A-3【要修：規範】ack 命名刻意偏離固定格式。**  
規範 `spec/kernel.md:164`、`spec/kernel.md:167` 假設同格同家最多一則 ack；`lib/aos_kernel.py:265`、`lib/aos_kernel.py:297` 增加被 ack 名稱的摘要。實作較正確：補前格出貨、收新回音、清多個 tick 回音都可能需要多筆，改回規範格式反而會漏 ack。

**A-4【要修：規範】boot 多交接舊 kcpu。**  
規範 `spec/kernel.md:302` 只交接新 info 選出的 c；`lib/aos_kernel.py:470` 先驗舊、新兩顆，再逐一 kill、等移除。這是必要修正：換池時若只殺新 c，舊 tick 仍可能改帳本。另應明列新 c 暫時保留工作 slot，直到在途回音結清。

**A-5【可先放：已授權的介面差異】完整結果放在新 API。**  
`spec/cpu.md:191` 字面要求 `run_target()` 回傳 `timed_out`；`lib/aos_exec.py:175` 新增 `run_target_full()`，舊入口仍回 tuple。這符合 `notes/2026-09-23-rearch/impl-task.md:22` 的明確授權，應更新規範名稱，不應破壞相容性去改舊 API。

**規範未寫、實作自行選擇，不算偏差**

**A-6** 空集合的數字名稱從 0 起、只計 ASCII 十進位（`lib/aos_kernel.py:195`）；帶 id 的 ack／stop 選擇回 `-32600`（`lib/aos_home.py:217`）；exit 檔失敗只記診斷、保留孩子原退出碼（`lib/aos_daemon.py:239`）。這些細節的裁決見 B。既有行程不隨 info 預設改變則已有明文，並非自行擴張。

## B／12 條 impl-findings 裁決

編號對應 `notes/2026-09-23-rearch/impl-findings.md:7` 起的原 1～12 條。

**B-1 — (a) 規範要補寫。**  
`lib/aos_exec.py:175`；理由：任務書明授權保留舊契約。可貼：  
> `run_target_full()` 對三種目標回傳 `code`、`kind`、`timed_out`、`stopped`、`ms`，cpu 使用此入口；既有 `run_target()` 保留 `(code, kind)` 相容契約。

**B-2 — (b) 程式要改。**  
改 `lib/aos_exec.py:112`、`lib/aos_exec.py:117`：非同步入口的缺失目標統一為 `SpawnFailed`，由 daemon 回 `-32000`，理由見 A-1。Popen 起不來時不造 pid、不寫 exit 可以接受；inst 顯式指定 stdin／stdout 的 `-32602` 保留。

**B-3 — (a) 規範要補寫。**  
`lib/aos_daemon.py:239`；理由：孩子失敗與 exit 檔收尾失敗應分開，符合既定重拉判準。可貼：  
> daemon 的 `last_exit` 與 restart 判定只使用孩子實際退出碼；exit 檔寫失敗另記 `WriteFailed`，不改退出碼，也不因此重拉正常退出的孩子。

**B-4 — (a) 規範要補寫。**  
`lib/aos_home.py:217`；理由：notification 要求已有，缺的是違反時的處置。可貼：  
> `ack-`／`stop-` 檔必須是相應 method 的 notification；帶 id 時回 `-32600`，不執行控制動作。合法 notification 的 method／params 錯誤只刪原單、不回音。

**B-5 — (a) 規範要補寫。**  
`lib/aos_kernel.py:265`；理由：固定名稱不能承載同格多筆 ack。可貼：  
> ack 名稱為 `ack-<chain>-<seq>-<c>-<digest>.json`；digest 是被 ack 檔名之 SHA-256 前 16 個十六進位字元。同格同家可以有多筆 ack，不得把不同回音的確認合併。

**B-6 — (a) 規範要補寫。**  
`lib/aos_kernel.py:470`、`lib/aos_kernel.py:290`；理由：換池仍須維持唯一帳本主人。可貼：  
> boot 對舊 kcpu 與新 c 去重，先全部驗 target，再依序 kill 並等孩子表移除；兩筆 kill 的檔名加 cpu 名。新 c 原有工作 slot 暫留至 collect 結清，ack_ticks 跳過該回音。

**B-7 — (a) 規範要補寫。**  
`lib/aos_kernel.py:195`；理由：最大值加一未定義空集合。可貼：  
> 省略 name 時，只計 ASCII 十進位名稱；有數字名取最大值加一，沒有則從 `0` 開始。CLI once 未給 name 時仍使用自己的 request 檔名。

**B-8 — (c) 照現況接受。**  
`spec/kernel.md:152` 已明定行程政策 add 後不改，`lib/aos_kernel.py:201` 正照做。每格重讀 info 不代表覆寫既有政策，無須另加保證外條款。

**B-9 — (c) 照現況接受。**  
`spec/daemon.md:204` 已明列 init 收孤兒的前提；`lib/aos_daemon.py:68` 符合規範。測試使用 subreaper 合理。可加：「不會收孤兒的 PID 1 環境，不在接手完成保證內。」

**B-10 — (a) 規範要補寫。**  
`lib/aos_kernel.py:503` 只清帳本；理由：帳本待辦與已送通知是不同狀態，不能暗示兩者都取消。可貼：  
> boot 只丟棄帳本中尚未出貨的 stops；已送到 cpu.requests 的 stop 仍有效，新主人可能因此立即退出。boot 成功不保證排除這種跨代通知，須另確認鏈已運行。

**B-11 — (c) 照現況接受。**  
`spec/kernel.md:244` 本就把 append 排在出貨後，`lib/aos_kernel.py:444` 符合。可加：「kernel.log 不保證涵蓋崩潰中途已結帳的回音。」不能把現況描述成完整持久稽核紀錄。

**B-12 — (c) 照現況接受。**  
`spec/cpu.md:246`、`spec/kernel.md:341` 已排除 cpu 被 KILL 而工作仍活著；`lib/aos_exec.py:409` 確實另開 session。應在 `spec/kernel.md:305` 的「c 消失＝沒有格在跑」補上此例外；此次不要求新增 kill-tree。

## C／未覆蓋的崩潰窗口與競態

**C-1 — cpu 家初始化半成品，會永久卡住重試。**  
`spec/kernel.md:230`、`spec/kernel.md:310`；`lib/aos_kernel.py:331`。時序：mkdir → info／inst 尚未齊全就崩潰 → 重試見目錄存在直接返回 → 持續 spawn 失敗。`lib/test/test_kernel_recovery.py:178` 只測完整建立。應在 mkdir 後、info 寫完後各注入故障，重跑 boot／tick，驗可完成初始化且不覆蓋完整既有家。這是恢復缺口，不是單純順序偏差。

**C-2 — daemon 握手中間兩段未驗。**  
`spec/daemon.md:112`；`lib/aos_daemon.py:159`、`lib/aos_daemon.py:229`。時序：表已寫→go 前，或 go 已送→回音前崩潰；前者孩子應不碰家，後者可能已開始工作，須先交接再對帳。`lib/test/test_daemon.py:333` 只注入表寫失敗。應在兩處設同步閘門後 KILL daemon，驗真實 PID 消失、回音及原單處置。

**C-3 — 接手中的 daemon 再次死亡未驗。**  
`spec/daemon.md:204`；`lib/aos_daemon.py:354`。時序：第二任已 TERM／KILL 舊孩子→未寫新 state 就死亡；第三任仍須依舊表等死透，不能提前清表。`lib/test/test_daemon.py:304` 只涵蓋一次交接。建議連續兩次故障注入，驗孩子實際消失後才公布新表，current 仍完成對帳。

**C-4 — cpu 對帳本身再崩潰，及完成五步的真實邊界。**  
`spec/cpu.md:285`、`spec/cpu.md:299`；`lib/aos_home.py:192`、`lib/aos_exec_cpu.py:193`。時序：Interrupted／正常回音已寫→原單未刪，或原單已刪→current 未清就崩潰；都應保留回音、不重跑。`lib/test/test_home.py:148`、`lib/test/test_exec_cpu.py:341` 主要驗判定或預造檔案。應在實際寫回音、unlink 後分別注入故障，再驗副作用恰好一次。

**C-5 — 工作自行結束與第二次訊號交錯。**  
`spec/cpu.md:235`；`lib/aos_exec.py:479`。時序：工作已退出→回音未寫→第二次訊號到達；結果應有效、`stopped=false`。`lib/test/test_exec_cpu.py:232` 只測仍在睡眠的工作。應卡住完成後的窗口再送訊號，驗原退出碼及 stopped，避免誤作廢成功結果。

**C-6 — 已出貨 stop 跨 boot。**  
`spec/kernel.md:306`；`lib/aos_kernel.py:276`、`lib/aos_kernel.py:503`。時序：stop 已放入 cpu 家→cpu 未讀就被殺→boot 清帳本 stops→新 cpu 讀到舊 stop，可能讓 kernel 鏈未啟動就停。`lib/test/test_kernel_recovery.py:201` 只驗帳本清空。應留下真實 stop 檔再 boot，檢查 CPU 存活、last_seq 與待執行 tick，明確驗出 B-10 的邊界。

**C-7 — 回音已結帳並 ack，log 尚未 append。**  
`spec/kernel.md:244`；`lib/aos_kernel.py:329`、`lib/aos_kernel.py:444`。時序：收結果存帳→ack 被 cpu 消化→append 前崩潰；結果不重算，但證據可能永久缺失。`lib/test/test_kernel_integration.py:87` 只驗正常完成。應在 append 前注入故障並讓 cpu 消化 ack，確認計數不重複，同時把日誌缺口列為明示限制。

**C-8 — 出貨箱測試未逐箱驗「送出後、清帳前」。**  
`spec/kernel.md:217`；`lib/aos_kernel.py:261`。`lib/test/test_kernel_recovery.py:117` 第一次 save 就故障，因此只停在 acks；`:106` 則是全箱完成後倒回舊帳本。應對 replies／stops／deletes 各注入邊界，讓接收者在重放前實際處理，再驗回音、停止通知及 syscall 去重；否則尚未驗到接收者並行時的恢復。

## D／測試品質

**D-1 — timeout 測試押注 Python 啟動速度。**  
`lib/test/test_exec_cpu.py:205` 給 150ms，卻要求工作先裝 TERM handler 並退 0。慢機可能 handler 尚未安裝就收到 TERM，得到 143。應等 ready，再以受控時鐘或閘門觸發期限。

**D-2 — 強停尚未證明整個工作群組死亡。**  
`lib/test/test_exec_cpu.py:232` 只驗 stopped、退出碼及 cpu 退出；`:34` 的 cleanup 會再 KILL 群組。應加入忽略 TERM 的同組後代，於 cleanup 前驗其死亡，才能驗到兩秒後 KILL 的保證。不能泛稱整套都只信快照：`lib/test/test_rearch_e2e.py:77` 已逐一檢查實際 PID 消失。

**D-3 — Killing／Stopping 測試靠短窗口搶跑。**  
`lib/test/test_daemon.py:188` 在 300ms 階梯內串兩次 RPC；`:353` 在 400ms 內等狀態再串 RPC。慢機可能孩子先移除、回 NotFound，或 daemon 已退出。應控制階梯時鐘／閘門，再主動放行。

**D-4 — 用壁鐘上限推斷機制，受負載影響。**  
`lib/test/test_daemon.py:184`、`:230`、`:241` 分別用 0.8／0.9／1 秒上限推断立即重拉、並行階梯與 EPIPE 跳階。應以受控時鐘驗期限及訊號目標，真行程測試只保留合理總逾時。

**D-5 — context switch 不是訊號已處理的證據。**  
`lib/test/test_exec_cpu.py:235` 等 voluntary context switches 增加三次，推測第一次訊號已被 poll 消化；排程與 I/O 切換不等於該狀態已成立。應以明確 poll 同步點取代推測。

**D-6 — log 斷言弱，而且讀取過早。**  
`lib/test/test_kernel_integration.py:91` 等 bad／done 後立即讀 log，只搜尋幾個字串；但 `lib/aos_kernel.py:329` 先存狀態，`:446` 才 append，可能讀早。應輪詢解析 JSON，驗對應行程的完整 response、bad event 與精確門檻。

**D-7 — tick 週期斷言依賴取樣相位。**  
`lib/test/test_kernel_integration.py:110` 讀 seq 後才起錶，要求再跨三格至少 0.30 秒；若讀取後被暫停，起錶時可能已靠近格尾，只剩兩個完整 120ms 週期。應以受控時鐘驗睡眠設定，或記錄格變動的時間，避免用非同步取樣推斷固定下限。