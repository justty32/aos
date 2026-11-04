# proto5/lib — daemon（6 支）

← [proto5/lib README](../README.md)｜上一份：[執行與共用底層](exec.md)｜下一份：[kernel](kernel.md)

一檔一行（新增模組照這個格式插一行）：

| 檔 | 職責 |
|---|---|
| [`aos_daemon.py`](../aos_daemon.py) | daemon 的家、info 讀驗、`is_alive`、給 kernel 讀的 `pool_summary`／`pool_summary_state`／`pool_kid`、`run`（boot）與 `stop`（halt） |
| [`aos_daemon_pools.py`](../aos_daemon_pools.py) | 池的資料形狀（`pool.json`／`kids/<i>.json`／`summary.json`）、檔案動作、拉孩子（只留 fd 0 一條 pipe） |
| [`aos_daemon_loop.py`](../aos_daemon_loop.py) | daemon 的一圈：收屍、狀態機、退避、節流、fd 預算、批次停機階梯 |
| [`aos_daemon_rpc.py`](../aos_daemon_rpc.py) | daemon 收的單 `scale`／`kill`／`ls`／`tick` 怎麼驗、怎麼判（同步做完才回） |
| [`aos_daemon_ticks.py`](../aos_daemon_ticks.py) | （09-24 one-boot）daemon 替 kernel 開 tick：`tick` 登記（`D/kernels/<id>.json`）、定時或 `K/requests/` 有新檔就開一格、同時一格、逾時整組 KILL、連敗退避不停 |
| [`aos_daemon_cli.py`](../aos_daemon_cli.py) | `aos-daemon boot／halt／ls／scale／kill` 命令列 |

## aos_daemon — 池的主人（六支：aos_daemon／pools／loop／rpc／ticks／cli）

09-24 由 proto5-2 納入：daemon 手上不再是一顆一顆孩子的 `spawn／kill`，而是一份「每池要哪幾號」的
宣告（`pool.json`），每圈把孩子往宣告靠（死了自己拉、多了自己收）。規範在 [spec/daemon/](../../spec/daemon/README.md)。

`aos_daemon.py`：`daemon_home(value=None)` 依 `--target／AOS_DAEMON_HOME／` 目前資料夾找家；`run(home)`
是前景主迴圈（開機先整批殺掉上一任的孩子、kids 檔改成 pending、照 `pool.json` 節流拉回來；舊版 proto5 家
的 `children` 表也照殺）；`stop(home, wait_ms=30000)` 是 `halt`：不活就不放單、印 `not running`，活的放
stop notification、flock 等退出。`is_alive(home)` 非阻塞共享 flock 探測。給 kernel 讀的小函式：
`pool_summary(home, dpool)`（讀 `summary.json`，不在或壞了回 `None`；顯示用）、`pool_summary_state(home, dpool)`
（回 gone／ok／unknown，只有 gone 才算池已拿掉；交接用）、`pool_kid(home, dpool, i)`（讀 `kids/<i>.json`）。
`main` 轉給 aos_daemon_cli。

`aos_daemon_pools.py`：池與一顆一檔的形狀（`pool.json`／`kids/<i>.json`／`summary.json`）、
`valid_pool_name()`（1～64 bytes、只用 `A-Za-z0-9_.-`）、`peek(path)`（讀一個 JSON 物件，讀不到回 `None`）、
`spawn_child()`（叫 `aos_exec_spawn.spawn_target`，`launcher` 換成只留 fd 0 一條控制 pipe、fd 1 接 `/dev/null`）。

`aos_daemon_loop.py`：`Daemon` 的一圈——`waitpid(-1)` 收屍；dead／failed 的到期、活滿 `stable_ms` 取消
重拉標記、批次階梯的下一段，全部放在同一個按時間排的堆積；可以拉的號每池一條佇列，只有佇列不空的池參加
輪流（`spawn_per_sec` 節流，`max_children` 是 fd 預算）；每圈只碰有事的池。

`aos_daemon_rpc.py`：`Requests.scale {pool,count,skip?,inst?,home?,decl?,owner?}`（池不在要給 `inst`
樣板；`owner` 是別人的池要 `--force` 才能改）、`kill {pool, names|all}`、`ls`、`tick`（轉給 aos_daemon_ticks），一律同步做完才回。

`aos_daemon_ticks.py`（09-24 one-boot）：`tick {home, cli, every_ms?, timeout_ms?}` 登記／`off: true` 撤登記，
存 `D/kernels/<id>.json`（id＝K 絕對路徑 SHA-256 前 16 字元，只在登記、失敗、恢復時重寫）。每圈：沒有一格在跑、而且
時間到（上一格開始後 `every_ms`）或 `K/requests/` 出現新檔名（只 stat 資料夾、不讀內容）就開 `<cli> tick --target K`。
退 0 好、75 鎖被佔不算失敗、其他算失敗（退避、不停）；跑超過 `timeout_ms` 整組 KILL。`registered(D)`、`peek(D, K)` 給 `aos down` 與 health 讀。
`stop／ack` 走既有的 `aos_home.scan_controls`。

`aos_daemon_cli.py`：`aos-daemon boot／halt／ls／scale／kill`，家一律 `--target`。`ls` 只偷看檔案、
不放單（daemon 沒在跑也看得到最後的摘要，第一行講 daemon 有沒有在跑）；給 `--pool` 才一顆一行；
`running` 那格寫成 `2（含 restarting 1）`（restarting 是 running 的子集，0 就只印 `2`；`--json` 照舊兩欄）；
`scale／kill` 放單等回音（10 秒）。
