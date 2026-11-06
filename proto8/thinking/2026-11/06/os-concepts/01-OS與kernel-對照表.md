← [入口](README.md)｜涵蓋：子題 1——RTOS／init 系統／Linux 概念 ↔ aos 的 kernel 與 proc 排程對照表 28 列、最有意思的三個｜下一份 [02-OS與kernel-能借鑒](02-OS與kernel-能借鑒.md)

# 子題 1：OS 概念 ↔ aos 的 kernel 與 proc 排程

**一句話**：aos 把 RTOS 排程器的兩件事拆開了——daemon／判官只管「准不准掛」（準入控制），「誰先跑」只活在 llm kernel 的身體裡（優先序＋aging＋EDF＋包的 slots＝教科書 RTOS 那幾招，已經八成到位）。沒時間片、沒搶佔、沒阻塞原語是天然差異，標出來不追（[08](08-天然差異.md)）。

銜接 [daemon-board 01](../daemon-board/01-對照表.md)／[01-續](../daemon-board/01-對照表-續.md)（窗、信箱、中斷、看門狗、電源、OTA 那些列不重列）。狀態：**已經是這樣**／**差一點（差在哪）**／**天然差異**。

| OS／RTOS 概念 | aos 現在有的 | 狀態 | 一句白話 |
|---|---|---|---|
| 排程器＝准入＋派工兩件事 | 判官（`allowed`／`max_running`）管准不准；llm kernel 身體管誰先 | 差一點：派工只在 llm kernel 一處，通用 kernel 沒有 | C-47 加嚴後的 kernel 定義剛好是「准入」那半。 |
| 優先序等級（RTOS 32／256 級） | 信的 `priority`：low／normal／high／數字／`{level, deadline}` | 已經是這樣 | 數字不封頂。 |
| aging／防餓死 | 等 10 拍升一級、不封頂（拍＝daemon `interval_ms`，300 ms） | 已經是這樣；單位是「拍」，見 [02 § 5](02-OS與kernel-能借鑒.md) | low 等 6 秒就超過 high。 |
| EDF（期限最近先） | 級數之後比 deadline；過期 `DeadlineMissed` | 已經是這樣 | 第二排序鍵。 |
| 同級 FIFO | 等得久 → 先寄 | 已經是這樣 | |
| 計數信號量 | kernel 總 `slots`、包各自 `slots`（C-10 格數） | 已經是這樣 | slots 就是 counting semaphore。 |
| 互斥鎖 | flock `DaemonRunning`；aos-lock 租約（T2 改檔案鎖） | 已經是這樣 | |
| 優先序反轉／繼承／天花板 | 包的 slots 被 low 佔滿、high 等；不搶位、不升級在飛的 | 天然差異（錢已花，feat-proto 03 代定 5） | 見 [02 § 4](02-OS與kernel-能借鑒.md)。 |
| 時間片／round-robin | 無：一次身體跑完才換人 | 天然差異 | 排程粒度＝一次 exec。 |
| 任務狀態 ready／running／blocked／suspended | running／stopping／stopped／sleeping（＋P7 `stuck`）；沒有 ready | 差一點：daemon 表沒「等格」列；llm kernel 的 `new/` 才是 ready queue | 判官拒＝`SlotMissing`，不排隊。 |
| 阻塞等待原語（sem_wait／event wait） | 無；每拍輪詢窗與信箱，inotify 加速 | 天然差異 | 等＝下一拍再看。 |
| 訊息佇列滿了 block／drop | 信＝檔案，信箱不會滿 | 天然差異 | 磁碟滿才滿。 |
| workqueue／每件事一條 kthread | kernel 每封請求掛一個 `max: 1` 的 loop 型 proc | 已經是這樣 | 下半部交 daemon 跑。 |
| 異質核／affinity（big.LITTLE） | 能力包各自 `slots`（`smart-high`、`stupid-fast`）；信寫代號＝釘核 | 已經是這樣（C-29 外部 PU） | 不替人換包（C-56）。 |
| 負載平衡／自動降級（EAS） | 包到頂 `BudgetMissing`、不 fallback | 天然差異（使用者偏「寫什麼做什麼」） | 刻意拿掉的那半。 |
| oneshot／longrun／bundle（s6-rc） | exec 型／loop 型／`{"daemon": …}` 子樹（P6） | 已經是這樣 | 三型一一對上。 |
| `Restart=` 策略＋防爆衝 | loop 型不重起；daemon 型重起、短時間連 3 次失敗留 `stopped`（P6） | 已經是這樣 | s6 是「至少隔 1 秒」。 |
| 依賴順序（`After=`／`Requires=`） | 照 `procs` 順序起、`_tick` 插最前；不等誰 ready | 差一點：沒有「等它第一拍跑完」 | [02 § 2](02-OS與kernel-能借鑒.md)。 |
| readiness 通知（sd_notify、s6 notification-fd） | `state.json` 的 `counter_runs ≥ 1` 就是 ready；沒人等它 | 差一點 | [notes/s6-runit](../../../../notes/s6-runit.md) 已指出。 |
| runlevel／target | `procs` 可 `$ref` 多份檔合成（N-28 ①）；沒有「切 target」動詞 | 差一點：機制有、慣例沒寫 | [02 § 3](02-OS與kernel-能借鑒.md)。 |
| 裝置樹 overlay | 定義不動、stack 裡 `llm.json`／tools 覆蓋層疊上去 | 已經是這樣 | 定義＝DTS、stack＝runtime。 |
| HAL／驅動註冊表 | `_tooldef.json`＋`tools.json`；能力包＝endpoint 驅動 | 已經是這樣 | |
| 熱插拔（udev 事件） | ctl 信箱 `procs_added`／`removed`、inotify | 已經是這樣 | |
| /proc、top | `procs_state.json`、`ctl ls`、各自 `state.json`；沒有即時 CPU／記憶體用量 | 差一點：沒有 top | 要量就包 `limits` 讓它撞。 |
| OOM killer | rlimit 到頂自己死、留 `stopped`＋`reason`；daemon 不挑誰殺 | 天然差異 | |
| 系統呼叫表 | 掛 proc 唯一入口＝ctl 信箱的 `procs_*` key | 已經是這樣 | 判官＝seccomp 白名單。 |
| capabilities（主體×動作×客體） | 判官只看客體名字；「誰能對誰做什麼」遠期（N-42 旁） | 差一點 | 不驗主體是使用者 11-05 裁的。 |
| DVFS（調頻） | `interval_ms` 可從 ctl 改、`_tick.interval_ms` | 已經是這樣 | |
| 可換排程類別（sched class） | C-15 排序程式可由模型寫；但 llm kernel 排序寫死 C++ | 差一點（概念有、無鉤子） | 要換＝寫另一個 kernel 身體。 |

