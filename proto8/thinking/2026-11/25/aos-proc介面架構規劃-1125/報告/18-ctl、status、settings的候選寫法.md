給下一輪跟使用者談 ctl／status／settings 用的材料：盤了今天實際有的字與欄位，寫出三套具體候選（最小套、今天套、Plan 9 套）與八項比較，推薦「必備只有三個字與九行、其餘是名字統一的選配」，最後附十題的題目單。

# 18　ctl、status、settings 的候選寫法

← [架構規劃入口](../README.md)

寫的人：這批的第 18 隻子 agent（fable）。只讀程式與活樹，沒改任何既有的檔；實驗只在 `~/.aos/scratch/aos-proc-arch-1125/18/` 跑，沒留行程。需求來源是 [9P proc 第一輪談話](../../9p-proc-1125.md)，下面說「定了的」都指那一份。

三種話怎麼分：加引號寫「使用者」的＝他的原話；帶 `檔名:行號` 或寫「實測」的＝查到的；標「推論」「推薦」的＝我的，還沒有他的話。標「憑記憶」的外部知識這台查不到原文。

縮寫（只在本檔用）：`$P`＝某一隻 proc 自己的目錄，`$D`＝某一台 daemon 自己的目錄。出處裡 `aos-loop/…`、`aos-daemon/…` 開頭的在 `proto8/cpp/` 底下。三套候選叫**最小套**、**今天套**、**Plan 9 套**（[01](01-aos-loop現況.md) 已經用甲～辛稱呼另一件事，這裡不用甲乙丙）。

## 1. 結論

1. **今天「控制」分五條路（[02](02-aos-daemon現況.md) 2.4）、狀態分三個 JSON 檔**，字與欄位都盤齊了（第 2 節）。搬成純文字時行名幾乎都能沿用今天的鍵名；要換的只有回音那兩個（`ctl_seq`、`ctl_warning`）與 `stack`（改叫 `persist`）。
2. **推薦今天套的字表，但分兩層**：必備只有 `stop`、`pause`、`resume` 三個字、`status` 九行、`settings` 兩行，一支 21 行的 bash 腳本就做得出來（實測，2.6）；其餘（`set`、`ping`、agent 的 `retry`、daemon 管列的六個字）是「有做就要叫這個名字」的選配。
3. **daemon 管列的字建議寫到另一個檔 `procs_ctl`**，不跟它自己的 `ctl` 混：`echo "stop $NAME" > ctl` 的變數一空，就變成把整台 daemon 停掉。
4. **停著、睡著的列建議給一份純文字的表 `procs_status`**（`列名.欄: 值`）。proc 死了它自己的 `status` 就沒了，「信箱在哪」只有 daemon 答得出來；這台沒有 `jq`，JSON 的表在殼裡讀不了。
5. **實測（ctl）**：普通檔沒人讀也寫得進去、同一個字寫兩次看不出來；具名管線（FIFO）二十人同時寫一千行一行沒壞，行程一死從 `/proc/<PID>/cwd` 寫就是「沒有這個檔」；要當場回話得走 unix socket，一行問、一行答。
6. **實測（status）**：先寫暫存檔再改名，五萬次讀沒有一次讀到壞的；直接覆寫，八萬四千次讀有七萬六千次讀到空檔。
7. **錯誤建議兩邊都給**：`status` 的 `ctl_error` 一定有；socket、FUSE 這種能當場拒絕的再加當場拒絕。
8. **Plan 9 的字不能照搬**：它的 `stop`／`start` 是「停住／繼續」，跟使用者 11-03 定的三對同字不同義。可以借的是形狀：一行一道、被拒就讓那次寫入失敗。
9. 最該先裁的三題是第 8 節的問 1、問 2、問 3。

## 2. 今天實際有的

### 2.1 控制：誰收什麼字

| 誰收 | 檔或管道 | 收什麼 | 出處 |
|---|---|---|---|
| aos-loop（daemon 自己也是同一段程式） | `ctl.json`，整份 JSON＝一道指令 | `cmd`：`pause`／`resume`／`stop`；`max`、`interval_ms`（非負整數，`null`＝回設定值）；`seq`（只回音） | `aos-loop/include/aos/loop.hpp:52-60`、`aos-loop/src/engine/window.cpp:169-262`、`aos-loop/docs/02-窗.md:9` |
| aos-daemon 的名單（宣告：整份＝期望） | `procs_ctl.json` | `procs`、`procs_added`、`procs_removed`、`procs_stopped`、`procs_started`、`procs_slept`、`procs_woken`、`seq` | `aos-daemon/src/daemon/windows.cpp:26-103`、`aos-daemon/docs/04-兩個手把-兩扇狀態窗.md:50-66` |
| aos-daemon 的信箱（一封＝一次改動，可回信） | `procs_requests/` | 上面六個 `procs_*`，加 `ping`、`procs_state_path` | `aos-daemon/src/daemon/mailbox.cpp:111-197`、`aos-daemon/docs/05-信箱.md:19-33` |
| aos-daemon（訊號） | `SIGRTMIN+1／2／3`（poke）、`SIGTERM`（sleep） | 叫它馬上看檔；現在就收掉一列 | `aos-daemon/docs/04-兩個手把-兩扇狀態窗.md:70-91`、`aos-daemon/docs/03-起-停-暫停.md:69` |

加一列時那包內容的鍵：`exec`、`ws`、`stack`、`def`、`limits`、`auto_restart`、`restart_on_stuck`、`stuck_after_cycles`／`stuck_after_ms`、`as_written`，再加 loop 的 `max`、`interval_ms`（`aos-daemon/src/daemon/daemon.hpp:28,107`）。

指令與工具那一層：

| 指令或工具 | 動作 | 出處 |
|---|---|---|
| `aos-daemon-ctl` | add、rm、prune、stop、start、sleep、wake、pause、resume、ls、leftovers、where、ping、poke、shutdown、sweep（16 個） | `proto8/py/aos/apps/daemon_ctl/main.py:759-763` |
| `aos-agent ctl` | add、rm、set-def、start、stop、sleep、wake、pause、resume、retry、ls、state（別名 status）、where、who | `proto8/py/aos/apps/agent/ctl/__init__.py:8-11` |
| 工具 `subagent` 的 op | add、rm、ls、state、stop、start、sleep、wake、pause、resume、say、listen、ask、tools、llm、history、hook、system | `proto8/py/tools/agent/subagent/_tooldef.json:5` |
| 工具 `self_ctl` 的 op | stop、pause、sleep、rm | `proto8/py/tools/agent/self_ctl/_tooldef.json` |
| agent-fsm 認的信 | `/compact`、`/clear`、`/status`、`/usage`、`/exit` | `proto8/py/aos/apps/agent_fsm/slash.py:16`、`proto8/knowledge/aos/me/compact.md:32-49` |

每個動作實際走哪條路（細節在 [02](02-aos-daemon現況.md) 的 2.4，這裡只留跟字表有關的）：

- **pause／resume**：指令直接寫那隻自己的 `ctl.json`，不經 daemon；等回音最多 5 秒（`proto8/py/aos/daemon_ctl/ctl.py:60-75`）。
- **stop／start／sleep／wake／add／rm**：寄信給 daemon；指令先照表擋一輪，stop 只收 running、start 只收 stopped、wake 只收 sleeping，錯了回 `PhaseBad`（同檔 `:29-56`）。daemon 自己不擋。
- **stop 的後半**：daemon 替那一列寫它的 `ctl.json`、等它自己退，列留成 `stopped`（`aos-daemon/docs/03-起-停-暫停.md:9`）。**sleep** 不寫 ctl，直接送 `SIGTERM`；公開協定沒有 sleep 這個字（`aos-loop/docs/02-窗.md:47`）。
- **繞過 daemon 直接往一隻的 ctl 寫 stop**：它退 0，daemon 把那一列從表上拿掉（同一份 03 的 `:17`）；那一列開了 `auto_restart` 的話會被重起（`:48`）。

