"""aos7-daemon：常駐程式——只跑登記在 `.aosd/nodes.json` 的 node（不掃資料夾）、每條時間線一個迴圈、讀控制檔、寫 status.json
（spec.md 第 1、2 節，S-03～S-06）。

    aos7-daemon <root>

SIGTERM／SIGINT＝stop 加 kill（S-21 路一：子 daemon 被父時間線 kill 時帶走自己的任務）。
起點是 proto7-1 lib/aos7_daemon.py；掃描、rescan、log.jsonl（改成 log.on 開關）、retention／disk 拿掉，加上 register／unregister、
pause owner、node 消失的 inode 比對。
"""
import datetime
import errno
import fcntl
import os
import shutil
import signal
import stat
import sys
import threading
import time

import aos7_proc
import aos7_task
from aos7_daemon_timeline import POLL, Timeline
from aos7_fs import (FD_PREFIX, append_jsonl, is_int, is_regular, node_path, now, read_json, write_json)

CTL_BATCH = 200      # 一圈最多處理幾個控制檔（2.3）
CTL_BUDGET_S = 0.05  # 一圈處理控制檔最多花幾秒（跟 CTL_BATCH 取先到的）
LIVE_EVERY = 0.25    # status.json 的 live 與記著的 pgid 多久重算一次（秒；2.6、2.8）
GONE_ERRNO = (errno.ENOENT, errno.ENOTDIR)   # 這兩種才算「確定不存在」；其他（ESTALE、EIO、EACCES…）是「看不到」


def norm_id(node):
    """控制檔裡的 node → node id（`/` 分隔，根是 "."）；不合（絕對路徑、`..`、`.` 開頭的段、非字串）回 None。"""
    if not isinstance(node, str) or node.startswith("/") or "\0" in node:
        return None
    parts = [p for p in node.split("/") if p not in ("", ".")]
    if any(p == ".." or p.startswith(".") for p in parts):
        return None
    return "/".join(parts) or "."


def _replace(src, dst):
    """搬 src 到 dst，蓋掉同名舊的（資料夾也蓋）：只留最近一份（spec 2.3）。"""
    if os.path.isdir(dst) and not os.path.islink(dst):
        shutil.rmtree(dst)
    os.replace(src, dst)


