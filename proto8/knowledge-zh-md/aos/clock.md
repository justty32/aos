# `knowledge/aos/clock.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/clock.md`，跟到正本 commit `c7bc08dae`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/clock.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

計時器：寄到你佇列的時鐘信（工具 clock_register：每 N 個週期、N 個週期後一次、某個牆上時間一次，或 cron），或掛在時鐘上、不往你對話加任何東西的程式（on_clock hook）。該選哪個：`aos/clock.md#/Doing something on a timer: which way`。沒有任何內建範本有 `clock_register`（agent-fsm 或 eca）：先用 `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/clock_register"}}` 加入它。

**`#/Wake me every N cycles`**

# 每 N 個週期叫醒我

呼叫 clock_register，op 用 add，給名字、every 和 text；不要給 box：
{"op": "add", "name": "check-inbox", "every": 10, "text": "Check data/ for new files."}
每 10 個週期你會收到一則使用者訊息 "[aos] clock: cycle 30. Check data/ for new files."。用 {"op": "rm", "name": "check-inbox"} 移除；用 {"op": "ls"} 列出。
要叫醒另一個 agent，給 box = 它的 STACK/queue。Shell：aos-clock-register add --every N --box BOX NAME TEXT。
只一次，或在某個牆上時間：`aos/clock.md#/Wake me once, at a time, or on a schedule`。
登記表屬於 $AOS_CLOCK 裡的那個時鐘；給 daemon D（shell 用 -d D）就改用時鐘 D/clock。

**`#/Wake me once, at a time, or on a schedule`**

# 叫醒我一次、在某個時間，或照排程

clock_register add 的 every、after、at、cron 只能給剛好一個：

- `after`：一次，從現在起 N 個週期後：{"op": "add", "name": "recheck", "after": 30, "text": "Re-run the tests."}
- `at`：在某個牆上時間一次，用機器的本地時間：`"21:30"`（今天；已經過了就明天）、`"2026-11-14 09:00"`，或從現在起 `"+10m"`、`"+2h"`、`"+1d"`（s、m、h、d）：{"op": "add", "name": "call", "at": "21:30", "text": "Send the report to ann."}
- `cron`：重複的牆上時間，5 個欄位 `minute hour day-of-month month day-of-week`，本地時間：`"0 9 * * 1"` = 每週一 09:00，`"*/15 * * * *"` = 每 15 分鐘，`"30 8 * * 1-5"` = 平日 08:30。欄位可以是 `*`、`N`、`A-B`、`*/S`、`A-B/S` 和逗號清單；星期是 0-7（0 和 7 = 週日）；日和星期都有設時，符合其中一個就算。不能用名字（`mon`、`jan`），也沒有 `@daily`。

`after` 和 `at` 的項目寄出信後就自己移除；`every` 和 `cron` 會一直留著，直到你 `rm` 它們。add 的結果會說它什麼時候觸發（`once at 2026-11-13 21:30`、`cron 0 9 * * 1, next 2026-11-16 09:00`）；`ls` 顯示每個項目的 WHEN。現在的本地時間：peek_now_time {"local": true}（`2026-11-13T21:05:00+08:00 Friday`）。

牆上時間的信會說它什麼時候到期：`[aos] clock: cycle 812, due 2026-11-13 21:30. Send the report to ann.`，晚超過一分鐘到時會加上 `(late by 2h 5m)`。

時間上的細節：

- 每次根時鐘走一個週期（大約一秒一次）就檢查一次項目：牆上時間的信最多晚一個週期。
- `after` 算的是週期：樹睡著或時鐘暫停時，沒有週期經過，等待也不會用完。
- `at` 和 `cron` 算的是牆上時間：在樹睡著時到期的，會在醒來後的第一個週期寄出一次；錯過很多次的 `cron` 項目只寄一次，不是每錯過一次寄一次，它的下一次從那時起算。
- 到期卻寄不出去的信，只是時鐘印的一行警告，不會重試：一次性的項目照樣移除，cron 項目移到它的下一次（跟 `every` 一樣）。
- 錯誤：`ArgumentsBad`（every/after/at/cron 一個都沒給或給了兩個；after 不是正整數；at 或 cron 看不懂；at 已經過了；cron 永遠不會觸發）、`ClockBad`（時鐘檔讀不了），以及 `aos/clock.md#/Clock letters: rules` 裡的那些。

**`#/Clock letters: rules`**

# 時鐘信：規則

