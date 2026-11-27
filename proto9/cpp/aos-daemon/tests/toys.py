#!/usr/bin/env python3
# toys.py：測試時在天空裡跑的小程式（init、探路的 proc、照退出碼結束的、睡著的、時好時壞的 init、收到 SIGTERM 才收尾的 init、留下孩子的 proc 與 init、帶著孩子的 proc、試網路的 proc、試系統呼叫（seccomp）與開 namespace、mount 的 proc、送訊號與冒名送訊號的 proc、建與找 SysV IPC／POSIX mqueue 的 proc），外加在外面跑的：故意不回答的 FUSE（stuckfuse）、在 unshare 出來的那一層起 daemon 並在那一層掛卸 tmpfs（outer）、在沒有 /tmp 的根裡起 daemon（notmp）。
import errno, os, signal, socket, sys, time

# init 拿到的 AOS_DAEMON（它的 daemon_path，預設 /aos）；其他 proc 沒有（沒有時當 /proc/1/cwd，讀了會被擋）
ROOT = os.environ.get("AOS_DAEMON", "/proc/1/cwd")


def try_path(p):
    """讀一個路徑：夾就列、檔就讀；'kill:PID' 是試送訊號 0；'sig:PID:SIG' 是真的送訊號 SIG；'forge:PID:SIG:FAKEPID' 是用
    rt_sigqueueinfo 送、寄件人 PID 填 FAKEPID（si_code SI_QUEUE）；'env:NAME' 是那個環境變數；'put:PATH=VALUE' 是把 VALUE 寫進 PATH；
    'statvfs:PATH' 是那個檔案系統的總大小（位元組）；'fill:PATH:N' 是寫一個 N 位元組的檔；'ipc:KIND:WHAT' 是看不看得到那個
    SysV 物件或 mqueue（ipc_see）。回 'ok …' 或 'err ENAME'。"""
    try:
        if p.split(":", 1)[0] in ESCAPE_PROBES:   # escape 組：見 escape_probe
            return escape_probe(p)
        if p.startswith("ipc:"):   # ipc:KIND:WHAT：看不看得到那個 SysV 物件／mqueue（見 ipc_see）
            return ipc_see(*p[4:].split(":", 1))
        if p.startswith("statvfs:"):
            v = os.statvfs(p[8:])
            return "ok %d" % (v.f_blocks * v.f_frsize)
        if p.startswith("fill:"):
            path, n = p[5:].rsplit(":", 1)
            with open(path, "wb") as f:
                f.write(b"x" * int(n))
            return "ok"
        if p.startswith("sig:"):
            pid, sig = p[4:].split(":")
            os.kill(int(pid), int(sig))
            return "ok"
        if p.startswith("forge:"):
            pid, sig, fake = (int(x) for x in p[6:].split(":"))
            return forge(pid, sig, fake)
        if p.startswith("put:"):
            path, _, value = p[4:].partition("=")
            with open(path, "w") as f:
                f.write(value)
            return "ok"
        if p.startswith("env:"):
            v = os.environ.get(p[4:])
            return "err unset" if v is None else "ok " + v
        if p.startswith("kill:"):
            os.kill(int(p[5:]), 0)
            return "ok"
        if os.path.isdir(p):
            return "ok " + " ".join(sorted(os.listdir(p)))
        with open(p) as f:
            return "ok " + f.read(4000).replace("\n", "|")
    except OSError as e:
        return "err " + errno.errorcode.get(e.errno, str(e.errno))


ESCAPE_PROBES = {"devnodes", "umount", "mounttmpfs", "remountrw", "openrw", "link", "mkfifo", "symw", "tcp", "run", "rename", "rmdir"}


