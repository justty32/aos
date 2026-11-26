aos-daemon：照「daemon 只提供資訊與工具、判斷全交給主 kernel」重做的第一版 daemon（C++20，不用 root）：自己開 user／PID／mount namespace 當 1 號，擺出一個資訊與工具的目錄（外面走 `/proc/<PID>/cwd`、主 kernel 在自己天空裡的 `/aos` 讀寫，不給它任何權限），自己住進只有這個目錄的小世界，先起主 kernel，其他 proc 由 `start` 起、各進一個 Landlock domain；每隻 proc 的資訊是一個真的夾 `procs/<名>/`，`forget` 就消失。

# aos-daemon（proto9，11-26）

← [proto9](../../README.md)｜設計：[daemon職責-1126](../../../proto8/thinking/2026-11/26/daemon職責-1126.md)（第 1～8 條；「實作時定的」第 17～19 條＝結束寬限、`on_parent_death`、`forget -k`、daemon 設定檔）、[daemon當容器-1125](../../../proto8/thinking/2026-11/25/daemon當容器-1125.md)（五樣）｜前身：[sky-1125 小實驗](../../experiments/sky-1125/README.md)（Python 玩具，這裡照它的做法改寫成 C++）｜用的庫：[aos-procfs](../aos-procfs/README.md)

舊的 proto9 aos-daemon（照舊前提做的：判卡住、自動重起、register）11-26 使用者說收掉，最後一版在 commit `068bfb2fb`；這支原本叫 aos-daemon2，收掉舊的後改名。

## 夾裡有什麼

| 檔 | 是什麼 |
|---|---|
| `src/main.cpp` | 入口與「起動那一層」：讀 daemon 設定檔與參數（參數蓋過檔）、需要時經 `systemd-run --user --scope` 拿一個 cgroup、開 namespace、用 `newuidmap`／`newgidmap` 寫對照表、把訊號轉給 daemon、daemon 結束後清 cgroup |
| `src/daemon.cpp` | daemon 本體（1 號）：握住要的 fd、擺目錄、換根進小世界、起主 kernel、收屍、主 kernel 死了照起動參數做、`procs/<名>/` 的建與拿、工具檔的五個指令 |
| `src/spawn.cpp` | 起一隻 proc：子行程先在小世界拿 daemon 的目錄（主 kernel 才要）、進原本那一層拿來源、根從零組天空、換根、進 cgroup、上鎖、exec；跑的時候掛、卸 |
| `src/ns.cpp` | 天空表：讀那隻的 `/proc/<PID>/mountinfo`，一個掛載一行，對回設定標上來源 |
| `src/config.cpp` | 讀設定檔（json）與天空的每一行 |
| `src/util.cpp` | 小工具：經起動前握住的根讀外面的檔、時間、記錄、訊號名字 |
| `src/common.hpp` | 共用的型別 |
| `tests/run.py` | 測試（`make test`） |
| `tests/toys.py` | 測試時在天空裡跑的小程式 |

aos-procfs 的原始碼在 `make` 時編進 `build/obj/procfs/`，不動 `../aos-procfs` 的任何檔（含它的 `build/`）。JSON 用 `../third_party/nlohmann`。

## 怎麼編、怎麼跑

```
cd proto9/cpp/aos-daemon
make            # build/bin/aos-daemon；-Wall -Wextra 沒有警告
make test       # tests/run.py：約 20～25 秒（grace 組要等寬限）；只跑某幾組：python3 tests/run.py basic restart
```

手動玩（`k.json` 的寫法見下面「設定檔」；也可以 `build/bin/aos-daemon daemon.json &`，見下面「daemon 設定檔」）：

```
$ build/bin/aos-daemon --kernel /path/to/k.json &
export AOS_DAEMON=/proc/12345/cwd          # 外面（使用者）用的；主 kernel 拿到的 AOS_DAEMON 是 /aos
$ cat /proc/12345/cwd/status
$ echo "start /path/to/worker.json" > /proc/12345/cwd/ctl
$ cat /proc/12345/cwd/procs/worker/ns
$ echo "kill worker TERM" > /proc/12345/cwd/ctl
$ echo "forget worker" > /proc/12345/cwd/ctl
$ kill %1        # daemon 結束，底下整片跟著走
```

起動參數：

| 參數 | 意思 |
|---|---|
| `DAEMON_CONFIG`（位置參數，最多一個） | daemon 設定檔，見下面「daemon 設定檔」；下面的參數寫了就蓋過檔裡的值 |
| `--kernel CONFIG` | 主 kernel 的設定檔（跟 `start` 同一種格式），一定要給（這裡，或 daemon 設定檔的 `kernel`）；相對路徑從起動時的 cwd 算 |
| `--on-kernel-exit restart\|exit` | 主 kernel 死了：`restart`（預設）重起；`exit` daemon 直接結束 |
| `--restart-limit N`、`--restart-window S` | `S` 秒內死超過 `N` 次就不再起，daemon 結束（預設 5、60） |
| `--cgroup auto\|off` | `auto`（預設）：不在交給自己的 cgroup 裡，就用 `systemd-run --user --scope -p Delegate=yes` 重跑自己；沒有 systemd --user 就當 `off` |
| `--subuid auto\|off` | `auto`（預設）：`/etc/subuid`、`/etc/subgid` 有範圍又有 `newuidmap`／`newgidmap` 就接在 1 號後面 |
| `--exit-grace S` | 收到 SIGTERM／SIGINT／SIGHUP 時先只對主 kernel 送 SIGTERM、最多等 `S` 秒再全部 SIGKILL（預設 0＝馬上），見下面「結束」 |
| `--on-parent-death exit\|stay` | 起動那一層死了：`exit`（預設）daemon 跟著走；`stay` 留著，見下面「起動那一層死了」 |

### daemon 設定檔（使用者 11-26 定）

`aos-daemon daemon.json`：一個位置參數＝daemon 設定檔的路徑（相對路徑從 cwd 算，`status` 的 `config` 寫成絕對路徑）。一個 JSON 物件，除了 `kernel` 都可不寫，不寫＝下面的預設（跟命令列的預設一樣）：

```json
{
  "kernel": "kernel.json",
  "on_kernel_exit": "restart",
  "restart_limit": 5,
  "restart_window": 60,
  "exit_grace": 0,
  "on_parent_death": "exit",
  "cgroup": "auto",
  "subuid": "auto"
}
```

| 鍵 | 型別與值 | 對到的參數 |
|---|---|---|
| `kernel` | 字串：主 kernel 設定檔的路徑，相對路徑**從 daemon.json 所在的夾算**（絕對路徑也行）；或物件：整份主 kernel 設定直接寫在這裡（跟 `start` 同一種格式） | `--kernel` |
| `on_kernel_exit` | `"restart"`／`"exit"` | `--on-kernel-exit` |
| `restart_limit` | 整數 ≥ 0（`2.5`、`"5"` 都拒） | `--restart-limit` |
| `restart_window` | 數字 ＞ 0（秒） | `--restart-window` |
| `exit_grace` | 數字 ≥ 0（秒，可以有小數） | `--exit-grace` |
| `on_parent_death` | `"exit"`／`"stay"` | `--on-parent-death` |
| `cgroup`、`subuid` | `"auto"`／`"off"` | `--cgroup`、`--subuid` |

