家機量 proto9 aos-daemon 底下的 proc 除了檔案路徑還有哪些路碰得到外面與兄弟：照預設設定，SysV IPC 與 POSIX mqueue 三個方向全通（沒開 IPC namespace），另有經 /proc/1/net 看外面整台的 socket 表、照 PID 改兄弟與 daemon 的排程與上限、讀別人 nice 當暗道這幾條還開著；訊號、ptrace 一族、網路、危險系統呼叫都擋住了。

# 除了檔案還有哪些路（11-27，家機，小實驗）

← [proto9](../../README.md)｜量的對象：[aos-daemon](../../cpp/aos-daemon/README.md)｜背景：[daemon職責-1126](../../../proto8/thinking/2026-11/26/daemon職責-1126.md) 第 26（`net`）、27（seccomp）、29（准開 user namespace）、38（預設 subuid，還沒做）、46（看得到什麼是路由、行程之間是牆）條｜寫法照 [sky-1125](../sky-1125/README.md)

**為什麼量**：使用者 11-27 的說法是「daemon 擋下系統呼叫與網路，proc 只能用 Unix 路徑（aoslua）拿東西，kernel 遮得住檔案就管得住一切」——等於硬逼出一個 Plan 9 虛擬機。這要成立，前提是「除了檔案沒有別的路」。這裡把別的路一條一條試過，看現在封得多完整。**沒改 aos-daemon 的任何檔**；要改才能封的寫成建議。

## 怎麼跑

```
cd proto9/experiments/channels-1127
python3 run.py              # 約 4 秒；印一張表（每條一列、每種設定一欄）、cleanup 一行、SUMMARY 一行；全過退出碼 0
python3 run.py -v           # 每格的細節（讀到的內容、號碼）也印
python3 run.py --json out.json --tmp DIR --only default net_host
```

- 要有：gcc、`proto9/cpp/aos-daemon/build/bin/aos-daemon`（不在就自己 `make`）、`ipcs`／`ipcrm`、systemd --user（daemon 預設要）、`/etc/subuid` 有範圍（subuid 那兩欄要）。只有 x86_64。
- `run.py` 在 `--tmp`（預設系統暫存夾）底下開一個 `channels-1127-XXXX`，把 `probe.c`、`fakeabi.c` 編在裡面，跑完整個刪掉。開始前先清掉前一次被打斷時用同樣 key／名字留下的 IPC 物件（只動自己的）。
- 結束時比對跑前跑後：行程（exe 是這份 aos-daemon 或這次編的 probe）、掛載、`systemctl --user` 的 `aos-daemon-*`、cgroup 夾、`/tmp`、SysV IPC（`ipcs`）、`/dev/mqueue`、`/dev/shm`，有新的就印 `LEFT OVER` 並以 1 結束。
- 程式的輸出全是英文；表裡的格子是 `open`（做得到）或做不到時的錯誤碼。

## 怎麼量

每種設定起一次 daemon（`daemon.json` 只寫 `init`，其餘全預設：cgroup auto、subuid auto），init 是一隻只會睡的 probe（預設設定）。外面由 `run.py` 用 `ctl start` 起三隻：

| 誰 | 做什麼 |
|---|---|
| 外面的 hold（對照） | 天空外面、跟使用者同帳號的普通行程：建 0666 的 SysV shm／msg／sem（各放一個 `marker-out`）、POSIX mqueue `/channels1127-out`、abstract socket `@channels1127-out`、聽 `127.0.0.1` 的一個 TCP 埠、`/dev/shm/channels1127-out`；記下自己的 keyring 號碼與 hostname；收到 SIGTERM 全部清掉 |
| B（兄弟，hold） | 同樣的東西在天空裡建一份（`marker-B`、`@channels1127-B`、自己 lo 上的 TCP 埠），把自己的 nice 設成 7，記下 marker 在記憶體裡的位址 |
| A（探測） | 拿到 B、init 在天空裡的 PID 與上面那些名字，一條一條試，結果寫成 JSON 行 |
| C（探測，沒有 `/proc`） | 跟 A 一樣，但天空沒放 `proc` |
| 外面的 find | B 還在時，外面找 B 建的東西（裡面 → 外面看得到嗎） |

天空：`/usr`、`/etc` 唯讀、`/bin` 等 symlink、`dev`、`proc`（C 沒有）、`/tmp` tmpfs、`/w`（probe 所在的夾，唯讀）、`/out`（各自的結果夾，可寫）。B 與 A 的設定一樣，所以「B→A」跟「A→B」是同一回事，只量一邊。