def escape_probe(p):
    """escape 組（照 Codex、srt 測試的意思改寫）的探測，一個字串一件事；回 'ok …' 或 'err ENAME'（run 回 'ok rc=N …'）：
    devnodes＝/dev 的五個是字元裝置、/dev/null 寫得進、/dev/zero 讀得到 0、/dev/full 寫是 ENOSPC；umount:PATH；mounttmpfs:PATH；
    remountrw:PATH（bind 重掛成可寫）；openrw:PATH；link:SRC:DST（硬連結）；mkfifo:PATH；symw:LINK:TARGET（建一個指到 TARGET
    的 symlink 再經它寫）；tcp:IP:PORT（連線）；run:ARGV（空白分開，回退出碼與輸出的頭）；rename:SRC:DST；rmdir:PATH。"""
    import ctypes
    import stat as st
    kind, _, rest = p.partition(":")
    c = ctypes.CDLL(None, use_errno=True)

    def rc(r):
        return "ok" if r == 0 else "err " + errno.errorcode.get(ctypes.get_errno(), "?")
    if kind == "devnodes":
        bad = [n for n in ("null", "zero", "full", "random", "urandom") if not st.S_ISCHR(os.stat("/dev/" + n).st_mode)]
        if bad:
            return "err notchr " + ",".join(bad)
        with open("/dev/null", "wb") as f:
            f.write(b"x")
        with open("/dev/zero", "rb") as f:
            if f.read(4) != b"\0" * 4:
                return "err zero"
        try:
            with open("/dev/full", "wb", buffering=0) as f:
                f.write(b"x")
            return "err full-wrote"
        except OSError as e:
            if e.errno != errno.ENOSPC:
                raise
        return "ok"
    if kind == "umount":
        return rc(c.umount2(rest.encode(), 2))                        # MNT_DETACH
    if kind == "mounttmpfs":
        return rc(c.mount(b"none", rest.encode(), b"tmpfs", 0, None))
    if kind == "remountrw":
        return rc(c.mount(None, rest.encode(), None, 0x20 | 0x1000, None))   # MS_REMOUNT | MS_BIND，不帶 MS_RDONLY
    if kind == "openrw":
        os.close(os.open(rest, os.O_RDWR))
        return "ok"
    if kind == "link":
        a, b = rest.split(":", 1)
        os.link(a, b)
        return "ok"
    if kind == "mkfifo":
        os.mkfifo(rest)
        return "ok"
    if kind == "symw":
        link, target = rest.split(":", 1)
        os.symlink(target, link)
        with open(link, "w") as f:
            f.write("escaped")
        return "ok"
    if kind == "tcp":
        ip, port = rest.rsplit(":", 1)
        socket.create_connection((ip, int(port)), timeout=3).close()
        return "ok"
    if kind == "run":
        import subprocess
        r = subprocess.run(rest.split(" "), capture_output=True, text=True, timeout=20)
        return "ok rc=%d %s" % (r.returncode, (r.stdout + r.stderr).replace("\n", " ")[:200])
    if kind == "rename":
        a, b = rest.split(":", 1)
        os.rename(a, b)
        return "ok"
    if kind == "rmdir":
        os.rmdir(rest)
        return "ok"
    return "err unknown"


def forge(pid, sig, fake):
    """rt_sigqueueinfo(pid, sig, info)：info 的 si_code 是 SI_QUEUE（-1）、si_pid 是 fake（核心不改，除非寄件人在祖先的 PID namespace）。"""
    import ctypes, struct
    c = ctypes.CDLL(None, use_errno=True)
    c.syscall.restype = ctypes.c_long
    buf = ctypes.create_string_buffer(struct.pack("<iiiiiI", sig, 0, -1, 0, fake, 0) + b"\0" * 104, 128)
    ctypes.set_errno(0)
    if c.syscall(ctypes.c_long(129), ctypes.c_long(pid), ctypes.c_long(sig), buf) == -1:
        e = ctypes.get_errno()
        return "err " + errno.errorcode.get(e, str(e))
    return "ok"


def stuckfuse(mnt, out):
    """在外面跑：用 fusermount3 掛一個 FUSE 在 mnt，回答 INIT 與根的 GETATTR／STATFS，其他 LOOKUP 回 ENOENT，
    但 LOOKUP 名字以 "stuck" 開頭的讀了就不回答：碰 mnt/stuck… 的行程會卡在核心裡（SIGKILL 也要等這個請求回來）。
    掛好寫 out/ready；收到那種 LOOKUP 時寫 out/stuck-<那個請求的 pid>（同一個名字第二個人會在核心裡等第一個，不會再來一次）。被殺掉（fd 關了）時核心中止連線，卡住的人放開。"""
    import socket as sk, struct, subprocess
    a, b = sk.socketpair(sk.AF_UNIX, sk.SOCK_STREAM)
    env = dict(os.environ, _FUSE_COMMFD=str(b.fileno()))
    r = subprocess.run(["fusermount3", "-o", "fsname=aosdtest-stuck,subtype=stuck", "--", mnt], env=env, pass_fds=[b.fileno()])
    if r.returncode != 0:
        put(out, "failed", "fusermount3 exited %d\n" % r.returncode)
        return
    _, fds, _, _ = sk.recv_fds(a, 1, 1)
    fd = fds[0]
    uid, gid = os.getuid(), os.getgid()
    attr = struct.pack("<QQQQQQIIIIIIIIII", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0o40755, 2, uid, gid, 0, 4096, 0)

    def reply(unique, err=0, body=b""):
        os.write(fd, struct.pack("<IiQ", 16 + len(body), -err, unique) + body)

    while True:
        req = os.read(fd, 1 << 20)
        ln, op, unique, node = struct.unpack("<IIQQ", req[:24])
        rpid = struct.unpack("<I", req[32:36])[0]
        body = req[40:ln]
        if op == 26:     # INIT
            major, minor, ra, flags = struct.unpack("<IIII", body[:16])
            par = flags & (1 << 18)   # FUSE_PARALLEL_DIROPS：不然同一個夾裡的 lookup 一個一個來，第二個人卡在核心裡等第一個、到不了這裡
            reply(unique, 0, struct.pack("<IIIIHHIIHHI", 7, 31, ra, par, 0, 0, 4096, 1, 0, 0, 0) + b"\0" * 28)
            put(out, "ready", "x")
        elif op == 1:    # LOOKUP
            if body.split(b"\0")[0].startswith(b"stuck"):
                put(out, "stuck-%d" % rpid, "x")   # 讀了、不回答
            else:
                reply(unique, errno.ENOENT)
        elif op == 3:    # GETATTR
            reply(unique, 0, struct.pack("<QII", 1, 0, 0) + attr)
        elif op == 17:   # STATFS
            reply(unique, 0, b"\0" * 80)
        elif op in (2, 36, 38, 42):   # FORGET、INTERRUPT、DESTROY、BATCH_FORGET：不回
            pass
        else:
            reply(unique, errno.ENOSYS)


