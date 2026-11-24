# 04 aos proc 與 aos-loop／daemon（蒐集隊員，只讀，11-24）

說明：「讀到」＝我在檔裡看到那行字；「推測」＝我從程式推的，沒實跑。路徑都相對 `/home/lorkhan/repo/aos/proto8/`，除非寫 `wf/`。
先講一件事：**沒找到 `aos ps` 這個指令**。bin 裡沒有。`thinking/2026-10/30/agent-lifecycle/03-各題結論.md:12` 寫過「aos 不另做 `aos-ps`」。現在看 proc 清單的是 `aos-daemon-ctl ls` 和 `aos-agent ctl ls`。下面「ps」都指這兩個。

使用者 11-24 原話（`wf/user/advice/20261124.md:36-39`）：
> 這塊其實有點走歪了，應該是要用界面形式的。
> 也就是：任何 Linux proc，只要你能提供這些可存取的檔案佈局，如 ctl/status 等，那你就是 aos proc。
> 不管你在硬碟、/tmp、FUSE 都可以，哪怕是網路上也行。
> 這就是單純的 Plan 9 思想。硬要說有啥不同的話，就是我們主打 JSON，串接先前的概念。

---

## 一、現況

### 1.1 「aos proc」現在怎麼定義

**讀到的：現行定義是「被 daemon 起的、記在 daemon 表上的一列」，不是「提供某個檔案佈局」。**

- 知識庫一句話：`knowledge/aos/_description.md` 寫「proc: one running thing under a daemon. A running agent is a proc.」（在 daemon 底下才算）。
- 概念表：`docs/CONCEPTS/附錄1-名詞/02-inst到table.md:11` 寫「daemon 底下的子項不論包成 loop 一直跑、還是 aos-exec 跑一次都是 proc」。
- 一列怎麼來：只有一條路，就是 daemon 照名單起它。`cpp/aos-daemon/docs/02-看寫法決定怎麼起.md` 的表：字串或陣列＝exec 型，`aos-exec -- 目標` 跑一次；物件多了 loop 的 key＝loop 型，daemon 寫 `loop.json`、經 aos-exec 起一支 aos-loop。
- 我**沒找到**「把一支已經在跑、不是 daemon 起的 Linux 行程登記進表」的指令。`aos-daemon-ctl add`（`knowledge/aos/cli/daemon.md` 的 add 一節）給的永遠是「要跑的目標」。
- 所以：想當 proc，要讓 daemon 去起你；起了之後你要自己（或被包的 aos-loop）寫那些檔。

**另一邊也讀到：aos 自己有「界面」的想法，但只落在「窗」這一族，沒變成 proc 的定義。**
- `docs/NORMS/05-基礎設施-窗/03-N-13～N-14.md`（N-13）：「state／ctl＝程式內部狀態的外顯（程式願意分享給大家的，像 Plan 9／FUSE）」。「FUSE 可選、以後再說」。
- 同檔（N-14）：窗只收「只有最新那份算數」的固定檔，內容是 JSON，原子性靠 rename，位置落在 `$AOS_STACK`。
- 沒有哪條規範寫「提供這組檔就算 aos proc」。**沒找到**。
- `docs/NORMS/05-基礎設施-窗.md` 開頭還寫：這族窗「是給『反覆跑的東西』（daemon、kernel）用的。agent 這層沒有 ctl」。

### 1.2 stack 裡有哪些檔、誰寫誰讀（逐一）

以下是 loop 型 proc 的 stack（`$AOS_STACK`，預設 `<daemon stack>/procs/<名字>/`，也可每列自己指 `stack`）。

