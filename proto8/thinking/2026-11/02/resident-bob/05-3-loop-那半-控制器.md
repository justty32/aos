← [入口](README.md)｜涵蓋：規劃 › 3. 「loop」那半：控制器｜上一份 [04-1-誰當父-daemon-當父-控制器經](04-1-誰當父-daemon-當父-控制器經.md)｜下一份 [06-4-資料夾程式長什麼樣-怎麼請-daem](06-4-資料夾程式長什麼樣-怎麼請-daem.md)

### 3. 「loop」那半：控制器

- **定義在 `agents/resident_bob/ctl/`**，是一支 aos-loop，用 exec 型子項掛、入口是單子，讓 aos-loop 這個行程的 fd 1 就是 FIFO 寫端（[衝突 5](12-要使用者看的衝突與方向題-11-02-晚.md#衝突-5控制器用-exec-型包一支-aos-loop掛的目標指到-_entryjson-檔)）：

  ```json
  // ctl/_entry.json —— aos-exec 在 fork 前開 FIFO 寫端（等到 bob 開了讀端）、起 aos-loop
  {"argv": ["aos-loop", "loop.json"],
   "stdout": {"$env": "AOS_DAEMON_STACK", "$path": "loops/bob/in.fifo"}, "stdout_append": true}
  // ctl/loop.json —— 每 300 ms 跑一次 relay；窗用 ctl.json／state.json（ctl-state-names）
  {"exec": "relay", "interval_ms": 300}
  ```

  log 預設不印（loop-stdio），fd 1 上只有 `relay` 寫的東西；`relay` 往 stdout 寫一行＝送進 bob 的 stdin。**`ctl/` 裡有 `loop.json`，掛資料夾會被 aos-daemon-ctl 認成 loop 型、單子的 `stdout` 就沒了——所以掛的目標指到檔 `ctl/_entry.json`**，`--name bob_ctl`。
- **控制器的小格**＝`relay` 的 `$AOS_STACK`：`queue/`（aos-say 建）、`history.jsonl`（`relay` 寫，OpenAI 形，P-41／P-42）、`ctl.json`／`state.json`（aos-loop 的窗）、`relay_state.json`（`relay` 自己的）、`mailbox_warning.txt`（壞信）、`stderr.txt`。**人對話的 stack 就是這一格**。
- **`relay` 每輪**（Python；`ctl/relay/_entry`；有沒有事都退 0，失敗退 1、stderr 一行〔P-20、P-21〕；順序是 看 bob → 同步輸出 → 送信，[代定](10-實作時代定-11-02.md#實作時代定11-02)）：
  1. **看 bob**：直接讀 daemon 的名單窗（`$ref` 分檔照 aos-daemon-ctl 的讀法合回來），有沒有 `bob`；不在＝退 1 `BobGone`。
  2. **同步輸出**：從 `relay_state.json` 的 `out_offset` 讀 bob 的 `out.jsonl` 新的整行（沒有換行結尾的半行留到下輪），逐行：
     - 回吐的 user 行（`isReplay: true`）：內容＝這題併進去的訊息以 `\n` 接起來，照 `sent` 的順序比前綴定出這題答哪幾封，這時才把那幾則 user 寫進 history；對不上＝當成只答第一封、警告檔記一行。
     - `assistant`：Anthropic 區塊陣列（⑤）轉成一則 OpenAI message——`text` 接成 `content`、`tool_use`→`tool_calls`、`thinking` 丟掉；同一個 `message.id` 合成一則，最後一行是 `assistant` 時等下一行出現再寫。
     - 工具回吐的 `user`（`tool_result`）→ 每個區塊一行 `{"role": "tool", "tool_call_id", "content"}`。
     - `result`：這題的信全部 `aos-post finish`（**一個 result 結掉好幾封**，使用者決定「併題正常」）；`error_max_budget_usd` → 先結掉再 `rm bob`、退 1 `BudgetOut`；`error_during_execution` → 照樣結掉、警告檔記一行；`session_id` 以**最後一行**為準寫進 `relay_state.json`。
     - `system`／`init`（每題一次，④）、`rate_limit_event`、`conversation_reset` 等：略過。
  3. **送信**（一直丟，不等 `result`）：先探針 `os.open(in.fifo, O_WRONLY|O_NONBLOCK)`，`ENXIO`＝bob 還沒開讀端、這輪不送。`aos-post claim-all` 把 `new/` 全認領進 `cur/`，每封 `check`：
     - body 不是 `{"role": "user", "content": 非空字串}`＝壞信：`finish`、`mailbox_warning.txt` 記原因。
     - `content` 去掉開頭空白後以 `/` 開頭＝**不轉送**（⑪：`/clear` 會清對話、`/cost` 會吐帳號用量）：當壞信收掉、記「以 / 開頭的訊息不轉送」；第二版認 `/sleep`。
     - 好信：寫一行 `{"type": "user", "message": {"role": "user", "content": …}}` 到 stdout、flush；信留 `cur/`、信號記進 `sent`。寫時 `BrokenPipeError`＝這封不記 `sent`、下輪重送，並把 fd 1 `dup2` 成 `/dev/null` 再結束這輪（不然 Python 結束時 flush 再炸、退 120）。
  4. **睡／醒**（第二版，不做）：閒置超過 `--idle-ms`（11-01 使用者「旋鈕走 argv」）或收到 `/sleep` → `rm bob`、`bob`＝`asleep`；`asleep` 而有新信 → `add … -- --resume <session_id>`、`waking`；`waking` 而 bob 在表上 → `up`；`waking` 滿 10 秒還不在 → 退 1。
  5. **收工**：`relay` 不決定收工（收工是人的事：寫控制器的 `ctl.json` 停，或 `aos-daemon-ctl rm bob_ctl`）。aos-loop 結束→FIFO 寫端全關→bob 答完手上那題退 0。暫停＝aos-loop 不起 `relay`：信在 `new/` 排著、已送進去的照答。
- **`relay_state.json`**（只有 `relay` 寫，先寫暫存再改名，N-05）：`{"bob", "bob_pid", "session_id", "out_offset", "sent", "answering", "last_activity_at", "updated_at"}`。它同時是「stack 有沒有殘留對話」的小窗：install 看它有 `session_id` 就 `--resume`。`bob_pid` 跟表上的不同＝換了一支 bob → 先把舊輸出同步完，還沒結掉的 `sent` 全當沒送過、重送。
- **底下全叫現成的**：`aos-post claim-all／check／finish`（不自己 rename）、`aos-daemon-ctl add／rm`（不自己投信、不自己 kill）。
- **各身體另外定義**（使用者原文）：`relay` 放 `ctl/relay/`；以後要加別的身體＝`ctl/` 底下再一個資料夾、`loop.json` 的 `exec` 改指一張 aos-fsm 表。本題一個身體，不先鋪 fsm（C-56）。
