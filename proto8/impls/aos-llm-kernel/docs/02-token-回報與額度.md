← [回入口 README.md](../README.md)｜段落：用法｜上一份：[01-用法](01-用法.md)｜下一份：[03-元素等](03-元素等.md)

### 跑一封（endpoint 函數）

（[thinking 11-05 kernel-daemon 03](../../../thinking/2026-11/05/kernel-daemon/03-問腦改掛daemon.md)：kernel 不自己跑，每封請 daemon 掛成一個問腦 proc、下一次收）

1. 查代號（信的 `body.endpoint`，沒寫用預設）→ 解那組的指示詞 → 那組有 `exec` 就用它、沒有用 kernel.json 的 `exec`；讀那組的 `slots`／`budget`／`speed`（壞了 `CfgBad`）；`request` 撞到釘死的（`fixed` 的 key、那組有 `model` 時的 `model`）＝`RequestBad`；kernel 看的五個鍵（`exec`、`slots`、`budget`、`speed`、`backend`）拿掉。
2. 認領（`new/` → `cur/` 改名），在信的資料夾（`cur/<信件名稱>/`）寫 `request.json`＝`{"endpoint": 那組（指示詞已解、去掉那五個鍵）, "request": body.request, "priority": {"level", "deadline"?}}`（級數與推得期限見 [01 契約](01-用法.md)）。
3. 寄一封**掛信**進 daemon（`$AOS_KERNEL`，沒設＝`$AOS_DAEMON` 的 ctl 信箱）：
   `{"procs_added": {"llm_<信件名稱>": {"exec": {"argv": ["aos-exec", <exec 絕對路徑>], "cwd": "<信>", "stdin": "request.json", "stdout": "reply.json", "timeout_ms"?: kernel.json 的}, "max": 1, "stack": "<信>"}}}`。
   `max: 1` 的 loop 型 proc：跑一次就停、`state.json` 留下 `phase` 與結束碼；stderr 由 daemon 接到 `<信>/stderr.txt`。寄出後寫 `<信>/proc.json`＝`{"endpoint": 代號, "sender"?: 信封的 sender, "name", "exec", "mount_letter": 掛信的信件名稱, "seen_at": queue.seen_at_ms / 1000（抄不到＝null）, "mounted_at": epoch 秒, "retries": 重掛過幾次}`（`endpoint` 給「這包在飛幾封」與 `used.json` 的 `packs` 用，`sender` 同理給 `senders`；`request.json` 裡是解好的那組、沒有代號）；寄不進＝那封回 `LaunchFailed`。
   **endpoint 函數的環境＝daemon 給子項的**（`AOS_STACK`＝那封信的資料夾、`AOS_DAEMON`、daemon 的 `AOS_WS`、daemon 殼裡的其他變數），不是 kernel 轉交的；金鑰由端點小定義的 `--key-env NAME` 指定，小 proc 自己讀環境，不進 `request.json`。金鑰與跨樹 hub 由 root 殼 export，不寫定義的 `.env`；其他環境設定照 [N-67](../../../docs/NORMS/10-基礎設施-定義與工作區/09-N-67.md) ⑦⑧⑨。
