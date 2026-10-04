"""程序工具：活不活、程序群組、身分掃描（環境變數 NODE＋TID＋RUN）、收程序（spec.md 2.6、5.2、6 節；Q1 範圍）。

起點複製自 proto7-1 lib/aos7_task.py 的「程序」一段；身分掃描多比 `AOS7_RUN`（同一個槽上一個 run 的殘留不算這次的）。
所有函式只讀 /proc 與送訊號，不留記憶體狀態。

daemon 在 node 消失／停止時呼叫，tick／tock 透過 aos7_task 判定與收程序（S-03、S-17）。
讀 /proc 的 stat、cmdline、environ；不寫協定檔，exit.json 留給 runner 或上層。

**三態一路傳到底（A2-01）**：/proc 讀取只分三種結果——讀到、確定不在（ENOENT／ESRCH：程序剛走）、讀不到（EIO、ESTALE…）。
讀不到一律丟 `ProcUnknown`，不再悄悄當成「沒有」：掃描不完整就不能支持 lost、清槽、重起，
收程序的確認也不能說「收乾淨了」。呼叫的人（aos7_task.judge／resolve、kill_identity、daemon 的收程序）接住它，
保留現狀、把原因記進 errors／last_error（spec §0）。

**environ 讀不到權限（EACCES／EPERM）＝不是可辨認的任務、略過**：別的 uid、不可 ptrace 的程序（systemd --user…）本來就這樣。
管理範圍（spec §11）：任務程序必須跟 daemon 同 uid、environ 可讀；脫離這個範圍的任務是誤用，核心不保證認得出它。
cmdline 是全世界可讀的，EACCES 不是常態，照一般讀取錯誤當不知道。"""
import errno
import os
import signal
import time

from aos7_fs import inject, proc_starttime

KILL_GRACE = 1.0   # spec 第 6 節：SIGTERM 後等至多 1 秒，還在就 SIGKILL

ALIVE, GONE, UNKNOWN = "alive", "gone", "unknown"

PROC_GONE_ERRNO = (errno.ENOENT, errno.ESRCH)   # 讀 /proc/<pid>/* 時這兩種＝程序已經不在


class ProcUnknown(Exception):
    """/proc 讀不完整（列不出 /proc、某個程序的 stat／environ／cmdline 讀不到）：掃描結果不能當「確定沒有」（A2-01）。"""


def _read_proc(pid, name, binary=False):
    """讀 `/proc/<pid>/<name>`：回內容；程序確定不在回 None；其他讀取錯誤丟 ProcUnknown（三態的唯一入口）。

    只有 environ 遇到 EACCES／EPERM 回 None（身分讀不到＝不是可辨認的任務，跟「不在」一樣略過）。
    stat、cmdline 本來全世界可讀，任何讀取錯誤都是「不知道」。"""
    path = "/proc/%d/%s" % (pid, name)
    try:
        inject("proc-" + name, path)
        with open(path, "rb" if binary else "r") as f:
            return f.read()
    except OSError as e:
        if e.errno in PROC_GONE_ERRNO:
            return None
        if name == "environ" and e.errno in (errno.EACCES, errno.EPERM):
            return None
        raise ProcUnknown("讀不到 %s：%r" % (path, e)) from None


def pid_state(pid):
    """pid 在不在（三態）：ALIVE／GONE（不存在或殭屍）／UNKNOWN（kill(0) 說在，但 stat 讀不到）。A2-01 前讀不到當死。"""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return GONE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return GONE
    except PermissionError:
        pass                                  # 在，只是不是我們的
    try:
        st = stat_of(pid)
    except ProcUnknown:
        return UNKNOWN
    if st is None:
        return GONE
    return GONE if st[0] == "Z" else ALIVE


def pid_alive(pid):
    """程序在不在（bool）：GONE 才是 False；UNKNOWN 保守算在（spec §0：不知道不能當否）。給測試與顯示用，判定請用 pid_state。"""
    return pid_state(pid) != GONE


