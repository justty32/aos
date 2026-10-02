"""aos-daemon 的 kill／restart 送訊號（第十九批；從 aos_daemon.py 拆出）：找後代的程序群組、送 TERM／KILL。

帳號模組的物件（`aos_daemon._acct`）由 `aos_daemon.main()` 換上，所以呼叫時才去母模組讀。
對外照舊從 aos_daemon import（那裡 re-export）。
"""
import os
import signal
import time


def kill_targets(pid, final):
    """第十九批 kill：pid（aos-exec）底下要送訊號的程序群組。aos-exec 把任務開在另一個 session，所以只送
    aos-exec 自己的群組會讓任務變孤兒。從 /proc 找 pid 所有後代的程序群組：
    - SIGTERM 那一步（final=False）只送後代的群組、不送 aos-exec 自己——任務收到 TERM 自己收尾、結束，
      aos-exec 照常回任務的碼；沒有後代才送 aos-exec 自己。
    - SIGKILL 那一步（final=True）後代的群組加 aos-exec 自己，全部送。
    已經脫離親子樹的（setsid＋double fork 被收養的）找不到；那些靠 cgroup 模組清框。"""
    parents = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % name) as f:
                fields = f.read().rsplit(")", 1)[1].split()
            parents[int(name)] = (int(fields[1]), int(fields[2]))
        except (OSError, ValueError, IndexError):
            continue
    below, frontier = set(), {pid}
    while frontier:
        frontier = {p for p, (parent, _) in parents.items() if parent in frontier} - below
        below |= frontier
    groups = {parents[p][1] for p in below if p in parents} - {pid, os.getpgrp()}
    if final or not groups:
        groups.add(pid)
    return groups


def signal_run(item, final):
    """第十九批：對那一項正在跑的那一次送 SIGTERM（final=False）或 SIGKILL（final=True），對象見 `kill_targets()`。
    主程式開的自己送；經帳號模組 root 端開的請 root 端送（主程式降權了，送不到別的帳號）。沒在跑就什麼都不做。"""
    import aos_daemon
    rid = item.root_rid
    if rid is not None and aos_daemon._acct is not None:
        aos_daemon._acct.signal(rid, final)
        return
    pid = item.pid
    if pid is None:
        return
    sig = signal.SIGKILL if final else signal.SIGTERM
    for g in kill_targets(pid, final):
        try:
            os.killpg(g, sig)
        except ProcessLookupError:
            pass


def kill_run(item, seq, grace_s):
    """第十九批 `kill`：先 SIGTERM；等 grace_s 秒那一次（序號 seq）還沒結束就 SIGKILL，掛了 cgroup 再把整個框
    `cgroup.kill`。在自己的執行緒裡跑（控制指令送完訊號就回）。
    每次送訊號都在 item.cond 底下先核「還是第 seq 次、還在跑」：那一次已經結束（補跑的下一次已經開了）就不送，
    不會殺到下一次（`run_once()` 收屍前先在 cond 底下清掉 `item.pid`，所以拿到的 pid 一定是這一次的）。"""
    with item.cond:
        if not (item.running and item.run_seq == seq):
            return
        signal_run(item, False)
        deadline = time.monotonic() + grace_s
        while item.running and item.run_seq == seq:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            item.cond.wait(left)
        if not (item.running and item.run_seq == seq):
            return
        signal_run(item, True)
        if item.frame is not None:
            try:
                with open(os.path.join(item.frame, "cgroup.kill"), "w") as f:
                    f.write("1")
            except FileNotFoundError:
                pass
