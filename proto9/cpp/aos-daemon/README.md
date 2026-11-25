aos-daemon：proto9 第二塊正式程式——一台最小的 aos daemon（C++20，建在 aos-procfs 上）：自己是一隻 aos proc，另外擺出 `procs/`、`procs_ctl`、`procs_status` 管底下的 proc；被底下卡住的 proc 拖不住。

# aos-daemon（proto9，11-25）

← [proto9](../../README.md)｜介面：[01-aos-proc介面草稿](../../docs/01-aos-proc介面草稿.md)｜用的庫：[aos-procfs](../aos-procfs/README.md)

## 夾裡有什麼

| 檔 | 是什麼 |
|---|---|
| `src/main.cpp` | 參數、起來時清死掛載、擺出目錄（每個檔的 Producer、`ctl`、`procs_ctl` 的 Check／Action）、印 `export AOS_ROOT=…` |
| `src/daemon.hpp` | 設定、表（`Proc`）、請求、監工的宣告 |
| `src/supervisor.cpp` | 監工的事件迴圈：收屍、收小行程的結果、登記期限、查卡住 |
| `src/lifecycle.cpp` | 表上一隻的狀態變化：登記成功、結束、`procs/<名>` 連結的加與拿掉 |
| `src/commands.cpp` | `procs_ctl` 的六個字與 daemon 自己 `stop` 時收掉底下的 |
| `src/sys.cpp` | 拋棄式小行程（碰底下 proc 的檔只在這裡）、起底下的 proc（含填 `AOS_NAME_PID`）、讀 mountinfo |
| `src/json.cpp` | `add` 用的 json 的最小解析器 |
| `tests/run.py`、`tests/stuck.py`、`tests/common.py` | 測試（卡住的幾組在 `stuck.py`） |

## 怎麼編、怎麼跑

```
make -C ../aos-procfs     # 先編庫與 demo（這個 Makefile 只編這一夾）
make                      # build/bin/aos-daemon；-Wall -Wextra 沒有警告
make test                 # = python3 tests/run.py；只跑某幾組：python3 tests/run.py stuck nested
```

參數：`aos-daemon [NAME [MOUNTPOINT]] [--mount-base DIR] [--register-timeout S] [--check-interval S] [--check-timeout S] [--stop-timeout S] [--ctl-timeout S]`。NAME、MOUNTPOINT 不給就用 `$AOS_NAME`、`$AOS_MOUNT`（上面的 daemon 起它時給的），但只在 `$AOS_NAME_PID` 等於自己的 PID 時（庫的 `env_assignment()`；見下面「交給底下的環境變數」）。預設期限：登記 10 秒、每 5 秒查一次卡住、讀 `status` 1 秒沒回算卡住、`stop` 後等 10 秒才強制收、寫底下的 `ctl`（與讀 `add` 的檔）1 秒。`--help` 有全文。

手動玩（這台實跑的輸出，路徑縮短）：

```
$ D=~/.aos/scratch/proto9-daemon-1125
$ build/bin/aos-daemon root $D/mnt/root --mount-base $D/base &
export AOS_ROOT=/proc/576242/cwd
$ export AOS_ROOT=/proc/576242/cwd          # 根只提示，人自己 export
$ echo "add kid $PWD/../aos-procfs/build/bin/aos-procfs-demo" > $AOS_ROOT/procs_ctl
$ ls -l $AOS_ROOT/procs/
kid -> /proc/576253/cwd
$ cat $AOS_ROOT/procs/kid/status
aos_name: kid
aos_phase: running
aos_pid: 576253
...
$ cat $AOS_ROOT/procs_status
kid.phase: running
kid.want: up
kid.pid: 576253
kid.code: -
kid.signal: -
kid.reason: -
kid.persist: -
kid.mailbox: -
kid.stuck: no
$ echo 'stop kid' > $AOS_ROOT/procs_ctl
$ cat $AOS_ROOT/procs_status
kid.phase: stopped
kid.want: down
kid.pid: -
kid.code: 0
kid.signal: -
kid.reason: stopped
...
$ echo stop > $AOS_ROOT/ctl                 # 收掉底下的、卸掉自己、結束
```

