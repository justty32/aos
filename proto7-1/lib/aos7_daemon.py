"""aos7-daemon：常駐程式——掃 node、每條時間線一個迴圈、讀控制檔、寫 status.json 與 log.jsonl（spec.md 第 1、2 節，S-03～S-06）。

    aos7-daemon <root>

SIGTERM／SIGINT＝stop 加 kill（S-21 路一：子 daemon 被父時間線 kill 時帶走自己的任務）。
"""
import fcntl
import os
import signal
import sys
import threading
import time

import aos7_task
from aos7_daemon_timeline import POLL, Timeline
from aos7_fs import append_jsonl, now, read_json, write_json


def scan_nodes(root):
    """回 root 底下所有 node id（含 `.aos/timeline.json` 的資料夾）。

    跳過 `.` 開頭的資料夾；含 `.aosd/` 的子資料夾是別的 daemon 的根，整棵不進去（S-15）。"""
    found = []
    for d, subdirs, _ in os.walk(root):
        if d != root and os.path.isdir(os.path.join(d, ".aosd")):
            subdirs[:] = []
            continue
        subdirs[:] = sorted(s for s in subdirs if not s.startswith("."))
        if os.path.isfile(os.path.join(d, ".aos", "timeline.json")):
            rel = os.path.relpath(d, root)
            found.append("." if rel == "." else rel.replace(os.sep, "/"))
    return found


class Daemon:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.aosd = os.path.join(self.root, ".aosd")
        self.timelines = {}
        self.stopping = False
        self.kill_on_stop = False
        self._log_lock = threading.Lock()
        self.paused = set(read_json(os.path.join(self.aosd, "paused.json"), {}).get("paused", []))

    # ---------- 給 Timeline 用 ----------

    def is_paused(self, node_id):
        return node_id in self.paused

    def log(self, **kw):
        with self._log_lock:
            append_jsonl(os.path.join(self.aosd, "log.jsonl"), dict(at=now(), **kw))

    # ---------- 控制檔 ----------

    def apply(self, ctl):
        """執行一個 daemon 控制，回 (ok, msg)。"""
        op, node = ctl.get("op"), ctl.get("node")
        if op in ("pause", "resume"):
            if not isinstance(node, str):
                return False, "%s 要給 node" % op
            (self.paused.add if op == "pause" else self.paused.discard)(node)
            write_json(os.path.join(self.aosd, "paused.json"), {"paused": sorted(self.paused)})
            return True, "%s %s" % (op, node)
        if op == "stop":
            self.stop(bool(ctl.get("kill")))
            return True, "stopping" + (" with kill" if self.kill_on_stop else "")
        if op == "rescan":
            self.scan()
            return True, "rescanned"
        return False, "unknown op %r" % op

    def handle_ctl(self):
        cdir = os.path.join(self.aosd, "ctl")
        try:
            names = sorted(n for n in os.listdir(cdir) if n.endswith(".json"))
        except OSError:
            return
        for n in names:
            path = os.path.join(cdir, n)
            ctl = read_json(path)
            if isinstance(ctl, dict):
                ok, msg = self.apply(ctl)
            else:
                ctl, ok, msg = {"raw": "unreadable"}, False, "not a JSON object"
            ctl["result"] = {"ok": ok, "msg": msg, "at": now()}
            write_json(os.path.join(self.aosd, "ctl-done", n), ctl)
            try:
                os.remove(path)
            except OSError:
                pass
            self.log(ev="ctl", file=n, op=ctl.get("op"), node=ctl.get("node"), by=ctl.get("by"), ok=ok, msg=msg)

    def stop(self, kill):
        self.stopping = True
        self.kill_on_stop = self.kill_on_stop or kill
        for tl in self.timelines.values():
            tl.wake.set()

    # ---------- node ----------

    def scan(self):
        if self.stopping:
            return
        now_ids = set(scan_nodes(self.root))
        for nid in sorted(now_ids - set(self.timelines)):
            tl = Timeline(self, nid)
            self.timelines[nid] = tl
            tl.start()
            self.log(ev="node+", node=nid, round=tl.round)
        for nid in sorted(set(self.timelines) - now_ids):
            tl = self.timelines.pop(nid)
            tl.gone = True
            tl.wake.set()
            self.log(ev="node-", node=nid)

    def write_status(self):
        nodes = {}
        for nid, tl in list(self.timelines.items()):
            phase = "paused" if self.is_paused(nid) and tl.phase == "idle" else tl.phase
            nodes[nid] = {"round": tl.round, "phase": phase, "paused": self.is_paused(nid),
                          "live": aos7_task.live_tasks(tl.node)}
            if tl.last_error:
                nodes[nid]["last_error"] = tl.last_error
        write_json(os.path.join(self.aosd, "status.json"),
                   {"pid": os.getpid(), "root": self.root, "at": now(), "stopping": self.stopping,
                    "kill_on_stop": self.kill_on_stop, "nodes": nodes})

    # ---------- 主迴圈 ----------

    def run(self):
        os.makedirs(os.path.join(self.aosd, "ctl"), exist_ok=True)
        lock = open(os.path.join(self.aosd, "daemon.lock"), "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("aos7-daemon: %s 已經有 daemon 在跑" % self.root, file=sys.stderr)
            return 1
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, lambda *_: self.stop(True))
        self.log(ev="start", pid=os.getpid())
        while not self.stopping:
            self.handle_ctl()
            self.scan()
            self.write_status()
            time.sleep(POLL)
        self.log(ev="stopping", kill=self.kill_on_stop)
        while any(tl.is_alive() for tl in self.timelines.values()):
            self.write_status()
            time.sleep(POLL)
        self.write_status()
        self.log(ev="stop")
        return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not os.path.isdir(argv[0]):
        print("用法: aos7-daemon <root>（root 要是已存在的資料夾）", file=sys.stderr)
        return 1
    return Daemon(argv[0]).run()