五種設定（A、B、C 三隻一起換；init 一律預設）：

| 欄 | 設定 |
|---|---|
| 預設 | 什麼都不寫：uid 0（外面的使用者本人）、`net none`、內建 seccomp、Landlock（家機 ABI 7：含擋訊號與 abstract socket） |
| net host | `"net": "host"` |
| seccomp off | `"locks": {"seccomp": "off"}` |
| subuid（加做） | A、B、C 各寫 `"uid": 1`、`2`、`3`——第 38 條定了要改成預設、還沒做，先量它會封掉哪些 |
| ABI 3 模擬（加做） | 用 `LD_PRELOAD` 掛 `fakeabi.c`，daemon 問 Landlock 版本時拿到 3，就不加擋訊號與 abstract socket（像公司 WSL 6.6）；`status` 的 `landlock_abi` 確實是 3。另跑了「ABI 3＋net host」「ABI 3＋subuid」兩欄。只騙到 daemon，核心還是 6.18 |

## 結果

家機 Manjaro，Linux 6.18.55，Landlock ABI 7，gcc 16.2，Python 3.14。`run.py` 連跑兩次，整張表（7 欄 × 191 列）一字不差，兩次都 `cleanup: ok`、退出碼 0。

「通」＝做得到（括號是讀到的東西或細節）；「不通」後面是錯誤碼。C（沒有 `/proc`）除了讀 `/proc` 的那幾列，其他每一列每一欄都跟 A 一樣，所以表裡只寫 A，C 的差別寫在「看別人」那幾列。

### SysV IPC、POSIX mqueue

| 路 | 方向 | 預設 | net host | seccomp off | subuid（加做） | ABI 3 模擬（加做） | 怎麼封、成本 |
|---|---|---|---|---|---|---|---|
| SysV 共享記憶體 `shmget`／`shmat` | A→外面建的 | **通**（讀到 `marker-out`） | 通 | 通 | 通 | 通 | 每隻 proc 開自己的 IPC namespace（起 proc 時 `unshare` 多帶 `CLONE_NEWIPC`）；一個旗標，代價是兄弟之間也不能用 SysV 共用 |
| 同上 | A→兄弟建的 | **通**（讀到 `marker-B`） | 通 | 通 | 通 | 通 | 同上 |
| 同上 | 外面→裡面（B）建的 | **通** | 通 | 通 | 通 | 通 | 同上 |
| SysV 訊息佇列 `msgget`／`msgrcv`、號誌 `semget`／`semctl` | 上面三個方向 | **全通**（收到 `marker-out`／`marker-B`、號誌值 1101／1102） | 全通 | 全通 | 全通 | 全通 | 同上 |
| POSIX mqueue `mq_open` | 上面三個方向 | **全通**（收到 marker；不用掛 `/dev/mqueue`，mqueue 屬 IPC namespace、不經路徑） | 全通 | 全通 | 全通 | 全通 | 同上（同一個旗標一起封） |
| 列出整台的 shm（`shmctl` `SHM_STAT_ANY`、`/proc/sysvipc/shm`） | A→外面 | **通**（列出 4 段；uid 0 時對其中 2 段使用者桌面程式的 0600 私有段 `IPC_STAT` 也准，等於能 `shmat` 讀寫，沒試） | 通 | 通 | 通（但只准 0666 的那 2 段） | 通 | 同上 |
| `/dev/shm`（`shm_open` 那種） | A→外面 | 不通 `ENOENT`（天空的 `dev` 沒放；它本來就是檔案路徑） | 同 | 同 | 同 | 同 | 已封（走檔案那條） |

### socket 與網路

