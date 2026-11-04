"""chaos：決定性亂數同時高頻亂寫整個控制面，邊亂邊檢查 daemon／tick／tock 的不變式；另有一段「最小重現」逐條試會弄壞基礎設施的單一輸入。

    python3 proto7-1/probes/chaos/probe.py [--seed N] [--long] [--poison] [--no-a] [--no-b]

- A 段（亂）：6 條時間線＋一個會被 rm -rf 再重建的 `eph`＋一個假子 daemon 根 `sub/`（只有 `.aosd/`）。
  一個 thread 每 3～12 ms 做一件事：daemon ctl（合法／不認得的 op、壞 JSON、`[]`、同一批 pause+resume+wake、resume rounds、
  對不存在／子 daemon 底下的 node）、改 tasks.json（keep/each、max_live、from_round、壞欄位、整份壞）、改 timeline.json
  （壞 interval、拿掉再寫回＝node 消失又出現）、spawn（單一、batch、壞檔）、任務 ctl.json（kill/restart/壞的，對活的或已結束的）。
  任務自己也亂（task.py：立刻死、不理 SIGTERM、留孫程序、雙 fork、刪自己的 taskdir、等 tock、亂請加掛）。
  另一個 thread 每 30 ms 看 status：daemon 活著、`at` 有在動、每個 node 的 round 不倒退。
  亂完收斂（寫回正常設定、resume 全部），再查 rounds.jsonl、ctl、tasks-old，最後 stop --kill 查殘留程序。
- B 段（最小重現）：每條一個最小輸入，記「重現了沒」與證據。這些是現在會壞的，記成量與發現，不放 check。
- `--poison`：A 段也混進 B 段那些毒輸入（預期會紅，用來看連鎖反應）。
"""
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import aos7_fs as fs  # noqa: E402

PY = sys.executable
T = os.path.join(HERE, "task.py")
NODES = ["n0", "n1", "n2", "n3", "n4", "n5"]
KEEP_ENDED = {"n0": 2, "n1": 5}        # 其他用預設 20：搬 tasks-old 的要常發生


def raw_write(path, text):
    """原子寫任意文字（壞 JSON 也要整份一次出現）。"""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.chaos.%d" % (os.path.basename(path), threading.get_ident()))
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def jwrite(path, obj):
    raw_write(path, json.dumps(obj))


# ---------------- 亂源 ----------------

def good_items(rng):
    r = lambda a, b: str(round(rng.uniform(a, b), 2))   # noqa: E731  argv 一律字串（非字串見 B4）
    pool = [
        {"name": "ks", "mode": "keep", "argv": [PY, T, "sleep", r(0.2, 2)]},
        {"name": "die", "mode": "each", "argv": [PY, T, "die"]},
        {"name": "ml", "mode": "each", "max_live": 2, "argv": [PY, T, "sleep", r(0.1, 0.8)]},
        {"name": "stub", "mode": "keep", "argv": [PY, T, "stubborn", r(0.5, 2)]},
        {"name": "fk", "mode": "each", "from_round": rng.randint(1, 40), "argv": [PY, T, "forker", "2"]},
        {"name": "pol", "mode": "keep", "argv": [PY, T, "poller", str(rng.randint(1, 4))]},
        {"name": "mq", "mode": "keep", "argv": [PY, T, "mreq", "2"]},
        {"name": "sh", "mode": "each", "argv": ["sh", "-c", "exit 0"]},
        {"name": "nope", "mode": "each", "argv": ["/nonexistent/prog"]},
    ]
    rare = [
        {"name": "df", "mode": "each", "from_round": rng.randint(1, 60), "max_live": 1, "argv": [PY, T, "dfork", "2"]},
        {"name": "sd", "mode": "keep", "argv": [PY, T, "selfdel", "1.5"]},
    ]
    items = rng.sample(pool, rng.randint(1, 4))
    if rng.random() < 0.15:
        items.append(rng.choice(rare))
    return items


BAD_ITEMS = [
    {"name": "b1", "mode": "weird", "argv": ["true"]},
    {"name": "b2", "from_round": "x", "argv": ["true"]},
    {"name": "b3", "argv": "notalist"},
    {"name": "b4", "max_live": "2", "argv": ["true"]},
    {"name": "b5"},
    5,
    "str",
]
POISON_ITEMS = [
    {"name": 5, "argv": ["true"]},                 # B 段 R2
    {"name": "pz", "mode": "keep", "argv": ["sleep", 5]},   # B 段 R4
]


