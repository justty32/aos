# daemon：所有 cpu 的父行程（第 1 版，2026-09-23 定稿）

← [proto5 README](../README.md)｜範式：[cpu.md](cpu.md)｜客戶：[kernel](kernel.md)｜跑一次：[aos-exec.md](aos-exec.md)

> 2026-09-23 重架構第三份；同日照 astra 第二輪 D 清單（18 題）與第三輪（D3／X3／C3）改過。
> 2026-09-23 定稿並已實作：[`aos_daemon.py`](../lib/aos_daemon.py)（入口 `aos-daemon`）。舊 daemon-home.md／aos-daemon.md 已刪（副本在 [proto5.1/spec/](../../proto5.1/spec/)）。
> 已拍板的前提在 §8，我自己選的在 §9。
> 2026-09-24 實作補記：依實作審查回寫，見 [notes/2026-09-23-rearch/impl-review-report.md](../notes/2026-09-23-rearch/impl-review-report.md)；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。

一句話：**daemon 只管 cpu 行程的生死——啟動、重拉、停止，也就是當爸爸。誰叫它把一個 aos-exec 目標拉起來當孩子，
它就拉；孩子死了看要不要再拉；要停就照階梯把孩子都停掉。** 它不認識 kernel、不看孩子在做什麼、不轉發任何工作。
它自己的家也照 [cpu 範式](cpu.md)長：`info`／`state`／`requests`／`responses`，訊息是 JSON-RPC。

---

## 0. 名詞（白話）

跟 cpu 範式共用的詞（inst、目標、request、主人、控制 pipe、`go`、EOF、close-on-exec、process group、TERM／KILL…）在 [cpu.md §0](cpu.md)，這裡只列 daemon 自己的。

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

## 1. 家

```text
D/
  info.json           身分與設定；人寫的
  state.json          孩子表；daemon 寫的
  requests/ responses/
  daemon.log          daemon 自己的 stderr
  .daemon.lock        整個系統唯一的一把鎖（§6.1）
```

家由 `--home`，其次 `AOS_DAEMON_HOME`，再其次 `~/.aos-daemon` 決定。主人是 `aos-daemon` 這個行程；
外人只能放 request、放 ack，`state.json` 隨便偷看（kernel 就是偷看它來知道孩子活不活）。
孩子的家不在這裡——孩子的家是它自己的目標說了算（kernel 的 cpu 在 `K/cpus/<name>/`）。

**`name` 的範圍是整個 daemon**：兩個 kernel 想共用一個 daemon，cpu 名就不能撞（撞了是 `NameTaken`，§3）。

**外人怎麼知道 daemon 活不活**：對 `.daemon.lock` 試拿非阻塞的**共享** flock——拿不到＝daemon 正持著獨占鎖＝活著；
拿到了立刻放掉＝沒有 daemon。不看 `state.json` 的 pid（daemon 被 KILL 檔不會更新）。

### 1.1 `info.json`

```json
{"_metainfo": {"_type": "daemon", "_version": 1},
 "poll_ms": 20, "restart_delay_ms": 1000, "stop_wait_ms": 5000, "kill_wait_ms": 5000}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `poll_ms` | 正整數 | 20 | 一圈看一次 requests／孩子有沒有死的間隔 |
| `restart_delay_ms` | 非負整數 | 1000 | 孩子死了到再拉之間至少隔多久（擋崩潰迴圈空轉） |
| `stop_wait_ms` | 非負整數 | 5000 | 停機階梯第一段：pipe 說 stop 之後等多久才 TERM |
| `kill_wait_ms` | 非負整數 | 5000 | 第二段：TERM 之後等多久才 KILL |

整份解指示詞，中心是 D；沒有 `$opt`。daemon 啟動時沒有 info 就寫預設的，有就驗。

### 1.2 `state.json`

```json
{"pid": 100, "stopping": false,
 "current": null,
 "children": {
   "k": {"target": "/abs/K/cpus/k/inst.json", "dir_target": ".aos/inst.json", "restart": true,
         "pid": 2345, "alive": true, "state": "running", "exits": 0, "last_exit": null, "since": 1790000000.0}}}
