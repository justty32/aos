aos-daemon：照「daemon 只提供資訊與工具、判斷全交給 init」重做的第一版 daemon（C++20，不用 root）：自己開 user／PID／mount namespace 當 1 號，擺出一個資訊與工具的目錄（外面走 `/proc/<PID>/cwd`、init 在自己天空裡的 `daemon_path`（預設 `/aos`）讀寫，不給它任何權限），自己住進只有這個目錄的小世界，先起 init（有設定的話），其他 proc 由 `start` 起、各進一個 Landlock domain、預設各有自己的 network namespace（只有 lo）、每隻（含 init）exec 前都上一層 seccomp（預設內建的擋單）；每隻 proc 的資訊是一個真的夾 `procs/<名>/`，`forget` 就消失；停止訊號只收外面與 init 送的；目錄擺 aoslua 的介面宣告（`aos/ctl`、`aos/jsonpath`、`aos/proc`）。

# aos-daemon（proto9，11-26）

← [proto9](../../README.md)｜設計：[daemon職責-1126](../../../proto8/thinking/2026-11/26/daemon職責-1126.md)（第 1～8 條；「實作時定的」第 17～19 條＝結束寬限、`on_parent_death`、`forget -k`、daemon 設定檔；第 30～37 條＝`ns.json` 的 `by`／`at`、合併目錄、`restart-init`、介面宣告、停止訊號的寄件人、普通 proc 寫不到 init 的 ctl、bind 來源卡住）、[daemon當容器-1125](../../../proto8/thinking/2026-11/25/daemon當容器-1125.md)（五樣）｜前身：[sky-1125 小實驗](../../experiments/sky-1125/README.md)（Python 玩具，這裡照它的做法改寫成 C++）｜用的庫：[aos-procfs](../aos-procfs/README.md)

舊的 proto9 aos-daemon（照舊前提做的：判卡住、自動重起、register）11-26 使用者說收掉，最後一版在 commit `068bfb2fb`；這支原本叫 aos-daemon2，收掉舊的後改名。

**init**＝daemon 起的第一隻（地位像 Linux 的 1 號），判斷都歸它。使用者 11-26 定名 init（原本叫主 kernel、main kernel）：設定鍵、參數、`status` 的行、訊息、測試全改了，**舊名不再收**（daemon 設定檔的 `kernel`、`on_kernel_exit` 是不認得的鍵，`--kernel`、`--on-kernel-exit` 是不認得的參數，都是退出碼 2）。init 在 `procs/` 底下的名字照它設定的 `name`（測試裡叫 `main`）。

## 夾裡有什麼

| 檔 | 是什麼 |
|---|---|
| `src/main.cpp` | 入口與「起動那一層」：讀 daemon 設定檔與參數（參數蓋過檔）、需要時經 `systemd-run --user --scope` 拿一個 cgroup、開 namespace、用 `newuidmap`／`newgidmap` 寫對照表、把訊號轉給 daemon、daemon 結束後清 cgroup |
| `src/daemon.cpp` | daemon 本體（1 號）：握住要的 fd、擺目錄、換根進小世界、起 init、收屍、init 死了照起動參數做、`procs/<名>/` 的建與拿、工具檔的六個指令、停止訊號的寄件人、介面宣告 |
| `src/spawn.cpp` | 起一隻 proc：子行程先在小世界拿 daemon 的目錄（init 才要）、進原本那一層拿來源、根從零組天空（`net none` 時也開自己的 network namespace、打開 lo）、換根、進 cgroup、上鎖、exec；跑的時候掛、卸 |
| `src/ns.cpp` | 天空表：讀那隻的 `/proc/<PID>/mountinfo`，一個掛載一行，對回設定標上來源 |
| `src/config.cpp` | 讀設定檔（json）與天空的每一行；init 的 `daemon_path` 與 cgroup 夾的位置 |
| `src/seccomp.cpp` | seccomp 過濾器（手寫 BPF）：內建的擋單、使用者名單檔、x86_64 系統呼叫名字表、`locks` 檔的那一行 |
| `src/util.cpp` | 小工具：經起動前握住的根讀外面的檔、時間、記錄、訊號名字 |
| `src/common.hpp` | 共用的型別 |
| `tests/run.py` | 測試（`make test`） |
| `tests/toys.py` | 測試時在天空裡跑的小程式 |

aos-procfs 的原始碼在 `make` 時編進 `build/obj/procfs/`，不動 `../aos-procfs` 的任何檔（含它的 `build/`）。JSON 用 `../third_party/nlohmann`。

## 怎麼編、怎麼跑

```
cd proto9/cpp/aos-daemon
make            # build/bin/aos-daemon；-Wall -Wextra 沒有警告
make test       # tests/run.py：約 80 秒（grace 組要等寬限、stuck 組照實等三次 10 秒逾時）；只跑某幾組：python3 tests/run.py basic restart
```

手動玩（`init.json` 的寫法見下面「設定檔」；也可以 `build/bin/aos-daemon daemon.json &`，見下面「daemon 設定檔」）：

```
$ build/bin/aos-daemon --init /path/to/init.json &
export AOS_DAEMON=/proc/12345/cwd          # 外面（使用者）用的；init 拿到的 AOS_DAEMON 是它的 daemon_path（預設 /aos）
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
| `--init CONFIG` | init 的設定檔（跟 `start` 同一種格式）；相對路徑從起動時的 cwd 算。**沒給 daemon 設定檔時一定要給**（只用參數又沒 `--init`：退出碼 2，說明裡提示「要沒有 init 的 daemon，給一份不寫 `init` 的 daemon 設定檔」，見下面「沒有 init」） |
| `--on-init-exit restart\|exit` | init 死了：`restart`（預設）重起；`exit` daemon 直接結束 |
| `--restart-limit N`、`--restart-window S` | `S` 秒內死超過 `N` 次就不再起（預設 5、60）；之後怎樣看 `--on-restart-limit` |
| `--on-restart-limit exit\|stay` | 到重起上限：`exit`（預設）daemon 以 1 結束；`stay` daemon 留著、沒有 init，見下面「到重起上限」 |
| `--exit-code init\|own` | `on_init_exit exit` 時 daemon 的退出碼：`init`（預設）用 init 的；`own` 用自己的 **3**，見下面「退出碼」 |
| `--cgroup auto\|off\|PATH` | `auto`（預設）：不在交給自己的 cgroup 裡，就用 `systemd-run --user --scope -p Delegate=yes` 重跑自己；沒有 systemd --user 就當 `off`。`PATH`（絕對路徑）：用這個已經交給自己的 cgroup v2 夾，見下面「cgroup」 |
| `--subuid auto\|off` | `auto`（預設）：`/etc/subuid`、`/etc/subgid` 有範圍又有 `newuidmap`／`newgidmap` 就接在 1 號後面 |
| `--exit-grace S` | 收到 SIGTERM／SIGINT／SIGHUP 時先只對 init 送 SIGTERM、最多等 `S` 秒再全部 SIGKILL（預設 0＝馬上），見下面「結束」 |
| `--on-parent-death exit\|stay` | 起動那一層死了：`exit`（預設）daemon 跟著走；`stay` 留著，見下面「起動那一層死了」 |

### daemon 設定檔（使用者 11-26 定）

`aos-daemon daemon.json`：一個位置參數＝daemon 設定檔的路徑（相對路徑從 cwd 算，`status` 的 `config` 寫成絕對路徑）。一個 JSON 物件，每個鍵都可不寫，不寫＝下面的預設（跟命令列的預設一樣）；**不寫 `init` 就是沒有 init 的 daemon**（使用者 11-26 定，見下面「沒有 init」）：

```json
{
  "init": "init.json",
  "on_init_exit": "restart",
  "restart_limit": 5,
  "restart_window": 60,
  "on_restart_limit": "exit",
  "exit_code": "init",
  "exit_grace": 0,
  "on_parent_death": "exit",
  "cgroup": "auto",
  "subuid": "auto"
}
```

| 鍵 | 型別與值 | 對到的參數 |
|---|---|---|
| `init` | 字串：init 設定檔的路徑，相對路徑**從 daemon.json 所在的夾算**（絕對路徑也行）；或物件：整份 init 設定直接寫在這裡（跟 `start` 同一種格式）；不寫＝沒有 init | `--init` |
| `on_init_exit` | `"restart"`／`"exit"` | `--on-init-exit` |
| `restart_limit` | 整數 ≥ 0（`2.5`、`"5"` 都拒） | `--restart-limit` |
| `restart_window` | 數字 ＞ 0（秒） | `--restart-window` |
| `on_restart_limit` | `"exit"`／`"stay"` | `--on-restart-limit` |
| `exit_code` | `"init"`／`"own"` | `--exit-code` |
| `exit_grace` | 數字 ≥ 0（秒，可以有小數） | `--exit-grace` |
| `on_parent_death` | `"exit"`／`"stay"` | `--on-parent-death` |
| `cgroup` | `"auto"`／`"off"`／絕對路徑（已經交給自己的 cgroup 夾，起動那一層看到的路徑；相對路徑拒） | `--cgroup` |
| `subuid` | `"auto"`／`"off"` | `--subuid` |

- **參數蓋過檔**：`aos-daemon daemon.json --exit-grace 10` 用檔裡的其他值、`exit_grace` 用 10。檔裡有 `init` 又給了 `--init`：用 `--init`（檔裡沒有 `init` 而給了 `--init` 也一樣有 init）。只給參數不給檔（`aos-daemon --init init.json …`）照舊能用，`status` 的 `config` 寫 `-`。
- 不認得的鍵（含舊名 `kernel`、`on_kernel_exit`）、型別不對、值不對、檔讀不到、不是 JSON、最上層不是物件、給了兩個位置參數、只用參數又沒有 `--init`：起不來，退出碼 2，stderr 一行英文說明（跟其他起動錯誤一樣）。init 設定本身寫錯（路徑那份或內嵌那份）照舊由 daemon 讀時拒、退出碼 2。
- **內嵌的 init 設定**：`procs/<名>/config` 寫 **`<daemon.json 的絕對路徑>#/init`【擬】**（JSON pointer 的寫法，指到檔裡那一格）；init 重起時用起動時讀到的那份，不再讀檔（路徑那種也一樣）。
- `"cgroup": "off"` 時 `status` 寫 `cgroup: off ("cgroup": "off" in the daemon config)`；命令列的 `--cgroup off` 照舊寫 `off (--cgroup off)`。
- `--cgroup auto` 經 `systemd-run` 重跑自己時，daemon 設定檔與 `--init` 的路徑先換成絕對路徑，其他參數（含蓋過檔的）照原樣帶過去；重跑後再讀一次檔。

### 沒有 init（使用者 11-26 定）

daemon 設定檔不寫 `init`（也沒給 `--init`）：daemon 照樣起來、擺目錄、印 export 那行，但不起任何 proc。

- 沒有人拿到 `AOS_DAEMON`（`start` 起的 proc 本來就不給）；目錄只有外面走 `/proc/<daemon PID>/cwd` 碰得到，`ctl` 的指令照用（`start`、`kill`、`forget`…都由外面的人寫；`restart-init` 是 `EINVAL NoInit`）。
- `status`：`init: -`、`init_state: none (no init in the daemon config)`、`init_access: -`；`on_init_exit`、`restart_limit`、`on_restart_limit`、`exit_code` 照印設定的值，但用不到；`init_restarts` 一直是 0。stderr 記一行 `no init (the daemon config has no "init") …`。
- 收到 SIGTERM／SIGINT／SIGHUP：沒有人可給寬限，**直接全部 SIGKILL**、以 0 結束（`exit_grace` 設了也一樣）；stderr 寫 `exiting (got SIGTERM, no init)`。
- **只用參數（沒有 daemon 設定檔）又沒給 `--init`：照舊拒**（退出碼 2，說明裡提示寫一份不含 `init` 的 daemon 設定檔，例如只有 `{}`）**【擬】**：只用參數起的人多半是忘了 `--init`，悄悄起一個沒有 init 的 daemon 反而意外；要沒有 init 就明寫一份 daemon 設定檔。
- `{}`（空物件）是合法的 daemon 設定檔：全部預設、沒有 init。

### 到重起上限（`on_restart_limit`，使用者 11-26 定）

- `exit`（預設，照以前）：init 在 `restart_window` 秒內死超過 `restart_limit` 次，daemon 以 1 結束、整片收掉。
- `stay`：daemon **不結束**，其他 proc 照跑，外面的人照樣用 `ctl`。
  - init 不再起；死掉的那筆**留在表上**（`procs/<名>/` 在、`state` 是 `dead`、`exit` 記著最後一次怎麼死的）**【擬】**，要拿掉就 `forget`（之後同名的 `start` 是一般 proc，不是 init）。
  - `status`：`init` 照寫它的名字；`init_state: gone (restart limit reached: init died N times within W s, more than --restart-limit L; on_restart_limit stay)`；`init_restarts`、`init_last_exit` 照記。stderr 記 `… on_restart_limit stay: not restarting it, the daemon keeps running without init`。
  - 要 init 再起：`ctl` 寫 `restart-init`（使用者 11-26 定，見下面「`restart-init`」）。`start` 收的設定就算寫成 init 那份，起來的也只是一般 proc（進 Landlock、不給 `AOS_DAEMON`；設定裡有 `daemon_access`、`daemon_path` 還會被拒）。
  - 之後收到結束訊號：沒有 init 可等，直接全部 SIGKILL、以 0 結束。

### `restart-init`（使用者 11-26 定，daemon職責「實作時定的」第 33 條）

`echo restart-init > $AOS_DAEMON/ctl`（不帶參數）：

- **只在 init 不在時能用**：表上的 init 已經死了（到重起上限而 `stay` 的 `gone`）、或已經 `forget` 掉、或還沒起過。init 活著：寫入當場 `EINVAL`、`aos_ctl_error` 是 `InitAlive …`。daemon 設定沒有 init：`EINVAL`、`NoInit the daemon config has no init`**【擬：當場拒，跟其他寫錯的一樣】**。帶參數：`EINVAL ArgumentsBad`。表上同名的是一般 proc（`forget main` 之後有人 `start` 了一隻叫 `main` 的）：`EINVAL ProcExists … (forget it first)`**【擬】**。
- 照 daemon 設定的 init（起動時讀到的那份，跟自動重起一樣不再讀檔）起一隻**真正的 init**：mount 模式掛 `daemon_path`（與旁邊的 `cgroup`）、給 `AOS_DAEMON`、照它的 `locks.landlock`、`net`、`seccomp`。
- 表上舊的那筆先拿掉（`procs/<名>/` 整個拿掉，跟自動重起一樣）；**重起次數歸零**：`init_restarts` 與 `init_deaths_in_window` 都回到 0（重起的時間窗重新算）**【擬：兩個都歸零】**，`gone` 的狀態清掉；`init_last_exit` 照留（是上一隻的事）。stderr 記 `restart-init: starting init main (restart count reset)`。
- 起來之後照平常的規則：再死就照 `on_init_exit`／`restart_limit` 走。
- **起不來**（例：init 天空的 bind 來源不見了）：寫入 `EIO`、原因在 `aos_ctl_error`，**不自動再試**、daemon 照跑、沒有 init，`init_state` 寫 `gone (restart-init failed: <原因>)`**【擬】**（自動重起那條「起不來也算死一次」是給 daemon 自己判的；這裡是有人下指令，失敗就回給他，要不要再試由他定）。修好後再寫一次 `restart-init` 就好。
- 寫入等做完才回：回來時 init 已經 `alive`（跟 `start` 一樣等 exec）。
- 實測（`rinit` 組）：活著 `EINVAL InitAlive`；`--restart-limit 1 --on-restart-limit stay` 死兩次成 `gone` 後 `restart-init` 回 done、新的 init `alive`、兩個次數是 0、讀得到 `/aos/status`、天空有 `/aos`；再死一次又被自動重起（時間窗重算了）；`forget main` 之後也能用；bind 來源刪掉時 `EIO`、`gone (restart-init failed …`、daemon 照跑，補回來再寫就好；同名的一般 proc 在表上 `EINVAL ProcExists`；沒有 init 的 daemon `EINVAL NoInit`。

