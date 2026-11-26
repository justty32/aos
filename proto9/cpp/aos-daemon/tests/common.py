#!/usr/bin/env python3
# common.py：aos-daemon 測試共用的小工具——起 daemon 與 demo、限時跑殼指令（卡住也不跟著卡）、收乾淨殘留的行程與掛載。
import atexit, json, os, select, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
DAEMON = os.path.normpath(os.path.join(HERE, "..", "build", "bin", "aos-daemon"))
DEMO = os.path.normpath(os.path.join(HERE, "..", "..", "aos-procfs", "build", "bin", "aos-procfs-demo"))
SCRATCH = os.path.expanduser("~/.aos/scratch/proto9-daemon-1125")
MNT = os.path.join(SCRATCH, "mnt")     # daemon 自己與外面起的 demo 的掛載點
BASE = os.path.join(SCRATCH, "base")   # 給 --mount-base：底下的 proc 的掛載點
MARK = "AOS_DAEMON_TEST_RUN"           # 起的每支行程（連孫子）都帶這個環境變數，收尾時靠它找
RUN = str(os.getpid())
# 測試用的短期限：查卡住 0.3 秒一次、讀 status 0.5 秒沒回就算卡住
FAST = ["--check-interval", "0.3", "--check-timeout", "0.5", "--register-timeout", "3",
        "--stop-timeout", "3", "--ctl-timeout", "1"]

_procs = []   # 起過的 Popen
_stuck = []   # 限時到了還沒結束的殼（可能卡在 FUSE 裡）


def env():
    e = {k: v for k, v in os.environ.items() if k not in ("AOS_ROOT", "AOS_NAME", "AOS_MOUNT")}
    e[MARK] = RUN
    return e


def _wait_line(p, prefix, wait):
    deadline = time.monotonic() + wait
    buf = b""
    fd = p.stdout.fileno()
    while time.monotonic() < deadline:
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            break
        buf += chunk
        for line in buf.decode().splitlines():
            if line.startswith(prefix):
                return line
    raise RuntimeError("no %r line: %r" % (prefix, buf))


def start_daemon(test, *extra, wait=5.0):
    """起一台根 daemon（--mount-base 是這組自己的夾）；回 (Popen, pid, root, base)。"""
    base = os.path.join(BASE, test)
    os.makedirs(MNT, exist_ok=True)
    mnt = os.path.join(MNT, "d-%s-%s" % (test, RUN))
    p = subprocess.Popen([DAEMON, "root", mnt, "--mount-base", base, *FAST, *extra], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, cwd="/", env=env())
    _procs.append(p)
    line = _wait_line(p, "export AOS_ROOT=", wait)
    root = line.split("=", 1)[1]
    return p, int(root.split("/")[2]), root, base


def start_demo(name, *extra, wait=5.0, tag=""):
    """外面起一隻 demo（extra 是多給的旗標，tag 讓同名的第二隻用另一個掛載點）；回 (Popen, pid, root, mountpoint)。"""
    os.makedirs(MNT, exist_ok=True)
    mnt = os.path.join(MNT, "%s%s-%s" % (name, tag, RUN))
    p = subprocess.Popen([DEMO, name, mnt, *extra], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/", env=env())
    _procs.append(p)
    root = _wait_line(p, "AOS_ROOT=", wait).split("=", 1)[1]
    return p, int(root.split("/")[2]), root, mnt


def sh(cmd, timeout=5.0):
    """跑 bash -c cmd；回 (rc, stdout, stderr)。到時還沒完就 kill、不等它，rc=None。"""
    p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd="/")
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        p.kill()
        _stuck.append(p)
        return None, "", "timeout"


def bg(cmd):
    p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd="/")
    _stuck.append(p)
    return p


def timed(cmd, timeout=5.0):
    t = time.monotonic()
    r = sh(cmd, timeout)
    return r + (time.monotonic() - t,)


def parse_kv(text):
    d = {}
    for line in text.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            d[k] = v
    return d


def read_kv(path, timeout=3.0):
    rc, out, _ = sh("cat %s" % path, timeout)
    return parse_kv(out) if rc == 0 else None


