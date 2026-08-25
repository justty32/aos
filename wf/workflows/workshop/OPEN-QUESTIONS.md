# 尚未回答的問題
← [workshop](README.md)

計數方式：〈核心行程與子行程〉的四位參與者，與其後六場沿用的四位參與者是兩批不同的人；同一人跨場重問只算一位。以下只保留使用者既有表態後仍未解的部分。

## 擋住事情的

### 1. workflows 到底是哪一種不好用？

**問題｜**最近一次覺得 workflows 不好用時，主要卡在安裝升級、路由／遵守流程、活狀態維護，還是定時喚醒？  
**為什麼卡著｜**第一個 workflows 功能、磁碟真源與是否需要 runtime 都取決於真正痛點；紀錄中的痛點目前全是推論。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地問了。  
**候選答案｜**

- **安裝／升級**——先做來源版本、base hash、三方 diff 或 doctor，不先做 task runtime。
- **路由／遵守流程**——先改善 workflow 的找到、派發與 agent 遵守方式，不先建活狀態資料庫。
- **活狀態維護**——先做 `start／wait／resume／done／status`，取代手動搬 SESSION-LOG 與 WAIT_USER。
- **tick／schedule**——先把到期判斷、Deliver 與 cursor 更新機械化。

### 2. 近期 core 要回撤到哪裡？

**問題｜**近期 scope 要只留最小 Deliver，保留 Publish→Deliver→Effect 三項，還是繼續連行程控制平面一起設計？  
**為什麼卡著｜**三場早期紀錄與回頭審視給了互斥的近期 roadmap；不先拍板，後面的公開 API、Effect、join、lane 等題目都無法排程。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；4 位獨立地問了。  
**候選答案｜**

- **只做最小 Deliver**——Publish 留內部、Effect 留 adapter／人工，其餘等實測觸發再重開。
- **先做三項 core 原語**——依序公開 Publish、Deliver、Effect＋resolve，再跑 agent loop。
- **保留完整控制平面**——連 lane／proc-table／capability／promotion／join 一起形成耐久行程機制。

### 3. 第一個產品體驗是哪一邊？

**問題｜**第一個做好的體驗，是人在 coding agent 裡呼叫 aos，還是 aos 無人值守地批次召喚 coding agent？  
**為什麼卡著｜**兩者雖共用 CLI，卻需要不同的 session、批准、結果捕捉與 unknown 責任。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；2 位獨立地問了。  
**候選答案｜**

- **coding agent 互動入口**——先讓人透過 skill／MCP 呼叫 Status、Deliver，視權限再 Exec。
- **aos 批次召喚 agent**——先做 request、啟動 CLI、原子捕捉結果、exit／unknown 與完成 commit。

### 4. 模型與工具先給到什麼權限？

**問題｜**首版是全信任實驗、只准 Deliver 等人 Exec，還是在 container／sandbox 內允許自動 Exec？  
**為什麼卡著｜**模型輸出若能直通任意 argv，就能碰檔案、網路與憑證；root 的唯一權力若只靠守約，也不是安全邊界。  
**在哪問過｜**〈核心行程與子行程〉、〈四個懸而未決的設計選擇〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；兩批共 8 位獨立地問了。  
**候選答案｜**

- **全信任＋具名工具映射**——先跑玩具 golden slice；未知工具停住，但不承諾隔離真實資源。
- **只 Deliver、人工 Exec**——agent 只能排隊，由人核准後推世界一回合。
- **container 內自動 Exec**——上層 coding agent／OS sandbox 負責隔離，aos 不新增批准彈窗。

### 5. 第一個整合入口先驗哪個？

**問題｜**第一個宿主先做 pi 的 skill＋CLI，還是先做其他 coding agent 的 MCP façade？  
**為什麼卡著｜**pi 明確不走 MCP；兩條路要驗證的宿主、session 與 tool protocol 不同。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；1 位獨立地問了。  
**候選答案｜**

- **pi skill＋CLI**——建立 `.agents/skills/aos/SKILL.md`，由 pi 的 bash tool 呼叫同一套 aos CLI。
- **其他 agent 的 MCP**——先做無狀態薄殼，第一版暴露 Status＋Deliver，Exec 明示 opt-in。

