# cpu 範式與 exec cpu（第 1 版，2026-09-23 定稿）

← [proto5 README](../README.md)｜跑一次：[aos-exec.md](aos-exec.md)｜inst 長相：[inst-posix.md](inst-posix.md)｜上層：[kernel](kernel.md)、[daemon](daemon.md)

> 2026-09-23 重架構的第一份；同日照 astra 三輪審查改過（C／X／R、C2／X2／R2、C3／X3／R3）。
> 2026-09-23 定稿並已實作：[`aos_home.py`](../lib/aos_home.py)、[`aos_client.py`](../lib/aos_client.py)、[`aos_exec_cpu.py`](../lib/aos_exec_cpu.py)（入口 `aos-cpu`）。
> 舊的 run／daemon／kernel／cpu-queue 八份已刪（副本在 [proto5.1/spec/](../../proto5.1/spec/)）；llm-cpu／tool-cpu 四份等 agent 重寫落地再刪。
> 已拍板的前提在 §9，我自己選的在 §10。
> 2026-09-24 實作補記：依實作審查回寫，見 impl-review-report.md；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。（審查與實作紀錄在 [rearch 筆記](../notes/2026-09-23-rearch/README.md)）

一句話：**一顆 exec cpu 是一個資料夾加一個主人行程：逐件把 `requests/` 裡的工作 request 照 `aos-exec`
跑一次，回音寫到 `responses/` 同名檔；反覆、排程都是 kernel 的事，cpu 只做一次。**

問模型、跑工具、agent 走一格，全是 aos-exec 的目標、全是程式；能力差別在程式跟 cpu 的環境（§4.1），不在 cpu 的種類。
kernel 跟 daemon 的家也照這個範式長，它們多認的 method 各在自己那份。

## 0. 名詞（白話）

照正文第一次出現的順序排；跟實作有關的（fd、訊號）放後面。

| 詞 | 意思 |
|---|---|
| 家 | 一個 cpu 的資料夾（下面的 `C/`）。kernel 的家 `K/`、daemon 的家 `D/` 也是家；`K/cpus/k/` 是 kernel 專用那顆 cpu 的家，跟 `K/` 是兩個家 |
| 主人（行程） | 管這個家的執行與狀態的那支行程：exec cpu 的主人就是 `aos-cpu C`。啟動前人寫 `info.json` 是初始化，不算主人的事 |
| 外人 | 主人以外的行程：kernel、agent、人用 shell |
| 交件者／收件者 | 交件者＝送出 request 的那個程式；它同時就是那則回音的收件者。本文統一叫交件者 |
| request／response | 一則 JSON-RPC 請求／回音（§3）。工作 request 說「跑這個目標」，response 說跑得怎樣；`ack`、`stop` 也是 request，只是不用回音 |
| 目標（target） | aos-exec 的 `xxx`：普通檔、`.json` inst、資料夾三種（[aos-exec 三種目標](aos-exec.md)）。request 裡放的是目標路徑，不是 inst 內容 |
| inst | 一份 `inst.json`：說要跑什麼程式、cwd、環境、串流怎麼接（[inst-posix](inst-posix.md)）。cpu 不碰它的內容，交給 aos-exec |
| ack | 交件者讀完並記下回音後，再放一則「我拿走了」的通知（§3.3）；主人收到才刪回音 |
| 偷看 | 直接讀別人家的 `state.json`、`requests/`、`responses/`，不放單、不改任何檔 |
| 原子 | 一步做完、別人看不到「做到一半」。`rename`、`link`、`mkdir` 都是 |
| `.tmp` 再 rename | 先寫同目錄暫存檔、寫完 `rename` 蓋過去；讀的人永遠不會讀到半份 |
| `link` | 硬連結；目標已存在就失敗（EEXIST）。拿它做「有就失敗」的放單（§3.1） |
| base／cwd | base 是 inst 裡相對路徑的起點，aos-exec 定：`.json` 目標是檔所在的資料夾、資料夾目標是那個資料夾自己；cwd 是程式跑起來的工作目錄。關係在 aos-exec 三種目標那張表 |
| 指示詞、中心 | JSON 裡 `$env`／`$ref`／`$fmt` 那套（[directives](directives.md)）；「中心是 C」＝解 `$ref` 時相對路徑從 cpu 的家算起 |
| JSON-RPC 2.0 | 一種「請求／回音」的 JSON 信封格式（§3）；request 有 `method`／`params`，response 有 `result` 或 `error` |
| notification | JSON-RPC 裡**沒有 `id`** 的 request＝不用回音（`id: null` 不算沒有） |
| epoch ns | 1970 年到現在的奈秒數（`time.time_ns()`），檔名慣例用的。kernel 的 `not_before`、daemon 的 `since` 用的是 epoch **秒**（帶小數），同一個起點、差十億倍 |
| 旗標 | 程式裡的一個布林。訊號 handler 只能安全地做「把它設成 true」這件事，真正的動作由主迴圈看到旗標才做 |
| 控制 pipe、fd 0／fd 1 | 父行程開給孩子的管子：fd 0 父寫子讀、fd 1 子寫父讀。主人啟動時會把它們搬到別的號碼（§6.1） |
| `go` | 父行程在控制 pipe 上寫的第一行：「我登記好你了，開工吧」。等不到（EOF）＝父行程在登記前就死了，孩子什麼都不碰就退（§6.1） |
| EOF | 管子所有寫端都關了。父行程死了、且沒把寫端漏給別人，孩子就讀到 EOF |
| close-on-exec | 一個 fd 標了這個，跑別的程式（exec）時會自動關掉，孩子拿不到 |
| process group | 子程式跟它自己生的孫子被歸成一組，訊號可以一次發給整組；孫子自己脫離這組就管不到 |
| TERM／KILL | 兩種訊號：TERM 是「請你結束」（程式可以先收尾）；KILL 是直接砍掉、擋不了 |