| 路 | 方向 | 預設 | net host | seccomp off | subuid | ABI 3 模擬 | 怎麼封、成本 |
|---|---|---|---|---|---|---|---|
| abstract unix socket | A→外面 | 不通 `ECONNREFUSED`（自己一個 network namespace；abstract 名字是跟著 network namespace 分的） | 不通 `EPERM`（Landlock ABI 6 以上的 scope） | 不通 `ECONNREFUSED` | 不通 `ECONNREFUSED` | 預設不通；**＋net host 通** | `net none` 已封；net host 在舊 Linux 上沒得封（等 6.12） |
| 同上 | A→兄弟 | 不通 `ECONNREFUSED` | 不通 `EPERM` | 不通 | 不通 | 預設不通；**＋net host 通** | 同上 |
| 同上 | 外面→裡面（B） | 不通 `ECONNREFUSED` | **通**（外面不在 Landlock 裡，scope 只擋裡面往外連） | 不通 | 不通 | ＋net host 通 | 外面是使用者本人，設計上本來碰得到 |
| TCP 連 `127.0.0.1` 上聽著的埠 | A→外面 | 不通 `ECONNREFUSED`（自己的 lo 上沒人聽） | **通** | 不通 | 不通 | ＋net host 通 | `net none` 已封；net host 時要不要擋本機埠是另一題（Landlock ABI 4 有 TCP connect 規則，daemon 沒用） |
| 同上 | A→兄弟 | 不通 `ECONNREFUSED` | **通**（同一個 network namespace，Landlock 沒管 TCP） | 不通 | 不通 | ＋net host 通 | 同上 |
| 同上 | 外面→裡面（B） | 不通 `ECONNREFUSED` | 通 | 不通 | 不通 | ＋net host 通 | 同上 |
| 連外網（`connect 1.1.1.1:53`，不送資料） | A→外面 | 不通 `ENETUNREACH` | **通** | 不通 | 不通 | ＋net host 通 | `net none` 已封；net host 就是要網路（第 26 條） |

### 行程對行程（照 PID 直接叫）

| 路 | 方向 | 預設 | net host | seccomp off | subuid | ABI 3 模擬 | 怎麼封、成本 |
|---|---|---|---|---|---|---|---|
| 送訊號（`kill` 0 與 SIGWINCH） | A→兄弟、init、daemon（1 號） | 不通 `EPERM`（Landlock 擋訊號） | 不通 | 不通 | 不通 | **通**（三個都通；daemon 自己不理停止訊號）；＋subuid 不通 `EPERM` | 新 Linux 已封；舊 Linux 靠 subuid（第 38 條） |
| 同上 | A→外面的行程 | 不通 `ESRCH`（PID namespace 裡沒有那個號碼） | 同 | 同 | 同 | 同 | 已封 |
| `pidfd_open` | A→兄弟、init、daemon | **通**（拿得到 pidfd：知道它在、等得到它死） | 通 | 通 | 通 | 通 | 只有每隻自己一個 PID namespace 封得掉 |
| `pidfd_send_signal` | 同上 | 不通 `EPERM` | 不通 | 不通 | 不通 | **通**；＋subuid 不通 | 同送訊號 |
| `pidfd_getfd`、`ptrace`、`process_vm_readv`、`kcmp` | A→兄弟、init、daemon | 不通 `EPERM`（seccomp 擋） | 不通 | 不通 `EPERM`（seccomp 關了，Landlock 的「不能看 domain 外的行程」再擋一次） | 不通 | 不通 | 已封，兩層 |
| 數出有哪些行程（`kill(pid, 0)` 掃 1～4096） | A→天空這一層 | **通**（`EPERM` 跟 `ESRCH` 不一樣，看得出 1、3、4、5、6 號在；家機 ABI 7 時 5 個 `EPERM`） | 通 | 通 | 通 | 通（全部回 0） | 只有每隻自己一個 PID namespace |
| 讀別人的 nice（`getpriority`） | A→兄弟、init、daemon | **通**：B 把自己設成 7，A 讀到 7——**兄弟之間不經檔案的暗道** | 通 | 通 | **通**（subuid 也封不掉） | 通 | 只有每隻自己一個 PID namespace |
| 改別人的 nice、上限、CPU（`setpriority`、`prlimit`、`sched_setaffinity`；寫回它原本的值，只證明有權限） | A→兄弟、init | **通**（同一個 uid） | 通 | 通 | 不通 `EPERM` | 通；＋subuid 不通 | 第 38 條（subuid）就封 |
| 同上 | A→daemon（1 號） | `setpriority`、`sched_setaffinity` 不通 `EPERM`（daemon 有 caps，核心要求對方的 caps 不比自己多）；**`prlimit` 通**：讀得到也改得到 daemon 的 `RLIMIT_NOFILE`（調小就讓 daemon 開不了檔） | 同 | 同 | 不通 `EPERM` | 同預設；＋subuid 不通 | 第 38 條就封；在那之前想先擋，seccomp 可以只准 `prlimit64` 的 pid 是 0（只改自己；用 `prlimit(getpid())` 的程式會壞） |

### 看別人（`/proc`）

