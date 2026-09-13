# proto4-3／逐檔職責

← [README](../README.md)

## aos-exec／aos-run

- `aos-exec`、`aos-run`：可執行的薄命令列入口。
- `aos_exec.py`：認目標、跑一次、砍逾時、寫 exit 檔；核心是 `run_target()`。
- `aos_inst.py`：inst.json 的讀取、嚴格驗證與指示詞解析。
- `aos_run.py`：反覆呼叫 `run_target()`，管理間隔、停止條件與狀態事件。

## daemon

- `aos-daemon`：daemon 的前台命令列入口。
- `aos_daemon.py`：daemon 狀態表、七個動作、主迴圈、落地與收工。
- `aos_daemon_entry.py`：表上的一筆、五態狀態機、status／stderr 讀取執行緒與 key 規則。
- `aos_daemon_req.py`：逐張分派 `requests/` 裡的請求並寫進 `done/`。
- `aos-daemon-ctl`：ctl 的薄命令列入口。
- `aos_daemon_ctl.py`：送請求等回音、讀 `state.json` 印表；`ask(quiet=True)` 可收掉原始回音。
- `aos_home.py`：daemon 家目錄版面、家的優先序、原子寫檔與 pid 存活判定。

## kernel

- `aos-kernel`：`ls`／`add`／`rm` 的薄命令列入口。
- `aos_kernel.py`：`KHome` 版面與 config／state／log 共用操作，以及 CLI 分派。
- `aos_kernel_status.py`：`ls` 的 daemon、cpu、waiting、佇列與收尾狀態輸出。
- `aos-kernel-init`、`aos_kernel_init.py`：重灌入口與本體；建立 kernel 家、cpu、行程與 syscall 資料夾。
- `aos-kernel-boot`、`aos_kernel_boot.py`：把已初始化的 kernel 放上正在跑的 daemon。
- `aos_kernel_add.py`：正規化 cwd／argv[0]，用 aos-exec 規則驗證後原子排進 `procs/`。
- `aos_kernel_syscall.py`：`rm` 投單、等回音，以及 tick 端的 syscall 收件與拿掉行程。
- `aos-kernel-tick`：tick 的薄命令列入口。
- `aos_kernel_tick.py`：每回合點 cpu、收 syscall、退壞檔，再呼叫排程並寫表與 log。
- `aos_kernel_schedule.py`：排程、waiting 讓位，以及 done／連敗／125 的收尾規則。

## `config.json` 欄位

| 欄位 | 預設 | 意思 |
|---|---:|---|
| `ncpu` | 必填 | cpu 數量，至少 1 |
| `interval_ms` | 1000 | 每顆 cpu 兩次執行的間隔 |
| `timeout_ms` | 0 | 單次執行時限；0 表示不限 |
| `quantum` | 5 | 有別人排隊時，行程跑幾次後輪替 |
| `done_exit` | 100 | 這個退出碼表示做完；0 關閉 |
| `wait_exit` | 101 | 這個退出碼表示正在等待 |
| `bad_after` | 10 | 其他非零退出連續幾次後進 `bad/`；0 關閉 |
| `modules` | `[]` | init 時用 `--module` 掛入的絕對路徑清單 |

舊 config 沒有 `wait_exit`／`bad_after` 仍能讀，會自動採 101／10。

## 測試

- `test/`：`python3 -m unittest discover -s test`；kernel 回歸集中在 `test/test_kernel.py`。
- daemon 共用基底在 `test/_daemon.py`；查詢、操作與完整 CLI 生命周期分在
  `test_daemon.py`、`test_daemon_ops.py`、`test_daemon_cli.py`。
