aos-loop 今天讀寫哪些檔、ctl 與回音怎麼運作（讀程式加實測），對到「9P 的 aos proc 介面」哪些是活的身體、哪些要留、最小要動哪裡：現有的 loop、daemon、kernel、agent 外框都是同一份骨架，改一個檔就全部跟上；最難的一題是「寫回來＝收到」。

# 01　aos-loop 現況，與它對到新模型要動哪裡

← [架構規劃入口](../README.md)

寫的人：這批的 01 號子 agent（11-25 中午，公司 WSL）。只讀程式與活樹，沒改任何既有的檔。實驗只在 `~/.aos/scratch/aos-proc-arch-1125/01/` 跑，用的是 `proto8/bin/aos-loop`（11-25 09:44 建的那支），跑完沒有留行程。

三種話怎麼分：寫「使用者」加引號＝他的原話；帶 `檔名:行號` 或寫「實測」＝查到的；標「推論」＝我推的，沒有人說過。

路徑縮寫（只在本檔用）：`L/`＝`proto8/cpp/aos-loop/`，`D/`＝`proto8/cpp/aos-daemon/`，`P/`＝`proto8/py/aos/`。「身體」在第 2 節指 aos-loop 每一圈跑的那支程式（設定檔的 `exec`）；第 3 節起照使用者的新說法，指一隻活著的 proc 的目錄。

## 1. 結論

1. **改一個檔，全家跟上。** 現在會一直跑的 proc，外框都是同一份 C++ 骨架 `aos::loop::Loop`：aos-loop 直接用，aos-daemon 繼承它，agent、kernel、時鐘、清道夫都包在裡面。ctl 與 state 的讀寫全在 `L/src/engine/window.cpp`。
2. **今天的回音其實是「做了」，不是「收到」。** ctl 是一個 JSON 檔，loop 只在兩圈之間讀。實測回音：閒著 0.07～0.88 秒；身體在跑要等它跑完（3 秒的身體等了 2.53 秒）；stop 的回音排在 on_stop 後面，跟行程結束同時到（2.87 秒）。
3. **兩個人同時寫 ctl，檔不會壞，但會丟、會誤報。** 同一個讀取空檔裡先寫的那道直接消失；兩人算出同一個 seq 時，被蓋掉的人會看到回音、以為自己成功（實測重現）。
4. **aos-loop 自己不換目錄，站哪裡看誰起它。** 活樹上有三種：loop 站自己的小格；loop 站定義夾；表上的 pid 是一支監工（站小格），真正的 loop 是它的子（站定義夾），兩支同生共死，agent 多半是這種。`/proc/<PID>/cwd` 這招對第一種今天就通（實測）。
5. **aos-loop 自己要跨重起留的只有兩樣**：`paused`、最後一道 ctl 的號碼。其餘都是活的身體。判活三欄、seq 與回音、暫存檔、壞窗留證，都是「檔會活得比行程久」才需要的。
6. **最小改動四處，都能跟現有的 json 窗並存**：站進自己的身體、多寫一份文字 `status`、ctl 也收純文字、起來時寫 `settings`。json 窗不要急著拿掉：程式裡還有 29 個非測試檔提到 `state.json`。
7. **「寫回來＝收到」純檔案做不到，查到八種做法**（3.4），從零改動到自己當檔案伺服器。今天的執行檔把 ctl 直接換成 FIFO 會卡死，SIGTERM 也收不掉（實測）。
8. **繞不過去的一點：aos-loop 是單執行緒。** 身體在跑時它在等身體，不讀 ctl。要「當場回收到」，得在三個等待的地方加一個聽的口（其中一個在 aos-exec 裡），或由 daemon 這座橋代答。
9. **aos-loop 活著的只有外框。** 它的身體是一圈一支的短命行程，所以「活著走 unix socket」送進來的訊息，還是得落檔等下一圈的身體來拿。

## 2. 查到的事實

### 2.1 aos-loop 是什麼，誰建在它上面

- `aos-loop loop.json`：一次次跑設定檔裡的 `exec`，看它的結束碼決定下一步（`L/README.md:5`）。
- 骨架是類別 `aos::loop::Loop`，aos-daemon 繼承它（`L/README.md:21`、`D/src/daemon/daemon.hpp:155-162`）。所以 daemon 自己的 `ctl.json`／`state.json`／`state_flux.json` 是同一段程式在讀寫。
- 三扇窗的檔名、欄位名、指令字只定義一次：`L/include/aos/loop.hpp:52-78`。
- agent 與 kernel 的範本外框都是 aos-loop（`proto8/templates/agents/*/loop.json`、`proto8/templates/kernels/*/loop.json`）；活樹的時鐘、清道夫也是（`~/aos-home/.stack/procs/repo-aos/procs/_sweeper/loop.json`）。
- 規範早就把窗說成 Plan 9 式的東西：N-13「state／ctl＝程式內部狀態的外顯（程式願意分享給大家的，像 Plan 9／FUSE）」（`proto8/docs/NORMS/05-基礎設施-窗/03-N-13～N-14.md:5`）。

### 2.2 它讀寫的檔

都在 `$AOS_STACK` 底下。三扇窗的檔名可以用設定鍵 `ctl`／`state`／`state_flux` 或同名旗標改，寫 `null`＝不開（`L/src/engine/config.cpp:296-312`）。

