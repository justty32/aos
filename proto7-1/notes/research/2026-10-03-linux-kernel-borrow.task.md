# 任務：調查報告——aos 的 kernel 能從 Linux kernel 借鑑什麼

你在一份 repo 副本裡（目前目錄）。**只讀，不要改任何程式或文件**；唯一要寫的是報告檔 `report.md`（放在目前目錄根）。用繁體中文（台灣用語）寫，直白、不要花俏修辭。

## 背景（使用者原話）

> 我會覺得，我們的基底架構 daemon/tick 已經打好了，那 kernel 這塊，其實 linux 本身就有很多可以借鑑的地方。只是說我們的 kernel，其所管理的資源並非只是 cpu／空間等等，也包括 token 數量、易用性、人類可讀性等等。然後 kernel 的排程方式也可以有很多種，乃至於直接讓 agent 做排程。然後我們要 kernel 管理的任務，其時間單位是 ticktock，而內容則是 inst。目前是 agent 任務啦。總之去調查一下，linux kernel 有啥好借鑑的。

## 先讀

1. `proto7/spec/core.md`：核心 spec S-01～S-23（四層：daemon → 時空 → kernel → agent；S-16～S-18 是 kernel；S-01 LLM 可讀＝一切都是 JSON 檔）。
2. `proto7-1/spec.md`：試做的檔案格式。第 6 節任務控制、第 9 節 kernel、第 10 節 agent 最相關。
3. `proto7-1/lib/aos7_kernel.py`、`aos7_kernel_rules.py`：現在的 kernel（卡住、預算、總額、壽命、名冊五條規則）。
4. 按需：`proto7-1/notes/problems-kernel.md`、`problems-real.md`、`infra-needs.md`、`lib/aos_inst.py`（inst JSON 是什麼）。

要點：kernel 只是一個 tick 啟動的任務；它的手段只有寫檔——任務的 `ctl.json`（kill／restart）、daemon 的 `.aosd/ctl/*.json`（pause／resume／wake／resume rounds）、改 tasks.json、spawn、掛載。時間單位是 tick-tock 回合，不是牆鐘。被管的任務內容是 inst（目前主要是 LLM agent）。

## 要調查的

把 Linux kernel 裡值得對照的機制一個個拿出來（下面是起點，自己增刪；重要的多寫，不相關的一句帶過或不列）：

- 排程：CFS／EEVDF（vruntime、權重、lag、deadline）、nice、SCHED_DEADLINE（runtime/deadline/period 與准入控制）、RT throttling、autogroup、**sched_ext**（用 BPF 寫的可抽換排程器、出錯時退回預設排程器——對照「讓 agent 當排程器」）。
- 資源控制：cgroup v2（階層、cpu.weight／cpu.max、memory.min／low／high／max、io.weight、pids.max、freezer、委派）、rlimit、cpuset。
- 壓力與回收：PSI（pressure stall）、OOM killer 與 oom_score_adj、systemd-oomd、記憶體回收／LRU、throttle 與 backpressure。
- 觀測與帳：/proc、/sys、taskstats、schedstat、load average、cgroup 的 *.stat 檔、tracepoint、audit。
- 程序模型：狀態（R/S/D/Z/T）、信號、fork/exec、init 收養、kthread、workqueue、timer／hrtimer、jiffies 與 tickless（NO_HZ——對照 tick-tock 回合與 idle 時不該空轉）。
- 安全與隔離：namespace、seccomp、LSM、capabilities（對照掛載＝看得到什麼、mount_allow）。
- 其他你覺得有用的（例如 BFQ／mq-deadline 等 I/O 排程、DRF 多資源公平、Linux 以外但相關的：Borg／Kubernetes QoS、Erlang supervisor 的重啟策略）。

## 每一項要回答

1. Linux 裡它是什麼、解決什麼問題（短，事實要準；不確定的標「不確定」）。
2. 在 aos 對應什麼：資源換成什麼（token、LLM 呼叫數、牆鐘、回合數、磁碟、**易用性**、**人類可讀性**這類軟資源怎麼量化或代理）、時間單位換成回合後意義有沒有變。
3. **值得借、要改、不要借**三選一，給理由。
4. 值得借的：寫一個具體草圖——kernel 讀哪些檔、寫哪些檔、JSON 長怎樣（S-01：LLM 能讀懂）、需要 daemon／tick 多提供什麼（若有，標出來，這是使用者最關心的）。

## 另外要專門寫的幾節

- **多維資源**：token、錢、時間、易用性、可讀性這些不同維度怎麼放進同一個 kernel（權重？DRF？預算帳本？）；哪些是硬限制、哪些只能是軟目標；誰量「易用性／可讀性」（另一個 LLM 評分？人？）。
- **排程策略可抽換**：參考 sched_ext，設計「kernel 排程策略是一個可換的東西」，包含「由 agent（LLM）當排程器」——它怎麼拿到資訊、怎麼下決定、出錯或太慢時怎麼退回保底策略、如何防止它把自己排死。
- **inst 當任務內容**：Linux 的 task_struct／exec 對照 inst；kernel 要從 inst 裡知道什麼（宣告的資源需求？優先級？類別？），建議 inst 或 tasks.json 加哪些欄位。
- **回合當時間單位**：Linux 用 jiffies／ns，aos 用回合；各條時間線回合長短不一，跨 node 的公平怎麼算。
- **對 daemon／tick 的需求清單**：借這些東西，daemon／tick 層還缺什麼（例如資源帳由誰記、凍結、優先序、權重怎麼傳下去）。逐條，標「必要／有更好」。
- **建議的優先順序**：如果只做三件，做哪三件，為什麼。

## 格式

- 開頭一段摘要（10 行內）＋一張總表（機制｜aos 對應｜借／改／不借｜一句理由）。
- 之後逐項。JSON 草圖用程式碼區塊。
- 引用 aos 檔案時寫路徑，引用 spec 寫 S- 條號。
- 長度不限，但不灌水。