### 結束（`exit_grace`，使用者 11-26 定）

- **只收外面與 init 送的**（使用者 11-26 定，daemon職責「實作時定的」第 35 條）：signalfd 讀到的寄件人要是下面兩種之一才收尾，其他的不理、stderr 記一行（例 `ignored SIGTERM from pid 6 (s) in the daemon's PID namespace: stop signals are taken only from outside the namespace or from init`）：
  - `ssi_pid` 是 0（daemon 的 PID namespace 外面送的：起動那一層轉的、使用者直接 `kill` daemon 的 PID），而且 `ssi_code` 是 `SI_USER`（`kill()`）或 `SI_KERNEL`（終端機的 Ctrl-C、關終端機的 SIGHUP）。天空裡的 proc 用 `rt_sigqueueinfo` 能自己把寄件人填成 0，但那種的 `ssi_code` 一定是負的（`SI_QUEUE`），所以不收（`sigsrc` 組驗了）。
  - `ssi_pid` 是 init 在 daemon 這一層的 PID（或剛死掉、還沒處理完的那隻 init 的 PID），而且 `ssi_code` 是 `SI_USER` 或 `SI_TKILL`（`kill()`／`tgkill()`：寄件人 PID 由核心填）**【擬】**——別的 proc 用 `rt_sigqueueinfo` 填 init 的 PID，`ssi_code` 是負的，不收（`sigsrc` 組驗了）。
  - 不收的訊號完全不影響 daemon（不算進寬限、不重設什麼）。一般訊號同號的還沒讀走時再送會被核心併掉，所以連送很多也只記幾行。
  - 這擋的是「天空裡的 proc 停掉整台 daemon」。uid 0 的 proc 殺 init 與兄弟這一半擋不住，見下面「已知限制：uid 0 的 proc」。
- 收到（收下的）SIGTERM、SIGINT、SIGHUP（三個一樣）：先**只對 init** 送 SIGTERM（不送給它的行程組、不送給其他 proc），最多等 `exit_grace` 秒；init 先結束就馬上不等；時間到或 init 結束了，照舊 `kill(-1, SIGKILL)` 收掉其餘全部。退出碼照舊 0。
- 等的時候：init 結束了**不重起**（`on_init_exit` 是 `restart` 也一樣，`status` 的 `init_last_exit` 照記）；主循環照跑，`ctl` 照用（init 可以在這段用 `kill`、`forget` 收別的 proc；`start` 也還收，最後一樣被 SIGKILL）；用 monotonic 時鐘算期限。
- 等的時候再收到結束訊號：**不管，照樣等到期限【擬】**（在終端機按 Ctrl-C 時 daemon 與起動那一層同一個行程組，daemon 會收到兩次 SIGINT：自己一次、起動那一層轉一次；第二次要是算「馬上收」，寬限就沒用了）。要馬上收就 `kill -9` daemon。
- `exit_grace` 0（預設）：對 init 送 SIGTERM 後馬上全部 SIGKILL，等於以前的做法。
- 沒有 init 可等（設定沒有 init、到重起上限而 `stay`、或 init 剛好不在）：直接全部 SIGKILL，退出碼 0。
- daemon 是因為 init 已經死了才結束的（`on_init_exit exit`、到重起上限而 `exit`）：沒有 init 可等，直接 SIGKILL 其餘的，退出碼見下面「退出碼」。
- stderr 記：`got SIGTERM: sent SIGTERM to init …, waiting up to N s`，結束時 `exiting (got SIGTERM; init … within the exit grace)` 或 `… init was still running after exit_grace N s`。

### 起動那一層死了（`on_parent_death`，使用者 11-26 定）

- `exit`（預設，照以前）：daemon 設 parent-death signal（SIGKILL；現在在等起動那一層的 pipe 之前就設，中間死了也不漏），起動那一層被 `kill -9` 時 daemon 跟著走，PID namespace 的 1 號走了 Linux 收掉整片；cgroup scope 空了由 systemd 收。
- `stay`：不設 parent-death signal。起動那一層被 `kill -9` 時 daemon 與底下的 proc 照跑（daemon 被外面那層的 init 或 subreaper 收養），目錄照樣走 `/proc/<daemon PID>/cwd`，`ctl` 照用。要停就直接對 daemon 的 PID（export 那行裡的數字）送 SIGTERM（照上面「結束」、有寬限），daemon 的退出碼沒人收。
  - **cgroup 的收尾**：平常起動那一層在 daemon 結束後清 cgroup（刪漏的 `p-*`、關 controller、搬回 scope、刪 `daemon/`）。`stay` 而起動那一層已經死了，這段沒人做：daemon 結束前照舊自己刪它開的 `p-*`；剩下的 `daemon/` 與開著的 controller 留著，**scope 裡的行程走光時 systemd 把整個 scope（連同 `daemon/`）收掉、unit 也消失**（`--collect`；`pdeath` 組驗了）。沒有 cgroup（`off`）就沒有這段。
  - scope 在起動那一層死了之後還在（裡面還有 daemon 與 proc），`systemctl --user list-units 'aos-daemon-*'` 看得到，直到 daemon 結束。
  - SIGHUP 照舊是結束訊號：daemon 跟起動那一層同一個行程組（沒有 `setsid`），終端機關掉時一樣會收到。

### 退出碼（`exit_code`，使用者 11-26 定）

| 情形 | `exit_code init`（預設） | `exit_code own` |
|---|---|---|
| 收到 SIGTERM／SIGINT／SIGHUP（有寬限、沒有 init 也一樣） | 0 | 0 |
| init 結束了而 `on_init_exit exit` | init 的退出碼（被訊號殺是 128＋訊號） | **3【擬】**（固定；init 自己的碼只在 `status` 的 `init_last_exit` 與 stderr） |
| 到重起上限而 `on_restart_limit exit` | 1 | 1 |
| 起不來（含 init 設定用了保留的位置、uid 不是 0、壞的 `daemon_path`） | 2 | 2 |

0／1／2 的意思不變；3 只在 `own` 時出現。`exit_code init` 時 init 自己用 0～2 退出，daemon 也是 0～2，分不出是誰——要分就用 `own`。stderr 記 `exiting (init code 4, on_init_exit exit, exit_code own), code 3`。

## 資訊與工具的目錄

外面是 `/proc/<daemon PID>/cwd/`；init 的天空裡是它設定的 `daemon_path`（預設 `/aos/`，見下面「init」；設定選 `"daemon_access": "ptrace"` 時是 `/proc/1/cwd/`，daemon 在自己的 PID namespace 是 1 號）。其他 proc 碰不到（擋住它們的是各自的 Landlock domain，不是帳號規則，見下面「為什麼普通 proc 進不去 daemon 的目錄」）；沒有 init 時只有外面碰得到。

| 路徑 | 內容 |
|---|---|
| `status` | daemon 的資訊：`pid_ns`（1）、`pid_host`、`started_at`、`config`（daemon 設定檔的絕對路徑，只用參數起是 `-`）、`init`（init 的名字；沒有 init 是 `-`）、`init_state`（`alive`、`dead`、`starting`、`none (no init in the daemon config)`、`gone (restart limit reached: …; on_restart_limit stay)`、`gone (restart-init failed: …)`）、`on_init_exit`、`restart_limit`、`on_restart_limit`（`exit`／`stay`）、`exit_code`（`init`／`own`）、`exit_grace`（`N s`）、`on_parent_death`（`exit`／`stay`）、`init_restarts`、`init_deaths_in_window`、`init_last_exit`、`landlock_abi`、`cgroup`（外面的路徑或 `off (原因)`）、`subuid`、`init_access`（`mount <daemon_path>`、`ptrace /proc/1/cwd`，沒有 init 是 `-`）、`procs`，加上 ctl 回饋四行 `aos_ctl_cmd`／`state`／`error`／`count` |
| `ctl` | 工具：一次寫一行，見下 |
| `__meta/__interfaces/` | aoslua 的介面宣告（靜態、唯讀），見下面「介面宣告」：`aos/ctl/`（夾：`kind`、`path`、`commands`）、`aos/jsonpath`（空檔） |
| `procs/<名>/` | 一隻 proc 的資訊（真的夾：`start` 成功時建，`forget`、init 重起時連同底下整個拿掉；`ls procs/` 列出來的就是表上還在的名字），每個一個檔：`name`、`pid`（`ns: N` 是 daemon 那一層、也就是天空裡 `/proc` 看到的；`host: N` 是起 aos-daemon 的那一層）、`state`（`alive`／`dead`）、`exit`（`-`、`code N`、`signal N SIGNAME`）、`started_at`、`ended_at`（UTC）、`ns`（天空表，一行一個掛載的文字）、`ns.json`（同一張表的 JSON，見下）、`ns_check`（`ok` 或對不上的地方）、`uid`（`ns: N`、`host: N`）、`locks`（上了哪些鎖，一行一種）、`config`（設定檔路徑）、`__meta/__interfaces/aos/proc`（介面宣告，空檔）；有 cgroup 時還有 `cgroup` → 那隻的 cgroup 夾（`cpu.max`、`memory.max`、`pids.max`、`cgroup.freeze`、`cgroup.kill` 直接寫就是開關；相對連結 `../../../cgroup/p-…`，外面、init 的 `daemon_path` 底下都通） |

`ns` 是 Plan 9 的意思（這隻 proc 的天空表），跟 Linux 的 `/proc/<PID>/ns/`（namespace 連結的資料夾）不是同一個東西；使用者 11-26 定名。

工具（`ctl`）：

| 指令 | 做什麼 |
|---|---|
| `start CONFIG_PATH` | 照設定檔起一隻。路徑是起 daemon 那一層看到的絕對路徑【擬】 |
| `kill NAME SIGNAL` | 送訊號（`TERM`、`SIGTERM`、`15` 都認）。沒有「好好停」：要好好收，由 init 先送 TERM、等多久它定、再送 KILL |
| `mount NAME [-w] SRC DST` | 把外面的 SRC 掛進一隻跑著的 proc 的天空 DST（預設唯讀）；DST 不在而根是唯讀時，暫時把根改成可寫、建好掛載點再改回。init（mount 模式）天空裡 daemon 放的兩個地方（`daemon_path` 與 `dirname(daemon_path)/cgroup`，預設 `/aos`、`/cgroup`）與底下不收（`EINVAL`、`PathReserved <那個地方> …`）；照 init 設定的位置算，`/aos` 不是 `daemon_path` 時就不保留 |
| `umount NAME DST` | 從它的天空卸掉 DST；init 的那兩個地方同上不收 |
| `forget NAME` | 把死掉的從表上拿掉、`procs/<名>/` 連同底下整個拿掉（還活著就拒）；它的 cgroup 夾裡還有它留下的行程時也拒（`EIO`、`CgroupNotEmpty`，說明裡提示 `forget -k`；先寫 `cgroup.kill` 或用 `forget -k`） |
| `restart-init` | init 不在時照 daemon 設定的 init 起一隻真正的 init，見下面「`restart-init`」（使用者 11-26 定） |
| `forget -k NAME` | 跟 `forget` 一樣，但它的 cgroup 夾裡還有行程時，daemon 先寫 `cgroup.kill`、等到夾空了（最多 **5 秒【擬】**，monotonic）再照 `forget` 拿掉；逾時是 `EIO`、`aos_ctl_error` 寫 `Timeout … still has processes 5 s after writing cgroup.kill`，`cgroup.kill` 寫不進去是 `EIO`、`CgroupKillFailed`。那隻本身還活著照舊拒（`EINVAL`、`ProcAlive`：`forget` 是給死掉的，`-k` 只清它留下的孩子）。沒有 cgroup（`cgroup off`）時跟 `forget` 一樣（沒東西可清，留下的孩子照跑，daemon 結束時一起收）。使用者 11-26 定 |

**寫入等做完才回**（使用者 11-26 定；用 aos-procfs 的「做完才回」ctl，`Ctl::reply_when_done()`）：`start` 等那隻 exec 成功才回（寫入回來時 `procs/<名>/` 已經在、`state` 是 `alive`），`mount`／`umount` 等掛好、卸好，`kill` 等訊號送出（不等它死），`forget` 等從表上拿掉（寫入回來時 `procs/<名>` 已經走不到；`-k` 也等清完）。

- 寫錯的（不認得的字、參數不對、名字不在、`kill` 死掉的、`forget` 活著的、路徑不是絕對路徑）：寫入當場失敗 `EINVAL`，`aos_ctl_state: rejected`（不變）。
- 收下之後做的時候才失敗的（設定檔讀不到、json 不對、`locks.seccomp` 的名單檔讀不到或寫錯、init 以外的設定寫了 `daemon_access` 或 `daemon_path`、`net` 不對、同名的已經在、exec 失敗、組天空失敗、cgroup 上限寫不進去、掛不上、卸不掉）：寫入失敗 **`EIO`【擬】**（殼裡是 `write error: Input/output error`）。寫入帶不了字，原因照舊在 `status` 的 `aos_ctl_error`（`aos_ctl_state: failed`），daemon 也寫到 stderr。
- 寫入一回來，`status` 的 `aos_ctl_*` 已經是這一道的結果，不用再等。
- 等的時候按 Ctrl-C（或 `kill` 寫的那支）：寫的人當場拿到 `EINTR` 放開，指令照做，結果只在 `aos_ctl_*`。daemon 等的時候結束了：寫的人拿到連線斷掉的錯（`ECONNABORTED`／`ENOTCONN` 之類，沒進測試）。
- 一道還在做時（例 `start` 在組天空），別人寫 `ctl` 照舊當場 `EBUSY`；讀 `status` 不受影響。
- 最久等多久：`start` 的組天空、exec 各有 10 秒逾時，叫主執行緒做事有 60 秒逾時（逾時＝`EIO`＋`Timeout …`／`Internal …`）；之外沒有別的逾時。
- `stat` 看到 `ctl` 的大小是 1073741824：aos-procfs「做完才回」的 ctl 都這樣報（讓先開好檔的第二個人當場拿到 `EBUSY`，見 aos-procfs 的 README）。

