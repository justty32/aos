# 圖紙 B5：daemon 的 cgroup 總量（可選；線限 11-14，照 kernel-limits-plan 段 4；C++）

← [線限 11-14 紀錄](../kernel-limits-1114.md)｜設計出處：[07 cgroup 可選](../../13/kernel-limits-plan/07-cgroup可選.md)、[04 段 4](../../13/kernel-limits-plan/04-施工與驗收.md)、[05 K3、K12～K14](../../13/kernel-limits-plan/05-待裁與衝突.md)｜事實出處：`~/code/limits-1114/notes/G4-facts.md`（sol 11-14 在家機實測）

**疊在 B4 上面施工**：B4 改完、測試綠了之後才開工，改的是同一批檔。施工隊照這份寫碼，不做設計決定。圖紙沒寫到、或自相矛盾＝BLOCKED。

## 0. 範圍（只准動這些檔；全在 `proto8/` 底下）

- `impls/aos-daemon/src/child/cgroup.hpp`、`cgroup.cpp`（新）
- `impls/aos-daemon/src/child/limits.hpp`、`limits.cpp`、`child.hpp`、`child.cpp`
- `impls/aos-daemon/src/daemon/daemon.hpp`、`daemon.cpp`、`reconcile.cpp`、`tend.cpp`、`table.cpp`、`adopt.cpp`
- `impls/aos-daemon/CMakeLists.txt`（只加 `cgroup.cpp` 這個來源檔）
- `impls/aos-daemon/tests/test_cgroup.py`（新）
- `impls/aos-daemon/docs/09-份額.md`、`docs/01-用法.md`、`docs/06-結束碼等.md`、`docs/07-建置與測試.md`
- `docs/NORMS/04-基礎設施-loop與daemon/02-N-28.md`（`limits` 段）
- `knowledge/aos/cli/daemon.json`（repo 源頭；一句一鍵）

## 1. 事實（G4 實測，施工隊要知道）

- 家機用 `systemd-run --user --scope -p Delegate=yes -- <cmd>` 就能拿到委派的格，免 sudo。
  - 格子起初的 `cgroup.subtree_control` 是空的。
  - 格裡還有行程時寫 `+memory +pids` 會得到 EBUSY（cgroup v2 規定：有子格啟用控制器的格裡不能留行程）。
  - 要先把行程搬進子格 `daemon/`，再在父格寫 `+memory +pids`；`procs/` 也要再寫一次，`procs/<名>/` 才有 `memory.max`、`pids.max`。
- `memory.max` 只管實體記憶體：有 swap 時，配超過 memory.max 的量會被換出去，不會 OOM。實測要同時寫 `memory.swap.max=0` 才會 `oom_kill`。
- `pids.max`、`cgroup.kill` 實測有效；`cgroup.kill` 收得到 `setsid` 跑掉的行程。
- 現在的 stop：`stop` 只寫公開 ctl、等 proc 自己退；sleep／remove 送 SIGTERM，10 秒後掃後代行程組長 killpg（`tend.cpp:64-108`）。**這條路不改**，只在最後加 cgroup.kill。
- `launch.json#/wrap` 只在規劃裡，程式沒有讀它的地方。**這次不做 wrap**：要開 cgroup 的樹由起樹的人自己用 systemd-run 包；測試也自己包。
- 子行程現在的順序：setsid → 接 stderr → `apply_limits`（setrlimit、換身分）→ … → run_cli（`child.cpp:46-62`）。

## 2. 設計（ok-limits 定的；施工照做）

### 2.1 daemon.json 新鍵 `cgroup`

- 值只能是 `"off"`、`"auto"`、`"on"`，不寫＝`"off"`（K12）；別的值＝`CfgBad cgroup must be "off", "auto" or "on"`。
- 讀法照 B4 的 `limits_max`：daemon.cpp 讀、`daemon.hpp` 存 `std::string cgroup_mode_`。
- `off`：完全不碰 `/sys/fs/cgroup`（連讀都不讀）。

### 2.2 起 daemon 時的探測與搬格（`auto`、`on`；cgroup.cpp）

`cgroup_setup()` 在設定驗完、`make_stack()` 之前呼叫，照順序做：

