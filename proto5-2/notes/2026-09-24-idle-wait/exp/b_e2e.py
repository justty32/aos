"""實驗 B：真 daemon＋真 kernel＋N 個 agent，3 顆 llm cpu 被「掛住不回」的假模型佔滿，量一段時間內的空轉。

- 假模型：本機 HTTP，收到就一直不回（模擬「模型很慢／只有 3 顆」）。不碰 LM Studio、不連外。
- 每個 agent：init、放一句輸入、start。約兩格後它的 think 單送進 kernel，之後就一直「在等」。
- 量 WINDOW 秒：kernel 走了幾格、派了幾次 agent 的 tick、回音裡有幾個 101、
  各行程（daemon、kernel cpu、default 池、llm 池）用掉的 CPU 秒數（/proc 的 utime+stime+cutime+cstime 差）、
  帳本大小、agent tick 一次在 cpu 上跑多久（kernel 回音裡沒有，改用 default 池 cutime ÷ 派工數估）。
- 最後把所有指到 SCRATCH 的行程 SIGKILL 掉（不 halt：llm 那三件永遠不會回）。

用法：python3 b_e2e.py SCRATCH LABEL N_AGENTS N_DEFAULT_CPUS [WINDOW_S] [TICK_MS] [INTERVAL_MS]
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLI = REPO / 'proto5' / 'cli'
PY = sys.executable
HZ = os.sysconf('SC_CLK_TCK')
HOLD = threading.Event()


class Hang(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        HOLD.wait(3600)

    def do_GET(self):
        raw = b'{"data":[{"id":"hang"}]}'
        self.send_response(200)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


def procs_under(root):
    """回 {pid: (cmdline, cpu 秒含已收的孩子)}，只算 cmdline 含 root 的行程，排除自己。"""
    out = {}
    for d in os.listdir('/proc'):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            cmd = open('/proc/%s/cmdline' % d, 'rb').read().replace(b'\0', b' ').decode(errors='replace')
            if root not in cmd:
                continue
            f = open('/proc/%s/stat' % d).read().rsplit(')', 1)[1].split()
            # stat 欄位（去掉 pid、comm 後從 0 數）：utime=11 stime=12 cutime=13 cstime=14
            out[int(d)] = (cmd, sum(int(x) for x in f[11:15]) / HZ)
        except (OSError, IndexError, ValueError):
            pass
    return out


def classify(cmd, kernel):
    # 審查必修 7：還活著、沒被收屍的孩子也要算（它收屍後會移進父行程的 cutime，兩次快照一致）。
    if 'aos-agent' in cmd:
        return 'default 池 cpu（含 agent tick）'
    if 'aos-kernel' in cmd:
        return 'kernel cpu（含每格 aos-kernel tick）'
    if 'aos-llm' in cmd:
        return 'llm 池 cpu'
    if 'aos-daemon' in cmd:
        return 'daemon'
    if 'aos-cpu' in cmd:
        home = cmd.split()[-1]
        name = Path(home).name
        if name == 'k':
            return 'kernel cpu（含每格 aos-kernel tick）'
        return 'llm 池 cpu' if name.startswith('llm') else 'default 池 cpu（含 agent tick）'
    return None


def cpu_by_class(root, kernel):
    total = {}
    for pid, (cmd, secs) in procs_under(root).items():
        c = classify(cmd, kernel)
        if c:
            total[c] = total.get(c, 0.0) + secs
    return total


def kernel_log_events(path, start_line):
    lines = path.read_text().splitlines() if path.exists() else []
    dispatch = responses = r101 = r0 = 0
    for line in lines[start_line:]:
        for ev in json.loads(line)['events']:
            if not ev.get('proc', '').startswith('agent-'):
                continue
            if ev['event'] == 'dispatch':
                dispatch += 1
            elif ev['event'] == 'response':
                responses += 1
                code = ev.get('response', {}).get('result', {}).get('code')
                r101 += code == 101
                r0 += code == 0
    return len(lines), dispatch, responses, r101, r0


def run(cmd, env, **kw):
    r = subprocess.run([PY, str(CLI / cmd[0]), *cmd[1:]], env=env, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise SystemExit('%s: %s %s' % (cmd, r.returncode, r.stderr))
    return r


def main():
    scratch, label, n, ncpu = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    window = float(sys.argv[5]) if len(sys.argv) > 5 else 30
    tick_ms = int(sys.argv[6]) if len(sys.argv) > 6 else 1000
    interval_ms = int(sys.argv[7]) if len(sys.argv) > 7 else 1000
    root = scratch / ('b-' + label)
    if root.exists():
        raise SystemExit('%s 已存在，換 LABEL' % root)
    root.mkdir(parents=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Hang)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    D, K = root / 'D', root / 'K'
    path = str(CLI) + os.pathsep + os.environ['PATH']
    env = dict(os.environ, PATH=path, AOS_DAEMON_HOME=str(D), AOS_KERNEL_HOME=str(K), PYTHONDONTWRITEBYTECODE='1')
    (root / 'llm.json').write_text(json.dumps({'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
        'default': {'endpoint': 'http://127.0.0.1:%d/v1' % server.server_port, 'model': 'hang',
                    'timeout_ms': 3600000}}}))
    cpus = {str(i): {} for i in range(ncpu)}
    for i in range(3):
        cpus['llm%d' % i] = {'pool': 'llm', 'envs': {'AOS_LLM_CONFIG': str(root / 'llm.json')}}
    (root / 'kernel.json').write_text(json.dumps({'cpus': cpus, 'tick_ms': tick_ms, 'interval_ms': interval_ms}))
    D.mkdir()
    log = open(root / 'daemon.log', 'ab')
    daemon = subprocess.Popen([PY, str(CLI / 'aos-daemon'), 'boot', '--target', str(D)], env=env,
                              stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    try:
        for _ in range(200):
            if (D / 'state.json').exists():
                break
            time.sleep(.05)
        run(['aos-kernel', 'init', '--config', str(root / 'kernel.json')], env)
        info = json.loads((K / 'info.json').read_text())
        info.update(tick_ms=tick_ms, interval_ms=interval_ms)
        (K / 'info.json').write_text(json.dumps(info))
        t = time.time()
        run(['aos-kernel', 'boot', '--wait-ms', '120000'], env, timeout=300)
        boot_s = time.time() - t

        def agent(i):
            home = root / 'agents' / ('a%04d' % i)
            run(['aos-agent', 'init', '--target', str(home)], env)
            # 審查必修 8：init 預設 llm.timeout_ms 125000，窗口內會有人逾時結清；拉到一小時，並照參數設 interval。
            info = json.loads((home / 'info.json').read_text())
            info['llm']['timeout_ms'] = 3600000
            info['tick']['interval_ms'] = interval_ms
            (home / 'info.json').write_text(json.dumps(info, ensure_ascii=False))
            (home / 'input').mkdir(exist_ok=True)
            (home / 'input' / 'hello.json').write_text(json.dumps('你好'))
            run(['aos-agent', 'start', '--target', str(home)], env, timeout=120)
        t = time.time()
        (root / 'agents').mkdir()
        with ThreadPoolExecutor(32) as pool:
            list(pool.map(agent, range(n)))
        start_s = time.time() - t
        # 暖機：等到在等的 agent 夠多（think 已送出）。
        deadline = time.time() + 120
        while time.time() < deadline:
            waiting = 0
            for home in (root / 'agents').iterdir():
                try:
                    st = json.loads((home / 'state.json').read_text())
                except (OSError, ValueError):
                    continue
                b = st.get('batch')
                waiting += bool(b and b.get('sent'))
            if waiting >= n:
                time.sleep(5)  # 讓剛送出的那格回音也收掉，窗口內只剩純等
                break
            time.sleep(1)
        else:
            raise SystemExit('暖機 120 秒內只有 %d／%d 個 agent 送出 think，不量' % (waiting, n))
        state0 = json.loads((K / 'state.json').read_text())
        lines0, *_ = kernel_log_events(K / 'kernel.log', 0)
        cpu0 = cpu_by_class(str(root), K)
        t0 = time.time()
        time.sleep(window)
        t1 = time.time()
        cpu1 = cpu_by_class(str(root), K)
        state1 = json.loads((K / 'state.json').read_text())
        llm0 = {c: v['proc'] for c, v in state0['cpus'].items() if c.startswith('llm')}
        llm1 = {c: v['proc'] for c, v in state1['cpus'].items() if c.startswith('llm')}
        if llm0 != llm1 or None in llm1.values():
            raise SystemExit('窗口內 llm cpu 換了工作（%s → %s），不是純等' % (llm0, llm1))
        _, dispatch, responses, r101, r0 = kernel_log_events(K / 'kernel.log', lines0)
        dt = t1 - t0
        seqs = state1['last_seq'] - state0['last_seq']
        cpu = {k: round(cpu1.get(k, 0) - cpu0.get(k, 0), 2) for k in cpu1}
        queue = state1['queue']
        report = {
            'label': label, 'agents': n, 'default_cpus': ncpu, 'llm_cpus': 3, 'tick_ms': tick_ms,
            'interval_ms': interval_ms, 'window_s': round(dt, 1), 'boot_s': round(boot_s, 1),
            'start_all_s': round(start_s, 1), 'waiting_agents_at_start': waiting,
            'kernel_ticks': seqs, 'kernel_period_ms': round(dt * 1000 / max(seqs, 1)),
            'agent_tick_dispatches': dispatch, 'agent_tick_responses': responses,
            'responses_101': r101, 'responses_0': r0,
            'agent_ticks_per_s': round(responses / dt, 1),
            'per_agent_interval_s': round(n * dt / max(responses, 1), 2),
            'cpu_seconds': cpu, 'cpu_cores_busy_total': round(sum(cpu.values()) / dt, 2),
            'cpu_ms_per_agent_tick_on_default_pool': round(
                cpu.get('default 池 cpu（含 agent tick）', 0) * 1000 / max(responses, 1), 1),
            'kernel_cpu_ms_per_tick': round(cpu.get('kernel cpu（含每格 aos-kernel tick）', 0) * 1000 / max(seqs, 1), 1),
            'ledger_bytes': (K / 'state.json').stat().st_size,
            'queue_len': len(queue),
            'queue_llm_once': sum(1 for q in queue if state1['procs'][q]['once']),
            'kernel_log_bytes': (K / 'kernel.log').stat().st_size if (K / 'kernel.log').exists() else 0,
        }
        print(json.dumps(report, ensure_ascii=False, indent=1))
    finally:
        HOLD.set()
        for pid in procs_under(str(root)):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            os.killpg(daemon.pid, signal.SIGKILL)
        except OSError:
            pass
        daemon.wait()
        server.shutdown()


if __name__ == '__main__':
    main()
