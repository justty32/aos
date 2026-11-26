#!/usr/bin/env python3
# toys.py：測試時在天空裡跑的小程式（主 kernel、探路的 proc、照退出碼結束的、睡著的、時好時壞的 kernel）。
import errno, os, sys, time

# 主 kernel 拿到的 AOS_DAEMON（mount 模式 /aos、ptrace 模式 /proc/1/cwd）；其他 proc 沒有
ROOT = os.environ.get("AOS_DAEMON", "/proc/1/cwd")


def try_path(p):
    """讀一個路徑：夾就列、檔就讀；'kill:PID' 是試送訊號 0；'env:NAME' 是那個環境變數。回 'ok …' 或 'err ENAME'。"""
    try:
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


def put(out, name, text):
    tmp = os.path.join(out, "." + name + ".tmp")
    with open(tmp, "w") as f:
        f.write(text)
    os.rename(tmp, os.path.join(out, name))


def kernel(out):
    """主 kernel：記下自己讀不讀得到 $AOS_DAEMON/status（第一行）、AOS_DAEMON 是什麼、讀不讀得到 /proc/1/cwd；
    之後照 out/ask-* 做（讀路徑或寫 ctl），答案寫 out/ans-*。"""
    put(out, "kernel-%d.txt" % os.getpid(), "%s\nroot %s\nproc1 %s\n" % (
        try_path(ROOT + "/status"), os.environ.get("AOS_DAEMON", "-"), try_path("/proc/1/cwd/status")))
    while True:
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


def main():
    mode = sys.argv[1]
    if mode == "kernel":
        kernel(sys.argv[2])
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
    elif mode == "exit":
        sys.exit(int(sys.argv[2]))
    elif mode == "chatter":   # chatter OUT：stdout 與 stderr 各寫一行，記下 OUT/chatter.done，然後睡
        print("CHATTER-OUT", flush=True)
        print("CHATTER-ERR", file=sys.stderr, flush=True)
        put(sys.argv[2], "chatter.done", "x")
        time.sleep(1000)
    elif mode == "kchatter":   # 當主 kernel，同上
        print("CHATTER-OUT", flush=True)
        print("CHATTER-ERR", file=sys.stderr, flush=True)
        kernel(sys.argv[2])
    elif mode == "sleep":
        time.sleep(1000)
    elif mode == "flaky":   # flaky OUT N：前 N 次起來就以 5 結束，之後當主 kernel
        out, n = sys.argv[2], int(sys.argv[3])
        cnt = os.path.join(out, "flaky-count")
        k = int(open(cnt).read()) if os.path.exists(cnt) else 0
        with open(cnt, "w") as f:
            f.write(str(k + 1))
        if k < n:
            sys.exit(5)
        kernel(out)


if __name__ == "__main__":
    main()