---

## 1. 資料夾與規則一

```text
C/
  info.json           身分與設定；人寫的（啟動前）
  state.json          主人寫的現況；原子替換
  requests/<n>.json   下一個指令；外人只能原子放進來
  responses/<n>.json  回音，檔名照 request；收件者 ack 之後主人才刪
  cpu.log             主人的 stderr（由拉起它的人接）
```

**規則一（一個家一個主人）**：只有主人行程會改這個家。外人被允許的動作只有兩個，都是往
`requests/` 放檔：(a) 放一則 request（§3.1）；(b) 放一則 `ack`，說「`responses/` 那份我拿走了」（§3.3）。
外人**讀** `responses/`、`state.json`、`requests/` 隨意（偷看），但不刪不改。現在是軟性約定、靠自律；要硬性的以後走 FUSE。

所以這裡**沒有鎖**：放單靠 `link` 的「有就失敗」、換檔靠 `rename` 的原子性。沒有 `running/`
（正在做哪一件在 `state.json`）、沒有 `bad/`（壞單也回音，§4.3）、沒有收屍（主人死了拉它的人
立刻知道；死在哪件上，下一任開機對帳處理，§6.2）。

**名字不重用**：一個家裡，request 的檔名一旦用過（放過、做過、回音 ack 掉了）就**不能再給另一件工作用**。
`link` 只擋「當下同名」，擋不了「刪掉後再用同名」；再用同名會讓遲到的 ack 刪錯回音、舊回音被當成新結果。
慣例 `<交件者名>-<epoch ns>-<交件者 pid>`；kernel 另有帶鏈 id 的取名法（[kernel §1.3](kernel.md)）。
唯一性是交件者的責任，cpu 不查歷史。

## 2. `info.json` 與 `state.json`

