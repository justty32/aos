查 aos-daemon 今天怎麼記表、收信、起停與收子項、當機後怎麼接回，對到使用者 11-25 定的「daemon＝Linux 與 aos 之間的橋＋procs 夾」：版面與大半行為已經對得上，最大的三個落差是表上的 PID 四成是外殼不是 proc 本身、行程多半站在共用的定義夾、根的 PID 寫進路徑後今天「daemon 死了再起把子項接回」會斷。

# aos-daemon 現況，對到「橋＋procs 夾」

← [架構規劃入口](../README.md)

寫這份的是這批的第 02 隻子 agent（fable）。只讀程式與活樹，實驗都在自己的暫存夾做，沒改任何既有的檔。三種話分開標：**原話**（使用者逐字）、**查到**（附 `檔:行` 或實驗輸出）、**推論**（我的判斷，沒有使用者的話就不算定）。路徑沒寫前綴的相對 `proto8/`；`daemon/…`、`child/…` 指 `cpp/aos-daemon/src/` 底下。

兩個詞先講：daemon 起子項是先「複製出一支子行程」（fork）。那支有時直接變成要跑的程式，有時留著當**外殼**，再往下起真正的程式、自己在旁邊等；真正在跑的那支下面叫 **proc 本身**。「收屍」＝父行程讀走子行程的結束狀態；讀走之前子是殭屍，PID 還佔著，讀走之後 PID 才可能被別的行程拿去用。

## 1. 結論

1. **版面與骨架已經對得上**：daemon 是普通 Linux 行程，自己有 ctl 與 state 檔，底下 `procs/<名>/` 就是每個 proc 的目錄，對完全不懂 aos 的程式也照樣起、殺、重起、記結束碼（2.1、2.8、3.1）。
2. **表上的 PID 不等於 proc 本身**：活樹 49 列裡 20 列（41%）的 PID 是外殼，名字還叫 `aos-daemon`，本身在下面一到兩層。`procs/<名>` 直接連 `/proc/<表上的 PID>/cwd` 會連錯（2.5、問 1）。
3. **行程多半不站在自己的夾**：49 列只有 12 列的本身站在自己的 stack，其餘站定義夾，同一個定義夾同時站著 6 隻。daemon 自己也站定義夾，從 `/proc/<根PID>/cwd` 進去看不到 `procs`（2.5）。
4. **連結要晚建、早拿**：fork 完馬上建，讀到的是 daemon 自己的夾，那一刻往 `procs/x/ctl` 寫 stop 會停到 daemon；子一死連結就斷；「先拿連結、再收屍」做得到（實測，3.3）。
5. **根的 PID 寫進路徑，接回會斷**：今天 daemon 被 `kill -9` 再起，子項同 PID 原封接回、一支都不重起（實測）。照字面用 `AOS_ROOT=/proc/<PID>/cwd`，根一重起，所有活著的子項手上的路都變死路（3.9、問 2）。
6. **控制 daemon 今天有五條路**，要收成純文字 ctl。字彙可以直接從信的六個動作來；難的是「加一列」那包 JSON、「一封信幾件事一起生效」、錯了怎麼說（2.4、3.4、問 5）。
7. **「問信箱在哪」今天不經 daemon**：寄信的人自己讀表檔、拼 `<stack>/mailbox`，daemon 死了也問得到。要「問的時候順手叫醒」，問這件事得先改成經過 daemon（3.6、3.8）。
8. **「只登記、不起」已經有大半零件**：不是自己生的列，daemon 照樣判活、送訊號；實測外來行程在小格擺一份 state，daemon 就接它而不另起。缺一個不帶「怎麼起」的入口，與「誰能登記誰的 PID」的規矩（3.7、問 4）。
9. **換了 subuid 的子項走不進 `/proc/<PID>/cwd`**：daemon 今天的 `limits.user: "sub:N"` 起的子項，實測讀 daemon 的 `/proc/<PID>/cwd` 是 `Permission denied`，走硬碟路徑卻讀得到（4 之 1）。

## 2. 查到的事實

### 2.1 daemon 自己的 stack 裡有什麼

| 檔 | 誰寫 | 內容 | 出處 |
|---|---|---|---|
| `ctl.json` | 人、`aos-daemon-ctl shutdown`、上一層 daemon（對它下 stop 時） | 一道指令：`cmd`（`pause`／`resume`／`stop`）、`max`、`interval_ms`、`seq` | `cpp/aos-daemon/docs/04:7`；`cpp/aos-loop/include/aos/loop.hpp:52-60` |
| `state.json` | daemon | `phase`、`max`、`interval_ms`、`paused`、`cgroup`、`daemon`（上一層的 stack，根＝null）、`group`、`poke`（三個訊號號碼）、有身體才有 `body_code`、`pid`、`started_at_ticks`、`boot_id`、`updated_at` | `daemon/table.cpp:99-109` |
| `state_flux.json` | daemon | `responded_at`、`ctl_seq`、`ctl_warning`、`procs_ctl_seq`、`procs_ctl_warning`、`adopt_warning`、`mailbox_warning` | `daemon/windows.cpp:192-201` |
| `procs_ctl.json` | 人 | 宣告式名單（2.4 第 2 條） | `daemon/windows.cpp:26-71` |
| `procs_state.json` | daemon | 表（2.3）；也是 daemon 重開時讀回來的存檔。超過 100 列切到 `procs_state_procs/` | `daemon/windows.cpp:203-244` |
| `procs_requests/{tmp,new,cur}` | 任何人投、daemon 收 | 信（2.4 第 1 條）；底下 `reply/` 是 aos-daemon-ctl 建的共用回信箱 | `daemon/mailbox.cpp` |
| `procs/<名>/` | daemon 建 | 每個 proc 的 stack（2.5） | `daemon/reconcile.cpp:15-20` |
| stack 資料夾本身的鎖 | daemon | flock：同一個 stack 只准一台 daemon；行程一死就放 | `daemon/daemon.cpp:265-284` |

活樹根 daemon 現在的三份（11-25 中午讀的）：

```
state.json      {"phase": "waiting", "max": null, "interval_ms": 200, "paused": false, "cgroup": "off", "daemon": null,
                 "group": 60001, "poke": {"ctl": 35, "mail": 36, "all": 37}, "pid": 2223, "started_at_ticks": 31414, "boot_id": "e055…", "updated_at": "…"}
state_flux.json {"responded_at": "2026-11-25T03:12:11.514+00:00", "ctl_seq": 7, "ctl_warning": null, "procs_ctl_seq": null,
                 "procs_ctl_warning": null, "adopt_warning": null, "mailbox_warning": null}
ctl.json        {"cmd": "stop", "seq": 7}
```

`ctl.json` 還留著上一次收工那道 stop，daemon 活著、沒照做，因為回音 `ctl_seq` 已經是 7。這就是 [9p-proc-1125](../../9p-proc-1125.md) 說的「落檔的實作檔案永遠寫得進去，才需要 seq」的實例。

### 2.2 daemon.json 的 key