1. 讀 `/proc/self/cgroup`，要找到 `0::<路徑>` 那行；找不到＝失敗「no cgroup v2 entry」。`base = /sys/fs/cgroup<路徑>`。
2. `base/cgroup.controllers` 要同時有 `memory` 和 `pids`；少了＝失敗「controllers lack memory/pids」。
3. `mkdir base/daemon`（已存在可以）。把自己的 pid 寫進 `base/daemon/cgroup.procs`。
4. 寫 `+memory +pids` 到 `base/cgroup.subtree_control`。
5. `mkdir base/procs`（已存在可以），寫 `+memory +pids` 到 `base/procs/cgroup.subtree_control`。
6. 任何一步失敗：
   - 盡力還原：已經搬過自己就搬回 `base/cgroup.procs`；`daemon/`、`procs/` 是這次建的，而且是空的，就 rmdir。
   - 原因＝那一步做什麼加 strerror，例：`cannot write +memory +pids to <base>/cgroup.subtree_control: Device or resource busy`。
   - `auto`：stderr 一行 `aos-daemon: warning: cgroup: none (<原因>)`，之後照 off 跑。
   - `on`：`CfgBad cgroup on: <原因>`、退 1。
7. 成功：`cgroup_base_ = base`。

daemon 自己的狀態（`table.cpp:91` 的 info）多一欄 `cgroup`：

| 情況 | 值 |
|---|---|
| off | `"off"` |
| 降級 | `"none (<原因>)"` |
| 開成 | base 的絕對路徑 |

### 2.3 新的份額鍵 `mem_total_mb`、`procs_total`（limits.cpp）

- KEYS 表加兩鍵。它們**不是** rlimit：`resource = -1`，`apply_limits` 跳過它們。
- `check_limits`、`limits_max`（B4）、`limits_` 的檢查都認這兩鍵，正整數、MB 的上限規則照 `mem_mb`。
- 錯誤訊息裡的 known 清單加這兩個名字。

### 2.4 每支 proc 一格（reconcile.cpp 起動路徑；cgroup.cpp）

開成（`cgroup_base_` 不是空的）而且是自己 fork 的 proc：

1. launch 前，在父行程準備 `cell = base/procs/<名>`：
   - 已存在而且 `cgroup.procs` 是空的：rmdir 再 mkdir，計數歸零；
   - 已存在但裡面還有行程（上一輪留下的）：寫 `1` 到 `cgroup.kill`，每 50ms 看一次、最多等 1 秒，空了就 rmdir 再 mkdir；
   - 寫 `memory.max`：有 `mem_total_mb`＝MB×2^20，沒有＝`max`；同時寫 `memory.swap.max`：有 `mem_total_mb`＝`0`，沒有＝`max`。檔不存在（沒 swap 控制）就略過；
   - 寫 `pids.max`：有 `procs_total`＝那個數，沒有＝`max`。
   - 任何一步失敗＝丟 `Error{code::LimitBad, "cgroup <cell>: <原因>"}`，走 B4 說的單列 catch（stopped、daemon 不退）。
2. 子行程：接好 stderr 之後、`apply_limits` 之前，寫 `0` 到 `<cell>/cgroup.procs`（把自己搬進去）。
   - 失敗＝stderr 一行 `aos-daemon: error: LimitBad cgroup <cell>: <strerror>`、`_exit(1)`。
   - 路徑字串在 fork 前就備好，不在子行程裡組。
3. `Child` 加 `std::string cg;`，記 cell 路徑。

沒開成（off 或降級），但份額裡有 `mem_total_mb`／`procs_total`：

- 照起；
- `Child` 加 `Json limits_ignored`，記照 KEYS 順序的鍵名陣列；
- daemon stderr 一行 `aos-daemon: warning: <名>: <鍵…> need cgroup (cgroup is <off|none>), ignored`。
- 這行比照 B4 的 `procs_warned`：同一列只印一次。

### 2.5 收屍（child.cpp `alive()`）

自己 fork、`got == c.pid`，而且 `c.cg` 不是空的：

