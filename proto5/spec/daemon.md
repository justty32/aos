# daemon：所有 cpu 的父行程（第 1 版，**草稿**）

← [proto5 README](../README.md)｜範式：[cpu.md](cpu.md)｜客戶：[kernel](kernel.md)｜跑一次：[aos-exec.md](aos-exec.md)

> 2026-09-23 重架構第三份；同日照 astra 第二輪的 D 清單（18 題）補過。
> 舊 daemon-home.md／aos-daemon.md 等新的齊了一次換掉。已拍板的前提在 §8，我自己選的在 §9。

一句話：**daemon 只做一件事——當爸爸。誰叫它拉一份 inst 起來當孩子，它就拉；孩子死了看要不要再拉；
要停就照階梯把孩子都停掉。** 它不認識 kernel、不看孩子在做什麼、不轉發任何工作。
它自己的家也照 [cpu 範式](cpu.md)長：`info`／`state`／`requests`／`responses`，訊息是 JSON-RPC。

---

## 0. 名詞（白話）

跟 cpu 範式共用的詞（inst、request、主人、控制 pipe、EOF、close-on-exec、process group、TERM／KILL…）在 [cpu.md §0](cpu.md)，這裡只列 daemon 自己的。

| 詞 | 意思 |
|---|---|
| 孩子 | daemon 拉起來的子行程，每個有一個 `name`。daemon 只管它活不活，不管它在做什麼 |
| 階梯 | 停一個孩子的三段式，一段比一段狠：先從 pipe 好好說 `stop` → 還活著就 SIGTERM → 再不走就 SIGKILL；段跟段之間有等待時間 |
| 孩子表（`children`） | daemon 唯一的記憶：誰是誰、pid 多少、活不活、死過幾次。它**不是**排程狀態，孩子忙不忙 daemon 不知道也不記 |
| `.daemon.lock`／flock | 一把檔案鎖，由「持有它的行程還活著」撐著，行程一死鎖就自動消失，所以沒有「鎖沒人解」的問題。拿不到＝同一個家已經有一支 daemon 在跑 |
| 重拉（`restart`） | 孩子非 0 退出就再拉一次同一個 target。退 0 是孩子自願停，daemon 不跟它作對 |
| 崩潰迴圈／退避 | 「一拉起來就死、死了又拉」的空轉。這裡只用固定的 `restart_delay_ms` 隔開，沒有「越死越久才拉」的退避 |
| `stopping`（daemon 的） | 整個 daemon 收過 stop、正在把所有孩子停掉。這期間 `spawn` 一律拒絕 |
| `killing`（孩子的） | 這一個孩子被 `kill` 了、正在走階梯；死透就從表裡消失、不重拉 |
| `spawn` | 「把這份 inst 拉起來當孩子」。同名同 target 已經活著就什麼都不做、直接回它的 pid |
| process group／session | 兩層分組。孩子自己一個 process group＝訊號可以只打它那一組；但仍在同一個 session（同一個終端底下）＝終端的 Ctrl-C 打到前景那組（daemon），不會直接打到孩子，停孩子一律由 daemon 走階梯 |
| SIGHUP | session 的頭沒了（終端關掉）時系統發給同 session 行程的訊號，預設會把它們帶走。這裡不靠它：daemon 死了孩子是靠 pipe EOF 自己停 |
| 冪等 | 同一則做一次跟做兩次結果一樣；所以呼叫者等回音等到逾時、重送一次，也不會多拉一支 |
| 收屍（`waitpid`） | 子行程死掉之後，父行程要去把它的退出碼收回來，它才真的從系統消失（不收就留成殭屍，占著行程表的一格） |
| `WNOHANG` | `waitpid` 的旗標：「有死掉的就給我、沒有就馬上回來，別卡住我」。daemon 一圈問一次，問完繼續做別的 |
| 128+N | 被訊號 N 砍死的行程，退出碼慣例記成 128+N（SIGTERM 是 15→143、SIGKILL 是 9→137）。都算非 0，所以會被重拉 |
| SIGTERM／SIGINT／SIGKILL | TERM＝「請你結束」，程式可以先收尾；INT＝Ctrl-C，跟 TERM 同級；KILL＝直接砍掉，程式擋不了也來不及收尾 |
| `kill(pid, 0)` | 不送訊號、只拿 kill 這個系統呼叫問「這個 pid 還在不在」的用法。啟動時拿它輪詢上一任的孩子死透了沒 |
| pid 被重用 | 行程號碼會循環使用，久了可能有別的程式撿到同一個號。這裡當作機率可忽略，寫出來讓人知道 |
| 收養 | 接手上一任 daemon 留下的孩子、當成自己的孩子繼續管。**這份不做**：孩子表從空開始，要什麼孩子由客戶再 `spawn` |
| EPIPE | 往一條讀端已經關掉的 pipe 寫東西會得到的錯誤＝孩子那頭沒人了 |

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
孩子的家不在這裡——孩子的家是它自己的 inst 說了算（kernel 的 cpu 在 `K/cpus/<name>/`）。