| 管什麼 | key | 出處 |
|---|---|---|
| 自己這個迴圈（同 aos-loop） | `exec`（自己的身體，選填）、`max`、`interval_ms`（預設 200）、`ctl`／`state`／`state_flux`（檔名或 null）、`on_start`／`on_stop`、`gate` | `cpp/aos-daemon/docs/01:15-29` |
| 名單 | `procs`（{名字: 寫法}）、`procs_ctl`、`procs_state`、`procs_requests`（檔名或 null）、`adopt`（預設 true） | 同上 |
| 小格裡 daemon 寫的三個檔名 | `procs_loop`、`procs_exec`、`procs_stderr`（預設 `loop.json`、`exec.json`、`stderr.txt`） | 同上 |
| 份額 | `limits`（預設）、`limits_max`（天花板）、`cgroup`（off／auto／on）、`group` | `docs/09` |
| 每一列的寫法 | 字串或陣列（目標＋參數）；或物件：`exec`、`ws`、`stack`、`def`、`limits`、`auto_restart`、`restart_on_stuck`、`stuck_after_cycles` 或 `stuck_after_ms`、`as_written`。物件多任何一個別的 key（`max`、`interval_ms`…）＝包成一支 aos-loop 一直跑 | `docs/02:5-18`；`daemon/procs.cpp:197-210` |

名字不能是空的、不能有 `/` 或 `#`、不能以 `.` 開頭（`daemon/procs.cpp:11-15`），都能當資料夾裡的項名。

### 2.3 procs_state.json 每個欄位

頂層：`procs_loop`、`procs_exec`、`procs_stderr`、`procs_requests`（null＝沒開信箱）、`daemon`（上一層）、`procs`（表）、`pid`、`started_at_ticks`、`boot_id`、`updated_at`（`daemon/windows.cpp:214-239`）。有變才寫。

每列（`child/child.cpp:356-432`）：

| 欄 | 意思 |
|---|---|
| `pid`、`started_at_ticks` | daemon 直接 fork 出的那支，與它的啟動時間（`/proc/<pid>/stat` 第 22 欄）；停著、睡著＝null |
| `phase` | `running`／`stuck`／`stopping`／`stopped`／`sleeping` |
| `code`、`signal`、`reason` | 上一次怎麼結束；`reason` 是一句英文（為什麼停著、在等第幾次重起、卡多久了） |
| `stack` | 它的目錄，存成相對 daemon 的 stack；預設 `procs/<名>` |
| `ws`、`exec`、`def` | 工作區（有給才有）、起它時的目標、定義夾 |
| `launch` | 重起用的完整入口與參數 |
| `stop_mode` | 只在 `stopping`：`stop`／`sleep`／`remove`（daemon 中途死掉，重開照它接著收） |
| `auto_restart`、`restart_on_stuck`、`stuck_after_cycles`／`stuck_after_ms`、`counter_restarts` | 常駐與判卡住的設定、重起過幾次 |
| `limits`、`limit_hit`、`limit_suspect`、`limits_ignored`、`cgroup` | 份額與有沒有撞到 |
| `as_written` | 使用者原本寫的路徑原形（指示詞或絕對路徑），每次起再解 |

只在記憶體、daemon 一重起就歸零的：這列是不是自己生的、連著失敗幾次、退避到幾時、卡住的期限、手動叫睡的名單（所以睡著的列 daemon 重開會自己醒）（`child/child.hpp:48-64`；`daemon/daemon.hpp:253-258`）。

### 2.4 控制 daemon 的五條路

| # | 路 | 誰在用 | 內容 | 怎麼回 |
|---|---|---|---|---|
| 1 | 寄信到 `procs_requests/` | `aos-daemon-ctl add／rm／stop／start／sleep／wake／ping`；`aos-agent ctl …`（設了 `AOS_KERNEL` 就先寄到 kernel 站） | body 只認八個 key：`procs_added`（{名: 寫法}）、`procs_removed`、`procs_stopped`、`procs_started`、`procs_slept`、`procs_woken`（名字陣列）、`ping: true`、`procs_state_path: true`。一封裡照固定順序套：加→拿→停→起→睡→醒 | 有 `reply_to` 才回：好信 `{"applied": true}`（查詢信多帶表的絕對路徑）；body 壞 `{"applied": false, "error": {"code": "BodyBad", "msg": …}}`。信封壞不回，只記 `mailbox_warning`。daemon 暫停或收工中不收信、不回＝這次呼叫失敗 |
| 2 | `procs_ctl.json` | 活樹 10 張表沒有一張有這個檔 | 整份名單或只寫變動；每圈疊在「信改過的名單」上面 | `state_flux` 的 `procs_ctl_seq`、`procs_ctl_warning` |
| 3 | 直接寫子的 `ctl.json` | `aos-daemon-ctl pause／resume`（不經 daemon）；daemon 替 `stop` 寫 | `{"cmd", "seq"}` | 子的 `state_flux.ctl_seq` 跟上 |
| 4 | daemon 自己的 `ctl.json` | `aos-daemon-ctl shutdown`（寫 stop→送 poke→等行程不在） | 同 2.1 | 行程不在了 |
| 5 | poke | `aos-daemon-ctl poke` | 訊號 `SIGRTMIN+1／2／3`：叫 daemon 不等下一圈、馬上看一次檔；不帶內容 | 沒有 |

出處：`daemon/mailbox.cpp:111-197`；`daemon/tend.cpp:120-137、270-320`；`py/aos/daemon_ctl/ctl.py:63-75、125-160`；`py/aos/apps/daemon_ctl/main.py:567-582、759-763`；`daemon/daemon.cpp:18-54`。

- `applied` 的意思是「套進名單了」，不是「起來了」；結果要讀表。回信在那一圈對完表之後才寄。
- `set-def` 不是 daemon 認的信，是 aos-agent 那邊三步：停→拿掉→用同一個 stack 加回去。加回去那封同時帶 `procs_slept` 或 `procs_stopped`，靠的是「加＋睡寫在同一封＝上表但不起」（`py/aos/apps/agent/ctl/set_def.py:88-110`；`daemon/reconcile.cpp:367-389`）。
- 六個動作在指令那邊先照表擋一輪（stop 只收 running、start 只收 stopped、wake 只收 sleeping，錯了 `PhaseBad`；`py/aos/daemon_ctl/ctl.py:29-56`）。daemon 自己不擋。

### 2.5 怎麼起子項；表上的 PID 是誰、站在哪

| 階段 | 做什麼 | 出處 |
|---|---|---|
| fork 之前（daemon） | 建小格（`procs/<名>/`，或那列寫的 `stack`）；包 aos-loop 的寫 `loop.json`，內嵌單子寫 `exec.json`；開 `stderr.txt`（附加）；備好份額 | `child/child.cpp:104-153、216-293` |
| 子行程裡 | `setsid`（自成一組，不跟父的終端機）→ stdin、stdout 接 `/dev/null`，stderr 接小格的 `stderr.txt` → 進 cgroup 格（有開才做）→ setrlimit、換帳號 → 設 `AOS_STACK`＝小格、`AOS_DAEMON`＝daemon 的 stack（一律蓋掉），寫了 `ws` 才設 `AOS_WS`，其餘環境照繼承 → cd 到 **daemon 的 cwd** → 在行程裡呼叫 aos-exec：它再 cd 進入口檔所在的夾、讀那裡的 `.env`，然後開跑 | `child/child.cpp:49-100` |
| fork 之後（daemon） | 記 PID 與啟動時間、放上表、寫 `procs_state.json`（起一大批時最多 200 毫秒寫一次） | `child/child.cpp:174-186`；`daemon/reconcile.cpp:312-323` |

aos-exec 最後一步有兩種（`cpp/aos-exec/src/launch/launch.cpp:83-101`）：入口是執行檔或 argv 陣列＝直接變成那支程式，PID 不變；入口是單子（物件）＝自己留著，另起一支去跑、在旁邊等。所以表上的 PID 有下面幾種樣子（實驗 E1，暫存樹）：

