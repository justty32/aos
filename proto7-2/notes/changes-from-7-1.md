# proto7-1 → proto7-2 對照

← [proto7-2](../README.md)｜[spec 草稿](../spec.md)｜使用者建議：[user-advice](../../proto7/user-advice.md)

每一列是一個改動：proto7-1 怎麼做 → proto7-2 怎麼做 → 為什麼。N-／K- 編號指 [proto7-1 需求清單](../../proto7-1/notes/infra-needs.md) 與 [生命週期決定](../../proto7-1/notes/decisions/2026-10-03-lifecycle-invariants.md)。最後一節是**要你決定的 W 清單**。

## 五個主要改動，加 10-04 追加的一條

| # | proto7-1 | proto7-2 | 為什麼 |
|---|---|---|---|
| 1 node 登記 | daemon 每 20 ms 從空間根往下走，含 `.aos/timeline.json` 的資料夾就是 node。為此長出：子根排除、宣告子根也排除（F-08）、`scan-error`／`scan-ok`（F-03）、一圈最多起 20 條、`rescan` op | 控制檔加 `register`／`unregister`，清單存 `.aosd/nodes.json`，daemon 重開照它跑。daemon 只看清單上的 node。掃描帶來的規則全拿掉；`rescan` 拿掉；timeline.json 變成可有可無 | user-advice「daemon 不該去掃資料夾找 node，而是要一開始就登記」「走 ctl 這條路也可以中途登記」 |
| 1a node 消失（Q4） | 掃描沒看到＝消失，kill 上面的任務；新位置被掃到就自動是新 node | 只檢查**已登記**的 node：確定不存在或換了 inode → kill 任務、`phase: missing`、登記保留，資料夾回來就接著跑。看不到（EIO…）＝不知道、不動。新位置要另外 register（W1） | Q4 選 (a) 的保護沿用；沒有掃描就沒有自動發現 |
| 2 提前 tock 可選 | 本回合任務都結束就提前 tock，不能關 | timeline.json `early_tock`，**預設 false＝固定 interval**；true 才提前 | user-advice「這應該要是可選，有些人就是想要固定的 interval」 |
| 3 只留 tasks.json | 任務表 tasks.json，另有 `spawn/*.json`（一次性、batch、restart 都靠它），起完才刪，被殺會整批重起（N-86） | 一次性任務是 tasks.json 一項 `mode: "once"`，起完 tick 把它刪掉；restart 改成加一項 once（帶 `slot`）。tick 改表一律拿 flock。防重起：寫 birth.json 之前先在那項記 `launch`（槽＋run），下一個 tick 照 birth.json 是不是同一個 run 判斷「已起／確定沒起／不知道」。batch＝一次 `edit_json` 加多項 | user-advice「盡量統一一個檔案就好」；N-86（gang 探針：tick 起到第 8 個被殺，7/20 個變兩份） |
| 4 任務資料夾重用 | 每次起都開新資料夾 `.aos/tasks/<name>-r<回合>/`，結束 20 回合後搬到 `tasks-old/`，可選再刪 | 資料夾＝槽 `.aos/tasks/<name>/`，同名重用、換 run 時清掉上一個 run 的基礎設施檔。`each` 上一次還在跑就跳過；要並行用 `max_live` 開槽 `<name>.1`、`<name>.2`…。tid＝槽名，另加 `run`（＝起它的回合數，保證遞增）與 run id `<槽>#<run>`。`tasks-old` 拿掉 | user-advice「每個回合都會產生新的類似資料夾，我的老天，這不太好吧」 |
| 4a kill／restart／lost | 對著 `<tid>` 資料夾；身分掃描比 NODE＋TID | ctl.json 可帶 `run` 指定哪一次（換人了就不執行）；身分掃描比 NODE＋TID＋**RUN**，上一個 run 的殘留不會被當成這次 | 資料夾重用後，同一個 tid 會有好幾代程序 |
| 4b agent／kernel 接前任 | 新任務資料夾找不到 state 時，去找 `restart_of` 或同名回合最新的那份（兩處都找，讀到一半被搬走要重讀，F-02） | state.json、kernel-state.json 就在同一個槽裡，下一個 run 直接讀（W6） | 重用資料夾後這整套找前任的機制不需要了 |
| 5→追加 核心只留上一次 | 什麼都留：rounds.jsonl 每回合一行、log.jsonl、ctl-done／ctl-failed 每件一份、每個任務一個資料夾；Q3 預設只搬不刪，H-08 加了可選的 `keep_old_rounds`、`retention.json` | **使用者 10-04 追加，優先於原本的第 5 點**：核心只留「上一次」。`rounds.jsonl` → 覆寫的 `last-round.json`；每個槽只留最近一次 run 的結果；daemon 回條每個名字只留最近一份（建議固定檔名，W3）；核心沒有 log.jsonl（status 的 `last_event` 只留最近一件）。**不留就不用清**：`keep_ended_rounds`、`keep_old_rounds`、`retention.json`、status 的 `disk` 全拿掉。要歷史用可選的歷史 module（spec 第 9 節）：一個普通 keep 任務，每個 tock 讀「上一次」追加到自己的地方；daemon 事件流水帳另有 `.aosd/log.on` 開關（W9） | user-advice「正常運行的狀況下這些就是垃圾」；使用者 10-04 追加「留下歷史記錄要做成 module，或至少是可選的。唯一必須留的只有上次的歷史，往更前面的，在核心架構下是不管的」 |