### 2.2 狀態：每個欄位

| 檔 | 誰寫 | 欄位 | 出處 |
|---|---|---|---|
| `state.json`（loop） | 自己 | `phase`（running／waiting／paused／done／stopped）、`max`、`interval_ms`、`paused`、結束時多 `code`、`pid`、`started_at_ticks`、`boot_id`、`updated_at` | `aos-loop/src/engine/window.cpp:322-353` |
| `state.json`（daemon 多的） | 自己 | `cgroup`、`daemon`（上一層在哪，根＝null）、`group`、`poke`（三個訊號號碼）、有身體才有 `body_code` | `aos-daemon/src/daemon/table.cpp:99-109` |
| `state_flux.json` | 自己 | `responded_at`、`ctl_seq`、`ctl_warning`；daemon 多 `procs_ctl_seq`、`procs_ctl_warning`、`adopt_warning`、`mailbox_warning` | `aos-loop/src/engine/window.cpp:355-377`、`aos-daemon/src/daemon/windows.cpp:192-201` |
| `procs_state.json` 頂層 | daemon | `procs_loop`、`procs_exec`、`procs_stderr`、`procs_requests`、`daemon`、`procs`、`pid`、`started_at_ticks`、`boot_id`、`updated_at` | `aos-daemon/src/daemon/windows.cpp:214-240` |
| `procs_state.json` 每列 | daemon | 一律有：`pid`、`started_at_ticks`、`phase`（running／stuck／stopping／stopped／sleeping）、`code`、`signal`、`stack`、`launch`、`exec`、`def`、`reason`。有才寫：`ws`、`stop_mode`、`limits`、`limit_hit`、`limit_suspect`、`cgroup`、`limits_ignored`、`auto_restart`、`counter_restarts`、`stuck_after_ms`／`stuck_after_cycles`、`restart_on_stuck`、`as_written` | `aos-daemon/src/child/child.cpp:356-432` |
| `aos-agent ctl who -j` | 讀表現算 | `name`、`stack`、`ws`、`def`、`daemon`、`parent`、`notify_box` | `proto8/py/aos/apps/agent/ctl/who.py:48-49` |
| `aos-agent ctl state`（工具 `self_state`） | 讀表與 stack 現算 | 十一類：who、state（`state`、`phase`、`reason`、`queued`、`last_answer`）、tools、llm、system、hooks、history、mailbox、subagents、resources（`limits`、`memory_bytes`、`cpu_seconds`、`processes`）、time（`now`、`up_seconds`） | `proto8/py/aos/apps/agent/ctl/state.py:16`、`:111-124`、`:285-311` |
| `/status`、`/usage`（agent-fsm） | 身體現算 | model、reasoning_effort、history 則數、goal、compact 的 phase、冷卻、還排著幾封；token 加總（來源 `observed.jsonl`） | `proto8/py/aos/apps/agent_fsm/slash.py:70-135` |

活樹上的實際內容（11-25 中午讀的）：

```
$ cat ~/aos-home/.stack/ctl.json
{"cmd": "stop", "seq": 7}
$ cat ~/aos-home/.stack/state.json
{"phase": "waiting", "max": null, "interval_ms": 200, "paused": false, "cgroup": "off", "daemon": null, "group": 60001, "poke": {"ctl": 35, "mail": 36, "all": 37}, "pid": 2223, "started_at_ticks": 31414, "boot_id": "e0557f4e-03b8-49b0-b274-5366d1935ae6", "updated_at": "2026-11-25T00:01:15.214+00:00"}
$ cat ~/aos-home/.stack/state_flux.json
{"responded_at": "2026-11-25T03:12:11.514+00:00", "ctl_seq": 7, "ctl_warning": null, "procs_ctl_seq": null, "procs_ctl_warning": null, "adopt_warning": null, "mailbox_warning": null}
$ cat ~/aos-home/.stack/procs/repo-aos/procs/eca-aos/state.json
{"phase": "running", "max": null, "interval_ms": 300, "paused": false, "pid": 2243, "started_at_ticks": 31414, "boot_id": "e0557f4e-03b8-49b0-b274-5366d1935ae6", "updated_at": "2026-11-25T00:01:15.426+00:00"}
```

第一段值得看：根 daemon 正在跑，它的 `ctl.json` 卻還留著一道 `stop`。那是上一次收工留下的；程式靠「seq 跟舊回音一樣就不重做」才沒有一起來又停掉（`aos-loop/src/engine/window.cpp:236-238`）。檔活得比行程久，才需要這一套。

### 2.3 對照：別人怎麼寫

| 誰 | 控制 | 狀態 | 值得借的／要避開的 |
|---|---|---|---|
| Plan 9 `/proc/n/ctl`（憑記憶；原樣在 [07](07-9P與Plan9原樣.md)） | 一行一道：`stop`（停住）、`start`（繼續）、`kill`、`waitstop`（卡到真的停住）、`hang`／`nohang`、`pri N`、`close N`、`closefiles`、`private`、`noswap`、`wired N`。另有 `note` 檔：寫 `kill`、`interrupt` 進去＝敲它一下 | `status` 是**一行**十二欄、靠位置認：名字、使用者、狀態、六個時間、記憶體、兩個優先級 | 借：字加參數、寫入失敗＝被拒、`kill` 指令只是印出 `echo kill>/proc/123/note` 讓殼去跑。避開：它的 status 正是使用者不要的靠位置；stop／start 的意思跟 aos 相反 |
| Linux `/proc/<PID>/status`（這台實測，59 行、1493 位元組） | 沒有 ctl；訊號 | `Name:<TAB>值`，一行一個 | 借：靠名字找，所以十幾年來一直加行（手冊標著 2.6.10 到 4.17 陸續加的）舊程式沒壞。避開：行名大小寫混用（`VmPeak`、`Cpus_allowed_list`、`voluntary_ctxt_switches`）；值裡帶單位（`4368 kB`）；一行塞四個數（`Uid:`） |
| Linux cgroup v2（讀是這台實測；寫的行為憑記憶） | 往檔裡寫字：`echo 1 > cgroup.freeze`、`echo "+cpu" > cgroup.subtree_control`；寫錯當場失敗 | `cpu.stat` 是 `名稱 值` 一行一個（實測第一行 `usage_usec 99628132000`） | 借：一個檔管一件事，要改就往那個檔寫 |
| systemd（`show` 是這台實測；動作字憑記憶） | `systemctl stop／start／restart／kill／freeze／thaw` | `systemctl show -p …` 印 `MainPID=221`、`ActiveState=active` 一行一個；印出來的順序跟要求的順序不一樣 | 借：給機器的一律靠名字 |
| daemontools／runit／s6（憑記憶；細節在 [10](10-前例-服務目錄與監督者.md)） | 往一條具名管線 `supervise/control` 寫**一個字母**：`u` 起、`d` 停、`o` 只跑一次、`p` 暫停、`c` 繼續、`t` TERM、`k` KILL、`x` 監督者自己退 | 二進位的 `supervise/status`，另用 `svstat`／`sv status` 翻成人話；runit 多給純文字的 `supervise/stat`、`supervise/pid` | 借：寫了不回話、做完沒看狀態，跟使用者定的一樣，這三家用了二十多年。避開：它們的 pause 是 `SIGSTOP`（當場凍住），aos 的 pause 是做完這一步才停 |

### 2.4 實測：`ctl` 用三種檔各會怎樣