| 檔 | 誰寫 | 誰讀 | 出處 |
|---|---|---|---|
| `loop.json` | **daemon**（起 loop 型時先寫 `.loop.json` 再改名） | aos-loop 自己；`aos-daemon-ctl` 讀它找 ctl／state_flux 的檔名 | `cpp/aos-daemon/docs/02-看寫法決定怎麼起.md`「起子 loop」；`py/aos/daemon_ctl/ctl.py:18-25`（`need_ctl`）、`py/aos/daemon_ctl/base.py:5`（`procs_loop` 預設 `loop.json`） |
| `exec.json`（只有內嵌單子的 exec 型） | daemon | aos-exec | 同上檔「物件，key 只有 exec」那列 |
| `ctl.json`（慣用名） | 任何人：`aos-daemon-ctl pause/resume` 直接寫；daemon 替 `stop` 寫 | **proc 自己的 aos-loop** 每圈讀；**daemon 只看它的 mtime**（判 stuck） | `cpp/aos-loop/include/aos/loop.hpp:54`；`py/aos/daemon_ctl/ctl.py:60-75`；`cpp/aos-daemon/src/daemon/stuck.cpp:42-60` |
| `state.json` | proc 自己（aos-loop） | daemon 只在**接回（adopt）**時讀 pid、ticks、boot_id、`phase==done`；別人不讀 | `loop.hpp:63`；`cpp/aos-daemon/src/daemon/adopt.cpp:99-120` |
| `state_flux.json` | proc 自己 | daemon（判 stuck 看 `responded_at`）、`aos-daemon-ctl`（等 `ctl_seq` 追上） | `loop.hpp:74`；`stuck.cpp:38-60`；`py/aos/daemon_ctl/ctl.py:164-178` |
| `stop_cause.json` | **daemon**（SIGTERM 之前寫） | proc 的 aos-loop（收工時給 on_stop 的 `AOS_LOOP_CAUSE`） | `loop.hpp:80-91`；`cpp/aos-loop/src/engine/window.cpp:95-125` |
| `counter_runs.txt`（要 `--enable-counters`） | aos-loop | 沒人讀（設計上） | `docs/NORMS/05-基礎設施-窗/02-N-09～N-11/01-N-09-state與計數器.md` |
| `stderr.txt` | **daemon 把子行程的 stderr 接過去**；清道夫封存截短 | daemon 取最後非空行當表上 `reason` | `cpp/aos-daemon/docs/08-當機復原與已知限制.md:27-28`；`cpp/aos-daemon/docs/02-…md` 起 exec 型那段 |
| `mailbox/`（Maildir：tmp／new／cur） | 任何寄信人（aos-post） | 該 proc 自己 | `knowledge/aos/mailbox.md`；`docs/NORMS/05-基礎設施-窗/05-N-16/01-信箱與信封.md` |
| agent 專屬：`queue/`、`history.jsonl`、`letters.json`、`stage.txt`、`observed.jsonl` 等 | agent 本體 | `aos-agent ctl ls --deep` 讀 `stage.txt`；其餘看 agent 自己 | `knowledge/aos/me.md` 的 "What is in your stack"；`py/aos/apps/agent/ctl/ls.py:152-155` |

daemon 自己的 stack（「管轄」那一側）：
- `daemon.json`（設定）、`ctl.json`、`state.json`、`state_flux.json`、**`procs_ctl.json`**（宣告的名單，整份都是期望）、**`procs_state.json`**（表，可分檔 `{"$ref": [...]}`）、**`procs_requests/`**（信箱）、`procs/<名>/`。
- 出處：`cpp/aos-daemon/docs/04-兩個手把-兩扇狀態窗.md` 的表。
- 表每列的欄：`pid`、`started_at_ticks`、`phase`、`code`、`signal`、`stack`、`ws`、`exec`、`def`、`reason`，另存 `launch`、`stop_mode`（同檔）。

### 1.3 ctl 怎麼下、誰在讀

**讀到的：有兩條不同的路，容易混。**

1. **proc 自己的 `ctl.json`**（一個 JSON 物件＝一道指令）：
   - 欄：`cmd`（`pause`／`resume`／`stop`）、`max`、`interval_ms`、`seq`。出處 `docs/NORMS/05-基礎設施-窗/01-N-06～N-08.md`（N-06、N-07）。
   - 規則：跟上一次讀到的內容不一樣才算新指令；「誰能寫 ctl.json 就能控制」；讀的人只讀不寫。
   - 讀它的是 **proc 自己行程裡的 aos-loop**（`cpp/aos-loop/src/engine/window.cpp:191` 的 `read_ctl`）。
   - 回音走 `state_flux.json` 的 `ctl_seq`、`ctl_warning`、`responded_at`。
   - 手寫要換 `seq`，否則 daemon 會把它標成 stuck（`cpp/aos-daemon/docs/04-…md` 判卡住那節，讀到的）。
2. **daemon 的信箱 `procs_requests/`**（改名單、`stop/start/sleep/wake`、`ping`、`procs_state_path`）：
   - body 是 JSON 物件，只認 `procs_added`、`procs_removed`、`procs_stopped`、`procs_started`、`procs_slept`、`procs_woken`、`ping`、`procs_state_path`（`cpp/aos-daemon/docs/05-信箱.md`）。
   - 讀它的是**daemon 每圈**。daemon 收到 stop 後，替那個 proc 寫它的 `ctl.json`（`knowledge/aos/cli/daemon.md`「stop, sleep, pause, rm」：「stop writes the proc's ctl window and waits for exit (no SIGTERM fallback)」）。
   - sleep、rm、收工才送 SIGTERM（同段）。
3. 加一層：`$AOS_KERNEL` 設了，`aos-agent ctl` 會把信寄給 kernel（`knowledge/aos/kernel.md`「Where to send requests」），不直寄 daemon。
4. 還有一條「門鈴」：`aos-daemon-ctl poke` 用 pidfd 對 daemon 送 SIGRTMIN+n（`py/aos/daemon_ctl/poke.py:34-90`）。這是 pid 例外。

### 1.4 daemon 怎麼知道 proc 活著（現行規則）

- N-17：判死活只剩 daemon 自己，用 pid＋`started_at_ticks`＋`boot_id` 對 `/proc`；別人不碰 pid，讀上一層的表或寄信，沒回＝呼叫失敗（`docs/NORMS/05-基礎設施-窗/06-N-17/01-誰判死活與例外.md:3-4`，讀到的）。
- 程式裡：daemon 是子行程的父，用 `fork`＋`waitpid` 得知結束（`cpp/aos-daemon/src/child/child.cpp:153`、`:316`）。
- `stuck`：只在父 daemon 的表上標；條件是子的 `ctl.json` mtime 比子 `state_flux.responded_at` 新、且超過 `stuck_after_*`（`cpp/aos-daemon/docs/04-…md` 判卡住節）。預設不判（`stuck_after_*` 沒寫＝0）。

