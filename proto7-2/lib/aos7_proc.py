"""程序工具（spec.md 2.6、5.2、6 節；Q1 範圍）：程序的事實、程序群組、身分掃描（環境變數 NODE＋TID＋RUN）、收程序。
只讀 /proc、送訊號，不寫檔、不留狀態。單一程序的事實只經 `proc(pid)`：(N) 確定不在或殭屍、(OK, starttime)、(U, 說明)。
掃描讀不到一律丟 `aos7_fs.Unknown`（kind "proc"），不當「沒有」：掃描不完整就不能支持 lost、清槽、重起，也不能說「收乾淨了」。
environ 沒有權限讀＝不是可辨認的任務、略過（任務必須跟 daemon 同 uid、environ 可讀，spec §11）；stat、cmdline 讀不到照常是不知道。"""
import errno
import os
import signal
import time

from aos7_fs import N, OK, U, Unknown, inject, is_int, proc_starttime

KILL_GRACE = 1.0   # SIGTERM 後最多等 1 秒，還在就 SIGKILL
ALIVE, GONE, UNKNOWN = "alive", "gone", "unknown"


def _read_proc(pid, name, binary=False):
    """讀 `/proc/<pid>/<name>`：程序確定不在（ENOENT／ESRCH）或 environ 沒有權限讀回 None；其他讀不到丟 Unknown。"""
    path = "/proc/%d/%s" % (pid, name)
    try:
        inject("proc-" + name, path)
        with open(path, "rb" if binary else "r") as f:
            return f.read()
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ESRCH) or (name == "environ" and e.errno in (errno.EACCES, errno.EPERM)):
            return None
        raise Unknown("讀不到 %s：%r" % (path, e), kind="proc") from None


def proc(pid):
    """一個程序的事實：(N, None) 確定不在（含殭屍）｜(OK, starttime)｜(U, 說明) 在，但 /proc 讀不到。"""
    if not is_int(pid) or pid <= 0:
        return N, None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return N, None
    except PermissionError:
        pass                                  # 在，只是不是我們的
    try:
        st = stat_of(pid)
    except Unknown as e:
        return U, str(e)
    if st is None or st[0] == "Z":
        return N, None
    t = proc_starttime(pid)
    return (OK, t) if t is not None else (U, "/proc/%d/stat 的 starttime 讀不到" % pid)


def pid_alive(pid):
    """程序在不在：只有確定不在才是 False（不知道不能當否）。給顯示與測試用。"""
    return proc(pid)[0] != N


def same_process(pid, starttime):
    """pid＋starttime 還是同一個程序嗎：GONE（不在、殭屍、或 starttime 不同＝pid 被重用）｜ALIVE｜
    UNKNOWN（讀不到，或當初沒記到 starttime；判定照「不知道當活」）。"""
    st, cur = proc(pid)
    if st == N:
        return GONE
    if st == U or starttime is None:
        return UNKNOWN
    return ALIVE if cur == starttime else GONE


def all_pids():
    """/proc 底下所有 pid；列不出來丟 Unknown（空清單不能當「確定沒有程序」）。"""
    try:
        inject("proc-list", "/proc")
        return [int(p) for p in os.listdir("/proc") if p.isdigit()]
    except OSError as e:
        raise Unknown("列不出 /proc：%r" % e, kind="proc") from None


def stat_of(pid):
    """(state, ppid, pgid)；程序確定不在回 None；讀不到或解析不了丟 Unknown。"""
    text = _read_proc(pid, "stat", binary=True)
    if text is None:
        return None
    try:
        rest = text.rsplit(b")", 1)[1].split()
        return rest[0].decode("ascii"), int(rest[1]), int(rest[2])
    except (IndexError, ValueError):
        raise Unknown("/proc/%d/stat 內容解析不了" % pid, kind="proc") from None


def _table():
    """一次掃完 /proc：{pid: (state, ppid, pgid)}（掃描中途走掉的不列）；任何一個讀不到就丟 Unknown。"""
    return {p: st for p, st in ((p, stat_of(p)) for p in all_pids()) if st}