公司 WSL2、核心 6.6、bash 5.2。完整輸出在 `~/.aos/scratch/aos-proc-arch-1125/18/exp_ctl.out`，程式是同一夾的 `exp_ctl.py`。

| 測什麼 | 普通檔 | 具名管線（FIFO） | unix socket |
|---|---|---|---|
| 沒人在讀時 `echo stop > ctl` | 成功（結束碼 0） | 卡住（`timeout 1` 之後 124）；不卡的開法回 `ENXIO` | `echo >` 不能用：`No such device or address` |
| 有人在讀時 | 成功，但不代表有人讀 | 13.9 毫秒回來（多半是起 bash 的時間），對面讀到了 | `echo pause \| nc -U -N ctl.sock` 印 `ok` |
| 寫一個不認得的字 | 成功 | 成功，沒有回話的路 | 印 `error: CmdUnknown 'bogus' is not one of pause resume stop`（玩具伺服器自己編的句子） |
| 同一個字連寫兩次 | 內容沒變，比內容的讀者看不出來 | 兩道都到 | 兩道都到 |
| 一次寫三行 | 看讀的人怎麼切 | 三道照順序到 | 看協議 |
| 二十人同時各寫五十行 | 沒測（[01](01-aos-loop現況.md) 2.5 測過：會丟、會誤報） | 一千行全到、沒有一行被切開 | 沒測 |
| 行程被 `kill -9` 之後，從 `/proc/<PID>/cwd/ctl` 寫 | 沒測 | `No such file or directory`，當場 | 沒測（9p-proc-1125 測過：連不上，當場失敗） |
| 行程死後從真實路徑寫 | 成功 | 卡住（管線檔還在硬碟、沒人讀） | `Connection refused` |

另外兩個數字：

- **記位置的讀法會讀壞**：讀的人記「讀到第 5 個位元組」（剛讀完 `stop`），別人 `echo pause > ctl` 蓋過去之後，它從第 5 個位元組接著讀，只讀到一個換行。
- **當場拒絕長什麼樣**：`echo 9999 > /proc/self/oom_score_adj` 印 `bash: echo: write error: Invalid argument`、結束碼 1。這是 Linux 自己的檔；FUSE、9P 回答寫入時能做到同一件事（這台沒有 libfuse 標頭，沒直接測）。

### 2.5 實測：`status` 落檔時怎麼寫

寫的人不停重寫十四行的 status，讀的人不停整份讀，各跑 2 秒（`exp_status.py`）：

| 寫法 | 讀了幾次 | 讀到空檔 | 讀到半份 | 新舊混在一起 |
|---|---|---|---|---|
| 先寫暫存檔再改名（今天的做法，N-05） | 50,345 | 0 | 0 | 0 |
| 直接清空再寫 | 84,091 | 76,170 | 2 | 0 |

- 改名之後，**還開著舊檔沒關的讀者永遠看舊的那一份**（實測：舊的讀到 `phase: gen 1`，重開才讀到 `gen 2`）。所以 `tail -f status` 沒用，要每次重開。
- 一份十四行的 status 是 267～394 位元組，一次 `read` 讀完。

<details><summary>最小重跑（八行，只碰一個暫存夾；照這份貼的跑過）</summary>

```sh
cd "$(mktemp -d)" && mkfifo ctl
timeout 1 bash -c 'echo stop > ctl'; echo "沒人讀: $?"                      # 124
( exec 3<>ctl; while read -r line <&3; do echo "收到: $line"; [ "$line" = exit ] && break; done ) &
echo pause > ctl; printf 'set interval_ms 500\nresume\n' > ctl; echo exit > ctl; wait
: > plain; echo stop > plain; echo "普通檔沒人讀: $?"                       # 0
printf 'phase: running\n' > .status.tmp && mv .status.tmp status; exec 4< status
printf 'phase: paused\n'  > .status.tmp && mv .status.tmp status
echo "舊的: $(head -1 <&4)　重開: $(head -1 status)"                         # running／paused
```

</details>

### 2.6 實測：必備那一層，21 行 bash 做得出來

一支 bash 腳本站進自己的夾，擺出 `ctl`（FIFO）、九行的 `status`、兩行的 `settings`。另一支程式只從 `/proc/<PID>/cwd` 跟它講話：

```
$ echo pause > /proc/2568891/cwd/ctl     # 之後 status：phase: paused、ctl_count: 1
$ echo bogus > /proc/2568891/cwd/ctl     # 之後 status：ctl_error: CommandUnknown bogus is not one of stop pause resume；phase 不變
$ echo resume > /proc/2568891/cwd/ctl    # 之後 status：phase: running、ctl_error: -
$ echo stop > /proc/2568891/cwd/ctl      # 行程退 0
$ cat /proc/2568891/cwd/status
cat: /proc/2568891/cwd/status: No such file or directory
```

退了之後硬碟上那份 status 還在，第一行是 `phase: stopped`；落檔的實作，檔會活得比行程久。

<details><summary>那支腳本（也在 `~/.aos/scratch/aos-proc-arch-1125/18/toy_proc.sh`，旁邊的 `toy_drive.py` 是下指令的那一邊）</summary>

```bash
#!/bin/bash
# toy_proc.sh DIR - the required layer of an aos proc in bash: ctl (a FIFO), status, settings (report 18)
cd "$1" || exit 1
mkfifo ctl 2>/dev/null; exec 3<>ctl
printf 'persist: %s/persist\nmailbox: %s/persist/mailbox\n' "$PWD" "$PWD" > .settings.tmp && mv .settings.tmp settings
now() { date -u +%FT%T.%3N+00:00; }
phase=running count=0 last=- err=- at=- boot=$(cat /proc/sys/kernel/random/boot_id) ticks=$(cut -d' ' -f22 /proc/$$/stat)
put() { printf '%s: %s\n' phase "$phase" pid $$ started_at_ticks "$ticks" boot_id "$boot" updated_at "$(now)" \
        responded_at "$at" ctl_count "$count" ctl_last "$last" ctl_error "$err" > .status.tmp && mv .status.tmp status; }
put
while [ "$phase" != stopped ]; do
  if read -r -t 0.2 line <&3; then
    count=$((count + 1)) last=$line err=- at=$(now)
    case $line in
      stop) phase=stopped ;; pause) phase=paused ;; resume) phase=running ;;
      *) err="CommandUnknown ${line%% *} is not one of stop pause resume" ;;
    esac
    put
  fi
  if [ "$phase" = running ]; then :; fi      # one step of its own work goes here
done
```

</details>

## 3. 三套候選

三套的例子都照同一組行規則寫（要不要換別的規則在第 4 節比 1）：

- **ctl**：一行一道，換行結尾；第一個詞是字（小寫英文），後面是參數，用一個空白分開；一道 4096 位元組內。
- **status、settings**：一行一個 `名稱: 值`（冒號後一個空白）；名稱是小寫字母、數字、底線；值從那個空白之後到行尾，原樣；沒有值寫 `-`。

例子裡的 PID、時間、ticks、boot_id 是活樹上的真值（根 daemon 2223、`eca-aos` 2243）；`persist` 的路徑、`arena` 這一列、`ctl_*` 與 `procs_ctl_*` 那幾行的值是舉例。這些是「照今天的值排出來會長這樣」，不是現有程式的輸出。

### 3.1 最小套：只收今天 loop 有的三個字

想法：介面只定每隻 aos proc 一定有的最少東西，其餘留在各實作自己的 JSON 檔。

**ctl 的字**（每一種 proc 都一樣）

| 字 | 參數 | 做什麼 | loop | agent | daemon | kernel |
|---|---|---|---|---|---|---|
| `stop` | 無 | 做完手上這一步就結束 | ✓ | ✓ | ✓（＝收工，底下的睡下） | ✓ |
| `pause` | 無 | 做完手上這一步就停住，行程還在 | ✓ | ✓ | ✓（整圈暫停，不起不收） | ✓ |
| `resume` | 無 | 解除 pause | ✓ | ✓ | ✓ | ✓ |