### 6. golden slice 先用哪支真 agent CLI？

**問題｜**模型→具名工具→模型的第一條可執行 golden slice，要先鎖定 pi、Codex，還是 Claude 的 CLI？  
**為什麼卡著｜**stdout／JSONL、tool-call、session、取消、截斷與 exit 的實際形狀尚未測過，adapter 與 crash 記錄不能先定。  
**在哪問過｜**〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；3 位獨立地追問第一支 CLI。  
**候選答案｜**

- **pi**——先驗 skill＋CLI、`--no-session`、JSONL／RPC 與實際 session 旗標。
- **Codex**——先驗現有 CLI 的 tool-call、結果捕捉、session id 與 hard-kill 現場。
- **Claude**——先驗另一個 coding agent CLI 的 request／result 與 session 快取介面。

### 7. `aos deliver` 第一版命令長什麼樣？

**問題｜**`aos deliver` 第一版要採哪一組 WORLD、輸入檔／stdin、單筆／批次與旗標介面？  
**為什麼卡著｜**Deliver 是回頭審視後唯一仍保留的近期 core 缺口；參數不定就無法寫 CLI、skill 或 MCP schema。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地問了。  
**候選答案｜**

- **檔案為主**——`aos deliver [--key K] [--durable] <inst-file>`，只明收 instruction array。
- **資料夾＋可選檔案**——`aos deliver [--file FILE] [FOLDER]`，收單筆 object 或 array，FOLDER 預設 `.`。
- **world＋廣義 target**——`aos deliver [W] [--to X.json]`，由 `X.json` 推出 `X.tempd/`。
- **world＋stdin／檔案**——`aos deliver [WORLD] [-f FILE|-] [--key K]`，收單筆或 array。

### 8. Deliver 的 key 到底保證什麼？

**問題｜**沒有耐久 ledger 時，第一版 key 要拿掉、只作 correlation、只在 queue 內去重，還是連 ledger 一起做？  
**為什麼卡著｜**aggregate 會刪投遞檔；若仍宣稱跨回合 Already／Conflict，現有磁碟上沒有可查的舊事實。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地問了。  
**候選答案｜**

- **第一版沒有 key**——只承諾驗證與原子發布，caller 自己避免重送。
- **key 只作 correlation**——寫進檔名／receipt 方便串接，但不回 Already／Conflict。
- **只在 queue 存活期去重**——舊投遞檔還在時判 Already／Conflict，彙整刪除後不再承諾。
- **增加耐久 ledger**——跨回合保存 key、內容 hash 與結果，才承諾 Already／Conflict。

### 9. Deliver 的成功、錯誤與退出碼採哪套？

**問題｜**Deliver 要採哪一組成功 JSON、錯誤 JSON、receipt 欄位與退出碼編號？  
**為什麼卡著｜**skill、MCP、腳本必須讀同一份機器契約；目前只有 `0＝成功` 與錯誤要可定位形成共同形狀。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地各給一套。  
**候選答案｜**

- **receipt＋hash 版**——成功含 `receipt/state/hash`；2 用法、3 格式／大小、4 key 衝突、5 I/O。
- **delivery＋count 版**——成功含 `delivery/count`；2 payload、3 world／版本、4 I/O。
- **最小 JSON＋廣義 target 版**——成功欄位先從簡；2 用法、4 驗證、5 I/O。
- **published＋receipt＋count 版**——2 用法、3 JSON、4 schema、5 key 衝突、6 I/O。

### 10. workflows 活狀態的真源放哪裡？

**問題｜**open 狀態要隨 Git 跨機，放在 `wf/open/*.md`，還是只作本機狀態，放在 `.aos/wf/*.json`？  
**為什麼卡著｜**這會直接決定唯一真源、status 是否只是 generated view，以及 SESSION-LOG／WAIT_USER 能否由別台機器接手。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地都把它列為最沒把握的一題。  
**候選答案｜**

- **`.aos/wf/*.json` 本機真源**——原子 move 與 generated status 容易；不承諾自然隨 Git 跨機。
- **`wf/open/*.md` Git 真源**——front matter 保存 owner／resume，可跨機與人讀；`.aos` 只負責本次執行。

