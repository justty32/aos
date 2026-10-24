# aos-kernel-llm

`aos-kernel-llm - 從信箱挑最該跑的信、跑、回信，一次一輪`（NAME，C-54 R1）

**一句話：`aos-kernel-llm [旗標] kernel.json`——LLM kernel 跑一次：看信箱 `new/` 裡排隊的信（每封是一張「問腦」的單子），照優先度挑最該跑的幾封（`slots`），跑完把結果寫成回信，然後結束。**
要它一直顧著，就讓 aos-loop 或 aos-daemon 一次次拍它（C-47：kernel＝以 inst／loop／daemon 為基礎、管某張單子跑不跑的一張單子）。寄信的一方是 [aos-gate](../aos-gate/README.md)。
一個 lib（`lib/libaos-kernel-llm.a`，公開標頭 `aos/kernel_llm.hpp`：信箱與信的格式，aos-gate 也用）加一支薄命令列（`bin/aos-kernel-llm`）。連 [aos-loop](../aos-loop/README.md) 的公開 API（擋訊號、`resolve_keys`；它又帶進 aos-exec 的 `run_inst`）。全家慣例見 [impls/README.md](../README.md)。

像醫院掛號櫃台只叫號一次：候診室（`new/`）每張掛號單寫著要看什麼、急不急；叫號的人看一眼，急的先、時限近的先、等很久的先、其餘先來先看，一次叫幾個（診間數＝`slots`），看完把結果放進取件櫃（`done/`），這一輪就下班。
病人中途走掉（閘門被收掉）就把他的單子抽掉；上一輪的醫生昏倒、診間裡還有人（`cur/`）——還在看的讓他看完，沒人在看又沒結果的，回一張「沒看完」（`RunFailed`），不重看。

```sh
cat kernel.json
# {"mailbox": {"$env": "AOS_KERNEL"}, "slots": 1}
cat loop.json
# {"exec": {"argv": ["aos-kernel-llm", "kernel.json"]}, "interval_ms": 300}
AOS_STACK=st/ AOS_KERNEL=$PWD/mb aos-loop loop.json &    # kernel 一直顧著信箱 mb/
AOS_KERNEL=$PWD/mb aos-gate brain.json                    # 寄一封、等回信、結果原樣交回（見 aos-gate）
cat st/served.jsonl   # {"at": "...", "letter": "0179...", "level": "high", "waited_runs": 0, "code": 0, "signal": null, "error": null, "elapsed_ms": 1085, …, "tokens": 43, "report_bad": false}
cat st/used.json      # {"window": "day", "since": "2026-10-24T00:00:00+08:00", "calls": 3, "tokens": 129, "all_calls": 3, "all_tokens": 129}
```

設計與決定見 [thinking 2026-10-24 LLM kernel](../../thinking/2026-10-24-llm-kernel.md)；排序規則是 [10-15 LLM kernel 稿](../../thinking/2026-10-15-llm-kernel.md) 已定的六條；規範 [N-42](../../NORMS/09-kernel.md)、信箱 [N-16](../../NORMS/05-基礎設施-窗.md)。

## 用法

```
aos-kernel-llm [旗標] kernel.json
```

- **命令列**：唯一的位置參數＝設定檔（可寫 `檔#/指標`，aos-util 的 `load_cfg`）；目前沒有旗標（不認得＝`FlagUnknown`、沒給或多給＝`ArgumentsBad`）。
- **kernel.json**：`mailbox`（信箱資料夾；相對的從 `$AOS_STACK` 算——N-14 窗落在 `$AOS_STACK` 底下；沒寫＝`mailbox`）、`slots`（同時跑幾封，正整數；沒寫＝1）、`budget`（額度，見下「token 回報與額度」；沒寫＝不限、只記帳）、`accept`（只跑哪幾張單子，見下「accept」；沒寫＝什麼都收）；其他 key 忽略（`_entry`…）。
  這四格的指示詞先解（`{"$env": "AOS_KERNEL"}` 就是讓 kernel 與閘門讀同一個變數）；解不開 `DirectiveBad`。
