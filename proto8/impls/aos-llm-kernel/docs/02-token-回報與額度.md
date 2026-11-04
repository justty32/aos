← [回入口 README.md](../README.md)｜段落：用法｜上一份：[01-用法](01-用法.md)｜下一份：[03-元素等](03-元素等.md)

### token 回報與額度（[thinking § token 回報與額度](../../../thinking/2026-10/24/llm-kernel/README.md#token-回報與額度10-24-下午)）

- **回報**：kernel 跑每封信時，在信裡帶來的環境上**加一個** `AOS_KERNEL_REPORT`＝這封信小格裡的 `cur/<信件名稱>/report.json`（信裡原本有同名的也蓋掉）。腦願意就把 API 回覆的 `usage` 物件**原樣**寫進去（先寫 `.report.json` 再改名）；
  kernel 跑完讀它：`total_tokens`（非負整數）就是這封的 token 數；沒有 `total_tokens` 就 `prompt_tokens`＋`completion_tokens`；檔不在＝沒回報（`counter_tokens` null，只算次數）；讀不懂、不是物件、數字不對＝`report_bad: true`（也只算次數，照樣交回信）。
  一封信問了好幾次腦，由腦自己加總再寫（kernel 只讀最後那份）。範本 [agent-eve 的 brain.py](../../../tests/fixtures/agent-eve/brain.py)（11-04 前在 demo/）有寫（P-23 註）。
- **算什麼**：子行程起來過（`runner.json` 在）的信才算一次、才讀回報——`LetterBad`、`DeadlineMissed`、`BudgetMissing` 不算；kernel 死了、下一次回 `RunFailed` 的那封算（腦可能已經花了錢）。
- **額度**（kernel.json 的 `budget`，都選填）：`max_calls`、`max_tokens`＝每窗上限（非負整數；沒寫＝那一種不限；上限一律 `max_*`，寫 `calls`、`tokens`＝`CfgBad`，免得以為有上限）；`window`＝`"hour"`／`"day"`／`"all"`（沒寫＝`day`，10-15 定「一天一期歸零」；窗的起點用 kernel 的本地時間〔`TZ`〕的整點／午夜，`all`＝不歸零）；
  `spent`＝到頂時排著的信怎麼辦：`"refuse"`（沒寫＝這個，10-15「見底就擋」）回 `BudgetMissing`、不跑；`"wait"` 留在 `new/` 等下一窗（閘門一直等，由包它那格的 `timeout_ms` 守）。
  `budget` 沒寫也照樣記 `used.json`（窗＝day）。換窗＝`used.json` 的 `window` 或 `since` 跟現在算出來的不同：`counter_calls`、`counter_tokens` 歸零，`counter_all_*` 照留。
- **到頂怎麼判**：要開下一封之前看——`counter_calls`（已用）＋這次已開的＋上一次留下還在跑的 ≥ `max_calls`，或 `counter_tokens`（已用）≥ `max_tokens`。token 只能跑完才知道，所以一次裡最多超過「那一次所有封的量」（`slots` 1 時＝最後一封）。

### accept：只跑名單裡的單子（堵沙箱信箱後門，[thinking sandbox S14](../../../thinking/2026-10/24/sandbox/README.md)）

kernel 在沙箱外、用自己的身分照信跑任何單子；關在 [aos-sandbox](../../../extras/sandbox/README.md) 裡的程式寄得到信（設定把信箱綁進來）時，就能叫它跑「`cat 判準`」。誰寄得進信箱由 Linux 權限管（[sandbox/root/setup.sh](../../../extras/sandbox/root/setup.sh) `--mailbox`），寄進來之後替它跑什麼 Linux 管不到，現在只能靠 `accept`（跟「存取控制純靠 Linux」衝突、暫留，[thinking sandbox S18](../../../thinking/2026-10/24/sandbox/README.md)）：

```json
{"mailbox": {"$env": "AOS_KERNEL"}, "accept": [{"argv": ["python3", "/abs/agent/brain.py"], "cwd": "/abs/agent"}]}
```