def pdeath_kill():
    """Popen 的 preexec_fn：我（叫它的那支）死了，它也收到 SIGKILL。"""
    import ctypes
    ctypes.CDLL(None).prctl(1, 9, 0, 0, 0)   # PR_SET_PDEATHSIG, SIGKILL


def outer(argv):
    """在 unshare -Urm --propagation shared 裡跑（測試起它；這一層就是 daemon 的「外面」）：起 daemon（argv），把它 stdout 的第一行
    （export）轉出來；之後一行一道從 stdin 讀：'mount DIR'＝在這一層把一塊新 tmpfs 掛到 DIR 並寫 DIR/hello；'umount DIR'＝卸掉；
    每道回一行 ok／err。stdin 關了就對 daemon 送 SIGTERM、等它結束，以它的退出碼結束。"""
    import subprocess
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, preexec_fn=pdeath_kill)
    sys.stdout.write(p.stdout.readline().decode())
    sys.stdout.flush()
    while True:
        cmd = sys.stdin.readline()
        if not cmd:
            break
        what, _, d = cmd.strip().partition(" ")
        if what == "mount":
            r = subprocess.run(["mount", "-t", "tmpfs", "-o", "size=1m", "aosdtest-outer", d])
            if r.returncode == 0:
                put(d, "hello", "hi\n")
        else:
            r = subprocess.run(["umount", d])
        print("ok" if r.returncode == 0 else "err %d" % r.returncode, flush=True)
    p.send_signal(signal.SIGTERM)
    sys.exit(p.wait())


def notmp(root, binds, argv):
    """在 unshare -Urm 裡跑：root（空夾）掛一塊 tmpfs、照 binds（"外面=裡面"，用 , 分開）rbind 進去、加 bin／lib／lib64 連結，
    pivot_root 進去（新的根裡沒有 /tmp），再 exec argv。"""
    ctypes, c = libc()
    MS_BIND, MS_REC = 4096, 16384

    def ok(r, what):
        if r != 0:
            sys.exit("notmp: %s: %s" % (what, os.strerror(ctypes.get_errno())))
    ok(c.mount(b"aosdtest-notmp", root.encode(), b"tmpfs", 0, b"mode=0755"), "mount root")
    for spec in binds.split(","):
        src, dst = spec.split("=")
        os.makedirs(root + dst, exist_ok=True)
        ok(c.mount(src.encode(), (root + dst).encode(), None, MS_BIND | MS_REC, None), "bind " + src)
    for name, target in (("bin", "usr/bin"), ("lib", "usr/lib"), ("lib64", "usr/lib64")):
        os.symlink(target, os.path.join(root, name))
    os.chdir(root)
    c.syscall.restype = ctypes.c_long
    ok(c.syscall(ctypes.c_long(155), b".", b"."), "pivot_root")
    ok(c.umount2(b".", 2), "detach old root")
    os.chdir("/")
    os.execv(argv[0], argv)


def write_ctl(line):
    try:
        fd = os.open(ROOT + "/ctl", os.O_WRONLY)
        try:
            os.write(fd, (line + "\n").encode())
        finally:
            os.close(fd)
        return "ok"
    except OSError as e:
        return "err " + errno.errorcode.get(e.errno, str(e.errno))


