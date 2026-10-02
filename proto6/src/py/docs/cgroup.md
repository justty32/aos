# proto6/src/py — 收屍／cgroup

← [proto6/src/py README](../README.md)｜上一份：[重讀設定與記住狀態](reload-state.md)｜下一份：[訊息與 aos-mq](mq.md)

## 收屍／cgroup（m3m 模組二）

照 [plan m3m](../../../plan/m3m-daemon-modules.md) 模組二寫的（2026-10-01 第十二批，C1～C4 照建議），`lib/aos_daemon_cgroup.py`，spec [B-644](../../../spec/daemon/cgroup.md)、格式 [P-124](../../../spec/protocol/daemon/cgroup.md)。設定檔寫 `modules.cgroup` 才掛，沒寫時 daemon 跟上面一模一樣。

```json
{"interval_ms": 60000,
 "modules": {"cgroup": {}},
 "insts": {"a": {"cgroup": {"memory.max": "512M", "pids.max": "200"}}, "b": {}}}
```

要在委派好的 cgroup v2 子樹裡開，例如 `systemd-run --user --scope -p Delegate=yes bin/aos-daemon --config F`；沒有就照 Python 預設丟 traceback、回 1，不退回別的做法。

- 子樹根＝daemon 自己所在的 cgroup（自己已經在 `.../daemon` 裡就取上一層）。開起來先建 `<根>/daemon`、把根上所有程序搬進去，再開 `cpu`、`memory`、`pids` 裡根上有的。
- 每項一個葉框 `i-<inst 字面值 sha256 前 16 hex>`，開框時 stdout 印 `inst=<inst> cgroup=i-<h>`；框已經在（上次留下的）就先清空。那一項的 `cgroup` 物件原樣寫進框裡，不翻譯、不檢查。
- 每次跑：`sh -c 'echo $$ > 框/cgroup.procs && exec aos-exec …'` 先進框再變成 `aos-exec`（daemon 有很多執行緒，不用 `preexec_fn`）。`aos-exec` 結束時 `ms=` 停錶；框裡還有程序就寫 `cgroup.kill`（直接 SIGKILL）、等 `cgroup.events` 的 `populated 0`，才印 `exit=`、排下一次。有清到東西時接著印 `inst=<inst> reaped`。
- 殘留程序可能還拿著輸出的 pipe：掛了模組時 pipe 另開執行緒讀，清完框才讀得到結尾，輸出照樣收齊。
- 跟重讀設定一起掛：新加的項建框、寫上限，`added` 之後印對照；還在的項上限改了就重寫新設定寫的檔（拿掉的鍵不還原）；拿掉的項由自己的執行緒在最後一次跑完、清完後刪框（又被加回來就不刪）。建框、寫上限出錯算重讀出錯，但出錯前已經寫進去的不還原。

```text
2026-10-01T17:07:03+08:00 inst=a.json cgroup=i-6025a12236ee54ba
2026-10-01T17:07:06+08:00 inst=a.json exit=0 ms=2032
2026-10-01T17:07:06+08:00 inst=a.json reaped
```

| 函式 | 做什麼 |
|---|---|
| `aos_daemon_cgroup.Tree()` | 找根、建 `daemon` 子框、搬程序、開 controller |
| `Tree.make()`、`limits()`、`announce()` | 建（或接手）一項的框、寫上限、印對照 |
| `Tree.argv()`、`aos_daemon.run_once()` | 子程序先進框再 exec；結束後 `clear()`、回 `(碼, 毫秒, 有沒有收屍)` |
| `aos_daemon_cgroup.clear()`、`populated()` | `cgroup.kill`、等清空 |
| `aos_daemon._gone()`、`Tree.remove()` | 重讀拿掉的項跑完後刪框 |
| `aos_daemon_reload._apply()` | 重讀時先建框、寫上限，出錯就整份不套用 |

測試 `tests/test_daemon_cgroup_tree.py`、`test_daemon_cgroup_errors.py`（原 `test_daemon_cgroup.py`，15 條，約 9 秒）：每條用 `systemd-run --user --scope -p Delegate=yes` 包 daemon，拿不到委派的 scope 時整組跳過；`NotDelegated` 一條在測試自己所在的 cgroup 寫得進去時跳過（模擬不了沒委派）。2026-10-01 晚在家裡 Manjaro 實跑 14 過、1 跳過。