class Chaos:
    def __init__(self, sp, rng, poison=False):
        self.sp, self.rng, self.poison = sp, rng, poison
        self.n = {}
        self.ctl_written = []        # 唯一名字的 daemon ctl 檔
        self.vanish = []             # [(還原時刻, node, timeline 內容)]
        self.vanished = set()
        self.eph_gone_until = None
        self.seq = 0
        self.stop = threading.Event()
        self.errors = []

    def count(self, k):
        self.n[k] = self.n.get(k, 0) + 1

    def ctlname(self, tag):
        self.seq += 1
        return "c-%07d-%s.json" % (self.seq, tag)

    def daemon_ctl(self):
        rng, sp = self.rng, self.sp
        node = rng.choice(NODES + ["eph", "ghost", "sub/x", "sub", "n0/deep"])
        kind = rng.random()
        cdir = os.path.join(sp.root, ".aosd", "ctl")
        if kind < 0.45:
            op = rng.choice(["pause", "resume", "wake", "rescan"])
            obj = {"op": op, "node": node, "by": "chaos"}
            if op == "resume" and rng.random() < 0.4:
                obj["rounds"] = rng.choice([1, 2, 3, 0, "2", -1])
            name = self.ctlname(op)
            jwrite(os.path.join(cdir, name), obj)
        elif kind < 0.6:      # 同一批：pause、resume、wake（依檔名排序執行）
            self.seq += 1
            for k, op in enumerate(["pause", "resume", "wake"]):
                name = "c-%07d-%d-%s.json" % (self.seq, k, op)
                jwrite(os.path.join(cdir, name), {"op": op, "node": node, "by": "chaos-batch"})
                self.ctl_written.append(name)
            self.count("ctl-batch")
            return
        elif kind < 0.75:
            name = self.ctlname("junk")
            raw_write(os.path.join(cdir, name), rng.choice(["{", "[]", "null", "5", '"x"', '{"op": 5}', '{"op": "zap"}',
                                                             '{"op": "pause"}', '{"op": "pause", "node": ["a"]}', ""]))
        else:
            name = self.ctlname("pr")
            jwrite(os.path.join(cdir, name), {"op": rng.choice(["pause", "resume"]), "node": node})
        self.ctl_written.append(name)
        self.count("ctl")

    def tasks_json(self):
        rng = self.rng
        nid = rng.choice(NODES)
        p = self.sp.path(nid, ".aos", "tasks.json")
        k = rng.random()
        if k < 0.7:
            items = good_items(rng)
            if rng.random() < 0.3:
                items.append(rng.choice(BAD_ITEMS))
            if self.poison and rng.random() < 0.2:
                items.append(rng.choice(POISON_ITEMS))
            jwrite(p, {"tasks": items})
        elif k < 0.85:
            raw_write(p, rng.choice(["{", "", "[]", '{"tasks": {}}', '{"tasks": 5}', "null"]))
        else:
            jwrite(p, {"tasks": []})
        self.count("tasks.json")

    def timeline(self):
        rng = self.rng
        nid = rng.choice(NODES)
        p = self.sp.path(nid, ".aos", "timeline.json")
        if nid in self.vanished:
            return
        k = rng.random()
        base = {"keep_ended_rounds": KEEP_ENDED.get(nid, 20)}
        if k < 0.25 and not self.vanished:   # 消失又出現（一次最多一條在消失中）
            try:
                text = open(p).read()
                os.remove(p)
            except OSError:
                return
            self.vanished.add(nid)
            self.vanish.append((time.monotonic() + rng.uniform(0.0, 0.4), nid, text))
            self.count("vanish")
            return
        if k < 0.75:
            jwrite(p, dict(base, interval_ms=rng.choice([30, 50, 80, 120, 200])))
        else:
            raw_write(p, rng.choice(['{"interval_ms": "fast"}', '{"interval_ms": null}', '{"interval_ms": -5}',
                                     '{"interval_ms": 1e999}', '{"interval_ms": 0}', "{", "[]"]))
            self.count("timeline-bad")
        self.count("timeline")

    def spawn(self):
        rng = self.rng
        nid = rng.choice(NODES)
        self.seq += 1
        p = self.sp.path(nid, ".aos", "spawn", "s-%07d.json" % self.seq)
        k = rng.random()
        if k < 0.5:
            jwrite(p, rng.choice(good_items(rng)))
        elif k < 0.8:
            jwrite(p, {"batch": good_items(rng) + rng.sample(BAD_ITEMS[:5], 1)})
        else:
            raw_write(p, rng.choice(["{", "[]", "5", '{"batch": 5}', '{"argv": "x"}']))
        self.count("spawn")

    def task_ctl(self):
        rng = self.rng
        nid = rng.choice(NODES)
        td = self.sp.path(nid, ".aos", "tasks")
        try:
            tids = [t for t in os.listdir(td) if os.path.isfile(os.path.join(td, t, "birth.json"))]
        except OSError:
            return
        if not tids:
            return
        tid = rng.choice(tids[-12:] if rng.random() < 0.8 else tids)
        p = os.path.join(td, tid, "ctl.json")
        k = rng.random()
        try:
            if k < 0.45:
                jwrite(p, {"op": "kill", "by": "chaos"})
            elif k < 0.8:
                jwrite(p, {"op": "restart", "by": "chaos"})
            else:
                raw_write(p, rng.choice(["{", "[]", '{"op": "zap"}', "null"]))
        except OSError:
            return
        self.count("task-ctl")

    def eph(self):
        sp = self.sp
        if self.eph_gone_until is None:
            shutil.rmtree(fs.node_path(sp.root, "eph"), ignore_errors=True)
            self.eph_gone_until = time.monotonic() + self.rng.uniform(0.05, 0.5)
            self.count("eph-rm")

    def restore_due(self, force=False):
        now = time.monotonic()
        for item in list(self.vanish):
            t, nid, text = item
            if force or now >= t:
                raw_write(self.sp.path(nid, ".aos", "timeline.json"), text)
                self.vanish.remove(item)
                self.vanished.discard(nid)
        if self.eph_gone_until is not None and (force or now >= self.eph_gone_until):
            make_eph(self.sp, self.rng)
            self.eph_gone_until = None

    def run(self):
        acts = [(self.daemon_ctl, 30), (self.tasks_json, 15), (self.timeline, 10), (self.spawn, 15),
                (self.task_ctl, 25), (self.eph, 3)]
        fns = [a for a, w in acts for _ in range(w)]
        while not self.stop.is_set():
            try:
                self.restore_due()
                self.rng.choice(fns)()
            except Exception as e:     # 亂源自己的錯不算基礎設施的
                self.errors.append(repr(e)[:200])
            self.stop.wait(self.rng.uniform(0.003, 0.012))
        self.restore_due(force=True)