---

## 二、綁死本機／daemon 的地方清單

分五類。每條是「假設什麼」＋出處。這些我都是**讀到的程式**，沒實跑。

### A. 假設 proc 是 daemon 起的（父子關係）

1. **表上的列只能由 daemon 起出來。** 一列有 `launch`（重放入口），`start`／`wake`／`adopt` 都照它重起。`cpp/aos-daemon/src/daemon/adopt.cpp:210`（讀 `launch`）；`cpp/aos-daemon/docs/04-…md`「每列另存 `launch`」。**沒有「只登記、不起」的列。**
2. **daemon 是父，用 `fork`／`waitpid` 收屍。** `cpp/aos-daemon/src/child/child.cpp:153`（fork）、`:316`（waitpid WNOHANG）。外來行程不是它的子，拿不到結束碼。
3. **子行程環境由 daemon 設。** `child.cpp:52`（`setsid`）、`:53`（stdin/stdout 接 `/dev/null`）、`:88-89`（`setenv AOS_STACK`、`AOS_DAEMON`）。proc 靠這兩個環境變數知道「我的 stack」「我的 daemon」。
4. **proc 的 stderr 是 daemon 接到 `stderr.txt`。** 表上的 `reason` 就是從這檔最後一行取的（`cpp/aos-daemon/docs/08-…md:27-28`）。外來行程的錯誤不會自動成為 `reason`。
5. **`loop.json` 是 daemon 寫的。** `aos-daemon-ctl` 反過來讀它找 ctl 檔名：`py/aos/daemon_ctl/ctl.py:18-25`、`base.py:5`。外來行程沒有 `loop.json`，就只能用預設 `ctl.json`、`state_flux.json`。
6. **在 cgroup、setrlimit、subuid 裡跑。** `cpp/aos-daemon/src/child/cgroup.cpp`、`limits.cpp`、`subuid.cpp`。這些都是 daemon 起子行程時才做得到的事。
7. **kill：** `cpp/aos-daemon/src/daemon/tend.cpp:117`（`kill(c.pid, SIGTERM)`）、`:168`（`cgroup_kill`）。要有 pid、要在同機、要有權限。
8. **「同一個 stack 只准一個 daemon」靠 flock 資料夾。** `cpp/aos-daemon/src/daemon/daemon.cpp:262-276`（`check_running`，`flock(fd, LOCK_EX|LOCK_NB)`）。flock 只在本機檔案系統有意義，在 NFS／某些 FUSE 上不可靠（推測）。

### B. 假設 proc 在本機、能看 /proc

9. **adopt 用 pid＋ticks＋boot_id 對 /proc。** `cpp/aos-daemon/src/daemon/adopt.cpp:99-120`（`live_in_cell`）、`:197-199`、`:278-281`。
10. **`same_tree` 讀 `/proc/<pid>/environ` 看 `AOS_STACK`／`AOS_DAEMON`。** `adopt.cpp:57-59`。這是為了分辨「`cp -a` 過來的另一棵樹」。讀不到（權限）就當「是」。
11. **`/proc/sys/kernel/random/boot_id`。** `cpp/aos-util/src/proc.cpp:138`；Python 側 `py/aos/daemon_ctl/poke.py:51`、`py/aos/sweep_proc.py:35`。boot_id 本來就是「這台機器這次開機」的概念，換機器就沒意義。
12. **poke：pidfd。** `py/aos/daemon_ctl/poke.py:34-36`（讀 `/proc/<pid>/stat`）、`:83`（`os.pidfd_open`）、`:90`（`pidfd_send_signal`）。跨帳號／沙箱送不出去就 `PokeFailed`，不改走別條路（N-17「例外一」）。
13. **`aos-daemon-ctl shutdown` 靠 `check_alive` 對 /proc 等 daemon 退。** `py/aos/daemon_ctl/ctl.py:125-160`、`poke.py:41-68`。
14. **寄信前先核 daemon 活著沒。** `py/aos/apps/agent/ctl/shared.py:73-86`（`daemon_up`）；另 `:65-70` `nested_pid_ns` 讀 `/proc/self/ns/pid`，在沙箱的子 pid 命名空間裡就「不核」。
15. **`ls --deep` 對每列的 pid 查 `/proc`。** `py/aos/apps/agent/ctl/ls.py:120-141`（`pid_state`，回 alive／dead／reused…）。
16. **`ctl state` 的 resources 一節走 `/proc/*/stat` 算整個行程樹的記憶體和 cpu。** `py/aos/apps/agent/ctl/state.py:232-262`、`:289`、`:302-305`。
17. **清道夫掃全機 /proc、送訊號。** `py/aos/sweep_proc.py:130-140`（全機 /proc）、`:52-60`（`/proc/<pid>/environ`）。N-17「例外二」。
18. **aos-agent ctl add 預設的 stack 位置假設 `<daemon stack>/procs/<name>/`。** `py/aos/apps/agent/ctl/add.py:37`、`:208`。