4. **下一次收成品**（看 daemon 的表 `$AOS_DAEMON/procs_state.json` 與 `<信>/state.json`）：
   - 收尾、結束碼 0＝`reply.json` 成功物件拿掉 `child` 後當回信，`child` 原值進 ledger；讀不懂或是錯誤物件＝`ReplyBad`。
   - 先判逾時；收尾、非零且 stdout 整份為單行 JSON、頂層只有 `error`、`error.code` 與 `error.msg` 都為字串＝整份原樣回（error 內多的鍵保留）。其餘其他碼＝`EndpointFailed`，msg 帶 `reply.json` 的第一行（llm_http 失敗時 stdout 也印同一行），沒有就帶 `stderr.txt` 的第一行——**原樣**（C-52 明文例外：出口是給人看的回信原因；11-05 stdio-unify R10 代定：下層錯誤行的 `程式: error: ` 前綴不去掉，原因裡看得出是誰錯，例 `endpoint function exited with code 1: llm_http: error: 代號 原因`）。
   - 143（aos-exec 的 TERM）或 137（不理 TERM、寬限後 KILL）而且掛出去已經超過 `timeout_ms`＝`EndpointFailed` 逾時（11-05 edge-llm 補 137）。
   - 被收掉（沒逾時且沒有合格 error 的 143、`stopped`）、死在半路（`state.json` 沒收尾、表上也沒這列）＝**重掛一次**（同名、新掛信、`retries` 變 1；沿用首次 `request.json` 與 `seen_at`，期限不重算）；第二次還是這樣＝`EndpointFailed the brain call ran twice without a result (stopped or died midway)`。
   - 表上還有這列（`running`／`stopping`／`sleeping`）＝還在飛，佔一格。表上沒列、`state.json` 也沒有＝daemon 還沒套（暫停中、還沒輪到），照樣佔一格；daemon 的 `mailbox_warning` 提到這封掛信＝daemon 不收＝`LaunchFailed`。
   - 表上列著 `stopped` 而 `state.json` 收尾了＝照上面收，順手寄一封 `procs_removed` 把列拔掉。
   - 表上列著 `stopped` 而列上有 `reason`（11-05 晚：問腦 loop 退非 0——endpoint 退非 0、整個 loop 被打掉——daemon 不再下表、留 `stopped`＋原因；配合使用者裁 edge-agent 題 1「留表標 stopped (Recommended)」、edge-daemon 題 2「一起改成留表 (Recommended)」）＝**當收尾**：照上面看 `state.json` 的碼回信、寄 `procs_removed` 拔列；要重掛的（沒收尾、沒到時限的 143）先寄 `procs_removed`、`proc.json` 記 `"remount": true`，**等列拔了下一次才寄掛信**（同名 add 不會把 `stopped` 的拉起來；直接 `procs_started` 的話 daemon 還沒套信前，下一次會把舊列的 `reason` 當成第二次失敗）。`stopped` 而沒 `reason`、沒收尾＝有人下了 stop，照舊等（[04](04-已知限制.md)）。
5. 收到的寄回信、跑過的信追加逐封帳 `ledger.jsonl`，整封（`cur/<信>/`）刪掉，不留請求原文（11-04 夜使用者「舊信根本不用留，就是刪」）。金鑰只活在端點小 proc 的環境與記憶體裡，信資料夾不存金鑰。

endpoint 函數的契約（stdin `{"endpoint", "request", "priority"}` → stdout 一行 `{"message", "usage"?, "model"?, "child"?}`、退 0；錯退非 0、stderr 一行）是 [lib/base/llm_http、llm_fake](../../../lib/README.md) 定的，kernel 只看結束碼與 stdout 的形狀，不看內容（`message` 剪不剪是函數的事）。

### token 與額度

- **用量從回信拿**：回信的 `usage.total_tokens`（非負整數）就是這封的 token 數；沒有就 `prompt_tokens`＋`completion_tokens`；沒有 `usage`（含 error 回信）＝token 增量記 0、只算次數；`usage` 不是物件、數字不對＝token 增量也記 0（只算次數，照樣回信）。
- **逐封帳**：只有掛過的信才在 `Server::finish` 往本層 stack 的 `ledger.jsonl` 追加一行 JSON，欄位順序如下。錯誤也記；沒掛過的不記。重掛的 `mounted_at` 是最後一次掛上時間，`seen_at` 保留第一次；耗時包含最後一次掛上到 kernel 收尾的等待，牆鐘倒退記 0。寫入失敗只印英文 warning，回信、總帳與刪信照常。

  | 欄位（照寫入順序） | 內容 |
  |---|---|
  | `id` | 原請求信名 |
  | `endpoint` | proc 記的能力包代號，缺＝null |
  | `sender` | proc 原值，不改成用量帳的相對路徑，缺＝null |
  | `model` | 回覆原值，缺＝null |
  | `seen_at` | proc 抄下的首次看到時間，UTC epoch 秒，缺＝null |
  | `mounted_at` | 最後一次掛上時間，UTC epoch 秒，缺＝null |
  | `finished_at` | 收尾時間，UTC epoch 秒 |
  | `elapsed_ms` | 非負整數毫秒，沒有 mounted_at＝null |
  | `usage` | 回覆原樣，缺＝null |
  | `code` | 成功＝null；失敗＝回給寄件人的 error.code 字串 |
  | `child` | 成功 stdout 的 child 原樣，缺＝null；回信拿掉此鍵 |
  | `switched` | 從 proc 抄；有 backend 時首次掛上或換包的第一封為 true，其餘 false；重掛沿用第一次 |

  這是追加的觀測帳，kernel 不輪替；人或審視者清理。中斷或重收可能留下半行、缺行或重複行；讀者跳過壞行，用 `id` 去重。各層都記 usage，加總只加一層；全鏈只加沒有 `child` 的葉子行，避免重算。（11-07 使用者裁定：翻 11-05 的 served.jsonl「也刪」，ledger 留；見 [kernel-nest](../../../thinking/2026-11/07/kernel-nest/README.md)）