不認得的字不做，原因寫進 `status` 的 `ctl_error`。沒有參數、沒有 seq。

**daemon 多的字**（寫同一個 `ctl`）

```sh
echo "add arena /home/guanyu/aos-home/defs/arena" > $D/ctl    # 加一列並起它
echo "rm arena" > $D/ctl                                       # 收掉、拿掉那一列（persist 不刪）
```

停一列＝對那一隻自己的 ctl 寫 `stop`，退了就下表；再起＝再 `add` 一次。**代價**：使用者 11-03 定的三對（start／stop、sleep／wake、pause／resume）只剩一對半；開了 `auto_restart` 的列（活樹根表 11 列有 10 列）用這個辦法停不住，只能 `rm`。

**status**（七行，daemon 多一行）

```
$ cat $P/status                                      $ cat $D/status
phase: running                                       phase: waiting
pid: 2243                                            pid: 2223
started_at_ticks: 31414                              started_at_ticks: 31414
boot_id: e0557f4e-03b8-49b0-b274-5366d1935ae6        boot_id: e0557f4e-03b8-49b0-b274-5366d1935ae6
updated_at: 2026-11-25T00:01:15.426+00:00            updated_at: 2026-11-25T00:01:15.214+00:00
ctl_count: 0                                         ctl_count: 7
ctl_error: -                                         ctl_error: -
                                                     procs: 11
```

`ctl_count`＝起來之後收了幾道 ctl。表照舊是 `procs_state.json`（JSON），介面不管。

**settings**：只有兩行，`persist: 路徑` 與 `mailbox: 路徑`（寫法同 3.2 的例子）。

### 3.2 今天套：今天做得到的動作都有字

想法：今天經 `aos-daemon-ctl`、`aos-agent ctl` 做得到的事，新介面一樣做得到；字與欄位沿用今天的名字。分「必備」與「選配」：沒做的選配字就當不認得的字，在 `ctl_error` 寫 `CommandUnknown`，所以只做三個字的小實作不會被多出來的字弄壞。

**每隻 proc 自己的 `ctl`**

| 字 | 參數 | 做什麼 | 今天的對應 | loop | agent | daemon | kernel | |
|---|---|---|---|---|---|---|---|---|
| `stop` | 無 | 做完這一步就結束 | `cmd: stop` | ✓ | ✓ | ✓ | ✓ | 必備 |
| `pause` | 無 | 做完這一步就停住 | `cmd: pause` | ✓ | ✓ | ✓ | ✓ | 必備 |
| `resume` | 無 | 解除 pause | `cmd: resume` | ✓ | ✓ | ✓ | ✓ | 必備 |
| `set 名稱 值` | 2 | 改一個生效中的參數；能改的就是 `status` 裡看得到的那幾行（`interval_ms`、`max`） | `ctl.json` 的 `interval_ms`、`max` | ✓ | ✓ | ✓ | ✓ | 選配 |
| `unset 名稱` | 1 | 回到設定檔的值 | 寫 `null` | ✓ | ✓ | ✓ | ✓ | 選配 |
| `ping [記號]` | 0～1 | 什麼都不做，只讓 `ctl_count`、`responded_at` 動一下，用來問「你還在轉嗎」 | daemon 的 `ping` 信；父判卡住看 `responded_at` | ✓ | ✓ | ✓ | ✓ | 選配 |
| `retry` | 無 | 清掉失敗冷卻，下一拍就重試 | `aos-agent ctl retry`（刪 `cooldown.json`） | － | ✓ | － | － | 選配 |

沒收進來的：`sleep`（今天就不是 proc 自己的字，是 daemon 送訊號）；agent 的 `compact`、`clear`（今天是排在 queue 裡的信，靠排隊保證先後，搬進 ctl 會變成插隊）；kernel 沒有多的字（它收的請求是信，[14](14-kernel過去的規劃對照新模型.md) 的範圍）。

**daemon 管列的字**（寫到另一個檔 `$D/procs_ctl`；擋在 daemon 前面決定放不放行的 kernel 站收同一組字）

| 字 | 做什麼 | 今天的對應 |
|---|---|---|
| `add 名字 路徑` | 加一列並起它。路徑是定義夾，或一份 JSON 檔（內容照今天 `procs_added` 那包：`exec`、`ws`、`limits`、`auto_restart`…）；路徑從名字之後算到行尾，有空白也不用引號 | `procs_added` |
| `rm 名字` | 收掉、拿掉那一列（persist 不刪） | `procs_removed` |
| `stop 名字` | 替它寫 `stop`、等它自己退，列留成 `stopped` | `procs_stopped` |
| `start 名字` | `stopped` 的再起 | `procs_started` |
| `sleep 名字` | 現在就收（`SIGTERM`，10 秒後 `SIGKILL`），列留成 `sleeping` | `procs_slept` |
| `wake 名字` | `sleeping` 的再起 | `procs_woken` |
| `register 名字 PID` | 只登記、不起：一支已經在跑的行程說「我是 aos proc」 | 今天沒有（[02](02-aos-daemon現況.md) 問 1、問 4） |

```sh
echo "add arena /home/guanyu/aos-home/defs/arena" > $D/procs_ctl
echo '{"exec": "/home/guanyu/aos-home/defs/arena", "ws": "/mnt/c/code/mine/arena", "auto_restart": true}' > /tmp/arena.json
echo "add arena /tmp/arena.json" > $D/procs_ctl               # 其餘參數放那份 JSON 檔
printf 'add arena /tmp/arena.json\nstop arena\n' > $D/procs_ctl   # 同一次寫入的兩行一起生效＝上表但不起
echo "stop arena" > $D/procs_ctl
echo stop > $D/ctl                                             # 停 daemon 自己（今天的 shutdown）
```

今天有、但不必變成字的：ls／where／who／state（改成讀檔）、poke（ctl 是 FIFO 或 socket 時，寫進去本身就把它叫醒）、`procs_state_path` 查詢信（表的位置固定了）、leftovers／prune／sweep（指令自己讀檔做的事）、set-def（rm 加 add 的組合）。

**status**（「第一批」欄是比 8 的推薦）

| 行 | 值 | 今天在哪 | 第一批 |
|---|---|---|---|
| `phase` | running／waiting／paused／stopping／done／stopped | `state.json` | ✓ |
| `pid`、`started_at_ticks`、`boot_id` | 這支行程是誰 | `state.json` | ✓ |
| `updated_at` | 這份內容上次變的時間 | `state.json` | ✓ |
| `responded_at` | 上次對外面有反應的時間 | `state_flux.json` | ✓ |
| `ctl_count` | 起來後收了幾道 ctl（好壞都算） | 新；取代 `ctl_seq` | ✓ |
| `ctl_last` | 最後收的那一道，原樣 | 新 | ✓ |
| `ctl_error` | 最後那一道被拒的原因（`代號 原因`），好的＝`-` | `ctl_warning` | ✓ |
| `interval_ms`、`max` | 生效中的值 | `state.json` | 會反覆跑的才有 |
| `ctl_words` | 這隻收哪些字，空白分開 | 新 | 選配 |
| `stage`（agent） | idle／think／wait／act（agent-fsm）、cli（eca）、`-` | `stage.txt`、`busy.txt`（`proto8/py/aos/apps/agent/ctl/ls.py:76-90`） | ✓ |
| `queued`（agent） | 排著還沒答的信數 | 讀的人自己去數（`apps/agent/hints.py:158-162`） | ✓ |
| `procs`（daemon） | 表上幾列 | `procs_state.json` | ✓ |
| `procs_ctl_count`、`procs_ctl_last`、`procs_ctl_error`（daemon） | `procs_ctl` 的回音 | `procs_ctl_seq`、`procs_ctl_warning` | ✓ |
| `paused`、`code` | | `state.json` | 不收（看 `phase`；結束碼歸表） |
| `body_code`、`adopt_warning`、`mailbox_warning`、`cgroup`、`group`、`poke` | | 兩個 JSON 檔 | 不收（落檔 daemon 自己的事） |
| goal、冷卻、model、history 則數、context 讀數 | | `/status` 現算 | 不收（等「多給別的檔」） |

