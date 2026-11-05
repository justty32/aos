← [入口](README.md)｜涵蓋：C／C++ 側（proto8/impls）逐處盤點：哪些是 daemon 本身或 Linux 原生機制可留、哪些要改｜上一份 [01-盤點-py](01-盤點-py.md)｜下一份 [02-轉接設計](02-轉接設計.md)

# 盤點（C／C++ 側；opus 盤點員 11-05 夜實查）

結論：**C++ 側只有一處是「daemon 以外的程式自己讀 pid 判 daemon 死活」——`aos-llm` 的 `warn_idle`，該改。** 其餘是 daemon 本身、Linux 原生鎖、tmp 檔名或信名。另外兩處要另外決定（aos-lock 的名牌判死、aos-util 沒人叫的程序工具）。

類別：**L** 自己 fork 的子行程管理（正當）；**S** 寫自己的 pid／ticks／boot_id 進 state 窗（寫方）；**R** 讀別人窗的 pid 去 /proc 判活（讀方）；**K** 用 flock 判「別人」在不在；**T** tmp 檔名／信名帶 pid；**O** 其他。

## aos-daemon（全部保留：這就是使用者說「daemon 本身與 Linux 原生 proc 接觸」的範圍）

| 檔:行 | 做什麼 | 類 | 判斷 |
|---|---|---|---|
| `src/child/child.cpp:128-150`、`:198-210` | `run_child`／`launch`：fork、setsid、setrlimit、記 `c.pid`＋ticks、設 `AOS_STACK`／`AOS_DAEMON` | L | 留 |
| `child.cpp:306-326` `alive()` | 自己生的看 `waitpid(WNOHANG)`；**接回來的**（上一台 daemon 留下的、沒得 waitpid）比 /proc 的 ticks | L | 留 |
| `child.cpp:330-336` `row()` | 表上每列寫 `pid`、`started_at_ticks`（stopped／sleeping 寫 null） | S | 留（寫方）；重構後**外人不讀這兩欄判活** |
| `src/daemon/daemon.cpp:50-92` `leaders_below` | 掃 /proc 的 ppid／pgrp 找子 loop 底下自成一群的組長，收工時整群收 | L | 留 |
| `daemon.cpp:403-410` `check_running` | `flock(stack 資料夾, LOCK_EX\|LOCK_NB)`，鎖到行程結束；鎖不到＝`DaemonRunning` 退 1 | K（自防） | 留（11-05 B 線改成 flock 的）；**只在 aos-daemon 判**，aos-exec／aos-loop 都沒有這個代號 |
| `daemon.cpp:414-428` | 鎖不到時讀上一台的 `state.json` pid＋ticks 對 /proc，只為訊息印 `(pid N)`、看 phase 是不是 `stopping` | R（daemon 內） | 觀察：flock 已證明對方活著，可只看 phase、不對 /proc |
| `daemon.cpp:445-475` `cell_state`／`live_in_cell`、`:1028-1036` | 讀小格裡子 loop 的 `state.json` pid＋ticks 對 /proc，活著就接回不重起（kill -9 後「fork 了、表沒寫」那種） | R（daemon 讀自己的子） | 留 |
| `daemon.cpp:520-560` `adopt` | 讀上次的表每列 pid＋ticks 對得上才接回（**不比 boot_id**） | R（daemon 讀自己的表） | 留；可補比 boot_id（觀察） |
| `daemon.cpp:623` | 表頂層寫 daemon 自己的 pid／ticks／boot_id | S | 留（寫方） |
| `daemon.cpp:663-667`、`:700-711`、`:714-726`、`:939` | `term`／`hold`／`settle`（10 秒 SIGKILL 整群）、訊號排回自己 | L | 留 |
| `daemon.cpp:590-600` `log_child` | log 行帶 pid | O | 留 |
| `src/common/common.hpp:16-17` | `DaemonRunning` 註解**還是舊說法**（pid＋ticks＋boot_id） | O | 改註解成 flock |

**順帶發現（推論、沒實測）**：`lock_fd_` 只 `O_CLOEXEC`，exec 型目標是 inst 單子、或 daemon 自己的身體跑單子時，子行程在行程內跑 `run_cli`→`run_inst`、**不 exec**，於是一直繼承這把鎖——daemon 被 kill -9 後，新 daemon 要等那個單子跑完才拿得到鎖。補法：`run_child` 裡關掉 `lock_fd_`。列進 [06 邊緣](06-衝突與邊緣.md)、排 P1。

## aos-loop、aos-exec、inst、aos-util（保留）

