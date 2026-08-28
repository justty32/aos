#!/usr/bin/env python3
"""重現 handoff_fs.cpp write_file_flags() 的原語：固定路徑 + O_TRUNC + 非排他。
   這正是 aggregate 寫 .aos/inst.json.temp 的方式。"""
import os, sys

PATH = sys.argv[1]

def writer(payload):
    fd = os.open(PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)
    off = 0
    while off < len(payload):
        off += os.write(fd, payload[off:off + 4096])
    os.fsync(fd)
    os.close(fd)

a = b"A" * 400000
b = b"B" * 100000
bad = 0
first = None
for trial in range(300):
    pids = []
    for payload in (a, b):
        pid = os.fork()
        if pid == 0:
            writer(payload)
            os._exit(0)
        pids.append(pid)
    for pid in pids:
        os.waitpid(pid, 0)
    got = open(PATH, "rb").read()
    if got != a and got != b:
        bad += 1
        if first is None:
            first = (trial, len(got), got.count(b"A"), got.count(b"B"), got.count(b"\x00"))
if first:
    print("  第 %d 次就壞了：長度=%d  A=%d B=%d NUL=%d" % first)
print("  300 次「兩行程並寫同一個 O_TRUNC 固定路徑」：%d 次產生混合／破損內容" % bad)