- **參數蓋過檔**：`aos-daemon daemon.json --exit-grace 10` 用檔裡的其他值、`exit_grace` 用 10。檔裡有 `kernel` 又給了 `--kernel`：用 `--kernel`。只給參數不給檔（`aos-daemon --kernel k.json …`）照舊能用，`status` 的 `config` 寫 `-`。
- `kernel` 兩邊都沒給、不認得的鍵、型別不對、值不對、檔讀不到、不是 JSON、最上層不是物件、給了兩個位置參數：起不來，退出碼 2，stderr 一行英文說明（跟其他起動錯誤一樣）。主 kernel 設定本身寫錯（路徑那份或內嵌那份）照舊由 daemon 讀時拒、退出碼 2。
- **內嵌的主 kernel 設定**：`procs/<名>/config` 寫 **`<daemon.json 的絕對路徑>#/kernel`【擬】**（JSON pointer 的寫法，指到檔裡那一格）；主 kernel 重起時用起動時讀到的那份，不再讀檔（路徑那種也一樣）。
- `"cgroup": "off"` 時 `status` 寫 `cgroup: off ("cgroup": "off" in the daemon config)`；命令列的 `--cgroup off` 照舊寫 `off (--cgroup off)`。
- `--cgroup auto` 經 `systemd-run` 重跑自己時，daemon 設定檔與 `--kernel` 的路徑先換成絕對路徑，其他參數（含蓋過檔的）照原樣帶過去；重跑後再讀一次檔。

### 結束（`exit_grace`，使用者 11-26 定）

- 收到 SIGTERM、SIGINT、SIGHUP（三個一樣）：先**只對主 kernel** 送 SIGTERM（不送給它的行程組、不送給其他 proc），最多等 `exit_grace` 秒；主 kernel 先結束就馬上不等；時間到或主 kernel 結束了，照舊 `kill(-1, SIGKILL)` 收掉其餘全部。退出碼照舊 0。
- 等的時候：主 kernel 結束了**不重起**（`on_kernel_exit` 是 `restart` 也一樣，`status` 的 `kernel_last_exit` 照記）；主循環照跑，`ctl` 照用（主 kernel 可以在這段用 `kill`、`forget` 收別的 proc；`start` 也還收，最後一樣被 SIGKILL）；用 monotonic 時鐘算期限。
- 等的時候再收到結束訊號：**不管，照樣等到期限【擬】**（在終端機按 Ctrl-C 時 daemon 與起動那一層同一個行程組，daemon 會收到兩次 SIGINT：自己一次、起動那一層轉一次；第二次要是算「馬上收」，寬限就沒用了）。要馬上收就 `kill -9` daemon。
- `exit_grace` 0（預設）：對主 kernel 送 SIGTERM 後馬上全部 SIGKILL，等於以前的做法。
- daemon 是因為主 kernel 已經死了才結束的（`on_kernel_exit exit`、到重起上限）：沒有主 kernel 可等，直接 SIGKILL 其餘的，退出碼照舊。
- stderr 記：`got SIGTERM: sent SIGTERM to the main kernel …, waiting up to N s`，結束時 `exiting (got SIGTERM; main kernel … within the exit grace)` 或 `… still running after exit_grace N s`。

### 起動那一層死了（`on_parent_death`，使用者 11-26 定）

- `exit`（預設，照以前）：daemon 設 parent-death signal（SIGKILL；現在在等起動那一層的 pipe 之前就設，中間死了也不漏），起動那一層被 `kill -9` 時 daemon 跟著走，PID namespace 的 1 號走了 Linux 收掉整片；cgroup scope 空了由 systemd 收。
- `stay`：不設 parent-death signal。起動那一層被 `kill -9` 時 daemon 與底下的 proc 照跑（daemon 被外面那層的 init 或 subreaper 收養），目錄照樣走 `/proc/<daemon PID>/cwd`，`ctl` 照用。要停就直接對 daemon 的 PID（export 那行裡的數字）送 SIGTERM（照上面「結束」、有寬限），daemon 的退出碼沒人收。
  - **cgroup 的收尾**：平常起動那一層在 daemon 結束後清 cgroup（刪漏的 `p-*`、關 controller、搬回 scope、刪 `daemon/`）。`stay` 而起動那一層已經死了，這段沒人做：daemon 結束前照舊自己刪它開的 `p-*`；剩下的 `daemon/` 與開著的 controller 留著，**scope 裡的行程走光時 systemd 把整個 scope（連同 `daemon/`）收掉、unit 也消失**（`--collect`；`pdeath` 組驗了）。沒有 cgroup（`off`）就沒有這段。
  - scope 在起動那一層死了之後還在（裡面還有 daemon 與 proc），`systemctl --user list-units 'aos-daemon-*'` 看得到，直到 daemon 結束。
  - SIGHUP 照舊是結束訊號：daemon 跟起動那一層同一個行程組（沒有 `setsid`），終端機關掉時一樣會收到。

退出碼：收到 SIGTERM／SIGINT／SIGHUP 是 0（有寬限也一樣）；`--on-kernel-exit exit` 時是主 kernel 的退出碼（被訊號殺是 128＋訊號）；到重起上限是 1；起不來是 2（含主 kernel 設定用了保留的 `/aos`、`/cgroup`，或 uid 不是 0）。

## 資訊與工具的目錄

外面是 `/proc/<daemon PID>/cwd/`；主 kernel 的天空裡是 `/aos/`（預設，見下面「主 kernel」；設定選 `"daemon_access": "ptrace"` 時是 `/proc/1/cwd/`，daemon 在自己的 PID namespace 是 1 號）。其他 proc 碰不到。

| 路徑 | 內容 |
|---|---|
| `status` | daemon 的資訊：`pid_ns`（1）、`pid_host`、`started_at`、`config`（daemon 設定檔的絕對路徑，只用參數起是 `-`）、`main_kernel`、`on_kernel_exit`、`restart_limit`、`exit_grace`（`N s`）、`on_parent_death`（`exit`／`stay`）、`kernel_restarts`、`kernel_deaths_in_window`、`kernel_last_exit`、`landlock_abi`、`cgroup`（外面的路徑或 `off (原因)`）、`subuid`、`main_kernel_access`（`mount /aos` 或 `ptrace /proc/1/cwd`）、`procs`，加上 ctl 回饋四行 `aos_ctl_cmd`／`state`／`error`／`count` |
| `ctl` | 工具：一次寫一行，見下 |
| `procs/<名>/` | 一隻 proc 的資訊（真的夾：`start` 成功時建，`forget`、主 kernel 重起時連同底下整個拿掉；`ls procs/` 列出來的就是表上還在的名字），每個一個檔：`name`、`pid`（`ns: N` 是 daemon 那一層、也就是天空裡 `/proc` 看到的；`host: N` 是起 aos-daemon 的那一層）、`state`（`alive`／`dead`）、`exit`（`-`、`code N`、`signal N SIGNAME`）、`started_at`、`ended_at`（UTC）、`ns`（天空表，一行一個掛載的文字）、`ns.json`（同一張表的 JSON，見下）、`ns_check`（`ok` 或對不上的地方）、`uid`（`ns: N`、`host: N`）、`locks`（上了哪些鎖，一行一種）、`config`（設定檔路徑）；有 cgroup 時還有 `cgroup` → 那隻的 cgroup 夾（`cpu.max`、`memory.max`、`pids.max`、`cgroup.freeze`、`cgroup.kill` 直接寫就是開關；相對連結 `../../../cgroup/p-…`，外面、主 kernel 的 `/aos` 底下都通） |

