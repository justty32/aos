# proto5/lib — kernel（13 支）

← [proto5/lib README](../README.md)｜上一份：[daemon](daemon.md)｜下一份：[agent](agent.md)

一檔一行（新增模組照這個格式插一行）：

| 檔 | 職責 |
|---|---|
| [`aos_kernel.py`](../aos_kernel.py) | kernel 入口（`aos-kernel` 取 `main`）＋小匯出層（只留測試真的從這裡拿的名字） |
| [`aos_kernel_info.py`](../aos_kernel_info.py) | 池表讀驗（info.json 第 2 版）、成員公式、`init`、初始帳本、反覆工作判定 `classify`、共用錯誤 |
| [`aos_kernel_ledger.py`](../aos_kernel_ledger.py) | `KernelLedger` 帳本（記憶體裡跟第 2 版同形）：排隊、syscall、busy／on、四個出貨箱重放 |
| [`aos_kernel_store.py`](../aos_kernel_store.py) | （09-24 one-boot）帳本第 3 版 `K/ledger.sqlite`：整份讀、只寫變了的列一筆交易、舊 `state.json` 匯入；`proc／knows／procs／meta／peek_proc` 給 `aos-kernel proc`、agent、郵差讀 |
| [`aos_kernel_engine.py`](../aos_kernel_engine.py) | `Kernel` 一格十步（只碰有事的 cpu）與模組函式 `tick` |
| [`aos_kernel_pools.py`](../aos_kernel_pools.py) | kernel 這邊怎麼增減 cpu（每格第 7 步：收 scale 回音、重算、送單、寫 envs／模板、搬池） |
| [`aos_kernel_boot.py`](../aos_kernel_boot.py) | `boot`（寫帳本、向 daemon 登記開 tick）、`status` 偷看、`stop`（halt）等停好 |
| [`aos_kernel_cpu.py`](../aos_kernel_cpu.py) | `aos-kernel cpu add／rm／ls`：只改 `K/info.json` 的池表（鎖、指示詞原樣保留） |
| [`aos_kernel_rows.py`](../aos_kernel_rows.py) | 按池摘要（每池一格／一行）與一顆一行的資料與排版，`cpu ls` 與 `ls` 共用 |
| [`aos_kernel_health.py`](../aos_kernel_health.py) | `health(home)` 一句話健康判定（看每池摘要、不逐顆查）與 agent 暫停／重試標記 |
| [`aos_kernel_ls.py`](../aos_kernel_ls.py) | `aos-kernel ls`：`ls_data()` 收成穩定資料（就是 `--json`），`render()` 排成對齊表 |
| [`aos_kernel_check.py`](../aos_kernel_check.py) | `aos-kernel check`：啟動前唯讀檢查；`kernel_checks()`／`finish()` 給 `aos-agent check` 共用 |
| [`aos_kernel_cli.py`](../aos_kernel_cli.py) | `aos-kernel` 參數解析與 `main` |

## aos_kernel — 池表、sqlite 帳本與 tick（十三支：aos_kernel＋info／ledger／store／engine／pools／boot／cpu／rows／health／ls／check／cli）

09-24 由 proto5-2 納入：kernel 不再逐顆記 cpu，而是「池 P 要 N 顆」的宣告；一格只碰有事的
cpu（收到通知的、上一格剛派的、輪到巡檢的），派工從閒號堆疊直接拿。規範在 [spec/kernel/](../../spec/kernel/README.md)。

`aos_kernel.py`：入口（`cli/aos-kernel` 取 `main`）＋小匯出層，只留測試真的從這裡拿的名字
（`CLI`、`KernelError`、`classify`、`init`、`load_info`、`members`、`new_pool`、`new_state`、`Kernel`、`tick`、
`boot`、`status`、`main`）；其餘請直接 import 各模組。

`aos_kernel_info.py`：池表讀驗（`info.json` 第 2 版：`pools.P.count／skip／envs／daemon／dpool`）、
成員公式（`count` 顆扣掉 `skip` 那幾號）、`init(home, config=None, daemon=None)`（CLI 是 `init --config FILE`：
沒給就一個池都沒有；池名 `kernel` 是保留名、寫了就拒絕；成功印 `initialized <K>`）、`new_state()` 建初始帳本、
`classify()` 判定反覆工作結果。

`aos_kernel_ledger.py`：`KernelLedger` 帳本（記憶體裡跟第 2 版同形）——`ready／delayed` 堆積排隊（懶刪）、`busy`／`on`
記誰在哪格忙、`pools` 每格記 `want／sent／dirty／redeclare` 等、`sends／acks／replies／deletes` 四個
出貨箱，一格最多存三次（提交點 A／B／C，各一筆 sqlite 交易）。

`aos_kernel_store.py`（09-24 one-boot）：帳本第 3 版 `K/ledger.sqlite`（WAL、`synchronous=NORMAL`、busy_timeout 10 秒）。
表 `meta`／`procs`／`pools`／`busy`；`on` 不存、讀時從 `busy` 反推。`read(home)` 整份讀成 dict、`Store` 存檔只寫變了的列；
第 2 版 `K/state.json` 在 boot 時匯入、改名 `state.json.v2-old`。唯讀的 `proc(home, name)`／`knows`／`procs`／`meta`
給 `aos-kernel proc`、aos-agent；`peek_proc`／`peek_procs` 給 aos-team 郵差。