### 11. 人怎麼修改 workflows 活狀態？

**問題｜**人要直接改 JSON、直接改 markdown front matter，還是只能用 `aos wf` 命令修改？  
**為什麼卡著｜**若資料檔與 generated view 都能手改，就會重新形成雙真相；修復與 reconcile 規則也取決於入口。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位分別提出了三種形狀。  
**候選答案｜**

- **直接改 JSON**——人可修 `ready/<id>.json`，下一次 tick 採用。
- **直接改 markdown**——`wf/open/*.md` 本身是真源，Git diff 就是狀態變更。
- **只用 `aos wf` 命令**——markdown 只由 `status --format md` 產生，不接受反向手改。

### 12. 遠端效果變成 unknown 時預設怎麼辦？

**問題｜**LLM／有副作用工具可能已執行但本機沒記下時，要停住、只在 provider 可對帳時自動恢復，還是直接自動重試？  
**為什麼卡著｜**這決定是否可能重複付費、寄信或部署，也決定近期是否需要 Effect／resolve。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地問了。  
**候選答案｜**

- **unknown 一律停住**——交給人 retry、lost／abandon 或 adopt／import。
- **可對帳才自動恢復**——只有 provider 支援同 key 冪等或 request ID 查詢時才重送／取回。
- **unknown 自動重試**——loop 自動再呼叫，但接受重複付費與副作用的風險。

### 13. crash 要承諾到哪一級？

**問題｜**首版只保優雅 Ctrl-C，還要涵蓋 hard kill，或連斷電都列入恢復契約？  
**為什麼卡著｜**supervisor、`.runi`、temp 清理、fsync 與測試矩陣都取決於故障邊界。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；3 位獨立地分別追問 Ctrl-C、hard kill、斷電。  
**候選答案｜**

- **只承諾 Ctrl-C**——wrapper 有機會主動記狀態；hard kill 與斷電只觀察、不保自動恢復。
- **承諾 Ctrl-C＋hard kill**——逐點 kill，要求本機檔案能辨認未完成，但遠端仍可停在 unknown。
- **連斷電都承諾**——把檔案與目錄 fsync、power-loss durability 一起納入契約與測試。

### 14. `--durable` 與 fsync 承諾什麼？

**問題｜**Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？  
**為什麼卡著｜**這會改變跨平台契約、錯誤種類與每次投遞成本，也決定目錄 fsync 是保證還是盡力。  
**在哪問過｜**〈核心行程與子行程〉、〈agent loop 的實作架構〉、〈aos 與 coding agent、skills、MCP 的協作〉；兩批共 4 位獨立地問了。  
**候選答案｜**

- **只保 rename 可見性**——不宣稱 power-loss durability，第一版不收 `--durable`。
- **可選 `--durable`**——一般模式只 rename；旗標模式另做檔案與目錄 fsync，規格明列平台保證。

### 15. SESSION-LOG／WAIT_USER 要不要保留完成史？

**問題｜**現在留下的完成事項是刻意的歷史，還是應恢復 open-only？  
**為什麼卡著｜**若完成史是需求，`done` 不能只刪除；若不是，現況就是要被 runtime 修掉的 drift。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地問了。  
**候選答案｜**

- **嚴格 open-only**——完成即從 SESSION-LOG／WAIT_USER 移除，不保留已解項。
- **原檔保留完成史**——`done` 改成標記完成，不刪除原項。
- **open-only＋另存 archive**——活 view 只列 open，完成項移到獨立歷史／done 區。

### 16. template 安裝後還追不追上游？

**問題｜**既有專案要持續吸收 template 更新、只做診斷，還是安裝後永久分叉？  
**為什麼卡著｜**是否需要 source version／base hash、三方 diff、doctor 與 upgrade 命令，全取決於這個答案。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位獨立地問了。  
**候選答案｜**

- **安裝後永久分叉**——不做 upgrade；上游版本最多只作追溯。
- **來源鎖＋人工三方合併**——保存 base hash，upgrade 只產舊基底／新基底／本地差異。
- **自動換未修改檔**——未改檔自動升級，客製檔只顯示 diff，不覆蓋。
- **只做 doctor**——先掃 placeholder、壞連結與孤兒路由，不替人合併政策。

