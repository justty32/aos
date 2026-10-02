# daemon 收屍／cgroup 模組

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜格式：[P-124](../protocol/daemon/cgroup.md)｜舊設計：[暫緩區 B-605](../deferred/daemon/cgroup.md)

程式：`lib/aos_daemon_cgroup.py`；測試：`tests/test_daemon_cgroup_tree.py`、`test_daemon_cgroup_errors.py`（拿不到委派的 cgroup 時跳過）。

## B-644：收屍／cgroup 模組

做什麼：設定檔寫了 `modules.cgroup`，每一項一個 cgroup 框；`aos-exec` 開在那一項的框裡，結束後把框裡留下的程序全部殺掉、等清空，才算這次結束。每項可用 `cgroup` 物件設上限（鍵是 cgroup 檔名、值原樣寫進去）。

原則：

- 子樹根＝daemon 自己所在的 cgroup（要求是委派給 daemon 的 cgroup v2，例如 `systemd-run --user --scope -p Delegate=yes`）。**沒有委派就自然丟錯、回 1，不退回沒 cgroup 的做法。**
- 框名用 inst 字面值的雜湊，因為重讀後「第幾項」會變。
- 清框直接 `cgroup.kill`（SIGKILL，不先 SIGTERM）：任務要收乾淨就自己在結束前收。「上一次結束」＝`aos-exec` 結束而且框清空，所以同一項的殘留不會跟下一次疊著跑。
- Ctrl-C 照核心直接退出、框留著，下次開起來時才清。
- 先不做：逃生口、逾時砍、量測、`aos-cg`（[B-634](../deferred/cg.md)）。