| 檔（預設名） | 格式 | 誰寫 | 誰讀 | 怎麼寫 | 多久一次 |
|---|---|---|---|---|---|
| `ctl.json` 指令 | 一個 JSON 物件：`cmd`、`max`、`interval_ms`、`seq`，都選填；可以含 `$ref`／`$env` | 誰都能寫：daemon（`D/src/daemon/tend.cpp:120-137` 寫 stop、`reconcile.cpp:173-186` 重起前清舊 stop）、`aos-daemon-ctl` 與 `aos-agent ctl` 的 pause／resume（`P/daemon_ctl/ctl.py:63-75`）、清道夫（`P/sweep_proc.py:328-329`）、gdb、人手 | loop 自己（`window.cpp:191-262`）。父 daemon 只看它的修改時間（`D/src/daemon/stuck.cpp:40-47`） | 寫的程式都是先寫 `.ctl.json.<pid>.tmp` 再改名；loop 不刪不改 | 每圈開頭整檔讀進來比內容，不看修改時間。睡覺最多 1 秒就醒來讀。身體在跑時不讀 |
| `state.json` 我現在怎樣 | 一行 JSON：`phase`、`max`、`interval_ms`、`paused`、結束時多 `code`、`pid`、`started_at_ticks`、`boot_id`、`updated_at` | 只有 loop 自己（`window.cpp:322-353`） | 見表下 | 先寫 `.state.json.<pid>.tmp` 再改名，不 fsync（`proto8/cpp/aos-util/include/aos/util/files.hpp:42`） | 有變才寫。起來第一份、結束那份一定寫；`running` 與 `waiting` 互換不算變 |
| `state_flux.json` 我聽到了什麼 | 一行 JSON：`responded_at`、`ctl_seq`、`ctl_warning` | 只有 loop 自己（`window.cpp:355-377`） | 下指令的工具等 `ctl_seq`（`ctl.py:164-179`）；父 daemon 讀 `responded_at`（`stuck.cpp:41-57`）；loop 起來時接回 `ctl_seq`；gdb | 同上，排在 state 後面寫 | 第一份必寫，之後整份有變才寫（＝處理了一道新 ctl） |
| `counter_runs.txt` | 十進位整數加換行 | loop；要給 `--enable-counters`（`window.cpp:379-394`） | 給人看，程式不讀 | 暫存再改名 | 每跑一次身體之前 |
| `stop_cause.json` | JSON：`cause`、`pid`、`started_at_ticks`、`at_ticks`、`boot_id` | 父 daemon，送 SIGTERM 之前（`tend.cpp:81-108`） | loop 因為 SIGTERM 收工、而且有 `on_stop` 時才讀（`loop.cpp:89-94`、`window.cpp:88-130`、`L/src/engine/points.cpp:84-90`） | 暫存再改名，誰都不刪 | 一次啟動最多一次 |
| `<窗名>.bad-<時間>` | 壞掉的舊窗原樣 | loop 起來時把讀不了的舊窗改名留證（`window.cpp:265-290`） | 人 | 改名，不覆蓋 | 只在起來時 |
| `loop.json` 設定 | JSON | 定義的作者；或父 daemon 寫進小格 | loop 起來時讀一次。daemon、`aos-daemon-ctl`、清道夫讀小格那份找窗的檔名（`ctl.py:18-25`、`stuck.cpp:30-33`、`P/sweep_proc.py:156-169`） | — | 一次 |
| `stderr.txt` | 文字行 | 父 daemon 把子行程的 stderr 接過去（`D/src/child/child.cpp:52-61`） | daemon 取最後一行當表上的 reason | 附加 | 出錯時 |

讀 `state.json` 的不只 daemon。查到的：

- daemon 接回時核 `pid`＋`started_at_ticks`＋`boot_id`（`D/src/daemon/adopt.cpp:96-121`）。
- 拿那三欄當「這是哪一次啟動」的記號：閘 `proto8/cpp/aos-idle/src/idle/idle.cpp:48-58`（別人正在寫，沒交件）、`P/agentlib/hook_clock.py:82-88`、`P/agentlib/cli_linger.py:64-66`、`P/apps/agent_fsm/wait.py:222-229`。
- 看 `paused`：`P/apps/agent/hints.py:12-36`（連停著的那隻也讀，看它起來會不會先暫停）、`P/gdb/__init__.py:519-529`。
- loop 自己起來時接回 `paused`（`window.cpp:292-298`）。
- 數量：`proto8` 的 cpp、py、templates、frontend 裡，提到 `state.json`（不含 `procs_state.json` 這類）的程式檔 87 個，其中非測試 29 個；`ctl.json` 44 個（非測試 16）；`state_flux.json` 29 個（非測試 15）。（`grep -rlE '(^|[^_A-Za-z])state\.json'`，11-25。）

五個掛程式的點不是檔，是 loop 替你跑的小程式（`L/docs/01-用法.md:28-84`）：

| 點 | 什麼時候跑 | 期限 | 回的碼 | 多給的環境變數 |
|---|---|---|---|---|
| `on_start` | 第一圈之前一次 | `on_timeout_ms`，預設 5000 | 非 0＝收工 | — |
| `gate`（閘） | 每圈要跑身體之前，最先問 | `gate_timeout_ms`，預設 1000 | 10＝這拍跳過；0＝跑；其他＝印一行提醒、照跑 | — |
| `on_before_run` | 閘之後、身體之前 | 不限 | 10＝跳過這圈；其他非 0＝收工 | `AOS_LOOP_RUNS` |
| `on_after_run` | 身體之後 | 不限 | 身體是 0 而它非 0＝收工 | 上面那個，加 `AOS_LOOP_RUN_CODE`、`AOS_LOOP_RUN_SIGNAL`、`AOS_LOOP_RUN_MS` |
| `on_stop` | 要退時一次，在最後一份 state 之前 | `on_timeout_ms` | 本來要退 0 而它非 0＝改退它的碼 | `AOS_LOOP_CODE`、`AOS_LOOP_SIGNAL`、`AOS_LOOP_CAUSE` |

### 2.3 ctl 收哪些字、怎麼認新舊、seq 怎麼對上

