"""任務資料夾的共用邏輯：列任務、判斷狀態、kill、執行 ctl.json、寫 spawn、起任務（spec.md 第 4～6 節）。

tick、tock、daemon 共用；kernel 也可以 import `list_tasks`／`task_state`／`is_live` 來看任務。
所有函式只讀寫檔案與送訊號，不留任何記憶體狀態。
"""
import os
import re
import signal
import subprocess
import sys
import time

import aos7_mount
from aos7_fs import BIN, env_with_bin, node_path, now, read_json, tail_jsonl, write_json


KILL_GRACE = 1.0   # spec 第 6 節：SIGTERM 後等至多 1 秒，還在就 SIGKILL
LIVE_STATES = ("born", "live")


# ---------- 路徑 ----------

def tasks_dir(node):
    """`<node>/.aos/tasks/`。"""
    return os.path.join(node, ".aos", "tasks")


def task_dir(node, tid):
    return os.path.join(tasks_dir(node), tid)


def old_dir(node):
    """`<node>/.aos/tasks-old/`：tock 把結束超過 keep_ended_rounds 回合的任務資料夾搬來這裡（Q3）。"""
    return os.path.join(node, ".aos", "tasks-old")


def find_task_dir(node, tid):
    """tid 的資料夾：先找 tasks/，再找 tasks-old/；都沒有回 None。"""
    for d in (task_dir(node, tid), os.path.join(old_dir(node), tid)):
        if os.path.isdir(d):
            return d
    return None


def last_logged_round(node):
    """rounds.jsonl 最後幾行裡最大的整數 round（round.json 壞掉時接著數用；probes/chaos B6）；沒有回 None。"""
    rows = tail_jsonl(os.path.join(node, ".aos", "rounds.jsonl"), 20)
    rs = [x.get("round") for x in rows if isinstance(x, dict)]
    rs = [r for r in rs if isinstance(r, int) and not isinstance(r, bool)]
    return max(rs) if rs else None


def list_tasks(node):
    """回這個 node 所有任務的 tid（排序過）。node 是絕對路徑。"""
    try:
        return sorted(d for d in os.listdir(tasks_dir(node))
                      if os.path.isfile(os.path.join(tasks_dir(node), d, "birth.json")))
    except OSError:
        return []


def birth_of(tdir):
    """讀 birth.json；壞掉或不是物件回 {}（任務自己改壞也不拖垮 tick／tock；astra-4 I-05）。"""
    b = read_json(os.path.join(tdir, "birth.json"))
    return b if isinstance(b, dict) else {}


def name_of(tdir):
    """任務的 name：birth.json 的，讀不到就從 tid 推（`<name>-r<回合>[-k]`），免得 keep 以為沒有活實例又起一份。"""
    n = birth_of(tdir).get("name")
    if isinstance(n, str) and n:
        return n
    return re.sub(r"-r\d+(-\d+)?$", "", os.path.basename(tdir))


# ---------- 程序 ----------

def pid_alive(pid):
    """程序在不在（殭屍算不在）。"""
    if not isinstance(pid, int) or pid <= 0:
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


def group_alive(pgid):
    """程序群組還有沒有成員（殭屍不算）。"""
    if not isinstance(pgid, int) or pgid <= 0:
        return False
    for pid in _all_pids():
        st = _stat(pid)
        if st and st[2] == pgid and st[0] != "Z":
            return True
    return False


def _all_pids():
    return [int(p) for p in os.listdir("/proc") if p.isdigit()]


def _stat(pid):
    """回 (state, ppid, pgid) 或 None。"""
    try:
        with open("/proc/%d/stat" % pid) as f:
            rest = f.read().rsplit(")", 1)[1].split()
        return rest[0], int(rest[1]), int(rest[2])
    except (OSError, IndexError, ValueError):
        return None


def _groups_with_descendants(pgid):
    """pgid 本身，加上這群組成員所有後代所在的群組。

    為什麼要後代：搬來的 aos-exec 會把 inst 的子程式開在**另一個 session**，
    只殺 aos-exec 的群組收不到它（problems-core.md P-05）。"""
    table = {p: _stat(p) for p in _all_pids()}
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