def same_process(pid, starttime):
    """pid＋starttime 還是同一個程序嗎（三態，spec 第 0 節）：

    - "gone"：pid 確定不在（或是殭屍），或 starttime 確定不同（pid 被重用）。
    - "alive"：在，而且 starttime 相同。
    - "unknown"：pid 在但 /proc 讀不到、現在的 starttime 讀不到、或當初沒記到 starttime（K-05：不知道當活）。

    pid 是紀錄的程序號，starttime 是紀錄的啟動 tick；回 ALIVE／GONE／UNKNOWN（spec §5.4、P2-08）。"""
    ps = pid_state(pid)
    if ps != ALIVE:
        return ps
    # spec §5.4、P2-08：pid 還在也不等於身分已確定；缺啟動時間要保留 UNKNOWN。
    if starttime is None:
        return UNKNOWN
    cur = proc_starttime(pid)
    if cur is None:
        return UNKNOWN
    return ALIVE if cur == starttime else GONE


def all_pids():
    """列 /proc 的數字目錄回 pid 清單；列不出來丟 ProcUnknown（A2-01：空清單不能當「確定沒有程序」）。"""
    try:
        inject("proc-list", "/proc")
        return [int(p) for p in os.listdir("/proc") if p.isdigit()]
    except OSError as e:
        raise ProcUnknown("列不出 /proc：%r" % e) from None


def stat_of(pid):
    """回 (state, ppid, pgid)；程序確定不在回 None；讀不到或內容解析不了丟 ProcUnknown。"""
    text = _read_proc(pid, "stat")
    if text is None:
        return None
    try:
        rest = text.rsplit(")", 1)[1].split()
        return rest[0], int(rest[1]), int(rest[2])
    except (IndexError, ValueError):
        raise ProcUnknown("/proc/%d/stat 內容解析不了" % pid) from None


def _table():
    """一次掃完 /proc：回 {pid: (state, ppid, pgid)}，掃描中途走掉的程序不列；任何一個讀不到就丟 ProcUnknown。"""
    out = {}
    for p in all_pids():
        st = stat_of(p)
        if st:
            out[p] = st
    return out


def group_alive(pgid):
    """程序群組還有沒有成員（殭屍不算）：回 bool；掃描不完整丟 ProcUnknown（A2-01 前讀不到當「沒成員」）。"""
    if not isinstance(pgid, int) or pgid <= 0:
        return False
    return any(st[2] == pgid and st[0] != "Z" for st in _table().values())


def groups_with_descendants(pgid):
    """pgid 本身，加上這群組成員所有後代所在的群組（aos-exec 把 inst 的子程式開在另一個 session；proto7-1 P-05）。

    pgid 是起點群組；回群組號 set。掃描不完整丟 ProcUnknown，不拿半份表去決定要打哪些群組（spec §6、Q1）。"""
    table = _table()
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
    """是 aos7-run（任務的包裝）嗎：它等任務死了自己寫 exit.json，不先殺它。

    pid 是待辨識程序；回 bool，程序已不在回 False；cmdline 讀不到丟 ProcUnknown（spec §2.6、§5.3；A2-01）。"""
    data = _read_proc(pid, "cmdline", binary=True)
    return bool(data) and any(a.endswith(b"aos7-run") for a in data.split(b"\0"))


def environ_of(pid):
    """讀 /proc/<pid>/environ；回 bytes 環境項目的 set；程序已不在、環境是空的、或沒有權限讀（別的 uid、不可 ptrace）回 None；
    其他讀不到丟 ProcUnknown。"""
    data = _read_proc(pid, "environ", binary=True)
    return set(data.split(b"\0")) if data else None


def want_env(node, tid=None, run=None):
    """身分掃描要比的環境變數集合。

    node 是 node 絕對路徑；tid／run 可省略，指定時加入比對。回 bytes 項目的 set（spec §5.2）。"""
    w = {b"AOS7_NODE=" + node.encode()}
    if tid is not None:
        w.add(b"AOS7_TID=" + tid.encode())
    if run is not None:
        w.add(b"AOS7_RUN=" + str(run).encode())
    return w