```
$ cat $P/status                                      $ cat $D/status
phase: running                                       phase: waiting
stage: cli                                           interval_ms: 200
queued: 0                                            max: -
interval_ms: 300                                     procs: 11
max: -                                               pid: 2223
pid: 2243                                            started_at_ticks: 31414
started_at_ticks: 31414                              boot_id: e0557f4e-03b8-49b0-b274-5366d1935ae6
boot_id: e0557f4e-03b8-49b0-b274-5366d1935ae6        updated_at: 2026-11-25T00:01:15.214+00:00
updated_at: 2026-11-25T00:01:15.426+00:00            responded_at: 2026-11-25T03:12:11.514+00:00
responded_at: -                                      ctl_count: 7
ctl_count: 0                                         ctl_last: ping
ctl_last: -                                          ctl_error: -
ctl_error: -                                         procs_ctl_count: 12
ctl_words: stop pause resume set unset ping retry    procs_ctl_last: stop arena
                                                     procs_ctl_error: PhaseBad arena is already stopped
```

**表：`$D/procs_status`**（行名＝`列名.欄名`，最後一個點之後是欄名。每列只收八個標準欄：`phase`、`pid`、`code`、`signal`、`reason`、`counter_restarts`、`persist`、`mailbox`，沒有值的不寫；其餘 `launch`、`limits`、`as_written` 留在 daemon 自己的 JSON）

```
$ cat $D/procs_status
_clock.phase: running
_clock.pid: 2225
llm.phase: running
llm.pid: 2227
repo-aos.phase: running
repo-aos.pid: 2228
repo-aos.persist: /home/guanyu/aos-home/persist/repo-aos
repo-aos.mailbox: /home/guanyu/aos-home/persist/repo-aos/mailbox
arena.phase: stopped
arena.pid: -
arena.code: 1
arena.reason: failed to start: exited within 3s of wake/start (code 1): agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set
arena.counter_restarts: 3
arena.persist: /mnt/c/code/mine/arena/.aos/persist
arena.mailbox: /mnt/c/code/mine/arena/.aos/persist/mailbox
```

`phase` 的值是今天表上那五個（running／stuck／stopping／stopped／sleeping）。「問 daemon 某個 proc 的信箱在哪」就是讀 `arena.mailbox` 那一行，它死了也讀得到。

**settings**（起來時寫一次、之後不變；歸屬的道理在 [12](12-_metainfo、index與proc目錄.md) 的 3.1）

| 鍵 | 值 | 今天在哪 | 誰要讀 |
|---|---|---|---|
| `persist` | 要留的東西放哪；絕對路徑，或相對自己的目錄 | 表上的 `stack` 欄 | daemon（抄進表） |
| `mailbox` | 別人投信的夾；沒寫＝`persist` 底下的 `mailbox` | `<stack>/mailbox` | daemon、要寄信的人 |
| `sock` | 送訊息用的 unix socket；沒寫＝自己目錄的 `sock` | 新 | 要送訊息的人 |
| `name` | 這一列的名字 | 表的鍵（agent 今天從裡面不知道自己叫什麼） | 核對用 |
| `def`、`ws` | 定義夾、工作區 | 表的 `def`、`ws` 欄 | 人、工具 |
| `daemon` | 管它的那台 daemon 的目錄；根＝`-` | `state.json` 的 `daemon` | 往上找的人 |
| `parent`、`notify_box` | 誰要求加它的、做完往哪報 | `who` 的同名欄 | 它自己 |
| `wake_on_mail`（daemon） | 有人問信箱時要不要順手叫醒 | 新（使用者：「我傾向於這是daemon自身的可選設定」） | daemon 自己 |
| `default_persist`（daemon） | 沒自己挑的 proc 給哪一塊 | 新（使用者：「在/tmp開闢一塊給他」） | daemon 自己 |

```
$ cat $P/settings
name: eca-aos
persist: /home/guanyu/aos-home/persist/repo-aos/eca-aos
mailbox: /home/guanyu/aos-home/persist/repo-aos/eca-aos/mailbox
sock: sock
def: /home/guanyu/repo/aos/proto8/templates/agents/eca-claude
ws: /home/guanyu/repo/aos
daemon: /proc/2223/cwd/procs/repo-aos
parent: -
notify_box: -
```

### 3.3 Plan 9 套：照 Plan 9 的檔與字

想法：Plan 9 有的就用它的名字與意思，沒有的才補。這一小節講到 Plan 9、factotum 的地方都憑記憶。

**ctl 的字**

| 字 | Plan 9 的意思 | 搬到 aos 是什麼 | loop | agent | daemon | kernel |
|---|---|---|---|---|---|---|
| `stop` | 讓行程停在那裡 | 今天的 **pause** | ✓ | ✓ | ✓ | ✓ |
| `start` | 讓停住的繼續 | 今天的 **resume** | ✓ | ✓ | ✓ | ✓ |
| `kill` | 結束它 | 今天的 stop 或 sleep，得再挑一個 | ✓ | ✓ | ✓ | ✓ |
| `waitstop` | 寫的人卡住，直到它真的停住 | 「寫回來＝做完」，跟定了的「寫回來＝收到」不同 | － | － | － | － |
| `hang`／`nohang` | 下次起來先停住 | 今天靠舊 state 的 `paused` 接回 | △ | △ | △ | △ |
| `pri N` | 設優先級 | 問腦的優先級今天在 llm kernel 那邊，不在 proc 身上 | － | △ | － | － |
| `close N`、`closefiles`、`private`、`noswap`、`wired N` | 管行程的檔案代號、記憶體、綁哪顆 CPU | 沒有對應 | － | － | － | － |

另外兩個檔：`note`（寫一個詞＝敲它一下，`echo kill > $P/note` 是現在就收，今天的對應是訊號）、`wait`（讀它會卡住，直到底下有一隻結束，回一行結束訊息；今天沒有，[11](11-閒置成本、時鐘與等待.md) 的範圍）。被拒絕時那次寫入直接失敗、帶一句原因（要 9P 才帶得了一句話）。

**daemon 多的**：Plan 9 的 `/proc` 沒有「加一個行程」的字（行程是 fork 出來的）。借 factotum 的寫法，一行裡寫 `鍵=值`，值有空白用單引號：

```sh
echo "add name=arena def=/home/guanyu/aos-home/defs/arena ws='/mnt/c/code/mine/my arena'" > $D/ctl
echo kill > $D/procs/arena/ctl      # 結束；正常結束的列直接從 procs 夾消失
```

沒有表這個檔：`ls $D/procs` 就是表。出錯結束的列留著（Plan 9 裡壞掉的行程會留在 `/proc` 給人看），由 daemon 代答它的 `status`。「留著列等人 start」與 sleep／wake 這兩對沒有位置。

**status**：Plan 9 的原樣是一行靠位置，使用者已經定了不這樣。這一套是「用它的欄、改成一行一個」（數字取自這台 `/proc/2243/stat`、`/proc/2223/stat`）：