def group_alive(pgid):
    """程序群組還有沒有活成員（殭屍不算）。"""
    return is_int(pgid) and pgid > 0 and any(st[2] == pgid and st[0] != "Z" for st in _table().values())


def groups_with_descendants(pgid):
    """pgid 本身，加上群組成員所有後代所在的群組（aos-exec 把 inst 的子程式開在另一個 session，也要收得到）。"""
    table = _table()
    seen = {p for p, s in table.items() if s[2] == pgid}
    todo = list(seen)
    while todo:
        parent = todo.pop()
        for p, s in table.items():
            if s[1] == parent and p not in seen:
                seen.add(p)
                todo.append(p)
    return {pgid} | {table[p][2] for p in seen}


def is_runner(pid):
    """是 aos7-run 嗎：它等任務死了自己寫 exit.json，不先殺它。"""
    data = _read_proc(pid, "cmdline", binary=True)
    return bool(data) and any(a.endswith(b"aos7-run") for a in data.split(b"\0")[:2])


def environ_of(pid):
    """/proc/<pid>/environ 的項目 set；程序不在、環境是空的、沒有權限讀回 None。"""
    data = _read_proc(pid, "environ", binary=True)
    return set(data.split(b"\0")) if data else None


def env_procs(nodes, tid=None, run=None, skip=(), runners=False):
    """身分掃描（spec 5.2）：AOS7_NODE 在 nodes 裡、有 AOS7_TID（給了 tid 要相符）、給了 run 要 AOS7_RUN 相符的活程序 pid。
    槽名跨 run 重用，比 RUN 才不會把前任的殘留算成這次的。預設不含 aos7-run。回空清單＝掃完了、確定沒有。"""
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
        if (want_tid not in env) if want_tid is not None else not any(x.startswith(b"AOS7_TID=") for x in env):
            continue
        if want_run is not None and want_run not in env:
            continue
        st = stat_of(pid)
        if st is None or st[0] == "Z" or (not runners and is_runner(pid)):
            continue
        out.append(pid)
    return out


def me_and_ancestors():
    """自己與祖先的 pid（子 daemon 本身也是某個 node 的任務：收程序絕不能打到管理鏈）。祖先讀不到丟 Unknown。"""
    me = {os.getpid()}
    p = os.getppid()
    while p > 1 and p not in me:
        me.add(p)
        st = stat_of(p)
        p = st[1] if st else 1
    return me


def group_is_task(pgid, node, tid, run):
    """pid.json 的 pgid 還能打嗎：群組沒有活成員（沒東西可打）、或有成員的環境是這個 run 的 NODE＋TID＋RUN。
    防 pgid 被重用（外部故障）：記的群組號後來給了別人，kill 不能打過去。任務自己改 pgid 是誤用。"""
    if not is_int(pgid) or pgid <= 1:
        return False
    want = {b"AOS7_NODE=" + node.encode(), b"AOS7_TID=" + tid.encode(), b"AOS7_RUN=" + str(run).encode()}
    members = [p for p, st in _table().items() if st[2] == pgid and st[0] != "Z"]
    return not members or any(want <= (environ_of(p) or set()) for p in members)


def group_is_node(pgid, nodes):
    """記著的 pgid 沒有活成員、或有成員屬於這些 node 才能打（防群組號重用）。"""
    if not is_int(pgid) or pgid <= 1:
        return False
    nodes = [nodes] if isinstance(nodes, str) else nodes
    want = {b"AOS7_NODE=" + n.encode() for n in nodes}
    members = [p for p, st in _table().items() if st[2] == pgid and st[0] != "Z"]
    return not members or any(want & (environ_of(p) or set()) for p in members)


def _signal(groups, sig):
    for g in groups:
        try:
            os.killpg(g, sig)
        except (ProcessLookupError, PermissionError):
            pass