| 路 | 方向 | 預設 | net host | seccomp off | subuid | ABI 3 模擬 | 怎麼封、成本 |
|---|---|---|---|---|---|---|---|
| `/proc/<PID>/cmdline`、`status` | A→兄弟、init、daemon | **通**（daemon 的命令列含外面的 `daemon.json` 路徑） | 通 | 通 | 通 | 通 | 已知（aos-daemon README「天空裡看得到的外面資訊」）；每隻自己一個 PID namespace，或 proc 掛 `hidepid=invisible`＋subuid（沒實測） |
| `/proc/<PID>/mountinfo` | A→兄弟、daemon | **通**：B 的整張天空、每個 bind 來源在外面的路徑；daemon 的小世界（3 行） | 通 | 通 | 通 | 通 | 同上 |
| **`/proc/1/net/tcp`、`/proc/1/net/unix`**（daemon 在外面的 network namespace） | A→外面 | **通，`net none` 也通**：外面整台的 TCP 連線表、897 行 unix socket（含外面 hold 的 `@channels1127-out` 這種 abstract 名字）。唯讀，不能連 | 通 | 通 | **通**（subuid 也封不掉） | 通 | 每隻自己一個 PID namespace（看不到 1 號）；或 proc 掛 `hidepid=invisible`＋subuid（沒實測）。daemon 自己搬出外面的 network namespace 不行：net host 的 proc 要它 |
| `/proc/<PID>/net/*`（兄弟的） | A→兄弟 | 通（B 是 `net none`，只看到 B 自己的 lo） | 通（跟外面同一份） | 通 | 通 | 通 | 同上 |
| `/proc/<PID>/fd/`（列出 fd 號碼） | A→兄弟、init、daemon | **通**（只有號碼） | 通 | 通 | 不通 `EACCES` | 通 | 第 38 條就封 |
| `environ`、`root`、`fd/0` 的連結 | A→兄弟、init、daemon | 不通 `EACCES`（Landlock） | 不通 | 不通 | 不通 | 不通 | 已封 |
| 天空沒放 `proc`（C） | — | 上面這些全 `ENOENT`；**照 PID 直接叫的那張表（`pidfd_open`、`getpriority`、`prlimit`、掃 PID…）每一列跟 A 一模一樣** | 同 | 同 | 同 | 同 | 拿掉 `/proc` 只擋掉「讀檔」那一半 |

### 其他核心的東西

| 路 | 預設 | net host | seccomp off | subuid | ABI 3 模擬 | 說明、怎麼封 |
|---|---|---|---|---|---|---|
| `io_uring_setup` | 不通 `EPERM` | 不通 | **通**（家機 `io_uring_disabled` 0） | 不通 | 不通 | seccomp 封；關了照第 27 條是使用者自己選的 |
| `bpf`（建 map） | 不通 `EPERM` | 不通 | 不通 `EPERM`（`unprivileged_bpf_disabled` 2） | 不通 | 不通 | 兩層 |
| `keyctl`、`add_key` | 不通 `EPERM` | 不通 | **通**：**session keyring 跟起 daemon 的那個殼是同一個**（號碼一樣、`KEYCTL_READ` 列得出裡面有什麼）；user keyring 跟外面不同（照 user namespace 分），但跟兄弟 B 同一個 | 不通 | 不通 | seccomp 封；關了時外面登入 session 放的 key 讀得到。封法：daemon 在 exec 前替每隻換一個新的空 session keyring（`KEYCTL_JOIN_SESSION_KEYRING`），一行 |
| `perf_event_open` | 不通 `EPERM` | 不通 | 量自己通、量 B 不通 `EACCES` | 不通 | 不通 | seccomp＋Landlock |
| `userfaultfd` | 不通 `EPERM` | 不通 | 只有 user-mode-only 那種通（只碰自己的記憶體） | 不通 | 不通 | seccomp |
| `name_to_handle_at`／`open_by_handle_at` | 不通 `EPERM` | 不通 | 拿 handle 通、用 handle 開不通 `EPERM`（要外面那層的 `CAP_DAC_READ_SEARCH`） | 不通 | 不通 | 兩層 |
| `uname`／`sethostname` | 讀得到外面的 hostname；改不通 `EPERM` | 同 | 同 | 同 | 同 | 只是資訊；開 UTS namespace 一個旗標 |
| `clock_settime` | 不通 `EPERM` | 不通 | 不通 `EPERM`（沒有外面那層的 `CAP_SYS_TIME`） | 不通 | 不通 | 兩層 |
| `unshare` | user 與 user＋mount／net／ipc／uts／pid／cgroup／time 都通；不帶 user 的 mount、ipc 不通 `EPERM`；開了 user＋mount 之後 `mount` 不通 `EPERM`（Landlock） | 同 | 同 | 同 | 同 | 第 29 條故意准。proc 自己開 user＋ipc 之後外面的 key 就看不到了——自己做得到，只是沒人逼它 |
| `memfd_create` | 通 | 通 | 通 | 通 | 通 | 自己的匿名檔；要給別人只能經 unix socket 傳 fd，就是上面那幾條 |
| 繼承來的 fd | 沒有（0、1、2 以外 0 個） | 同 | 同 | 同 | 同 | 已封（daemon exec 前 `close_range`） |
| cgroup | `/proc/self/cgroup` 看得到外面的路徑（含 `aos-daemon-<起動那一層的 PID>.scope`）；`/sys/fs/cgroup` 不在天空 `ENOENT` | 同 | 同 | 同 | 同 | 只是資訊；進 cgroup 後開 cgroup namespace 一個旗標 |
| `/proc/self/mountinfo` | 看得到每個 bind 來源在外面那個檔案系統裡的路徑 | 同 | 同 | 同 | 同 | 已知（aos-daemon README 審查小事 10） |

