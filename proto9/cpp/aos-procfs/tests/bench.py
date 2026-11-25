#!/usr/bin/env python3
# bench.py：量 C++ 版 aos-procfs-demo 與 Python 玩具 toyproc 的延遲（讀 status、寫 ctl 各幾百次的中位數）與記憶體。
"""用法：python3 tests/bench.py [次數，預設 500]"""
import errno, os, select, statistics, subprocess, sys, time
import common
from common import start_demo, cleanup, leftovers, SCRATCH, _procs

EXP = os.path.normpath(os.path.join(common.HERE, "..", "..", "..", "experiments", "fuse-proc-1125"))


def start_toy():
    # 玩具的掛載點寫死在它自己的 scratch；改它的 SCRATCH 讓掛載落在這一夾，收尾才收得到
    code = ("import sys; sys.path.insert(0, %r); import toyproc; toyproc.SCRATCH = %r; "
            "sys.argv = ['toyproc', '--name', 'benchtoy', '--threads', '1']; toyproc.main()" % (EXP, SCRATCH))
    p = subprocess.Popen([sys.executable, "-B", "-c", code], stdout=subprocess.PIPE, cwd="/")
    _procs.append(p)
    r, _, _ = select.select([p.stdout], [], [], 10)
    line = p.stdout.readline().decode().split()
    return p, int(line[1]), "/proc/%s/cwd" % line[1]


def bench_read(path, n):
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        fd = os.open(path, os.O_RDONLY)
        while os.read(fd, 65536):
            pass
        os.close(fd)
        ts.append(time.perf_counter() - t)
    return statistics.median(ts) * 1e6


def bench_write(path, n):
    ts = []
    while len(ts) < n:
        t = time.perf_counter()
        try:
            fd = os.open(path, os.O_WRONLY)
            try:
                os.write(fd, b"resume\n")
            finally:
                os.close(fd)
        except OSError as e:
            if e.errno != errno.EBUSY:
                raise
            time.sleep(0.0005)   # 上一道還鎖著：等一下重來，這次不算
            continue
        ts.append(time.perf_counter() - t)
    return statistics.median(ts) * 1e6


def rss_kb(pid):
    for line in open("/proc/%d/status" % pid):
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    plain = os.path.join(SCRATCH, "plain.txt")
    with open(plain, "w") as f:
        f.write("aos_name: x\n" * 8)
    try:
        p, pid, root, _ = start_demo("bench")
        toy, tpid, troot = start_toy()
        print("n=%d (median, microseconds)" % n)
        print("plain file read          %8.1f" % bench_read(plain, n))
        print("C++  read status         %8.1f" % bench_read(root + "/status", n))
        print("toy  read status         %8.1f" % bench_read(troot + "/status", n))
        print("C++  write ctl           %8.1f" % bench_write(root + "/ctl", n))
        print("toy  write ctl           %8.1f" % bench_write(troot + "/ctl", n))
        print("RSS kB: C++ %d, toy %d" % (rss_kb(pid), rss_kb(tpid)))
        for r, q in ((root, p), (troot, toy)):
            fd = os.open(r + "/ctl", os.O_WRONLY)
            os.write(fd, b"stop\n")
            os.close(fd)
            q.wait(5)
    finally:
        os.unlink(plain)
        cleanup()
    print("leftovers:", leftovers())


if __name__ == "__main__":
    main()
