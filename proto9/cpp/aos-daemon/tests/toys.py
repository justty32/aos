#!/usr/bin/env python3
# toys.py：測試時在天空裡跑的小程式（init、探路的 proc、照退出碼結束的、睡著的、時好時壞的 init、收到 SIGTERM 才收尾的 init、留下孩子的 proc、試網路的 proc）。
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