`ns` 是 Plan 9 的意思（這隻 proc 的天空表），跟 Linux 的 `/proc/<PID>/ns/`（namespace 連結的資料夾）不是同一個東西；使用者 11-26 定名。

工具（`ctl`）：

| 指令 | 做什麼 |
|---|---|
| `start CONFIG_PATH` | 照設定檔起一隻。路徑是起 daemon 那一層看到的絕對路徑【擬】 |
| `kill NAME SIGNAL` | 送訊號（`TERM`、`SIGTERM`、`15` 都認）。沒有「好好停」：要好好收，由 kernel 先送 TERM、等多久它定、再送 KILL |
| `mount NAME [-w] SRC DST` | 把外面的 SRC 掛進一隻跑著的 proc 的天空 DST（預設唯讀）；DST 不在而根是唯讀時，暫時把根改成可寫、建好掛載點再改回。主 kernel（mount 模式）的 `/aos`、`/cgroup` 與底下不收（`EINVAL`、`PathReserved`） |
| `umount NAME DST` | 從它的天空卸掉 DST；主 kernel 的 `/aos`、`/cgroup` 同上不收 |
| `forget NAME` | 把死掉的從表上拿掉、`procs/<名>/` 連同底下整個拿掉（還活著就拒）；它的 cgroup 夾裡還有它留下的行程時也拒（`EIO`、`CgroupNotEmpty`，說明裡提示 `forget -k`；先寫 `cgroup.kill` 或用 `forget -k`） |
| `forget -k NAME` | 跟 `forget` 一樣，但它的 cgroup 夾裡還有行程時，daemon 先寫 `cgroup.kill`、等到夾空了（最多 **5 秒【擬】**，monotonic）再照 `forget` 拿掉；逾時是 `EIO`、`aos_ctl_error` 寫 `Timeout … still has processes 5 s after writing cgroup.kill`，`cgroup.kill` 寫不進去是 `EIO`、`CgroupKillFailed`。那隻本身還活著照舊拒（`EINVAL`、`ProcAlive`：`forget` 是給死掉的，`-k` 只清它留下的孩子）。沒有 cgroup（`cgroup off`）時跟 `forget` 一樣（沒東西可清，留下的孩子照跑，daemon 結束時一起收）。使用者 11-26 定 |

**寫入等做完才回**（使用者 11-26 定；用 aos-procfs 的「做完才回」ctl，`Ctl::reply_when_done()`）：`start` 等那隻 exec 成功才回（寫入回來時 `procs/<名>/` 已經在、`state` 是 `alive`），`mount`／`umount` 等掛好、卸好，`kill` 等訊號送出（不等它死），`forget` 等從表上拿掉（寫入回來時 `procs/<名>` 已經走不到；`-k` 也等清完）。

- 寫錯的（不認得的字、參數不對、名字不在、`kill` 死掉的、`forget` 活著的、路徑不是絕對路徑）：寫入當場失敗 `EINVAL`，`aos_ctl_state: rejected`（不變）。
- 收下之後做的時候才失敗的（設定檔讀不到、json 不對、非主 kernel 的設定寫了 `daemon_access`、同名的已經在、exec 失敗、組天空失敗、cgroup 上限寫不進去、掛不上、卸不掉）：寫入失敗 **`EIO`【擬】**（殼裡是 `write error: Input/output error`）。寫入帶不了字，原因照舊在 `status` 的 `aos_ctl_error`（`aos_ctl_state: failed`），daemon 也寫到 stderr。
- 寫入一回來，`status` 的 `aos_ctl_*` 已經是這一道的結果，不用再等。
- 等的時候按 Ctrl-C（或 `kill` 寫的那支）：寫的人當場拿到 `EINTR` 放開，指令照做，結果只在 `aos_ctl_*`。daemon 等的時候結束了：寫的人拿到連線斷掉的錯（`ECONNABORTED`／`ENOTCONN` 之類，沒進測試）。
- 一道還在做時（例 `start` 在組天空），別人寫 `ctl` 照舊當場 `EBUSY`；讀 `status` 不受影響。
- 最久等多久：`start` 的組天空、exec 各有 10 秒逾時，叫主執行緒做事有 60 秒逾時（逾時＝`EIO`＋`Timeout …`／`Internal …`）；之外沒有別的逾時。
- `stat` 看到 `ctl` 的大小是 1073741824：aos-procfs「做完才回」的 ctl 都這樣報（讓先開好檔的第二個人當場拿到 `EBUSY`，見 aos-procfs 的 README）。

daemon 不做的：自動重起（主 kernel 以外）、判卡住、准不准、kernel 登記表。

## 設定檔【擬】

```json
{
  "name": "worker",
  "argv": ["/usr/bin/python3", "/toys/toys.py", "sleep"],
  "env": {"PATH": "/usr/bin:/bin"},
  "cwd": "/",
  "ns": [
    {"type": "bind", "src": "/usr", "dst": "/usr"},
    {"type": "bind", "src": "/etc", "dst": "/etc"},
    {"type": "symlink", "target": "usr/bin", "dst": "/bin"},
    {"type": "symlink", "target": "usr/lib", "dst": "/lib"},
    {"type": "symlink", "target": "usr/lib64", "dst": "/lib64"},
    {"type": "dev", "dst": "/dev"},
    {"type": "proc", "dst": "/proc"},
    {"type": "tmpfs", "dst": "/tmp"},
    {"type": "bind", "src": "/home/me/toys", "dst": "/toys"},
    {"type": "bind", "src": "/home/me/out", "dst": "/out", "rw": true}
  ],
  "uid": 0,
  "locks": {"cgroup": {"memory.max": "64M", "pids.max": "50"}},
  "stdout": "/home/me/out/worker.log"
}
```

主 kernel 的設定（`--kernel`）多收一個鍵 **`daemon_access`【擬】**：`"mount"`（不寫＝這個）或 `"ptrace"`，見下面「主 kernel」。其他 proc 的設定寫了這個鍵，`start` 就失敗（`EIO`、`ConfigBad`）。