`status` 是第一批八行加 `aos_procs` 與 `aos_procs_ctl_cmd／state／error／count`。`procs_ctl` 的一道收下了、daemon 這邊做的時候失敗（例：`add` 的檔讀不到、對卡住的 `stop` 逾時），`aos_procs_ctl_state` 記 `failed`、原因在 `aos_procs_ctl_error`；`done` 一定是做成了（error 是 `-`）。

底下的 proc 若擺了信箱夾（例 demo），從 daemon 這邊走得到：`printf 'hi' > $AOS_ROOT/procs/kid/mailbox/tmp/m && mv $AOS_ROOT/procs/kid/mailbox/tmp/m $AOS_ROOT/procs/kid/mailbox/new/m`。`procs_status` 的 `kid.mailbox` 照舊是那隻 `settings` 的 `aos_mailbox`（掛了的時候信投到哪），不是這個活著的 `mailbox/`。

## 交給底下的環境變數

起一隻底下的 proc 時給四個：`AOS_NAME`（名字路）、`AOS_MOUNT`（掛載點）、`AOS_NAME_PID`（那一支自己的 PID）、`AOS_ROOT`。`AOS_NAME_PID` 照 systemd 的 `LISTEN_PID`：fork 之後、exec 之前由孩子自己填（只用 `getpid()` 與手寫的數字轉換，fork 後只做 async-signal-safe 的事）。孫子行程原樣繼承到這幾個時，`AOS_NAME_PID` 對不上自己的 PID，庫的 `env_assignment()` 就當沒給，它不會冒用孩子的名字與掛載點。`AOS_ROOT` 不在此限。

**後果**：`add` 給的若是一支包裝的殼（或 json 的 `exec` 是 `sh -c ...`），殼要 `exec` 真的程式；沒 exec，真的程式是孫子、不理這兩個變數，那隻就登記不起來（demo 退 1，表上記 `failed`）。測試 `envpid` 三種都驗了。

順手修的：json 的 `env` 若也寫了 `AOS_NAME` 這些鍵，原本兩份都進環境、`getenv` 拿到的是 json 的；現在同一個鍵後面的贏，daemon 自己給的一定蓋過 json 的（照原本 README 寫的意思）。`add` 的路徑是一支可執行檔，或一份 json：`{"exec": ["/path/prog", "arg"], "env": {"K": "V"}}`。嵌套：`add d1 d1.json`，json 的 `exec` 是另一台 `aos-daemon`（不給 NAME、MOUNTPOINT），之後 `$AOS_ROOT/procs/d1/procs/kid/status` 讀得到。

## 怎麼保證不被底下卡住的 proc 拖住

草稿第 8 節的規矩「回答只用自己記憶裡的東西」，在這裡落成三層：