```

| 鍵 | 意思 |
|---|---|
| `pid` | daemon 的 PID；正常停機時寫 0 |
| `stopping` | 整個 daemon 收過 stop（§5） |
| `current` | 正在處理的 request（範式 §2 那格），daemon 也是一個家 |
| `children.<name>` | `spawn` 給的 `target`／`dir_target`／`restart`；現在的 `pid`（死了是上一個）；`alive`；`state` 是 `running`／`killing`／`dead`；`exits` 死過幾次；`last_exit` 上次的退出碼；`since` 這一代拉起來的 epoch 秒 |

孩子表只在變動時寫（spawn、死、重拉、kill、停機），閒著不重寫。表裡的是**身分**（誰、哪個目標、pid、活不活），
重啟後只拿來找上一任的孩子（§6.1），不拿來接手。重拉的倒數、階梯走到哪一段這種**執行中的東西**只在記憶體，
daemon 崩了就沒了，也不需要——重啟後孩子表清空。

（09-24 補）`last_exit` 與重拉判定只用孩子實際的退出碼；exit 檔寫失敗另記 `WriteFailed`，不改退出碼，
也不因此重拉正常退出的孩子。

## 2. 孩子怎麼拉

`spawn` 的 `target` 照 [aos-exec](aos-exec.md) 讀（三種目標、base、指示詞都照它）——**每次拉都重讀**，
包括重拉；檔被改了就照新的拉、檔不見了就 `SpawnFailed`。串流有兩點不同：

- **fd 0、fd 1 一律接成控制 pipe**（範式 §3）：fd 0 daemon 寫、孩子讀；fd 1 孩子寫、daemon 讀。
  inst 裡寫了 `stdin`／`stdout` ＝ `-32602`（會被接管，寫了就是誤會）。stderr 照 inst（沒寫＝/dev/null，
  kernel 替 cpu 寫的 inst 是接 `cpu.log`）。
- 孩子放進**自己的 process group**，但**同一個 session**：終端的 Ctrl-C 只打到 daemon，由 daemon 走階梯；
  daemon 死了孩子不會被 SIGHUP 帶走，靠 pipe EOF 自己溫和停。

**拉的順序（`go` 握手，範式 §6.1）**：fork → **寫孩子表**（pid、`running`）→ 往它的 fd 0 寫一行
`{"jsonrpc":"2.0","method":"go"}` → 寫回音。孩子等到 `go` 才開始碰它的家；daemon 崩在寫表之前，
孩子讀到的是 EOF、什麼都沒碰就退——不會有「沒人記得的孤兒還在改家」。崩在寫表之後、回音之前：
孩子在表裡、正常在跑，客戶收不到回音會重送 `spawn`，同名同目標 → 回它的 pid（冪等）。

**pipe 端點誰拿著**（範式 §5.1 要求「寫端不能漏」）：每條 pipe 的四個端點都在 daemon 手上開的，
全部標 close-on-exec；拉孩子時只把它自己的讀端／寫端 `dup2` 到 fd 0／1，其他一律不傳（`close_fds`）。
所以 A 孩子拿不到 B 孩子的寫端，B 的 EOF 不會被 A 卡住。孩子那邊再把 fd 0／1 搬走、標 close-on-exec，
是範式 §6.1 的事，孫子拿不到。孩子死了 daemon 就關它那兩個端點。

**pipe 怎麼讀寫**：daemon 忽略 `SIGPIPE`；兩條都用非阻塞 I/O，不讓任何一個孩子卡住主迴圈。
fd 1 那條讀走就丟，不拿來做決定（現在孩子不會往上寫；不讀會塞住孩子，所以要讀）。
fd 0 那條只寫 `go` 跟 `stop` 各一行；寫失敗（EPIPE）＝孩子那頭讀端關了＝它在死的路上或已經死了，
階梯直接跳到下一階（EPIPE 不證明它死了，只證明它不聽了）。

`target` 讀不到、inst 壞掉、起不來（aos-exec 的 kind=aos）：`spawn` 回 `error.code=-32000`、`data.code="SpawnFailed"`，
`message` 帶 aos-exec 那一行（含它的代號）；不登記。
（09-24 補）target 不存在（不管是不是 `.json`）、資料夾目標缺 `dir_target` 指的檔，在這裡也一律是 `SpawnFailed`——
不照同步 aos-exec 分成用法錯；只有 inst 顯式寫了 `stdin`／`stdout` 的 `-32602` 不變。起不來時不造 pid、不寫 exit 檔。

**誰能當孩子**：只有遵守範式 §6.1 控制 pipe 契約的程式（等 `go`、認 `stop`、EOF 就溫和停）——現在就是 `aos-cpu`。
一般工作程式不是 daemon 的孩子，是 exec cpu 跑的。

## 3. method（`D/requests/`）

| method | params | 回音 |
|---|---|---|
| `spawn` | `name` 必填（合法檔名）；`target` 必填（絕對路徑）；`dir_target` 可省；`restart` 布林，預設 false | `{"pid"}`。看同名的那筆：**沒有**＝拉、登記、回新 pid。**有、`target`＋`dir_target` 都一樣**：`running`＝什麼都不做、回它的 pid（`restart` 不同就更新成新的）；`dead`＝取消等待、現在拉、回新 pid；`killing`＝`-32000`／`Killing`。**有、目標不一樣**＝`-32000`／`NameTaken`（不管活不活）。起不來＝`SpawnFailed` |
| `kill` | `name` 必填 | `{"pid"}`，立刻回。`running`＝`state=killing`、走 §5 的階梯；`dead`＝取消重拉、直接從表拿掉；`killing`＝已經在走，不重設期限。死透了從表裡拿掉、**不重拉**。不在＝`NotFound` |
| `stop` | notification | 整個 daemon 停機（§5） |
| `ack` | 範式 §3.3 | 別人收了 `D/responses/` 的回音要放 ack |

沒有 `ls`：偷看 `state.json`。`stopping` 期間 `spawn` 一律回 `-32000`／`Stopping`；`kill` 照常。
params 形狀不合＝`-32602`。回音、原單、ack 的處理照範式 §6.3；daemon 自己崩在中間，重啟照範式 §6.2 對帳
（`current` 那格就是為這個）。

## 4. 一圈

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

## 5. 停機

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
kernel 改綁另一個 daemon（`boot --daemon D2`）：**不支援交接**，舊 daemon 的孩子還在它那邊；要換就先把舊的停掉。

## 6. 主人的一生

```text
aos-daemon [--home D]                       # 跑 daemon
aos-daemon stop [--home D] [--wait-ms N]    # （09-24 補）放 stop、等它退出
aos-daemon -h ／ aos-daemon stop -h
```

（09-24 補）`stop`：先用 flock 探測 daemon 活不活——**不活就不放檔**（放了會讓下一任一開機就停）、印 `not running`、退 0；
活的就照範式 §3.1 往 `D/requests/` 放一則 `stop-*.json` notification，等到 flock 探測不到它、印 `stopped`、退 0。
`--wait-ms` 預設 30000，逾時 stderr `Timeout`、退 1（stop 已放、不撤回）。

### 6.1 啟動

1. 建家（缺的目錄）、讀驗或寫預設 `info.json`；忽略 `SIGPIPE`。
2. 拿 `.daemon.lock` 的獨占 flock（持到退出）。拿不到＝同家已有一支 daemon 在跑 → `AlreadyRunning`、退 1。
   這是整個系統唯一的一把鎖：它綁的是 daemon 行程的壽命（行程死鎖就消失），不是跨檔交易，
   所以沒有「鎖沒人解」的問題；外人也靠它探測 daemon 活不活（§1）。
3. **等上一任的孩子死透**：讀舊 `state.json`，對每個記錄的 pid 用 `kill(pid, 0)` 看還在不在——在的
   就送 TERM、等 **`stop_wait_ms`＋`kill_wait_ms`**、還在就 KILL 整組，直到全部不在（這是接手專用的等法，
   跟 §5 正常停機的階梯不同：pipe 已經沒了，沒得先好好說）。注意兩件事：
   (a) 那個 TERM 對孩子來說可能是「第一次」（它還沒讀到 EOF）、只會溫和停，所以才等兩段加起來的時間，最後可能落到硬砍；(b) 上一任 daemon 死後它的孩子歸 init 管、死了 init 會收屍，
   所以 `kill(pid,0)` 看到「不在」就是真的不在了（09-24 補：不會收孤兒的 PID 1 環境，不在接手完成保證內）。pid 被別的程式重用的機率當作可忽略，寫在這裡讓人知道。
   上一任 fork 了、還沒寫表就死的孩子不在表裡——但它等不到 `go`、自己就退了（§2），不用找。
4. 照範式 §6.2 對帳自己的 `current`（上一任崩在處理哪則 request）。
5. 寫新 `state.json`（pid、`current` null、children 空）。孩子表**從空開始**：daemon 不收養；要什麼孩子由客戶再
   `spawn`。
6. 進 §4 的迴圈。

### 6.2 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 正常停機（§5 走完） |
| 1 | 家、info 讀驗、鎖（`AlreadyRunning`）、state 寫不進去；stderr 一行 `aos-daemon: <代號>: <白話>` |
| 2 | 用法錯 |

一則 request 自己的錯誤回在 response 裡，不影響退出碼。

## 7. 這份沒管的

適用範圍同範式 §8（同一台 POSIX 機器；fork／waitpid／flock／訊號都是 POSIX 的）。孩子在做什麼（kernel／cpu 範式）；誰該被拉、幾顆（kernel 的 `info.cpus`）；多機（以後 socket）。
沒有 `aos-daemon-ctl`：客戶端就是往 `D/requests/` 放檔，kernel 的 boot／tick 已經在做；人要看就 `cat D/state.json`，
要停就放一份 `stop-*.json` 或 Ctrl-C（09-24 補：或 `aos-daemon stop`，§6）。

## 8. 已拍板的前提（使用者定的，不重問）

daemon 是所有 cpu 的父行程、最單純；IPC 用 pipe，只管生死；`spawn` 有 `restart:true`；家照 cpu 範式、JSON-RPC；
同名不同目標＝`NameTaken`。

## 9. 我自己選的（等你確認）

沒翻案就照這樣實作。

1. **重拉只在非 0 退出、且沒被主動叫停**：退 0＝孩子自願停（kernel 的 stop、pipe EOF），daemon 不跟它作對；
   `kill`／`stop` 一定贏過重拉。
2. **重拉節流只有固定 `restart_delay_ms`**，沒有上限、沒有退避；一直死就看 `exits`。
3. **`go` 握手**：fork → 寫表 → `go`。多一行，換掉「沒人記得的孤兒」。
4. **孩子自己一個 process group、同一個 session**（舊版是 `setsid` 開新 session）：Ctrl-C 只打 daemon，
   階梯由 daemon 控制；daemon 死了孩子靠 EOF 停，不靠 SIGHUP。
5. **`.daemon.lock` 這把 flock 留著**，而且外人拿它探測 daemon 活不活：綁行程壽命的鎖不是我們要拿掉的那種鎖。
6. **啟動先等上一任的孩子死透**（`kill(pid,0)` 輪詢＋階梯，可能落到硬砍），孩子表從空開始、不收養。
7. **沒有 `aos-daemon-ctl`、沒有 `ls`**：放檔就是 ctl，偷看 state 就是 ls。
8. **`kill` 立刻回、非同步走階梯**；`dead` 的直接拿掉。
9. **階梯的 TERM 只給孩子本身、KILL 給整組**：TERM 要讓 cpu 自己做強制停（砍它的子程式、回 `stopped:true`）；
   KILL 是最後手段才掃整組。
10. **`spawn` 同步**：拉起來、登記、`go`、回音；失敗不登記；等價鍵是 `target`＋`dir_target`，`restart` 不同就更新。
11. **重拉每次重讀 target**，不用保存的副本。
12. **改綁 daemon 不支援交接**，先停舊的；**daemon 重啟後 kernel 要重 boot**。

## 實作補記（2026-09-24）

依 [實作審查報告](../notes/2026-09-23-rearch/impl-review-report.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §1.2：`last_exit`／重拉只看孩子實際退出碼，exit 檔寫失敗另記（審查 B-3）。
- §2：缺檔一律 `SpawnFailed`（A-1、B-2），程式同步改了。
- §6：新增 `aos-daemon stop` 子命令與 `-h`（LM Studio 真跑報告 ⑤-1）；§7 同步一句。
- §6.1：不收孤兒的 PID 1 環境在保證外（B-9）。