def make_eph(sp, rng):
    sp.node("eph", [{"name": "e", "mode": "keep", "argv": [PY, T, "sleep", "1"]},
                    {"name": "d", "argv": [PY, T, "die"]}], interval_ms=rng.choice([40, 80]), keep_ended_rounds=3)


class Monitor(threading.Thread):
    def __init__(self, sp, proc):
        super().__init__(daemon=True)
        self.sp, self.proc = sp, proc
        self.stop = threading.Event()
        self.last_at, self.last_change = None, time.monotonic()
        self.max_gap = 0.0
        self.rounds = {}
        self.backwards = []
        self.died = None
        self.samples = 0

    def run(self):
        while not self.stop.wait(0.03):
            if self.proc.poll() is not None:
                self.died = self.proc.returncode
                return
            st = self.sp.status()
            if not st:
                continue
            self.samples += 1
            now = time.monotonic()
            if st.get("at") != self.last_at:
                self.max_gap = max(self.max_gap, now - self.last_change)
                self.last_at, self.last_change = st.get("at"), now
            for nid, v in (st.get("nodes") or {}).items():
                if nid not in NODES:
                    continue
                r = v.get("round")
                if not isinstance(r, int):
                    continue
                if r < self.rounds.get(nid, 0):
                    self.backwards.append((nid, self.rounds[nid], r))
                self.rounds[nid] = max(r, self.rounds.get(nid, 0))