```json
{"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 20, "timeout_ms": 0}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | 必填 | `_type` 說主人是哪支程式（exec cpu＝`exec_cpu`、kernel＝`kernel`、daemon＝`daemon`）；`_version` 只認整數 1 |
| `poll_ms` | 正整數 | 20 | 沒事時看一次 `requests/` 的間隔（不准 0，避免空轉） |
| `timeout_ms` | 非負整數 | 0 | request 沒帶 `timeout_ms` 時的預設；0＝不限 |

讀的時候先展開 [指示詞](directives.md)（`$ref` 的相對路徑從 C 算起），再驗欄位型別；不提供 `$opt`。缺檔、身分不合＝`NotAHome`。

```json
{"pid": 1234, "current": {"name": "agent-1790000000000000000-77.json", "id": "agent-1790000000000000000-77", "notify": false}, "runs": 3}
```

| 鍵 | 意思 |
|---|---|
| `pid` | 主人的 PID。有 pid 不代表活著——活不活問拉它起來的人，不從這裡猜 |
| `current` | 正在做的那件：`name` 是 request 檔名（含 `.json`）、`id` 是它的 JSON-RPC id、`notify` 是不是 notification（是＝不寫回音）。閒著是 `null` |
| `runs` | 做完幾件 |

主人啟動時寫一次、每件開始與結束各寫一次；閒著不重寫。

## 3. 訊息：JSON-RPC 2.0，一個信封走兩條路

| 路 | 一則長怎樣 | 誰對誰 | 載什麼 |
|---|---|---|---|
| 檔案 | `requests/<n>.json` 一份一則；回音 `responses/<n>.json` 同名 | 任何人 → cpu | 工作、ack、stop |
| 控制 pipe | 一行一則（換行結尾，內容不含換行） | 父行程 ↔ cpu | 只有 `go`、`stop` 與 EOF |

信封照 JSON-RPC 2.0 原樣：request `{"jsonrpc":"2.0","id":…,"method":…,"params":…}`；`method` 必須是
字串；`id` 是字串、數字或 `null`。response `{"jsonrpc":"2.0","id":…,"result":…}` 或
`{"jsonrpc":"2.0","id":…,"error":{"code":整數,"message":白話,"data":…}}`。不支援 batch。

收到一份檔，分三類：

| 類 | 怎麼判 | 回不回 |
|---|---|---|
| 讀不出來 | 不是 JSON／UTF-8 壞了／不是物件／缺 `jsonrpc`、`method`／型別不合 | **回**，`id` 抓得到就抓、抓不到是 `null`（-32700／-32600） |
| notification | 信封合法、**沒有 `id` 這個鍵** | **絕不回**，就算 method 不認得、params 壞掉也不回 |
| 有 id 的 request | 信封合法、有 `id` | 一定回，成功 `result`、失敗 `error` |

**兩層身分**：檔名 `<n>` 是運輸層的身分（回音靠它對回去，壞 JSON 也對得回去）；`id` 是協議層的身分
（交件者自己認）。慣例兩者用同一個字串。

### 3.1 怎麼放單

寫同目錄唯一 `.tmp` → `os.link(tmp, requests/<n>.json)` → 刪 `.tmp`。目標已存在＝EEXIST＝交件者
的錯，換個名字再來。（放單的人自己也可以用 EEXIST 當「已經放過了」的訊號——kernel 就是這樣重做派工。）

### 3.2 error.code 怎麼編

JSON-RPC 規定 `code` 是整數。信封、method、params 的檢查用它保留的四個號碼（下表）；其餘 aos 錯誤一律 `-32000`，
真正的代號放 `data.code`（字串，沿用現有的 `NotAHome`／`FieldTypeMismatch`…），`message` 是白話。

| code | 什麼時候 | data |
|---|---|---|
| -32700 | 檔不是 JSON／UTF-8 壞了 | 無 |
| -32600 | 不是物件、缺 `jsonrpc`／`method`、`jsonrpc` 不是 `"2.0"`、`method` 不是字串、`id` 型別不合 | 無 |
| -32601 | 這個 cpu 不認得的 method | 無 |
| -32602 | params 形狀不對，或 aos-exec 會回「用法錯」的情況（§4.1） | `{"code":"FieldTypeMismatch"｜"Usage","position":[…]}` |
| -32000 | 其他 aos 錯誤，含 `Interrupted`（§6.2） | `{"code":"<代號>"}` |

### 3.3 `ack`：收件者說「拿走了」

```json
{"jsonrpc":"2.0","method":"ack","params":{"name":"agent-1790000000000000000-77.json"}}
```

notification，**檔名必須以 `ack-` 開頭**（主人只掃前綴）。主人處理的順序：刪 `responses/<name>`
（不在＝ENOENT＝當成功）→ 刪這份 ack 檔。崩在中間＝下次重來一次，兩步都是可重做的。
回音在 ack 之前一直留著，所以收件者可以「讀 → 自己記下 → 再 ack」，中間崩了重讀同一份，不會漏。

## 4. exec cpu 認的 method

### 4.1 `aos-exec`：params 就是 aos-exec 的命令列

request 的意思是「像命令列 `aos-exec TARGET --dir-target R --timeout-ms N --stderr S -- ARGS`
那樣跑一次」，params 的欄位一對一照 [aos-exec](aos-exec.md) 的 `run_target_full()`：

```json
{"jsonrpc":"2.0","id":"agent-1790000000000000000-77","method":"aos-exec",
 "params":{"target":"/abs/agent-bob/think.json","timeout_ms":60000}}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `target` | 字串 | 必填 | aos-exec 的 `xxx`：普通檔、`.json`、資料夾三種都行，怎麼分、base 是誰、串流怎麼接**全照 aos-exec**。相對路徑以 **C** 為起點（cpu 的 cwd 就是它的家） |
