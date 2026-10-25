← [入口](../proto8.md)｜涵蓋：`proto8/impls/` 的 LLM kernel 兩支（aos-kernel-llm、aos-gate，10-24）

> 2026-10-24 新做時另開一份（[01-impls與舊lib](01-impls與舊lib.md) 已近 8 KB，照 [STRUCTURE](../../../../STRUCTURE.md) 不往裡塞）。逐專案說明在 [aos-kernel-llm](../../../../../proto8/impls/aos-kernel-llm/README.md)、[aos-gate](../../../../../proto8/impls/aos-gate/README.md)；設計紀錄 [thinking 2026-10-24-llm-kernel](../../../../../proto8/thinking/2026-10-24-llm-kernel.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `aos-kernel-llm/include/aos/kernel_llm.hpp`、`src/letter/letter.cpp` | 10-24：信箱四格（`Mailbox`）、信號（`letter_id`：奈秒.pid.started_at_ticks，只管先後與不撞名）、寄信人存活（`hold_sender`／`sender_alive`：信裡 `sender.lock` 的 flock，10-24 晚改、不看 pid）、`parse_priority`（low／normal／high、數字看正負、`{level, deadline}`、ISO 8601 帶時區或 epoch 秒）、`priority_of`（排隊依據的唯一讀法：priority＋單子 `_metainfo` 的 `time_ms`、`llm_tokens`，寫壞當沒寫）、`read_reply`、信箱與信的全部代號（閘門也用） |
| `aos-kernel-llm/src/queue/queue.cpp` | `queue.json`（`counter_runs`、`seen_at_runs`）讀寫、`effective`（level＋等了幾次÷10）、`order`（級數 → deadline → `_metainfo.time_ms` → 等得久 → 先寄） |
| `aos-kernel-llm/src/serve/serve.cpp` | `read_cfg`（`mailbox` 從 `$AOS_STACK` 算、`slots`、`budget`、`accept`〔10-24 晚〕）、`accepted`（有 `accept` 時單子的 argv、cwd 要一字不差、不能自帶 envs 與串流，不然回 `InstUnknown`）、`Server`：flock、`recover`（cur/ 留下的：有回信照交、`runner.json` 活著就讓它跑完、不然 `RunFailed`）、`sweep`（寄信人不在〔`sender.lock` 沒人鎖〕的刪；`tmp/` 裡 `.` 開頭的＝閘門正在寫，已有 `letter.json` 而沒人鎖才刪）、`scan`（`LetterBad`、`DeadlineMissed`）、額度到頂（`spent`＝refuse 回 `BudgetMissing`／wait 停）、`start_runner`（fork、環境換成信裡的〔有 `accept`＝kernel 自己的＋信裡 `AOS_*`〕再加 `AOS_KERNEL_REPORT`、串流預設、`run_inst`、寫 `reply.json`）、`wait_runners`（轉訊號）、`finish`（`runner.json` 在才算一次並讀 `report.json`、`served.jsonl` 一行〔含 `counter_waited_runs`、`counter_tokens`、`report_bad`〕、記 `used.json`、cur → done） |
| `aos-kernel-llm/src/budget/budget.cpp` | 10-24 下午：token 回報與額度——`parse_budget`（`calls`、`tokens`、`window` hour／day／all、`spent` refuse／wait）、`window_since`（本地時間的整點／午夜）、`read_used`／`add_used`（`$AOS_STACK/used.json` 的 `counter_calls`、`counter_tokens`、`counter_all_*`，換窗歸零、`counter_all_*` 照留、`UsedBad`；10-25 計數改 `counter_*`）、`spent`、`read_report`（usage 的 `total_tokens` 或 prompt＋completion） |
| `aos-kernel-llm/src/main.cpp` | 命令列 `aos-kernel-llm [旗標] kernel.json`、要 `AOS_STACK` |
| `aos-gate/src/send/send.cpp` | `mailbox`（`$AOS_KERNEL`，不在＝`MailboxMissing`）、`post`（設 `AOS_CF`／`AOS_CD`／`AOS_CO`、解指示詞、驗 priority、cwd 轉絕對、整份環境、在 `tmp/.<id>/` 先 `hold_sender` 鎖住再寫信、→ new） |
| `aos-gate/src/wait/wait.cpp`、`src/main.cpp` | `wait_reply`（每 20 毫秒看 done/、訊號＝撤信 `withdraw`、`LetterMissing`）、`relay`（stdout／stderr 原樣、回信的碼或錯）；命令列 `aos-gate [旗標] 單子.json` |
| `aos-kernel-llm/tests/test_cli.py`、`aos-gate/tests/test_cli.py` | 單元（ctest 的 `test_cli`）：kernel 40 案（信自己寫、自己鎖 `sender.lock`；H 段＝回報與額度、I 段＝accept）、閘門 16 案（測試自己當 kernel）；兩支接起來跑的在 `proto8/tests/test_kernel_llm.py`（10 案，含 agent-dan 的 brain.py 經閘門回報 usage、額度到頂閘門印 `BudgetMissing`） |

依賴：aos-gate → aos-kernel-llm（公開標頭 `aos/kernel_llm.hpp`）→ aos-loop → aos-exec（`run_inst`）。