1. **回答的線**（庫的那條）：`status`、`procs_status`、`settings` 的 Producer 只在 `State::mu` 底下抄表、組字串；`procs_ctl` 的 Check 只看參數與表。`State::mu` 從不拿著做會等的事：拿著它時只做記憶體更新、`fork()`、讀 `/proc/self/mountinfo`、寫 `/sys/fs/fuse/connections/<編號>/abort`、`kill()`；要跑 `fusermount3` 的清死掛載排到放開鎖之後做。
2. **監工**（主線，唯一碰底下 proc 的線）：一個 `poll` 迴圈（signalfd 收 SIGCHLD 與停止訊號、eventfd 收請求、小行程的管子、外來 proc 的 pidfd），自己從不阻塞。**碰底下 proc 目錄的動作**——讀 `settings`（登記）、讀 `status`（查卡住）、寫 `ctl`（`stop`）、連讀 `add` 給的那份檔（路徑可能指進某隻卡住的 proc）——**全部交給 fork 出來的拋棄式小行程**：它只做一次 `open`＋`read`／`write`，結果從管子帶回；到期就 SIGKILL、放棄。小行程先 `chdir("/")`、關掉管子以外所有 fd，卡住了也攥不住 daemon 自己的 `/dev/fuse` 與掛載點。被放棄、還沒收到屍的小行程記在那隻的 `hung`：在它收屍之前**不再碰那隻**（草稿「同一個對象上一次還沒回來，就不再問第二次」），`stop` 直接回 `ProcStuck … use kill`。
3. **做事的線**（`procs_ctl` 的 Action）：把指令交給監工、等它回話，有上限（`ctl-timeout`＋`check-timeout`＋5 秒，正常走不到）。監工不阻塞，所以 `procs_ctl` 最久鎖住的情形是「對一隻卡住的 proc 下 `stop`」或「`add` 的路徑在卡住的 proc 裡」，都是 `ctl-timeout`（預設 1 秒）就放棄、回錯；鎖一放 `kill` 就下得進去。`kill` 本身不碰那隻的目錄：從 mountinfo 照 fsname 的 PID 找到它的連線、寫 abort（放開被它拖住的人）、SIGKILL，死掛載等收屍時 `fusermount3 -u -z`（lazy，不跟它講話）。

daemon 自己的路徑一律用絕對路徑，監工不碰自己的掛載點。

實測（`tests/stuck.py` 與另跑的量測）：底下一隻被 SIGSTOP 時，殼裡 `cat status`、`cat procs_status`、`echo 'stop b' > procs_ctl`、`echo 'add c …' > procs_ctl` 各 3～25 毫秒（含起 bash）；Python 連讀 2 秒，`status`／`procs_status` 中位數 72～83 微秒、p99 2～5 毫秒、最大 11～40 毫秒，**有沒有卡住的都一樣**（尾巴是拿著鎖 fork 小行程與 WSL 排程，不是卡住造成的）。daemon 約 4.6 MB。

## 照了哪些【擬】

- 草稿第 3 節：daemon 起底下的時把 `AOS_ROOT` 放進它的環境。
- 派工時定的【擬】：名字路、掛載點、根走環境變數 **`AOS_NAME`、`AOS_MOUNT`、`AOS_ROOT`**（daemon 的值蓋過 json 的 `env`）。aos-procfs-demo 也改成沒給參數時讀前兩個。
- 派工時定的【擬】：`procs_ctl` 的「做完」＝daemon 這邊的動作做完（`stop`＝字送進那隻的 `ctl` 了；`add`／`start`＝行程起了；`kill`＝abort＋SIGKILL 送出了；`rm`＝`stop` 送出了），結果看 `procs_status`。
- 第 8 節「卡住」的查法（另開、帶期限、不直接讀；讀回來就改回、連結恢復）與 `名字.stuck` 一欄。
- 第 8 節：`kill` 先斷開連線再收行程。
- 第 7 節 `settings` 兩行 `aos_persist`、`aos_mailbox`（daemon 自己都是 `-`，另多一行 `mount_base`）。
- 第 8 節「死掉的掛載」：根自己死掉留下的，下次起來時清。
- 第 6 節的鎖、回饋、基礎三字照庫（daemon 的 `ctl`：`stop`、`pause`、`resume`）；回饋的 `failed`（【定】，使用者 11-25）也照庫。

## 碰到的【開】與怎麼處理（都挑保守的，使用者看了不對就改）