- `name`：字母、數字、`_ - .`，1～64 字，不以 `.` 開頭。同名的還在表上（活的或死了沒 forget）就拒。
- `argv[0]`：天空裡的絕對路徑。
- `env`：不給就是 `PATH=/usr/local/bin:/usr/bin:/bin`、`HOME=/`。一律加上 `AOS_NAME=<名>`。`AOS_DAEMON` 只給主 kernel（mount 模式 `/aos`、ptrace 模式 `/proc/1/cwd`）；其他 proc 讀不到 daemon 的目錄，所以不給，設定裡寫了也拿掉【擬】。
- `ns`：根一定是一塊新的空 tmpfs（組好後改唯讀），每條一個 JSON 物件（**使用者 11-26 定**；不再收字串，字串當設定錯拒），照順序做：`{"type": "bind", "src": SRC, "dst": DST}`（預設唯讀，加 `"rw": true` 才可寫；`rw` 可不寫、只有 bind 收、要是布林；SRC 是外面的路徑）、`{"type": "tmpfs", "dst": DST}`（mode 1777）、`{"type": "proc", "dst": DST}`、`{"type": "dev", "dst": DST}`（tmpfs 加 null、zero、full、random、urandom 與 fd、stdin、stdout、stderr 四個 symlink，組好後唯讀）、`{"type": "symlink", "target": TARGET, "dst": DST}`。不認得的鍵、缺的鍵、型別不對、不認得的 `type` 都拒（`ConfigBad`，說明哪一條哪裡錯；`start` 是 `EIO`、`--kernel` 的檔是退出碼 2）。天空裡的 symlink 只在天空裡解（`openat2` 的 `RESOLVE_IN_ROOT`），寫成絕對路徑也不會碰到外面。
- `uid`：0＝天空裡的 0 號（外面的使用者本人）；N＞0＝subuid 範圍的第 N 個（外面是 subuid 起點＋N−1），gid 同號。
- `locks.cgroup`：起動前寫進那隻 cgroup 夾的檔與值（不收 `cgroup.*`）。沒有 cgroup 時給了就拒。`locks.landlock` 只能是 `true`（不能關）；`locks.seccomp` 這版不收。
- `stdout`、`stderr`：外面的路徑（附加寫）；不給就是 `/dev/null`（**使用者 11-26 定**；不再跟 daemon 的 stderr，主 kernel 也一樣；只給一條，另一條也是 `/dev/null`）。stdin 一律 `/dev/null`。
- 不認得的鍵一律拒。

## 天空表的寫法【擬】

一個掛載一行：`種類 來源 天空裡的位置 ro|rw [locked]`，例：

```
tmpfs - / ro
bind /usr /usr ro
bind /usr/lib/wsl/lib /usr/lib/wsl/lib ro locked
dev - /dev ro
bind /dev/null /dev/null rw
proc - /proc rw
bind /home/me/out /out rw
```

表是在 proc 組好天空、exec 之前從它的 `mountinfo` 量出來的（跑的時候掛、卸之後重量一次），每行對回設定標上來源，所以跟 mountinfo 一行對一行。`locked`＝設定沒寫、是 bind 來源底下外面那層掛的、被迫一起帶進來的（公司 WSL 的 `/usr` 底下有三個）。量的跟設定對不上（少了、多了、唯讀可寫不同）就寫在 `ns_check`。路徑裡的空白、tab、換行、反斜線照 mountinfo 寫成 `\040` 這種八進位。symlink 不是掛載，不在表上。

同一張表另有 JSON 版 `procs/<名>/ns.json`（使用者 11-26 定：設定檔的 `ns` 每條一個 JSON 物件；資訊有 `ns`（一行一行的文字）與 `ns.json`（同一張表的 JSON）共存）。兩個檔是同一次量的、掛／卸之後一起換，永遠是同一張表；`ns_check` 還是文字。格式：`[` 單獨一行、每個物件一行（除了最後一個，行尾有逗號）、`]` 單獨一行、結尾有換行；鍵跟設定的一條一樣（`type`、`src`、`dst`、`rw`），`rw` 一定有，`locked: true` 只有 locked 的才有，文字行上是 `-` 的 `src` 不寫；路徑是一般 JSON 字串（不寫 `\040`，mountinfo 的八進位跳脫會解開）。例：

```
[
{"type": "tmpfs", "dst": "/", "rw": false},
{"type": "bind", "src": "/usr", "dst": "/usr", "rw": false},
{"type": "bind", "src": "/usr/lib/wsl/lib", "dst": "/usr/lib/wsl/lib", "rw": false, "locked": true},
{"type": "proc", "dst": "/proc", "rw": true}
]
```

主 kernel 的 `/aos`、`/cgroup` 兩條在 `ns.json` 也一樣有（`{"type": "aos", "dst": "/aos", "rw": true}`、`{"type": "cgroup", "src": "…", "dst": "/cgroup", "rw": true}`）。

## 做法

### 起動（不用 root）

1. 起動那一層用 `clone(CLONE_NEWUSER | CLONE_NEWPID | CLONE_NEWNS)` 生出 daemon；daemon 先停在一根 pipe 上。
2. 起動那一層自己叫 `newuidmap <PID> 0 <uid> 1 1 <subuid 起點> <數量>`、`newgidmap` 同樣（不靠 `unshare` 的參數：util-linux 2.39 只認最後一個 `--map-users`）；沒有 subuid 就直接寫 `uid_map`、`setgroups deny`、`gid_map` 一段。寫好了把 daemon 在外面的 PID 等幾個數字從 pipe 送過去。
3. 起動那一層留著：把 SIGTERM／SIGINT／SIGHUP 轉給 daemon，等它結束、清 cgroup、用它的退出碼結束。`on_parent_death exit`（預設）時 daemon 設了 parent-death signal（SIGKILL），起動那一層被 `kill -9` 時 daemon 跟著走；`stay` 不設（見上面「起動那一層死了」）。
4. daemon 是 1 號：SIGCHLD、SIGTERM、SIGINT、SIGHUP 擋下來由 signalfd 收（1 號沒裝處理的訊號會被丟掉；擋著的訊號外面那層也送得進來）；收到後三個就照上面「結束」做（先給主 kernel `exit_grace` 秒）。結束前自己 `kill(-1, SIGKILL)`、收完屍、刪掉開過的 cgroup 夾；被 `kill -9` 時 Linux 照樣收掉整片（PID namespace 的 1 號走了）。

### 小世界