### C. 假設「表」是一個本機檔案，路徑從環境變數找

19. **表就是 `<AOS_DAEMON>/procs_state.json`。** 檔名寫死：`py/aos/daemon_table.py:8`（`STATE_FILE`）、`py/aos/daemon_ctl/base.py:2`（`STATE`）、`py/aos/comm/walk.py:11`、`:16-17`（`is_daemon`：「stack 裡有 `procs_state.json` 就是 daemon」）。
20. **daemon 從 `AOS_DAEMON` 環境變數（本機路徑）找。** `py/aos/daemon_table.py:72-86`（`daemon_folder`）；`py/aos/daemon_ctl/table.py:14-30`（`find_daemon`：`--daemon` ＞ `$AOS_DAEMON` ＞ `./.stack`）。使用者 11-05 說過「環境變數是預設管道、不是唯一」（`thinking/2026-11/05/no-pid/README.md` 定下的第 5 條），但**現有程式裡的替代管道是 `--daemon D`，D 一樣是本機資料夾**。
21. **走 kernel 時，表的位置是「寄信問來的絕對路徑」。** `knowledge/aos/kernel.md`「Reading the table through the kernel」：回信 `{"procs_state_path": "/abs/path/procs_state.json"}`；`py/aos/daemon_ctl/state_path.py:87`。問來的還是**本機檔案路徑**，讀的方式還是開檔。
22. **表分檔 `{"$ref": [...]}`、相對路徑從表所在資料夾算。** `py/aos/daemon_table.py:35-53`、`py/aos/daemon_ctl/table.py:51-60`。
23. **proc 的 stack 位置從表上那列的 `stack` 取。** `py/aos/daemon_ctl/table.py:123-130`（`cell_of`，註解寫「拿 stack 只在這裡」）。所有 ctl／state 路徑都由它拼。**proc 的檔案佈局被視為「在一個本機資料夾裡」**。
24. **`ctl who` 靠「$AOS_STACK 落在表上哪一列的 stack 裡」認身分。** `py/aos/apps/agent/ctl/who.py:35-46`、`py/aos/daemon_table.py:108-120`（`definition`）。不在表上的行程＝`InstanceMissing`。
25. **`mailbox send --to NAME`：名字→表→那列的 stack 是不是本機資料夾→`<stack>/mailbox`。** `py/aos/apps/mailbox/__init__.py:339-347`。`--box PATH` 只要求 `tmp/ new/ cur/` 三個資料夾（`:325-337`），這條最接近「界面」。
26. **信箱原子性靠同檔案系統的 rename。** `cpp/aos-util/src/files.cpp:4-6`、`:130`（「暫存檔放在同一個資料夾，才保證在同一個檔案系統上」）；`py/aos/daemon_ctl/post.py:80`（`os.rename`）。N-14 寫「原子性只靠 rename」。
27. **鎖：mkdir 掛牌＋flock 判主人死活。** `docs/NORMS/05-基礎設施-窗/04-N-15.md`；`cpp/aos-lock/src/holder/holder.cpp:91`、`cpp/aos-lock/src/lock/lock.cpp:216`。flock 判活只在同機有意義。

### D. 假設「檔案變動」能被即時看到、時間在同一台

28. **loop／daemon 是輪詢，每圈看檔。** N-14 寫「等變化輪詢保底、inotify 加速（/mnt/c 上 inotify 會靜默失效）」。**我在 `cpp/*/src` 和 `py/aos` 裡 grep 不到 inotify 的實際使用**（沒找到），所以現況只有輪詢。
29. **stuck 判斷用 ctl 檔的 mtime 對時鐘。** `cpp/aos-daemon/src/daemon/stuck.cpp:42-60`。註解提到時鐘倒退、搬家時鐘差要擋（`:58`）。跨機器（時鐘不同步）會誤判（推測）。
30. **`boot_id` 對不上就整張表的行程都當不在。** `adopt.cpp:197-199`。機器換了這條自然成立，但「遠端 proc 的 boot_id」沒有對應意義。
31. **state 窗帶 poke 欄，假設 SIGRTMIN 號碼在本機有效。** `cpp/aos-daemon/docs/04-…md`「poke 門鈴」。

### E. 路徑／環境本身

32. **loop 要開窗卻沒 `AOS_STACK`＝`StackMissing`。** `cpp/aos-loop/include/aos/loop.hpp:252`。窗的位置固定在 `$AOS_STACK` 底下（N-14：「強制落在 `$AOS_STACK` 的只有窗」）。
33. **proc 環境裡固定有 `AOS_STACK`、`AOS_DAEMON`、`AOS_WS`。** `child.cpp:88-89`。這是「被 daemon 起」帶來的，外來行程沒有這些（除非自己設）。

---

## 三、外來行程思想實驗（只讀程式碼推，沒起行程）

設定：一支外面的 Linux 行程 X。它自己 `mkdir` 出一個資料夾 S，放了 `ctl.json`、`state.json`、`state_flux.json`，內容格式照 N-06～N-09，也自己讀 `ctl.json`、回 `ctl_seq`。它不是任何 daemon 起的，也不在任何表上。分兩種：X 在同一台機器；X 在遠端（S 是 NFS、FUSE 或遠端掛載）。

