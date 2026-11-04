← [入口](README.md)｜涵蓋：規劃（fable 11-02 晚第二版，照使用者決定與實測改寫；可翻案） › 3. 「loop」那半：控制器｜上一份 [04-1-誰當父-daemon-當父-控制器經](04-1-誰當父-daemon-當父-控制器經.md)｜下一份 [06-4-資料夾程式長什麼樣-怎麼請-daem](06-4-資料夾程式長什麼樣-怎麼請-daem.md)

### 3. 「loop」那半：控制器

- **定義在 `agents/resident_bob/ctl/`**，是一支 aos-loop，用 exec 型子項掛、入口是單子，讓 aos-loop **這個行程**的 fd 1 就是 FIFO 寫端（loop 型子項的行程 fd 由 daemon 定成 `/dev/null`，拿不到；[衝突 5](12-要使用者看的衝突與方向題-11-02-晚.md#衝突-5控制器用-exec-型包一支-aos-loop掛的目標指到-_entryjson-檔)）：

  ```json
  // ctl/_entry.json —— aos-exec 在 fork 前開 FIFO 寫端（等到 bob 開了讀端）、起 aos-loop；兩個行程都握著 fd 1 直到結束
  {"argv": ["aos-loop", "loop.json"],
   "stdout": {"$env": "AOS_DAEMON_STACK", "$path": "loops/bob/in.fifo"}, "stdout_append": true}
  // ctl/loop.json —— 每 300 ms 跑一次 relay；窗加前綴 loop_（exec 像繼承：共用 stack 的名字各自加前綴）
  {"exec": "relay", "interval_ms": 300, "ctl": "loop_ctl.json", "state": "loop_state.json"}
  ```
  （11-02 晚推翻：控制器改用 `ctl.json`／`state.json`，試驗場已改，見 [ctl-state-names](../ctl-state-names.md)。）

  log 預設不印（loop-stdio 決定），fd 1 上只有 `relay` 寫的東西。`relay` 繼承 fd 1（aos-loop 跑資料夾目標＝fork＋`run_cli`，不另開串流），往 stdout 寫一行＝送進 bob 的 stdin。**`ctl/` 裡有 `loop.json`，`aos-daemon-ctl add <ctl 資料夾>` 會自動認成 loop 型**（它看「資料夾有 `loop.json`」）、單子的 `stdout` 就沒了——所以掛的目標指到**檔** `ctl/_entry.json`（C-73 入口可以是單子檔；XXX 不是帶 `loop.json` 的資料夾＝exec 型），`--name bob_ctl`。
- **控制器的小格 `$AOS_DAEMON_STACK/loops/bob_ctl/`**＝`relay` 的 `$AOS_STACK`，裡面：`queue/`（aos-say 建，N-16 有順序）、`history.jsonl`（`relay` 寫，OpenAI 形，P-41／P-42）、`loop_ctl.json`／`loop_state.json`（aos-loop 的窗）、`relay_state.json`（`relay` 自己的，前綴 `relay_`）、`mailbox_warning.txt`（壞信，同 agent 範本）、`stderr.txt`。**人對話的 stack 就是這一格**：`aos-say --stack $AOS_DAEMON_STACK/loops/bob_ctl 話`。
- **`relay` 每輪的身體**（Python；`ctl/relay/_entry`；一輪＝下面五步，有沒有事都退 0，失敗退 1、stderr 一行〔P-20、P-21〕）：
  1. **看 bob**：讀 `$AOS_DAEMON_STACK/loops_state.json`（分檔的 `$ref` 解回來，表 >100 列才會有）→ `execs` 表有沒有 `bob`。`relay_state.json` 的 `bob` 欄＝`up`／`asleep`／`waking`（第二版）；`up` 卻不在表上＝死了 → 退 1（第 1 節 2）。第一輪 `bob` 欄還沒有：控制器的 aos-exec 要等 bob 開了 FIFO 讀端才起得來，所以 `relay` 跑到時 bob 一定在表上（或剛死）→ 在就記 `up`。
  2. **送信**（一直丟，不等 `result`）：bob 在表上才做。先探針 `os.open(in.fifo, O_WRONLY|O_NONBLOCK)`——沒有讀端＝`ENXIO`（bob 的 aos-exec 還沒開到 stdin）＝這輪不送；探到就關掉探針。然後 `aos-post claim-all` 把 `new/` 全認領進 `cur/`，每封 `aos-post check` 讀 body：
     - body 不是 `{"role": "user", "content": 非空字串}`＝壞信：`finish` 收掉、`mailbox_warning.txt` 寫原因（同 aos-eca-turn）。
     - `content` 去掉開頭空白後以 `/` 開頭＝**不轉送**（⑪：`/clear` 會清對話、`/cost` 會吐帳號用量、`/compact` 多半真的執行）：第一版沒有控制器自己認的指令，一律當壞信收掉、`mailbox_warning.txt` 記「以 / 開頭的訊息不轉送」；第二版認 `/sleep`（第 4 步）；要不要改成轉義後照送見[方向題 2](13-衝突-7-控制器建-bob-小格裡的-F.md#方向題-2-開頭的訊息拒收還是轉義送進去控制器自己的指令用什麼字頭)。
     - 好信：`{"role": "user", "content": …}` 原樣追加 `history.jsonl`（agent-lifecycle A-3：一封信＝一行），再寫一行 `{"type": "user", "message": {"role": "user", "content": …}}` 到 stdout＝FIFO（實測的輸入形狀，`content` 字串就行）、flush。信**留在 `cur/`**，信號記進 `relay_state.json` 的 `sent`（寫到管子裡、還沒被 `result` 結掉的）。寫 stdout `BrokenPipeError`（探針到寫之間 bob 剛好沒了）＝這封留 `cur/`、不記 `sent`，下一輪重送（`cur/` 裡不在 `sent` 的＝沒送成的）；bob 真死了下一輪第 1 步會退 1。
  3. **同步輸出**：從 `relay_state.json` 的 `out_offset` 讀 `loops/bob/out.jsonl` 新的整行（每行都是完整的 JSON，⑧；讀到沒有換行結尾的半行就留到下輪），逐行：
     - `system`／`init`（每題一次，④）：**把 `sent` 裡現在的信號快照成這題的 `answering`**——claude 開一題時把到那一刻為止排在 stdin 的訊息併成一則（⑥），之後進來的歸下一題；記下 `session_id`。
     - `assistant`：`message.content` 是 Anthropic 區塊陣列（⑤）→ 轉成一則 OpenAI message 追加 history：`text` 區塊接成 `content` 字串；`tool_use` 區塊→`tool_calls: [{"id", "type": "function", "function": {"name", "arguments": JSON 字串}}]`（有 tool_calls 時 aos-listen 不當回答，正好）；`thinking` 區塊丟掉。
     - `user`（用工具時 claude 回吐的 `tool_result` 區塊；形狀沒測）→ 每個區塊一行 `{"role": "tool", "tool_call_id", "content"}`；不是 tool_result 的 `user` 行（`--replay-user-messages` 沒開，應該不會有）略過。
     - `result`：`answering` 裡的信全部 `aos-post finish`（**一個 result 結掉好幾封**，使用者決定「併題正常」）、從 `sent` 拿掉；`subtype` 是 `error_max_budget_usd` → 第 1 節 3（`rm bob`、退 1）；`error_during_execution`（被 `interrupt` 打斷，⑨）→ 信照樣結掉、`mailbox_warning.txt` 記一行；`session_id` 寫進 `relay_state.json`（以**最後一行**為準——`/clear` 過 id 會換 ⑪，雖然 `/` 已經擋掉）。
     - `rate_limit_event`、`system`／其他 subtype、`conversation_reset`：略過。
     - 寫完 `out_offset`。history 於是「幾則 user、一則 assistant」一段段——`aos_ws.exchanges` 本來就把一則回答前的所有 user 收成一段，aos-listen `--last N` 直接對；`aos-listen 信號`「信不在 `new/`／`cur/` 了就印最新那則回答」照樣成立，只是那則回答可能同時回了好幾封（使用者決定接受）。
  4. **睡／醒**（**第二版**，第一版只預留 `relay_state.json` 的欄位與第 1 步的 `asleep`／`waking` 分支）：`relay_state.json` 記 `last_activity_at`（最後一次送信或 `result`）；閒置超過 `--idle-ms`（`loop.json` 的 `exec` 寫成 `["relay", "--idle-ms", "600000"]`；11-01 使用者「旋鈕走 argv」；沒給＝不睡）、或收到 `/sleep`（第 2 步攔下、不進 bob）→ `aos-daemon-ctl rm bob`、`bob`＝`asleep`。之後每輪：`asleep` 而 `new/` 有信 → `aos-daemon-ctl add --name bob <abs>/bob -- --resume <session_id>`、`bob`＝`waking`；`waking` 而 bob 在表上 → `up`、照第 2 步送（探針擋住「進程在了、stdin 還沒開」那幾毫秒）；`waking` 滿 10 秒還不在表上＝起不來 → 退 1。睡著時信在 `new/` 排著、`history.jsonl` 不動、aos-listen 照等。
  5. **收工**：`relay` 自己不決定收工（收工是人的事：`loop_ctl.json` 寫 `{"stopped": true}` 或 `aos-daemon-ctl rm bob_ctl`）。aos-loop 結束→aos-exec 結束→FIFO 寫端全關→bob 答完手上那題退 0（第 1 節 1）。`paused`＝aos-loop 不起 `relay`：信在 `new/` 排著、bob 閒著、已送進去的照答（N-07 原義）。
- **`relay_state.json`**（只有 `relay` 寫，先寫 `.relay_state.json` 再改名，N-05）：`{"bob": "up"|"asleep"|"waking", "session_id", "out_offset", "sent": [信號...], "answering": [信號...], "last_activity_at", "updated_at"}`。它同時是**「stack 有沒有殘留對話」的小窗**：install 看它有 `session_id` 就用 `--resume`。
- **底下全叫現成的**：`aos-post claim-all／check／finish`（不自己 rename，agent-lifecycle A-9）、`aos-daemon-ctl add／rm`（不自己投信、不自己 kill）；`loops_state.json` 用 `aos-directive` 解或自己照 `$ref` 讀（表 ≤100 列時就是一份物件）。
- **各身體另外定義**（使用者原文）：`relay` 放控制器自己的資料夾 `ctl/relay/`（N-50／P-25，相對路徑零個 `..`）；以後要加別的身體（定時摘要、定時問一句）＝`ctl/` 底下再一個資料夾、`loop.json` 的 `exec` 改指一張 aos-fsm 表各身體一格。本題一個身體，不先鋪 fsm（C-56）。
