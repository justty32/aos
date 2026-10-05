**proto7-2 可以在核心零改動下保存觀測到的快照、既有 daemon 成功追加的事件，以及合作任務主動發布的事件；若要求所有底層事件都不漏，則必須補上來源端的交接契約，單靠 history、JSONL 或集中收集都做不到。**

## 1. 審查範圍與證據限制

本報告針對「事件保存」提出調查與候選方案，沒有實作或替使用者選定方向。

- 審查日期：2026-10-05。
- 工作樹版本：`6daebe2ef8227021745def649f4e3d86a3a8038c`。
- 使用五條唯讀子代理線，分別檢查核心事件、history／擴充點、模組讀者、儲存語意與原始設計意圖，再交叉核對。
- 全程未修改檔案、未執行測試或故障探針、未 commit／push。檢查前後 `git status --short` 均無輸出。
- 下文的崩潰案例是**有程式行序支持的靜態推導**，不是本輪實測結果。既有測試只用來核對目前承諾。

有兩項來源限制：

1. **找不到 `proto7/user-advice.md` 正本。** 工作樹搜尋與 Git 歷史查詢均未找到；SESSION-LOG 也註明當時未 commit。因此只引用現存轉述，不聲稱讀過原檔。保存原則的轉述見 [changes-from-7-1.md](../../changes-from-7-1.md):18，未 commit 記載見 [SESSION-LOG.md](../../../../wf/SESSION-LOG.md):16。
2. **`layer-interfaces.md` 是較早版本的調查。** 它明寫對象為 `6ed9a7a7`；其中部分問題已修、部分功能已移出核心。本報告用它理解分層，現況以目前程式與 spec 核對。見 [layer-interfaces.md](../../layer-interfaces.md):5、[problems.md](../../problems.md):146。

## 2. 原始方向對事件保存的限制

使用者想法正本要求：**操作與協議盡量採 JSON／文字，讓 LLM 讀得懂、能操作**；kernel 與 agent 建立在檔案系統和 tick-tock 之上。見 [2026-10-03-aos-layering.md](../../../../proto6/notes/2026-10-03-aos-layering.md):7、[同檔](../../../../proto6/notes/2026-10-03-aos-layering.md):48。

目前落地的相關邊界是：

| 邊界 | 對本提案的含義 | 證據 |
|---|---|---|
| 核心只留上一次，歷史可選 | 新保存功能可以增加模組自己的資料，不能默默讓核心恢復逐回合累積歷史 | [spec.md](../../../spec.md):21 |
| 新功能預設進模組 | 儲存、查詢、輪替與留存政策應先放模組；進核心須回答現有三問 | [README.md](../../../README.md):75 |
| 正式接面是任務、argv 包裝、工具 | 現況沒有正式的 tick／tock 外掛 hook | [spec.md](../../../spec.md):269 |
| 已否決同步外部 hook | hook 的失敗與逾時會進入核心執行路徑；重新提出須明說是在改既有決定 | [core-slimming.md](../../core-slimming.md):174 |
| 事件逐件保存是上層通道契約 | 要定保存、確認、容量與滿載處理，不能只換檔案格式 | [r5-synthesis.md](../../../../proto7/notes/thinking/2026-10-04-r5-synthesis.md):11 |

「事件保存 → agent／LLM 作者與 adapt-llm」確實是目前剩餘順序；更早的思考紀錄則限定為「有逐件需求再補」。這支持先釐清要保住的事件，不代表已經決定建一套全系統流水帳。見 [SESSION-LOG.md](../../../../wf/SESSION-LOG.md):15、[r6-synthesis.md](../../../../proto7/notes/thinking/2026-10-04-r6-synthesis.md):24。

## 3. 現在會遺失什麼，誰需要它

以下列的是**目前已有的流失路徑**，不表示每項都是 bug。只留最新、漏取樣與回條覆寫，多數是現行規格明定的取捨。

### 3.1 核心與控制通道