def errname(e):
    return errno.errorcode.get(e.errno, str(e.errno)) if e.errno else type(e).__name__


def net(port):
    """試網路：連外面（起測試的那一層）127.0.0.1:port、在自己的 127.0.0.1 收發一個位元組、/proc/net/dev 列的介面。"""
    res = []
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        res.append("host ok")
    except OSError as e:
        res.append("host err " + errname(e))
    try:
        lis = socket.socket()
        lis.bind(("127.0.0.1", 0))
        lis.listen(1)
        c = socket.create_connection(lis.getsockname(), timeout=2)
        a, _ = lis.accept()
        c.sendall(b"x")
        res.append("loop ok" if a.recv(1) == b"x" else "loop bad")
    except OSError as e:
        res.append("loop err " + errname(e))
    with open("/proc/net/dev") as f:
        res.append("ifaces " + ",".join(sorted(l.split(":")[0].strip() for l in f.read().splitlines()[2:])))
    return "\n".join(res) + "\n"


def libc():
    import ctypes
    return ctypes, ctypes.CDLL(None, use_errno=True)


def sys_probe(what):
    """試一個系統呼叫（x86_64 號碼，直接 syscall()，不經 glibc 的包裝）；回 'ok' 或 'err ENAME'。"""
    ctypes, c = libc()
    c.syscall.restype = ctypes.c_long
    L = ctypes.c_long
    me = os.getpid()
    if what == "process_vm_readv":
        class Iov(ctypes.Structure):
            _fields_ = [("base", ctypes.c_void_p), ("len", ctypes.c_size_t)]
        src, dst = ctypes.create_string_buffer(b"x" * 8), ctypes.create_string_buffer(8)
        a, b = Iov(ctypes.addressof(dst), 8), Iov(ctypes.addressof(src), 8)
        args = (L(310), L(me), ctypes.byref(a), L(1), ctypes.byref(b), L(1), L(0))
    elif what == "process_vm_writev1":   # 寫 PID 1（daemon）的記憶體（idea from srt test/sandbox/pid-namespace-isolation.test.ts）
        class Iov(ctypes.Structure):
            _fields_ = [("base", ctypes.c_void_p), ("len", ctypes.c_size_t)]
        src = ctypes.create_string_buffer(b"x" * 8)
        a, b = Iov(ctypes.addressof(src), 8), Iov(0x400000, 8)
        args = (L(311), L(1), ctypes.byref(a), L(1), ctypes.byref(b), L(1), L(0))
    elif what == "vsockpair":            # socketpair(AF_VSOCK, SOCK_STREAM)
        sv = (ctypes.c_int * 2)()
        args = (L(53), L(40), L(1), L(0), sv)
    else:
        table = {
            "getpid": (39,), "getppid": (110,),
            "ptrace": (101, 2, 1, 0, 0),                  # PTRACE_PEEKDATA pid 1（不是 TRACEME：那會讓 daemon 變成追蹤它的人）
            "bpf": (321, 0, 0, 0), "init_module": (175, 0, 0, 0), "finit_module": (313, -1, 0, 0),
            "kcmp": (312, me, me, 1, 0, 0),               # KCMP_VM：跟自己比
            "personality_query": (135, 0xffffffff), "personality_aslr": (135, 0x0040000),
            "keyctl": (250, 0, -4, 0),                    # KEYCTL_GET_KEYRING_ID user keyring
            "userfaultfd": (323, 1),                      # UFFD_USER_MODE_ONLY
            "io_uring_setup": (425, 1, 0),
            "name_to_handle_at": (303, -100, 0, 0, 0, 0),
            "syslog": (103, 10, 0, 0),                    # SYSLOG_ACTION_SIZE_BUFFER
            "reboot": (169, 0, 0, 0, 0), "swapon": (167, 0, 0), "acct": (163, 0),
            "clock_settime": (227, 0, 0),
            # 11-27 跟 Codex、srt 對照加的（idea from codex-rs/linux-sandbox/src/seccomp_tests.rs::x32_preserves_allowed_calls_and_socket_conditions
            # 與 srt test/sandbox/seccomp-vsock-block.test.ts、pid-namespace-isolation.test.ts）
            "vsock_stream": (41, 40, 1, 0), "vsock_dgram": (41, 40, 2, 0), "vsock_seqpacket": (41, 40, 5, 0),
            "vsock_hi": (41, (1 << 32) | 40, 1, 0),      # domain 暫存器的上半有東西：核心只看低 32 位，照樣是 AF_VSOCK
            "unix_socket": (41, 1, 1, 0), "inet_socket": (41, 2, 1, 0), "inet6_socket": (41, 10, 1, 0),
            "netlink_socket": (41, 16, 3, 0),           # AF_NETLINK、SOCK_RAW、NETLINK_ROUTE
            "io_uring_enter": (426, -1, 0, 0, 0, 0, 0), "io_uring_register": (427, -1, 0, 0, 0),
            "ptrace_attach1": (101, 16, 1, 0, 0),         # PTRACE_ATTACH PID 1（daemon）
        }
        args = tuple(L(x) for x in table[what])
    ctypes.set_errno(0)
    r = c.syscall(*args)
    if r == -1:
        e = ctypes.get_errno()
        return "err " + errno.errorcode.get(e, str(e))
    return "ok"