def kill_groups(groups, grace=KILL_GRACE):
    """對一組群組（連同後代的群組）SIGTERM，最多等 grace 秒，還在就 SIGKILL。回 True＝確定收乾淨。
    不打自己與祖先所在的群組。送訊號前掃描不完整丟 Unknown；送完確認不了＝回 False（不能說收乾淨）。"""
    me = me_and_ancestors()
    allg = set()
    for g in groups:
        if is_int(g) and g > 1:
            allg |= groups_with_descendants(g)
    my_groups = {st[2] for st in (stat_of(p) for p in me) if st}
    allg = {g for g in allg if g > 1 and g not in me and g not in my_groups}
    if not allg:
        return True

    def any_alive():
        try:
            return any(group_alive(g) for g in allg)
        except Unknown:
            return True
    _signal(allg, signal.SIGTERM)
    end = time.monotonic() + grace
    while time.monotonic() < end:
        if not any_alive():
            return True
        time.sleep(0.02)
    _signal(allg, signal.SIGKILL)
    time.sleep(0.05)
    return not any_alive()


def groups_of(pids):
    """這些程序的 pgid（掃描中途走掉的略過）。"""
    return {st[2] for st in (stat_of(p) for p in pids) if st}


def _kill_remaining(nodes, tid=None, run=None):
    """清場後再身分掃描，最多補收三輪；最後掃空才算收斂。"""
    ok = True
    for _ in range(3):
        pids = env_procs(nodes, tid, run, skip=me_and_ancestors())
        if not pids:
            return ok
        ok = kill_groups(groups_of(pids)) and ok
    return ok and not env_procs(nodes, tid, run, skip=me_and_ancestors())


def kill_identity(node, tid, run, pgid=None, task=None):
    """照 Q1 (a) 的範圍收一次 run，回 (乾不乾淨, 說明)：pid.json 的群組（先確認還是這個任務的）、群組成員的後代所在的群組、
    環境變數 NODE＋TID＋RUN 相符的程序（含被 init 收養的）。/proc 掃描不完整回 (False, "unknown…")。
    task＝pid.json 的 (pid, starttime)：最後再看一次它，還活著或認不出死了沒就不能回「收乾淨」（回條不能說謊）。"""
    try:
        groups = groups_of(env_procs(node, tid, run, skip=me_and_ancestors()))
        note = ""
        if pgid is not None:   # pid.json 是任務寫得到的檔：不能只信它的 pgid 就向別人送訊號
            if group_is_task(pgid, node, tid, run):
                groups.add(pgid)
            else:
                note = "；pid.json 的 pgid %r 不是這個任務的群組，沒動它" % (pgid,)
        clean = kill_groups(groups) if groups else True
        clean = _kill_remaining(node, tid, run) and clean
    except Unknown as e:
        return False, "unknown：/proc 讀不完整，不知道有沒有收乾淨（%s）" % e
    if task and task[0]:
        ts = same_process(task[0], task[1])
        if ts != GONE:
            return False, "unknown：pid.json 記的任務程序 %d %s，不能說收乾淨%s" % (
                task[0], "還活著" if ts == ALIVE else "認不出死了沒", note)
    if not groups and clean:
        return True, "no process" + note
    return clean, ("killed %d group(s)" % len(groups) if clean else "still alive after SIGKILL") + note


def kill_node(nodes, known_pgids=()):
    """收一個或幾個 node 上的任務（node 消失、取消登記、stop 帶 kill 的最後補掃）：記著的 pgid（先重驗，有活成員卻都不屬這些
    node 的不打，防群組號重用），加上環境 AOS7_NODE 是它們、
    有 AOS7_TID 的程序（aos7-run 不殺，任務死了它自己寫 exit.json）。回 (群組數, 乾不乾淨)。
    掃描不完整時照樣打記著的群組，回 clean=False。"""
    groups = {g for g in known_pgids if is_int(g) and g > 1}
    try:
        for g in list(groups):
            if not group_is_node(g, nodes):
                groups.discard(g)   # 確定是外人的群組：之後掃描不完整也不打
        groups |= groups_of(env_procs(nodes, skip=me_and_ancestors()))
        clean = kill_groups(groups) if groups else True
        return len(groups), _kill_remaining(nodes) and clean
    except Unknown:
        try:
            if groups:
                kill_groups(groups)
        except Unknown:
            pass
        return len(groups), False