- **`$AOS_STACK`**（必要）：kernel 自己的兩個檔——
  - `queue.json`：`{"runs": kernel 跑過幾次, "seen_at_runs": {信號: 第一次看到它是第幾次}}`（只留還在排的；先寫暫存再改名）。在但讀不懂＝`QueueBad`（刪掉就從頭算）。
  - `served.jsonl`：每封信一行 `{"at", "letter", "level", "waited_runs", "code", "signal", "error", "elapsed_ms", "time_ms", "metainfo_bad", "tokens", "report_bad"}`（只附加）；跑了＝`code`／`signal`，沒跑或跑不起來＝`error` 是代號；
    `elapsed_ms`＝實際花多久、`time_ms`＝單子 `_metainfo` 宣告的（沒寫＝null）——宣告與實測放一起，kernel 絕不回寫使用者的 `_metainfo`（10-24 metainfo M7）；`metainfo_bad`＝寫壞而當沒寫的 key；
    `tokens`＝腦回報的 token 數（沒回報、回報壞、沒跑＝null）、`report_bad`＝回報檔在但讀不懂（10-24 下午加）。
  - `used.json`：用量帳 `{"window", "since", "calls", "tokens", "all_calls", "all_tokens"}`——這一窗（`since` 起）跑了幾封、多少 token，與開帳以來的總數；每封跑過的信寫完 served 那行就記一次（先寫暫存再改名）。在但讀不懂＝`UsedBad`（刪掉就從 0 算）。
- **信箱**（N-16 資料夾式）：`tmp/`、`new/`、`cur/`、`done/` 四格，一封信＝一個資料夾 `<信號>/`；kernel 每次先建好四格（建不了 `MkdirFailed`），`.lock` 用 flock 鎖住整次（另一個 kernel 鎖著＝`LockFailed`）。
  信號＝`<UTC 奈秒 20 位>.<閘門 pid>.<閘門 started_at_ticks>`：字典序＝寄的先後，名字就看得出寄信的閘門還在不在（pid＋啟動時間，N-15、N-17）。