## 結論

**「除了檔案沒有別的路」現在不成立。** 照預設設定還開著的、不經檔案的路：

1. **SysV IPC 與 POSIX mqueue，三個方向全通**（A↔外面、A↔兄弟、外面↔裡面），資料真的讀得到。原因就是 main 讀程式看到的：daemon 只開 user／PID／mount namespace，每隻 proc 另開 mount 與（`net none` 時）network，**沒開 IPC namespace**。這是最大的一條：兩隻 proc 不經任何 kernel 就能互傳任意資料；uid 0 時還碰得到使用者桌面程式的私有共享記憶體。另外 `shm_rmid_forced` 是 0，proc 沒清掉就死的 msg／sem／shm 會留在整台上，daemon 結束也不會走。
2. **`/proc/1/net/*`**：`net none` 的 proc 照樣讀得到外面整台的 TCP 連線表與 unix socket 名字（唯讀資訊）。因為 daemon（1 號）自己留在外面的 network namespace，而 `/proc/<PID>/net` 不看 ptrace 權限。
3. **照 PID 動別人**：改兄弟與 init 的 nice、資源上限、CPU 綁定；`prlimit` 連 daemon 的上限都改得到（能把它能開的 fd 數調小）。讀別人的 nice 是兄弟之間的暗道（B 寫、A 讀，subuid 也還在）。
4. **看得到誰在、在做什麼**：掃 PID、`pidfd_open`、別人的命令列、`status`、`mountinfo`（含兄弟天空的外面路徑）、fd 號碼。拿掉天空的 `proc` 只擋讀檔那一半，照 PID 直接叫的全部照舊。
5. 資訊類：hostname、cgroup 路徑、自己 mountinfo 裡的外面路徑。

**已經擋住的**：訊號（新 Linux）、ptrace 一族（seccomp 與 Landlock 兩層）、abstract socket 與 TCP 與外網（`net none`；`net host` 時 abstract 靠 Landlock）、io_uring／bpf／keyring／perf／userfaultfd／file handle（seccomp）、`mount`（Landlock）、別人的 `environ`／`root`／fd 連結、繼承來的 fd、`/dev/shm`。

**封路建議**（都要改 aos-daemon，這次沒改；由使用者挑）：

| # | 建議 | 封掉哪幾條 | 成本 |
|---|---|---|---|
| 1 | 起每隻 proc（含 init）時 `unshare` 多帶 `CLONE_NEWIPC` | 第 1 條整條（SysV、mqueue、列出整台的 shm）；proc 結束時它的 IPC 物件跟著消失 | 一個旗標（子行程那時還有 caps）。兄弟之間不能再用 SysV 共用；要共用就經 kernel 給的路 |
| 2 | 同一行再帶 `CLONE_NEWUTS`；進 cgroup 之後開 `CLONE_NEWCGROUP` | hostname、cgroup 路徑（資訊） | 各一個旗標 |
| 3 | 做第 38 條（預設 subuid、每隻不同） | 改別人的 nice／上限／CPU（含改 daemon 的上限）、列別人的 fd、舊 Linux 上的訊號 | 已經定了要做；subuid 欄就是做完的樣子 |
| 4 | 每隻自己一個 PID namespace（第 46 條「先不做」的那條），天空的 `proc` 掛那隻自己的 | `/proc/1/net`、看得到誰在、讀 nice 的暗道、`pidfd_open`、別人的命令列與 mountinfo——3 做完之後剩下的這些只有它封得掉 | 中：daemon 收屍、`kill`、`ns` 表、天空的 `/proc` 都要跟著改；init 要看全部時另外給它看。便宜的半套：proc 掛 `hidepid=invisible`，配 subuid 時別人的 `/proc/<PID>` 整個看不見（沒實測；PID 照樣叫得到） |
| 5 | exec 前替每隻換一個新的空 session keyring | `seccomp off`（或自己的名單放了 `keyctl`）時讀得到外面登入 session 的 keyring | 一行 |
| 6 | （3 做完前的權宜）seccomp 的擋單加「`prlimit64` 只准對自己（pid 0）」 | 改 daemon 的上限 | 用 `prlimit(getpid())` 而不是 0 的程式會失敗 |