# SysV IPC 與 POSIX mqueue（ipc 組）：天空裡的 proc 與外面的 run.py 都用這幾個（run.py import 這個檔）。
# 物件：shm KEY、sem KEY+1、msg KEY+2、mq NAME；回 'ok …' 或 'err ENAME'
IPC_CREAT, IPC_EXCL, IPC_RMID, IPC_NOWAIT, SHM_RDONLY, GETVAL, SETVAL = 0o1000, 0o2000, 0, 0o4000, 0o10000, 12, 16


def ipc_libs():
    ctypes, c = libc()
    c.shmat.restype = ctypes.c_void_p
    c.shmat.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    c.shmdt.argtypes = [ctypes.c_void_p]
    rt = c
    if not hasattr(c, "mq_open"):   # glibc 2.34 以前 mq_* 在 librt
        rt = ctypes.CDLL("librt.so.1", use_errno=True)
    return ctypes, c, rt


def ipc_err(ctypes):
    e = ctypes.get_errno()
    return "err " + errno.errorcode.get(e, str(e))


def sem_value(marker):
    return sum(marker.encode()) % 30000


def ipc_make(kind, what, marker):
    """建一個（IPC_EXCL／O_EXCL：已經有同 key、同名的就 EEXIST），放進 marker。"""
    ctypes, c, rt = ipc_libs()
    ctypes.set_errno(0)
    m = marker.encode()
    if kind == "shm":
        i = c.shmget(int(what), 64, IPC_CREAT | IPC_EXCL | 0o600)
        if i < 0:
            return ipc_err(ctypes)
        a = c.shmat(i, None, 0)
        if a is None or a == ctypes.c_void_p(-1).value:
            return ipc_err(ctypes)
        ctypes.memmove(a, m + b"\0", len(m) + 1)
        c.shmdt(ctypes.c_void_p(a))
        return "ok"
    if kind == "sem":
        i = c.semget(int(what), 1, IPC_CREAT | IPC_EXCL | 0o600)
        if i < 0 or c.semctl(i, 0, SETVAL, ctypes.c_int(sem_value(marker))) < 0:
            return ipc_err(ctypes)
        return "ok"
    if kind == "msg":
        i = c.msgget(int(what), IPC_CREAT | IPC_EXCL | 0o600)
        buf = ctypes.create_string_buffer(b"\1\0\0\0\0\0\0\0" + m)
        if i < 0 or c.msgsnd(i, buf, len(m), IPC_NOWAIT) < 0:
            return ipc_err(ctypes)
        return "ok"
    if kind == "mq":
        fd = rt.mq_open(what.encode(), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600, None)
        if fd < 0:
            return ipc_err(ctypes)
        r = rt.mq_send(fd, m, len(m), 0)
        rt.mq_close(fd)
        return "ok" if r == 0 else ipc_err(ctypes)
    return "err unknown-kind"


def ipc_see(kind, what):
    """看得到嗎：shm 回裡面的字、sem 回值、msg 回第一封的字（MSG_COPY 不拿走；核心沒有 MSG_COPY 就只回 ok）、mq 回 ok。"""
    ctypes, c, rt = ipc_libs()
    ctypes.set_errno(0)
    if kind == "shm":
        i = c.shmget(int(what), 0, 0)
        if i < 0:
            return ipc_err(ctypes)
        a = c.shmat(i, None, SHM_RDONLY)
        if a is None or a == ctypes.c_void_p(-1).value:
            return ipc_err(ctypes)
        s = ctypes.string_at(a)
        c.shmdt(ctypes.c_void_p(a))
        return "ok " + s.decode(errors="replace")
    if kind == "sem":
        i = c.semget(int(what), 0, 0)
        v = c.semctl(i, 0, GETVAL) if i >= 0 else -1
        return ipc_err(ctypes) if v < 0 else "ok %d" % v
    if kind == "msg":
        i = c.msgget(int(what), 0)
        if i < 0:
            return ipc_err(ctypes)
        buf = ctypes.create_string_buffer(8 + 256)
        n = c.msgrcv(i, buf, 256, 0, IPC_NOWAIT | 0o40000)   # MSG_COPY：照位置 0 複製一封、不拿走
        return "ok " + buf.raw[8:8 + n].decode(errors="replace") if n >= 0 else "ok"
    if kind == "mq":
        fd = rt.mq_open(what.encode(), os.O_RDONLY, 0, None)
        if fd < 0:
            return ipc_err(ctypes)
        rt.mq_close(fd)
        return "ok"
    return "err unknown-kind"