- **字只有三個**：`pause`、`resume`、`stop`。其他字整份拒用（`window.cpp:173-178`）。沒有 sleep：daemon 的 sleep、rm、收工走 SIGTERM（`L/docs/02-窗.md:47`）。
- **兩個數字**：`max`、`interval_ms`。寫數字＝從現在起用它；寫 `null`＝回設定檔的值；沒寫＝不動。
- **`seq`**：非負整數，只拿來回音。同一道裡 stop 壓過其他。不認得的鍵當沒看到。
- **新舊比內容**：把解完的整份轉成字串，跟上一次讀到的比（`window.cpp:229-235`）。不比 seq、不比修改時間。同內容再寫一次不算新的，也不回應。
- **壞的整份拒用**（不是 JSON、型別錯、不認得的字、指示詞解不開）：原因寫進 `ctl_warning`，`responded_at` 照更新，`ctl_seq` 不動。實測 F：寫純文字 `stop` 進去，得到 `"ctl_warning": "ctl: cannot read or not JSON: …/ctl.json"`，loop 照跑。
- **起來第一次讀**：seq 跟舊 `state_flux.json` 的 `ctl_seq` 一樣＝做過了，略過；其他照做（`window.cpp:236-238`）。所以行程不在時寫進去的 pause／stop，起來那一刻就生效。daemon 重起一列之前會先把舊 stop 的 `cmd` 拿掉（`reconcile.cpp:173-186`）。
- **seq 誰配**：寫的人自己配。`aos-daemon-ctl`＝「ctl 現有的 seq」與「state_flux 的 ctl_seq」取大的加一（`ctl.py:100-104`），讀完到寫之間沒有鎖。daemon 寫 stop 時是「ctl 現有的 seq」與「自己記的數」取大的加一（`tend.cpp:125-130`）。
- **怎麼等回音**：寫完每 50 毫秒讀一次 `state_flux.json`，等 `ctl_seq` 等於自己那號；預設等 5 秒，等不到印一行提醒、退 0（`ctl.py:60`、`ctl.py:164-179`）。

### 2.4 一圈的順序，與 ctl 生效的時點

照 `L/src/engine/loop.cpp:124-238`：

```
① 有訊號排著 → 收工（128＋訊號號碼）
② 讀 ctl                                              ← 讀取點 1
③ stop 過 → 跑 on_stop → 寫最後一份 state → 寫回音 → 退 0
④ 跑滿 max → 一樣收工
⑤ 暫停中，或還沒到時間 → 寫 state → 寫回音 → 睡（最多 1 秒）→ 回 ①
⑥ 有閘：跑閘。10＝跳過、回 ①；0＝再讀一次 ctl          ← 讀取點 2
⑦ 有 on_before_run：跑它。0＝再讀一次 ctl              ← 讀取點 3
⑧ 次數加一 → 寫 state（running）→ 寫回音
⑨ 跑身體（這段不讀 ctl，跑多久等多久）
⑩ on_after_run → 看身體的碼：0＝回 ①；10＝收工退 0；其他＝收工退那個碼
```

- pause、resume、stop 都只在讀取點生效，**不打斷正在跑的身體**。要當場收掉只有訊號。
- pause：在 ⑤ 停住，state 寫 `paused`，之後每秒醒來讀一次 ctl。
- stop：不再起身體，跑 `on_stop`（預設最多 5 秒），寫最後一份 state（`phase: stopped`、`code: 0`），退 0。
- 回音排在「寫 state」之後（`window.cpp:307-320`）。好處：看到 `ctl_seq` 追上時，state 一定已經寫好。代價：stop 的回音排在 `on_stop` 後面（`loop.cpp:104-109`）。
- 第一份 state 在 `on_start` 跑完之後才寫（`loop.cpp:115-123`）。實測 J：`on_start` 花 1.5 秒，`state.json` 到 1.59 秒才出現。

實測（寫 ctl 到 `ctl_seq` 追上，隔多久）：

| 情況 | 結果 |
|---|---|
| A1　身體要跑 3 秒，跑到 0.5 秒時寫 pause | 2.53 秒（等身體跑完） |
| A2　暫停中寫 resume | 0.70 秒 |
| A3　閒著（間隔 60 秒），隨機時刻寫 5 次 | 0.07～0.88 秒 |
| D　寫 stop，`on_stop` 要跑 2 秒 | 2.87 秒；行程也在 2.87 秒結束 |
| D2　同一支 loop 改寫 pause | 0.82 秒 |

### 2.5 兩個人同時寫 ctl

- **檔不會寫壞**：各寫各的暫存檔（檔名帶 pid）再改名，改名是一步到位（`window.cpp:37-50`、`ctl.py:107-119`）。
- **先寫的那道會消失**：條文本來就這樣定，N-06「後寫的蓋前寫的，被蓋的就沒了」（`proto8/docs/NORMS/05-基礎設施-窗/01-N-06～N-08.md:6`）。實測 C：甲寫 pause（seq 1），乙緊接著寫 `max: 5`（seq 2）。3 秒內 `ctl_seq` 只出現過 `null` 與 `2`，state 是 `paused: false`。甲永遠等不到自己的號。
- **同號會誤報**：實測 B。甲乙同一刻算號，都算出 1。甲寫 pause，乙緊接著寫 stop。loop 只看到 stop，停了。甲 0.81 秒後看到 `ctl_seq == 1`，回報成功；實際是 `phase: stopped`、`paused: false`。原因是 2.3 那個沒上鎖的「讀了再加一」。
- **人手 `echo … > ctl.json` 不是一步到位**，但會自己好。實測 M：loop 剛好讀到被清空的檔，記一筆 `ctl_warning`（`cannot read or not JSON`）；內容寫進去之後下一次讀到完整的，照做，警告清回 `null`。

### 2.6 cwd、環境變數、怎麼起身體、結束碼