def _is_runner(pid):
    """是 aos7-run（任務的包裝）嗎：它等任務死了自己寫 exit.json，不能先殺它。"""
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            return any(a.endswith(b"aos7-run") for a in f.read().split(b"\0"))
    except OSError:
        return False


def _env_has(pid, want):
    try:
        with open("/proc/%d/environ" % pid, "rb") as f:
            return want <= set(f.read().split(b"\0"))
    except OSError:
        return False


def group_is_task(pgid, tid, node):
    """pid.json 的 pgid 真的是這個任務的嗎：群組沒有活成員（沒東西可打），或有成員（或成員的父程序＝aos7-run）
    的環境變數 AOS7_TID＋AOS7_NODE 是這個任務。pid.json 在任務自己寫得到的 taskdir，改了 pgid 的不能讓 kill 打到別人（probes/chaos B7）。"""
    if not isinstance(pgid, int) or pgid <= 1:
        return False
    want = {b"AOS7_NODE=" + node.encode(), b"AOS7_TID=" + tid.encode()}
    members = [(p, st) for p, st in ((p, _stat(p)) for p in _all_pids()) if st and st[2] == pgid and st[0] != "Z"]
    if not members:
        return True
    return any(_env_has(p, want) or _env_has(st[1], want) for p, st in members)


def _escaped(tid, node, skip):
    """環境變數 AOS7_TID、AOS7_NODE 都是這個任務、但已經不是後代的程序（雙 fork、setsid 後被 init 收養；probes/polyglot N5）。
    tid 給 None＝這個 node 的任何任務（有 AOS7_TID 就算；node 消失時用，Q4）。"""
    want = {b"AOS7_NODE=" + node.encode()}
    if tid is not None:
        want.add(b"AOS7_TID=" + tid.encode())
    out = []
    for pid in _all_pids():
        if pid in skip:
            continue
        try:
            with open("/proc/%d/environ" % pid, "rb") as f:
                env = set(f.read().split(b"\0"))
        except OSError:
            continue
        if want <= env and (tid is not None or any(x.startswith(b"AOS7_TID=") for x in env)) and not _is_runner(pid):
            out.append(pid)
    return out


