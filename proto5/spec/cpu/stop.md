← [cpu](README.md)｜[spec 總導航](../README.md)

# 5. 停下來

三種「停」，由輕到重。四個溫和停的來源都只是**設旗標**；旗標什麼時候被看到、看到做什麼，在 §6.3 的迴圈裡寫死。

## 5.1 溫和停：`stop`

| 來源 | 長怎樣 |
|---|---|
| 控制 pipe | 一行 `{"jsonrpc":"2.0","method":"stop"}`；不是 `go`／`stop` 的行一律忽略。半行先留著等下一段；EOF 時剩下的半行丟掉 |
| 控制 pipe EOF | 所有寫端關了（正常就是父行程死了）。拉起它的人**不可以**把寫端漏給別的孩子，不然永遠等不到 EOF |
| 檔案 | `requests/stop-*.json`，內容同上；任何人都能放 |
| 訊號 | 第一次 SIGTERM 或 SIGINT（handler 只設旗標） |

旗標一設，主人就：

1. **不再取新的**（§6.3 的迴圈在「掃完 ack-／stop-」之後、「取單」之前一定重看旗標）。`requests/` 裡
   其他單原地留著，下一任主人啟動會接著做；沒人接就一直在。
2. 手上那件**照常做完**：等它自己結束或 `timeout_ms` 到，回音照常寫（§6.3 的順序不變）。
3. `stop-*.json` 全刪（notification 沒回音）。
4. 寫 `state.json`（current=null），退出碼 0。

閒著時收到就直接 3、4。所以「溫和停」最慢等一件工作；工作有 `timeout_ms` 就有上限、沒有就沒有。

（09-24 補）控制 pipe 的一行要算數，得是物件、`jsonrpc` 為 `"2.0"`、`method` 是字串；有 `id` 鍵的話型別要合法（字串、數字、null）；
`stop` 不能帶 `id`（必須是 notification）。`go` 帶合法 id 容忍放行。不合的整行忽略，cpu 的 stderr 記一行 `BadControl`。

## 5.2 強制停：第二次訊號

**已經處理過第一次**（旗標已設）之後再收到 SIGTERM／SIGINT：子程式還在跑 → 對它的 process group
發 TERM、寬限 2 秒、再 KILL；回音**照常寫**，`result.stopped=true`、`code` 是子程式實際的退出碼
（通常 143 或 137）、`kind` 照實。子程式已經自己結束、只是回音還沒寫 → 不砍、`stopped=false`、結果算數。
之後跟 5.1 的 3、4 一樣退出。
（同種訊號連發太快 Linux 可能合併成一次，所以「第二次」是指主人已經處理完第一次之後才到的那次。
父行程死了、cpu 還沒讀到 EOF 就先收到別人的 TERM，那個 TERM 就是「第一次」，只會溫和停——
接手的人得有再等一段、最後硬砍的心理準備，見 [daemon §6.1](../daemon/lifecycle.md)。）

砍的是「子程式那一組」；脫離這組的後代砍不到，跟 timeout 一樣，不另做 kill-tree。
收件者看到 `stopped:true` 就知道這次結果不算數。

## 5.3 硬砍：主人被 KILL

主人來不及做任何事。下一任主人開機對帳（§6.2）照表處理：回音已經發出去的就留著，
還沒發的補一則 `Interrupted`，原單還沒開始的照常做。子程式如果還活著沒人管（在保證外）。

## 5.4 誰負責發

- **kernel**：往它管的每顆 cpu 放 `stop-*.json`（[kernel.md §3](../kernel/tick.md)），不發訊號。
- **daemon 停機**：對每個孩子的控制 pipe 寫 `stop`；等；逾時才走訊號（階梯在 [daemon §5](../daemon/shutdown.md)）。
- **人**：終端裡 Ctrl-C 一次＝溫和、兩次＝強制。