做完 1～3，剩下的不經檔案的路只有「讀得到」的資訊與 nice 暗道；要連這些都沒有，就是 4。

**設計上故意留的**：開 user namespace 與各種 namespace（第 29 條）；`net host` 打開本機埠、外網、舊 Linux 上的 abstract socket（第 26 條：要網路的寫 host；能上網但碰不到本機服務要 pasta 那類，以後再說）；`seccomp off` 打開 io_uring 等（第 27 條：要的人自己選）；外面 → 裡面全通（外面是使用者本人）；`memfd_create`（只碰自己）；看得到什麼由天空定（第 46 條）。

## 跟公司 WSL（Linux 6.6、Landlock ABI 3）可能不同的地方

- **看「ABI 3 模擬」三欄**：訊號與 `pidfd_send_signal` 對兄弟、init、daemon 都送得出（daemon 不理停止訊號；核心也不讓 namespace 裡的行程用 SIGKILL 殺 1 號）；`net host` 時 abstract socket A↔兄弟、A→外面都通。subuid 擋得住訊號（abi3_subuid 欄 `EPERM`），擋不住 net host 的 abstract socket（它看的是 network namespace 與 Landlock，不看帳號）。WSL 上這三欄應該跟同名不帶 abi3 的三欄一樣——在公司跑一次 `run.py` 就能對。
- 模擬只騙了 daemon，核心還是 6.18。由核心與 sysctl 決定的格子在 WSL 上可能不同，影響的多半是 `seccomp off` 那欄：`perf_event_paranoid`、`unprivileged_bpf_disabled`、`unprivileged_userfaultfd`、`io_uring_disabled` 的值（家機 2、2、0、0）。IPC 那幾條靠的 `SHM_STAT_ANY`（4.17 起）、mqueue、`/proc/<PID>/net` 在 6.6 一樣有，預期照樣全通。
- WSL 外面那層的 `/proc/1/net/unix` 會多 WSL 自己的 socket；hostname 是 Windows 的電腦名。
- `run.py` 在 WSL 上照跑（`fakeabi.so` 在 ABI 3 的機器上等於沒作用）。

## 沒測的

- 時間、CPU、快取、記憶體壓力這類側通道：要統計才量得出來，不是「通不通」的問題，這次不做。同類的還有整台的計數（`/proc/stat`、`/proc/loadavg`、`/proc/meminfo`）與共用檔案系統的剩餘空間（`statfs`），兩邊都讀得到就能當暗道。
- UDP、ICMP、netlink：`net none` 下跟 TCP 同一個 network namespace，理由相同，沒另外測。
- futex：要先有共享記憶體，就是 SysV shm 那條。
- tty（`TIOCSTI` 之類）：天空的 `dev` 沒有 tty。
- 外面的 D-Bus、X11、Wayland 等服務：都是 unix socket，路徑型的走檔案（天空沒放就沒有），abstract 型的看上面那列。
- 真的去 `shmat` 別的程式的私有段、真的把 daemon 的上限調小：只證明有權限，沒做會影響別人的事。
- subuid 與 `hidepid` 一起時 `/proc` 那幾列會怎樣：要改 daemon 的 proc 掛載選項，沒做。

## 檔案

| 檔 | 是什麼 |
|---|---|
| `run.py` | 一鍵跑：編、起 daemon、起 B／A／C、外面的 hold 與 find、印表、比對殘留 |
| `probe.c` | 探測程式：`hold`（建東西、等 SIGTERM、清掉）、`probe`（A、C 試的每一條）、`find`（外面找 B 的）、`sleep`（init） |
| `fakeabi.c` | `LD_PRELOAD` 墊片：daemon 問 Landlock 版本時回 3（模擬舊 Linux） |
