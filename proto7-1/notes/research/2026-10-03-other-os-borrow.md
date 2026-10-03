# aos 能向 Linux 以外的作業系統與研究借什麼

（astra 2026-10-03 寫，題目見同名 `.task.md`；頂層只搬進 repo，未改內容。報告中的連結是相對 repo 根寫的。）

調查日期：2026-10-03。最值得借的是 **Plan 9 的任務命名空間、resource containers 的工作歸帳、seL4 MCS 的代辦預算，以及階層排程器**。
token 不等於 WCET，lottery ticket 不等於存款；應用「工作帳戶＋可縮限的支用權」處理子任務花父任務的錢。
回合可用來安排發放時機與工作階段，不能靠 pause 做 CPU／遠端 LLM 的硬時間分區。LLM 適合選政策，確定性程式負責准入、記帳與每回合執行。
本次強化上一份報告的機制／政策分工，補上請求穿越服務時的付費與依賴關係；並更正舊報告漏掉現有 `restart reload:true` 的說法。以下「新／同／推翻」都相對上一份報告。

| 對象 | aos 對應 | 借／改／不借 | 跟 Linux 報告比 | 一句理由 |
|---|---|---|---|---|
| Plan 9／Inferno | 每任務可組合的服務目錄 | 借 | 新 | 掛載不只隔離，也是 inst 的依賴注入與可讀介面 |
| FreeRTOS／Zephyr／VxWorks | 優先序與有界工作准入 | 改 | 同＋新 | 排序相同；依賴造成的優先序反轉值得補 |
| QNX Neutrino | 代辦請求繼承急迫性 | 改 | 新 | 應提升真正阻擋急件的服務，不只提升等待者 |
| RM／EDF／WCET | 週期、期限、成本上界 | 改 | 同 | token 上界不提供完成時間上界 |
| TTA／ARINC 653 | 固定回合窗口、群組階段 | 改 | 新 | 借可預測的發放表，不宣稱硬即時隔離 |
| tickless／watchdog | 空轉控制、故障保底 | 改 | 同 | D-08／D-16 已涵蓋；不能補造回合 |
| Mach／L4 | 管理服務拆分、窄 IPC | 借 | 同 | daemon 小、政策在任務，已有此方向 |
| seL4 capability／形式驗證 | 可縮限權力、可驗不變量 | 改 | 新＋同 | 驗少數執行規則，比證明 LLM 好用實際 |
| seL4 MCS | 服務帶著呼叫者的預算工作 | 改 | 新 | 排程份額與工作付費身分可以跨服務傳遞 |
| MINIX 3 | 可替換工具服務、監督重起 | 借 | 同＋新 | 重起已有；穩定服務介面與重接仍待設計 |
| Zircon handles／jobs | 權利縮限、任務管理樹 | 改 | 同＋新 | 管理樹不必等於付費樹或路徑樹 |
| Aegis／ExOS | 保護與資源政策分離 | 借 | 同 | 強化 daemon／kernel 邊界，不照搬裸硬體抽象 |
| Nemesis | 摘要、檢索等間接成本歸帳 | 借 | 新 | 別讓共享服務的工作偷吃別人的額度 |
| MirageOS | 專用、固定依賴的 inst | 改 | 同 | 借最小依賴；不必把 Python 任務改成 VM 映像 |
| KeyKOS／EROS／CapROS | 邏輯狀態持久化與復原邊界 | 改 | 新 | 檔案都在，不代表多檔與外部副作用一致 |
| Capsicum／CHERI | 掛載權利縮限的參考 | 改／不借硬體 | 同＋新 | 權力須不可偽造；JSON 名字不是 capability |
| Lottery／stride／currency | 分群份額、可傳遞服務權 | 改 | 新＋同 | currency 能隔離內部分票；stride 便於重播 |
| Resource containers | 每項工作跨任務歸帳 | 借 | 新 | 執行在哪個程序，不決定該算誰的錢 |
| Scheduler activations | 有原因的事件送給使用者層排程器 | 改 | 新＋同 | 補通知語意，不把 upcall 改成 daemon 問 LLM |
| CPU inheritance／HLS | 排程器本身受上層配額管理 | 借 | 新 | 最貼近 S-16／S-20 的排程器組合 |
| Eclipse／Scout | 資源保留域／端到端工作路徑 | 改 | 新 | 分別處理資源域與跨階段服務，兩者不同 |
| BVT | 有上限的互動優先權借用 | 改 | 同 | 長期公平仍要還帳，與 EEVDF 啟發重疊 |
| Coscheduling／gang | 合作任務成組准入 | 改 | 新 | 借避免夥伴互等，不追求同秒運行 |
| Feedback control | 依延遲與壓力調整並行度 | 改 | 新 | 有模型、有延遲的回授，比每輪憑感覺調參可查 |
| Spawn／Tycoon | 有限信用內的價值投標 | 改 | 新 | 適合效用提案，不保證誠實或最優 |
| Barrelfish | 多 kernel 訊息協作、版本化副本 | 改 | 新 | 副本可用於讀，消耗額度仍須唯一權威 |
| Singularity／Spring | 有版本的服務契約、狀態通道 | 借 | 新 | JSON 格式正確之外，還要檢查操作順序 |
| Amoeba／Sprite | 遠端放置／checkpoint 後重派 | 改 | 新 | 不把搬資料夾誤認成透明程序遷移 |
| Actor 模型 | mailbox、狀態機與背壓 | 改 | 同＋新 | 符合 agent，但沒有自動恰好一次保證 |
| AIOS／MemGPT | 請求服務層／context 分層 | 改 | 新＋同 | 研究確實存在；不是外部 API 可搶佔的證明 |

## 0. 範圍、現況與草圖讀法

已讀 [核心 S-01～S-23](proto7/spec/core.md)、[proto7-1 細部規格](proto7-1/spec.md)、[上一份 Linux 報告](proto7-1/notes/research/2026-10-03-linux-kernel-borrow.md)，並對照 `proto7-1/lib/aos7_kernel.py`、`aos7_kernel_rules.py`、`notes/infra-needs.md` 與 sched／llmkernel 探針。沒有執行探針、daemon 或付費模型；本次只寫此報告。

以下歷史事實依原論文、作者／研究機構或官方文件；**aos 對應、JSON、實驗與推薦是本報告的設計推論**，不是原系統已提供的功能。論文年份指發表／初稿年份，不採搜尋引擎的「幾個月前」日期。

不重寫 D-01～D-20。本文的「必要」是對某項新增保證必要，不是要求先做完才可試 kernel。最簡原型仍可合作式讀寫檔案；硬限制另需可信執行入口。

**草圖約定：** 除標「現有格式」外，新增的檔名與欄位都尚未實作。`<C>` 是控制 node，`<B>` 是帳本服務 node，`<S>` 是共享服務 node；`$AOS7_TASK` 是本次 kernel 的任務資料夾。跨 node 的讀寫描述的是目標位置，實際一律經已核准的 `$AOS7_TASK/mnt/<別名>/...`（S-10、S-23）；不能因知道根目錄就直接越界。各節的檔案操作沿用原子 rename；共享讀改寫加鎖或交給唯一寫入者。**寫了一份新 JSON 不代表現有 tick 會執行它。**

三個既有邊界會反覆影響借法：

- `resume rounds:N` 限制開幾個回合，不是做幾次 LLM 動作；慢 agent 會略過中間 tock。`pause` 不凍結活任務，也不取消遠端呼叫。
- kernel 收到自己的 tock 才讀快照並決策，通常影響後續邊界。它不是在 tick 內同步執行的前置鉤子；tick 不能等待 LLM。
- mounts 是符號連結；`mount_allow` 只管動態加掛，未設定時預設允許根內路徑；目前不做卸掛。這是協議，不是不可繞過的 capability 沙箱。

## 1. Plan 9／Inferno：最值得深借的是「組裝任務看到的世界」

### 1.1 每程序命名空間，而不是只有「一切皆檔案」

