"""daemon 崩潰窗口（proto5-2 按池版）：閘門卡住真 daemon、真 SIGKILL、下一任接手。

手法沿用 proto5 的 daemon-crash 筆記：閘門全在測試 driver 裡用替換函式注入（GATED），產品程式沒有任何測試掛鉤。
所有 daemon 都由 HUB 拉起：HUB 是 subreaper，daemon 被 KILL 後孤兒歸它收屍；它先用 WNOWAIT 偷看、
記下退出狀態才真的收屍——所以殭屍消失（下一任 daemon 的 kill(pid,0) 看到「不在」）之前，記錄一定已經寫好。
test_kernel_crash 借用這裡的 HUB（同名保留）。
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

import aos_client
import aos_home

from _daemon_util import CLI, LIB, PY, DaemonCase, read_json, wait_for

# 測試專用 subreaper：照 cmd-N.json 用 posix_spawn 拉 daemon，記下每個收到的死者。
HUB = r'''
import ctypes, json, os, signal, sys, time
from pathlib import Path
hub = Path(sys.argv[1])
if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0):
    raise OSError(ctypes.get_errno(), 'prctl')
parent = os.getppid()
def publish(path, obj):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj))
    os.replace(tmp, path)
def reap_one():
    try:
        info = os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return None
    if info is None:
        return False
    killed = info.si_code in (os.CLD_KILLED, os.CLD_DUMPED)
    with (hub / 'reaped.jsonl').open('a') as f:
        f.write(json.dumps({'pid': info.si_pid, ('signal' if killed else 'exit'): info.si_status}) + '\n')
    os.waitpid(info.si_pid, 0)
    return True
def kids():
    # 直接孩子＝拉起的 daemon＋收養的孤兒（測試還沒記到 pid 就失敗的也算）
    found = []
    for entry in os.listdir('/proc'):
        if entry.isdigit():
            try:
                stat = open('/proc/%s/stat' % entry).read()
            except OSError:
                continue
            if int(stat.rsplit(')', 1)[1].split()[1]) == os.getpid():
                found.append(int(entry))
    return found
def finish():
    # 只砍還沒收屍的直接孩子（pid 不可能被別人重用）與它們那一組
    until = time.monotonic() + 4
    while time.monotonic() < until:
        for pid in kids():
            for kill in (os.killpg, os.kill):
                try: kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError): pass
        done = reap_one()
        if done is None: return
        if not done: time.sleep(.005)
seq = 0
while True:
    while reap_one(): pass
    cmd = hub / ('cmd-%d.json' % seq)
    if cmd.exists():
        spec = json.loads(cmd.read_text())
        log = str(hub / ('daemon-%d.log' % seq))
        actions = [(os.POSIX_SPAWN_OPEN, 0, '/dev/null', os.O_RDONLY, 0),
                   (os.POSIX_SPAWN_OPEN, 1, '/dev/null', os.O_WRONLY, 0),
                   (os.POSIX_SPAWN_OPEN, 2, log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)]
        pid = os.posix_spawn(sys.executable, [sys.executable] + spec['argv'],
                             dict(os.environ, **spec.get('env', {})), file_actions=actions)
        publish(hub / ('started-%d.json' % seq), {'pid': pid})
        seq += 1
        continue
    quit = hub / 'quit.json'
    if quit.exists():
        finish()
        break
    if os.getppid() != parent:
        finish()
        break
    time.sleep(.002)
'''

# 閘門 daemon：跑真的 aos_daemon.run，只在 AOS_TEST_GATES 點名的步驟寫 <點>.reached 後停住，等測試 SIGKILL。
# 沒點名的步驟照常走。另記證據：spawns.jsonl（每次 fork 的孩子）、responses.jsonl（每次寫回音）、
# published.json（第一次寫自己的 state 那一刻，上一任 kids 檔／舊表裡每個 pid 還在不在）。
# spawned 閘門在第 AOS_TEST_GATE_N 顆拉起來（go 已送）之後停；pool_written／before_pool_json 有
# AOS_TEST_GATE_VER 時只在那個 ver 停。另記 forks.jsonl（每次 fork，kids 檔還沒寫）與 summaries.jsonl（寫摘要的池）。
GATED = r'''
import json, os, signal, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos_daemon, aos_daemon_loop, aos_daemon_pools, aos_home
home = Path(sys.argv[2]).absolute()
gates = set(filter(None, os.environ.get('AOS_TEST_GATES', '').split(',')))
gate_dir = Path(os.environ['AOS_TEST_GATE_DIR'])
nth = int(os.environ.get('AOS_TEST_GATE_N', '1'))
only_ver = os.environ.get('AOS_TEST_GATE_VER')
phase = ['startup']
real_write = aos_home.write_json
(home / 'pools').mkdir(parents=True, exist_ok=True)
old_pids = sorted(aos_daemon._scan_pools(home)[2])
def record(name, obj):
    with (gate_dir / name).open('a') as f:
        f.write(json.dumps(obj) + '\n')
def gate(point, **extra):
    if point in gates:
        real_write(gate_dir / (point + '.reached'), dict(extra, daemon=os.getpid()))
        while True:
            time.sleep(1)
def write_json(path, obj):
    real_write(path, obj)
    path = Path(path)
    if path.name == 'summary.json':
        record('summaries.jsonl', path.parent.name)
    if path.parent == home / 'responses':
        record('responses.jsonl', path.name)
        gate('reconcile_interrupted' if phase[0] == 'reconcile' else 'responded', name=path.name)
aos_home.write_json = write_json
real_pool = aos_daemon_pools.write_pool_json
def write_pool_json(target, decl):
    hit = only_ver is None or int(only_ver) == decl['ver']
    if hit:
        gate('before_pool_json', ver=decl['ver'])              # 收了單、寫 pool.json 之前
    real_pool(target, decl)
    if hit:
        gate('pool_written', ver=decl['ver'])                  # 寫了 pool.json、回音之前
aos_daemon_pools.write_pool_json = write_pool_json
class GatedOs:
    """只給 aos_daemon_pools 用：刪完某池的 summary.json 之後停（還沒刪 pool.json）。"""
    def __getattr__(self, name):
        return getattr(os, name)
    def unlink(self, path, *args, **kwargs):
        os.unlink(path, *args, **kwargs)
        path = Path(path)
        if path.name == 'summary.json' and path.parent.parent == home / 'pools':
            gate('summary_removed', pool=path.parent.name)
aos_daemon_pools.os = GatedOs()
real_spawn = aos_daemon_pools.spawn_child
def spawn_child(*args, **kwargs):
    handle = real_spawn(*args, **kwargs)
    record('forks.jsonl', handle.process.pid)
    gate('forked', child=handle.process.pid)                   # fork 完、kids 檔還沒寫
    return handle
aos_daemon_pools.spawn_child = spawn_child
real_launch = aos_daemon_loop.Daemon.launch
spawned = []
def launch(self, pool, kid):
    real_launch(self, pool, kid)
    if kid.handle is not None and kid.state == 'running':
        spawned.append(kid.pid)
        record('spawns.jsonl', kid.pid)
        if len(spawned) == nth:
            gate('spawned', child=kid.pid)                     # 第 n 顆 go 已送
aos_daemon_loop.Daemon.launch = launch
real_line = aos_daemon_loop.Daemon.write_line
def write_line(self, kid, method):
    if method == 'go':
        gate('before_go', child=kid.pid)                       # kids 檔已寫、go 未送
    return real_line(self, kid, method)
aos_daemon_loop.Daemon.write_line = write_line
real_signal = aos_daemon._signal_pid
def signal_pid(pid, sig, group=False):
    real_signal(pid, sig, group)
    gate('prev_term' if sig == signal.SIGTERM else 'prev_kill', child=pid)
aos_daemon._signal_pid = signal_pid
real_previous = aos_daemon._previous_children
def previous(pids, info):
    real_previous(pids, info)
    gate('prev_done')                                          # 舊孩子死透、對帳之前
aos_daemon._previous_children = previous
real_reconcile = aos_home.reconcile
def reconcile(target, current):
    phase[0] = 'reconcile'
    real_reconcile(target, current)
    phase[0] = 'loop'
    gate('reconciled')
aos_home.reconcile = reconcile
real_save = aos_daemon_loop.Daemon.save
published = []
def save(self):
    if not published and self.state['pid'] == os.getpid():     # 新 state 第一次公布
        published.append(True)
        real_write(gate_dir / 'published.json', {str(p): aos_daemon._pid_exists(p) for p in old_pids})
    real_save(self)
aos_daemon_loop.Daemon.save = save
sys.exit(aos_daemon.run(home))
'''


class DaemonCrashWindowTest(DaemonCase):
    PREFIX = "aos-daemon-crash-"

    def setUp(self):
        super().setUp()
        self.hub = self.root / "hub"
        self.hub.mkdir()
        self.seq = 0
        log = open(self.root / "hub.log", "ab")
        self.addCleanup(log.close)
        self.hub_proc = subprocess.Popen([PY, "-c", HUB, str(self.hub)], stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=log, start_new_session=True)
        self.addCleanup(self.stop_hub)

    def stop_hub(self):
        aos_home.write_json(self.hub / "quit.json", {})
        try:
            self.hub_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.hub_proc.kill()
            self.hub_proc.wait(timeout=4)
            raise

    # ---- hub 與 daemon ----

    def daemon(self, gates=(), n=1, ver=None):
        seq, self.seq = self.seq, self.seq + 1
        gate_dir = self.root / ("gates-%d" % seq)
        gate_dir.mkdir()
        env = {"AOS_TEST_GATES": ",".join(gates), "AOS_TEST_GATE_DIR": str(gate_dir), "AOS_TEST_GATE_N": str(n)}
        if ver is not None:
            env["AOS_TEST_GATE_VER"] = str(ver)
        aos_home.write_json(self.hub / ("cmd-%d.json" % seq),
                            {"argv": ["-c", GATED, str(LIB), str(self.home)], "env": env})
        pid = wait_for(lambda: read_json(self.hub / ("started-%d.json" % seq), {}).get("pid"))
        return pid, gate_dir

    def reached(self, gate_dir, gate):
        return wait_for(lambda: read_json(gate_dir / (gate + ".reached")))

    def reaped(self):
        path = self.hub / "reaped.jsonl"
        if not path.exists():
            return {}
        return {entry["pid"]: entry for entry in map(json.loads, path.read_text().splitlines())}

    def sigkill(self, pid):
        os.kill(pid, signal.SIGKILL)
        self.assertEqual(wait_for(lambda: self.reaped().get(pid)), {"pid": pid, "signal": 9})

    def published(self, pid, gate_dir, old_pids):
        """等新任公布 state：公布那一刻上一任的孩子一個都不在（kill(pid,0) 當場探）。"""
        wait_for(lambda: self.state().get("pid") == pid)
        self.assertEqual(read_json(gate_dir / "published.json"), {str(p): False for p in old_pids})
        return self.reaped()

    def records(self, name, gate_dir=None):
        found = []
        for path in sorted(self.root.glob("gates-*/" + name) if gate_dir is None else [gate_dir / name]):
            if not path.exists():
                continue
            found += [json.loads(line) for line in path.read_text().splitlines()]
        return found

    def stop_daemon(self, pid):
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(wait_for(lambda: self.reaped().get(pid)), {"pid": pid, "exit": 0}, self.logs())
        self.assertEqual(self.state()["pid"], 0)

    def logs(self):
        return "".join(p.read_text() for p in sorted(self.hub.glob("daemon-*.log")))

    def cpu_targets(self, n):
        for i in range(n):
            cpu = self.root / "cpus" / str(i)
            cpu.mkdir(parents=True)
            aos_home.write_json(cpu / "info.json", {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 5})
            aos_home.write_json(cpu / "inst.json", {"argv": [PY, str(CLI / "aos-cpu"), str(cpu)]})
        return str(self.root / "cpus/{name}/inst.json")

    def assert_interrupted(self, request):
        self.assertFalse((self.home / "requests" / request).exists())
        response = read_json(self.home / "responses" / request)
        self.assertEqual(response["id"], request[:-5])
        self.assertEqual(response["error"]["data"]["code"], "Interrupted", response)
        self.assertEqual(self.records("responses.jsonl").count(request), 1)      # 回音只寫過一次

    def submit_scale(self, count, target, decl=None):
        params = {"pool": "p", "owner": "/k", "count": count, "target": target}
        if decl is not None:
            params["decl"] = decl
        return aos_client.submit(self.home, "scale", params)

    # ---- 拉一半死 ----

    def test_killed_mid_fill_next_daemon_kills_old_and_fills_exactly(self):
        target = self.targets(5, "kill")
        gen1, g1 = self.daemon(["spawned"], n=2)
        wait_for(lambda: self.state().get("pid") == gen1)
        self.submit_scale(5, target)
        reached = self.reached(g1, "spawned")
        old = self.records("spawns.jsonl")
        self.assertEqual(len(old), 2)
        self.assertEqual(reached["child"], old[1])
        wait_for(lambda: all(self.starts("p", i) for i in range(2)))
        self.sigkill(gen1)
        time.sleep(.1)
        self.assertFalse(set(old) & set(self.reaped()))           # EOF 叫不停 kill 模式的孩子
        gen2, g2 = self.daemon()
        reaped = self.published(gen2, g2, old)
        for pid in old:                                            # 公布前舊的已死透（TERM 被忽略 → KILL）
            self.assertEqual(reaped.get(pid), {"pid": pid, "signal": 9})
        self.running("p", 5)
        time.sleep(.2)
        self.assertEqual(len(self.records("spawns.jsonl")), 7)    # 舊 2 顆＋照 pool.json 補 5 顆，不多拉
        self.assertEqual([self.kid("p", i)["gen"] for i in range(5)], [2, 2, 1, 1, 1])
        self.assertEqual(self.summary()["running"], 5)
        self.stop_daemon(gen2)

    def test_killed_after_kid_file_before_go_real_cpu_untouched(self):
        target = self.cpu_targets(1)
        gen1, g1 = self.daemon(["before_go"])
        wait_for(lambda: self.state().get("pid") == gen1)
        self.submit_scale(1, target)
        child = self.reached(g1, "before_go")["child"]
        self.assertEqual(self.kid("p", 0)["state"], "running")
        self.sigkill(gen1)
        self.assertEqual(wait_for(lambda: self.reaped().get(child)), {"pid": child, "exit": 0})
        self.assertEqual(sorted(os.listdir(self.root / "cpus/0")), ["info.json", "inst.json"])
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [child])
        fresh = wait_for(lambda: (self.kid("p", 0) or {}).get("state") == "running" and
                         self.kid("p", 0)["pid"] != child and self.kid("p", 0)["pid"])
        wait_for(lambda: read_json(self.root / "cpus/0/state.json", {}).get("pid") == fresh)
        self.assertEqual(self.kid("p", 0)["gen"], 2)
        self.stop_daemon(gen2)

    # ---- scale 單的兩個窗口（protocol §4）----

    def test_killed_after_pool_json_before_response(self):
        target = self.targets(2)
        gen1, g1 = self.daemon(["pool_written"])
        wait_for(lambda: self.state().get("pid") == gen1)
        request = self.submit_scale(2, target, [7, 1])
        self.assertEqual(self.reached(g1, "pool_written")["ver"], 1)
        self.sigkill(gen1)
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["ver"], 1)
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [])
        self.assert_interrupted(request)
        self.running("p", 2)                                       # 宣告已生效
        self.assertEqual(self.ok(self.scale(count=2, target=target, decl=[7, 1])),
                         {"pool": "p", "count": 2, "ver": 1})       # 重送同一份，ver 不加
        self.assertEqual(len(self.records("spawns.jsonl")), 2)
        self.stop_daemon(gen2)

    def test_killed_after_request_before_pool_json(self):
        target = self.targets(2)
        gen1, g1 = self.daemon(["before_pool_json"])
        wait_for(lambda: self.state().get("pid") == gen1)
        request = self.submit_scale(2, target, [7, 1])
        self.reached(g1, "before_pool_json")
        self.assertEqual(self.state()["current"]["name"], request)
        self.sigkill(gen1)
        self.assertFalse((self.home / "pools/p").exists())
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [])
        self.assert_interrupted(request)
        self.assertFalse((self.home / "pools/p").exists())         # 宣告沒生效
        self.assertEqual(self.ok(self.scale(count=2, target=target, decl=[7, 1]))["ver"], 1)
        self.running("p", 2)
        self.stop_daemon(gen2)

    # ---- 接手中的 daemon 再被 KILL ----

    def test_killed_twice_during_takeover_third_converges(self):
        target = self.targets(1, "kill")
        gen1, g1 = self.daemon(["spawned"])
        wait_for(lambda: self.state().get("pid") == gen1)
        self.submit_scale(1, target)
        child = self.reached(g1, "spawned")["child"]
        wait_for(lambda: self.starts("p", 0))
        first = self.state()
        self.sigkill(gen1)
        for _ in range(2):
            gen, gate_dir = self.daemon(["prev_term"])
            self.assertEqual(self.reached(gate_dir, "prev_term")["daemon"], gen)
            self.sigkill(gen)
            self.assertEqual(self.state(), first)                  # 新 state 還沒公布，舊的原封不動
            self.assertEqual(self.kid("p", 0)["pid"], child)
        self.assertNotIn(child, self.reaped())
        last, gate_dir = self.daemon()
        self.assertEqual(self.published(last, gate_dir, [child]).get(child), {"pid": child, "signal": 9})
        wait_for(lambda: len(self.starts("p", 0)) == 2)
        self.assertEqual(len(self.records("spawns.jsonl")), 2)
        self.stop_daemon(last)

    def test_killed_after_interrupted_written_before_request_deleted(self):
        target = self.targets(1)
        gen1, g1 = self.daemon(["pool_written"])
        wait_for(lambda: self.state().get("pid") == gen1)
        request = self.submit_scale(1, target)
        self.reached(g1, "pool_written")
        self.sigkill(gen1)
        gen2, g2 = self.daemon(["reconcile_interrupted"])
        self.reached(g2, "reconcile_interrupted")
        self.sigkill(gen2)
        written = (self.home / "responses" / request).read_bytes()
        self.assertTrue((self.home / "requests" / request).exists())
        gen3, g3 = self.daemon()
        self.published(gen3, g3, [])
        self.assert_interrupted(request)
        self.assertEqual((self.home / "responses" / request).read_bytes(), written)
        self.running("p", 1)
        self.stop_daemon(gen3)


    # ---- review P10：跨邊界的定點崩潰 ----

    def test_killed_after_scale_response_before_request_deleted(self):
        """回了成功、還沒刪原單就崩：重開保留成功回音（bytes 不變）、消掉原單、不重做。"""
        target = self.targets(1)
        gen1, g1 = self.daemon(["responded"])
        wait_for(lambda: self.state().get("pid") == gen1)
        request = self.submit_scale(1, target, [3, 1])
        self.reached(g1, "responded")
        self.sigkill(gen1)
        written = (self.home / "responses" / request).read_bytes()
        self.assertEqual(json.loads(written)["result"], {"pool": "p", "count": 1, "ver": 1})
        self.assertTrue((self.home / "requests" / request).exists())
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [])
        self.assertFalse((self.home / "requests" / request).exists())
        self.assertEqual((self.home / "responses" / request).read_bytes(), written)
        self.assertEqual(self.records("responses.jsonl").count(request), 1)   # 沒重做
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["ver"], 1)
        self.running("p", 1)
        self.stop_daemon(gen2)

    def test_killed_after_summary_removed_before_pool_json(self):
        """刪了 summary、還沒刪 pool.json 就崩：重開不把池拉回來（不寫摘要、不拉孩子），照規則收完再刪。"""
        target = self.targets(1)
        gen1, g1 = self.daemon(["summary_removed"])
        wait_for(lambda: self.state().get("pid") == gen1)
        self.ok(self.scale(count=1, target=target))
        self.running("p", 1)
        self.ok(self.scale(count=0))
        self.assertEqual(self.reached(g1, "summary_removed")["pool"], "p")
        self.sigkill(gen1)
        self.assertIsNone(self.summary())
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["count"], 0)
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [])
        wait_for(lambda: not (self.home / "pools/p").exists())
        self.assertEqual(self.records("summaries.jsonl", g2), [])              # 沒把池發布回來
        self.assertEqual(len(self.records("spawns.jsonl")), 1)                 # 沒再拉
        self.assertEqual(self.ok(self.call("ls"))["pools"], {})
        self.stop_daemon(gen2)

    def test_killed_after_readd_of_killing_before_reconcile(self):
        """killing 中的號又被加回、pool.json 已寫、還沒對帳就崩：下一任先收乾淨舊的，再照最新宣告拉恰好一支。"""
        self.set_info(stop_wait_ms=5000, kill_wait_ms=5000)
        target = self.targets(2, "kill")                                       # 不理 stop 也不理 TERM
        gen1, g1 = self.daemon(["pool_written"], ver=3)
        wait_for(lambda: self.state().get("pid") == gen1)
        self.assertEqual(self.ok(self.scale(count=2, target=target))["ver"], 1)
        self.running("p", 2)
        old = self.records("spawns.jsonl")
        self.assertEqual(self.ok(self.scale(count=1))["ver"], 2)
        wait_for(lambda: (self.kid("p", 1) or {}).get("state") == "killing")
        request = self.submit_scale(2, target)
        self.assertEqual(self.reached(g1, "pool_written")["ver"], 3)
        self.sigkill(gen1)
        self.assertEqual(read_json(self.home / "pools/p/pool.json")["count"], 2)
        self.assertEqual(self.kid("p", 1)["state"], "killing")
        self.set_info(stop_wait_ms=80, kill_wait_ms=80)
        gen2, g2 = self.daemon()
        reaped = self.published(gen2, g2, old)
        for pid in old:
            self.assertEqual(reaped.get(pid), {"pid": pid, "signal": 9})
        self.assert_interrupted(request)
        self.running("p", 2)
        time.sleep(.2)
        self.assertEqual(len(self.records("spawns.jsonl", g2)), 2)            # 每號恰好一支
        self.assertEqual([len(self.starts("p", i)) for i in range(2)], [2, 2])
        self.assertEqual(self.summary()["killing"] + self.summary()["draining"], 0)
        self.stop_daemon(gen2)

    def test_killed_after_fork_before_kid_file(self):
        """fork 完、kids 檔還沒寫就崩：沒收到 go 的孩子不碰家、自己退；下一任不多拉。"""
        target = self.cpu_targets(1)
        gen1, g1 = self.daemon(["forked"])
        wait_for(lambda: self.state().get("pid") == gen1)
        self.submit_scale(1, target)
        child = self.reached(g1, "forked")["child"]
        self.assertIsNone(self.kid("p", 0))
        self.sigkill(gen1)
        self.assertEqual(wait_for(lambda: self.reaped().get(child)), {"pid": child, "exit": 0})
        self.assertEqual(sorted(os.listdir(self.root / "cpus/0")), ["info.json", "inst.json"])
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [])
        fresh = wait_for(lambda: (self.kid("p", 0) or {}).get("state") == "running" and self.kid("p", 0)["pid"])
        wait_for(lambda: read_json(self.root / "cpus/0/state.json", {}).get("pid") == fresh)
        time.sleep(.2)
        self.assertEqual(self.records("forks.jsonl", g2), [fresh])            # 下一任只拉一支
        self.assertEqual(self.kid("p", 0)["gen"], 1)
        self.stop_daemon(gen2)


if __name__ == "__main__":
    unittest.main()