### 17. 哪些 workflow 需要自動喚醒？

**問題｜**schedule／tick 是普遍 runtime 能力、少數專案特例，還是暫時維持人工喚醒？  
**為什麼卡著｜**若是普遍能力，task 狀態要收 `next_at`、Deliver 與 cursor；若不是，先做 scheduler 會放錯 scope。  
**在哪問過｜**〈用 aos 實現 workflows〉；3 位獨立地問了。  
**候選答案｜**

- **人工喚醒**——不做 runtime scheduler，沿用現在的 tick／cron 外部觸發。
- **只收 `next_at`**——人或 cron 到點呼叫，成功 Deliver 後才更新時間／cursor。
- **納入 `aos wf` runtime**——ready、schedule 與 wake 都由 task 狀態機管理。

### 18. stdout→stdin 的穩定 context 從哪裡來？

**問題｜**coding agent 的 stdin 要吃 request file、`status --json`，還是新的 `aos prompt／emit`？  
**為什麼卡著｜**四位已排除 raw `aos exec` stdout；去程沒有 envelope，就無法與回程 Deliver 組成可靠閉環。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；4 位共同留下這個缺口。  
**候選答案｜**

- **request file**——driver 直接把 world 裡已提交的 request／context 檔餵給 agent stdin。
- **`status --json`**——由現有查詢工具輸出穩定 machine context，不新增 prompt 命令。
- **專用 `prompt／emit`**——新增只輸出帶 turn／source envelope 的 context exporter。

### 19. agent session 要先求可攜還是續談速度？

**問題｜**第一版預設 `--no-session` 從 world 重建，還是優先使用 agent session 作續談快取？  
**為什麼卡著｜**session 定址、JSONL final event 與 RPC 的跨版本承諾尚未核對；若先依賴它，skill 與 adapter 會被宿主格式綁住。  
**在哪問過｜**〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地都碰到。  
**候選答案｜**

- **`--no-session` 可攜預設**——world 保存完整 request／history，session 遺失不影響重建。
- **session 快取優先**——先核對並固定實際旗標與 event 格式，把綁定記在 world，但仍不當真源。
- **RPC／JSONL adapter 優先**——先驗跨版本介面，再由 adapter 捕捉 final／exit；不用未核對的 `--session-dir`。

### 20. 子工作成果何時進父世界？

**問題｜**lane／子工作可直接改世界、完成即共享，還是只能交 proposal／delta 由 root 原子 commit？  
**為什麼卡著｜**這決定隔離、因果順序、父 crash 後 receipt 歸屬，以及單一 root 的權力如何落到提交邊界。  
**在哪問過｜**〈核心行程與子行程〉、〈四個懸而未決的設計選擇〉；兩批共 5 位獨立地問到結果可見性或 commit。  
**候選答案｜**

- **子工作直接寫／立即共享**——完成就改世界；父不用另做 commit，但隔離與回滾較少。
- **完成後一次 commit**——子工作先隔離，只有 completion commit 後父世界才看見。
- **proposal／delta 交 root**——lane 只算結果，barrier 後由唯一 root 發布到父世界。

### 21. 父要怎麼等子工作？

**問題｜**父等待子工作要採同步阻塞、持久 join handle，還是接完成事件／receipt？  
**為什麼卡著｜**這決定父回合是否能結束、crash 後如何續等，以及子結果要投到哪裡。  
**在哪問過｜**〈核心行程與子行程〉；1 位直接問了，另有兩位從結果 commit 延伸到同一邊界。  
**候選答案｜**

- **同步阻塞**——父回合等子工作全部完成才往下走。
- **持久 join**——父留下 handle，之後回合再檢查／收割。
- **完成事件／receipt**——子完成後投事件，父不持續阻塞。

### 22. 子工作失敗時父怎麼走？

**問題｜**子工作失敗後，父要停住、隔離該子工作、重試，還是照常提交下一回合？  
**為什麼卡著｜**沒有失敗政策，lane 生命週期、receipt 與人工恢復都無法定義。  
**在哪問過｜**〈核心行程與子行程〉；1 位直接列出四個選項。  
**候選答案｜**