1. 還在原本那一層（自己 mount namespace 裡的那份）時，先握住：根的 O_PATH fd、外面的 procfs、cgroup 夾，再掛上自己 PID namespace 的 procfs、握住它與這個 mount namespace 本身（`/proc/self/ns/mnt`）。
2. 再 `unshare(CLONE_NEWNS)` 開小世界：一塊 64k 的 tmpfs，裡面只有 `aos/`（aos-procfs 的 FUSE 掛載，`fusermount3` 在 user namespace 裡可以用）與 `cgroup/`（交給 daemon 的 cgroup 夾的 bind）；改成唯讀後 `pivot_root` 進去、舊的根整片卸掉、站進 `/aos`。
3. 之後 daemon 碰外面只經握住的 fd：讀設定檔用 `openat2(根, 路徑, RESOLVE_IN_ROOT)`；組天空、跑的時候掛時，子行程先 `setns` 回原本那一層再拿來源（`open_tree(OPEN_TREE_CLONE)` 只認呼叫者自己 mount namespace 裡的掛載，原本那一層要一直活著，所以握的是 namespace 而不只是根的 fd）。
4. 沒設 non-dumpable：`/proc/<PID>/root` 從外面看只有 `aos`、`cgroup` 兩個夾（測試驗了），`/proc/<PID>/cwd` 照樣能用。

### 起一隻 proc

只有主執行緒 fork 與收屍；工具檔的做事的線把要 fork 的事交給主執行緒做、等它回話。子行程：

0. 只有主 kernel（mount 模式）：還在小世界時把 `/aos`（有 cgroup 時加 `/cgroup`）`open_tree(OPEN_TREE_CLONE)` 成還沒掛上的掛載（見下面「主 kernel」）。
1. 進原本那一層；讀外面的 procfs 的 `self` 拿到自己在外面的 PID；開 stdin／stdout／stderr。
2. 每個 bind 的來源先 `open_tree(OPEN_TREE_CLONE)`；被拒（EINVAL：來源底下有鎖住的子掛載）就連子掛載一起（`AT_RECURSIVE`）。
3. `unshare(CLONE_NEWNS)`，在自己這份的 `/tmp` 掛一塊新 tmpfs 當根（來源都拿好了，蓋住外面的 `/tmp` 不影響），照設定一條一條做；bind 用 `mount_setattr` 設 nosuid、nodev、唯讀再 `move_mount`；主 kernel 再掛上第 0 步拿的 `/aos`、`/cgroup`（可寫）。根改唯讀，`pivot_root` 進去、舊的根卸掉。
4. 進自己的 cgroup（`p-<名>-<流水號>`，上限 daemon 先寫好了）。
5. 告訴 daemon「組好了」，daemon 趁它停著讀 mountinfo 做天空表，再叫它走。
6. 上鎖：清附加群組；securebits（noroot、no_setuid_fixup、keep_caps_locked、no_cap_ambient_raise，全部鎖住）；清空 bounding set；設 uid/gid；caps 清成 0（ptrace 模式的主 kernel 留 cap_sys_ptrace）；no_new_privs；進一個自己的 Landlock domain（主 kernel 不進）。exec。哪一步失敗，原因經 pipe 回 daemon，`start` 記 `failed`、不留在表上。

Landlock 的 domain 只管一種檔案系統的權限（建 block 裝置，本來就做不到），沒有別的規則：要的是「自己一個 domain」帶來的隔開——不能讀 daemon 與旁邊 proc 的 `/proc/<PID>/root`、`cwd`、`environ`。ABI 6 以上再加擋訊號與 abstract unix socket；公司 WSL（6.6，ABI 3）擋不住訊號，測試照實記下（同帳號的 proc 能對 daemon 送訊號）。

### 主 kernel

- daemon 掛好目錄、印出 export 那行後第一件事起它。它是唯一不進 Landlock 的 proc。
- **怎麼碰 daemon 的目錄**（使用者 11-26 定，[daemon職責-1126](../../../proto8/thinking/2026-11/26/daemon職責-1126.md)「實作時定的」第 2 條；設定檔的 `daemon_access`）：

| `daemon_access` | 目錄在哪 | 權限 | `AOS_DAEMON` |
|---|---|---|---|
| `mount`（預設） | 自己天空裡的 **`/aos`【擬】**；有 cgroup 時 cgroup 夾在 **`/cgroup`【擬】** | **一個 cap 都沒有**（bounding set 也清空），跟其他 proc 一樣 | `/aos` |
| `ptrace`（舊的做法，「保留 A」） | `/proc/1/cwd` | 留 CAP_SYS_PTRACE 一個 | `/proc/1/cwd` |

- **mount 模式怎麼做**：daemon 的目錄是小世界裡的一個 FUSE 掛載，只在 daemon 的 mount namespace 裡。起主 kernel 的子行程 fork 出來時還在小世界，**先 `open_tree(OPEN_TREE_CLONE)` 把 `/aos`（與 `/cgroup`）複製成還沒掛上的掛載**，再進原本那一層拿天空的來源；組天空時（根改唯讀之前）用 `mount_setattr`（nosuid、nodev、可寫）＋`move_mount` 掛到天空的 `/aos`、`/cgroup`。還沒掛上的掛載可以掛進別的 mount namespace（天空的 bind 本來就這樣做），所以不用任何新權限。FUSE 只放跟 daemon 同 uid 的行程進來、`ctl` 是 0200，主 kernel 用天空裡的 0 號就讀寫得到，跟 caps 無關。實測（`access` 組）：caps 全 0、讀得到 `/aos/status`、寫 `/aos/ctl` 的 `start` 等到 `alive` 才回、失敗是 `EIO`、原因在 `/aos/status`、`kill`／`forget` 後 `/aos/procs/<名>` 走不到；讀 `/proc/1/cwd` 是 `EACCES`。
- **為什麼也掛 `/cgroup`**：`procs/<名>/cgroup` 是相對連結 `../../../cgroup/p-…`。小世界裡 `/aos` 旁邊是 `/cgroup`，主 kernel 的天空擺成一樣，連結在兩邊都通（外面走 `/proc/<PID>/cwd` 時解在 daemon 的根裡，照舊通）。所以 mount 模式的主 kernel，天空設定不能自己用 `/aos`（有 cgroup 時還有 `/cgroup`）與底下：daemon 起不來（退出碼 2，說明原因）；`ctl` 的 `mount`／`umount` 也不准動這兩個地方。
- **天空表**多兩行：`aos - /aos rw` 與 `cgroup <cgroup 夾外面的路徑> /cgroup rw`（`ns_check` 照樣對）；`locks` 檔寫 `capabilities: none (bounding set empty)` 與 `daemon directory: /aos in its ns …`。
- **ptrace 模式**：Linux 讀別的行程的 `/proc/<PID>/cwd` 時，除了同 uid，還要「自己的 caps 包含對方的」；daemon 在 user namespace 裡有全部 caps，主 kernel 清成 0 就讀不到（實測：0 caps EACCES，只留 cap_sys_ptrace 就讀得到）。代價是能 ptrace 同一個 user namespace 裡的行程（含 daemon）。這個模式天空裡沒有 `/aos`。
- 兩種模式主 kernel 都讀得到其他 proc 的 `/proc/<PID>/root`（mount 模式也行：對方 caps 是 0、同 uid；Landlock 只擋 domain 裡的往外，不擋外面的往裡）。
- 主 kernel 要用天空裡的 0 號（uid 0）：`ctl` 是 0200、FUSE 也只放跟 daemon 同 uid 的行程進來。主 kernel 設定的 uid 不是 0，daemon 起不來（退出碼 2，說明原因；兩種 `daemon_access` 都一樣；重起主 kernel 時不再讀設定檔，所以只在起動時檢查）——使用者 11-26 定。
- 它死了：`restart`（預設）就重起；`--restart-window` 秒內死超過 `--restart-limit` 次（預設 60 秒內超過 5 次，即第 6 次）就不再起，daemon 結束、整片收掉。起不來（exec 失敗之類）也算死一次。重起時舊的那筆從表上拿掉（`procs/<名>/` 整個拿掉）、用同一個名字起新的（新的 `procs/<名>/`）；`status` 的 `kernel_restarts`、`kernel_last_exit` 記著。`exit`：daemon 直接結束，退出碼用主 kernel 的。