1. 讀 `<cg>/memory.events` 的 `oom_kill N`：`N > 0`＝`c.limit_hit = "mem"`，並把 `limit_suspect` 清成 null。
2. 讀 `<cg>/pids.events` 的 `max N`：`N > 0`，而且 limit_hit 還沒設＝`c.limit_hit = "procs"`。
3. 讀不到檔＝不設，不報錯。
4. 讀完之後，`<cg>/cgroup.procs` 還有行程（孫子沒收乾淨）：寫 `1` 到 `cgroup.kill`。不等它，下次 launch 前那步會處理。

B4 的 SIGXCPU／SIGXFSZ 判斷照舊，先做；cgroup 的 `mem` 會蓋過 B4 的 suspect。

### 2.6 stop 收整格（tend.cpp；K14）

- `settle` 裡 10 秒寬限到了、要送 SIGKILL 的那一步（`tend.cpp:108` 附近）：`c.cg` 不是空的，就**再**寫 `1` 到 `<cg>/cgroup.kill`（原本的 killpg 照做）。
- 主行程退了、格子裡還有行程：2.5 的第 4 步會收。
- 列被移除（`table.cpp:31` drop）：`c.cg` 不是空的，就 cgroup.kill，再試 rmdir；失敗只 warn。

### 2.7 接回（adopt.cpp）

- 接回的 running 列（`own == false`）：
  - `base/procs/<名>/cgroup.procs` 裡有那個 pid＝`c.cg` 設成那格，只給 2.6 收整格用。
  - 接回的列不讀 events、不重設格子。
- 接回時要是 `cgroup_base_` 跟上一輪不同（換了模式）：不管舊格。

### 2.8 表列（child.cpp `row()`）

緊接在 B4 的 `limit_hit`／`limit_suspect` 之後，不是空的才輸出：

- `cgroup`：cell 的絕對路徑；
- `limits_ignored`：鍵名陣列。

## 3. 建置

照 B4 第 3 節。`CMakeLists.txt` 加 `cgroup.cpp` 之後，要重新跑一次 cmake configure：

```sh
cmake -S "$B/source/impls/aos-daemon" -B "$B/cmake" -G Ninja -DCMAKE_BUILD_TYPE=Release
```

## 4. 測試 `tests/test_cgroup.py`（新）

- 測試自己用 `systemd-run --user --scope -p Delegate=yes --unit=aos-limits-test-<隨機> -- <起 daemon 的指令>` 起 daemon。
  - 只准 transient scope，不准裝 unit 檔、不准改 systemd 設定。
  - 每個 scope 的名字都記下來，收尾停掉 daemon 後，確認 `systemctl --user list-units --all` 裡已經沒有它；沒消失就 `systemctl --user stop <名>`（只停自己起的）。
- 家機沒有 systemd user manager 的話，整個 class skip，並印出原因。
- 至少要有這幾例：
  1. 不寫 `cgroup`：daemon 狀態 `cgroup "off"`；寫了 `mem_total_mb: 256` 的列照起，表上有 `limits_ignored ["mem_total_mb"]`，stderr 有那行 warning。測試前後比一次 `/sys/fs/cgroup` 底下那個 scope 的子格清單，要沒變。
  2. `cgroup: "auto"`、包 Delegate scope：
     - 狀態是格子路徑；
     - 列 `mem_total_mb: 128` 跑 `exec python3 -c "x = bytearray(512 * 1024 * 1024); import time; time.sleep(5)"` → 被 OOM 收，`limit_hit "mem"`；
     - 列 `procs_total: 20` 跑 shell 開 40 支 `sleep 30 &` → 只開得到 20 支以內，表上 `limit_hit "procs"`（主行程退後）。
     - 跑 shell 用 exec，讓 shell 本身就是主行程。
  3. `cgroup: "auto"`、包**沒有** Delegate 的 scope（`systemd-run --user --scope -- …`）→ stderr 有 `cgroup: none (`，照起，狀態以 `none (` 開頭；同樣情況寫 `"on"` → daemon 退 1、stderr 有 `CfgBad cgroup on:`。
  4. 開了 cgroup：proc 裡 `setsid sleep 999 &`，然後 `exec sleep 999`；對它下 sleep（會送 SIGTERM）→ 列停了之後，那支 setsid 的 sleep 也不在（用它寫的 pid 檔查 `/proc/<pid>`）。
  5. 列的份額有 `limits: {"cpu_s": 30, "mem_total_mb": 256}` → `/proc/<pid>/cgroup` 是那一格，`/proc/<pid>/limits` 的 cpu 照 B4（soft 30、hard 31）。
  6. 同名列重起：第二輪的 `memory.events` 的 oom_kill 從 0 起算（格子重建過）。
