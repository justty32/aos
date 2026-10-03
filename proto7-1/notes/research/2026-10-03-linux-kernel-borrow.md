# aos 的 kernel 能從 Linux kernel 借鑑什麼

（astra 2026-10-03 寫，題目見同名 `.task.md`；頂層只搬進 repo，未改內容。）

aos 最值得借的是「可核對的資源帳、分層限制、排程與執行分離、策略失敗仍能運作」，再來才是 CFS／EEVDF 的選人算法。現有 daemon／tick 足以試做按回合輪替，但 `pause` 不會停止正在跑的任務，不能當成 token 硬限制。建議先補記帳與控制回饋，再建立執行前的額度閘門，最後讓規則程式或 LLM 經同一份 JSON 協議提出排程。回合保留為邏輯時間；token、金額、並行槽位各自記帳；易用性與人類可讀性作為可查證的軟目標。kernel 仍是 tick 啟動、只靠讀寫檔案做事的任務，不把 LLM 或業務判斷塞進 daemon。

| 機制 | aos 對應 | 借／改／不借 | 一句理由 |
|---|---|---|---|
| CFS vruntime、nice | 依權重分配 token 服務額度 | 要改 | CPU 執行時間換成可核算的服務量，回合數不能直接當成本 |
| EEVDF lag、虛擬 deadline | 公平欠額＋短互動工作優先 | 要改 | 虛擬截止點可借，但 LLM 呼叫通常不能中途搶佔 |
| autogroup／群組公平 | 專案、使用者先分，再分給其任務 | 值得借 | 避免多開 agent 就多拿資源 |
| SCHED_DEADLINE／准入 | 宣告每個週期的額度與交付回合 | 要改 | 可保留服務額度，不能保證外部模型準時完成 |
| RT throttling | 高優先工作上限、控制面保留額度 | 值得借 | 緊急任務也不能把復原能力吃光 |
| sched_ext | 可替換的規則／LLM 排程提案 | 值得借 | 可信執行端驗證，失敗退回保底策略 |
| cgroup 階層、委派 | 專案→團隊→任務的預算樹 | 值得借 | 子層可分配，不能擴張父層總額 |
| cpu.weight／cpu.max、io.weight | 相對權重、週期額度、工具佇列權重 | 要改 | 比例、速率與終身預算必須分開 |
| memory.min／low／high／max | 保留額度、優先保護、節流線、拒絕線 | 要改 | token 已花掉不能像記憶體一樣回收 |
| pids.max | 整個群組的活任務與呼叫並行上限 | 值得借 | 目前 `max_live` 只管同名任務 |
| freezer | 真正凍結本機執行、合作式停止新動作 | 要改 | 暫停時間線與凍結程序是兩件事 |
| rlimit | 每個任務的硬上限、每次呼叫上限 | 要改 | token 要在 API 呼叫入口管，OS 看不到 |
| cpuset | 模型池／工具池的可用範圍 | 要改 | 借適配與放置限制，無須把 CPU 編號搬進 aos |
| PSI | 有工作卻因額度／槽位／I/O 等待的壓力 | 要改 | idle、等人與資源不足要分開 |
| OOM killer、systemd-oomd | 壓力下取消可重做工作 | 要改 | 停工作只能省未來成本，不能退回已花的 token |
| LRU／回收 | context、可重建快取與日誌保留 | 要改 | 不能只按最近使用時間刪掉任務目標或名冊 |
| throttle／backpressure | 生產端限流、有界信箱與工具佇列 | 值得借 | 不要等產生大量工作後才 kill |
| /proc、/sys、taskstats、schedstat、*.stat | 統一 JSON 快照、累計帳與等待原因 | 值得借 | 排程要靠同一份事實來源 |
| tracepoint、audit | 決策、接受、執行、結算的事件鏈 | 值得借 | 找得到「為什麼排／停這個任務」 |
| Linux load average 的數字 | 原樣套到 agent 負載 | 不要借 | 活程序數和 agent 的可執行需求差太多 |
| task_struct、狀態、信號、fork／exec、收養 | 任務身分、inst 定義、生命週期與監督 | 要改 | inst 是執行描述，並不是活任務本身 |
| kthread／workqueue | 維護任務、有界工作池 | 要改 | 保留 S-04 程序模型，借分工與併發上限 |
| timer／hrtimer、jiffies、NO_HZ | 回合計時、外部逾時、事件喚醒 | 要改 | 不空轉，但不能偷把經過秒數換算成回合 |
| namespace、capabilities、LSM | 可見範圍、控制權與驗證邊界 | 要改 | symlink 掛載與宣告不是強制隔離 |
| seccomp 直接充當 aos 權限系統 | 用 syscall 過濾判斷任務權限 | 不要借 | 不懂 node、token 或文字指令的語意 |
| BFQ／mq-deadline | LLM／工具請求的公平與防飢餓 | 要改 | 借佇列規則，不借磁碟細節 |
| DRF | 多個稀缺資源池的公平分配 | 要改 | 適合可量化容量，不適合把可讀性當份額 |
| Borg／Kubernetes QoS | 宣告需求、工作類別、容量准入 | 要改 | 借 request／limit 與降級順序，不承諾輸出品質 |
| Erlang supervisor | 重啟範圍、重試上限、失敗升級 | 值得借 | 比「卡住就一直 restart」更可靠 |

## 1. 調查範圍與現有能力

調查日期：2026-10-03。Linux 事實以各節連結的官方文件、Linux man-pages 或專案原始文件為依據；網頁可能隨主線更新，不代表 aos 所在主機已啟用該功能。本報告是設計調查，未啟動 daemon、未執行 agent、未改程式。所有標示「提案」的格式都尚未實作；數值只是說明用，不是建議的正式預設值。

### 1.1 不改的核心邊界

- `proto7/spec/core.md` S-01：操作與狀態須讓 LLM 靠讀寫 JSON／文字就能理解。可讀不等於把所有歷史都塞進 prompt。
- S-02、S-03、S-06：daemon 處理運行與邊緣狀況，kernel 處理管理政策。
- S-08～S-11、S-17：任務由 tick 啟動，可跨回合；kill／restart 在 tick／tock 邊界執行。回合是邏輯時間，不是固定長度的 CPU time slice。
- S-16：由 agent 提排程仍然可以是 kernel 性質的任務，不需要特殊身分或另一層架構。
- S-18、S-23：跨 node 的觀測與控制經掛載，管理時間線靠 daemon ctl。
- S-20、S-21：子 daemon 可作為普通任務被管理，但父 daemon 核心不必知道整棵業務從屬樹。
- S-22：控制成環由使用者承擔。後文保護排程器自己的規則，是可選的 kernel 政策，不把全域禁止成環改成核心規定。

### 1.2 目前的控制不是 CPU 搶佔

依 `proto7-1/spec.md` 第 2、4～7、9、10 節與 `proto7-1/lib/aos7_kernel.py`、`proto7-1/lib/aos7_kernel_rules.py`：

| 現有操作 | 真正效果 | 對設計的限制 |
|---|---|---|
| daemon `pause` | 本回合收完後不開新回合；活任務繼續跑 | LLM、工具和子程序仍可消耗資源 |
| `resume`＋`rounds: N` | 執行 N 次回合，最後 tock 後自動 pause | N 次 tock 不等於 N 次 agent 動作；慢 agent 會漏看中間 tock |
| `wake` | 縮短 idle 等待 | 不解除 pause、不打斷當前回合、不代表喚醒某個指定 agent |
| 任務 `ctl.json` | tick／tock 才做 kill 或 restart | 已 pause 的 node 會把 ctl 留到 resume；不能宣稱立即止血 |
| 改 `tasks.json` | 改未來啟動規則 | 不會停掉既有實例；`keep` 會補回被 kill 的實例 |
| `spawn/*.json` | 下次 tick 請求啟動，具至少一次語意 | 動作中斷後可能重複起；不是恰好一次 |
| 掛載 | tick 建 symlink，給路徑與回條 | 是可見範圍的協議，目前沒有 OS 強制隔離 |

回條 `result.ok` 不一律等於目標已達成。時間線 pause 要看 `.aosd/status.json` 的 `phase: "paused"`、`pause_pending: false`，仍不能推論活任務已停止。把「接受 pause」「停止開回合」「停止發起新呼叫」「本機程序凍結」「遠端呼叫取消」分成五件事，是整份設計的前提。

### 1.3 五條規則已暴露的缺口

1. **預算與總額是事後控制。** `aos7_agent.py:do_think()` 在 LLM 回來後才 `add_usage()`；kernel 加總 `tasks/` 與 `tasks-old/` 的 `usage.json`。並行中的成本尚不可見，kill 也未必追回遠端計費。現在的 `budget_tokens` 是累計超額後冷卻，不是固定週期 token bucket；`cap_tokens` 是逐成員檢查，不是自動加總整個團隊的共同 cap。
2. **卡住其實主要是心跳。** `progress.json` 帶 round，idle 也更新。業務沒進展與沒處理 tock 不同；`problems-real.md` R-1、R-3、`problems-kernel.md` K-7 都有實例。
3. **回合計數有抽樣差異。** `rule_stuck()` 發現成員 round 前進只做 `same += 1`，不是加 round 差值。成員從 10 跳到 20，只算一次觀察；不是精確「十回合沒進度」。`problems-real.md` R-3 已指出此差異。
4. **決定未必送達。** `run_rules()` 先改 `paused`／`issued`；`one_round()` 即使 `apply_decision()` 跳過或失敗，仍儲存新狀態。它不讀控制回條，可能把未成功的操作記成已處理。見 K-10。
5. **任務狀態有兩份判斷。** `aos7_kernel_rules.task_state()` 只看任務 pid；`aos7_task.task_state()` 還看 runner。這是 K-3 預告的實際不一致，不宜再增加第三份。
6. **名冊與壽命值得保留。** roster 是供 agent 使用的穩定資訊（R-2）；`max_age` 是自己 node 的回合壽命限制。兩者不必硬套成 Linux 某個子系統。

`proto7-1/notes/problems-kernel.md` 包含較早的問題紀錄；例如 K-1 描述直接跨路徑寫入，但現行 kernel 已使用 resolver 與動態掛載。判斷現況以程式與 `spec.md` 為準，筆記用來解釋代價。

## 2. 先借觀測與記帳：/proc、/sys、taskstats、schedstat、tracepoint

