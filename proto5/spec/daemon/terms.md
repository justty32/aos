← [daemon](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

跟 cpu 範式共用的詞（inst、目標、request、主人、控制 pipe、`go`、EOF、close-on-exec、process group、TERM／KILL…）在 [cpu.md §0](../cpu/terms.md)，這裡只列 daemon 自己的。

| 詞 | 意思 |
|---|---|
| 孩子 | daemon 拉起來的子行程，每個有一個 `name`。daemon 只管它活不活，不管它在做什麼 |
| 階梯 | 停一個孩子的三段式，一段比一段狠：先從 pipe 好好說 `stop` → 還活著就 SIGTERM → 再不走就 SIGKILL；段跟段之間有等待時間 |
| 孩子表（`children`） | daemon 的記憶：誰是誰、pid 多少、活不活、死過幾次。它**不是**排程狀態，孩子忙不忙 daemon 不知道也不記 |
| `.daemon.lock`／flock | 一把檔案鎖，由「持有它的行程還活著」撐著，行程一死鎖就自動消失，所以沒有「鎖沒人解」的問題。拿不到＝同一個家已經有一支 daemon 在跑；外人也拿它探測 daemon 活不活 |
| 重拉（`restart`） | 只有 `restart:true`、非 0 退出、而且沒被主動叫停（`kill`／daemon `stop`）的孩子，才再拉一次同一個目標。退 0 是孩子自願停，daemon 不跟它作對 |
| 崩潰迴圈／退避 | 「一拉起來就死、死了又拉」的空轉。這裡只用固定的 `restart_delay_ms` 隔開，沒有「越死越久才拉」的退避 |
| `stopping`（daemon 的） | 整個 daemon 收過 stop、正在把所有孩子停掉。這期間 `spawn` 一律拒絕、不重拉 |
| `killing`（孩子的） | 這一個孩子被 `kill` 了、正在走階梯；死透就從表裡消失、不重拉 |
| `dead`（孩子的） | 非 0 死了、在等 `restart_delay_ms` 到了重拉 |
| `spawn` | 「把這個目標拉起來當孩子」。同名、同 `target`＋`dir_target` 的孩子已經在跑＝沿用它的 pid，只把 `restart` 更新成新的 |
| process group／session | 兩層分組。孩子自己一個 process group＝訊號可以只打它那一組；但仍在同一個 session（同一個終端底下）＝終端的 Ctrl-C 打到前景那組（daemon），不會直接打到孩子，停孩子一律由 daemon 走階梯 |
| SIGHUP | session 的頭沒了（終端關掉）時系統發給同 session 行程的訊號，預設會把它們帶走。這裡不靠它：daemon 死了孩子是靠 pipe EOF 自己停 |
| 冪等 | 同一則做一次跟做兩次結果一樣；所以呼叫者等回音等到逾時、重送一次，也不會多拉一支 |
| 收屍（`waitpid`） | 子行程死掉之後，父行程要去把它的退出碼收回來，它才真的從系統消失（不收就留成殭屍，占著行程表的一格） |
| `WNOHANG` | `waitpid` 的旗標：「有死掉的就給我、沒有就馬上回來，別卡住我」。daemon 一圈問一次，問完繼續做別的 |
| 128+N | 被訊號 N 砍死的行程，退出碼慣例記成 128+N（SIGTERM 是 15→143、SIGKILL 是 9→137）。算非 0，符合上面重拉條件的會被重拉 |
| SIGTERM／SIGINT／SIGKILL | TERM＝「請你結束」，程式可以先收尾；INT＝Ctrl-C，跟 TERM 同級；KILL＝直接砍掉，程式擋不了也來不及收尾 |
| SIGPIPE／EPIPE | 往一條讀端已經關掉的 pipe 寫東西：預設會收到 SIGPIPE 被打死；忽略這個訊號之後只會得到 EPIPE 錯誤＝孩子那頭沒人了 |
| `kill(pid, 0)` | 不送訊號、只拿 kill 這個系統呼叫問「這個 pid 還在不在」的用法。啟動時拿它輪詢上一任的孩子死透了沒。「在」不等於「還在做事」（殭屍也算在） |
| pid 被重用 | 行程號碼會循環使用，久了可能有別的程式撿到同一個號。這裡當作機率可忽略，寫出來讓人知道 |
| 收養 | 接手上一任 daemon 留下的孩子、當成自己的孩子繼續管。**這份不做**：孩子表從空開始，要什麼孩子由客戶再 `spawn` |

---
