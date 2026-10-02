← [proto5/lib 模組](../proto5-lib.md)（分檔 1/3）｜[下一份](02-llm-agent.md)

| 模組 | 職責 |
|------|------|
| `aos_directives` | 指示詞（`$env`／`$fmt`／`$ref`／`$opt`）解析的純函式庫 |
| `aos_directives_edit` | `aos-directives`：人格分節編輯（ls／show／set／add／rm／export／import／versions／revert）＋指示詞 resolve／check |
| `aos_inst` | inst.json 的讀、驗、解 |
| `aos_exec` | 執行一次的上層：三種目標的解讀（`run_target`／`run_target_full`／`run_inst`）與 `aos-exec` 命令列 |
| `aos_exec_run` | 執行一次的底層：前置檢查、開串流、起子行程、等待／逾時／強停整組、寫 exit 檔 |
| `aos_exec_spawn` | daemon 的非同步入口 `spawn_target`（`launcher` 決定 fd 0／1 怎麼接） |
| `aos_home` | JSON-RPC 信封、原子放單與狀態、ack／stop、開機對帳、`--target` 找家 |
| `aos_client` | 交件者：取名、放單、等回音、ack |
| `aos_exec_cpu` | 長命 exec cpu（`aos-cpu`）：逐件執行、訊號與對帳、回完音丟 `notify` 通知 |
| `aos_daemon` | daemon 的家、info、`is_alive`、給 kernel 讀的池摘要／kids 檔、boot（`run`）與 halt（`stop`） |
| `aos_daemon_pools` | 池的資料形狀（pool.json／kids／summary.json）、檔案動作、拉孩子 |
| `aos_daemon_loop` | daemon 的一圈：收屍、狀態機、退避、節流、fd 預算、批次停機階梯 |
| `aos_daemon_rpc` | daemon 收的單 `scale`／`kill`／`ls`／`tick` 怎麼驗、怎麼判 |
| `aos_daemon_ticks` | （one-boot）daemon 替 kernel 開 tick：登記檔 `D/kernels/`、定時或 `K/requests/` 有新檔就開一格、同時一格、逾時 KILL、連敗退避 |
| `aos_daemon_cli` | `aos-daemon boot／halt／ls／scale／kill` 命令列 |
| `aos_kernel` | kernel 入口（`main`）＋只留測試在用的小匯出層 |
| `aos_kernel_info` | 池表讀驗（info 第 2 版）、成員公式、`init`、初始帳本、`classify`、共用錯誤 |
| `aos_kernel_ledger` | `KernelLedger` 帳本（記憶體裡第 2 版同形）：排隊、syscall、busy／on、四個出貨箱 |
| `aos_kernel_store` | （one-boot）帳本第 3 版 `K/ledger.sqlite`：整份讀、只寫變了的列一筆交易、舊 `state.json` 匯入；`proc`／`peek_proc` 給 `aos-kernel proc`、agent、郵差讀 |
| `aos_kernel_engine` | `Kernel` 一格十步與 `tick` |
| `aos_kernel_pools` | kernel 這邊怎麼增減 cpu（每格第 7 步：scale 回音、重算、送單、搬池） |
| `aos_kernel_boot` | `boot`（寫帳本、向 daemon 登記開 tick）、`status`、halt 等停好 |
| `aos_kernel_cpu` | `aos-kernel cpu add／rm／ls`：只改 `K/info.json` 的池表 |
| `aos_kernel_rows` | 按池摘要與一顆一行的資料與排版（`cpu ls`、`ls`、health、check 共用） |
| `aos_kernel_health` | `health()` 一句話健康判定與 agent 暫停／重試標記；（09-24 tick-gap）有反覆工作 bad 就報 `bad` |
| `aos_hops` | （09-24 tick-gap）`AOS_HOPS` 設了才記的每一跳時間戳；`report` 把一個 agent 的牆上時間切成一跳一跳 |
| `aos_kernel_ls` | `aos-kernel ls`：穩定資料（`--json`）與對齊表 |
| `aos_kernel_check` | `aos-kernel check` 啟動前唯讀檢查（`aos-agent check` 共用前半） |
| `aos_kernel_cli` | `aos-kernel` 參數解析與 `main` |
| `aos_up` | （one-boot，入口 `cli/aos`）`aos up`：daemon 沒在跑就開→`aos-kernel boot`→等第一格；`aos down`：halt→沒人用的 daemon 一起停 |
| `test/test_one_boot.py` | one-boot 的真 daemon＋真 tick 測試：交易中 kill -9 回滾、tick 逾時與連敗、新單觸發、同時一格、`aos up`／`down` 不留行程、舊帳本匯入 |