| 編號 | 會消失的資訊與時機 | 主要讀者／用途 | 證據 |
|---|---|---|---|
| F01 | 每回合的 started、ended、skipped、errors、控制與掛載結果，在下一份 `last-round.json` 發布後被覆寫；槽內 `tock.json` 也只留最新 | kernel／重試模組判斷工作進度；agent 接續上下文；人追查漏跑 | [aos7_tock.py](../../../lib/aos7_tock.py):90、[spec.md](../../../spec.md):238 |
| F02 | 通知失敗 `notify_errors` 只寫進 `round.json`，不進已提交的總結；下一次 tick 重建 round 時消失 | kernel、人：為何某任務沒收到回合通知 | [aos7_tock.py](../../../lib/aos7_tock.py):101、[aos7_tick.py](../../../lib/aos7_tick.py):287 |
| F03 | 換 run 時清掉 birth、pid、exit、out.log、writes.jsonl 與動態掛載資料；刪整槽時連任務自己的 state 也消失 | agent、人、稽核：當時跑了什麼、輸出與退出原因 | [aos7_task.py](../../../lib/aos7_task.py):20、[同檔](../../../lib/aos7_task.py):275、[aos7_tock.py](../../../lib/aos7_tock.py):133 |
| F04 | `tasks.json` 舊版本、once 原項目與修改沿革消失；`tasks_rev` 只是摘要，不能還原原文。birth 保存的欄位也不是完整任務表 | kernel、作者、人、稽核：依哪份定義派工 | [aos7_tick.py](../../../lib/aos7_tick.py):319、[同檔](../../../lib/aos7_tick.py):355、[aos7_task.py](../../../lib/aos7_task.py):294 |
| F05 | 實際展開後的 argv、執行環境及 inst 當時內容未完整留存；只有路徑時，來源檔改掉就不能還原執行依據 | agent、人、稽核：重現與解釋結果 | [aos7_run.py](../../../lib/aos7_run.py):66、[同檔](../../../lib/aos7_run.py):72、[aos_inst.py](../../../lib/aos_inst.py):77 |
| F06 | daemon 的 `last_event`、`last_error` 與 phase 沿革只剩最新值；一般時間線錯誤沒有全部送進 log | kernel 監督、人、稽核：何時卡住、恢復或被控制 | [aos7_daemon.py](../../../lib/aos7_daemon.py):79、[aos7_daemon_timeline.py](../../../lib/aos7_daemon_timeline.py):111 |
| F07 | daemon／task 控制回條同名覆寫；任務總結只保存部分控制結果。restart 的去重證據在 pending once／目前 birth，換 run 後可能消失 | kernel、agent、人、稽核：哪個請求被接受、作用在哪個 run、是否已做 | [aos7_daemon.py](../../../lib/aos7_daemon.py):365、[aos7_task.py](../../../lib/aos7_task.py):240、[control/README.md](../../../modules/control/README.md):22 |
| F08 | 掛載准駁回條同名覆寫，換 run 清掉動態掛載與請求；先前給過什麼、為何拒絕，無永久沿革 | kernel、agent、人、稽核：依賴與可見空間的變化 | [spec.md](../../../spec.md):185、[aos7_task.py](../../../lib/aos7_task.py):21 |

其中 F07 要區分兩種情況：**已處理回條被下一份覆寫**是目前的保存政策；不同寫者把尚未處理的同名請求互蓋，則是既有檔名協定的使用邊界。保存端都無法在事後補回原內容。見 [spec.md](../../../spec.md):68、[同檔](../../../spec.md):286。

### 3.2 已落地的模組與任務包

| 編號 | 已有證據與仍會遺失的部分 | 誰需要 | 證據 |
|---|---|---|---|
| F09：step | 槽外結果可供接續；但 `halt` 在 resume 時清掉，close 刪 results，重開工作會換框架。這不是完整的派工／等待／重送歷史 | kernel 工作控制、agent 作者、人 | [aos7_step.py](../../../packs/step/aos7_step.py):689、[同檔](../../../packs/step/aos7_step.py):741 |
| F10：adapt | 明定只轉最新值。短暫越過門檻再恢復、中間版本與 unknown→ok 過程可能沒被看見；`skipped` 只能指出部分漏取樣數量 | 需要「每件」或「期間曾發生」的 kernel／agent、人 | [adapt/README.md](../../../packs/adapt/README.md):25、[同檔](../../../packs/adapt/README.md):33 |
| F11：budget | 帳的餘額、ops、轉移記錄與去重證據一起保存；但拒絕的預留不入帳，回條可被消費／清理，gateway 的 intent 被終局取代。核帳完整不等於每次拒絕、准入、重送都留史 | kernel 資源管理、稽核、人 | [budget/README.md](../../../packs/budget/README.md):30、[aos7_budget_gate.py](../../../packs/budget/aos7_budget_gate.py):96、[budget/spec.md](../../../packs/budget/spec.md):95 |
| F12：subd／audit | subd 生命週期檔持續更新，部分原因只在 out.log；audit 的 writes.jsonl 只留本 run，且只涵蓋包裝過的 Python 寫入操作 | kernel 管子空間、人、稽核 | [aos7-subd](../../../modules/subd/aos7-subd):264、[audit/README.md](../../../modules/audit/README.md):17 |

