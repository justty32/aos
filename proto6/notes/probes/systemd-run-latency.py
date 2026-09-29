#!/usr/bin/env python3
"""量開短命程序的成本：直接 fork/exec vs systemd-run --user 各種選項 vs git commit。
用法：python3 proto6/notes/probes/systemd-run-latency.py [N=200] [--md]
只用 systemd-run --user，不需要 root。暫存放 $TMPDIR 下自建資料夾，跑完清掉。"""
import os, subprocess, sys, time, statistics, tempfile, shutil, platform, uuid
from concurrent.futures import ThreadPoolExecutor

N = int(next((a for a in sys.argv[1:] if a.isdigit()), 200))
TAG = "aosprobe" + uuid.uuid4().hex[:6]
TRUE = ["/bin/true"]
PY = ["python3", "-c", "pass"]
SR = ["systemd-run", "--user", "--quiet"]
LIM = ["-p", "MemoryMax=512M", "-p", "CPUQuota=50%", "-p", "TasksMax=64"]

def run(cmd, cwd=None):
    t = time.perf_counter()
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, cwd=cwd)
    dt = (time.perf_counter() - t) * 1000
    if r.returncode != 0:
        raise SystemExit(f"失敗 {cmd}: {r.stderr.decode()[:300]}")
    return dt

def stats(xs):
    xs = sorted(xs)
    return (statistics.median(xs), xs[min(len(xs) - 1, int(len(xs) * 0.9))], xs[-1])

rows = []
def bench(name, mk, n=N):
    xs = [run(mk(i)) for i in range(n)]
    m, p, mx = stats(xs)
    rows.append((name, n, m, p, mx))
    print(f"{name:52s} n={n:4d} 中位 {m:8.1f}  p90 {p:8.1f}  最大 {mx:8.1f} ms", flush=True)

def uname(i): return ["--unit", f"{TAG}-{i}-{uuid.uuid4().hex[:4]}"]

for label, prog in (("/bin/true", TRUE), ("python3 -c pass", PY)):
    bench(f"1 直接 fork/exec {label}", lambda i, p=prog: p)
    bench(f"2 run --wait {label}", lambda i, p=prog: SR + ["--wait", "--collect"] + p)
    bench(f"3 run --scope {label}", lambda i, p=prog: SR + ["--scope"] + p)
    bench(f"4 run --wait +MemoryMax/CPUQuota/TasksMax {label}",
          lambda i, p=prog: SR + ["--wait", "--collect"] + LIM + p)
    bench(f"5 run --wait +KillMode=control-group,--collect {label}",
          lambda i, p=prog: SR + ["--wait", "--collect", "-p", "KillMode=control-group"] + p)
    bench(f"5b run --wait 不加 --collect {label}",
          lambda i, p=prog: SR + ["--wait"] + p)
    bench(f"6 run --pipe --wait {label}",
          lambda i, p=prog: SR + ["--pipe", "--wait", "--collect"] + p)

# 7 並發 10
def conc(prog, total=max(100, N)):
    t = time.perf_counter()
    with ThreadPoolExecutor(10) as ex:
        list(ex.map(lambda i: run(SR + ["--wait", "--collect"] + prog), range(total)))
    return total / (time.perf_counter() - t)
for label, prog in (("/bin/true", TRUE), ("python3 -c pass", PY)):
    tp = conc(prog)
    rows.append((f"7 並發10 run --wait {label}（每秒開幾個）", max(100, N), tp, 0, 0))
    print(f"7 並發10 {label}: {tp:.1f} 個/秒", flush=True)
t0 = time.perf_counter()
with ThreadPoolExecutor(10) as ex:
    list(ex.map(lambda i: run(TRUE), range(200)))
tp0 = 200 / (time.perf_counter() - t0)
print(f"對照 並發10 直接 fork/exec /bin/true: {tp0:.1f} 個/秒")
rows.append(("7 並發10 直接 fork/exec /bin/true（每秒開幾個）", 200, tp0, 0, 0))

def sh_count(d): return subprocess.run(['git','-C',d,'rev-list','--count','HEAD'],capture_output=True,text=True).stdout.strip()
# 8 git commit
d = tempfile.mkdtemp(prefix="aosprobe-git-")
try:
    g = lambda *a: ["git", "-c", "user.name=p", "-c", "user.email=p@x", "-c", "commit.gpgsign=false", *a]
    run(g("init", "-q", d)); open(f"{d}/big.txt", "w").write("x\n" * 1000)
    run(g("add", "-A"), cwd=d); run(g("commit", "-q", "-m", "init"), cwd=d)
    xs = []
    for i in range(N):
        open(f"{d}/f{i % 20}.txt", "a").write(f"line {i}\n")
        t = time.perf_counter()
        run(g("add", "-A"), cwd=d); run(g("commit", "-q", "-m", f"c{i}"), cwd=d)
        xs.append((time.perf_counter() - t) * 1000)
    print("  (驗證 commit 數:", sh_count(d), ")")
    m, p, mx = stats(xs); rows.append(("8 git add -A + commit（小變動）", N, m, p, mx))
    print(f"8 git add+commit n={N} 中位 {m:.1f} p90 {p:.1f} 最大 {mx:.1f} ms")
finally:
    shutil.rmtree(d, ignore_errors=True)

def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
print("\n## 機器")
print("CPU:", sh("lscpu | grep 'Model name' | sed 's/.*: *//'"), "/ 核心數", os.cpu_count())
print("systemd:", sh("systemctl --version | head -1"), "/ kernel", platform.release())
print("\n| 項目 | N | 中位 ms | p90 ms | 最大 ms |\n|---|---|---|---|---|")
for n, c, m, p, mx in rows:
    print(f"| {n} | {c} | {m:.1f} | {p:.1f} | {mx:.1f} |" if p else f"| {n} | {c} | {m:.1f} | | |")
# 清殘留（只清自己的）
subprocess.run(f"systemctl --user reset-failed '{TAG}*' 2>/dev/null", shell=True)
