"""daemon 測試的控制協議孩子、輪詢與隔離崩潰接手 driver。"""
import json
from pathlib import Path
import time

# 每個孩子確實等待 go，只有收到後才留下 ready 記錄。模式故意不全遵守
# stop，用來測 daemon 必須處理的失敗邊界；正常模式也認 EOF。
CHILD = r'''
import json, os, signal, sys, time
mode, ready = sys.argv[1:3]
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        sys.exit(0)
    if json.loads(line).get('method') == 'go':
        break
if mode in ('kill', 'epipe'):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
def terminated(sig, frame):
    with open(ready + '.term', 'w') as f: f.write(str(time.monotonic()))
    sys.exit(0)
if mode == 'term':
    signal.signal(signal.SIGTERM, terminated)
if mode == 'epipe':
    os.close(0)
with open(ready, 'w') as f:
    json.dump({'pid': os.getpid(), 'pgid': os.getpgrp(), 'sid': os.getsid(0),
               'at': time.monotonic()}, f)
if mode.startswith('exit'):
    sys.exit(int(mode[4:]))
if mode in ('kill', 'epipe'):
    while True: time.sleep(.01)
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        sys.exit(0)
    if json.loads(line).get('method') == 'stop' and mode != 'term':
        sys.exit(0)
'''


def wait_for(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.005)
    raise AssertionError("等不到行程或檔案狀態")


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


# 只有這個隔離 driver 當 subreaper。真 daemon 崩潰之後它代替 init 收孤兒，
# 避免容器 PID 1 不收屍；不更動 unittest 主行程的收屍政策。
ORPHAN_DRIVER = r'''
import ctypes, json, os, signal, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import aos_client, aos_home
lib, cli, home, target, ready = sys.argv[1:]
home, ready = Path(home), Path(ready)
if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0):
    raise OSError(ctypes.get_errno(), 'prctl')
procs, children = [], set()
def state():
    try: return json.loads((home/'state.json').read_text())
    except FileNotFoundError: return {}
def reap():
    for pid in list(children):
        try: done, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError: continue
        if done: children.remove(pid)
def wait(predicate):
    until=time.monotonic()+8
    while time.monotonic()<until:
        reap()
        if predicate(): return
        time.sleep(.005)
    raise RuntimeError('isolated restart timed out')
def start():
    p=subprocess.Popen([sys.executable,cli,'--home',str(home)],stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    procs.append(p)
    return p
try:
    first=start()
    wait(lambda: state().get('pid')==first.pid)
    response=aos_client.call(home,'spawn',{'name':'old','target':target},timeout_ms=3000,poll_ms=5)
    child=response['result']['pid']
    children.add(child)
    wait(lambda: ready.exists())
    first.kill(); first.wait(timeout=3)
    second=start()
    wait(lambda: state().get('pid')==second.pid)
    assert not state()['children'], state()
    assert child not in children, 'old child not reaped before publishing new daemon state'
    aos_home.post_request(home,aos_client.new_name('stop'),{'jsonrpc':'2.0','method':'stop'})
    assert second.wait(timeout=4)==0
    print(json.dumps({'old_pid':child,'new_pid':second.pid,'children':state()['children']}))
finally:
    for p in procs:
        if p.poll() is None: p.kill()
        p.wait(timeout=3)
    for pid in children:
        try: os.killpg(pid,signal.SIGKILL)
        except ProcessLookupError: pass
    until=time.monotonic()+3
    while children and time.monotonic()<until:
        reap(); time.sleep(.005)
'''

# 僅測試 driver 注入時鐘；每圈完成後公布快照，測試才推下一個期限。
CLOCK_DRIVER = r'''
import json, sys, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import aos_daemon, aos_home
home, clock, snapshot, signals = map(Path, sys.argv[2:])
aos_daemon.time = SimpleNamespace(monotonic=lambda: json.loads(clock.read_text()),
                                 time=time.time, sleep=time.sleep)
step = aos_daemon.Daemon.step
send = aos_daemon._signal_pid
def signal_pid(pid, sig, group=False):
    with signals.open('a') as stream:
        stream.write(json.dumps([pid, int(sig), group, aos_daemon.time.monotonic()])+'\n')
    send(pid, sig, group)
aos_daemon._signal_pid = signal_pid
def observed_step(owner):
    now = aos_daemon.time.monotonic()
    result = step(owner)
    aos_home.write_json(snapshot, {'clock': now, 'stages': {name: [stage, None if deadline == float('inf') else deadline]
                                             for name, (stage, deadline) in owner.stages.items()},
                                  'restarts': owner.restarts, 'children': owner.children})
    return result
aos_daemon.Daemon.step = observed_step
sys.exit(aos_daemon.run(home))
'''