```
$ cat $P/status                  $ cat $D/status
name: eca-aos                    name: root
user: guanyu                     user: guanyu
state: Running                   state: Running
utime_ms: 6500                   utime_ms: 39360
stime_ms: 21650                  stime_ms: 15020
rtime_ms: 15689810               rtime_ms: 15689810
mem_kb: 2784                     mem_kb: 3388
pri: 20                          pri: 20
```

這八行除了 `name`，Linux 自己的 `/proc/<PID>/status` 與 `stat` 少走一層 `cwd` 就有；aos 才知道的事（在想還是在做、排了幾封信、上一道 ctl 怎麼了）反而一行都沒有。

**settings**：Plan 9 沒有這個檔。最接近的是 `ns`，一行一個「哪個名字接到哪裡」：

```
bind /home/guanyu/aos-home/persist/repo-aos/eca-aos persist
bind /home/guanyu/repo/aos ws
bind /home/guanyu/repo/aos/proto8/templates/agents/eca-claude def
```

## 4. 逐項比較與推薦

### 比 1　值裡有空白、換行、中文；名稱用什麼字

- **名稱**：三套都用小寫字母、數字、底線。今天所有 JSON 鍵本來就長這樣，不用改名。Linux 的 status 大小寫混用，是反例。
- **空白與冒號**：值是「到行尾原樣」，所以裡面可以有空白、冒號、等號。實測 `sed -n 's/^ws: //p'` 對 `/mnt/c/code/我的 專案/a: b` 拿得回原樣。
- **中文**：直接寫 UTF-8。今天 C++ 寫 JSON 也是不轉義（`proto8/cpp/aos-util/src/io.cpp:69`）。
- **換行與控制字元**：三種做法。

| | 做法 | 好處 | 壞處 |
|---|---|---|---|
| a | 寫的人把換行與控制字元換成一個空白 | 讀的人不用解；今天印 `reason` 就是這樣做（`proto8/cpp/aos-daemon/src/daemon/failure.cpp:59-60`、`proto8/py/aos/apps/daemon_ctl/main.py:597`） | 還原不了原字 |
| b | 反斜線轉義（`\n`、`\\`） | 還原得了 | 每個讀的人都要解，殼裡不好做 |
| c | 值一律寫成 JSON（字串加引號） | 型別清楚、還原得了 | `grep`、`sed` 拿到的字帶引號；跟「status 用純文字」的本意相反 |

**推薦 a**。會帶換行的今天只有給人看的句子（`reason`、`adopt_warning`）；路徑、名字裡有換行的直接拒收。ctl 那邊：每個字最多一個「到行尾」的參數，所以不用引號；放不下的（加一列那包）寫成一份 JSON 檔，ctl 只帶它的路徑。Plan 9 套的單引號與 `鍵=值` 是另一條路，要多一套切字規則。

### 比 2　版本怎麼標；以後加行會不會弄壞舊的讀者

- **照名字找就不會壞**。Linux 的 status 十幾年一直加行沒有版本號；systemd 印出來的順序甚至跟要求的不一樣。
- 使用者 11-09 對狀態檔的裁定是現在不加版本檢查，正式版那天才加（`proto8/thinking/2026-11/09/format-versioning/README.md` 的「使用者 11-09 裁定」；N-09 末句「只做『讀不了就說話』，不加版本檢查」）。

| | 做法 |
|---|---|
| a | 現在不標。規則寫死四條：照名字找、不認位置與行序；不認得的行跳過；沒有的行當作 `-`；一個名字的意思不改，要改就換新名字 |
| b | status 第一行 `format: aos-proc/1` |
| c | 標在 `_metainfo`（它本來就在答「我是什麼」），status 不標 |

**推薦 a**，正式版那天再照 c 補。b 會讓人以為第一行有特殊地位，跟「不認位置」打架。

### 比 3　錯誤怎麼回

第 2.4 節的實測就是答案的範圍：普通檔與 FIFO 沒有回話的路；socket、FUSE、9P 才能當場拒絕。

| | 做法 | 好處 | 壞處 |
|---|---|---|---|
| a | 只寫 `status` 的 `ctl_error` | 每一種實作都做得到 | 兩個人接連寫，後一道會蓋掉前一道的結果 |
| b | 只讓那次寫入失敗 | 下令的人當場知道，不會看到別人的 | 普通檔與 FIFO 做不到；FUSE 只回得了錯誤號碼，帶不了一句話（憑記憶） |
| c | 兩者：`ctl_error` 一定有；做得到的實作再加當場拒絕 | 讀的人只要認一個地方；好的實作體驗更好 | 規格要寫兩段 |

**推薦 c**。錯誤的字沿用今天的「代號 原因」與現有代號（`CommandUnknown`、`ArgumentsBad`、`PhaseBad`、`ProcMissing`、`InstanceExists`）。一個順帶的好處：今天「stop 只收 running」是指令先讀表再寄信擋的，兩步之間表可能變；改成 daemon 收到當下自己擋，就沒有這個空窗。真的需要「我這一道的結果」的人（加一列被 kernel 拒絕、排隊）走 socket，用同一組字、一行問一行答，細節在 [20](20-送訊息兩條路的細節.md)。

### 比 4　帶參數的命令進 ctl，還是寫 settings

| | 做法 | 例 | 評 |
|---|---|---|---|
| a | 進 ctl | `echo "set interval_ms 500" > $P/ctl` | 今天就是這樣（`ctl.json` 帶 `interval_ms`）。只有 ctl 一個檔是別人寫的 |
| b | 寫 settings | `echo "interval_ms: 500" > $P/settings` | 落檔的實作裡，這一下會把整份 settings 清掉，`persist` 那一行跟著不見 |
| c | 一個參數一個檔 | `echo 500 > $P/interval_ms` | cgroup 的做法；落檔時檔很多，每個都要有人去看 |

**推薦 a**：`ctl` 是唯一給別人寫的檔，`status` 與 `settings` 都是自己寫、別人只讀。能 `set` 的就是 `status` 裡看得到的那幾行，改完去 `status` 看。最小套不收參數，要改間隔只能重起。

### 比 5　多個人同時寫 ctl；一次寫多行

- **會不會丟，看用什麼檔**，不看格式：普通檔後寫的蓋掉先寫的；FIFO 每次 4096 位元組內的寫入不會被拆開（`man 7 pipe`），實測一千行全到；socket 一人一條線。aos-loop 該用哪一種是 [01](01-aos-loop現況.md) 第 5 節第 1、4 題。
- **格式這邊要定的四條**（推薦）：
  1. 一行一道，照到的順序做；每一道各自成敗，不因為同一批裡別行壞了就整批不做。
  2. 一定要換行結尾。沒有換行的半行會跟下一個人寫的黏在一起（實測：FIFO 上先 `printf stop`、別人再 `echo pause`，讀的人收到一行 `stoppause`）。
  3. 同一次寫入的幾行一起生效。今天「加＋停寫在同一封信＝上表但不起」靠的就是這個（`proto8/cpp/aos-daemon/docs/03-起-停-暫停.md:11`），`set-def` 也靠它（[02](02-aos-daemon現況.md) 2.4）。
  4. 兩個人下相反的字（一個 pause、一個 resume）：後到的算數，不鎖。跟今天一樣。
- 這四條把今天「只有最後一道算數」（N-06）改成「一道一道排隊」，是動到過去定案的地方，[01](01-aos-loop現況.md) 3.4 已經點出來。

### 比 6　好不好用殼操作

下面每一條都對樣本檔跑過（Plan 9 套的後兩條要 FUSE 或 9P，沒跑）。