- **算什麼**：掛出去過（`proc.json` 在）的信才算一次——`LetterBad`、`RequestBad`、`Endpoint{Missing,Unknown}`、`DeadlineBad`、`BudgetMissing`、第一次就寄不出掛信的 `LaunchFailed` 不算；`EndpointFailed`、`ReplyBad` 算（函數跑過、可能已經花了錢）。
- **額度**（kernel.json 的 `budget`，都選填）：`max_calls`、`max_tokens`＝每窗上限（非負整數；沒寫＝那一種不限）；`window`＝`"hour"`／`"day"`／`"all"`（沒寫＝`day`；窗的起點用 kernel 的本地時間〔`TZ`〕的整點／午夜，`all`＝不歸零）；
  `spent`＝到頂時排著的信怎麼辦：`"refuse"`（沒寫＝這個）回 `BudgetMissing`、不跑；`"wait"` 留在 `new/` 等下一窗。
- **每個寄件人的額度**（`budget.senders`，11-05 使用者「會想要限制特定aos proc所占用的資源。以及daemon/kernel自己本身被限制占用資源，並且會分配份額給proc」，[feat-proto 05 代定 4](../../../thinking/2026-11/05/feat-proto/05-資源份額.md)）：
  `{"senders": {"<寄件人>": {"max_calls": 50, "max_tokens": 200000}}}`——寄件人＝信封的 `sender`（aos-post／aos-llm 寫的身分：`$AOS_WS` ＞ `$AOS_STACK` ＞ `$AOS_CF` ＞ cwd 的絕對路徑；agent 就是它的工作區）。key 寫相對路徑時先從 kernel 定義資料夾（kernel.json 所在）算位置，寫絕對路徑也可；兩邊都整理路徑後，轉成**相對 kernel stack** 的 key（stack 外的寄件人用 `../` 開頭，兩個 key 算出同一個人＝`CfgBad`）。信封的絕對 `sender` 也轉成同一種 key 才比對；kernel、定義與寄件人整包 `cp -a` 搬家，相對位置相同就沿用同一格帳。每格只認 `max_calls`、`max_tokens`（非負整數）；窗與 `spent` 用 kernel 的（這裡寫別的鍵＝`CfgBad`）。**沒列的寄件人不限**（只記帳）；信封沒有 `sender` 字串的信不認人、不擋也不記。
  寄件人 kernel **不驗**（10-15「濫用：先信任」）：寫得到信箱的人能冒用別人的身分，要真擋＝照 Linux 權限分帳號、分信箱（[04](04-已知限制.md)）。
  `budget` 沒寫也照樣記 `used.json`（窗＝day）：`{"window", "since", "counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens", "packs": {代號: {"counter_calls", "counter_tokens"}}, "senders": {寄件人: {"counter_calls", "counter_tokens"}}}`（`packs`＝這一窗每個包用了多少，代號從 `proc.json` 的 `endpoint` 拿；`senders`＝這一窗每個寄件人用了多少，從 `proc.json` 的 `sender` 拿、整理成相對 kernel stack 的 key，**有沒有列在 `budget.senders` 都記**；11-05 feat-proto）。換窗＝`window` 或 `since` 跟現在算出來的不同：`counter_calls`、`counter_tokens`、`packs`、`senders` 歸零，`counter_all_*` 照留。
- **到頂怎麼判**：要掛下一封之前看——`counter_calls`＋在飛的＋這次新掛的 ≥ `max_calls`，或 `counter_tokens` ≥ `max_tokens`。token 收到回信才知道，所以最多超過「在飛那幾封的量」。包的 `budget` 同一個判法、只數那包（`packs.<代號>` 與那包在飛的），寄件人的同理（`senders.<寄件人>` 與那人在飛的），窗跟 kernel 的同一個；kernel 的先判、再包、再寄件人。

### 一次