class Daemon:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        # 自己的 `.aosd` 一律經 root 的 fd 讀寫：root 被搬走寫到新位置，被刪就寫不進去（2.5）
        self.rfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.aosd = FD_PREFIX + str(self.rfd) + "/.aosd"
        self.root_gone = False
        self.registry = {}           # nodes.json 的內容 {id: {"by", "at"}}
        self.timelines = {}          # {id: Timeline}
        self.missing = {}            # {id: {"since", "why"}}：已登記、資料夾不在
        self.node_errors = {}        # {id: last_error}：沒有時間線時的錯誤（看不到…）
        self.reapers = {}            # {id: thread}：node 消失時在背景收程序；收完才重開時間線
        self.retiring = {}           # {id: (Timeline, kill)}：unregister 中
        self.stopping = False
        self.stopping_since = None
        self.kill_on_stop = False
        self._lock = threading.Lock()
        self.paused = {}             # {id: [owner...]}（2.4）
        self.steps = {}              # {id: {"owner", "left"}}：resume 帶 rounds
        self._live = {}              # {id: (monotonic, [run id])}
        self._pgids = {}             # {id: {pgid}}：活任務的程序群組，node 消失時收（2.6）
        self.gen = None
        self.io_errors = 0
        self.ctl_backlog = False
        self.ctl_stuck = set()
        self.last_ctl_error = None
        self.last_event = None

    # ---------- 小工具 ----------

    def log(self, **kw):
        """記一件事：status 的 last_event 只留最近一件；有 `.aosd/log.on` 才追加到 log.jsonl（W9）。"""
        ev = dict(at=now(), **kw)
        self.last_event = ev
        try:
            if os.path.lexists(os.path.join(self.aosd, "log.on")):
                with self._lock:
                    append_jsonl(os.path.join(self.aosd, "log.jsonl"), ev)
        except OSError:
            pass

    def save_nodes(self):
        write_json(os.path.join(self.aosd, "nodes.json"), {"nodes": self.registry})

    def save_paused(self):
        write_json(os.path.join(self.aosd, "paused.json"),
                   {"paused": {k: v for k, v in sorted(self.paused.items()) if v}})

    def load_state(self):
        nj = read_json(os.path.join(self.aosd, "nodes.json"))
        nodes = nj.get("nodes") if isinstance(nj, dict) else None
        if isinstance(nodes, dict):
            self.registry = {k: (v if isinstance(v, dict) else {}) for k, v in nodes.items() if norm_id(k) == k}
        elif nj is not None:
            self.node_errors["."] = {"prog": "nodes.json", "at": now(), "err": "nodes.json 讀不懂，當空的（沒改它）"}
        pj = read_json(os.path.join(self.aosd, "paused.json"), {})
        pl = pj.get("paused") if isinstance(pj, dict) else None
        if isinstance(pl, dict):
            self.paused = {k: [o for o in v if isinstance(o, str)] for k, v in pl.items() if isinstance(v, list)}
        elif isinstance(pl, list):   # proto7-1 的格式：一個 node 一個開關 → 不帶 owner 的那一格
            self.paused = {k: [""] for k in pl if isinstance(k, str)}

    def is_paused(self, nid):
        return bool(self.paused.get(nid))

    def round_done(self, nid):
        """時間線每關上一回合呼叫：resume 帶 rounds 的倒數，到 0 以同一個 owner 再 pause（2.4）。"""
        with self._lock:
            s = self.steps.get(nid)
            if not s:
                return
            s["left"] -= 1
            if s["left"] > 0:
                return
            del self.steps[nid]
            lst = self.paused.setdefault(nid, [])
            if s["owner"] not in lst:
                lst.append(s["owner"])
            self.save_paused()
        self.log(ev="steps-done", node=nid, owner=s["owner"])

    def other_root(self, nid):
        """node 落在別的 daemon 的根（含 `.aosd/` 的子資料夾）底下時，回那個根的 id；否則 None（S-15）。"""
        parts = [p for p in nid.split("/") if p not in ("", ".")]
        for k in range(1, len(parts) + 1):
            sub = "/".join(parts[:k])
            if os.path.isdir(os.path.join(node_path(self.root, sub), ".aosd")):
                return sub
        return None

    def owner(self):
        """`.aosd/owner.json` 的 owner 塊（2.7）：沒有這個檔回 None（頂層 daemon）；壞掉或沒有 owner 塊當 {}（不允許）。"""
        path = os.path.join(self.aosd, "owner.json")
        if not os.path.lexists(path):
            return None
        ow = read_json(path)
        o = ow.get("owner") if isinstance(ow, dict) else None
        return o if isinstance(o, dict) else {}

    def claim_owner(self):
        """拿到 daemon.lock 之後才寫 owner.json（2.7、K-08）：owner 塊照 tick 給的三個環境變數（任務重起時照項目重寫），
        沒給就沿用（人手重開）；daemon 塊每次都更新。三個變數用完從環境拿掉。頂層 daemon（沒 owner 也沒給變數）不寫。"""
        env = os.environ
        onode, otid, allow = env.pop("AOS7_OWNER_NODE", None), env.pop("AOS7_OWNER_TID", None), \
            env.pop("AOS7_ALLOW_STOP", None)
        sub = env.get("AOS7_SUBROOT")
        path = os.path.join(self.aosd, "owner.json")
        owner = None
        if onode and otid and sub:
            try:
                if os.path.samestat(os.stat(sub), os.fstat(self.rfd)):
                    owner = {"node": onode, "tid": otid, "allow_stop": allow == "1"}
            except OSError:
                pass
        if owner is None:
            if not os.path.lexists(path):
                return
            cur = read_json(path)
            if not (isinstance(cur, dict) and isinstance(cur.get("owner"), dict)):
                return   # 壞掉的不蓋（stop 照樣當不允許）
            owner = cur["owner"]
        write_json(path, {"owner": owner, "daemon": {"pid": os.getpid(), "since": now()}})

    # ---------- 控制檔 ----------

    def apply(self, ctl):
        """執行一個 daemon 控制，回 (ok, msg)。"""
        op = ctl.get("op")
        if op in ("register", "unregister", "pause", "resume", "wake"):
            nid = norm_id(ctl.get("node"))
            if nid is None:
                return False, "%s 要給 node（相對空間根的路徑，不能是絕對、不能有 .. 或 . 開頭的段），拿到 %r" % (
                    op, ctl.get("node"))
            if op != "unregister":
                sub = self.other_root(nid)
                if sub:
                    return False, "%s 屬於 daemon %s（寫那個 daemon 的控制檔）" % (nid, sub)
            return getattr(self, "op_" + op)(nid, ctl)
        if op == "stop":
            return self.op_stop(ctl)
        return False, "unknown op %r" % (op,)

    def op_register(self, nid, ctl):
        if nid in self.registry:
            return True, "%s 已登記" % nid
        real_root = os.path.realpath(self.root)
        p = node_path(self.root, nid)
        q = p
        while not os.path.lexists(q) and q != self.root:
            q = os.path.dirname(q)
        rq = os.path.realpath(q)
        if not (rq == real_root or rq.startswith(real_root + os.sep)):
            return False, "%s 沿符號連結跑出空間根（%s），不登記" % (nid, rq)
        if os.path.lexists(p) and not os.path.isdir(p):
            return False, "%s 不是資料夾，不登記" % nid
        self.registry[nid] = {"by": ctl.get("by"), "at": now()}
        self.save_nodes()
        self.log(ev="register", node=nid, by=ctl.get("by"))
        return True, "registered %s%s" % (nid, "" if os.path.isdir(p) else "（資料夾目前不在，出現時才開回合）")

    def op_unregister(self, nid, ctl):
        if nid not in self.registry:
            return True, "%s 沒有登記" % nid
        kill = ctl.get("kill", True) is not False
        del self.registry[nid]
        self.save_nodes()
        tl = self.timelines.pop(nid, None)
        self.missing.pop(nid, None)
        self.steps.pop(nid, None)
        if tl and tl.is_alive():
            tl.retire, tl.retire_kill = True, kill
            tl.wake.set()
            self.retiring[nid] = (tl, kill)
        elif kill:
            self.reap(nid, node_path(self.root, nid), "unregister-kill")
        self.log(ev="unregister", node=nid, by=ctl.get("by"), kill=kill)
        return True, "unregistered %s（%s）" % (nid, "活任務會被收掉" if kill else "kill: false，任務留著、從此收不到 tock")

    def op_pause(self, nid, ctl):
        owner = ctl.get("owner", "")
        if not isinstance(owner, str):
            return False, "owner 要是字串"
        with self._lock:
            lst = self.paused.setdefault(nid, [])
            if owner not in lst:
                lst.append(owner)
            if (self.steps.get(nid) or {}).get("owner") == owner:
                del self.steps[nid]
            self.save_paused()
        return True, "pause %s（owner %r；現在：%s）%s" % (nid, owner, self.paused[nid], self._note(nid))

    def op_resume(self, nid, ctl):
        owner = ctl.get("owner", "")
        rounds = ctl.get("rounds")
        if not isinstance(owner, str):
            return False, "owner 要是字串"
        if rounds is not None and (not is_int(rounds) or rounds < 1):
            return False, "rounds 要是正整數"
        with self._lock:
            lst = self.paused.setdefault(nid, [])
            if ctl.get("all") is True:
                lst.clear()
            elif owner in lst:
                lst.remove(owner)
            if (self.steps.get(nid) or {}).get("owner") == owner or ctl.get("all") is True:
                self.steps.pop(nid, None)
            if rounds is not None:
                self.steps[nid] = {"owner": owner, "left": rounds}
            self.save_paused()
            left = list(lst)
        if not left:
            self._kick(nid)   # 沒人 pause 了：順便 wake（N-84）
        return True, "resume %s（owner %r%s%s）；%s%s" % (
            nid, owner, "，all" if ctl.get("all") is True else "", "，rounds=%d" % rounds if rounds else "",
            "還有 %s 在 pause" % left if left else "沒人 pause 了，馬上開回合", self._note(nid))

    def op_wake(self, nid, ctl):
        self._kick(nid)
        return True, "wake %s%s" % (nid, self._note(nid))

    def _kick(self, nid):
        tl = self.timelines.get(nid)
        if tl:
            tl.kick = True
            tl.wake.set()

    def _note(self, nid):
        if nid not in self.registry:
            return "（%s 沒有登記，登記後才生效）" % nid
        return "" if nid in self.timelines else "（目前沒有這個 node 的資料夾，出現時才生效）"

    def op_stop(self, ctl):
        if ctl.get("node") is not None:
            return False, "stop 是整個 daemon，不收 node；要停一個 node 用 pause 或 unregister"
        ow = self.owner()
        if ow is not None and ow.get("allow_stop") is not True:
            return False, ("這個 daemon 屬於 node %s（任務 %s），不允許外部 stop；要停請 %s 在 tasks.json 那項設 "
                           "allow_stop: true，或由 %s kill 這個任務" % (ow.get("node", "?"), ow.get("tid", "?"),
                                                                      ow.get("node", "?"), ow.get("node", "?")))
        if ow is not None:
            write_json(os.path.join(self.aosd, "stopped.json"),
                       {"by": ctl.get("by"), "why": ctl.get("why"), "at": now(), "kill": bool(ctl.get("kill"))})
        self.stop(bool(ctl.get("kill")))
        return True, "stopping" + (" with kill" if self.kill_on_stop else "") + (
            "；已寫 .aosd/stopped.json，%s 不會再起它（刪掉才會）" % ow.get("node", "?") if ow is not None else "")

    def handle_ctl(self):
        cdir = os.path.join(self.aosd, "ctl")
        try:
            names = sorted(n for n in os.listdir(cdir) if not n.startswith("."))
        except OSError:
            return
        self.ctl_stuck &= set(names)
        names = [n for n in names if n not in self.ctl_stuck] + [n for n in names if n in self.ctl_stuck]
        self.ctl_backlog = False
        t_end = time.monotonic() + CTL_BUDGET_S
        for k, n in enumerate(names):
            if k >= CTL_BATCH or time.monotonic() >= t_end:
                self.ctl_backlog = True   # 剩下的下一圈接著做（照檔名順序）
                break
            try:
                self.ctl_one(cdir, n)
            except Exception as e:   # noqa: BLE001  一件出事不擋同圈其他件（特別是 stop）
                self.ctl_failed(cdir, n, e)

    def ctl_one(self, cdir, n):
        path = os.path.join(cdir, n)
        done = os.path.join(self.aosd, "ctl-done")
        bad = None
        if not n.endswith(".json"):
            bad = "檔名要以 .json 結尾"
        elif not is_regular(path):
            bad = "不是一般檔（FIFO、資料夾…）"
        if bad:
            os.makedirs(done, exist_ok=True)
            base = n if n.endswith(".json") else n + ".json"
            try:
                _replace(path, os.path.join(done, n + ".bad" if n.endswith(".json") else base[:-5] + ".bad"))
            except OSError:
                pass
            write_json(os.path.join(done, base), {"raw": "not read", "result": {"ok": False, "msg": bad, "at": now(),
                                                                              "queued_at": None}})
            self.log(ev="ctl", file=n, op=None, ok=False, msg=bad)
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
            dst = os.path.join(done, n)
            if os.path.isdir(dst) and not os.path.islink(dst):
                shutil.rmtree(dst)
            write_json(dst, ctl)   # 同名的舊回條直接蓋掉（每個名字只留最近一份；W3）
        except Exception as e:   # noqa: BLE001
            raise RuntimeError("已執行（ok=%s：%s），但回條寫不進去：%r" % (ok, msg, e)) from e
        try:
            os.remove(path)
        except OSError:
            pass
        self.log(ev="ctl", file=n, op=ctl.get("op"), node=ctl.get("node"), by=ctl.get("by"), ok=ok, msg=msg)

    def ctl_failed(self, cdir, n, err):
        """一件控制檔處理丟例外：原物搬到 `.aosd/ctl-failed/<名>`（蓋掉同名舊的）；搬不走就留在 ctl/、之後排到最後。"""
        self.io_errors += 1
        moved = None
        try:
            fdir = os.path.join(self.aosd, "ctl-failed")
            os.makedirs(fdir, exist_ok=True)
            _replace(os.path.join(cdir, n), os.path.join(fdir, n))
            moved = "ctl-failed/" + n
        except OSError:
            self.ctl_stuck.add(n)
        self.last_ctl_error = {"file": n, "at": now(), "err": repr(err)[:300], "moved_to": moved}
        self.log(ev="ctl-error", file=n, err=repr(err)[:300], moved_to=moved)

    def stop(self, kill):
        if not self.stopping:
            self.stopping_since = time.monotonic()
        self.stopping = True
        self.kill_on_stop = self.kill_on_stop or kill
        for tl in self.timelines.values():
            tl.wake.set()

    # ---------- node ----------

    def check_nodes(self):
        """每圈只看已登記的 node（2.6）：確定不存在或 inode 換了 → 收程序、時間線停、phase missing、登記保留；
        看不到＝不知道，保留現狀；在、沒有時間線（而且收程序做完了）→ 開時間線。"""
        if self.stopping:
            return
        for nid, (tl, kill) in list(self.retiring.items()):
            if not tl.is_alive():
                del self.retiring[nid]
                if kill and nid not in self.registry:
                    self.reap(nid, tl.node, "unregister-kill")
        for nid in sorted(self.registry):
            path = node_path(self.root, nid)
            tl = self.timelines.get(nid)
            try:
                st = os.stat(path)
                gone = None if stat.S_ISDIR(st.st_mode) else "不是資料夾了"
            except OSError as e:
                if e.errno not in GONE_ERRNO:
                    err = {"prog": "daemon", "rc": None, "at": now(), "err": "看不到 node（%r），保留現狀" % e}
                    if tl:
                        tl.last_error = err
                    else:
                        self.node_errors[nid] = err
                    continue
                gone, st = "不存在", None
            if tl and not gone and (st.st_dev, st.st_ino) != tl.node_ident:
                gone = "inode 換了（被搬走或換成別的資料夾）"
            if gone:
                if tl:
                    self.timelines.pop(nid)
                    tl.gone = True
                    tl.wake.set()
                    self.steps.pop(nid, None)
                    self._live.pop(nid, None)
                    self.reap(nid, path, "node-gone-kill", why=gone)
                if nid not in self.missing:
                    self.missing[nid] = {"since": now(), "why": gone}
                continue
            if tl:
                continue
            r = self.reapers.get(nid)
            if r is not None and r.is_alive():
                continue   # 收程序還沒做完：新時間線的任務會被一起收掉，等它
            if any(t.node_id == nid for t, _ in self.retiring.values()):
                continue
            self.missing.pop(nid, None)
            self.node_errors.pop(nid, None)
            tl = Timeline(self, nid, (st.st_dev, st.st_ino))
            self.timelines[nid] = tl
            tl.start()
            self.log(ev="node+", node=nid, round=tl.round, **({"paused": True} if self.is_paused(nid) else {}))

    def reap(self, nid, node, ev, why=None):
        """背景收掉 node 上的任務（Q1 範圍：記著的 pgid＋環境變數 AOS7_NODE 相符），不擋主迴圈。"""
        known = self._pgids.pop(nid, set())

        def work():
            n, clean = aos7_proc.kill_node(node, known)
            self.log(ev=ev, node=nid, groups=n, ok=clean, **({"why": why} if why else {}))
        th = threading.Thread(target=work, name="reap:" + nid, daemon=True)
        self.reapers[nid] = th
        th.start()

    def kill_live(self, nid, node):
        """時間線呼叫：stop 或 unregister 帶 kill 時收掉本 node 所有活任務（逐槽照 Q1 範圍）。"""
        slots, _ = aos7_task.list_slots(node)
        for slot in slots:
            fslot = aos7_task.slot_dir(node, slot)
            try:
                v = aos7_task.judge(fslot, node, slot, None)
                if v.state in (aos7_task.LIVE, aos7_task.SUSPECT) and v.run is not None:
                    ok, msg = aos7_task.kill_run(fslot, node, slot, v)
                    self.log(ev="kill", node=nid, run=aos7_task.run_id(slot, v.run), ok=ok, msg=msg)
            except Exception as e:   # noqa: BLE001
                self.log(ev="kill-error", node=nid, slot=slot, err=repr(e)[:200])
        aos7_proc.kill_node(node, self._pgids.get(nid, ()))

    def live_of(self, nid, tl):
        """活任務的 run id（每 LIVE_EVERY 秒重算），順便記 pgid（2.6）。只讀不殺：疑似 lost 不算活。"""
        t, live = self._live.get(nid, (None, None))
        if t is not None and time.monotonic() - t < LIVE_EVERY:
            return live
        live, pgids = [], set()
        slots, _ = aos7_task.list_slots(tl.node)
        for slot in slots:
            fslot = aos7_task.slot_dir(tl.node, slot)
            try:
                v = aos7_task.judge(fslot, tl.node, slot, tl.round)
            except Exception:   # noqa: BLE001
                continue
            if v.state in (aos7_task.LIVE, aos7_task.UNKNOWN) and v.run is not None:
                live.append(aos7_task.run_id(slot, v.run))
                pid = read_json(os.path.join(fslot, "pid.json"))
                if isinstance(pid, dict) and pid.get("run") == v.run and is_int(pid.get("pgid")):
                    pgids.add(pid["pgid"])
        self._live[nid] = (time.monotonic(), live)
        self._pgids[nid] = pgids
        return live

    def sweep_leftovers(self):
        nodes = [node_path(self.root, n) for n in self.registry]
        if nodes:
            n, clean = aos7_proc.sweep_nodes(nodes)
            self.log(ev="stop-sweep", groups=n, ok=clean)

    # ---------- status ----------

    def write_status(self, stopped=False):
        nodes = {}
        for nid in sorted(set(self.registry) | set(self.timelines)):
            tl = self.timelines.get(nid)
            by = list(self.paused.get(nid) or [])
            if tl is None:
                row = {"round": None, "round_open": None, "recovery_pending": False,
                       "phase": "missing" if nid in self.missing else ("stopped" if stopped else "idle"),
                       "paused_by": by, "pause_pending": False, "interval_ms": None, "early_tock": None, "live": []}
                if nid in self.missing:
                    row["missing"] = self.missing[nid]
                if nid in self.node_errors:
                    row["last_error"] = self.node_errors[nid]
            else:
                phase = "paused" if by and tl.phase == "idle" else tl.phase
                row = {"round": tl.round, "round_open": tl.round_open, "recovery_pending": tl.recovery_pending,
                       "phase": phase, "paused_by": by,
                       "pause_pending": bool(by) and phase not in ("paused", "stopped", "error"),
                       "interval_ms": tl.interval_ms, "early_tock": tl.early_tock, "live": self.live_of(nid, tl)}
                if tl.last_error:
                    row["last_error"] = tl.last_error
                if tl.last_event:
                    row["last_event"] = tl.last_event
            if nid in self.steps:
                row["steps_left"] = self.steps[nid]["left"]
            nodes[nid] = row
        st = {"pid": os.getpid(), "root": self.root, "at": now(), "poll_s": POLL, "gen": self.gen,
              "io_errors": self.io_errors, "stopping": self.stopping, "stopped": stopped,
              "last_event": self.last_event, "nodes": nodes}
        if self.last_ctl_error:
            st["last_ctl_error"] = self.last_ctl_error
        if self.root_gone:
            st["root_gone"] = True
        write_json(os.path.join(self.aosd, "status.json"), st)

    def check_root(self):
        """root 的字串路徑還指著抓著的資料夾嗎：確定不存在或 inode 換了＝root 消失，照 stop 加 kill 收尾（2.5）。"""
        try:
            same = os.path.samestat(os.stat(self.root), os.fstat(self.rfd))
        except OSError as e:
            if e.errno not in GONE_ERRNO:
                return
            same = False
        if not same and not self.root_gone:
            self.root_gone = True
            self.stop(True)
            self.log(ev="root-gone", root=self.root)

    # ---------- 主迴圈 ----------

    def run(self):
        os.makedirs(os.path.join(self.aosd, "ctl"), exist_ok=True)
        lock = open(os.path.join(self.aosd, "daemon.lock"), "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("aos7-daemon: %s 已經有 daemon 在跑" % self.root, file=sys.stderr)
            return 1
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, lambda *_: self.stop(True))
        self.claim_owner()
        self.load_state()
        self.save_paused()   # 一起來就寫一份（空的也寫）
        if not os.path.lexists(os.path.join(self.aosd, "nodes.json")):
            self.save_nodes()
        old = read_json(os.path.join(self.aosd, "gen.json"), {}) or {}
        self.gen = (old.get("gen", 0) if isinstance(old, dict) and is_int(old.get("gen")) else 0) + 1
        write_json(os.path.join(self.aosd, "gen.json"), {"gen": self.gen, "pid": os.getpid(), "at": now()})
        self.log(ev="start", pid=os.getpid(), gen=self.gen)
        sp = os.path.join(self.aosd, "stopped.json")
        if os.path.lexists(sp):
            was = read_json(sp)
            try:
                os.remove(sp)
            except OSError:
                pass
            self.log(ev="stopped-cleared", was=was)
        while not self.stopping:
            for step in (self.check_root, self.handle_ctl, self.check_nodes, self.write_status):
                self.guard(step)
            if not self.ctl_backlog:
                time.sleep(POLL)
        self.guard(lambda: self.log(ev="stopping", kill=self.kill_on_stop))
        alive = list(self.timelines.values()) + [t for t, _ in self.retiring.values()]
        while any(tl.is_alive() for tl in alive):
            self.guard(self.write_status)
            time.sleep(POLL)
        if self.kill_on_stop:
            self.guard(self.sweep_leftovers)
        for th in list(self.reapers.values()):
            th.join(5)
        self._live.clear()
        self.guard(lambda: self.write_status(stopped=True))
        self.guard(lambda: self.log(ev="stop"))
        return 0

    def guard(self, step):
        """主迴圈的一步丟例外不讓 daemon 退出：io_errors +1、stderr 說明，下一圈再試。"""
        try:
            step()
        except Exception as e:   # noqa: BLE001
            self.io_errors += 1
            print("aos7-daemon: %s 失敗：%r" % (getattr(step, "__name__", "step"), e), file=sys.stderr, flush=True)
            try:
                self.log(ev="error", step=getattr(step, "__name__", "step"), msg=repr(e)[:300])
            except Exception:   # noqa: BLE001
                pass


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not os.path.isdir(argv[0]):
        print("用法: aos7-daemon <root>（root 要是已存在的資料夾）", file=sys.stderr)
        return 1
    return Daemon(argv[0]).run()