- **父停住**——保留現場，等人處理後才有下一回合。
- **隔離子工作**——父可處理其他工作，失敗 lane 保持 failed 等收割。
- **自動重試**——依既定上限重新推進同一工作。
- **照常提交**——把失敗當一筆結果，父回合繼續。

### 23. kernel 序言／尾聲失敗怎麼算一回合？

**問題｜**序言或尾聲失敗時，業務批次要不要跑，並且要不要保留 `.runi` 把整回合視為未完成？  
**為什麼卡著｜**`kernel.json` 已收，但失敗原子邊界尚未拍板；它會改 executor 的控制流與恢復語意。  
**在哪問過｜**〈核心行程與子行程〉；3 位獨立地問了。  
**候選答案｜**

- **核心失敗就不跑業務**——序言／尾聲是硬門檻，失敗立即停住。
- **業務可跑，尾聲失敗算回合未完成**——保留 `.runi`，等修復後處理尾聲／整批。
- **業務與下一回合照常**——另記核心錯誤，不讓尾聲失敗阻斷 queue。

### 24. coding agent 的首版 runtime tool set 有幾支？

**問題｜**首版只公開 Deliver，公開 Deliver＋Status＋Exec，還是再把 Init 放進同一組？  
**為什麼卡著｜**skill／MCP 的 schema、權限面與實作範圍取決於首版工具集合。  
**在哪問過｜**〈三場研討會的回頭審視〉、〈aos 與 coding agent、skills、MCP 的協作〉；4 位獨立地整理過。  
**候選答案｜**

- **只有 Deliver**——近期只補現存投遞缺口，Status／Exec 沿用既有人工 CLI。
- **Deliver＋Status＋Exec**——四位共同的最小 runtime 三支；Status 可讀、Exec 另授權。
- **再加 Init**——把 world 建立也放入 agent tool set，不另列建置期。

## 可以慢慢想的

### 25. Publish 要不要成為公開 API？

**問題｜**Publish 只當 Deliver／Effect 的私有 helper，還是公開給檔案、目錄、cursor 與 event 共用？  
**為什麼卡著｜**只有在近期 scope 不回撤時才會擋 API；公開後要背 temp/source 或 payload、目錄交易與 durability 的相容承諾。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；4 位獨立地先提出、後又收回近期公開。  
**候選答案｜**

- **只作私有 helper**——Deliver 內部共用 temp＋rename，不形成公開 ABI。
- **公開 source/temp 版**——`publish TARGET TEMP`／`publish_at(..., source)` 發布已寫好的檔或目錄。
- **公開 payload 版**——API 直接收內容，由 Publish 自己建立 temp、write-all 與 rename。

### 26. Effect 放 core 還是 adapter？

**問題｜**外呼日誌與 unknown／resolve 要留在 provider adapter，還是成為通用 core Effect？  
**為什麼卡著｜**若近期只做 Deliver 可延後；若要自動 agent loop，就要先定通用狀態與 provider-specific 對帳的切線。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；4 位獨立地先提出通用 Effect，後又撤回近期前置。  
**候選答案｜**

- **全留 adapter／人工**——wrapper 記簡單 attempt，unknown 交人處理，不新增 core ABI。
- **core 只記通用效果狀態**——request／pending／done／unknown 由 core 保存，查 provider 仍由 adapter。
- **core Effect＋resolve**——公開 run 與 retry／lost／abandon／adopt／import 動作，包所有有副作用命令。

### 27. 平行 join／reconcile 放哪裡？

**問題｜**平行工具收齊與 crash 後 event／cursor／receipt／next-delivery 對帳，要留腳本還是升成 core？  
**為什麼卡著｜**串行首版不擋；一旦平行，沒有 barrier 可能提早進下一回合，但升 core 又可能把 agent turn 語意帶進去。  
**在哪問過｜**〈agent loop 的實作架構〉、〈三場研討會的回頭審視〉；3 位獨立地問到 join 或 reconcile。  
**候選答案｜**

- **先只跑串行**——沒有平行 join，等實測瓶頸再重開。
- **driver 腳本掃結果**——腳本確認全 done／unknown，再投下一回合。
- **core `effect_join(keys)`**——只理解 effect 狀態，不理解 turn／final。
- **core reconcile／barrier**——一起對齊 event、cursor、receipt 與補投。

