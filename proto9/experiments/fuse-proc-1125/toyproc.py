#!/usr/bin/env python3
# 玩具 aos proc（spike）：純標準庫自己講 FUSE 核心協議，把自己的目錄（status／ctl／settings／attrs）掛出來並 chdir 進去。
"""
用法：python3 toyproc.py --name kid1 [--threads 2] [--size zero-direct|zero-cache|real]
                         [--gen open|read] [--busy-check open|write|both] [--auto-unmount]
起好後在 stdout 印一行 "READY <pid> <mountpoint>"。
環境變數 TOY_TRACE=<檔> 會把每個收到的 FUSE 操作記一行；TOY_STATUS_PAD=N 讓 status 多 N 行（測讀到一半內容變）。
"""
import argparse, errno, os, signal, socket, struct, subprocess, sys, threading, time

SCRATCH = os.path.expanduser("~/.aos/scratch/proto9-fuse-1125")

# ---- 協議常數（照 /usr/include/linux/fuse.h，7.39） ----
OP = dict(LOOKUP=1, FORGET=2, GETATTR=3, SETATTR=4, READLINK=5, OPEN=14, READ=15, WRITE=16,
          STATFS=17, RELEASE=18, FSYNC=20, GETXATTR=22, LISTXATTR=23, FLUSH=25, INIT=26,
          OPENDIR=27, READDIR=28, RELEASEDIR=29, ACCESS=34, CREATE=35, INTERRUPT=36,
          DESTROY=38, IOCTL=39, POLL=40, BATCH_FORGET=42, READDIRPLUS=44, LSEEK=46, STATX=52)
OPNAME = {v: k for k, v in OP.items()}
NO_REPLY = {OP["FORGET"], OP["BATCH_FORGET"], OP["INTERRUPT"]}
IN_HDR = struct.Struct("<IIQQIIIHH")          # fuse_in_header 40B
OUT_HDR = struct.Struct("<IiQ")               # fuse_out_header 16B
ATTR = struct.Struct("<QQQQQQIIIIIIIIII")     # fuse_attr 88B
FOPEN_DIRECT_IO = 1 << 0
FATTR_SIZE = 1 << 3
DT_DIR, DT_REG, DT_LNK = 4, 8, 10
S_IFDIR, S_IFREG, S_IFLNK = 0o040000, 0o100000, 0o120000
O_ACCMODE = 3
BUFSIZE = 1 << 20 | 4096
MAX_WRITE = 1 << 17


def fuse_mount(mnt, opts, auto_unmount):
    """叫 setuid 的 fusermount3 掛；它從 _FUSE_COMMFD 那條 socketpair 用 SCM_RIGHTS 送回 /dev/fuse 的 fd。"""
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    if auto_unmount:
        opts += ",auto_unmount"
    env = dict(os.environ, _FUSE_COMMFD=str(b.fileno()))
    p = subprocess.Popen(["fusermount3", "-o", opts, "--", mnt], env=env,
                         pass_fds=[b.fileno()], cwd="/")
    b.close()
    msg, fds, _flags, _addr = socket.recv_fds(a, 1, 1)
    if not fds:
        p.wait()
        raise RuntimeError("fusermount3 沒送回 fd（退出碼 %s）" % p.returncode)
    fd = fds[0]
    os.set_inheritable(fd, False)              # 坑：收到的 fd 預設會被子行程繼承
    if not auto_unmount:
        p.wait()
        a.close()
        return fd, None, None
    return fd, a, p                            # auto_unmount：fusermount3 留著盯這條 socket，斷了就幫忙卸


