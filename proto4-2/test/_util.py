"""測試共用的小工具：路徑、複製 fixture、等條件、收乾淨。"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FX = os.path.join(HERE, "fx")
sys.path.insert(0, ROOT)

CPU = os.path.join(ROOT, "aos_cpu.py")
AOS = os.path.join(ROOT, "aos.py")
PY = sys.executable


def mktmp(prefix="aos-proto4-2-"):
    return tempfile.mkdtemp(prefix=prefix)


def copy_fx(name, into):
    """把 fixture 複製一份到暫存目錄再跑，別弄髒 repo 裡的 fx/。"""
    dst = os.path.join(into, name)
    shutil.copytree(os.path.join(FX, name), dst)
    return dst


def wait_until(pred, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.05)
    return False


def alive(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            st = f.read()
    except (OSError, TypeError):
        return False
    return st[st.rindex(")") + 2] != "Z"


def kill_hard(pid):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except OSError:
            return
        if wait_until(lambda: not alive(pid), 2.0):
            return


def cli(home, *args, timeout=30):
    return subprocess.run([PY, AOS] + list(args), env=dict(os.environ, AOS_HOME=home),
                          capture_output=True, text=True, timeout=timeout)


def find_done(folder, pred, timeout=15.0):
    """在一個 done 資料夾裡等到有一筆符合 pred 的請求紀錄，回傳那筆（逾時回 None）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            names = []
        for n in names:
            p = os.path.join(folder, n)
            try:
                with open(p, encoding="utf-8") as f:
                    r = json.load(f)
            except (OSError, ValueError):
                continue
            if pred(r):
                return r
        time.sleep(0.05)
    return None
