"""所有 cpu 的父行程（proto5-2）：按池、宣告式——手上是一份「每池要哪幾號」，每圈把孩子往宣告靠。

規範：spec/daemon-home.md（家）、daemon-reconcile.md（一圈）、protocol.md（單）、handoff.md §2（重開）、
daemon-cli.md（指令）；沒寫的照 proto5/spec/daemon/。分檔：
  aos_daemon.py        家、info 讀驗、活不活、給 kernel 的小函式、啟動（run）與 halt（stop）
  aos_daemon_pools.py  池與一顆一檔的形狀、檔案動作、拉孩子
  aos_daemon_loop.py   一圈：收屍、狀態機、退避、節流、fd 預算、批次階梯、停機
  aos_daemon_rpc.py    scale／kill／ls 的驗與判
  aos_daemon_cli.py    命令列（boot／halt／ls／scale／kill）
"""
import fcntl
import os
from pathlib import Path
import resource
import signal
import time

import aos_client
import aos_daemon_loop
import aos_daemon_pools as pools
import aos_home
from aos_daemon_rpc import DaemonError
from aos_directives import Context, DirectiveError, Document, parse_options, resolve_located

Daemon = aos_daemon_loop.Daemon
_signal_pid, _pid_exists, _log = pools.signal_pid, pools.pid_exists, pools.log

INFO_DEFAULTS = {"poll_ms": 20, "restart_delay_ms": 1000, "restart_max_ms": 60000, "stable_ms": 10000,
                 "spawn_per_sec": 50, "max_children": 20000, "stop_wait_ms": 5000, "kill_wait_ms": 5000}
POSITIVE = ("poll_ms", "spawn_per_sec", "max_children")


def daemon_home(value=None):
    """--target → AOS_DAEMON_HOME → 目前資料夾（09-24 fix-r4：~/.aos-daemon 預設拿掉）。"""
    return str(aos_home.resolve_target(value, "AOS_DAEMON_HOME")[0])


def is_alive(home):
    """共享 flock 只探測獨占主人；state 裡的 pid 不作生死判斷。"""
    try:
        fd = os.open(os.path.join(home, ".daemon.lock"), os.O_RDONLY | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def read_state(home):
    """state.json 只剩 pid／stopping／current；舊版的 children 讀得到就照給（啟動時會殺掉、拿掉）。"""
    state = aos_home.read_state(home, {"pid": 0, "stopping": False, "current": None})
    state.setdefault("children", {})
    return state


def _peek(path):
    try:
        value = aos_home.read_json(path)
    except aos_home.HomeError:
        return None
    return value if isinstance(value, dict) else None


def pool_summary(home, dpool):
    """給 kernel：讀 D/pools/<dpool>/summary.json；不在或壞了回 None（不在＝池已完全拿掉）。"""
    if not pools.valid_pool_name(dpool):
        return None
    return _peek(pools.pool_dir(home, dpool) / "summary.json")


def pool_summary_state(home, dpool):
    """給交接用（review P6）：回 (狀態, 摘要)。
    ("gone", None)＝summary.json 確定不存在（FileNotFoundError／NotADirectoryError，池資料夾不在也算；
    名字本身不合法的池 daemon 永遠不會建，也算 gone）；("ok", dict)＝讀到物件；
    ("unknown", None)＝檔在但讀不到、壞 JSON、不是物件、其他 OSError——呼叫端要等或報錯，不能放行。"""
    if not pools.valid_pool_name(dpool):
        return "gone", None
    path = pools.pool_dir(home, dpool) / "summary.json"
    try:
        text = path.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return "gone", None
    except OSError:
        return "unknown", None
    try:
        value = aos_home._loads(text.decode("utf-8"))
    except (ValueError, UnicodeError):
        return "unknown", None
    return ("ok", value) if isinstance(value, dict) else ("unknown", None)


def pool_kid(home, dpool, i):
    """給 kernel：讀 D/pools/<dpool>/kids/<i>.json；不在（還沒拉過）或壞了回 None。"""
    if not pools.valid_pool_name(dpool):
        return None
    try:
        i = int(i)
    except (TypeError, ValueError):
        return None
    return _peek(pools.kid_path(home, dpool, i)) if i >= 0 else None


def load_info(home):
    """daemon-home §1：第 2 版的新鍵；第 1 版照讀、缺的用預設。展開指示詞同 aos_home.load_info。"""
    home = Path(home).absolute()
    path = home / "info.json"
    try:
        obj = aos_home.read_json(path)
    except aos_home.HomeError as exc:
        raise aos_home.HomeError("NotAHome", exc.msg) from exc

    def expand(value, ctx, position):
        loc = resolve_located(value, ctx, position)
        value = parse_options(loc.value, loc.position, {})[1]
        if isinstance(value, dict):
            return {k: expand(v, loc.ctx, loc.position + [k]) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v, loc.ctx, loc.position + [str(i)]) for i, v in enumerate(value)]
        return value

    try:
        obj = expand(obj, Context(Document(str(path), obj), base_dir=str(home)), [])
    except DirectiveError as exc:
        raise aos_home.HomeError(exc.code, exc.msg) from exc
    mi = obj.get("_metainfo") if isinstance(obj, dict) else None
    if (not isinstance(mi, dict) or mi.get("_type") != "daemon" or
            type(mi.get("_version")) is not int or mi["_version"] not in (1, 2)):
        raise aos_home.HomeError("NotAHome", "info 的身分必須是 daemon 第 1 或第 2 版")
    if "restart_max_ms" not in obj and type(obj.get("restart_delay_ms")) is int:
        obj["restart_max_ms"] = max(INFO_DEFAULTS["restart_max_ms"], obj["restart_delay_ms"])  # D-51
    for key, default in INFO_DEFAULTS.items():
        value = obj.setdefault(key, default)
        minimum = 1 if key in POSITIVE else 0
        if type(value) is not int or value < minimum:
            raise DaemonError("FieldTypeMismatch", "%s 必須是%s整數" % (key, "正" if minimum else "非負"))
    if obj["restart_max_ms"] < obj["restart_delay_ms"]:
        raise DaemonError("FieldTypeMismatch", "restart_max_ms 必須 ≥ restart_delay_ms")
    return obj


