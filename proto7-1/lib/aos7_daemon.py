"""aos7-daemon：常駐程式——掃 node、每條時間線一個迴圈、讀控制檔、寫 status.json 與 log.jsonl（spec.md 第 1、2 節，S-03～S-06）。

    aos7-daemon <root>

SIGTERM／SIGINT＝stop 加 kill（S-21 路一：子 daemon 被父時間線 kill 時帶走自己的任務）。
"""
import datetime
import errno
import fcntl
import os
import signal
import stat
import sys
import threading
import time

import aos7_task
from aos7_daemon_timeline import POLL, Timeline
from aos7_fs import FD_PREFIX, append_jsonl, is_regular, node_path, now, read_json, write_json

SCAN_BATCH = 20      # 一圈最多起幾條新時間線；多的下一圈再起，主迴圈不停擺（probes/fleet N2）
CTL_BATCH = 200      # 一圈最多處理幾個控制檔；多的下一圈接著做（照檔名順序），status 照常寫（astra-5 F-10）
CTL_BUDGET_S = 0.05  # 一圈處理控制檔最多花幾秒（跟 CTL_BATCH 取先到的）
LIVE_EVERY = 0.25    # status.json 的 live 多久重算一次（秒）；任務資料夾多時每圈全掃太貴（probes/fleet N3、swarm N4）


GONE_ERRNO = (errno.ENOENT, errno.ENOTDIR)   # 這兩種才算「確定不存在」；其他（ESTALE、EIO、EACCES…）是「看不到」


def _probe(path):
    """path 是一般檔／資料夾嗎：回 "file"、"dir"、"other"、None（確定不存在），看不到（I/O 錯）丟 OSError。"""
    try:
        st = os.stat(path)
    except OSError as e:
        if e.errno in GONE_ERRNO:
            return None
        raise
    return "file" if stat.S_ISREG(st.st_mode) else "dir" if stat.S_ISDIR(st.st_mode) else "other"


def scan_nodes(root, errors=None):
    """回 root 底下所有 node id（含 `.aos/timeline.json` 的資料夾）。

    跳過 `.` 開頭的資料夾；含 `.aosd/` 的子資料夾是別的 daemon 的根，整棵不進去（S-15）。
    errors 給一個 dict 時，**看不到**的地方（scandir／stat 丟 ENOENT、ENOTDIR 以外的 OSError：ESTALE、EIO、EACCES…）
    記成 {id: 錯誤}，那個 id（以及它底下）這一圈沒有結論——呼叫的人不能當它消失（astra-5 F-03）。"""
    found = []
    errors = {} if errors is None else errors

    def rel_id(d):
        rel = os.path.relpath(d, root)
        return "." if rel == "." else rel.replace(os.sep, "/")

    todo = [root]
    while todo:
        d = todo.pop()
        try:
            if d != root and _probe(os.path.join(d, ".aosd")) == "dir":
                continue
            if _probe(os.path.join(d, ".aos", "timeline.json")) == "file":
                found.append(rel_id(d))
        except OSError as e:
            errors[rel_id(d)] = repr(e)[:200]
            continue
        try:
            with os.scandir(d) as it:
                subs = [x.path for x in it if not x.name.startswith(".") and x.is_dir(follow_symlinks=False)]
        except OSError as e:
            if e.errno not in GONE_ERRNO:
                errors[rel_id(d)] = repr(e)[:200]
            continue
        todo.extend(sorted(subs, reverse=True))
    return sorted(found)


def under(nid, prefix):
    """node id nid 在 prefix（node id）底下或就是它。"""
    return prefix == "." or nid == prefix or nid.startswith(prefix + "/")