| 碰到的 | 怎麼做 |
|---|---|
| 多久查一次卡住、期限多長（第 12 節第 1 條） | 照派工的預設 5 秒／1 秒，參數可改 |
| `phase` 的值 | `starting`（起了、還沒登記）／`running`／`stopping`（`stop` 送到了）／`stopped`（結束了，不管怎麼結束；原因看 `code`、`signal`、`reason`）／`failed`（起動失敗：登記期限到、或登記前就死） |
| 外來登記的「多一欄」 | 只有它們多一行 `名字.external: yes` |
| `register`（第 12 節第 7 條）誰可以登記誰、daemon 有多少權力 | 寫得進 `procs_ctl` 的都能登記任何 PID；daemon 只用 pidfd 看它死了沒、讀它的 `settings`／`status`；不送訊號、不寫它的 `ctl`、不卸它的掛載：`stop`、`start`、`kill` 都拒（`ProcExternal`），只收 `rm`；daemon 自己 `stop` 時不管它。登記期限內讀不到 `settings` 就記 `failed`，不碰它 |
| `aos_procs` 數什麼 | 表上幾隻（含死的、停著的） |
| 根的 `aos_name` | 照第 7 節【定】是 `/`；所以根的 NAME 參數現在沒用到。不是根、又沒有 `AOS_NAME` 時才用 NAME |
| 掛載點放哪（第 12 節第 2 條） | `<mount-base>/<名字路把 / 換成 %>`，例 `d1%kid`；名字只准英數 `_ - .`，撞不到。起來時清的「自己前一次的」＝根清 mount-base 底下全部的死掛載，`d1` 只清 `d1%` 開頭的；活著的一律不動 |
| `stop` 一隻還在 `starting` 的 | 拒（`ProcStarting`，它還沒有 `ctl`），要收用 `kill` |
| `rm` 一隻活著的 | 先寫 `stop`，`stop-timeout` 到了還在就強制收；收屍後從表上拿掉（persist 不碰）。卡住的、還沒登記的直接強制收 |
| 讀 `status` 回錯（不是逾時，例：連線被斷開） | 也算卡住（走不進去就是走不進去） |
| daemon 自己 `pause` | `aos_phase: paused`，`procs_ctl` 的 `add`、`start`、`register` 拒（`DaemonPaused`）；`stop`、`kill`、`rm` 照收，收屍與查卡住照做 |
| daemon 的 FUSE 連線被斷開（例：上面的 daemon `kill` 了它） | 照 `stop` 收底下的（SIGTERM／SIGINT／SIGHUP 也是） |
| `add` 的路徑 | 要絕對路徑（daemon 站在自己的掛載點裡，相對路徑會指進自己）；檔讀不到、或既不是可執行也不是 json：那道記 `failed`＋`PathBad`，表上不留。寫入本身成功——檔要在小行程裡讀，回答的線上看不到 |
| `AOS_NAME_PID` 對不上（不是 daemon 起的那一支） | 當沒給環境變數：要靠參數給 NAME、MOUNTPOINT，不然退 1 |
| json 的 `exec[0]` | 帶 `/` 的相對路徑照 json 所在的夾算；不帶 `/` 照 `PATH` 找 |
| 底下的 stdio | stdin 接 `/dev/null`，stdout 併進 daemon 的 stderr（daemon 的 stdout 只留那行 `export`）；各自一個行程組（殼對 daemon 按 Ctrl-C 不會一起打到底下，由 daemon 好好收） |
| 被拒、寫入失敗的錯誤號 | 照庫：參數不對 `EINVAL`、鎖著 `EBUSY` |
| `stuck` 的時間格式 | 同 `aos_started_at`，本地時間帶時差 |
| proto8 的 `sleep`／`wake`（第 12 節第 3 條） | 沒做 |

## 測試（`tests/run.py`）

