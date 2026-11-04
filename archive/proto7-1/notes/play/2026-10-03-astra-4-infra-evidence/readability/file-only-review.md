# S-01：只讀檔案的獨立判讀

讀者是本輪時間探針 subagent，已讀 README／spec，**尚未見 tasks 實驗結果、provenance 或 `/proc` 真相**；不是全新上下文 LLM。此次只讀指定 snapshot-A/B/C.json，沒有執行其中任務或查詢程序。以下回答是「提供的檔案快照所記錄的最後狀態」，不能把快照說成此刻仍然有效的存活證明。

## Snapshot A

- **幾條時間線：** 一條，`n`；由 `n/.aos/timeline.json` 與 daemon `status.nodes` 一致支持。
- **第幾回合：** `round.json` 與最後 daemon tick 事件是第 5 回合、open；最後完成的是第 4 回合。status 仍寫第 4 回合 `phase:tick`，其 `at` 比第 5 回合 tick 事件早約 8 ms，因此是不同時刻的觀測，不能只讀 status 就稱目前第 4 回合。沒有共同 snapshot revision 讓讀者證明這些檔是同一瞬間。
- **哪些任務活著：** 協議列出的活任務為零。`fork-r1` 有 `exit.code:0`、`ended.round:1`，kill 回條也說 `already ended`。另有 `n/grandchild.json` 記 PID 1110682／PGID 1110677，表示曾記錄一個孫程序；**它是否仍活著是 unknown**，此檔沒有存活時間、退出資訊或 daemon 管理狀態。不可因 task exit=0 推論整群程序都結束。
- **剛哪裡出錯：** 檔案沒有報 tick/tock 失敗，kill 回條成功。我能指出「孫程序是否收掉未知」，不能僅憑檔案斷言它仍活著或 kill 失敗。

## Snapshot B

- **幾條時間線：** 一條 `n`。
- **第幾回合：** 第 4 回合已完成，round `open:false`、status `idle` 一致。
- **哪些任務活著：** status 與 rounds 的 `alive` 都是空陣列；但第 1 回合曾起 `delete-r1`，之後沒有 ended 事件、沒有 exit.json，也沒有 taskdir。`deleted.json` 記 PID 1112396 且 `taskdir_exists:false`。因此「daemon 目前列零個活任務」可確定；「曾起的任務是否真正結束、PID 1112396 是否仍活著」均 **unknown**。
- **剛哪裡出錯：** 能從檔案看出任務追蹤資料消失、生命週期缺尾段。daemon 所有 tick/tock rc 都 0，没有 last_error。`deleted.json` 是任務額外寫的證詞；沒有它時只能看到 started 沒有 ended，不能判斷消失原因。即使有它，也沒有可驗證的刪除者與刪除時刻，不能把檔名當作責任證明。

## Snapshot C

- **幾條時間線：** 一條 `n`。
- **第幾回合：** 第 4 回合已完成、idle；第 2～4 回合的 tick 都失敗，tock 仍成功。因此「回合數已到 4」不代表四次 tick 工作都成功。
- **哪些任務活著：** daemon 最後觀測將 `birtharray-r1` 列為活，rounds 最新 `alive` 與 task `tock.round:4` 相符，pid.json 指 PID 1112420、runner 1112419，無 exit.json。可回答「最後觀測的活任務是 birtharray-r1」；離開觀測時點後是否仍活，單次快照仍 **unknown**。
- **剛哪裡出錯：** 可以定位：birth.json 是 JSON 陣列 `[1]`，tick 的 `live_names` 對它呼叫 `.get("name")`，第 2、3、4 回合都發生 `AttributeError: 'list' object has no attribute 'get'`、rc=1。status.last_error 直接指出第 4 回合 tick 失敗；這一案只看檔足以判讀故障位置。看不出由誰、何時把 birth.json 改成陣列。

## 缺什麼欄位或檔案

1. **存活觀測的範圍與新鮮度：** `live:[]` 目前只代表已被索引的 taskdir，不證明 Linux 工作量已歸零。需要清楚區分 last_observed、unknown、exited，以及哪些程序群組／後代屬於管理範圍。只靠靜態檔案不可能永久證明未來仍活；可提供期限、epoch 與需重新觀測的明確語意。
2. **獨立於任務可刪資料夾的任務名冊：** 至少包含 tid、啟動／程序身分、最後觀測、退出／失聯／資料夾消失原因。B 目前連該把哪個 task 標 unknown 都只能從歷史 started 倒推。
3. **跨檔一致性標記：** daemon session、snapshot revision／event sequence、最後成功 tick 與 tock round。A 已實際出現 status=4、round=5；C 則表示 round 遞增不能拿來代表 tick 成功。
4. **可讀故障語意：** C 的 last_error 很有用；可以再補 error_kind、source_file、observed_round，讓讀者不必理解 Python traceback。A、B 的追蹤缺口應有 daemon 寫出的 unknown／tracking_lost 事件，不能只靠任務自寫 grandchild/deleted 檔。

**判定：** 時間線數可答 3/3；已開／已完成回合可答 3/3（A 要合讀 log＋round＋status）；最新已記錄活任務可答 3/3，但真實仍活程序／後代無法答。故障定位 C 可直接答，A 沒有足夠證據斷言故障，B 可辨識追蹤缺口卻無法辨識實際存活與責任。這證明可讀 JSON 已具備基本價值；缺的是可信且完整的觀測協議。
