#!/usr/bin/env python3
"""家目錄的版面（哪個檔在哪）＋ 幾個看 /proc 的小工具。daemon 與 CLI 共用。

家走 --home 或環境變數 AOS_HOME，裡面：

    H/requests/            使用者面的請求（CLI 寫這裡，只有 kernel 讀）
    H/requests/done/       處理過的搬來這裡
    H/kernel/              第一顆 cpu 跑的 proc（daemon 起來時自動生 .aos/inst.json）
    H/daemon/daemon.pid    daemon 的 pid
    H/daemon/state.json    每輪寫一次：daemon pid ＋ 每顆 cpu 的近況
    H/daemon/cpus.json     登記表
    H/daemon/daemon.log    daemon 與各 cpu 的 stdout／stderr
    H/daemon/requests/     daemon 請求（只有 kernel 該寫），處理完搬到 requests/done/
"""
import json
import os


class Home:
    def __init__(self, d):
        self.dir = os.path.abspath(d)
        self.requests = os.path.join(self.dir, "requests")           # 使用者面
        self.done = os.path.join(self.requests, "done")
        self.kernel = os.path.join(self.dir, "kernel")
        self.daemon = os.path.join(self.dir, "daemon")
        self.dreq = os.path.join(self.daemon, "requests")            # daemon 面
        self.ddone = os.path.join(self.dreq, "done")
        self.pidf = os.path.join(self.daemon, "daemon.pid")
        self.statef = os.path.join(self.daemon, "state.json")
        self.cpusf = os.path.join(self.daemon, "cpus.json")
        self.logf = os.path.join(self.daemon, "daemon.log")

    def ensure(self):
        for p in (self.dir, self.requests, self.done, self.kernel,
                  self.daemon, self.dreq, self.ddone):
            os.makedirs(p, exist_ok=True)

    def pid(self):
        try:
            with open(self.pidf) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def alive(self):
        return alive(self.pid())

    def state(self):
        try:
            with open(self.statef) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None


def alive(pid):
    """活著＝/proc 有它、而且不是殭屍。"""
    if not pid:
        return False
    try:
        with open("/proc/%d/stat" % pid) as f:
            st = f.read()
    except OSError:
        return False
    return st[st.rindex(")") + 2] != "Z"


def rss_kb(pid):
    """佔用資源：/proc/<pid>/status 的 VmRSS。"""
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def cpu_field(d, key, default=None):
    """讀那顆 cpu 自己寫的 .aos/cpu.json（tick 跑到第幾格、stopped 是為什麼退的）。"""
    try:
        with open(os.path.join(d, ".aos", "cpu.json")) as f:
            return json.load(f).get(key, default)
    except (OSError, ValueError):
        return default
