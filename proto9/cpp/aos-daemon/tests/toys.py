#!/usr/bin/env python3
# toys.py：測試時在天空裡跑的小程式（init、探路的 proc、照退出碼結束的、睡著的、時好時壞的 init、收到 SIGTERM 才收尾的 init、留下孩子的 proc、試網路的 proc、試系統呼叫（seccomp）與開 namespace、mount 的 proc）。
import errno, os, signal, socket, sys, time

# init 拿到的 AOS_DAEMON（mount 模式 /aos、ptrace 模式 /proc/1/cwd）；其他 proc 沒有
ROOT = os.environ.get("AOS_DAEMON", "/proc/1/cwd")


def try_path(p):
    """讀一個路徑：夾就列、檔就讀；'kill:PID' 是試送訊號 0；'env:NAME' 是那個環境變數；'put:PATH=VALUE' 是把 VALUE 寫進 PATH。
    回 'ok …' 或 'err ENAME'。"""
    try:
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
        }
        args = tuple(L(x) for x in table[what])
    ctypes.set_errno(0)
    r = c.syscall(*args)
    if r == -1:
        e = ctypes.get_errno()
        return "err " + errno.errorcode.get(e, str(e))
    return "ok"


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
