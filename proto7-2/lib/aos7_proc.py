"""程序工具：活不活、程序群組、身分掃描（環境變數 NODE＋TID＋RUN）、收程序（spec.md 2.6、5.2、6 節；Q1 範圍）。

起點複製自 proto7-1 lib/aos7_task.py 的「程序」一段；身分掃描多比 `AOS7_RUN`（同一個槽上一個 run 的殘留不算這次的）。
所有函式只讀 /proc 與送訊號，不留記憶體狀態。
"""
import os
import signal
import time

from aos7_fs import proc_starttime

KILL_GRACE = 1.0   # spec 第 6 節：SIGTERM 後等至多 1 秒，還在就 SIGKILL

ALIVE, GONE, UNKNOWN = "alive", "gone", "unknown"


def pid_alive(pid):
    """程序在不在（殭屍算不在）。"""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def same_process(pid, starttime):
    """pid＋starttime 還是同一個程序嗎（三態，spec 第 0 節）：

    - "gone"：pid 確定不在（或是殭屍），或 starttime 確定不同（pid 被重用）。
    - "alive"：在，而且 starttime 相同。
    - "unknown"：pid 在，但現在的 starttime 讀不到、或當初沒記到 starttime（K-05：不知道當活）。"""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return GONE
    if not pid_alive(pid):
        return GONE
    if starttime is None:
        return UNKNOWN
    cur = proc_starttime(pid)
    if cur is None:
        return UNKNOWN
    return ALIVE if cur == starttime else GONE


