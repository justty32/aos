← [daemon](README.md)｜[spec 總導航](../README.md)

# 5. 停機與階梯

（2026-09-24 proto5-2 池式納入：階梯一批一批做；`halt` 後 `pool.json` 留著，重開自動拉回。）

會讓孩子走階梯的四個來源：`stop` request（檔案）、SIGTERM／SIGINT 打到 daemon、`kill`（§3，砍掉重來）、宣告縮小（不再是成員的 `running`）。
前兩個把 `stopping` 設起來、所有 `running` 的進階梯，`pending`／`dead`／`failed` 的直接拿掉。

## 階梯

| 時間 | 做什麼 | 孩子那邊（[cpu §5](../cpu/stop.md)） |
|---|---|---|
| 0 | 往它的 fd 0 寫一行 `{"jsonrpc":"2.0","method":"stop"}`（非阻塞；EAGAIN 下一圈再寫；EPIPE＝跳下一階） | 溫和停：做完手上那件、回完音就退 |
| `stop_wait_ms` 後還活著 | SIGTERM 給它（**只給孩子本身**，不給整組） | 第二次＝強制停：砍它的子程式那組、回 `stopped:true`、退 |
| 再 `kill_wait_ms` 後還活著 | SIGKILL 給**它的 process group** | 硬砍；它手上那件下次開機對帳補 `Interrupted` |

最慢 `stop_wait_ms`＋`kill_wait_ms` 之後一定 KILL（孩子自己那 2 秒寬限落在第二段裡，不另外加）。
孩子任何時候退出就收屍、不再發下一階。

**一批一批做**：同一圈要收的孩子是一批——這一圈就對整批每個孩子的 fd 0 寫 `stop`，整批共用一個到期時間；
到期時只看那一批裡還活著的，一起送 TERM，下一個到期再一起 KILL。到期時間放在按時間排的佇列裡，每圈只拿到期的批，不逐顆檢查。
所以 `halt` 一萬個孩子是「一圈寫一萬行 stop、等 5 秒、一圈送還活著的 TERM、等 5 秒、再一圈 KILL」，而不是一萬個各自的計時器。

## daemon 停機（`halt`／訊號）

`stopping` 設起來、所有 `running` 的進一批階梯、`pending`／`dead`／`failed` 的直接拿掉、`scale` 回 `Stopping`、`kill` 照常、不再拉任何孩子。
全部孩子不在了：成員的 kids 檔改成 `pending`（pid null、streak 0，gen／exits 照留），非成員的刪掉；`pid` 寫 0、放鎖、退 0。
**`pool.json` 留著**——下次開 daemon 會照宣告把孩子拉回來（§6.1；09-24 Q8 照草稿）。不想要它們回來，就先讓 owner 把池縮到 0（kernel 的 `halt` 就會這樣做）。
停機途中 daemon 自己被 KILL：孩子的 pipe EOF 讓它們自己溫和停，只是沒人等它們；沒 `timeout_ms` 的工作可能等很久，那是那件工作的事。
停機之後才到的 request／ack：留在 `requests/`，下一支 daemon 啟動接著處理。

## 跟 kernel 的停機的關係

kernel 的 `halt` 是「排程收乾淨，再把每個池縮到 0」（[kernel §6 停機](../kernel/boot.md)）：池收完就從 daemon 消失，
之後再停 daemon 沒孩子可收、直接退，下次開 daemon 也不會拉任何東西，等 `aos-kernel boot` 重新宣告。
反過來先停 daemon：cpu 在階梯裡停——溫和停的那些手上那件做完、回音有寫；被 TERM／KILL 的那些才會是 `stopped:true` 或 `Interrupted`。
下次開 daemon 會照 `pool.json` 把池拉回來，kernel 的鏈多半接得上（不一定要 `aos-kernel boot`）。**建議先 kernel、後 daemon**，daemon 不強制。
kernel 改綁另一個 daemon：照 kernel 的搬池流程（[kernel §1.1](../kernel/info.md)），舊 daemon 那池縮到 0、消失後才換。