def kill_group(pgid, grace=KILL_GRACE, also=()):
    """對 pgid（連同後代的群組）與 also（另外找到的程序所在的群組）送 SIGTERM，等至多 grace 秒，還在就 SIGKILL。回 True＝收乾淨。"""
    groups = _groups_with_descendants(pgid)
    for pid in also:
        st = _stat(pid)
        if st:
            groups |= _groups_with_descendants(st[2])
    for g in groups:
        try:
            os.killpg(g, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    end = time.monotonic() + grace
    while time.monotonic() < end:
        if not any(group_alive(g) for g in groups):
            return True
        time.sleep(0.02)
    for g in groups:
        try:
            os.killpg(g, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.05)
    return not any(group_alive(g) for g in groups)


# ---------- 狀態 ----------

def task_state(tdir):
    """回任務狀態字串（spec 第 5 節）：

    - "ended"：有 exit.json
    - "live"：有 pid.json，任務程序或 aos7-run 還在
    - "lost"：有 pid.json，任務與 aos7-run 都不在，又沒 exit.json
    - "born"：只有 birth.json（剛起，算活）
    """
    if os.path.exists(os.path.join(tdir, "exit.json")):
        return "ended"
    pid = read_json(os.path.join(tdir, "pid.json"))
    if not isinstance(pid, dict) or not pid:
        return "born"
    if pid_alive(pid.get("pid")) or pid_alive(pid.get("runner_pid")):
        return "live"
    # aos7-run 可能剛好在這一瞬間寫完 exit.json（P-07），再看一次
    if os.path.exists(os.path.join(tdir, "exit.json")):
        return "ended"
    return "lost"


def is_live(state):
    return state in LIVE_STATES


def live_tasks(node):
    """回 node 上活著（born 或 live）的 tid 清單。"""
    return [t for t in list_tasks(node) if is_live(task_state(task_dir(node, t)))]


# ---------- 控制 ----------

def kill_task(tdir):
    """kill 一個任務，回 (ok, msg)。已結束當成功。"""
    if os.path.exists(os.path.join(tdir, "exit.json")):
        # 主程序結束了，但它開的子孫可能還在（astra-4 I-04）：照樣找環境變數是這個任務的程序收掉
        tid = os.path.basename(tdir)
        node = os.path.dirname(os.path.dirname(os.path.dirname(tdir)))
        left = _escaped(tid, node, {os.getpid()})
        if not left:
            return True, "already ended"
        st = _stat(left[0])
        clean = kill_group(st[2] if st else left[0], also=left)
        return clean, "already ended; %d leftover process(es) %s" % (len(left), "killed" if clean else "still alive")
    end = time.monotonic() + KILL_GRACE
    pid = read_json(os.path.join(tdir, "pid.json"))
    while not isinstance(pid, dict) and time.monotonic() < end:   # 剛起、aos7-run 還沒寫 pid.json
        time.sleep(0.02)
        pid = read_json(os.path.join(tdir, "pid.json"))
    if not pid:
        return False, "no pid.json"
    node = os.path.dirname(os.path.dirname(os.path.dirname(tdir)))
    tid = os.path.basename(tdir)
    also = _escaped(tid, node, {os.getpid(), pid.get("runner_pid")})
    if not group_is_task(pid.get("pgid"), tid, node):
        # pid.json 被改過（或 pgid 壞掉）：不打那個群組，只收環境變數相符的
        if also:
            st = _stat(also[0])
            clean = kill_group(st[2] if st else also[0], also=also)
        else:
            clean = True
        return False, "pid.json 的 pgid %r 不是這個任務的群組，沒動它；環境變數相符的 %d 個程序%s" % (
            pid.get("pgid"), len(also), "收掉了" if clean else "沒收乾淨")
    clean = kill_group(pid.get("pgid"), also=also)
    return clean, "killed" if clean else "still alive after SIGKILL"


def kill_node_procs(node, known=(), skip=()):
    """node 消失時收掉它上面的任務（Q4）：known＝daemon 平常記著的 [(pgid, runner_pid)]（只用 pgid），
    再加上環境變數 AOS7_NODE 是這個 node 的程序（pid.json 跟著資料夾被刪了也找得到）。回收到的群組數與乾不乾淨。"""
    me = {os.getpid()}
    p = os.getppid()
    while p > 1 and p not in me:      # 不殺自己與祖先（子 daemon 本身也是某個 node 的任務）
        me.add(p)
        st = _stat(p)
        p = st[1] if st else 1
    groups = set()
    for pgid, _runner in known:
        if isinstance(pgid, int) and pgid > 1 and pgid not in me:
            groups.add(pgid)
    left = _escaped(None, node, me)
    for pid in left:
        st = _stat(pid)
        if st and st[2] not in me:
            groups.add(st[2])
    clean = True
    for g in sorted(groups):
        clean = kill_group(g) and clean
    return len(groups), clean   # aos7-run 不殺：任務死了它自己經 fd 寫 exit.json（搬家時寫到新位置）


def write_spawn(node, fname, item):
    """寫 `<node>/.aos/spawn/<fname>.json`：請下個 tick 起一個任務。"""
    write_json(os.path.join(node, ".aos", "spawn", fname + ".json"), item)


def run_ctl(node, tid):
    """執行 `<taskdir>/ctl.json`（若有），搬成 ctl-done.json。回紀錄 dict 或 None。"""
    tdir = task_dir(node, tid)
    path = os.path.join(tdir, "ctl.json")
    ctl = read_json(path)
    if ctl is None and not os.path.exists(path):
        return None
    bad = None
    if not isinstance(ctl, dict):         # 讀不懂或不是物件（例如 `[]`）：寫失敗回條、搬走，不拖垮 tick（同 daemon ctl）
        bad = "unreadable JSON" if ctl is None else "not a JSON object"
        ctl = {"raw": "unreadable" if ctl is None else ctl}
    op = ctl.get("op")
    if bad:
        ok, msg = False, bad
    elif op == "kill":
        ok, msg = kill_task(tdir)
    elif op == "restart":
        ok, msg = kill_task(tdir)
        birth = birth_of(tdir)
        item = {k: birth[k] for k in ("name", "argv", "inst", "subroot") if k in birth}
        item["mounts"] = aos7_mount.decl_of(birth)   # 新任務照原本的宣告重新掛
        item["restart_of"] = tid
        write_spawn(node, "restart-" + tid, item)
        msg += "; spawn written"
    else:
        ok, msg = False, "unknown op %r" % op
    ctl["result"] = {"ok": ok, "msg": msg, "at": now()}
    write_json(os.path.join(tdir, "ctl-done.json"), ctl)
    try:
        os.remove(path)
    except OSError:
        pass
    return {"tid": tid, "op": op, "ok": ok}


def run_all_ctl(node):
    """對 node 每個任務執行 ctl.json，回紀錄清單。"""
    out = []
    for tid in list_tasks(node):
        r = run_ctl(node, tid)
        if r:
            out.append(r)
    return out


# ---------- 起任務 ----------

def new_tid(node, name, rnd):
    """`<name>-r<回合>`，撞名加 -2、-3。"""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name or "task")
    base = "%s-r%d" % (safe, rnd)
    tid, n = base, 1
    while os.path.exists(task_dir(node, tid)) or os.path.exists(os.path.join(old_dir(node), tid)):
        n += 1
        tid = "%s-%d" % (base, n)
    return tid