兩個重要限制：

- **budget 目前算的是 `fakeapi.calls`，不是 LLM 的可計費 token。** 任務失敗也可能已受理，不能拿失敗事件當「沒有支用」。見 [budget/README.md](../../../packs/budget/README.md):13、[同檔](../../../packs/budget/README.md):34。
- **audit 的 `ok` 表示寫入位置是否在允許範圍，不是該次寫入成功。** 它也不保存被寫入的內容。見 [audit/README.md](../../../modules/audit/README.md):28。

### 3.3 四種讀者，不能共用一種完整性假設

| 讀者 | 需要的資料 | 可以接受的界線 |
|---|---|---|
| kernel／控制與恢復模組 | run、request、結果、控制完成證據、可否重試 | 觀測可取樣；一旦用來驅動必做工作，就要有逐件交接與去重契約 |
| agent／LLM 作者 | 當時輸入、依據版本、工具結果、錯誤與決策脈絡 | 可讀摘要，但要能追到原證據，並知道哪些內容已不存在 |
| 人 | 時間順序、原因、前後狀態、缺口 | 可以接受有標示的缺口；不能把讀不到顯示成「沒發生」 |
| 稽核 | 請求人、請求身分、准入／拒絕、效果與結算的關聯 | 不能從快照、退出碼或摘要推導完整效果史 |

proto7-2 尚未落地完整的 kernel／agent；後兩層需求是下一階段的設計需求。既有核心恢復仍靠 round／last-round，step、budget、subd 也各有權威證據，通用事件保存不應直接取代它們。見 [README.md](../../../README.md):5、[spec.md](../../../spec.md):262。

## 4. 現有 history 與 log.on 能做到哪裡

### 4.1 history 是取樣器，還不是逐件事件通道

目前流程是：

> 等自己的 tock → 逐一讀來源最新總結 → append → 必要時截行 → 最後另存取樣進度。

見 [history.py](../../../modules/history.py):57、[同檔](../../../modules/history.py):106。

具體限制如下：

| 發現 | 影響 | 證據 |
|---|---|---|
| 只讀 last-round 與 status 頂層 last_event | 不保存整份 status、notify_errors、birth／exit、輸出或回條 | [history.py](../../../modules/history.py):65 |
| 首次直接記當下回合；之後才對跳號記 gap | 「沒有 gap」不能證明從開始到結束都完整 | [history.py](../../../modules/history.py):69 |
| 收到通知後才讀來源 | 收到第 R 回合通知，不保證讀取時仍是第 R 份總結；跨來源也不是同一時刻的快照 | [history.py](../../../modules/history.py):112、[aos7_tock.py](../../../lib/aos7_tock.py):96 |
| 只接受 `round > prev` | 同路徑來源重建、回合歸零時，會略過新回合直到超過舊進度，沒有 reset 記錄 | [history.py](../../../modules/history.py):69 |
| 檔名把 `/` 換成 `+` | `a/b` 與 `a+b` 共檔；`daemon-events` 來源又可能與 `--status` 共檔 | [history.py](../../../modules/history.py):72、[同檔](../../../modules/history.py):85 |
| `--max-lines` 是整檔讀回再 replace | 不是分段輪替；限制行數不等於限制 bytes，gap 與重複行也占額度 | [history.py](../../../modules/history.py):39 |
| append 與 state 分開提交 | append 後被殺可能重複；歷史檔失去但 state 還在時，不會自動補回 | [history.py](../../../modules/history.py):75、[同檔](../../../modules/history.py):115 |

現有 history 測試把 `gap` 展開後一起算覆蓋，因此測試通過代表「缺號可被表達」，不代表每回合原始資料都有保存。見 [test_modules_history.py](../../../modules/tests/test_modules_history.py):40。

### 4.2 log.on 比 last_event 取樣完整，但仍有限

`log.on` 讓 daemon 將顯式發出的事件追加到 `.aosd/log.jsonl`。它有本程序的 thread lock，但寫入 `OSError` 直接略過，主流程繼續。見 [aos7_daemon.py](../../../lib/aos7_daemon.py):79。

因此 [modules/README.md](../../../modules/README.md):31 所說的「完整流水帳」，應限縮理解為：**比只保留 last_event 更完整的既有事件出口**。它不等於：

- 每次 tick／tock、每個 task 啟停都有事件。
- 每個已發生事件都成功寫入。
- 斷電後所有紀錄都還在。
- 現有 history 已經會續讀這份檔案。

一般時間線錯誤只更新 `last_error`，就是未全面進入 log 的例子。見 [aos7_daemon_timeline.py](../../../lib/aos7_daemon_timeline.py):111。