| `dir_target` | 字串 | `.aos/inst.json` | 同 `--dir-target` |
| `timeout_ms` | 非負整數 | info 的預設 | 同 `--timeout-ms`；0＝不限；bool 不算 |
| `stderr` | `null`／`"-"`／字串 | `null` | 同 `--stderr`；`"-"`＝接 cpu 自己的 stderr（`cpu.log`）；路徑相對 C |
| `args` | 字串陣列 | **沒這個鍵**＝沒給 | 同 `--`；只有普通檔目標能給。`[]` 是「有給 `--` 但沒元素」，inst 目標一樣拒；`null` 不合法 |

**cpu 的環境就是工作的環境。** cpu 是被拉起來的一支行程，它帶著什麼——環境變數、PATH、跑它的身分與權限、
cwd（＝它的家）——工作 inst 沒寫 `clear` 就整包繼承（aos-exec 的規則）；普通檔目標更是全部繼承。
所以「llm cpu」不是另一種 cpu：是一顆普通 exec cpu，拉它的那份 inst（[kernel 替它寫的 `K/cpus/<c>/inst.json`](kernel.md)）
把 `llm-http` 所在目錄放進 PATH、把 API key 放進 `envs`；工作 inst 的 argv 直接寫 `llm-http` 就找得到。
cpu 自己讀的是它自己的環境，不會替工作補任何東西。

cpu **不讀、不解 inst**：指示詞、base、`$ref` 都是 aos-exec 讀那份檔時照它自己的規則做。
指到還不存在的 `.json` 也收，跑起來是 kind=aos（`ReadFailed`），跟 aos-exec 一樣——**收下不等於會等它出現**，
每次跑都是一次 aos 失敗，怎麼算是收件者的事（[kernel §4](kernel.md)）。
aos-exec 會回「用法錯」（退出碼 2）的情況——`.json`／資料夾目標卻給 `args`、不存在的非 `.json` 路徑、
`dir_target` 指的檔不在——在這裡是 `-32602`／`data.code:"Usage"`，不算跑過。

一顆 cpu **一次只做一件**；`requests/` 按檔名排序取第一份（所以交件者想排序就靠檔名）。

result：

```json
{"code":0,"kind":"child","timed_out":false,"stopped":false,"ms":42}
```

