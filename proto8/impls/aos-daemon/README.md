# aos-daemon

`aos-daemon - 照一張名單，把幾個 proc 各自起在自己的小格裡、看著它們`（NAME，C-54 R1）

**一句話：`aos-daemon [旗標] daemon.json`——一個開了窗的 aos-loop，外加一張 proc 的表：照表把 proc（經 aos-exec）起起來、看著、停掉、收掉。**
一個 lib（`lib/libaos-daemon.a`，沒有公開標頭）加一支薄命令列（`bin/aos-daemon`）。連 [aos-loop](../aos-loop/README.md) 的公開 API
（骨架 `aos::loop::Loop`；它又帶進 aos-exec、inst、aos-util、aos-directive）與 [aos-post](../aos-post/README.md) 的庫（信箱；它再帶進 aos-lock）。全家慣例見 [impls/README.md](../README.md)。
規範（語意以它為準）：[N-28、N-54](../../docs/NORMS/04-基礎設施-loop與daemon.md)；窗 [N-06～N-17](../../docs/NORMS/05-基礎設施-窗.md)；`AOS_DAEMON_STACK` [N-63、N-64](../../docs/NORMS/10-基礎設施-定義與工作區.md)。

照「資料夾＝程式」的做法寫（使用者「daemon也用新做法重寫吧」、「照預設」，[ideas § 25](../../thinking/2026-10-19-ideas.md)）。名詞見 [thinking procs](../../thinking/2026-11-03-procs.md)：
daemon 管的子項不論包在 aos-loop 裡一直跑的（loop 型）還是 aos-exec 跑一次的（exec 型）都叫 **proc**；**一份名單 `procs`**、**看寫法決定怎麼起**（沒有 `kind`）、**每項可寫自己的 `stack`**、
daemon 的 **stop／start**（`procs_stopped`／`procs_started`：列留成 `stopped`、用同一個 stack 再起）、收工時的 **sleep／開門的 wake**（還在跑的 loop 型列留成 `sleeping`、再開自動起，[下「收工與開門」](#收工與開門sleepwake)）；手把 `procs_ctl.json`、窗 `procs_state.json`（一張表）、信箱 `procs_ctl_mailbox/`、小格 `procs/<名字>/`。
舊名 `loops`、`execs`、`loops_ctl`、`loops_state`、`loops_ctl_mailbox`、`loops_added`……**當沒看到**（C-48，使用者「1. 當沒看到。」）：不報錯、不提醒。

像一個領班：手上一張名單（`procs`），名單上每個人各有一個小隔間（`$AOS_STACK/procs/<名字>/`，或他自己指定的 `stack`）。他每隔一會兒（`interval_ms`）看一眼兩塊佈告欄：
一塊管他自己（ctl 窗：暫停、收工、節奏），一塊管名單（procs_ctl 窗）。名單改了就把多的請走、少的叫來、要停的請他做完手上這件就下班（**留在名單上**，叫得回來）；
誰自己下班了（`done`）或被他請走了（`stopped`）就在工作日誌（stdout 的 log）記一行「誰、結束碼幾」、從名單白板（procs_state 窗）上擦掉，**這一班不會再叫他回來**；
他自己的狀況寫在另一塊白板（state 窗）。他自己收工時（不論為什麼）先把每個人都請走、寫好白板，才走人——還在做事的不擦名字，白板上改寫「休息中」（`sleeping`），他下次開門就把這些人叫回同一個隔間接著做（被他請下班的 `stopped` 不叫）。

```sh
cat daemon.json
# {"max": 10, "interval_ms": 200, "ctl": "ctl.json", "state": "state.json",
#  "procs": {"bob": {"exec": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}, "max": 1},
#            "tick": "../tick"}}
AOS_STACK=$PWD/.stack/ aos-daemon --enable-logs daemon.json     # 慣例用法是 aos-exec 它（11-04 前的例子 proto8/demo/daemon 刪了）；PATH 上要有 aos-exec、aos-loop
```

**起 daemon 要看 log 就加 `--enable-logs`**：不加的話 daemon 什麼都不印（stdout、stderr 都安靜，只有出錯時 stderr 一行），看起來像卡住，其實照常在跑；子項起落要看就加它（見下「log」），或看 `aos-daemon-ctl ls`。
**收工：在 daemon 的視窗按 Ctrl-C**（使用者 11-03 晚定）——SIGINT 走正常收工（`finish`），還在跑的 loop 型睡下（`sleeping`），下次開門自己醒（見下「收工與開門」）。

## 用法

```
aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [--enable-logs] daemon.json [-- 參數...]
```

命令列同 [aos-loop](../aos-loop/README.md)（共用 `loop_cli`）：唯一的位置參數＝設定檔（必給、只能一個；可寫 `檔#/指標`）；旗標放前面；起跑時 旗標 ＞ daemon.json ＞ 預設；
`procs`、`adopt`、`procs_ctl`、`procs_state`、`procs_ctl_mailbox` 只在 daemon.json（沒有旗標）。usage 錯一行 `aos-daemon: ArgumentsBad usage: aos-daemon [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [--enable-logs] 設定檔.json [-- 參數...]（原因）`。
`--enable-logs`（不帶值的開關）＝印 log（見下「log」）。`daemon.json -- 參數...`：附加參數**只接在 daemon 自己的 `exec` 後面**（每次都帶），不影響 proc；沒有 `exec` 卻給了＝`ArgumentsBad`。

daemon.json＝loop.json 的超集（N-28）：

| key | 型別 | 沒寫 | 意思 |
|---|---|---|---|
| `exec` | 字串、`[目標, 參數...]` 或單子物件 | 不跑 | 自己每次的身體（同 aos-loop）；純監工不寫 |
| `max` | 非負整數 | 不限 | 跑幾次就收工（寫 `null` 不行） |
| `interval_ms` | 非負整數 | 200 | 兩次之間至少隔幾毫秒 |
| `ctl`、`state` | 檔名或 `null` | 不開 | loop 面向的兩扇窗，在 `$AOS_STACK` 底下（同 aos-loop）。程式沒有預設名；慣用 `ctl.json`、`state.json` |
| `procs_ctl`、`procs_state` | 檔名或 `null` | `procs_ctl.json`、`procs_state.json` | 管轄（名單）的手把與狀態窗，在 `$AOS_STACK` 底下；寫 `null`＝不開 |
| `procs_ctl_mailbox` | 路徑或 `null` | 不開 | 信箱：名單的增減也可以一封封信投進來（在 `$AOS_STACK` 底下；慣用名 `procs_ctl_mailbox`）；跟 `procs_ctl` 可以同時開，都不開＝名單只看 daemon.json。見下「信箱」 |
| `procs` | `{名字: proc}` | `{}` | 名單；每項怎麼起看寫法（下「看寫法決定怎麼起」）；物件可多寫 `ws`、`stack`。拆成好幾份檔寫 `{"$ref": ["procs-1.json", "procs-2.json"]}`（下「指示詞與切檔」） |
| `adopt` | 布林 | true | 起來時讀自己上次的 procs_state，把還活著的接回、不重起；`stopped` 的列接成 `stopped`、`sleeping` 的列接回後自動 wake |

- 要 `$AOS_STACK`（沒設＝`StackMissing`）。名字不能當資料夾名或會被 aos-exec 誤認（空、含 `/`、含 `#`、以 `.` 開頭）＝`CfgBad`「procs 的名字 … 不能當資料夾名」。跟自己的窗同名不擋（小格在 `procs/<名字>/`，撞不到 stack 頂層的窗）。
- **每次**（Loop 讀完 ctl 之後）：讀 procs_ctl →（開了信箱：套信、改底）→ 期望表＝procs_ctl 的 `procs`（有寫）或底，＋`procs_added`－`procs_removed`；stopped 集合＝底＋`procs_stopped`－`procs_started` →
  表上多出來的送 SIGTERM（`phase: stopping`）就往下走、**不等**，之後每次看一眼：退了印 log、從表上拿掉（小格留著），滿 10 秒還在就 SIGKILL 整群（子 loop 那群，加上它底下自成一群的——inst 起的單子）→
  在 stopped 集合裡、還在跑的＝daemon 的 stop（下「起、停、暫停」）→ 看誰自己結束了（`phase: done`，記 `code`／`signal`，印 log、拿掉、本次執行不再起）→
  起表上少掉的（在 stopped 集合裡的＝直接一列 `stopped`、不起；收的途中的同名項還在表上，等它退了下一次才起；本次執行已自己結束的不起）、`stopped` 的列拿出集合了＝start →
  跑 `exec`（有寫才跑）→ 寫 state、接著寫 procs_state（有變才寫）。ctl 是 `stop` 或 `pause` 的那圈不調表（下「兩個手把、兩扇狀態窗」）。
- **同名改寫法**（例：loop 型改成 exec 型、改了 `ws`）＝設定變了，已在跑的**不重起**（N-54「名字已在表上的不看設定變了沒」）；等它退了被拿掉／被 rm 再放回、或 stop 再 start 才照新寫法。
- **子項結束後不留名單、不自動重起**（使用者「改成子項結束後不留名單」、「照舊拿掉」）：跑滿 `max`、身體退 10、訊號、別人直接往子 loop 的 ctl 寫 `{"cmd": "stop"}`——
  只要不是 daemon 自己下的 stop，退了就印 log、從表上拿掉（＝對 daemon 不存在），小格照留。自己結束（`done`）的**本次執行不再起**：記進 `ended_`（名字），期望表扣掉它；某一圈的期望表裡沒有它了才從 `ended_` 拿掉（之後名單再有它就照常起）。
  開了信箱再從底拿掉，而且下一圈套信之前，不是 procs_ctl 疊上去的就從 `ended_` 放掉（之後再有信同名 `procs_added`＝重新起）。daemon 重起時 `ended_` 是空的（照 daemon.json 再起）。
- **adopt**：讀上次的 procs_state（沒開 procs_state 窗＝沒東西可接；舊的 `loops_state.json` 不讀），`phase` 是 `running`、pid＋`started_at_ticks`（/proc 第 22 欄）對得上的放回表上、不重起（log 也印一行 `running`；接回的 `stack` 照列上的，哪一型看小格有沒有 daemon 寫的 `loop.json`）；
  `phase` 是 `stopped` 的列接成 `stopped`（不起、不判活）、名字進底的 stopped 集合；`phase` 是 `sleeping` 的列接成 `sleeping`、**不**進 stopped 集合＝第一圈 wake（下「收工與開門」）；其他列（`stopping`）不接。接回的不是自己的子行程，之後看 /proc 判斷活不活，結束那行 `code`／`signal` 是 null。
- **子 loop 被 SIGKILL 時**它小格裡的 `state.json` 停在最後那份（多半 `running`），daemon 不替它改（N-09）；看死活照 N-17。daemon 的 log 那一行是準的（`stopped`、`signal` 9、`code` 137）。
- 效能（使用者「都修都處理」，[thinking](../../thinking/2026-10-23-daemon-bench.md)）：收子項不原地等；表＝「照加入順序的串列＋名字→那一列的雜湊表」；
  沒有 `exec` 時一圈只讀一次 ctl、只對一次表、最多寫一份 state（`waiting`；有變才寫，睡著時兩扇窗都不動）；對表時起子項之前先寫一份 procs_state、之後每起一個寫一次（有變才寫）。

### 看寫法決定怎麼起

| 寫法 | 型 | daemon 怎麼起 | 小格裡 |
|---|---|---|---|
| 字串、`[目標, 參數...]`（非空字串陣列） | exec 型 | `aos-exec -- 目標 參數...` 一次，不包 aos-loop（`spawn_exec`） | `stderr.txt`、程式自己的檔 |
| 物件，key 只有 `exec`（＋`ws`、`stack`）；`exec` 是目標或內嵌單子 | exec 型 | 同上；單子＝寫成小格的 `exec.json` `{"exec": 單子}`，`aos-exec -- 小格/exec.json#/exec` 跑一次 | 同上（單子多一份 `exec.json`） |
| 其他物件（多了任何一個 key：`max`、`interval_ms`、`ctl`、`state`、`body`、`envs`……；沒有 `exec` 也算） | loop 型 | 寫小格的 `loop.json`、經 aos-exec 起一支子 aos-loop（`spawn`） | `loop.json`、`state.json`（子 loop 的窗）、`stderr.txt`、程式自己的檔 |

- **坑**：`{"exec": "fsm.json"}` 只有 exec＝跑一次；要它當 loop 一直跑就寫一個 loop 的 key（例 `"interval_ms": 0`）。名單裡的字串也是跑一次，不會包成子 loop。
- **不標哪種**：要分看小格有沒有 `loop.json`（daemon 寫的）。`Child::once` 只在記憶體裡（起的時候判、adopt 看 `loop.json`）。
- exec 型物件的 `exec` 不是目標也不是物件（例 `3`、`null`）＝`CfgBad`；loop 型物件 daemon 只解自己認的格（`exec`、`max`、`interval_ms`、`ctl`、`state`、`ws`、`stack`），其他原樣交給子 loop、不驗（寫錯了子 loop 自己退 1，沒有 `exec`＝「沒有東西可跑」退 1）。
- **起子 loop**（經 aos-exec）：小格 mkdir；設定補上 `"ctl": "ctl.json"`、`"state": "state.json"`（沒寫才補）、拿掉 `ws`、`stack`（daemon 的 key，不寫進 `loop.json`），
  **一律蓋上 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]`**，相對的 `exec`（字串，或陣列的第一個元素）照 daemon 的 cwd 轉成絕對路徑（子 loop 的 cwd 會是小格）；`exec` 是內嵌單子＝沒寫 `cwd` 補上 daemon 的 cwd、相對的接在後面（指示詞不動），單子裡相對的 `$ref` 檔名照它來自的檔轉成絕對（`abs_refs`，不解）；
  先寫 `.loop.json` 再改名成 `loop.json`；fork 一個子行程：`setsid` 自成 session、stdin／stdout 接 `/dev/null`、stderr 附加到小格的 `stderr.txt`、`AOS_STACK=小格/`、`AOS_DAEMON_STACK=daemon 的 stack`、（寫了 `ws`）`AOS_WS`、
  解開三個訊號、cd 到 daemon 的 cwd，呼叫 aos-exec 的 `run_cli({"--", "小格/loop.json#/_entry"})`——它 cd 進小格、讀小格的 `.env`（若有）、設好 `AOS_CF`＝小格的 loop.json，再 **exec 成 PATH 上的 aos-loop**（pid 不變）。
  所以 **PATH 上要有 aos-loop 和 aos-exec**；沒有＝子 loop 以 1 結束、原因寫在小格的 `stderr.txt`。
- **起 exec 型**：小格、`stderr.txt`、setsid、`/dev/null`、`AOS_STACK`、`AOS_DAEMON_STACK`、`AOS_WS`、cd 到 daemon 的 cwd 都同上，**只是不包 aos-loop、不寫 `loop.json`、不補 `ctl`／`state`**：子行程直接 `run_cli({"--", 目標, 參數...})`，表上的 pid 就是那支程式；相對路徑從 daemon 的 cwd 算（不轉）。
  退了＝`done`、不重起（同 loop 型）；**exec 型只有跑和拔**（使用者「他停下來就是沒了，新開的就是新的 CPU 了」）：`procs_stopped`／`procs_started` 裡有它＝procs_ctl 整份不採用／壞信（下「起、停、暫停」）。要一次性的東西能停，寫成 `max: 1` 的 loop。

### 每個 proc 自己的 stack

```json
{"procs": {"c": {"exec": "../clock", "interval_ms": 1000, "stack": "/tmp/c"}, "j": {"exec": "../job", "stack": "jobs/j"}}}
```

- **`stack`**（物件選填）：非空字串；`null`＝當沒寫；其他型別、空字串＝寫壞（daemon.json `CfgBad`、procs_ctl 不採用、信壞信）。字串／陣列寫法沒地方放，要指定就寫成 `{"exec": 它, "stack": S}`。指示詞照解（`resolve_keys` 有 `stack`）。
- **相對路徑從 daemon 的 cwd 算**（同 `ws`、子項 `exec`），讀進來就轉絕對（`abspath`：`.`、`..` 收掉、捷徑不解、結尾不帶 `/`）。
- **用法**：`AOS_STACK=<S>/`（取代預設小格）；loop 型的 `loop.json`／`ctl.json`／`state.json`、單子的 `exec.json`、`stderr.txt` 都寫進 S；**S 不在就建**（`mkdir -p`，同 `aos-exec --stack`）；建不了＝`MkdirFailed`。
  沒寫＝預設小格 `$AOS_STACK/procs/<名字>/`（只建 `procs/` 與小格兩層；`$AOS_STACK` 不在＝開了 state 或 procs_state 窗就 `WriteFailed`、兩扇都沒開才 `MkdirFailed`，都退 1——建 daemon 的 stack 只在 aos-exec 做，N-59 第 1 件）。寫了 `stack` 的 `procs/<名字>/` 根本不建。
- **不查、不擋**（C-52、N-28）：S 裡有別的東西、兩個 proc 同一個 S、S 指到 daemon 自己的 stack、S 是捷徑——都不管，使用者自己承擔。`rm` 不清 S。
- **`procs_state` 每列一律有 `stack`**（絕對；預設小格也寫）：adopt 與 start 照列上的，`aos-daemon-ctl where` 也靠它。

### 起、停、暫停

四態：**running**（表上、活著）、**stopping**（收的途中）、**stopped**（表上、**行程不在**、stack 留著）、**表上沒有**（＝對 daemon 不存在）；另有收工留下的 `sleeping`（下「收工與開門」）。動作：`add`／`rm`＝`procs_added`／`procs_removed`、`stop`／`start`＝`procs_stopped`／`procs_started`、`pause`／`resume`＝不是 daemon 的事（直接寫子 loop 的 ctl）。

- **stop（loop 型）**：名字在期望表又在 stopped 集合、行程活著→daemon 往它的 `ctl.json`（小格裡 daemon 自己寫的 `loop.json` 的 `ctl` 那格）寫一道 **`{"cmd": "stop", "seq": N}`**（先寫 `.ctl.json` 再改名，N-05；N 見「實作注意」），
  讓它**跑完這一次自己退 0**，不 SIGTERM、不殺半路的身體；等的這段列 `stopping`、沒有時間上限（N-28 ①）。退了**列留在表上**：`{"pid": null, "started_at_ticks": null, "phase": "stopped", "code": 0, "signal": null, "stack", "ws"?}`；stack 不碰。
  子 loop 沒開 ctl（`"ctl": null`）、或讀不到 `loop.json`＝改送 SIGTERM（10 秒 SIGKILL），退了一樣留成 `stopped`（代定）。寫不了 ctl＝`WriteFailed`、daemon 退 1（同起子項寫不了 `loop.json`）。
- 名字在 stopped 集合、行程還沒等到 daemon 寫 ctl 就自己退了＝一樣留成 `stopped`。等它自己退的途中被拿掉（不在期望表了）＝改送 SIGTERM，退了照樣拿掉。
- **同一封信（或同一份 procs_ctl）add＋stop**＝列直接 `stopped`（`pid`、`code` 都是 null）、不起、**stack 先不建**。
- **start**：從 stopped 集合拿掉→下一圈用**列上的 `stack`** 再起（loop 型重寫同一格的 `loop.json`；**不清 ctl**：子 loop 起來第一次讀的那份當基準線、不執行，所以舊的 `{"cmd": "stop"}` 留著沒事）。起來是跑還是暫停看它自己 `state.json` 的 `paused`（暫停中被停的，起來先暫停；代定）。
  設定照期望表上的（同名 add 換過就是新的）；信箱接回的列沒有設定（null）＝照小格裡現有的 `loop.json` 起（代定）。
- **只有指令叫起**：信來、procs_ctl 別的 key 變、`procs_added` 同名都不會把 `stopped` 的拉起來（同名 add＝設定換掉、停照停）。procs_ctl 拿掉 `procs_stopped` 的名字＝回初始值＝起（N-06）；要一直停就一直寫。底的 stopped 集合是 adopt 接回的 `stopped` 列＋信改過的——**重起 daemon 後**，procs_ctl 拿掉名字不會起它（初始就是停的），要 `procs_started`（代定）。
- **exec 型只有跑和拔**：`procs_stopped`／`procs_started` 裡的名字是 exec 型（表上有＝看那列；不在表上＝看寫法）＝procs_ctl 整份不採用、`ctl_warning`「exec 型 "X" 沒有 stop／start（exec 型只有跑和拔）」；信＝壞信、`mailbox_warning` 同句、有 `reply_to` 也不回。**不在期望表的名字**出現在這兩個陣列＝不管。
- **stopped 的被 rm**：列與集合都拿掉、stack 不碰；它 ctl 裡的 `{"cmd": "stop"}` 留著沒事。
- **繞過 daemon 自己往子 loop 的 ctl 寫 `{"cmd": "stop"}`**：子 loop 退 0，daemon 看到的是「退了」→從表上拿掉（＝拔掉，不是 stop；使用者「照舊拿掉」）。掛在 daemon 下要停就走 daemon。
- **pause／resume**：不是 daemon 的事——寫子 loop 自己的 ctl `{"cmd": "pause"}`／`{"cmd": "resume"}`（`aos-daemon-ctl pause`／`resume` 就是這樣做）；daemon 不轉述 paused（不讀子項的 state，C-52），要看讀它的 `state.json`。
- **daemon 自己暫停中**：起停也等解除（不寫子 loop 的 ctl）；daemon 收工＝收掉活著的（等它自己退的那些改送 SIGTERM，退了照樣留成 `stopped`；還在跑的 loop 型留成 `sleeping`，下一段）、`stopped` 的列照寫進最後一份 procs_state；再起 adopt 接回 `stopped` 的、wake `sleeping` 的、照名單起其他的。

### 收工與開門：sleep／wake

使用者「改寫成休息中」「我們有start/stop, sleep/wake, pause/resume，我們缺了sleep/wake」（[procs § 8](../../thinking/2026-11-03-procs.md#8-收工時改寫成休息中sleepwake11-03-晚)）：daemon 收工時還在跑的不從表上擦掉，改寫成 **`sleeping`**（表上、行程不在、stack 留著），daemon 再開時**自動 wake**。

- **sleep**：daemon 收工（自己 ctl 的 `{"cmd": "stop"}`、SIGTERM／SIGINT／SIGHUP，或出錯退出——都走 `finish`）時，還在跑的 **loop 型**照舊 SIGTERM（10 秒 SIGKILL），退了列留成 `{"pid": null, "started_at_ticks": null, "phase": "sleeping", "code", "signal", "stack", "ws"?}`，log 一行 `sleeping`。
  **exec 型**拿掉（「他停下來就是沒了」）；收工前已是 `stopped` 的、等 daemon 的 stop 退的途中的＝`stopped`；被 rm 收的途中的＝拿掉。
- **wake**：daemon 再開 adopt 時，`sleeping` 的列接回、不進 stopped 集合；第一圈 reconcile 跟 start 走同一條：**用列上的 `stack`** 再起（設定照期望表；信箱接回的沒有設定＝照小格裡現有的 `loop.json`、`ws` 照列上記的），log 一行 `running`。
  收工時本來暫停中的：子 loop 被 SIGTERM 時最後一份 `state.json` 記著 `paused: true`，用同一個 stack 起來照它自己的 state 先暫停（代定），`resume` 才接著跑。
- **睡著時收到的指令**（daemon 沒在跑時 `aos-daemon-ctl` 寄的信，開門後先套信再對表）：`procs_stopped`＝改成 `stopped`、不 wake（要 `start`）；`procs_removed`＝列拿掉；名單（daemon.json／procs_ctl）上已經沒有它＝列拿掉。
- daemon 開門時自己是暫停中（它的 state.json 記著 `paused`）＝跟起停一樣等解除才 wake。`adopt: false`＝不讀舊表，`sleeping` 的列就不認了（照 daemon.json 重新起）。
- **不在範圍**：`kill -9` 的 daemon 沒走收工，子項還活著，照舊 adopt 接回；`sleep`／`wake` 不是 `aos-daemon-ctl` 的子命令（只有 daemon 收工／開門自己用；代定）。

### log

使用者「daemon和loop他們就是把log輸出到stdout」，「應該要改成默認不印」：`--enable-logs` 才印到 **stdout**（同 aos-loop；不寫 log 檔）。一行一個 JSON：

- **行程起來一行、結束一行**：`{"at": ISO 8601 UTC 毫秒, "name": 名字, "phase": "running"|"done"|"stopped"|"sleeping", "pid", "code", "signal"}`，起它時給了 `ws` 的多一欄 `"ws"`（最後一欄）。起來那行 `code`／`signal` 是 null；adopt 接回的也印一行 `running`；
  daemon 停掉的退了也是 `stopped` 那一行（列留在表上）；收工時收掉的 loop 型是 `sleeping` 那一行（列留在表上）、wake 起來印 `running`；`stopped` 的列被 rm、add＋stop 直接成的 `stopped` 列沒有行程起落，不印。
- daemon 自己有 `exec`（身體）時同 aos-loop 每跑完一次一行 `{"started_at", "counter_runs", "code", "signal", "elapsed_ms"}`；沒有身體不印每圈的行。
- 子項的 stdout 接 `/dev/null`（N-28），不會混進來；daemon 自己的身體繼承 daemon 的 stdout，會跟 log 交錯。印不了（關掉的管子）＝之後不印、照跑。

### 兩個手把、兩扇狀態窗

| 面向 | 手把（人寫） | 狀態窗（daemon 寫） |
|---|---|---|
| loop 面向與自身 | `ctl.json`（慣用名）：一道指令 `cmd`（`pause`／`resume`／`stop`）、`max`、`interval_ms`、`seq`（同 aos-loop，起來第一次讀的當基準線） | `state.json`（慣用名）：同 aos-loop（`phase`、`counter_runs`、`max`、`interval_ms`、`paused`、`ctl_seq`、`ctl_warning`、收尾的 `code`、`pid`、`started_at_ticks`、`boot_id`、`updated_at`），**沒有 `procs`** |
| 管轄（名單） | `procs_ctl.json`：`procs`、`procs_added`、`procs_removed`、`procs_stopped`、`procs_started`、`seq`；另可同時開信箱 `procs_ctl_mailbox`（見下） | `procs_state.json`：`{"ctl_seq", "ctl_warning", "mailbox_warning"（開了信箱才有）, "procs", "pid", "started_at_ticks", "boot_id", "updated_at"}` |

- 每圈先讀 ctl（`ctl.json`）、再讀 `procs_ctl.json`，**各自**採用或不採用（一份壞不影響另一份；壞的原因進各自那扇狀態窗的 `ctl_warning`、`ctl_seq` 回各自的 `seq`）。ctl.json 裡的名單 key（舊的 `loops*`、或 `procs*`）一律不認、不提醒。
- `procs_state.json` 的 `procs`：`{名字: {"pid", "started_at_ticks", "phase", "code", "signal", "stack", "ws"?}}`，`phase`∈`running`／`stopping`／`stopped`／`sleeping`；`stopped`、`sleeping` 的列 `pid`、`started_at_ticks` 是 null。
- `procs_state.json` 跟 state 一起看（`Loop::write_more`，每次要寫 state 都呼叫；沒開 state 也照呼叫），**有變才寫**：組好的那份（分檔前的表、`ctl_seq`、`ctl_warning`、`mailbox_warning`，不含 pid 那幾欄與 `updated_at`）跟上一份寫出去的一樣就不碰檔，不一樣才寫分檔→清舊分檔→寫主檔；daemon 對表時起一個、退一個也各寫一次。`pid`、`started_at_ticks`、`boot_id` 同一個行程的值——只讀這扇也能判 daemon 死活（N-17）。
- **`stop`**＝這圈收工（收子項照 P-36），不再看名單。**`pause`**（`resume` 解除）＝整圈暫停：不跑 `exec`、**也不調表**（不收多的、不起少的、起停也等；procs_ctl 的變動與信等解除暫停那圈才生效），
  但照讀兩份 ctl（`ctl_seq` 照回）、兩扇 state 照規則寫（有變才寫）、照收已在收的、照記自己結束的（`done`：印 log、拿掉、本次不再起）、daemon 要停的退了照樣留成 `stopped`。

### procs_ctl 只寫變動（N-54）

使用者「ctl這塊我會想要是"啓動XXX loop/刪除XXX loop"，而不是每次都讓他讀全部」，選「維持宣告式，但可以只寫變動的」：

```json
{"seq": 3, "procs_added": {"carl": "agent-carl"}, "procs_removed": ["bob"], "procs_stopped": ["ann"]}
```

- `procs_added`＝名單上要多這些（寫法同 `procs`，也能 `{"$ref": [檔, …]}`）；`procs_removed`＝名單上要少這些（名字的陣列）；`procs_stopped`／`procs_started`＝要停／要起的名字（下「起、停、暫停」）。
- **期望表＝（procs_ctl 的 `procs`，沒寫＝底）＋`procs_added`－`procs_removed`**，先加後減：同一個名字兩邊都寫＝不要；`procs_removed` 裡名單上沒有的名字不管；名單上已有的名字寫進 `procs_added`＝設定換成這份，已在跑的不重起。
- **stopped 集合＝底＋`procs_stopped`－`procs_started`**（同名兩邊都寫＝起）。
- 還是宣告（N-06）：只看這一份 procs_ctl 與底，讀幾次都一樣；**procs_ctl 拿掉 `procs_added`＝加進來的收掉**、拿掉 `procs_removed`＝減掉的照底重新起、拿掉 `procs_stopped`＝起。要一直加著、停著就一直寫著。
- 壞（不是 JSON 物件、`seq` 不是非負整數、三個名字陣列不是字串陣列、`procs`／`procs_added` 寫法或名字不合、指示詞解不開、`procs_stopped`／`procs_started` 有 exec 型）＝整份不採用、記 procs_state 的 `ctl_warning`。daemon.json 不認這幾個 key。
- **底**：起來時 daemon.json 的 `procs`（開了信箱再加 adopt 接回、不在上面的）＋信改過的，存在記憶體裡；stopped 集合的底＝adopt 接回的 `stopped` 列＋信改過的。只開 procs_ctl＝底就是 daemon.json（＋adopt 的 stopped）。

### 信箱（N-28、N-16）

多個人要改名單時，不必搶寫同一份 `procs_ctl.json`：daemon.json 寫 `"procs_ctl_mailbox": "procs_ctl_mailbox"`，大家各自投一封信（[aos-post](../aos-post/README.md) 的 `send`），daemon 每圈收。
跟 procs_ctl 可以同時開（procs_ctl 沒寫＝預設 `procs_ctl.json` 照開；寫 `null`＝不開）：**信是一次性的改動，改的是底**；**procs_ctl 是宣告，每圈疊在底上**；同一圈先套完信、再疊 procs_ctl、再對表。

```sh
echo '{"procs_added": {"bob": "../agent-bob"}}' | aos-post send "$AOS_STACK/procs_ctl_mailbox"   # 加 bob（字串＝exec 型）
echo '{"procs_stopped": ["ann"]}' | aos-post send "$AOS_STACK/procs_ctl_mailbox"                  # 停 ann（loop 型）
echo '{"procs_removed": ["bob"]}' | aos-post send --reply-to 我的信箱 "$AOS_STACK/procs_ctl_mailbox"   # 刪 bob，套用完回一封 {"applied": true}
```

- **起來時**：`aos::post::init` 建好 `tmp/`、`new/`、`cur/`（已在就沿用；`$AOS_STACK` 不在＝`MkdirFailed`、不替人建）。
- **底**＝daemon.json 的 `procs`＋重起時 adopt 接回、不在 daemon.json 裡的（只留名、設定記 null，不會被重起；`stopped` 的列 start 時照小格裡的 `loop.json` 起）＋依序套用的每封信；
  **接回的留在名單上，直到有信把它 `procs_removed`、或它結束**。自己結束（`done`）的從底一併拿掉；之後再有信同名 `procs_added`＝重新起。
- **每圈**（`stop`／`pause` 那圈不認領，信留在 `new/`，解除暫停那圈才套）：`new/` 全部認領（`aos-post take-all`，照處理順序：有序在前、照名字）→ 逐封驗、好的依序套進底（後面的蓋前面的）→ **全部套完、疊上 procs_ctl 才對一次表** →
  有 `reply_to` 的好信回一封 `body: {"applied": true}`（`in_reply_to`＝原信的信件名稱）→ 信收掉（`aos-post done`，不留 `archive/`）。起來時 `cur/` 不空（上次認領了、沒收完就死）＝照處理順序排在 `new/` 的前面重做。
- **信的 `body`**：物件，只認 `procs_added`（寫法同 `procs`）、`procs_removed`、`procs_stopped`、`procs_started`（名字的陣列），其他 key 忽略（舊名 `loops_added`、`execs_added`…也是）；
  一封裡的套法：`procs_added`→`procs_removed`（名單與 stopped 集合都拿掉）→`procs_stopped` 加進集合→`procs_started` 從集合拿掉。沒有整份的 `procs`（整份宣告留給 procs_ctl）。相對的 `exec`、`ws`、`stack`、`$ref` 都從 daemon 的 cwd 算。
- **壞信**＝信封壞（`aos::post::see`）、`body` 不是物件、型別錯、`procs_added` 的項不合格、指示詞解不開、`procs_stopped`／`procs_started` 有 exec 型（套完的底上看）：
  **丟掉、不套、不回信**，原因寫進 `procs_state.json` 的 `mailbox_warning`（`"信 <信件名稱> 不採用：原因"`，最後一封壞信的；之後的圈沒有壞信就維持原值）；不影響同一圈的好信。
- 回信寄不出去、收信失敗都不管，照樣往下走。要知道「加進去了沒」的標準做法是讀 `procs_state.json`。誰能寄：純靠 Linux 檔案權限（N-54 末）。

### 子項的工作區 ws

- **寫在哪**：proc 的**物件**多一個選填 key `ws`（字串或陣列寫法沒地方寫，要 ws 就寫成物件；exec 型物件 `{"exec", "ws"}` 仍是 exec 型）。daemon.json、procs_ctl 的 `procs`／`procs_added`、信都認。
- **值**：非空字串（指示詞照解）；**相對路徑從 daemon 的 cwd 算**，轉成絕對路徑（`abspath`）存進期望表。`null`＝當沒寫。其他型別、空字串＝壞（`CfgBad`／不採用／壞信）。在不在不驗（不在＝子項經 aos-exec 報 `WsMissing`）。
- **起子項時**：子行程的環境多設 `AOS_WS=<ws>`；**沒寫＝繼承 daemon 的環境**。loop 型的 `ws` 不寫進 `loop.json`，只進環境。`ws` 跟 `stack` 各管各的（`AOS_WS`／`AOS_STACK`）。
- **改了 ws**＝設定變了：已在跑的不重起、環境不變。列與 log 那兩行，起它時給了 `ws` 就多一欄 `"ws"`（起的那一刻的值）；沒給不寫這欄。`adopt` 照舊列的 `ws` 留著。

<a id="子項的-aos_daemon_stack11-02thinking-11-02-resident-bob-衝突-2"></a>
### 子項的 AOS_DAEMON_STACK

daemon 起子項（loop 型、exec 型都算）時，子行程的環境多設 **`AOS_DAEMON_STACK`＝daemon 自己的 stack**（`$AOS_STACK` 轉成絕對、結尾補 `/`，建構時算好 `dstack_`），**只設這一個**，一律蓋過去；`ws`、`stack` 都不影響它。
用處：兄弟（常駐 bob 的控制器與 bob）靠它找到共同的 daemon——讀 `procs_state.json`、叫 `aos-daemon-ctl`。條文在 [N-63、N-64 ④](../../docs/NORMS/10-基礎設施-定義與工作區.md)。

### 指示詞與切檔（N-28、N-45）

- **daemon.json、ctl 與 procs_ctl 的指示詞**（使用者「aos 讀的 JSON 全部支援」）：同 aos-loop 只解自己讀的格——再加 `procs`（本身、每項本身）、`adopt`、`procs_ctl`、`procs_state`、`procs_ctl_mailbox`；
  項是目標＝整個解；是物件＝只解 `exec`、`max`、`interval_ms`、`ctl`、`state`、`ws`、`stack`（搬進小格後相對 `$ref` 會從小格算，所以 daemon 先解），其他 key（`body`…）原樣。
  相對 `$ref` 從寫著它的那份檔所在的資料夾算（daemon.json 的資料夾；ctl、procs_ctl＝`$AOS_STACK` 底下那份的資料夾）。解不開：daemon.json＝`DirectiveBad` 退 1；ctl、procs_ctl＝不採用。
- **`procs` 拆成好幾份**（使用者「當loop太多的時候，json超大，我會希望他會自動用$ref切，每個檔案一百個」）：用 `$ref` 陣列（aos-directive，N-45）——幾份照順序合成一份物件，同名後面的蓋前面的；
  合不起來＝`DirectiveBad`、合出來不是物件＝`CfgBad`。不拆也能整份 `"procs": {"$ref": "procs.json"}`。每項裡的相對 `$ref` 從它來自的那份檔的資料夾算。
- **procs_state 自動切檔**：`procs` 表超過 100 列（`PART_ROWS`，不開 key）才切，每份最多 100 列、照表的順序；100 列以內維持物件：

  ```json
  {"ctl_seq": null, "ctl_warning": null, "procs": {"$ref": ["procs_state_procs/3f9a2c1e07d45b6a.json", "procs_state_procs/<雜湊>.json", ...]}, "pid": ..., "updated_at": ...}
  ```

  分檔資料夾＝procs_state 檔名去副檔名＋`_procs`、跟它同一層（預設 `procs_state_procs/`）；檔名＝內容的 FNV-1a 64 雜湊。每份先寫 `.` 開頭暫存再改名，內容沒變的沿用不重寫；
  分檔都寫好才寫主檔（**主檔改名是唯一的提交點**）；寫完清掉這次與上一次主檔都沒用到的分檔（行程第一次寫時不清），上一次的那些等下一次要寫但沒變的那一下再清；縮回 100 以內、清空後拿掉資料夾。
  讀的人用 aos-directive 解主檔（`aos-directive < procs_state.json`，cwd＝它的資料夾）就拿回整張 `procs` 物件。`adopt` 也是這樣解。

### 結束碼

| 怎麼結束 | 結束碼 | stderr |
|---|---|---|
| 跑滿 `max`、ctl `stop`、身體退 10 | 0 | 不寫 |
| 身體退其他非 0 | 那個碼 | 一行 `aos-daemon: 第 N 次 誰 失敗，結束碼 C` |
| 收到 SIGINT／SIGTERM／SIGHUP | 128＋N | 不寫 |
| 自己的錯（設定壞、沒 AOS_STACK、子項起不來、子 loop 的 ctl 寫不了、state／procs_state 寫不了、信箱建不了、沒有 exec 卻給了 `-- 參數`） | 1 | 一行 `aos-daemon: 代號 原因` |

不論哪一種，都先收掉所有活著的 proc（全部送 SIGTERM，等它們退；等的這段 state 寫一份 `phase` `stopping`、之後每退一批寫一次 procs_state；滿 10 秒還在的 SIGKILL 整群，連底下自成一群的單子）、寫好 state 再結束（P-36）：
收掉的 log 記 `stopped`、從表上拿掉——還在跑的 loop 型例外：log 記 `sleeping`、列留成 `sleeping`，下次開門自動 wake（上「收工與開門」）；最後一次之後才自己結束的記 `done`、`code`；daemon 停掉的（`stopped` 的列、等它自己退的那些）留在最後一份 procs_state 上。子項的結束碼不影響 daemon 的。

## 元素

```
 main ──▶ block_signals ──▶ loop_cli ──▶ Daemon(opts, 設定檔)（Loop 的建構子＋AOS_STACK／procs／adopt／procs_ctl／procs_state／信箱）──▶ Loop::serve
   每次 Daemon::tend ──▶ read_procs_ctl ──▶（ctl stop／pause＝只看一眼：look）
                       ──▶（信箱：take_letters 改底）──▶ ctl_want＋ctl_stopped ──▶ reconcile：look（結束了？）／term（多的）／halt（要停的：寫子 loop 的 ctl）／hold（停了：留 stopped）
                           ──▶ start（少的、要 start 的：spawn 寫小格 loop.json ──▶ run_cli({"--", 小格/loop.json#/_entry})；spawn_exec ──▶ run_cli({"--", 目標, 參數...})）──▶ done_letters
   Daemon::write_more ──▶ procs_state（有變才寫：procs 表＋write_parts）；Daemon::drop ──▶ log 一行、拿掉、done 的本次不再起；Daemon::finish ──▶ term（活著的）＋等到退（退一批 flush_table 一次）
```

| 檔 | 做什麼 |
|---|---|
| `src/common/common.hpp` | `using`、代號（全沿用 aos-loop 的） |
| `src/child/child.hpp`、`child.cpp` | 一個 proc：`Child`（`pid`、`phase`、`once`、`held`〔stopped／sleeping 的列〕、`soft`〔daemon 下的 stop〕、`nap`〔收工時收的 loop 型〕、`termed`、`stack`、`ws`…）；`spawn`（loop 型：小格、`loop.json`〔補 ctl／state、蓋 `_entry`、相對 exec 轉絕對、單子補 `cwd`、拿掉 `ws`／`stack`〕；設定 null＝照現有的 `loop.json`）、`spawn_exec`（exec 型：不寫 loop.json、單子寫 `exec.json`）、`make_cell`（預設小格兩層、自己的 stack `mkdir -p`）、`launch`／`run_child`（stderr.txt、fork、setsid、`/dev/null`、`AOS_STACK`、`AOS_DAEMON_STACK`、`AOS_WS`、cd、aos-exec 的 `run_cli`）、`alive`、`row`（多 `stack`；stopped 的 pid null） |
| `src/daemon/daemon.hpp`、`daemon.cpp` | `read_procs`（名單：名字規則、指示詞〔本身、每項各從它來自的檔算；單子只換一層、`abs_refs`〕、`fix_path` 處理 `ws`／`stack`、exec 型物件驗 `exec`）、`is_once`（看寫法）、`merge_want`；`Daemon`（`aos::loop::Loop` 的子類別）：建構子（`procs`、`procs_ctl`／`procs_state`／信箱的路徑、`dstack_`）、`adopt`（running 對得上才接、stopped 的列接成 stopped 並進 `stopped_`、sleeping 的列接成 sleeping 不進）、`tend`（ctl stop／pause 不調表）、`ctl_want`／`ctl_stopped`、`reconcile`、`look`、`term`／`settle`（收不等、10 秒 SIGKILL，連 `leaders_below`）、`halt`（寫子 loop 的 ctl `{"cmd": "stop", "seq": N}`）、`hold`、`start`／`cell_of`、`finish`、`add`／`drop`／`log_child`／`flush_table` |
| `src/daemon/windows.cpp` | 管轄那一對窗：`read_procs_ctl`（每圈讀 procs_ctl.json，同 read_ctl 的不採用規則）、`check_lists`（`procs`／`procs_added`／三個名字陣列）、`check_once`（exec 型沒有 stop／start）、`write_more`（procs_state.json：一張 `procs` 表；有變才寫）、`write_parts`（切檔）、`clean_parts` |
| `src/daemon/mailbox.cpp` | 信箱：`open_mailbox`（建 `tmp/`、`new/`、`cur/`，底多接回的、記下 `cur/` 的殘骸並照 `sort_letters` 排）、`take_letters`（`take_all` 認領、`see` 驗信封、逐封套進底、壞信記 `mailbox_warning`）、`apply_letter`（驗 body：`check_lists`、`check_once`；先在副本上套 `want_`／`stopped_`）、`done_letters`（回 `applied`、`done` 收信）；連 aos-post 的庫 |
| `src/main.cpp` | 命令列：`block_signals` → `loop_cli` → `Daemon` → `serve`；出錯印「aos-daemon: 代號 原因」 |

## 實作注意

- **繼承 aos-loop 的 `Loop`**：daemon.json 是 loop.json 的超集，每次讀 ctl、睡 interval、跑身體、寫 state、轉訊號都一樣；daemon 用 tend／finish／write_more 三個掛鉤（ctl 的檢查用 Loop 預設的）。ctl 的 stop／pause 由 Loop 照做完放在 `stopping_`／`paused_`，`tend` 看這兩格決定調不調表。
- **子 loop 經 aos-exec 起**（使用者「5.要」）：子 loop 跟別的程式一樣是「一個資料夾程式」——小格就是它的資料夾、`loop.json` 的 `_entry` 就是入口，所以小格裡放 `.env` 也有作用。
  fork 後在子行程裡呼叫 aos-exec 的 `run_cli`（不必在 PATH 上找 aos-exec），它最後 exec 成 PATH 上的 aos-loop，所以 `ps` 看到的子 loop 叫 `aos-loop`。
  fork 時 daemon 只有一條執行緒，子行程裡 C++ 配置、setenv 安全；三個訊號 daemon 一開始就擋著，子行程 exec 之前解開。
- **相對的 exec 照 daemon 的 cwd 轉絕對**：子 loop 經 aos-exec 起之後 cwd 是小格，不轉的話 `"exec": "../agent-bob"` 會從小格算。只轉字串與陣列的第一個元素，其他不動、不驗。
- **stop 的 seq**：daemon 寫子 loop 的 ctl 前讀它現有的 `seq`、取「自己數的＋1」與「現有的＋1」大的那個（遞增，內容一定跟上一道不一樣）——daemon 重起後計數從 0 開始，不這樣的話可能寫出跟子 loop 基準線一樣的內容、被當成同一道。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`，84 案、unittest，約 2 分鐘；`run_d`／`start` 一律帶 `--enable-logs`；結束的 phase／code 看 daemon 的 log：`ended`、`upped`、`logs`）：
  基本案（loop.json 直接丟給 daemon、要 AOS_STACK、名單壞、小格與窗、不自動重起、子項 stderr 在小格、ctl 增減、SIGTERM 收子項 143、旗標蓋過設定、exec 陣列與設定檔規則、子 loop 經 aos-exec 起、
  **字串子項＝exec 型跑一次**、收工時剛死的子項標 done、adopt、`adopt: false`）、錯誤代號、子 loop 的 state 是自己的 pid、daemon 重開照名單起、子項跟窗同名照起；
  效能 4 案（不肯退的子 loop 不卡住 daemon、睡著時兩扇窗不動、起子項之前先有 procs_state、`$AOS_STACK` 不在不建）；G 段（`procs` 用 `$ref` 陣列拆檔、寫壞、procs_ctl 的 `procs_added`／`procs_removed`、相對 `$ref`、切檔、切了檔照樣 adopt、縮回物件）；
  exec 直接放單子與還原、訊號、`abs_refs` 邊界、不理 SIGTERM 的單子隨子 loop 一起被 SIGKILL；
  H 段（**舊 key 不認**〔daemon.json 的 `loops`／`execs`／`loops_*`、ctl.json 與 procs_ctl 的 `loops_added`、信的 `loops_added`／`execs_added`：不起、不提醒〕、兩份 ctl 同一圈、ctl 壞 procs_ctl 好、`pause` 時 procs_ctl 的變動不生效、窗 `null` 與型別壞、跟窗同名照起）；
  I 段（信箱：同一圈照處理順序、`pause` 時信留著、接回的留到 `procs_removed`、壞信、`reply_to`、設定規則〔舊名 `loops_ctl_mailbox` 不認〕、`cur/` 殘骸重做、殘骸也照 aos-post 的處理順序〔有序名在前〕）；
  J 段（exec 型：三種寫法各跑一次、`procs_removed` 的 SIGTERM 直接打那支程式、**寫法規則與同名改寫法不重起**〔loop 型→exec 型不重起；拿掉再放回才照新寫法〕、adopt、`max: 1` 的 loop 跟 exec 型並排、信箱的 exec 型與 **exec 型的 stop／start＝壞信**、loop 型與 exec 型同一張表切檔）；
  K 段（`ws`）；L 段（log、done 的不再起、關掉的 stdout）；M 段（信箱與 procs_ctl 共存、procs_ctl 的整份 `procs`、exec 型收內嵌單子、窗全 null、`-- 參數`、running ⇄ waiting）；N 段（`AOS_DAEMON_STACK`）；
  **O 段**（`stack`：相對／絕對／結尾 `/`／`$env`、不在就建、`loop.json` 與 `stderr.txt` 都在 S、不建預設小格、兩個 proc 同一個 S 不擋、`null`＝預設、列上有 `stack`、`kill -9` 再起照列上接回、型別壞＝`CfgBad`）；
  **P 段**（stop／start：stop＝寫子 loop 的 ctl `{"cmd": "stop", "seq": N}`、跑完退 0、列 `stopped`／pid null、不重起；拿掉名字＝start、同一個 stack、ctl 不清；再停 seq 往上；同名兩邊都寫＝起；
  暫停中被停的 start 後起來先暫停、寫它的 ctl resume 才跑；信的 add＋stop＝列 `stopped`、stack 不建、同名 add 不叫起、`procs_started` 起、stopped 的 `procs_removed`；`kill -9` daemon 再起 stopped 的照停、要 `procs_started`；
  exec 型的 stop／start＝`ctl_warning`；daemon 暫停中起停等解除；繞過 daemon 寫子 loop 的 ctl stop＝列消失）；
  **Q 段**（sleep／wake：收工時跑著的 loop 型留 `sleeping`、再開自動 wake、`stopped` 照停、exec 型拿掉；Ctrl-C 收工、暫停中的醒來照暫停；信箱模式睡著時的信先套；
  醒來後與 stopped→start 後表上、log 的 `ws` 照舊，信箱接回只留名的子行程 `AOS_WS` 也照舊〔11-03 晚修〕）。
  PATH 放 impls 的 aos-exec、aos-loop 兩支的 `bin/`（子 loop 要 exec 成 PATH 上的 aos-loop）。
- `test_demo`（跑 `proto8/demo` 的 daemon、daemon-2、daemon-3）11-04 隨 demo 刪了。`test_cli` 要先建好 ../aos-exec、../aos-loop 的 `bin/`。
