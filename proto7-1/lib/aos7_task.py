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

from aos7_fs import BIN, env_with_bin, node_path, now, read_json, write_json

KILL_GRACE = 1.0   # spec 第 6 節：SIGTERM 後等至多 1 秒，還在就 SIGKILL
LIVE_STATES = ("born", "live")


# ---------- 路徑 ----------

def tasks_dir(node):
    """`<node>/.aos/tasks/`。"""
    return os.path.join(node, ".aos", "tasks")


def task_dir(node, tid):
    return os.path.join(tasks_dir(node), tid)


def list_tasks(node):
    """回這個 node 所有任務的 tid（排序過）。node 是絕對路徑。"""
    try:
        return sorted(d for d in os.listdir(tasks_dir(node))
                      if os.path.isfile(os.path.join(tasks_dir(node), d, "birth.json")))
    except OSError:
        return []


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


def kill_group(pgid, grace=KILL_GRACE):
    """對 pgid（連同後代的群組）送 SIGTERM，等至多 grace 秒，還在就 SIGKILL。回 True＝收乾淨。"""
    groups = _groups_with_descendants(pgid)
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
    if not pid:
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
        return True, "already ended"
    end = time.monotonic() + KILL_GRACE
    pid = read_json(os.path.join(tdir, "pid.json"))
    while not pid and time.monotonic() < end:   # 剛起、aos7-run 還沒寫 pid.json
        time.sleep(0.02)
        pid = read_json(os.path.join(tdir, "pid.json"))
    if not pid:
        return False, "no pid.json"
    clean = kill_group(pid.get("pgid"))
    return clean, "killed" if clean else "still alive after SIGKILL"


def write_spawn(node, fname, item):
    """寫 `<node>/.aos/spawn/<fname>.json`：請下個 tick 起一個任務。"""
    write_json(os.path.join(node, ".aos", "spawn", fname + ".json"), item)


def run_ctl(node, tid):
    """執行 `<taskdir>/ctl.json`（若有），搬成 ctl-done.json。回紀錄 dict 或 None。"""
    tdir = task_dir(node, tid)
    path = os.path.join(tdir, "ctl.json")
    ctl = read_json(path)
    if ctl is None:
        if os.path.exists(path):          # 壞檔：也搬走，免得每回合重讀
            ctl = {"raw": "unreadable"}
        else:
            return None
    op = ctl.get("op")
    if op == "kill":
        ok, msg = kill_task(tdir)
    elif op == "restart":
        ok, msg = kill_task(tdir)
        birth = read_json(os.path.join(tdir, "birth.json"), {})
        item = {k: birth[k] for k in ("name", "argv", "inst", "dirs") if k in birth}
        item["dirs"] = birth.get("dirs", [])[1:]   # 第一個是 node 本身，tick 會再加
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
    while os.path.exists(task_dir(node, tid)):
        n += 1
        tid = "%s-%d" % (base, n)
    return tid


def start_task(root, node_id, item, rnd):
    """寫 birth.json，用 aos7-run 起任務（新 session，不等）。回 tid。"""
    root = os.path.abspath(root)
    node = node_path(root, node_id)
    tid = new_tid(node, item.get("name"), rnd)
    tdir = task_dir(node, tid)
    dirs = [node] + [os.path.normpath(os.path.join(node, d)) for d in item.get("dirs", [])]
    birth = {"tid": tid, "name": item.get("name", "task"), "node": node_id, "round": rnd,
             "dirs": dirs, "at": now(), "restart_of": item.get("restart_of")}
    if "inst" in item:
        birth["inst"] = item["inst"]
    else:
        birth["argv"] = item.get("argv", [])
    write_json(os.path.join(tdir, "birth.json"), birth)
    env = env_with_bin()
    env.update({"AOS7_ROOT": root, "AOS7_NODE": node, "AOS7_NODE_ID": node_id,
                "AOS7_TASK": tdir, "AOS7_TID": tid})
    subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-run"), tdir], cwd=node, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return tid