### `procs/<名>/`：真的夾（使用者 11-26 定，「實作時定的」第 4 條）

- 表是「名字 → 那隻」。`start` 成功時建 `procs/<名>/` 與底下每個檔；`forget`（與主 kernel 重起時的舊那筆）用 aos-procfs 的 `remove_tree` 連同底下整個拿掉。以前的 `slots/<i>/`＋symlink 拿掉了。
- 每個檔的內容由那隻自己的記錄產生（檔抓著那隻記錄的 `shared_ptr`）；夾拿掉時跟著放。
- 「表」與「目錄」一起改（一把只在放上表、拿掉時拿的鎖）：主執行緒的 `start`、主 kernel 重起，跟做事的線的 `forget` 不會交錯。回答的線不拿這把鎖，所以拿著它叫 `remove_tree`（要跟核心講話）不會卡住回答的線。
- `forget` 只拿它看過、確定死掉的那一筆：中間主 kernel 剛好被重起成同名的新一隻，就不動新的那隻。
- 拿掉之後：寫入一回來，`procs/<名>` 就走不到（核心的快取也丟了）；同名馬上再起，看到的是新的；拿掉前已經開著的檔照舊讀得到開檔那刻的內容（`dirs` 組驗了）。

### cgroup

- `--cgroup auto`：先用 `systemctl --user show -p Version` 確認有 systemd --user，再 `systemd-run --user --scope --quiet --collect -p Delegate=yes --unit=aos-daemon-<PID> -- 自己 參數…` 重跑自己（PID 不變）。
- 在 scope 裡：起動那一層把自己搬進 `scope/daemon/`（cgroup v2 規定開了 controller 的夾不能直接放行程），再把 `cgroup.controllers` 列的都寫進 `cgroup.subtree_control`（這台有 cpu、memory、pids 等）。每隻 proc 一個 `scope/p-<名>-<流水號>/`。
- 收尾：daemon 結束前刪它開的 `p-*`；起動那一層再刪一次漏的、關掉 controller、搬回 scope、刪 `daemon/`，scope 由 systemd 收。起動那一層被 `kill -9` 時 systemd 也會整個收掉（測試驗了）；`on_parent_death stay` 時 scope 留到 daemon 結束、裡面空了才由 systemd 整個收（見上面「起動那一層死了」）。
- 沒有 systemd --user：`status` 寫 `cgroup: off (原因)`，設定給了 `locks.cgroup` 就拒，其餘照常。

## 測試

`make test`（公司 WSL：Linux 6.6.114.1-microsoft-standard-WSL2、Landlock ABI 3、cgroup v2、有 systemd --user、`/etc/subuid` 有範圍）：**280 PASS、0 FAIL**（11-26 加 daemon 設定檔、結束寬限、`on_parent_death`、`forget -k` 四組 `dconf`、`grace`、`pdeath`、`forgetk` 共＋91 條，在那之前 189；11-26 proc 的 stdout／stderr 沒設改 `/dev/null`、加 `stdio` 組＋10 條，在那之前 179；11-26 設定檔 `ns` 改物件、加 `ns.json` 與 `nsconf` 組共＋22 條；在那之前 157：主 kernel 改走 `/aos`、`procs/<名>/` 改成真的夾後 155；再加主 kernel uid 不是 0 要拒的 2 條），約 20～25 秒（grace 組照實等寬限），清 build 跑一次加連跑 3 次都一樣。等待一律用 monotonic 時鐘、等到條件成立（WSL2 的牆上時鐘每 32 秒左右往回跳 1.6 秒）。

