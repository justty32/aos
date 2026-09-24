"""kernel 崩潰窗口（審查 C-7、C-8；proto5-2 加 C-9）：閘門卡住真 tick、真 SIGKILL、下一格（或 boot）接手。

proto5-2 搬遷：
- cpu 家改在 K/pools/<P>/cpus/<i>，trace 裡的 home 記成 `P/i`（kernel cpu 是 `kernel/0`，daemon 家記 `D`）。
- 派工「先記後放」：同一格派的幾件在提交點 3 就全部記好，才逐一放檔（kernel-tick 第 8 步）。
  proto5 的「第一顆放了、第二顆還沒記」這個窗口不存在了，那條改成驗「兩件都已記、沒放的下一格照原名補放」。
- 出貨箱 `stops` 拿掉：停機改成每池縮 0（handoff §3）。proto5 的 C-8 stop 箱三條改測 `sends` 箱的縮池單：
  送出後、清帳前被 KILL（daemon 在 kernel 死掉時已處理、回音）與記帳後、送出前被 KILL；kernel 池那張同理，下次 boot 收尾。
- C-9（新）：kernel 改宣告（長大）一半死、真 daemon 在中間處理完——下一格不重放同名單、照回音結帳（D-25、kernel-pools §5）。

手法照 test_daemon_crash：
- 真 daemon 由 HUB（測試專用 subreaper，借 test_daemon_crash 的）拉起；kernel cpu 被砍後
  另一組的 tick 孤兒歸它收屍。
- kernel 的 `cli` 換成測試專用啟動器 TICK（boot 時把 aos_kernel_boot.CLI 指過去），它跑的是真的
  `aos_kernel.main()`，只在測試 driver 裡替換幾個函式當閘門，**產品程式沒有測試掛鉤**。
  閘門是 gates/ 下的檔：`<id>.json` 點名「哪一步、什麼條件」，一次性；命中寫 `<id>.reached`
  （pid、seq、細節）後停住，等測試 SIGKILL 或放 `<id>.release`。
- TICK 另把 kernel 每次放檔／回音／刪單記進 trace.jsonl（成功或 EEXIST），用來查「同名只到一次」。
- 工作是真的 aos-cpu 跑一份 inst，每跑一次往 runs-<名>.txt 加一行，查「副作用恰好一次」。
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import aos_client
import aos_home
import test_daemon_crash
from _kernel_util import KernelCase, CLI, PY, read_json, wait_for

LIB = CLI.parent / "lib"
HUB = test_daemon_crash.HUB

TICK = r'''
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
GATES = HERE / "gates"
sys.path.insert(0, %(lib)r)
import aos_home, aos_kernel, aos_kernel_engine as engine, aos_kernel_ledger as ledger
argv = sys.argv[1:]
SEQ = int(argv[argv.index("--seq") + 1]) if "--seq" in argv else None
CHAIN = argv[argv.index("--chain") + 1] if "--chain" in argv else None
ctx = {"kernel": None, "flush": False}

def trace(**entry):
    with (HERE / "trace.jsonl").open("a") as f:
        f.write(json.dumps(dict(entry, seq=SEQ, chain=CHAIN, pid=os.getpid())) + "\n")

def matches(spec, detail):
    if spec.get("seq_min") is not None and (SEQ is None or SEQ < spec["seq_min"]):
        return False
    if spec.get("chain") is not None and spec["chain"] != CHAIN:
        return False
    for key, value in spec.get("match", {}).items():
        if key.endswith("_endswith"):
            if not str(detail.get(key[:-len("_endswith")])).endswith(value):
                return False
        elif key == "response_proc":
            if value not in [e.get("proc") for e in detail.get("events", []) if e.get("event") == "response"]:
                return False
        elif isinstance(value, list):
            if detail.get(key) not in value:
                return False
        elif detail.get(key) != value:
            return False
    return True

def gate(point, **detail):
    if not GATES.is_dir():
        return
    for path in sorted(GATES.glob("*.json")):
        spec = json.loads(path.read_text())
        if spec["point"] != point or not matches(spec, detail):
            continue
        gid = path.name[:-5]
        reached = GATES / (gid + ".reached")
        tmp = GATES / (gid + ".tmp-%%d" %% os.getpid())
        tmp.write_text(json.dumps(dict(detail, point=point, pid=os.getpid(), seq=SEQ, chain=CHAIN)))
        try:
            os.link(tmp, reached)       # 一次性：先到先得
        except FileExistsError:
            continue
        finally:
            tmp.unlink()
        while not (GATES / (gid + ".release")).exists():
            time.sleep(.005)

def label(home):
    home = Path(home)
    if home.parent.name == "cpus":
        return "%%s/%%s" %% (home.parent.parent.name, home.name)
    return home.name

def kind_of(home, name):
    home = Path(home)
    if name.startswith("ack-"):
        return "ack" if ctx["flush"] else "tick_ack"
    if name.startswith("stop-"):
        return "stop"
    if home.parent.name == "cpus" and SEQ is not None and name == "k-%%s-%%s.json" %% (CHAIN, SEQ + 1):
        return "tick"
    if home.parent.name == "cpus":
        return "work"
    return "daemon"

real_post = aos_home.post_request
def post_request(home, name, obj):
    kind = kind_of(home, name)
    detail = {"box": kind, "home": label(home), "name": name,
              "target": (obj.get("params") or {}).get("name") if kind in ("ack", "tick_ack") else None}
    if kind in ("ack", "stop", "daemon"):
        gate("before_put", **detail)
    try:
        real_post(home, name, obj)
    except aos_home.RequestExists:
        trace(op="post", outcome="exists", **detail)
        raise
    trace(op="post", outcome="ok", **detail)
    if kind in ("ack", "stop", "daemon"):
        gate("after_put", **detail)
    return name
aos_home.post_request = post_request

real_link = aos_home.link_json
def link_json(path, obj):
    detail = {"box": "reply", "home": "K", "name": Path(path).name}
    gate("before_put", **detail)
    try:
        real_link(path, obj)
    except aos_home.RequestExists:
        trace(op="reply", outcome="exists", **detail)
        raise
    trace(op="reply", outcome="ok", **detail)
    gate("after_put", **detail)
aos_home.link_json = link_json

real_unlink = Path.unlink
def unlink(self, missing_ok=False):
    watched = ctx["flush"] and ctx["kernel"] is not None and self.parent.name == "requests" and self.parent.parent == ctx["kernel"].home
    detail = {"box": "delete", "home": "K", "name": self.name}
    if watched:
        gate("before_put", **detail)
    existed = self.exists()
    real_unlink(self, missing_ok=missing_ok)
    if watched:
        trace(op="delete", outcome="ok" if existed else "missing", **detail)
        gate("after_put", **detail)
Path.unlink = unlink

real_flush = ledger.KernelLedger.flush_outboxes
def flush_outboxes(self):
    ctx["flush"] = True
    try:
        return real_flush(self)          # 回「有沒有做事」：engine 靠它決定寫不寫提交點 2／4
    finally:
        ctx["flush"] = False
ledger.KernelLedger.flush_outboxes = flush_outboxes

real_post_work = engine.Kernel._post_work
def post_work(self, c, name, proc):
    detail = {"cpu": c, "name": name, "proc": next(n for n, p in self.state["procs"].items() if p is proc)}
    gate("before_post", **detail)
    real_post_work(self, c, name, proc)
    gate("after_post", **detail)
engine.Kernel._post_work = post_work

real_step = engine.Kernel.step
def step(self):
    ctx["kernel"] = self
    return real_step(self)
engine.Kernel.step = step

real_open = Path.open
def path_open(self, mode="r", *args, **kwargs):
    if self.name == "kernel.log" and "a" in mode and ctx["kernel"] is not None:
        events = [{"event": e.get("event"), "proc": e.get("proc")} for e in ctx["kernel"].events]
        gate("before_log", events=events)
    return real_open(self, mode, *args, **kwargs)
Path.open = path_open

if argv[:1] == ["tick"]:
    gate("start")
sys.exit(aos_kernel.main())
'''

# boot 照產品程式走，只把釘進帳本的 cli 換成 TICK。
BOOT = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos_kernel_boot
aos_kernel_boot.CLI = Path(sys.argv[3])
sys.exit(aos_kernel_boot.boot(sys.argv[2], wait_ms=8000))
'''

JOB = "import sys; open(sys.argv[1], 'a').write('x\\n'); sys.exit(int(sys.argv[2]))"


class KernelCrashWindowTest(KernelCase):
    def setUp(self):
        super().setUp()
        self.hub = self.root / "hub"
        self.hub.mkdir()
        self.hub_seq = 0
        log = open(self.root / "hub.log", "ab")
        self.addCleanup(log.close)
        self.hub_proc = subprocess.Popen([PY, "-c", HUB, str(self.hub)], stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=log, start_new_session=True)
        self.addCleanup(self.stop_hub)
        self.tickdir = self.root / "tick"
        self.gates = self.tickdir / "gates"
        self.gates.mkdir(parents=True)
        self.wrapper = self.tickdir / "aos-kernel-gated"
        self.wrapper.write_text("#!%s\n%s" % (PY, TICK % {"lib": str(LIB)}))
        self.wrapper.chmod(0o755)
        self.daemon_pid = None
        self.addCleanup(self.shutdown)          # 比 stop_hub 先跑（addCleanup 後進先出）

    # ---- hub、daemon、boot ----

    def stop_hub(self):
        aos_home.write_json(self.hub / "quit.json", {})
        try:
            self.hub_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.hub_proc.kill()
            self.hub_proc.wait(timeout=4)
            raise

    def reaped(self):
        path = self.hub / "reaped.jsonl"
        if not path.exists():
            return {}
        return {e["pid"]: e for e in map(json.loads, path.read_text().splitlines())}

    def start_daemon(self):
        seq, self.hub_seq = self.hub_seq, self.hub_seq + 1
        aos_home.write_json(self.hub / ("cmd-%d.json" % seq),
                            {"argv": [str(CLI / "aos-daemon"), "boot", "--target", str(self.daemon)]})
        self.daemon_pid = wait_for(lambda: read_json(self.hub / ("started-%d.json" % seq), {}).get("pid"))
        wait_for(lambda: self.dstate().get("pid") == self.daemon_pid)

    def boot(self):
        chain = self.state().get("chain")
        result = subprocess.run([PY, "-c", BOOT, str(LIB), str(self.home), str(self.wrapper)],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.info = read_json(self.home / "info.json")
        wait_for(lambda: self.state().get("chain") != chain and self.state().get("last_seq", 0) >= 1)

    def setup_running(self, pools=None, **settings):
        pools = pools or {"default": {"count": 2}}
        self.initialize(pools, **settings)
        self.start_daemon()
        self.boot()
        self.assertEqual(self.state()["cli"], str(self.wrapper))
        for pool, config in pools.items():                       # 工作池宣告確認過（第一張 scale 單收完音）
            wait_for(lambda: (self.state()["pools"].get(pool) or {}).get("sent", {}).get("count") == config["count"])
            self.wait_running(pool, config["count"])

    def held_pids(self):
        """所有還活著的 TICK（照 cmdline 找），收尾時一律 KILL，免得 cpu 溫和停永遠等它。"""
        found = []
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                try:
                    cmd = Path("/proc/%s/cmdline" % entry).read_bytes()
                except OSError:
                    continue
                if str(self.wrapper).encode() in cmd:
                    found.append(int(entry))
        return found

    def shutdown(self):
        for pid in self.held_pids():
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.daemon_pid is None or not self.alive(self.daemon_pid):
            return
        aos_home.post_request(self.daemon, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        try:
            wait_for(lambda: not self.alive(self.daemon_pid), timeout=8)
        except AssertionError:
            for pid in self.held_pids():
                os.kill(pid, signal.SIGKILL)
            wait_for(lambda: not self.alive(self.daemon_pid), timeout=8)

    @staticmethod
    def alive(pid):
        try:
            stat = Path("/proc/%d/stat" % pid).read_text()
        except OSError:
            return False
        return stat.rsplit(")", 1)[1].split()[0] != "Z"

    # ---- 閘門 ----

    def gate(self, gid, point, seq_min=None, chain=None, **match):
        aos_home.write_json(self.gates / (gid + ".json"),
                            {"point": point, "seq_min": seq_min, "chain": chain, "match": match})

    def reached(self, gid, timeout=8):
        return wait_for(lambda: read_json(self.gates / (gid + ".reached")), timeout=timeout)

    def release(self, gid):
        aos_home.write_json(self.gates / (gid + ".release"), {})

    def kill_tick(self, gid, hold=None):
        """KILL 卡在 gid 的那格；hold 給了就先把下一格卡在開頭（下一格要等這格死才會開始，沒有競態）。"""
        hit = self.reached(gid)
        if hold:
            self.gate(hold, "start", seq_min=hit["seq"] + 1, chain=hit["chain"])
        os.kill(hit["pid"], signal.SIGKILL)
        wait_for(lambda: not self.alive(hit["pid"]))
        return hit, (self.reached(hold) if hold else None)

    # ---- 證據 ----

    def trace(self, **match):
        path = self.tickdir / "trace.jsonl"
        entries = self.jsonl(path)
        return [e for e in entries if all(e.get(k) == v for k, v in match.items())]

    @staticmethod
    def jsonl(path):
        """鏈還在 append：只收以換行結尾的完整行。"""
        if not path.exists():
            return []
        text = path.read_text()
        return [json.loads(line) for line in text[:text.rfind("\n") + 1].splitlines()]

    def log_lines(self):
        return self.jsonl(self.home / "kernel.log")

    def job(self, name, code=0):
        runs = self.root / ("runs-%s.txt" % name)
        target = self.write(self.root / (name + ".json"), {"argv": [PY, "-c", JOB, str(runs), str(code)]})
        return target, runs

    def runs(self, name):
        path = self.root / ("runs-%s.txt" % name)
        return len(path.read_text().splitlines()) if path.exists() else 0

    def settle(self, ticks=4):
        """多等幾格，讓「重派／重放」若會發生就發生。"""
        target = self.state()["last_seq"] + ticks
        wait_for(lambda: self.state().get("last_seq", 0) >= target, timeout=10)

    def assert_no_same_name_twice(self):
        """kernel 放出去的每個（家, 檔名）、每則 K 的回音，至多成功一次；stop 另外看。"""
        seen = {}
        for e in self.trace(outcome="ok"):
            if e["op"] in ("post", "reply") and e["box"] != "stop":
                key = (e["home"], e["name"])
                self.assertNotIn(key, seen, "同名放了兩次：%s" % (key,))
                seen[key] = e

    def cpu_pids(self):
        pids = {"kernel/0": self.kid_pid("kernel", 0)}
        for pool, entry in self.state()["pools"].items():
            if pool != "kernel":
                for i in range(entry["sent"]["count"]):
                    pids["%s/%d" % (pool, i)] = self.kid_pid(pool, i)
        return pids

    def home_of(self, label):
        pool, i = label.split("/")
        return self.cpu_home(pool, i)

    # ---- C-7：已結帳、已送 ack，append kernel.log 之前被 KILL ----

    def test_c7_repeat_result_booked_and_acked_then_killed_before_log(self):
        self.c7_repeat(code=0, fails=0)

    def test_c7_repeat_failure_booked_then_killed_before_log_counts_once(self):
        self.c7_repeat(code=3, fails=1)

    def c7_repeat(self, code, fails):
        self.setup_running()
        target, _ = self.job("job", code)
        self.gate("log", "before_log", response_proc="job")
        self.add(target, "job", interval_ms=600000)
        pids = self.cpu_pids()
        hit, held = self.kill_tick("log", hold="next")
        n, chain = hit["seq"], hit["chain"]
        self.assertEqual(held["seq"], n + 1)
        ledger = self.state()
        job = ledger["procs"]["job"]
        self.assertEqual((job["runs"], job["fails"], job["status"]), (1, fails, "queued"))
        self.assertEqual(ledger["busy"], {})
        self.assertEqual({box: ledger[box] for box in ("acks", "replies", "sends", "deletes")},
                         {"acks": [], "replies": [], "sends": [], "deletes": []})
        ack = [e for e in self.trace(box="ack", outcome="ok", seq=n) if e["home"] in ("default/0", "default/1")]
        self.assertEqual(len(ack), 1, ack)
        cpu = self.home_of(ack[0]["home"])
        # 下一格開始前，cpu 就把 ack 消化掉（回音沒了、ack 單也沒了）
        wait_for(lambda: not (cpu / "responses" / ack[0]["target"]).exists()
                 and not list((cpu / "requests").glob("ack-*.json")))
        self.assertNotIn(n, [line["seq"] for line in self.log_lines() if line["chain"] == chain])
        self.release("next")
        self.settle()
        job = self.state()["procs"]["job"]
        self.assertEqual((job["runs"], job["fails"], job["status"]), (1, fails, "queued"))
        self.assertEqual(self.runs("job"), 1)
        lines = [line for line in self.log_lines() if line["chain"] == chain]
        self.assertNotIn(n, [line["seq"] for line in lines])                 # 缺那一格
        self.assertFalse([e for line in lines for e in line["events"]
                          if e["event"] == "response" and e["proc"] == "job"])
        # 被砍的那格由後面某格記成 tick_error（kernel cpu 的回音 code≠0）
        self.assertTrue([e for line in lines for e in line["events"] if e["event"] == "tick_error"
                         and e["request"] == "k-%s-%d.json" % (chain, n)])
        self.assertEqual(self.cpu_pids(), pids)                               # 沒有 cpu 被重拉
        self.assert_no_same_name_twice()

    def test_c7_once_reply_delivered_then_killed_before_log(self):
        self.setup_running()
        target, _ = self.job("once")
        self.gate("log", "before_log", response_proc="once")
        name = aos_client.submit(self.home, "add", {"name": "once", "target": target, "once": True})
        hit, held = self.kill_tick("log", hold="next")
        reply = read_json(self.home / "responses" / name)                     # 第 10 步已出貨
        self.assertEqual((reply["id"], reply["result"]["code"]), (name[:-5], 0), reply)
        self.assertNotIn("once", self.state()["procs"])
        aos_client.ack(self.home, name)                                       # 交件者在下一格前收走
        self.release("next")
        wait_for(lambda: not (self.home / "responses" / name).exists())
        self.settle()
        self.assertFalse((self.home / "responses" / name).exists())            # 沒有重新冒出來
        self.assertEqual(len(self.trace(op="reply", outcome="ok", name=name)), 1)
        self.assertEqual(self.runs("once"), 1)
        self.assertNotIn("once", self.state()["procs"])
        self.assertNotIn(hit["seq"], [l["seq"] for l in self.log_lines() if l["chain"] == hit["chain"]])
        self.assert_no_same_name_twice()

    def test_c7_boot_takes_over_after_kill_before_log(self):
        self.setup_running()
        target, _ = self.job("job")
        self.gate("log", "before_log", response_proc="job")
        self.add(target, "job", interval_ms=600000)
        hit, held = self.kill_tick("log", hold="next")
        old_chain = hit["chain"]
        # 下一格卡在開頭時重新 boot：舊 kernel cpu 被收，卡住的那格是另一組、成了孤兒（歸 HUB）
        self.boot()
        new_chain = self.state()["chain"]
        self.assertNotEqual(new_chain, old_chain)
        # 卡住的下一格通常被舊 cpu 的強制停（第二次 TERM 轉給工作那組）砍掉；若還活著（成了孤兒、歸 HUB），
        # 放它走，舊鏈殘格在第 1 步自滅
        if self.alive(held["pid"]):
            self.release("next")
        wait_for(lambda: not self.alive(held["pid"]))
        self.settle()
        ledger = self.state()
        job = ledger["procs"]["job"]
        self.assertEqual((job["runs"], job["fails"], job["status"]), (1, 0, "queued"))
        self.assertEqual(self.runs("job"), 1)
        self.assertEqual(ledger["busy"], {})
        self.assertFalse([e for line in self.log_lines() for e in line["events"]
                          if e["event"] == "response" and e["proc"] == "job"])
        # 舊鏈殘格（若跑到）什麼都沒放：它之後沒有任何屬於舊鏈、seq > n+1 的放檔
        self.assertFalse([e for e in self.trace(chain=old_chain) if e["seq"] > hit["seq"]])
        self.assert_no_same_name_twice()

    # ---- C-8：派工逐顆放檔，中途被 KILL ----

    def two_jobs_in_one_tick(self):
        """先把鏈卡住，一次放兩則 add，放行後同一格收單、兩顆各派一件。"""
        self.setup_running()
        self.gate("hold", "start")
        self.reached("hold")
        targets = [self.job(n)[0] for n in ("a", "b")]
        names = [aos_client.submit(self.home, "add", {"name": n, "target": t, "interval_ms": 600000})
                 for n, t in zip(("a", "b"), targets)]
        return names

    def finish_two_jobs(self):
        wait_for(lambda: all(self.state()["procs"][n]["runs"] == 1 for n in ("a", "b")), timeout=10)
        self.settle()
        procs = self.state()["procs"]
        self.assertEqual([(procs[n]["runs"], procs[n]["fails"]) for n in ("a", "b")], [(1, 0), (1, 0)])
        self.assertEqual((self.runs("a"), self.runs("b")), (1, 1))
        self.assert_no_same_name_twice()

    def test_c8_dispatch_first_cpu_posted_second_recorded_not_posted(self):
        self.two_jobs_in_one_tick()
        self.gate("post", "before_post", cpu="default/1")
        self.release("hold")
        hit, held = self.kill_tick("post", hold="next")
        ledger = self.state()
        req0, req1 = ledger["busy"]["default/0"]["req"], ledger["busy"]["default/1"]["req"]
        self.assertEqual((ledger["busy"]["default/1"]["proc"], req1), (hit["proc"], hit["name"]))
        self.assertEqual(ledger["ready"]["default"], [])
        self.assertEqual(ledger["recent"], ["default/0", "default/1"])
        self.assertFalse((self.cpu_home("default", 1) / "requests" / req1).exists())
        self.assertEqual(len(self.trace(op="post", home="default/0", name=req0, outcome="ok")), 1)
        self.release("next")
        self.finish_two_jobs()
        # 已送的 default/0 沒被重放；沒送的 default/1 由下一格（recent）照帳本原名補放一次
        self.assertEqual(len(self.trace(op="post", home="default/0", name=req0)), 1)
        self.assertEqual([e["seq"] for e in self.trace(op="post", home="default/1", name=req1)], [hit["seq"] + 1])

    def test_c8_dispatch_both_recorded_before_first_post(self):
        """proto5 的「第一顆放了、第二顆還沒記」：proto5-2 先記後放，放第一顆時兩件都已在帳上。"""
        self.two_jobs_in_one_tick()
        self.gate("post", "after_post", cpu="default/0")
        self.release("hold")
        hit, held = self.kill_tick("post", hold="next")
        ledger = self.state()
        self.assertEqual(ledger["busy"]["default/0"]["req"], hit["name"])
        req1 = ledger["busy"]["default/1"]["req"]
        other = "b" if hit["proc"] == "a" else "a"
        self.assertEqual(ledger["busy"]["default/1"]["proc"], other)
        self.assertEqual(ledger["procs"][other]["status"], "running")
        self.assertEqual(ledger["ready"]["default"], [])
        self.release("next")
        self.finish_two_jobs()
        self.assertEqual(len(self.trace(op="post", home="default/0", name=hit["name"])), 1)
        # 另一件沿用被砍那格記下的名字，下一格才真的放出去；沒有第二個名字
        later = [e for e in self.trace(op="post", box="work", outcome="ok") if e["name"] != hit["name"]]
        self.assertEqual([(e["name"], e["seq"]) for e in later], [(req1, hit["seq"] + 1)])

    # ---- C-8：四張出貨箱逐箱，「送出後、清帳前」與「記帳後、送出前」 ----

    def booked_job(self, gid, point):
        """一件反覆工作跑完被收帳時，卡在給工作 cpu 的那則 ack 的 point；回它的 request 名。"""
        self.setup_running()
        target, _ = self.job("job")
        self.gate(gid, point, box="ack", home=["default/0", "default/1"])
        self.add(target, "job", interval_ms=600000)
        return self.reached(gid)["target"]

    def test_c8_ack_delivered_before_clear_receiver_consumes_then_replay(self):
        req = self.booked_job("ack", "after_put")
        hit, held = self.kill_tick("ack", hold="next")
        cpu = self.home_of(hit["home"])
        self.assertIn(req, [a["name"] for a in self.state()["acks"]])         # 帳上還在
        wait_for(lambda: not (cpu / "responses" / req).exists()               # cpu 先消化掉
                 and not list((cpu / "requests").glob("ack-*.json")))
        self.release("next")
        self.settle()
        self.assertEqual(self.state()["acks"], [])
        self.assertEqual((self.state()["procs"]["job"]["runs"], self.runs("job")), (1, 1))
        # 下一格照規範重放：新一格的 ack 名（不同 seq），對 cpu 無害（回音已不在、notification 沒回音）
        acks = self.trace(op="post", box="ack", target=req, outcome="ok")
        self.assertEqual([e["seq"] for e in acks], [hit["seq"], hit["seq"] + 1])
        self.assertEqual(len({e["name"] for e in acks}), 2)
        wait_for(lambda: not list((cpu / "requests").glob("ack-*.json")))
        self.assertEqual(sorted(p.name for p in (cpu / "responses").iterdir()), [])
        self.assertEqual(self.kid(*hit["home"].split("/"))["state"], "running")

    def test_c8_ack_recorded_not_delivered_is_delivered_next_tick(self):
        req = self.booked_job("ack", "before_put")
        hit, held = self.kill_tick("ack", hold="next")
        cpu = self.home_of(hit["home"])
        self.assertIn(req, [a["name"] for a in self.state()["acks"]])
        self.assertTrue((cpu / "responses" / req).exists())                   # 沒人 ack，回音留著
        self.release("next")
        wait_for(lambda: not (cpu / "responses" / req).exists())
        self.settle()
        self.assertEqual((self.state()["procs"]["job"]["runs"], self.runs("job")), (1, 1))
        self.assertEqual([e["seq"] for e in self.trace(op="post", box="ack", target=req, outcome="ok")],
                         [hit["seq"] + 1])

    def reply_window(self, point):
        self.setup_running()
        target, _ = self.job("once")
        name = aos_client.new_name("client")
        self.gate("reply", point, box="reply", name=name)
        aos_client.submit(self.home, "add", {"name": "once", "target": target, "once": True}, name=name)
        hit, held = self.kill_tick("reply", hold="next")
        self.assertEqual(self.state()["replies"][0]["name"], name)
        return name, hit

    def test_c8_reply_delivered_before_clear_client_acks_then_no_ghost(self):
        name, hit = self.reply_window("after_put")
        reply = read_json(self.home / "responses" / name)
        self.assertEqual(reply["result"]["code"], 0, reply)
        aos_client.ack(self.home, name)                                       # 交件者在重放前就收走
        self.release("next")
        wait_for(lambda: not (self.home / "responses" / name).exists())
        self.settle()
        self.assertFalse((self.home / "responses" / name).exists())            # 沒有鬼回音
        self.assertEqual([e["outcome"] for e in self.trace(op="reply", name=name)], ["ok", "exists"])
        self.assertEqual((self.state()["replies"], self.runs("once")), ([], 1))

    def test_c8_reply_recorded_not_delivered_is_delivered_once(self):
        name, hit = self.reply_window("before_put")
        self.assertFalse((self.home / "responses" / name).exists())
        self.release("next")
        response = aos_client.wait_response(self.home, name, timeout_ms=5000, poll_ms=5)
        self.assertEqual(response["result"]["code"], 0, response)
        aos_client.ack(self.home, name)
        wait_for(lambda: not (self.home / "responses" / name).exists())
        self.settle()
        self.assertFalse((self.home / "responses" / name).exists())
        self.assertEqual([e["outcome"] for e in self.trace(op="reply", name=name)], ["ok"])
        self.assertEqual(self.runs("once"), 1)

    def delete_window(self, point):
        """一則 add（反覆）已收、回音與刪原單都記在帳上；卡在刪原單的 point。"""
        self.setup_running()
        target, _ = self.job("job")
        name = aos_client.new_name("client")
        self.gate("del", point, box="delete", name=name)
        # 不給 name：重做的話會多出一個行程 "1"（而不是被 AlreadyExists 遮住）
        aos_client.submit(self.home, "add", {"target": target, "interval_ms": 600000}, name=name)
        hit, held = self.kill_tick("del", hold="next")
        self.assertEqual(self.state()["deletes"], [name])
        return name, hit

    def check_delete_converged(self, name, early):
        """early：原單已刪，交件者在重放前就讀回音、ack；否則原單還在，交件者照規矩等它消失（下一格才刪）。"""
        if not early:
            self.release("next")
        reply = aos_client.wait_response(self.home, name, timeout_ms=5000, poll_ms=5)
        self.assertEqual(reply, {"jsonrpc": "2.0", "id": name[:-5], "result": {"name": "0"}})
        aos_client.ack(self.home, name)
        if early:
            self.release("next")
        wait_for(lambda: not (self.home / "responses" / name).exists())
        wait_for(lambda: self.runs("job") == 1)
        self.settle()
        ledger = self.state()
        self.assertEqual((ledger["deletes"], list(ledger["procs"])), ([], ["0"]))
        self.assertEqual(ledger["procs"]["0"]["request"], name)
        self.assertFalse((self.home / "requests" / name).exists())
        self.assertEqual(len(self.trace(op="reply", name=name, outcome="ok")), 1)   # 沒有第二則（AlreadyExists）
        self.assertEqual(self.runs("job"), 1)

    def test_c8_delete_done_before_clear_syscall_not_reapplied(self):
        name, hit = self.delete_window("after_put")
        self.assertFalse((self.home / "requests" / name).exists())
        self.check_delete_converged(name, early=True)
        self.assertEqual([e["outcome"] for e in self.trace(op="delete", name=name)], ["ok", "missing"])

    def test_c8_delete_recorded_not_done_syscall_not_reapplied(self):
        name, hit = self.delete_window("before_put")
        self.assertTrue((self.home / "requests" / name).exists())              # 原單還在，但已記在 deletes
        self.check_delete_converged(name, early=False)
        self.assertEqual([e["outcome"] for e in self.trace(op="delete", name=name)], ["ok"])

    # ---- C-8：sends 箱的縮池單（取代 proto5 的 stop 箱；handoff §3） ----

    def shrink_window(self, point):
        """kernel halt：停機縮池那格要送 default 的 count 0；卡在那張 scale 單的 point。"""
        self.setup_running()
        self.gate("scale", point, box="daemon", name_endswith="-scale-default.json")
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        hit, held = self.kill_tick("scale", hold="next")
        ledger = self.state()
        entry = ledger["pools"]["default"]
        self.assertEqual((ledger["phase"], ledger["halting"]), ("stopping", True))
        self.assertEqual(entry["pending"], {"name": hit["name"], "count": 0, "skip": []})
        self.assertEqual([s["name"] for s in ledger["sends"]], [hit["name"]])     # 帳上還在
        return hit

    def finish_halt_and_reboot(self, hit):
        self.release("next")
        wait_for(lambda: self.state()["phase"] == "stopped", timeout=8)
        self.wait_gone("default")
        self.wait_gone("kernel")
        # 縮池單的回音收完就 ack 掉；kernel 池那張的回音照 handoff §3 留在 daemon 家，等下次 boot 讀
        wait_for(lambda: not (self.daemon / "responses" / hit["name"]).exists(), timeout=8)
        self.assertEqual(len(self.trace(op="post", box="daemon", name=hit["name"], outcome="ok")), 1)
        self.assertEqual(self.state()["pools"]["default"]["sent"], {"count": 0, "skip": []})
        # 下次 boot 照常：重宣告、派工
        self.boot()
        target, _ = self.job("after")
        self.add(target, "after", interval_ms=600000)
        wait_for(lambda: self.state()["procs"]["after"]["runs"] == 1, timeout=8)
        self.assertEqual((self.runs("after"), self.state()["procs"]["after"]["fails"]), (1, 0))
        self.assertEqual(self.summary("default")["count"], 2)

    def test_c8_shrink_delivered_before_clear_daemon_answers_while_kernel_dead(self):
        hit = self.shrink_window("after_put")
        # kernel 那格死了，daemon 照樣處理：池收完、拿掉，回音在 D/responses
        self.wait_gone("default")
        self.assertIn("result", read_json(self.daemon / "responses" / hit["name"]))
        self.finish_halt_and_reboot(hit)
        # 下一格出貨看到回音已在，不再放同名單（D-25）；收音照 kernel-pools §2 第 1 步
        self.assertEqual([e["seq"] for e in self.trace(op="post", box="daemon", name=hit["name"])], [hit["seq"]])

    def test_c8_shrink_recorded_not_delivered_is_delivered_next_tick(self):
        hit = self.shrink_window("before_put")
        self.assertFalse((self.daemon / "requests" / hit["name"]).exists())
        self.assertEqual(self.summary("default")["count"], 2)                    # daemon 什麼都不知道
        self.finish_halt_and_reboot(hit)
        self.assertEqual([e["seq"] for e in self.trace(op="post", box="daemon", name=hit["name"])], [hit["seq"] + 1])

    def test_c8_kernel_pool_shrink_delivered_before_clear_next_boot_recovers(self):
        """停機最後一張是 kernel 池的 count 0：它送出後 kernel cpu 就被收，帳上沒清的由下次 boot 收尾（handoff §3 第 3 步）。"""
        self.setup_running()
        self.gate("scale", "after_put", box="daemon", name_endswith="-scale-kernel.json")
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        hit = self.reached("scale")
        os.kill(hit["pid"], signal.SIGKILL)
        self.wait_gone("kernel")
        self.wait_gone("default")
        ledger = self.state()
        self.assertEqual(ledger["phase"], "stopped")
        self.assertEqual(ledger["pools"]["kernel"]["pending"]["name"], hit["name"])
        self.assertEqual(len(self.trace(op="post", box="daemon", name=hit["name"])), 1)   # 沒重放
        self.assertTrue((self.daemon / "responses" / hit["name"]).exists())       # 回音留在 daemon 家
        self.boot()                                                               # 第 2 步讀掉舊 pending、ack
        self.assertEqual(self.state()["phase"], "running")
        wait_for(lambda: not (self.daemon / "responses" / hit["name"]).exists(), timeout=8)
        target, _ = self.job("after")
        self.add(target, "after", interval_ms=600000)
        wait_for(lambda: self.state()["procs"]["after"]["runs"] == 1, timeout=8)
        self.assertEqual(self.runs("after"), 1)

    # ---- C-9：kernel 改宣告（長大）一半死，真 daemon 在中間處理 ----

    def test_c9_grow_delivered_then_killed_daemon_grows_meanwhile(self):
        """scale 單已放、帳還沒清就被 KILL；daemon 在 kernel 死掉時照單長大、回音。
        下一格：回音已在所以不重放（D-25）；收音照結帳，新的號進 free，派得到。"""
        self.setup_running({"default": {"count": 1}})
        ver = self.summary("default")["ver"]
        self.gate("grow", "after_put", box="daemon", name_endswith="-scale-default.json")
        self.set_count("default", 3)
        hit, held = self.kill_tick("grow", hold="next")
        entry = self.state()["pools"]["default"]
        self.assertEqual((entry["sent"]["count"], entry["pending"]["count"]), (1, 3))
        self.wait_running("default", 3)                                         # daemon 自己長大了
        self.assertEqual(self.summary("default")["ver"], ver + 1)
        self.assertIn("result", read_json(self.daemon / "responses" / hit["name"]))
        self.assertEqual(self.state()["pools"]["default"]["free"], [0])          # 還沒確認的號不派
        self.release("next")
        wait_for(lambda: self.state()["pools"]["default"]["sent"]["count"] == 3)
        self.assertEqual(sorted(self.state()["pools"]["default"]["free"]), [0, 1, 2])
        wait_for(lambda: not (self.daemon / "responses" / hit["name"]).exists())
        self.assertEqual([e["seq"] for e in self.trace(op="post", box="daemon", name=hit["name"])], [hit["seq"]])
        self.assertEqual(self.summary("default")["ver"], ver + 1)                # 沒有第二次宣告
        self.two_jobs_after_grow()

    def two_jobs_after_grow(self):
        targets = [self.job(n)[0] for n in ("a", "b", "c")]
        for n, t in zip(("a", "b", "c"), targets):
            self.add(t, n, interval_ms=600000)
        wait_for(lambda: all(self.state()["procs"][n]["runs"] == 1 for n in ("a", "b", "c")), timeout=10)
        self.assertEqual({self.runs(n) for n in ("a", "b", "c")}, {1})
        self.assert_no_same_name_twice()