| 那一列怎麼寫 | 表上 PID 的程式名（暫存樹） | 它站在 | proc 本身 | 小格裡的檔 |
|---|---|---|---|---|
| 包 aos-loop（daemon 寫 `loop.json`） | `aos-loop` | 自己的小格 | 同一支 | `loop.json`、`stderr.txt`，加它自己寫的 `state.json`、`state_flux.json` |
| 目標是定義夾，入口是 argv 陣列 | `sleep` | 定義夾 | 同一支 | `stderr.txt` |
| 目標是定義夾，入口是單子物件 | `aos-daemon`（外殼） | 定義夾 | 下一層的 `sleep`，站定義夾 | `stderr.txt` |
| 內嵌單子（寫進小格 `exec.json`） | `aos-daemon`（外殼） | 小格 | 下一層的 `sleep`，站 daemon 的定義夾 | `exec.json`、`stderr.txt` |
| 普通執行檔 `["/usr/bin/sleep", "600"]` | `sleep` | `/usr/bin` | 同一支 | `stderr.txt` |

暫存樹的 daemon 自己：站 `$B/def`，那裡只有 `_entry`、`daemon.json`；`procs`、`procs_state.json`、`state.json` 都在 `$B/stack`。

活樹（11-25 12:16 那一刻，10 張表、49 列、全 running；樹一直在變，12:05 是 44 列）：

| 表上的 PID 是 | 站在自己的小格 | 站在定義夾等別處 |
|---|---|---|
| proc 本身（29 列） | 12（`_clock` 1 列、`_sweeper` 10 列、llm kernel 的請求列 1 列；都是包 aos-loop 的寫法，沒有一隻 agent） | 17 |
| 外殼（20 列） | 14 | 6 |

- 同一個夾被不只一個表上 PID 站著的有 3 個；`templates/agents/eca-claude` 同時站著 6 隻。
- 根 daemon（PID 2223）站 `~/aos-home/root`，裡面是 `.env`、`README.md`、`_entry`、`daemon.json`；它的 stack 在 `~/aos-home/.stack`。起它的殼手上的 PID 其實是 2222（`aos-exec root`，外殼），2223 才是 daemon。
- 根表上 `repo-aos` 那列的 PID 2228 是外殼，底下 2233 是 `aos-exec`，再底下 2239 才是 repo-aos 這台 daemon；repo-aos 自己 `state.json` 寫的 pid 是 2239。
- `ps` 看得到 30 支叫 `aos-daemon` 的，真的 daemon 只有 10 台。

小格同時是「父放東西的地方」與「子自己的 stack」：`~/aos-home/.stack/procs/repo-aos/` 裡，`exec.json`、`stderr.txt`、`ctl.json` 是根放的或寫的；`state.json`、`procs_state.json`、`procs_requests/`、`procs/` 是 repo-aos 自己的。根對它下 stop，就是往這個夾的 `ctl.json` 寫 stop，repo-aos 把它當自己的 ctl 讀到、自己收工。

### 2.6 停、收屍、重起、判卡住、當機復原、份額

| 事 | 今天怎麼做 | 出處 |
|---|---|---|
| stop | 往它小格的 ctl 檔寫 `{"cmd":"stop","seq":N}`，列變 `stopping`，等它自己退；沒有時間上限、不改送訊號；退了留 `stopped` | `daemon/tend.cpp:120-137` |
| sleep、rm、daemon 收工、卡住重起 | 對表上那個 PID 送 SIGTERM；10 秒後還在＝SIGKILL 它那一群、底下自成一群的、（有開）整個 cgroup 格。包 aos-loop 的列，送之前先在小格寫 `stop_cause.json` 說原因 | `daemon/tend.cpp:22、81-118、156-176` |
| 收屍 | 每圈對每列 `waitpid`（不等）；拿到結束碼或訊號（被訊號打掉記 128＋N）。不是自己生的列（接回的）改比 `/proc` 裡的啟動時間，拿不到碼 | `child/child.cpp:301-354` |
| 結束之後 | 退 0＝從表上拿掉，小格留著；非 0＝列留 `stopped`＋`reason`（3 秒內退寫 `failed to start`，其餘 `failed while running`，後面接 `stderr.txt` 最後一個非空行，最多 300 位元組）；接回的拿不到碼＝拿掉 | `daemon/tend.cpp:181-268`；`daemon/failure.cpp:61-123` |
| `auto_restart` | 自己退了就照表重起：第 1 次同一拍，連著的等 1、2、4…秒，上限 60 秒，撐過 60 秒重算；連 3 次都在 3 秒內退＝留 `stopped`。等的期間列是 `sleeping`。次數與等待只在記憶體 | `daemon/tend.cpp:196-227`；`daemon/daemon.hpp:87-93` |
| cooldown | daemon 沒有這個詞。agent 的腦失敗後那份 `cooldown.json` 是身體寫在自己 stack 裡的，daemon 不讀；daemon 這邊像冷卻的只有上一列的退避 | `knowledge/aos/cli/agent.md:52` |
| 判卡住 | 預設不判（門檻沒寫＝0）。寫了門檻的列：子的 ctl 檔修改時間比它 `state_flux.responded_at` 新、也比父起它的時間新＝有人下了指令；過了期限還沒回＝表上標 `stuck`＋原因，回了就回 `running`。父只看子的 ctl 檔時間與 `state_flux`，不讀它的 state、不看它的信箱。列上寫 `restart_on_stuck` 才殺掉重起，連 3 次留 `stopped` | `daemon/stuck.cpp:10-90`；NORMS N-17 |
| daemon 當機後再起 | 讀自己上次的 `procs_state.json`：`boot_id` 相同、PID＋啟動時間對得上、那支的環境變數 `AOS_STACK`／`AOS_DAEMON` 指的是這棵樹＝接回、不重起。對不上＝列留 `stopped`，原因 `ended while the daemon was not running`（daemon.json 寫的列與 `auto_restart` 的照舊再起）；`stopping` 的照 `stop_mode` 接著收；`sleeping` 的第一圈叫醒 | `daemon/adopt.cpp:144-334` |
| 起之前再看一眼 | 小格裡若有一份 state 檔、記的 PID 還活著＝接它、不另起（上一個 daemon「fork 了、表還沒寫」就死的那種） | `daemon/reconcile.cpp:59-88`；`daemon/adopt.cpp:96-121` |
| 份額 | 每列 `limits`：rlimit（每個行程各自的上限，不從 daemon 總額扣）、換帳號（要 root）或 `sub:N`（免 root，另開 user namespace）；可選 cgroup v2（整列連子孫的記憶體與行程數，要先有委派）；超過 `limits_max`＝那列起不來。都在 fork 之後、變成那支程式之前由 daemon 做，proc 自己不知道。活樹 10 台 `cgroup` 都是 off，49 列只有 1 列有 `limits` | `cpp/aos-daemon/docs/09`；`child/child.cpp:65-85` |

### 2.7 根與子；shutdown、睡與醒

同一支程式、同一套檔，差別只有：

| | 根 | 子 daemon |
|---|---|---|
| 誰起 | 人：`aos-exec --stack S 定義`，起之前要清掉殼裡的 `AOS_DAEMON` 等 | 上一層表上的一列，對上一層是普通 proc |
| `daemon` 欄 | null | 上一層的 stack（起來時繼承到的 `AOS_DAEMON`，`daemon/daemon.cpp:193-207`） |
| 誰顧 | 使用者（或自己交給 systemd／s6）；死了沒人重起。活樹的根是 zsh 底下直接起的 | 上一層：寫了 `auto_restart` 就重起，寫了門檻就判卡住 |
| 時鐘 | 範本帶 `_clock` 列與 `.env` 的 `AOS_CLOCK` | 不帶，聽根的 |
| 怎麼停 | `aos-daemon-ctl shutdown` 或 Ctrl-C | 對上一層下 `stop <名>`；對它自己下 shutdown，上一層的 `auto_restart` 會馬上把它拉起來（`templates/daemons/daemon-sub/README.md:47`） |