# ---------------- 收斂後的檢查 ----------------

def birth_dirs(d):
    try:
        return {t for t in os.listdir(d) if os.path.isfile(os.path.join(d, t, "birth.json"))}
    except OSError:
        return set()


def analyze_rounds(sp, nid):
    lines = sp.rounds(nid)
    rs = [x.get("round") for x in lines]
    dup = len(rs) - len(set(rs))
    nonincr = sum(1 for a, b in zip(rs, rs[1:]) if not (isinstance(a, int) and isinstance(b, int) and b > a))
    gaps = sum(b - a - 1 for a, b in zip(rs, rs[1:]) if isinstance(a, int) and isinstance(b, int) and b > a + 1)
    ended = [e.get("tid") for x in lines for e in x.get("ended", [])]
    return {"lines": len(lines), "dup": dup, "nonincr": nonincr, "gaps": gaps,
            "ended_dup": len(ended) - len(set(ended)), "incomplete": sum(1 for x in lines if x.get("incomplete")),
            "errors": sum(len(x.get("errors", [])) for x in lines),
            "tasks_error_rounds": sum(1 for x in lines if x.get("tasks_error")),
            "archived": sum(len(x.get("archived", [])) for x in lines)}


def leftovers(base):
    """還活著、AOS7_ROOT 在 base 底下的程序，依 task.py 的行為分類。"""
    out = {}
    for pid in pl.our_procs(base):
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
        except OSError:
            continue
        if T in argv:
            kind = argv[argv.index(T) + 1] if argv.index(T) + 1 < len(argv) else "?"
        else:
            kind = os.path.basename(argv[1]) if len(argv) > 1 and argv[0] == PY else os.path.basename(argv[0]) if argv else "?"
            if kind == "aos7-run" and not os.path.isdir(argv[-1]):
                kind = "selfdel"        # 任務刪了自己的 taskdir：它的 aos7-run 還在等它（同一類）
        out.setdefault(kind, []).append(pid)
    return out


ALLOWED_LEFTOVER = {"forker", "dfork", "selfdel"}   # 已結束任務留下的子孫、刪了自己 taskdir 的：Q1 (a) 任務自己負責


