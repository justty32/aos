← [daemon](README.md)｜[spec 總導航](../README.md)

# 4. 一圈

```text
處理 requests/ 裡的 ack- 與 stop-（範式 §6.3 那套）
處理其他 request（§3；spawn 是同步的：拉起來、登記、go、回音）
收屍：對每個 alive 的孩子 waitpid(WNOHANG)；死了 → alive=false、exits+1、last_exit、關它的 pipe 端點、寫 state
  restart=true 且 last_exit≠0 且 state 是 running（不是 killing）且 daemon 沒在 stopping → state=dead，記下「restart_delay_ms 之後再拉」
  否則 → 從表裡拿掉（killing 的、退 0 的、restart=false 的、daemon 在 stopping 的）
到期的 dead 孩子 → 再查一次 stopping（是就拿掉不拉）→ 再拉（重讀 target），成功 → running、寫 state；失敗 → log 一行、再等一輪 restart_delay_ms
推進停機階梯（§5）
睡 poll_ms
```

**重拉只在「非 0 退出、而且沒被主動叫停」時**：退 0 是孩子自己決定要停（收到 kernel 的 `stop-*.json`、
或 pipe EOF），daemon 不跟它作對；被訊號砍死（128+N）、崩掉、回 1 都算非 0。**`kill`／`stop` 一定贏過重拉**：
標了 `killing`、或 daemon 在 `stopping`，死了就拿掉。重拉之間至少隔 `restart_delay_ms`，沒有上限、沒有退避——
一直死就一直每秒拉一次，`exits` 看得出來，要不要管是人的事。
（cpu 因為磁碟壞掉每次開機對帳都退 1，就是這種：一直拉、一直退，log 會一直長，這是接受的。）

孩子表是 daemon 的記憶，不是排程狀態：孩子在做什麼、忙不忙，daemon 不知道也不記。
**孩子是不是原來那個**：daemon 只認自己 `fork` 出來的 pid、只 `waitpid` 它們；`kill(pid,0)` 只在啟動找上一任的孩子時用（§6.1）。