**原話**（11-06，`cpp/aos-daemon/docs/02:17` 引）：「對於daemon來說，子daemon對他來說就只是一個普通的proc。不要耦合」。**原話**（11-05，`thinking/2026-11/05/no-pid/README.md`）：「關於root daemon，我覺得不用限制他一定要怎樣怎樣，他就是一個普通daemon，只是說因爲他頭上沒daemon了，所以使用者要保証他能正常運行。」同一段後面：「但也可以就只是一個普通的linux user proc，壞了就壞了。」

- **收工**（shutdown、SIGINT／SIGTERM／SIGHUP、身體退 10、跑滿 `max`）：所有活著的列送 SIGTERM（10 秒後 SIGKILL）；原本 running 的留 `sleeping`，stop 途中的留 `stopped`，rm 途中的拿掉；寫好表才退（`daemon/tend.cpp:321-371`）。
- **重開**：讀表，`sleeping` 的第一圈用同一個 stack 再起，`stopped` 的不起，要人 `start`。
- **整棵樹**：父對子 daemon 送 SIGTERM，子 daemon 自己收工、把自己的列留 `sleeping` 才退，所以葉先睡、根最後；醒的時候反過來。每層自己做，父不排順序（`cpp/aos-daemon/docs/03:32`）。

### 2.8 完全不懂 aos 的普通行程，今天被怎麼顧（實驗 E2）

列 `plain`＝`["/usr/bin/sleep", "600"]`：

| 做什麼 | 實測結果 |
|---|---|
| 起 | 表上一列 `running`，PID 就是 `sleep`，站 `/usr/bin`；小格只有 `stderr.txt` |
| `pause` | 小格多一份 `ctl.json`＝`{"cmd": "pause", "seq": 1}`，行程照跑；指令退 0，多一行 `warning: plain has not applied pause (seq 1) within 1 s …` |
| `stop` | 列 `stopping`（`stop_mode: stop`），`ctl.json` 變 `{"cmd": "stop", "seq": 2}`；1 秒後行程還在，會一直等下去 |
| 再下 `sleep` | SIGTERM；列 `stopped`、`code` 143、`signal` 15 |
| `start` | 同一個小格再起，新的 PID |
| 從外面 `kill -9` | 94 毫秒後表跟上：`stopped`、`code` 137、`signal` 9、`reason`＝`failed to start: exited within 3s of wake/start (code 137, signal 9)` |
| 退 0 的（`/usr/bin/true`） | 那一列直接從表上消失 |
| 退 3、stderr 印 `boom` 的 | `stopped`、`code` 3、`reason`＝`failed to start: exited within 3s of wake/start (code 3): boom` |
| 判卡住 | 不判（小格沒有 `state_flux`） |

所以對這種行程，今天通的是：起、殺（sleep／rm／收工）、重起、結束碼與訊號、原因、stderr 存檔、份額、表上一列。不通的是 stop、pause、resume，三樣都是寫一個沒人讀的檔。

### 2.9 外來行程自己擺檔，daemon 會接（實驗 E3）

一支不是 daemon 生的行程（父是我的腳本），自己在 `procs/foreign/` 放一份 `state.json`，寫自己的 `pid`、`started_at_ticks`、`boot_id`。再對 daemon 下 `add -n foreign <隨便一個定義>`：

```
foreign: {"phase": "running", "pid": 2229770, "launch": {"exec": "../defs/arr"}, "def": "../defs/arr"}
foreign pid=2229770 ppid=2229085 (root daemon is 2229099); row pid == foreign pid: True; new children of the daemon: []
after the foreign process exits (reaped by its real parent, not the daemon):   foreign: (not on the table)
```

daemon 沒有起任何東西，表上那列的 PID 就是外來那支；它結束後（別人收的屍）列直接消失，沒有結束碼。這是 2.6「起之前再看一眼」那條的副作用，不是做成功能的入口。

### 2.10 daemon 被 `kill -9`（實驗 E4）

輸出節錄（`[…]` 是我略掉的字）：

```
before: /proc/2229099/cwd exists=True
after : /proc/2229099/cwd exists=False ; children:
      loopinline pid=2229102 alive=True ppid=3117(Relay(3127))
      arr        pid=2229103 alive=True ppid=3117(Relay(3127))
      obj        pid=2229104 alive=True ppid=3117(Relay(3127))
      inl        pid=2229105 alive=True ppid=3117(Relay(3127))
table on disk still says: {'loopinline': 'running', 'arr': 'running', 'obj': 'running', 'inl': 'running', 'plain': 'stopped', 'bad': 'stopped'} ; top-level pid=2229099
$ aos-daemon-ctl ping --timeout-s 1  -> rc=1 | stderr: aos-daemon-ctl: error: DaemonFailed no reply from the daemon at $B/stack within 1 s ([…])
restarted: new daemon pid=2230240 ; rows: {'loopinline': ('running', 2229102, 'same pid'), 'arr': ('running', 2229103, 'same pid'), 'obj': ('running', 2229104, 'same pid'), 'inl': ('running', 2229105, 'same pid'), […]}
state_flux adopt_warning = None
$ aos-daemon-ctl shutdown --timeout-s 20  -> rc=0 daemon at $B/stack stopped (ctl seq 1); 4 procs asleep, they wake when it starts again
```

daemon 死著的時候 `aos-daemon-ctl ls` 照印表，後面兩行是（另一次跑的，只掛一列）：

```
plain	running	2428175	-	-	-
# daemon: not running (pid 2428174 is gone); the table above is what it left
# root daemon (no supervisor)
```

子項都活著（每支自成一組；daemon 與它直接生的子之間沒有「父死子跟著死」的設定，那個設定只在外殼與它底下那支之間，`cpp/aos-inst/src/inst_proc.c:20-23、122`），被別的行程收養。硬碟上的表還寫著 running 與死掉的 PID。新的 daemon 把四列同 PID 接回，沒有重起任何一支；接回之後收工，四支也都收得掉。

## 3. 對新介面的含意

### 3.1 今天已經是這樣的