### 28. `.runi` 要保存哪一版 kernel 現場？

**問題｜**`.runi` 只存 hash 驗出不同，還是必須能取回當時真正執行的有效 kernel？  
**為什麼卡著｜**若要重播／事故重建，hash 本身沒有內容；若只要偵測版本漂移，保存全文會增加清理與容量。  
**在哪問過｜**〈四個懸而未決的設計選擇〉；4 位獨立地問了。  
**候選答案｜**

- **只存 hash**——只驗出現在內容不同，不承諾重建舊現場。
- **內容隨 `.runi` 保存**——未完成回合直接帶當時有效 kernel。
- **hash 指不可變物件**——內容放版本物件庫，`.runi` 只保存可取回的指標。
- **每 world 常駐物化有效檔**——執行只讀本地完整內容，`.runi` 指認該版本。

### 29. 每份本地 kernel 由誰建立與升級？

**問題｜**每個 world 都有完整本地 kernel 後，要由人／腳本逐份改、core 套模板、記 `kernel.source.json`，還是由父建立時物化？  
**為什麼卡著｜**動態分層已被收窄，但多份本地 kernel 仍會漂移；升級失敗的現場與來源也尚未定。  
**在哪問過｜**〈核心行程與子行程〉、〈四個懸而未決的設計選擇〉；兩批共 5 位獨立地問到修改權或升級來源。  
**候選答案｜**

- **人／腳本逐份更新**——kernel 完全自足，不另存規格化來源。
- **core 套模板更新**——建立與升級都由 core 把模板寫成完整本地檔。
- **`kernel.source.json`＋物化**——保存來源資訊，但執行只讀完整本地 kernel。
- **父先寫完整檔再呼叫**——父在建立／升級子 world 時明寫內容，exec 不做繼承。

### 30. 非 UUID 的 handle 用什麼？

**問題｜**既然不綁 UUID，world／子工作 handle 要直接用相對路徑，還是用父域內的 name＋generation？  
**為什麼卡著｜**兩者都符合非 UUID，但同名刪除重建後，舊 receipt／join 是否會誤投的結果不同。  
**在哪問過｜**〈四個懸而未決的設計選擇〉；4 位獨立地提出非 UUID 後的兩種殘留方案。  
**候選答案｜**

- **正規相對路徑**——rename 就是改址、copy 是新 world；metadata 最少。
- **父域 name＋generation**——同名新目錄不收上一代結果；跨父域要 detach／adopt。

### 31. 「一個 exec 推多世界」具體是哪種？

**問題｜**未來真的推多世界時，要同一 OS 行程內 multiplex、一個命令接多個 world，還是由命令樹逐個呼叫單世界 exec？  
**為什麼卡著｜**使用者已表態傾向一個 exec 推多世界，但這三種對 root fd、cwd、退出碼與故障隔離的要求不同；回頭審視建議先等第二個 world。  
**在哪問過｜**〈四個懸而未決的設計選擇〉；4 位各給了不同實作。  
**候選答案｜**

- **同一 OS 行程 multiplex**——抽 `advance_once(World&)`，所有內部 I/O 改 root fd／`*at`。
- **一個命令接多個 world**——`aos exec w1 w2` 逐 root fd 推進，另定 busy／失敗與總退出碼。
- **命令樹逐個單世界 exec**——父批次呼叫多個 `aos exec <path>`，保留現有 cwd 模型。

### 32. 要不要把分支世界做成正式方向？

**問題｜**四位都挑中的「複製世界、試跑未來、提交一條」要先做 boundary fork、回合 branch、speculate，還是 arena？  
**為什麼卡著｜**它不擋近期 Deliver，但若轉成 roadmap，要先定可複製狀態、`.runi` 邊界與勝者如何成為 current。  
**在哪問過｜**〈隨意發想〉；4 位獨立地提出並各自選中同一家族。  
**候選答案｜**

- **`aos fork --at-boundary`**——有 `.runi` 就拒絕，複製 world／kernel、清空在途狀態。
- **`aos branch world@turn`**——保存真實回合快照，再從指定現場分兩條未來。
- **`aos speculate -n N`**——reflink 多份候選 world，評分後原子切換 current。
- **arena＋winner**——各 agent 在具名子目錄跑固定回合，由 judge 把勝者 rename 成 winner。