| 工具 | X 在本機、不在表上 | 為什麼 | X 在遠端／FUSE |
|---|---|---|---|
| `aos-daemon-ctl ls` | **看不到** | ls 讀 daemon 的表，表上沒有它（`daemon_ctl/table.py:89` `state()`、`:111` `rows()`，列只來自 `procs_state.json`） | 同左 |
| `aos-agent ctl ls`／`who`／`state` | **看不到**；`who` 報 `InstanceMissing` | `who.py:35-46`：S 必須落在某列的 stack 裡 | 同左 |
| `ls --deep`（走表樹） | **看不到** | `walk.py:16-17` 只認「列的 stack 裡有 `procs_state.json`」才往下走 | 同左 |
| `aos-daemon-ctl pause/resume X` | **不能**：先 `row_of(d, name)` 找表（`ctl.py:62-65`），找不到＝`ProcMissing` | 要先有一列、而且 `phase` 是 running／stuck（`ctl.py:66-69`） | 同左 |
| 直接 `echo {"cmd":"pause","seq":N} > S/ctl.json` | **能**（X 讀得到就會照做）；這是現況最接近「界面」的地方 | N-06：「誰能寫 ctl.json 就能控制」 | 能，只要那個檔案系統 rename 可用、X 輪詢它 |
| `aos-daemon-ctl stop/start/sleep/wake/rm X` | **不能** | 這些是寄信給 daemon，daemon 只管自己表上的列（`cpp/aos-daemon/docs/05-信箱.md`），`PHASE_OK` 要表上的 phase（`ctl.py:30-50`） | 不能 |
| daemon 的 stuck 判斷 | **不會判它** | 只判表上「正在跑的列」（`cpp/aos-daemon/docs/04-…md` 判卡住節） | 不會 |
| daemon 的 adopt／重起／`auto_restart` | **不會** | 要有 `launch`；它不是 daemon 起的（A.1） | 不會 |
| `mailbox_send --to X` | **不能** | `--to` 要查表（`mailbox/__init__.py:339-340`） | 不能 |
| `aos-mailbox send --box S/mailbox` | **能**，只要 `S/mailbox` 有 `tmp new cur` | `mailbox/__init__.py:325-337` 只驗三個資料夾；回信、`reply_to` 也只是路徑 | 看檔案系統：rename 要原子、要同一個 fs；跨 fs 的 rename 會失敗（`files.cpp:4-6`） |
| `aos-post send S/mailbox`（C++） | **能** | 同上，aos-post 只要資料夾 | 同上 |
| `ctl state --target X` | **不能** | 同 who | 同左 |
| `ls --deep` 的 `pid` 欄 | 不適用 | 讀的是表上那列的 pid | 即使有 pid，遠端 pid 查本機 `/proc` 是錯的（`ls.py:120-141`），會變 `dead` 或 `reused` |
| 清道夫 | **不會收 X**（讀到的條件，推測不會誤傷） | 它只收「`D/procs/<名>/` 底下、不在表上、state 窗 pid 對得上 /proc、environ 的 `AOS_STACK`＝這格且 `AOS_DAEMON`＝這台」的行程（`sweep_proc.py:1-5`、N-17 例外二）。X 的 S 不在 `D/procs/`，環境也不符 | 不會（它只看本機 /proc） |
| 另一個 aos-loop 把 S 當自己的窗 | 可以：aos-loop 的窗路徑由 `ctl`／`state` key 與 `AOS_STACK` 決定（`loop.hpp:252`），指到 S 就行 | 這是「讓別人用我的窗」，不是「X 當 proc」 | — |

**小結（觀察）：**
- X 提供的那組檔，**「窗」這一側的讀寫（寫 ctl、讀 state）別人可以直接用**；
- **「發現」「列清單」「用名字找」「重起」「卡住判斷」這些全部要先在 daemon 的表上有一列**；
- 所以現在「是不是 aos proc」其實由**表上有沒有那列**決定，不是由有沒有檔案佈局決定。

---

## 四、以前說過什麼（逐字引用＋路徑）

### 4.1 使用者講過的「Plan 9／檔案／界面」

1. 11-05 晚（`thinking/2026-11/05/no-pid/README.md:13`）：
   > 1.aos體系脫胎於plan9，也就是純粹的unix哲學。還記得state.json嗎？我會希望以這個爲主。寄信收信是我們aos的非同步呼叫的底層機制，寄信不回，等同於呼叫失敗，……記住，所有牽涉到linux原生行程的機制，都以daemon爲界面，而daemon所擔任的，就是橋梁，並且盡量將各類東西暴露爲檔案。
2. 11-06（`docs/CONCEPTS/01-設計理念/09-C-83.md`，C-83 ②）：
   > 這些linux原生的各種特性，都必須在daemon之下，由daemon做介面
   隨即改口「剛剛這句可以的話，改成"建議"」。C-83 的結論：「**可遷移性是上位原則；經 daemon 是建議手段**」，並寫「no-pid 那批不放寬」：「N-17 判活只剩 daemon、別人不碰 pid、ctl 寄信、aos-lock 改檔案鎖（T2）照舊」。