- 跑法（兩條都要全綠；第二條是全套回歸，包含 B4 的 test_limits.py）：

```sh
L=/home/lorkhan/code/limits-1114
$L/clean.sh bash -c "cd $L/work && export TMPDIR=$L PYTHONDONTWRITEBYTECODE=1 && python3 proto8/impls/aos-daemon/tests/test_cgroup.py -v"
$L/clean.sh bash -c "cd $L/work && export TMPDIR=$L PYTHONDONTWRITEBYTECODE=1 && python3 -m unittest discover -s proto8/impls/aos-daemon/tests -p 'test_*.py'"
```

- `test_cgroup.py` 檔頭照 B4 7.3 加 `sys.path.insert`。

## 5. 說明文件

- docs/09：
  - 開關三值；
  - 探測與搬格的步驟；
  - 怎麼起（自己用 `systemd-run --user --scope -p Delegate=yes --` 包；`launch.json` 的 wrap 還沒做）；
  - `mem_total_mb` 會連 swap 一起封（memory.swap.max=0）；
  - `procs_total`；
  - `limit_hit` 的 `mem`／`procs`；
  - `limits_ignored`；
  - stop 收整格；
  - 接回的列不讀 events。
  - 把 B4 加的「rlimit 與 cgroup 對照表」補上 cgroup 那一欄。
- docs/01：daemon.json 頂層鍵表加 `cgroup`；份額鍵加兩個。
- docs/06：錯誤加 `CfgBad cgroup …`、`LimitBad cgroup <cell>: …`。
- docs/07：測試清單加 `test_cgroup.py`，並註明會起 transient scope。
- N-28 與知識庫各一句。

## 6. 不做（寫進回報即可）

- `launch.json#/wrap` 自動包 systemd-run。
- `cpu.max`。
- kernel 站 B1 的 `KEYS` 加這兩鍵：今天 kernel 的 `default`／`max` 表寫它們會 CfgBad，寄件人自帶的照轉。
- aos-sandbox 認這兩鍵。
- 段 3 的 subuid 換身分在 C++ 的順序（07 要求先進格、再換 uid；今天子行程不換 uid，先進格、再 `apply_limits` 就對了）。

## 7. 完成條件

- 第 0 節以外沒動。
- 建置成功。
- 第 4 節兩條測試全綠，在回報裡貼原文。
- 列出每個起過的 transient scope 名稱，並附「已消失」的確認輸出。
- `git diff --stat`。

## 8. Argon 審後的修正（11-14 ok-limits；跟上面衝突時以這節為準）

原文在 `/tmp/ok-limits-argon3/argon.out`（暫存）。採納表在紀錄檔。

### 8.1 探測（改 2.1、2.2）

- `daemon.cpp:79` 要解指示詞的那串鍵加上 `"cgroup"`。先驗 `is_string()`，不是字串、或不是三個值之一，都報 2.1 那條 CfgBad。
- **呼叫點改了**：`cgroup_setup()` 改在 `check_running()`（stack 的鎖）**之後**、`adopt()` **之前**呼叫，免得誤起第二台 daemon 時動到第一台的格。字串合法性照舊在驗設定那段先檢查。
- 第 1 步：`<路徑>` 去掉行尾的 `\r\n`；`<路徑>` 是 `/` 時 `base = /sys/fs/cgroup`；其他情況去掉尾端的 `/`。
- 第 2 步：`cgroup.controllers` 用空白切開，逐個 token 比對 `memory`、`pids`。
- 第 6 步，還原照這個順序（每一步都盡力做，失敗不另報）：
  1. `base/procs` 是這次建的而且是空的：rmdir；
  2. 第 4 步這次寫成功過：寫 `-memory -pids` 到 `base/cgroup.subtree_control`；
  3. 已經搬過自己：把自己的 pid 寫回 `base/cgroup.procs`；
  4. `base/daemon` 是這次建的而且是空的：rmdir。
- 同一個格裡重起（含 `adopt: true`）：`daemon/`、`procs/` 已經存在就直接用。先搬自己，再寫 `+memory +pids`（已經開了的再寫一次不會出事）。`procs/<名>` 這些舊格一律不碰，留給 adopt 接回。

