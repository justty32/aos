"""daemon 崩潰窗口（審查 C-2、C-3）：多段閘門卡住真 daemon、真 SIGKILL、下一任接手。

閘門全在測試 driver 裡用替換函式注入（GATED），產品程式沒有任何測試掛鉤。
所有 daemon 都由 HUB 拉起：HUB 是 subreaper，daemon 被 KILL 後孤兒歸它收屍；
它先用 WNOWAIT 偷看、記下退出狀態，才真的收屍——所以殭屍消失（下一任 daemon
的 kill(pid,0) 看到「不在」）之前，記錄一定已經寫好，測試可以拿「新 state 公布那一刻」
比對「舊孩子是否已被收屍、怎麼死的」。
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import aos_client
import aos_home

from _daemon_util import CHILD, wait_for, read_json

CLI = Path(__file__).resolve().parents[2] / "cli"
LIB = CLI.parent / "lib"
PY = sys.executable

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

# 閘門 daemon：跑真的 aos_daemon.run，只在 AOS_TEST_GATES 點名的步驟寫 <點>.reached 後停住，
# 等測試 SIGKILL。沒點名的步驟照常走，所以跟產品路徑一樣。另外記三樣證據到 gate 資料夾：
# spawns.jsonl（每次 fork 的孩子）、responses.jsonl（每次寫回音）、published.json
#（第一次寫自己的 state 那一刻，上一任表裡每個 pid 還在不在）。
GATED = r'''
import json, os, signal, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos_daemon, aos_exec, aos_home
home = Path(sys.argv[2]).absolute()
gates = set(filter(None, os.environ.get('AOS_TEST_GATES', '').split(',')))
gate_dir = Path(os.environ['AOS_TEST_GATE_DIR'])
phase = ['startup']
real_write = aos_home.write_json
old_pids = sorted({c['pid'] for c in aos_daemon.read_state(home).get('children', {}).values()
                   if type(c.get('pid')) is int and c['pid'] > 0})
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
    if path.parent == home / 'responses':
        record('responses.jsonl', path.name)
        gate('reconcile_interrupted' if phase[0] == 'reconcile' else 'responded', name=path.name)
aos_home.write_json = write_json
real_spawn = aos_exec.spawn_target
def spawn_target(*args, **kwargs):
    handle = real_spawn(*args, **kwargs)
    record('spawns.jsonl', handle.process.pid)
    gate('spawned', child=handle.process.pid)             # fork 之後、寫孩子表之前
    return handle
aos_exec.spawn_target = spawn_target
real_send = aos_daemon.Daemon._send
def send(self, name, method):
    if method == 'go':
        gate('before_go', child=self.children[name]['pid'])   # 孩子表已寫、go 未送
    real_send(self, name, method)
    if method == 'go':
        gate('go_sent', child=self.children[name]['pid'])     # go 已送、回音未寫
aos_daemon.Daemon._send = send
real_signal = aos_daemon._signal_pid
def signal_pid(pid, sig, group=False):
    real_signal(pid, sig, group)
    if phase[0] == 'startup':                                  # 接手上一任孩子時送出的訊號
        gate('prev_term' if sig == signal.SIGTERM else 'prev_kill', child=pid)
aos_daemon._signal_pid = signal_pid
real_previous = aos_daemon._previous_children
def previous(state, info):
    real_previous(state, info)
    gate('prev_done')                                          # 舊孩子死透、對帳之前
aos_daemon._previous_children = previous
real_reconcile = aos_home.reconcile
def reconcile(target, current):
    phase[0] = 'reconcile'
    real_reconcile(target, current)
    phase[0] = 'loop'
    gate('reconciled')                                         # 對帳完、新 state 未公布
aos_home.reconcile = reconcile
real_save = aos_daemon.Daemon.save
published = []
def save(self):
    if not published and self.state['pid'] == os.getpid():     # 新 state 第一次公布
        published.append(True)
        real_write(gate_dir / 'published.json', {str(p): aos_daemon._pid_exists(p) for p in old_pids})
    real_save(self)
aos_daemon.Daemon.save = save
sys.exit(aos_daemon.run(home))
'''


class DaemonCrashWindowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-daemon-crash-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "D"
        self.home.mkdir()
        aos_home.write_json(self.home / "info.json", {"_metainfo": {"_type": "daemon", "_version": 1},
            "poll_ms": 5, "restart_delay_ms": 80, "stop_wait_ms": 80, "kill_wait_ms": 80})
        self.child_script = self.root / "child.py"
        self.child_script.write_text(CHILD)
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

    def launch(self, argv, env=None):
        seq, self.seq = self.seq, self.seq + 1
        aos_home.write_json(self.hub / ("cmd-%d.json" % seq), {"argv": argv, "env": env or {}})
        pid = wait_for(lambda: read_json(self.hub / ("started-%d.json" % seq), {}).get("pid"))
        return pid

    def daemon(self, gates=()):
        gate_dir = self.root / ("gates-%d" % self.seq)
        gate_dir.mkdir()
        pid = self.launch(["-c", GATED, str(LIB), str(self.home)],
                          {"AOS_TEST_GATES": ",".join(gates), "AOS_TEST_GATE_DIR": str(gate_dir)})
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
        """等新任公布 state：公布那一刻上一任的孩子一個都不在（kill(pid,0) 當場探），回 hub 收屍名單。"""
        wait_for(lambda: self.state().get("pid") == pid)
        probe = read_json(gate_dir / "published.json")
        self.assertEqual(probe, {str(p): False for p in old_pids})
        return self.reaped()

    def records(self, name):
        found = []
        for path in sorted(self.root.glob("gates-*/" + name)):
            found += [json.loads(line) for line in path.read_text().splitlines()]
        return found

    def stop_daemon(self, pid, spawns=1):
        self.assertEqual(len(self.records("spawns.jsonl")), spawns)   # 沒有多拉任何一顆
        aos_home.post_request(self.home, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(wait_for(lambda: self.reaped().get(pid)), {"pid": pid, "exit": 0},
                         self.logs())
        self.assertEqual(self.state()["pid"], 0)
        self.assertEqual(self.state()["children"], {})

    def logs(self):
        return "".join(p.read_text() for p in sorted(self.hub.glob("daemon-*.log")))

    # ---- 家與目標 ----

    def state(self):
        return read_json(self.home / "state.json", {})

    def kill_target(self):
        """不聽 TERM、不讀 stdin（EOF 叫不停）的孩子；收到 go 才寫 ready。"""
        ready = self.root / "child.ready"
        target = self.root / "child.json"
        aos_home.write_json(target, {"argv": [PY, str(self.child_script), "kill", str(ready)]})
        return str(target), ready

    def cpu_target(self):
        cpu = self.root / "cpu"
        cpu.mkdir()
        aos_home.write_json(cpu / "info.json", {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 5})
        aos_home.write_json(cpu / "inst.json", {"argv": [PY, str(CLI / "aos-cpu"), str(cpu)]})
        return str(cpu / "inst.json"), cpu

    def crash_mid_spawn(self, gate, target):
        """第一任卡在 spawn 的某一步，SIGKILL；回（原單名、孩子 pid、被 KILL 前的 state）。"""
        gen1, gates = self.daemon([gate])
        wait_for(lambda: self.state().get("pid") == gen1)
        request = aos_client.submit(self.home, "spawn", {"name": "child", "target": target})
        reached = self.reached(gates, gate)
        before = self.state()
        child = reached.get("child") or before["children"]["child"]["pid"]
        self.sigkill(gen1)
        return request, child, before

    def assert_interrupted(self, request):
        self.assertFalse((self.home / "requests" / request).exists())
        response = read_json(self.home / "responses" / request)
        self.assertEqual(response["id"], request[:-5])
        self.assertEqual(response["error"]["data"]["code"], "Interrupted", response)
        self.assertEqual(os.listdir(self.home / "responses"), [request])
        self.assertEqual(self.records("responses.jsonl"), [request])       # 回音只寫過一次
        return response

    # ---- C-2：daemon 握手中段被 KILL ----

    def test_c2_killed_after_fork_before_table_child_exits_untouched(self):
        target, cpu = self.cpu_target()
        request, child, before = self.crash_mid_spawn("spawned", target)
        self.assertEqual(before["children"], {})                      # 沒登記
        self.assertEqual(before["current"]["name"], request)
        # 沒有人會找它：它自己讀到 EOF、沒收到 go 就退 0，家一個檔都沒動
        self.assertEqual(wait_for(lambda: self.reaped().get(child)), {"pid": child, "exit": 0})
        self.assertEqual(sorted(os.listdir(cpu)), ["info.json", "inst.json"])
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [child] if before["children"] else [])
        self.assertEqual(self.state()["children"], {})
        self.assertIsNone(self.state()["current"])
        self.assert_interrupted(request)
        self.stop_daemon(gen2)

    def test_c2_killed_after_table_before_go_child_exits_untouched(self):
        target, cpu = self.cpu_target()
        request, child, before = self.crash_mid_spawn("before_go", target)
        self.assertEqual(before["children"]["child"]["pid"], child)   # 已登記、go 未送
        self.assertEqual(before["children"]["child"]["state"], "running")
        self.assertEqual(wait_for(lambda: self.reaped().get(child)), {"pid": child, "exit": 0})
        self.assertEqual(sorted(os.listdir(cpu)), ["info.json", "inst.json"])
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [child] if before["children"] else [])
        self.assertEqual(self.state()["children"], {})
        self.assert_interrupted(request)
        self.stop_daemon(gen2)

    def test_c2_killed_after_go_before_response_takeover_kills_before_publish(self):
        target, ready = self.kill_target()
        request, child, before = self.crash_mid_spawn("go_sent", target)
        wait_for(ready.exists)                                        # 孩子已開始做事
        self.assertEqual(before["children"]["child"]["pid"], child)
        time.sleep(.2)
        self.assertNotIn(child, self.reaped())                        # EOF 叫不停它
        gen2, g2 = self.daemon()
        reaped = self.published(gen2, g2, [child])
        # 新表公布之前，舊孩子已死透；TERM 被忽略，所以是階梯最後的 KILL
        self.assertEqual(reaped.get(child), {"pid": child, "signal": 9})
        self.assertEqual(self.state()["children"], {})
        self.assert_interrupted(request)
        self.stop_daemon(gen2)

    def test_c2_go_sent_real_cpu_stops_on_eof_and_respawn_gets_new_pid(self):
        target, cpu = self.cpu_target()
        request, child, _ = self.crash_mid_spawn("go_sent", target)
        wait_for(lambda: read_json(cpu / "state.json", {}).get("pid") == child)
        self.assertEqual(wait_for(lambda: self.reaped().get(child)), {"pid": child, "exit": 0})
        gen2, g2 = self.daemon()
        self.published(gen2, g2, [child])
        self.assert_interrupted(request)
        self.assertIsNone(read_json(cpu / "state.json")["current"])
        # 跨 daemon 重啟不冪等：表從空開始，重送 spawn 是拉新的一顆
        response = aos_client.call(self.home, "spawn", {"name": "child", "target": target},
                                   timeout_ms=6000, poll_ms=5)
        fresh = response["result"]["pid"]
        self.assertNotEqual(fresh, child)
        wait_for(lambda: read_json(cpu / "state.json", {}).get("pid") == fresh)
        self.stop_daemon(gen2, spawns=2)              # 新的那顆是 gen2 自己的孩子，由它收屍
        self.assertIsNone(read_json(cpu / "state.json")["current"])

    def test_c2_killed_after_response_before_unlink_keeps_response(self):
        target, ready = self.kill_target()
        request, child, _ = self.crash_mid_spawn("responded", target)
        wait_for(ready.exists)                        # 孩子已裝好忽略 TERM，死因才固定是 KILL
        written = (self.home / "responses" / request).read_bytes()
        self.assertEqual(json.loads(written)["result"], {"pid": child})
        self.assertTrue((self.home / "requests" / request).exists())
        gen2, g2 = self.daemon()
        reaped = self.published(gen2, g2, [child])
        self.assertEqual(reaped.get(child), {"pid": child, "signal": 9})
        self.assertEqual(self.state()["children"], {})
        # 對帳只刪原單、不改回音：回音裡的 pid 已經被新任砍掉（不收養）
        self.assertFalse((self.home / "requests" / request).exists())
        self.assertEqual((self.home / "responses" / request).read_bytes(), written)
        self.assertEqual(self.records("responses.jsonl"), [request])
        self.stop_daemon(gen2)

    # ---- C-3：接手中的 daemon 再被 KILL ----

    def crash_during_takeover(self, *gates):
        """第一任卡在 go 已送、回音未寫；之後每一任都在接手的 gates[i] 被 KILL。"""
        target, ready = self.kill_target()
        request, child, first = self.crash_mid_spawn("go_sent", target)
        wait_for(ready.exists)
        for gate in gates:
            gen, gate_dir = self.daemon([gate])
            self.assertEqual(self.reached(gate_dir, gate)["daemon"], gen)
            self.sigkill(gen)
            mid = self.state()
            # 死在接手途中：新 state 還沒公布，舊表（第一任的 pid、孩子、current）原封不動
            self.assertEqual(mid, first)
        return request, child

    def converge(self, request, child, interrupted_before):
        written = (self.home / "responses" / request).read_bytes() if interrupted_before else None
        last, gate_dir = self.daemon()
        reaped = self.published(last, gate_dir, [child])
        self.assertEqual(reaped.get(child), {"pid": child, "signal": 9})
        self.assertEqual(self.state()["children"], {})
        self.assertIsNone(self.state()["current"])
        self.assert_interrupted(request)
        if written is not None:                       # 回音恰好一份，不被重寫
            self.assertEqual((self.home / "responses" / request).read_bytes(), written)
        self.stop_daemon(last)

    def test_c3_killed_after_term_sent_old_child_still_alive(self):
        request, child = self.crash_during_takeover("prev_term")
        time.sleep(.2)
        self.assertNotIn(child, self.reaped())        # TERM 被忽略，孩子還活著
        self.assertFalse((self.home / "responses" / request).exists())
        self.converge(request, child, False)

    def test_c3_killed_twice_after_term_third_takeover_converges(self):
        request, child = self.crash_during_takeover("prev_term", "prev_term")
        self.assertNotIn(child, self.reaped())
        self.converge(request, child, False)

    def test_c3_killed_after_group_kill_sent(self):
        request, child = self.crash_during_takeover("prev_kill")
        self.assertEqual(wait_for(lambda: self.reaped().get(child)), {"pid": child, "signal": 9})
        self.assertFalse((self.home / "responses" / request).exists())
        self.converge(request, child, False)

    def test_c3_killed_after_old_children_gone_before_reconcile(self):
        request, child = self.crash_during_takeover("prev_done")
        self.assertEqual(self.reaped().get(child), {"pid": child, "signal": 9})
        self.assertTrue((self.home / "requests" / request).exists())
        self.assertFalse((self.home / "responses" / request).exists())
        self.converge(request, child, False)

    def test_c3_killed_after_interrupted_written_before_request_deleted(self):
        request, child = self.crash_during_takeover("reconcile_interrupted")
        self.assertTrue((self.home / "requests" / request).exists())
        self.assertEqual(read_json(self.home / "responses" / request)["error"]["data"]["code"], "Interrupted")
        self.converge(request, child, True)

    def test_c3_killed_after_reconcile_before_publish(self):
        request, child = self.crash_during_takeover("reconciled")
        self.assertFalse((self.home / "requests" / request).exists())
        self.converge(request, child, True)


if __name__ == "__main__":
    unittest.main()