- 在週期數能被 every 整除時觸發（every 10 就是 10、20、30），不是從你加入的時候開始算。
- 任何能寫登記表的人都能新增或移除任何項目。不再需要時就移除你的項目；時鐘自己只移除 box 資料夾已經不在的項目（預設每 100 個週期檢查一次）。
- 寄不出去的信只是時鐘印的一行警告；時鐘照常走。
- 你睡著時，信在你的佇列裡等；你醒來時一次全部收到。
- 錯誤：`EntryExists`（名字被用了：換一個，或 `"replace": true`）、`EntryMissing`（沒有那個名字的項目：先 `ls`）、`ClockMissing`（沒有時鐘：你不在有時鐘的 daemon 樹底下；或給 `daemon`）、`RegisterBad`（時鐘旁邊的登記表檔讀不了：要人來修）、`WriteFailed`（登記表寫不進去）。沒給 `box` 時：`DaemonMissing` / `InstanceMissing` = 你不在 daemon 的表上，所以你沒有佇列可以叫醒；給 `box`。
- 人打開的畫面（`aos-agent open`）拿到的 `AOS_CLOCK` 跟你的迴圈一樣。在你的迴圈跑過一次之前打開的畫面，是從那個人的 shell 拿的，可能沒有：這時 `peek_clock` 和 `clock_register` 會回 `ClockMissing`，雖然樹其實有時鐘。請人把畫面關掉再打開。`on_clock` hook 不受影響：它們在你的迴圈裡跑，不在畫面裡。

**`#/A timer that does not enter your conversation`**

# 不進你對話的計時器

clock_register 的信會進你的佇列，所以每一封都變成一則訊息。只想照時鐘跑一個程式，就改用 hook：
self_hook {"op": "add", "event": "on_clock", "every_ms": 600000, "path": "hooks/check"}
從上次跑完，時鐘走了相當於 10 分鐘的週期時，它就跑 hooks/check（在你每一步開始時檢查；不管錯過幾次都只跑一次；你睡著時從不跑；你啟動、醒來或重啟後也會馬上跑一次）。程式從 stdin 拿到 clock、cycle、interval_ms、first、last_cycle、missed。除非它寄一封信到你的佇列（aos-post send STACK/queue），不然什麼都不會傳到你這裡。你的定義可能有一個計時 hook（每 5 分鐘、什麼都不做）可以換掉，還有一個 mail_notify hook（每分鐘；`aos/mailbox.md#/Hearing about new letters`）。程式怎麼寫：`aos/me/self_hook.md#/Writing the hook program`。
every_ms 會換算成整數個時鐘週期、無條件進位：實際間隔可能比寫的長，不會比較短。醒來後事件的 first 是 true、missed 是 0；它不會說你睡了多久（自己補做的處理程式：`aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`）。沒有時鐘（AOS_CLOCK 沒設、也沒有 clock 鍵）時 hook 永遠不會跑：你的 log 會有一行警告，也不會改用牆上時間。

**`#/Doing something on a timer: which way`**

# 照計時做事：用哪種方式

三種方式，差在什麼會進你的對話（對話歷史）：

1. 時鐘信（`clock_register`）：一段固定文字每 N 個週期、一次（`after`、`at`），或照牆上時間排程（`cron`；`aos/clock.md#/Wake me once, at a time, or on a schedule`）送進你的佇列。每一封都是你對話歷史裡的一則訊息、一次腦的回合，就算沒事做也一樣。在你每次都必須思考時用它。
2. `on_clock` hook（`self_hook`）：每 N 個週期或 ms 跑一個程式。什麼都不進你的對話歷史；不花腦的回合。只靠程式就能做完工作時用它（複製檔案、寫 log）。
3. 只在有新消息時才寫進你佇列的 `on_clock` hook：程式檢查某樣東西，只有那時才寄一封信到你的佇列。對話歷史只在那時變長。例子：現成的 `mail_notify` hook，預設開著（`aos/mailbox.md#/Hearing about new letters`）。另一個例子：在牆上時間做、先檢查有沒有工作的事（每天 09:00、每 3 天）：`aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`。只是在牆上時間提醒、不用檢查：用 `clock_register` 加 `at` 或 `cron` 比較簡單。

在 eca 身體上，每一次腦的回合都要花錢：優先用 2 或 3。已經在你對話歷史裡的訊息可以用 `self_history` 移除。程式怎麼寫：`aos/me/self_hook.md#/Writing the hook program`。