| 鍵 | 意思 |
|---|---|
| `code`、`kind` | 就是 `run_target_full()` 回的 `code`、`kind`：`child`＝子程式真的跑了一次（`code` 是它的退出碼，找不到程式 127、沒執行權 126、逾時 143／137 都算 child）；`aos`＝aos-exec 自己失敗、那次根本沒跑（`code` 是 1，跟 API 一樣、不換算成 125） |
| `timed_out` | 真的撞到 `timeout_ms`（真實旗標，不從 143／137 猜）。aos-exec 的 `run_target_full()` 三種目標都回這格 |
| `stopped` | 是被強制停砍掉的（§5.2）；子程式在強制停到達**之前**就自己結束的，`stopped` 是 false、結果算數 |
| `ms` | 耗時 |

（09-24 補）`run_target_full()` 對三種目標回傳 `code`、`kind`、`timed_out`、`stopped`、`ms`，cpu 用的就是這個入口；
舊的 `run_target()` 保留回 `(code, kind)` 的相容契約，給還沒遷移的呼叫者。

**`kind=aos` 是 result 不是 error**：params 合法、只是那份 inst 讀不到／壞掉／前置檢查沒過。
stdout 不在 result 裡——要輸出就在 inst 裡寫 `stdout`。

### 4.2 `stop`

notification，**檔名必須以 `stop-` 開頭**（主人只掃前綴）。細節整節在 §5。

### 4.3 壞單也回音

§3 那張三類表：讀不出來的回 -32700／-32600（`id` 能抓就抓）、有 id 但 method／params 壞的回
-32601／-32602，都寫 `responses/<n>.json`、再刪原單；notification 壞了只刪不回。cpu 不停、不隔離、不重試。

幾個邊角：request 檔名必須是 `.json` 結尾的單一檔名（不含 `/`、NUL）；`ack-`／`stop-` 開頭但 `method` 不是
`ack`／`stop` 的，照三類表處理（有 id 回 -32600、沒 id 只刪）；`state.runs` 只數真的跑過 aos-exec 的，壞單不算。
（09-24 補）`ack-`／`stop-` 檔必須是相應 method 的 notification；帶 id 時回 `-32600`，不執行控制動作。
合法 notification 的 method／params 錯誤只刪原單、不回音。

## 5. 停下來

三種「停」，由輕到重。四個溫和停的來源都只是**設旗標**；旗標什麼時候被看到、看到做什麼，在 §6.3 的迴圈裡寫死。

### 5.1 溫和停：`stop`

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

### 5.2 強制停：第二次訊號

**已經處理過第一次**（旗標已設）之後再收到 SIGTERM／SIGINT：子程式還在跑 → 對它的 process group
發 TERM、寬限 2 秒、再 KILL；回音**照常寫**，`result.stopped=true`、`code` 是子程式實際的退出碼
（通常 143 或 137）、`kind` 照實。子程式已經自己結束、只是回音還沒寫 → 不砍、`stopped=false`、結果算數。
之後跟 5.1 的 3、4 一樣退出。
（同種訊號連發太快 Linux 可能合併成一次，所以「第二次」是指主人已經處理完第一次之後才到的那次。
父行程死了、cpu 還沒讀到 EOF 就先收到別人的 TERM，那個 TERM 就是「第一次」，只會溫和停——
接手的人得有再等一段、最後硬砍的心理準備，見 [daemon §6.1](daemon.md)。）

砍的是「子程式那一組」；脫離這組的後代砍不到，跟 timeout 一樣，不另做 kill-tree。
收件者看到 `stopped:true` 就知道這次結果不算數。

### 5.3 硬砍：主人被 KILL

主人來不及做任何事。下一任主人開機對帳（§6.2）照表處理：回音已經發出去的就留著，
還沒發的補一則 `Interrupted`，原單還沒開始的照常做。子程式如果還活著沒人管（在保證外）。

### 5.4 誰負責發

- **kernel**：往它管的每顆 cpu 放 `stop-*.json`（[kernel.md §3](kernel.md)），不發訊號。
- **daemon 停機**：對每個孩子的控制 pipe 寫 `stop`；等；逾時才走訊號（階梯在 [daemon §5](daemon.md)）。
- **人**：終端裡 Ctrl-C 一次＝溫和、兩次＝強制。