def fd_budget(info):
    """daemon-reconcile §5：軟上限調到硬上限；預算＝min(max_children, 開檔數 − 64)。"""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft != hard:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
        except (ValueError, OSError):
            pass
        soft = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
    if soft == resource.RLIM_INFINITY:
        return info["max_children"]
    return max(0, min(info["max_children"], soft - 64))


def _previous_children(pids, info):
    """接手沒有 pipe 的上一任孩子（proto5 §6.1 第 3 步）：整批 TERM、等兩段、整批 KILL 整組、等 pid 消失。"""
    pids = {pid for pid in pids if _pid_exists(pid)}
    for pid in pids:
        _signal_pid(pid, signal.SIGTERM)
    deadline = time.monotonic() + (info["stop_wait_ms"] + info["kill_wait_ms"]) / 1000
    killed = False
    while pids:
        pids = {pid for pid in pids if _pid_exists(pid)}
        if pids and not killed and time.monotonic() >= deadline:
            for pid in pids:
                _signal_pid(pid, signal.SIGKILL, group=True)
            killed = True
        if pids:
            time.sleep(info["poll_ms"] / 1000)


def _scan_pools(home):
    """讀每池的 pool.json（壞了整個不開，D-55）與每個 kids 檔；回（宣告們, 舊 kids, 舊孩子的 pid）。"""
    decls, kids, pids = [], [], set()
    for path in sorted(pools.pools_dir(home).iterdir()):
        if not path.is_dir():
            continue
        if (path / "pool.json").exists():
            decls.append(pools.read_pool_json(path / "pool.json"))
        kid_dir = path / "kids"
        if not kid_dir.is_dir():
            continue
        for leaf in sorted(kid_dir.iterdir()):
            stem = leaf.name[:-5] if leaf.name.endswith(".json") else None
            if stem is None or not pools.NAME_RE.fullmatch(stem):
                continue
            record = _peek(leaf)
            kids.append((path.name, int(stem), leaf, record))
            if (record is not None and record.get("state") in ("running", "killing") and
                    type(record.get("pid")) is int and record["pid"] > 0):
                pids.add(record["pid"])
    return decls, kids, pids


def run(home):
    home = Path(home).absolute()
    home.mkdir(parents=True, exist_ok=True)
    if not (home / "info.json").exists():
        aos_home.write_json(home / "info.json", dict({"_metainfo": {"_type": "daemon", "_version": 2}},
                                                     **INFO_DEFAULTS))
    info = load_info(home)
    lock = os.open(home / ".daemon.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    handlers = {}
    owner = None
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DaemonError("AlreadyRunning", "同家已有 daemon 在跑") from exc
        aos_home.ensure_queue(home)
        pools.pools_dir(home).mkdir(exist_ok=True)
        old_state = read_state(home)
        decls, old_kids, pids = _scan_pools(home)
        pids.update(child["pid"] for child in old_state["children"].values()      # 舊版 proto5 的家
                    if isinstance(child, dict) and type(child.get("pid")) is int and child["pid"] > 0)
        owner = Daemon(home, info, fd_budget(info))
        def on_signal(signum, frame):
            owner.stop_requested = True
        for sig in (signal.SIGTERM, signal.SIGINT):
            handlers[sig] = signal.signal(sig, on_signal)
        handlers[signal.SIGPIPE] = signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        _previous_children(pids, info)
        aos_home.reconcile(home, old_state.get("current"))
        owner.adopt(decls, old_kids)
        owner.save()                                   # 舊孩子死透才公布新狀態（children 拿掉）
        while not owner.step():
            time.sleep(owner.sleep_s())
        owner.state["pid"] = 0
        owner.save()
        return 0
    finally:
        if owner is not None:
            owner.close()
        for sig, previous in handlers.items():
            signal.signal(sig, previous)
        os.close(lock)


serve = run


def stop(home, wait_ms=30000):
    """放 stop notification 後，以 flock 等主人退出；逾時保留已送通知。"""
    if not is_alive(home):
        print("not running")
        return 0
    aos_home.post_request(home, aos_client.new_name("stop"),
                          {"jsonrpc": "2.0", "method": "stop"})
    deadline = time.monotonic() + wait_ms / 1000
    while is_alive(home):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DaemonError("Timeout", "等 daemon 退出逾時；stop 通知已送出，未撤回")
        time.sleep(min(.02, remaining))
    print("stopped")
    return 0


def main(argv=None):
    import aos_daemon_cli
    return aos_daemon_cli.main(argv)


if __name__ == "__main__":
    import sys
    sys.exit(main())