def ipc_drop(kind, what):
    ctypes, c, rt = ipc_libs()
    if kind == "mq":
        return rt.mq_unlink(what.encode())
    get = {"shm": lambda: c.shmget(int(what), 0, 0), "sem": lambda: c.semget(int(what), 0, 0),
           "msg": lambda: c.msgget(int(what), 0)}[kind]
    i = get()
    if i < 0:
        return i
    return {"shm": lambda: c.shmctl(i, IPC_RMID, None), "sem": lambda: c.semctl(i, 0, IPC_RMID),
            "msg": lambda: c.msgctl(i, IPC_RMID, None)}[kind]()


def ipc_objects(key, mq):
    return [("shm", str(key)), ("sem", str(key + 1)), ("msg", str(key + 2)), ("mq", mq)]


def sysvipc_keys():
    """這個 IPC namespace 的 SysV 物件的 key（/proc/sysvipc/*，十進位）；讀不到回 None。"""
    keys = set()
    for k in ("shm", "sem", "msg"):
        try:
            lines = read_file("/proc/sysvipc/" + k).splitlines()[1:]
        except OSError:
            return None
        keys |= {int(l.split()[0]) for l in lines if l.strip()}
    return keys


def read_file(p):
    with open(p) as f:
        return f.read()


def ipc_toy(out, name, key, mq, probes):
    """ipc 那隻：在自己的 IPC namespace 建四樣（marker-NAME），再看 probes（'shm:KEY'、'sem:KEY'、'msg:KEY'、'mq:NAME'）
    與自己的那四樣，加上 /proc/sysvipc 列得出的 key；結果寫 OUT/NAME.txt。"""
    marker = "marker-" + name
    res = ["make:%s %s" % (k, ipc_make(k, w, marker)) for k, w in ipc_objects(key, mq)]
    res += ["own:%s %s" % (k, ipc_see(k, w)) for k, w in ipc_objects(key, mq)]
    res += ["%s %s" % (p, ipc_see(*p.split(":", 1))) for p in probes]
    ks = sysvipc_keys()
    res.append("sysvipc %s" % ("unreadable" if ks is None else ",".join(str(k) for k in sorted(ks)) or "-"))
    put(out, name + ".txt", "\n".join(res) + "\n")


def nsmount(uid_line):
    """在新的 user＋mount＋pid＋net＋uts＋ipc＋cgroup namespace 裡：寫 uid_map（uid_line）、mount 一塊 tmpfs、卸掉、setns 回自己的 uts。"""
    ctypes, c = libc()
    res = []

    def rc(name, r):
        res.append("%s %s" % (name, "ok" if r == 0 else "err " + errno.errorcode.get(ctypes.get_errno(), "?")))

    flags = 0x10000000 | 0x00020000 | 0x20000000 | 0x40000000 | 0x04000000 | 0x08000000 | 0x02000000
    rc("unshare", c.unshare(flags))
    try:
        with open("/proc/self/uid_map", "w") as f:
            f.write(uid_line + "\n")
        res.append("uid_map ok")
    except OSError as e:
        res.append("uid_map err " + errname(e))
    rc("mount", c.mount(b"none", b"/tmp", b"tmpfs", 0, None))
    rc("umount", c.umount2(b"/tmp", 2))
    fd = os.open("/proc/self/ns/uts", os.O_RDONLY)
    rc("setns", c.setns(fd, 0x04000000))
    return "\n".join(res) + "\n"


def die_arch(kind):
    """x32：號碼帶 0x40000000 的 getpid；i386：int 0x80 的 getpid（從一小段可執行的記憶體叫）。被 seccomp 擋就是整個行程被 SIGSYS 殺掉。"""
    ctypes, c = libc()
    if kind == "x32":
        c.syscall.restype = ctypes.c_long
        return c.syscall(ctypes.c_long(0x40000000 | 39))
    import mmap
    m = mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
    m.write(b"\xb8\x14\x00\x00\x00\xcd\x80\xc3")   # mov eax, 20; int 0x80; ret
    addr = ctypes.addressof(ctypes.c_char.from_buffer(m))
    return ctypes.CFUNCTYPE(ctypes.c_int)(addr)()


