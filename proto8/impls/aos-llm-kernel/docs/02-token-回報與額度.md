← [回入口 README.md](../README.md)｜段落：用法｜上一份：[01-用法](01-用法.md)｜下一份：[03-元素等](03-元素等.md)

### 跑一封（endpoint 函數）

（[thinking 11-05 kernel-daemon 03](../../../thinking/2026-11/05/kernel-daemon/03-問腦改掛daemon.md)：kernel 不自己跑，每封請 daemon 掛成一個問腦 proc、下一次收）

1. 查代號（信的 `body.endpoint`，沒寫用預設）→ 解那組的指示詞 → 那組有 `exec` 就用它、沒有用 kernel.json 的 `exec`；讀那組的 `slots`／`budget`／`speed`（壞了 `CfgBad`）；`request` 撞到釘死的（`fixed` 的 key、那組有 `model` 時的 `model`）＝`RequestBad`；kernel 看的四個鍵（`exec`、`slots`、`budget`、`speed`）拿掉。
2. 認領（`new/` → `cur/` 改名），在信的資料夾（`cur/<信件名稱>/`）寫 `request.json`＝`{"endpoint": 那組（指示詞已解、去掉那四個鍵）, "request": body.request}`。
3. 寄一封**掛信**進 daemon（`$AOS_KERNEL`，沒設＝`$AOS_DAEMON` 的 ctl 信箱）：
   `{"procs_added": {"llm_<信件名稱>": {"exec": {"argv": ["aos-exec", <exec 絕對路徑>], "cwd": "<信>", "stdin": "request.json", "stdout": "reply.json", "timeout_ms"?: kernel.json 的}, "max": 1, "stack": "<信>"}}}`。
   `max: 1` 的 loop 型 proc：跑一次就停、`state.json` 留下 `phase` 與結束碼；stderr 由 daemon 接到 `<信>/stderr.txt`。寄出後寫 `<信>/proc.json`＝`{"endpoint": 代號, "sender"?: 信封的 sender, "name", "exec", "mount_letter": 掛信的信件名稱, "mounted_at": epoch 秒, "retries": 重掛過幾次}`（`endpoint` 給「這包在飛幾封」與 `used.json` 的 `packs` 用，`sender` 同理給 `senders`；`request.json` 裡是解好的那組、沒有代號）；寄不進＝那封回 `LaunchFailed`。
   **endpoint 函數的環境＝daemon 給子項的**（`AOS_STACK`＝那封信的資料夾、`AOS_DAEMON`、daemon 的 `AOS_WS`、daemon 殼裡的其他變數），不是 kernel 的；金鑰已經解進 `request.json`。函數要別的變數（代理、憑證）＝寫進 daemon 的 `.env` 或函數自己的 `.env`。
4. **下一次收成品**（看 daemon 的表 `$AOS_DAEMON/procs_state.json` 與 `<信>/state.json`）：
   - 收尾、結束碼 0＝`reply.json` 讀得懂就原樣當回信；讀不懂＝`ReplyBad`。
   - 收尾、其他碼＝`EndpointFailed`，msg 帶 `reply.json` 的第一行（llm_http 失敗時 stdout 也印同一行），沒有就帶 `stderr.txt` 的第一行——**原樣**（C-52 明文例外：出口是給人看的回信原因；11-05 stdio-unify R10 代定：下層錯誤行的 `程式: error: ` 前綴不去掉，原因裡看得出是誰錯，例 `endpoint function exited with code 1: llm_http: error: 代號 原因`）。
   - 143（aos-exec 的 TERM）或 137（不理 TERM、寬限後 KILL）而且掛出去已經超過 `timeout_ms`＝`EndpointFailed` 逾時（11-05 edge-llm 補 137）。
   - 被收掉（沒逾時的 143、`stopped`）、死在半路（`state.json` 沒收尾、表上也沒這列）＝**重掛一次**（同名、新掛信、`retries` 變 1）；第二次還是這樣＝`EndpointFailed the brain call ran twice without a result (stopped or died midway)`。
   - 表上還有這列（`running`／`stopping`／`sleeping`）＝還在飛，佔一格。表上沒列、`state.json` 也沒有＝daemon 還沒套（暫停中、還沒輪到），照樣佔一格；daemon 的 `mailbox_warning` 提到這封掛信＝daemon 不收＝`LaunchFailed`。
   - 表上列著 `stopped` 而 `state.json` 收尾了＝照上面收，順手寄一封 `procs_removed` 把列拔掉。
   - 表上列著 `stopped` 而列上有 `reason`（11-05 晚：問腦 loop 退非 0——endpoint 退非 0、整個 loop 被打掉——daemon 不再下表、留 `stopped`＋原因；配合使用者裁 edge-agent 題 1「留表標 stopped (Recommended)」、edge-daemon 題 2「一起改成留表 (Recommended)」）＝**當收尾**：照上面看 `state.json` 的碼回信、寄 `procs_removed` 拔列；要重掛的（沒收尾、沒到時限的 143）先寄 `procs_removed`、`proc.json` 記 `"remount": true`，**等列拔了下一次才寄掛信**（同名 add 不會把 `stopped` 的拉起來；直接 `procs_started` 的話 daemon 還沒套信前，下一次會把舊列的 `reason` 當成第二次失敗）。`stopped` 而沒 `reason`、沒收尾＝有人下了 stop，照舊等（[04](04-已知限制.md)）。