Plan 9 讓不同服務輸出檔案樹，每個程序再把所需服務組成自己的命名空間。同一路徑可在不同程序代表不同資源。9P 是存取這些服務的訊息協議；服務不必是磁碟上的普通檔案。這不等於 Plan 9 是微核心，也不表示所有協議內容都是文字。[Pike 等，*Plan 9 from Bell Labs*（1995）](https://9p.io/sys/doc/9.html)

**值得借；相對 Linux 報告是新增的介面組合觀點。** 舊報告第 11 節偏重可見性與隔離；aos 可再走一步：讓 inst 只認 `mnt/model`、`mnt/mail`、`mnt/context`，不必知道專案叫什麼、服務在哪個 node。kernel 的一部分工作變成替任務裝配環境。S-01 的好處是 agent 只讀一份服務卡就知道可以做什麼；S-23 正好提供接線方式。

**現有可試草圖。** kernel 讀 `<C>/bindings.json` 與各服務的 `service.json`，寫目標 node 的 `.aos/spawn/reviewer-17.json`：

```json
{
  "name": "reviewer",
  "inst": "review.inst.json",
  "mounts": {
    "mail": "project-a/inbox",
    "model": "services/model-a/clients/reviewer",
    "context": "project-a/context/rev-7"
  }
}
```

這是**現有 spawn／mounts 格式**。`review.inst.json` 及 runner 可執行內容要事先放好；上例不會自行提供新服務。`services/model-a/clients/reviewer/service.json` 是新增服務卡：

```json
{
  "schema": "aos.service-card.v1",
  "service_id": "model-a",
  "interface": "llm-submit.v1",
  "instance_epoch": "model-a-4",
  "submit": "requests/<request_id>.json",
  "receipt": "receipts/<request_id>.json",
  "operations": ["submit", "query"],
  "charging": "caller_context",
  "completion": "receipt.state == settled",
  "why": "提交後查回條；檔案寫成功不表示模型已回答"
}
```

任務先核對 `interface`，再把請求原子寫進 `mnt/model/requests/`，由 tick 啟動的服務任務處理。mock 與真模型可有相同服務樹，切換只改掛載；kernel 不必改 prompt、inst 或 agent 的業務程式。

**daemon／tick：首次裝配不需新增。** 要在活任務上用同一別名換服務，目前會碰到「名字已掛別處」而被拒。可靠熱切換需要 E-03 的版本化重綁；初版可 restart 新實例切換，並保留舊服務給舊請求收尾。

### 1.2 Union mount：借有次序的視圖，不偷做 JSON 合併

Plan 9 的 bind／mount 可以替換目錄，或把目錄接在既有內容前後，形成依序查找的 union directory；它不是把同名檔案內容合成一份。命名空間變更可限定在特定程序／共享該命名空間的程序群，不必全系統一起改。[Pike 等，*The Use of Name Spaces in Plan 9*（1993）](https://9p.io/sys/doc/names.html)

**要改；新。** aos 可把站點工具、專案工具、任務工具組成有限清單，也能提供「測試資料蓋過正式資料」的可重建視圖。但無聲遮蔽同名 `policy.json` 容易誤導 LLM。先用 manifest 明列來源與遮蔽規則，比真的做 union filesystem 更易懂。

kernel 讀 `<C>/namespace-plans/reviewer.json`、來源目錄清單，寫任務可讀的 `namespace.json` 與唯讀的解析結果目錄〔合作式原型〕：

```json
{
  "schema": "aos.namespace-plan.v1",
  "revision": 7,
  "views": [{
    "alias": "tools",
    "sources": ["project-a/tools", "shared/tools"],
    "lookup": "first_match",
    "on_name_collision": "report",
    "create_target": "project-a/tools",
    "merge_file_contents": false
  }],
  "resolved": [{"name": "lint.json", "source": "project-a/tools/lint.json"}]
}
```

上例每個來源仍須核准；`create_target` 是新服務的政策，不是現有 symlink 自動支援。穩定的解析 manifest 應與執行定義一起留存，否則「相同 inst」可能因視圖不同而做不同事情。

**daemon／tick：不必新增 union mount。** kernel 可先產生視圖，再以現有 mount 掛入。若要求執行中整組別名同時替換、不讓讀者看見半新半舊，才需要 E-03；若要求唯讀強制，沿用 D-09／D-19，不另列需求。

### 1.3 9P／Inferno：統一服務入口，不等於隱藏遠端故障

Inferno 把資源檔案化、每程序命名空間與 Styx／9P 延伸到可原生運行或寄居其他 OS 的環境；這比「aos 必須自己接管硬體」更貼近現況。[Inferno Design Principles（官方）](https://inferno-os.org/inferno/design.html)、[Inferno 概覽（官方）](https://www.vitanuova.com/inferno/)

**值得借組合方式；不要急著導入 9P、Dis VM 或 Limbo。** 9P 是二進位傳輸協議，不是 S-01 的替代。aos 可維持普通 JSON request／receipt，由橋接任務把一個遠端服務表成目錄；agent 不必學 socket，但必須能看見遠端的 `unavailable／pending／unknown`。

kernel 讀 `mnt/model/service.json` 與 `health.json`，寫自己的 `bindings.json`，必要時 spawn 新橋接器；請求沿用下列新增格式：

```json
{
  "schema": "aos.service-request.v1",
  "request_id": "review-17-call-2",
  "interface": "llm-submit.v1",
  "operation": "submit",
  "expected_service_epoch": "model-a-4",
  "charge_context": "cc-review-17",
  "input_ref": "inputs/review-17.json",
  "reply_key": "review-17-call-2"
}
```

`input_ref`、reply 位置由服務在已授權根內解析；不能接受任意路徑而替人越權讀寫。服務回條提供 transport 狀態與業務狀態兩條軸。網路斷線不能當「沒花錢」，同名替代服務也不能吃舊請求重做一次。

**daemon／tick：橋接任務可用現有機制啟動。** 遠端協議、去重與帳務在橋接器／帳本，D-02／D-05／D-11 已列；不用讓 daemon 實作 9P。

## 2. RTOS：先分清「選誰做」與「能保證何時完成」

### 2.1 FreeRTOS、Zephyr、VxWorks、QNX 實際有什麼

| 系統 | 查證到的機制 | aos 判斷與 Linux 差異 |
|---|---|---|
| FreeRTOS | 可設定搶佔／合作排程；典型配置選最高 ready 優先序，同級可時間切片；mutex 使用簡化優先序繼承 | **改／同**：優先序能排准入；**新**在依賴繼承。不能把它說成內建通用 EDF／完整天花板協定 |
| Zephyr | 區分 cooperative、preemptible 執行緒；可選 deadline 排序，但先比靜態優先序，EDF 只解同級排序 | **改／同**：適合「類別優先，再按截止回合」；不是所有工作全域 EDF |
| VxWorks | 優先序搶佔與可選 round-robin；VxWorks 653 另外提供分區平台 | **改／同＋新**：普通優先序與 653 分區不可混稱同一功能 |
| QNX Neutrino | 優先序排程，含 FIFO、round-robin、sporadic；訊息可傳遞優先序 | **改／新**：服務的優先序可反映客戶請求，詳見 §3 |

來源：[FreeRTOS 排程說明](https://www.freertos.org/Documentation/01-FreeRTOS-quick-start/01-Beginners-guide/01-RTOS-fundamentals)、[FreeRTOS mutex](https://freertos.org/Real-time-embedded-RTOS-mutexes.html)、[Zephyr Scheduling](https://docs.zephyrproject.org/latest/kernel/services/scheduling/index.html)、[VxWorks 官方資料表（2025）](https://www.windriver.com/sites/default/files/2025-07/VxWorks%20Data%20Sheet%20-%20July%202025%20_0.pdf)、[QNX 官方排程概覽（6.3.2）](https://www.qnx.com/developers/docs/6.3.2/neutrino/prog/overview.html)。此處以文件所述版本為準，不替所有商業版本背書。

**共用草圖。** kernel 讀 `<C>/ready/*.json`、群組額度與 `<C>/class-policy.json`，寫 `dispatch/*.json` 給合作式 worker；真正啟動仍寫目標 `.aos/spawn/`，不是 kernel 自己起工作程序（S-10）：

```json
{
  "schema": "aos.dispatch-rule.v1",
  "class_order": ["control", "interactive", "batch"],
  "within_class": "earliest_control_deadline",
  "selection_point": "before_next_call",
  "urgent_max_share": 0.7,
  "aging_after_control_rounds": 8,
  "running_call": "keep_reserved_until_settled"
}
```

這是請求排程，不能中途奪回已送出的 LLM 呼叫。D-04／D-05 負責准入；daemon 不需理解 RTOS priority 數值。

### 2.2 優先序繼承／天花板：追著依賴提升，不能只提升急件本人

基本 priority inheritance 讓鎖持有者暫時繼承等待者的較高優先序；priority ceiling protocols 額外用資源天花板與取得規則限制阻塞，並在論文假設下避免死鎖。單純「priority 不准超過某數」不是這套協定。[Sha、Rajkumar、Lehoczky，*Priority Inheritance Protocols: An Approach to Real-Time Synchronization*（1990）](https://experts.illinois.edu/en/publications/priority-inheritance-protocols-an-approach-to-real-time-synchroni/)

產品也要分開看：Zephyr mutex 支援 priority inheritance；其繼承上限設定不能直接等同上述完整 PCP。QNX 文件明列 `PTHREAD_PRIO_INHERIT`／`PTHREAD_PRIO_PROTECT`。VxWorks 5.4 原廠手冊的 mutex semaphore 可選 `SEM_INVERSION_SAFE` 啟用繼承；這是歷史版本證據，不據此推定每個新版 API 的全部細節。[Zephyr Mutexes](https://docs.zephyrproject.org/latest/kernel/services/synchronization/mutexes.html)、[QNX 8.0 同步物件文件](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/s/synctypecreate.html)、[VxWorks 5.4 Reference Manual（1999，原廠文件鏡像）](https://bitsavers.trailing-edge.com/pdf/windRiver/VxWorks-5.4/DOC-12910-ND-00_Reference-Manual-5.4_199905.pdf)

**要改；新。** 急件 A 等低優先的索引 B，而大量普通工作 M 把 B 擋住，aos 就有應用層優先序反轉。提高 A 的權重無用；應把 A 的急迫性沿「正在等待哪個工作」傳給 B。這不表示可以突破 B 所需的權限，也不會憑空增加金額上限。

kernel 讀 agent 的 `wait.json` 與服務回條，寫 `<C>/effective-priorities.json`，再按結果發 grant：

```json
{
  "schema": "aos.dependency-donation.v1",
  "waiter_work": "urgent-answer-8",
  "holder_work": "index-42",
  "resource": "index:project-a:rev7",
  "inherit": {"class": "interactive", "deadline_control_round": 84},
  "cost_authority": "cc-answer-8",
  "end_when": "dependency_ready_or_request_cancelled",
  "max_hops": 4,
  "why": "急件被索引阻擋；先服務索引才能縮短等待"
}
```

先核對真實依賴與帳戶授權，再傳遞。優先序 donation 與付費 donation 是兩件事；沒有 `cost_authority` 仍可改順序，但不能花等待者的錢。對會動態增加依賴的 agent，不借完整 PCP 的可排程性／無死鎖保證；鎖順序、循環偵測與傳遞深度上限可作 kernel 政策，不能變成違反 S-22 的全域強制禁環。

**daemon／tick：排序與依賴圖不用新功能。** 若要可信地把支用權交給代辦服務，需 E-01；不要讓 LLM 持著 `flock` 等模型回覆。

### 2.3 RM、EDF 與 WCET：token 只能近似「最壞消耗」，不是最壞時間

RM 以週期短者給較高固定優先序；EDF 按絕對期限選 ready 工作。Liu／Layland 的經典結果依賴單處理器、可搶佔、獨立週期工作、已知執行上界等假設。deadline 等於 period 的該模型下，RM 的 `n(2^(1/n)-1)` 是充分利用率界，EDF 可達利用率 1；不代表任意 agent 工作都套得上。[Liu、Layland，*Scheduling Algorithms for Multiprogramming in a Hard-Real-Time Environment*（1973，原論文）](https://bears.ece.ucsb.edu/class/ece253/papers/laylandliu77.pdf)

**要改；主要與舊報告 §5 相同。** aos 可按控制回合做 periodic release／EDF 准入順序，但一個 agent 不是固定 WCET 的程式段。少量 output token 也可能等很久，輸入長度、重試與工具回覆會改變成本。`max_tokens` 更不保證答案正確或工作完成。

kernel 讀 `<C>/work-contracts/*.json`，寫准入結果與 grant。新的契約可以明說：

```json
{
  "schema": "aos.work-bound.v1",
  "work_id": "summary-12",
  "clock": {"node": "control", "epoch": "c-1"},
  "release_round": 80,
  "deadline_round": 86,
  "period_rounds": 10,
  "max_attempts": 2,
  "per_attempt_bound": {"input_tokens": 3000, "output_tokens": 1000},
  "reserve_tokens": 8000,
  "bound_basis": "fixed_input_and_enforced_output_limit",
  "guarantee": "admission_opportunity",
  "on_exhausted": "return_partial_with_reason"
}
```

數字是假設兩次輸入都固定 3000、輸出都可強制 ≤1000，且無其他計費類別才成立；第二次把錯誤回覆接進 prompt 時必須重算。沒有可證明上界就標 estimate，不叫 WCET。若要稱 worst-case token consumption，至少還得限制遞迴、工具扇出、重試、輸入與額外計費 token。即使全部做到，仍沒有遠端 wall-clock 完成上界。

**daemon／tick：D-04／D-10 已含啟動窗口。** 真正 token 上界由 D-05 的呼叫入口實施；不用新增「token WCET scheduler」到底層。

### 2.4 TTA／ARINC 653：可借回合表，但它們不是同一件事

TTA 以具精度界線的全域時間組織分散節點的時間觸發互動。ARINC 653 的分區排程把處理器時間切成重複 major frame 內的分區窗口，分區內可再排程；時空隔離是整套平台的責任。前者偏分散互動架構，後者是航電分區介面／執行模型，不能混成一個算法。[Kopetz、Bauer，*The Time-Triggered Architecture*（2003）](https://blough.ece.gatech.edu/6102/presentations/TTA_Paper.pdf)、[Wind River，VxWorks 653 分區說明](https://www.windriver.com/resource/safety-critical-software-development-for-integrated-modular-avionics)

**要改；新。** aos 可以規定每八個控制回合，前兩回合只發資料整理授權、接著三回合發推理授權，再兩回合發審閱授權，最後一回合結算。這是「發放窗口」；不是把 CPU 或遠端服務硬切成八片。跨 node 的 round 不能直接對齊；S-08 不要求同步全域鐘。

kernel 讀 `<C>/frame-plan.json`、控制 round 與 grant 帳，寫各服務本窗口的 dispatch；數字版草圖：

```json
{
  "schema": "aos.frame-plan.v1",
  "clock": {"node": "control", "epoch": "c-1"},
  "origin_round": 1,
  "frame_rounds": 8,
  "windows": [
    {"offset": 0, "length": 2, "class": "prepare", "max_calls": 2},
    {"offset": 2, "length": 3, "class": "reason", "max_calls": 3},
    {"offset": 5, "length": 2, "class": "review", "max_calls": 2},
    {"offset": 7, "length": 1, "class": "settle", "max_calls": 0}
  ],
  "late_window": "skip_and_report",
  "running_calls_at_boundary": "carry_reservation",
  "unused_capacity": "do_not_lend_in_first_probe"
}
```

控制 kernel 在 tock 後規劃**下一窗口**；以發放／claim 所觀察的控制 round 記錄，而非推定 task 已在某秒起跑。若階段要求前一批全部結束，必須以結果 barrier 前進，這時是資料依賴階段，不再是固定長度 frame。空窗不能補發過期 grant 追趕。

**daemon／tick：軟排程表不需修改。** 時間線輪替可用現有 `resume rounds`；新付費動作仍要入口驗窗口。想讓跨 node 合作群組一次承諾／取消才需要 E-04；不要為此強迫所有時間線同步。真正 ARINC 653 式 CPU、記憶體和 I/O 隔離超出此原型，**不借其認證或硬即時保證**。

### 2.5 Tickless 與 watchdog

FreeRTOS tickless idle 停止週期 tick interrupt，醒來會修正 RTOS tick count；Zephyr task watchdog 可監看多個任務，並可搭配硬體 watchdog 保底。[FreeRTOS Low Power Support](https://freertoswww.freertos.org/Documentation/02-Kernel/02-Kernel-features/07-Lower-power-support)、[Zephyr Task Watchdog](https://docs.zephyrproject.org/latest/services/task_wdt/index.html)

**改；同。** 前者用於省電，不能照搬「睡多久補多少 tick」到 S-08。後者強化 D-08 的運行層保底；agent 更新 heartbeat 不代表工作有進展。kernel 讀 `activity.json`／外部事件，寫既有 pause／resume／wake；業務期限讀控制回合，daemon watchdog 才用 monotonic 時間。草圖直接沿用舊報告 §6.4／§10.3，**不另造 E 編號**。

## 3. 微核心：aos 的 kernel 比較像可替換的管理服務

### 3.1 Mach 與 L4

Mach 將 task、thread、虛擬記憶體與以 port 權利為基礎的 IPC 作為核心機制；Mach 3 的研究把 Unix 功能搬成其上的服務。L4 強調只留不可移出的核心機制與低成本 IPC。不能把所有 Mach 歷史版本一律說成相同的純微核心。[CMU Mach 概覽](https://www.cs.cmu.edu/afs/cs.cmu.edu/project/mach/public/www/overview.html)、[*Unix as an Application Program*](https://www.cs.cmu.edu/afs/cs/project/mach/public/www/doc/abstracts/mach3_intro.html)、[Liedtke，*On µ-Kernel Construction*（1995）](https://os.itec.kit.edu/deutsch/65_1029.php)

**值得借；主要是同。** S-16 已經讓 kernel 成為 tick 任務，所以不是再把 aos kernel 拆成微核心；真正的對照是 daemon／runner 提供機制，上層帳本、排程器、服務登錄各自成任務。不要為每個小欄位再拆一個服務，徒增檔案往返、token 與診斷成本。

kernel 讀 `<C>/services.json` 與服務卡，寫各服務 `requests/*.json`；回條共用 §1.3 格式。需要換排程器就改核准的 inst、在邊界 restart；LLM 只拿提案入口。**daemon／tick：現有 spawn／restart 足以試拆分，可靠性仍是 D-02／D-07／D-09；沒有新底層需求。**

### 3.2 seL4 capability 與形式驗證

seL4 用 capability 表示對核心物件的操作權，權利可受限委派。2009 年功能正確性驗證是重要成果，但「seL4 已驗證」不能推出所有架構、所有設定、MCS、驅動與上層服務都被同一證明涵蓋。官方明列 verified configurations，MCS 文件仍標示驗證工作進行中。[seL4 capabilities 教學](https://docs.sel4.systems/Tutorials/capabilities.html)、[驗證設定表](https://docs.sel4.systems/projects/sel4/verified-configurations.html)、[官方 CAVEATS](https://github.com/seL4/seL4/blob/master/CAVEATS.md)

原始驗證論文是 [Klein 等，*seL4: Formal Verification of an OS Kernel*（2009）](https://sel4.org/Research/pdfs/sel4-formal-verification-os-kernel.pdf)；借的是把抽象規格與實作之間的性質說清楚，不是套上名稱就取得證明。

**值得借小而明確的保護規則；形式驗證要改，新增。** aos 應先能檢查「子權力不擴大、額度不重複花、舊世代不能提交」，而不是宣稱能證明 LLM 選到最佳工作。把這三個性質放在確定性驗證器，LLM 只提供候選政策。

kernel 讀政策、提案與帳本版號，寫 `validation/<proposal_id>.json`：

```json
{
  "schema": "aos.proposal-check.v1",
  "proposal_id": "p-82",
  "checks": {
    "scope_is_subset": true,
    "ancestor_budgets_fit": true,
    "epoch_matches": true,
    "claim_is_unique": true
  },
  "accepted": true,
  "assurance": "runtime_checks_only",
  "why": "僅通過列出的規則，不代表排程最優或輸出正確"
}
```

先對小型狀態機做窮舉／model checking：兩個子任務同時領最後一筆、在 reserve 與 settle 間崩潰、撤權與 claim 競爭。檢查涵蓋範圍必須寫出；測試通過不叫形式證明，程式證明也不涵蓋不受控 API。

**daemon／tick：基本執行點沿用 D-04／D-09／D-11。** capability 衍生與撤銷語意才是 E-02；無需把 seL4 移植進 aos。

### 3.3 seL4 MCS：最接近「代辦服務花呼叫者的錢」

MCS 把 scheduling context（SC）分離成帶 budget／period 的物件。被動服務沒有自己的 SC 時，可在同步 IPC 接收呼叫者捐出的 SC；回覆鏈追蹤歸還。這使 CPU 消耗歸於真正要求服務的一方，而非共享 server 自己的獨立時間額度。SC 管的是 CPU 時間，並非 LLM token；捐出 SC 也不等於自動取得更高 thread priority。[*Scheduling-Context Capabilities*（2018）](https://www.sel4.systems/Research/pdfs/scheduling-context-capabilities.pdf)、[seL4 MCS 官方教學](https://docs.sel4.systems/Tutorials/mcs.html)

**要改；本次最重要的新借法之一。** A 呼叫審稿服務 S，S 又叫檢索 R：三者執行身分不同，但這筆工作的 `charge_context` 應一路相同。A 不該因服務有自己的 node，就把成本丟給服務的公共預算。反過來，服務自己整理共用索引的成本應有明訂 service account，不能亂扣當時碰巧來的客戶。

kernel 讀 `<B>/contexts/*.json`、請求與委派政策，向帳本寫 `delegation-requests/<id>.json`；帳本核准後寫下列 context，kernel 再交給服務入口：

```json
{
  "schema": "aos.charge-context.v1",
  "context_id": "cc-review-17",
  "root_account": "project-a",
  "work_id": "review-17",
  "parent_context": "cc-project-a-job9",
  "holder": "services/review",
  "mode": "exclusive_loan",
  "authority_id": "cap-81",
  "escrow": {"tokens": 2400, "calls": 2},
  "may_redelegate": true,
  "max_depth": 3,
  "state": "available_to_holder",
  "return_on": "reply_or_reconciled_failure"
}
```

這份 JSON 是**可信帳本的可讀紀錄**，不是 agent 自己寫就生效的支票。同步式代辦可用 exclusive loan：轉交期間父方不能再花同一筆。aos 常是非同步扇出，應改成互不重疊的子額度：A 同時委派 S、R 時分別保留 1600、800，不能把 2400 原封不動複製兩份。傳回的是剩餘支用權，不是退回已消耗 token；供應商未結算的部分也不能歸還。

**daemon／tick：新需求 E-01 是「可信請求付費脈絡」，不是把價格塞進 daemon。** tick 固定任務的授權來源；服務／呼叫閘門按每個 request 綁定 context，帳本原子移轉。D-05／D-11 的預留結算仍需先成立。kernel 可決定誰借誰，不能自己改帳冒充已交接。

### 3.4 QNX Neutrino：IPC 也可以傳遞急迫性

QNX 的訊息驅動 priority inheritance 讓服務處理請求時反映客戶優先序，降低共享服務造成的反轉；它不是 token 預算 donation。[QNX，Priority inheritance and messages（7.1）](https://qdn.qnx.com/developers/docs/7.1/com.qnx.doc.neutrino.sys_arch/topic/ipc_Priority_inheritance_messages.html)

**要改；新。** 在 §1.3 請求加上核准的 `urgency_ref`，與 §3.3 `charge_context` 分開。kernel 讀服務佇列與依賴，寫 `effective-priorities.json`；服務的下一筆准入採真正客戶的急迫性，完成便解除，不永久把整個 server 升成最高級。多客戶併發時按 request 隔離，不只給程序一個全域「很急」。草圖用 §2.2；**daemon 無新需求，入口有 E-01 脈絡綁定需求**。

### 3.5 MINIX 3：替換故障服務，先處理介面與狀態

MINIX 3 把許多驅動／服務放在使用者空間，由 reincarnation server 監督與重起，縮小故障範圍。這不表示所有驅動任何時刻都能無痕復原。[Herder 等，MINIX 3 可靠性研究（2006）](https://www.minix3.org/docs/jorrit-herder/edcc06.pdf)、[MINIX servers 官方說明](https://wiki.minix3.org/doku.php?id=developersguide%3Aoverviewofminixservers)

**值得借；監督是同，穩定服務重接是新補充。** 舊報告已借 Erlang supervisor，這裡不重抄退避與 restart budget。aos 新重點是工具代理或帳本重起後，舊 client 怎麼知道「同一個服務的新實例」而不是重送一切。

kernel 讀 `<S>/service.json`、exit 與未結 requests，寫 `<C>/recovery/<service>.json` 和現有 task `ctl.json`。服務把 `service_id` 保留、`instance_epoch` 更新；舊 request ID 先查結果再決定續做。復原草圖見 §5.2 的 manifest。**daemon／tick：D-18 足以管重起；需要宣稱復原到一致業務狀態時再加 E-05。**

### 3.6 Fuchsia／Zircon：handle、job 與三種樹

Zircon handle 帶特定物件的權利；複製／替換可縮限權利。job 包含子 job 與 process，政策向下約束，例外可沿樹上報。job policy 不是通用 token 預算系統。[Zircon Handles](https://fuchsia.dev/fuchsia-src/concepts/kernel/handles)、[Jobs](https://fuchsia.dev/fuchsia-src/concepts/process/jobs)、[job_set_policy](https://fuchsia.dev/reference/syscalls/job_set_policy)

**要改；部分同，補上分離三種樹。** aos 應分清 node 路徑樹（S-14）、生命週期管理樹（誰負責取消／重起），以及付費帳戶樹（誰出錢）。共享檢索服務不應因某客戶取消，就跟著整個被殺；該取消的是那個工作脈絡。

kernel 讀 `<C>/jobs/*.json` 與帳本，寫取消／監督請求：

```json
{
  "schema": "aos.job.v1",
  "job_id": "review-17",
  "parent_job": "project-a-job9",
  "payer": "project-a",
  "owned_tasks": ["agents/reviewer:reviewer-r4"],
  "shared_service_requests": ["search-request-31"],
  "on_cancel": "cancel_owned_tasks_and_own_requests",
  "authority": {"may_spawn": true, "may_stop_daemon": false}
}
```

共享服務只取消指定 request；已開始的成本留帳。S-21 子 daemon 的所有權規則照現行 spec，不由 job 樹自動改寫。**daemon／tick：任務生命週期與來源沿用 D-01／D-06／D-09；請求級別取消／付費脈絡需 E-01，能力縮限需 E-02。**

## 4. Exokernel、library OS、unikernel：保護要小，抽象要有人負責

### 4.1 Aegis／ExOS

Exokernel 把保護與管理分離；Aegis 保護並多工分配資源，ExOS 等 library OS 在使用者層提供抽象。它不是完全沒有抽象或撤回機制，而是避免把唯一高階資源政策綁死在核心。[Engler 等，*Exokernel: An Operating System Architecture for Application-Level Resource Management*（1995）](https://doi.org/10.1145/224056.224076)、[MIT Exokernel 專案](https://pdos.lcs.mit.edu/archive/exo/)

**值得借；強化舊結論。** aos 的 daemon 保證啟動、邊界控制、歸屬與回條；kernel library 可以各自實作 EDF、stride 或 LLM 政策。token／錢是 aos 的原生管理對象，不必假裝成裸記憶體頁。只說「daemon 不管政策」仍不足夠：任務能直接繞過呼叫入口時，就沒有安全的資源多工。

kernel 讀 `<C>/policy.json`、統一 snapshot，寫 proposal／grants；可將共同帳務 SDK 做成 library，但其硬上限仍由可信入口執行。JSON 沿用舊報告 §6 的 proposal→grant 契約，**不重造一版**。daemon／tick 對應 D-04／D-09；無 E 新需求。

### 4.2 Nemesis：不要讓共享服務成本串到別人身上

Nemesis 把 QoS 與可歸責的資源使用放在架構中心；self-paging 讓應用承擔自己的分頁工作，降低共享服務內的隱藏競爭（QoS crosstalk）。這不等於完全消除硬體共享干擾。[Hand，*Self-Paging in the Nemesis Operating System*（1999）](https://www.usenix.org/legacy/events/osdi99/full_papers/hand/hand.pdf)

**值得借；新。** aos 的「分頁」可對應摘要、context 壓縮、檢索、工具資料轉換。若 A 產生十萬字交給公共摘要服務，摘要費用全算公共服務，A 就能繞過自己的預算，還拖慢 B。這比只看 agent 的 `usage.json` 更關鍵。

kernel 讀工作鏈與服務 usage，寫 `<B>/charge-requests/*.json`；服務的新增事件：

```json
{
  "schema": "aos.service-cost.v1",
  "event_id": "summary-91-settled",
  "request_id": "summary-91",
  "work_id": "review-17",
  "charge_context": "cc-review-17",
  "kind": "context_compaction",
  "usage": {"input_tokens": 1800, "output_tokens": 300, "calls": 1},
  "executor": "services/summary",
  "payer": "project-a"
}
```

跨客戶共用的 cache miss 先定價：由首個請求付、由服務公共額度付，或按明定比例分攤。不能事後把每個 cache 命中都算一遍原始全成本。人的審閱也可記 `review_minutes` 與 `pending_reviews`，但可讀性分數不是可搬移的 CPU／token 存量。

**daemon／tick：E-01 保存請求脈絡；計量與分攤屬服務／帳本。** 不要叫 daemon 決定摘要是不是值得做。

### 4.3 MirageOS／unikernel

MirageOS 的 unikernel 以 library OS 將應用及需要的系統元件組成專用映像，針對部署減少不必要元件。[Madhavapeddy 等，*Unikernels: Library Operating Systems for the Cloud*（2013）](https://unikernel.org/files/2013-asplos-mirage.pdf)

**改；同。** aos 可借固定 inst 依賴、明列工具與資料介面、保留可重建版本；不用借每任務一個 VM 映像或單語言限制，否則增加操作與除錯成本，還違背 S-04 的多語言優勢。kernel 讀 inst sidecar／digest，寫核准 spawn；格式沿用舊報告 §9.2，服務需求用 §1.1 卡片。**daemon／tick 無新需求，D-06 的執行描述快照即可。**

## 5. Object-capability 與持久化 OS

### 5.1 KeyKOS／EROS／CapROS、Capsicum、CHERI：權力是一個受保護的引用

KeyKOS、EROS、CapROS 這條系譜結合 capability 與持久物件；EROS 的代表論文是 *EROS: A Fast Capability System*（1999），CapROS 延續其設計。Capsicum（2010）在 UNIX 上以 capability mode、受限檔案描述元支援權限分隔。CHERI 是指令集層的 capability 擴充，提供細粒度記憶體保護與隔間化，不是 agent 預算系統。[CapROS 架構與原論文入口](https://www.capros.org/overview.html)、[Watson 等，*Capsicum: Practical Capabilities for UNIX*（2010）](https://www.usenix.org/conference/usenixsecurity10/legacy-presentation/capsicum-practical-capabilities-unix)、[CHERI 官方 FAQ](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/cheri-faq.html)

**值得借權力縮限；CHERI 硬體不要借來解當前問題。** 舊報告的 Linux capabilities 是拆分 root 特權；object-capability 更直接指「這個特定收件入口／帳戶，你能做哪些事」。可見路徑、名字難猜、JSON 有簽名欄位，都不會自動變成不可偽造的權力。

kernel 讀受保護 `<B>/authorities/*.json`，向權限服務提出縮限請求；核准者寫出只讀描述，再由入口驗證：

```json
{
  "schema": "aos.authority-view.v1",
  "authority_id": "cap-81-child2",
  "derived_from": "cap-81",
  "subject": "services/review",
  "object": "account:project-a:review-17",
  "rights": ["reserve", "settle"],
  "constraints": {"tokens_total": 2400, "max_calls": 2, "pool": "text-small"},
  "may_delegate": false,
  "revocation_epoch": 3,
  "enforcement": "trusted_gateway_lookup"
}
```

持有者送的是 ID，可信入口按受保護身分查表，不採信任務自己附的 rights。若使用 bearer token，要防止可讀描述把秘密外洩；S-01 不要求把授權秘密印給所有讀者。子權利取父權利交集；縮小 `max_calls` 不會解除 `tokens_total`。

同理，「只能送件」應由收件服務實施；直接給 inbox 目錄的寫權，往往也能改刪其他信，不能拿它冒充只有 send 權利的 object-capability。

撤銷也不能只刪 symlink：任務可能保有 open fd、已讀到資料或已送出 API。新 claim 需查撤銷世代，既有在途費用繼續結算。**daemon／tick：D-09／D-19 是基礎；E-02 補衍生鏈與撤銷生效點。** 合作式探針可用表模擬，但不能宣稱對任意 inst 強制。

### 5.2 Persistent OS：借「一致復原點」，不把整台機器倒帶

KeyKOS／EROS／CapROS 的持久儲存設計把物件、程序等狀態納入 checkpoint；CapROS 明確區分邏輯切點（demarcation）與資料全部落盤（stabilization），並承接、調整前代設計。持久世界與非持久驅動／外部世界的邊界仍須特別處理。[CapROS，*The Checkpoint Mechanism*](https://www.capros.org/design-notes/Checkpoint.html)、[*Persistence, Non-persistence, and Device Drivers*](https://www.capros.org/design-notes/UserDrivers.html)

其中 single-level store／orthogonal persistence 的重點是物件的持久生命週期不直接受限於某次程序開機，不是所有資料只能放一層目錄。aos 可借穩定工作／物件身分，無須把一般 JSON 檔案介面改造成整個虛擬記憶體的持久映像。

**要改；新。** aos 已把 state、plan、pc 存檔，但多檔 rename 不是共同交易。現行 agent 在 act 恢復時某一步可能重做；磁碟回到昨天也不會讓昨天的 API 費用取消。因此值得持久化的是「可重建的邏輯工作、權力與待對帳清單」，不承諾任意程序記憶體透明恢復。

kernel 讀 agent checkpoint、帳務游標、未結 request 與命名空間版號，寫 `<C>/recovery/review-17/manifest.json`；只有全部引用的不可變版本都存在，才發布 `committed.json`：

```json
{
  "schema": "aos.recovery-manifest.v1",
  "checkpoint_id": "review-17-cp4",
  "work_id": "review-17",
  "state_ref": "states/rev4.json",
  "definition_revision": 7,
  "namespace_revision": 3,
  "account_cursor": 981,
  "external_requests": [
    {"request_id": "review-17-call-2", "state": "unknown", "reservation": "res-41"}
  ],
  "resume_at": "before_review_result_commit",
  "on_unknown": "reconcile_before_retry",
  "storage_guarantee": "process_crash_only"
}
```

寫 immutable state→確認引用→最後寫 commit marker，是邏輯發布順序。要保證斷電還在，必須另定 fsync／目錄持久化等契約；上例只宣告程序崩潰範圍。復原仍查當前帳本，不把 `account_cursor:981` 當成可以把帳退回 981。供應商無查詢／冪等能力時，unknown 可能需人裁決，不能保證外部 exactly-once。

**daemon／tick：現有 inst 可以讀 manifest 自行恢復。** 若要 runner 承諾「只從已提交 checkpoint 起」，新增 E-05；它只驗完整性與版本，業務續做方式仍在 agent。這補 D-17 的帳 checkpoint，不重列同一項。

## 6. 份額、歸帳與階層排程：四件不同的事

### 6.1 Lottery／stride：票是競爭份額，不是花一次少一張的 token

Lottery scheduling 以 ticket 比例抽選資源使用者；currency 讓一個模組在自身獲得的外部份額內自由分配內部 tickets，ticket transfer 可把等待客戶的服務權暫時交給 server。Stride 用確定性的 pass／stride 排序提供比例份額，降低 lottery 的短期隨機波動。[Waldspurger、Weihl，*Lottery Scheduling: Flexible Proportional-Share Resource Management*（1994）](https://www.usenix.org/legacy/publications/library/proceedings/osdi/full_papers/waldspurger.pdf)、[*Stride Scheduling: Deterministic Proportional-Share Resource Management*（1995）](https://www.waldspurger.org/carl/papers/stride-mit-tm528.pdf)

**要改；currency／transfer 是新，公平排序與舊 CFS 類似。** aos 的專案 A 可有 100 外部 tickets，內部分給 2 個或 200 個 agent，都不增加 A 相對於 B 的總份額。某一回合抽中不保證完成，更不保證 token 等量；一次 100 token 與一次 10000 token 不能都當一份公平服務。

kernel 讀 ready、群組份額與實際服務帳，寫 `$AOS7_TASK/stride-state.json` 和 dispatch：

```json
{
  "schema": "aos.share-state.v1",
  "pool": "text-small",
  "service_unit": "billed_tokens",
  "policy": "stride_inspired",
  "pass_update": "actual_service / normalized_share",
  "groups": [
    {"id": "project-a", "root_tickets": 100, "pass": 3000,
     "local_tickets": {"planner": 20, "workers": 80}},
    {"id": "project-b", "root_tickets": 100, "pass": 3500}
  ],
  "inflight_service": "reserve_estimate_then_reconcile",
  "new_member_baseline": "current_virtual_floor"
}
```

同一池先挑有需求、可負擔的最低 pass 群組，再在群組內挑。派出時先計入預估在途量，回覆後補差；不足額的大工作可累積保留，不能永遠被小工作塞滿空隙。動態加入、票數修改與非均勻成本需要明訂 pass 修正，不能直接繼承原論文所有誤差界。

**建議先用 stride 啟發版，不先抽籤。** 理由是好重播、好解釋，而不是 lottery 錯。若要比較 lottery，固定 seed、保存每次候選集與抽值；短期飢餓仍要另設限制。ticket transfer 只轉競爭地位，不自動轉金額；實際支出用 §3.3。

**daemon／tick 無新算法需求。** D-03／D-05 提供服務帳，D-04 提供准入。kernel 可先在合作式 worker 上試，不能拿「各跑同樣回合數」當 token 公平的結果。

### 6.2 Resource containers：讓記帳單位跨越 process／node

Banga、Druschel、Mogul 把 resource principal 從程序拆開：一項活動使用的使用者層與核心層工作可歸同一 container；一個 server 執行緒也能先後服務不同活動。論文原型是修改 Digital UNIX，不是另一套獨立 OS；本次借的是它對程序中心記帳的修正。[*Resource Containers: A New Facility for Resource Management in Server Systems*（1999）](https://www.usenix.org/legacy/events/osdi99/full_papers/banga/banga.pdf)

**值得借；新，且比 ticket 更適合作為 token 帳本的主體。** 一個 `review-17` 工作跨 planner、search、writer、reviewer；四個任務各有 tid，但只有一條可核對的工作帳。相反，同一常駐 reviewer 處理十位客戶，不應把十位費用全放在 reviewer node 的帳戶。

kernel 讀服務事件、job 宣告，寫給帳本的容器建立請求；帳本輸出 `<B>/containers/review-17.json`：

```json
{
  "schema": "aos.resource-container.v1",
  "container_id": "work:review-17",
  "owner_account": "project-a",
  "parent_container": "work:project-a-job9",
  "members_are": "requests_not_processes",
  "limits": {"tokens_total": 10000, "calls_total": 6},
  "spent": {"tokens": 3600, "calls": 2},
  "reserved": {"tokens": 2400, "calls": 2},
  "request_ids": ["plan-17", "search-31", "review-17-call-2"],
  "why": "跨服務的同一件工作，不因改名或重起洗掉成本"
}
```

容器是**歸帳與限制的身份**，不必是新的目錄階層、namespace 或常駐程序。kernel 仍依 S-17 管任務；請求是任務內部細分的計量單位，沒有把 S-17 偷改成只管請求。一次共享呼叫若替多件工作產生成果，必須有唯一總帳事件與明訂分攤，不能每個容器都重算全額。

**daemon／tick：D-03／D-06 已有持續身分；E-01 新增同一活任務內的逐請求歸帳綁定。** 靜態 birth.group 不足以描述 multiplexing server。這是對舊報告的實質補充，不是把 cgroup 改名。

### 6.3 Scheduler activations：給排程器足夠事件，不給它幻想的原子快照

Scheduler activations 解決使用者層執行緒排程看不到阻塞、喚醒或處理器重新配置的問題；核心以 upcall 通知使用者層，讓其管理平行度。它不是「任意智能體都能排得好」的理論。[Anderson 等，*Scheduler Activations: Effective Kernel Support for User-Level Management of Parallelism*（1991 會議版／1992 期刊版）](https://homes.cs.washington.edu/~tom/pubs/sched_act.html)

**要改；通知理由是新，可靠事件輸送與 D-01／D-15／D-16 相同。** aos 不移植 thread／upcall；改為持久事件檔，由 kernel 任務在自己的回合處理。不能只通知「又過一回合」，還應知道「有槽位」「工作解除阻塞」「服務失聯」。不用每個事件都呼叫一次 LLM。

kernel 讀 `mnt/events/events.jsonl` 與最新 snapshot，寫 `$AOS7_TASK/event-cursor.json`、dispatch：

```json
{
  "schema": "aos.scheduler-event.v1",
  "event_id": "pool-text-small-991",
  "event": "capacity_available",
  "source": "services/model-a",
  "source_epoch": "model-a-4",
  "capacity_revision": 38,
  "reason": "request_settled",
  "request_id": "call-81",
  "hint": {"free_slots": 1},
  "requires_recheck": true
}
```

事件只提示重查；讀到 free_slots=1 不代表輪到自己時還有一格。事件序號缺口要補查，重播不重發 grant。新事件可由普通服務任務寫，kernel 自己看；需要省輪詢時才接 D-16 wake。**daemon／tick 無新增 E 需求，更不應在 daemon 中呼叫排程 LLM。**

### 6.4 CPU inheritance scheduling／HLS：最符合「排程器也是任務」

CPU inheritance scheduling 允許一般 thread 充當其他 thread 的 scheduler，透過 CPU 時間捐贈組成階層。HLS 則研究不同 soft real-time scheduler 的階層組合及可分析的保證契約；不是任意堆 scheduler 就自動保有原保證。[Ford、Susarla，*CPU Inheritance Scheduling*（1996）](https://www.usenix.org/conference/osdi-96/cpu-inheritance-scheduling)、[Regehr、Stankovic，*HLS: A Framework for Composing Soft Real-Time Schedulers*（2001）](https://www-old.cs.utah.edu/flux/papers/hls-rtss01/)

**值得借；新。** S-16 早已允許 LLM 任務做 kernel；這兩項研究補上「如何把這樣的 scheduler 約束在父層承諾內」。根 scheduler 只配專案額度；專案內可以用 EDF、LLM、stride，各自決定；父層不需讀所有子 agent 的 prompt。S-20 的同像性可用於這種契約，但不能讓父 daemon 自動理解所有子 daemon 從屬。

父 kernel 讀 `<C>/child-schedulers/*/demand.json`、帳務摘要，寫子 scheduler 能讀的 `envelope.json`；子 kernel 讀 envelope、自己的 ready，寫子 proposals：

```json
{
  "schema": "aos.scheduler-envelope.v1",
  "envelope_id": "env-a-12",
  "child_scheduler": "project-a/policy",
  "clock": {"node": "control", "epoch": "c-1", "from_round": 80, "until_round": 100},
  "escrow_id": "escrow-a-12",
  "limits": {"tokens_total": 10000, "calls_inflight": 2},
  "policy_cost_cap_tokens": 500,
  "policy_cost_included_in_total": true,
  "scope": ["project-a/jobs"],
  "fallback": "stride_inspired",
  "report": "usage_and_oldest_ready_wait"
}
```

父層扣住 10000，子層不因新開子 scheduler 就擴大它。兩個 child envelope 互不重疊；policy 的 500 也在總額內。child 承諾每四個控制回合服務一次前，得先確定父層供應的時機，不只看平均 token 數。報不出可證的供應界，就稱 best effort。

**daemon／tick：可完全用任務與掛載試階層。** D-08 管保底、D-09 管範圍、D-11 管額度；E-01／E-02 把 envelope 延伸成可受限委派的支用權。排程 LLM 慢或消失時，父層額度不會因此無限續發。

## 7. 其他有用的排程研究：挑問題借，不追算法名氣

### 7.1 Eclipse 與 Scout：一個是保留域，一個是工作路徑

Eclipse（1998）基於 Plan 9，以 reservation domain 分配 CPU、I/O、記憶體等資源，研究累積服務保證。Scout（1996）把 path 作為明確抽象，沿資料處理路徑管理資源與排程。**Eclipse 的核心不是 Scout 那個 path；兩者不能合稱「Eclipse／Scout 的 path」。** [Bruno 等，*The Eclipse Operating System: Providing Quality of Service via Reservation Domains*（1998）](https://www.usenix.org/conference/1998-usenix-annual-technical-conference/eclipse-operating-system-providing-quality)、[Mosberger、Peterson，*Making Paths Explicit in the Scout Operating System*（1996）](https://www.usenix.org/conference/osdi-96/making-paths-explicit-scout-operating-system)

**兩者都要改；新。** Eclipse 對應「此專案在每個服務池都有一份經准入的資源」，Scout 對應「收件→檢索→生成→審閱」的整條交付路徑。只保障生成 agent 很快，審閱沒有額度，最後仍交不出結果。易用性也要看端到端需幾次人工補救，不只某個 agent 的文字評分。

kernel 讀 `<C>/paths/*.json`、各服務容量，寫工作 container、階段 grants：

```json
{
  "schema": "aos.work-path.v1",
  "path_id": "answer-9",
  "container_id": "work:answer-9",
  "deadline": {"clock_node": "control", "round": 110},
  "stages": [
    {"id": "retrieve", "after": [], "budget_tokens": 1000},
    {"id": "draft", "after": ["retrieve"], "budget_tokens": 4000},
    {"id": "review", "after": ["draft"], "budget_tokens": 2000}
  ],
  "admission": "reserve_end_to_end_budget_before_first_paid_stage",
  "acceptance": {"artifact": "answer.json", "needs_review": true}
}
```

先保留整體可消耗額度，服務槽在各階段即將執行時才領，不必全程霸占。不能把 pipeline 每一步都當 gang 同時啟動；資料還沒出來時，下游應 blocked。Eclipse 的服務界線也不直接變成答案品質保證。

**daemon／tick 無新增需求。** D-04／D-05／D-11 管預留與各階段准入；E-01 讓整條 path 的成本歸到同一工作。

### 7.2 Borrowed Virtual Time（BVT）

BVT 讓延遲敏感工作暫時把有效虛擬時間往前移（warp），同時保留長期加權服務記帳與對 warp 的限制。[Duda、Cheriton，*Borrowed-Virtual-Time Scheduling: Supporting Latency-Sensitive Threads in a General-Purpose Scheduler*（1999）](https://doi.org/10.1145/319344.319169)

**要改；主要同。** aos 可讓剛收到人類訊息的工作借一小段優先機會，實際花費照記 pass。不能把每封自寄訊息都當新互動，重啟也不能洗掉借用紀錄。它補充舊報告 EEVDF 的互動延遲思路，沒有必要同時維護兩套公平帳。

kernel 讀現有 fair-state 與可信人類事件，寫 `$AOS7_TASK/latency-state.json`：

```json
{
  "entity": "project-a",
  "policy": "bounded_virtual_time_advance",
  "max_advance_service_tokens": 500,
  "max_burst_calls": 1,
  "cooldown_control_rounds": 8,
  "actual_service_always_charged": true,
  "trigger": "verified_human_request"
}
```

這是 aos 啟發版，不是重現 BVT 的時間參數。**daemon／tick 無新需求。** 保底上限與 grant 沿用 D-04／D-05。

### 7.3 Coscheduling／gang scheduling

Coscheduling 研究互相通訊的工作若被分開排，會發生等待與效率損失；gang scheduling 更嚴格地把一組成員一起安排。原脈絡是平行計算處理器配置，不是讓所有 agent 同時聊天。[Ousterhout，*Scheduling Techniques for Concurrent Systems*（1982）](https://web.stanford.edu/~ouster/cgi-bin/papers/coscheduling.pdf)

**要改；新。** aos 有用的是「合作閉包」：辯論雙方、協作工具和收尾服務都取得最低可行額度，避免只喚醒 A、B 永遠被餓死。對一般檢索→寫作 pipeline，只需階段依賴，不需要同步運行。

kernel 讀 `<C>/cohorts/debate-4.json` 與容量，向帳本申請整組 reservation，再寫授權：

```json
{
  "schema": "aos.cohort.v1",
  "cohort_id": "debate-4",
  "members": ["argue-a", "argue-b", "judge"],
  "admission": "all_or_none_budget",
  "phase": "prepared",
  "commit_epoch": 6,
  "required_ready": ["argue-a", "argue-b"],
  "judge_release": "both_results_ready",
  "on_prepare_timeout": "release_unclaimed_reservations"
}
```

prepared 只占額度，不能先發起付費動作；commit 後各入口核對同一世代。這保證「不只放行半組」，不保證跨機器物理同時起跑，也不保證 commit 後所有程序都活著。組太大會阻塞小工作；需最大群組大小與等待上限。

現有 `spawn {"batch":[...]}` 只讓同 node 在同回合依序處理一批，壞項可被跳過、tick 中斷可能只起一部分；**不是原子 gang 准入**。合作式原型可讓 worker 等 commit 檔。**正式需要 E-04；不要把 batch 說成已完成。**

### 7.4 Feedback control scheduling

這條研究把排程當有量測、有控制輸入與動態延遲的系統，以回授調整准入、工作品質或利用率，處理實際負載與估計差異。[Stankovic 等，*The Case for Feedback Control Real-Time Scheduling*（1999）](https://ieeexplore.ieee.org/document/777445/)、[Lu 等，*Feedback Control Real-Time Scheduling: Framework, Modeling, and Algorithms*（2002）](https://www.cse.wustl.edu/~lu/papers/rtsj02.pdf)

**要改；新。** aos 可量最老 ready 等待回合、服務失敗率、slot 壓力、每完成工作成本，再調並行數與預取量。LLM 適合解讀任務變化、建議下一段目標；不適合在無模型下每個 tock 猛改多個參數。

kernel 讀窗口統計、寫 `$AOS7_TASK/controller-state.json` 與下一窗口 policy：

```json
{
  "schema": "aos.feedback-policy.v1",
  "sample_clock": "control",
  "window_rounds": 20,
  "metric": "oldest_ready_wait_rounds",
  "target": 4,
  "actuator": "max_calls_inflight",
  "range": [1, 4],
  "max_change_per_window": 1,
  "minimum_settle_windows": 2,
  "only_raise_when": "backend_has_spare_capacity_and_budget",
  "on_missing_data": "hold_last_safe_value",
  "saturation_behavior": "do_not_accumulate_unbounded_error"
}
```

等待升高可能因 provider 壅塞；此時加並行反而更糟。先用階躍實驗量方向與延遲，再挑控制規則。回合長度不固定時，分開看「每控制回合的使用者等待」與 provider 的每秒 rate limit，不能用變動的 round 直接代入固定秒數的控制器。聲稱穩定性需模型／量測支持，LLM 的理由文字不能取代。

**daemon／tick 無新需求。** D-15 是量測，D-05 是執行閘門；數值控制器在普通 kernel 任務內就能做。

### 7.5 Market／auction：Spawn 與 Tycoon

Spawn（1992）以計算經濟模型分配分散的閒置資源；Tycoon（2004 預印本、2005 期刊）以有限信用及投標調整比例資源份額。這些研究確有軟體 agent 參與資源配置，但那不是今天的生成式 LLM。[Waldspurger 等，*Spawn: A Distributed Computational Economy*（1992）](https://www.waldspurger.org/carl/papers/spawn-ieee-tse-feb92.pdf)、[Lai 等，*Tycoon: An Implementation of a Distributed, Market-Based Resource Allocation System*（2004）](https://arxiv.org/abs/cs/0412038)、[2005 期刊版](https://journals.sagepub.com/doi/10.3233/MGS-2005-1303)

**要改；新，但不排第一。** LLM 可以評估「多花 1000 token 審一次，比做另一件事值不值得」，把偏好轉成有限預算內的投標；確定性 auctioneer 決定分配。不能讓每個 agent 任意宣告自己價值無限大，也不能把內部信用和真實貨幣混為一談。

kernel 讀 `<C>/bids/*.json`、信用帳與真實成本上界，寫 `auction-results/*.json`，再走既有 grant：

```json
{
  "schema": "aos.resource-bid.v1",
  "bid_id": "bid-review-17",
  "bidder_account": "project-a",
  "work_id": "review-17",
  "window": {"clock_node": "control", "from_round": 80, "until_round": 90},
  "pool": "text-small",
  "max_internal_credits": 30,
  "external_cost_cap_microunits": 6000,
  "currency": "USD",
  "expected_benefit": "降低交付前漏掉錯誤的機率",
  "evidence": ["review-checklist:rev3"],
  "minimum_bundle": {"tokens": 2000, "calls": 1}
}
```

投標被選中仍要過真實預算、權限與 slot 檢查。對整套審閱不可分割的工作，比例分到 20% 並不代表有用；需 bundle／最低可行額度與放不下的處理。Sybil、多開 agent 增票要靠外部 owner 帳限制。可讀性與易用性可寫入預期效益及驗收證據，不能只讓作者自己打高分換錢。此設計不主張誘因相容、truthfulness 或最優性。

**daemon／tick 無新需求。** 投標、清算與信用在 kernel／帳本；D-11 防超配。先固定價格／有限點數試驗，沒有證據前不用真金錢交易市場。

## 8. 分散式、契約、Actor：通訊方式會反過來決定排程

### 8.1 Barrelfish multikernel

Barrelfish 把多核心機器視為分散系統：明確訊息傳遞、與硬體分離的 OS 結構、把狀態看成可複製的分散狀態，而非默認大家共享一份可變資料。[Baumann 等，*The Multikernel: A New OS Architecture for Scalable Multicore Systems*（2009）](https://www.microsoft.com/en-us/research/wp-content/uploads/2009/10/paper.pdf)

**要改；新。** aos 對照的是多 node／多 daemon 的管理，不是每個 CPU 核心起一個 LLM。各域 kernel 可持有本地快照，透過 S-23 訊息交換需求與額度；讀取副本過期可接受，兩邊各花同一份餘額不可接受。

kernel 讀本域 snapshot 與上層 envelope，寫 `<C>/exports/summary.json`：

```json
{
  "schema": "aos.domain-summary.v1",
  "domain": "project-a",
  "epoch": "a-3",
  "seq": 71,
  "observed_clock": {"node": "project-a/control", "round": 29},
  "ready": 6,
  "escrow_id": "escrow-a-12",
  "unspent_in_local_escrow": 1800,
  "authority": "local_escrow_only",
  "stale_after_parent_round": 100
}
```

父層分不重疊 escrow，子層在自己的額度內運作。父層收到較舊 seq 就忽略；沒收到新摘要應標 stale，不回收未知在途費用。可把可見性做 eventual consistency，不能把總額保證也順便降成「最後大概一致」。**daemon／tick 沿用 D-10／D-11，不必先加入全域共識或同步時鐘；新增脈絡與權利仍是 E-01／E-02。**

### 8.2 Singularity：通道不只規定欄位，也規定下一步能做什麼

Singularity 以 software-isolated processes（SIP）、契約式通道與 manifest 為核心研究方向，依靠語言／驗證條件支援隔離與通訊規則；任意 Python／shell 任務不會自動取得 SIP 性質。[Hunt、Larus，*Singularity: Rethinking the Software Stack*（2007）](https://www.microsoft.com/en-us/research/publication/singularity-rethinking-the-software-stack/)

**值得借通道狀態機；不借限制所有 inst 的語言。新。** JSON schema 能驗欄位，不一定能擋「尚未 reserve 就 settle」「同一 request 已完成又改成 accepted」。kernel 讀契約、回條與狀態，寫驗證／拒絕結果；服務端執行轉移：

```json
{
  "schema": "aos.channel-contract.v1",
  "interface": "paid-call.v1",
  "initial": "submitted",
  "transitions": {
    "submitted": ["reserved", "rejected"],
    "reserved": ["started", "cancelled_unstarted"],
    "started": ["settled", "unknown"],
    "unknown": ["settled", "confirmed_not_started"],
    "settled": []
  },
  "duplicate_event": "return_existing_result",
  "terminal_rewrite": "reject"
}
```

取消與查詢是對 request 的操作，不應粗暴地把任何 started 狀態改成「已退款」。此契約還能產生簡短操作卡，改善 S-01；一次能看到下一步合法操作，比讀一大段 API 手冊容易。

**daemon／tick：控制回條仍沿用 D-02；業務通道由服務驗。** 只有跨節點成組提交才需 E-04，不為每種 JSON 通道新增 daemon 功能。

### 8.3 Spring：介面與實作分離

Spring 是 Sun 的分散、物件導向 OS 研究；其 object model 以強型別介面描述服務，分離介面與實作，也支援跨地址空間／機器的組合。[Mitchell 等，*An Overview of the Spring System*（1994）](https://citeseerx.ist.psu.edu/document?doi=2dc6e0965f66e0dc1ed92fa376107a9f3ea2870f&repid=rep1&type=pdf)、[Radia 等，*The Spring Object Model*（1995）](https://www.usenix.org/conference/coots-95/spring-object-model)

**值得借；新，但可合併進 Plan 9 方案。** kernel 讀 §1 的 `service.json`，驗 `interface: llm-submit.v1` 後綁定；同介面可由不同語言、mock 或遠端服務實作。服務回條須有可讀版本錯誤，不能猜不相容欄位。草圖沿用 §1.1／§8.2，**不另外導入 IDL 編譯器、分散物件 broker；daemon 無新需求，熱替換看 E-03。**

### 8.4 Amoeba／Sprite：放置工作，比透明移動程序實際

Amoeba 的設計偏向共享處理器池、物件與 capability、使用者層 IPC；Sprite 著重 UNIX 相容工作站環境與透明程序遷移。原作者的比較明列這項差異，不應把兩者都簡化成相同的 migration OS。[Douglis 等，*A Comparison of Two Distributed Systems: Amoeba and Sprite*（1991 稿）](https://www.cs.vu.nl/~ast/Publications/Papers/csj-1991.pdf)、[Douglis、Ousterhout，*Transparent Process Migration: Design Alternatives and the Sprite Implementation*（1991）](https://onlinelibrary.wiley.com/doi/abs/10.1002/spe.4380210802)

**要改；新。** aos 可以把下一個可恢復 inst 放到另一個模型／工具域，移交 checkpoint、付費脈絡及需要的掛載。不要搬整個 node 資料夾期待程序繼續：現行 node 消失會觸發 kill，路徑又是 node id（S-14）。

kernel 讀工作 checkpoint、目標 `service.json`、目前在途清單，寫移交提案：

```json
{
  "schema": "aos.relocate-work.v1",
  "work_id": "review-17",
  "from_domain": "local",
  "to_domain": "remote-a",
  "checkpoint_id": "review-17-cp4",
  "transfer_mode": "stop_at_safe_point_then_spawn",
  "account_identity": "work:review-17",
  "old_holder_epoch": 4,
  "new_holder_epoch": 5,
  "requires": ["old_holder_fenced", "unknown_calls_reconciled", "target_mounts_ready"]
}
```

準備資料由另一個 tick 任務執行，準備完成才發目標 spawn；不能讓新舊實例各自重做同一 paid step。**daemon／tick 初版不用透明 process migration；D-02／D-10 與 E-01／E-05 已足。** 不可重建的記憶體、open socket、遠端生成中的 hidden state 不確定能否遷移，應拒絕或等它完成。

### 8.5 Actor 模型：概念存在，但不要替它發明一套「標準 Actor OS」

Actor 是非同步訊息與局部狀態的並行模型；收到訊息後可送訊息、建立 actor、決定後續行為。它本身不是通用 OS，沒有一套統一的檔案、持久化或 exactly-once 規格。[Agha，*Actors: A Model of Concurrent Computation in Distributed Systems*（1986）](https://direct.mit.edu/books/monograph/4794/ActorsA-Model-of-Concurrent-Computation-in)

**要改；大部分同。** S-19 agent 狀態機與 inbox 已很接近 actor 寫法，舊報告也有 supervisor／背壓。新補的是把「邏輯 agent 身分、信箱、付費工作」分開，讓重起換 tid 不換地址；同一信箱按受控順序處理。

kernel 讀 mailbox 水位與 consumer checkpoint，寫 mailbox admission；worker 讀 `inbox/*.json`，寫 `processed/<message_id>.json`：

```json
{
  "schema": "aos.message.v1",
  "message_id": "review-17-msg3",
  "to_actor": "project-a/reviewer",
  "sender_seq": 12,
  "work_id": "review-17",
  "charge_context": "cc-review-17",
  "reply_to_alias": "caller-replies",
  "body_ref": "inputs/rev3.json"
}
```

不能拿不同 sender 的 timestamp 充當全域總序；若業務需要順序，receiver 分配 inbox seq。去重標記與業務提交要有復原協議，先標 processed 再做事會漏工作，反過來則可能重做。**daemon／tick 無新的 Actor 功能；S-10 的建立請求仍走 spawn，E-01 處理成本脈絡。**

## 9. AIOS／MemGPT：確有研究，但不是現成的 aos kernel 理論

### 9.1 AIOS

*AIOS: LLM Agent Operating System* 確實存在：2024-03 初稿，查到的 v5 為 2025-08，頁面標示 COLM 2025。它將 agent 的 LLM／工具／記憶體等請求放入服務層，實作 FIFO／RR，並研究文字式、logits 式 context snapshot／restore；它依賴傳統 OS，不是取代硬體 kernel。[Mei 等，AIOS 論文與版本紀錄](https://arxiv.org/abs/2403.16971)、[v5 §3 與附錄](https://arxiv.org/html/2403.16971v5)

**要改；服務層是同，context 中斷能力宣告是新補充。** 最值得借的是統一請求分類及可替換 LLM backend。論文把某些推論狀態保存後續做，不能推出每個商業 HTTP API 都支援廉價搶佔。文字接續可能是另一筆付費呼叫，不能等同恢復原生成器、同樣輸出或保留 KV cache；實際支援須查指定 backend。

kernel 讀服務能力卡與 ready 請求，寫 call grants；能力卡新增：

```json
{
  "schema": "aos.inference-capabilities.v1",
  "service_id": "model-a",
  "preemption": "between_requests_only",
  "continuation": "text_reprompt",
  "continuation_is_new_paid_attempt": true,
  "preserves_exact_generation_state": false,
  "cancel_ack_proves_no_more_billing": false,
  "context_snapshot_ref": "snapshots/review-17-v2.json"
}
```

預設非搶佔；有可查證的 backend 支援才改能力值。這比把所有 LLM 叫「CPU core」更能避免錯誤承諾。**daemon／tick 無新需求；context 管理器是普通任務，接續呼叫仍走 D-05。** 本報告不把 AIOS 實驗的加速比移植成 aos 預期效益。

### 9.2 MemGPT

*MemGPT: Towards LLMs as Operating Systems*（2023，2024 v2）提出 virtual context management：在有限上下文與外部儲存之間移動資訊，由模型協助管理控制流程，評估長文件與跨會話記憶。它不是多租戶資源隔離的 OS kernel，也不是恢復 GPU 推論暫存狀態的同義詞。[Packer 等，原論文](https://arxiv.org/abs/2310.08560)、[作者研究頁](https://research.memgpt.ai/)

**值得借分層 context；要改，部分同。** 舊報告 §7.3 已談 LRU／摘要；這裡補一個真正 agent 系統的對照：agent 可自己決定查什麼，kernel 只管 context 上限、整理成本與不能遺失的項目。LLM 自主管理不代表人類可讀性自動提升。

kernel 讀 context inventory 與驗收缺漏，寫 agent 的 `context-policy.json`；整理任務輸出 immutable manifest：

```json
{
  "schema": "aos.context-manifest.v1",
  "revision": 8,
  "model_tokenizer": "configured-backend-tokenizer",
  "input_budget_tokens": 6000,
  "pinned": ["goal", "open_commitments", "roster", "budget_status"],
  "working": ["summary:rev7", "evidence:latest"],
  "archive_alias": "memory",
  "summaries": [{"id": "summary:rev7", "sources": ["msg:1", "msg:2"]}],
  "compaction_charge_context": "cc-review-17",
  "on_pinned_overflow": "report_and_request_budget_or_reduce_scope"
}
```

pin 放不下不能無聲截掉目標；摘要要能追原文，整理所用 input/output 也記帳。量驗收問題答對率、查幾份檔、人工修正次數，不能只量省了多少 prompt token。**daemon／tick 無新需求；服務成本歸帳用 E-01。**

## 10. 專題：讓 agent 當排程器，哪種學術支撐最貼近？

**首選階層排程作骨架，feedback 作慢速調參，activations 作事件來源，market 作可選的偏好表達。** 這是根據前述研究做的 aos 設計判斷，不是任何論文已證明 LLM 排程優於規則。

| 研究方向 | 真正支撐什麼 | LLM 適合放哪裡 | 對 aos 的順位與限制 |
|---|---|---|---|
| CPU inheritance／HLS | 排程器可由一般執行實體實作，能階層組合、接受上層資源契約 | 專案內的政策任務，拿有限 envelope 再決定子工作 | **第一**；最貼近 S-16／S-20，能把錯誤影響限制在子域 |
| Feedback control | 依量測誤差調整輸入，分析延遲、飽和、穩定性 | 較慢地更新目標、類別與可調範圍；便宜控制器執行 | **第二**；LLM 不取代穩定性分析，避免多個慢回授互打 |
| Scheduler activations | 使用者層 scheduler 需要真實阻塞／容量事件 | 消費已摘要事件，必要時重訂政策 | **基礎配套**；支持接口分工，不直接支持 LLM 的決策品質 |
| Spawn／Tycoon | 用有限信用表達價值與分散資源競爭 | 估價、提出 bundle 或選擇值得做的工作 | **後做**；驗收難、投機與策略成本可能超過收益 |

在 aos 的具體擺法如下，讀寫都在掛載範圍內：

1. **根 kernel（確定性）**讀 `<B>/summary.json`、D-01 snapshot，寫 envelope 與短期 grant；每回合都能工作，不等待 LLM。
2. **專案 policy-agent**由 tick 啟動，只讀 `policy-input.json`、服務卡與 envelope，寫 `proposals/<id>.json`；它可以算 kernel 性質的 agent（S-16）。
3. **驗證／執行 kernel**讀 proposal，核對時鐘、版號、範圍、剩餘額度、最大等待，再轉成 spawn、daemon ctl 或服務 dispatch。未回、太慢、格式錯、越權，就沿用有效規則或保底。
4. **帳本／服務入口**在每次實際副作用前重新核對 grant、context、撤權世代，再記結果。LLM 的「我已經排完」不是事實來源。

政策提案宜給一段有限期間的**規則**，不只下一個名字：

```json
{
  "schema": "aos.agent-policy-proposal.v1",
  "proposal_id": "policy-a-9",
  "input_revision": 41,
  "envelope_id": "env-a-12",
  "validity": {"clock_node": "control", "epoch": "c-1", "until_round": 100},
  "choice": {
    "group_policy": "stride_inspired",
    "interactive_max_wait_rounds": 4,
    "dependency_donation": true,
    "max_calls_inflight": 2
  },
  "reason_code": "interactive_work_arrived",
  "why": "先處理阻擋回覆的檢索，其他工作維持長期份額",
  "evidence": ["ready:answer-9", "wait:retrieve-31"]
}
```

`interactive_max_wait_rounds` 是政策目標；若剩餘預算為零，要回報無法達成，不能為了滿足提案而越限。具體每回合的候選篩選由同一段可重播規則做。policy-agent 的 token、檔案查詢量與人類修正成本也納入其 envelope；不隱藏排程自己的成本。

評估 LLM 是否值得，不只問「排序像不像人」：比較**含排程成本的合格交付數、使用者等待、超限次數、人工補救次數**。如果 LLM 只重述 stride 的結果又多花一筆錢，就不用它。既有 `probes/llmkernel/README.md` 已記錄慢模型靠 `resume rounds` 才能控制回合、模型可能數錯輪次；本次借階層契約與持久狀態，正是針對這些具體問題。

## 11. 專題：token 的最佳模型與父子委派

**用 resource container 決定「算誰的」，用 capability 限制「誰能花多少」，用 MCS 啟發的 context 決定「這次代辦帶哪筆錢」。Lottery currency 管競爭份額；成本上界管單次風險。這些不是四選一。**

| 模型 | 它回答的問題 | 不回答什麼 | aos 用法 |
|---|---|---|---|
| Lottery ticket／currency | 有需求時，誰占多少相對服務份額？局部怎麼分票？ | 不是有限存款，不保證總支出上限 | 專案間公平、專案內自由分配；權重與金額分欄 |
| Resource container | 多個程序替同一工作消耗資源，帳歸哪裡？ | 本身不定義支用權交接與取消 | **帳本主體**：project／work／request，跨 tid 持續 |
| seL4 MCS donation | 服務替誰工作，如何帶著呼叫者執行額度？ | 原生是同步 CPU 預算，不是非同步 token 存款 | **委派語意**：同步獨占借用；非同步拆分 escrow |
| WCET 啟發成本界 | 這一段最多能消耗多少，超過怎麼辦？ | 不保證外部回應時間或任務成功 | 每次呼叫／工具／重試的可強制上界與停止條件 |

### 11.1 四個身分，不要塞進同一個 `node`

- `executor`：真正跑這次呼叫的 task／service。
- `work_id`／`container_id`：這次業務活動是什麼，可跨 restart／跨服務。
- `payer_account`：從哪個專案／擁有者扣實際 token、金額。
- `authority_id`／`charge_context`：此 executor 為什麼有權替此工作花這筆錢。

一個帳可支援多件工作，一個工作可委派多個 executor；不允許 executor 自報 payer 就直接扣款。不同模型的 token 分池，金額依模型／費率版號記整數最小單位。input、output、其他可計費 token 分類保存；同時保留 calls、inflight slots。**金額是成本、token 是消耗、slot 是可重用容量，可讀性是驗收品質**，不要全部加成一個餘額。

### 11.2 一筆父預算怎麼借、怎麼還

例：P 總額 10000 token，已花 3000、已有在途預留 1000，所以自由額度 6000。P 委派 2400 給 review 工作後，P 可再分配的只剩 3600；不是 review 多出 2400，P 還保有原先 6000。

review 要非同步開 S、R，帳本把這 2400 切成 1600、800。假設 S 最後用 1200、R 用 700，新增實支 1900，剩餘 500 回父可分配額度。此時整體為已花 4900、原在途 1000、自由 4100，總和仍是 10000。S／R 的花費已包含在父累計，不能再把父累計和子累計相加報成總花費。

必要不變量：

```text
根限額 = 根下唯一計數的已花額 + 未結保留額 + 未支用委派額 + 自由額度
子可支用權 ≤ 父已切出且未被別處占用的權力
同一 request 的最終結算只計一次；重試是另一個 attempt
同一保留額由 unspent → reserved → spent 轉移，不在兩欄同時計數
祖先統計是彙總視圖，不是另一筆可供花用的存款
```

有退款／調整時增加帶來源的新事件；不回頭刪掉歷史。上式範例假定沒有退款與增額，實際帳本要把這些資金流也列出。

**同步 loan：** 父持有權先轉入 transferred 狀態，再讓 server claim；父不可同時使用。回覆／確定未開始時交回剩額。**非同步 split：** 子 grant 各有獨立 ID 與上限，父保留其他餘額；不得複製同一 loan 給多個 worker。

帳本接收的委派請求〔提案，kernel 寫 request、帳本寫 receipt〕：

```json
{
  "schema": "aos.delegate-request.v1",
  "request_id": "delegate-review-17",
  "parent_context": "cc-project-a-job9",
  "mode": "split",
  "children": [
    {"context_id": "cc-review-17-s", "holder": "services/review", "tokens": 1600},
    {"context_id": "cc-review-17-r", "holder": "services/search", "tokens": 800}
  ],
  "expected_account_revision": 81,
  "expires_for_new_claims": {"clock_node": "control", "epoch": "c-1", "round": 100},
  "revoke_scope": "unclaimed_and_future_calls",
  "on_inflight_unknown": "retain_reservation"
}
```

D-11 的單一帳務交易核准整份 split：版號已變就重讀，不做半套；receipt 記錄各 context 與扣款事件。帳本可以是一個 tick 啟動的普通任務，提供 JSON inbox，不必變成 daemon 的大型子系統。只用本機合作程序也可先用鎖；不要把遠端共用檔案鎖當跨機器交易保證。

### 11.3 回合補額不等於新錢

seL4 SC 的 CPU 預算會按 period 補充，lottery 票能持續代表份額；token／美元的終身存款用完不會自動長回來。aos 應分成：

- **lifetime wallet**：真實終身支出上限，除非擁有者增額／可確認退款，不補回。
- **window allowance**：每 N 個父控制回合允許花多少，補充時仍受 lifetime wallet 限制。
- **share**：競爭時的相對份額；沒有需求不必把資源空留著。

parent 的 clock 決定補額；子 node pause 不停止父帳戶時鐘。control 本身停住則進入運行層 lease／保底問題（D-08），不能自行把 `at` 換算成假回合發錢。

## 12. 與 Linux 報告的差異：強化、補充與真正更正

| 舊結論／段落 | 本次結果 | 依據與實際改變 |
|---|---|---|
| §6：策略可換、執行端確定性驗證 | **強化** | Exokernel、微核心、CPU inheritance 都支持分工；LLM 不需特權常駐到 daemon |
| §3：父子額度、群組公平 | **強化＋補充** | currency 補「內部分票不放大外部分額」；MCS 補同步代辦／非同步 split 的權力轉移 |
| §2／§9：穩定 task identity、birth.group | **補充其不足** | resource containers 表明常駐服務每個 request 可替不同客戶工作；不能只在出生時指定單一 payer |
| §11：mount 是可見範圍，不是強隔離 | **強化＋擴展** | Plan 9 補「環境組合、別名與服務可替換」；object-capability 補受保護引用、縮限與撤權 |
| §5／§10：回合不是 CPU time slice、pause 不搶佔 | **強化** | RTOS／TTA 的保證有實體時間與執行上界前提；不能拿 token 直接替 WCET |
| §7.3：context 要 pin、摘要有成本 | **強化＋補充** | MemGPT 提供具體 agent 研究；Nemesis 要求整理／分頁成本也歸到受益工作 |
| §12.3：supervisor／重起 | **補充** | MINIX 是同類恢復；persistent OS 提醒多檔狀態、外部副作用與服務重接要有共同復原邊界 |
| §8：易用性／可讀性是軟目標 | **保留** | market 可表達偏好，不能證明可讀性是可交換資源；S-01 應用操作答對率驗 |
| §9.3：改定義要 kill＋keep；Q6 未決 | **推翻這段現況描述** | 現行 spec §6、infra-needs N-31 已有 `restart`＋`reload:true`，會查 tasks.json 同名項、驗證後重起並列 diff；無效時不 kill |
| D-18：啟動 enabled／not_before／restart_policy | **仍待補，不全撤銷** | `reload:true` 解決換定義，沒有一併實作可靠 supervisor 准入與退避 |
| 既有 spawn batch | **補充限制** | 同回合處理不是跨 node 原子 all-or-none；只有要成組准入時才新增 E-04 |

現況更正的直接格式是：

```json
{
  "op": "restart",
  "reload": true,
  "by": "control:kernel",
  "why": "重新載入 tasks.json 的同名執行定義"
}
```

寫到目標 `<taskdir>/ctl.json`，tick／tock 才執行；node pause 仍要等 resume。未加 reload 仍按 birth 定義重起；即使按 birth 的 inst 路徑，該檔內容若變過，也不是完整歷史執行快照。以上對照 [現行 spec §6](proto7-1/spec.md)、[infra-needs N-31](proto7-1/notes/infra-needs.md)。

**沒有研究推翻舊報告「先有可信帳與准入，才談排程算法」的主結論。** 真正的新設計重點是工作跨服務的脈絡、可組裝命名空間，以及階層 scheduler 的承諾界線。不能為了寫第二份就把同一個 watchdog 或公平權重換名字當新發現。

## 13. daemon／tick 的新增需求：只列 D 表沒有說清楚的新語意

先講界線：**三個實驗都能不改 daemon／tick 先做。** 新增 E 是未來要把合作協議升成可靠基底時的契約。帳本、服務卡、投標、feedback、評分器都可以是普通任務；不用搬進 daemon。

| 編號 | 等級 | 新增契約與最小責任 | 跟 D- 的關係／不是重列什麼 |
|---|---|---|---|
| **E-01** | **必要：可信代辦歸帳** | **逐請求綁定 charge context**：保存 caller、executor、work、payer、授權鏈；同一常駐服務可同時服務不同付款者。tick／runner 提供可信執行身分；gateway 在送出前驗 context，帳本做 split／loan／return，事件帶同一鏈 | D-03／06 有任務身分，D-05／11 有預留；新增的是「執行者不等於付款者、脈絡可交接」，不是再要求一遍扣帳 |
| **E-02** | **必要：可撤回的受限委派** | **權力衍生鏈與撤銷世代**：子權利只能縮小；撤祖先使未開始的後代 claim 失效。tick 的 spawn／mount 入口及付費 gateway 驗當前世代；保留在途結算，不把撤權當取消遠端 | D-09／19 有來源與授權檢查；新增的是衍生與撤銷的生命週期，尤其 restart 繼承的舊 mount／authority 不能復活 |
| **E-03** | **有更好：活任務換服務** | **命名空間的版本化重綁／卸綁**：tick 在邊界核准整份新 alias map，記 revision／回條；任務每次新操作固定一版。舊 request 留在舊服務收尾，不能因同名替換重送 | D-02／06／19 有 mount 回條、birth、權限；新增的是現行不支援的 replace／unmount 與整組視圖版本，不等於刪 symlink 就撤銷所有存取 |
| **E-04** | **有更好；聲稱群組原子准入時必要** | **cohort prepare／commit／abort**：共同 reservation、ready 回覆、唯一 commit epoch；未 commit 的工作不可起付費步驟。tick 可建立只等待的成員，gateway 驗 commit；若要連程序出生都 all-or-none，還需更強啟動協調，本報告不要求 | D-04／11 管單項原子領取；新增是跨成員的組合契約。D-02 去重與 `spawn batch` 都不提供此語意 |
| **E-05** | **有更好：可核對的工作復原** | **啟動綁定已提交 recovery manifest**：runner／tick 可驗 state／inst／namespace 版號存在且 commit 完整，birth 記 checkpoint id；不完整則拒絕或啟動 recovery inst。agent 查當前帳與外部未結請求後才續做 | D-17 是帳務 checkpoint、D-18 是重起政策；新增是多份業務狀態的共同發布點與啟動綁定，沒有承諾全機器透明持久化 |

E-01／02 的「必要」以**所有付費動作確實經受控入口**為前提。如果任務握有自己的 API key、任意網路與可改的帳本，只能報合作式保證，不能靠多兩個 JSON 欄位變成硬限制。這沿用舊報告的保證界線，沒有替核心規格追加一套未獲決定的權限部署方式。

**優先次序：E-01 → 視委派需求加入 E-02；E-03／04／05 等探針出現具體必要再做。** 即使 E-01 暫時只由 kernel＋服務閘門提供，也比讓 daemon 先理解各種模型價格有用。D-07／D-08 的控制面容量與保底仍是前提，這次不改列 E。

## 14. 最值得做的三個實驗

以下是**待做的探針設計，沒有實測結果**。每個空間用獨立 root，先建立 tasks／服務資料、最後建立 timeline；全部任務由 tick 啟動。利用現有 mounts、`spawn`、`resume rounds`、tock、ctl-done 與 status，**不改 daemon／tick**。未來要執行時才另外建立探針檔；本次沒有建立。

### 實驗一：同一 inst、兩套命名空間，驗證 S-01／S-23 的價值

**要驗證：** agent 是否真的能只看本地服務卡，換專案、換 mock backend、遇到服務重起時都不用改業務 inst；以及固定別名是否降低誤讀與操作成本。

**做法：**

1. 仿既有 `probes/llmkernel` 的讀檔／寫檔介面，準備同一份 reviewer inst 和六件固定工作。它只認 `mnt/mail`、`mnt/model`、`mnt/context`，所有請求用 §1.3 格式。
2. A、B 兩 node 掛不同 inbox／context 與 mock-model 客戶目錄；mock 服務回固定結果，記完整 request、來源與工作 ID，不花真 token。初始映射使用現有 tasks.json／spawn 的 `mounts`。
3. A 服務完成一部分後故障並重起，換 `instance_epoch`；未結 request 留存。為 A 的新 reviewer 寫新版 tasks.json mounts，再下 `restart reload:true`；新實例讀舊 checkpoint／回條，不盲目重送。B 繼續正常服務。
4. 增加一個同名 `lint.json` 來源衝突，讓 namespace manifest 明列 winner；再換不相容 `interface`，預期拒絕而不是猜格式。此步用生成視圖，不改 tick 做真正 union mount。
5. 做簡短盲讀：只給服務卡／manifest／回條，問「在哪送件」「誰付錢」「是否已完成」「故障後能否重送」「哪份工具生效」。與完整 node 路徑硬編碼版用相同題目比較。若用真 LLM 評讀，將其成本單獨列出；離線版先驗可重現的協議行為。

**成功門檻：** 兩個專案使用相同業務 inst，所有工作結果都歸對 inbox／container；重起後同 request 不產生第二次副作用；介面不合必有可讀拒絕；衝突來源可由 manifest 唯一判定。盲讀至少答對 4/5，且操作錯誤不高於硬編碼版；另報讀取檔案數、prompt token 與重綁所需控制步數，不捏造「一定比較省」。

**觀察檔：** birth.mounts、mount-done、namespace manifest、service receipts、ctl-done、decisions.jsonl。可用現有 Python audit 檢查誤寫，但它不涵蓋所有語言、不證明隔離。

**失敗能回答什麼：** 若只是別名少幾個字、仍需讀整棵 `.aos`，則服務卡粒度不對；若只在原服務在途請求切換時出錯，先做 request 路由／epoch，再考慮 E-03 熱重綁。

### 實驗二：父額度分給子工作，共享服務不漏帳、不重花

**要驗證：** resource container＋MCS 啟發的 split／loan，比現有每 task usage 相加能否正確表達代辦、並行扇出與故障復原。

**做法：**

1. 父工作 P 有 10000 合成 token；另有客戶 Q，獨立帳。兩者都用同一個長駐摘要／模型服務。服務每次處理 request 時記 `executor`、`payer`、`work_id`、`context_id`；不得只記 service node。
2. 帳本是 tick 起的 keep 任務，唯一寫入 ledger；kernel 透過其 request／receipt 檔申請委派。以 §11.2 的 3000 已花、1000 在途、2400 委派範例重播，並用獨立事件重算器核對總額。
3. 同時送出兩筆競爭最後剩額的請求；再把一個 grant 檔複製交給兩個 worker。只有帳本 claim 成功的一筆能呼叫 mock provider。試同步 loan 時父方同時 claim，必須被拒；試 split 時父子可用各自不重疊餘額。
4. 在 reserve 後、provider 已做完但 receipt 未寫、settle 已寫但 client 未讀三個切點注入崩潰；重送相同 request／event ID。mock provider 另有可查的已執行帳，不與帳本程序一起丟失。
5. 注入一筆「provider 是否執行未知」：不得釋放 reservation；到期、parent 退出、task 歸檔、控制 kernel restart 都不免帳。給 provider 確認後才結算／釋放；後來的 retry 用新 attempt ID。
6. Q 的請求穿插其中，驗 shared server 沒把 P 成本串到 Q。若做 capability 模擬，加一個撤銷 parent epoch 後重啟子任務的案例，舊 child grant 不可再次 claim。

**成功門檻：** 每一步皆滿足 §11.2 守恆式、可支用餘額非負；每次 mock provider 副作用只對應一筆最終帳，無重複／遺失；重播和摘要完全一致；未知在途持續占額；Q 的帳無 P 的事件。所有拒絕回條都能指出是額度、重複、撤權或未知保留。

**觀察檔：** delegation receipts、contexts、ledger events／summary、mock-provider execution ledger、birth.restart_of、tasks-old。多跑不同交錯 seed；結果報「合作式 mock 閘門可維持不變量」，不能外推為任意付費 API 已硬隔離。

**失敗能回答什麼：** 若只用 birth.group 就串帳，E-01 有直接證據；若同一 grant 多次 claim 成功，先修 D-11，不必改選人算法；若撤權後只因 restart 又活過來，才需要 E-02 衍生鏈 fencing。

### 實驗三：階層 scheduler 的慢策略、快執行，比直接 LLM 排程划算嗎？

**要驗證：** LLM 的價值是否在跨工作語意取捨，而不是機械數回合；固定 frame、依賴繼承、feedback 是否改善等待且不破壞公平／預算。

**做法：**

1. 延用 `probes/sched`／`probes/llmkernel` 結構：獨立控制 node、兩個專案、每專案三個合作式 worker。根 kernel 固定每專案權重與 envelope；worker 每筆開始前請求 grant。控制 node 不列入被測策略的 pause 範圍。
2. 建同一份可重播 trace：便宜互動工作、昂貴背景工作、急件 A 等低優先檢索 B、外部延遲突然變長、跨回合在途呼叫。用 mock provider 設定不同合成 token 成本；不要只令每 tock 加固定 5 token。
3. 比較四組：A＝確定性 stride 啟發版；B＝固定八回合發放窗口；C＝LLM 直接選下一份有界工作；D＝LLM 每 20 個控制回合或重大事件提出 §10 政策，確定性 kernel 每輪驗證／執行，並可用 §7.4 的受限 feedback 調並行。各組共用同一帳本、閘門與根額度，避免把保護差異誤算成算法收益。
4. 先用預錄／合成 proposal 測控制協議：讓提案晚三回合、壞 JSON、超父額、引用舊 epoch、要求 pause 自己。預期即時拒絕並走保底。此階段只能驗協議；要比較 LLM 決策品質，後續才接真 policy-agent、限總成本、記錄模型與設定。
5. 在 trace 中途將 P 子 worker 從 1 個增為 10 個，Q 不變；再插入急件依賴。比較 donation 開／關的等待時間，觀察子數量是否偷放大根份額。對固定 frame 組故意延遲某階段，記 carry／miss，不追發過期 grant。
6. 每組同一 trace 跑至少五次，保存 trace seed、policy revision、提案、接受／拒絕理由、mock 延遲與成本；slot 數與總金額固定。kernel restart 後讀回持久狀態繼續，不能讓 LLM 靠對話記輪次。

**成功門檻分兩層：**

- **基底通過：** 超額／越權／過期提案零次生效；保底在下一次正常控制決策機會接手；根額度不因多開子任務增加；禁止發新授權後，在途成本仍保留；控制線持續可觀察。token 用盡時可以拒絕全部付費工作，不算保底失敗。
- **政策值得保留：** 在基底全部通過後，D 相對 A 能改善預先選定的主要指標，例如互動等待 p95 降至少 20%，或相同總成本下合格交付數增加至少 10%；同時背景最久等待與人工錯誤不能明顯惡化。這是探針的採用門檻，不是文獻保證。若達不到，就保留 A，把 LLM 限於人工可讀的策略建議。

**要看什麼：** 實際 token／金額、calls、合格交付、各類 p50／p95 等待控制回合、另外記錄牆鐘等待、最久飢餓、grant 拒絕、frame miss、排程自身成本、讀檔量、人工修正。只在各專案都持續 ready 且未觸限制的區段比較長期份額；不能拿整段的 idle 時間說不公平。

**失敗能回答什麼：** D 與 A 相同但更貴，表示 LLM 暫無排程價值；D 被長推論卡住，表示政策／執行尚未真的分離；固定 frame 大量空窗但互動穩定，才評估是否要借出閒置窗口。只有需要「半組不能啟動」的實際工作出現，再把 E-04 加進下一輪探針。

## 15. 尚不能由這份調查確定的事

- **真實 provider 的可取消性、完整 token 上界、text continuation 成本：不確定。** 本次未指定供應商。AIOS 的機制與 mock 探針都不能代替其契約。
- **何種 scheduler 最省錢又好用：不確定。** 需上述相同工作 trace 與品質驗收；文獻只能幫忙拆問題，不能給 aos 的預設參數。
- **硬 capability 要用什麼 Linux 適配：仍待設計。** 不在本報告把合作式 mounts 變成已完成安全邊界；也不要求引入 CHERI 或重寫成 seL4。
- **全域回合、透明遷移、整機 persistent OS：不建議為本次目標加入。** 它們改變的基底與故障模型太多；穩定服務別名、工作 context、可提交的 checkpoint 已能先回答大部分實際需求。

可立即開工的 kernel 方向是：以 Plan 9 式服務卡與別名縮小 agent 看到的世界，以 resource container 固定工作帳，再讓受 envelope 約束的 kernel／policy-agent 自由選排程。daemon／tick 先維持現有程序與回合模型，用探針證明缺口後才增加 E 契約。