class FuseServer:
    """最小的 FUSE 伺服器；子類別提供 node 表。nodeid 1 是根。"""

    def __init__(self, mnt, fsname, threads=2, auto_unmount=False, size_mode="zero-direct",
                 gen_mode="open", trace=None):
        self.mnt, self.fsname, self.nthreads = mnt, fsname, threads
        self.auto_unmount, self.size_mode, self.gen_mode = auto_unmount, size_mode, gen_mode
        self.trace = open(trace, "a", buffering=1) if trace else None
        self.lock = threading.RLock()
        self.fh_next, self.fh_data = 1, {}
        self.uid, self.gid = os.getuid(), os.getgid()
        self.stopping = threading.Event()
        self.threads = []

    # --- 子類別要給的 ---
    def node(self, nid):            # -> (kind, mode, extra) 或 None；kind in dir/file/link
        raise NotImplementedError

    def children(self, nid):        # -> [(name, nid)]
        raise NotImplementedError

    def content(self, nid):         # 只讀檔當場產生的內容 bytes
        return b""

    def readlink(self, nid):
        return b""

    def open_check(self, nid, flags):   # 回 0 或 errno
        return 0

    def write(self, nid, data):     # 回寫進的長度或 -errno
        return -errno.EACCES

    # --- 協議 ---
    def mount(self):
        os.makedirs(self.mnt, exist_ok=True)
        opts = "fsname=%s,subtype=aosproc,default_permissions" % self.fsname
        self.fd, self.comm, self.helper = fuse_mount(self.mnt, opts, self.auto_unmount)
        for i in range(self.nthreads):
            t = threading.Thread(target=self.loop, daemon=True, name="fuse%d" % i)
            t.start()
            self.threads.append(t)

    def unmount(self):
        """正常結束：先離開自己的掛載點（不然 umount 會 EBUSY），再請 fusermount3 卸。"""
        self.stopping.set()
        os.chdir("/")
        r = subprocess.run(["fusermount3", "-u", self.mnt], capture_output=True, text=True)
        if r.returncode != 0:      # 還有人站在裡面：退一步用 lazy
            subprocess.run(["fusermount3", "-u", "-z", self.mnt], capture_output=True)
        for t in self.threads:
            t.join(2)
        try:
            os.rmdir(self.mnt)
        except OSError:
            pass

    def attr(self, nid):
        kind, mode, _ = self.node(nid)
        size = 0
        if kind == "dir":
            mode |= S_IFDIR
        elif kind == "link":
            mode |= S_IFLNK
            size = len(self.readlink(nid))
        else:
            mode |= S_IFREG
            if self.size_mode == "real" and mode & 0o444:
                size = len(self.content(nid))
        now = int(time.time())
        return ATTR.pack(nid, size, (size + 511) // 512, now, now, now, 0, 0, 0, mode,
                         2 if kind == "dir" else 1, self.uid, self.gid, 0, 4096, 0)

    def reply(self, unique, err=0, data=b""):
        try:
            os.write(self.fd, OUT_HDR.pack(OUT_HDR.size + len(data), -err, unique) + data)
        except OSError as e:
            if e.errno != errno.ENOENT:          # ENOENT＝那個請求已被中斷，照協議忽略
                raise

    def loop(self):
        while True:
            try:
                buf = os.read(self.fd, BUFSIZE)
            except OSError as e:
                if e.errno in (errno.EINTR, errno.EAGAIN, errno.ENOENT):
                    continue
                if e.errno == errno.ENODEV:          # 被卸掉了
                    self.stopping.set()
                    return
                raise
            if not buf:
                return
            ln, opcode, unique, nid, uid, gid, pid, _ext, _pad = IN_HDR.unpack_from(buf)
            body = buf[IN_HDR.size:ln]
            try:
                self.dispatch(opcode, unique, nid, pid, body)
            except Exception as e:                   # 玩具：任何錯都回 EIO，別讓整條執行緒死掉
                sys.stderr.write("toyproc: op %s 出錯 %r\n" % (opcode, e))
                if opcode not in NO_REPLY:
                    self.reply(unique, errno.EIO)

    def log(self, opcode, nid, pid, extra=""):
        if self.trace:
            self.trace.write("%.6f %s nid=%d pid=%d %s\n" % (time.time(), OPNAME.get(opcode, opcode), nid, pid, extra))

    def dispatch(self, opcode, unique, nid, pid, body):
        name = OPNAME.get(opcode)
        if opcode == OP["INIT"]:
            major, minor, ra, flags = struct.unpack_from("<IIII", body)
            self.log(opcode, nid, pid, "kernel=%d.%d flags=%#x" % (major, minor, flags))
            out = struct.pack("<IIIIHHIIHHI", 7, 31, ra, 0, 16, 12, MAX_WRITE, 1, 0, 0, 0) + b"\0" * 28
            return self.reply(unique, 0, out)
        if opcode in NO_REPLY:
            self.log(opcode, nid, pid)
            return
        if opcode == OP["LOOKUP"]:
            nm = body.split(b"\0", 1)[0].decode()
            hit = dict(self.children(nid)).get(nm) if self.node(nid) and self.node(nid)[0] == "dir" else None
            self.log(opcode, nid, pid, "name=%s -> %s" % (nm, hit))
            if hit is None:
                return self.reply(unique, errno.ENOENT)
            ttl = 0 if self.node(hit)[0] == "link" else 1
            return self.reply(unique, 0, struct.pack("<QQQQII", hit, 0, ttl, 0, 0, 0) + self.attr(hit))
        if self.node(nid) is None:
            self.log(opcode, nid, pid, "stale")
            return self.reply(unique, errno.ENOENT)
        if opcode == OP["GETATTR"]:
            self.log(opcode, nid, pid)
            return self.reply(unique, 0, struct.pack("<QII", 0, 0, 0) + self.attr(nid))
        if opcode == OP["SETATTR"]:
            valid, _p, fh, size = struct.unpack_from("<IIQQ", body)
            self.log(opcode, nid, pid, "valid=%#x size=%d" % (valid, size))
            return self.reply(unique, 0, struct.pack("<QII", 0, 0, 0) + self.attr(nid))
        if opcode == OP["READLINK"]:
            self.log(opcode, nid, pid)
            return self.reply(unique, 0, self.readlink(nid))
        if opcode == OP["OPEN"]:
            flags, = struct.unpack_from("<I", body)
            err = self.open_check(nid, flags)
            self.log(opcode, nid, pid, "flags=%#o -> %s" % (flags, errno.errorcode.get(err, err)))
            if err:
                return self.reply(unique, err)
            with self.lock:
                fh = self.fh_next
                self.fh_next += 1
                if (flags & O_ACCMODE) != os.O_WRONLY and self.gen_mode == "open":
                    self.fh_data[fh] = self.content(nid)     # 開的那一刻拍一張，整次讀都讀這張
            oflags = FOPEN_DIRECT_IO if self.size_mode == "zero-direct" else 0
            return self.reply(unique, 0, struct.pack("<QII", fh, oflags, 0))
        if opcode == OP["READ"]:
            fh, off, size = struct.unpack_from("<QQI", body)
            self.log(opcode, nid, pid, "off=%d size=%d" % (off, size))
            with self.lock:
                data = self.fh_data.get(fh)
            if data is None:
                data = self.content(nid)
            return self.reply(unique, 0, data[off:off + size])
        if opcode == OP["WRITE"]:
            fh, off, size = struct.unpack_from("<QQI", body)
            data = body[40:40 + size]
            r = self.write(nid, data)
            self.log(opcode, nid, pid, "off=%d data=%r -> %s" % (off, data, r))
            if r < 0:
                return self.reply(unique, -r)
            return self.reply(unique, 0, struct.pack("<II", r, 0))
        if opcode in (OP["FLUSH"], OP["FSYNC"], OP["RELEASEDIR"]):
            self.log(opcode, nid, pid)
            return self.reply(unique)
        if opcode == OP["RELEASE"]:
            fh, = struct.unpack_from("<Q", body)
            self.log(opcode, nid, pid)
            with self.lock:
                self.fh_data.pop(fh, None)
            return self.reply(unique)
        if opcode == OP["OPENDIR"]:
            self.log(opcode, nid, pid)
            return self.reply(unique, 0, struct.pack("<QII", 0, 0, 0))
        if opcode == OP["READDIR"]:
            fh, off, size = struct.unpack_from("<QQI", body)
            self.log(opcode, nid, pid, "off=%d" % off)
            ents = [(".", nid), ("..", 1)] + list(self.children(nid))
            out = b""
            for i, (nm, cid) in enumerate(ents[off:], start=off):
                kind = self.node(cid)[0] if self.node(cid) else "file"
                t = {"dir": DT_DIR, "link": DT_LNK}.get(kind, DT_REG)
                nb = nm.encode()
                ent = struct.pack("<QQII", cid, i + 1, len(nb), t) + nb
                ent += b"\0" * (-len(ent) % 8)
                if len(out) + len(ent) > size:
                    break
                out += ent
            return self.reply(unique, 0, out)
        if opcode == OP["STATFS"]:
            self.log(opcode, nid, pid)
            return self.reply(unique, 0, struct.pack("<QQQQQIIII", 0, 0, 0, 0, 0, 4096, 255, 4096, 0) + b"\0" * 24)
        if opcode == OP["DESTROY"]:
            self.log(opcode, nid, pid)
            self.reply(unique)
            return
        self.log(opcode, nid, pid, "-> ENOSYS")
        return self.reply(unique, errno.ENOSYS)