## 5. 崩潰語意：哪些是遺失，哪些已有恢復

### 5.1 現行程式的關鍵窗口

| 中斷位置 | 靜態推導結果 | 對保存提案的要求／證據 |
|---|---|---|
| history append 成功，state 尚未保存 | 重起可能再追加同一份總結；有截行時，重複還會擠掉較早紀錄 | 需要穩定識別及重播規則。[history.py](../../../modules/history.py):75、[同檔](../../../modules/history.py):115 |
| JSONL 寫到半行或半個 UTF-8 字元 | 舊半行不會自動恢復；下一次 append 只是補換行隔開 | 讀者須報損壞，不能把跳過壞行當完整成功。[aos7_fs.py](../../../lib/aos7_fs.py):163 |
| daemon 已 apply、寫回條、刪請求，尚未 log | 動作已生效，流水帳可能沒有這件；回條之後也可被覆寫 | 事後 collector 無法單獨補足。[aos7_daemon.py](../../../lib/aos7_daemon.py):358 |
| task 已起、once 已刪，但 started 尚未落盤 | 實際執行可存在，恢復總結仍可能沒有 started 項 | 總結不能當完整啟動事件流；這裡不判定為違反現行契約。[aos7_tick.py](../../../lib/aos7_tick.py):338 |
| runner 已 wait 得到退出碼，尚未寫 exit | 原退出碼可能永久失去，後續只剩 lost／unknown | 保存包不能從 lost 推回成功、失敗或未執行。[aos7_run.py](../../../lib/aos7_run.py):89 |
| tock 已收到通知寫入錯誤，尚未存 round | 錯誤只在記憶體；重播若成功，第一次失敗可能再無證據 | 連保存所有 summary 都不足以保存所有實際錯誤。[aos7_tock.py](../../../lib/aos7_tock.py):102 |
| tock 已提交 summary，尚未通知／標記／關回合 | **已有恢復協定**：重播同回合總結並補收尾 | 不應把這個窗口誤報成總結必遺失。[aos7_tock.py](../../../lib/aos7_tock.py):60、[同檔](../../../lib/aos7_tock.py):139 |

這裡有一個無法靠提高輪詢頻率解決的界線：對觀測器而言，「來源只發布 X」與「來源發布 Y，再覆寫成 X，觀測器才醒來」可能完全相同。來源若沒有留下 Y，保存端就無從補回。這也符合既有思考紀錄對「核心零新增」的限縮。見 [r5-synthesis.md](../../../../proto7/notes/thinking/2026-10-04-r5-synthesis.md):28。

### 5.2 `kill -9` 與整台斷電要分開承諾

目前 `write_json` 是暫存檔寫完後 replace；`append_jsonl` 正常返回前會關檔，但兩者沒有 `fsync`。這有助於避免讀者看到半份替換，**不能直接推成主機斷電後的新資料必定保存**。見 [aos7_fs.py](../../../lib/aos7_fs.py):119、[同檔](../../../lib/aos7_fs.py):163。

新契約可以區分：

| 等級 | 「保存成功」的意思 | 尚未涵蓋 |
|---|---|---|
| 程序中斷可接續 | 資料完整交給作業系統後才確認；收集程序被 SIGKILL 可重新讀取 | 主機斷電、儲存裝置故障 |
| 主機中斷可接續 | 完成必要的檔案同步；新檔與輪替還處理目錄項同步，成功後才確認 | 多檔自動形成交易、外部副作用恰好一次 |
| 批次同步 | 公開「已同步到哪一筆」；較新的資料尚未有同等承諾 | 不能只因設定每秒同步，就保證最多只丟一秒 |