def declared_subroots(root, node_id):
    """node 的 tasks.json 各項與 spawn 檔宣告的合格 `subroot`（空間路徑）：那裡要開子 daemon，父 daemon 不收裡面的 node
    （astra-5 F-08：tick 建 `.aosd/` 之前的第一次掃描也不搶）。"""
    node = node_path(root, node_id)
    items = []
    t = read_json(os.path.join(node, ".aos", "tasks.json"))
    if isinstance(t, dict) and isinstance(t.get("tasks"), list):
        items += t["tasks"]
    sdir = os.path.join(node, ".aos", "spawn")
    try:
        names = sorted(n for n in os.listdir(sdir) if n.endswith(".json") and not n.startswith("."))
    except OSError:
        names = []
    for n in names:
        o = read_json(os.path.join(sdir, n))
        items += o["batch"] if isinstance(o, dict) and isinstance(o.get("batch"), list) else [o]
    out = []
    for it in items:
        sub = it.get("subroot") if isinstance(it, dict) else None
        if isinstance(sub, str):
            good, _ = aos7_task.subroot_of(root, node_id, sub)
            if good:
                out.append(good)
    return out


class Daemon:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        # 自己的 `.aosd` 一律經 root 資料夾的 fd 寫（`/proc/self/fd/N/.aosd`）：root 被搬走就寫到新位置，被刪掉就寫不進去，
        # 不會照舊路徑 makedirs 把它建回來（astra-6 G-03）。root 換了身分由 root_ok 發現，照 stop 收尾
        self.rfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.aosd = FD_PREFIX + str(self.rfd) + "/.aosd"
        self.root_gone = False
        self.timelines = {}
        self.stopping = False
        self.kill_on_stop = False
        self._log_lock = threading.Lock()
        pj = read_json(os.path.join(self.aosd, "paused.json"), {})
        pl = pj.get("paused") if isinstance(pj, dict) else None
        self.paused = set(x for x in pl if isinstance(x, str)) if isinstance(pl, list) else set()
        self.steps = {}              # resume 帶 rounds：{node: 還剩幾回合}，到 0 自動 pause（probes/sched N2）
        self._live = {}              # {node: (monotonic 時間, live 清單)}
        self._pids = {}              # {node: {tid: (pgid, runner_pid)}}：活任務，node 消失時收（Q4）
        self.reapers = []
        self.stopping_since = None
        self.gen = None              # 世代（run 時換）
        self.io_errors = 0
        self.scan_errors = {}        # 上一圈掃描看不到的地方（astra-5 F-03）
        self.ctl_backlog = False     # 上一圈控制檔沒處理完（astra-5 F-10）
        self.ctl_stuck = set()       # 處理失敗、又搬不到 ctl-failed/ 的控制檔名：之後排到最後（astra-6 G-01）
        self.last_ctl_error = None   # 最近一次控制檔處理失敗（status.json 帶出來）

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

    def owner(self):
        """`.aosd/owner.json`（tick 起子 daemon 時寫；Q5）：沒有回 None（頂層 daemon）；壞掉當 {}（不允許）。"""
        path = os.path.join(self.aosd, "owner.json")
        if not os.path.lexists(path):
            return None
        ow = read_json(path)
        return ow if isinstance(ow, dict) else {}

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
            if ctl.get("node") is not None:   # stop 是整個 daemon；帶 node 多半是想停一個 node（probes/llmteam 誤解 4）
                return False, "stop 是整個 daemon，不收 node；要停一個 node 用 pause"
            ow = self.owner()
            if ow is not None and ow.get("allow_stop") is not True:
                # 子 daemon 歸屬起它的 node（使用者 10-03 Q5）：那個 node 沒允許，路二的 stop 不算數
                return False, ("這個 daemon 屬於 node %s（任務 %s），%s 不允許外部 stop；要停請 %s 在 tasks.json 那項設 "
                               "allow_stop: true（或直接改 .aosd/owner.json），或由 %s kill 這個任務" % (
                                   ow.get("node", "?"), ow.get("tid", "?"), ow.get("node", "?"), ow.get("node", "?"),
                                   ow.get("node", "?")))
            if ow is not None:
                # 留標記：擁有者 node 的 tick 看到就不再起這個子 daemon（刪掉標記才會再起）
                write_json(os.path.join(self.aosd, "stopped.json"),
                           {"by": ctl.get("by"), "why": ctl.get("why"), "at": now(), "kill": bool(ctl.get("kill"))})
            self.stop(bool(ctl.get("kill")))
            return True, "stopping" + (" with kill" if self.kill_on_stop else "") + (
                "；已寫 .aosd/stopped.json，%s 不會再起它（刪掉才會）" % ow.get("node", "?") if ow is not None else "")
        if op == "rescan":
            self.scan()
            return True, "rescanned"
        return False, "unknown op %r" % op

    def handle_ctl(self):
        cdir = os.path.join(self.aosd, "ctl")
        try:
            names = sorted(n for n in os.listdir(cdir) if not n.startswith("."))
        except OSError:
            return
        self.ctl_stuck &= set(names)
        # 失敗過、搬不走的排到最後：照檔名順序處理其他件，不會每圈卡在同一件（astra-6 G-01）
        names = [n for n in names if n not in self.ctl_stuck] + [n for n in names if n in self.ctl_stuck]
        self.ctl_backlog = False
        t_end = time.monotonic() + CTL_BUDGET_S
        for k, n in enumerate(names):
            if k >= CTL_BATCH or time.monotonic() >= t_end:
                # 控制檔洪水（一萬個 wake）不能佔住主迴圈：剩下的下一圈接著做，順序照檔名不變（astra-5 F-10）
                self.ctl_backlog = True
                break
            try:
                self.ctl_one(cdir, n)
            except Exception as e:   # noqa: BLE001  一件的回條寫不進去（ctl-done/<名>.json 是資料夾…）不擋同圈其他件（astra-6 G-01）
                self.ctl_failed(cdir, n, e)

    def ctl_one(self, cdir, n):
        path = os.path.join(cdir, n)
        bad = None
        if not n.endswith(".json"):
            bad = "檔名要以 .json 結尾"          # 以前默默略過，寫的人等不到回條（probes/llmkernel）
        elif not is_regular(path):
            bad = "不是一般檔（FIFO、資料夾…）"   # 以前 FIFO 卡死主迴圈、資料夾每圈重處理（probes/chaos B5、B10）
        if bad:
            self.reject_ctl(n, path, bad)
            return
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
        try:
            write_json(os.path.join(self.aosd, "ctl-done", n), ctl)
        except Exception as e:   # noqa: BLE001
            raise RuntimeError("已執行（ok=%s：%s），但回條寫不進去：%r" % (ok, msg, e)) from e
        try:
            os.remove(path)
        except OSError:
            pass
        self.log(ev="ctl", file=n, op=ctl.get("op"), node=ctl.get("node"), by=ctl.get("by"), ok=ok, msg=msg)

    def ctl_failed(self, cdir, n, err):
        """一件控制檔處理失敗：搬到 `.aosd/ctl-failed/<名>`（可追蹤、不再每圈重做）；搬不走就留在 ctl/、之後排到最後。
        log `ev: "ctl-error"`，status 的 `io_errors` +1、`last_ctl_error` 記下來（astra-6 G-01）。"""
        self.io_errors += 1
        moved = None
        try:
            fdir = os.path.join(self.aosd, "ctl-failed")
            os.makedirs(fdir, exist_ok=True)
            dst = os.path.join(fdir, n)
            if os.path.lexists(dst):
                dst = os.path.join(fdir, "%s.%d" % (n, time.time_ns()))
            os.rename(os.path.join(cdir, n), dst)
            moved = "ctl-failed/" + os.path.basename(dst)
        except OSError:
            self.ctl_stuck.add(n)
        self.last_ctl_error = {"file": n, "at": now(), "err": repr(err)[:300], "moved_to": moved}
        try:
            self.log(ev="ctl-error", file=n, err=repr(err)[:300], moved_to=moved)
        except OSError:
            pass

    def reject_ctl(self, n, path, msg):
        """不是 `<名>.json` 一般檔的控制檔：原物搬到 ctl-done/<名>.bad，另寫 ctl-done/<名>.json 回條 ok: false。"""
        done = os.path.join(self.aosd, "ctl-done")
        os.makedirs(done, exist_ok=True)
        base = n if n.endswith(".json") else n + ".json"
        dst = os.path.join(done, n + ".bad")
        if os.path.lexists(dst):
            dst = os.path.join(done, "%s.%d.bad" % (n, time.time_ns()))
        try:
            os.rename(path, dst)
        except OSError:
            pass
        write_json(os.path.join(done, base), {"raw": "not read", "result": {"ok": False, "msg": msg, "at": now(),
                                                                          "queued_at": None}})
        self.log(ev="ctl", file=n, op=None, ok=False, msg=msg)

    def stop(self, kill):
        if not self.stopping:
            self.stopping_since = time.monotonic()   # 正在跑的 tick／tock 最多再等 STOP_GRACE 秒
        self.stopping = True
        self.kill_on_stop = self.kill_on_stop or kill
        for tl in self.timelines.values():
            tl.wake.set()

    # ---------- node ----------

    def scan(self):
        if self.stopping:
            return
        errors = {}
        now_ids = set(scan_nodes(self.root, errors))
        if errors:
            # 看不到（ESTALE、EIO、EACCES…）不等於消失：那底下既有的 node 與 pgid 都留著、不 kill，下一圈重掃（astra-5 F-03）
            self.io_errors += 1
            if errors != self.scan_errors:
                self.log(ev="scan-error", errors=errors)
            now_ids |= {nid for nid in self.timelines if any(under(nid, e) for e in errors)}
        elif self.scan_errors:
            self.log(ev="scan-ok")
        self.scan_errors = errors
        new = sorted(now_ids - set(self.timelines))
        if new:
            subs = []
            for nid in now_ids:
                if any(under(x, nid) and x != nid for x in new):   # 只看新 node 的祖先 node
                    subs += declared_subroots(self.root, nid)
            new = [x for x in new if not any(under(x, sr) for sr in subs)]   # 子 daemon 的地盤，不收（astra-5 F-08）
        for nid in new[:SCAN_BATCH]:
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
            self.reap_gone(nid, tl.node)

    def live_of(self, nid, tl):
        t, live = self._live.get(nid, (None, None))
        if t is None or time.monotonic() - t >= LIVE_EVERY:
            live = aos7_task.live_tasks(tl.node)
            self._live[nid] = (time.monotonic(), live)
            # 記著活任務的 pgid／runner：node 被 rm -rf（pid.json 跟著沒了）也收得到（Q4）
            pids = {}
            for tid in live:
                p = read_json(os.path.join(aos7_task.task_dir(tl.node, tid), "pid.json"))
                if isinstance(p, dict):
                    pids[tid] = (p.get("pgid"), p.get("runner_pid"))
            self._pids[nid] = pids
        return live

    def reap_gone(self, nid, node):
        """node 消失：kill 它上面的活任務（使用者 10-03 Q4 選 (a)；搬家＝舊任務全死，新位置由 keep 重起）。在背景做，不擋主迴圈。"""
        known = list(self._pids.pop(nid, {}).values())

        def work():
            n, clean = aos7_task.kill_node_procs(node, known)
            if n:
                self.log(ev="node-gone-kill", node=nid, groups=n, ok=clean)
        th = threading.Thread(target=work, name="reap:" + nid, daemon=True)
        th.start()
        self.reapers.append(th)

    def sweep_leftovers(self):
        """stop 帶 kill（含 SIGTERM）的最後一步：各時間線收完活任務後，再一次掃 /proc，把環境變數 AOS7_NODE 是本 daemon
        各 node 的程序（已結束任務留下的子孫、tasks-old 裡任務的也算）連群組收掉（astra-5 F-01）。log `ev: "stop-sweep"`。"""
        nodes = [tl.node for tl in self.timelines.values()]
        if not nodes:
            return
        n, clean = aos7_task.sweep_nodes(nodes)
        self.log(ev="stop-sweep", groups=n, ok=clean)

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
        st = {"pid": os.getpid(), "root": self.root, "at": now(), "poll_s": POLL,
              "gen": self.gen, "io_errors": self.io_errors, "stopping": self.stopping, "stopped": stopped,
              "kill_on_stop": self.kill_on_stop, "nodes": nodes}
        if self.last_ctl_error:
            st["last_ctl_error"] = self.last_ctl_error
        if self.root_gone:
            st["root_gone"] = True
        write_json(os.path.join(self.aosd, "status.json"), st)

    def check_root(self):
        """root 的字串路徑還指著自己抓著的資料夾嗎：被刪（ENOENT／ENOTDIR）或搬走、換成別的（inode 不同）＝root 消失，
        照 stop 帶 kill 收尾（Q4：搬家＝舊任務全死；astra-6 G-03）。ESTALE、EIO 這類看不到的不算。"""
        try:
            same = os.path.samestat(os.stat(self.root), os.fstat(self.rfd))
        except OSError as e:
            if e.errno not in GONE_ERRNO:
                return
            same = False
        if same:
            return
        if not self.root_gone:
            self.root_gone = True
            self.stop(True)
            try:
                self.log(ev="root-gone", root=self.root)   # 搬走的寫到新位置；刪掉的寫不進去
            except OSError:
                pass

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
        self._save_paused()   # 一起來就有 paused.json（空清單也寫），讀的人不會碰到「不存在」（probes/llmkernel 誤解 3）
        old = read_json(os.path.join(self.aosd, "gen.json"), {}) or {}
        self.gen = (old.get("gen", 0) if isinstance(old, dict) and isinstance(old.get("gen"), int) else 0) + 1
        write_json(os.path.join(self.aosd, "gen.json"), {"gen": self.gen, "pid": os.getpid(), "at": now()})
        self.log(ev="start", pid=os.getpid(), gen=self.gen)
        sp = os.path.join(self.aosd, "stopped.json")
        if os.path.lexists(sp):
            # 被路二 stop 過還是起來了（tick 會擋，所以多半是人手跑的）：算人決定的，標記清掉、記 log（Q5）
            self.log(ev="stopped-cleared", was=read_json(sp))
            try:
                os.remove(sp)
            except OSError:
                pass
        while not self.stopping:
            for step in (self.check_root, self.handle_ctl, self.scan, self.write_status):
                self.guard(step)
            if not self.ctl_backlog:
                time.sleep(POLL)
        self.guard(lambda: self.log(ev="stopping", kill=self.kill_on_stop))
        while any(tl.is_alive() for tl in self.timelines.values()):
            self.guard(self.write_status)
            time.sleep(POLL)
        if self.kill_on_stop:
            self.guard(self.sweep_leftovers)
        for th in self.reapers:
            th.join(5)
        self._live.clear()
        self.guard(lambda: self.write_status(stopped=True))
        self.guard(lambda: self.log(ev="stop"))
        return 0

    def guard(self, step):
        """主迴圈的一步丟例外（OSError：磁碟滿、唯讀…；其他：壞檔）不讓 daemon 直接退出：記到 stderr 與 log（寫得進去的話），下一圈再試（astra-4 I-07）。"""
        try:
            step()
        except Exception as e:   # 不只 OSError：某個 node 的壞檔丟出的任何例外都不讓 daemon 退出（probes/chaos B1）
            self.io_errors += 1
            print("aos7-daemon: %s 失敗：%r" % (getattr(step, "__name__", "step"), e), file=sys.stderr, flush=True)
            try:
                self.log(ev="io-error" if isinstance(e, OSError) else "error", step=getattr(step, "__name__", "step"),
                         msg=repr(e))
            except OSError:
                pass


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not os.path.isdir(argv[0]):
        print("用法: aos7-daemon <root>（root 要是已存在的資料夾）", file=sys.stderr)
        return 1
    return Daemon(argv[0]).run()