daemon 不做的：自動重起（init 以外）、判卡住、准不准、kernel 登記表（判斷都歸 init）。

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
  "net": "none",
  "stdout": "/home/me/out/worker.log"
}
```

init 的設定（`init`／`--init`）多收兩個鍵，見下面「init」；其他 proc 的設定寫了任一個，`start` 就失敗（`EIO`、`ConfigBad`）：

- **`daemon_access`【擬】**：`"mount"`（不寫＝這個）或 `"ptrace"`。
- **`daemon_path`**（使用者 11-26 定）：mount 模式時 daemon 的目錄在 init 天空裡的位置，不寫＝`/aos`。要是絕對、乾淨（沒有 `.`、`..`、空段、尾巴的 `/`）、不是 `/`，而且 `dirname(daemon_path)/cgroup` 不能等於它（例 `/cgroup`、`/x/cgroup` 都拒）；錯了 daemon 起不來（退出碼 2）。跟 `"daemon_access": "ptrace"` 一起寫：**拒（退出碼 2）【擬】**（ptrace 模式走 `/proc/1/cwd`，用不到這個位置；悄悄不理反而讓人以為掛上了）。

- `name`：字母、數字、`_ - .`，1～64 字，不以 `.` 開頭。同名的還在表上（活的或死了沒 forget）就拒。
- `argv[0]`：天空裡的絕對路徑。
- `env`：不給就是 `PATH=/usr/local/bin:/usr/bin:/bin`、`HOME=/`。一律加上 `AOS_NAME=<名>`。`AOS_DAEMON` 只給 init（mount 模式是它的 `daemon_path`、預設 `/aos`，ptrace 模式 `/proc/1/cwd`）；沒有 init 時誰都沒有；其他 proc 讀不到 daemon 的目錄，所以不給，設定裡寫了也拿掉【擬】。
- `ns`：根一定是一塊新的空 tmpfs（組好後改唯讀），每條一個 JSON 物件（**使用者 11-26 定**；不再收字串，字串當設定錯拒），照順序做：`{"type": "bind", "src": SRC, "dst": DST}`（預設唯讀，加 `"rw": true` 才可寫；`rw` 可不寫、只有 bind 收、要是布林；SRC 是外面的路徑）、`{"type": "tmpfs", "dst": DST}`（mode 1777）、`{"type": "proc", "dst": DST}`、`{"type": "dev", "dst": DST}`（tmpfs 加 null、zero、full、random、urandom 與 fd、stdin、stdout、stderr 四個 symlink，組好後唯讀）、`{"type": "symlink", "target": TARGET, "dst": DST}`、`{"type": "overlay", "lower": [TOP, …, BOTTOM], "dst": DST}`（使用者 11-26 定，見下面「合併目錄」C：起動時疊好、唯讀、起動後不能加層；`lower` 是外面的絕對路徑，**至少兩個【擬】**（Linux 的唯讀 overlay 沒有 upper 時要兩層）、**第一個在最上面【擬】**（跟 overlayfs 的 `lowerdir` 同序）；不收 `rw`、`src`）。不認得的鍵、缺的鍵、型別不對、不認得的 `type` 都拒（`ConfigBad`，說明哪一條哪裡錯；`start` 是 `EIO`、`--init` 的檔是退出碼 2）。天空裡的 symlink 只在天空裡解（`openat2` 的 `RESOLVE_IN_ROOT`），寫成絕對路徑也不會碰到外面。
- `uid`：0＝天空裡的 0 號（外面的使用者本人）；N＞0＝subuid 範圍的第 N 個（外面是 subuid 起點＋N−1），gid 同號。
- `locks.cgroup`：起動前寫進那隻 cgroup 夾的檔與值（不收 `cgroup.*`）。沒有 cgroup 時給了就拒。`locks.landlock` 只能是 `true`（不能關）：init 以外的 proc 寫不寫都進自己的 Landlock domain；**init 寫了 `true` 才進**（不寫＝不進，照以前；使用者 11-26 定，見下面「init」）。`locks.seccomp`（使用者 11-26 定）：不寫＝內建的擋單、`"off"`＝不上、絕對路徑＝自己的名單檔，見下面「seccomp」。
- `net`（使用者 11-26 定）：`"none"`（**預設**）＝自己一個新的 network namespace，裡面只有 lo、而且已經打開（`127.0.0.1`、`::1` 能用，連不到外面，也連不到外面那層的 `127.0.0.1`）；`"host"`＝跟 daemon 同一個 network namespace，也就是外面的網路（以前的做法）。init 也一樣（預設 `none`）。別的值、不是字串都拒（`ConfigBad`）。**預設改了**：要網路的 proc 現在要寫 `"net": "host"`。見下面「網路」。
- `stdout`、`stderr`：外面的路徑（附加寫）；不給就是 `/dev/null`（**使用者 11-26 定**；不再跟 daemon 的 stderr，init 也一樣；只給一條，另一條也是 `/dev/null`）。stdin 一律 `/dev/null`。
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
overlay /home/me/top:/home/me/bottom /tools ro
```

overlay 那行的來源是 `lower` 用 `:` 接起來（只給人看；路徑裡本來有 `:` 時分不清，以 `ns.json` 的陣列為準）**【擬】**。

表是在 proc 組好天空、exec 之前從它的 `mountinfo` 量出來的（跑的時候掛、卸之後重量一次），每行對回設定標上來源，所以跟 mountinfo 一行對一行。`locked`＝設定沒寫、是 bind 來源底下外面那層掛的、被迫一起帶進來的（公司 WSL 的 `/usr` 底下有三個）。量的跟設定對不上（少了、多了、唯讀可寫不同）就寫在 `ns_check`。路徑裡的空白、tab、換行、反斜線照 mountinfo 寫成 `\040` 這種八進位。symlink 不是掛載，不在表上。

同一張表另有 JSON 版 `procs/<名>/ns.json`（使用者 11-26 定：設定檔的 `ns` 每條一個 JSON 物件；資訊有 `ns`（一行一行的文字）與 `ns.json`（同一張表的 JSON）共存）。兩個檔是同一次量的、掛／卸之後一起換，永遠是同一張表；`ns_check` 還是文字。格式：`[` 單獨一行、每個物件一行（除了最後一個，行尾有逗號）、`]` 單獨一行、結尾有換行；鍵跟設定的一條一樣（`type`、`src`、`dst`、`rw`；overlay 是 `lower` 陣列、沒有 `src`），`rw` 一定有，`locked: true` 只有 locked 的才有，文字行上是 `-` 的 `src` 不寫；路徑是一般 JSON 字串（不寫 `\040`，mountinfo 的八進位跳脫會解開）。

**每筆多 `by` 與 `at`**（使用者 11-26 定，daemon職責「實作時定的」第 30 條；文字的 `ns` 不加）：

| `by` | 意思 |
|---|---|
| `start` | 起動時照設定的 `ns` 放的（根的 tmpfs、`dev` 底下的裝置檔也算） |
| `mount` | 跑的時候 `ctl` 的 `mount` 掛的 |
| `daemon` | daemon 自己加的、設定裡沒有：init 的 daemon 目錄（`aos`）與 cgroup 夾（`cgroup`） |
| `locked` | 設定沒寫、bind 來源底下外面那層掛的、被迫一起帶進來的（同時有 `locked: true`） |

- `at`：放上天空的時間，UTC，寫法同 `started_at`（例 `2026-11-26T07:54:56.964Z`）。起動時放的都是「天空組好、exec 前量表」那一刻**【擬】**（同一隻的 `start`、`daemon` 各筆一樣）；`ctl mount` 的是掛好那一刻；`locked` 的跟帶它進來的那條 bind 一樣。之後掛／卸重量表，其他筆的 `by`、`at` 不變（`nsby` 組驗了）。
- 分不出是誰寫的 `ctl`（外面寫的人 PID 看到 0），所以只有 `mount`，不分 init 或外面的使用者（能寫的本來也只有這兩個）。
- 量到、但對不上設定的掛載（文字行種類是 `unknown`、`ns_check` 寫 `unexpected mount`）**沒有 `by`、`at`【擬】**：`by` 只有上面四種值，不另造一種；照理不會出現（proc 自己沒有 caps 動不了天空）。

例：

```
[
{"type": "tmpfs", "dst": "/", "rw": false, "by": "start", "at": "2026-11-26T07:54:56.964Z"},
{"type": "bind", "src": "/usr", "dst": "/usr", "rw": false, "by": "start", "at": "2026-11-26T07:54:56.964Z"},
{"type": "bind", "src": "/usr/lib/wsl/lib", "dst": "/usr/lib/wsl/lib", "rw": false, "locked": true, "by": "locked", "at": "2026-11-26T07:54:56.964Z"},
{"type": "proc", "dst": "/proc", "rw": true, "by": "start", "at": "2026-11-26T07:54:56.964Z"},
{"type": "overlay", "lower": ["/home/me/top", "/home/me/bottom"], "dst": "/tools", "rw": false, "by": "start", "at": "2026-11-26T07:54:56.964Z"},
{"type": "bind", "src": "/home/me/live", "dst": "/live", "rw": false, "by": "mount", "at": "2026-11-26T07:54:57.015Z"}
]
```

init 的 daemon 目錄與 cgroup 夾兩條在 `ns.json` 也一樣有，`by` 是 `daemon`，位置照它的 `daemon_path`（預設 `{"type": "aos", "dst": "/aos", "rw": true, "by": "daemon", …}`、`{"type": "cgroup", "src": "…", "dst": "/cgroup", "rw": true, "by": "daemon", …}`；`daemon_path` `/run/aos` 時是 `/run/aos` 與 `/run/cgroup`）。

## 做法

### 起動（不用 root）

1. 起動那一層用 `clone(CLONE_NEWUSER | CLONE_NEWPID | CLONE_NEWNS)` 生出 daemon；daemon 先停在一根 pipe 上。
2. 起動那一層自己叫 `newuidmap <PID> 0 <uid> 1 1 <subuid 起點> <數量>`、`newgidmap` 同樣（不靠 `unshare` 的參數：util-linux 2.39 只認最後一個 `--map-users`）；沒有 subuid 就直接寫 `uid_map`、`setgroups deny`、`gid_map` 一段。寫好了把 daemon 在外面的 PID 等幾個數字從 pipe 送過去。
3. 起動那一層留著：把 SIGTERM／SIGINT／SIGHUP 轉給 daemon，等它結束、清 cgroup、用它的退出碼結束。`on_parent_death exit`（預設）時 daemon 設了 parent-death signal（SIGKILL），起動那一層被 `kill -9` 時 daemon 跟著走；`stay` 不設（見上面「起動那一層死了」）。
4. daemon 是 1 號：SIGCHLD、SIGTERM、SIGINT、SIGHUP 擋下來由 signalfd 收（1 號沒裝處理的訊號會被丟掉；擋著的訊號外面那層也送得進來）；收到後三個先看寄件人（只收外面與 init 送的），收下的就照上面「結束」做（先給 init `exit_grace` 秒）。結束前自己 `kill(-1, SIGKILL)`、收完屍、刪掉開過的 cgroup 夾；被 `kill -9` 時 Linux 照樣收掉整片（PID namespace 的 1 號走了）。

### 小世界

1. 還在原本那一層（自己 mount namespace 裡的那份）時，先握住：根的 O_PATH fd、外面的 procfs、cgroup 夾，再掛上自己 PID namespace 的 procfs、握住它與這個 mount namespace 本身（`/proc/self/ns/mnt`）。
2. 再 `unshare(CLONE_NEWNS)` 開小世界：一塊 64k 的 tmpfs，裡面只有 `aos/`（aos-procfs 的 FUSE 掛載，`fusermount3` 在 user namespace 裡可以用）與 `cgroup/`（交給 daemon 的 cgroup 夾的 bind）；改成唯讀後 `pivot_root` 進去、舊的根整片卸掉、站進 `/aos`。
3. 之後 daemon 碰外面只經握住的 fd：讀設定檔用 `openat2(根, 路徑, RESOLVE_IN_ROOT)`；組天空、跑的時候掛時，子行程先 `setns` 回原本那一層再拿來源（`open_tree(OPEN_TREE_CLONE)` 只認呼叫者自己 mount namespace 裡的掛載，原本那一層要一直活著，所以握的是 namespace 而不只是根的 fd）。
4. 沒設 non-dumpable：`/proc/<PID>/root` 從外面看只有 `aos`、`cgroup` 兩個夾（測試驗了），`/proc/<PID>/cwd` 照樣能用。

### 起一隻 proc

只有主執行緒 fork 與收屍；工具檔的做事的線把要 fork 的事交給主執行緒做、等它回話。子行程：

0. 只有 init（mount 模式）：還在小世界時把小世界的 `/aos`（有 cgroup 時加 `/cgroup`）`open_tree(OPEN_TREE_CLONE)` 成還沒掛上的掛載（見下面「init」）。
1. 進原本那一層；讀外面的 procfs 的 `self` 拿到自己在外面的 PID；開 stdin／stdout／stderr。
2. 每個 bind 的來源先 `open_tree(OPEN_TREE_CLONE)`；被拒（EINVAL：來源底下有鎖住的子掛載）就連子掛載一起（`AT_RECURSIVE`）。overlay 在這裡用 `fsopen`／`fsconfig`／`fsmount` 照外面的路徑疊成還沒掛上的掛載（見上面「合併目錄」C）。
3. `unshare(CLONE_NEWNS)`；`net none` 時再 `unshare(CLONE_NEWNET)`、用 `ioctl(SIOCSIFFLAGS)` 打開 lo（見下面「網路」）。在自己這份的 `/tmp` 掛一塊新 tmpfs 當根（來源都拿好了，蓋住外面的 `/tmp` 不影響），照設定一條一條做；bind 用 `mount_setattr` 設 nosuid、nodev、唯讀再 `move_mount`；init 再把第 0 步拿的兩個掛到 `daemon_path` 與 `dirname(daemon_path)/cgroup`（可寫，中間缺的夾在根的 tmpfs 裡建）。根改唯讀，`pivot_root` 進去、舊的根卸掉。
4. 進自己的 cgroup（`p-<名>-<流水號>`，上限 daemon 先寫好了）。
5. 告訴 daemon「組好了」，daemon 趁它停著讀 mountinfo 做天空表，再叫它走。
6. 上鎖：清附加群組；securebits（noroot、no_setuid_fixup、keep_caps_locked、no_cap_ambient_raise，全部鎖住）；清空 bounding set；設 uid/gid；caps 清成 0（ptrace 模式的 init 留 cap_sys_ptrace）；no_new_privs；進一個自己的 Landlock domain（init 只有設定寫了 `locks.landlock: true` 才進）；chdir、接好 0／1／2；**最後上 seccomp**（`locks.seccomp` 不是 `off` 的話；過濾器 fork 之前就組好）。exec。哪一步失敗，原因經 pipe 回 daemon，`start` 記 `failed`、不留在表上。