| 定了的 | 今天 |
|---|---|
| daemon 是普通 Linux 行程 | 是。一支靜態連結的執行檔，沒有特權；活樹的根就是殼裡起的行程 |
| daemon 也是 aos proc，上層能對它下 ctl、看 status | 是，只是用 JSON：`ctl.json`、`state.json`、`state_flux.json`（它繼承 aos-loop）。上一層對它下 stop 就是寫它的 ctl |
| 多一個放各 proc 的資料夾，每項連到那個 proc 的目錄 | 版面是：`<daemon 的 stack>/procs/<名>/` 就是那個 proc 的 stack（活樹 49 列只有 1 列放別處）。但它是真的資料夾、不是連結；proc 死了還在；夾裡有的不等於表上有的（repo-aos 的 `procs/` 有 8 個夾，表上 5 列，3 個是表上已經沒有的舊夾）。今天認「這個夾是不是 daemon」是看裡面有沒有 `procs_state.json`（`py/aos/comm/walk.py:16-17`） |
| `proc` 與 `procs` 兩個名字指同一處 | 今天只有 `procs`，名字寫死在程式裡（`daemon/reconcile.cpp:19`；`py/aos/daemon_ctl/table.py:219`）。多放一個 `proc` 連到它就有了（推論） |
| kernel 是普通 aos proc | 一半。子 daemon 對父是普通一列；但今天的 llm kernel 是「daemon＋自己的身體」（daemon.json 的 `exec`），長在 daemon 這支程式上（活樹 10 台有 1 台）。細節在 [14](14-kernel過去的規劃對照新模型.md) |
| Linux 那邊的事歸 daemon | 是。訊號、fork、收屍、份額都只有它做（N-17：「只有 aos-daemon 與這支指令懂訊號，proc 與其他 aos 程式只寫檔」） |
| 掛了就問 daemon 信箱在哪、改寄信 | 後半有：表上每列的 `stack` 停著睡著都留著，信箱固定是 `<stack>/mailbox`。前半（活著走 socket）沒有，在 [05](05-信與IPC現況.md)、[20](20-送訊息兩條路的細節.md) |
| 要留的放 `procs/<名>/persist` | 今天整個 `procs/<名>/` 都留著，rm 也不刪 |
| token 用量 daemon 不管帳 | 是，表上沒有任何用量欄 |
| 入口是根 daemon 的 PID | 還不是。今天入口是硬碟路徑：`AOS_DAEMON`＝daemon 的 stack，起子項時一律設（`child/child.cpp:89`） |

### 3.2 要變的

| # | 項目 | 今天 | 新模型要的 | 動到哪（推論） |
|---|---|---|---|---|
| 1 | daemon 站哪 | 定義夾；起來時把它記成變數 `cwd_`，當子項相對路徑的基準（`daemon/daemon.cpp:178`） | 自己的身體，不然 `/proc/<PID>/cwd` 底下沒有 `procs` | 記完之後補一次 cd；靠行程的 cwd 算相對路徑的幾處改用 `cwd_`（查到 `daemon/procs.cpp:81`、`daemon/reconcile.cpp:211-217`）；起自己的身體、`on_start`、`gate` 之前要 cd 回去 |
| 2 | 子項站哪 | aos-exec 一律 cd 進入口檔所在的夾 | 自己的身體 | 這是 aos-exec／aos-loop 的慣例，定義裡的相對路徑靠它；歸 [01](01-aos-loop現況.md)、[03](03-agent-fsm身體與stack現況.md)、[04](04-eca身體與stack現況.md)、[06](06-路徑、環境變數與命名現況.md) |
| 3 | `procs/<名>` 是什麼 | 真的資料夾（父建的小格＝子的 stack） | 連到活著的 proc 的目錄 | 真夾與連結不能同名（實測 `File exists`）：身體得放在別的位置，`procs/<名>` 才能是連結 |
| 4 | 連結指到誰 | — | proc 本身的 PID，不是表上那個 | 3.3、問 1 |
| 5 | 父往子的夾裡放的檔 | `loop.json`／`exec.json`（怎麼起）、`stderr.txt`、`stop_cause.json`、`ctl.json` 的 stop | 身體是 proc 自己的 | 「怎麼起」與 stderr 是橋這邊的事，改放 daemon 自己那邊；停的原因可以直接寫在 ctl 那一行 |
| 6 | 表放哪 | `procs_state.json`，在 daemon 的 stack | daemon 的 persist；每列多「persist 在哪」「本身的 PID」，少 `stack` | 3.9 |
| 7 | 控制 | 2.4 的五條路 | 純文字 ctl | 3.4 |
| 8 | 判卡住 | 比子 ctl 檔的時間與 `responded_at` | 定了的是「寫 ctl 回來＝收到」；所以寫不進去、等不到回，寫的人當場就知道（推論） | 對落檔的子，原來那套還要留 |
| 9 | `ping`、`procs_state_path`、poke | 三樣都是因為「檔永遠寫得進去、表在哪要用問的、daemon 是輪著看檔」才有 | ctl 會回、`procs` 在固定名字 | 可以不帶進新介面 |
| 10 | 環境變數 | `AOS_STACK`＝小格、`AOS_DAEMON`＝上一層的 stack，都是硬碟路徑 | `AOS_ROOT`、`AOS_DAEMON=$AOS_ROOT/procs/…` | `child/child.cpp:88-92` 那幾行。daemon 今天不知道自己在上一層叫什麼名字，只知道上一層的路；要拼 `$AOS_ROOT/procs/a/procs/b` 就得由上一層起它時告訴它 |
| 11 | daemon 怎麼等 | 每 200 毫秒一圈：讀兩份 ctl、列信箱、每列問一次「退了沒」、組整張表比有沒有變（`daemon/tend.cpp:270-320`） | ctl 有人寫才動、子退了才動 | 歸 [11](11-閒置成本、時鐘與等待.md) |

### 3.3 `procs/<名>` 連結：什麼時候建、什麼時候拿

實測（暫存夾裡一支「daemon」與一支子；各自的夾裡有 `status`）：

```
(a) right after fork : procs/kid/status -> name: daemon | readlink /proc/kid/cwd -> $B/daemon
    after kid chdir   : procs/kid/status -> name: kid
(b) zombie (state Z) : procs/kid/status -> <No such file or directory> | os.path.lexists(link) = True
    waitid WNOWAIT    : si_pid=2237595 si_code=2 si_status=9 ; /proc/2237595 still there: True
    unlink first      : lexists(link) = False ; then reap -> (2237595, 9) ; /proc/2237595 there: False
(c) symlink over the real cell dir -> File exists
```

- **建**：fork 完不能馬上建。子行程一開始站的是 daemon 的夾（真的 daemon 的子行程在交給 aos-exec 之前都站在 daemon 的 cwd，`child/child.cpp:93`），這時 `procs/kid/status` 讀到的是 daemon 自己的，往 `procs/kid/ctl` 寫 stop 停的是 daemon（a）。推論：等那個 proc 站好、報到之後才建，建之前 daemon 先讀一次它的 `status`／`settings` 核對名字與 PID。
- **拿**：子一死、還沒收屍，連結就走不進去了，連結檔本身還在（b）。收屍之後 PID 可能被別人拿去用，舊連結就指到別人的 cwd。推論：順序是「先拿連結、再收屍」。今天 daemon 一步就收（`child/child.cpp:316`）；實測可以先偷看結束狀態、不收屍，拿掉連結再收。要插的地方是 `alive()`（`child/child.cpp:301`）、`hold()`（`daemon/tend.cpp:139`）、`drop()`（`daemon/table.cpp:33`）。
- **換**：重起＝新 PID。推論：連結要一步換掉（建在暫名、再改名蓋過去），不能先刪再建，不然中間有人讀到「沒有這隻」。
- **不是自己生的列**（接回的、外來的）沒有殭屍期可以利用：收屍的是別人，daemon 只能每圈比啟動時間，最多晚一個 `interval_ms`（預設 200 毫秒）。這台 `pid_max` 是 4194304，200 毫秒內 PID 被重用幾乎不可能，但不是零（推論）。
- **daemon 不在的時候**，硬碟上的連結沒人顧；重開機後整批都是垃圾。推論：procs 夾放在關機就沒的地方（tmpfs），或 daemon 起來先把對不上的連結清掉。今天接回時本來就逐列比 `boot_id`、PID、啟動時間（`daemon/adopt.cpp:197-199、277-281`）。
- **停著、睡著的列沒有 PID**，連結指不到東西（問 3）。

### 3.4 daemon 自己的純文字 ctl：今天的字彙