def env_procs(nodes, tid=None, run=None, skip=(), runners=False):
    """一次掃 `/proc/*/environ`（spec 5.2 身分掃描）：AOS7_NODE 在 nodes 裡、有 AOS7_TID（給了 tid 要相符）、
    給了 run 要 AOS7_RUN 相符的程序。預設不含 aos7-run。回 pid 清單。

    nodes 可為單一路徑或可迭代路徑集；skip 是排除 pid，runners=True 才包含包裝程序。
    回空清單＝**掃完了、確定沒有**；掃描不完整（列不出 /proc、environ 讀不到…）丟 ProcUnknown（spec §0、§5.2；A2-01）。"""
    nodes = [nodes] if isinstance(nodes, str) else list(nodes)
    want_nodes = {b"AOS7_NODE=" + n.encode() for n in nodes}
    want_tid = None if tid is None else b"AOS7_TID=" + tid.encode()
    # spec §5.2：槽名跨 run 重用；加上 RUN 才不把前任殘留當成本次任務。
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
        if st is None or st[0] == "Z":
            continue
        if not runners and is_runner(pid):
            continue
        out.append(pid)
    return out


def me_and_ancestors():
    """無參數；回自己與祖先的 pid set，供 P2-14 排除收程序時不能打到的管理鏈（spec §2.7、§6）。
    祖先的 stat 讀不到丟 ProcUnknown：認不出管理鏈就不能放心送訊號（A2-01）。"""
    me = {os.getpid()}
    p = os.getppid()
    while p > 1 and p not in me:      # 不殺自己與祖先（子 daemon 本身也是某個 node 的任務）
        me.add(p)
        st = stat_of(p)
        p = st[1] if st else 1
    return me


def group_is_task(pgid, node, tid, run):
    """pid.json 的 pgid 還能打嗎：群組沒有活成員＝True（沒東西可打）；有成員的環境含這個 run 的 NODE＋TID＋RUN＝True；
    否則 False。防的是 pgid 被重用（外部故障）：pid.json 記的群組號後來給了別人，kill 不能打過去（spec 第 6 節）。

    pgid 是待核對群組，node／tid／run 是目標身分；回 bool。掃描不完整丟 ProcUnknown。"""
    if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 1:
        return False
    want = want_env(node, tid, run)
    members = [p for p, st in _table().items() if st[2] == pgid and st[0] != "Z"]
    if not members:
        return True
    return any(want <= (environ_of(p) or set()) for p in members)