Landlock 的 domain 只管一種檔案系統的權限（建 block 裝置，本來就做不到），沒有別的規則：要的是「自己一個 domain」帶來的隔開——不能讀 daemon、init 與旁邊 proc 的 `/proc/<PID>/root`、`cwd`、`environ`（domain 裡的行程不能 ptrace、也就不能看 domain 外的行程）。ABI 6 以上再加擋訊號與 abstract unix socket；公司 WSL（6.6，ABI 3）擋不住訊號，測試照實記下（同帳號的 proc 送得出訊號；daemon 自己不理天空裡 init 以外送的停止訊號，見上面「結束」）。

#### 為什麼普通 proc 進不去 daemon 的目錄（11-26 實測改寫，daemon職責「實作時定的」第 36 條）

**擋住它的是它自己的 Landlock domain，不是帳號規則。** 以前這裡（與 daemon職責第 2、12 條）寫「其他 proc 也沒有權限／用 subuid 的帳號，光這條就進不去」，那只對 `/proc/1/cwd` 成立（daemon 有全部 caps，caps 0 的 proc 照「自己的 caps 要包含對方的」就讀不到）。經 init 走就不一樣：

- mount 模式的 init 是 uid 0、caps 0；預設的 proc（設定沒寫 `uid`）也是 uid 0、caps 0。照帳號與 caps 的規則，同 uid、對方 caps 不比自己多，就讀得到對方的 `/proc/<PID>/root`、`cwd`；FUSE 只認「跟 daemon 同 uid」，`ctl` 是 0200、主人是 0 號，它也過。所以單看帳號規則，uid 0 的普通 proc 走 `/proc/<init 在那一層的 PID>/root/aos/ctl` 是寫得進去的。
- 實際寫不進去，是因為普通 proc 一定在自己的 Landlock domain 裡，domain 裡的行程不能看 domain 外的行程（Landlock 的 ptrace 限制）。`ipath` 組實測（ABI 3）：uid 0 的普通 proc 讀 `/proc/<init>/root/aos/status`、`/proc/<init>/cwd/aos/status`、`/proc/<init>/root/aos/procs`、`/proc/<init>/root`、`/proc/<init>/cwd`，寫 `/proc/<init>/root/aos/ctl`、`/proc/<init>/cwd/aos/ctl`，**全部 `EACCES`**、沒有東西被起起來；init 設 `locks.landlock: true`（init 也在自己的 domain、但普通 proc 的 domain 不在它底下）時一樣全部 `EACCES`。
- 所以這是整套裡最要緊的一道，而且只有一道：哪天為了別的事（例如疊 daemon，見「要使用者定的」第 6 條）讓某隻 uid 0 的 proc 不進 Landlock，它就寫得到 init 的 `ctl`（等於拿到使用者整個帳號）。用 subuid 的 proc（`"uid": N`）才多一道帳號規則（FUSE 與 `ctl` 的權限位擋掉）。
- 沒有 Landlock 的 Linux 上 init 以外的 proc 一律起不來（daemon職責第 20 條），理由也是這個。

#### 已知限制：uid 0 的 proc（11-26 先接受，daemon職責「實作時定的」第 35 條）

- 預設的 proc 是 uid 0（外面的使用者本人）。Landlock ABI 6 以前擋不住訊號，所以它**殺得掉 init 與其他 uid 0 的 proc**（`kill(-1, SIGKILL)` 一次就全部）；init 在 `restart_window` 秒內死超過 `restart_limit` 次（預設 60 秒內第 6 次），照 `on_restart_limit` 預設 daemon 以 1 結束、整片收掉。
- 停掉 daemon 本身這一條擋住了：daemon 不理天空裡 init 以外送的停止訊號（見上面「結束」）。
- `locks` 檔照實寫：uid 0 的普通 proc 在 ABI 小於 6 時多一行 `signals: can signal init and other uid-0 procs (Landlock ABI 3 has no signal scoping; the daemon ignores stop signals from it)`。只寫在普通 proc 上**【擬】**（init 本來就是管它們的那一方；subuid 的 proc 是別的帳號，送不到 uid 0 的）。
- 擋法（都沒做，要使用者挑）：設定寫 `"uid": N` 用 subuid；每隻 proc 自己一個 PID namespace；等 Linux 6.12 以上（ABI 6，程式會自動加上擋訊號）。

### init

- daemon 掛好目錄、印出 export 那行後第一件事起它（daemon 設定檔沒有 `init` 就不起，見上面「沒有 init」）。預設它是唯一不進 Landlock 的 proc（設定寫 `locks.landlock: true` 就進，見下面）。
- **怎麼碰 daemon 的目錄**（使用者 11-26 定，[daemon職責-1126](../../../proto8/thinking/2026-11/26/daemon職責-1126.md)「實作時定的」第 2 條；設定檔的 `daemon_access`）：

| `daemon_access` | 目錄在哪 | 權限 | `AOS_DAEMON` |
|---|---|---|---|
| `mount`（預設） | 自己天空裡的 **`daemon_path`**（預設 `/aos`）；有 cgroup 時 cgroup 夾在 **`dirname(daemon_path)/cgroup`**（預設 `/cgroup`） | **一個 cap 都沒有**（bounding set 也清空），跟其他 proc 一樣 | `daemon_path` |
| `ptrace`（舊的做法，「保留 A」） | `/proc/1/cwd`（`daemon_path` 不收） | 留 CAP_SYS_PTRACE 一個 | `/proc/1/cwd` |

- **mount 模式怎麼做**：daemon 的目錄是小世界裡的一個 FUSE 掛載，只在 daemon 的 mount namespace 裡。起 init 的子行程 fork 出來時還在小世界，**先 `open_tree(OPEN_TREE_CLONE)` 把小世界的 `/aos`（與 `/cgroup`）複製成還沒掛上的掛載**，再進原本那一層拿天空的來源；組天空時（根改唯讀之前）用 `mount_setattr`（nosuid、nodev、可寫）＋`move_mount` 掛到天空的 `daemon_path`、`dirname(daemon_path)/cgroup`。還沒掛上的掛載可以掛進別的 mount namespace（天空的 bind 本來就這樣做），所以不用任何新權限。FUSE 只放跟 daemon 同 uid 的行程進來、`ctl` 是 0200，init 用天空裡的 0 號就讀寫得到，跟 caps 無關。實測（`access` 組）：caps 全 0、讀得到 `/aos/status`、寫 `/aos/ctl` 的 `start` 等到 `alive` 才回、失敗是 `EIO`、原因在 `/aos/status`、`kill`／`forget` 後 `/aos/procs/<名>` 走不到；讀 `/proc/1/cwd` 是 `EACCES`。
- **`daemon_path`**（使用者 11-26 定）：目錄放哪由 init 的設定定，cgroup 夾一定放在它旁邊的 `cgroup`（`daemon_path` `/run/aos` → cgroup 夾在 `/run/cgroup`）。**為什麼 cgroup 夾跟著放旁邊**：`procs/<名>/cgroup` 是相對連結 `../../../cgroup/p-…`。小世界裡 `/aos` 旁邊是 `/cgroup`，init 的天空擺成一樣（目錄旁邊就是 `cgroup`），連結在兩邊都通（外面走 `/proc/<PID>/cwd` 時解在 daemon 的根裡，照舊通；`dpath` 組驗了 `/run/aos/procs/w/cgroup/pids.max` 讀得到）。所以 mount 模式的 init，天空設定不能自己用這兩個地方與底下：daemon 起不來（退出碼 2，說明原因）；`ctl` 的 `mount`／`umount` 也不准動這兩個地方（照設定的位置算，`daemon_path` 不是 `/aos` 時 `/aos` 就是一般的地方）。天空設定在這兩個地方的**上面**放東西可以（例 `{"type": "tmpfs", "dst": "/run"}` 再 `daemon_path` `/run/aos`）；放的是唯讀的 bind（例 `daemon_path` `/usr/aos` 而 `/usr` 是唯讀 bind）就建不了掛載點，init 起不來，照「起不來也算死一次」走重起規則。
- **天空表**多兩行：`aos - <daemon_path> rw` 與 `cgroup <cgroup 夾外面的路徑> <dirname(daemon_path)/cgroup> rw`（`ns_check` 照樣對）；`locks` 檔寫 `capabilities: none (bounding set empty)` 與 `daemon directory: <daemon_path> in its ns (daemon_access mount), cgroup directory at …`；`status` 的 `init_access` 是 `mount <daemon_path>`。
- **ptrace 模式**：Linux 讀別的行程的 `/proc/<PID>/cwd` 時，除了同 uid，還要「自己的 caps 包含對方的」；daemon 在 user namespace 裡有全部 caps，init 清成 0 就讀不到（實測：0 caps EACCES，只留 cap_sys_ptrace 就讀得到）。代價是能 ptrace 同一個 user namespace 裡的行程（含 daemon）。這個模式天空裡沒有 daemon 的目錄。
- 兩種模式、沒有 Landlock 的 init 都讀得到其他 proc 的 `/proc/<PID>/root`（mount 模式也行：對方 caps 是 0、同 uid；Landlock 只擋 domain 裡的往外，不擋外面的往裡）。
- **`locks.landlock: true`**（使用者 11-26 定；預設不進，照以前）：init 也進一個自己的 Landlock domain，規則跟其他 proc 一樣（只管建 block 裝置）。`locks` 檔第一行寫 `landlock: own domain (ABI N); …; init asked for it (locks.landlock true)`。實測（`ilandlock` 組，ABI 3）：caps 照舊 0、讀得到 `$AOS_DAEMON/status`、經 `/aos/ctl` `start`、`kill`、`forget` 照用、讀得到 `procs/w/cgroup/pids.max`、寫 `cgroup.freeze` 凍得住（Landlock 只擋建 block 裝置，不擋讀寫這些檔）；**代價**：其他 proc 的 domain 不在它底下，init 讀不到它們的 `/proc/<PID>/root`（`EACCES`，測試照實記下）。沒有 Landlock 的 Linux 上 init 寫了 `true`：daemon 起不來（退出碼 2）。uid 0 的要求照舊。
- init 要用天空裡的 0 號（uid 0）：`ctl` 是 0200、FUSE 也只放跟 daemon 同 uid 的行程進來。init 設定的 uid 不是 0，daemon 起不來（退出碼 2，說明原因；兩種 `daemon_access` 都一樣；重起 init 時不再讀設定檔，所以只在起動時檢查）——使用者 11-26 定。
- 它死了：`restart`（預設）就重起；`--restart-window` 秒內死超過 `--restart-limit` 次（預設 60 秒內超過 5 次，即第 6 次）就不再起，照 `on_restart_limit`：`exit`（預設）daemon 以 1 結束、整片收掉；`stay` daemon 留著（見上面「到重起上限」）。起不來（exec 失敗之類）也算死一次。重起時舊的那筆從表上拿掉（`procs/<名>/` 整個拿掉）、用同一個名字起新的（新的 `procs/<名>/`）；`status` 的 `init_restarts`、`init_last_exit` 記著。`exit`：daemon 直接結束，退出碼照 `exit_code`（見上面「退出碼」）。

### seccomp（`locks.seccomp`，使用者 11-26 定）

每隻 proc（**init 也一樣**）在 exec 前最後一步上一層 seccomp 過濾器：在 no_new_privs、Landlock 之後，所以 daemon 自己的預備（組天空、`unshare`、`mount`、`pivot_root`、Landlock）不受影響；daemon 本身與起動那一層不上。過濾器是手寫的 classic BPF（`linux/filter.h`、`linux/seccomp.h`、`linux/audit.h`，沒有用 libseccomp，這台也沒裝）。

| `locks.seccomp` | 意思 | `locks` 檔那一行 |
|---|---|---|
| 不寫（**預設**）或 `"builtin"`【擬】 | 內建的擋單（下表），擋的回 `EPERM` | `seccomp: builtin (44 syscalls denied with EPERM, personality limited to safe values; other arch and x32 calls kill the process)` |
| `"off"` | 不上 | `seccomp: off` |
| `"/abs/list.json"` | 自己的名單檔（路徑照起 daemon 那一層看，跟 `start` 的路徑一樣經握住的根讀） | `seccomp: /abs/list.json (default allow, N denied with EPERM; …)` 或 `(default deny, N allowed, the rest EPERM; …)` |

**不擋建 namespace 與 mount 那一族**（使用者 11-26 定：要能在 proc 裡再起 daemon，一層疊一層）：`unshare`、`clone`、`clone3`（含 `CLONE_NEW*` 的 user、mount、pid、net、uts、ipc、cgroup）、`setns`、`mount`、`umount2`、`pivot_root`、`open_tree`、`move_mount`、`mount_setattr`、`fsopen`、`fsconfig`、`fsmount`、`fspick` 都放；外面那層的掛載本來就鎖住，user namespace 裡的 mount 只動得到自己那份。也不擋 `seccomp`（疊上去的 daemon 要再上一層）、`landlock_*`、`prctl`、`capset`。

內建的擋單（x86_64 號碼；44 個一律 `EPERM`，`personality` 看參數）：

| 系統呼叫 | 為什麼擋 |
|---|---|
| `init_module`、`finit_module`、`delete_module`、`create_module`、`get_kernel_syms`、`query_module` | 載入／卸下核心模組（後三個是早就拿掉的舊呼叫，順手擋） |
| `kexec_load`、`kexec_file_load` | 換核心 |
| `reboot` | 重開機、關機 |
| `swapon`、`swapoff` | 動整台的 swap |
| `settimeofday`、`clock_settime`、`clock_adjtime`、`adjtimex` | 改整台的時鐘（時間不分 namespace；x86_64 沒有 `stime`） |
| `acct` | 整台的行程記帳 |
| `quotactl`、`quotactl_fd` | 檔案系統配額 |
| `bpf` | 載 eBPF 程式（核心攻擊面大） |
| `perf_event_open` | 效能計數器，可看到別的行程與核心的資訊 |
| `userfaultfd` | 常被拿來把核心的競爭條件拉長（攻擊手法） |
| `keyctl`、`add_key`、`request_key` | 核心的 keyring 不分 namespace |
| `ptrace` | 追蹤、改別的行程 |
| `process_vm_readv`、`process_vm_writev` | 直接讀寫別的行程的記憶體 |
| `kcmp` | 比對兩個行程的核心物件（跟 ptrace 同一類的窺看）【擬：擋】 |
| `pidfd_getfd` | 從別的行程拿 fd（要 ptrace 權限的那種）【擬：一起擋】 |
| `open_by_handle_at`、`name_to_handle_at` | 用 file handle 開檔，可繞過路徑（Docker 早年逃出容器的手法） |
| `lookup_dcookie` | 舊的 profiling 介面，洩漏路徑 |
| `iopl`、`ioperm` | 直接碰 I/O port |
| `syslog` | 讀核心的訊息緩衝（dmesg） |
| `uselib`、`vhangup`、`nfsservctl`、`_sysctl` | 舊的或用不到的（`uselib` 是 a.out 時代的、`vhangup` 掛斷終端機、後兩個核心早拿掉了） |
| `move_pages`、`migrate_pages` | 搬別的行程的記憶體頁（NUMA）【擬：擋；只動自己的 `mbind`、`set_mempolicy`、`get_mempolicy` 放】 |
| `io_uring_setup`、`io_uring_enter`、`io_uring_register` | io_uring：核心漏洞多，Docker 現在預設也擋【擬：擋】 |
| `personality` | 只放 `0`、`0x8`（PER_LINUX32）、`0x20000`（UNAME26）、`0x20008`、`0xffffffff`（只查不改），跟 Docker 一樣；別的值（例 `ADDR_NO_RANDOMIZE`）`EPERM` |