| 今天 | 對照（只是照翻，寫法歸 [18](18-ctl、status、settings的候選寫法.md)） |
|---|---|
| 信 `procs_removed`／`procs_stopped`／`procs_started`／`procs_slept`／`procs_woken` | `rm x`／`stop x`／`start x`／`sleep x`／`wake x` |
| daemon 自己 ctl 的 `cmd`、`max`、`interval_ms` | `pause`／`resume`／`stop`、`max 10`、`interval_ms 500` |
| 信 `procs_added` | 難，見下面第 1 點 |
| `ping`、`procs_state_path`、poke、`seq` | 不需要（3.2 第 9 列） |

三個難處（查到的現況）：

1. **「加一列」的內容是一包 JSON**：目標可以是字串、陣列、一整張單子或一整份 loop 設定，另外有 `ws`、`stack`、`def`、`limits`（物件）、環境變數、幾個開關、`as_written`。一行純文字放不下。
2. **一封信可以幾件事一起生效**：`set-def` 靠「加＋睡」同一封；「加＋停」同一封＝上表、不起、夾先不建。一行一道就沒有「一起」。
3. **錯了怎麼說**：今天壞信有三個地方看得到（回信的 `BodyBad` 與原因、`state_flux.mailbox_warning`、daemon 的 stderr），指令那邊還先擋一輪 `PhaseBad`。「寫 ctl 回來＝收到」只說到收到；這題使用者已經列在「還沒談到的」。

另外兩件（推論）：`procs_ctl.json` 那條宣告式的路活樹沒人用，而且會跟信互相蓋（信拿掉的列，下一圈被它疊回來，`cpp/aos-daemon/docs/08:40`），新介面可以不帶。落檔的 `ctl` 永遠寫得進去；如果 `ctl` 是一條具名管道（FIFO），沒人在讀時開檔就失敗（實測 `ENXIO`），有人讀就一寫即到，不用 FUSE 也有「寫得進去＝有人在收」，細節歸 [18](18-ctl、status、settings的候選寫法.md)、[20](20-送訊息兩條路的細節.md)。

### 3.5 從子的 `settings` 讀 persist

**原話**（11-25 第 7 段）：「1. daemon起proc的時候給，沒錯，但daemon是透過proc的一些東西來確定他的persist在哪，或許是起來之後訪問其/proc/<PID>/settings，找到相關路徑？具體的應該會是proc自己挑 ，proc沒登記就死，那自然就是這樣。daemon可以給預設位置OK，並且是在/tmp開闢一塊給他。」

- 今天方向相反：位置是 daemon 定的（那列的 `stack`，沒寫就是 `procs/<名>`），起之前就記在表上，用 `AOS_STACK` 告訴子。「給預設位置」就是設 `AOS_STACK` 的同一招，現成。
- daemon 起了子之後會去讀子的檔，今天只有三處：小格 state 檔裡的 PID（接回用）、ctl 檔時間與 `state_flux`（判卡住）、`stderr.txt` 的尾巴（寫原因）。所以「起來之後去讀它的 `settings`」是新的一步。
- 這一步需要每列多一個「報到了沒」的狀態：沒報到之前表上怎麼顯示、等多久算起不來。今天沒有這種中間狀態（N-17：「沒有 `starting`…子項起來就算 `running`」）；最接近的是「3 秒內就退＝`failed to start`」。
- 讀 `settings` 要找對 PID：表上的 PID 四成是外殼，它站的地方沒有 `settings`（問 1）。

### 3.6 回答「某個 proc 的信箱在哪」

- 今天答案在表上那列的 `stack` 加固定名字 `mailbox`。寄信的人自己開 `procs_state.json` 讀，不寄信問 daemon（`py/aos/apps/mailbox/__init__.py:338-349`）。走 kernel 的才先寄一封 `procs_state_path` 查詢信問「表在哪」，拿到路徑還是自己讀（`py/aos/daemon_ctl/state_path.py:57-95`）。
- 所以今天 daemon 死了、暫停了都問得到；列被 rm 之後問不到（夾其實還在）。
- 推論：新模型裡 `procs/<名>` 掛了就走不進去，daemon 的表要在 proc 活著時記下 persist（已定），停著、睡著的列也要留著那一格。表留成一份 daemon 不在也讀得到的檔（今天的做法）當保底，另外多一條活的路直接問 daemon；兩條並存。

### 3.7 外來行程「只登記、不起」

今天已經有的零件：

- **表上可以有不是自己生的列**：判活改比 `/proc` 的啟動時間；sleep、rm、收工照樣對它送 SIGTERM（E4 接回的四列收工時都收掉了）。
- **起之前看小格的 state 檔**：E3，外來行程擺一份 state，daemon 就接它。
- **「加＋停」**：上表、不起、不建夾。

缺的：

- **入口**。信一定要帶「怎麼起」，沒有「這個 PID 是我，登記一下」的 key。沒有起法的列之後要 `start` 會報 `no recorded launch entry`（`daemon/reconcile.cpp:100-101`）。
- **結束碼、stderr、份額**都要「是我 fork 的」才有。外來的結束了列直接消失，不會留 `stopped`＋原因；沒有 `stderr.txt`；吃不到 rlimit 與換帳號。
- **誰能登記誰**。全部行程同一個 Linux 帳號，誰都能報任何 PID；而 daemon 之後會對表上的 PID 送 SIGTERM（rm、收工）。「登記別人的 PID 再 rm」等於借 daemon 的手殺它（推論，問 4；怎麼核對「來報的就是那個 PID」歸 [08](08-Linux機制實測.md)、[15](15-權限過去的規劃對照新模型.md)）。

推論：daemon 起的與外來的可以走同一條路（proc 自己報到，daemon 去讀它的 `settings` 核對），eca-aos 已經攤過；這也順便解掉「表上的 PID 是外殼」。

### 3.8 有人問就叫醒

**原話**（11-25 第 6 段）：「要不要順手叫醒...這是後續的實作細節，我傾向於這是daemon自身的可選設定」

- 今天沒有。睡著的列只有 `wake` 指令或 daemon 重開會醒；信投進睡著的 agent 的信箱就躺著。daemon 不看子項的信箱（**原話** 11-06：「子daemon管好自己，父daemon只看他有沒有活着，子daemon的其他東西父daemon別碰。盡量解耦合。」）。
- 前提是「問」要經過 daemon；今天不經過（3.6）。叫醒本身現成：把名字從「叫睡的名單」拿掉，下一圈照表起（`daemon/reconcile.cpp:335-361`）。
- 推論：只叫 `sleeping` 的，不叫 `stopped` 的（今天 `stopped` 是有人要它停或它出錯，「只有指令叫起」，`cpp/aos-daemon/docs/03:14`）；`auto_restart` 在等下一次重起的不提早（今天 `wake` 也不提早）。這不牴觸 11-06 那句：daemon 回應的是寄給它自己的問題，沒有去看子的信箱。

### 3.9 daemon 自己死掉

| | 今天（E4 實測） | 新模型（推論） |
|---|---|---|
| 子項 | 都活著，被別的行程收養 | 一樣 |
| 別人怎麼知道 | 表檔還寫著 running；`ping` 等滿才知道；`ls` 最後一行會說 `not running` | daemon 的目錄 `/proc/<PID>/cwd` 立刻不存在，不用問 |
| procs 夾 | 真資料夾都在，信照樣投得進各 proc 的信箱 | 子項都活著，但**從這台 daemon 進來的每一條路都斷了**，它底下每一層每一隻都走不到 |
| 再起 | 同一個 stack 起新的（鎖已經放了），讀表、逐列比對、同 PID 接回 | 新 daemon 是新 PID。子 daemon：上一層把 `procs/<名>` 改指過來，底下的人手上的路不用變。根：沒有上一層 |
| 誰重起它 | 子 daemon＝上一層（`auto_restart`）；根＝沒人 | 一樣 |