5. 收到的寄回信、整封（`cur/<信>/`）刪掉，不留紀錄（11-04 夜使用者「舊信根本不用留，就是刪」）。`request.json` 裡有那組的金鑰，跟著整封刪（[04 #13](../../../thinking/2026-11/04/think-as-function/04-邊緣狀況.md)）。

endpoint 函數的契約（stdin `{"endpoint", "request"}` → stdout 一行 `{"message", "usage", "model"}`、退 0；錯退非 0、stderr 一行）是 [lib/base/llm_http、llm_fake](../../../lib/README.md) 定的，kernel 只看結束碼與 stdout 的形狀，不看內容（`message` 剪不剪是函數的事）。

### token 與額度

- **用量從回信拿**：回信的 `usage.total_tokens`（非負整數）就是這封的 token 數；沒有就 `prompt_tokens`＋`completion_tokens`；沒有 `usage`（含 error 回信）＝`counter_tokens` null、只算次數；`usage` 不是物件、數字不對＝`usage_bad: true`（也只算次數，照樣回信）。
- **算什麼**：掛出去過（`proc.json` 在）的信才算一次——`LetterBad`、`RequestBad`、`Endpoint{Missing,Unknown}`、`DeadlineBad`、`BudgetMissing`、第一次就寄不出掛信的 `LaunchFailed` 不算；`EndpointFailed`、`ReplyBad` 算（函數跑過、可能已經花了錢）。
- **額度**（kernel.json 的 `budget`，都選填）：`max_calls`、`max_tokens`＝每窗上限（非負整數；沒寫＝那一種不限）；`window`＝`"hour"`／`"day"`／`"all"`（沒寫＝`day`；窗的起點用 kernel 的本地時間〔`TZ`〕的整點／午夜，`all`＝不歸零）；
  `spent`＝到頂時排著的信怎麼辦：`"refuse"`（沒寫＝這個）回 `BudgetMissing`、不跑；`"wait"` 留在 `new/` 等下一窗。
- **每個寄件人的額度**（`budget.senders`，11-05 使用者「會想要限制特定aos proc所占用的資源。以及daemon/kernel自己本身被限制占用資源，並且會分配份額給proc」，[feat-proto 05 代定 4](../../../thinking/2026-11/05/feat-proto/05-資源份額.md)）：
  `{"senders": {"<寄件人>": {"max_calls": 50, "max_tokens": 200000}}}`——寄件人＝信封的 `sender`（aos-post／aos-llm 寫的身分：`$AOS_WS` ＞ `$AOS_STACK` ＞ `$AOS_CF` ＞ cwd 的絕對路徑；agent 就是它的工作區）。key 寫絕對路徑照用、相對的從 kernel 定義資料夾（kernel.json 所在）算、轉成絕對（兩個 key 算出同一個人＝`CfgBad`）。每格只認 `max_calls`、`max_tokens`（非負整數）；窗與 `spent` 用 kernel 的（這裡寫別的鍵＝`CfgBad`）。**沒列的寄件人不限**（只記帳）；信封沒有 `sender` 字串的信不認人、不擋也不記。
  寄件人 kernel **不驗**（10-15「濫用：先信任」）：寫得到信箱的人能冒用別人的身分，要真擋＝照 Linux 權限分帳號、分信箱（[04](04-已知限制.md)）。
  `budget` 沒寫也照樣記 `used.json`（窗＝day）：`{"window", "since", "counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens", "packs": {代號: {"counter_calls", "counter_tokens"}}, "senders": {寄件人: {"counter_calls", "counter_tokens"}}}`（`packs`＝這一窗每個包用了多少，代號從 `proc.json` 的 `endpoint` 拿；`senders`＝這一窗每個寄件人用了多少，從 `proc.json` 的 `sender` 拿、**有沒有列在 `budget.senders` 都記**；11-05 feat-proto）。換窗＝`window` 或 `since` 跟現在算出來的不同：`counter_calls`、`counter_tokens`、`packs`、`senders` 歸零，`counter_all_*` 照留。
- **到頂怎麼判**：要掛下一封之前看——`counter_calls`＋在飛的＋這次新掛的 ≥ `max_calls`，或 `counter_tokens` ≥ `max_tokens`。token 收到回信才知道，所以最多超過「在飛那幾封的量」。包的 `budget` 同一個判法、只數那包（`packs.<代號>` 與那包在飛的），寄件人的同理（`senders.<寄件人>` 與那人在飛的），窗跟 kernel 的同一個；kernel 的先判、再包、再寄件人。

### 一次

1. 建信箱三格；找 daemon（沒 `AOS_DAEMON`＝`DaemonMissing`、沒 ctl 信箱＝`MailboxMissing`，都退 1）；flock；`queue.json` 的 `counter_runs`＋1；讀 `used.json`（換窗了先歸零）、讀 daemon 的表；寫窗 `endpoints.json`（有變才寫）。
2. **收成品**：`cur/` 裡有 `proc.json` 的照上面「跑一封」第 4 步看，收尾的寄回信、刪掉，還在飛的記一格。沒有 `proc.json` 的：有讀得懂的 `reply.json`＝上一次寄到一半，照寄；都沒有＝認領了還沒掛就停了，改名回 `new/` 重排。
3. **收拾**（只看有 `sender.flock` 的信）：`tmp/` 裡寄信的人不在了的刪掉；`new/` 裡寄信的不在了的先改名回 `tmp/` 再刪（不白跑）。沒有 `sender.flock` 的一律不碰。
4. **看 `new/`**：`LetterBad`、`RequestBad`、`EndpointMissing`、`EndpointUnknown`、那組壞了（`DirectiveBad`、`CfgBad`）、deadline 已過（`DeadlineBad`）＝直接回信（都不佔格、不跑）。
5. **排隊**（11-05 使用者「讓kernel能根據信件中額外附送的priority之類資訊做排程」，[feat-proto 03](../../../thinking/2026-11/05/feat-proto/03-scheduling.md)）：`level`＋等了幾次÷10（每等 10 次升一級，不封頂）大的先 → deadline 近的先（有寫的在沒寫的前面）→ **那封的包的 `speed`**（`fast` → `normal` → `slow`）→ 等得久的先 → 先寄的先。
   同級、同 deadline 狀態下，慢包的信會被後寄的快包信超過（今天就有 priority 超車，aging 保底不會餓死）。
6. 掛之前看一眼訊號（有＝不認領、寫完 `queue.json` 以 128＋N 結束）。照排好的順序一封封看：
   - kernel 的額度到頂＝`refuse` 回 `BudgetMissing`、`wait` 就**停整列**；在飛＋這次新掛的到 kernel 的 `slots` 就停（其餘下一次）。
   - **包的額度**（那組的 `budget`）到頂（`packs.<代號>.counter_calls`＋這包在飛＋這次新掛的 ≥ `max_calls`、或 `counter_tokens` ≥ `max_tokens`）＝`refuse` 回 `BudgetMissing`（`endpoint once: max_calls 1 reached in this window (day); not run (no fallback: pick another endpoint name)`）；`wait` 時那封留在 `new/` 等、**別包照跑**。不替人降級換包（C-56；要換就寄信的自己改代號重寄）。
   - **寄件人的額度**（`budget.senders` 列了這封的信封 `sender`）到頂（`senders.<寄件人>.counter_calls`＋這人在飛＋這次新掛的 ≥ `max_calls`、或 `counter_tokens` ≥ `max_tokens`）＝同包的做法：`refuse` 回 `BudgetMissing`（`sender /home/me/ws_a: max_calls 1 reached in this window (day); not run`）；`wait` 時那封留在 `new/` 等、**別人照跑**。
   - **包的格**（那組的 `slots`）：這包在飛＋這次新掛的已到它的 `slots`＝**跳過、看下一封**（不是停下），讓別包的信補位。
   - 不然照「跑一封」1～3 步掛上去。
7. 寫 `queue.json`；結束碼 0。**不等問腦跑完**：一次只花看信、寄信的時間。

### 訊號

整支擋著 SIGINT／SIGTERM／SIGHUP。kernel 自己不跑子行程，沒有東西要轉；收到了就不再掛新的，寫完 `queue.json` 以 128＋N 結束（P-36）。已經掛出去的問腦 proc 歸 daemon 管：daemon 收工時它們被收掉、列留 `sleeping`，daemon 再起來自己醒、從頭跑一次，kernel 下一次照樣收。
