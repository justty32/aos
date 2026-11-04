← [入口](README.md)｜涵蓋：規劃 › 1. 誰當父：daemon 當父、控制器經 daemon 管、2. 「exec」那半：bob 怎麼變成一直跑的｜上一份 [03-現況-查清的-不是規劃](03-現況-查清的-不是規劃.md)｜下一份 [05-3-loop-那半-控制器](05-3-loop-那半-控制器.md)

### 1. 誰當父：daemon 當父、控制器經 daemon 管

- **daemon 當 bob 與控制器兩個的父**；bob、控制器都是 daemon 表上的一列（`aos-daemon-ctl ls` 看得到），各有小格。控制器起 bob＝`aos-daemon-ctl add --name bob … [-- --resume ID]`，收 bob＝`aos-daemon-ctl rm bob`，看 bob＝讀 daemon 的名單窗有沒有 `bob`。控制器不當 bob 的父程式（aos-loop 的身體活不過一輪；要當父就得重寫一個小 daemon，C-56；使用者 11-01「明明現有的機制組合一下就能搞定」）；daemon 也不加「綁組」key（等第二個需要的場合）。
- **同生共死靠四條各自現成的路**：
  1. **控制器沒了 → bob 跟著走**：控制器行程握著 FIFO 唯一的寫端，不論怎麼死（停、`rm`、崩、SIGKILL），寫端一關 bob 就讀到 EOF，**答完手上那題以 0 結束**（⑫）。
  2. **bob 沒了 → 控制器跟著停**：`relay` 每輪讀一次 daemon 的名單窗；bob 該在卻不在表上＝死了 → stderr 一行、退 1 → aos-loop 以 1 結束（P-20）。
  3. **bob 活著卻沒用 → 控制器收它、自己也停**：`result.subtype` 是 `error_max_budget_usd`（⑦）→ `aos-daemon-ctl rm bob`、stderr 一行、退 1。
  4. daemon 沒了 → 它收工時全部送 SIGTERM（P-36），兩個一起走。
- **「結束由控制器明確送 SIGTERM」**用在控制器**主動**要 bob 停的場合（3 與第二版的睡）；控制器**自己**被停時 bob 走 1 的 EOF 路（[方向題 1](13-衝突-7-控制器建-bob-小格裡的-F.md#方向題-1控制器自己被停時bob-走-eof答完退還是先-rm-bob立刻退)）。

### 2. 「exec」那半：bob 怎麼變成一直跑的

- **還是 `claude -p`，多旗標** `--input-format stream-json --output-format stream-json --verbose --replay-user-messages`（最後一個是實作時加的，[代定](10-實作時代定-11-02.md#實作時代定11-02)）；其餘照現有 bob，`--max-budget-usd 2`（[衝突 6](02-衝突與方向題的裁定-11-02-晚-使用.md#衝突與方向題的裁定11-02-晚使用者)）；`system.txt` 多兩句（「你會一直在，一題接一題，答完等下一題」「每題答完用一兩句說你做了什麼」）。
- **入口是一張靜態單子**，`stdin`／`stdout` 都指自己的小格；`--resume` 靠 aos-exec 把 args 接在 `argv` 後面，不用小殼：

  ```json
  // agents/resident_bob/bob/_entry.json
  {"argv": ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--model", "haiku", "--tools", "Read,Write,Edit,Glob,Grep", "--permission-mode", "acceptEdits",
            "--strict-mcp-config", "--add-dir", {"$env": "AOS_WS"}, "--append-system-prompt-file", "system.txt"],
   "stdin":  {"$env": "AOS_STACK", "$path": "in.fifo"},
   "stdout": {"$env": "AOS_STACK", "$path": "out.jsonl"}, "stdout_append": true}
  ```

  `aos-daemon-ctl add --name bob <abs>/bob -- --resume <id>` → `claude … --resume <id>`；沒有 `--` 參數就是新對話。`stderr` 不寫＝daemon 給的小格 `stderr.txt`。
- **bob 的小格**裡有：`in.fifo`（控制器在 add 之前 `mkfifo`——inst 的 `open` 不建 FIFO，路徑不在＝`OpenFailed`）、`out.jsonl`（claude 原汁事件流，追加不重寫；是紀錄、不是成果，決定 26）、`stderr.txt`。**控制器寫進 bob 小格的只有 FIFO 這一個檔，而且在 bob 存在之前**（P-17；[衝突 7](13-衝突-7-控制器建-bob-小格裡的-F.md#衝突-7控制器建-bob-小格裡的-fifo讀-bob-小格的-outjsonl)）。
- **等新訊息＝stdin 阻塞在 FIFO 上**，不花錢（②）；寫端開著就一直在，寫端全關才 EOF 退 0（⑫），SIGTERM 立刻退 143（⑧）。
- **睡醒之間 FIFO 不會出事**：寫端被控制器握整個壽命；bob 被收掉時沒有讀端、寫會 EPIPE，所以 `relay` 只在 bob 在表上而且探針成功時才寫；bob 再起來 `open(O_RDONLY)` 時已有寫端，立刻接著讀。
