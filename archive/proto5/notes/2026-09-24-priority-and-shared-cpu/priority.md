# 題 1：讓某個 agent 最優先

← [本題 README](README.md)｜規範：[kernel 派工](../../spec/kernel/tick.md) 第 8 步、[帳本](../../spec/kernel/ledger.md)、[agent 送件](../../spec/aos-agent/send.md)、[proto5-2 派工](../../../proto5-2/spec/kernel-tick.md)

（astra 審查後改：必修 1～6、9 與建議 11～14 已併進來，見 [review-astra.md](review-astra.md)）

## 1. 現況（照規範與程式查的，沒跑）

- **派工沒有優先權，看的是 queue 順序。** kernel 帳本裡有一條 `queue`（行程名的陣列）。每一格第 8 步，kernel 逐顆看閒的 cpu（`req` 是 null），
  從 `queue` 頭找**第一個**「池相符、`not_before` 到了」的行程派給它（[`aos_kernel_engine.py`](../../lib/aos_kernel_engine.py) `dispatch()`）。
  所以是「同一池、時間到了的工作照 queue 順序拿」，不是全系統照送出時刻排。
- **誰排在前面**：新的 `add` 在收單那步接到 `queue` 尾；同一格收到好幾張單時照**檔名字典序**處理（agent 名也會影響先後）。
  反覆行程（agent 的 tick）每跑完一次就接回 `queue` 尾，所以 agent 之間是輪流——輪流拿到機會，不代表用到的 cpu 時間一樣。
- **cpu 那邊沒有工作的隊伍。** 正常運作時，kernel 只在 cpu 的 `req` 是 null 時才派，一顆工作 cpu 同時最多一件 kernel 派的工作還沒結清（ack／stop 這種控制單另計）。
  cpu 規範的「按檔名排序取第一份」對 kernel 管的工作 cpu 來說沒得選。**工作的隊伍只有 kernel 帳本那一條。**
- **llm cpu 是同步等模型的**：它跑 `aos-llm call`，打一次 HTTP、等模型回完才結束。一顆 llm cpu 同一時間只在等一個回答。
- **一個 agent 用到三種工作，走兩到三個池**：自己每一格（`tick.pool`，預設 `default`）、問模型（`llm.pool`，預設 `llm`）、
  跑工具（`tool_pool`，預設 `default`——**跟所有 agent 的 tick 搶同一池**）。三種都經過同一條 `queue`。
- 一個 agent 同時在途的工作最多是：**自己一格 tick，加上一批**（think 批只有一件；act 批有幾個 tool call 就幾件，**件數沒有上限**）。think 和 act 共用同一個 `batch`，不會同時在途。

### 一句話從 say 到模型回來（標出能插優先級的點）

```text
aos-agent say "…"            只寫 <amy>/input.json，不經 kernel
  ▼ [P1] kernel 派 agent-amy 的 tick → tick.pool 的閒 cpu（照 queue 順序＋not_before）
amy tick①：收輸入、改成 think，退出 → kernel 收回音時回 queue 尾，not_before＝收回當下＋interval_ms
  ▼ [P1]
amy tick②：建 think 批，往 K/requests/ 放 add --once pool=llm      [P2] 這張單可以帶 priority
  ▼ [P3] kernel 某一格收單 → 接到 queue 尾（同一格就可能派出去）
  ▼ [P4] kernel 派工：llm 池閒了，拿 queue 裡第一個 llm 行程       ← 真正決定「誰先問模型」的地方
llm cpu：aos-llm call，同步 HTTP                                   [P5] body 可帶 priority（llm.params 併進 body）
  ▼ [P6] 模型伺服器自己的排隊（LM Studio／LiteLLM／vLLM）
llm cpu 寫回音 → kernel 某一格收、寫 K/responses/
  ▼ [P1]
amy tick③：收回音、寫記憶；有 tool_calls 就把 state 切成 act，退出（這一格不送工具）
  ▼ [P1]
amy tick④：建 act 批，每個 call 一張 add --once pool=tool_pool     [P2][P4]（預設跟所有 tick 搶 default 池）
  ▼ …工具回來 → [P1] tick 收 → [P1] tick 再建 think 批 → [P4][P6] → 回話寫進記憶；say --wait 讀記憶看到
```

kernel 那段（收單、派工、收回音）以「格」為單位，預設約一秒一格；HTTP 與模型不是。沒人搶的時候延遲主要是格數，**優先級只在有人排隊時才有用**。
不改程式的另一個旋鈕是 amy 的 `tick.interval_ms`：`interval_ms` 從 kernel **收回音那一刻**起算，而同一格是先收回音再派工，
所以只有 `0` 能讓剛收回的 tick 當格再派；預設一秒一格時，`200` 跟 `1000` 通常一樣要等下一格。調成 0 的代價是 amy 閒著也每格被叫一次（空轉、讀檔、佔 cpu）。

## 2. 四種放法