- **cwd**：aos-loop 從不換目錄（`L/src` 裡沒有 `chdir`；`L/docs/01-用法.md:21`「相對路徑照 cwd 算、loop 不 cd 不轉」）。站哪裡由起它的人決定，見 2.7。
- **靠 cwd 的只有一種寫法**（實測 I）：`exec` 寫字串或陣列時，目標的相對路徑從 loop 的 cwd 算；loop 站到別處就 `EntryMissing`。`exec` 寫成單子（物件）時不受影響，身體的 cwd 是設定檔所在的夾（`proto8/cpp/aos-exec/src/inst/lib_input.cpp:56-60`）。agent-fsm 範本用的是字串（`"exec": "fsm.json"`），eca-claude 用的是單子。
- **環境變數**：aos-loop 自己的程式只讀 `AOS_STACK`（`config.cpp:295`、`L/src/engine/stack.cpp:12`），一起來先拿掉 `AOS_LOOP_CAUSE`（`window.cpp:72`）；連進來的 aos-exec 函式庫另外會用到 `AOS_WS`、`AOS_CLOCK` 這些。其他原樣傳給身體。活樹上一支 agent 的 loop 帶著這些 `AOS_*`（只列名字）：`AOS_HOME`、`AOS_DAEMON`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`、`AOS_CLOCK`、`AOS_LLM_KERNEL`、`AOS_NOTIFY_BOX`、`AOS_PARENT_STACK`。誰設的、各是什麼意思是 06 的範圍。
- **每一圈怎麼起身體**：不另外執行一支 aos-exec，而是呼叫 aos-exec 的函式庫。
  - 字串、陣列：fork 一個子行程，在裡面呼叫 `run_cli`，等於 `aos-exec -- 目標 參數...`；每圈重找入口（`L/src/run/folder.cpp:140-175`）。
  - 單子：在 loop 自己的行程裡呼叫 `run_inst`，由它起子程式、管期限（`L/src/run/inline.cpp:67-87`）。
  - 等身體的那段，loop 只做一件事：把收到的 SIGINT／SIGTERM／SIGHUP 轉給身體。
- **結束碼**（`L/docs/02-窗.md:26-34`）：

| 情況 | loop 怎麼做 |
|---|---|
| 身體退 0 | 下一圈 |
| 身體退 10 | 正常收工，loop 退 0 |
| 身體退其他 | stderr 一行 `RunFailed`，loop 退那個碼 |
| 跑滿 `max`、ctl 的 stop | 退 0 |
| 收到 SIGINT／SIGTERM／SIGHUP | 等這圈結束，退 128＋訊號號碼 |
| 四個點之一失敗 | stderr 一行 `PointFailed`，退那個點的碼 |
| loop 自己出錯 | stderr 一行 `aos-loop: error: 代號 原因`，退 1 |

### 2.7 表上的 pid 是誰、站在哪：今天有三種

共同說明寫「今天 daemon 與 agent 行程站的是定義夾」，對 daemon 與 agent 的 aos-loop 成立。補上兩個例外（活樹 `~/aos-home/.stack/procs/repo-aos`，11-25 12:1x 用 `readlink /proc/<pid>/cwd` 與 `/proc/<pid>/exe` 查）：

| 起法 | 例 | 表上的 pid 是 | 它站哪 | aos-loop 自己 |
|---|---|---|---|---|
| daemon 把 `loop.json` 寫進小格 | `_sweeper`（2242） | aos-loop | **小格（stack）** | 同一支 |
| 字串目標，aos-exec 直接換成 aos-loop | `eca-aos`（2243） | aos-loop | 定義夾 | 同一支 |
| 單子寫進小格的 `exec.json` | `eca-aos-kb`（2244）、`-templates`、`-core` | 一支監工：daemon fork 出來、沒有換程式的分身，在顧那張單子 | **小格（stack）** | 監工的子（2250），站定義夾；`state.json` 記的 pid 是它 |

- 第一種今天就走得通：`cat /proc/2242/cwd/state.json` 讀到 `_sweeper` 的 state。
- 第二、三種從 aos-loop 的 `/proc/<pid>/cwd` 進去，看到的是定義夾：有 `_metainfo.json`、`loop.json`，沒有 state。同一份範本的每一隻都站在同一個夾。
- 第三種「表上的 pid」與「回答 ctl 的那支」不是同一支，但同生共死。實測 N（用 aos-exec 當監工重現同一條路）：監工被 `kill -9`，loop 1 秒內也沒了；loop 被 `kill -9`，監工以 137 退。原因是 aos-inst 替子程式設了「父死子跟著死」（`proto8/cpp/aos-inst/src/inst_proc.c:20-23`、`:122`）。

### 2.8 實測怎麼重跑

`bash ~/.aos/scratch/aos-proc-arch-1125/01/run.sh [a b c d e f g h i j k l m n]`（`run.sh` 先拿掉所有 `AOS_*`；`exp.py` 純標準庫，一個字母一個實驗）。原始輸出（刪掉長路徑與已經列在上面的）：

```
E1 ctl.json is a FIFO, 1.5 s after start: alive=True, state.json exists=False, blocked in syscall nr 257 (257 = openat on x86_64)
E2 1 s after SIGTERM: alive=True
E3 after a writer opened and closed the FIFO: exit code=143; state_flux={… "ctl_warning": "ctl: cannot read or not JSON: …/e/st/ctl.json"}
G1 read /proc/<pid>/cwd/state.json -> phase=running pid=True
G2 pause written (tmp + rename) through /proc/<pid>/cwd: echoed after 0.50 s; paused=True
G3 after kill -9, not reaped yet: /proc/<pid>/cwd/state.json readable=False
   the file on disk still says: {"phase": "paused", … "paused": true, "pid": 2228900, …}