3. 10-14（`thinking/2026-10/14/json-entry/02-原文-1i至1q.md:7`）：
   > state.json/ctl.json這塊，我會覺得，它本質上是程式內部狀態的外顯，有點plan 9 fuse的感覺，會在參數(stdin)中指定其狀態外顯，要放在哪裡。
   → 落成 N-13（1.1）。同批裁定「FUSE 可選，用了更舒服，以後再說」（`thinking/2026-10/14/json-entry/03-決定未決.md:24`）。
4. 10-30（`thinking/2026-10/30/map-review/01-使用者原文.md:5`）：
   > 程式之間說話的方式，感覺還有一種，就是純粹的寫檔案、讀檔案，途中可以設置串流，這就是plan 9那種方式。這一塊我們aos好像沒有用到，之後可以考慮。
   結論「開著」，11-12 使用者裁「poke 就夠、其餘以後再說」（`thinking/2026-10/30/map-review/02-結論.md:7`；`thinking/2026-11/12/small-rulings.md:27` Q11）。
5. 10-11 第二輪口述（`thinking/2026-10/11/restart/03-補充與第二輪口述.md:14`）：
   > 說到外部設備，資料庫／硬碟／快取／記憶體／雲端那塊，也可以被納入所謂空間的定義中，好比 Plan 9。
   → C-30、C-37「空間照 Plan 9」（`docs/CONCEPTS/附錄1-名詞/01-aos到agent.md:15`；`thinking/2026-11/06/os-concepts/06-很多核-對照表.md:35`：「Plan 9 CPU server｜`AOS_DAEMON`＝stack＝『那台機器』；跨樹寄信＝另一台 server」）。
6. 11-10（`thinking/2026-11/10/two-machines/README.md:37`）：
   > 知識庫這東西不用想太多，他就是一個資料夾，這個資料夾可能是git repo也可能不是。甚至搞不好他是透過plan 9偽裝成資料夾的東西
   （講知識庫，不是 proc。）
7. 11-13（`thinking/2026-11/13/any-resource-os/00-使用者原話.md:31`）：
   > 之後如果有人像在lisp/lua內開發，然後用plan9方式接入aos，那也是好事。
   計劃把它記成「遠期方向，不排」（`thinking/2026-11/13/any-resource-os/04-實作計劃.md:113`）。
8. 11-21（`thinking/2026-11/21/kernel-宣告進interfaces-1121/07-對外與對內.md:7`）：
   > kernel那塊，界面有分對外與對內，interfaces.json中當然兩者都可以有，只是說未來，對外的界面宣告的json，需要另外準備一份，用於讓他人存取
   （這是 kernel 的 `interfaces.json` 宣告，跟 proc 的檔案佈局是兩件事，但同一個「界面」詞。）
9. 11-24（`wf/user/advice/20261124.md:36-39`，見檔頭）：這次的話。

### 4.2 以前被討論過、但沒做的「把 proc 映成檔案」

`thinking/2026-11/09/daemon-interrupt/`：使用者 11-09 問中斷時自己提了三條路（訊號／socket／plan9）。
- 第三條原話（`thinking/2026-11/09/daemon-interrupt/README.md:7`）：「第三種是走plan9路線，將/proc映射過去」。
- 當時的分析（`02-三條路.md:38-53`）：「daemon 自己當一個合成檔案系統（FUSE）：掛 `$AOS_DAEMON/live/`，裡面 `ctl`、`state`、`procs/<名>/ctl`……」；也列了 9P server、延遲、卡住時所有碰 `live/` 的人一起卡、`user_allow_other` 要 root。
- 結論（`04-方向題與結論.md:8`）：「②Unix socket 先做……③排後，等『proc 連函式庫都不要、只寫一個路徑』的需求真的出現再做」。
- 使用者實際選的（`README.md:30`）：選了訊號、做 `aos-daemon-ctl poke`；③「留在本檔當已規劃未做」（`04-…md` 末）。
- **所以 FUSE／9P 做成「daemon 對外的檔案介面」曾被規劃過，沒實作。**

### 4.3 「遠端」「網路上」「跨機」

- NORMS／概念層：我 grep `proto8/docs/NORMS`、`proto8/docs/CONCEPTS` 的「遠端、網路上、remote、ssh」，**沒找到**講 proc 在遠端的條文。
- 兩台機器（`thinking/2026-11/10/two-machines/`）是「同一批 agent 靠 git 輪流在兩台跑」，**不是同時跨機**。每台各自一棵樹（`AGENTS.md` 開發環境一節也寫 stack 每台各有各的）。
- 手機看板（`thinking/2026-11/08/forum/README.md:15`）：「artifact 是純界面，本機是源頭」。那是論壇，不是 proc。
- 9P 的提及：`thinking/2026-11/10/two-machines/07-知識庫接點.md:51`：「工具層不為了 9P 重寫」（講知識庫的鎖在 9P 掛載上要寫進說明）。
- `thinking/2026-11/18/linux-as-hw-1118/03-別人怎麼做.md:38-42`：Plan 9「所有資源……都是說 9P 協定的檔案伺服器」；「跟 aos 的距離：C-30、C-37 早就定了」。`05-發想.md:39` 的「丁：權限＝遞給你的夾（Plan 9／Fuchsia 式）」。這是安全面的發想，沒有決定。

