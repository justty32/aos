#!/usr/bin/env python3
"""量 tick 每個任務跑完後「確認沒留子程序」的成本：A 共用葉子 vs B 每任務一層。

跑法：python3 proto6/notes/probes/per-task-cgroup-cost.py [次數，預設 200]
會自己用 systemd-run --user --scope -p Delegate=yes 重開一次拿委派 cgroup。
"""
import os, statistics, subprocess, sys, time

N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 200
TRUE = '/bin/true'


def reexec():
    if os.environ.get('PROBE_IN_SCOPE'):
        return
    env = dict(os.environ, PROBE_IN_SCOPE='1')
    os.execvpe('systemd-run', ['systemd-run', '--user', '--scope', '--quiet', '-p', 'Delegate=yes',
                               sys.executable, os.path.abspath(__file__), *sys.argv[1:]], env)


def own_cgroup():
    line = open('/proc/self/cgroup').read().strip().splitlines()[-1]
    return '/sys/fs/cgroup' + line.split('::', 1)[1]


def write(path, text):
    with open(path, 'w') as f:
        f.write(text)


def spawn(argv, cgroup_procs=None):
    """fork；子程序若給了 cgroup_procs 就先把自己搬進去再 exec。"""
    pid = os.fork()
    if pid == 0:
        try:
            if cgroup_procs:
                write(cgroup_procs, '0')
            os.execv(argv[0], argv)
        finally:
            os._exit(127)
    return pid


def procs(path):
    return [int(x) for x in open(path + '/cgroup.procs').read().split()]


def stats(name, xs):
    xs = sorted(xs)
    med = statistics.median(xs)
    p95 = xs[int(len(xs) * 0.95) - 1]
    print('%-28s 中位 %8.3f ms  p95 %8.3f ms  最大 %8.3f ms' % (name, med * 1e3, p95 * 1e3, xs[-1] * 1e3))
    return med, p95


def main():
    reexec()
    scope = own_cgroup()
    node = scope + '/node'
    tick = node + '/tick'
    os.mkdir(node)
    os.mkdir(tick)
    write(tick + '/cgroup.procs', '0')       # 先搬進子層 leaf，node 才能有子層
    me = os.getpid()
    print('cgroup:', tick, ' N =', N)

    base, a, b, b_split = [], [], [], []
    for _ in range(20):                       # 暖機
        os.waitpid(spawn([TRUE]), 0)
    for i in range(N):
        t0 = time.perf_counter()
        os.waitpid(spawn([TRUE]), 0)
        base.append(time.perf_counter() - t0)

        # A：共用葉子，跑完讀 cgroup.procs，除了自己有剩就 kill
        t0 = time.perf_counter()
        pid = spawn([TRUE])
        os.waitpid(pid, 0)
        left = [p for p in procs(tick) if p != me]
        for p in left:
            os.kill(p, 9)
        a.append(time.perf_counter() - t0)
        assert not left

        # B：每任務一層
        d = '%s/task-%d' % (node, i)
        t0 = time.perf_counter()
        os.mkdir(d)
        t1 = time.perf_counter()
        pid = spawn([TRUE], d + '/cgroup.procs')
        os.waitpid(pid, 0)
        t2 = time.perf_counter()
        populated = 'populated 1' in open(d + '/cgroup.events').read()
        if populated:
            write(d + '/cgroup.kill', '1')
        os.rmdir(d)
        t3 = time.perf_counter()
        b.append(t3 - t0)
        b_split.append((t1 - t0, t3 - t2))
        assert not populated

    print()
    mb, _ = stats('基準 fork+exec true+wait', base)
    ma, pa = stats('A 共用（含 fork+exec）', a)
    mbb, pb = stats('B 每任務（含 fork+exec）', b)
    stats('  B 的 mkdir', [x[0] for x in b_split])
    stats('  B 的 events+rmdir', [x[1] for x in b_split])
    print('\n每任務額外（扣掉基準中位數）：A %.3f ms，B %.3f ms' % ((ma - mb) * 1e3, (mbb - mb) * 1e3))

    # 定性示範：任務 double-fork 留下一個 sleep
    print('\n-- 留子程序示範 --')
    d = node + '/task-leak'
    os.mkdir(d)
    pid = spawn(['/bin/sh', '-c', '(sleep 30 &) ; exit 0'], d + '/cgroup.procs')
    os.waitpid(pid, 0)
    time.sleep(0.05)
    ev = open(d + '/cgroup.events').read().split()
    print('B 任務結束後 events:', ev, ' procs:', procs(d))
    t0 = time.perf_counter()
    write(d + '/cgroup.kill', '1')
    while 'populated 1' in open(d + '/cgroup.events').read():
        time.sleep(0.0005)
    os.rmdir(d)
    print('B kill 到 rmdir 成功 %.3f ms' % ((time.perf_counter() - t0) * 1e3))
    pid = spawn(['/bin/sh', '-c', '(sleep 30 &) ; exit 0'], tick + '/cgroup.procs')
    os.waitpid(pid, 0)
    time.sleep(0.05)
    left = [p for p in procs(tick) if p != me]
    print('A 任務結束後 tick 葉子裡除了自己還有:', left)
    for p in left:
        os.kill(p, 9)
    time.sleep(0.05)
    os.waitpid(-1, os.WNOHANG) if False else None


main()