## 最有意思的三個對照

1. **判官是準入控制，不是排程器。** RTOS scheduler 一手做「准不准進 ready」和「誰先上 CPU」；aos 把前者給了 daemon／判官（C-47 加嚴後 kernel 定義恰好只剩這半），後者只在 llm kernel 身體裡活著。所以「通用 kernel 要不要排程」是個真空位、不是漏掉——答案就是 README 方向題 1。
2. **覆蓋層就是裝置樹 overlay。** 嵌入式把「硬體長怎樣」（DTS）跟程式分開、再用 overlay 疊差異；aos 的定義資料夾不動、stack 裡 `llm.json`／tools 覆蓋層疊上去，是同一個形狀——`tools reset` 一刀回定義＝卸 overlay。這條 aos 天生就對，不用補。
3. **能力包＝big.LITTLE，代號＝釘核，而且故意沒有 EAS。** `smart-high`／`stupid-fast` 各自 `slots` 就是異質多核；信寫代號就是 affinity；Linux 的 EAS 會在核之間遷移任務，aos 使用者偏「寫什麼做什麼」（不降級換包）——這是刻意拿掉的那半，寫明比補上有價值。

## 板子比喻在 kernel 層哪裡失效

板子比喻到「誰先跑」就斷了：bare-metal super-loop 只有一個寫死的順序、沒有排程器；aos 一旦有 llm kernel 的級數／aging／slots，它就已經是 **MCU 上一顆很薄的 RTOS 核**（FreeRTOS 那種）——daemon＝板子＋BSP（起停、電源軌、看門狗）、kernel 身體＝scheduler task、proc＝task；而「掛不掛、oneshot／longrun、target」那半更像 **s6-rc 這種服務管理器**。所以彙整用三段式：**板子（daemon）＋薄 RTOS 核（kernel 身體）＋服務目錄（`procs` 表）**，各管一層；「很多核」那層再換成 AMP SoC（[05](05-很多核-比喻失效與換比喻.md)）。
