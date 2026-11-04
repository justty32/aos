← [入口](README.md)｜涵蓋：規劃（fable 11-02 晚第二版，照使用者決定與實測改寫；可翻案） › 1. 誰當父：daemon 當父、控制器經 daemon 管（頂層「控制器當父」案的評估）、2. 「exec」那半：bob 怎麼變成一直跑的｜上一份 [03-現況-查清的-不是規劃](03-現況-查清的-不是規劃.md)｜下一份 [05-3-loop-那半-控制器](05-3-loop-那半-控制器.md)

### 1. 誰當父：daemon 當父、控制器經 daemon 管（頂層「控制器當父」案的評估）

頂層的初步看法是「起停睡醒都歸控制器，控制器當 bob 的父程式最自然、pid 在手、同生共死好做」。三案比過，**建議 (B)**：

- **(A) 控制器當 bob 的父程式**。aos-loop 的身體是每輪一支新行程，活不過一輪，當不了長壽子程式的父；要當父，控制器的 `_entry` 得改成一支自己寫的常駐 Python（開管子、`Popen` claude、自己輪詢 queue、自己讀 ctl、自己收屍）——這等於重寫一個小 daemon＋小 loop（起子程式、記 pid、SIGTERM、等退、表、`interval_ms`、`paused`／`stopped`），跟 aos-daemon、aos-loop 做的事重疊（C-56「不多造」；使用者 11-01「明明現有的機制組合一下就能搞定」）。aos 裡「叫別人」＝給小格、**等它做完**（P-17）；「起一個不等它、長壽的」就是 daemon 的工作（C-74 基礎層）。pid 在手的好處其實用不到：收 bob 用 `aos-daemon-ctl rm bob`＝daemon 送 SIGTERM，不必知道 pid；bob 死活讀 daemon 的 `loops_state.json`（窗，N-14「最新那份算數」）。結構上也變成「一個 exec（裡面偷偷包著 bob）」，不是使用者說的「一個 exec 加一個 loop」。
- **(B) daemon 當兩個的父，控制器經 daemon 管 bob**（建議）。bob、控制器都是 daemon 表上的一列（`aos-daemon-ctl ls` 一眼看到），各有小格；控制器起 bob＝`aos-daemon-ctl add --name bob … [-- --resume ID]`，收 bob＝`aos-daemon-ctl rm bob`，看 bob＝讀 `$AOS_DAEMON_STACK/loops_state.json` 的 `execs` 表有沒有 `bob`。**同生共死不靠一條機制，靠三個方向各自現成的路**：
  1. **控制器沒了 → bob 跟著走**：控制器行程（aos-exec 監工＋aos-loop）握著 FIFO 唯一的寫端，不論它怎麼死（`stopped`、`rm`、崩掉、SIGKILL），寫端一關 bob 就讀到 EOF，**答完手上那題以 0 結束**（⑫）、daemon 從表上拿掉。不用控制器做任何事，SIGKILL 也擋不住。
  2. **bob 沒了 → 控制器跟著停**：`relay` 每輪讀一次 `loops_state.json`；它認為 bob 該在（不是自己哄睡的）卻不在表上＝bob 死了（崩、被人 `rm`、`--resume` 接不回）→ stderr 一行、退 1 → aos-loop 以 1 結束（P-20 停下等人）→ daemon 表上 `bob_ctl` 走掉。不等寫信時 EPIPE 才發現（bob 死了而沒信進來時 EPIPE 永遠不會來）。
  3. **bob 活著卻沒用 → 控制器收它、自己也停**：超預算（⑦）bob 不退，`relay` 看到 `result.subtype` 是 `error_max_budget_usd`＝這題起沒答、之後也不會答 → `aos-daemon-ctl rm bob`（daemon 送 SIGTERM）、stderr 一行、退 1。
  4. daemon 沒了 → 它收工時全部送 SIGTERM（P-36），兩個一起走。
  
  **「結束由控制器明確送 SIGTERM」**（使用者決定）落在控制器**主動**要 bob 停的場合（3 與第二版的睡）；控制器**自己**被停時 bob 走的是 1 的 EOF 路——這條比 SIGTERM 溫和（SIGTERM 會丟掉手上那題 ⑧，EOF 讓它答完），但跟使用者「不是靠關管子」那句有出入，列成[方向題 1](13-衝突-7-控制器建-bob-小格裡的-F.md#方向題-1控制器自己被停時bob-走-eof答完退還是先-rm-bob立刻退)。
- **(C) daemon 綁組**：aos-daemon 多一個「這幾個子項同組、一個退了全收」的 key。要改 C++、立新條文（N-28 補），而且「活著卻沒用」（3）它看不出來，還是得控制器自己判；等第二個需要綁組的場合出現再做（C-56 最後一步減法）。不做。

### 2. 「exec」那半：bob 怎麼變成一直跑的

- **還是 `claude -p`，多三個旗標** `--input-format stream-json --output-format stream-json --verbose`；其餘旗標照現有 bob；`system.txt` 多兩句（「你會一直在，一題接一題，答完等下一題」「每題答完用一兩句說你做了什麼」）。**`--max-budget-usd` 是整個 session 的總額、超了不退只報錯**（⑦）：拿掉或調大是錢的事（[衝突 6](12-要使用者看的衝突與方向題-11-02-晚.md#衝突-6exec-就是我們現有的-bob但要加旗標處理預算) (c)），控制器照第 1 節 3 處理超預算。
- **入口是一張靜態單子**，`stdin`／`stdout` 都指自己的小格（`$AOS_STACK`＝daemon 給的 `loops/bob/`）；題目與 `--resume` 都靠 aos-exec 把 args 接在 `argv` 後面（inst「args 接在後面」），**不用小殼**：

  ```json
  // agents/resident_bob/bob/_entry.json
  {"argv": ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--model", "haiku", "--tools", "Read,Write,Edit,Glob,Grep", "--permission-mode", "acceptEdits",
            "--strict-mcp-config", "--add-dir", {"$env": "AOS_WS"}, "--append-system-prompt-file", "system.txt"],
   "stdin":  {"$env": "AOS_STACK", "$path": "in.fifo"},
   "stdout": {"$env": "AOS_STACK", "$path": "out.jsonl"}, "stdout_append": true}
  ```

  `aos-daemon-ctl add --name bob <abs>/bob -- --resume <id>` → daemon 起 `aos-exec <abs>/bob --resume <id>`（aos-daemon-ctl 剝掉 `--`）→ `claude … --resume <id>`。沒有 `--` 參數就是新對話。`stderr` 不寫＝daemon 給的小格 `stderr.txt`。
- **bob 的小格 `$AOS_DAEMON_STACK/loops/bob/`** 裡有：`in.fifo`（控制器在 add 之前 `mkfifo`——inst 的 `open` 不建 FIFO、路徑不在＝`OpenFailed` 退 1；aos-daemon-ctl `--ws` 也是先替子項把小格建好，同一個慣例）、`out.jsonl`（claude 原汁事件流，一行一事件、追加不重寫；bob 的紀錄、不是成果，決定 26）、`stderr.txt`。**控制器寫進 bob 小格的只有 FIFO 這一個檔，而且是在 bob 存在之前**——叫人的那一方替被叫的準備小格（P-17），bob 自己只看 `$AOS_STACK`、不知道上面有誰（[衝突 7](13-衝突-7-控制器建-bob-小格裡的-F.md#衝突-7控制器建-bob-小格裡的-fifo讀-bob-小格的-outjsonl)）。
- **等新訊息＝stdin 阻塞在 FIFO 上**：沒讀到下一行就什麼都不做、不花錢（②）。沒有輪詢、沒有自己寫的循環。**只要寫端還開著它就一直在**（②）；寫端全關才 EOF 退 0（⑫）；SIGTERM 立刻退 143（⑧）。
- **為什麼 FIFO 不會在睡醒之間出事**：FIFO 的寫端被控制器行程握著整個壽命；bob 被收掉（睡）時只是沒有讀端——這時寫會 EPIPE，所以 `relay` 只在 bob 在表上、而且探針成功時才寫（第 3 節 ②）；bob 再起來 `open(O_RDONLY)` 時已有寫端，立刻回來、接著讀。管子裡不會留下沒人讀的半截（沒有讀端時 `relay` 根本不寫）。