```sh
# 最小套
echo pause > $P/ctl                                              # 叫它停住
sed -n 's/^phase: //p' $P/status                                 # 現在怎樣
until grep -qx 'phase: paused' $P/status; do sleep 0.2; done     # 等到真的停住

# 今天套
grep -H '^phase: ' $D/procs/*/status                             # 活著的每一隻現在怎樣
grep '\.phase: ' $D/procs_status | grep -v ': running$'          # 表上誰沒在跑
sed -n 's/^arena\.mailbox: //p' $D/procs_status                  # arena 的信箱在哪（它死了也答得出來）

# Plan 9 套
echo stop > $P/ctl                                               # 停住（Plan 9 的意思）
echo bogus > $P/ctl                                              # 當場印 write error（要 FUSE／9P）
read line < $D/wait                                              # 卡住等到有一隻結束（要 FUSE／9P）
```

兩個坑（實測）：

- `awk -F': ' '{print $2}'` 會把值從第二個「冒號空白」切斷：`ctl_error: ArgumentsBad … got: abc` 只印到 `got`。用 `sed -n 's/^名稱: //p'`，或 bash 的 `k=${line%%: *}; v=${line#*: }`。
- `while read` 逐行讀沒問題；`while IFS=': ' read -r k v` 在 bash 5.2 上值也完整。

今天的表是 JSON，這台沒有 `jq`，殼裡要讀只能起 Python。

### 比 7　status 的時間戳、誰寫、多久更新、讀到一半被改寫

- **誰寫**：只有自己（N-09）。daemon 對它的看法寫在 daemon 那邊的表，不寫進它的 status。
- **多久更新**：有變才寫，沒有心跳（N-17；使用者 11-02「心跳這塊就直接看pid就好」）。當場回答的實作（FUSE、9P）每次讀都是現做的。
- **時間戳**：`updated_at`（這份內容上次變的時間）、`responded_at`（上次對外面有反應的時間），格式照今天的 ISO 8601 UTC 到毫秒。當場回答的實作可以不給 `updated_at`。
- **讀到一半被改寫**：落檔一律先寫暫存再改名（N-05），實測五萬次讀零次壞；直接覆寫九成讀到空檔。讀的人每次重開檔、一次讀完；整份控制在 4096 位元組內（樣本最大 394）。
- **判活著**：`pid`、`started_at_ticks`、`boot_id` 三行留著。從 `/proc/<PID>/cwd` 進來的人不需要；從真實路徑進來的人、以及防 PID 被重用（[01](01-aos-loop現況.md) 第 4 節第 13 條）還用得到。

三套在這一項沒有差別，照今天的規矩就好。

### 比 8　「目前只先給 status」之下，先收哪些

判準三條（推薦）：

1. **Linux 已經有的不收**。記憶體、CPU 時間、行程狀態，`/proc/<PID>/status` 少走一層 `cwd` 就有。
2. **行程一死就沒意義的才放 status**。結束碼、為什麼停、重起幾次，要在它死後還讀得到，歸 daemon 的表。
3. **起來後不變的放 settings**（`daemon`、`def`、`ws`、`parent`、`notify_box`），不放 status。

照這三條，第一批是今天套表格裡打 ✓ 的：**每隻都有的九行**（`phase`、`pid`、`started_at_ticks`、`boot_id`、`updated_at`、`responded_at`、`ctl_count`、`ctl_last`、`ctl_error`），會反覆跑的加 `interval_ms`、`max`，agent 加 `stage`、`queued`，daemon 加 `procs` 與 `procs_ctl_*` 三行。先不收的與理由也在那張表。token 用量照使用者說的另給一個檔，不進 status；今天的來源是 `observed.jsonl`。

逐欄歸哪個檔的完整表在 [12](12-_metainfo、index與proc目錄.md) 的 3.1，這裡跟它一致，只多寫了行名與例子。

## 5. 對著「定了的」逐條

| 定了的 | 這份得到的 |
|---|---|
| `ctl` 吃純文字，寫回來＝收到 | 一行一道。FIFO、socket、FUSE 做得到「有人收」；普通檔只做得到「存著」（實測）。行程死了從 `/proc/<PID>/cwd` 寫會當場失敗，這一點 Linux 白送 |
| 做完沒看 `status` | 落檔與 FIFO 的實作要靠 `ctl_count`、`ctl_last`、`ctl_error` 三行把「讀到沒、被拒沒」接起來；當場回答的實作可以不要前兩行 |
| `status` 一行一個「名稱: 值」，目前只給這一個檔 | 第一批九行加各類兩三行，四百位元組內 |
| persist 以 proc 自己說的為準，daemon 從 `settings` 讀 | settings 只放起來時就定的；daemon 讀到之後要把 `persist`、`mailbox` 抄進自己的表，proc 死了才答得出來 |
| `_metainfo` 照現有的 JSON | 不動；版本、收哪些字這類「我是什麼」的事以後放那裡 |
| token 各自報 | 另給一個檔，不進 status |
| daemon 也是 aos proc | 它自己的 `ctl` 就是那三個字（`stop`＝收工）；管列的字在另一個檔 |
| kernel 是普通的 aos proc | 沒有多的 ctl 字；kernel 站代收加列的請求時，收跟 daemon 同一組管列的字 |
| 活著走 socket、掛了問 daemon 信箱在哪 | 要回話的請求走 socket、用同一組字；信箱在哪讀 `procs_status` 的 `列名.mailbox` |
| 問信箱時要不要叫醒是 daemon 的可選設定 | 放 daemon 的 `settings`（`wake_on_mail`）；只叫 `sleeping` 的、不叫 `stopped` 的（推論，[02](02-aos-daemon現況.md) 3.8 同） |

## 6. 邊緣狀況

1. **直接對一隻寫 `stop`，跟請 daemon 停它，結果不一樣**。今天前者算它自己做完，列被拿掉，開了 `auto_restart` 的還會被馬上重起。新介面裡 `echo stop > $D/procs/arena/ctl` 會是最順手的打法，這個落差會比今天常被踩到（問 7）。
2. **寫回來、讀到、做完是三個時間點**。pause 是做完這一步才停；eca 一步可能二三十分鐘，這段時間 `ctl_count` 不會動。判卡住今天預設是關的，就是因為這個（`proto8/cpp/aos-daemon/src/daemon/daemon.hpp:6`，引使用者 11-15「逾時這東西應該要默認爲0，也就是不限時間」）。
3. **真實路徑上的 FIFO 沒人讀時，`echo` 會一直卡著**（實測）。一律從 `/proc/<PID>/cwd` 進去就不會；工具可以用不卡的開法。今天的 aos-loop 直接把 ctl 換成 FIFO 會卡死（[01](01-aos-loop現況.md) 實測），要改讀法。
4. **`stopped`、`sleeping`、`stuck` 不會出現在 proc 自己的 status**。前兩個它已經不在了，第三個是 daemon 的判斷。它們只出現在表上。所以同一個詞 `phase` 有兩份：自己說的，與 daemon 說的。
5. **名字進了純文字之後要收窄**。今天只擋 `/`、`#`、開頭的 `.`（`proto8/cpp/aos-daemon/src/daemon/daemon.hpp:109`），空白、冒號、換行都合法，會弄壞 ctl 的參數與表的行名。活樹兩張表 16 個名字都符合「字母、數字、`_`、`-`、`.`，不以 `.` 開頭」。
6. **宣告式的 `procs_ctl.json` 沒有純文字的對應**。它是「整份＝期望、拿掉就回底」，純文字 ctl 是一道一道的指令。活樹十張表沒有一張在用它（[02](02-aos-daemon現況.md) 2.4）。要不要留是 [16](16-過去定案與新模型的衝突檢查.md) 的範圍。
7. **N-13、N-14 寫著「窗的內容是 JSON」**，ctl、status 改成純文字後這兩條要跟著改，同上歸 16。
8. **表上的 PID 不一定是寫 status 的那一支**。我看到兩例（`repo-aos` 表上 2228、自己報 2239；`eca-aos-core` 表上 2246、自己報 2252），[02](02-aos-daemon現況.md) 量過是四成。所以 status 的 `pid` 行與 `register` 這個字是配套的。
9. **`set` 改的值重起就忘**。今天也是（`max`、`interval_ms` 起來回設定值）。要記住得改定義。
10. **兩個 `status` 同名**，Linux 的與 aos 的只差一層 `cwd`，而且都是一行一個。認 aos 的要找小寫的 `phase` 那一行（[12](12-_metainfo、index與proc目錄.md) 第 4 節第 5 條同）。
11. **現有的 json 工具讀不進純文字**（[12](12-_metainfo、index與proc目錄.md) 實測）。它們已經會讀 md 裡的 `key: value` 項目（`proto8/knowledge/aos/tools/json_get.md:36`），補成也認這種檔是小改（推論）；12 的第 2 題在問這件事。
12. **根 daemon 的 `ctl.json` 現在還留著一道 stop**（2.2）。ctl 跟著行程生死之後，這一類「上輩子留下的指令」就沒有了。