## 6. 主人的一生

```text
aos-cpu DIR
```

### 6.1 啟動

1. 若 fd 0 是 pipe：**先等 `go`**。用非阻塞讀一行一行組，讀到 `{"jsonrpc":"2.0","method":"go"}` 才往下；
   先讀到 EOF＝拉它的人在登記前就死了，**什麼都不碰**（不讀 info、不寫 state）、退出碼 0。
   `SIGPIPE` 一律忽略（往關掉的 pipe 寫只會得到 EPIPE，不會被訊號打死）。
2. 讀驗 `info.json`；`requests/`、`responses/` 沒有就建。
3. 若 fd 0 是 pipe：把 fd 0／fd 1 **搬到高位 fd、標 close-on-exec** 當控制 pipe，然後 fd 0 接 `/dev/null`、
   fd 1 接 fd 2。這樣工作繼承串流時拿到的是 `/dev/null` 與 `cpu.log`，高位那兩個又因 close-on-exec 跟不
   進工作——工作既拿不到控制訊息、也握不住回程寫端（fork 到 exec 之間的那一瞬間有副本，exec 就沒了）。
   fd 0 不是 pipe（人在終端跑、或 stdin 接 `/dev/null`）就沒有控制 pipe，只認檔案與訊號，也不等 `go`。
   用程式包 `aos-cpu` 的人注意：`stdin=PIPE` 就等於「我要用控制協議」，得送 `go`、還得一直握著那條 pipe。
4. **先讀舊 `state.json` 做開機對帳（§6.2），對帳完才寫**新的 `state.json`（pid、current=null、runs 照舊）。
   沒有舊 `state.json`（第一次跑）＝當作 `current: null`、`runs: 0`。

### 6.2 開機對帳

上一任可能停在哪，看 `current`（含 name、id、notify）＋兩個檔在不在。前提：名字不重用（§1）、
只有主人會刪這兩個檔（ack 也是主人處理的）。

| `current` | `requests/X` | `responses/X` | 可能停在哪 | 做什麼 |
|---|---|---|---|---|
| null | — | — | 閒著 | 沒事 |
| X | 在 | 不在 | 還沒開始、執行中、或跑完還沒發回音 | 有 id：用 `current.id` 寫 `-32000`／`Interrupted`，再刪原單。notification：只刪原單 |
| X | 在 | 在 | 發了回音、還沒刪原單 | 刪原單 |
| X | 不在 | 在 | 刪了原單、還沒清 current | 沒事 |
| X | 不在 | 不在 | notification 的正常路徑（沒回音、原單刪了、current 還沒清）；有 id 的不該出現 | 沒事 |

然後 current 清 null。對帳自己崩了再來一次也是同一張表（每列的動作都可重做）。
`requests/` 裡其他還沒開始的單不在對帳範圍，照常一件一件做。

### 6.3 迴圈

```text
掃 requests/ 的 ack-（§3.3 兩步）與 stop-（設旗標）
看旗標（§5.1 四來源）→ 有就收尾退出
取 requests/ 第一份非 ack-／stop- 的 X
  (1) 寫 state.current={name,id,notify}
  (2) 跑（run_target）；跑的期間每 poll_ms 看一次控制 pipe 與訊號旗標，只記、不動手（強制停除外）
  (3) 原子寫 responses/X（notification 跳過）
  (4) 刪 requests/X
  (5) 寫 state.current=null、runs+1
沒單就睡 poll_ms
```

**(3) 在 (4) 前**是開機對帳那張表的根據：回音一定先於原單消失。收件者查「做完了沒」也要照這個
順序看——先看原單在不在、再看回音——才不會看錯（[kernel §3 第 6 步](kernel.md)）。
(3) 寫不出去（ENOSPC、EACCES…）是**主人層級**的錯：stderr 一行、`state.current` 留著、退出碼 1；
下一任開機看到「原單在、回音不在」就補 `Interrupted`——結果丟了但不會重跑、不會失單。
磁碟一直壞就會一直退 1、一直被 daemon 重拉（[daemon §4](daemon.md)），這是接受的。

