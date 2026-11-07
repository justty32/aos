← [入口](README.md)｜涵蓋：使用者 11-06 補的想法（比喻落地＝直接用 Linux 原生特性，但要可遷移、建議經 daemon）——判準、兩軸分類表 17 列、偏離建議的地方與方向題在續｜上一份 [08-天然差異](08-天然差異.md)｜下一份 [09-續](09-續-偏離建議的地方與方向題.md)

# Linux 原生機制怎麼用才不破壞可遷移性（使用者 11-06 補）

## 使用者原文（11-06，逐字，依先後）

> 我這邊有個想法，想請你交給rtos fable：就是說，我們目前只是比喻，但實際狀況是，我們可以利用linux原生的各種特性，如權限、setrlimit、原生proc排程等等，但是要考慮到我們最終要的是可遷移性。

> 以及，這些linux原生的各種特性，都必須在daemon之下，由daemon做介面

> 剛剛這句可以的話，改成"建議"

**定下的**：原生特性可以用；**建議**經 daemon 套用與讀取（不是硬原則；直接用的要寫清代價）；可遷移性＝daemon-board 已裁的兩件：暫停的目的是能遷移（SIGSTOP 不採）、一棵樹一份 image（範本連 tick 一起帶走）。

## 判準（一句）

**設定寫在定義或表上、跟著樹搬、到另一台由那台的 daemon 重新套用＝好；Linux 行程身上的執行期狀態不可以變成真相（它搬不走）。** 兩軸看每一項：軸 1＝daemon 怎麼把它暴露成檔案或設定（表列 key → 子行程套用、表欄回顯；或根本不暴露）；軸 2＝搬得走嗎（設定可攜／值是「這台的」要人重設／行程狀態本來就不該搬）。板子比喻：daemon＝BSP，原生機制＝暫存器——韌體只寫 BSP 給的設定檔，不直接戳暫存器；設定在 image 裡，換板子由新板的 BSP 重套。

## 兩軸分類表

| 機制 | 現況 | 軸 1：daemon 怎麼暴露 | 軸 2：搬得走？ | 建議 |
|---|---|---|---|---|
| setrlimit（mem_mb／cpu_s／files／file_mb／procs） | 表列 `limits` → daemon 在子行程 `setrlimit`；表欄回顯（docs/09） | **已經是這樣** | ✓ 數字可攜；另一台 hard 更低＝`LimitBad` 留 `stopped`（寫什麼做什麼） | 照舊 |
| 換帳號（`limits.user`） | daemon 子行程 `setuid`，要 root | 已經是這樣 | 半：帳號**名**在樹裡、帳號本身是這台的（沒有＝`LimitBad user … no such user`） | P8 食譜一句「搬完先建帳號」 |
| 檔案權限／擁有者（誰能寫 ctl 信箱＝「唯一」第 2 級） | 人手 chmod／chown；daemon 不管（C-64 權限是使用者的事） | 不暴露（不加 `mode` key：多規則、daemon 不該改擁有者） | mode 隨 `cp -a`、不隨 git（只留 `+x`）；owner／uid 是這台的 | 食譜「搬完重設擁有者」；跟 `AOS_LLM_KERNEL` 同列「這台的」 |
| nice／ionice／排程策略（SCHED_*） | 沒有；全 nice 0（feat-proto 05 代定 7） | 候選：`limits.nice`／`limits.sched` → 子行程 `setpriority`／`sched_setscheduler`（約 1 h）；在此之前寫在 `exec` 前綴＝偏離建議（下節） | nice 值可攜 ✓；SCHED_FIFO 要 CAP_SYS_NICE＝這台的 | 先不做；判準 [07 § 2](07-很多核-能借鑒.md) |
| CPU affinity（taskset／cpuset） | 沒有 | 不建議暴露；要就併 cgroup 的 cpuset | ✗ 核號是這台的（另一台核數不同） | 不做；標天然差異 |
| cgroup v2（整樹總額、`memory.max`、`cpu.weight`、`pids.max`） | 沒有；docs/09 列未來選項（要 root／委派） | 候選：表列 `limits.cgroup`，daemon 起子行程時 mkdir＋寫 pid；根＝人用 `systemd-run --scope` 包（樹外） | 設定值 ✓ 可攜；委派是這台的（沒委派＝`LimitBad`，不退回 rlimit） | 等「一個 agent 一個帳號」root 小程式一起（[07 § 3](07-很多核-能借鑒.md)）；**daemon 不讀 `memory.current` 寫表**（C-52） |
| namespaces（bwrap：mount／net／pid） | aos-sandbox 由定義的 `exec` 自己包、不經 daemon | 候選：daemon 認 `sandbox` key → 轉成 bwrap chain；現況 feat-proto 05 代定 6「daemon 不重用 chain、命名空間是定義自己的事」 | bind 路徑要相對 daemon（daemon-board 04 #18、P5）；pid namespace 曾讓 aos-agent 找不到 daemon（no-pid 04 已解） | 方向題 B（下） |
| 訊號（TERM／KILL／HUP） | daemon 對子項（已）；父對自己 fork 的子（inst timeout、lib 工具）直接送 | daemon：表動作 stop／sleep／rm；父對自己的子＝不暴露（偏離、代價低，下節） | 無關（行程不在 image） | 照舊 |
| flock／fcntl 鎖（`DaemonRunning`、`sender.flock`、`mailbox/.flock`、eca lock、aos-lock T2） | 各程式直接用 | 不暴露：鎖的語意就是「此刻、這台」 | 不搬＝正好（搬過去沒人鎖＝可起） | **可直接用的例外**，代價零 |
| /proc 判活（pid、`started_at_ticks`、`boot_id`） | 只有 daemon（N-17 已改讀、P5b 寫回）；殘留：aos-lock 名牌、aos-llm `kill(pid, 0)` | daemon：表上 `phase`；別人讀表或寄信等回信 | `boot_id` 不同＝全當死＝正確 | 殘留照 T2、no-pid 清 |
| 執行期環境變數 | daemon 給子項六個＋hub 型；人 export 的（`AOS_LLM_KERNEL`…） | 已經是這樣 | 每次開門重算 ✓；人 export 的＝這台的 | 照舊（daemon-board 04 #11） |
| 原生 proc 排程（CFS 分時） | 不管、不暴露 | — | — | AMP：Linux 在底下隱形（[05](05-很多核-比喻失效與換比喻.md)） |
| 根 daemon 的外包（systemd unit、`prlimit`／`ulimit -H`、scope） | 人做、在樹外（「daemon 自己被限＝起它的人包」） | 不暴露（根的根不在 image） | 這台的 | 食譜一句；天然 |
| oom_score_adj | 沒有 | 候選 `limits.oom`——不做（OOM killer 是天然差異） | — | 不做 |
| SIGSTOP／SIGCONT、cgroup freezer、CRIU | 不採（11-06 已裁） | — | ✗ 行程狀態成真相 | 不要碰 |
| shm／mmap／socket／FIFO 當 IPC | 不寫進標準（10-28 決定 12～15）；eca `tty.sock` 自擔 | — | ✗ 搬過去是死的 | 不要碰；交流只走檔（C-75） |
| inotify | 加速、不是真相（N-14；/mnt/c 靜默失效） | — | 無關 | 照舊 |

## 偏離建議的地方、方向題 A／B、代定

見 [09-續](09-續-偏離建議的地方與方向題.md)。

**11-07 使用者裁定（sol 審查 #34-4）**：降優先權等先不經 daemon，維持 exec 前綴的現況；不把 nice／排程策略改成 daemon 新介面。