| 組 | 驗什麼 |
|---|---|
| `basic` | 一般使用者起得來；export 那行；daemon 在自己的 PID namespace 是 1 號（NSpid）；uid 對照表；經 `/proc/<PID>/cwd` 讀 `status`；`/proc/<PID>/root` 只有小世界、看不到 `/etc`、`/usr`；目錄裡只有 `ctl`、`procs/`、`status`（沒有 `slots/`）；主 kernel 讀得到 `$AOS_DAEMON/status`、`AOS_DAEMON` 是 `/aos`、caps 是 0；SIGTERM 後退出碼 0 |
| `procs` | start／kill／forget；`start` 的寫入回來時那隻已經在表上、`alive`；`pid` 兩層對得上 NSpid；forget 活的、kill 不在的、壞訊號、不認得的字、相對路徑都寫入失敗 `EINVAL`；同名、讀不到設定、關 Landlock、exec 失敗都是寫入失敗 `EIO`＋`failed`＋原因；退出碼 7、SIGTERM 記對；uid 1001 在外面是 subuid；主 kernel 自己寫 `/aos/ctl` 起一隻（寫入回來時已經 `alive`），起不來的它拿到 `EIO` |
| `nsconf` | 設定的 `ns` 物件寫法能起（`rw` 可不寫）；字串條目、不認得的鍵、缺 `dst`／`src`、`rw` 不是布林或用在非 bind、不認得的 `type`、`dst` 不是字串都是 `EIO`＋`ConfigBad` 且不留 `procs/` 的夾；`--kernel` 的檔寫字串條目退出碼 2 |
| `ns` | `ns.json` 是 JSON、版面（`[`、一行一物件、`]`）、條數與 `ns` 行數一樣、type／dst／rw／locked 對得上、`rw` 一定有、含空白的路徑是一般字串（文字檔仍是 `\040`）、掛／卸之後 `ns.json` 跟著換；天空表的行數、掛載點、唯讀可寫跟 mountinfo 一樣；每個 bind 的來源跟掛載點是同一個檔（dev＋inode）；WSL 的 `/usr` 子掛載記成 `locked`；唯讀的地方寫不進去、`-w` 的寫得進去而且落在外面的夾；根裡只有設定放的東西 |
| `landlock` | 非主 kernel 的 proc 讀不到 `/proc/1/cwd`、`/proc/1/root`、旁邊 proc 的 `/proc/<PID>/root` 與 `environ`，自己的 `/proc/self/root` 可以；能不能對 daemon 送訊號照 ABI 記（ABI 3：能）；主 kernel 讀得到旁邊 proc 的 `/proc/<PID>/root`；`locks` 檔；caps 0、no_new_privs |
| `cgroup` | `procs/<名>/cgroup` 可用、行程在裡面、`memory.max`／`pids.max` 照設定、`cgroup.freeze` 凍住再解凍、forget 刪掉夾、不認得的上限檔 `EIO`＋`failed`、daemon 結束後 scope 不見 |
| `mount` | 跑的時候掛進去、看得到、表多一行且仍跟 mountinfo 一樣；`-w`；卸掉後不見、表也拿掉；來源不在、卸沒掛的地方都是 `EIO`＋`failed`；相對路徑寫入失敗 `EINVAL` |
| `modes` | `--cgroup off --subuid off`：對照表只有一段、給 cgroup 上限或 uid 5 都 `EIO`＋`failed`、一般 proc 照起、`locks` 寫 groups kept |
| `restart` | 前兩次起來就死的主 kernel 被重起兩次後活著；`--restart-limit 3` 起 4 次後 daemon 以 1 結束並說明原因；`--on-kernel-exit exit` 以主 kernel 的 4 結束、不重起；`--restart-limit 0` 第一次死就結束 |
| `teardown` | `kill -9` daemon：底下 4 隻 1 秒內全不見、起動那一層以 137 結束；`kill -9` 起動那一層：daemon 與底下跟著走 |
| `access` | mount 模式（預設）：`status` 寫 `main_kernel_access: mount /aos`；主 kernel 的 CapInh／Prm／Eff／Bnd／Amb 全 0；`AOS_DAEMON=/aos`、讀得到 `/aos/status`、讀 `/proc/1/cwd` 是 `EACCES`；天空表有 `aos - /aos rw` 與 cgroup 那行、`ns_check` ok；mountinfo 裡 `/aos` 是 `fuse.aosproc`；`locks` 寫 caps none、目錄在 `/aos`；列 `/aos`；寫 `/aos/ctl` 的 `start` 回來時已經 `alive`、讀 `/aos/procs/w/state`；起不來的是 `EIO`、原因在 `/aos/status`；經 `/aos/procs/w/cgroup` 讀到 `pids.max`；`ctl` 卸 `/aos`、掛蓋 `/aos` 都 `EINVAL`（`PathReserved`）；`kill`、`forget` 後 `/aos/procs/w` 走不到。非主 kernel 的：沒有 `/aos`、`/cgroup`，讀不到 `/proc/1/cwd`，沒有 `AOS_DAEMON`（有 `AOS_NAME`）；設定寫 `daemon_access` 是 `EIO`＋`ConfigBad`；外面的 `/proc/<PID>/cwd` 照通。ptrace 模式：`status` 寫 `ptrace /proc/1/cwd`、只留 cap_sys_ptrace、`AOS_DAEMON=/proc/1/cwd` 讀得到、沒有 `/aos`、經它寫 `start` 可以。主 kernel 天空自己用 `/aos`：daemon 以 2 結束並說明；主 kernel uid 5（mount、ptrace 兩種模式）：daemon 以 2 結束、說明要 uid 0 |
| `dirs` | `procs/x` 是夾不是 symlink、裡面是那幾個檔；`ls procs/`；先讓核心快取那條路、開著一個檔，`forget` 回來時 `procs/x` 與底下都走不到、`ls procs/` 只剩 main、開著的檔照讀；同名再起是新的那隻；10 次 start／forget 每次都建、拿；最後 `procs/` 與 `status` 的 `procs` 對 |
| `dconf` | 只用參數起照舊、`status` 的 `config` 是 `-`、`exit_grace`／`on_parent_death` 的預設；daemon.json 給 `kernel` 絕對路徑（`config` 是那個檔、`procs/main/config` 是 kernel 路徑、`cgroup auto` 經重跑照樣有 cgroup）；相對路徑從 daemon.json 的夾算（cwd 是 `/`）；daemon.json 本身給相對路徑（`config` 寫絕對、重跑也帶得過去）；內嵌的主 kernel（`main_kernel` 是它的名字、`procs/<名>/config` 是 `<檔>#/kernel`、讀得到 `$AOS_DAEMON/status`）；每個鍵都讀（`status` 各行）；參數蓋過檔（`--on-kernel-exit`、`--restart-limit`、`--exit-grace`、`--on-parent-death`、`--cgroup auto` 蓋過、`restart_window`／`subuid` 留檔裡的）；`--kernel` 蓋過 `kernel`；不認得的鍵、型別不對、值不對、沒有 `kernel`、不是 JSON、最上層不是物件、kernel 檔不在、內嵌的缺 `argv`、檔讀不到、兩個位置參數、`--exit-grace` 壞值、`--on-parent-death` 壞值都是退出碼 2＋說明 |
| `grace` | `--exit-grace 5`：收 SIGTERM 會收尾的主 kernel 收完（檔在）、daemon 以 0 結束、主 kernel 一結束就不等（< 3 秒）、其他 proc 被殺、沒重起；不理 SIGTERM 的主 kernel＋`--exit-grace 2`：等的時候主 kernel 與其他 proc 都還活著、約 2 秒後以 0 結束、全收掉、說明原因；寬限裡以 3 結束的主 kernel 不重起、daemon 馬上以 0 結束；主 kernel 在寬限裡經 `ctl` `kill`＋`forget`；寬限裡外面的 `start` 與主 kernel 的 `kill` 照用、第二個 SIGTERM 不會提早收、3 秒後以 0 結束；預設 0：不收尾、馬上結束；SIGINT 一樣有寬限；`on_kernel_exit exit`、到重起上限時不等 |
| `pdeath` | `--on-parent-death stay`：`status` 寫 `stay`；`kill -9` 起動那一層後 daemon 還在、`/proc/<PID>/cwd/status` 讀得到、proc 照跑、`ctl` 照用、scope 還在；對 daemon 送 SIGTERM 後 daemon 與 proc 都不見、scope 與 unit 由 systemd 收掉 |
| `forgetk` | 死掉的 proc 在 cgroup 裡留了孩子：`forget` 照舊 `EIO`＋`CgroupNotEmpty`（提示 `forget -k`）、夾還在、孩子還在；`forget -k` 回 done、`procs/<名>` 不見、孩子不見、cgroup 夾刪掉、記了 `cgroup.kill`；活的 `EINVAL`＋`ProcAlive`、不在的 `ProcUnknown`、用法錯 `ArgumentsBad`；cgroup 空的照樣 done；主 kernel 經 `/aos/ctl` 寫 `forget -k`；`--cgroup off`：`-k` 跟 `forget` 一樣、孩子照跑、daemon 結束時一起走 |
| `leftovers`（最後一定跑） | 沒有留下行程（daemon、起動那一層、天空裡的 toys.py）、systemd unit、`aos-daemon-*` cgroup、掛載 |

## 【擬】（不清楚時選保守的，之後可改）

