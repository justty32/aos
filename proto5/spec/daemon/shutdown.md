← [daemon](README.md)｜[spec 總導航](../README.md)

# 5. 停機

三個來源：`stop` request（檔案）、SIGTERM／SIGINT 打到 daemon、`kill` 針對一個孩子。前兩個把
`stopping` 設起來、對**每個** `running` 的孩子同時開始階梯（`dead` 的直接拿掉）；第三個只對那一個（`killing`）。
階梯每個孩子各自計時、並行：

| 時間 | 做什麼 | 孩子那邊（範式 §5） |
|---|---|---|
| 0 | 往它的 fd 0 寫一行 `{"jsonrpc":"2.0","method":"stop"}`（EPIPE＝跳下一階） | 溫和停：做完手上那件、回完音就退 |
| `stop_wait_ms` 後還活著 | SIGTERM 給它（**只給孩子本身**，不給整組） | 孩子已經在溫和停，這是第二次＝強制停（第一次就是上一階從 pipe 送的 `stop`）：砍它的子程式那組、回 `stopped:true`、退 |
| 再 `kill_wait_ms` 後還活著 | SIGKILL 給**它的 process group** | 硬砍；它手上那件下次開機對帳補 `Interrupted` |

最慢 `stop_wait_ms`＋`kill_wait_ms` 之後一定 KILL（孩子自己那 2 秒寬限落在第二段裡，不另外加）；每個孩子各自算、不累加。
孩子任何時候退出就收屍、不再發下一階。全部孩子都不在了：`children` 清空、`pid` 寫 0、放掉鎖、退 0。
停機途中 daemon 自己被 KILL：孩子的 pipe EOF 讓它們自己溫和停，只是沒人等它們；沒 `timeout_ms` 的工作
可能等很久，那是那件工作的事。停機之後才到的 request／ack：留在 `requests/`，下一支 daemon 啟動接著處理。

**跟 kernel 的 stop 的關係**：kernel 的 stop 是「排程收乾淨再叫 cpu 停」，cpu 退 0、daemon 不重拉，
之後孩子表裡就沒有它們了；再來人叫 daemon stop，階梯沒東西可走、直接退。反過來先叫 daemon stop：
cpu 在階梯裡停——溫和停的那些手上那件做完、回音有寫，kernel 下次 boot 照常收；被 TERM／KILL 的那些
才會是 `stopped:true` 或 `Interrupted`——能用，但不乾淨。**順序是先 kernel、後 daemon**，這是給人的慣例，daemon 不強制。
**daemon 重啟過（孩子表清空）之後，kernel 要重新 boot**——沒人會替它放第 1 格。
kernel 改綁另一個 daemon（`aos-kernel boot --daemon-target D2`）：**不支援交接**，舊 daemon 的孩子還在它那邊；要換就先把舊的停掉。
