# astra 審查：10-01 spec 統一更新

← [notes](../../README.md)

核心流程大致對得上。主要問題是**舊 daemon 規則仍混進正式篇，以及新用法接到舊設計後留下缺口**。以下未把刻意暫緩、POC 不處理異常當成缺失。全程唯讀，沒有改檔。

**一、必修**

1. **正式篇仍承諾舊 daemon 才有的功能。**  
   位置：`proto6/spec/settled/terms.md:59`、`proto6/spec/settled/tick.md:520`、`proto6/spec/settled/README.md:57`。  
   問題：仍說擋板會讓 daemon 不開格，並把通道、格後清理、node 框列成「經 daemon 跑才有」的差別；入口也把暫緩功能列為核心必需。現行 daemon 其實不提供這些。  
   建議：擋板改寫為「daemon 照常叫，由 tick 自己擋」；其餘明標只適用舊 daemon，移出現行核心依賴表。

2. **恢復前驗證依賴已暫緩的授權與指令。**  
   位置：`proto6/spec/settled/tick.md:482`。  
   問題：仍要求 daemon 核對可信額度，驗過才送 `node.resume`；但現行控制模組不驗身分，也沒有這個 RPC。B-620 又把這段當成完整 schema 的把關者。  
   建議：舊授權流程標暫緩；若保留現行人工驗證，寫清楚「工具／人工先驗，再用 `aos-ctl resume`，daemon 不代驗」。

3. **新 daemon 協議引用的「共用約定」與自己矛盾。**  
   位置：`proto6/spec/settled/protocol/daemon/README.md:22`、`proto6/spec/protocol/README.md:19`。  
   問題：共用條文要求持久 JSON 帶 `version`、daemon socket 使用 JSON-RPC 並核對身分；P-120／P-121 都不是這樣。現在只交代了陌生欄位的例外。  
   建議：在新協議入口集中列明哪些舊共用條文不適用，以 P-120／P-121 為準。

4. **wake「照最後一次」少了一個正常操作的例外。**  
   位置：`proto6/spec/settled/daemon/control.md:37`。  
   問題：先排補跑並設 `keep_schedule:true`，再送 `skip_while_running:true`，程式會保留前一次選項；文字卻說照最後一次 wake。plan 與程式都明定被 skip 的請求什麼都不改。  
   建議：改為「照最後一次**沒有被 skip 丟掉**的 wake；skip 不取消既有補跑，也不修改選項」。

5. **控制請求的 schema 比協議多禁了一個欄位。**  
   位置：`proto6/spec/protocol/schemas/daemon-ctl.schema.json:29`。  
   問題：`{"status":"a","ok":"extension"}` 依 P-121 與程式會忽略陌生欄位、正常接受，schema 卻拒絕。  
   建議：請求與回應分別驗 `$defs/Request`、`$defs/Reply`，不要為了合併驗證入口而新增協議沒有的限制。

6. **暫緩區自己的訊息授權判準互相矛盾。**  
   位置：`proto6/spec/settled/deferred/daemon/runtime.md:55`、`proto6/spec/settled/deferred/daemon/messaging.md:24`。  
   問題：前者仍看收件方 `requests/` 寫權，後者明定看 `.aos/mq/get/`，而且明說 `requests/` 不影響。P-111 也殘留前一種說法。  
   建議：B-601、P-111 直接引用 B-614 的判準，避免重寫三份。

7. **憑證的狀態混成「暫緩」與「已被取代」。**  
   位置：`proto6/spec/settled/conventions.md:80`、`proto6/spec/settled/deferred/daemon/channel.md:36`。  
   問題：前者說 `AOS_TICK_TOKEN` 已被控制模組取代；後者卻保留整套通道憑證，並說控制 socket 不是這條通道。現有裁定只足以支持「現行控制不使用憑證」。  
   建議：統一標「現行控制不使用；舊通道憑證暫緩，未來另定」，不要推成永久取消。

8. **輸出順序承諾比程式強。**  
   位置：`proto6/spec/settled/protocol/daemon/core.md:72`。  
   問題：說 `stopped` 緊接自己的 `exit` 行；程式分兩次取輸出鎖，其他項的整行可以插進來。  
   建議：改成「在該次 exit 行之後另印一行，其他項可能穿插」。

