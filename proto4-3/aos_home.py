#!/usr/bin/env python3
"""家目錄的版面（哪個檔在哪）＋兩個小工具：原子寫檔、pid 活不活。daemon 與 ctl 共用。

家怎麼決定：`--home H` → 環境變數 `AOS_DAEMON_HOME` → 預設 `~/.aos-daemon`（`resolve_home`）。
裡面五樣東西：

    H/requests/         請求檔（誰都可以寫，daemon 每 0.2 秒掃一次；`.tmp` 忽略）
    H/requests/done/    處理完搬來這裡，內容＝原請求 ＋ `ok` ＋ `result`
    H/daemon.pid        daemon 的 pid
    H/state.json        每 0.5 秒寫一次＝`ls` 的內容，CLI 的 ls／get 直接讀它
    H/daemon.log        daemon 自己的話 ＋ 每個 aos-run 的 stderr（原樣，前面加 key）

從 proto4-2 的 `aos_home.py` 改的：那一版的家分成使用者面與 daemon 面兩層（中間隔著
kernel），這一版沒有 kernel、daemon 自己讀請求，所以只剩一層、也就攤平了。
"""
import json
import os
import time

DEFAULT_HOME = os.path.expanduser("~/.aos-daemon")


def resolve_home(explicit=None):
    """家的優先序：`--home H`（`explicit`）→ 環境變數 `AOS_DAEMON_HOME` → 預設 `~/.aos-daemon`。"""
    return explicit or os.environ.get("AOS_DAEMON_HOME") or DEFAULT_HOME


class Home:
    def __init__(self, d):
        self.dir = os.path.abspath(d)
        self.requests = os.path.join(self.dir, "requests")
        self.done = os.path.join(self.requests, "done")
        self.pidf = os.path.join(self.dir, "daemon.pid")
        self.statef = os.path.join(self.dir, "state.json")
        self.logf = os.path.join(self.dir, "daemon.log")

    def ensure(self):
        for p in (self.dir, self.requests, self.done):
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
            with open(self.statef, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None


def write_json(path, obj):
    """先寫 `.tmp` 再 rename——讀的人看到的一定是完整的一份。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def put_request(home, req):
    """丟一個請求檔，回它的檔名（CLI 之後就是等 `done/<這個名字>` 冒出來）。"""
    home.ensure()
    name = "%013d-%d.json" % (time.time() * 1000, os.getpid())
    write_json(os.path.join(home.requests, name), req)
    return name


def alive(pid):
    """活著＝/proc 有它、而且不是殭屍（跟 proto4-2 同一招）。"""
    if not pid:
        return False
    try:
        with open("/proc/%d/stat" % pid) as f:
            st = f.read()
    except OSError:
        return False
    return st[st.rindex(")") + 2] != "Z"