def start_task(root, node_id, item, rnd):
    """建掛載點、寫 birth.json，用 aos7-run 起任務（新 session，不等）。回 tid。"""
    root = os.path.abspath(root)
    node = node_path(root, node_id)
    tid = new_tid(node, item.get("name"), rnd)
    tdir = task_dir(node, tid)
    os.makedirs(tdir, exist_ok=True)   # 先佔住 tid，掛載點建在裡面
    birth = {"tid": tid, "name": item.get("name") or "task", "node": node_id, "round": rnd,
             "mounts": aos7_mount.make(root, tdir, item.get("mounts") or {}),
             "at": now(), "restart_of": item.get("restart_of")}
    if item.get("spawn"):
        birth["spawn"] = item["spawn"]   # 從哪個 spawn 檔起的（追得到請求的去向；astra-4 I-02）
    sub = item.get("subroot")
    if isinstance(sub, str):
        # 這個任務要在 sub 開子 daemon（路一）：先建 `<sub>/.aosd/`，父 daemon 掃描就跳過它，
        # 不會在子 daemon 起來前把裡面的 node 當自己的（P-11；probes/nest3 N3）
        good, bad = aos7_mount.check({"subroot": sub})
        sp = node_path(root, good["subroot"]) if good else None
        if good and aos7_mount.in_root(root, good["subroot"]) and os.path.realpath(sp).startswith(
                os.path.realpath(node) + os.sep):
            os.makedirs(os.path.join(sp, ".aosd"), exist_ok=True)
            birth["subroot"] = good["subroot"]
        else:
            # 子根要在任務自己的 node 底下、不能是 node 本身（S-10；probes/llmteam 誤解 2：寫成 "sub" 就在空間根建了 .aosd）
            birth["subroot_error"] = (bad or ["subroot %s 要在自己的 node（%s）底下" % (sub, node_id)])[0]
    if "inst" in item:
        birth["inst"] = item["inst"]
    else:
        birth["argv"] = item.get("argv", [])
    write_json(os.path.join(tdir, "birth.json"), birth)
    env = env_with_bin()
    env.update({"AOS7_ROOT": root, "AOS7_NODE": node, "AOS7_NODE_ID": node_id,
                "AOS7_TASK": tdir, "AOS7_TID": tid})
    env.pop("AOS7_SUBROOT", None)   # 子 daemon 起的任務不要繼承父任務的
    if birth.get("subroot"):
        # 子根的絕對路徑：argv 寫 ["aos7-daemon", "$AOS7_SUBROOT"]，不必管 cwd 是 node（probes/llmteam 誤解 1）
        env["AOS7_SUBROOT"] = node_path(root, birth["subroot"])
    # 寫入紀錄（spec 第 5 節）：aos7-run 起任務時才把 audit_site/ 放進任務的 PYTHONPATH，
    # 不給 aos7-run 自己（它寫的 pid.json、exit.json 不算任務的寫入；probes/polyglot N7）
    subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-run"), tdir], cwd=node, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return tid