(b)「交給 llm cpu 排」：在**現行「一顆 cpu 一次一件」的協定下**，llm cpu 看不到 kernel 還沒交給它的工作，沒得重排，所以不成立。
要成立得改成「集中接件的服務／代理佇列」，那是大改，而且只管得到模型、管不到工具。改寫成 (b')；另外多列 (d)。

| | (a) kernel 派工看 priority | (b') priority 交給模型伺服器 | (c) 高優先 agent 專屬池 | (d) cpu 可以服務多個池（有先後） |
|---|---|---|---|---|
| 做法 | `add` 多一欄 `priority`（整數，預設 0）；第 8 步從符合的行程裡挑 priority 最大的，一樣大照 queue 順序 | amy 的 `llm.params` 寫 `"priority": …`；`aos-llm call` 把 params 併進 HTTP body（只忽略 `model`／`messages`／`tools`／`stream`）；伺服器有優先權排程才有用 | K 的 info 多開池，amy 的池指過去 | cpu 的 `pool` 可以寫陣列 `["amy-llm", "llm"]`：先看第一個池有沒有工作，沒有才接第二個 |
| 改哪些檔 | 規範：kernel syscall.md、ledger.md、tick.md 第 8 步、cli-ops.md（`add --priority`）、cli-ls.md；agent info.md（新欄）、aos-agent send.md、register.md。程式：`aos_kernel_ledger.py` `_add`、`aos_kernel_engine.py` `dispatch`、`aos_kernel_cli.py`、`aos_agent_home.py`／`aos_agent_info.py`、`aos_agent_batch.py`、`aos_agent.py` start | 都不用改 | 都不用改（只改 JSON） | 規範：kernel home.md §1.1（pool 可為陣列、kernel 池仍只能單獨一顆）、tick.md 第 8 步、syscall.md（pool 合法性）、cli-ls.md、cli-ops.md（check）。程式：`aos_kernel_info.py`（現在直接拒絕陣列）、`aos_kernel_ledger.py` `_add`、`aos_kernel_engine.py` `dispatch`、`aos_kernel_check.py`、`aos_kernel_ls.py` |
| 大概多少 | **只算核心邏輯的粗估、沒驗證**：程式數十行＋測試；規範 8 個檔 | 0 | 0 | **粗估、沒驗證**：比 (a) 少，但不只派工那幾行（驗證、池存在性、顯示都要改） |
| 對別人公不公平 | 嚴格優先：高的永遠先拿 | 看伺服器 | 硬切：amy 用不到別池，別人也用不到 amy 閒著的 cpu | amy 的工作先；amy 沒事時她的 cpu 幫大家做 |
| 餓死 | **會，一個 VIP 就夠**：只要派工當下一直有可派的高優先工作，低的就一直等。例：default 池只有一顆、VIP 的 tick `interval_ms=0`，它閒著也每格退 101、每格被收回又立刻重新入選，普通工作永遠派不到。一批很多工具時也一樣。要解得加「等久了自動升級」（aging）或「每池留一顆不看 priority」 | 看伺服器 | 其他 agent 不會被 amy 餓死；**amy 自己的工作之間仍要排隊**（見下） | 其他池若**只剩**能借給它的 cpu，而高順位的工作一直有，一樣會餓死；一般池保留自己的 cpu 就不會 |
| amy 最壞等多久 | aos 這層：等一顆 cpu 做完手上那件（不搶佔） | — | 等自己池裡前面的工作做完 | amy 的 cpu 借出去時要等那件做完，**沒有統一上限**：工具可設 600000 ms 或 0（不限），tick 的工作預設也不限時，再加收回／派工的格延遲 |
| 真的「最優先」嗎 | 只在 aos 這層；模型伺服器那層還是先到先回 | 只在伺服器那層；aos 的 queue 照舊 | aos 這層不跟別的 agent 搶；伺服器那層還是會跟別的 llm cpu 同時打過去 | 同 (c)，但有借出去的延遲 |
| proto5-2 池式下 | 成立：每池的 `ready` 改成「每個優先級一條」，還要交代 `delayed` 到期後進哪一級；選取部分是 O(級數) | 成立（跟 kernel 無關） | 成立：宣告一個新池，後續由 kernel／daemon 建（見下） | 成立但要多定幾件事：cpu 做完回哪一池的 `free`、縮池怎麼算、一般池先用自己的 cpu |
| 改優先級要怎樣 | 行程政策 add 後不改：要 amy `stop` 再 `start`；在途的單照舊 | 改 `llm.params`；`aos-llm call` **執行當下**才讀，已排隊還沒跑的那問也會吃到新值 | 見下 | 改 K 的 info，下一格生效 |

### (c) 的使用者操作：「把 amy 設成最優先」（照規範應該可以，沒真跑）

先講清楚 (c) 給的是什麼：**amy 不跟其他 agent 搶 cpu**；不是「amy 什麼都不用排隊」。一顆 cpu 一次一件，amy 自己的 tick 和她同一批的好幾個工具，
在同一池裡還是一件一件來；長工具跑著時她的 tick 也進不去。所以 tick 跟工具最好也分開池：

1. 編 `K/info.json` 的 `cpus`（寫成 `.tmp` 再 rename，免得 tick 讀到半份），加三顆，名字要沒用過（`K/cpus/<名>/` 不在、daemon 孩子表也沒有這個名字——不然舊家的 inst 不會被覆寫、或跟別的 K 撞名 `NameTaken`）：
   `"amy-llm": {"pool": "amy-llm", "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}}`、`"amy-tick": {"pool": "amy-tick"}`、`"amy-tool": {"pool": "amy-tool"}`。
   `envs` 只在第一次建家時抄進 `K/cpus/<名>/inst.json`；PATH、金鑰照舊是從 daemon 的環境繼承。工具多就把 `amy-tool` 開成幾顆（`amy-tool-1`…同池）。
2. 不用重 boot：kernel 每格重讀 info，下一格就叫 daemon 拉（[kernel home.md §1.1](../../spec/kernel/home.md)「改 info 之後」）。`aos-kernel ls` 看到它們活了、再往下。
3. 編 `amy/info.json`：`"llm": {…, "pool": "amy-llm"}`、`"tool_pool": "amy-tool"`、`"tick": {"pool": "amy-tick", "interval_ms": 0}`。
   `llm.pool`、`tool_pool` 在 amy **送件那一刻**才讀，所以下一批就生效（一批送到一半崩了、恢復時還沒送的那幾件也會用新池）。
   `tick.pool`／`interval_ms` 是登記時寫進 kernel 的：`aos-agent stop`、等那格跑完（`aos-kernel ls` 看不到 `agent-amy`），再 `aos-agent start`。
   不 stop 直接 start 會印 `already started`，但池和 interval **不會換**。stop 不會取消已經送出的那批，它們照跑、start 之後再收。
4. 兩個小洞：`aos-kernel check`／`--probe` 的模型設定檢查**只看名字剛好叫 `llm` 的池**；而且所有 llm 池的模型代號被合成一張表，
   `aos-agent check` 拿這張表對 amy 的模型代號——`amy-llm` 的 `AOS_LLM_CONFIG` 設錯不會被抓到，兩份 llm.json 不同時也可能誤判通過（檢查都在 [`aos_kernel_check.py`](../../lib/aos_kernel_check.py)）。

proto5-2 下第 1、2 步換成 `aos-kernel cpu add --pool amy-llm --count 1 --env AOS_LLM_CONFIG=/abs/llm.json`（新池才能帶 `--env`，既有池不能這樣改環境）。
這是**宣告**：kernel 送 scale 單、daemon 回成功後那些號才可以派，cpu 真正起來又要再等 daemon 慢慢拉。

## 3. 其他漏看的便宜做法（astra 補）

- **全體 agent 的 tick 與工具分池**（零程式）：例如所有 agent 的 `tool_pool` 指到 `tools` 池。長工具再也擋不到任何人的 tick；不是優先級，但常常就是「覺得慢」的原因。
- **一小組 VIP 共用一個池**：跟 (c) 一樣，只是幾個 agent 一起指過去。
- 只把真的擠的那一種資源隔開（例如只給 amy 專屬 llm 池，tick／工具照舊）。

## 4. 建議

**先用 (c)，不改程式。** 理由：
- 使用者要的是「amy 的 llm／tool 都最先」。(c) 讓 amy 的三種工作都**不跟別的 agent 搶**；(a) 若只給 llm 加 priority，amy 的 tick 還是卡在 default 池排隊——優先權倒置。
- 零程式、零規範改動，其他 agent 不會被 amy 餓死；proto5-2 下也一樣能做。
- 代價是 amy 那幾顆閒著時是浪費。會在意再做 (d)：只動 kernel、不動 agent 與帳本形狀；要保住「一般工作一定前進」，一般池得留著自己的 cpu。
- (a) 最貴（kernel＋agent 兩邊、8 份規範），而且一個 VIP 就可能餓死別人，一定要配 aging 或保留名額；等「很多 agent、分好幾級」的需求真的出現再做。
- 不管選哪個，**模型伺服器是最後一個隊伍**。amy 的請求跟別人的一起打到伺服器，還是伺服器說了算。
  伺服器支援優先權排程的話疊 (b') 是零成本（例如 vLLM、LiteLLM 好像有 priority 參數——**我沒查證，要看端點文件**）。

**最小版**：(c) 的四步寫進教程 05 當一節「讓某個 agent 最優先」（只改文件）；順手修 check：
模型表**按池**保留、agent 照自己的 `llm.pool` 查那一池的模型、不再強制一定要有叫 `llm` 的池（`aos_kernel_check.py`＋kernel cli-ops.md、aos-agent cli-check.md 各一句）。
注意 `--probe` 通過只代表端點連得上（常常只打 `GET /models`），不代表 amy 帶著她的 params／工具去問一定會過。