- 每張＝`{"argv": 非空字串陣列, "cwd": 字串}`（`cwd` 相對的從 kernel.json 的資料夾算）。信裡單子的 `argv` 與 `cwd` 要跟其中一張**一字不差**，而且不能自帶 `envs`、`stdin`、`stdout`、`stderr`、`stdout_append`、`stderr_append`；不合＝回 `InstUnknown`、不跑、不算次數。
- **環境不整份換**：用 kernel 自己的，只疊上信裡 `AOS_` 開頭的（`AOS_WS`、`AOS_STACK`…）——寄信的改不了 `PATH`、`LD_PRELOAD`、`PYTHONPATH`；`AOS_BRAIN_KEY` 信裡沒有就用 kernel 這邊的（key 可以只放在 kernel 外面）。
- 名單裡的 `argv` 要指沙箱寫不到的程式（絕對路徑）：`["python3", "brain.py"]` 配上沙箱寫得到的 `cwd`，等於還是讓它跑自己寫的檔。
- 沒寫 `accept`＝什麼都收、環境整份照信（閘門透明，C-20）。

### 一次

1. 建信箱四格、flock；`queue.json` 的 `counter_runs`＋1。
2. **`cur/` 還有信**＝上一次 kernel 跑到一半死了（一次跑完才結束、又有鎖，正常時這裡是空的）：有 `reply.json` 就照它；跑信的子行程（`runner.json`）還活著＝讓它跑完、這次少一格；都不是＝回 `RunFailed`（10-15 六題 6「回錯」，不重跑）。有回信的寫一行 served、搬 `done/`。
3. **收拾**：`tmp/`、`done/` 裡寄信的閘門不在了（`sender.flock` 沒人鎖）的刪掉（`done/` 的先撤回它寄過、還沒人拿的回信）；`new/` 裡寄信的不在了的先改名回 `tmp/` 再刪（不白跑；跟閘門撤信同一招，不會跟認領撞）。
4. **看 `new/`**：信讀不懂、`inst` 不是物件、priority 壞＝回 `LetterBad`；有 `accept` 而單子不在名單裡＝回 `InstUnknown`；deadline 已過＝回 `DeadlineMissed`（都不佔格、不跑）。
5. **排隊**（`used.json` 先讀進來、換窗了先歸零）：`level`＋等了幾次÷10（每等 10 次升一級，不封頂）大的先 → deadline 近的先（有寫的在沒寫的前面）→ `_metainfo` 宣告的 `time_ms` 短的先（有寫的在沒寫的前面；從不蓋過 level 與 deadline，aging 照算所以插隊有上限）→ 等得久的先 → 先寄的先。
6. 跑之前看一眼訊號（有＝不認領、直接 128＋N）。照排好的順序一封封看：**額度到頂**＝`spent` 是 `refuse` 就把這封（以及之後的每一封）回 `BudgetMissing`，是 `wait` 就停、剩下的留著；沒到頂、`slots` 也還有空就認領（`new/` → `cur/` 改名；改不成＝閘門剛撤信，換下一封），**每封 fork 一個子行程**（`run_runner`）：
   先寫 `runner.json`，環境整份換成信裡的 `env`（再加 `AOS_KERNEL_REPORT`），單子沒寫 `stdout`／`stderr`＝寫進信的 `stdout.txt`／`stderr.txt`、沒寫 `stdin`＝`/dev/null`，交給 aos-exec 的 `run_inst`（`timeout_ms`、`grace_ms`、整群收都照單子），結果寫 `reply.json`。
7. **全部跑完才往下**（一次裡不補位）：每封讀回報、有 `reply_to` 就寄回信、寫一行 served、記進 `used.json`、`cur/` → `done/`；寫 `queue.json`；結束碼 0。

### 訊號

整支擋著 SIGINT／SIGTERM／SIGHUP。跑信的期間收到就轉給每個子行程（它們的 `run_inst` 再轉給單子的整群），等全部結束、回信照寫，再以 128＋N 結束（P-36）。閘門那邊拿到的就是單子被停掉的碼（例 143）。