### 8.2 份額鍵（改 2.3）

- KEYS 表**最後面**依序加 `mem_total_mb`、`procs_total`。
- `prep_limits` 巡鍵時，`resource < 0` 直接 `continue`：不呼叫 `getrlimit`、不放進 `out.rl`。`apply_limits` 也保險跳過 `resource < 0`。
- `limits.cpp:75` 的訊息改成 `{mem_mb, cpu_s, procs, file_mb, files, mem_total_mb, procs_total: positive integers; user: a string}`。
- `:91` 的 known 清單改成 `(known: mem_mb, cpu_s, procs, file_mb, files, mem_total_mb, procs_total, user)`。

### 8.3 格子（改 2.4、2.5、2.6、2.7）

- **共用函式** `cgroup_empty_cell(cell, bool remove)`，「格子裡還有沒有行程」一律看 `<cell>/cgroup.events` 的 `populated`：
  1. `populated 1` 就寫 `1` 到 `cgroup.kill`，每 50ms 看一次、最多等 1 秒，等到 `populated 0`；
  2. 等到了，先由下往上 rmdir 子格，`remove` 為真再 rmdir cell 本身；
  3. 等不到，回傳失敗原因。
- 2.4 第 1 步：格子已存在 → `cgroup_empty_cell(cell, true)` 再 mkdir；失敗＝丟 LimitBad。
- 2.6 的 drop：`cgroup_empty_cell(cell, true)`；失敗只 warn。
- 2.5 第 4 步：`populated 1` 才寫 `cgroup.kill`，照舊不等（下次 launch 或 drop 會用共用函式收尾）。
- 子行程搬進格失敗：退出碼改成 `_exit(126)`，避免被當成 `limit_suspect`。
- **`limit_hit` 的優先順序**：
  - B4 的 `cpu_s`／`file_mb` 先判；
  - 接著，`limit_hit` 還是 null 才判 `mem`（oom_kill > 0），再判 `procs`（pids max > 0）；
  - 最後只要 `limit_hit` 不是 null，`limit_suspect` 一律清成 null。
- **接回的列**（`own == false`）：`alive()` 發現主行程已經不在、而且還沒標過 `reaped` 時，標 `c.reaped = true`；`c.cg` 不是空的、而且 `populated 1`，就寫 `cgroup.kill`。這條只收孤兒，照舊不讀 events。
- **每次 launch 嘗試**（reconcile 兩條路徑都算，還有 tend 的重起）開頭先 `c.cg.clear()`、`c.limits_ignored = Json()`，進 catch 也清。
- `Child` 加 `bool cgroup_warned`，`c.limits` 變了就重設。
- 2.4 那行 warning 寫死：
  - 鍵名用 `", "` 連接，例 `mem_total_mb, procs_total`；
  - 括號裡只印 `cgroup is off` 或 `cgroup is none`，不帶原因。

### 8.4 測試（改第 4 節）

- **起 daemon**：全部用 `systemd-run --user --scope --collect -p TimeoutStopUSec=2s --unit=aos-limits-test-<隨機> …`。
- **收尾**：包一個 `ScopedDaemon`，在 `addCleanup` 裡依序做：
  1. 停 daemon；
  2. scope 的 `cgroup.kill` 寫 1；
  3. `systemctl --user stop <unit>`；
  4. `systemctl --user reset-failed <unit>`（沒有也不算錯）；
  5. 最後確認 `list-units --all` 裡已經沒有它。
- **例 1**：daemon 起好之後，從 `/proc/<daemon_pid>/cgroup` 取 scope 路徑。在起那一列之前、那一列跑完之後（daemon 停之前）各看一次那個目錄，兩次都不能有 `daemon/`、`procs/`。
- **例 2 的 procs**：改用 `exec python3 -c` 寫迴圈，直接呼叫 `os.fork()`。
  - 子行程 `time.sleep(30)`；
  - 父行程接 `BlockingIOError`，確認成功 fork 的次數 ≤ 19，然後退 0。
  - 不用 shell 開背景行程（bash 遇到 EAGAIN 會退避 1+2+4+8 秒）。