- **架構檢查**：`seccomp_data.arch` 不是 `AUDIT_ARCH_X86_64`（例 `int 0x80` 進來的 i386 呼叫），或號碼帶 x32 的位元（`0x40000000`）：**整個行程殺掉**（`SECCOMP_RET_KILL_PROCESS`，那隻記 `signal 31 SIGSYS`）**【擬】**——不然 i386／x32 的入口能繞過整張表；32 位元或 x32 的程式在 proc 裡本來就不支援，殺掉比「每個呼叫都 EPERM、半死不活」清楚。名單檔也一樣有這段。
- **擋的回 `EPERM`**（使用者 11-26 定），不殺。
- **名單檔**（格式【擬】）：`{"default": "allow", "deny": ["ptrace", "bpf"]}`（列的回 `EPERM`、其餘放）或 `{"default": "deny", "allow": [...]}`（列的放、其餘 `EPERM`；兩種都做了）。名字是 x86_64 的系統呼叫名（`src/seccomp.cpp` 裡的表，照 `asm/unistd_64.h` 抄的 373 個）；重複的算一個。不認得的名字、`default` 不是 `allow`／`deny`、清單的鍵跟 `default` 對不上（`allow` 配 `allow`）、多的鍵、項目不是字串、不是 JSON、讀不到：`start` 寫入失敗 `EIO`、`ConfigBad locks.seccomp list …`、不留 `procs/` 的夾；init 的就 daemon 起不來（退出碼 2）。名單檔**不疊在內建的擋單上**【擬】：寫了名單就只照名單（要內建的那些就自己列進去）。`default deny` 的名單要放 `execve` 等 exec 要的呼叫，不然 `start` 是 `EIO`、`StartFailed exec …: Operation not permitted`。
- `locks.seccomp` 不是字串、不是 `"off"`／`"builtin"`／乾淨的絕對路徑：`ConfigBad`。
- init 的名單檔只在 daemon 起動時讀一次，重起 init 用同一份（跟 init 設定一樣）。
- init 照內建的擋單跑得好好的（整套測試的 init 都上了；它要的都沒擋）。
- 實測（`seccomp` 組）：init 與一般 proc 試 `ptrace`、`bpf`、`init_module`、`finit_module`、`kcmp`、`personality(ADDR_NO_RANDOMIZE)`、`keyctl`、`userfaultfd`、`io_uring_setup`、`name_to_handle_at`、`syslog`、`process_vm_readv`、`reboot`、`swapon`、`acct`、`clock_settime` 都是 `EPERM`；`off` 時 `kcmp`、`personality(ADDR_NO_RANDOMIZE)`、對自己的 `process_vm_readv` 照通（核心本來就放）；x32、i386 的 `getpid` 被殺（`SIGSYS`），`off` 時照通；`/proc/<PID>/status` 的 `Seccomp_filters` 比外面多 1（`off` 不多）；init（沒有 Landlock）裡 `unshare` 七種 namespace、`mount`、`umount2`、`setns` 都行。
- 只有 x86_64：別的架構編不過（`#error`）**【擬】**。

### 疊 daemon（proc 裡再起 daemon；11-26 量的）

使用者 11-26 要的：照預設的鎖（`net none`、內建 seccomp、Landlock、uid 0、沒有 caps、no_new_privs）起一隻 proc，裡面跑 `build/bin/aos-daemon`（binary 綁進天空），帶自己的 daemon.json 與 init。**量的結果：照預設的鎖起不來，有兩道是根本的，這版沒有放寬任何預設**（`nest` 組把這些界線寫成測試）：

1. **uid 0 對照不了自己**：裡面那份要開新的 user namespace，對照表得把外面那層的 uid 0（proc 自己）放進去。Linux 5.12 起（`verify_root_map`），對照表裡有「上一層的 0 號」時，寫的人要在上一層有 **CAP_SETFCAP**（或建 namespace 的人當時有）；proc 的 caps 全清了，所以 `uid_map` 寫入 `EPERM`。實測：uid 0 的 proc 跑裡面那份，它以 2 結束、`could not write the uid/gid maps of the daemon`；`unshare -U` 本身行（seccomp 不擋），只是寫 `0 0 1` 被拒。用 subuid 的 uid（例 `"uid": 1`）就過得了這關（對照 `0 1 1` 不含上一層的 0 號，實測 OK）。`newuidmap` 也幫不上：no_new_privs 讓它的 setuid 不作用。
2. **Landlock 不准動掛載**：只要 domain 管了任何一種檔案系統的權限（這裡管「建 block 裝置」），Linux 就不准 `mount`、`umount`、`pivot_root`、`move_mount`（Landlock 文件的已知限制）；init 以外的 proc 一定進 Landlock。實測：`"uid": 1` 的 proc 跑裡面那份，對照表寫得進去，下一步 `make mounts private: Operation not permitted`、以 2 結束；`seccomp` 關掉也一樣（是 Landlock 不是 seccomp）；拆開試：uid 1 的 proc `unshare` 後 `uid_map` OK、`mount` 一塊 tmpfs `EPERM`。這台 6.6（ABI 3）沒辦法做「不管檔案系統的 Landlock domain」（建 ruleset 至少要一種權限，ABI 6 以上才有只管 signal／abstract socket 的 scoped；新核心那樣的 domain 擋不擋 mount 沒實測）。
3. **init 那條路也不通**：init 預設不進 Landlock，但它一定要 uid 0（使用者 11-26 定），撞上第 1 道。實測：init 跑裡面那份，以 2 結束（`could not write the uid/gid maps`），`--on-init-exit exit` 時外面那份也以 2 結束。
4. 另外一道小的：天空的 `dev` 只有 null、zero、full、random、urandom，**沒有 `/dev/fuse`**；`bind` 一律 `nodev`，自己綁 `/dev/fuse` 也開不了。裡面那份的資訊目錄是 FUSE，要 `/dev/fuse`。

**拿掉這幾道之後量的**（在 scratch 用改過的一份 build 量，沒進程式）：proc 不進 Landlock、`"uid": 1`、天空的 `/dev` 多 `fuse` 時，裡面那份 **起得來**：印 export 那行、init 讀得到自己的 `$AOS_DAEMON/status`、經 `/aos/ctl` `start` 一隻 proc（`done`；那隻的 `locks` 照樣有 Landlock、內建 seccomp，`Seccomp_filters` 疊成兩層，Landlock、seccomp 疊上去都沒擋到裡面那份）、外面那份收 SIGTERM 時整片走光（用 exe 的 dev＋inode 找，沒有留下）。要的參數：`--subuid off`（no_new_privs 下 `newuidmap` 沒用；uid 1 在 `/etc/passwd` 對到別的名字，`auto` 本來也找不到範圍）、`--cgroup off`，或用下面的 `--cgroup PATH`。

**cgroup**：裡面那份可以用外面給那隻 proc 的 cgroup 夾，量過能用，但要三件事：
- 裡面那份要能「用這個已經交給我的夾」：**做了**（`--cgroup PATH`／daemon.json `"cgroup": "/path"`，見下面「cgroup」；`cgpath` 組在最外層用 systemd-run 給的 scope 測）。
- 外面那份把 `p-<名>-<流水號>` 夾**交給那隻的 uid**（chown 夾與 `cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads`；因為第 1 道，它是 uid 1，不是夾的主人 0 號），並把夾綁進它的天空（可寫）。實測這樣裡面那份的 `status` 寫 `cgroup: /cg`、開得了 cpu／memory／pids、建 `p-iinit-1`、`p-w-2`。**沒做**：疊 daemon 本身照預設起不來，先不加。
- 外面那份收尾時要**由深到淺刪**它那隻夾底下裡面那份建的夾（那些夾的主人是 subuid，起動那一層沒有權限刪，要 daemon 自己刪）；不然 systemd 收掉 unit 後 cgroup 夾留著（實測留下過，已清掉）。**沒做**，理由同上。

要放寬哪一道是使用者的事，見下面「要使用者定的」第 6 條。

### 合併目錄（使用者 11-26 定，daemon職責「實作時定的」第 31 條）

想讓一隻 proc 在一個地方看到好幾個來源的東西（例如好幾個工具夾），有三種做法，daemon 都撐得住：

- **A. 不合併，各放各的資料夾，用 `PATH` 串起來**（不用 daemon 做任何事）：每個來源各一條 bind，再在設定的 `env` 把它們接進 `PATH`。例：

  ```json
  "ns": [
    {"type": "bind", "src": "/home/me/tools-a/bin", "dst": "/tools/a"},
    {"type": "bind", "src": "/home/me/tools-b/bin", "dst": "/tools/b"},
    …
  ],
  "env": {"PATH": "/tools/a:/tools/b:/usr/bin:/bin"}
  ```

  名字撞了照 `PATH` 的順序先找到的算。天空表一條一行，看得出每個東西從哪來。
- **B. 起動時留一個空的 `tmpfs`，跑的時候用 `ctl` 的 `mount` 把單一個檔一個一個掛進去**：設定放 `{"type": "tmpfs", "dst": "/merged"}`，之後 `mount NAME /外面/某個檔 /merged/tool-a`、`mount NAME /別處/另一個檔 /merged/tool-b`。掛載點（空檔）由 daemon 在那塊可寫的 tmpfs 裡建，所以夾一定要是可寫的 tmpfs（唯讀的根底下 daemon 會暫時把根改可寫建掛載點，但放進 tmpfs 比較乾淨）。每個檔在天空表各一行、`ns.json` 的 `by` 是 `mount`。`umount` 掉之後**留下一個空的掛載點檔**（實測；daemon 不刪）。`merge` 組驗了（init 的 `/merged` 掛兩個不同夾來的檔，列得出兩個、內容對、`ns_check` ok）。
- **C. overlay**：設定的 `ns` 寫 `{"type": "overlay", "lower": ["/外面/上層", "/外面/下層"], "dst": "/tools"}`。起動時疊好（同名的取上面那層），**唯讀**、**起動後不能再加層**（沒有改層的指令；`ctl mount` 只能在上面再蓋一條 bind）。做法：子行程還在原本那一層時用 `fsopen("overlay")`、`fsconfig` 設 `lowerdir`（路徑裡的 `\`、`:` 加 `\`）與 `ro`、`fsmount` 成一個還沒掛上的掛載，再跟 bind 一樣 `move_mount` 進天空（user namespace 裡可以掛 overlay，Linux 5.11 起）。lower 不在或疊不起來：`start` 寫入 `EIO`、`StartFailed create overlay …`。天空表一行 `overlay 上層:下層 /tools ro`，`ns.json` 寫 `"lower": [...]`。`overlay` 組驗了（兩層都看得到、同名取上層、寫新檔與改舊檔都 `EROFS`、mountinfo 是 `overlay` 而且 `ro`、六種寫錯 `ConfigBad`、lower 不在 `StartFailed`）。
- D. 用 FUSE 現算的合併目錄不在 daemon：歸某個 kernel 提供（使用者：「就當以後有人想提供這個介面」）。

### 介面宣告（aoslua，使用者 11-26 定，daemon職責「實作時定的」第 34 條、[kernel-1126](../../../proto8/thinking/2026-11/26/kernel-1126.md) 第 2 條）

daemon 的目錄照 aoslua「存取得到＝有這個介面」擺靜態宣告（aos-procfs 的唯讀節點：夾 0555、檔 0444，寫、建、刪都 `EACCES`）：

| 路徑（以 daemon 的目錄起算） | 內容 |
|---|---|
| `__meta/__interfaces/aos/ctl/` | 夾：這個目錄收指令（共同介面 `aos/ctl`） |
| `__meta/__interfaces/aos/ctl/kind` | `file`（寫一行進那個檔、做完才回、失敗在寫入那一下回錯誤） |
| `__meta/__interfaces/aos/ctl/path` | `ctl`（以宣告所在的目錄起算：外面是 `/proc/<PID>/cwd/ctl`、init 是 `/aos/ctl`） |
| `__meta/__interfaces/aos/ctl/commands` | `start kill mount umount forget restart-init`（實際收的指令，空白分開；程式裡跟 ctl 用同一張表寫） |
| `__meta/__interfaces/aos/jsonpath` | 空檔：底下可以用 `#` 加 JSON Pointer 存取 json 檔（例 `procs/w/ns.json#/0/src`；解析由讀的人做，daemon 只宣告） |
| `procs/<名>/__meta/__interfaces/aos/proc` | 空檔：每隻 proc 的夾符合 `aos/proc` |

- 三個小檔的內容後面有一個換行**【擬】**（跟其他資訊檔一樣；`$(cat …)` 會去掉）。
- 宣告是靜態的：不隨狀態變（例 init 活著時 `restart-init` 會被拒，`commands` 照樣列著——列的是「收這個字」，不是「現在一定成功」）。
- `aos/daemon` 不做（kernel-1126 第 2 條改成共同介面 `aos/ctl`）。
- init 從自己天空的 `daemon_path` 讀得到：`iface` 組實測 init 讀 `/aos/__meta/__interfaces/aos/ctl/kind`（`file`）、`path`、`commands`、`aos/jsonpath`、`/aos/procs/w/__meta/__interfaces/aos/proc` 都行，寫 `kind` 是 `EACCES`。`commands` 列的每個字寫進 `ctl` 都不是 `CommandUnknown`（`iface` 組驗了）。

### bind 來源卡住時（使用者 11-26 定，daemon職責「實作時定的」第 37 條）

