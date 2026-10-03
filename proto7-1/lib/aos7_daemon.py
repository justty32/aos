"""aos7-daemon：常駐程式——掃 node、每條時間線一個迴圈、讀控制檔、寫 status.json 與 log.jsonl（spec.md 第 1、2 節，S-03～S-06）。

    aos7-daemon <root>

SIGTERM／SIGINT＝stop 加 kill（S-21 路一：子 daemon 被父時間線 kill 時帶走自己的任務）。
"""
import datetime
import fcntl
import os
import signal
import sys
import threading
import time

import aos7_task
from aos7_daemon_timeline import POLL, Timeline
from aos7_fs import append_jsonl, node_path, now, read_json, write_json

SCAN_BATCH = 20      # 一圈最多起幾條新時間線；多的下一圈再起，主迴圈不停擺（probes/fleet N2）
LIVE_EVERY = 0.25    # status.json 的 live 多久重算一次（秒）；任務資料夾多時每圈全掃太貴（probes/fleet N3、swarm N4）


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
        self.steps = {}              # resume 帶 rounds：{node: 還剩幾回合}，到 0 自動 pause（probes/sched N2）
        self._live = {}              # {node: (monotonic 時間, live 清單)}
        self.gen = None              # 世代（run 時換）
        self.io_errors = 0

    # ---------- 給 Timeline 用 ----------

    def is_paused(self, node_id):
        return node_id in self.paused

    def round_done(self, node_id):
        """時間線每 tock 完一回合呼叫：resume 帶 rounds 的倒數，到 0 就 pause。"""
        with self._log_lock:
            if node_id not in self.steps:
                return
            self.steps[node_id] -= 1
            if self.steps[node_id] > 0:
                return
            del self.steps[node_id]
            self.paused.add(node_id)
            self._save_paused()
        self.log(ev="steps-done", node=node_id)

    def _save_paused(self):
        write_json(os.path.join(self.aosd, "paused.json"), {"paused": sorted(self.paused)})

    def owner_root(self, node_id):
        """node 落在別的 daemon 的根（含 `.aosd/` 的子資料夾）底下時，回那個根的 node 路徑；否則 None。"""
        parts = [p for p in node_id.split("/") if p not in ("", ".")]
        for k in range(1, len(parts) + 1):
            sub = "/".join(parts[:k])
            if os.path.isdir(os.path.join(node_path(self.root, sub), ".aosd")):
                return sub
        return None

    def log(self, **kw):
        with self._log_lock:
            append_jsonl(os.path.join(self.aosd, "log.jsonl"), dict(at=now(), **kw))

    # ---------- 控制檔 ----------

    def apply(self, ctl):
        """執行一個 daemon 控制，回 (ok, msg)。"""
        op, node = ctl.get("op"), ctl.get("node")
        if op in ("pause", "resume", "wake"):
            if not isinstance(node, str):
                return False, "%s 要給 node" % op
            node = node.strip("/") or "."
            sub = self.owner_root(node)
            if sub:   # 屬於子 daemon，這個 daemon 永遠不會跑它（probes/multid N4）
                return False, "%s 屬於 daemon %s（寫那個 daemon 的控制檔）" % (node, sub)
            note = "" if node in self.timelines else "（目前沒有這個 node，出現時才生效）"
            if op == "wake":
                tl = self.timelines.get(node)
                if tl:
                    tl.kick = True       # 正在 idle 就不等滿 interval；回合中的照舊等任務或 interval（probes/event N1）
                return True, "wake %s%s" % (node, note)
            rounds = ctl.get("rounds")
            if op == "resume" and rounds is not None:
                if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
                    return False, "rounds 要是正整數"
            with self._log_lock:
                (self.paused.add if op == "pause" else self.paused.discard)(node)
                self.steps.pop(node, None)
                if op == "resume" and rounds is not None:
                    self.steps[node] = rounds
                self._save_paused()
            return True, "%s %s%s%s" % (op, node, " rounds=%d" % rounds if op == "resume" and rounds else "", note)
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
            try:
                queued = datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="milliseconds")
            except OSError:
                queued = None
            ctl["result"] = {"ok": ok, "msg": msg, "at": now(), "queued_at": queued}
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
        for nid in sorted(now_ids - set(self.timelines))[:SCAN_BATCH]:
            tl = Timeline(self, nid)
            self.timelines[nid] = tl
            tl.start()
            self.log(ev="node+", node=nid, round=tl.round, **({"paused": True} if nid in self.paused else {}))
        for nid in sorted(set(self.timelines) - now_ids):
            tl = self.timelines.pop(nid)
            tl.gone = True
            tl.wake.set()
            self.steps.pop(nid, None)
            self._live.pop(nid, None)
            self.log(ev="node-", node=nid)

    def live_of(self, nid, tl):
        t, live = self._live.get(nid, (None, None))
        if t is None or time.monotonic() - t >= LIVE_EVERY:
            live = aos7_task.live_tasks(tl.node)
            self._live[nid] = (time.monotonic(), live)
        return live

    def write_status(self, stopped=False):
        nodes = {}
        for nid, tl in list(self.timelines.items()):
            paused = self.is_paused(nid)
            phase = "paused" if paused and tl.phase == "idle" else tl.phase
            nodes[nid] = {"round": tl.round, "phase": phase, "paused": paused, "interval_ms": tl.interval_ms,
                          # 已要求停、但這回合還沒收完（probes/sched N1）
                          "pause_pending": paused and phase not in ("paused", "stopped"),
                          "live": self.live_of(nid, tl)}
            if nid in self.steps:
                nodes[nid]["steps_left"] = self.steps[nid]
            if tl.last_error:
                nodes[nid]["last_error"] = tl.last_error
        write_json(os.path.join(self.aosd, "status.json"),
                   {"pid": os.getpid(), "root": self.root, "at": now(), "poll_s": POLL,
                    "gen": self.gen, "io_errors": self.io_errors, "stopping": self.stopping, "stopped": stopped,
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
        # 換世代：之後這個 daemon 起的 tick／tock 帶 AOS7_GEN，舊 daemon 留下的動作拿到 action.lock 時看到世代不同就不寫（astra-4 I-01）
        old = read_json(os.path.join(self.aosd, "gen.json"), {}) or {}
        self.gen = (old.get("gen", 0) if isinstance(old, dict) and isinstance(old.get("gen"), int) else 0) + 1
        write_json(os.path.join(self.aosd, "gen.json"), {"gen": self.gen, "pid": os.getpid(), "at": now()})
        self.log(ev="start", pid=os.getpid(), gen=self.gen)
        while not self.stopping:
            for step in (self.handle_ctl, self.scan, self.write_status):
                self.guard(step)
            time.sleep(POLL)
        self.guard(lambda: self.log(ev="stopping", kill=self.kill_on_stop))
        while any(tl.is_alive() for tl in self.timelines.values()):
            self.guard(self.write_status)
            time.sleep(POLL)
        self._live.clear()
        self.guard(lambda: self.write_status(stopped=True))
        self.guard(lambda: self.log(ev="stop"))
        return 0

    def guard(self, step):
        """主迴圈的一步丟 OSError（磁碟滿、唯讀…）不讓 daemon 直接退出：記到 stderr 與 log（寫得進去的話），下一圈再試（astra-4 I-07）。"""
        try:
            step()
        except OSError as e:
            self.io_errors += 1
            print("aos7-daemon: %s 失敗：%r" % (getattr(step, "__name__", "step"), e), file=sys.stderr, flush=True)
            try:
                self.log(ev="io-error", step=getattr(step, "__name__", "step"), msg=repr(e))
            except OSError:
                pass


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not os.path.isdir(argv[0]):
        print("用法: aos7-daemon <root>（root 要是已存在的資料夾）", file=sys.stderr)
        return 1
    return Daemon(argv[0]).run()
