"""登記表 $AOS_HOME/.aos/registry.json。欄位照 WRITER-BRIEF 4.6。"""
import os

from . import fsutil, layout, status

PENDING = "pending"
RUNNING = "running"
STOPPED = "stopped"


def empty():
    return {"format_version": 1, "daemon_pid": None,
            "daemon_pid_start": None, "entries": []}


def _canonicalize(reg):
    """補齊正式欄位，並把舊版 ext.result／ext.args 搬到那筆的頂層。"""
    reg.setdefault("daemon_pid_start", None)
    for e in reg.get("entries", []):
        ext = e.get("ext")
        if isinstance(ext, dict):
            if "result" not in e and "result" in ext:
                e["result"] = ext["result"]
            if "args" not in e and "args" in ext:
                e["args"] = ext["args"]
            ext.pop("result", None)
            ext.pop("args", None)
        result = e.get("result")
        e["result"] = os.path.abspath(result) if isinstance(result, str) else None
        args = e.get("args")
        e["args"] = dict(args) if isinstance(args, dict) else None
    return reg


def load(home=None):
    h = home or layout.Home()
    return _canonicalize(fsutil.read_json(h.registry, empty()) or empty())


def save(reg, home=None):
    h = home or layout.Home()
    fsutil.write_json(h.registry, _canonicalize(reg))


def _lock(home=None):
    h = home or layout.Home()
    return fsutil.Lock(h.registry_lock, wait_ms=5000)


def find(reg, path):
    p = os.path.abspath(path)
    for e in reg["entries"]:
        if e["path"] == p:
            return e
    return None


def register(path, clock, budget=None, parent=None, state=PENDING, home=None,
             result=None, args=None):
    """登記一塊地的時鐘。已在的就更新。回傳那筆。"""
    h = home or layout.Home()
    fsutil.ensure_dir(h.aos)
    with _lock(h):
        reg = load(h)
        e = find(reg, path)
        now = fsutil.now_iso()
        if e is None:
            e = {
                "path": os.path.abspath(path),
                "pid": None,
                "pid_start": None,
                "state": state,
                "clock": clock,
                "budget": budget,
                "result": os.path.abspath(result) if result is not None else None,
                # 脫節子地的環境變數（AOS_RESULT／AOS_CALLER／AOS_ARG_*）要從這裡重建：
                # P-01 之後起子地那支 run 是 daemon 生的，拿不到父當初 exec 的環境。
                "args": dict(args) if args is not None else None,
                "parent": os.path.abspath(parent) if parent else None,
                "registered_at": now,
                "updated_at": now,
            }
            reg["entries"].append(e)
        else:
            e["clock"] = clock
            e["budget"] = budget
            if result is not None:
                e["result"] = os.path.abspath(result)
            if args is not None:
                e["args"] = dict(args)
            e["parent"] = os.path.abspath(parent) if parent else e.get("parent")
            if e["state"] == STOPPED:
                e["state"] = state
                e["pid"] = None
            e["updated_at"] = now
        save(reg, h)
        return dict(e)


def update(path, home=None, **fields):
    h = home or layout.Home()
    with _lock(h):
        reg = load(h)
        e = find(reg, path)
        if e is None:
            return None
        e.update(fields)
        e["updated_at"] = fsutil.now_iso()
        save(reg, h)
        return dict(e)


def proc_start(pid):
    """行程起始時間（clock tick）。拿不到就 None。防 pid 重用誤判。"""
    try:
        with open("/proc/%d/stat" % int(pid), "rb") as f:
            data = f.read()
    except (OSError, ValueError, TypeError):
        return None
    # comm 可能含空白與括號，從最後一個 ')' 之後切
    try:
        rest = data[data.rindex(b")") + 2:].split()
        return int(rest[19])
    except (ValueError, IndexError):
        return None


def alive(pid, pid_start=None):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if pid_start is not None:
        now = proc_start(pid)
        if now is not None and now != pid_start:
            # pid 被回收給別的行程了，不是我們那支
            return False
    return True


def entry_alive(e):
    return alive(e.get("pid"), e.get("pid_start"))


def reconcile(home=None):
    """對帳：pid 不在→ stopped；已停的子若漏結果，替父補狀態檔。"""
    h = home or layout.Home()
    changed = []
    with _lock(h):
        reg = load(h)
        for e in reg["entries"]:
            if e["state"] == RUNNING and not entry_alive(e):
                e["state"] = STOPPED
                e["pid"] = None
                e["pid_start"] = None
                e["updated_at"] = fsutil.now_iso()
                changed.append(e["path"])
            if e["state"] == STOPPED:
                _mark_missing_result(e)
        if reg.get("daemon_pid") is not None and not alive(
                reg["daemon_pid"], reg.get("daemon_pid_start")):
            reg["daemon_pid"] = None
            reg["daemon_pid_start"] = None
        save(reg, h)
    return changed


def daemon_alive(home=None):
    reg = load(home)
    return alive(reg.get("daemon_pid"), reg.get("daemon_pid_start"))


def set_daemon_pid(pid, home=None):
    h = home or layout.Home()
    fsutil.ensure_dir(h.aos)
    with _lock(h):
        reg = load(h)
        reg["daemon_pid"] = pid
        reg["daemon_pid_start"] = proc_start(pid) if pid else None
        save(reg, h)


def _mark_missing_result(e):
    """已停的脫節子地漏結果時，依停止原因替父補上可分辨的壞消息。"""
    result = e.get("result")
    if not result:
        return
    if os.path.exists(result) or os.path.exists(status.status_path(result)):
        return
    stopped = fsutil.read_json(layout.Land(e["path"]).stopped) or {}
    stopped_reason = stopped.get("reason")
    if stopped_reason in ("idle", "budget", "steps_done"):
        reason = status.NO_RESULT
        message = "%s 已經做完，但結果落點 %s 什麼都沒留下" % (e["path"], result)
    elif stopped_reason in ("failed", "parse_error", "stalled"):
        reason = status.CHILD_FAILED
        message = "%s 的串失敗了，沒有產出結果：%s" % (
            e["path"], stopped.get("message") or "子地沒有留下說明")
    else:
        reason = status.KILLED
        message = "%s 的 run 被停掉或消失了，結果落點 %s 什麼都沒留下" % (
            e["path"], result)
    status.write_failed(result, reason, message,
                        ext={"land": e["path"], "stopped_reason": stopped_reason})