- 起 proc 的子行程（拿 bind 來源、組天空、exec）與跑的時候掛、卸的幫手，都可能卡在一個不回應的檔案系統上（卡住的 FUSE、WSL 的 `/mnt/c`、NFS）。請求一旦送到 FUSE 伺服器手上，Linux 要等它回來才讓那個行程死，**SIGKILL 也沒用**（行程停在 `D`）。
- 以前：主執行緒 10 秒逾時後送 SIGKILL，再用會一直等的 `waitpid` 等它——主執行緒就跟著卡死（不收屍、不處理 `ctl`、不理 SIGTERM）。
- 現在：逾時（或其他失敗）送 SIGKILL 之後**最多等 0.5 秒【擬】**（WNOHANG 輪詢，monotonic；平常死得掉的當場收掉），還沒走就**直接回失敗**，stderr 記 `start sb: pid 6 did not exit 0.5 s after SIGKILL (stuck in the kernel?); not waiting for it, the main loop reaps it when it goes`。那個 PID 留給主循環平常的收屍：`reap_all` 收到不認得的 PID 就略過（`stuck` 組驗了：放開後兩隻卡住的都被收掉、沒有殭屍）。幫手正常寫完結束時也一樣最多等 1 秒、不無限等。
- 它的 cgroup 夾：先照樣刪；子行程還在夾裡（已經進了 cgroup 才卡住，例如卡在 exec）刪不掉時記一筆（`cgroup p-sx-3 not removed yet (its process has not gone); will retry`），主循環每圈再試（有等著的夾時 poll 每秒醒一次），刪掉時記 `removed cgroup p-sx-3 (left over from a failed start)`；daemon 結束時也會再刪一次。卡在進 cgroup 之前（拿 bind 來源時）的夾是空的，當場就刪掉。
- 寫 `ctl` 的人：`start` 拿到 `EIO`、`Timeout building the ns took more than 10 s`（卡在拿來源、組天空）或 `Timeout exec took more than 10 s`（卡在 exec）；`mount` 拿到 `EIO`、`MountFailed Timeout mount took more than 10 s`。這 10 秒裡主執行緒照舊在等（其他 `start` 排著、SIGTERM 晚一點處理），之後馬上回來做事。
- 卡住的行程放開（FUSE 伺服器回答或死掉）之前一直在：daemon 收到 SIGTERM 時照舊 `kill(-1, SIGKILL)`、最多等 5 秒就結束，但 **Linux 要等 PID namespace 裡卡住的行程都走了，daemon 這個行程才真的消失**（起動那一層會一直等到那時）。這版沒處理（要處理得去中止那個 FUSE 連線，daemon 不知道是哪個）。
- 實測（`stuck` 組；測試自己起一支故意不回答的 FUSE：`toys.py stuckfuse`，用 `fusermount3` 掛、回答 `INIT`、`GETATTR`，名字以 `stuck` 開頭的 `LOOKUP` 讀了不回）：bind 來源在它上面的 `start` 10.5 秒回 `EIO Timeout building the ns`、FUSE 收到那個 lookup、子行程在 SIGKILL 之後仍是 `D`、daemon 當場讀得到 `status`、另一個 `start` 0.05 秒就 done、cgroup 夾當場刪掉；程式在 FUSE 上的 `start` 10.5 秒回 `EIO Timeout exec`、子行程 `D`、cgroup 夾留著等之後刪；`ctl mount` 來源在 FUSE 上 10.5 秒回 `EIO MountFailed Timeout`、幫手 `D`、`ctl` 照用；殺掉 FUSE 伺服器後三隻都走、被收掉（`/proc/<PID>` 不見）、留著的 cgroup 夾刪掉、daemon 收 SIGTERM 以 0 結束。
- 測試的 FUSE 伺服器要開 `FUSE_PARALLEL_DIROPS`：不然同一個夾的 lookup 一次一個，第二個卡在核心裡等第一個，FUSE 收不到。

### 網路（`net`，使用者 11-26 定）

- 每隻 proc（含 init）的設定 `net`：`"none"`（預設）或 `"host"`。`locks` 檔多一行：`net: none (own netns, loopback only)` 或 `net: host (the daemon's network namespace)`。
- `none` 怎麼做：子行程在 daemon 的 user namespace 裡（還有全部 caps 時）`unshare(CLONE_NEWNET)`，新的 network namespace 屬於這個 user namespace，所以用一個 `AF_INET` socket 的 `ioctl(SIOCGIFFLAGS／SIOCSIFFLAGS)` 把 lo 設成 UP（要 CAP_NET_ADMIN，之後才丟 caps）；lo 打開時核心自己加上 `127.0.0.1/8` 與 `::1`。不用外面的 `ip`。
- 實測（`net` 組）：`none` 的 proc 連外面那層 `127.0.0.1` 上聽著的 TCP port 是 `ECONNREFUSED`（它自己的 lo 上沒人聽）、自己的 `127.0.0.1` bind／connect／收發可以、`/proc/net/dev` 只有 `lo`、`/proc/<PID>/ns/net` 跟外面不同；`host` 的連得到外面那個 port、介面跟外面一樣、`ns/net` 跟外面同一個。init 預設也是 `none`；寫 `"host"` 就跟 daemon 同一個。
- daemon 自己一直在外面的 network namespace（它不開新的）；`ctl` 的 `mount`／`umount` 不碰網路。

### `procs/<名>/`：真的夾（使用者 11-26 定，「實作時定的」第 4 條）

- 表是「名字 → 那隻」。`start` 成功時建 `procs/<名>/` 與底下每個檔；`forget`（與 init 重起時的舊那筆）用 aos-procfs 的 `remove_tree` 連同底下整個拿掉。以前的 `slots/<i>/`＋symlink 拿掉了。
- 每個檔的內容由那隻自己的記錄產生（檔抓著那隻記錄的 `shared_ptr`）；夾拿掉時跟著放。
- 「表」與「目錄」一起改（一把只在放上表、拿掉時拿的鎖）：主執行緒的 `start`、init 重起，跟做事的線的 `forget` 不會交錯。回答的線不拿這把鎖，所以拿著它叫 `remove_tree`（要跟核心講話）不會卡住回答的線。
- `forget` 只拿它看過、確定死掉的那一筆：中間 init 剛好被重起成同名的新一隻，就不動新的那隻。
- 拿掉之後：寫入一回來，`procs/<名>` 就走不到（核心的快取也丟了）；同名馬上再起，看到的是新的；拿掉前已經開著的檔照舊讀得到開檔那刻的內容（`dirs` 組驗了）。

### cgroup

- `--cgroup auto`：先用 `systemctl --user show -p Version` 確認有 systemd --user，再 `systemd-run --user --scope --quiet --collect -p Delegate=yes --unit=aos-daemon-<PID> -- 自己 參數…` 重跑自己（PID 不變）。
- 在 scope 裡：起動那一層把自己搬進 `scope/daemon/`（cgroup v2 規定開了 controller 的夾不能直接放行程），再把 `cgroup.controllers` 列的都寫進 `cgroup.subtree_control`（這台有 cpu、memory、pids 等）。每隻 proc 一個 `scope/p-<名>-<流水號>/`。
- 收尾：daemon 結束前刪它開的 `p-*`；起動那一層再刪一次漏的、關掉 controller、搬回 scope、刪 `daemon/`，scope 由 systemd 收。起動那一層被 `kill -9` 時 systemd 也會整個收掉（測試驗了）；`on_parent_death stay` 時 scope 留到 daemon 結束、裡面空了才由 systemd 整個收（見上面「起動那一層死了」）。
- 沒有 systemd --user：`status` 寫 `cgroup: off (原因)`，設定給了 `locks.cgroup` 就拒，其餘照常。
- **`--cgroup PATH`／`"cgroup": "/path"`**（為了疊 daemon 加的【擬】）：用一個已經交給自己的 cgroup v2 夾（例：外面那層給的、systemd 的 `Delegate=yes`），不經 `systemd-run`、不看名字。路徑先 `realpath`（`status` 的 `cgroup` 寫解開的）；要有 `cgroup.procs`、`cgroup.subtree_control` 可寫；之後跟 scope 一樣：起動那一層搬進 `PATH/daemon/`、把 `cgroup.controllers` 列的都開給底下、每隻一個 `PATH/p-<名>-<流水號>/`、收尾刪掉。路徑不在、不是可管的 cgroup 夾、搬不進去：**起不來（退出碼 2）**（明講要用的夾用不了，不悄悄變 `off`）；相對路徑拒（退出碼 2）。`--cgroup auto`／`off` 蓋過檔裡的路徑，`--cgroup PATH` 蓋過檔裡的 `auto`／`off`。

## 測試

`make test`（公司 WSL：Linux 6.6.114.1-microsoft-standard-WSL2、Landlock ABI 3、cgroup v2、有 systemd --user、`/etc/subuid` 有範圍）：**559 PASS、0 FAIL**（11-26 審查三條與五樣：加 `sigsrc`、`ipath`、`stuck`、`nsby`、`overlay`、`merge`、`rinit`、`iface` 八組共＋115 條（14＋20＋17＋10＋15＋9＋13＋17），`basic`、`access`、`dirs` 的目錄清單多 `__meta`，`mount`、`dpath` 比 `ns.json` 時不看 `by`／`at`，在那之前 444；11-26 seccomp、疊 daemon、`--cgroup PATH`：加 `seccomp`、`nest`、`cgpath` 三組共＋71 條（47＋10＋14），`leftovers` 改用 exe 的 dev＋inode 也找天空裡的那份，在那之前 373；11-26 主 kernel 改名 init、五個選項、`net`：加 `rename`、`noinit`、`rlstay`、`dpath`、`ilandlock`、`exitcode`、`net` 七組共＋94 條，`dconf` 的「沒有 `kernel`」那條拿掉（沒有 `init` 現在是合法的），在那之前 280；11-26 加 daemon 設定檔、結束寬限、`on_parent_death`、`forget -k` 四組 `dconf`、`grace`、`pdeath`、`forgetk` 共＋91 條，在那之前 189；11-26 proc 的 stdout／stderr 沒設改 `/dev/null`、加 `stdio` 組＋10 條，在那之前 179；11-26 設定檔 `ns` 改物件、加 `ns.json` 與 `nsconf` 組共＋22 條；在那之前 157：init 改走 `/aos`、`procs/<名>/` 改成真的夾後 155；再加 init uid 不是 0 要拒的 2 條），約 80 秒（grace 組照實等寬限、stuck 組照實等三次 10 秒逾時），清 build 跑一次加連跑 3 次都一樣。等待一律用 monotonic 時鐘、等到條件成立（WSL2 的牆上時鐘每 32 秒左右往回跳 1.6 秒）。