def all_pids():
    try:
        return [int(p) for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return []


def stat_of(pid):
    """回 (state, ppid, pgid) 或 None。"""
    try:
        with open("/proc/%d/stat" % pid) as f:
            rest = f.read().rsplit(")", 1)[1].split()
        return rest[0], int(rest[1]), int(rest[2])
    except (OSError, IndexError, ValueError):
        return None


def group_alive(pgid):
    """程序群組還有沒有成員（殭屍不算）。"""
    if not isinstance(pgid, int) or pgid <= 0:
        return False
    for pid in all_pids():
        st = stat_of(pid)
        if st and st[2] == pgid and st[0] != "Z":
            return True
    return False


def groups_with_descendants(pgid):
    """pgid 本身，加上這群組成員所有後代所在的群組（aos-exec 把 inst 的子程式開在另一個 session；proto7-1 P-05）。"""
    table = {p: stat_of(p) for p in all_pids()}
    table = {p: s for p, s in table.items() if s}
    members = {p for p, s in table.items() if s[2] == pgid}
    seen, todo = set(members), list(members)
    while todo:
        parent = todo.pop()
        for p, s in table.items():
            if s[1] == parent and p not in seen:
                seen.add(p)
                todo.append(p)
    return {pgid} | {table[p][2] for p in seen if p in table}


def is_runner(pid):
    """是 aos7-run（任務的包裝）嗎：它等任務死了自己寫 exit.json，不先殺它。"""
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            return any(a.endswith(b"aos7-run") for a in f.read().split(b"\0"))
    except OSError:
        return False


def environ_of(pid):
    try:
        with open("/proc/%d/environ" % pid, "rb") as f:
            return set(f.read().split(b"\0"))
    except OSError:
        return None


def want_env(node, tid=None, run=None):
    """身分掃描要比的環境變數集合。"""
    w = {b"AOS7_NODE=" + node.encode()}
    if tid is not None:
        w.add(b"AOS7_TID=" + tid.encode())
    if run is not None:
        w.add(b"AOS7_RUN=" + str(run).encode())
    return w


def env_procs(nodes, tid=None, run=None, skip=(), runners=False):
    """一次掃 `/proc/*/environ`（spec 5.2 身分掃描）：AOS7_NODE 在 nodes 裡、有 AOS7_TID（給了 tid 要相符）、
    給了 run 要 AOS7_RUN 相符的程序。預設不含 aos7-run。回 pid 清單。"""
    nodes = [nodes] if isinstance(nodes, str) else list(nodes)
    want_nodes = {b"AOS7_NODE=" + n.encode() for n in nodes}
    want_tid = None if tid is None else b"AOS7_TID=" + tid.encode()
    want_run = None if run is None else b"AOS7_RUN=" + str(run).encode()
    out = []
    for pid in all_pids():
        if pid in skip:
            continue
        env = environ_of(pid)
        if not env or not (env & want_nodes):
            continue
        if want_tid is not None:
            if want_tid not in env:
                continue
        elif not any(x.startswith(b"AOS7_TID=") for x in env):
            continue
        if want_run is not None and want_run not in env:
            continue
        st = stat_of(pid)
        if st and st[0] == "Z":
            continue
        if not runners and is_runner(pid):
            continue
        out.append(pid)
    return out


def me_and_ancestors():
    me = {os.getpid()}
    p = os.getppid()
    while p > 1 and p not in me:      # 不殺自己與祖先（子 daemon 本身也是某個 node 的任務）
        me.add(p)
        st = stat_of(p)
        p = st[1] if st else 1
    return me


def group_is_task(pgid, node, tid, run):
    """pid.json 的 pgid 真的是這個任務（這一次 run）的嗎：群組沒有活成員（沒東西可打），或有成員（或成員的父程序＝aos7-run）
    的環境是 NODE＋TID＋RUN。pid.json 在任務自己寫得到的槽裡，改了 pgid 的不能讓 kill 打到別人（spec 第 6 節）。"""
    if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 1:
        return False
    want = want_env(node, tid, run)
    members = [(p, st) for p, st in ((p, stat_of(p)) for p in all_pids()) if st and st[2] == pgid and st[0] != "Z"]
    if not members:
        return True
    for p, st in members:
        e = environ_of(p)
        pe = environ_of(st[1])
        if (e and want <= e) or (pe and want <= pe):
            return True
    return False


def kill_groups(groups, grace=KILL_GRACE):
    """對一組群組（各自連同後代的群組）SIGTERM，等至多 grace 秒，還在就 SIGKILL。回 True＝收乾淨。"""
    me = me_and_ancestors()
    allg = set()
    for g in groups:
        if isinstance(g, int) and g > 1:
            allg |= groups_with_descendants(g)
    my_groups = {stat_of(p)[2] for p in me if stat_of(p)}
    allg = {g for g in allg if g > 1 and g not in me and g not in my_groups}
    if not allg:
        return True
    for g in allg:
        try:
            os.killpg(g, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    end = time.monotonic() + grace
    while time.monotonic() < end:
        if not any(group_alive(g) for g in allg):
            return True
        time.sleep(0.02)
    for g in allg:
        try:
            os.killpg(g, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.05)
    return not any(group_alive(g) for g in allg)


def groups_of(pids):
    out = set()
    for pid in pids:
        st = stat_of(pid)
        if st:
            out.add(st[2])
    return out


def kill_identity(node, tid, run, pgid=None):
    """Q1 (a) 的範圍收一次 run：pid.json 的群組（先確認是這個任務的）、群組成員活著的後代所在的群組、
    環境變數 NODE＋TID＋RUN 相符的程序（含被 init 收養的）。回 (乾不乾淨, 說明)。"""
    me = me_and_ancestors()
    found = env_procs(node, tid, run, skip=me)
    groups = groups_of(found)
    note = ""
    if pgid is not None:
        if group_is_task(pgid, node, tid, run):
            groups.add(pgid)
        else:
            note = "；pid.json 的 pgid %r 不是這個任務的群組，沒動它" % (pgid,)
    if not groups:
        return True, "no process" + note
    clean = kill_groups(groups)
    return clean, ("killed %d group(s)" % len(groups) if clean else "still alive after SIGKILL") + note


def kill_node(node, known_pgids=()):
    """node 消失或取消登記時收它上面的任務（Q4、Q1）：daemon 記著的 pgid，加上環境變數 AOS7_NODE 是這個 node、有 AOS7_TID 的程序。
    回 (收到的群組數, 乾不乾淨)。aos7-run 不殺（任務死了它自己經 fd 寫 exit.json）。"""
    me = me_and_ancestors()
    groups = {g for g in known_pgids if isinstance(g, int) and g > 1}
    groups |= groups_of(env_procs(node, skip=me))
    if not groups:
        return 0, True
    return len(groups), kill_groups(groups)


def sweep_nodes(nodes):
    """daemon stop（帶 kill）的最後收尾：環境變數 AOS7_NODE 是 nodes 之一、有 AOS7_TID 的程序連同群組收掉（不含 aos7-run、自己與祖先）。"""
    me = me_and_ancestors()
    groups = groups_of(env_procs(list(nodes), skip=me))
    if not groups:
        return 0, True
    return len(groups), kill_groups(groups)