def kill_groups(groups, grace=KILL_GRACE):
    """對一組群組（各自連同後代的群組）SIGTERM，等至多 grace 秒，還在就 SIGKILL。回 True＝確定收乾淨。

    groups 是群組號集合，grace 是寬限秒數；不送訊號給自己／祖先群組（P2-14）。
    掃描不完整丟 ProcUnknown（送訊號之前）；送完之後確認不了＝回 False（不能說收乾淨；A2-01）。"""
    me = me_and_ancestors()
    allg = set()
    for g in groups:
        if isinstance(g, int) and g > 1:
            allg |= groups_with_descendants(g)
    # spec §2.7、P2-14：子 daemon 本身也是任務，排除整個祖先群組才不會收掉管理鏈。
    my_groups = {st[2] for st in (stat_of(p) for p in me) if st}
    allg = {g for g in allg if g > 1 and g not in me and g not in my_groups}
    if not allg:
        return True

    def any_alive():
        """還有沒有群組活著；確認不了當「還活著」（不能宣稱收乾淨）。"""
        try:
            return any(group_alive(g) for g in allg)
        except ProcUnknown:
            return True
    for g in allg:
        try:
            os.killpg(g, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    end = time.monotonic() + grace
    while time.monotonic() < end:
        if not any_alive():
            return True
        time.sleep(0.02)
    for g in allg:
        try:
            os.killpg(g, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.05)
    return not any_alive()


def groups_of(pids):
    """pids 是程序號集合；回這些程序的 pgid set（掃描中途走掉的略過；讀不到丟 ProcUnknown）。"""
    out = set()
    for pid in pids:
        st = stat_of(pid)
        if st:
            out.add(st[2])
    return out


def kill_identity(node, tid, run, pgid=None, task=None):
    """Q1 (a) 的範圍收一次 run：pid.json 的群組（先確認是這個任務的）、群組成員活著的後代所在的群組、
    環境變數 NODE＋TID＋RUN 相符的程序（含被 init 收養的）。回 (乾不乾淨, 說明)。

    node／tid／run 指定唯一一次執行，pgid 可帶紀錄的群組；task＝pid.json 的 (pid, starttime)。回 (bool, 字串)。
    身分核對不了的群組不打。/proc 掃描不完整回 (False, 說明)：不知道有沒有收乾淨，呼叫的人當「不知道」處理（spec §6）。
    最後再看一次 pid.json 記的任務程序：它還活著（或認不出死了沒）就不能回「收乾淨」，即使群組沒打（回條不能說謊）。"""
    try:
        me = me_and_ancestors()
        found = env_procs(node, tid, run, skip=me)
        groups = groups_of(found)
        note = ""
        # spec §6：pid.json 是任務能改的檔，不能只相信其中的 pgid 就向別人送訊號。
        if pgid is not None:
            if group_is_task(pgid, node, tid, run):
                groups.add(pgid)
            else:
                note = "；pid.json 的 pgid %r 不是這個任務的群組，沒動它" % (pgid,)
        clean = kill_groups(groups) if groups else True
    except ProcUnknown as e:
        return False, "unknown：/proc 讀不完整，不知道有沒有收乾淨（%s）" % e
    if task and task[0]:
        ts = same_process(task[0], task[1])
        if ts != GONE:
            return False, "unknown：pid.json 記的任務程序 %d %s，不能說收乾淨%s" % (
                task[0], "還活著" if ts == ALIVE else "認不出死了沒", note)
    if not groups:
        return True, "no process" + note
    return clean, ("killed %d group(s)" % len(groups) if clean else "still alive after SIGKILL") + note


def kill_node(node, known_pgids=()):
    """node 消失或取消登記時收它上面的任務（Q4、Q1）：daemon 記著的 pgid，加上環境變數 AOS7_NODE 是這個 node、有 AOS7_TID 的程序。
    回 (收到的群組數, 乾不乾淨)。aos7-run 不殺（任務死了它自己經 fd 寫 exit.json）。

    node 是 node 絕對路徑，known_pgids 是 daemon 記住的群組；沒有群組回 (0, True)。
    /proc 掃描不完整時只打記住的群組、回 clean=False（不能說收乾淨；spec §2.6、§11；A2-01）。"""
    groups = {g for g in known_pgids if isinstance(g, int) and g > 1}
    try:
        me = me_and_ancestors()
        groups |= groups_of(env_procs(node, skip=me))
        if not groups:
            return 0, True
        return len(groups), kill_groups(groups)
    except ProcUnknown:
        # spec §2.6：掃描不完整時只打記著的群組（astra-2 讀碼：以前這裡直接回 False，連記著的群組都沒收）
        try:
            if groups:
                kill_groups(groups)
        except ProcUnknown:
            pass
        return len(groups), False


def sweep_nodes(nodes):
    """daemon stop（帶 kill）的最後收尾：環境變數 AOS7_NODE 是 nodes 之一、有 AOS7_TID 的程序連同群組收掉（不含 aos7-run、自己與祖先）。

    nodes 是 node 路徑集合；回 (群組數, bool)，掃不到回 (0, True)，掃描不完整回 (0, False)。
    這次補掃補上時間線收尾途中才出現的任務，仍以 Q1 範圍為界（spec §2.7）。"""
    try:
        me = me_and_ancestors()
        groups = groups_of(env_procs(list(nodes), skip=me))
        if not groups:
            return 0, True
        return len(groups), kill_groups(groups)
    except ProcUnknown:
        return 0, False