1. 建信箱三格；找 daemon（沒 `AOS_DAEMON`＝`DaemonMissing`、沒 ctl 信箱＝`MailboxMissing`，都退 1）；flock；給了 `--enable-counters` 才把 `counter_kernel_runs.txt`＋1（壞＝`CounterBad`）；讀 `used.json`（換窗了先歸零）、讀 daemon 的表；寫窗 `endpoints.json`（有變才寫）。
2. **收成品**：`cur/` 裡有 `proc.json` 的照上面「跑一封」第 4 步看，收尾的寄回信、刪掉，還在飛的記一格。沒有 `proc.json` 的：有讀得懂的 `reply.json`＝上一次寄到一半，照寄；都沒有＝認領了還沒掛就停了，改名回 `new/` 重排。
3. **收拾**（只看有 `sender.flock` 的信）：`tmp/` 裡寄信的人不在了的刪掉；`new/` 裡寄信的不在了的先改名回 `tmp/` 再刪（不白跑）。沒有 `sender.flock` 的一律不碰。
4. **看 `new/`**：`LetterBad`、`RequestBad`、`EndpointMissing`、`EndpointUnknown`、那組壞了（`DirectiveBad`、`CfgBad`）、deadline 已過（`DeadlineBad`）＝直接回信（都不佔格、不跑）。
5. **排隊**（11-05 使用者「讓kernel能根據信件中額外附送的priority之類資訊做排程」，[feat-proto 03](../../../thinking/2026-11/05/feat-proto/03-scheduling.md)）：`level`＋`waited_ticks / aging_ticks`（整數除法；每 `aging_ticks` 格升一級，預設 3，不封頂）大的先 → deadline 近的先（有寫的在沒寫的前面）→ 同一 backend 的信黏著最後掛的包 → **那封的包的 `speed`**（`fast` → `normal` → `slow`）→ 等得久的先 → 先寄的先。
   `waited_ticks`：kernel 有時鐘而這封信也有 `seen_at_ticks`，用現在 tick 減那一格；否則用 `(現在 UTC epoch 毫秒 − seen_at_ms) / AOS_TICK_INTERVAL`（預設 1000 毫秒），負的當 0。「等得久」也比同一個值。同一輪掃描只各讀一次 tick 與牆鐘。時鐘凍住，已有 tick 記錄的信就不升級；沒有時鐘時凍住再醒仍會計入牆鐘經過的時間。
   跨樹信的 `priority.deadline` 仍是牆鐘（帶時區 ISO 8601 或 epoch 秒；N-65 ③），kernel 不讀信裡任何 tick 欄。
   不搶位、不保留格；要保證 high 不等＝短 deadline 或多開一包。
   同級、同 deadline 狀態下，慢包的信會被後寄的快包信超過（今天就有 priority 超車，aging 保底不會餓死）。
6. 掛之前看一眼訊號（有＝不認領、寫完 `queue.json` 以 128＋N 結束）。照排好的順序一封封看：
   - kernel 的額度到頂＝`refuse` 回 `BudgetMissing`、`wait` 就**停整列**；在飛＋這次新掛的到 kernel 的 `slots` 就停（其餘下一次）。
   - **包的額度**（那組的 `budget`）到頂（`packs.<代號>.counter_calls`＋這包在飛＋這次新掛的 ≥ `max_calls`、或 `counter_tokens` ≥ `max_tokens`）＝`refuse` 回 `BudgetMissing`（`endpoint once: max_calls 1 reached in this window (day); not run (no fallback: pick another endpoint name)`）；`wait` 時那封留在 `new/` 等、**別包照跑**。不替人降級換包（C-56；要換就寄信的自己改代號重寄）。
   - **寄件人的額度**（`budget.senders` 列了這封的信封 `sender`）到頂（`senders.<寄件人>.counter_calls`＋這人在飛＋這次新掛的 ≥ `max_calls`、或 `counter_tokens` ≥ `max_tokens`）＝同包的做法：`refuse` 回 `BudgetMissing`（`sender /home/me/ws_a: max_calls 1 reached in this window (day); not run`）；`wait` 時那封留在 `new/` 等、**別人照跑**。
   - **包的格**（那組的 `slots`）：這包在飛＋這次新掛的已到它的 `slots`＝**跳過、看下一封**（不是停下），讓別包的信補位。
   - 不然照「跑一封」1～3 步掛上去。
7. 寫 `queue.json`（內容跟原來一樣就不寫）；結束碼 0。**不等問腦跑完**：一次只花看信、寄信的時間。

### 訊號

整支擋著 SIGINT／SIGTERM／SIGHUP。kernel 自己不跑子行程，沒有東西要轉；收到了就不再掛新的，寫完 `queue.json` 以 128＋N 結束（P-36）。已經掛出去的問腦 proc 歸 daemon 管：daemon 收工時它們被收掉、列留 `sleeping`，daemon 再起來自己醒、從頭跑一次，kernel 下一次照樣收。