**Linux 是什麼。** `/proc` 暴露程序與系統狀態，`/sys` 暴露 kernel 物件與屬性；taskstats 經 netlink 提供存活中及退出時的任務統計；schedstat 有執行與等待等累計數；cgroup 的 `*.stat` 是群組統計。這些介面讓政策不用猜底層狀態。[proc 文件](https://docs.kernel.org/filesystems/proc.html)、[sysfs 文件](https://docs.kernel.org/filesystems/sysfs.html)、[taskstats 文件](https://docs.kernel.org/accounting/taskstats.html)、[schedstat 文件](https://docs.kernel.org/scheduler/sched-stats.html)

**判斷：值得借。** 借固定入口、權威寫入者、累計計數與退出結算，不照搬二進位 netlink 或數字欄位表。aos 可以直接用 JSON。以回合觀察等待，以呼叫事件結算成本；兩者不要混為一個計數器。

### 2.1 快照與帳的草圖〔提案〕

runner／tick 產生 `<node>/.aos/status.json`；可信呼叫入口產生帳，kernel 只讀。跨 node 仍經 S-23 掛載。kernel 讀此檔、`kernel.json`、`.aosd/status.json`，把決定與排程狀態寫到自己的 `$AOS7_TASK/`。

```json
{
  "schema": "aos.node-status.v1",
  "daemon_gen": 3,
  "snapshot_seq": 218,
  "clock": {"node": "team/agents/amy", "round": 80},
  "coverage": "registered_tasks",
  "account_seq": 937,
  "tasks": [{
    "tid": "agent-r3",
    "task_key": "team/agents/amy:agent",
    "lifecycle": "live",
    "activity": "waiting_external",
    "wait_reason": "llm_response",
    "last_tock_seen": 76,
    "progress_seq": 12,
    "usage_source": "call_gateway",
    "inflight_calls": 1,
    "unknown_fields": []
  }]
}
```

`task_key` 代表可跨 restart 的邏輯工作；`tid` 代表一次實例。跨不同 daemon 還須附 daemon 的穩定識別，`gen` 只識別其重開世代。未知狀態寫 `unknown`／`null` 與原因，不能因讀不到就當成零使用量。快照不是所有 node 同時凍住的全域視圖：逐 node 帶版本與觀測回合，套用時再驗證。

`<account-root>/.aos/accounts/events.jsonl` 每行一個事件；`summary.json` 是可重建的累計摘要。這裡的 account-root 是 kernel 配置指定、已掛載的帳務根，不必是 daemon 根。

```json
{
  "schema": "aos.account-event.v1",
  "event_id": "provider-a:req-481:final",
  "request_id": "req-481",
  "account_seq": 938,
  "task": {"node": "team/agents/amy", "tid": "agent-r3"},
  "group": "project-x/team-a",
  "event": "settled",
  "clock": {"node": "team/agents/amy", "round": 81},
  "usage": {"input_tokens": 3000, "output_tokens": 900, "calls": 1},
  "cost": {"currency": "USD", "microunits": 2400, "price_revision": "example-v1"},
  "quality": "provider_reported"
}
```

價錢是示意，沒有引用任何供應商現行費率。金額用整數最小單位，另記幣別、模型、費率版號及快取／推理等可計費類別，不能只拿 total_tokens 乘一個永久固定價格。重試各有 request id；同一結算事件重送去重，修帳用新的 adjustment 事件。任務被歸檔或刪掉，終身總帳不能變小。

**誰記什麼：** daemon／runner 記啟停、程序／磁碟等可直接觀察數據；LLM 呼叫入口記請求、重試與供應商用量；任務自報語意進度；人或評估任務記品質。若沒有受控呼叫入口，只能標 `task_reported`，不能假裝是強制帳務。

**daemon／tick 需求：必要**是統一狀態、世代／序號、結束結算與帳務持久化接口；LLM 帳本本體可由另一個 tick 啟動的服務任務維護，不必讓 daemon 理解 tokenizer 或價格。初版 kernel 也可自行增量彙總現有 usage，但不能消除回報遺失與繞過問題。

### 2.2 tracepoint／audit：把因果鏈接起來〔值得借〕

Linux tracepoint 是可掛接的事件觀測點；audit 的使用者空間 daemon 將稽核事件落盤。aos 要借「可追蹤事件」，不用每個 kernel 決策都啟用 Linux 全量 syscall audit。[tracepoint 文件](https://docs.kernel.org/trace/tracepoints.html)、[auditd 手冊](https://man7.org/linux/man-pages/man8/auditd.8.html)

kernel 讀 `ctl-done` 與 status，寫自己的 `decisions.jsonl`；daemon／tick 寫執行事件，兩邊以 request id 關聯。現有 `by` 是自報字串，若要安全稽核，執行者還要記錄經過驗證的來源。

```json
{
  "request_id": "k3-r120-004",
  "event": "applied",
  "operation": "pause",
  "target": "team/agents/amy",
  "decision_clock": {"node": "control", "round": 120},
  "applied_clock": {"node": "team/agents/amy", "round": 81},
  "daemon_gen": 3,
  "reason_code": "period_budget_exhausted",
  "why": "本週期額度已用完，停止開新回合",
  "evidence": {"account_seq": 938},
  "effect": {"timeline_paused": true, "processes_frozen": false}
}
```

請求生命週期至少分 `proposed → accepted → applied`，另有 `rejected／expired／failed`；不能用一個 `ok` 混過去。原子 rename 只保證單檔完整，不保證多檔交易或斷電耐久；重要結算要有可回放事件、單一寫入者或鎖、明確的持久化政策。保留短摘要給 LLM，完整事件按需查，日誌輪替與索引也要有預算。

**daemon／tick：必要**補 request id、執行狀態與重試去重；**有更好**補事件訂閱與可配置的 trace 級別。現有 `AOS7_AUDIT` 只記 Python 寫入且不阻擋，不能當全語言的安全稽核，見 `proto7-1/spec.md` 第 5 節。

### 2.3 load average 原樣不要借

Linux load average 包含 runnable 與不可中斷等待工作，提供 1／5／15 分鐘趨勢，並不是 CPU 使用率。[proc_loadavg 手冊](https://man7.org/linux/man-pages/man5/proc_loadavg.5.html)

**判斷：不要借其數字定義。** aos 一百個 idle agent 可以毫無工作，一個 agent 卻可能掛十個外部呼叫。改看 ready 工作數、最老等待回合、在途呼叫、被額度擋住的工作數；按回合平均必須註明哪條時間線。若需要主機負載，另列 Linux 指標，不拿它推論團隊進度。

## 3. cgroup v2：先把資源控制語意分清楚

以下 Linux 對照均指 cgroup v2 的概念；各 controller 是否可用取決於 kernel 與設定。aos 的預算樹是管理模型，不表示現行 daemon 已使用 Linux cgroup。

### 3.1 階層與委派〔值得借〕

Linux cgroup 依階層限制資源；子樹不能用自己的設定突破祖先約束，委派也有範圍限制。[cgroup v2：概念與委派](https://docs.kernel.org/admin-guide/cgroup-v2.html#delegation)

aos 先以擁有者／專案分配，再分團隊與任務；資源歸屬不必照資料夾巢狀推定。共享工具、跨 node 通訊與 S-15 的重疊，必須顯式指定唯一的付費群組，否則不是漏帳就是雙算。子 daemon 是另一個運行層，不應被父 daemon 掃進來；跨 daemon 分帳由 kernel 與受控帳本協議處理。

kernel 讀各群組的 `limits.json` 與帳摘要，寫子群組額度及 grant；下列為 `<account-root>/.aos/groups/team-a/limits.json`〔提案〕：

```json
{
  "schema": "aos.group-limits.v1",
  "group": "project-x/team-a",
  "parent": "project-x",
  "weight": 100,
  "period": {"clock_node": "control", "rounds": 20},
  "limits": {
    "tokens_per_period": 40000,
    "calls_inflight": 3,
    "live_tasks": 8,
    "lifetime_cost": {"currency": "USD", "microunits": 5000000}
  },
  "delegation": {"may_create_children": true, "may_raise_parent_limit": false},
  "why": "此團隊最多使用專案核配額度"
}
```

父帳檢查 `spent + reserved + 新預留 <= limit`，對整條祖先鏈作一次序列化授權；不能讓兩個子 kernel 各讀同一個剩餘額度後都領走。父層可先切不重疊額度給子層，降低每次呼叫跨 daemon 的協調成本。週期起點也由父層定，不能靠 restart 重新開始。

**daemon／tick：必要**在啟動時固定群組身分、保留 restart 後的邏輯歸屬；階層政策與分帳算法可放 kernel／帳本任務。若只靠合作式 JSON，委派是協議；要抵抗任務自行改上限，還需可信的寫入與執行邊界。

### 3.2 cpu.weight、cpu.max、io.weight〔要改〕

Linux 的 weight 是競爭時的相對份額；cpu.max 是每個 period 的頻寬上限；io.weight 是 I/O 比例權重，其效果依底層支援。weight 不等於保證額度，也不等於 cap。[cgroup v2：資源分配模型](https://docs.kernel.org/admin-guide/cgroup-v2.html#resource-distribution-models)

aos 對應三個獨立欄位：`weight` 決定等候者的服務比例，`tokens_per_period` 限制速率，`lifetime_cost` 限制總花費。週期以指定控制 node 的回合計，pause 成員不會停止補額時鐘；外部供應商的每分鐘速率另以 monotonic 時間管理。LLM 請求與工具 I/O 可使用不同佇列、不同權重。

草圖直接使用上節 limits 加第 4 節服務帳；kernel 讀帳與 ready 清單，寫核可工作或 `resume rounds`。**daemon／tick：必要**在起任務前遵守核可清單；**呼叫入口必要**在每次 LLM／工具動作前遵守額度。單純把 `weight` 塞進 tasks.json、或改 Linux nice，都不會讓遠端 LLM 按這個比例服務。

### 3.3 memory.min／low／high／max〔要改〕

Linux 的 min 是有效範圍內的硬回收保護，low 是盡力保護，high 施加回收與節流，max 是硬限制、無法回收時可導致該群組 OOM；min／low 的有效保護受祖先與超額配置影響。high 本身不是 OOM 開關，max 也不是「事前分配保證」。[cgroup v2：Memory](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory)

aos 借四級政策，不照抄名稱造成「token 可回收」的誤解：

```json
{
  "schema": "aos.budget-bands.v1",
  "group": "project-x/team-a",
  "period_clock": "control",
  "period_rounds": 20,
  "reserved_min_tokens": 4000,
  "protected_target_tokens": 10000,
  "throttle_after_tokens": 30000,
  "deny_after_tokens": 40000,
  "throttle_action": "defer_background_calls"
}
```

最低保留只有在父額度已扣住、需求可滿足時才成立；protected target 是負載下優先保護；throttle 先延後背景工作；deny 在呼叫開始前拒絕。不把「還有多少可用 token」跟「模型 context 裡已佔多少 token」混在一起：前者是不可逆花費，後者是可調整的儲存／輸入長度。

kernel 讀 band 設定、帳本，寫下一批 grants 或降級請求；品質允許時由 agent 選便宜模型／縮短 context，kernel 不擅自改業務需求。**daemon／tick：啟動准入必要；LLM 入口：事前預留必要。** 沒有這兩個執行點，這四條線只能是告警線。

### 3.4 pids.max、rlimit、cpuset〔分別：值得借／要改／要改〕

Linux pids.max 限制群組新建 task；rlimit 有各項資源的 soft／hard limit，soft 是執行中的限制、hard 限制提高 soft 的幅度，並非通用「超 soft 只告警」；cpuset 限定 CPU 與記憶體 node 的放置範圍。[cgroup v2：PID](https://docs.kernel.org/admin-guide/cgroup-v2.html#pid)、[getrlimit 手冊](https://man7.org/linux/man-pages/man2/getrlimit.2.html)、[cpuset 文件](https://docs.kernel.org/admin-guide/cgroup-v1/cpusets.html)

aos 的三種對應：

- **pids.max → 全群組 live_tasks／inflight_calls。** 現有 tasks.json 的 `max_live` 只限制同名任務，多換名字即可繼續起；並行呼叫也不能用程序數替代。
- **rlimit → 每次呼叫／每任務上限。** 任務自己可以降低上限，提高則不能越過群組授權；實際 OS 的 fd、地址空間等限制可由 runner 設，token 仍由呼叫入口設。
- **cpuset → 可選模型池與工具池。** 例如只能用內部模型、只能用有特定工具的 worker；這是資格限制，不是份額。資源池容量不一時不得平均分配「一個槽位」就稱公平。

共用一份 tasks.json 任務項目〔提案，與第 9 節完整格式合用〕：

```json
{
  "name": "review",
  "mode": "keep",
  "inst": "review.inst.json",
  "resources": {
    "group": "project-x/team-a",
    "limits": {"calls_inflight": 1, "output_tokens_per_call": 1500},
    "allowed_pools": ["internal-text", "local-tools"]
  }
}
```

kernel 讀池容量與 task 宣告，寫 grant；tick 必須在一次啟動序列中保留群組槽位，跨 node 不能各自讀剩餘數後競爭超發。runner 退出釋放活任務槽，呼叫入口結束釋放呼叫槽。回合只決定何時再考慮排程，不能表示槽位已釋放。**daemon／tick：必要**補群組准入、失聯後對帳；**有更好**補 OS rlimit 支援。cpuset 的模型池適配主要在呼叫入口，不必進 daemon。

### 3.5 freezer〔要改；不是第一階段必要功能〕

Linux `cgroup.freeze` 停止群組及子樹程序，完成後才回報 frozen；它不是暫停程式自己的邏輯時鐘而已。[cgroup v2：freezer](https://docs.kernel.org/admin-guide/cgroup-v2.html#core-interface-files)

aos 需要先定義要停哪一層：停止新回合用現有 pause；停止新呼叫用 grant 閘門；暫停本機任務用未來的 freeze；取消遠端工作要供應商支援。即使本機 SIGSTOP 或 cgroup freeze，已送出的模型呼叫仍可能執行與計費。

若以後需要 freeze，kernel 可寫任務 `ctl.json`〔新增 op 提案〕：

```json
{
  "op": "freeze",
  "request_id": "k3-r121-freeze-1",
  "by": "control:kernel-r1",
  "why": "暫時釋放本機執行機會，保留程序狀態"
}
```

tick／tock 在邊界執行並回報 `freeze_requested／frozen`；runner 留在可管理的一側，不與 payload 一起失去記帳能力。現在沒有 freeze／thaw，且 `proto7-1/spec.md` 第 6 節已選擇不用 cgroup／subreaper 追捕所有逃逸子孫，因此若要求完整子樹凍結，要另訂運行層契約，不能當作現有保證。

**daemon／tick：有更好**加入邊界 freeze／thaw 與完成確認；若將它當強制搶佔工具，完整程序歸屬追蹤就成為必要。已 pause 的 node 沒有邊界，不能偷偷讓 daemon 任意時刻執行 ctl；可在 pause 前處理，或設計第 10 節的「不准啟動工作之維護回合」。

## 4. 公平排程：CFS、nice、EEVDF、autogroup

### 4.1 CFS 與 nice〔要改〕

**Linux 是什麼。** CFS 以加權的虛擬執行時間追蹤服務量，偏向選擇 vruntime 較小的可執行實體；nice 影響公平類別的相對權重，不是硬即時優先序。現代 Linux 公平排程已朝 EEVDF 演進，不能把歷史 CFS 的「挑最小 vruntime」當作所有現行版本的完整選擇規則。[CFS 文件](https://docs.kernel.org/scheduler/sched-design-CFS.html)、[sched 手冊的 nice 說明](https://man7.org/linux/man-pages/man7/sched.7.html)

**aos 對應。** 在同一個資源池選一個可比較的服務量 `service_i`，例如實際計費 token，或特定模型池的已占用槽位時間。示意更新式：`v_i += service_i × reference_weight / weight_i`。只在有需求、依賴已滿足且符合限制的群組間競爭；idle 不能一直累積無上限的欠額。

例：A 權重 100、B 權重 200，參考權重 100；A 已用 1000 token，B 已用 2000 token，兩者 v 都增加 1000。長期同時有需求且沒有其他限制時，才朝 1:2 分配。A、B 都跑三回合，不能證明公平。異質模型的 token 算力與價格不一樣，應按模型池分帳，或明說此處公平的是金額，不是運算工作量。

**草圖〔提案〕。** kernel 讀第 2 節帳摘要、task ready 狀態與 `weight`，寫 `$AOS7_TASK/fair-state.json`：

```json
{
  "schema": "aos.fair-state.v1",
  "pool": "internal-text",
  "service_unit": "billed_tokens",
  "account_seq": 938,
  "reference_weight": 100,
  "entities": {
    "project-a": {"weight": 100, "virtual_service": 1000, "ready": true},
    "project-b": {"weight": 200, "virtual_service": 1000, "ready": true}
  }
}
```

選定對象後，現有控制可寫 `.aosd/ctl/k-004.json`：

```json
{
  "op": "resume",
  "node": "team/agents/amy",
  "rounds": 1,
  "by": "control:kernel-r1",
  "why": "此群組的加權已服務量最低，本次給一回合機會"
}
```

這只能做到**回合機會的近似公平**。呼叫完成前先按保守估計扣暫定服務額，結束後補差，避免一直把「尚未記帳」的長呼叫當便宜工作。新加入者的 v 放在現有公平基準附近；restart 沿用 task_key 的帳；不得每次重起都歸零。需要 token 層級的公平時，輸出改成第 6 節的有界 grant。

**daemon／tick：試做不必新增**，現有 `resume rounds` 可跑實驗；**精確執行必要**是起任務／呼叫准入。無需 daemon 實作紅黑樹或 nice 換算表，選人算法留在 kernel。

### 4.2 EEVDF：lag 與虛擬截止點〔要改〕

**Linux 是什麼。** lag 表示理應得到與實際得到服務之差；非負 lag 的任務具資格，再選其中最早的虛擬 deadline。短服務片段可改善延遲；虛擬 deadline 不是使用者交付日期。睡眠任務的 lag 處理避免靠短暫睡眠洗掉超用紀錄，具體細節會隨版本演進。[EEVDF 文件](https://docs.kernel.org/scheduler/sched-eevdf.html)

**aos 對應。** `lag_i = entitled_service_i − actual_service_i`；使用簡化的「虛擬起點＋請求服務量／權重」作排序點，先判公平資格再看誰較短。這是 EEVDF 啟發的設計，並非聲稱重現 Linux 實作。已在 provider 執行的長呼叫通常無法細切，短片段應是一次有 max output 的 LLM 呼叫、一次工具工作或合作式 checkpoint。

kernel 讀 work 宣告、資源帳，寫策略狀態與 grants〔提案〕：

```json
{
  "entity": "project-a",
  "lag_tokens": 1200,
  "eligible": true,
  "request": {"work_id": "reply-31", "estimated_tokens": 600},
  "virtual_deadline": 1600,
  "deadline_kind": "fairness_virtual",
  "why": "有公平欠額，且這次回覆的預估片段較短"
}
```

不要照 JSON 的小 deadline 就無條件插隊；需核驗估計誤差並按實際消耗補帳。小任務連續插隊時，大任務要累積等待權益或保留較大 grant，否則會被「每次剩餘額度都放不下」餓死。重啟／睡眠／改名不能清掉服務帳。

**daemon／tick：必要**提供有界工作准入與消耗回報，才能把此政策變成可執行公平；只有 pause／resume 時，這只是選擇下一批回合的啟發式，不具有 Linux 的延遲界線。

### 4.3 autogroup／群組公平〔值得借〕

Linux autogroup 可按 session 將工作分組，讓大量批次程序不因數量多就壓過其他群組；其效果受群組排程及 cgroup 配置影響。[sched 手冊：autogroup](https://man7.org/linux/man-pages/man7/sched.7.html)

aos 改用明確的 `owner／project／group`，不要自動把每個新 node 當成獨立公平實體。專案 A 生 20 個 agent、B 只有 1 個，頂層各拿相同權重，再於各自內部分配。node id 是路徑（S-14），改路徑不應免費重置專案配額。

草圖使用第 3.1 節 groups 檔，再於第 9 節 task 宣告 `group`；kernel 讀群組成員與需求，先發群組額度、再發任務額度。**daemon／tick：必要**把核准的付費／公平群組寫進 birth；分組政策可完全在 kernel，無須仿造 POSIX session。

## 5. SCHED_DEADLINE、准入控制與 RT throttling

### 5.1 SCHED_DEADLINE〔要改〕

Linux 用 EDF 加 CBS 管理每個週期的執行額度；`runtime <= deadline <= period`，配合准入控制避免承諾超過能力。這三個量在 Linux 都是時間；單看平均利用率的加總，不足以證明任意多核、受限 deadline 工作集合都能準時完成。[SCHED_DEADLINE 文件](https://docs.kernel.org/scheduler/sched-deadline.html)

aos 可借「先申請，再承諾」：任務宣告每 10 個控制回合需要 2 次呼叫、4000 token，希望第 6 回合前得到服務。**runtime 不能直接改名 tokens 後仍套 `runtime <= deadline`**，因為單位不同。分開寫資源向量與回合期限：

```json
{
  "schema": "aos.reservation-request.v1",
  "work_class": "interactive",
  "clock_node": "control",
  "period_rounds": 10,
  "relative_deadline_rounds": 6,
  "service_request": {"tokens": 4000, "calls": 2},
  "max_call_tokens": 2000,
  "guarantee": "admission_opportunity",
  "on_miss": "report_and_defer"
}
```

kernel 讀 pool capacity、已有 reservations 與 ready 工作，寫 `<node>/.aos/admission/<work-id>.json`〔提案〕：

```json
{
  "work_id": "reply-cycle-19",
  "accepted": true,
  "clock": {"node": "control", "release_round": 190, "deadline_round": 196},
  "reserved": {"tokens": 4000, "calls": 2},
  "guarantee": "admission_opportunity",
  "why": "剩餘額度與槽位足夠；不保證遠端回覆或內容完成"
}
```

初步容量檢查可用各維度 `Σ(request_per_period / period_rounds) <= 可承諾的每控制回合容量`，還必須檢查 deadline 前的需求尖峰、最大片段、並行槽與依賴。若來源容量只有「每秒 API 配額」，不能把一回合當固定秒數來建立硬保證；只能用實測下界做保守估計，或把保證降為盡力服務。

成功准入保證的是本系統願意在期限內提供機會／預留額度，並不保證模型準時、正確地完成業務。期限錯過記 miss，不為了追趕而無限制補跑過期批次。任務被 pause 時，控制時鐘的 deadline 繼續走；若要「暫停也延長期限」，必須另訂契約。

**daemon／tick：必要**執行授權的啟動窗口、回報實際開始回合；**LLM／工具入口必要**執行 reservation。排程本身仍留 kernel。硬牆鐘即時保證在外部 LLM 延遲不可控的情況下不成立。

### 5.2 RT throttling〔值得借其保底原則〕

Linux RT 頻寬控制限制即時工作在 period 內的 runtime，讓失控高優先工作不致吃完所有服務機會；具體能力受配置影響。[RT group scheduling 文件](https://docs.kernel.org/scheduler/sched-rt-group.html)

aos 的 `urgent` 不能有無上限優先權。控制面、帳務與保底排程要有可用程序槽、I/O 容量；LLM 排程提案本身也有 token cap。保底算法則應不依賴 LLM，錢花完仍能停止接案與結算。

kernel 讀群組用量與急件佇列，寫 `policy.json` 與 grants〔提案〕：

```json
{
  "schema": "aos.class-policy.v1",
  "period": {"clock_node": "control", "rounds": 20},
  "control": {"reserved_task_slots": 2, "requires_llm": false},
  "urgent": {"max_token_share": 0.7},
  "batch": {"minimum_service_share_when_ready": 0.1},
  "on_urgent_exhausted": "compete_as_normal"
}
```

這是 aos 自己的政策，不是 Linux 的預設比例。share 指同一服務池、同一窗口的份額；總保留量須通過准入，不能全員都宣告最低 90%。**daemon／tick：必要**維持控制操作可服務、區隔工作槽與控制槽；不用直接替 Python kernel 設 SCHED_FIFO，更不能靠給它 RT 權限解決 token 分配。

## 6. 排程策略可抽換：以 sched_ext 為參考

### 6.1 借的是接口與復原責任〔值得借〕

Linux sched_ext 讓 BPF 程式定義排程策略，可動態啟停；偵測錯誤、runnable task 停滯或人工觸發時，撤掉 BPF scheduler，回到 fair-class 排程。它也有部分接管模式。文件明示 BPF 排程接口會演進，不宜把它想成永遠不變的 ABI。[sched_ext 官方文件](https://docs.kernel.org/scheduler/sched-ext.html)

aos 不必執行 BPF。現有 `snapshot → run_rules → apply_decision` 已接近可換策略接口，應把政策輸出改成**提案**，由確定性的驗證／套用端控制副作用。規則程式、不同公平算法與 LLM 都產生相同 JSON。

### 6.2 任務分工與檔案協議〔提案〕

| 元件 | 做什麼 | 讀／寫 |
|---|---|---|
| kernel 管理任務 | 做快照、驗證提案、核配、核對回條 | 讀狀態／帳；寫 `input.json`、grants、ctl、decision log |
| policy 任務（可為 LLM） | 從有限快照提出下一批順序 | 只讀 policy input；只寫 `proposal.json` |
| 保底策略 | 無 LLM、固定成本的加權輪替＋准入檢查 | 使用同份快照與服務帳 |
| daemon／tick／呼叫入口 | 執行已驗證且未過期的授權 | 不替業務做價值判斷；回報實際結果 |

四者不必各是一支常駐程序。驗證器與保底可在同一 kernel 程式；LLM 呼叫必須放在獨立 policy 任務，避免一個同步 API 呼叫卡住整個管理迴圈。所有任務仍由 tick 啟動（S-10、S-16）。

`<control-node>/policy.json`：

```json
{
  "schema": "aos.scheduler-policy.v1",
  "policy": {"kind": "agent", "task_name": "scheduler-agent", "revision": 7},
  "scope": ["team/agents/amy", "team/agents/bob"],
  "input": ".aos/scheduler/input.json",
  "proposal": ".aos/scheduler/proposals/proposal.json",
  "fallback": "weighted_round_robin",
  "clock_node": "control",
  "proposal_ttl_rounds": 2,
  "max_tokens_per_proposal": 2000,
  "max_grant_rounds": 2,
  "mode": "shadow"
}
```

初期 shadow 只寫差異報告，不下真控制；再限一個群組接管，最後擴大範圍。這不是本次實作，只是建議導入順序。

`input.json` 只包含資源需求、ready／blocked、版本與簡短業務標籤；不要把全部信件內容直接當作排程指令：

```json
{
  "schema": "aos.scheduler-input.v1",
  "snapshot_id": "g3-control-r120-s218",
  "daemon_gen": 3,
  "policy_revision": 7,
  "clock": {"node": "control", "round": 120},
  "valid_until_round": 122,
  "capacity": {"calls_free": 1, "tokens_unreserved": 6000},
  "candidates": [{
    "work_id": "amy-reply-31",
    "node": "team/agents/amy",
    "observed_round": 80,
    "ready": true,
    "estimated_tokens": 1500,
    "wait_control_rounds": 4,
    "weight": 100,
    "class": "interactive"
  }],
  "allowed_actions": ["grant", "defer"],
  "protected_targets": ["control", "accounting"]
}
```

LLM 寫 `proposal.json`：

```json
{
  "schema": "aos.scheduler-proposal.v1",
  "snapshot_id": "g3-control-r120-s218",
  "policy_revision": 7,
  "actions": [{
    "op": "grant",
    "work_id": "amy-reply-31",
    "max_calls": 1,
    "reserve_tokens": 1500,
    "max_rounds": 1,
    "reason_code": "oldest_interactive",
    "why": "已等待四個控制回合，且本次額度足夠"
  }]
}
```

驗證器檢查 schema、有限且非負數值、數量上限、scope、policy 版號、daemon 世代、工作仍 ready、帳本剩餘額度、保護對象與飢餓限制。`snapshot_id` 只供定位，不能取代套用時重新檢查。按全案驗證後才核配，避免前半批已改帳、後半批才發現超額。

### 6.3 grant 如何變成真控制

**現況版：** 驗證後寫現有 daemon `resume rounds: 1`，並記 pending，下一輪讀回條與 status。切換前確認前一條線已 paused；此做法只限制開回合，對在途呼叫不構成互斥。`proto7-1/probes/llmkernel/kernel_task.py` 已有讓 LLM 讀寫檔排程的探針，照稿版也會確認 pause 生效；那是試驗，不代表正式 kernel 已有受限提案或強制隔離。

**受控版〔提案〕：** kernel／帳本服務核發 `<node>/.aos/grants/g-481.json`，tick 或呼叫入口只在 grant 存在、相符且未消耗時動作：

```json
{
  "schema": "aos.grant.v1",
  "grant_id": "g-481",
  "request_id": "req-481",
  "work_id": "amy-reply-31",
  "node": "team/agents/amy",
  "task_key": "team/agents/amy:agent",
  "daemon_gen": 3,
  "policy_revision": 7,
  "clock": {"node": "control", "issued_round": 120, "expires_round": 122},
  "allow": {"calls": 1, "tokens_reserved": 1500},
  "consume": "once",
  "why": "公平輪替核配"
}
```

grant 的消耗要在共享帳本中原子 claim，不是每個 worker 自己刪檔就算；同一 grant 不可被兩個呼叫同時使用。到期只取消尚未開始的授權；已開始的 reservation 要等結算或列 unknown，不能到期自動退款。取消／逾時後遠端是否仍計費不確定，要留在途負債直到有證據結清。

**daemon／tick 必要能力：** 啟動核可、帶版本的 grant、過期判斷、回條與執行去重。**agent／呼叫入口必要能力：** 每個 LLM 呼叫及重試都先領額，設定可強制的輸出上限，結束後結算。單靠 tick 管 inst 的出生，管不到常駐 inst 後續發出的呼叫。

### 6.4 錯誤、太慢、把自己排死

1. **LLM 缺席也照常排。** 每次控制 tock，提案缺失、格式錯、版本舊、超額或超過 TTL，就立即用保底策略。tick 不等 LLM；晚到提案因 snapshot 過期而丟棄。只需能指出哪個條件不合，無須請另一個 LLM 仲裁。
2. **保底不能依賴提案者。** kernel 控制迴圈與 scheduler-agent 是不同任務；管理 node 不在此策略的可 pause scope。scheduler-agent 沒有直接修改 ctl、policy、帳本的權限；合作式原型可先限工具路徑，強保證則要第 11 節的 OS／runner 隔離。
3. **保底也要有上限。** 保底只給一個有界工作片段，先檢查硬額度，再以穩定群組身分輪替，含最大等待保護。資源帳 unknown 時拒絕新付費工作並允許觀測／結算，不能無條件 resume 全世界。
4. **控制 kernel 自己掛掉。** `keep` 只能在控制時間線仍前進時補起。若要接近 sched_ext 的底層保證，daemon 還須提供事先配置的控制任務 lease：lease 過期後停止接受新 grants，撤銷未開始的舊授權，在下一個控制 tick 啟動固定的 recovery inst。recovery 讀帳並做安全保底，不由 daemon 現場問 LLM。
5. **時間線也停止怎麼辦。** 用控制回合判提案過期；若控制時間線本身卡住，靠 daemon 的 monotonic watchdog 判運行異常。這是 S-06 的運行保底，不把秒數冒充業務回合。復原只處理明確授權的控制 node，不幫使用者自動解除所有 S-22 控制環。
6. **避免排程成本超過工作成本。** 不必每一回合問一次 LLM；在需求／優先序／資源池有重大變化時才請它更新較長期政策，有效期內由便宜的規則選下一件。所有提案成本歸 scheduler 自己帳，超額便只用保底。

保底事件寫 `decisions.jsonl`〔提案〕：

```json
{
  "clock": {"node": "control", "round": 123},
  "event": "scheduler_fallback",
  "policy_revision": 7,
  "reason_code": "proposal_expired",
  "proposal_snapshot": "g3-control-r120-s218",
  "fallback": "weighted_round_robin",
  "why": "提案超過兩個控制回合，改用已驗證的保底策略"
}
```

**結論：** 現有架構可先完成策略插槽與軟保底；要宣稱「錯誤排程器永遠排不死系統」，必須補執行隔離、控制面資源保留與 daemon lease／復原路徑。把這些當成新增能力，不能只仿照 sched_ext 的名字。

## 7. 壓力、回收與背壓

### 7.1 PSI：量受阻，不只量使用率〔要改〕

Linux PSI 記錄因 CPU、記憶體、I/O 稀缺而停滯的時間。some 表示至少有工作受阻；full 表示所有非 idle 工作同時受阻。system-level CPU full 有特殊限制，不能當成通用的「CPU 都不動」指標。[PSI 文件](https://docs.kernel.org/accounting/psi.html)

aos 應區分 `waiting_budget／waiting_slot／waiting_tool／waiting_dependency／waiting_human／waiting_external`；沒有信的 idle 不算壓力。等外部模型是服務延遲，不一定是本地資源不足；工作是否真正 ready 也要由任務宣告及依賴狀態核對。

kernel 讀統一 status 和 ready 佇列，輸出自己的 `pressure.json`〔提案〕：

```json
{
  "schema": "aos.pressure.v1",
  "window": {"clock_node": "control", "from_round": 101, "to_round": 120},
  "samples": 20,
  "known_samples": 19,
  "budget": {"some_samples": 8, "full_samples": 2},
  "slots": {"some_samples": 12, "full_samples": 3},
  "ready_count": 7,
  "oldest_ready_wait_rounds": 9,
  "inflight_calls": 3,
  "why": "這是控制回合抽樣率，不是牆鐘時間比例"
}
```

定義 some 為該次樣本至少一件 ready 工作被此資源阻擋；full 為有需求但全體可服務工作都因此無法前進。unknown 樣本另算，沒有工作時 full 是零，不把「全員放假」判為壅塞。也可另存 monotonic stall_ms，供操作與供應商速率調整用，不與回合比例混算。

策略例如連續兩個窗口出現高 slot 壓力，就限制生產端派生工作、先清最老佇列；恢復門檻低於節流門檻，避免反覆停／開。kernel 寫下一批 grants、task 啟動許可或現有 pause。**daemon／tick：必要**提供一致生命週期；**agent／入口必要**提供等待原因。kernel 不能從 `pid 活著` 自行推導 PSI。

### 7.2 OOM killer、oom_score_adj、systemd-oomd〔要改〕

Linux OOM killer 在記憶體無法滿足時選擇犧牲者，`oom_score_adj` 可調整被選傾向（-1000 是排除該 OOM 選擇的特殊值，不是任何情況都殺不死）。systemd-oomd 是使用者空間服務，利用 cgroup v2 與 PSI 在 kernel OOM 前終止選中的群組；它不是 kernel 內建排程器。[oom_score_adj 手冊](https://man7.org/linux/man-pages/man5/proc_pid_oom_score_adj.5.html)、[systemd-oomd 官方原始文件](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd-oomd.service.xml)

aos 可以有一個壓力管理 kernel 任務，按「未來可省成本、可恢復性、業務重要性、重做成本」選取消對象。不要選 token 已花最多的就殺：花過的錢無法回收，快完成的工作反而可能最不該殺。

kernel 讀帳、pressure、checkpoint 與 task policy，寫決策，再寫真正的 task ctl。`<node>/eviction-policy.json`〔提案〕：

```json
{
  "schema": "aos.eviction-policy.v1",
  "order": ["deny_new_background", "request_checkpoint", "cancel_restartable"],
  "classes": {
    "control": {"protected": true},
    "batch": {"eviction_preference": 100},
    "interactive": {"eviction_preference": 20}
  },
  "require_future_savings": true,
  "do_not_kill_for_quality_score_only": true
}
```

現有 `ctl.json` 能表達最後一步：

```json
{"op": "kill", "by": "control:kernel-r1", "why": "取消可重做背景工作，降低後續呼叫需求"}
```

但需先把其 `keep` 定義停用／移出 task 表或拒絕後續 grant，否則下一個 tick 又起回來。停用的是新啟動，不代表既有在途費用消失；是否要取消同一工作群組的相依任務，必須由工作契約決定。

**daemon／tick：現在可做邊界 kill；必要補充**是 request 回饋及「停新工作但允許控制收尾」；checkpoint 是 agent／工具協議，不是 daemon 替任務保存語意狀態。已 pause 的 node 不能宣稱此 kill 立即執行。

### 7.3 LRU／記憶體回收〔要改〕

Linux 回收利用頁面的存取／老化資訊辨認較冷內容，Multi-Gen LRU 以多個世代改善這類判斷；目的是在壓力下保留較有用的工作集。[Multi-Gen LRU 文件](https://docs.kernel.org/admin-guide/mm/multigen_lru.html)

aos 可回收的是快取、可重建工具結果、context 的可選部分與過期日誌；已花 token 不可回收。目標、承諾、名冊、尚未完成的請求與帳務不是「最近沒讀就可刪」的快取。R-2／R-13 已證明只按最近幾封信保留記憶會遺失合作對象。

kernel 讀 context／cache inventory 與磁碟用量，寫 `memory-policy.json` 給 agent，或透過 spawn 啟動有範圍限制的整理 inst〔提案〕：

```json
{
  "schema": "aos.context-policy.v1",
  "max_input_tokens": 6000,
  "pin": ["goal", "roster", "open_commitments", "latest_checkpoint"],
  "evict_order": ["rebuildable_tool_cache", "duplicate_messages", "old_detail"],
  "summary_requires_source_refs": true,
  "charge_summary_calls": true,
  "account_ledger_is_not_cache": true
}
```

整理過程可用「存取回合」排序，但跨 node 必須保留 clock_node，不比較裸 round。摘要會失真、也要花錢；需留下來源與可還原原文的位置。`tasks-old/` 現在只是搬移，沒有釋放空間；不能宣稱現有歸檔已解決磁碟上限。

**daemon／tick：通常不用新功能**，kernel 可 spawn 清理任務；**有更好**是提供檔案／日誌用量、保留世代與磁碟低水位。磁碟硬限額要 OS quota 或受控寫入端，不能只靠回合後掃描。

### 7.4 throttle／backpressure〔值得借〕

Linux 資源控制能讓消耗端延後執行；aos 更需要讓生產端知道下游沒容量。單純 pause 消費 node，仍讓別人往它 inbox 寫信，會把問題轉成磁碟和下一次 prompt 爆量。這裡借的是有界佇列與消耗反饋的原則，不宣稱 Linux 有一個同名統一服務。

kernel 讀 `queue-stat.json`，寫 `<receiver>/admission.json` 或 grant；寄信者經掛載讀它。送件改為有 request id 的請求與回條〔提案〕：

```json
{
  "schema": "aos.queue-admission.v1",
  "queue": "team/agents/bob/inbox",
  "max_pending": 40,
  "pending": 40,
  "accepting": false,
  "retry_after": {"clock_node": "control", "round": 125},
  "reason_code": "queue_full",
  "why": "收件端待辦已滿；送件者保留原件，不重複投遞"
}
```

「先讀 pending 再寫信」仍會競爭超額；硬上限需單一收件入口或原子 reservation。未被接受的工作留在 sender outbox，限制重試次數，不能每回合叫一次 LLM 重寫同一封催辦。既有 agent outbox 主要處理掛載未就緒／寄件失敗，不等於容量背壓。

**daemon／tick：不必理解信件內容；必要**是若採工作准入，提供可通用的 request／receipt 機制。佇列計數、去重與 retry_after 可由專門任務／工具協議完成。若不用受控入口，就誠實標成軟背壓。

## 8. 多維資源：保留向量，不把一切加成一個分數

### 8.1 哪些是硬限制，哪些是軟目標

| 維度 | 原始量與誰記 | 可做硬限制的條件 | 軟目標／陷阱 |
|---|---|---|---|
| token | 呼叫入口記 input／output／其他計費類別；provider 結算 | 預留完整上界、限制輸出、所有呼叫都經入口 | 不同模型 token 不等價；估計不是結算 |
| 金額 | 帳本依模型、費率版號、幣別記整數金額 | 入口可預估保守上界且價格契約明確 | 價格未知或遠端超時計費未明時只能保守扣住 |
| LLM 呼叫數 | 入口記每次嘗試、重試、結束 | 每次送出前原子領取 | 一次呼叫可能很大，不代表等成本 |
| 並行槽 | 入口／runner 記占用與釋放 | 共用原子配額，失聯要對帳 | 任務進入 idle 不代表外部呼叫已取消 |
| 牆鐘經過時間 | runner／入口記 monotonic duration | 可限制本機等待／執行時間 | 不保證外部服務已停止；不是成功完成期限 |
| 回合 | tick／tock 的 node、epoch、round | 可限制啟動窗口、存活回合與回合授權 | 不同 node 的一回合不是相同工作量 |
| 磁碟／檔案數 | 檔案系統／受控寫入端記 bytes、檔案數 | quota／受控寫入限制 | 掃描後清理只有反應式上限；小檔有額外成本 |
| context 空間 | agent 組 prompt 時量模型 token | 送出前截限並確認必要內容可放下 | 截短不等於更好讀；摘要有失真風險 |
| 人的注意力 | UI／人記介入次數、審閱時間、未結決策數 | 可限制通知數／待審數 | 很難事前保證人的實際心力 |
| 易用性 | 人的任務完成率、操作步數、修正次數、錯誤恢復時間 | 只能硬限具體代理，如最多三個必要操作 | 「少步驟」可能掩蓋複雜性；不是可互換資源 |
| 人類可讀性 | schema 檢查、盲讀測試、人工或 LLM 評分 | 可硬驗 JSON 合法、欄位存在與術語一致 | 可理解、無歧義與內容正確仍是品質目標 |

判斷一個限制是否「硬」，要問執行端能不能在副作用發生前拒絕，不是看 JSON 欄位名字是不是 `max`。目前 `usage.json`、tick 邊界 kill 與 pause 不足以保證前四項全部硬限制。

具體例子：群組剩 5000 token，某次請求已確認輸入 3000、可強制的最大輸出 1000，入口先預留 4000，其他請求只能看到剩 1000。實際輸出 600 時結算 3600、釋放 400；若逾時且不知 provider 是否完成，就保留未結 reservation，不能因本機沒收到回覆就全部退還。此例假設沒有額外計費類別；若模型有推理 token 等額外消耗，必須一起納入可證明的上界，否則只能標估計上限。重試是另一筆可能付費的請求，仍須獨立預留。

### 8.2 建議決策順序

1. **資格與權限。** 工作存在、依賴已滿足、可用模型／工具符合要求。
2. **硬限制與預留。** 所有維度都可容納才准入；任一硬上限不足就延後或拒絕。
3. **最低保留及群組公平。** 先保障已核准的保留額度，再在有需求者間分配。
4. **服務目標。** 在以上可行方案中比較 deadline、最老等待、預期品質與成本。
5. **品質驗收與人工回饋。** 驗收結果更新估計與未來策略；不回頭把已花成本改寫成零。

權重可用在第 3、4 步，但不把「多花 1000 token」和「少一次人工修正」硬說成固定匯率。若真的需要效用函數，量尺、正規化方式、權重與負責人須明示，保存各項原值，讓人知道取捨。與其立刻引入五維黑箱分數，初版用上述順序比較更易讀、更好除錯。

### 8.3 DRF〔要改；第二階段再用〕

DRF 是 Linux 以外的多資源公平研究：把各資源份額正規化，某使用者最大的那項稱 dominant share，再按此處理公平分配。在原論文的資源與需求假設下有相應公平性質，不能任意換成主觀評分後繼續宣稱那些性質成立。[DRF 原論文入口](https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types)

示意式：對同一分配域，`dominant_share_i = max_r(allocation_i,r / capacity_r)`；有權重時比較 `dominant_share_i / weight_i`，但實作還須定義需求、可切分程度與工作能否真的放進剩餘容量。

例如某窗口有 10000 token 額度與 4 個呼叫槽：A 分配 2000 token、4 槽，dominant share 為 1；B 分配 5000 token、1 槽，為 0.5。兩份配置**不能同時完全滿足**，因總槽數是 5；DRF 用來決定如何退讓，不是因各自某個份額小就通通批准。

更大的問題是 token 在窗口內被消耗、槽位會隨完成釋放，這不是完全相同的資源模型。建議先分兩層：可重用槽位／記憶體採容量分配；token／金額採窗口服務份額及終身帳本。若合成「窗口化 DRF 啟發式」，就用這個名稱，不宣稱原始 DRF 保證。錢和 token 高度相關時，也不要把同一稀缺性重複加權。

kernel 讀各 pool capacity、已分配向量、工作需求，寫自己的 fair-state 與 grants〔提案〕：

```json
{
  "schema": "aos.multiresource-policy.v1",
  "reusable_pool_policy": "weighted_drf",
  "reusable_resources": ["call_slots", "tool_memory_bytes"],
  "consumable_policy": "weighted_service_with_budget",
  "consumable_resources": ["tokens", "cost_microunits"],
  "clock_node": "control",
  "window_rounds": 20,
  "quality_is_resource_share": false
}
```

一個大工作暫時放不下時，可讓小工作 backfill，但必須記錄保留起點或最大等待，避免永遠碎片化。跨不同 provider 的槽位不可直接加在一起，應按能力相同的 pool 分別分配。

**daemon／tick：必要前提**仍是向量記帳與准入；不必理解 DRF。初版沒有可靠 demand 與容量資料時，先用群組權重加硬限制，比一開始就套 DRF 有用。

### 8.4 易用性與可讀性由誰量

S-01 的檢驗可以具體化：讓沒看過內部實作的人或 LLM，只讀一份 snapshot，回答「誰在等什麼」「下一步能怎麼做」「哪一份 ctl 尚未生效」。測答對率、需讀的檔案數／token、錯操作次數、完成所需人工介入，不只評「文字漂不漂亮」。

建議由三層量測：確定性檢查器驗 schema、必填原因、單位與連結；獨立評估 agent 依版本化 rubric 做抽樣盲評；人定期校正與裁決。任務作者不能自己給分就換到更多額度；評估任務同樣記 token 帳，並設評估總額上限。

`<artifact>/review.json`〔提案，評估者寫，kernel 只讀〕：

```json
{
  "schema": "aos.quality-review.v1",
  "artifact": "work/result.json",
  "artifact_revision": 8,
  "rubric": "operator-can-explain-next-action-v2",
  "evaluator": {"kind": "human", "id": "reviewer-1"},
  "observations": {"questions_correct": 4, "questions_total": 5, "files_opened": 2},
  "scores": {"readability": 4, "usability": 3},
  "scale": {"min": 1, "max": 5},
  "evidence": ["沒寫清楚 pause 不等於停止 LLM 呼叫"],
  "status": "needs_revision"
}
```

kernel 可據此把「補說明」列入工作、發給評估或修訂 inst 一次有界 grant；不要直接因分數 3 就 kill 作者。少寫內容可能提升表面簡潔卻降低正確性，因此驗收必須保留「讀者是否做對」的外部結果。易用性／可讀性主要是**品質限制與效用目標**，人的審閱時間、prompt token 和人工修正次數才是相關的稀缺成本代理。

**daemon／tick：不需要品質評分功能。** 只需能啟動評估任務、管其額度、保存產物與身分；語意評分留在人與 agent 層。

## 9. inst 當任務內容：task_struct、exec 與生命週期

### 9.1 執行描述與活實例分開〔要改〕

Linux 的 task_struct 是活 task 的核心紀錄，task 粒度包含 thread；fork 建新程序，exec 替換現有程序映像，不等同建立新 PID。aos 的 inst 比較接近 exec 的輸入描述，不等同 task_struct。[taskstats 的 task 定義](https://docs.kernel.org/accounting/taskstats.html)、[fork 手冊](https://man7.org/linux/man-pages/man2/fork.2.html)、[execve 手冊](https://man7.org/linux/man-pages/man2/execve.2.html)

對照關係應是：

| Linux 概念 | aos 對應 |
|---|---|
| 可執行檔、argv、環境與 I/O 設定 | inst 原始／解開後的執行描述 |
| task_struct 與 PID | birth、tid、runner 身分、權威狀態與使用量的組合 |
| fork／clone | tick 消費 spawn 或 tasks.json 而建立實例；不是讓 kernel 直接 fork |
| exec | runner／aos-exec 解讀 inst 後執行；aos restart 則建立新實例 |
| 排程屬性、cgroup 成員 | tasks.json 的資源／排程宣告及核准後 birth 紀錄 |

`proto7-1/lib/aos_inst.py` 現在處理 `_metainfo` 與 `argv／stdin／stdout／stderr／exit／cwd／envs`，還有 `$env／$fmt／$ref／$opt` 指示詞；不會替 kernel 解釋 token、優先級或品質需求。新增頂層欄位不代表 runtime 自動採用，因此建議**先把資源宣告放 tasks.json**，保留 inst 作為執行契約。

### 9.2 kernel 需要知道的宣告〔提案〕

```json
{
  "name": "reviewer",
  "mode": "keep",
  "inst": "reviewer.inst.json",
  "max_live": 1,
  "task_key": "project-x/reviewer",
  "definition_revision": 4,
  "resources": {
    "group": "project-x/team-a",
    "requests": {"tokens_per_step": 2000, "call_slots": 1},
    "limits": {"tokens_per_call": 3000, "calls_inflight": 1},
    "allowed_pools": ["internal-text"]
  },
  "scheduling": {
    "class": "interactive",
    "weight": 100,
    "clock_node": "control",
    "deadline_round": 150,
    "dependencies": ["draft-ready"],
    "preemption": "between_steps"
  },
  "lifecycle": {
    "restart_policy": "on_failure",
    "restart_definition": "pinned",
    "restart_limit": {"count": 3, "window_rounds": 20, "clock_node": "control"},
    "checkpoint": "work/checkpoint.json",
    "side_effects": "idempotency_key_required"
  },
  "observability": {"activity": "activity.json", "progress": "progress.json"},
  "quality": {"rubric": "review-checklist-v2", "required_artifact": "work/review.json"}
}
```

`requests` 是估計，用於准入與排序；`limits` 是允許上限，要有入口執行。class／weight 是偏好，不能突破父額度；deadline 附時鐘；dependencies 是 kernel 能觀察的事件或產物，不要求它讀懂所有文章內容。`preemption` 告訴 kernel 哪裡能安全停，`side_effects` 告訴 supervisor 重做的風險。

初期只需 group、估計／上限、weight、可恢復性幾項，其餘可選並提供明白預設。JSON schema 應報出「哪個欄位不支援」，不能靜默接受一個實際無效的硬限制。

**inst 可選增補方向：** 若想讓同一份 inst 隨處攜帶資源需求，可另定 versioned `requirements` metadata 或 sidecar，例如 `reviewer.requirements.json`，由 tick 讀取後與 tasks.json 的站點政策合併；限制取更嚴者、需要的能力不可被任務自行升級。不要把排程政策藏在 argv 或 prompt 中讓 kernel 猜。

**daemon／tick：必要**驗證宣告、把「核准值」與實際執行定義寫進 birth。inst 可透過 `$ref` 或環境改變解析結果，僅記 inst 路徑不足以重現同一工作；應保存解開後的執行描述、必要輸入版號與 digest，敏感環境值另作遮蔽。digest 僅證明一致，不能代替權限檢查。

### 9.3 restart 的定義必須可讀

現有 `proto7-1/lib/aos7_task.py:run_ctl()` 複製 birth 的 name／argv／inst／subroot／mounts 再寫 spawn，`restart_of` 指舊 tid；**不是重讀 tasks.json 的最新定義**。而 birth 的 inst 是路徑，若該檔已改，重跑也未必是相同內容。`infra-needs.md` N-31／Q6 已記錄 LLM 誤操作，不在本報告替使用者把 Q6 定案。

未來介面可以明說 `restart_definition: "pinned"` 或 `"latest"`，記錄 `definition_revision`，回條列舊／新版；pinned 要真的留解析快照。現在改任務定義後要靠更新 tasks.json 加 kill 讓 keep 重起，不能用「restart 一定套新設定」來設計控制器。

### 9.4 狀態 R／S／D／Z／T 與信號〔要改〕

Linux R 是 running／runnable，S 是可中斷睡眠，D 是不可中斷等待，Z 是退出但待回收，T 是停止；這是程序執行狀態，不是業務狀態。信號提供通知／終止等機制，SIGKILL／SIGSTOP 不能被攔截；但 D 狀態下不代表送 SIGKILL 就立即完成終止。[proc_pid_stat 手冊](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html)、[signal 手冊](https://man7.org/linux/man-pages/man7/signal.7.html)

aos 不應讓 LLM 看單字母推理。把三條軸分開：生命週期 `born／live／ended／lost／unknown`；活動 `idle／ready／running_step／waiting_external／waiting_dependency／waiting_human`；管理狀態 `admitted／throttled／freeze_requested／frozen`。Linux S 可能只是 agent 正等 tock，不能直接映射為「沒有工作」；保留 exit.json 的資料夾也不是 Linux zombie。

任務寫 `activity.json`〔提案〕，runner／tick 的生命週期仍是權威：

```json
{
  "activity": "waiting_external",
  "wait_reason": "llm_response",
  "request_id": "req-481",
  "clock": {"node": "team/agents/amy", "since_round": 80},
  "last_tock_seen": 80,
  "progress_seq": 12,
  "progress_evidence": "work/checkpoint.json",
  "safe_point": false,
  "next_need": "provider_response"
}
```

kernel 讀此檔與權威 status 決定是否續等、告警或 restart，仍只寫 ctl。`progress_seq` 只在有可說明的工作進展時變；heartbeat 另列。服務慢、等待人、等待資源，不以同一個 stuck_rounds 處理。

**daemon／tick：必要**統一生命週期；**有更好**提供合作式 `checkpoint_requested／cancel_requested` 通知與確認，保留強制 kill 作收尾。普通 JSON 請求不能假裝具有 OS signal 的強制效果。

### 9.5 init 收養、kthread、workqueue〔要改〕

Linux 孤兒程序由最近的 subreaper 或所屬 PID namespace 的 init 等收養，負責 wait 回收；這不等於恢復它的業務。kthread 是 kernel 執行脈絡，workqueue 把工作交給受管理的 worker 執行。[subreaper 手冊](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html)、[kernel thread API](https://docs.kernel.org/driver-api/basics.html#kernel-threads)、[workqueue 文件](https://docs.kernel.org/core-api/workqueue.html)

aos 分三件事：runner 收 OS 子程序退出；supervisor 決定重啟／失敗升級；帳本確保任務死了用量不失蹤。子程序被 Linux init 收養，不代表工作已移交給另一個 agent。現行 kill 範圍是第 6 節 spec 的有限保證，不在這裡改成「必須啟用 subreaper」。

kthread／workqueue 值得借的是維護工作與業務工作分開、有界 worker 池、可延後工作清單；不要借 thread 實作來改掉 S-04。kernel 可以讀 `<node>/jobs/*.json`，寫 `.aos/spawn/*.json` 讓 tick 起處理器：

```json
{
  "name": "cache-maintenance",
  "mode": "each",
  "max_live": 1,
  "inst": "maintenance.inst.json"
}
```

這是現有 spawn 格式；kernel 要確認同一 job 沒有在途實例，維護內容與允許路徑由 inst／job 檔指定。大量細工作可交給固定數量的長駐 worker，各自領 job，不必一件起一個 agent。**daemon／tick：初版無新增需求；強保證需要**跨工作池槽位准入、可回收身分與 request 去重。

## 10. 回合當時間：計時、跨 node 公平與 tickless

### 10.1 jiffies、ns、timer／hrtimer〔要改〕

Linux 同時有粗粒度 tick／jiffies、以 ns 計的時鐘與高解析計時；hrtimer 不只是把傳統 timer wheel 刻度縮小。現代公平排程的記帳也不能簡化成「數了幾次 scheduler tick」。[time 手冊](https://man7.org/linux/man-pages/man7/time.7.html)、[hrtimer 文件](https://docs.kernel.org/timers/hrtimers.html)

aos 的回合是 S-08 定義的事件邊界。tick 寫出的 round 標籤不表示任務已做了一步；tock 完成關閉回合，不要求所有跨回合任務停下。三種時鐘應明列：

| 時鐘 | 用途 | pause 時是否前進 |
|---|---|---|
| 任務所在 node 的邏輯回合 | 自己的狀態轉移、壽命、局部定時 | 不前進 |
| kernel／父調度域的控制回合 | 額度窗口、冷卻、跨 node 排隊與 lease | 只要控制線運行就前進 |
| monotonic 經過時間 | OS／API 逾時、daemon watchdog、供應商每秒速率 | 一般繼續前進；屬運行層時間 |

任務順序與邏輯 deadline 不依賴可跳動的日期時間 `at`；新增加的 ms 指標只量 duration。現有 daemon 已用 monotonic 等待與 action_timeout_s，見 `infra-needs.md` N-07、N-54；不必為了保持回合抽象移除這些運行保底。

kernel 讀 `round.json`／status，寫 `timers.json`〔提案〕：

```json
{
  "schema": "aos.kernel-timers.v1",
  "timers": [{
    "id": "amy-cooldown",
    "clock": {"node": "control", "timeline_epoch": "control-v1"},
    "due_round": 128,
    "action": {"op": "resume", "node": "team/agents/amy", "rounds": 1},
    "why": "冷卻以持續運行的控制線計算"
  }]
}
```

`timeline_epoch` 是提案，用於刪掉再建立／回合重置時分辨不同邏輯歷史；現有 daemon gen 只處理 daemon 世代，不等於時間線身分。到期只下有限操作，帳本與其他 pause 原因仍須重新核對。

**daemon／tick：一般 kernel 回合 timer 現在就可做；必要補強**是可辨識的 epoch／回合來源。外部事件 timer 可以是任務或 daemon 的運行層服務，不能讓被 pause 的成員靠自己的 due_round 自我恢復。

### 10.2 各條回合長度不同，怎麼公平

兩條 node 分別每 100 ms 與 1000 ms 一回合，各給十回合，只能稱相同的邏輯回合機會，不能稱相同秒數、token 或模型服務。`interval_ms` 也不是回合工作量的嚴格上界：tick／tock 成本、提早 tock、跨回合任務與主機壓力都會影響。

建議公平域選定明確的「給什麼」：同模型池按 token／服務量，同價值預算按金額，多池按各池容量；等待多久則以控制回合表達，另記牆鐘等待供人看。**公平比較的是資源帳，回合決定何時作決策。**

同一 kernel 可以管理不同回合速度的成員，但每個 decision 保存來源：

```json
{
  "decision_clock": {"node": "control", "round": 200},
  "observations": [
    {"node": "fast", "round": 980, "account_seq": 410},
    {"node": "slow", "round": 97, "account_seq": 209}
  ],
  "fairness_domain": "shared-model-pool",
  "service_unit": "billed_tokens",
  "why": "不直接比較 fast 與 slow 的 round 數字"
}
```

跨 daemon 則指定上層調度域的時鐘與帳，或由上層分配互不重疊的子額度。不同 node 的 round 是局部順序，不是全域先後；跨 node 事件因果以 request_id／parent_event 關聯，不靠 `r100 > r90`。

卡住判斷要明選一種語意：若依任務自報的 `last_progress_round`，可計「經過多少本地回合」，但可信度屬自報；若只有抽樣的 progress，只能計「觀察到多少次未變」，不能假裝知道兩次觀察中間完全沒進展。現有 `rule_stuck()` 屬後者，不應單純改成加 round 差值就宣稱修好語意。

**daemon／tick：必要**提供一致、附來源的時鐘與帳務序號；跨域公平策略仍由 kernel 決定，不要求 daemon 維護全域同步回合。

### 10.3 NO_HZ：idle 不空轉〔要改〕

Linux NO_HZ_IDLE 可在 CPU idle 時停止不必要的排程 tick，NO_HZ_FULL 在特定條件下進一步減少 tick；計時與事件仍會運作，不是把實際時間停掉。[NO_HZ 文件](https://docs.kernel.org/timers/no_hz.html)

aos 的差異在於回合本身就是時間。因此不能「睡十秒後補 100 個回合」，也不能一看到 agent idle 就停止回合：它可能設定 `agent.json` 的 `wake.rounds`，或有其他任務等 tock。停回合會改變這些任務的可見時間。

建議分兩級：

- **現況可做：** 已知沒有任何按回合等待者時，由 kernel pause 該 node；外部收信處理器經授權寫 resume，再視需要 wake。不依賴該 node 裡自己也等 tock 的 agent 發出喚醒。現有 wake 單獨對 paused node 無效。
- **未來事件模式：** 任務明確登記 wake source 與下一個需要的回合；daemon 依宣告睡眠到外部事件或計時點，醒來仍執行正常 tick／tock。只有所有相關任務都允許跳過空回合，才能設計跳號／合併回合；這會改契約，不能預設。

`<node>/.aos/idle-policy.json`〔提案〕：

```json
{
  "schema": "aos.idle-policy.v1",
  "mode": "event_driven",
  "clock_behavior": "advance_only_on_actual_tick_tock",
  "require_all_tasks_idle_safe": true,
  "wake_sources": [{"kind": "directory_change", "path": "inbox"}],
  "safety_poll_ms": 5000,
  "why": "只在有工作時開回合；保留低頻補查以免漏事件"
}
```

注意「註冊 watch → 重查佇列 → 確認可睡」的順序，避免訊息剛到而通知遺失；事件只是提示，醒來仍重讀真實檔案。不要每次檔案變更都開一回合，先合併重複事件。若 worker 還在等遠端請求，可能只需等完成事件，不必產生數百個空 tock。

**daemon／tick：有更好**提供可靠的事件等待、wake reason 與 idle-safe 宣告；現有 `wake`／`resume rounds` 已是很好的基礎。純回合定時的 wake 任務仍保持原有週期，不能被自動優化掉。

### 10.4 控制回合與多個 pause 原因〔提案〕

預算 kernel、人、另一個管理 kernel 都可能 pause 同一條線。現有 daemon 是單一 paused 狀態，某個 kernel 到期 resume 可能解除別人的意圖。與其讓多個控制器盲寫相反 ctl，建議由單一管理者整理帶 owner 的 holds；有效限制取交集，只有自己建立的 hold 可以由自己解除。

```json
{
  "schema": "aos.timeline-holds.v1",
  "node": "team/agents/amy",
  "holds": [
    {"id": "budget-81", "owner": "budget-policy", "kind": "no_new_paid_work"},
    {"id": "human-7", "owner": "operator", "kind": "pause_timeline"}
  ]
}
```

這可以先在 kernel 合成為現有 pause／resume；要讓多個管理者獨立可靠操作，就需 daemon 的 owner／hold 協議。

若 paused node 上有待 kill ctl，建議新增**維護回合模式**：由外部 kernel 請求正常 tick／tock 邊界，tick 只處理控制與收尾，不消費 spawn、不補 keep，且新付費呼叫閘門關閉；完成後仍保留原 pause holds。此模式會有一個實際回合，不能假裝沒發生，也不能只靠現在 `resume rounds: 1` 就說安全：現在會起 spawn／keep，tock 還可能觸發 agent 新動作。

**daemon／tick：若要在 pause 下可靠收尾，此能力必要；一般排程有更好。** 這是維持 S-17「在 tick-tock 時控制」的擴充方向；另一個選擇是接受目前 ctl 要等正常 resume 的限制，不能直接改成任意時刻 kill 而不說語意改變。

## 11. 安全與隔離：掛載是可見範圍，權限要有執行者

### 11.1 namespace〔要改〕

Linux namespace 隔離資源的視圖，例如 mount、PID、network；它不是通用的資源額度限制。[namespaces 手冊](https://man7.org/linux/man-pages/man7/namespaces.7.html)

aos 的對應是 S-10／S-23：任務只看自己的 node 與獲准掛載。現有 `mnt/` 是 symlink，任務仍可能直接開其他可存取的路徑；`mount_allow` 只管執行中加掛請求，沒寫預設全給，而且不審 tasks.json 的靜態 mounts。這些都在 `proto7-1/spec.md` 第 4、5 節，不應描述成現有沙箱。

**草圖〔提案〕。** kernel 在可見的政策檔宣告需求，tick 驗證靜態與動態掛載；runner 決定是否使用 OS mount namespace、唯讀 bind mount、user identity 等技術強制落實：

```json
{
  "schema": "aos.visibility-policy.v1",
  "task_key": "project-x/scheduler-agent",
  "views": [
    {"name": "snapshot", "path": "control/.aos/scheduler/input.json", "access": "read"},
    {"name": "proposal", "path": "control/.aos/scheduler/proposals", "access": "write"}
  ],
  "dynamic_mounts": {"default": "deny", "allow": []},
  "enforcement": "runner_sandbox"
}
```

這不是現有 mounts 格式；不能把其中 `access: read` 放進現有檔就以為已唯讀。若 OS 隔離尚未做，寫 `enforcement: cooperative`，LLM 工具包限制路徑只能提供合作式防誤操作。

**daemon／tick：需要強隔離時必要**統一掛載驗證、唯讀／可寫模式與 runner 執行。權限是否強制是核心 spec 留待後續的範圍，本報告提出選項，不把它當作必須全面容器化。

### 11.2 capabilities 與 LSM〔要改〕

Linux capabilities 把傳統 root 權力分成不同權能；LSM 提供安全檢查掛點，讓安全模組在操作位置實施政策。兩者都不是「給一份 JSON 自稱有權就可以」。[capabilities 手冊](https://man7.org/linux/man-pages/man7/capabilities.7.html)、[LSM 文件](https://docs.kernel.org/security/lsm.html)

aos 借細分控制權與在副作用點驗證：能讀 status 不代表能寫 ctl；能 pause amy 不代表能 stop daemon；能管理 tasks 不代表能改父預算。掛 `.aosd` 整棵給 LLM 排程器過於寬，最好提供只讀摘要與受限提案目錄。

`<trusted-policy-root>/grants/scheduler-policy.json`〔權限授權提案，與資源 grant 不同 schema〕：

```json
{
  "schema": "aos.authority.v1",
  "principal": "control:kernel",
  "permissions": [
    {"operation": "timeline.resume", "nodes": ["team/agents/amy", "team/agents/bob"], "max_rounds": 2},
    {"operation": "task.restart", "groups": ["project-x/team-a"]}
  ],
  "policy_revision": 4,
  "why": "只委派此團隊的有界調度權"
}
```

kernel 讀政策、寫普通 ctl；daemon／tick 根據受保護的來源身分與 policy 檢查。`by` 只供人讀，不能作身分驗證；權限檔若任務自己可改，也不構成授權。可用不同 UID、受控請求入口或受保護的 runner 對應表實作，不必一開始設計憑證系統。

權限上限取父政策交集；expired authority 不等於已開始副作用能撤回。若權限有效期以回合計，要指定時鐘並定義控制線停住時怎麼處理，否則「兩回合過期」可能永遠不過期。

**daemon／tick：若要受限委派，必要**在 ctl、spawn、初始 mounts、動態 mounts 與 grant claim 的執行點驗權。kernel 可以決定政策，可信執行端負責不能繞過的檢查；不讓 LLM 自己裁判自己有沒有越權。

### 11.3 seccomp〔不要借來當 aos 語意權限〕

seccomp 過濾 syscall 與可檢查參數，文件也明說它本身不是完整沙箱。它不理解 JSON 的 `op: resume`、node id 或一次 API 的 token 費用，不能簡單用 syscall filter 判斷路徑指向的內容。[seccomp 文件](https://docs.kernel.org/userspace-api/seccomp_filter.html)

**判斷：不要借作 kernel 管理接口。** 若未來 runner 要縮小任意 inst 的 OS 攻擊面，seccomp 可作底層補強；那是 daemon／runner 的部署選項，與回合排程本身無關，不需要 kernel 每回合產生 BPF。

## 12. 其他值得對照的機制

### 12.1 BFQ／mq-deadline：LLM 佇列比 CPU 佇列更像 I/O〔要改〕

BFQ 以預算與權重分配 I/O 服務；mq-deadline 使用排序／FIFO 到期等機制降低飢餓，deadline 主要限制請求在排程佇列的等待，不保證磁碟何時完成。這些並非 CPU 的 SCHED_DEADLINE。[BFQ 文件](https://docs.kernel.org/block/bfq-iosched.html)、[deadline tunables](https://docs.kernel.org/block/deadline-iosched.html)、[mq-deadline 原始碼](https://raw.githubusercontent.com/torvalds/linux/master/block/mq-deadline.c)

aos 的 LLM 常是提交後等外部服務，排程重點是送出前的順序、批量與在途數量。可借 BFQ 的群組服務預算，借 deadline 的最久等待保護；不用借磁碟 seek 排序。批次可提高吞吐，但大量整理工作不能一直擋著一封短回覆。

kernel 讀 `<pool>/queue/*.json`、容量與帳，寫 grant／dispatch manifest〔提案〕：

```json
{
  "schema": "aos.dispatch-policy.v1",
  "pool": "internal-text",
  "group_policy": "weighted_budget",
  "max_inflight": 4,
  "max_batch_items": 3,
  "max_wait": {"clock_node": "control", "rounds": 5},
  "deadline_means": "dispatch_opportunity",
  "oversized_request": "reserve_then_dispatch"
}
```

等待上限是到期提高優先權或報 miss，不允許突破硬額度。正在跑的請求通常讓它跑完；取消是否划算要看供應商行為與重做成本，不能拿 kill 當零成本切片。

**daemon／tick：不必知道模型佇列細節；必要執行者**是 LLM／工具入口。若工作單位是一個短 inst，則 tick 按 dispatch manifest 起任務即可。

### 12.2 Borg／Kubernetes QoS〔要改〕

Borg 以准入、資源分配與工作放置等機制管理大規模工作；Kubernetes 用資源宣告形成 Guaranteed／Burstable／BestEffort 等 QoS 類別，參與資源壓力下的管理。這些類別不是應用內容品質或成功完成的保證。[Borg 論文入口](https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/)、[Kubernetes QoS 文件](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)

aos 借「要求多少、上限多少、何時可降級」三件事。不要把自己的 `quality: 5` 映射成 Kubernetes Guaranteed。建議叫 `reserved／elastic／opportunistic`，讓名稱指資源承諾：

```json
{
  "schema": "aos.service-class.v1",
  "class": "elastic",
  "request": {"tokens_per_control_window": 4000, "call_slots": 1},
  "limit": {"tokens_per_control_window": 10000, "call_slots": 2},
  "may_borrow_idle_capacity": true,
  "on_pressure": "reduce_to_request",
  "result_quality_guaranteed": false
}
```

kernel 讀工作類別與各 pool 可用容量，將最小需求放得下的工作准入，再借空閒容量；寫 grants／tasks 啟動許可。借出的已消耗 token 收不回，只能收回未開始授權及未來額度，所以 opportunistic 使用必須限片段大小。跨 pool 放置還要看模型能力／資料可見範圍，不能只比較剩餘 token。

**daemon／tick：必要**執行第 3 節的宣告與啟動准入；容量估計、類別和放置算法在 kernel。不需要引入完整 Kubernetes 控制平面。

### 12.3 Erlang supervisor〔值得借〕

Erlang supervisor 提供 one_for_one、one_for_all、rest_for_one 等重啟範圍，以及一定時間內最大重啟次數；反覆失敗會往上升級，而不是無限重起。子工作也可區分不同重啟條件。[Erlang supervisor 官方文件](https://www.erlang.org/doc/system/sup_princ.html)

aos 最直接可借：同一 task_key 的 restart budget、因果明確的 exit、退避與升級。現有 `keep` 只是「沒活實例就起」，不是 on_failure；stuck 的 restart 也可能重送 LLM 或重做工具步驟，見 `proto7-1/spec.md` 第 10 節恢復語意。

kernel 讀 exit、birth、restart_of、語意進度與控制回條，寫 `$AOS7_TASK/supervisor-state.json`，必要時改 tasks.json、spawn 或 task ctl。設定〔提案〕：

```json
{
  "schema": "aos.supervisor-policy.v1",
  "group": "project-x/review-pipeline",
  "strategy": "one_for_one",
  "restart_when": "failure",
  "max_restarts": 3,
  "window": {"clock_node": "control", "rounds": 20},
  "backoff_rounds": [1, 2, 4],
  "on_exhausted": "disable_and_report",
  "requires_idempotency_keys": true
}
```

退避的回合數是 aos 提案，不是說 Erlang 原生使用回合。rest_for_one 只在有明確啟動／依賴順序時才合適，例如某個前置 context 版本失效導致下游必須重建；互寄信的團隊不是一個天然線性依賴鏈，不能照順序把全部 agent 重啟。

**現況可做：** kernel 持有 task 定義，在有鎖的讀改寫中暫時移除／延後 keep 項目，確認後再 kill，退避到期透過 spawn 或恢復 tasks.json；保留原定義供復原。此作法與 tick 間仍有競爭，且若 kernel 和目標同 node，不能 pause 整條線做退避。

**daemon／tick 必要補強（若要可靠契約）：** 每個邏輯工作的 `enabled／not_before／restart_policy` 啟動狀態、套用版號、退出原因及重啟序號；讓 keep 與 supervisor 只由同一個啟動准入狀態決定，避免一邊禁止、一邊補起。Erlang 的整棵樹終止不必照搬；aos 可先把工作標 failed、停新 grant、留下人可讀報告。

## 13. 一輪 kernel 應該怎麼做

這是以上機制共用的流程，避免各政策自己讀一遍歷史、自己猜一次程序狀態、互相覆蓋 ctl。

1. 讀版本化的 kernel 設定與權限範圍，確認掛載已就緒；未掛載保留 unknown，不當成沒有任務。
2. 讀權威 status、帳摘要、未完成請求與回條，先把上輪 `pending` 對帳為 applied／failed。
3. 對所有資源硬限額與必要保留做可行性檢查，建立 ready 候選清單。
4. 呼叫規則策略，或讀一份仍有效的 LLM 提案；缺失便使用保底。
5. 驗證整份提案，序列化預留額度；對每個工作只產生一份有效授權。
6. 寫 grants／現有 ctl／task 定義變更，記錄 request id 與 desired state；這時只叫 pending，不叫已完成。
7. 等下一輪核對執行，或事件喚醒後核對；記錄成本、等待、決策原因與錯誤，不重複消費同一事件。

kernel 自己的可恢復狀態〔提案〕：

```json
{
  "schema": "aos.kernel-state.v2",
  "clock": {"node": "control", "round": 123},
  "config_revision": 9,
  "account_cursor": 938,
  "pending": [{
    "request_id": "k3-r123-005",
    "target": "team/agents/amy",
    "desired": "timeline_paused",
    "status": "accepted",
    "receipt_path": "mnt/aosd/ctl-done/k3-r123-005.json"
  }],
  "holds_owned": ["budget-81"],
  "fallback_count": 2
}
```

控制器重啟時先讀真實狀態與 pending，再決定重送或結案。原子寫檔不等於一輪全部成功；需要讓中途失敗可以重做，而不是把所有 issued 永久記住。單一 task `ctl.json` 目前只能放一個命令，沒有 CAS 式多寫入者保證；第一階段可指定唯一控制寫入者，較大的系統再加有序 request queue。

這個分工保持 daemon 簡單：daemon／tick 做身分、邊界、原子准入和回報；kernel 做政策；agent 做業務與品質判斷。資源可新增，只要提供計量器、限制的執行點與人可讀 schema，不需要把每種資源都寫死在 daemon。

## 14. 對 daemon／tick 的需求清單

「必要」指對報告建議的**可靠記帳、有界准入與可替換策略**必要；不是說先把表全部實作才可以玩排程。表內會分清其他層的責任，避免把所有新需求推給 daemon。

| 編號 | 等級 | 需求、已有部分與缺口 | 由誰提供／不必由誰提供 |
|---|---|---|---|
| D-01 | 必要 | 統一任務狀態：born／live／ended／lost／unknown；附 snapshot_seq、觀察範圍與 daemon gen。目前 kernel 與 task.py 判活不同 | runner／tick 是來源，daemon 可彙整；kernel 不再掃 PID 自判 |
| D-02 | 必要 | ctl／spawn／mount 的 request id、accepted／applied／failed、重送去重；現有 ctl-done、birth.spawn 可沿用但不完整 | daemon／tick；payload 外部副作用仍需自己的 idempotency key |
| D-03 | 必要 | 可持續的帳務身分、退出事件與累計游標；歸檔／restart 不抹帳 | runner／tick 提供生命週期；獨立帳本服務做累加與結算 |
| D-04 | 必要 | 起任務前的 group／limits／grant 檢查，原子占槽；包含 spawn、keep、restart 各路徑 | tick＋共享准入服務；不能只檢查 tasks.json 的普通啟動 |
| D-05 | 必要 | 每次付費呼叫與重試事前預留、事後結算、未知在途保留；**這不是 tick 單獨能提供** | LLM／工具入口或 agent SDK；daemon 僅提供可信身分與接入方式 |
| D-06 | 必要 | 宣告與執行分開：核准的 group、權重、上限、inst 版號寫進 birth，無效欄位有回條 | tick 驗證、runner 執行；權重由 kernel 轉成 grant，daemon 不必自己排公平次序 |
| D-07 | 必要 | 控制面有保留容量：控制操作與工作啟動有界，不讓大量 node／inst 阻擋 stop、帳務和 recovery | daemon／tick；已有每圈新建 node 上限與 action timeout，仍需可觀測的過載狀態 |
| D-08 | 必要（強保底） | 控制 kernel lease、generation fencing、固定 recovery inst；錯誤或卡住時仍能停止新授權 | daemon 只執行預先配置復原流程，recovery 仍由 tick 啟動；不是 daemon 調用 LLM |
| D-09 | 必要（受限策略） | 經驗證的來源、policy scope、受保護帳／grant；提案者只能寫提案 | runner／檔案權限／請求入口；若只合作式隔離，報告就只能稱軟保底 |
| D-10 | 必要 | 時鐘欄位附 node、round，回合重建有 epoch；未知／舊世代提案拒絕 | tick／daemon；現有 AOS7_GEN 已解決部分舊動作倒寫問題 |
| D-11 | 必要（硬上限） | reservation／grant 跨 node 原子領取，崩潰後重播與去重；未確定遠端停止前不能釋放其預留 | 帳本／准入服務；可為普通任務，tick／入口共同使用 |
| D-12 | 必要（多控制者） | pause／budget／人為禁用各有 owner；自己的 resume 不解除別人的限制 | 初版 kernel 單一仲裁；多寫入者時由 daemon／tick 驗證 holds |
| D-13 | 必要（pause 下收尾） | 維護回合：只執行管理控制與收尾，不起 spawn／keep、不開新付費動作 | daemon／tick＋入口；不新增時就明說 ctl 等正常 resume |
| D-14 | 有更好 | freeze／thaw 與 frozen 完成狀態，和 pause 分開 | runner／tick；完整程序子樹歸屬需另立契約，遠端取消不由 freezer 保證 |
| D-15 | 有更好 | 等待原因、heartbeat、語意 progress 分開，佇列壓力與歷史峰值 | agent／入口回報，kernel 彙整；daemon 不讀懂業務進度 |
| D-16 | 有更好 | 事件式 wake、idle-safe、watch 後重查、低頻補查與 wake reason | daemon／tick；不能自動跳過仍有人依賴的邏輯回合 |
| D-17 | 有更好 | 日誌輪替、帳務 checkpoint、摘要索引、磁碟低水位 | 記帳服務與維護任務；daemon 暴露儲存失敗與過載，不能靜默漏帳 |
| D-18 | 有更好 | 任務 restart_policy、not_before、enabled 與版號套用回條 | tick 的啟動機制；退避／升級策略由 kernel 決定 |
| D-19 | 有更好 | OS rlimit／quota／sandbox 適配、初始及動態掛載同一套授權 | runner／tick 的 Linux 適配層；保留上層 JSON 協議 |
| D-20 | 有更好 | 不含業務機密的大綱快照、按需事件查詢，欄位有單位、理由與範圍 | 狀態輸出／查詢工具；評分器與易用性量測不必進 daemon |

這份清單可直接對照 `proto7-1/notes/infra-needs.md`：N-08／09 是接受與生效，N-12 是快照來源與 unknown，N-17 是控制面可用性，N-19 是請求生命週期，N-31 是重啟定義，N-32 是 pause 不搶佔，N-33 是 tasks.json 多寫入者。已做的 `resume rounds`、`pause_pending`、generation、原子 JSON 與檔案鎖應保留，不重造另一套。

## 15. 如果只做三件事

### 第一件：做一份可信的資源帳與控制結果

先統一 status 與 task identity，記錄單調帳務事件，kernel 用 pending／applied 而不是「寫完就算成功」。把 token／calls 的累計彙總移出每回合掃完整 `tasks-old/` 的路徑。這直接處理現有 K-3、K-8、K-10，也讓後續任何算法能用同一份證據。

**完成標準：** 任務或 kernel restart、任務歸檔、控制回條延遲、重送結算後，總帳不重複不倒退；讀不到要顯示 unknown。人只讀一份摘要就能知道「誰花了多少、哪個操作還在等」。

### 第二件：做有界准入，讓預算真的能執行

先有階層預算、預留／結算、每群組並行上限與起任務／呼叫前檢查；保留一塊不用 LLM 的控制容量。這比先寫很精緻的公平算法重要：沒有執行前閘門，任何算法都只能在超支之後 pause。freeze 可晚做，先把「下一筆不能花」管住。

**完成標準：** 兩個 agent 同時申請最後一份額度，最多一個成功；provider 逾時留下 unknown 預留；pause 不被當成停止計費；控制面在工作滿載時仍可結算、拒絕新工作與回報。

### 第三件：做可抽換排程策略，先有便宜保底再接 LLM

沿用現有純函式規則，定義 snapshot／proposal／grant JSON；預設群組加權輪替，增加版本、期限、飢餓防護和回條核對。LLM 先 shadow，再接管有限群組；慢、錯、超額就回到保底。如此可以公平比較 CFS 啟發、EEVDF 啟發、DRF 或 LLM 策略，無須每換策略就改 daemon。

**完成標準：** LLM 輸出壞 JSON、永遠不回、想 pause 自己或提出超額 grant，都不能讓合法工作與控制面永久失去服務；若管理 kernel 也故障，要明確區分已有的 keep 恢復與尚待實作的 daemon lease 強保底。

## 16. 用哪些情境驗證建議

這是後續實作時的驗收情境，本次只寫報告，未執行或新增測試。

| 情境 | 應看到的結果 |
|---|---|
| 快 node 和慢 node 各有持續工作、權重 1:2 | 對同一資源池的長期服務量趨近 1:2；回合數可以不同 |
| agent 開十個子 agent，或改名重啟 | 頂層專案份額與終身帳不變，群組活任務 cap 仍有效 |
| 長 LLM 呼叫中 pause | 時間線停，新呼叫被閘門擋住；既有 request 仍標在途，不假裝零成本 |
| ctl 寫出後掛載斷掉／daemon 重開 | pending 不誤記 applied；舊世代授權不能執行；恢復後可核對 |
| 帳務事件重送、任務進 tasks-old、kernel restart | 相同 event_id 不重算，總帳不因目錄移動變小 |
| 同時領最後 1500 token | 原子預留只放行容量內的請求，其他有可讀拒絕原因 |
| LLM policy 輸出延遲三回合或要求控制自己 | 提案過期／越權被拒，保底照常供應有界服務 |
| agent 每回合更新 heartbeat 卻一直沒有成果 | 不判程序卡死；另列業務無進展供評估／人檢查 |
| 一個 background 工作持續重啟 | 達 supervisor restart budget 後停止補起，保留診斷與帳 |
| idle node 設有 wake.rounds，另一 node 純事件驅動 | 前者維持回合語意；後者可休眠，被事件可靠喚醒且不補假回合 |
| 兩個 kernel／人分別持有 pause 原因 | 解除自己的 hold 後，其他 hold 仍生效 |
| 可讀性評分高但操作測試答錯 | 不以高分換額度；記錄具體誤解並修訂 rubric／介面 |

## 17. 不確定與應保留的設計選擇

- **外部 LLM 的取消、計費與用量完整性：不確定。** 取決於 provider 契約；本次未指定 provider，不能保證 kill／HTTP timeout 會停止計費，也不能假設每次失敗都有完整 usage。報告以保守預留與 unknown 處理。
- **Linux 特定功能是否可用：不確定。** 本次未調查運行主機的 kernel config、cgroup controller 或 sandbox 權限。借設計不要求立即啟用 sched_ext、cgroup freezer 或 seccomp。
- **品質與 token 的最佳交換比例：不確定。** 要用 aos 實際任務與人工驗收量測，不能由 Linux 文件推導。
- **哪些時間線可跳過空回合：尚未定義。** S-08、S-19 與現有 wake.rounds 都有可觀察行為，需由工作宣告 idle-safe，不能默認所有 agent 都能跳。
- **restart 應採新定義還是舊快照、權限要多強：仍是設計選擇。** 報告給明確格式與代價，不覆蓋 `infra-needs.md` Q6 或核心 spec 保留到後續的權限議題。

以上未定項不妨礙前三件事先從合作式原型開始；但每項保證都要寫清楚是「政策希望如此」還是「執行端確實會擋」。這個區分本身，就是最值得從 Linux 資源管理借來的部分。