**一個 daemon 家一次只服務一組叫得出名字的孩子**：`name` 的範圍是整個 daemon。兩個 kernel 想共用一個 daemon，
cpu 名就不能撞（撞了是 `NameTaken`，§3）。

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
| `children.<name>` | `spawn` 給的 `target`／`dir_target`／`restart`；現在的 `pid`（死了是上一個）；`alive`；`state` 是 `running`／`killing`（被 `kill` 了，在走階梯）／`dead`（死了、在等重拉）；`exits` 死過幾次；`last_exit` 上次的退出碼；`since` 這一代拉起來的 epoch 秒 |

孩子表只在變動時寫（spawn、死、重拉、kill、停機），閒著不重寫。**表裡的每一筆都是持久的**，
沒有只在記憶體裡的東西；daemon 崩了重啟，表只拿來找上一任的孩子（§6.1），不拿來接手。

## 2. 孩子怎麼拉

`spawn` 的 `target` 照 [aos-exec](aos-exec.md) 讀（三種目標、base、指示詞都照它）——**每次拉都重讀**，
包括重拉；檔被改了就照新的拉、檔不見了就 `SpawnFailed`。串流有兩點不同：

- **fd 0、fd 1 一律接成控制 pipe**（範式 §3）：fd 0 daemon 寫、孩子讀；fd 1 孩子寫、daemon 讀。
  inst 裡寫了 `stdin`／`stdout` ＝ `-32602`（會被接管，寫了就是誤會）。stderr 照 inst（沒寫＝/dev/null，
  kernel 替 cpu 寫的 inst 是接 `cpu.log`）。
- 孩子放進**自己的 process group**，但**同一個 session**：終端的 Ctrl-C 只打到 daemon，由 daemon 走階梯；
  daemon 死了孩子不會被 SIGHUP 帶走，靠 pipe EOF 自己溫和停。

**pipe 端點誰拿著**（範式 §5.1 要求「寫端不能漏」）：每條 pipe 的四個端點都在 daemon 手上開的，
全部標 close-on-exec；拉孩子時只把它自己的讀端／寫端 `dup2` 到 fd 0／1，其他一律不傳（`close_fds`）。
所以 A 孩子拿不到 B 孩子的寫端，B 的 EOF 不會被 A 卡住。孩子那邊再把 fd 0／1 搬走、標 close-on-exec，
是範式 §6.1 的事，孫子拿不到。daemon 端：孩子死了就關它那兩個端點。

**fd 1 那條**：daemon 讀走就丟，不拿來做決定（現在孩子不會往上寫）；不讀會塞住孩子，所以要讀。
**fd 0 那條**：只寫 `stop` 一行；寫失敗（EPIPE）＝孩子那頭已經沒了，當它已經在死的路上，階梯直接跳到下一階。

`target` 讀不到、inst 壞掉、起不來（aos-exec 的 kind=aos）：`spawn` 回 `-32000`／`SpawnFailed`，
`data.code` 是 aos-exec 的代號、`message` 是它那一行 stderr；不登記。起來了才登記、才回 `{"pid"}`。
**副作用先於回音**：崩在「拉起來了、還沒寫表／回音」之間，那個孩子成了沒人記的孤兒——它讀到 EOF 會自己
溫和停；客戶收不到回音會重送 `spawn`，新 daemon 再拉一個（§6.1 先等孤兒死透）。

## 3. method（`D/requests/`）

| method | params | 回音 |
|---|---|---|
| `spawn` | `name` 必填（合法檔名）；`target` 必填（絕對路徑）；`dir_target` 可省；`restart` 布林，預設 false | `{"pid"}`。**同名、同 target 已活著＝什麼都不做、回它的 pid**（冪等，逾時後重送安全）；同名 `dead`（等重拉中）＝取消等待、現在拉、回新 pid；同名 `killing`＝`-32000`／`Killing`；同名但 **target 不同**＝`-32000`／`NameTaken`（不管活不活）；起不來＝`SpawnFailed` |
| `kill` | `name` 必填 | `{"pid"}`，立刻回；那個孩子 `state=killing`、走 §5 的階梯、**不重拉**、死透了從表裡拿掉。不在＝`NotFound` |
| `stop` | notification | 整個 daemon 停機（§5） |
| `ack` | 範式 §3.3 | 別人收了 `D/responses/` 的回音要放 ack |