| 組 | 驗什麼 |
|---|---|
| `basic` | 一般使用者起得來；export 那行；daemon 在自己的 PID namespace 是 1 號（NSpid）；uid 對照表；經 `/proc/<PID>/cwd` 讀 `status`；`/proc/<PID>/root` 只有小世界、看不到 `/etc`、`/usr`；目錄裡只有 `__meta/`、`ctl`、`procs/`、`status`（沒有 `slots/`）；init 讀得到 `$AOS_DAEMON/status`、`AOS_DAEMON` 是 `/aos`、caps 是 0；SIGTERM 後退出碼 0 |
| `procs` | start／kill／forget；`start` 的寫入回來時那隻已經在表上、`alive`；`pid` 兩層對得上 NSpid；forget 活的、kill 不在的、壞訊號、不認得的字、相對路徑都寫入失敗 `EINVAL`；同名、讀不到設定、關 Landlock、exec 失敗都是寫入失敗 `EIO`＋`failed`＋原因；退出碼 7、SIGTERM 記對；uid 1001 在外面是 subuid；init 自己寫 `/aos/ctl` 起一隻（寫入回來時已經 `alive`），起不來的它拿到 `EIO` |
| `nsconf` | 設定的 `ns` 物件寫法能起（`rw` 可不寫）；字串條目、不認得的鍵、缺 `dst`／`src`、`rw` 不是布林或用在非 bind、不認得的 `type`、`dst` 不是字串都是 `EIO`＋`ConfigBad` 且不留 `procs/` 的夾；`--init` 的檔寫字串條目退出碼 2 |
| `ns` | `ns.json` 是 JSON、版面（`[`、一行一物件、`]`）、條數與 `ns` 行數一樣、type／dst／rw／locked 對得上、`rw` 一定有、含空白的路徑是一般字串（文字檔仍是 `\040`）、掛／卸之後 `ns.json` 跟著換；天空表的行數、掛載點、唯讀可寫跟 mountinfo 一樣；每個 bind 的來源跟掛載點是同一個檔（dev＋inode）；WSL 的 `/usr` 子掛載記成 `locked`；唯讀的地方寫不進去、`-w` 的寫得進去而且落在外面的夾；根裡只有設定放的東西 |
| `landlock` | init 以外的 proc 讀不到 `/proc/1/cwd`、`/proc/1/root`、旁邊 proc 的 `/proc/<PID>/root` 與 `environ`，自己的 `/proc/self/root` 可以；能不能對 daemon 送訊號照 ABI 記（ABI 3：能）；init 讀得到旁邊 proc 的 `/proc/<PID>/root`；`locks` 檔；caps 0、no_new_privs |
| `cgroup` | `procs/<名>/cgroup` 可用、行程在裡面、`memory.max`／`pids.max` 照設定、`cgroup.freeze` 凍住再解凍、forget 刪掉夾、不認得的上限檔 `EIO`＋`failed`、daemon 結束後 scope 不見 |
| `mount` | 跑的時候掛進去、看得到、表多一行且仍跟 mountinfo 一樣；`-w`；卸掉後不見、表也拿掉；來源不在、卸沒掛的地方都是 `EIO`＋`failed`；相對路徑寫入失敗 `EINVAL` |
| `modes` | `--cgroup off --subuid off`：對照表只有一段、給 cgroup 上限或 uid 5 都 `EIO`＋`failed`、一般 proc 照起、`locks` 寫 groups kept |
| `restart` | 前兩次起來就死的 init 被重起兩次後活著；`--restart-limit 3` 起 4 次後 daemon 以 1 結束並說明原因；`--on-init-exit exit` 以 init 的 4 結束、不重起；`--restart-limit 0` 第一次死就結束 |
| `teardown` | `kill -9` daemon：底下 4 隻 1 秒內全不見、起動那一層以 137 結束；`kill -9` 起動那一層：daemon 與底下跟著走 |
| `access` | mount 模式（預設）：`status` 寫 `init_access: mount /aos`；init 的 CapInh／Prm／Eff／Bnd／Amb 全 0；`AOS_DAEMON=/aos`、讀得到 `/aos/status`、讀 `/proc/1/cwd` 是 `EACCES`；天空表有 `aos - /aos rw` 與 cgroup 那行、`ns_check` ok；mountinfo 裡 `/aos` 是 `fuse.aosproc`；`locks` 寫 caps none、目錄在 `/aos`；列 `/aos`；寫 `/aos/ctl` 的 `start` 回來時已經 `alive`、讀 `/aos/procs/w/state`；起不來的是 `EIO`、原因在 `/aos/status`；經 `/aos/procs/w/cgroup` 讀到 `pids.max`；`ctl` 卸 `/aos`、掛蓋 `/aos` 都 `EINVAL`（`PathReserved`）；`kill`、`forget` 後 `/aos/procs/w` 走不到。init 以外的：沒有 `/aos`、`/cgroup`，讀不到 `/proc/1/cwd`，沒有 `AOS_DAEMON`（有 `AOS_NAME`）；設定寫 `daemon_access` 是 `EIO`＋`ConfigBad`；外面的 `/proc/<PID>/cwd` 照通。ptrace 模式：`status` 寫 `ptrace /proc/1/cwd`、只留 cap_sys_ptrace、`AOS_DAEMON=/proc/1/cwd` 讀得到、沒有 `/aos`、經它寫 `start` 可以。init 天空自己用 `/aos`：daemon 以 2 結束並說明；init uid 5（mount、ptrace 兩種模式）：daemon 以 2 結束、說明要 uid 0 |
| `dirs` | `procs/x` 是夾不是 symlink、裡面是那幾個檔；`ls procs/`；先讓核心快取那條路、開著一個檔，`forget` 回來時 `procs/x` 與底下都走不到、`ls procs/` 只剩 main、開著的檔照讀；同名再起是新的那隻；10 次 start／forget 每次都建、拿；最後 `procs/` 與 `status` 的 `procs` 對 |
| `dconf` | 只用參數起照舊、`status` 的 `config` 是 `-`、`exit_grace`／`on_parent_death` 的預設；daemon.json 給 `init` 絕對路徑（`config` 是那個檔、`procs/main/config` 是 init 路徑、`cgroup auto` 經重跑照樣有 cgroup）；相對路徑從 daemon.json 的夾算（cwd 是 `/`）；daemon.json 本身給相對路徑（`config` 寫絕對、重跑也帶得過去）；內嵌的 init（`init` 是它的名字、`procs/<名>/config` 是 `<檔>#/init`、讀得到 `$AOS_DAEMON/status`）；每個鍵都讀（`status` 各行，含 `on_restart_limit`、`exit_code`）；參數蓋過檔（`--on-init-exit`、`--restart-limit`、`--on-restart-limit`、`--exit-code`、`--exit-grace`、`--on-parent-death`、`--cgroup auto` 蓋過、`restart_window`／`subuid` 留檔裡的）；`--init` 蓋過 `init`；不認得的鍵、型別不對、值不對、`init` 是數字、不是 JSON、最上層不是物件、init 檔不在、內嵌的缺 `argv`、檔讀不到、兩個位置參數、`--exit-grace` 壞值、`--on-parent-death` 壞值都是退出碼 2＋說明 |
| `grace` | `--exit-grace 5`：收 SIGTERM 會收尾的 init 收完（檔在）、daemon 以 0 結束、init 一結束就不等（< 3 秒）、其他 proc 被殺、沒重起；不理 SIGTERM 的 init＋`--exit-grace 2`：等的時候 init 與其他 proc 都還活著、約 2 秒後以 0 結束、全收掉、說明原因；寬限裡以 3 結束的 init 不重起、daemon 馬上以 0 結束；init 在寬限裡經 `ctl` `kill`＋`forget`；寬限裡外面的 `start` 與 init 的 `kill` 照用、第二個 SIGTERM 不會提早收、3 秒後以 0 結束；預設 0：不收尾、馬上結束；SIGINT 一樣有寬限；`on_init_exit exit`、到重起上限時不等 |
| `pdeath` | `--on-parent-death stay`：`status` 寫 `stay`；`kill -9` 起動那一層後 daemon 還在、`/proc/<PID>/cwd/status` 讀得到、proc 照跑、`ctl` 照用、scope 還在；對 daemon 送 SIGTERM 後 daemon 與 proc 都不見、scope 與 unit 由 systemd 收掉 |
| `forgetk` | 死掉的 proc 在 cgroup 裡留了孩子：`forget` 照舊 `EIO`＋`CgroupNotEmpty`（提示 `forget -k`）、夾還在、孩子還在；`forget -k` 回 done、`procs/<名>` 不見、孩子不見、cgroup 夾刪掉、記了 `cgroup.kill`；活的 `EINVAL`＋`ProcAlive`、不在的 `ProcUnknown`、用法錯 `ArgumentsBad`；cgroup 空的照樣 done；init 經 `/aos/ctl` 寫 `forget -k`；`--cgroup off`：`-k` 跟 `forget` 一樣、孩子照跑、daemon 結束時一起走 |
| `rename` | `--init` 起得來；`status` 有 `init`、`init_state alive`、`on_init_exit`、`on_restart_limit exit`、`exit_code init`、`init_restarts`、`init_deaths_in_window`、`init_last_exit`、`init_access`（預設值）且沒有一行名字帶 `kernel`；stderr 記 `started main (… , init)`；舊鍵 `kernel`、`on_kernel_exit`，舊參數 `--kernel`、`--on-kernel-exit`，`on_restart_limit`／`exit_code`／`--on-init-exit`／`--on-restart-limit`／`--exit-code` 壞值，只用參數沒 `--init`（說明提示不寫 `init` 的 daemon 設定檔）都是退出碼 2＋說明；`--help` 講 init、沒有 main kernel、`--kernel` |
| `noinit` | daemon.json 沒有 `init`（`exit_grace` 5）：起得來、`init: -`、`init_state none`、`init_access: -`、`procs/` 空、stderr 說沒有 init；外面 `start` 一隻：沒有 `AOS_DAEMON`（有 `AOS_NAME`）、沒有 `/aos`、讀不到 `/proc/1/cwd`；外面 `kill`、`forget`；SIGTERM 馬上（< 2 秒）以 0 結束、proc 不見、stderr 說 no init；同一份檔加 `--init` 就有 init |
| `rlstay` | `--restart-limit 1 --on-restart-limit stay`：`status` 寫 `stay`；`kill main KILL` 第一次重起、第二次之後 daemon 還在、`init_state` 寫 gone（restart limit reached、stay）、`init` 還是 main、`init_restarts` 1；死掉的 init 留在表上（`dead`、`signal 9 SIGKILL`）、沒再起、stderr 說 not restarting；另一隻 proc 照跑；外面 `start` 照用；`forget main` 可以；SIGTERM 馬上以 0 結束 |
| `dpath` | init `daemon_path` `/run/aos`（天空另放一塊 tmpfs 在 `/aos`）：`init_access: mount /run/aos`；`AOS_DAEMON=/run/aos` 讀得到 status；天空表 `aos - /run/aos rw`、`cgroup … /run/cgroup rw`、`ns_check` ok、`ns.json` 也有；`locks` 寫這兩個位置；`/aos` 是它自己的空 tmpfs；經 `/run/aos/ctl` 起一隻；`/run/aos/procs/w/cgroup/pids.max` 讀得到（相對連結解到 `/run/cgroup`）、`/run/cgroup` 裡有那隻的夾；`ctl` 卸 `/run/aos`、掛到 `/run/cgroup/x` 都 `EINVAL PathReserved <那個位置>`；掛蓋 `/aos` 可以了；非 init 設定寫 `daemon_path` 是 `EIO ConfigBad`；init 天空用了 `/run/aos` 退出碼 2；`daemon_path` 相對、`/`、尾巴 `/`、`..`、`/cgroup`、`/x/cgroup`、數字、跟 ptrace 一起都退出碼 2 |
| `ilandlock` | init `locks.landlock: true`：`locks` 寫 own domain、init asked for it；caps 0；讀得到 `$AOS_DAEMON/status`；經 `/aos/ctl` 起一隻、讀它的 `state`、讀 `cgroup/pids.max`、寫 `cgroup.freeze` 凍得住；實測讀不到那隻的 `/proc/<PID>/root`（`EACCES`）；`kill`、`forget` 照用 |
| `exitcode` | `--on-init-exit exit --exit-code own`：init 以 4 結束 → daemon 3、stderr 寫 exit_code own；init 被 SIGKILL → 3（不是 137）；`--exit-code init` → 4；`own` 時 `status` 寫 own、SIGTERM 照舊 0；`own` 時到重起上限照舊 1 |
| `net` | 外面在 `127.0.0.1` 開一個 TCP port：init 預設 `net none`（`locks`、`ns/net` 跟外面不同）；預設的 proc 連那個 port 失敗（`ECONNREFUSED`）、自己的 `127.0.0.1` 收發可以、`/proc/net/dev` 只有 `lo`、`locks` 寫 none、`ns/net` 跟外面不同；`"net": "host"` 連得到、自己的 lo 也行、介面跟外面一樣、`locks` 寫 host、`ns/net` 跟外面同一個；`net` 是 `"maybe"`、`5` 都 `EIO ConfigBad`；init `"net": "host"` 跟外面同一個 |
| `seccomp` | init（內建的擋單）試 16 個被擋的呼叫都 `EPERM`、`getpid`／`getppid`／`personality(0xffffffff)` 照通、`locks` 那行、`Seccomp: 2` 且過濾器比外面多 1、init 照樣讀 `$AOS_DAEMON/status` 與經 ctl 起一隻、daemon 自己沒多上；一般 proc 預設同上；`"builtin"` 跟不寫一樣；`off`：`kcmp`、`personality(ADDR_NO_RANDOMIZE)`、`process_vm_readv` 照通、`locks` 寫 off、沒多過濾器；x32、i386 的呼叫被 `SIGSYS` 殺、`off` 時照通；名單 `default allow`（重複算一個、不疊內建的）、`default deny`（全部名字減 `getppid`）、`default deny` 沒放 `execve` 是 `EIO`＋exec 失敗；名單寫錯七種、`seccomp` 值錯五種都是 `EIO`＋`ConfigBad`；init 名單有不認得的名字退出碼 2、init `off`、init 用自己的名單；init 裡 `unshare` 七種 namespace、`mount`、`umount2`、`setns` 都行（`uid_map` 寫 `0 0 1` 是核心拒的 `EPERM`） |
| `nest` | 疊 daemon 量到的界線（見「疊 daemon」）：uid 0 的 proc 跑裡面那份以 2 結束（對照表寫不進去）；uid 1 的以 2 結束（`make mounts private: Operation not permitted`）、seccomp 關掉也一樣；拆開試 uid 0／uid 1／uid 1＋seccomp off 的 `unshare`、`uid_map`、`mount`；SIGTERM 後沒有留下（exe 的 dev＋inode）；init 跑裡面那份以 2 結束、外面那份也以 2 結束 |
| `cgpath` | `systemd-run --user --scope -p Delegate=yes` 給一個 scope，`--cgroup <那個夾>`：`status` 的 `cgroup` 是它、daemon 在 `<夾>/daemon`、proc 的上限在 `<夾>/p-w-…`、結束後夾不見；`--cgroup` 給不在的、不是 cgroup 的、相對的路徑，daemon.json `"cgroup"` 給相對、數字、不在的路徑都退出碼 2＋說明 |
| `sigsrc` | 天空裡的 uid 0 proc 對 daemon（1 號）送 SIGTERM、SIGHUP、SIGINT：ABI 3 送得出去、daemon 不停、`status` 照讀、stderr 每個記一行 `ignored … from pid N (s)`；冒名（`rt_sigqueueinfo`、`SI_QUEUE`）寄件人填 0、填 init 的 PID 都不理；之後 `ctl` 照用；uid 0 的普通 proc 的 `locks` 有 `signals: can signal init and other uid-0 procs`（ABI < 6），init 與 subuid 的沒有；init 送 SIGTERM：daemon 收尾、以 0 結束、不算 ignored；外面經起動那一層送 SIGTERM、直接對 daemon 的 PID 送 SIGHUP：以 0 結束 |
| `ipath` | uid 0 的普通 proc 經 `/proc/<init 在那一層的 PID>/root`、`cwd` 讀 `aos/status`、`aos/procs`、`root`、`cwd`，寫 `aos/ctl`：全部 `EACCES`（測試名字帶著量到的錯誤）、沒有東西被起起來；init 設 `locks.landlock: true` 時再驗一次 |
| `stuck` | 故意不回答的 FUSE 先掛好再起 daemon：bind 來源在上面的 `start` 約 10 秒 `EIO Timeout building the ns`、子行程 SIGKILL 後仍 `D`、daemon 馬上能讀 `status`、另一個 `start` 馬上 done、表上沒有它、stderr 說沒等、cgroup 夾當場刪；程式在 FUSE 上的 `start` `EIO Timeout exec`、子行程 `D`、cgroup 夾留著等之後刪；`ctl mount` 來源在上面 `EIO MountFailed Timeout`、幫手 `D`、`ctl` 照用；FUSE 伺服器死掉後卡住的都被收掉（`/proc/<PID>` 不見）、cgroup 夾刪掉、SIGTERM 以 0 結束 |
| `nsby` | `ns.json` 每筆有 `by`、`at`；`at` 是 UTC 時間；設定的是 `start`、被迫帶進來的是 `locked`；init 的 `/aos`、`/cgroup` 是 `daemon`；`ctl mount` 的是 `mount`、`at` 另記；重量表後其他筆不變；文字 `ns` 沒有 by／at |
| `overlay` | `{"type": "overlay", "lower": [上, 下], "dst": "/ov"}`：兩層都看得到、同名取上層；新檔、舊檔都 `EROFS`；天空表 `overlay 上:下 /ov ro`；`ns.json` 有 `lower` 陣列、`rw` false、`by` start、沒有 `src`；`ns_check` ok；mountinfo 是 `overlay`、`ro`；一層、不是陣列、相對路徑、缺 `lower`、帶 `rw`、帶 `src` 都 `EIO ConfigBad`；lower 不在 `EIO StartFailed` |
| `merge` | 合併目錄 B：init 的空 tmpfs `/merged`，`ctl mount` 兩個不同夾來的單一個檔：都 done、列得出兩個、內容對、天空表各一行、`by` mount、`ns_check` ok；卸一個後留下空的掛載點檔 |
| `rinit` | `restart-init`：init 活著 `EINVAL InitAlive`、帶參數 `ArgumentsBad`；`gone` 後回 done、新 init alive、兩個次數 0、是真的 init（`AOS_DAEMON=/aos`、讀得到 status、天空有 `/aos`）、stderr 有記；時間窗重算（再死一次被自動重起）；`forget main` 之後也行；bind 來源不見時 `EIO`、`gone (restart-init failed …)`、daemon 照跑，補回再寫 done；同名一般 proc `EINVAL ProcExists`；沒有 init 的 daemon `EINVAL NoInit` |
| `iface` | `__meta/__interfaces/aos` 有 `ctl/`、`jsonpath`；`ctl/` 有 `kind`（file）、`path`（ctl，指得到）、`commands`（六個，含 restart-init）；每個字 ctl 都認得、沒列的是 `CommandUnknown`；`jsonpath` 空檔；夾 0555、檔 0444，寫、建、刪都 `EACCES`；每隻 `procs/<名>/__meta/__interfaces/aos/proc` 空檔；init 從 `/aos` 讀得到這些、寫 `kind` 失敗 |
| `leftovers`（最後一定跑） | 沒有留下行程（daemon、起動那一層、天空裡的 toys.py；exe 跟 `build/bin/aos-daemon` 是同一個檔（dev＋inode）的也算，天空裡的那份 readlink 看到的是天空裡的路徑）、systemd unit、`aos-daemon-*` cgroup、掛載 |

## 【擬】（不清楚時選保守的，之後可改）

