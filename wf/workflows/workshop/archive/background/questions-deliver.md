# 題目導讀：Deliver 公開契約
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### 題目：`aos deliver` 第一版要採哪一組 WORLD、輸入檔／stdin、單筆／批次與旗標介面？

**這題其實在問什麼**：這支命令怎麼指定要投給哪個 world，指令從檔案還是 pipe 進來，一次允許一筆還是一批，第一版是否就背 key/durable/廣義 target。
**為什麼會有這題**：Deliver 已是回頭審視後唯一保留的近期 core 缺口，但[工具協作場](../records/tool-interop.md) 四位給了四種 `--help`，後面的 skill/MCP 都必須同聲。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| 檔案為主 | 最小 parser/CLI，instruction array 邊界清楚 | pipe/tool-call 需先造臨時檔，WORLD 可能靠檔位置間接推 | agent 整合大部分來自 stdin，每次都多一步 |
| 資料夾＋可選檔案 | `FOLDER` 符合 `aos exec` 手感，單筆／批次皆收 | key/durable 先不進介面 | 立刻需要 correlation 或耐久旗標，又要擴 CLI |
| world＋廣義 target | 同一原語可投給其他 CPU 的 `X.json`/`X.tempd` | target 推導規則現在就變公開契約 | 其他 CPU 最後不遵守同一布局，廣化沒有第二使用者 |
| world＋stdin／檔案 | shell、skill、MCP 都容易接，一個 WORLD 帶一批 | 介面最完整，仍要拍板單筆、key、預設輸入 | 第一版同時收太多形狀，錯誤優先序與文件變複雜 |

**如果現在不決定會怎樣**：會直接擋住 Deliver CLI、skill 範例與 MCP schema；內部 deliver 函式可先以 bytes＋target 實作，但公開 CLI 不能無限拖。
**最小的驗證方式**：先用 PowerShell/bash 各寫三個真呼叫：人工檔案投遞、pipe 單筆、agent tool 傳批次；將四種 CLI 草案套上這三例，只計額外臨時檔、歧義與必填參數，不用寫 C++ 就能看出哪些表面真的會被用。

### 題目：沒有耐久 ledger 時，第一版 key 要拿掉、只作 correlation、只在 queue 內去重，還是連 ledger 一起做？

**這題其實在問什麼**：Deliver 收到同一號碼的重送時，是否承諾記得它以前來過；若承諾，記憶要保留到什麼時候。
**為什麼會有這題**：投遞檔在 aggregate 成功後會刪掉，所以以前提的 Already/Conflict 在下一回合沒有證據；這是[回頭審視](../records/step-back-review.md)發現的真契約漏洞。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| 第一版沒有 key | 契約最誠實、最小 | caller 無共同串接號碼，重送全自理 | agent/driver 很快就需要對齊 request 與 receipt |
| key 只作 correlation | 記錄可串起來，不做假冪等承諾 | caller 仍得自己防止重做 | 使用者看到 `--key` 自然誤以為它能去重 |
| queue 存活期去重 | 目前待辦檔還在時可擋重送 | 消費後不再記得，語意有時間邊界 | caller 在消費後重送，以為還受保護 |
| 耐久 ledger | 才能跨回合誠實回 Already/Conflict | 要定 scope、hash、保留期、GC、crash 與容量 | 實際從沒發生重送，卻先背了一本永久帳 |

**如果現在不決定會怎樣**：會擋住 Deliver 的 `--key`、receipt state 與錯誤碼；可以先實作不帶 key 的內部原子發布。
**最小的驗證方式**：在玩具 queue 連續做四次「同 key 同內容」：發布前重叫、發布後未 aggregate 重叫、aggregate 後重叫、重開 process 後重叫；把你直覺上希望每一步回什麼寫下來，就會直接看出是否願意為最後兩步付 ledger 的代價。

### 題目：Deliver 要採哪一組成功 JSON、錯誤 JSON、receipt 欄位與退出碼編號？

**這題其實在問什麼**：呼叫者怎麼機械地判斷投了幾筆、得到哪個憑據、哪個參數錯了，以及 shell 光看數字要如何分類錯誤。
**為什麼會有這題**：skill、MCP、shell 都要讀同一份 machine contract；[工具協作場](../records/tool-interop.md) 四位只對 `0=成功`、錯誤要能定位形成共同形狀，其他號碼互相衝突。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| receipt＋hash 版 | 有可對帳識別與內容 hash，key 衝突獨立分類 | 在 key/ledger 未定前先背了較重的成功契約 | hash/receipt 沒有後續查詢者，成為永久裝飾欄位 |
| delivery＋count 版 | 成功簡單，又能辨識這次投遞與數量 | 對 JSON/schema/key 錯誤分類較粗 | agent 需要針對欄位修正，卻只拿到大類 |
| 最小 JSON＋廣義 target | 公開欄位最少，target 可泛化 | 成功證據與 JSON/schema 錯誤判斷不細 | skill/MCP 得再解析文字或猜哪一層驗證失敗 |
| published＋receipt＋count | 成功資訊完整，錯誤種類最細 | 退出碼 2–6 與 receipt 形狀會立刻凍結 | 後來發現多數呼叫者只看 `ok/code/pointer`，其餘都是維護包袱 |

**如果現在不決定會怎樣**：會擋住 Deliver 公開 CLI 與任何 skill/MCP 範例；內部可先用 typed result 不對外凍結號碼。
**最小的驗證方式**：不實作 Deliver，先為五個現場手寫預期輸出：成功兩筆、JSON parse 錯、第二筆 `/argv/0` schema 錯、world 版本錯、I/O 錯；再寫十行 shell 與一個假 tool caller 各消費一次。一小時內哪些欄位實際被讀，就是首版的契約候選。