### 4.4 外部 agent 當 proc

- `thinking/2026-10/30/map-review/02-結論.md:7`（結論 3）：外部 coding agent 跟 aos agent 平級；共同點＝queue／history／ctl 三樣；外部 agent＝aos-loop 包 `lib/eca/turn`。
- 這是「用 aos-loop 把外部程式包成 proc」的路，不是「外部程式自己提供佈局」的路。

### 4.5 規範裡已有、跟使用者現在說法方向一致的句子

- `docs/NORMS/05-基礎設施-窗/06-N-17/01-誰判死活與例外.md:3` 的「只有 aos-daemon 與這支指令懂訊號，proc 與其他 aos 程式只寫檔」。
- 同夾 `02-phase與stuck.md`：判 stuck「對任何有公開 ctl／state_flux 窗的 proc 都判；父讀的是子 ctl 與子 state_flux」。使用者 11-06 晚：「子daemon管好自己，父daemon只看他有沒有活着，子daemon的其他東西父daemon別碰。盡量解耦合。」（同夾引的 `thinking/2026-11/05/no-pid/17-P7實作結果.md`）。
- `cpp/aos-daemon/README.md`「P7」：「父只看公開 ctl／state_flux 窗判卡住，任何有窗的 proc 都能用」。
- 這幾句讀起來是「父不認子是什麼，只認那幾個檔」。這是現有程式裡最像使用者新說法的地方。

---

## 五、差距（只列事實，不給方案）

對照使用者 11-24 那句，現況有這些落差：

1. **定義**：使用者說「提供檔案佈局就是 aos proc」；現況是「在 daemon 表上有一列＝proc」（1.1）。檔案佈局只是「窗」的規範，沒當成 proc 的定義。
2. **誰能進表**：只有 daemon 自己起的才進得去（A.1、A.2）。沒有「登記一個外面已存在的佈局」的入口。
3. **「佈局」本身沒有一份寫死的清單**：ctl、state、state_flux 的名字、欄位散在 N-06～N-14、`loop.hpp:54-91`、daemon 文件。沒找到「proc 界面」單一一頁規格。`interfaces.json` 是「資料夾宣告它遵守哪些介面」（`docs/NORMS/命名-續-概念搬來的檔名/01-入口-metainfo-介面-血緣.md:26-29`），現有的介面名像 `aos-agent`、`aos-ledger`、`aos-observed`，沒有 `aos-proc`（我沒找到）。
4. **名詞 status vs state**：使用者說 `ctl/status`；現況檔名是 `ctl.json`／`state.json`／`state_flux.json`。`status` 可能只是舉例（推測）。
5. **窗的位置**：固定在 `$AOS_STACK` 底下，由 daemon 的環境變數交給 proc（C.20、E.32、E.33）。外來行程沒有這個入口。
6. **「發現」只有表**：`ls`、`who`、`mailbox --to`、`ls --deep` 全走表（第三節）。`mailbox --box PATH` 是唯一「給一個資料夾就能用」的口。
7. **判死活**：規範寫「不碰 pid、用寄信問」，但實作裡「daemon 對自己的子」全靠 pid（A.2、B.9–B.13）。對一個非自己起的、或遠端的 proc，現有機制沒有對應的活著判斷（沒找到）。唯一不靠 pid 的是 `state_flux.responded_at` 和 `ctl_seq`，但只用在 stuck，而且 stuck 預設關。
8. **位置假設是本機檔案系統**：rename 原子（C.26）、flock（A.8、C.27）、mtime（D.29）、輪詢（D.28）。「不管你在硬碟、/tmp、FUSE 都可以，哪怕是網路上也行」這句，對 /tmp 與一般本機硬碟程式成立；對 FUSE、網路，N-14 自己提過「/mnt/c 上 inotify 會靜默失效」，`thinking/2026-11/09/daemon-interrupt/03-衝突與邊緣.md:28` 提過 drvfs／9p 上 AF_UNIX socket 建不起來、inotify 收不到。
9. **aos-loop 與 daemon 的關係**：N-13 寫「aos-loop、aos-daemon 照做，`src/engine/window.cpp`」；窗的程式碼是 aos-loop 的一部分（`loop.hpp` 公開 `CtlWindow`／`StateWindow`），daemon 繼承 `aos::loop::Loop`（`cpp/aos-daemon/README.md`）。所以「窗」目前是**一份 C++ 實作**，沒有獨立於實作的協議文件（推測）。Python 側各自重寫了一份讀寫（`py/aos/daemon_ctl/ctl.py:107-120` 的 `put_ctl`、`py/aos/flags.py` 的 `read_window`），格式靠大家照著寫。

---

## 六、已知的缺點與沒解的問題

文件或程式裡自己承認的，加上我讀到時注意到的（標「觀察」）。