| 檔:行 | 做什麼 | 類 | 判斷 |
|---|---|---|---|
| `aos-loop/src/engine/window.cpp:52-69` `proc_fields()`、`:215-225`；`loop.hpp:17,129-131,166,197` | 每份 state 都帶自己的 pid／`/proc/self` 第 22 欄／`boot_id` | S | 留（寫方）；註解「心跳拿掉，判活看 pid」那句是本次要翻的前提 |
| `aos-loop/src/run/folder.cpp:84-110,127-136` | fork 身體、三個訊號轉給子、`waitpid` | L | 留 |
| `aos-exec/src/inst/signals.cpp:44-117`、`run.cpp:150-171`、`exec.hpp:45` | 訊號 `killpg` 轉子群組、grace 後 SIGKILL；`Result.pid` | L | 留 |
| `inst/src/inst_proc.c:77-362`、`inst_exec.c:145-194`、`inst_internal.h`、`aos.h` | fork＋setsid＋execvp、pidfd_open／poll、waitpid、`kill(-pid)` | L | 留；沒有「找別人」 |
| `aos-util/src/proc.cpp:108-135` `proc_started_at_ticks`、`:185-196` `unique_id()`＝`<ns>.<pid>.<ticks>`、`boot_id()` | 工具函式；信名／鎖名唯一化 | O／T | 留 |
| `aos-util/src/proc.cpp:28-105`、`proc.hpp:31-50` `spawn`／`has_exited`／`wait_exited`／`reap`／`stop`／`wait_plain`／`memfd_*`／`read_all` | **impls 裡沒人呼叫、只剩 `signal_group` 在用**；檔頭「loop 起 aos-inst、daemon 起 loop 都用這組」已不對 | O | **死碼**：併進大重構 S10 的清單（方向題 6 已授權 aos-util 沒人叫的 API 刪） |

## aos-post、aos-json、aos-llm-kernel（保留）

| 檔:行 | 做什麼 | 類 | 判斷 |
|---|---|---|---|
| `aos-post/include/aos/post.hpp:19`、`aos-llm/src/send/send.cpp:123` | 預設信名＝`unique_id`（N-16 的 `<UTC 奈秒>.<pid>.<ticks>`） | T | 留：pid 只為同機不撞名，不是找東西 |
| `aos-json/src/doc/doc.hpp:4,41`、`file.cpp:129` | 原子寫的暫存檔 `.名.<getpid>.tmp` | T | 留 |
| `aos-llm-kernel/include/aos/llm_kernel.hpp:8,18-24,70`、`src/letter/letter.cpp:25-51` | `sender.flock`：同步 `ask` 的寄信人持 LOCK_EX；kernel 試 LOCK_SH 拿不到＝寄信人還在（撤信／刪信靠它，`serve.cpp:177,480-481`） | K（判別人） | 留：**設計上就是為了脫離 pid**（沙箱裡也認得），合方向 |
| `aos-llm-kernel/src/serve/serve.cpp:287-292` | 信箱 `.flock` 擋第二個 kernel | K（自防） | 留 |
| `aos-llm-kernel/src/serve/serve.cpp:359-415` | 看它掛的問腦 proc：讀 daemon 的表（phase／reason）＋信資料夾的 `state.json`，**完全不碰 pid** | — | **現成的「經 daemon」範例**；kernel-daemon 08 代定 1 的四格判法 |
| `aos-llm-kernel/src/daemon/daemon.cpp:24-28` | 找 daemon 靠 `AOS_DAEMON` | — | 已合規；kernel 沒有殘留 pid 欄、沒有死碼 |

## 要改／要決定的兩處

| 檔:行 | 做什麼 | 類 | 判斷 |
|---|---|---|---|
| **`aos-llm/src/send/send.cpp:39-58` `warn_idle`**（`main.cpp:93,107` 叫） | `ask` 等很久時讀 **llm daemon 的 `state.json`** 拿 pid、`kill(pid,0)` 判它在不在（**沒比 ticks**，pid 重用會誤判），警告字尾加 `, pid gone` | **R** | **改**：警告改成不下判斷的句子 `no reply after Ns from the llm kernel at <stack>; is its daemon running?`，不讀別人的窗；要真判就寄 ping（C++ 要多連一段 aos-post 的等回信，不值；代定） |
| `aos-lock/src/holder/holder.cpp:46-61,99-152`、`src/main.cpp:77-84` | mkdir 資料夾鎖＋名牌 `holder.json`（pid、ticks、boot_id、lease）；拿不到鎖時 `reapable()` 比三欄＋`kill 0`＋殭屍＋租約，判**持鎖的另一個寄信人**死了沒、死了就收。只有 aos-post `send --ordered` 的 `order.lock/` 在用；CLI 的 `acquire --pid N` 替別的行程掛名、repo 內沒人用 | R（判別人，但不是找 daemon） | **留**（方向題 4）：它是基礎層的鎖、Linux 原生機制那一類；要嚴格套用就改成名牌旁放 flock 檔（學 `sender.flock`）。`--pid N` 這個旗標沒人用，可隨 S10 刪 |