- **例 3 改成兩種確定會失敗的前提**，兩種都在有 Delegate 的 scope `S` 裡跑：
  - **缺控制器**：包裝腳本先 `mkdir S/noctrl && echo $$ > S/noctrl/cgroup.procs && exec aos-daemon …` → `auto` 時 stderr 有 `cgroup: none (controllers lack memory/pids)`，照起；`on` 時退 1。
  - **EBUSY 與還原**：包裝腳本先 `sleep 60 &`（留在 S 裡、記 pid），再 exec daemon → `auto` 時有 `cgroup: none (`、而且 S 底下沒有殘留 `daemon/`、`procs/`。收尾 kill 掉那支 sleep。
  - 原本「沒有 Delegate 的 scope」那個例子刪掉。家機上它不會失敗。
- **例 4 拆兩列**：
  - (a) 原本的寫法，主行程 `exec sleep 999`：下 sleep 之後，最多輪詢 2 秒，確認 setsid 的那支不在；
  - (b) 主行程 `trap '' TERM`，而且 setsid 一支、自己 `while :; do sleep 1; done`：下 sleep 後等過 10 秒寬限（測試最多等 15 秒），兩支都不在。這一例涵蓋 2.6。
- **例 5**：腳本 `touch ready && exec sleep 30`，等 `ready` 出現才讀 `/proc/<pid>/cgroup` 與 `/proc/<pid>/limits`。

### 8.5 說明文件（加進第 5 節）

docs/09 加一段邊界說明：還沒接上段 3 的 subuid 之前，proc 跟 daemon 是同一個 uid，對自己那格的 `memory.max`、`cgroup.procs` 都有寫入權。所以 cgroup 總量和 cgroup.kill 防的是：

- 失控的記憶體；
- fork 炸彈；
- setsid 跑掉的孤兒。

它不防同 uid 的行程故意改寫 cgroupfs。要防這個，得等換 subuid。

## 9. 施工前更正（11-14 ok-limits，sol-4 回報 BLOCKED 後；跟第 4 節、8.4 衝突時以這節為準）

sol-4 對過程式碼：主行程退 0 的列，`tend.cpp:166` 標成 done，reconcile 接著就把它從表上拿掉，`limit_hit` 沒地方看。B4 的 cpu／file 例子沒遇到這個問題，因為那些主行程是被訊號停的，碼非 0，列會留成 stopped。

裁定：**生命週期不改**，只改測試。

1. 例 2 的 procs：python 父行程接到 `BlockingIOError`、確認成功 fork 的次數 ≤ 19 之後，**改成 `os._exit(3)`**；次數超過就 `os._exit(4)`，讓測試能分辨。不用 1，免得跟 B4 limit_suspect 的條件攪在一起；這例本來也沒寫 mem_mb。測試斷言：
   - 列留成 stopped、`code == 3`、`limit_hit == "procs"`，而且 `limit_suspect` 不在表上；
   - 格子裡留下的 `sleep 30` 由 2.5 第 4 步的 `cgroup.kill` 收掉。輪詢最多 5 秒，看那格的 `cgroup.events` 是不是 `populated 0`；如果那格在 launch 時已經被重建或移除，看不到就算過。
2. 例 2 的 mem：被 OOM 的 SIGKILL 停掉，碼 137，列會留著，照原本寫法就行。斷言 `limit_hit == "mem"`、`signal == 9`。
3. 其他例子要從表上讀 `limit_hit`／`limit_suspect` 的，一律讓主行程以非 0 結束，或被訊號停掉。
4. **契約寫進 docs/09**：`limit_hit`、`limit_suspect` 只留在還在表上的列；主行程退 0 的列照舊收掉，不留這兩欄，結束 log（`table.cpp`）也不加。要從結束 log 看到這兩欄，是另一件事，這次不做。

## 10. 施工中更正（11-14 ok-limits，sol-4 第二次回報 BLOCKED 後）

- 8.4 的 `-p TimeoutStopUSec=2s` 寫錯了：那是 D-Bus 屬性的名字，systemd-run 的命令列會報 `Unknown assignment`（家機 systemd 261）。**改成 `-p TimeoutStopSec=2s`**，ok-limits 實測過，scope 起得來，`--collect` 也收得掉。8.4 其他照舊。