def table(root, name):
    """procs_status 裡 name 那幾欄；沒有那隻回 {}。"""
    d = read_kv(root + "/procs_status") or {}
    return {k.split(".", 1)[1]: v for k, v in d.items() if k.startswith(name + ".")}


def ctl(path, line, timeout=5.0):
    return sh("echo '%s' > %s" % (line, path), timeout)


def wait_until(fn, timeout=5.0, step=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return fn()


def alive(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def our_mounts():
    out = []
    with open("/proc/mounts") as f:
        for line in f:
            parts = line.split()
            if parts[2] == "fuse.aosproc" and parts[1].startswith(SCRATCH):
                out.append(parts[1])
    return out


def marked():
    """帶著這次 MARK 的行程（daemon 起的孫子也在內）。"""
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            with open("/proc/%s/environ" % d, "rb") as f:
                if (b"%s=%s\0" % (MARK.encode(), RUN.encode())) in f.read() and alive(int(d)):
                    out.append(int(d))
        except OSError:
            pass
    return out


def cleanup():
    """收乾淨：叫醒被暫停的、殺掉帶 MARK 的行程，卸掉 scratch 底下殘留的掛載、刪空夾。只跑部分或中途被殺也會跑到。"""
    for pid in marked():
        try:
            os.kill(pid, signal.SIGCONT)
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for p in _procs:
        try:
            p.wait(3)
        except subprocess.TimeoutExpired:
            pass
    for m in our_mounts():
        subprocess.run(["fusermount3", "-u", "-z", m], capture_output=True)
    for p in _stuck:
        if p.poll() is None:
            p.kill()
        try:
            p.wait(3)
        except subprocess.TimeoutExpired:
            pass
    for top in (MNT, BASE):
        for dirpath, dirs, _ in os.walk(top, topdown=False) if os.path.isdir(top) else []:
            for d in dirs:
                try:
                    os.rmdir(os.path.join(dirpath, d))
                except OSError:
                    pass


def leftovers():
    return marked() + [p.pid for p in _stuck if p.poll() is None], our_mounts()


# ---------- 各組測試共用 ----------

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("%s  %s%s" % ("ok  " if cond else "FAIL", name, "" if cond or not detail else "  -- %s" % (detail,)), flush=True)


def spec(path, argv, envs=None):
    with open(path, "w") as f:
        json.dump({"exec": argv, "env": envs or {}}, f)
    return path


def phase_is(root, name, want, timeout=5.0):
    return wait_until(lambda: table(root, name).get("phase") == want, timeout)


def pctl_done(root, timeout=5.0, prefix="aos_procs_ctl_"):
    """等 procs_ctl（或 prefix 給的那個 ctl）的那道做完，回 status。
    寫入回來只代表「收到」：收下的那一刻 state 已經是 doing（回答的線上設的），所以寫完再等「不是 doing」就是等那一道。"""
    st = wait_until(lambda: (read_kv(root + "/status") or {}).get(prefix + "state") != "doing" and read_kv(root + "/status"), timeout)
    return st or {}


def pctl(root, line, timeout=5.0):
    """寫 procs_ctl 並等那道做完；回 (rc, stderr, status)。被拒的（rc 不是 0）不等。"""
    rc, _, err = ctl(root + "/procs_ctl", line)
    return rc, err, (pctl_done(root, timeout) if rc == 0 else read_kv(root + "/status") or {})


def own_ctl(root, line, timeout=5.0):
    """寫 daemon 自己的 ctl 並等那道做完（stop 除外：它鎖到結束）；回 (rc, stderr)。"""
    rc, _, err = ctl(root + "/ctl", line)
    if rc == 0:
        pctl_done(root, timeout, "aos_ctl_")
    return rc, err


def stop_daemon(p, root, label):
    rc, _, err = ctl(root + "/ctl", "stop")
    try:
        code = p.wait(10)
    except subprocess.TimeoutExpired:
        code = None
    check("%s: daemon stop -> exits 0" % label, rc == 0 and code == 0, (rc, err, code))


atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda *a: sys.exit(143))