H1 FIFO with no reader, non-blocking open for write: ENXIO
H2 FIFO with no reader, plain blocking open (what `echo stop > ctl` does): still blocked after 1 s (killed)
H3 reader holds the FIFO open but is busy: two writers' open+write+close returned in 0.04 ms total
H4 reader reads later: b'pause\nresume\n' (both lines, in order)
H5 unix socket, listener busy for 1 s: connect+send returned in 0.27 ms; reply b'ok pause\n' came after 1.00 s
H6 listener gone, socket file still on disk: connect -> ECONNREFUSED
I1 loop stands in def,   "exec": "body.sh"    -> loop exit 0, body cwd = def
I2 loop stands in stack, "exec": "body.sh"    -> loop exit 1, body cwd = (body never ran); stderr: aos-exec: error: EntryMissing …
I3 loop stands in def,   exec = inline inst   -> loop exit 0, body cwd = def
I4 loop stands in stack, exec = inline inst   -> loop exit 0, body cwd = def
K  two writers x 10 commands, one taker polling every 50 ms: taken 20, acked 20, lost 0; each writer's order kept=True; ack latency max 255 ms
L  append-only ctl, two writers x 10, reader polls every 50 ms and reports ctl_read in status: taken 20, acked 20, same order as the file=True; ack latency max 74 ms
M  loop read the file while it was empty: ctl_warning='ctl: cannot read or not JSON: <case>/st/ctl.json'; after the content arrived: ctl_seq=3 after 1.00 s, ctl_warning=None, paused=True
N1 supervisor pid != loop pid: True; supervisor cwd=<case>
N2 1 s after kill -9 of the supervisor: path through the supervisor readable=False, loop alive=False
N3 kill -9 of the loop: supervisor exit code=137
```

A～G、I、J、M、N 用真的 aos-loop（N 另外用真的 aos-exec）；H、K、L 是純 Python 的玩具，用來看 3.4 幾種做法的性質。

## 3. 對新介面的含意

### 3.1 對著「定了的」逐條

| 定了的（[9p-proc-1125](../../9p-proc-1125.md)） | aos-loop 今天 | 差在哪 |
|---|---|---|
| persist 的位置以 proc 自己說的為準，daemon 從它的目錄讀（例如 `settings`） | 沒有這種檔。「我的東西放哪」只在行程的環境變數與 daemon 的表裡；別人要從行程身上問，只能讀 `/proc/<pid>/environ`（`adopt.cpp:56-91` 就這樣做） | 起來時把那幾樣寫成 `settings` |
| aos-loop／daemon 退成普通實作 | 三扇窗本來就是公開格式（`loop.hpp:49-78`） | 改 `window.cpp` 一處，Loop 一家都跟上 |
| `ctl`、`status` 純文字；`_metainfo` 照現有的 json | 窗全是 JSON；純文字寫進去會被拒（實測 F）。`_metainfo.json` 在定義夾，不在 stack | 多收一種文字；`_metainfo` 要從身體走得到 |
| 寫 ctl 回來＝收到，做完沒看 status | 寫永遠成功。要知道收到沒得等 `ctl_seq`，而那個回音實際上是「做了」（2.4） | 3.4 |
| `status` 一行一個「名稱: 值」，目前只給一個檔 | 兩個 JSON 檔加一個選開的計數檔。aos-loop 的欄都是平的，直接變成行 | 合成一份 |
| token 用量自己報 | aos-loop 自己不花 token，那是身體的事（03、04）。`status` 是 loop 寫的，身體是另一支程式、加不了行 | 身體的數字照「定了的」那句「以後可以多給別的檔（例如 token 用量）」另開檔 |
| daemon 也是 aos proc；kernel 是普通 aos proc | daemon 繼承 Loop；kernel 範本本來就是 aos-loop 包一個身體 | 跟著 aos-loop 一起有 |
| 入口是 `/proc/<PID>/cwd` | aos-loop 不換目錄，三種站法（2.7） | 讓它站進自己的身體 |
| stack＝活的身體，`.stack` 以後沒有 | `AOS_STACK` 是硬碟上一直在的夾；aos-loop 起來還會讀回上一次留下的窗 | 3.2 |
| 要留的放 persist | aos-loop 自己只有兩樣要留 | 3.2 |
| 活著走 unix socket，掛了走寄信 | aos-loop 沒有 socket，也沒有信箱（信箱是身體或 daemon 的） | 結論第 9 點；細節在 05、20 |

### 3.2 每一樣算哪一類

**身體（活的，行程一沒就該跟著沒）**

| 今天的東西 | 說明 |
|---|---|
| `ctl.json` | 指令只對活著的行程有意義。今天落檔，所以死了也寫得進去，重起時還會照做 |
| `state.json` 的 `phase`、`paused`、`max`、`interval_ms`、`updated_at` | 變成 `status` 的行 |
| `state_flux.json` 的 `ctl_warning` | 變成 `status` 的一行；有回應的寫法則直接當錯誤回給寫的人 |
| `counter_runs.txt` | 變成 `status` 的一行。當初從 json 拉出去是嫌每圈固定寫檔的開銷（N-09「計數器」，`proto8/docs/NORMS/05-基礎設施-窗/02-N-09～N-11/01-N-09-state與計數器.md:6`）；這個理由只對落檔成立 |
| ctl 蓋過的 `max`、`interval_ms` | 今天重起就回設定檔的值（`L/docs/02-窗.md:14`） |
| `stop_cause.json` | 只對這一次啟動有效（裡面記著啟動時間） |
| 閘的 `idle_gate.json` 等短命記號 | 記著「這次 loop」的身分，換一次啟動就作廢 |

**persist（重起後還要是同一隻，就得留）**

| 今天的東西 | 說明 |
|---|---|
| `paused` | loop 起來時從舊 `state.json` 接回（`window.cpp:292-298`）；`hints.py:28-30` 還會去讀停著那隻的這一欄 |
| 最後一道 ctl 的號碼 | 重起去重用（`window.cpp:299-304`）。ctl 不落檔就不需要 |
| 遺言：最後的 `phase` 與 `code` | 今天寫在最後一份 state，行程退了還留著，人與工具查得到。身體一沒，這份就讀不到了。daemon 自己倒是沒在用它（邊緣 7） |
| `stderr.txt`、`.bad-*` 留證檔 | 出事之後才要看的東西 |

**settings（我的東西放哪）**：身體在哪（今天的 `AOS_STACK`）、persist 在哪、定義在哪（`AOS_CD`、`AOS_CF`）、工作區（`AOS_WS`）、上一層 daemon（`AOS_DAEMON`）。今天這些只在環境變數裡。

**定義（原始碼，不屬於某一隻）**：`loop.json`（跑什麼、隔多久、五個點）、`_metainfo.json`。

**會消失（活的行程當場回答時用不到；落檔的實作自己內部還要）**

| 今天的東西 | 為什麼用不到 |
|---|---|
| 判活三欄 `pid`、`started_at_ticks`、`boot_id` | 路徑走不到＝死了（實測 G3）。今天要這三欄，是因為檔活得比行程久。`pid` 留一行當護欄還有用（邊緣 13） |
| `seq`、`ctl_seq`、`responded_at` | 寫回來＝收到 |
| 暫存檔、「有變才寫」、state 分兩扇、計數另開檔 | 都是為了少寫檔、不讓人讀到半份 |
| 起來先讀舊窗、壞窗留證、重起前清舊 stop | 身體每次都是新的 |
| 窗的檔名可以改 | 介面的檔名要固定，別人才找得到 |
| daemon 用 ctl 檔的修改時間判卡住 | 「寫了沒回來」本身就是卡住 |

**實作內部（不屬於介面，照舊）**：五個點與它們的環境變數、結束碼 0／10／其他、`--enable-logs` 的 log 行。

有一樣要小心：好幾支程式拿判活三欄當「這是哪一次啟動」的記號（2.2）。身體如果還留在硬碟上，這個記號得留著（推論）。

### 3.3 最小要動哪裡

每一列都可以跟現有的 json 窗並存。「估多大」是我的估計（推論），沒有實作過。

| 要做到什麼 | 動哪裡 | 改什麼 | 估多大 |
|---|---|---|---|
| **站進自己的身體** | `L/src/main.cpp:62-76`；`config.cpp:295`、`245-258`；`L/src/run/folder.cpp:76-85` | 設定讀完、stack 建好之後換目錄到 stack。之前先把相對的 `AOS_STACK`、`AOS_WS`、兩個旗標檔路徑轉成絕對。起字串目標的子行程先換回原本的目錄再找入口（實測 I2 就是不換回去的後果） | 二、三十行 |
| **多寫一份文字 `status`** | `window.cpp:307-320`（`write_state`）；常數加在 `loop.hpp:61-78` 旁邊 | state 與 state_flux 寫完之後，把同一批欄位印成一行一個「名稱: 值」，暫存再改名。排最後寫，「看到回音時狀態已寫好」這條照舊成立 | 五、六十行 |
| **ctl 也收純文字** | `window.cpp:191-262`（`read_ctl`）、`169-189`（`check_base`） | 多一段文字解析，解出來的東西走原本那條路。舊的 `ctl.json` 照收 | 六、七十行 |
| **起來時寫 `settings`** | `loop.cpp:111-123`（`main_loop` 開頭，`on_start` 之前） | 把 3.2 那幾個位置寫成一個檔。只寫固定那幾樣，不把整份環境倒進去 | 二、三十行 |
| **`_metainfo` 從身體走得到** | 同上 | 在身體裡放一個連到 `$AOS_CD/_metainfo.json` 的連結；或交給 daemon 做（12 的範圍） | 十行內 |
| **「收到」早於「做完」** | `loop.cpp:128` 之後 | 讀完 ctl 馬上寫一次回音，stop 的回音就不用等 `on_stop`。代價是放掉「回音一定晚於狀態」 | 三行 |
| **兩樣要留的搬去 persist**（身體與 persist 分開時才要） | `window.cpp:292-305`（`read_old_state`）、`322-353` | `paused` 與遺言改讀寫 persist 裡的一個小檔 | 三、四十行 |

- 不改 aos-loop 的替代：2.7 的第一、三種，表上的 pid 今天就站在小格。daemon 把連結連到表上那支，aos-loop 一行都不用動；第二種（字串目標）要改成也經小格起。代價見邊緣 2：第三種連到的是監工，路徑上的 PID 跟 state 裡記的 pid 不是同一個數。
- aos-daemon 有自己的 `main`（`D/src/main.cpp:55-70`），「站進身體」那一列它要另外做（02 的範圍）；其餘幾列它繼承就有（它蓋掉的 `write_state` 會叫回 Loop 那份，`D/src/daemon/table.cpp:69-78`）。
- 會受影響的讀者：2.2 那串讀 `state.json` 的程式。json 窗留著就不受影響。
- 改完要重跑的：`L/tests/` 5 支、`D/tests/` 18 支。另有 Python 測試靠行程的 cwd 做事：5 支用它找自己留下的行程（`proto8/py/tests/apps/agent/test_ctl_kit.py:44-49` 等），2 支斷言 daemon 站在定義夾（`proto8/py/tools/agent/kernel_gate/tests/test_query_daemon.py:53`、`proto8/py/tools/aos/kernel/tests/test_runner.py:67`）。遷移衝擊是 13 的範圍。

### 3.4 「寫回來＝收到」：aos-loop 這邊的做法

使用者（11-25 第 4 段）：「1.寫ctl回來，算是收到。」

先分清楚「收到」可以有兩級（推論）：**送達**＝東西進了活著的行程手上的管子，證明有人在聽，不保證讀了；**讀到**＝行程看過、回了話，壞指令可以當場退回。9P 的寫是後一種。

| 做法 | 「寫回來」代表 | 身體在跑時 | 兩人同時寫 | 人手 `echo` | aos-loop 要動 |
|---|---|---|---|---|---|
| **甲　照舊**：檔＋seq，由下指令的工具等回音才回來 | 讀到並採用（今天其實是做了） | 等這圈跑完 | 丟、會誤報（2.5）；號碼改成不會撞的（例如亂數）可解誤報（推論） | 行，沒有回音 | 不用動（今天就是）。可加 3.3「收到早於做完」那三行 |
| **乙　甲＋門鈴**：寫完送一個訊號叫它馬上讀 | 同甲，閒著時快 | 等這圈跑完 | 同甲 | 行 | `loop.cpp:55-82` 的 `nap` 已經留了喚醒的口（`loop.hpp:305`、`332-336`），daemon 的 poke 就是這樣；約三十行。寫的人要知道 pid |
| **丙　讀了就拿走**：loop 先把檔改名拿走再讀；檔不見＝收到 | 讀到 | 等這圈跑完 | 寫的人用「不蓋已有的」方式放，就不會丟（玩具 K：20 道 0 丟） | 極小機率丟一道 | `read_ctl` 約二十行；所有寫的人改寫法；N-06「讀的人只讀不寫」要改 |
| **丁　只往後加**：ctl 是一份只加不改的指令流，`status` 報讀到第幾個位元組 | 讀到 | 等這圈跑完 | 不丟、不撞號、照順序（玩具 L） | `>>` 行；`>` 會出錯 | `read_ctl` 約四十行；重起時要清空 |
| **戊　FIFO**（具名管子） | 送達 | 寫的人馬上回來；loop 之後才讀 | 不丟、照順序（H3、H4） | 最自然 | 約一百多行：起來時建管子、不擋的方式開著、`nap` 改成同時等管子。今天的執行檔不能直接換（實測 E） |
| **己　unix socket** | 讀到，可以回錯 | 連得上（H5：0.27 毫秒），回覆等它有空 | 不丟 | 不行，要一支小工具 | 三百行以上：聽、收、回，加三個等待點都要接 |
| **庚　daemon（橋）代答**：別人寫給橋，橋替它寫 `ctl.json` 等回音再回話 | 讀到，可以回錯 | 等這圈跑完 | 橋排隊，不丟 | 看橋給什麼 | 不用動；工作在 daemon 與 09 |
| **辛　自己當檔案伺服器**（FUSE／9P） | 讀到，當場 | 要另一條執行緒才回得了 | 不丟 | 行 | 很大；09 的範圍 |

幾件表格放不下的事：

- 最後一欄的行數同樣是估的。「人手 `echo`」那欄裡，丙與丁兩格是照做法推的，沒實測；甲是實測 M，戊是實測 H。
- **戊的兩面**。行程活著時寫一定回得來；行程死了，從真實路徑寫會卡住等人（H2），從 `/proc/<PID>/cwd/ctl` 寫則是當場「沒有這個檔」。所以戊跟「入口走 `/proc/<PID>/cwd`」是配套的。它回不了錯，壞字只能寫在 `status`。
- **戊、丁、丙都把「只有最後一道算數」改成「一道一道排隊」**。這動到使用者 11-03 定的方向（N-06 引的原話：「還是用指令吧，不然大家不好理解。但是loop就不要用mailbox那套，就是誰能寫ctl.json就能控制。」）。誰能寫就能控制這點沒變，變的是被蓋掉的那道還算不算。
- **三個等待點**：睡覺（`loop.cpp:55-82`）、等字串目標的子行程（`folder.cpp:89-136`，本來就在等一個檔案代號，好接）、等單子（在 aos-exec 的 `run_inst` 裡，`proto8/cpp/aos-exec/include/aos/exec.hpp:64`，沒有口可以接）。要「身體在跑時也當場回」，第三個得改 aos-exec。
- **不能隨手加一條執行緒**。aos-loop 的 fork 靠「只有一條執行緒」才安全（`folder.cpp:12-13`、`L/docs/03-元素等.md:16-20`）。
- **daemon 判卡住今天靠 ctl 檔的修改時間**，而且只認一般檔（`stuck.cpp:42`）。ctl 換成管子或 socket，這段要跟著換；它預設是關的（`stuck.cpp:19-23`）。
- **純文字不等於不要記號**。ctl 仍是一般檔的話，工具要認「我這道被讀了沒」還是需要一個回音記號（甲的 seq、丁的位置、丙的檔不見了）。字表與行表是 18 的範圍。

我的看法（推論，沒有使用者的話）：先甲，一行都不用動，今天就能說「工具回來＝收到」；要讓人手 `echo` 也算數，戊最貼近字面；己跟「活著走 unix socket」那條一起長出來；庚等橋有了再接。

## 4. 邊緣狀況

1. **落檔的 status 永遠讀得到，但可能是舊的；現做現答的 status 一定是新的，但行程在忙就讀不到。** aos-loop 等身體時不做別的事，如果它自己當場回答，身體跑幾分鐘，連 `status` 都會卡幾分鐘。
2. **表上的 pid 不一定是回答的那支**（2.7 第三種）。兩支同生共死（實測 N），所以從監工的 cwd 進去，死活對得上；對不上的是數字：路徑上的 PID 是監工的，`status` 裡若還有 pid 一行，寫的是 loop 的。另外「父死子跟著死」只打直接的子（`inst_proc.c:23`）：loop 用 fork 起的身體（字串目標那種，`folder.cpp:76-85` 沒設這個）不在內，loop 被殺時它會留下來（照程式推的，沒實測）。
3. **第一份 status 出現得晚**：要等 `on_start` 跑完（實測 J），範本的 `on_start` 是 hook，期限 5 秒。若把「讀得到 status 的那一刻」當成登記完成，這段時間 daemon 會以為它還沒起來。
4. **只跑一次的列沒有 ctl 也沒有 state**（`D/docs/02-看寫法決定怎麼起.md` 的 exec 型）。照新定義它不算 aos proc，除非有人替它回答。
5. **寫給死掉的 proc**。今天寫得進去，下次起來照做（2.3）。使用者第 5 段說的是「proc睡著或死掉的...那自然就收不到」。從 `/proc/<PID>/cwd` 進去就對了；從真實路徑寫仍然寫得進去。
6. **重起後還記不記得暫停**。今天記得（`loop.hpp:268`：11-03 代定「繼續暫停」）。照「stack＝活的身體」，`paused` 不特別留就會忘。
7. **遺言沒地方放，但 daemon 今天也沒在讀它**。行程退了，最後一份 state（`phase`、`code`）還在硬碟。daemon 對自己生的子本來就拿得到結束碼；它不在場時結束的那種，程式直接寫「exit code unknown」留成 `stopped`（`adopt.cpp:310-321`），沒去讀那份 state。所以搬不搬進 persist，影響的是人與工具，不是 daemon。
8. **seq 撞號是現在就有的毛病**，跟新模型無關：兩個人同時對同一隻下 pause／resume，其中一個會被誤報成功（實測 B）。少見，但值得讓 eca-aos 知道。
9. **agent 起來時兩支 loop 搶一個身體**。今天靠 state 裡的 pid 認「小格裡已經有一支活的」（`adopt.cpp:96-121`）。判活三欄拿掉之後，這道防線要換一種做法（例如身體裡放一把跟著行程生死的鎖；推論）。
10. **檔名可以改，其實沒人改**。範本寫的都是預設名。工具只認 daemon 寫進小格的那份設定（`ctl.py:18-25`）；照這段程式，定義夾裡的 `loop.json` 若改了窗名，工具會寫到預設名那個檔去（推論，沒實測）。介面固定檔名，實際上不損失什麼。
11. **站在身體裡會釘住那個檔案系統**：有行程站在裡面的掛載點卸不掉（一般 Linux 行為，憑記憶）。跟「樹放 tmpfs、定期同步」那條有關。
12. **一行一個值放不下多行的值**。aos-loop 自己的欄都是單行；daemon 的 `adopt_warning` 會帶換行（`adopt.cpp:131-135`），`poke` 是巢狀的。02、18 的範圍。
13. **PID 被重用時，連結會指到別人站的地方。** 判活三欄當初就是防這個。只靠 `/proc/<PID>/cwd` 的話，萬一舊 PID 被另一隻 aos proc 拿去，`procs/甲/ctl` 會寫到乙身上。這台 `pid_max` 是 4194304，很難撞，但不是零。便宜的護欄（推論）：`status` 留一行 pid，工具核「路徑上的 PID 等於 status 裡的 pid」才動手；這也是第 3 題推薦 a 的另一個理由（監工那種起法，這兩個數永遠不相等）。使用者 11-09 對 pid 重用的態度是風險自己承擔、護欄照做（N-17 引的原話：「pid被別的程式重用...這是使用者自己要承擔的風險，但我們確實也會做一些護欄，就是你說的這些。」，`proto8/docs/NORMS/05-基礎設施-窗/06-N-17/01-誰判死活與例外.md:6`）。
14. **讀 ctl 今天是輪詢**：每隻 loop 每一拍開檔讀一次（範本的間隔是 300 毫秒）。換成管子或 socket 可以改成有東西才醒；「等」怎麼做是 11 的範圍。

## 5. 要問使用者的

**第 1 題　「寫 ctl 回來＝收到」，落檔的實作（aos-loop）要做到哪一級？**

- a. 檔案這層不要求。由下指令的工具（或橋）等到回音才回來，就算收到；人手直接寫檔的，自己看 `status`。
- b. 要做到「有人在聽」：`ctl` 改成管子，人手 `echo` 寫得進去＝行程活著。
- c. 要做到「讀到並回話」：socket、或 daemon 代答、或自己當檔案伺服器。

推薦 a 起步，c 跟「活著走 unix socket」一起做。理由：a 今天就成立、一行不用改，而且它的回音比「收到」還強。

**第 2 題　身體正在跑（可能幾分鐘）時，「收到」可以等到這一圈跑完嗎？**

- a. 可以，跑完才讀（今天這樣）。
- b. 「收到」要當場回，生效仍然等這圈跑完。
- c. 要當場生效（stop 直接收掉身體，等於今天的 SIGTERM）。

推薦 b 當介面的定義，a 當落檔實作的過渡。理由（推論）：不當場回，「沒回」分不出是忙還是卡住。今天這題還沒被解：loop 跑身體時不讀 ctl，父 daemon 判卡住的期限預設是 0＝不判（`stuck.cpp:19-23`，註解引使用者 11-15「逾時這東西應該要默認爲0」「很久沒動靜算黃色，不殺掉」）。

**第 3 題　`procs/<名>` 要連到哪一支行程站的地方？**

- a. 回答 ctl、寫 status 的那一支（aos-loop 自己）；它起來後站進身體（3.3 第一列）。
- b. daemon 起的那一支。三種起法裡兩種今天就站在小格（其中一種是監工，跟 loop 同生共死）；剩下「字串目標」那種改成也經小格起。aos-loop 不用改。
- c. 由 proc 起來後自己向 daemon 登記，跟「只登記、不起」走同一條路。

推薦 a，b 可以當過渡。理由：不是 daemon 起的 aos-loop（人手起、別的程式起）也一樣站得對；路徑上的 PID 跟它自己報的 pid 是同一個數。c 可以之後疊上去。

**第 4 題　兩個人接連寫 ctl：只有最後一道算數（今天），還是一道一道照順序做？**

- a. 維持只有最後一道算數。
- b. 改成排隊，回了「收到」的每一道都會做。
- c. 介面只說「回了收到的就會做」，要不要排隊各實作自己定。

推薦 b。理由：管子、socket、9P 本來就是一道一道來；回了收到卻沒做，說不通。

**第 5 題　落檔的 aos-loop，身體與 persist 要不要真的分成兩個夾？**

- a. 不分：`settings` 寫 persist 就是身體這個夾。檔還在硬碟，只是行程死了從 `/proc/<PID>/cwd` 走不到。
- b. 分：身體放記憶體（例 `/tmp`），persist 留硬碟。
- c. 先 a，等「樹放 tmpfs」那條要做時再 b。

推薦 c。理由：a 零搬動就有「死了走不到」的效果；b 會動到每一種 agent 的檔案位置，是 03、04、13 的大題。

## 6. 沒查到／沒把握的

- 3.3、3.4 的行數都是估的，沒有實作過，也沒有跑 aos-loop 的測試（只讀）。
- 管子在別的檔案系統上的行為沒測（WSL 的 `/mnt/c`、FUSE、網路掛載）；只在 ext4 上試過。
- 沒查有沒有人真的在 ctl 裡寫 `$ref`／`$env`；改成純文字後這個能力就沒了。
- aos-daemon 自己的 ctl 只知道它沿用 Loop 那三個字，多出來的行為沒細看（02 的範圍）。
- 2.7 只看了公司這台活樹當下的 5 列；「agent 多半是第三種」是從這 5 列說的。
- `proto8/cpp/aos-idle/` 還沒交件，2.2 引的行號之後可能變。
- 順手看到兩處條文跟實作對不上，歸 16：
  - `proto8/docs/NORMS/04-基礎設施-loop與daemon.md:7` 還寫起停兩格出問題「只印一行 warning，不擋起停」；實作與 `L/README.md:35` 是失敗就收工（11-20、11-21 改的）。
  - N-17 寫 daemon 接回時讀子 state 的 `phase == done`（`proto8/docs/NORMS/05-基礎設施-窗/06-N-17/02-phase與stuck.md` 的「接回時讀子 `phase`」）；我在 `D/src` 裡沒找到這段，daemon 只讀子 state 的判活三欄（`adopt.cpp:96-121`）。