原本頂層給的第 5 點（「預設清垃圾，各有上限，超過刪最舊」）被追加的原則取代：上限、輪替都需要設定與清理邏輯，而「只留上一次」根本不會長，所以核心不需要它們。唯一還會隨時間變多的是「每次取新名字寫的控制檔回條」與「名字不在表上的槽」：前者交給寫的人（W3），後者報完結束再留一回合就刪（W7）。

## 原本依賴歷史的地方

| 依賴 | proto7-1 靠什麼 | proto7-2 改靠什麼 |
|---|---|---|
| tock 被打斷的恢復 | rounds.jsonl 最後 5 行有沒有這回合（F-05、G-08） | last-round.json 的 `round` 是不是這回合；不是就重寫，是就只收尾 |
| 回合數接續（round.json 壞掉） | rounds.jsonl 最後幾行裡最大的 round | last-round.json 的 round；兩個都不能用＝不知道 → error，等人修 |
| agent 接前任 state | 兩處找前任資料夾 | 同一個槽的 state.json |
| kernel 用量累計（不變條件三、K-07） | 掃所有任務資料夾（含 tasks-old）加總；purge 會讓用量歸零 | usage.json 在槽裡跨 run 只增不減；kernel-state 記每槽已見最大值＋`retired`，槽被刪也不掉 |
| 「誰下的 pause」（N-81 的 arbiter 翻 log 尾端） | log.jsonl | paused.json 本身記 owner |

## 生命週期三態與三個不變條件怎麼落地

| 項目 | proto7-2 |
|---|---|
| 三態判定原則 | spec 第 0 節，全文照用 |
| 不變條件一（K-01、K-02） | spec 2.2，照原決定；status 加 `round_open`、`recovery_pending` |
| 不變條件二（K-03～K-06） | spec 5.3、5.4；身分掃描改比 NODE＋TID＋RUN；once 的 `launch` 標記補上 tick 那一側的交接 |
| 不變條件三（K-07） | spec 第 8 節。tasks-old／purge 沒了，K-07 原本的觸發（purge 歷史）消失；剩下「名字從表上拿掉、槽被刪」這一種，用 kernel-state 記住的值擋 |
| K-08 owner 分兩塊 | spec 2.7，照原決定 |
| K-09 disk 掃描卡主迴圈 | **消失**：沒有 disk 計算，也沒有清理工作要在主迴圈做 |
| K-10 「1～2 ms 撿到新 node」 | **消失**：沒有掃描；register 在下一圈處理控制檔時生效 |

## 沿用的 proto7-1 保護（寫得更精簡）

世代 gen 與 `AOS7_GEN`、action.lock 與舊動作接管（認不出身分不殺）、動作逾時、抓目錄 fd 讀寫（root、node、任務資料夾）、tock 沒關上回合就補、控制檔每圈預算與逐件錯誤邊界（ctl-failed）、kill 範圍（Q1）、node 消失收程序（Q4）、子 daemon 所有權與 allow_stop／stopped.json（Q5）、restart 的 reload（Q6）、掛載與執行中加掛（S-23）、單項壞掉只跳過那項、非一般檔當不存在。這些在 spec 裡只寫規則，典故留在 proto7-1。

改了一點的：ctl-failed 改成同名蓋掉（H-07 的「保證不覆蓋」是為了留歷史，現在只留上一次）；JSONL 半行補換行那套只剩可選的 log.jsonl 與寫入紀錄用得到。

## 第三波探針建議的處理

