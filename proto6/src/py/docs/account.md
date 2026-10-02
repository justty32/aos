# proto6/src/py — 帳號

← [proto6/src/py README](../README.md)｜上一份：[訊息與 aos-mq](mq.md)｜下一份：[daemon 跑 daemon](daemon-run.md)

## 帳號（m3m 模組五）

照 [plan m3m](../../../plan/m3m-daemon-modules.md) 模組五寫的（2026-10-01 第十二、十三批），`lib/aos_daemon_account.py`（主程式那側）、`lib/aos_daemon_root.py`＋`bin/aos-daemon-root`（root 端），spec [B-646](../../../spec/settled/daemon/account.md)、格式 [P-126](../../../spec/settled/protocol/daemon/account.md)。設定檔寫 `modules.account` 才掛，沒寫時 daemon 跟上面一模一樣（每項的 `account` 照不認得的鍵忽略）。

```json
{"interval_ms": 60000,
 "modules": {"account": {"user": "lorkhan", "allow": ["agent-*", "bob"], "deny": ["agent-admin"]}},
 "insts": {"a.json": {}, "jobs/bob.json": {"account": {"user": "bob"}}}}
```

要用 root 開：`sudo bin/aos-daemon --config F`。開起來的順序：

1. 讀設定（root）→ `Policy` 核預設帳號（`user`，沒寫用 `SUDO_USER`；不准是 root、要查得到）、名單（`*` 只能在結尾、`deny` 比得到預設帳號＝錯）、每一項的帳號（名單准、`getpwnam` 查得到）。不合 stderr `aos-daemon: account: <說明>`、回 1；沒用 root 開也是。
2. 掛了 cgroup 模組：照常建子樹、建框，然後 `chown_tree()` 整棵交給預設帳號。
3. `Account()`：開一條 `SOCK_SEQPACKET` socketpair，fork＋exec `aos-daemon-root <fd>`（另一個 session），第一個封包送名單。
4. `Account.drop()`：`initgroups`／`setgid`／`setuid` 永久降成預設帳號，`HOME`／`USER`／`LOGNAME` 換掉，起收回應的執行緒。
5. 之後才 `give_env()`、開控制／訊息 socket（〔第二十五批〕一律 chmod 666，不管有沒有掛帳號模組；誰能連由所在資料夾決定）、起各項。

跑一項：帳號是預設帳號（或沒寫）的，照舊自己開；別的帳號的走 `run_via_root()`——主程式開好 stdout／stderr 的 pipe（沒設路徑就交 `/dev/null`），連同請求 `{"id","user","argv","cwd","env","frame"}` 交給 root 端；root 端再核一次名單與 `getpwnam`，fork：`setsid`、有框先寫 `cgroup.procs`、切帳號、chdir、exec `aos-exec`，結束回 `{"id","exit"}`。查不到帳號回 `{"id","error"}`，主程式 stderr `aos-daemon: account: no such user <名字>`、那一次 `exit=1`。root 端不見了（EOF）：stderr 一行、刪 socket 檔、回 1。

| 函式 | 做什麼 |
|---|---|
| `aos_daemon_account.Policy`、`match()`、`lookup()`、`item_user()` | 預設帳號、名單比對、每項的帳號 |
| `Policy.check_items()` | 開起來與重讀時核每一項（重讀照開起來時的名單） |
| `chown_tree()` | cgroup 子樹交給預設帳號 |
| `Account`、`Account.drop()`、`Account.run()`、`_replies()` | 開 root 端、降權、送請求、照 id 收回應 |
| `run_via_root()`、`aos_daemon.run_once()` | 別的帳號的那一項：pipe、等碼、清框、收齊輸出 |
| `aos_daemon._die()` | 刪 socket 檔、直接退出（SIGINT／SIGTERM 回 0，root 端不見了回 1） |
| `aos_daemon_root.main()`、`check()`、`child()` | root 端：單執行緒 select＋SIGCHLD、核帳號、fork 切帳號 exec |

測試 `tests/test_account_policy.py`、`test_account_ns.py`（原 `test_account.py`，21 條，約 2 秒）：名單比對、設定錯、沒 root 回 1 用一般帳號跑；其餘用 `unshare --user --map-root-user --map-auto` 當假 root（namespace 裡 UID 1～65536 對到 /etc/subuid，系統帳號 http、daemon、nobody 切得過去），把 src/py 複製到 /tmp 底下跑（別的 UID 進不了 /home/lorkhan）；拿不到就跳過。跟 cgroup 模組一起的一條用 `systemd-run --user --scope -p Delegate=yes` 再包 unshare。真 root、真帳號的整套要手動驗（plan m3m 模組五驗收草稿）。