- **根重起的問題**：行程的環境變數是起它那一刻給的，之後改不了。今天給的是硬碟路徑，daemon 換了 PID 照樣對。新模型照字面給 `AOS_ROOT=/proc/<根PID>/cwd`，根一重起，所有活著的子項拿的都是死路，今天「接回」這個能力等於沒了（問 2）。
- **表要放哪**：今天 `procs_state.json` 就是存檔。新模型 daemon 的身體跟行程一起沒；表若只在身體裡，daemon 一死就不知道自己有哪些子，接不回，也答不出信箱在哪。推論：表是 daemon 的 persist。
- 可對照的**原話**（11-05）：「我原本想說daemon不可以掛，使用者有義務讓daemon成爲最早開始執行，最晚結束的linux行程，並且他必須正常運行。後來想想，我們一大堆daemon在跑，總會有幾個daemon可能卡住，或是crash，那怎麼辦...你有啥好想法嗎。」當時定的是監管樹：crash＝上一層收到、照表重起，孩子靠自己的 stack 接著跑（`thinking/2026-11/05/no-pid/README.md`「定下的」第 4 條）。

### 3.10 不懂 aos 的行程，橋能替它擺出多少

| 介面 | 橋手上有什麼料 | 今天做到哪 |
|---|---|---|
| `ctl` | 訊號：停＝SIGTERM（逾時 SIGKILL 整群）、暫停＝SIGSTOP 或 cgroup 的凍結、繼續＝SIGCONT | 只有 sleep／rm／收工會送 SIGTERM；stop、pause、resume 寫的是沒人讀的檔（2.8） |
| `status` | daemon 自己知道的：名字、phase、PID、重起幾次、上次的結束碼與訊號、原因；Linux 給的：`/proc/<PID>/status` 的狀態、記憶體、執行緒數，`/proc/<PID>/stat` 的 CPU 時間；開了 cgroup 還有整格的總量 | 料都有，但寫在父的表上那一列（JSON），不在那個 proc 自己的目錄裡 |
| `settings` | 工作區、定義在哪、persist 在哪，都是 daemon 起它時給的 | 表上的 `ws`、`def`、`stack` |
| `_metainfo` | 定義夾裡有就用它的；普通執行檔沒有 | daemon 不碰 |
| stderr、份額 | daemon 接檔、設上限 | 有 |
| 信箱、活的 socket | 它自己不會讀信、也沒有 socket；要有就是 daemon 代收代答 | 沒有 |

這種行程站在執行檔所在的夾（實測 `/usr/bin`）或定義夾，`/proc/<PID>/cwd` 底下不會有 aos 的東西。推論：它的 `procs/<名>` 不能連到 `/proc/<PID>/cwd`，要連到 daemon 替它擺的一個目錄。於是 procs 夾底下會有兩種項：proc 自己答的、daemon 代答的；外面的人要不要分得出來，歸 [12](12-_metainfo、index與proc目錄.md)、[18](18-ctl、status、settings的候選寫法.md)。

可對照的**原話**（10-30，NORMS N-28 引）：「沒有的話也沒關係，linux本身的proc管理就夠，aos體系就是用ps aux+kill去管理」——沒掛 daemon 的歸 Linux 管；掛了的，daemon 就是替它說 aos 話的那一個。

## 4. 邊緣狀況

1. **換了 subuid 的子項走不進 `/proc/<PID>/cwd`**（實測，暫存樹一列寫 `"limits": {"user": "sub:5"}`）：它讀 daemon 的 `/proc/<PID>/cwd` 是 `Permission denied`，同一時間用硬碟路徑 `ls $AOS_DAEMON` 讀得到；反過來，使用者帳號的行程讀得到它的 `/proc/<PID>/cwd`。也就是 daemon 今天已經做好的「把一列換成另一個 uid 跑」，跟新入口相撞；使用者 11-05 對以後的方向說過（原話）：「喔不是，應該說一個agent一個賬號。」權限那邊歸 [15](15-權限過去的規劃對照新模型.md)。
2. **連穿的層數有上限**：實測從根往下第 19 層還讀得到，第 20 層 `ELOOP`。每多一層 daemon 要多跟 2 次連結（`procs/<名>` 一次、`/proc/<PID>/cwd` 一次），照實測反推一條路最多跟 40 次。今天走表的工具最深只走 5 層（`py/aos/comm/walk.py:12`），活樹的 daemon 最深在根底下第 2 層。
3. **同一個定義夾站著好幾隻**：就算不改起法，`/proc/<PID>/cwd` 也分不出誰是誰。
4. **外殼站的夾可能就是 proc 本身的 stack**（14 列）：本身若把 `status` 寫在那裡，`/proc/<外殼PID>/cwd/status` 讀得到，可是那個 PID 不是它。訊號送給外殼會被轉給底下那一群，所以今天殺得掉；但拿這個 PID 去核對身分會對不上。
5. **小格的 state 檔記的 PID 跟表上不同**（同樣那 20 列）：平常表上記的是外殼的 PID；走 2.6「起之前再看一眼」那條接回來時，記的會是 proc 本身的。同一列在兩種情況下記的是不同層的行程。讀程式推的，沒實測。
6. **`stop` 對不讀 ctl 的行程永遠等**（2.8）。今天靠人改下 `sleep`。推論：橋代答的行程，`stop` 就該是 SIGTERM。
7. **daemon 暫停中**：今天照讀兩份 ctl、不收信、不調表。「寫 ctl 回來＝收到」在暫停時是收下排著還是拒收，要定。
8. **重起次數只在記憶體**：daemon 一重起，`counter_restarts` 與退避歸零。要在 `status` 顯示就得接受歸零，或放進 persist。
9. **rm 之後再加同名**：今天舊夾留著，再加同名＝接著用（歷史、信箱都在）。新模型「重起＝新身體接回舊 persist」要靠 daemon 記得那個名字的 persist；列一拿掉就不記得，除非預設位置能用名字算出來（eca-aos 已攤：用名字算、不用 PID 算）。
10. **起根的人手上的 PID 是外殼的**：活樹是 2222（`aos-exec`），daemon 是 2223。「給根 daemon 的 PID」得由根自己公布，不能拿殼裡的 `$!`。
11. **入口若放在大家都能寫的地方**（例如 `/tmp` 底下一條固定名字的連結）：單一帳號沒事；分帳號之後，別人可以放一條同名連結把整棵樹的入口指到別處（推論）。
12. **「別人不碰 pid」**（N-17）與「pid 搬不走」（C-83）：新入口讓每個人手上都有一條帶 PID 的路，只當字串用、不送訊號。算不算碰，歸 [16](16-過去定案與新模型的衝突檢查.md)。
13. **proc 站定之後又 cd 走**：`/proc/<PID>/cwd` 跟著它現在站的地方走，daemon 核對過一次之後不會再核對。aos-loop 自己不會換夾（`cpp/aos-loop/src` 裡查不到 chdir），但外來行程或外殼腳本會。介面要寫明「站定就不換」，或 daemon 定期再對一次（推論）。

## 5. 要問使用者的