| 編號 | 做法 | 理由 |
|---|---|---|
| N-81 pause 帶 owner | **納入**：paused.json 改成每 node 一份 owner 清單，resume 只拿掉自己的，`all: true` 全清；不帶 owner 的共用一格 | 多個控制者（預算 kernel、人、維運）一定會互相放掉對方的 pause（holds 探針被放掉 14～17 回合）；改法只是把一個布林換成一個清單，舊用法照樣能用 |
| N-84 resume 順便 wake | **納入** | 沒有人想要「resume 後還要等滿上一個 interval」；一行的改動，tickless 探針 790 ms → 100 ms |
| N-79 keep 的 not_before／enabled／restart 政策 | **部分納入**：`from_round` 本來就是 not_before（而且現在 once 也看，所以「第 N 回合跑一次」與退避都寫得出來）；`enabled` 納入；restart 政策（always／on-failure／never）**之後** | `enabled` 讓人停用一項又不丟掉槽裡的 state；restart 政策要先定「失敗」算什麼（非零結束碼？lost？被 kill？），是語意題，不是最簡能代定的（W11） |
| N-80 看得出 tick 用哪一版表 | **順手納入**：round.json 與 tick 輸出帶 `tasks_rev` | tick 現在本來就要拿鎖讀表，算個雜湊幾乎免費 |
| N-82、N-83、N-85 | 之後 | 現有基底用合作式協定做得到（探針已示範），不是這次五點的範圍 |

## 要你決定的（W 清單）

每題先照推薦寫進 spec 了，你說不要就改。

- **W1 已登記的 node 被搬走，新位置要不要自動接上？** 推薦：**不自動**，舊 id 保留登記、狀態 `missing`，新位置要另外 register。其他選項：(b) 舊 id 資料夾不見就自動取消登記；(c) 用 inode 追到新位置自動改 id（要掃描才找得到，等於把掃描請回來）。
- **W2 unregister 預設要不要 kill 上面的任務？** 推薦：**要**（跟 node 消失一致），`kill: false` 才留著。留著的任務從此收不到 tock，容易變孤兒。
- **W3 daemon 回條怎麼只留上一次？** 推薦：**同名蓋掉，寫的人用固定檔名**（`aos7-ctl` 預設 `<by>.<op>.<node>.json`）。代價：同一個人對同一件事連下兩次、daemon 還沒處理時只剩後一次（意思相同，影響小）；每次取新名字的人回條會越積越多，由他自己收。其他選項：(b) 只留全域最近一份回條（寫的人可能來不及讀）；(c) 回條留到被讀走（daemon 判斷不了誰讀過）。
- **W4 run 號怎麼來？** 推薦：**＝起它的回合數**（萬一不大於上一個 run 就用上一個＋1）。好讀（`job#57`＝第 57 回合起的），不用另外記計數器。其他選項：每個槽自己從 1 數。
- **W5 each 跟 keep 在 `max_live: 1` 時行為一樣，要不要合併？** 推薦：**兩個名字都留**，只在 `max_live` 大於 1 時不同（each 每回合起一個、keep 一次補滿所有槽）；名字表達意圖，對 LLM 好讀（S-01）。同題附帶：任務名只准英數、`_`、`-`（`.` 留給槽號），不合的整項跳過，不再偷偷換字元。
- **W6 任務自己寫的檔（state.json、usage.json…）換 run 時要不要留？** 推薦：**留**，這就是接前任；基礎設施檔才清。其他選項：每個 run 都清空，要接前任的自己存到槽外。
- **W7 名字從 tasks.json 拿掉的槽什麼時候刪？** 推薦：**結束報過之後再留一回合就刪**（含任務自己寫的檔）。once 任務的交付物因此要寫到槽外面。其他選項：留到人手刪（會越積越多，違反 10-04 原則）。
- **W8 tick 現在會改 tasks.json，不拿鎖直接用編輯器存檔的人可能被蓋掉。** 推薦：**接受**，tick 只在有 once 項時才改；文件寫明，工具給 `aos7-ctl add`。其他選項：once 的 `launch` 標記改記在另一個檔（但 once 項起完還是得刪，改表躲不掉）。
- **W9 daemon 事件流水帳要不要留一個開關？** 推薦：**留** `.aosd/log.on`，有這個檔 daemon 才寫 log.jsonl，而且不清、開的人自己管。理由：daemon 的事件（node 消失收程序、接管舊動作）任務只能從 status 取樣，會漏。其他選項：完全不給，只有 status 的 `last_event`。
- **W10 一次 run 的 out.log 會一直長（常駐又話多的任務），核心要不要管？** 推薦：**先不管**，它是「這一次」不是歷史；之後要管可以讓 tock 在超過上限時截斷（copytruncate，會掉幾行）。
- **W11 keep 的 restart 政策（N-79）現在定還是之後？** 推薦：**之後**。要先回答「失敗」是什麼：非零結束碼、lost、被 kill 各算不算。
- **W12 timeline.json 變成可有可無，可以嗎？** 推薦：**可以**，登記已經是 node 的標記，timeline.json 只放設定。代價：「刪掉 timeline.json＝node 消失」這個用法沒了，改用 unregister。