沒有 `ls`：偷看 `state.json`。`stopping` 期間 `spawn` 一律回 `-32000`／`Stopping`；`kill` 照常。
params 形狀不合＝`-32602`。回音、原單、ack 的處理照範式 §6.3；daemon 自己崩在中間，重啟照範式 §6.2 對帳
（`current` 那格就是為這個），只是 `spawn` 的副作用不在對帳裡（上一段）。

## 4. 一圈

```text
處理 requests/ 裡的 ack- 與 stop-（範式 §6.3 那套）
處理其他 request（§3；spawn 是同步的：拉起來、拿到 pid 才回音）
收屍：對每個 alive 的孩子 waitpid(WNOHANG)；死了 → alive=false、exits+1、last_exit、關它的 pipe 端點、寫 state
  restart=true 且 last_exit≠0 且不是 killing 且 daemon 沒在 stopping → state=dead，記下「restart_delay_ms 之後再拉」
  否則 → 從表裡拿掉（killing 的、退 0 的、restart=false 的）
到期的 dead 孩子 → 再拉（重讀 target），成功 → running、寫 state；失敗 → log 一行、再等一輪 restart_delay_ms
推進停機階梯（§5）
睡 poll_ms
```

**重拉只在「非 0 退出」時**：退 0 是孩子自己決定要停（收到 kernel 的 `stop-*.json`、或 pipe EOF），
daemon 不跟它作對；被訊號砍死（128+N）、崩掉、回 1 都算非 0。重拉之間至少隔 `restart_delay_ms`，
沒有上限、沒有退避——一直死就一直每秒拉一次，`exits` 看得出來，要不要管是人的事。
（cpu 因為磁碟壞掉每次開機對帳都退 1，就是這種：一直拉、一直退，log 會一直長，這是接受的。）

**主動停 vs 重拉**：`kill`／`stop` 一定贏——標了 `killing` 或 `stopping` 的孩子死了不重拉。

孩子表是 daemon 的記憶，不是排程狀態：孩子在做什麼、忙不忙，daemon 不知道也不記。
**孩子是不是原來那個**：daemon 只認自己 `fork` 出來的 pid、只 `waitpid` 它們；`kill(pid,0)` 只在啟動找上一任的孩子時用（§6.1）。

## 5. 停機

三個來源：`stop` request（檔案）、SIGTERM／SIGINT 打到 daemon、`kill` 針對一個孩子。前兩個把
`stopping` 設起來、對**每個**孩子同時開始階梯；第三個只對那一個（`killing`）。階梯每個孩子各自計時、並行：

| 時間 | 做什麼 | 孩子那邊（範式 §5） |
|---|---|---|
| 0 | 往它的 fd 0 寫一行 `{"jsonrpc":"2.0","method":"stop"}`（EPIPE＝跳下一階） | 溫和停：做完手上那件、回完音就退 |
| `stop_wait_ms` 後還活著 | SIGTERM 給它（**只給孩子本身**，不給整組） | 孩子已經在溫和停，這是第二次＝強制停（第一次就是上一階從 pipe 送的 `stop`）：砍它的子程式那組、回 `stopped:true`、退 |
| 再 `kill_wait_ms` 後還活著 | SIGKILL 給**它的 process group** | 硬砍；它手上那件下次開機對帳補 `Interrupted` |

總預算＝`stop_wait_ms`＋`kill_wait_ms`＋孩子自己的 2 秒寬限，每個孩子各自算、不累加。
孩子任何時候退出就收屍、不再發下一階。全部孩子都不在了：`children` 清空、`pid` 寫 0、放掉鎖、退 0。
停機途中 daemon 自己被 KILL：孩子的 pipe EOF 讓它們自己溫和停，只是沒人等它們；沒 `timeout_ms` 的工作
可能等很久，那是那件工作的事。停機之後才到的 request／ack：留在 `requests/`，下一支 daemon 啟動接著處理。