- **信**（`letter.json`）：`{"inst": 單子, "env": 寄信那一刻閘門的整份環境, "priority": 原樣}`。**priority**（10-15 稿）：沒寫＝normal；`"low"`／`"normal"`／`"high"`；數字看正負；
  物件 `{"level", "deadline", 其他 key 照帶不管}`；`deadline`＝帶時區的 ISO 8601 或 epoch 秒（沒時區不猜＝壞）。
  **`_metainfo`**（10-24，被叫者自報的特性，[thinking 10-24 metainfo § 5](../../thinking/2026-10-24-metainfo/02-誰讀與kernel接法.md#5-給-llm-kernel-實作者的接法)）：只讀信裡單子的 `_metainfo` 的 `time_ms`、`llm_tokens`（數字，或 `{"val", "max"}` 取 `val`；非負數才算）；
  形狀不對＝那個 key 當沒寫、記進 served 的 `metainfo_bad`，**照樣跑、不回 `LetterBad`**（M8）。`llm_tokens` 這版只讀不用（留給額度）。不讀單子以外的檔（資料夾的 `_metainfo`、子葉）。
  排隊依據都從 `priority_of` 一個函式讀（priority＋`_metainfo`）。
- **回信**（`reply.json`）：`{"code", "signal"}` 或 `{"error": {"code", "msg"}}`。

### token 回報與額度（10-24 下午，[thinking § token 回報與額度](../../thinking/2026-10-24-llm-kernel.md#token-回報與額度10-24-下午)）

- **回報**：kernel 跑每封信時，在信裡帶來的環境上**加一個** `AOS_KERNEL_REPORT`＝這封信小格裡的 `cur/<信號>/report.json`（信裡原本有同名的也蓋掉）。腦願意就把 API 回覆的 `usage` 物件**原樣**寫進去（先寫 `.report.json` 再改名）；
  kernel 跑完讀它：`total_tokens`（非負整數）就是這封的 token 數；沒有 `total_tokens` 就 `prompt_tokens`＋`completion_tokens`；檔不在＝沒回報（`tokens` null，只算次數）；讀不懂、不是物件、數字不對＝`report_bad: true`（也只算次數，照樣交回信）。
  一封信問了好幾次腦，由腦自己加總再寫（kernel 只讀最後那份）。範本 [agent-dan 的 brain.py](../../demo/agent-dan/brain.py) 與 demo 的 agent-ivy 有寫（P-23 註）。
- **算什麼**：子行程起來過（`runner.json` 在）的信才算一次、才讀回報——`LetterBad`、`DeadlineMissed`、`BudgetMissing` 不算；kernel 死了、下一次回 `RunFailed` 的那封算（腦可能已經花了錢）。
- **額度**（kernel.json 的 `budget`，都選填）：`calls`、`tokens`＝每窗上限（非負整數；沒寫＝那一種不限）；`window`＝`"hour"`／`"day"`／`"all"`（沒寫＝`day`，10-15 定「一天一期歸零」；窗的起點用 kernel 的本地時間〔`TZ`〕的整點／午夜，`all`＝不歸零）；
  `spent`＝到頂時排著的信怎麼辦：`"refuse"`（沒寫＝這個，10-15「見底就擋」）回 `BudgetMissing`、不跑；`"wait"` 留在 `new/` 等下一窗（閘門一直等，由包它那格的 `timeout_ms` 守）。
  `budget` 沒寫也照樣記 `used.json`（窗＝day）。換窗＝`used.json` 的 `window` 或 `since` 跟現在算出來的不同：`calls`、`tokens` 歸零，`all_*` 照留。
- **到頂怎麼判**：要開下一封之前看——`calls` 已用＋這次已開的＋上一次留下還在跑的 ≥ 上限，或 `tokens` 已用 ≥ 上限。token 只能跑完才知道，所以一次裡最多超過「那一次所有封的量」（`slots` 1 時＝最後一封）。

### accept：只跑名單裡的單子（10-24，堵沙箱信箱後門，[thinking sandbox S14](../../thinking/2026-10-24-sandbox.md)）

kernel 在沙箱外、照信跑任何單子；關在 [aos-sandbox](../../sandbox/README.md) 裡的程式寄得到信（`kernel: true`）時，就能叫它跑「`cat 判準`」。要擋就寫 `accept`：

```json
{"mailbox": {"$env": "AOS_KERNEL"}, "accept": [{"argv": ["python3", "/abs/agent/brain.py"], "cwd": "/abs/agent"}]}
```

- 每張＝`{"argv": 非空字串陣列, "cwd": 字串}`（`cwd` 相對的從 kernel.json 的資料夾算）。信裡單子的 `argv` 與 `cwd` 要跟其中一張**一字不差**，而且不能自帶 `envs`、`stdin`、`stdout`、`stderr`、`stdout_append`、`stderr_append`；不合＝回 `InstUnknown`、不跑、不算次數。
- **環境不整份換**：用 kernel 自己的，只疊上信裡 `AOS_` 開頭的（`AOS_WS`、`AOS_STACK`…）——寄信的改不了 `PATH`、`LD_PRELOAD`、`PYTHONPATH`；`AOS_BRAIN_KEY` 信裡沒有就用 kernel 這邊的（key 可以只放在 kernel 外面）。
- 名單裡的 `argv` 要指沙箱寫不到的程式（絕對路徑）：`["python3", "brain.py"]` 配上沙箱寫得到的 `cwd`，等於還是讓它跑自己寫的檔。
- 沒寫 `accept`＝照舊什麼都收、環境整份照信（閘門透明，C-20）。

### 一次

1. 建信箱四格、flock；`queue.json` 的 `runs`＋1。
2. **`cur/` 還有信**＝上一次 kernel 跑到一半死了（一次跑完才結束、又有鎖，正常時這裡是空的）：有 `reply.json` 就照它；跑信的子行程（`runner.json`）還活著＝讓它跑完、這次少一格；都不是＝回 `RunFailed`（10-15 六題 6「回錯」，不重跑）。有回信的寫一行 served、搬 `done/`。
3. **收拾**：`tmp/`、`done/` 裡寄信的閘門不在了的刪掉；`new/` 裡寄信的不在了的先改名回 `tmp/` 再刪（不白跑；跟閘門撤信同一招，不會跟認領撞）。
4. **看 `new/`**：信讀不懂、`inst` 不是物件、priority 壞＝回 `LetterBad`；有 `accept` 而單子不在名單裡＝回 `InstUnknown`；deadline 已過＝回 `DeadlineMissed`（都不佔格、不跑）。
5. **排隊**（`used.json` 先讀進來、換窗了先歸零）：`level`＋等了幾次÷10（每等 10 次升一級，不封頂）大的先 → deadline 近的先（有寫的在沒寫的前面）→ `_metainfo` 宣告的 `time_ms` 短的先（有寫的在沒寫的前面；10-24，從不蓋過 level 與 deadline，aging 照舊所以插隊有上限）→ 等得久的先 → 先寄的先。
6. 跑之前看一眼訊號（有＝不認領、直接 128＋N）。照排好的順序一封封看：**額度到頂**＝`spent` 是 `refuse` 就把這封（以及之後的每一封）回 `BudgetMissing`，是 `wait` 就停、剩下的留著；沒到頂、`slots` 也還有空就認領（`new/` → `cur/` 改名；改不成＝閘門剛撤信，換下一封），**每封 fork 一個子行程**（`run_runner`）：
   先寫 `runner.json`，環境整份換成信裡的 `env`（再加 `AOS_KERNEL_REPORT`），單子沒寫 `stdout`／`stderr`＝寫進信的 `stdout.txt`／`stderr.txt`、沒寫 `stdin`＝`/dev/null`，交給 aos-exec 的 `run_inst`（`timeout_ms`、`grace_ms`、整群收都照單子），結果寫 `reply.json`。
7. **全部跑完才往下**（一次裡不補位）：每封讀回報、寫一行 served、記進 `used.json`、`cur/` → `done/`；寫 `queue.json`；結束碼 0。

### 訊號

整支擋著 SIGINT／SIGTERM／SIGHUP。跑信的期間收到就轉給每個子行程（它們的 `run_inst` 再轉給單子的整群），等全部結束、回信照寫，再以 128＋N 結束（P-36）。閘門那邊拿到的就是單子被停掉的碼（例 143）。

## 元素

```
 main ──▶ block_signals ──▶ parse_cli ──▶ 要 AOS_STACK ──▶ read_cfg ──▶ serve：lock → read_used → recover → sweep → scan → order → （spent？回錯／停）認領＋fork run_runner → wait_runners → finish（read_report、add_used）→ write_queue
```

| 檔 | 做什麼 |
|---|---|
| `include/aos/kernel_llm.hpp` | 公開：信箱四格（`Mailbox`）、信號（`letter_id`、`sender_alive`）、`parse_priority`／`priority_of`（priority＋`_metainfo` 的 `time_ms`、`llm_tokens`）／`level_name`、`read_reply`、全部代號（閘門也用） |
| `src/letter/letter.cpp` | 上面那些的實作（ISO 8601 自己解：`YYYY-MM-DDTHH:MM:SS[.小數](Z|±HH:MM)`） |
| `src/queue/queue.hpp`、`queue.cpp` | `queue.json` 讀寫、`waited_runs`、`effective`、`order` |
| `src/serve/serve.hpp`、`serve.cpp` | `read_cfg`、`serve`（`Server`：鎖、收拾、看信、額度到頂就回錯或停、認領、fork 子行程跑〔設 `AOS_KERNEL_REPORT`〕、等、回信、served.jsonl） |
| `src/budget/budget.hpp`、`budget.cpp` | token 回報與額度：`parse_budget`、`window_since`、`read_used`／`add_used`（`used.json`、換窗歸零）、`spent`、`read_report` |
| `src/common/common.hpp` | `using` |
| `src/main.cpp` | 命令列：串上面；出錯印「aos-kernel-llm: 代號 原因」 |

## 為什麼這樣做

- **一次跑完才結束、不常駐**：kernel 跟 fsm 一樣是被拍的一張單子（C-47、C-38「它只是一個排程」），節奏、暫停、收工交給 loop／daemon 的 ctl／state。代價：`slots` 大於 1 時，一次裡先跑完的那格要等最慢的那封才空出來（見已知限制）。
- **每封 fork 一個子行程**：`run_inst` 一次只跑一張、會卡住，要同時跑幾封就各開一個行程；子行程裡才能把環境整份換成寄信那一刻的（`run_inst` 讀 `environ`），kernel 本身的環境不動。
- **環境帶寄信那一刻的整份**：閘門是透明的（C-20：agent 不知道有 kernel），單子在 kernel 這邊跑跟在原地直接跑要一樣——`brain.py` 要的 `AOS_STACK`、`AOS_WS`、`AOS_BRAIN_*` 都在。
- **信箱用改名認領、flock 擋第二個 kernel**：N-14 原子性只靠 rename、mkdir、flock 三種。閘門撤信也是改名（`new/` → `tmp/`），跟 kernel 認領（`new/` → `cur/`）只有一個改得成。

## 錯誤代號

自己出錯：stderr 一行 **`aos-kernel-llm: 代號 原因`**、退 1（N-60）。**一封信的錯不是 kernel 的錯**：寫進那封的回信，閘門印成它自己的一行。

| 代號 | 誰 | 什麼時候 |
|---|---|---|
| `ArgumentsBad`、`FlagUnknown`（共用） | kernel | 沒給／多給設定檔、不認得的旗標 |
| `StackMissing`（共用） | kernel | 沒設 `AOS_STACK` |
| `CfgMissing`、`CfgBad`、`DirectiveBad`（共用） | kernel | kernel.json 不在、指不到；不是物件、`mailbox` 不是非空字串、`slots` 不是正整數、`budget` 形狀不對；指示詞解不開 |
| `MkdirFailed`、`WriteFailed`（共用） | kernel | 信箱四格建不了；`queue.json`、`served.jsonl`、回信寫不了、改名不了 |
| `LockFailed` | kernel | 信箱被另一個 kernel 鎖著 |
| `QueueBad` | kernel | `queue.json` 在但讀不懂 |
| `UsedBad` | kernel | `used.json` 在但讀不懂 |
| `LetterBad` | 回信 | `letter.json` 讀不懂、`inst` 不是物件、`env` 不是物件、priority 壞 |
| `DeadlineMissed` | 回信 | 輪到之前時限已過，沒跑（10-15 稿定的名字；C-54 R10 四種結尾套不上，照原名） |
| `InstUnknown` | 回信 | kernel.json 寫了 `accept`，這張單子不在名單裡（或自帶 `envs`、串流），沒跑（10-24） |
| `BudgetMissing` | 回信 | 這一窗的額度用完了（`spent` 是 `refuse`），沒跑（10-15 稿叫 `BudgetExhausted`，照 C-54 R10 四種結尾改名） |
| `RunFailed` | 回信 | 上一次 kernel 跑到一半死了、沒回信；跑信的子行程沒寫回信就結束了 |
| `EntryBad`、`DirectiveBad`、`LaunchFailed`、`Internal` | 回信 | 單子跑不起來（同 aos-exec 跑單子；原因開頭「單子跑不起來：」） |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`，unittest 39 案，約 3 秒）：A 命令列與設定（usage、`StackMissing`、設定壞、mailbox 預設在 stack、指示詞、`QueueBad`）；B 排隊（level／數字／deadline 字串與數字／先來先上／`waited_runs`、aging 到了與還沒到、`seen_at_runs` 只留還在排的）；
  C slots（2 封一起跑、1 封串著）；D 回信（碼與 stdout／stderr、單子自己導 stdout 不蓋、`DeadlineMissed` 不跑、`LetterBad` 七種、單子壞＝回信不是 kernel 的錯）；
  E 收拾（寄信人不在的 new／tmp／done、cur/ 留下的回 `RunFailed` 或照現成回信、跑信的子行程還活著就讓它跑完並佔格、子行程死了＝`RunFailed`）；F 鎖、環境與 cwd 照信、`timeout_ms`、SIGTERM 轉給單子、早到的訊號不留半套；G `_metainfo`（同級時宣告短的後寄也先跑、有寫的在沒寫的前面、level 與 deadline 照樣壓過它、三種寫壞照樣跑並記 `metainfo_bad`）；
  H token 回報與額度（`AOS_KERNEL_REPORT` 指進信小格並蓋掉信裡的、回報有寫／只有 prompt＋completion／沒寫／三種寫壞、沒跑的不算、`calls` 到頂回 `BudgetMissing`、`tokens` 到頂排著的全回錯、`wait` 留著等換窗後跑、`all` 不歸零與改窗歸零、`budget` 與 `used.json` 壞）；I accept（名單裡的才跑、`cat` 祕密檔與換了 `cwd`、自帶 `stdout`、`envs` 的回 `InstUnknown`，環境用 kernel 的 `PATH` 與 key、只疊信裡的 `AOS_*`；`accept` 寫壞＝`CfgBad`）。
  信是測試自己寫的（假裝閘門；pid 用測試自己＝寄信的人還在）。改掉排序、過期檢查、收拾、runner 檢查、slots、`_metainfo` 那層比較任一處都會紅（10-24 實測）；拿掉設 `AOS_KERNEL_REPORT`、讀回報、到頂判斷、`wait`、換窗歸零、「跑過才算」任一處 H 段都會紅（10-24 下午實測）。
- gate＋kernel＋loop／daemon 一起跑的在 `proto8/tests/test_kernel_llm.py`（10 案；含 agent-dan 的 brain.py 經閘門、kernel 跑、假 server 回 usage → served 記到 token）。

## 已知限制

- **token 靠腦自願回報**：腦沒寫（或寫錯）就只算次數，`tokens` 額度看不到它；回報的數字 kernel 不驗（腦說幾個就是幾個）。單子裡的工具、子行程也看得到 `AOS_KERNEL_REPORT`，誰最後寫算誰的。
- **token 額度事後才知道**：跑之前不知道這封會吃多少，所以會超過一點（見上「到頂怎麼判」）；`_metainfo.llm_tokens` 的預先擋沒做（只讀不用）。
- **窗用本地時間**：kernel 的 `TZ` 換了、或日光節約，`since` 會變＝當成換窗歸零一次。`wait` 配 `window: "all"`＝到頂後永遠等（直到有人改 kernel.json 或刪 `used.json`）。
- 一次裡不補位：`slots` 2、一封 1 秒一封 10 秒，那一格空等 9 秒；新來的高優先信也要等這一次結束。
- kernel 整群被 SIGKILL：跑信的子行程跟著死，但單子自成行程群組、可能還在跑；下一次回 `RunFailed`，單子實際跑了一半或跑完沒人收。
- 回信放在 `done/` 等閘門來拿；閘門還活著卻一直不拿（不會發生，除非有人 SIGSTOP 它）就一直佔著。
- 信裡帶整份環境（含 `AOS_BRAIN_KEY` 這種），信箱在誰都讀得到的地方就會外洩：信箱放自己的 stack 裡。
- **寄信的人是誰 kernel 不驗**：信號只是 pid＋啟動時間，寫得到信箱的程式很容易冒充一個還活著的行程；擋任意單子只能靠 `accept`。關在 aos-sandbox 裡（有自己的行程編號）的閘門反過來：它的 pid 在外面對不上，kernel 當寄信的人不在、把信丟掉——沙箱裡的 agent 現在用不了 kernel（[thinking sandbox S15](../../thinking/2026-10-24-sandbox.md)）。
- **共用信箱看得到別人的信**：寫得到信箱就讀得到別封信（含整份環境）與回信；沙箱裡的 agent 要用 kernel，信箱與 kernel 都該是它專用的一份。
- 沒有每個寄件人的配額（10-15「濫用：先信任」）；`class` 不看；`_metainfo` 宣告錯（說 1 秒跑 1 小時）不處罰，只記在 served 裡（只有單子的 `timeout_ms` 收得掉它）。