def part_a(r, seed, dur, poison):
    rng = random.Random(seed)
    with pl.Space("chaos") as sp:
        for nid in NODES:
            sp.node(nid, good_items(rng), interval_ms=rng.choice([40, 60, 100]),
                    keep_ended_rounds=KEEP_ENDED.get(nid, None))
        make_eph(sp, rng)
        os.makedirs(os.path.join(sp.root, "sub", ".aosd"))           # 假子 daemon 根：底下的 node 父不該跑
        sp.node("sub/x", [{"name": "nope", "argv": ["true"]}], interval_ms=50)
        proc = sp.start()
        sp.wait_for(lambda: all(sp.round_of(n) >= 1 for n in NODES), 10, msg="node 沒都起來")
        mon = Monitor(sp, proc)
        mon.start()
        ch = Chaos(sp, rng, poison)
        th = threading.Thread(target=ch.run, daemon=True)
        t0 = time.monotonic()
        th.start()
        while time.monotonic() - t0 < dur and mon.died is None:
            time.sleep(0.1)
        ch.stop.set()
        th.join(5)
        r.measure("A 亂源動作數", dict(sorted(ch.n.items())))
        if ch.errors:
            r.measure("A 亂源自己的例外（不算）", ch.errors[:3])
        r.check("A 亂的期間 daemon 沒退出", mon.died is None, mon.died)
        if mon.died is not None:
            r.measure("A daemon 輸出末段", open(os.path.join(sp.base, "daemon-0.out")).read()[-800:])
            return

        # 收斂：寫回正常設定、resume 全部
        r.measure("A 亂完時的 status", {n: (v.get("phase"), v.get("round"), v.get("paused"), v.get("steps_left"), v.get("interval_ms"))
                                         for n, v in (sp.status().get("nodes") or {}).items()})
        for nid in NODES:
            jwrite(sp.path(nid, ".aos", "tasks.json"),
                   {"tasks": [{"name": "calm", "mode": "keep", "argv": [PY, T, "sleep", "30"]}]})
            jwrite(sp.path(nid, ".aos", "timeline.json"), {"interval_ms": 60, "keep_ended_rounds": KEEP_ENDED.get(nid, 20)})
            sp.ctl("resume", nid, by="calm")
        sp.ctl("resume", "eph", by="calm")
        t1 = time.monotonic()
        base_r = {n: sp.round_of(n) for n in NODES}
        try:
            sp.wait_for(lambda: all(sp.round_of(n) >= base_r[n] + 4 for n in NODES), 20, msg="收斂後 node 沒前進")
            converged = True
        except pl.ProbeTimeout:
            converged = False
        r.measure("A 收斂所需秒數", round(time.monotonic() - t1, 2))
        r.check("A 收斂後每條線都前進 ≥4 回合", converged,
                {n: (base_r[n], sp.round_of(n)) for n in NODES})
        time.sleep(0.3)
        mon.stop.set()
        mon.join(2)
        r.check("A status.at 一直在動（最長停 < 2 秒）", mon.max_gap < 2.0, round(mon.max_gap, 3))
        r.measure("A status 最長沒更新秒數", round(mon.max_gap, 3))
        r.check("A 每個 node 的 round 在 status 裡不倒退", not mon.backwards, mon.backwards[:5])

        # daemon ctl：每個（唯一名字的）控制檔恰好處理一次
        cdir = os.path.join(sp.root, ".aosd")
        left_ctl = [n for n in os.listdir(os.path.join(cdir, "ctl")) if n.endswith(".json")]
        r.check("A ctl/ 全部處理完", not left_ctl, left_ctl[:5])
        log = sp.log()
        per = {}
        for x in log:
            if x.get("ev") == "ctl":
                per[x.get("file")] = per.get(x.get("file"), 0) + 1
        bad_once = [n for n in ch.ctl_written if per.get(n) != 1]
        r.check("A 每個 daemon 控制檔恰好處理一次（log 一行）", not bad_once, bad_once[:5])
        subs = [fs.read_json(os.path.join(cdir, "ctl-done", n)) for n in ch.ctl_written]
        sub_ok = [d for d in subs if isinstance(d, dict) and str(d.get("node", "")).startswith("sub")
                  and d.get("op") in ("pause", "resume", "wake") and (d.get("result") or {}).get("ok")]
        r.check("A 對子 daemon 底下 node 的 pause/resume/wake 都回 ok:false", not sub_ok, sub_ok[:2])
        r.check("A 子 daemon 根底下的 node 父 daemon 沒跑", "sub/x" not in (sp.status().get("nodes") or {})
                and not os.path.exists(sp.path("sub/x", ".aos", "round.json")))

        # 任務 ctl.json：收斂後沒有殘留
        left_tctl, strays = [], []
        for nid in NODES:
            td = sp.path(nid, ".aos", "tasks")
            for t in os.listdir(td) if os.path.isdir(td) else []:
                has_birth = os.path.isfile(os.path.join(td, t, "birth.json"))
                if not has_birth:
                    strays.append("%s/%s" % (nid, t))
                elif os.path.exists(os.path.join(td, t, "ctl.json")):
                    left_tctl.append("%s/%s" % (nid, t))
        r.check("A 任務 ctl.json 收斂後都執行了", not left_tctl, left_tctl[:5])
        r.measure("A tasks/ 裡沒有 birth.json 的資料夾（亂源寫 ctl 撞上搬家，留下的空殼）", len(strays))

        # 停：stop --kill
        sp.ctl("stop", kill=True)
        t_stop = time.monotonic()
        try:
            rc = proc.wait(15)
        except subprocess.TimeoutExpired:
            rc = None
        r.check("A stop --kill 後 daemon 15 秒內正常退出", rc == 0, rc)
        r.measure("A stop --kill 所需秒數", round(time.monotonic() - t_stop, 2))
        if rc != 0:
            st = sp.status()
            r.measure("A 停不下來時的 status", {n: (v.get("phase"), v.get("round"), v.get("live")) for n, v in (st.get("nodes") or {}).items()})
            r.measure("A 停不下來時 log 末段", [x for x in sp.log()[-12:]])
        time.sleep(0.2)
        left = leftovers(sp.base)
        bad_left = {k: v for k, v in left.items() if k not in ALLOWED_LEFTOVER}
        r.measure("A stop 後殘留程序（依行為分）", {k: len(v) for k, v in left.items()})
        r.check("A stop 後沒有不該留的殘留（只准已結束任務的孫程序、刪了 taskdir 的）", not bad_left,
                {k: len(v) for k, v in bad_left.items()})

        # rounds.jsonl 與 round.json
        stats = {nid: analyze_rounds(sp, nid) for nid in NODES}
        r.measure("A 每個 node 的回合總結", stats)
        r.check("A rounds.jsonl 沒有重號", all(s["dup"] == 0 for s in stats.values()))
        r.check("A rounds.jsonl 回合號嚴格遞增", all(s["nonincr"] == 0 for s in stats.values()))
        r.measure("A rounds.jsonl 缺號（有 tick 沒 tock 的回合）總數", sum(s["gaps"] for s in stats.values()))
        r.measure("A ended 重報總數", sum(s["ended_dup"] for s in stats.values()))
        mism = {}
        for nid in NODES:
            rj = fs.read_json(sp.path(nid, ".aos", "round.json"), {}) or {}
            last = (sp.rounds(nid) or [{}])[-1].get("round")
            if not (rj.get("open") is False and rj.get("round") == last):
                mism[nid] = (rj.get("round"), rj.get("open"), last)
        r.check("A 停機後 round.json 已關，且等於 rounds.jsonl 最後一行", not mism, mism)
        overlap = {}
        for nid in NODES + ["eph"]:
            a = birth_dirs(sp.path(nid, ".aos", "tasks"))
            b = birth_dirs(sp.path(nid, ".aos", "tasks-old"))
            if a & b:
                overlap[nid] = sorted(a & b)[:3]
        r.check("A tasks/ 與 tasks-old/ 的 tid 不重複", not overlap, overlap)
        r.measure("A 搬到 tasks-old 的任務數", sum(s["archived"] for s in stats.values()))

        # node 消失後不被建回來（daemon 已停：這裡用重啟一次 daemon，再 rm -rf eph）
        proc2 = sp.start()
        sp.wait_for(lambda: (sp.status().get("nodes") or {}).get("eph", {}).get("round", 0) >= 1, 10,
                    msg="重啟後 eph 沒開回合")
        shutil.rmtree(fs.node_path(sp.root, "eph"))
        time.sleep(1.0)
        r.check("A rm -rf 的 node 1 秒後沒被建回來", not os.path.exists(fs.node_path(sp.root, "eph")))
        sp.ctl("stop", kill=True)
        try:
            proc2.wait(15)
        except subprocess.TimeoutExpired:
            pass
        r.measure("A daemon log 行數", len(log))