**文件承認的：**
1. N-13 自己寫：「新舊打架，11-17『新的覆蓋舊的』：N-14『內容是 JSON』10-29 較晚」（`docs/NORMS/05-基礎設施-窗/03-N-13～N-14.md`）。窗是不是 JSON 有過來回。
2. 「窗不自述種類」：state 不帶 `kind`（N-14，使用者 11-02「kind沒人在用，那就拿掉」）。所以**外面只看一份 state 檔，無法知道它是 loop、daemon 還是別的**。要判必須靠位置或旁邊的檔。（觀察：這跟「提供佈局就是 proc」之間的關係沒有討論過。）
3. 判死活沒有心跳、也不從 mtime 判（N-17，使用者 11-02）。被 `kill -9` 的程式它的 state 會停在 `running`，「別人從它自己的窗看不出死活，寄信沒回＝這次呼叫失敗」（N-17 `02-phase與stuck.md`「被 SIGKILL」）。
4. 外來行程被 daemon 當「別棵樹的」跳過的邊角：`same_tree` 讀不到 environ（權限）就當「是」（`adopt.cpp:57-59`）；`cpp/aos-daemon/docs/08-…md:12`。
5. daemon 的 `stop` 沒有時間上限，卡住的 proc 要改 `sleep`（TERM／KILL）（`08-…md:39`）。
6. `stuck` 預設關（11-15 改），手寫 ctl 要換 `seq`（`04-…md`）。要判卡住就要開 `state_flux`，關了就丟了監看。
7. 表很大時每拍 CPU 跟列數成正比（`08-…md:35`）。
8. 鎖與 flock 命名分兩種（`.lock` 資料夾、`.flock` 檔）；flock 在網路檔案系統上的行為，文件沒寫（沒找到）。
9. FUSE 的坑已寫在 `daemon-interrupt/02-三條路.md:48-53`、`03-衝突與邊緣.md:37`：FUSE 請求會把呼叫者卡到 daemon 回應為止；殭屍掛載卡 `ls`、`git add`；跨帳號要 `user_allow_other`（要 root）；沒有 `/dev/fuse` 的環境要退回。
10. 信箱「一個信箱預設一個處理者」、`tmp/` 殘骸處理者不碰（N-16）。

**觀察（讀程式時注意到，沒人說過）：**
11. 「ctl 到底由誰讀」在規範裡其實有兩種：proc 自己的 aos-loop 讀，與 daemon 的 `procs_ctl.json`／信箱（1.3）。外來行程若要當 proc，要實作的是**前者**（ctl.json＋state_flux 回音）；若還要被 daemon 管，還要**後者**的對手方（被起、被收屍）。兩者的邊界目前沒有一頁寫清楚。
12. `aos-daemon-ctl pause/resume` 是**直接寫 proc 的 ctl.json**（`ctl.py:60-75`），不需要 daemon 在跑，只需要表上有那列；`stop/start/sleep/wake` 則必須 daemon 在跑（寄信）。同一個「ctl」詞下行為不一致。
13. 表上每列的 `pid`、`started_at_ticks` 是 daemon 記的，`state.json` 裡 aos-loop 也自己記一份（`window.cpp:62-65`）。外來行程如果自己寫 state.json，這兩欄要它自己誠實填；daemon 的 adopt 會拿它去對 /proc（`adopt.cpp:99-120`）。沒有地方驗「這份 state 是不是這個行程寫的」。
14. 使用者 11-24 這句話與 11-05「所有牽涉到linux原生行程的機制，都以daemon爲界面」在字面上是兩個方向：前者的「界面」是**proc 提供的檔案佈局**，後者的「界面」是**daemon 提供給別人的橋**。C-83 已把後者降成「建議」（4.1 第 2 條），但程式與 N-17 還是照後者實作。這是事實的並列，我不下判斷。
15. `aos ps` 沒有：沒有一個不經 daemon 表、只看「某幾個資料夾有沒有那組檔」的列表指令。`py/aos/comm/walk.py` 的 `walk()` 是走表的樹，不是掃資料夾。

---

## 附：我讀過的主要檔（方便回查）

- `proto8/cpp/aos-daemon/README.md`、`docs/02`、`04`、`05`、`08`；`src/daemon/{adopt,daemon,tend,stuck}.cpp`；`src/child/child.cpp`
- `proto8/cpp/aos-loop/README.md`、`include/aos/loop.hpp`、`src/engine/window.cpp`
- `proto8/py/aos/daemon_table.py`、`daemon_ctl/{base,ctl,table,poke,post,state_path}.py`、`apps/agent/ctl/{ls,who,shared,state}.py`、`apps/mailbox/__init__.py`、`comm/walk.py`、`sweep_proc.py`
- `proto8/docs/NORMS/04-…loop與daemon.md`、`05-…窗/*`、`proto8/docs/CONCEPTS/01-設計理念/09-C-83.md`、`附錄1-名詞/*`
- `proto8/knowledge/aos/{_description,kernel,me,status,mailbox}.md`、`cli/daemon.md`
- `proto8/thinking/2026-11/05/no-pid/`、`2026-11/09/daemon-interrupt/`、`2026-11/10/two-machines/README.md`、`2026-10/30/map-review/`、`2026-10/14/json-entry/`
- `wf/user/advice/20261124.md`