- 設定檔的格式（json 鍵、天空每條一個 JSON 物件的寫法、`uid` 的意思、`locks` 的樣子）。
- `start` 的路徑是起 daemon 那一層看到的絕對路徑（主 kernel 住在自己的天空裡，未必知道那些路徑）。
- 天空表一行的寫法（`種類 來源 位置 ro|rw [locked]`），從 mountinfo 量、對回設定。
- 主 kernel 天空裡放 daemon 目錄的固定位置叫 `/aos`；有 cgroup 時 cgroup 夾放 `/cgroup`（跟小世界一樣的擺法，`procs/<名>/cgroup` 的相對連結才通）。這兩個地方主 kernel 的天空設定不能用（用了 daemon 起不來），`ctl` 的 `mount`／`umount` 也不准動。**（使用者 11-26 定：照這樣）**
- 選舊做法的設定鍵叫 `daemon_access`（`mount`／`ptrace`，預設 `mount`），放在主 kernel 的設定檔裡；其他 proc 的設定寫了就拒。**（使用者 11-26 定：照這樣）**
- `status` 多一行 `main_kernel_access`**（使用者 11-26 定：留著）**；天空表的兩行寫成 `aos - /aos rw`、`cgroup <外面的路徑> /cgroup rw`。
- 小世界裡除了 `aos/` 還有 `cgroup/`（cgroup 夾的 bind）；`procs/<名>/cgroup` 是相對 symlink `../../../cgroup/p-…`，外面走 `/proc/<PID>/cwd/…`、主 kernel 走 `/aos/…` 都通。
- 工具檔叫 `ctl`，回饋在 `status` 的 `aos_ctl_*` 四行。
- 做的時候失敗的寫入回 `EIO`（原因只在 `aos_ctl_error`）；`kill` 的「做完」是訊號送出、不等它死；`start` 的「做完」是 exec 成功。
- 主 kernel 重起時舊的那筆直接拿掉、同名起新的；它死的情形記在 `status`。
- 主 kernel 起不來也算死一次，照重起規則走。
- ~~daemon 結束時不另給寬限~~、~~起動那一層被殺時 daemon 跟著走~~：**使用者 11-26 定**做成參數、預設照以前（`exit_grace` 0、`on_parent_death exit`）。參數名 `--exit-grace`、`--on-parent-death` 是 eca-aos 擬的（daemon職責「實作時定的」第 17 條）；daemon 設定檔的鍵名照第 19 條。
- 寬限裡再收到結束訊號不管、照樣等到期限（見「結束」）。
- `status` 多 `exit_grace`（`N s`）、`on_parent_death` 兩行（`config` 一行是使用者定的）。
- 內嵌的主 kernel 設定，`procs/<名>/config` 寫 `<daemon.json>#/kernel`。
- daemon 設定檔沒有 `kernel` 但給了 `--kernel` 也能起（兩邊都沒有才拒）。
- `forget -k` 最多等 5 秒；不帶 `-k` 的 `forget` 碰到 cgroup 裡還有行程照舊是 `EIO`（做下去才知道，跟以前一樣），不是 `EINVAL`。
- `--cgroup auto` 重跑自己時只把 daemon 設定檔與 `--kernel` 的路徑換成絕對路徑，其他參數照原樣。
- proc 的 stdout／stderr 沒設就是 `/dev/null`（**使用者 11-26 定**；含主 kernel；daemon 自己的 stdout 只印 export 那行、stderr 只有 daemon 自己的訊息）；stdin 是 `/dev/null`；每隻 `setsid`。
- `AOS_DAEMON` 只給主 kernel（`/aos` 或 `/proc/1/cwd`）；其他 proc 不給（讀不到 daemon 的目錄），設定裡寫了也拿掉。`AOS_NAME` 每隻都給。**（使用者 11-26 定：照這樣）**
- 名字跟 proto8 的 `AOS_DAEMON`（daemon 的資料夾）同一個意思；使用者 11-26 定（原本叫 `AOS_ROOT`）。舊名 `AOS_ROOT` 現在沒有特殊意思：設定的 `env` 寫了就當一般環境變數照傳。
- `forget` 時那隻的 cgroup 夾裡還有它留下的行程就拒；`forget -k` 先清（**使用者 11-26 定**）。
- Landlock 的規則只管「建 block 裝置」一種，用意只在進一個自己的 domain；沒有 Landlock 的核心上非主 kernel 的 proc 一律起不來。
- subuid 最多用 65535 個（uid 0～65535）。
- 退出碼的分法（0／主 kernel 的碼／1／2）。

## 還沒做的

- seccomp（設定給了就拒）。
- 網路（`net none` 之類）：天空都跟 daemon 同一個 network namespace，也就是外面的網路。
- 擋訊號、abstract socket：要 Landlock ABI 6（Linux 6.12 以上）；這台 6.6 擋不住，程式在 ABI 6 以上會自動加。
- `start` 的路徑用天空裡的路徑（照主 kernel 自己的天空換算）：這版只收外面的路徑。
- 天空表只在起動與跑的時候掛／卸之後量；proc 自己改不了天空（沒有 caps），所以這兩個時候以外不會變。
- 一個很慢的天空（例如 bind 的來源卡在別的 FUSE 上）會讓主執行緒等到 10 秒逾時，這段時間其他 `start` 也排著。
- 沒試過：沒有 Landlock 的核心、沒有 systemd --user 而 `--cgroup auto`（照程式會寫 `off (no systemd --user …)`）、cgroup v1、家機。

## 要使用者定的

1. ~~ctl 的錯誤要不要等做完才回~~：使用者 11-26 定「要」。aos-procfs 加了「做完才回」的 ctl，這裡用上了（見上面「寫入等做完才回」）；還要看的只剩 errno 挑 `EIO` 可不可以。
2. ~~主 kernel 留 CAP_SYS_PTRACE 可以嗎~~：使用者 11-26 選「掛進主 kernel 的天空、不給權限」，並保留舊做法。做好了（見上面「主 kernel」）；`/aos`、`/cgroup`、`daemon_access`、非主 kernel 不給 `AOS_DAEMON`（改名自 `AOS_ROOT`）、`main_kernel_access`，使用者 11-26 都說照這樣。
3. **ABI 3 擋不住訊號**：非主 kernel 的 proc 能對 daemon 送 SIGTERM（daemon 一收就整片收掉）。daemon 職責第 5 條已記「之後要求較新的 Linux」；這版照實記在測試與 `locks` 檔。
4. ~~小世界裡放 `cgroup/`~~：使用者 11-26 定「照現在這樣」。開關照第 7 條「直接擺進資訊」，這版是把 cgroup 夾 bind 進小世界、用相對 symlink 指過去；所以 `/proc/<PID>/root` 會看到 `aos`、`cgroup` 兩個夾。
5. ~~資訊夾用 `slots/<i>/` 加 symlink~~：使用者 11-26 定 `procs/<名>/` 是真的夾、`forget` 就消失。aos-procfs 加了 `remove_tree`，這裡用上了（見上面「`procs/<名>/`：真的夾」）。
