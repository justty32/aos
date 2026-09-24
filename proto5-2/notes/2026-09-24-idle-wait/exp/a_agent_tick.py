"""實驗 A：一個「在等模型」的 agent，被派一格 `aos-agent tick` 要花多少。

不起 daemon／kernel：直接照 kernel 派的那條命令列（tick.json 的 argv）跑 `aos-agent tick --target 家`，
K 只是一個有 requests/、responses/ 的空資料夾——think 單已經「交出去、還在 kernel 裡」，所以兩個檔都不在 → 退 101。
對照組：idle 沒輸入（J 隊講的那種）、以及 `python3 -c pass`、只 import aos_agent。

用法：python3 a_agent_tick.py SCRATCH [N]
"""
import json
import os
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLI = REPO / 'proto5' / 'cli'
PY = sys.executable


def run(argv, env):
    t = time.perf_counter()
    r = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    return time.perf_counter() - t, r


def bench(label, argv, env, n, expect=None):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    walls = []
    for _ in range(n):
        wall, r = run(argv, env)
        if expect is not None and r.returncode != expect:
            raise SystemExit('%s: exit %s %s' % (label, r.returncode, r.stderr))
        walls.append(wall * 1000)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = ((after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)) * 1000 / n
    walls.sort()
    return {'label': label, 'n': n, 'wall_ms_median': round(statistics.median(walls), 1),
            'wall_ms_p90': round(walls[int(n * .9) - 1], 1), 'cpu_ms_mean': round(cpu, 1),
            'maxrss_mb': round(after.ru_maxrss / 1024, 1)}


def main():
    scratch = Path(sys.argv[1]) / 'a'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    kernel = scratch / 'K'
    for d in ('requests', 'responses'):
        (kernel / d).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, AOS_KERNEL_HOME=str(kernel), PATH=str(CLI) + os.pathsep + os.environ['PATH'],
               PYTHONDONTWRITEBYTECODE='1')
    homes = {}
    for name in ('wait', 'idle'):
        home = scratch / name
        if not home.exists():
            subprocess.run([PY, str(CLI / 'aos-agent'), 'init', '--target', str(home)], env=env,
                           check=True, capture_output=True)
        homes[name] = home
    # 在等模型：think 批已送出（sent=true），單名 aw-wait-1 在 K 裡既沒原單也沒回音＝還在 kernel 裡。
    # 記憶放 20 則，像一個聊過幾輪的 agent（等的時候 tick 仍會讀驗整份記憶）。
    hist = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': '第 %d 則，' % i + '內容' * 200}
            for i in range(20)]
    for name, home in homes.items():
        (home / 'prompts').mkdir(exist_ok=True)
        (home / 'prompts' / 'history.json').write_text(json.dumps(hist, ensure_ascii=False))
    (homes['wait'] / 'state.json').write_text(json.dumps({
        'state': 'think', 'errors': 0, 'input': 'input.json', 'waits': [], 'intake': None,
        'consuming': [], 'sweep': [],
        'batch': {'kind': 'think', 'kernel': str(kernel), 'base_len': 20, 'sent': True,
                  'calls': [{'name': 'aw-wait-1', 'done': None, 'acked': False}]}}))
    (homes['idle'] / 'state.json').write_text(json.dumps({'state': 'idle'}))

    results = [
        bench('python3 -c pass', [PY, '-c', 'pass'], env, n, 0),
        bench('只 import aos_agent', [PY, '-c', 'import sys; sys.path.insert(0, %r); import aos_agent'
                                     % str(REPO / 'proto5' / 'lib')], env, n, 0),
        bench('tick：在等模型（think 批在途）', [PY, str(CLI / 'aos-agent'), 'tick', '--target',
                                         str(homes['wait'])], env, n, 101),
        bench('tick：idle 沒輸入', [PY, str(CLI / 'aos-agent'), 'tick', '--target', str(homes['idle'])],
              env, n, 101),
    ]
    io = {}
    for name, home in homes.items():
        out = scratch / ('io-%s.json' % name)
        r = subprocess.run([PY, str(HERE / 'count_io.py'), str(out), '--', str(CLI / 'aos-agent'), 'tick',
                            '--target', str(home)], env=env, capture_output=True, text=True)
        data = json.loads(out.read_text())
        io[name] = {'exit': r.returncode, 'counts': data['counts'],
                    'data_paths': {k: sorted({p.replace(str(scratch), '$S') for p in v})
                                   for k, v in data['data_paths'].items()}}
    report = {'n': n, 'python': sys.version.split()[0], 'results': results, 'io': io}
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