class ToyProc(FuseServer):
    """一隻玩具 aos proc：status（讀）、ctl（寫）、settings、attrs。"""
    ROOT, STATUS, CTL, SETTINGS, ATTRS = 1, 2, 3, 4, 5
    KIND = "toyproc"

    def __init__(self, name, busy_check="both", **kw):
        super().__init__(os.path.join(SCRATCH, "mnt", "%s-%d" % (name, os.getpid())), "toy-" + name, **kw)
        self.name, self.busy_check = name, busy_check
        self.t0 = time.time()
        self.phase = "running"
        self.ctl_cmd, self.ctl_state, self.ctl_error = "", "idle", ""
        self.busy = False
        self.reads = 0
        self.selfread = ""
        self.pad = int(os.environ.get("TOY_STATUS_PAD", "0"))

    def node(self, nid):
        return {self.ROOT: ("dir", 0o555, None), self.STATUS: ("file", 0o444, None),
                self.CTL: ("file", 0o200, None), self.SETTINGS: ("file", 0o444, None),
                self.ATTRS: ("file", 0o444, None)}.get(nid)

    def children(self, nid):
        if nid == self.ROOT:
            return [("status", self.STATUS), ("ctl", self.CTL), ("settings", self.SETTINGS), ("attrs", self.ATTRS)]
        return []

    def status_lines(self):
        with self.lock:
            self.reads += 1
            lines = ["name: %s" % self.name, "pid: %d" % os.getpid(), "phase: %s" % self.phase,
                     "aos_ctl_cmd: %s" % self.ctl_cmd, "aos_ctl_state: %s" % self.ctl_state,
                     "aos_ctl_error: %s" % self.ctl_error, "uptime: %.3f" % (time.time() - self.t0),
                     "status_reads: %d" % self.reads]
            if self.selfread:
                lines.append("selfread: %s" % self.selfread)
            gen = self.reads
        for i in range(self.pad):
            lines.append("pad_%04d: gen=%d" % (i, gen))   # 每行帶這次產生的序號：拼接出不同版本就看得出來
        return lines

    def content(self, nid):
        if nid == self.STATUS:
            return ("\n".join(self.status_lines()) + "\n").encode()
        if nid == self.SETTINGS:
            return ("persist: /tmp/aos-%s/persist\nthreads: %d\nsize_mode: %s\n" % (self.name, self.nthreads, self.size_mode)).encode()
        if nid == self.ATTRS:
            return ("kind: fuse\nlive: yes\nimpl: %s\n" % self.KIND).encode()
        return b""

    def open_check(self, nid, flags):
        if nid == self.CTL and (flags & O_ACCMODE) != os.O_RDONLY and self.busy_check in ("open", "both"):
            with self.lock:
                if self.busy:
                    return errno.EBUSY            # 鎖住中：開檔就拒，失敗不動 aos_ctl_*
        return 0

    def write(self, nid, data):
        if nid != self.CTL:
            return -errno.EACCES
        lines = [l.strip() for l in data.decode(errors="replace").splitlines() if l.strip()]
        if not lines:
            return len(data)
        if len(lines) > 1:
            return -errno.EINVAL                  # 一次寫一道
        words = lines[0].split()
        with self.lock:
            if self.busy and self.busy_check in ("write", "both"):
                return -errno.EBUSY
            self.busy = True
            self.ctl_cmd, self.ctl_state, self.ctl_error = lines[0], "working", ""
            cmd = words[0]
            ok = cmd in ("stop", "pause", "resume", "selfread", "selfread-inline") or \
                (cmd == "slow" and len(words) == 2 and words[1].replace(".", "", 1).isdigit())
            if not ok:
                self.ctl_state, self.ctl_error, self.busy = "error", "unknown command: %s" % lines[0], False
                return len(data)
        if cmd == "selfread-inline":
            # 故意在 FUSE 處理執行緒裡讀自己掛載點：只有一條執行緒時會卡死（問題 5）
            self.do_selfread()
            self.finish()
            return len(data)
        threading.Thread(target=self.run_cmd, args=(words,), daemon=True).start()
        return len(data)                          # 寫回來＝收到，不等做完

    def do_selfread(self):
        t = time.time()
        with open(os.path.join("/proc/%d/cwd" % os.getpid(), "status")) as f:
            n = len(f.read().splitlines())
        with self.lock:
            self.selfread = "%d lines in %.1f ms" % (n, (time.time() - t) * 1000)

    def finish(self, state="done"):
        with self.lock:
            self.ctl_state, self.busy = state, False

    def run_cmd(self, words):
        cmd = words[0]
        if cmd == "pause":
            self.phase = "paused"
        elif cmd == "resume":
            self.phase = "running"
        elif cmd == "slow":
            time.sleep(float(words[1]))
        elif cmd == "selfread":
            self.do_selfread()
        elif cmd == "stop":
            self.phase = "stopping"
            self.before_stop()
            self.finish()
            self.stopping.set()
            return
        self.finish()

    def before_stop(self):
        pass


def common_args(ap):
    ap.add_argument("--name", required=True)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--size", default="zero-direct", choices=["zero-direct", "zero-cache", "real"])
    ap.add_argument("--gen", default="open", choices=["open", "read"])
    ap.add_argument("--busy-check", default="both", choices=["open", "write", "both"])
    ap.add_argument("--auto-unmount", action="store_true")


def run(proc):
    signal.signal(signal.SIGTERM, lambda *a: proc.stopping.set())
    proc.mount()
    os.chdir(proc.mnt)            # 要在伺服器執行緒起來之後：chdir 本身會送 LOOKUP/GETATTR 進來
    print("READY %d %s" % (os.getpid(), proc.mnt), flush=True)
    while not proc.stopping.wait(0.5):
        pass
    proc.unmount()


def main():
    ap = argparse.ArgumentParser()
    common_args(ap)
    a = ap.parse_args()
    run(ToyProc(a.name, busy_check=a.busy_check, threads=a.threads, auto_unmount=a.auto_unmount,
                size_mode=a.size, gen_mode=a.gen, trace=os.environ.get("TOY_TRACE")))


if __name__ == "__main__":
    main()
