# proto6/src/py — daemon 跑 daemon

← [proto6/src/py README](../README.md)｜上一份：[帳號](account.md)

## daemon 跑 daemon：輸出上限、鎖檔、kill／restart（第十九批）

〔使用者 2026-10-01 第十九批〕上層 daemon 把下層 daemon 當一項跑（inst 的 argv 是 `aos-daemon --config …`）時要的三件事。spec：[B-640](../../../spec/settled/daemon/core.md)「輸出」「鎖檔」、[B-641](../../../spec/settled/daemon/control.md)「kill 與 restart」，格式 [P-120](../../../spec/settled/protocol/daemon/core.md)、[P-121](../../../spec/settled/protocol/daemon/control.md)、[P-126](../../../spec/settled/protocol/daemon/account.md)（root 端送訊號）。

```json
{"interval_ms": 5000, "exec_out_path": "<inst>/daemon.log", "exec_output_max_bytes": 65536,
 "modules": {"control": {"socket": "./aos.sock", "kill_grace_ms": 3000}},
 "insts": {"daemons/lorkhan.json": {}}}
```

- **輸出上限**：頂層 `exec_output_max_bytes`（預設 1048576，各項共用、每項不能覆蓋）。`run_once()` 對 stdout／stderr 各開一條執行緒跑 `drain()`：讀一段就接上、超過上限就從前面丟，所以一直印的下層 daemon 記憶體也只到上限。寫出時標頭多 `dropped=<bytes>`（有丟才加）。帳號模組經 root 端的那條路（`run_via_root()`）也用 `drain()`。
- **鎖檔**：`main()` 讀完設定就對 `lock_path`（預設 `<設定檔>.lock`，相對以設定檔資料夾為準）取 `flock(LOCK_EX|LOCK_NB)`；拿不到 stderr `aos-daemon: lock: another aos-daemon holds <鎖檔>`、回 1——在開 socket、建 cgroup、開 root 端、降權之前，所以不會搶走第一個 daemon 的 socket。fd 握到程序結束（`os.open` 開的不可繼承）。重讀設定時鎖檔路徑變了只警告 `reload: need restart: lock_path`。
- **kill／restart**：`aos_daemon_ctl._kill()` 另開執行緒跑 `aos_daemon.kill_run()`：先 `signal_run(item, False)`（SIGTERM），等 `kill_grace_ms` 那一次（`Item.run_seq`）還沒結束就 `signal_run(item, True)`（SIGKILL），掛 cgroup 再寫那一項框的 `cgroup.kill`。對象由 `kill_targets()` 從 /proc 算：aos-exec 把任務開在另一個 session，所以 TERM 送給 aos-exec 底下所有後代的程序群組（不含 aos-exec，讓它照常回任務的碼；沒有後代才送它），KILL 再加上 aos-exec 自己。別的帳號的項（帳號模組）`signal_run()` 改請 root 端送（`Account.signal()` → `{"signal": id, "final": …}`，root 端 `targets()` 是同一套規則的另一份）。restart：先記一次待補（像 wake）、記下 `Item.restart_seq`，被殺的那次非 0 不算 `stop_on_nonzero`。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon.drain()`、`write_outputs()`、`_block()` | 邊讀邊丟、寫出加 `dropped=` |
| `aos_daemon.main()` 開頭 | 鎖檔 |
| `aos_daemon.kill_targets()`、`signal_run()`、`kill_run()` | 算要送的程序群組、送 TERM／KILL、寬限 |
| `aos_daemon_ctl._kill()`、`grace_of()`、`set_grace()` | kill／restart 指令、`kill_grace_ms` |
| `aos_daemon_account.Account.signal()`、`aos_daemon_root.targets()` | 別的帳號的項經 root 端送訊號 |

測試 `tests/test_daemon_kill.py`（20 條）：輸出上限（含一直印 20 MB）、鎖檔、kill／restart；掛 cgroup 的一條要委派的 scope、帳號模組的一條要 namespace 假 root，拿不到就跳過。
