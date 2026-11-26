#!/usr/bin/env python3
# common.py：aos-procfs 測試與量測共用的小工具——起 demo、限時跑殼指令（卡住也不跟著卡）、收乾淨殘留的行程與掛載。
import atexit, os, select, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "..", "build", "bin", "aos-procfs-demo")
SCRATCH = os.path.expanduser("~/.aos/scratch/proto9-procfs-1125")
MNT = os.path.join(SCRATCH, "mnt")

_procs = []      # 起過的 Popen（demo 與其他）
_stuck = []      # 限時到了還沒結束的子行程（可能卡在 FUSE 裡，等伺服器收掉才會走）


def start_demo(name, *extra, wait=5.0):
    """起一隻 demo，等它印出 AOS_ROOT；回 (Popen, pid, root, mountpoint)。"""
    os.makedirs(MNT, exist_ok=True)
    mnt = os.path.join(MNT, "%s-%d" % (name, os.getpid()))
    p = subprocess.Popen([DEMO, name, mnt, *extra], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/")
    _procs.append(p)
    deadline = time.monotonic() + wait
    buf = b""
    fd = p.stdout.fileno()
    while time.monotonic() < deadline:
        # 直接讀 fd：用帶緩衝的 readline 會把兩行一起吃進緩衝，select 就再也等不到
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            break
        buf += chunk
        lines = buf.decode().splitlines()
        for line in lines:
            if line.startswith("AOS_ROOT="):
                pid = int(lines[0].split()[1])
                return p, pid, line.split("=", 1)[1], mnt
    raise RuntimeError("demo did not start: %r" % buf)


def sh(cmd, timeout=5.0, cwd="/"):
    """跑 bash -c cmd；回 (rc, stdout, stderr)。到時還沒完就 kill、不等它（卡在 FUSE 的人殺不掉），rc=None。"""
    p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        p.kill()
        _stuck.append(p)
        return None, "", "timeout"


def bg(cmd, cwd="/"):
    """背景跑 bash -c cmd，回 Popen（不等）。"""
    p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
    _stuck.append(p)
    return p


def parse_kv(text):
    d = {}
    for line in text.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            d[k] = v
    return d


def status(root, timeout=3.0):
    rc, out, _ = sh("cat %s/status" % root, timeout)
    return parse_kv(out) if rc == 0 else None


def wait_until(fn, timeout=5.0, step=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return fn()


def our_mounts():
    out = []
    with open("/proc/mounts") as f:
        for line in f:
            parts = line.split()
            if parts[2] == "fuse.aosproc" and parts[1].startswith(MNT):
                out.append(parts[1])
    return out


def mounted(mnt):
    return mnt in our_mounts()


def cleanup():
    """收乾淨：叫醒被暫停的、殺掉起過的行程，卸掉 scratch 底下殘留的掛載、刪空夾。只跑部分測試時也會跑到。"""
    for p in _procs:
        if p.poll() is None:
            try:
                os.kill(p.pid, signal.SIGCONT)
                p.kill()
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
    if os.path.isdir(MNT):
        for d in os.listdir(MNT):
            try:
                os.rmdir(os.path.join(MNT, d))
            except OSError:
                pass


RESULTS = []


def check(name, cond, detail=""):
    """印一條 ok／FAIL，記進 RESULTS（mail.py、mail_more.py 用；run.py 有自己的）。"""
    RESULTS.append(bool(cond))
    print("%s  %s%s" % ("ok  " if cond else "FAIL", name, "" if cond or not detail else "  -- %s" % (detail,)), flush=True)


def leftovers():
    alive = [p.pid for p in _procs + _stuck if p.poll() is None]
    return alive, our_mounts()


atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda *a: sys.exit(143))