64 條全過（self 7、add 10、crash 3、stuck 8、regfail 5、register 5、lock 3、nested 6、startup 3、stopstuck 5、sigterm 1、envpid 4、mailbox 3，加最後一條「沒有殘留」）。驗的有：status 十三行、根的 `aos_name: /`、`pause` 時 `add` 被拒；不認得的字、相對路徑、不認得的名字、壞名字都被拒；`add` 後 `procs/kid/status`、`proc/kid` 讀得到、掛在 mount-base 底下；json 帶 `--persist` 進表；`stop`／`start`／`rm`；kill -9 底下的 → `signal: 9`、reason 有 SIGKILL、連結沒了、死掛載與夾都清了；SIGSTOP → 1 秒多 `stuck` 有時間、連結沒了，這期間 daemon 的 `status`、`procs_status`、`procs_ctl` 都在幾毫秒內答、而且生效；SIGCONT → 恢復；`kill` 卡住的 → 被它拖住的 `cat` 被放開、行程沒了、掛載清了；`/bin/sleep 60` 3 秒期限到記 `RegisterTimeout` 並收掉；`/bin/false` 記「登記前就死」；不存在的路徑記 `failed`＋`PathBad`；`register` 外面起的 demo → 走得進去、`kill` 被拒、`rm` 後它與它的掛載都還在、daemon `stop` 也不碰它；`add` 的路徑指進卡住的 proc → `procs_ctl` 鎖著時別人寫是 busy、1 秒後放棄（`failed`）；兩層嵌套 `procs/d1/procs/kid/status`（`aos_name: d1/kid`）；daemon `stop` 後兩層的行程與掛載都沒了；起來時清掉 mount-base 底下的死掛載；根被 kill -9 後在同一個掛載點重起得來；對卡住的 `stop` 1.1 秒放棄（`failed`＋`CtlTimeout`）之後 `kill` 下得進去；帶著卡住的 daemon `stop` 3 秒後強制收、結束；SIGTERM＝`stop`；孩子的 `AOS_NAME_PID` 是它自己的 PID、殼 exec 的登記得起來、殼沒 exec 的（demo 成了孫子）不冒用名字與掛載點；寄信進 `$AOS_ROOT/procs/kid/mailbox/` 寄得到、`kid.mailbox` 照舊。

收尾：起的每支行程（連孫子）都帶環境變數 `AOS_DAEMON_TEST_RUN=<測試的 PID>`，`tests/common.py` 用 atexit＋SIGTERM 掃 `/proc/*/environ` 找出來 SIGCONT＋SIGKILL，再 `fusermount3 -u -z` 卸掉 scratch 底下的掛載、刪空夾。中途 SIGTERM 測試行程也收得乾淨（實測過）。測試用的掛載與暫存都在 `~/.aos/scratch/proto9-daemon-1125/`。

`lock` 那組在整支跑時偶爾一次沒過（11-25 最後一輪前看到一次：慢的那道 `add` 在 0.3 秒內就做完了，第二個人寫進去而不是 busy），單跑三次都過；原因沒查到，應該是機器忙時的時間差，不是這次改的東西。

## 行數

`src/` 1387 行；每個檔都在 300 行以內（`supervisor.cpp` 原本 303 行，登記、結束、連結那幾個函數搬到 `lifecycle.cpp`；最長 `main.cpp` 280）。測試 592 行（`run.py` 258、`common.py` 230、`stuck.py` 104）。

## 還沒做的

- 自動重起（`want: up` 卻 `stopped` 的不會自己起來）；proto8 的 `sleep`／`wake`；只斷開不收的字（第 8 節【開】）。
- daemon 不替底下的 proc 開預設的 persist（第 7 節「可以在 `/tmp` 開一塊」）；`persist`、`mailbox` 只照它自己的 `settings` 記。
- 底下的 stderr 沒有收進 `reason`（proto8 的 daemon 有）。
- 各檔的 json 版、`sock`；daemon 自己不擺信箱夾（底下的 proc 自己擺，例 demo）。
- `kill` 一台嵌套的 daemon：它被 SIGKILL，它底下的變成沒人管的（使用者定的「自行承擔風險」）；daemon 自己被 kill -9 也一樣。要好好收請用 `stop`。
- 兩台互不相干的根共用同一個 mount-base 時，同名的底下 proc 會搶同一個掛載點（後起的那隻掛不上、記成失敗）。
- `register` 不驗身分：誰都能把任何 PID 登記進來（它不擺 `settings` 就只是記成 `failed`）。
- `State::mu` 拿著時會 fork（小行程、起底下的 proc），讀表的尾巴延遲因此到幾十毫秒；要再壓可以把 fork 移到鎖外。監工固定 100 毫秒醒一次看期限。
- 沒進 code map、`_index.json`、proto9/README（只准寫這一夾）。