Python 官方要求緩衝檔案先 `flush()` 再 `os.fsync()`；Linux 文件也明說檔案 fsync 不自動同步其目錄項，成功 write 本身不等於持久化。見 [Python `os.fsync`](https://docs.python.org/3/library/os.html#os.fsync)、[Linux `fsync(2)`](https://man7.org/linux/man-pages/man2/fsync.2.html)、[Linux `write(2)`](https://man7.org/linux/man-pages/man2/write.2.html)。

## 6. 三個候選做法

**A、B 回答「存在哪裡」；C 回答「在哪裡取得事件」。它們可以組合，並非完全互斥的三選一。**

| 面向 | A：每 node JSONL＋分段輪替 | B：集中事件收集 | C：來源提供事件出口，保存交模組 |
|---|---|---|---|
| 主要價值 | 單 node 可獨立使用、資料靠近來源 | 跨 node 查詢、統一配額與維護 | 在資訊消失前取得事件 |
| 輸入 | 快照取樣、既有 log、合作任務發布 | 同 A，集中讀取或接收 | 任務作者／wrapper；必要時新的核心事實出口 |
| 崩潰重點 | 半寫尾端、輪替、append 與游標分離 | A 的問題，加上收件確認與來源積壓 | 狀態改變與發事件之間的窗口 |
| 檔数成長 | 隨 node／stream 數及保留段數成長 | 中央段數＋來源暫存＋讀者狀態 | 由保存後端決定；逐事件檔會隨事件數成長 |
| 讀者 | 直接讀 JSONL；工具按來源／run／游標查詢 | 統一查詢；保留各來源的識別與順序 | 需要另選 A 或 B 才有保存與查詢 |
| 核心零改 | 可以；對現有核心來源仍有取樣／出口覆蓋限制 | 可以集中取樣；可靠逐件交付需來源合作 | 任務端出口可以；新增正式核心 hook 不可以 |
| 主要代價 | 多 node 分散管理 | 集中故障點、積壓與滿載政策 | 必須定義事件的提交、補交與失敗語意 |

### 6.1 A：每 node 保存 JSONL，模組自行分段

候選形態是在槽外建立模組自己的事件資料夾，使用固定數量的活躍檔、不可再修改的封存段，以及少量 JSON 狀態。避免每回合新建一個資料夾。

**擷取能力分三種標示：**

- `sample`：觀測公開最新檔，承認可能漏。
- `source_log`：續讀既有來源流水帳，只承諾來源成功寫出的範圍。
- `published`：合作來源主動交付，有穩定事件 ID 與確認協定。

這與目前 A 任務、B argv 包裝、C 工具的接法相容。見 [modules/README.md](../../../modules/README.md):7。

**kill -9 在寫一半時：**

- 讀者只前進到完整紀錄邊界；未完成尾端不能當正常 EOF 或已消費。
- 恢復寫者在排他保護下處理壞尾，必要時隔離舊尾並開新段，留下損壞範圍。
- 已寫入但尚未回確認的事件可以重送；沿用原事件 ID。
- append 成功但游標未保存，允許重讀，由明確的去重契約處理。
- 封存段使用不重用的識別；輪替不只靠 `.1`、`.2` 這類會換意義的名稱。

**寫入者必須有契約。** 可以單寫者，或所有合作寫者共同拿不會被輪替的 sidecar lock。不能直接把目前沒有跨程序協調的 `append_jsonl` 當通用多寫者介面。見 [aos7_fs.py](../../../lib/aos7_fs.py):163。

**核心零改的容量例外：** 新包可限制自己的歷史檔，但 `.aosd/log.jsonl` 仍無限追加。現有 history 的 trim 沒有與 daemon 共鎖，不能安全地拿來裁正在寫的來源 log。讀取到 replace 之間的追加可能消失；已開啟的 fd 也仍指向舊檔。見 [history.py](../../../modules/history.py):44、[aos7_daemon.py](../../../lib/aos7_daemon.py):85、[Linux `rename(2)`](https://man7.org/linux/man-pages/man2/rename.2.html)。

若坚持核心零改，來源 log 必須明列為「不在本包容量上限內」，或安排所有寫者停止後的維護。

### 6.2 B：集中 collector／事件匯流

候選形態是一個普通任務，集中接收多個 node 的事件，使用單寫者管理中央 JSONL 分段與查詢。

**若只是集中輪詢最新檔，它仍然是取樣。** 集中化不會自動提高來源完整性，也不會把不同時間讀到的多個 node 變成一致快照。

若要可靠交付合作來源發布的事件，來源需要保存「已送出、尚未確認」的資料：

> 來源保存待交資料 → collector 保存 → 回收件確認 → 來源才可清掉已交資料。

**kill -9 在各階段的結果：**

| 中斷點 | 所需行為 |
|---|---|
| 來源尚未完成待交保存 | 不能回報發布成功；已發生的外部效果仍可能未知 |
| 待交資料已保存，collector 未收到 | 來源恢復後重送 |
| collector 寫到半筆 | 按 A 的尾端規則恢復 |
| collector 已保存，確認尚未送到 | 來源重送同 ID；collector 去重 |
| 讀者已做事，自己的處理位置尚未保存 | 可能重做；讀者仍需冪等或自己的提交協定 |

來源暫存若也是 node-local JSONL，實際就是 **A＋B**。若改成每事件一檔，則會增加大量檔案；不能只計中央檔案數。

集中順序只能稱為**收件順序**。跨 node 的 `round` 各屬自己的時間線，不能直接混成全域先後。

### 6.3 C：只提供事件出口，保存由模組負責

這個方案要分兩種。

**C1：任務作者或 argv wrapper 主動發事件。**

可以核心零改。適合工作結果、控制意圖、資源准入、LLM／工具呼叫等由上層掌握的事件。step 已有「由結果產生者發布不覆寫的槽外結果」的例子。見 [aos7_step_result.py](../../../packs/step/aos7_step_result.py):28。

限制是 wrapper 開始前的啟動失敗、wrapper 本身被殺，以及繞過它的工作，都不會因此得到完整紀錄。

**C2：新增核心事實出口。**

這是核心改動，即使只加少量呼叫也一樣。現有正式契約沒有此 hook，而且已否決同步外部程式與進程內外掛。見 [spec.md](../../../spec.md):271、[core-slimming.md](../../core-slimming.md):177。

若使用者要求保存每份已提交的核心結果，較具體的問題應是：

- 來源何時建立可重讀的待交證據？
- 來源提交後、交付前被殺，誰負責恢復補交？
- 在補交完成前，能不能覆寫唯一的舊證據？
- 保存失敗是否阻止下一個動作？

單純「動作後呼叫 hook」仍留有動作完成、hook 尚未執行的空窗；改成非同步單一通知檔也仍會覆寫。只要保留未確認資料，就已經引入待交佇列、容量與清理責任。

**不能借用 `AOS7_TEST_HOOKS` 冒充正式零改方案。** 它在核心行程同步載入與呼叫測試程式，沒有正式外掛的故障隔離契約，提供的也只是測試點。見 [aos7_fs.py](../../../lib/aos7_fs.py):51。

## 7. 不論選哪案，都需要先寫清楚的契約

以下是提案內容，尚未實作或定案。

### 7.1 分清楚紀錄、事件與確認

每筆資料至少要能回答：

1. 誰產生？
2. 這是來源發布的事件，還是觀測器讀到的快照？
3. 何時算保存成功？
4. 成功前中斷，怎麼確認或重送？
5. 誰可以刪，何時可以刪？
6. 它能證明哪件事？

建議把兩種確認分開：

- **保存確認**：保存端已接受這筆，承諾指定故障模型與保留期。
- **消費確認**：某個讀者已處理到這筆。

LLM 看過摘要不等於 kernel 已完成該事件要求的動作；collector 收件也不等於讀者已處理。

### 7.2 JSON 保留來源，識別不靠時間戳猜

例如取樣紀錄可長成：

```json
{
  "v": 1,
  "stream": "保存串流識別",
  "seq": 42,
  "kind": "round.observed",
  "capture": "sample",
  "source": {"node": "team", "round": 17},
  "observed_at": "時間",
  "payload": {"原始總結": "……"}
}
```

合作來源發布的事件另外帶穩定 `event_id`，以及適用的 request、attempt、slot、run。

幾個必要區別：

- 保存器配的 `seq` 只排序**已保存的紀錄**，不能證明未觀測事件不存在。
- `(node, round)` 不足以代表同回合所有版本；內容相同也不一定是同一件業務事件。
- 來源重建要有明確的資料世代；daemon gen、inode 或內容雜湊都不能普遍替代它。
- 核心零改的旁路觀測器若無法辨識重建，應回報 `source_reset_unknown`，不能自行猜完就宣稱去重完整。

現有 history 的 nid＋round 比較正是需要改進的證據；budget 則示範了 request 與 attempt 應分開，後者不是新扣款鍵。見 [history.py](../../../modules/history.py):69、[budget/README.md](../../../packs/budget/README.md):42。

### 7.3 讀者介面要能表達缺口與未知

保留可直接 `cat` 的 JSONL，再提供可輸出 JSON／文字的模組工具。查詢至少支援來源、kind、round／run、游標、筆數上限。

回覆應包含：

| 欄位 | 用途 |
|---|---|
| `records` | 本次讀到的紀錄 |
| `next_cursor` | 下次接續位置 |
| `earliest_cursor` | 目前最早仍可讀的位置 |
| `coverage` | 此來源是取樣或逐件發布，涵蓋從哪裡開始 |
| `gaps` | 已知的取樣缺號、留存淘汰、來源重設 |
| `errors` | 不可讀、損壞或來源身分不明 |

目前 `read_jsonl` 對壞行略過，讀取錯誤回已讀部分；無結尾換行但合法的 JSON 也會被接受。新包若採「完整換行才算紀錄邊界」，必須明訂為**新契約**。見 [aos7_taskside.py](../../../modules/tools/aos7_taskside.py):97。

完整換行只代表紀錄格式完整，仍不等於 fsync 完成或讀者確認。

### 7.4 留存政策不能破壞原包的恢復證據

新保存包應管理自己的資料，不順手清掉其他包的權威紀錄：

- budget 的帳、入口與後端紀錄，規定保留到預算明確退役。見 [budget/spec.md](../../../packs/budget/spec.md):102。
- subd 在停止提交中斷後，會讀 status 與本代 stop 回條，判斷是否應保留子任務。任意清回條會影響恢復判定。見 [aos7-subd](../../../modules/subd/aos7-subd):141。
- step 結案會清结果；若新讀者需要結案後追溯，須在清理前完成明確的保存交接。見 [aos7_step.py](../../../packs/step/aos7_step.py):689。

此外，adapt 的 `basis.sha` 能指認版本，不能還原已消失的原文。要供 agent／LLM 重查或重算，須保存必要原版及規則版本，否則明確回報 unavailable。見 [adapt/spec.md](../../../packs/adapt/spec.md):94。

## 8. 檔數與容量估算

令：

- \(N\)：node 數。
- \(\lambda\)：每 node 每秒紀錄數。
- \(b\)：平均每筆 bytes。
- \(T\)：保存秒數。
- \(S\)：每段目標大小。

未壓縮資料量約為：

\[
V = N\lambda bT
\]

輪替只能限制單檔大小；**沒有淘汰政策，總容量仍持續成長**。

| 方案 | 資料檔估算 | 額外要計入 |
|---|---|---|
| A：每 node 分段 | 約 \(\sum_i \lceil V_i/S\rceil\) | 每來源活躍檔、manifest、鎖、讀者位置 |
| B：集中分段 | 約 \(\lceil\sum_i V_i/S\rceil\) | 來源待交資料、中央狀態、去重與讀者位置 |
| C：每事件一檔交付 | 未清理部分隨事件數成長 | 接收確認、回條、清理狀態；若改分段則回到 A／B |

**示例，不是本輪量測：**100 個 nodes，每 node 每秒一筆，每筆 2 KiB：

- 每天約 **16.48 GiB**。
- 七天約 **115.36 GiB**。
- 每段 16 MiB、理想填滿估算：分散約 7,400 段，集中約 7,383 段，尚未計額外檔案。

集中化幾乎不減少資料本體。

若每 node 最多留 **8 段、每段 64 MiB**，資料段最多 800 檔、50 GiB；上述流速只能保存約 **3.03 天**，不能同時承諾完整七天。

要使容量上限成立，還需限制單筆大小、在超過段大小前換段，並計入來源積壓、暫存與隔離壞尾。現有 `.aosd/log.jsonl` 與 budget 自有證據另有自己的成長規則，不能算進「新保存包有上限」就當全系統有上限。見 [spec.md](../../../spec.md):117、[budget/spec.md](../../../packs/budget/spec.md):95。

## 9. 後續落地時的驗收項目

本輪沒有執行下列測試；這是方案選定後的驗收建議。

| 驗收情境 | 應驗證的結果 | 現有依據／可延伸位置 |
|---|---|---|
| 來源比讀者快、讀者 pause、首次晚加入 | 取樣來源誠實報覆蓋限制；逐件來源在契約範圍內可補讀 | [test_modules_history.py](../../../modules/tests/test_modules_history.py):31 |
| append／確認／游標各中斷點 SIGKILL | 已確認且未淘汰資料可查；未確認重送沿用 ID；不憑空報成功 | [history.py](../../../modules/history.py):75 |
| 半行 JSON、半個 UTF-8、合法但未換行尾端 | 不誤報完整；讀者不自行修檔；恢復後能繼續前進 | [aos7_fs.py](../../../lib/aos7_fs.py):163 |
| 輪替前後中斷、讀者仍在舊段 | 游標不指向錯誤檔案；無靜默漏段；淘汰明報 gap | [history.py](../../../modules/history.py):39 |
| 同路徑來源重建、round 歸零、名稱碰撞 | 不略過新來源、不混合不同來源；無法判定時報未知 | [history.py](../../../modules/history.py):69 |
| collector／來源暫存滿載或不可寫 | 按選定政策等待或放行；失敗不能回成已保存 | [aos7_daemon.py](../../../lib/aos7_daemon.py):87 |
| step close、budget 重送、subd 停止恢復 | 保存與淘汰不破壞既有恢復、去重和停止判定 | [budget/spec.md](../../../packs/budget/spec.md):102、[test_subd_recover.py](../../../modules/subd/tests/test_subd_recover.py):246 |
| 消費者做完副作用、存處理位置前被殺 | 依冪等／回條契約恢復；不能只靠 archive 去重就宣稱效果恰好一次 | [budget/README.md](../../../packs/budget/README.md):39 |

既有 SIGKILL 測試可作為測試風格參考，但不等於已驗證新保存契約：核心交接點見 [test_matrix_once.py](../../../tests/core/test_matrix_once.py):25，通知失敗與重播見 [test_matrix_a3.py](../../../tests/core/test_matrix_a3.py):325。

## 10. 唯讀查核指令

以下可在 repo 根目錄重查本報告的關鍵證據；不會啟動 daemon、執行測試或產生 pycache。

```sh
# 版本與缺失的原始文件
git --no-optional-locks rev-parse HEAD
git --no-optional-locks status --short
git --no-optional-locks ls-files proto7/user-advice.md
git --no-optional-locks log --all --oneline -- proto7/user-advice.md

# history 保存、去重、截行與 checkpoint 順序
nl -ba proto7-2/modules/history.py | sed -n '39,115p'
nl -ba proto7-2/modules/tests/test_modules_history.py | sed -n '31,68p'

# 原子替換、JSONL 追加、讀取時如何處理壞行
nl -ba proto7-2/lib/aos7_fs.py | sed -n '119,172p'
nl -ba proto7-2/modules/tools/aos7_taskside.py | sed -n '97,112p'

# summary 與通知錯誤的提交順序
nl -ba proto7-2/lib/aos7_tock.py | sed -n '90,110p'
nl -ba proto7-2/lib/aos7_tick.py | sed -n '278,288p'

# daemon 事件出口與控制完成後才記事件的窗口
nl -ba proto7-2/lib/aos7_daemon.py | sed -n '79,88p;357,377p'
rg -n 'self\.log\(|self\.event\(|last_error' proto7-2/lib/aos7_daemon*.py

# 槽清理、啟動紀錄、退出碼的保存窗口
nl -ba proto7-2/lib/aos7_task.py | sed -n '275,305p'
nl -ba proto7-2/lib/aos7_tick.py | sed -n '338,360p'
nl -ba proto7-2/lib/aos7_run.py | sed -n '85,92p'

# 上層保存與清理責任
rg -n 'accepted|def close|halt=None' proto7-2/packs/step/aos7_step.py
rg -n 'last_seq|skipped|write_json|write_reg' proto7-2/packs/adapt/aos7_adapt.py
rg -n 'admitted_tock|done_from|write_json' proto7-2/packs/budget/aos7_budget_gate.py
rg -n 'allowed_stop|commit_stop|recovering' proto7-2/modules/subd/aos7-subd
```

## 11. 需要使用者決定的題

以下預設建議都只是供選擇，尚未當成決定或實作授權。

| 題目 | 選項與後果 | 預設建議 |
|---|---|---|
| **1. 第一版要保到什麼程度？** | 保存看見的狀態，能核心零改但會漏取樣；保存合作來源發布的每件事件，需要來源採交接協定；保存全部核心內部轉換，還要重新討論核心出口 | **合作來源的逐件業務事件，加上明示為取樣的核心觀測。** 不先承諾全系統每件事都有紀錄 |
| **2. 主要是給人／LLM 回看，還是有任務必須逐件處理？** | 回看可設定有限保存期；必讀事件需要消費確認，讀者長期不處理時會造成積壓 | **兩種用途分開宣告。** 一般觀測有界保留；必讀資料在責任完成前保留，不能用「LLM 看過」代替完成 |
| **3. 第一個落地單位是單 node，還是立即集中管理？** | A 容易獨立使用；B 方便跨 node 查詢，但要處理集中故障與來源積壓 | **先用單 node 驗證保存與讀者契約。** 若當下主要需求就是跨 node 查詢，則選 B，但把來源暫存一併算入 |
| **4. 空間滿了或存不進去，工作要不要等？** | 繼續工作可能永久漏事件；保住每件則可能阻止新工作被接受。有限容量、讀者可永久停住、來源不停、事件不漏，四者不能同時成立 | **必讀通道保留未確認資料，停止接受超出容量的新責任；一般觀測可繼續，但明報缺口。** 已發生的效果不能因拒收事件就當作沒發生 |
| **5. 保存成功後，要抵抗哪種中斷？** | 只處理程序被殺，契約較小；納入整台當機／斷電，要增加同步、輪替持久性與相應驗證 | **第一版明確承諾程序 SIGKILL 可接續。** 若事件要作為不可重做工作的唯一證據，再把主機中斷後仍可恢復列為必要條件 |