# ---------------- B 段：最小重現 ----------------

def part_b(r):
    found = {}

    # B1：新出現的 node 的 round.json 不是物件 → daemon 整個掛掉
    with pl.Space("chaos-b1") as sp:
        sp.node("ok", [{"name": "w", "mode": "keep", "argv": ["sleep", "30"]}], interval_ms=50)
        p = sp.start()
        sp.wait_for(lambda: sp.round_of("ok") >= 2, 10)
        pl.write(sp.path("bad", ".aos", "round.json"), [])
        sp.node("bad", [], interval_ms=50)
        time.sleep(0.8)
        died = p.poll()
        out = open(os.path.join(sp.base, "daemon-0.out")).read()
        found["B1 round.json 是 [] 的 node 出現 → daemon 退出"] = {
            "重現": died is not None, "rc": died,
            "證據": out.strip().splitlines()[-1][-160:] if out.strip() else None,
            "孤兒任務": len(pl.our_procs(sp.base))}

    with pl.Space("chaos-b") as sp:
        good = {"name": "good", "mode": "keep", "argv": ["sleep", "30"]}
        # B2：tasks.json 一項 name 不是字串 → 整個 tick 例外，同 node 的好項目永遠起不來
        sp.node("b2", [{"name": 5, "argv": ["true"]}, good], interval_ms=50)
        # B3：spawn 檔 name 不是字串 → tick 每回合例外，spawn 檔不刪（毒丸），整條線不再起任何任務
        sp.node("b3", [good], interval_ms=50, files={".aos/spawn/x.json": {"name": ["a"], "argv": ["true"]}})
        # B4：argv 裡有非字串 → aos7-run 當場例外（stderr 丟到 /dev/null），沒有 pid.json 也沒有 exit.json，永遠算「born」＝活
        sp.node("b4", [{"name": "k", "mode": "keep", "argv": ["sleep", 5]}], interval_ms=50)
        # B6：round.json 的 round 被改成字串 → 下個 tick 從 1 重數，rounds.jsonl 出現重號
        sp.node("b6", [], interval_ms=50)
        # B8：timeline.json 在回合中途拿掉又放回 → 那回合沒有 tock（rounds.jsonl 缺號）
        sp.node("b8", [{"name": "s", "argv": ["sleep", "0.25"]}], interval_ms=400)
        # B9：interval_ms 寫 -5 或 0 → 默默當 1 ms（不記 last_error），整條線全速空轉
        sp.node("b9", [], interval_ms=-5)
        p = sp.start()
        sp.wait_for(lambda: all(sp.round_of(n) >= 3 for n in ("b2", "b3", "b4", "b6")), 10)
        b6_before = sp.round_of("b6")
        rj = fs.read_json(sp.path("b6", ".aos", "round.json"))
        rj["round"] = "x"
        pl.write(sp.path("b6", ".aos", "round.json"), rj)
        # B8：等 b8 進入回合中（running），拿掉 timeline.json，等 node- 再放回
        sp.wait_for(lambda: (sp.status().get("nodes") or {}).get("b8", {}).get("phase") == "running", 10, poll=0.005)
        r8 = sp.round_of("b8")
        tl = sp.path("b8", ".aos", "timeline.json")
        txt = open(tl).read()
        os.remove(tl)
        sp.wait_for(lambda: any(x.get("ev") == "node-" and x.get("node") == "b8" for x in sp.log()), 5, poll=0.005)
        raw_write(tl, txt)
        # B5：daemon ctl/ 裡有一個叫 d.json 的資料夾 → 每圈都「處理」一次（rm 不掉），log 一秒灌 ~50 行
        os.makedirs(os.path.join(sp.root, ".aosd", "ctl", "d.json"))
        time.sleep(1.5)
        n_d = sum(1 for x in sp.log() if x.get("file") == "d.json")
        shutil.rmtree(os.path.join(sp.root, ".aosd", "ctl", "d.json"), ignore_errors=True)   # 修補後 daemon 已把它搬到 ctl-done/
        sp.wait_for(lambda: sp.round_of("b8") >= r8 + 2, 10)
        st = sp.status().get("nodes") or {}

        def err(n):
            return ((st.get(n) or {}).get("last_error") or {}).get("err", "")[-120:]
        found["B2 tasks.json 一項 name=5 → 同 node 的好項目起不來"] = {
            "重現": not any(t.startswith("good-") for t in sp.tasks("b2")), "last_error": err("b2")}
        found["B3 spawn 檔 name=[..] → 毒丸：檔不刪、每回合 tick 失敗"] = {
            "重現": os.path.exists(sp.path("b3", ".aos", "spawn", "x.json"))
            and not any(t.startswith("good-") for t in sp.tasks("b3")), "last_error": err("b3")}
        b4 = sp.path("b4", ".aos", "tasks", "k-r1")
        b4files = sorted(os.listdir(b4)) if os.path.isdir(b4) else []
        found["B4 argv 有非字串 → 任務永遠 born（算活），keep 不再起、tock 不提前"] = {
            "重現": b4files == ["birth.json", "out.log", "tock.json"] and "k-r1" in sp.live("b4"),
            "檔": b4files, "status live": (st.get("b4") or {}).get("live"),
            "tasks_error": (fs.read_json(sp.path("b4", ".aos", "round.json"), {}) or {}).get("tasks_error")}
        found["B5 ctl/ 裡有 d.json 資料夾 → 每圈重處理"] = {"重現": n_d > 10, "1.5 秒內 log 行數": n_d}
        rs6 = [x.get("round") for x in sp.rounds("b6")]
        found["B6 round.json 的 round 被改成字串 → 從 1 重數、rounds.jsonl 重號"] = {
            "重現": len(rs6) != len(set(rs6)), "改之前": b6_before, "之後": sp.round_of("b6")}
        b9 = st.get("b9") or {}
        found["B9 interval_ms=-5 → 默默當 1 ms 全速跑"] = {
            "重現": b9.get("interval_ms") != 1000 or not b9.get("last_error"), "interval_ms": b9.get("interval_ms"),
            "回合數": b9.get("round")}
        rs8 = [x.get("round") for x in sp.rounds("b8")]
        found["B8 回合中 node 消失又出現 → 那回合沒有 tock"] = {
            "重現": r8 not in rs8, "消失時的回合": r8, "rounds.jsonl": rs8[-5:]}

    # B7：任務改寫自己的 pid.json 指向別人的程序群組 → kill 打到別人
    with pl.Space("chaos-b7") as sp:
        victim = subprocess.Popen(["sleep", "60"], start_new_session=True)
        try:
            sp.node("b7", [{"name": "f", "mode": "each", "argv": [PY, "-c",
                    "import json,os,time;p=os.path.join(os.environ['AOS7_TASK'],'pid.json');time.sleep(0.2);"
                    "d=json.load(open(p));d['pgid']=%d;json.dump(d,open(p,'w'));time.sleep(30)" % victim.pid],
                    "from_round": 1, "max_live": 1}], interval_ms=100)
            sp.start()
            sp.wait_for(lambda: (sp.task_file("b7", "f-r1", "pid.json") or {}).get("pgid") == victim.pid, 10)
            pl.write(os.path.join(sp.path("b7", ".aos", "tasks", "f-r1"), "ctl.json"), {"op": "kill", "by": "probe"})
            sp.wait_for(lambda: sp.task_file("b7", "f-r1", "ctl-done.json"), 10)
            time.sleep(0.2)
            found["B7 任務改自己的 pid.json 的 pgid → kill 打到別人的程序群組"] = {
                "重現": victim.poll() is not None, "被害者退出碼": victim.poll(),
                "回條": (sp.task_file("b7", "f-r1", "ctl-done.json") or {}).get("result", {}).get("msg")}
        finally:
            if victim.poll() is None:
                victim.kill()
            victim.wait()

    # B10：daemon ctl/ 裡有一個叫 f.json 的 FIFO → 主迴圈卡在 open()，status 停更、之後的控制檔都不處理（連 stop 也收不到）
    with pl.Space("chaos-b10") as sp:
        sp.node("a", [], interval_ms=50)
        sp.start()
        sp.wait_for(lambda: sp.round_of("a") >= 2, 10)
        fifo = os.path.join(sp.root, ".aosd", "ctl", "f.json")
        os.mkfifo(fifo)
        time.sleep(0.3)
        at0 = sp.status().get("at")
        name = sp.ctl("pause", "a")
        time.sleep(1.0)
        frozen = sp.status().get("at") == at0
        stuck = os.path.exists(os.path.join(sp.root, ".aosd", "ctl", name))
        found["B10 ctl/ 裡有 FIFO → daemon 主迴圈卡住"] = {
            "重現": frozen and stuck, "status 1 秒沒動": frozen, "後面的 pause 沒處理": stuck,
            "時間線照跑（回合）": sp.round_of("a")}
        try:   # 解開：寫一份給它讀（daemon 是讀的那端，非阻塞開寫端會成功）
            fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            os.write(fd, b"{}")
            os.close(fd)
        except OSError:
            pass

    for k, v in found.items():
        r.measure(k, v)
        # 第二波修補（spec.md、tests/test_wave2.py）之後，這些都不該再重現
        r.check("修補後不再重現：%s" % k.split()[0], not v.get("重現"), None if not v.get("重現") else v)
    hit = [k.split()[0] for k, v in found.items() if v.get("重現")]
    r.measure("B 重現了的", hit)
    return found


def main():
    argv = sys.argv[1:]
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 7
    dur = 60.0 if "--long" in argv else 12.0
    r = pl.Result("chaos")
    r.measure("seed", seed)
    if "--no-a" not in argv:
        part_a(r, seed, dur, "--poison" in argv)
    if "--no-b" not in argv:
        part_b(r)
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