- 設定檔的格式（json 鍵、天空每條一個 JSON 物件的寫法、`uid` 的意思、`locks` 的樣子）。
- `start` 的路徑是起 daemon 那一層看到的絕對路徑（init 住在自己的天空裡，未必知道那些路徑）。
- 天空表一行的寫法（`種類 來源 位置 ro|rw [locked]`），從 mountinfo 量、對回設定。
- init 天空裡放 daemon 目錄的位置預設叫 `/aos`；有 cgroup 時 cgroup 夾放旁邊的 `cgroup`（跟小世界一樣的擺法，`procs/<名>/cgroup` 的相對連結才通）。這兩個地方 init 的天空設定不能用（用了 daemon 起不來），`ctl` 的 `mount`／`umount` 也不准動。**（使用者 11-26 定：照這樣；11-26 再定位置可由 init 設定的 `daemon_path` 改，cgroup 夾跟著放 `dirname(daemon_path)/cgroup`）**
- 選舊做法的設定鍵叫 `daemon_access`（`mount`／`ptrace`，預設 `mount`），放在 init 的設定檔裡；其他 proc 的設定寫了就拒。**（使用者 11-26 定：照這樣）**
- `status` 多一行 `init_access`**（使用者 11-26 定：留著；原名 `main_kernel_access`，11-26 改名）**；天空表的兩行寫成 `aos - <daemon_path> rw`、`cgroup <外面的路徑> <dirname(daemon_path)/cgroup> rw`。
- 小世界裡除了 `aos/` 還有 `cgroup/`（cgroup 夾的 bind）；`procs/<名>/cgroup` 是相對 symlink `../../../cgroup/p-…`，外面走 `/proc/<PID>/cwd/…`、init 走 `<daemon_path>/…` 都通。
- 工具檔叫 `ctl`，回饋在 `status` 的 `aos_ctl_*` 四行。
- 做的時候失敗的寫入回 `EIO`（原因只在 `aos_ctl_error`）；`kill` 的「做完」是訊號送出、不等它死；`start` 的「做完」是 exec 成功。
- init 重起時舊的那筆直接拿掉、同名起新的；它死的情形記在 `status`。
- init 起不來也算死一次，照重起規則走。
- ~~daemon 結束時不另給寬限~~、~~起動那一層被殺時 daemon 跟著走~~：**使用者 11-26 定**做成參數、預設照以前（`exit_grace` 0、`on_parent_death exit`）。參數名 `--exit-grace`、`--on-parent-death` 是 eca-aos 擬的（daemon職責「實作時定的」第 17 條）；daemon 設定檔的鍵名照第 19 條。
- 寬限裡再收到結束訊號不管、照樣等到期限（見「結束」）。
- `status` 多 `exit_grace`（`N s`）、`on_parent_death` 兩行（`config` 一行是使用者定的）。
- 內嵌的 init 設定，`procs/<名>/config` 寫 `<daemon.json>#/init`。
- daemon 設定檔沒有 `init` 但給了 `--init`：有 init。兩邊都沒有：有 daemon 設定檔就是沒有 init 的 daemon（使用者 11-26 定），只用參數就拒（見下）。
- `forget -k` 最多等 5 秒；不帶 `-k` 的 `forget` 碰到 cgroup 裡還有行程照舊是 `EIO`（做下去才知道，跟以前一樣），不是 `EINVAL`。
- `--cgroup auto` 重跑自己時只把 daemon 設定檔與 `--init` 的路徑換成絕對路徑，其他參數照原樣。
- proc 的 stdout／stderr 沒設就是 `/dev/null`（**使用者 11-26 定**；含 init；daemon 自己的 stdout 只印 export 那行、stderr 只有 daemon 自己的訊息）；stdin 是 `/dev/null`；每隻 `setsid`。
- `AOS_DAEMON` 只給 init（`daemon_path` 或 `/proc/1/cwd`）；其他 proc 不給（讀不到 daemon 的目錄），設定裡寫了也拿掉。`AOS_NAME` 每隻都給。**（使用者 11-26 定：照這樣）**
- 名字跟 proto8 的 `AOS_DAEMON`（daemon 的資料夾）同一個意思；使用者 11-26 定（原本叫 `AOS_ROOT`）。舊名 `AOS_ROOT` 現在沒有特殊意思：設定的 `env` 寫了就當一般環境變數照傳。
- `forget` 時那隻的 cgroup 夾裡還有它留下的行程就拒；`forget -k` 先清（**使用者 11-26 定**）。
- Landlock 的規則只管「建 block 裝置」一種，用意只在進一個自己的 domain；沒有 Landlock 的核心上 init 以外的 proc 一律起不來。
- subuid 最多用 65535 個（uid 0～65535）。
- 退出碼的分法（0／init 的碼／1／2）；`exit_code own` 時 init 結束的那種是 3。
- **以下是 11-26 init 改名、五個選項、`net` 這一輪 eca-aos 自己挑的**（使用者定的是：改名 init、舊名不收、`init` 可不寫、`on_restart_limit`、`daemon_path`、init 的 `locks.landlock`、`exit_code`、`net` 與它的預設 `none`）：
- 只用參數（沒有 daemon 設定檔）又沒給 `--init`：照舊拒、退出碼 2，說明裡提示寫一份不含 `init` 的 daemon 設定檔（例如 `{}`）；理由：只用參數多半是忘了 `--init`。
- 沒有 init 時 `status` 寫 `init: -`、`init_state: none (no init in the daemon config)`、`init_access: -`；其餘設定行照印（用不到）。
- `status` 多 `init_state`（`alive`／`dead`／`starting`／`none (…)`／`gone (restart limit reached: …; on_restart_limit stay)`）、`on_restart_limit`、`exit_code` 三行。
- `on_restart_limit stay` 時死掉的 init 留在表上（`dead`），要拿掉就 `forget`；要再起就 `restart-init`（使用者 11-26 加的）。
- `exit_code own` 的固定碼是 3（0／1／2 已有意思，3 是下一個）。
- `daemon_path` 跟 `"daemon_access": "ptrace"` 一起寫就拒（退出碼 2），不是悄悄不理。
- `daemon_path` 要「乾淨」（尾巴的 `/`、`.`、`..`、空段都拒），不幫忙改寫；在唯讀 bind 底下的 `daemon_path` 不先擋，起的時候建不了掛載點就照「起不來也算死一次」。
- init 寫了 `locks.landlock: true` 而 Linux 沒有 Landlock：daemon 起不來（退出碼 2）。
- `locks` 檔的寫法：`net: none (own netns, loopback only)`／`net: host (the daemon's network namespace)`；init 進 Landlock 時第一行尾巴加 `init asked for it (locks.landlock true)`、沒進時寫 `landlock: none (init)`。
- 打開 lo 用 `ioctl(SIOCSIFFLAGS)`（不用 netlink、不用 `ip`）；在子行程 `unshare(CLONE_NEWNS)` 之後、丟 caps 之前做。
- daemon 的 stderr 訊息裡 init 寫作 `init`（例 `started main (pid …, init)`、`restarting init main`）；`--restart-limit` 的說明文字照舊寫 `more than --restart-limit N`。
- **以下是 11-26 seccomp、疊 daemon 這一輪 eca-aos 自己挑的**（使用者定的是：每隻 proc 預設上內建的擋單、擋的回 `EPERM`、建 namespace 與 mount 那一族不擋（為了疊 daemon）、`"off"`、自己的名單檔、init 也一樣、`locks` 檔那一行）：
- 擋單裡的取捨：`kcmp`、`pidfd_getfd` 擋（跟 ptrace 同一類）；`move_pages`、`migrate_pages` 擋、`mbind`／`set_mempolicy`／`get_mempolicy` 放（只動自己）；`io_uring_*` 擋（使用者沒列，照 Docker 現在的預設）；`personality` 照 Docker 只放五個值；`create_module`、`get_kernel_syms`、`query_module`、`_sysctl` 這些核心早拿掉的也列（不花什麼）。
- 別的架構（i386 的 `int 0x80`）與 x32 的號碼：整個行程殺掉（`KILL_PROCESS`），不是 `EPERM`。
- `"seccomp": "builtin"` 也收（跟不寫一樣）。
- 名單檔的格式 `{"default": "allow", "deny": [...]}`／`{"default": "deny", "allow": [...]}`，兩種都做了；名單不疊在內建的擋單上；重複的算一個；名字只認 x86_64 的；只能 x86_64 編（別的架構 `#error`）。
- `locks` 那行的寫法：`seccomp: builtin (44 syscalls denied with EPERM, personality limited to safe values; other arch and x32 calls kill the process)`、`seccomp: off`、`seccomp: <路徑> (default allow, N denied with EPERM; …)`／`(default deny, N allowed, the rest EPERM; …)`。
- seccomp 上在 chdir、接好 0／1／2 之後、`execve` 前一刻（使用者說的是「Landlock 之後、exec 前最後一步」）。
- `--cgroup PATH`／`"cgroup": "/path"`：給的夾用不了就起不來（退出碼 2），不悄悄變 `off`；路徑要絕對；`status` 寫 `realpath` 後的路徑。
- 疊 daemon 的界線寫成 `nest` 組的測試（照實記下「起不來、在哪一步」），沒有為了讓它起來放寬任何預設。
- **以下是 11-26 審查三條與五樣這一輪自己挑的**（使用者定的是：停止訊號只收外面〔`ssi_pid` 0 且 `SI_USER`／`SI_KERNEL`〕與 init 送的、uid 0 殺得掉 init 與兄弟先接受並寫進 README 與 `locks`、測普通 proc 寫不到 init 的 ctl、卡住時不再無限等、`ns.json` 的 `by`／`at` 四種值、overlay、合併目錄 B 的測試與 A 的寫法、`restart-init` 的規則、介面宣告的位置與三個檔）：
- init 送的停止訊號另外要 `ssi_code` 是 `SI_USER` 或 `SI_TKILL`（寄件人 PID 由核心填）；剛死掉的那隻 init 的 PID 也認（它死前送的訊號可能在收屍後才讀到）。
- 不理的停止訊號每個記一行 log（寫寄件人 PID、表上的名字、`si_code`）。
- `locks` 的 `signals:` 那行只寫在 uid 0 的普通 proc 上（init、subuid 的不寫），寫法 `signals: can signal init and other uid-0 procs (Landlock ABI N has no signal scoping; the daemon ignores stop signals from it)`。
- 逾時或失敗時送 SIGKILL 後最多等 0.5 秒（幫手正常結束最多等 1 秒），沒走就留給主循環；刪不掉的 cgroup 夾主循環每秒再試、daemon 結束時再刪。
- `ns.json` 的 `at`：起動時的各筆都用「天空組好、量表」那一刻；`locked` 跟帶它進來的 bind 同一刻；對不上設定的 `unknown` 筆沒有 `by`、`at`。
- overlay：`lower` 至少兩個、第一個在最上面；文字表的來源用 `:` 接；只收 `type`、`lower`、`dst`。
- `restart-init`：沒有 init 的 daemon、同名的一般 proc 在表上都是當場 `EINVAL`；`init_restarts` 與 `init_deaths_in_window` 都歸零；起不來回 `EIO`、不自動再試、`init_state` 寫 `gone (restart-init failed: …)`。
- 介面宣告的三個小檔內容後面帶換行；`commands` 照收的字列、不隨狀態變。

## 還沒做的

- seccomp 只有 x86_64；名單只認名字（不收號碼、不看參數；內建的擋單只有 `personality` 看參數）。
- **疊 daemon 照預設的鎖起不來**（見「疊 daemon」）；放寬要使用者定。外面那份把 proc 的 cgroup 夾交給它、綁進天空、收尾由深到淺刪：量過、沒做。
- 網路只有 `none`（只有 lo）與 `host` 兩種；要「有網路但不是外面那個」（veth、slirp、指定介面）這版沒有。
- 擋訊號、abstract socket：要 Landlock ABI 6（Linux 6.12 以上）；這台 6.6 擋不住，程式在 ABI 6 以上會自動加。
- `start` 的路徑用天空裡的路徑（照 init 自己的天空換算）：這版只收外面的路徑。
- 天空表只在起動與跑的時候掛／卸之後量；proc 自己改不了天空（沒有 caps），所以這兩個時候以外不會變。
- 一個很慢的天空（例如 bind 的來源卡在別的 FUSE 上）會讓主執行緒等到 10 秒逾時，這段時間其他 `start` 也排著（之後不再卡：見「bind 來源卡住時」）。卡住的行程沒放開前，daemon 結束時 Linux 要等它們走，daemon 才真的消失。
- 6.6 上 uid 0 的 proc 殺得掉 init 與兄弟（先接受，見「已知限制：uid 0 的 proc」）。
- 沒試過：沒有 Landlock 的核心（含 init 寫 `locks.landlock: true` 時的拒）、沒有 systemd --user 而 `--cgroup auto`（照程式會寫 `off (no systemd --user …)`）、cgroup v1、家機、沒開 IA32／x32 的核心（`seccomp` 組的「`off` 時照通」那兩條會不一樣）。

## 要使用者定的

1. ~~ctl 的錯誤要不要等做完才回~~：使用者 11-26 定「要」。aos-procfs 加了「做完才回」的 ctl，這裡用上了（見上面「寫入等做完才回」）；還要看的只剩 errno 挑 `EIO` 可不可以。
2. ~~init 留 CAP_SYS_PTRACE 可以嗎~~：使用者 11-26 選「掛進 init 的天空、不給權限」，並保留舊做法。做好了（見上面「init」）；`/aos`、`/cgroup`、`daemon_access`、init 以外不給 `AOS_DAEMON`（改名自 `AOS_ROOT`）、`init_access`，使用者 11-26 都說照這樣。
3. **ABI 3 擋不住訊號**：~~init 以外的 proc 能對 daemon 送 SIGTERM（daemon 一收就整片收掉）~~ 使用者 11-26 定：daemon 只收外面與 init 送的停止訊號（做好了，見「結束」）；uid 0 的 proc 殺得掉 init 與兄弟**先接受**（README「已知限制：uid 0 的 proc」、`locks` 檔照實寫）。預設 uid 要不要改成 subuid 是另一題（使用者還沒定）。
4. ~~小世界裡放 `cgroup/`~~：使用者 11-26 定「照現在這樣」。開關照第 7 條「直接擺進資訊」，這版是把 cgroup 夾 bind 進小世界、用相對 symlink 指過去；所以 `/proc/<PID>/root` 會看到 `aos`、`cgroup` 兩個夾。
5. ~~資訊夾用 `slots/<i>/` 加 symlink~~：使用者 11-26 定 `procs/<名>/` 是真的夾、`forget` 就消失。aos-procfs 加了 `remove_tree`，這裡用上了（見上面「`procs/<名>/`：真的夾」）。
6. **疊 daemon 要放寬哪一道**（11-26 量的，見「疊 daemon」）：照預設的鎖，proc 裡的 daemon 起不來。能選的（各有代價，都沒做）：
   - a. 讓某隻 proc 不進 Landlock（例 `locks.landlock: false` 只准給要疊 daemon 的 proc；現在使用者定的是「不能關」）——代價：那隻讀得到旁邊 proc 的 `/proc/<PID>/root` 這類東西少了一道擋。或等 Landlock ABI 6 以上（Linux 6.12+），改成只管 signal／abstract socket、不管檔案系統的 domain：照 Linux 原始碼，新的核心只在 domain 管了檔案系統權限時才擋 mount（**沒實測**，這台 6.6 做不到）。
   - b. uid：疊 daemon 的 proc 用 subuid 的 uid（`"uid": 1` 之類，現在就能寫），或給它留 CAP_SETFCAP（讓 uid 0 對照得了自己）。前者不用改程式。
   - c. 天空的 `dev` 加 `/dev/fuse`（例 `{"type": "dev", "dst": "/dev", "fuse": true}`）。
   - d. cgroup：外面那份把那隻的 cgroup 夾交給它的 uid、綁進它的天空、收尾由深到淺刪（裡面那份的 `--cgroup PATH` 已經做了）。
   量過 a＋b（uid 1）＋c 一起放寬時，裡面那份起得來、init 讀得到目錄、能 `start` 一隻、收 SIGTERM 時整片走光；再加 d 時 cgroup 也用得了。