`aos_kernel_engine.py`：`Kernel`（`PoolsMixin` ＋ `KernelLedger`）一格十步：讀通知、收回音、（第 7 步）交給
`aos_kernel_pools` 對池做事、派工、四出貨箱重放、停機。模組函式 `tick(home)` 跑一格：先非阻塞拿 `K/.tick.lock`
（拿不到退 75）、設 `tick_timeout_ms` 鬧鐘；帶舊的 `chain／seq`（舊 kernel cpu 裡排著的舊格）就退 0 什麼都不做。
停好那格往 daemon 放一張 `tick {off: true}` 撤登記。

`aos_kernel_pools.py`：kernel 這邊怎麼增減 cpu——每格第 7 步：收 scale 回音 → info 變了沒 → `dirty`
才重算 → 送下一張 scale 單 → 重寫 `envs.json`／池模板 `inst.json` → 搬池／池消失，只碰有變化的池。

`aos_kernel_boot.py`：`boot(home, wait_ms=30000)`——驗 info、cli、開 tick 的 daemon 與每池的 daemon 都活著 → 拿
`K/.tick.lock` → （只有舊帳本才有）舊 kernel 池縮到 0 → 一筆交易寫新帳本（新 chain、`pools` 全部標 `dirty` 待第一格整份重送）
→ 建家與模板 → 放開鎖前向 daemon 送 `tick` 登記單、等回音。`status(home)` 偷看帳本＋各池 daemon 摘要＋tick 登記；
`stop(home, wait_ms)` 是 `halt`：每個池縮到 0，等 daemon 那邊全部消失才印 `stopped`。

`aos_kernel_cpu.py`：`cpu_add()`／`cpu_rm()`／`cpu_ls()`——只改 `K/info.json` 的池表：拿
`K/.info.lock` 獨占鎖（等 10 秒）→ 讀 → 改 → 驗 → 唯一 `.tmp` → rename；不放任何單、不用 `boot`，
kernel 在跑的話下一格就照新數字做。指示詞（`$env`…）原樣保留，不是字面值就退 1、不寫。

`aos_kernel_rows.py`：`pool_rows()`／`pool_row()` 每池一格 dict（`--json` 讀的就是它）、`row_line()`／`pool_lines()`
一池一行（`running` 那格同 daemon ls，restarting 寫進括號）、`cpu_rows()`／`cpu_line()` 一顆一行（逐顆讀 kids 檔）；
`cpu ls`、`aos-kernel ls`、health、check 共用。

`aos_kernel_health.py`：`health(home)` 先中先印：缺目錄 → 舊帳本 → 停機中 → daemon 沒在跑 → 沒人開 tick（daemon 沒登記）
→ tick 連敗或停住 → 某池出錯／池不見了 → 搬池中或池少幾顆（`recovering`）→ ok；只看每池的 `summary.json`。
`agent_marks()`／`agents_health()` 給 `ls` 標 agent 的暫停／重試。

`aos_kernel_ls.py`：`ls_data()` 收成 `aos_kernel_ls` 第 3 版資料（就是 `--json`；09-24 one-boot `kernel.cpu` 換成 `kernel.tick`、池表不再有 kernel，欄位表在
[kernel/cli-ls.md](../../spec/kernel/cli-ls.md)），`render()` 排成對齊表（第一行 health、按池摘要、行程）；
`stderr_hint()` 給 bad 行程指路。

`aos_kernel_check.py`：啟動前唯讀檢查（info、K 家目錄、daemon、PATH、池表、llm 設定；`--probe` 真的打一次
endpoint）；`kernel_checks()`／`finish()` 給 `aos-agent check` 共用。

CLI（`aos_kernel_cli.py`）：每個子命令都用 `--target K`（省略找 `AOS_KERNEL_HOME` 再目前資料夾，
退 1 的錯誤行附來源）：`aos-kernel init --config FILE [--daemon D]／boot [--wait-ms N]／cpu add／rm／ls／tick／
add INST／rm NAME／ack NAME／ls [--pool P] [--procs] [--json] [-v]／proc NAME [--json]／halt [--wait-ms N] [--no-wait]／
check [--daemon-target D] [--probe]`（`--agent` 一律用法錯、指到 `aos-agent check`），各有 `-h`。
反覆 add 等回音印 NAME；once 預設印 request 與回音路徑，帶 `--wait-ms` 才等；CLI 收到回音代 ack，
JSON-RPC error 退 1；exec result 即使工作失敗仍退 0、由內容判成敗。

`aos_up.py`（09-24 one-boot，入口 `cli/aos`）：`up(home, wait_ms)`——開 tick 的 daemon 與各池的 daemon 沒在跑就開
（`setsid`、stdin `/dev/null`、stdout／stderr 附加到 `D/daemon.log`、PATH 前面補 `proto5/cli`），再 `aos_kernel_boot.boot`，
等帳本 `last_seq ≥ 1`（第一格跑完）、各池第一張宣告有回音（最多 5 秒），印 `up K=…` 與一行 `health …`（池出錯、daemon／tick 有問題就退 1）。`down(home, wait_ms, keep_daemon)`——`aos_kernel_boot.stop`，
等撤登記生效（最多 5 秒），daemon 沒有別的 kernel 登記、沒有池就 `aos_daemon.stop`，否則印 `daemon D 沒停：還有 別的 kernel：…；池：…`。
規範 [spec/daemon/up.md](../../spec/daemon/up.md)。