def put(out, name, text):
    tmp = os.path.join(out, "." + name + ".tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.rename(tmp, os.path.join(out, name))


def init_loop(out, tick=None):
    """init：記下自己讀不讀得到 $AOS_DAEMON/status（第一行）、AOS_DAEMON 是什麼、讀不讀得到 /proc/1/cwd；
    之後照 out/ask-* 做（讀路徑或寫 ctl），答案寫 out/ans-*。tick：每一圈先叫一次（igrace 用）。"""
    put(out, "init-%d.txt" % os.getpid(), "%s\nroot %s\nproc1 %s\n" % (
        try_path(ROOT + "/status"), os.environ.get("AOS_DAEMON", "-"), try_path("/proc/1/cwd/status")))
    while True:
        if tick:
            tick()
        for n in sorted(os.listdir(out)):
            if not n.startswith("ask-"):
                continue
            with open(os.path.join(out, n)) as f:
                q = f.read().strip()
            os.unlink(os.path.join(out, n))
            if q.startswith("ctl "):
                a = write_ctl(q[4:])
            else:
                a = try_path(q)
            put(out, "ans-" + n[4:], a + "\n")
        time.sleep(0.02)


def igrace(out, how):
    """當 init；收到 SIGTERM 時照 how 做：
    clean：寫 out/term，等 0.5 秒（收尾），寫 out/cleanup，以 0 結束
    ignore：SIGTERM 不理，照樣當 init
    stay：寫 out/term，照樣當 init（測試在寬限裡用 ask 叫它寫 ctl）
    die：寫 out/term，馬上以 3 結束
    ctl：寫 out/term，經 ctl 殺掉 w、等它死、forget 它，結果寫 out/cleanup，以 0 結束"""
    got = []
    if how == "ignore":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    else:
        signal.signal(signal.SIGTERM, lambda *_: got.append(1))

    def tick():
        if not got:
            return
        got.clear()
        put(out, "term", "x")
        if how == "clean":
            time.sleep(0.5)
            put(out, "cleanup", "x")
            sys.exit(0)
        if how == "die":
            sys.exit(3)
        if how == "ctl":
            a = write_ctl("kill w KILL")
            end = time.monotonic() + 5
            while try_path(ROOT + "/procs/w/state") != "ok dead|" and time.monotonic() < end:
                time.sleep(0.02)
            b = write_ctl("forget w")
            put(out, "cleanup", "%s %s %s\n" % (a, b, try_path(ROOT + "/procs/w")))
            sys.exit(0)
    init_loop(out, tick)


def main():
    mode = sys.argv[1]
    if mode == "init":
        init_loop(sys.argv[2])
    elif mode == "probe":   # probe OUT NAME PATH...：每個路徑一行結果，然後睡
        out, name = sys.argv[2], sys.argv[3]
        put(out, name + ".txt", "".join("%s %s\n" % (p, try_path(p)) for p in sys.argv[4:]))
        time.sleep(1000)
    elif mode == "write":   # write OUT NAME PATH...：試著在每個路徑寫一個檔
        out, name = sys.argv[2], sys.argv[3]
        res = []
        for p in sys.argv[4:]:
            try:
                with open(p, "w") as f:
                    f.write("x")
                res.append("%s ok" % p)
            except OSError as e:
                res.append("%s err %s" % (p, errno.errorcode.get(e.errno, str(e.errno))))
        put(out, name + ".txt", "\n".join(res) + "\n")
        time.sleep(1000)
    elif mode == "net":     # net OUT NAME PORT：見 net()，結果寫 OUT/NAME.txt，然後睡
        put(sys.argv[2], sys.argv[3] + ".txt", net(int(sys.argv[4])))
        time.sleep(1000)
    elif mode == "sys":     # sys OUT NAME CALL...：每個系統呼叫一行「CALL ok|err ENAME」，然後睡
        out, name = sys.argv[2], sys.argv[3]
        put(out, name + ".txt", "".join("%s %s\n" % (w, sys_probe(w)) for w in sys.argv[4:]))
        time.sleep(1000)
    elif mode == "ipc":     # ipc OUT NAME KEY MQNAME PROBE...：見 ipc_toy()，然後睡
        ipc_toy(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6:])
        time.sleep(1000)
    elif mode == "nsmount":   # nsmount OUT NAME UID_MAP_LINE：見 nsmount()，然後睡
        put(sys.argv[2], sys.argv[3] + ".txt", nsmount(sys.argv[4]))
        time.sleep(1000)
    elif mode == "isys":    # isys OUT CALL...：當 init，先試系統呼叫、寫 OUT/isys.txt
        put(sys.argv[2], "isys.txt", "".join("%s %s\n" % (w, sys_probe(w)) for w in sys.argv[3:]))
        init_loop(sys.argv[2])
    elif mode == "insmount":   # insmount OUT UID_MAP_LINE：當 init，先試 nsmount、寫 OUT/insmount.txt（在孩子裡試，自己不換 namespace）
        pid = os.fork()
        if pid == 0:
            put(sys.argv[2], "insmount.txt", nsmount(sys.argv[3]))
            os._exit(0)
        os.waitpid(pid, 0)
        init_loop(sys.argv[2])
    elif mode == "arch":    # arch OUT NAME x32|i386：寫 OUT/NAME.before，試；活下來就寫 OUT/NAME.txt
        out, name = sys.argv[2], sys.argv[3]
        put(out, name + ".before", "x")
        r = die_arch(sys.argv[4])
        put(out, name + ".txt", "survived %d\n" % r)
        time.sleep(1000)
    elif mode == "exit":
        sys.exit(int(sys.argv[2]))
    elif mode == "chatter":   # chatter OUT：stdout 與 stderr 各寫一行，記下 OUT/chatter.done，然後睡
        print("CHATTER-OUT", flush=True)
        print("CHATTER-ERR", file=sys.stderr, flush=True)
        put(sys.argv[2], "chatter.done", "x")
        time.sleep(1000)
    elif mode == "ichatter":   # 當 init，同上
        print("CHATTER-OUT", flush=True)
        print("CHATTER-ERR", file=sys.stderr, flush=True)
        init_loop(sys.argv[2])
    elif mode == "sleep":
        time.sleep(1000)
    elif mode == "igrace":   # igrace OUT HOW：見 igrace()
        igrace(sys.argv[2], sys.argv[3])
    elif mode == "orphan":   # orphan OUT NAME：生一個睡著的孩子（留在同一個 cgroup），寫 OUT/NAME.orphan 後自己以 0 結束
        if os.fork() == 0:
            os.setsid()
            put(sys.argv[2], sys.argv[3] + ".orphan", str(os.getpid()))
            time.sleep(1000)
            os._exit(0)
        end = time.monotonic() + 5
        while not os.path.exists(os.path.join(sys.argv[2], sys.argv[3] + ".orphan")) and time.monotonic() < end:
            time.sleep(0.01)
        os._exit(0)
    elif mode == "family":   # family OUT NAME same|setsid：生一個睡著的孩子（setsid＝它自己開新的 session、離開行程組），寫 OUT/NAME.child 後睡
        out, name = sys.argv[2], sys.argv[3]
        if os.fork() == 0:
            if sys.argv[4] == "setsid":
                os.setsid()
            put(out, name + ".child", str(os.getpid()))
            time.sleep(1000)
            os._exit(0)
        time.sleep(1000)
    elif mode == "iorphan":   # iorphan OUT：第一次起來生一個 setsid 的孩子（留在同一個 cgroup，寫 OUT/iorphan.child）後以 5 結束；之後當 init
        out = sys.argv[2]
        cnt = os.path.join(out, "iorphan-count")
        k = int(open(cnt).read()) if os.path.exists(cnt) else 0
        with open(cnt, "w") as f:
            f.write(str(k + 1))
        if k == 0:
            if os.fork() == 0:
                os.setsid()
                put(out, "iorphan.child", str(os.getpid()))
                time.sleep(1000)
                os._exit(0)
            end = time.monotonic() + 5
            while not os.path.exists(os.path.join(out, "iorphan.child")) and time.monotonic() < end:
                time.sleep(0.01)
            sys.exit(5)
        init_loop(out)
    elif mode == "outer":   # outer DAEMON_ARGV...：在 unshare 出來的那一層跑，見 outer()
        outer(sys.argv[2:])
    elif mode == "notmp":   # notmp ROOT BINDS DAEMON_ARGV...：見 notmp()
        notmp(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif mode == "stuckfuse":   # stuckfuse MNT OUT：在外面跑，見 stuckfuse()
        stuckfuse(sys.argv[2], sys.argv[3])
    elif mode == "flaky":   # flaky OUT N：前 N 次起來就以 5 結束，之後當 init
        out, n = sys.argv[2], int(sys.argv[3])
        cnt = os.path.join(out, "flaky-count")
        k = int(open(cnt).read()) if os.path.exists(cnt) else 0
        with open(cnt, "w") as f:
            f.write(str(k + 1))
        if k < n:
            sys.exit(5)
        init_loop(out)


if __name__ == "__main__":
    main()