沒有父行程也能跑（終端直接 `aos-cpu DIR`）。沒有「自己反覆跑同一份 inst」的模式——要反覆是 kernel 的事。

## 7. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 正常停（§5.1／5.2）、或等 `go` 等到 EOF |
| 1 | `info.json` 讀驗不過、`state.json`／回音寫不進去、佇列目錄建不起來；stderr 一行 `aos-cpu: <代號>: <白話>` |
| 2 | 用法錯：DIR 不是資料夾、多餘旗標 |

一則 request 本身的錯誤都回在 response 裡，不影響退出碼；子程式的 stderr 照 inst 走。

## 8. 這份沒管的

**適用範圍**：同一台 POSIX 機器、大家都直接摸得到各家的檔案。多機（socket）、Windows 都是以後另訂，
這份寫的 fd／訊號／flock／`link` 都是 POSIX 的。

誰拉 cpu 起來、怎麼知道它死了、`restart`、停機階梯（[daemon](daemon.md)）；誰決定哪個目標去哪顆、
一次性還是反覆、專門打 LLM 的 cpu 怎麼保留（[kernel](kernel.md)）；agent 怎麼用 aos-exec 取代原本的 llm／tool cpu（agent）。

## 9. 已拍板的前提（使用者定的，不重問）

規則一是軟性的（硬性以後走 FUSE）；cpu 聽命執行不自己迴圈；IPC 用 pipe（多機以後再 socket）；
JSON-RPC 2.0；所有**工作** request 的 method 都是 `aos-exec`（`ack`／`stop` 是管理用的）；params 就是 aos-exec 的 argv（`target`＋旗標），不包 inst 內容；
cpu 的環境就是工作的環境（llm cpu＝環境裡有 `llm-http` 的普通 exec cpu）；daemon 的 `spawn` 有 `restart:true`。

## 10. 我自己選的（等你確認）

沒翻案就照這樣實作。

1. **pipe 只管生死，工作走資料夾**：kernel 派工是往 exec cpu 的 `requests/` 放檔，不經 daemon 轉發。
2. **回音要 `ack` 才刪**（§3.3），不是收件者自己刪：規則一回到純的、開機對帳沒有歧義、收件者崩了重讀不漏。
   代價：一件工作三個檔（request／response／ack）。
3. **`go` 握手**（§6.1）：父行程登記完才放行，登記前死了孩子自己退、不碰家。多一行，換掉「同家兩個主人」。
4. **名字不重用是交件者的責任**（§1），cpu 不查歷史。
5. **`stop-`、`ack-` 檔名前綴是規定**，主人只掃前綴，不逐份打開。
6. **`running/`、`bad/`、收屍、`hold`、kill-tree 旗標全部拿掉**。
7. **aos 錯誤統一 `-32000` ＋ `data.code` 字串**，不給每個代號編整數。
8. **上一任死掉的單回 `Interrupted`**，語意「結果不明」，收件者自己決定要不要重送。
9. **訊號：第一次＝溫和停、第二次＝砍子程式那組並回 `stopped:true`**；KILL 主人交給開機對帳。
10. **`_type` 叫 `exec_cpu`**、程式叫 `aos-cpu`；aos-run 這個名字退休。

## 實作補記（2026-09-24）

依 [實作審查報告](../notes/2026-09-23-rearch/impl-review-report.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §4.1：`run_target()` 改稱 `run_target_full()`（審查 A-5、B-1），舊入口保留相容。
- §4.3：`ack-`／`stop-` 帶 id 回 `-32600`（B-4）。
- §5.1：控制 pipe 驗信封（A-2）；`go` 帶合法 id 放行是隊長裁決。
- 主人被 KILL 後另一 session 的子程式仍可能活著（§5.3 已列保證外），kernel 那邊的後果見 [kernel §6](kernel.md) boot 第 2 步的補句（B-12）。