9. **幾處小型敘述與引用錯誤。**  
   位置：`proto6/spec/settled/tick.md:384`、`proto6/spec/settled/README.md:151`、`proto6/spec/settled/deferred/daemon/README.md:33`。  
   問題：`mq-get` 並非兩版範本都排第一；H-036 連到錯篇；T-09 仍連搬家前入口。  
   建議：`mq-get` 註明有 git 時排在 `git-open` 後；H-036 改連 `cli/walkthrough.md`；T-09 直連 `deferred/terms.md`。

**二、設計問題**

1. **`aos-cg` 照規定收尾，會連自己一起殺掉。**  
   位置：`proto6/spec/settled/tick.md:357`、`proto6/spec/settled/deferred/daemon/cgroup.md:171`。  
   問題：先把監督程式自己搬進任務框，再要求殺空、等待、刪框；自己還在框內，無法完成收尾。另外推薦的 `aos-cg -- aos-as …` 已讓框內有人，helper 卻要求空框，正常用法也過不了。  
   建議：監督程式留框外，只讓子程序進框；helper 核對框的歸屬與允許的現有程序。這是設計流程本身的問題，不是要求現在實作暫緩功能。

2. **自訂任務表沒有辦法交給需要讀表的系統任務。**  
   位置：`proto6/spec/settled/tick.md:115`、`proto6/spec/settled/tick.md:556`。  
   問題：允許 `aos-tick /w/other.json`，甚至沒有預設 `tasks.json`；但 `aos-git` 要回查本格任務表的 `kind`。環境變數、紀錄與 git 命令參數都沒提供表路徑。  
   建議：定一個取得本格任務表的方式，例如紀錄保存絕對路徑，或新增專用環境變數，讓三個 git 命令共用。

3. **同一格式限制拆成 schema 與 Python 兩套。**  
   位置：`proto6/spec/settled/protocol/daemon/core.md:59`。  
   問題：「頂層與每項都沒有 `interval_ms`，schema 表達不了」不正確；目前 schema 接受 `{"insts":{"a":{}}}`，再靠範例驗證腳本補擋，直接使用 schema 的工具會漏驗。  
   建議：用 schema 的條件規則表達「頂層沒提供時，每項必填」，移除範例腳本的重複判定。程式本身的設定檢查照留。

**三、建議**

1. **把已實作核心與待做系統程式分篇。**  
   位置：`proto6/spec/settled/tick.md:284`。  
   問題：662 行同時裝現行核心、未實作程式、依賴暫緩功能的流程，「正式」很容易被讀成「現在已有」。  
   建議：核心留 `tick.md`；範本與各系統程式移到下一層，每篇開頭標「已實作／待實作／依賴暫緩」。保留條號，不必全面改名。

2. **README 的疑點清單先分清哪些真的要問人。**  
   位置：`proto6/spec/settled/README.md:102`。  
   問題：十題混了方向選擇、已裁定的 POC 取捨、以及文件怎麼標的編輯問題，容易把已回答的事再問一次。  
   建議：只把會改變行為或保證的選擇留在「待裁定」；例如重複 id 不檢查、異常自然丟錯，照既有裁定記清楚即可。

**四、要使用者裁定**

1. **`AOS_DIRNAME=""` 時，git 到底管哪些檔？**  
   位置：`proto6/spec/settled/conventions.md:43`、`proto6/spec/settled/tick.md:544`。  
   問題：空字串代表狀態資料夾就是工作資料夾；再套「`.aos/` 下追蹤的檔全歸 aos」，就會把使用者檔一起提交、還原，撞上「只管 aos 自己的東西」。  
   **建議與後果：**建議空字串時列舉 aos 自有檔與子目錄，再加明確納入的路徑；能保住使用者檔，但要維護清單。若選整個資料夾，就必須明確接受使用者檔也受還原影響。

2. **未來檔案控制入口，與現在的 socket 控制模組是什麼關係？**  
   位置：`proto6/notes/verdicts/11-tick-as-unit.md:340`、`proto6/spec/settled/daemon/README.md:17`。  
   問題：node 模組方向寫「叫醒、暫停、狀態放核心，檔觸發、不開 socket」；現行則是控制模組加 socket，未交代取代或並存。  
   **建議與後果：**建議現在維持 socket 版，將檔觸發標為未排程、關係待定。將來若並存，兩種入口應共用狀態邏輯；若取代，要處理 `aos-ctl` 與環境變數的相容性。這不算現行程式錯誤。

驗證：完成本地連結／錨點掃描及局部記憶體驗證；未發現不存在的連結目標。完整 schema／examples 驗證腳本因缺 `referencing` 未能執行，未安裝套件。