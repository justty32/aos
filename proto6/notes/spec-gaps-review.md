# proto6 規格遺漏獨立審查

← [筆記](README.md)｜[規格](../spec/README.md)

**結論：本次確認的六項首版契約缺口已由主線補齊，最終回讀未留下這六項的阻擋問題。** 普通收發已接通；完整部署／CLI 可後補。以下保留審查場景與修法，不表示產品已驗證。

讀取時點：2026-09-28 22:18–22:29（Asia/Taipei）；草案在審查中同步修訂，最後重讀至 22:29。

範圍：四篇概念筆記、spec 全部 22 篇 Markdown，以及經 tabledb 核對的 methods.json。以事件交錯推演契約，完稿前重讀受影響條款。只寫本報告，未改產品、呼叫 API 或執行實際故障注入。

## 首版一致性：六項發現均已關閉

### G-01．final tick 可能等待自己完成

定位：[C-03/C-05](../spec/contracts.md)、[A-502/A-503](../spec/agent/tick.md)、[B-202](../spec/base/execution.md)、[B-603](../spec/base/lifecycle.md)、[S-102](../spec/scheduling/runs.md)。

觸發與後果：最後一個 tick 正提交 final，但 tick 自己也是帶 run_id 的在途 job。原 pending／完成屏障涵蓋全部工作，按字面會拒絕 final；另開 tick 消費前一 tick，又多出新的未完成 tick。提交後、程序退出前崩潰，也可能被通用 unknown 恢復規則誤轉 needs_attention。

最小補法與已採修正：語意 pending／消費集合只含 tool/llm，排除控制 tick；程序清空與 claim 釋放仍獨立落實。B-603 新增 tick 恢復分支：已有提交收據保留 checkpoint/final；沒有則先清舊範圍，再由舊 checkpoint 推進，不重做未知外部工作。

驗收：final 可由當前 tick 一次提交；提交前與提交後退出前各殺 tick，分別維持未提交／已提交事實，沒有自我消費鏈、雙寫或重複回答。

### G-02．後續訊息可能喚醒等待中的當前 run 空轉

定位：[A-202](../spec/agent/input.md)、[C-05](../spec/contracts.md)、[B-602](../spec/base/lifecycle.md)、[S-201](../spec/scheduling/admission.md)。

觸發與後果：R1 等工具，R2 訊息入 FIFO。原規則增加 pending_seq／ready，R1 卻不能消費 R2；若 served_seq 是語意消費進度，ready 永遠留著。直接清 ready 又缺乏 R1 結束時喚起 R2 的保證。

最小補法與已採修正：S-201 區分事件已投影與輸入已消費；ready 只代表當前可推進。後續訊息不喚醒等待中的 R1，R1 終局交易重新計算 FIFO。最終稿亦明定暫停隊首不能跳過，與 S-101 一致。

驗收：R1 長等時投 R2/R3，沒有重複空 tick；R1 完成後依序各啟動一次，交易間重啟仍不漏件、不越過暫停隊首。

### G-03．人工 fail 曾越過整輪收尾屏障

定位：[S-401](../spec/scheduling/operations.md)、[A-503](../spec/agent/tick.md)、[S-102](../spec/scheduling/runs.md)。

觸發與後果：J1 unknown、同 run 的 J2 仍有活程序，操作者對 J1 選 fail。原 S-401 直接 run→failed，可能讓下一輪開始，但 J2 還在改檔；與 failed 不得遺留未收回工作的條款相撞。

最小補法與已採修正：S-401 先記 pending_resolution、停新派工並取消該 run 其餘未終局工作；全部本機範圍清空後才 failed/canceled。決議接受未知副作用，但不把舊 unknown 偽造為確定失敗。

驗收：J1 unknown＋J2 活孫程序時 fail 不立即終局；清空後才結束，下一輪才可開始，原未知證據保留。

### G-04．滿 quota 後恢復完整結果的保證缺少儲存前提

定位：[A-303](../spec/agent/memory.md)、[B-304](../spec/base/identity-resources.md)、[B-401/B-404](../spec/base/storage.md)。

觸發與後果：輸出尚未耐久保存就耗盡 block/inode quota，再停機。所有大 blob 與 home 共用 quota，控制庫只留有界摘要；摘要不能重建未落盤結果。原「容量恢復後核對同一結果」缺少資料未保存時的出口。