## 7. 沒查到／沒把握的

- Plan 9、factotum、daemontools、runit、s6 的字都憑記憶，這台沒裝、沒連外網查。以 [07](07-9P與Plan9原樣.md)、[10](10-前例-服務目錄與監督者.md) 為準。
- FUSE、9P 上「寫入失敗帶原因」沒在這台直接測，用 Linux 自己的 `/proc` 檔示範同一種行為。「FUSE 只回得了錯誤號碼」憑記憶。
- 沒對活樹跑 `aos-agent ctl who`、`ctl state`（守「不叫 aos 的 ctl」），欄位是讀程式列的。
- FIFO 在 `/mnt/c`（Windows 那邊的磁碟）上能不能用沒測；cgroup 寫錯的行為憑記憶。
- kernel 有沒有自己專用的控制字：沒查到。今天 kernel 收的都是信。
- `procs_status` 到一千列會是 250 KB 上下（每列五行估的），每變一次重寫整份。今天的 JSON 表也是同一個量級、超過一百列才切檔。沒實測到那個規模。

## 8. 給協調者的下一輪題目單

十題，最重要的在前。問 1～3 定了，其餘大半可以回「照推薦」。跟別份重疊的已標出，可以併題。

**問 1　ctl 的字要定到多少？**
- a. 只定三個：`stop`、`pause`、`resume`。其他各實作自己加，名字不管。
- b. 三個必備，另外一張選配表：有做就要叫這個名字、照這個意思（`set`、`unset`、`ping`、agent 的 `retry`）。不做的回 `CommandUnknown`。
- c. 照 Plan 9 的字（`stop`＝停住、`start`＝繼續、`kill`＝結束）。
- 推薦 **b**。外來行程做三個字就算數，常用的動作又不會各叫各的；c 會跟你 11-03 定的三對同字不同義。

**問 2　daemon 管列的字（加、拿掉、起、停、睡、醒）寫到哪？**
- a. 寫它自己的 `ctl`：`echo "stop arena" > $D/ctl`。
- b. 另一個檔 `procs_ctl`；它自己的 `ctl` 只收那三個字。
- c. 寫到那一列自己的路：`echo stop > $D/procs/arena/ctl`，死了的由 daemon 代收。
- 推薦 **b**。a 的 `stop $NAME` 變數一空就把整台 daemon 停掉；今天也是分兩個（`ctl.json` 與 `procs_ctl.json`）。

**問 3　停著、睡著的列，狀態與「信箱在哪」用什麼給？**（[02](02-aos-daemon現況.md) 問 3 問的是它們在 `procs` 夾裡出不出現，可以併）
- a. 照舊，daemon 的 JSON 表。
- b. 一份純文字的表 `procs_status`，行名是 `列名.欄名`，每列只收七、八個標準欄。
- c. 併進 daemon 的 `status`，多幾行。
- 推薦 **b**。proc 死了自己的 status 就沒了，這張表是唯一答得出來的地方；純文字殼裡一行 `sed` 就拿到，JSON 這台要起 Python。c 列一多，daemon 自己的 status 會變得很長。

**問 4　被拒絕的原因怎麼讓下令的人看到？**
- a. 只寫 `status` 的 `ctl_error`。
- b. 只讓那一次寫入失敗。
- c. 兩者：`ctl_error` 一定有；socket、FUSE 這種做得到的再加當場拒絕。
- 推薦 **c**。普通檔與 FIFO 沒有回話的路（實測），a 是每種實作都做得到的底。

**問 5　加一列的其餘參數（工作區、份額、auto_restart…）怎麼帶？**（跟 [02](02-aos-daemon現況.md) 問 5 同題）
- a. 不帶：`add 名字 定義夾`，其餘都用預設。
- b. 寫成一份 JSON 檔，ctl 只帶名字與那份檔的路徑；「上表但不起」用同一次寫入的兩行（`add …` 加 `stop …`）。
- c. 攤成一行的 `鍵=值`。
- 推薦 **b**。那包內容本來就是巢狀的，也合你說的「部分用json」；ctl 這邊不用發明引號規則。

**問 6　改參數（間隔、上限）走哪？**
- a. ctl 的 `set 名稱 值`；`status` 與 `settings` 別人只讀。
- b. 直接寫 `settings`。
- c. 一個參數一個檔。
- 推薦 **a**。b 在落檔的實作裡一寫就把整份 settings 清掉。

**問 7　直接對一隻 proc 自己的 ctl 寫 `stop`，daemon 怎麼看那一列？**
- a. 照今天：算它自己做完，列拿掉；開了 `auto_restart` 的會被重起。要留著列就跟 daemon 說。
- b. 一律留成 `stopped`，不重起。
- 推薦 **a**，規格裡寫明「有 daemon 顧的要停就寫 daemon 的 `procs_ctl`」。b 要 daemon 分得出「自己做完」與「被叫停」，今天兩種都是退 0，分不出來。

**問 8　`settings` 用什麼格式、放什麼？**（[12](12-_metainfo、index與proc目錄.md) 第 2 題相關）
- a. 跟 status 同一種「名稱: 值」；只放起來時就定的：`persist`、`mailbox` 必備，`sock`、`name`、`def`、`ws`、`daemon`、`parent`、`notify_box` 選配。
- b. JSON（跟 `_metainfo` 一樣，路徑可以用今天的指示詞）。
- c. 不另開這個檔：`persist` 用一條連結，其餘放 `_metainfo`。
- 推薦 **a**。殼腳本寫得出來，讀的人只學一種寫法；路徑寫絕對的，或相對自己的目錄。

**問 9　status 第一批收多少行？**
- a. 只收每隻都有的九行。
- b. 九行，加各類兩三行（會反覆跑的：`interval_ms`、`max`；agent：`stage`、`queued`；daemon：`procs` 與 `procs_ctl` 的回音）。
- c. 今天 `state.json` 加 `state_flux.json` 的欄位全收。
- 推薦 **b**。Linux 已經有的、行程死了才有意義的都不收；token 照你說的另給一個檔。

**問 10　格式細則一包，要不要逐條談？**
內容：名稱用小寫字母數字底線、沿用今天的鍵名；值到行尾原樣，換行與控制字元換成空白；沒有值寫 `-`；現在不標版本，規則是照名字找、不認得的行跳過；ctl 一行一道、換行結尾、4096 位元組內、同一次寫入的幾行一起生效；列名收窄成字母數字與 `_`、`-`、`.`。
- a. 整包照推薦。
- b. 逐條談。
- 推薦 **a**。每一條都是今天已經在做的，或這次實測過的。
