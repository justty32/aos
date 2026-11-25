#!/usr/bin/env python3
# 玩具 daemon（spike）：本身是一隻 toyproc，多一個 procs/ 夾（別名 proc），裡面每項是指到 /proc/<kid PID>/cwd 的 FUSE symlink。
"""
用法：python3 toydaemon.py --name d1 --kids kid1,kid2,kid3 [toyproc 的其他選項]
起好後印 "READY <pid> <mountpoint>"，另外每隻 kid 印一行 "KID <名> <pid>"。
"""
import argparse, os, subprocess, sys, threading, time

from toyproc import ToyProc, common_args, run

HERE = os.path.dirname(os.path.abspath(__file__))


class ToyDaemon(ToyProc):
    PROCS, PROC_ALIAS = 6, 7
    KIND = "toydaemon"

    def __init__(self, name, kids, kid_args, **kw):
        super().__init__(name, **kw)
        self.kid_names, self.kid_args = kids, kid_args
        self.kids = {}            # 名 -> (pid, nodeid, Popen)

    def spawn_kids(self):
        for i, k in enumerate(self.kid_names):
            p = subprocess.Popen([sys.executable, os.path.join(HERE, "toyproc.py"), "--name", k] + self.kid_args,
                                 stdout=subprocess.PIPE, text=True, cwd="/")   # cwd="/"：別讓 kid 繼承站在 daemon 掛載點裡
            line = p.stdout.readline().split()
            p.mnt = line[2]
            with self.lock:
                self.kids[k] = (int(line[1]), 100 + i, p)
            threading.Thread(target=self.reap, args=(k, p), daemon=True).start()
            print("KID %s %s" % (k, line[1]), flush=True)

    def reap(self, k, p):
        p.wait()
        with self.lock:
            self.kids.pop(k, None)    # 收屍後 procs/<名> 就不見了
        # kid 被 kill -9 時它的掛載會留下（Transport endpoint is not connected）；
        # 這台 fusermount3 的 auto_unmount 實測收不掉，所以由 daemon 收屍時順手卸。
        if any(l.split()[1] == p.mnt for l in open("/proc/mounts")):
            r = subprocess.run(["fusermount3", "-u", "-z", p.mnt], capture_output=True, text=True)
            print("REAPED %s unmount rc=%d %s" % (k, r.returncode, r.stderr.strip()), flush=True)
        try:
            os.rmdir(p.mnt)
        except OSError:
            pass

    def node(self, nid):
        if nid == self.PROCS:
            return ("dir", 0o555, None)
        if nid == self.PROC_ALIAS:
            return ("link", 0o777, None)
        with self.lock:
            for k, (pid, kn, _p) in self.kids.items():
                if kn == nid:
                    return ("link", 0o777, None)
        return super().node(nid)

    def children(self, nid):
        if nid == self.ROOT:
            return super().children(nid) + [("procs", self.PROCS), ("proc", self.PROC_ALIAS)]
        if nid == self.PROCS:
            with self.lock:
                return [(k, kn) for k, (pid, kn, _p) in self.kids.items()]
        return []

    def readlink(self, nid):
        if nid == self.PROC_ALIAS:
            return b"procs"
        with self.lock:
            for k, (pid, kn, _p) in self.kids.items():
                if kn == nid:
                    return ("/proc/%d/cwd" % pid).encode()
        return b""

    def status_lines(self):
        lines = super().status_lines()
        with self.lock:
            lines.insert(3, "procs: %s" % " ".join("%s=%d" % (k, v[0]) for k, v in self.kids.items()))
        return lines

    def before_stop(self):
        with self.lock:
            kids = list(self.kids.items())
        for k, (pid, kn, p) in kids:
            try:
                with open("/proc/%d/cwd/ctl" % pid, "w") as f:
                    f.write("stop\n")
            except OSError:
                p.terminate()
        for k, (pid, kn, p) in kids:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()


def main():
    ap = argparse.ArgumentParser()
    common_args(ap)
    ap.add_argument("--kids", default="kid1,kid2")
    ap.add_argument("--kid-args", default="", help="傳給每隻 kid 的選項（空白分隔）")
    a = ap.parse_args()
    d = ToyDaemon(a.name, [k for k in a.kids.split(",") if k], a.kid_args.split(), busy_check=a.busy_check,
                  threads=a.threads, auto_unmount=a.auto_unmount, size_mode=a.size, gen_mode=a.gen,
                  trace=os.environ.get("TOY_TRACE"))
    d.spawn_kids()
    run(d)


if __name__ == "__main__":
    main()
