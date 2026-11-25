#!/usr/bin/env python3
# 補充量測（spike）：threads=1/2/4 時 cat status、單一 pread（一個 READ 來回）、stat 各要多久。
import subprocess, sys, os, time

H=os.path.join(os.path.dirname(os.path.abspath(__file__)), "toyproc.py")
for th in ["1","2","4"]:
    p=subprocess.Popen([sys.executable,H,"--name","b"+th,"--threads",th],stdout=subprocess.PIPE,text=True,cwd="/")
    pid=int(p.stdout.readline().split()[1]); path="/proc/%d/cwd/status"%pid
    for _ in range(50): open(path).read()
    ts=[]
    for _ in range(1000):
        t=time.perf_counter(); open(path).read(); ts.append(time.perf_counter()-t)
    ts.sort()
    fd=os.open(path,os.O_RDONLY); t=time.perf_counter()
    for _ in range(1000): os.pread(fd,4096,0)
    pr=(time.perf_counter()-t)/1000; os.close(fd)
    st=os.stat(path); t=time.perf_counter()
    for _ in range(1000): os.stat(path)
    sr=(time.perf_counter()-t)/1000
    print("threads=%s open+read+close median %.0f µs p90 %.0f µs | 單一 pread（一個 READ 來回）%.0f µs | stat %.0f µs"%(th,ts[500]*1e6,ts[900]*1e6,pr*1e6,sr*1e6))
    open("/proc/%d/cwd/ctl"%pid,"w").write("stop\n"); p.wait(5)