### 33. 外部處理器完成後要交什麼？

**問題｜**外部處理器完成一件工作後，是只 ack、寫 receipt，還是直接 Deliver 給下一顆 CPU？  
**為什麼卡著｜**這決定外部處理器只是 caller 的同步延伸，還是可串成 pipeline，也會影響共同 completion commit。  
**在哪問過｜**〈核心行程與子行程〉；1 位直接問了。  
**候選答案｜**

- **只 ack**——完成狀態回給原 caller，下一步由 caller 決定。
- **寫 receipt／result**——原子留下可查的結果與 correlation，之後由 driver 收割。
- **Deliver 下一顆 CPU**——外部處理器完成後直接投遞下一段 pipeline。

### 34. 怎麼證明外部處理器讀對 ABI？

**問題｜**不引用 aos lib 的外部處理器，要靠 golden files＋conformance CLI，還是統一透過同一 CLI／parser 驗證？  
**為什麼卡著｜**沒有一致性檢查，「不引用 lib 也接得上」只是一項宣稱；磁碟 ABI 改版時尤其無法判斷相容性。  
**在哪問過｜**〈核心行程與子行程〉、〈四個懸而未決的設計選擇〉、〈aos 與 coding agent、skills、MCP 的協作〉；兩批共 2 位直接問 conformance，後一場 4 位要求單一 parser 語意。  
**候選答案｜**

- **golden files＋conformance CLI**——外部實作用固定案例證明 parse、publish、receipt 與錯誤一致。
- **全部呼叫 aos CLI**——外部處理器不連 lib，但投遞與驗證統一經 Deliver。
- **共用 lib／parser**——CLI、MCP 與整合程式共用實作，不允許另寫一套契約。

### 35. task 何時升成 world／lane？

**問題｜**短 task 要在首次 yield、首次需要獨立恢復，還是需要獨立等待／收件／queue 時升格？  
**為什麼卡著｜**job／lane 已拆開，但升格門檻會決定何時建立 kernel、queue、cursor 與生命週期；回頭審視建議先不自動升格。  
**在哪問過｜**〈核心行程與子行程〉、〈用 aos 實現 workflows〉；兩批共 5 位問到或提出門檻。  
**候選答案｜**

- **首次 yield**——一跨回合就原子升成 lane。
- **首次需要獨立恢復**——只有必須單獨重啟／重試時升格。
- **需要獨立等待／反覆收件／自己的 queue**——時間長本身不算，具備獨立執行需求才升格。

### 36. inbox 要機械化到哪裡？

**問題｜**inbox 要維持手工信件、只加明示 `wf accept`，還是連命名與歸檔生命週期都交給 aos？  
**為什麼卡著｜**信件原本可以不回；若直接變 instruction，就會把知會誤升成必須 claim 的工作。  
**在哪問過｜**〈用 aos 實現 workflows〉；2 位直接問到目前痛點，4 位都要求信與 queue 分開。  
**候選答案｜**

- **維持手工 inbox**——寄、讀、忽略、歸檔都不進 aos runtime。
- **只加 `wf accept MAIL`**——信仍可忽略，只有明示接受才轉 open task／Deliver。
- **管理完整信件生命週期**——aos 配唯一名稱、標未讀／已收／done，但接受前仍不進 instruction queue。

### 37. workflows module 管到哪一層？

**問題｜**non-invasive module 只負責安裝、負責安裝＋升級，還是連 task runtime 一起提供？  
**為什麼卡著｜**`install／init／module add` 三種名字背後的責任尚未對齊；若混在一起，模板來源與活狀態會綁成同一套生命週期。  
**在哪問過｜**〈用 aos 實現 workflows〉；4 位提出不同命令形狀並留下責任問題。  
**候選答案｜**

- **只管安裝**——建立 `wf/` 非侵入式骨架，安裝後專案自行分叉。
- **安裝＋升級**——另記 source version／base hash，提供三方 diff，不碰 runtime。
- **安裝＋升級＋runtime**——同一 module 也提供 `wf start／wait／resume／done／status`。