**跟 kernel 的 stop 的關係**：kernel 的 stop 是「排程收乾淨再叫 cpu 停」，cpu 退 0、daemon 不重拉，
之後孩子表裡就沒有它們了；再來人叫 daemon stop，階梯沒東西可走、直接退。反過來先叫 daemon stop，
cpu 會在手上那件做完後退，kernel 的在途工作就會在下次 boot 時當 `Interrupted` 收、once 的客戶收到的是
`Interrupted`——能用，但不乾淨。**順序是先 kernel、後 daemon**，這是給人的慣例，daemon 不強制。
kernel 改綁另一個 daemon（`boot --daemon D2`）：**不支援交接**，舊 daemon 的孩子還在它那邊；要換就先把舊的停掉。

## 6. 主人的一生

```text
aos-daemon [--home D]
```

### 6.1 啟動

1. 建家（缺的目錄）、讀驗或寫預設 `info.json`。
2. 拿 `.daemon.lock` 的 flock（獨占、持到退出）。拿不到＝同家已有一支 daemon 在跑 → `AlreadyRunning`、退 1。
   這是整個系統唯一的一把鎖：它綁的是 daemon 行程的壽命（行程死鎖就消失），不是跨檔交易，
   所以沒有「鎖沒人解」的問題。
3. **等上一任的孩子死透**：讀舊 `state.json`，對每個記錄的 pid 用 `kill(pid, 0)` 看還活不活——活著的
   （它們已經因為上一任的 pipe EOF 在溫和停了）就對它走 §5 的階梯（從 TERM 那階開始，因為 pipe 已經沒了），
   直到全部不在。pid 被別的程式重用的機率當作可忽略，寫在這裡讓人知道。
4. 照範式 §6.2 對帳自己的 `current`（上一任崩在處理哪則 request）。
5. 寫新 `state.json`（pid、`current` null、children 空）。孩子表**從空開始**：daemon 不收養；要什麼孩子由客戶再
   `spawn`（kernel 的 tick 每格都會補拉它缺的 cpu）。
6. 進 §4 的迴圈。

### 6.2 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 正常停機（§5 走完） |
| 1 | 家、info 讀驗、鎖（`AlreadyRunning`）、state 寫不進去；stderr 一行 `aos-daemon: <代號>: <白話>` |
| 2 | 用法錯 |

一則 request 自己的錯誤回在 response 裡，不影響退出碼。

## 7. 這份沒管的

孩子在做什麼（kernel／cpu 範式）；誰該被拉、幾顆（kernel 的 `info.cpus`）；多機（以後 socket）。
沒有 `aos-daemon-ctl`：客戶端就是往 `D/requests/` 放檔，kernel 的 boot／tick 已經在做；人要看就 `cat D/state.json`，
要停就放一份 `stop-*.json` 或 Ctrl-C。

## 8. 已拍板的前提（使用者定的，不重問）

daemon 是所有 cpu 的父行程、最單純；IPC 用 pipe，只管生死；`spawn` 有 `restart:true`；家照 cpu 範式、JSON-RPC。

## 9. 我自己選的（等你確認）

1. **重拉只在非 0 退出**：退 0＝孩子自願停（kernel 的 stop、pipe EOF），daemon 不跟它作對。
   不然 kernel 叫 cpu 停、daemon 馬上又拉起來，兩邊打架。
2. **重拉節流只有固定 `restart_delay_ms`**，沒有上限、沒有退避；一直死就看 `exits`。
3. **孩子自己一個 process group、同一個 session**（舊版是 `setsid` 開新 session）：Ctrl-C 只打 daemon，
   階梯由 daemon 控制；daemon 死了孩子靠 EOF 停，不靠 SIGHUP。
4. **`.daemon.lock` 這把 flock 留著**：綁行程壽命的鎖不是我們要拿掉的那種鎖。
5. **啟動先等上一任的孩子死透**（`kill(pid,0)` 輪詢＋階梯），孩子表從空開始、不收養。
6. **沒有 `aos-daemon-ctl`、沒有 `ls`**：放檔就是 ctl，偷看 state 就是 ls。
7. **`kill` 立刻回、非同步走階梯**；沒人在等它。
8. **階梯的 TERM 只給孩子本身、KILL 給整組**：TERM 要讓 cpu 自己做強制停（砍它的子程式、回 `stopped:true`）；
   KILL 是最後手段才掃整組。
9. **`spawn` 同步**：拉起來、拿到 pid 才回音；失敗不登記；同名不同 target 是 `NameTaken`。
10. **重拉每次重讀 target**，不用保存的副本。
11. **改綁 daemon 不支援交接**，先停舊的。