最小補法與已採修正：不新增無限額儲存。A-303 已縮小承諾：未能保存 bytes 可丟棄，保留有界摘要及不完整標記；只有原已持久化的結果才承諾恢復。缺內容仍需處置，普通 resume 不能找回資料，也不得自動重做工具。

驗收：block/inode 各滿一次並重啟，能查 storage_blocked／截斷摘要；釋放空間不會讓未保存 bytes 憑空出現，已有結果不重複消費。

### G-05．run 剩餘預算原本只有引用，沒有累計帳

定位：[A-302](../spec/agent/memory.md)、[A-403](../spec/agent/tools.md)、[S-302/S-306](../spec/scheduling/llm.md)。

觸發與後果：模型持續回合法工具要求，每次建立新 job。單 job max_attempts=1 與 scope 窗口仍合規，卻可無限累計；A-302 要讀的 run 剩餘預算及 A-403 的限制無法實作。

最小補法與已採修正：S-306 補有限 jobs、LLM attempts、token 估額與經過時間，以及可信計帳、reserved/known/uncertain 歸屬；S-302 同交易檢查 scope 與 run 額度。耗盡進 needs_attention。首版沒有原 run 續額 API，收尾後另建 run；數字仍是未拍板預設，不是使用者要求。

驗收：mock 永遠回合法呼叫，達 run 門檻後停止新派工；重啟不重置消耗，unknown 不當零消耗。此處不宣稱精準貨幣硬預算。

### G-06．unknown 補證據與同 ID 異內容拒絕曾相撞

定位：[C-03](../spec/contracts.md)、[S-104](../spec/scheduling/runs.md)、[S-302](../spec/scheduling/llm.md)。

觸發與後果：attempt 已記 unknown，稍後可信成功結果到達。S-104 允許補全，原 C-03 卻要求同 ID 不同 Outcome 一律 conflict；導入器可能永久拒收唯一真實結果。

最小補法與已採修正：C-03 明定 unknown 是可由可信證據單調補全的暫定判斷，保留舊事件；確定終局異內容才拒絕。舊 attempt 可補自身證據與實際 usage，但不覆蓋人工已選的新 attempt。

驗收：unknown 補真實成功，再重送兩次，僅補全及結算一次；已有重試時舊結果不蓋新結果，第二份相矛盾的確定結果仍拒絕。

## 可後補的操作契約

### G-07．普通收發已接通，完整人端操作仍待定

定位：[B-505](../spec/base/transport.md)、[RPC 操作](../spec/base/methods.json)、[A-101](../spec/agent/configuration.md)、[B-604](../spec/base/lifecycle.md)。

原場景：人只有文字，RPC 卻要求 input_ref；取得 final_ref 後也缺讀出入口。這會迫使實作者自行發明 BlobRef 導入／導出，甚至直接操作內部資料。

已採修正：B-505 補認證 import_blob/export_blob adapter，methods.json 補 run.outputs。普通流程已有「文字 JSON→導入→submit→查正式輸出→讀取內容」契約，這部分已關閉。

仍可後補：CLI argv、部署初始化、登記／更新設定、停用後啟用與管理者恢復的具體操作。部署 backend 選定後，試玩前需串一條公開介面流程；不要求現在選宿主 root，也不要求另造排程產品。

驗收：只靠公開介面與假 LLM，從建立 agent 到取 final，再演示受阻原因可查、修復／恢復可操作，不直接改 SQLite。

## 已有保證，不另算遺漏

- 身分／cgroup／quota 分工、工具共享資源、全局准入及 profile 不合格拒絕啟動已有明示；不把尚未選外牆當缺陷。
- 後代清理、PID 不能單獨認定身分、lease 先對帳、generation fencing、取消與成功競態已有條款。
- 檔案耐久發布、checkpoint/cursor/job 意圖單交易、重送去重及三種 ack 已有規定；不把檔案與 DB 不是單一交易本身再報一次。
- unknown 禁止自動重試、遠端取消限制、429 有界退避、共享 scope 已規定。
- FUSE、分散式、父子 demo、逐字串流不是本次首版閉合要求。人工介入便利性屬產品選項。

尚未完成的是運行時故障注入、真 UID／quota／外牆強制驗證、萬級效能，以及上述完整人端操作。本輪完成文件契約審查與修訂回讀，不宣稱這些實作驗收已通過。