**問 1｜`procs/<名>` 該連到誰？**（表上的 PID 四成是外殼，2.5）
- a. proc 站好之後自己向 daemon 報到，帶自己的 PID；daemon 讀它的 `settings` 核對過才建連結。daemon 起的與外來的走同一條路。
- b. 改起法：daemon 直接生的那一支要一路變成 proc 本身，中間不准留外殼；daemon 拿 fork 得到的 PID 直接連。
- c. 兩個都做：b 當加速，a 當定義。
- 推薦 **a**。理由：外殼來自「入口寫成單子」「帶環境變數掛上去」「包沙箱」這些現有用法，b 要全部改掉；a 順便解掉「還沒站好就被讀到 daemon 的夾」，也就是「只登記、不起」的入口。

**問 2｜根重起之後，活著的子項手上的 `AOS_ROOT` 怎麼辦？**（3.9）
- a. `AOS_ROOT` 給一條固定名字的連結，根每次起來把它指到自己的 `/proc/<PID>/cwd`；大家手上的字不變。
- b. 照字面給 `/proc/<PID>/cwd`；根死了就整棵樹重起，不接回。
- c. 子項發現根不見了，自己去一個固定位置問新的根在哪。
- 推薦 **a**。理由：多一條連結就保住今天已經在用的「接回」，Linux 的 `/proc` 一樣不用加東西。b 合你 11-05 說的「壞了就壞了」，但比現況退一步。

**問 3｜停著、睡著的列（沒有 PID）在 procs 夾裡長怎樣？**（3.3）
- a. 不出現。procs 夾只有活的；停著的看 daemon 的 `status` 或它留下的表。
- b. 留著名字，改連到它的 persist，掛了也走得到信箱。
- c. 留一條走不進去的連結，看得到名字。
- 推薦 **a**。理由：跟「死了馬上讀不到＝不用問就知道」同一個規則；b 會讓同一條路活著時是身體、死了變成 persist，兩種東西長得不一樣。

**問 4｜外來行程登記之後，daemon 對它有多少權力？**（3.7）
- a. 只記名字、建連結；daemon 不對它送任何訊號，要停只寫它的 ctl。
- b. 跟自己起的一樣：rm、收工都送 SIGTERM（今天接回的列就是這樣）。
- c. 登記時它自己說。
- 推薦 **a**。理由：不是 daemon 起的就不該由 daemon 殺，也擋掉「登記別人的 PID 再 rm」。

**問 5｜「加一列」怎麼用純文字的 ctl 下？**（3.4）
- a. ctl 那一行只帶名字與一個檔的路徑，內容照舊是一份 JSON 檔；另外給一個「先上表、不起」的寫法，`set-def` 就夠用。
- b. 把內容攤成一行的「鍵=值」。
- c. 加一列不走 ctl，照舊寄信；ctl 只收 rm／stop／start／sleep／wake。
- 推薦 **a**。理由：那包內容本來就是巢狀的（一整張單子、份額物件），攤平會漏；跟你 11-25 說的「改成部分用json」一致。

## 6. 沒查到／沒把握的

- aos-loop 的窗怎麼讀寫沒細讀（daemon 繼承它），歸 [01](01-aos-loop現況.md)。kernel 站轉信那條路只讀了寄信這一側。
- cgroup 與換真帳號沒實測（這台 10 台都沒開 cgroup；換真帳號要 root）。3.10 說的「cgroup 的凍結」：這台的 cgroup 樹裡看得到 `cgroup.freeze` 這個檔，沒試。SIGSTOP／SIGCONT 當暫停／繼續也沒試。
- PID 被重用時連結指到別人：只講道理，沒做出重用。
- 「改名蓋過連結是一步完成」「外來行程可以事後補上限、搬進 cgroup」：憑記憶，沒查。
- 邊緣 5 沒實測。
- 活樹的數字是 11-25 12:16 那一刻的；樹在變。
- NORMS 的 N-28／N-54 分檔只讀了三份與 N-17 兩份，其餘以 `cpp/aos-daemon/docs/` 為準，兩邊沒逐條對。

## 附：實驗怎麼重跑

五支腳本與輸出留在 `~/.aos/scratch/aos-proc-arch-1125/02/`（`exp_daemon.py`＝E1～E4、`exp_ls.py`＝daemon 死著時的 `ls`、`exp_link.py`＝3.3、`exp_depth.py`＝層數與 FIFO、`exp_sub.py`＝subuid；各有同名 `.out`）。都用 `env -i` 清掉所有 `AOS_*` 才跑，只碰自己的暫存夾；跑完核對過沒有留下行程。暫存夾被清掉的話，E1～E4 的最小做法：

<details><summary>暫存樹（E1、E2、E4）</summary>

```sh
B=$(mktemp -d); mkdir -p $B/def $B/defs/arr $B/defs/obj
echo '["aos-daemon","daemon.json"]'  > $B/def/_entry
echo '["sleep","600"]'               > $B/defs/arr/_entry
echo '{"argv":["sleep","600"]}'      > $B/defs/obj/_entry
cat > $B/def/daemon.json <<EOF
{"interval_ms": 100, "procs": {
  "loopinline": {"exec": {"argv": ["sleep", "0.2"]}, "interval_ms": 1000},
  "arr": {"exec": "$B/defs/arr"}, "obj": {"exec": "$B/defs/obj"},
  "inl": {"exec": {"argv": ["sleep", "600"]}},
  "plain": ["/usr/bin/sleep", "600"], "ok0": ["/usr/bin/true"],
  "bad": ["/usr/bin/sh", "-c", "echo boom >&2; exit 3"]}}
EOF
run() { env -i HOME="$HOME" PATH=/home/guanyu/repo/aos/proto8/bin:/usr/bin:/bin "$@"; }   # 清掉所有 AOS_*
run setsid aos-exec --stack $B/stack $B/def &
# E1：$B/stack/procs_state.json 每列的 pid，各看 /proc/<pid>/comm、readlink /proc/<pid>/cwd、/proc/<pid>/task/*/children
# E2：run aos-daemon-ctl -d $B/stack pause --timeout-s 1 plain；再依序 stop、sleep、start，每步讀表
# E4：kill -9 <$B/stack/state.json 的 pid>；看子項與 /proc/<那個 pid>/cwd；再跑一次上面 aos-exec 那行；讀表
# 收：run aos-daemon-ctl -d $B/stack shutdown
```

這一段照抄跑過一次（`recipe.sh`），`ls` 印出五列 running、一列 `bad` stopped，各 PID 的程式名與 cwd 跟 2.5 的表一樣。

</details>

<details><summary>連結什麼時候建、什麼時候拿（3.3 的 a、b）</summary>

```python
import os, signal, tempfile, time
base = tempfile.mkdtemp(); dd, kd = base + "/daemon", base + "/bodies/kid"
os.makedirs(dd + "/procs"); os.makedirs(kd)
open(dd + "/status", "w").write("name: daemon\n"); open(kd + "/status", "w").write("name: kid\n")
os.chdir(dd); link = dd + "/procs/kid"
r, w = os.pipe(); kid = os.fork()
if kid == 0:
    time.sleep(0.3); os.chdir(kd); os.write(w, b"1"); signal.pause()
os.symlink("/proc/%d/cwd" % kid, link)
print(open(link + "/status").read())            # name: daemon
os.read(r, 1); print(open(link + "/status").read())   # name: kid
os.kill(kid, signal.SIGKILL); time.sleep(0.2)
print(os.path.exists(link + "/status"), os.path.lexists(link))                   # False True
print(os.waitid(os.P_PID, kid, os.WEXITED | os.WNOHANG | os.WNOWAIT).si_status)  # 9，還沒收屍
os.unlink(link); print(os.waitpid(kid, 0))                                       # 先拿連結，再收屍
```

</details>
