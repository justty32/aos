"""aos-daemon-root：帳號模組的 root 端（plan m3m-daemon-modules.md 模組五）。

主程式（還是 root）開它、交一頭 SOCK_SEQPACKET 的 socketpair，然後主程式永久降成預設帳號。
這支一直是 root，只做一件事：**用某個帳號開一個程序，等它結束，回結束碼**。
不讀設定檔、不 import aos 的其他模組，程式越小越好。單執行緒（select＋SIGCHLD），不在多執行緒裡 fork。

封包（一個封包一則，UTF-8 JSON）：

- 第一則（主程式→這裡）：`{"default": "<預設帳號>", "allow": [...], "deny": [...]}`。名單之後不變。
- 請求（主程式→這裡）：`{"id": n, "user": "<帳號>", "argv": [...], "cwd": "...", "env": {...}, "frame": "<框>"|null}`，
  附兩個 fd（SCM_RIGHTS）：子程序的 stdout、stderr。stdin 是 /dev/null。
- 回應（這裡→主程式）：`{"id": n, "exit": <碼，被訊號 N 殺＝128+N>}`；開不了：`{"id": n, "error": "<說明>"}`。

開之前再核一次：帳號照名單是准的、`getpwnam` 查得到、不是 root（UID 0）。子程序：開新 session、有框就先把
自己寫進框的 `cgroup.procs`（還是 root，別的帳號的程序才搬得進去）、`initgroups`／`setgid`／`setuid`、
`HOME`／`USER`／`LOGNAME` 換成那個帳號的、chdir、exec。

主程式那頭關了（讀到 EOF）就退出，不殺還在跑的子程序。
"""
import json
import os
import pwd
import select
import signal
import socket
import sys

MAX = 1 << 20


def match(pattern, name):
    return name.startswith(pattern[:-1]) if pattern.endswith("*") else name == pattern


def check(policy, name):
    """回 struct_passwd；不准或查不到回錯誤說明字串。"""
    try:
        pw = pwd.getpwnam(name)
    except KeyError:
        return "no such user %s" % name
    if pw.pw_uid == 0:
        return "not allowed: %s is root" % name
    if name == policy["default"]:
        return pw
    if any(match(p, name) for p in policy["deny"]) or not any(match(p, name) for p in policy["allow"]):
        return "not allowed: %s" % name
    return pw


def child(req, pw, out_fd, err_fd):
    """fork 出來的子程序：到 exec 為止。出事就寫到 stderr fd、以 127 結束。"""
    try:
        os.setsid()
        if req.get("frame"):
            with open(os.path.join(req["frame"], "cgroup.procs"), "w") as f:
                f.write(str(os.getpid()))
        os.initgroups(pw.pw_name, pw.pw_gid)
        os.setgid(pw.pw_gid)
        os.setuid(pw.pw_uid)
        os.chdir(req["cwd"])
        null = os.open(os.devnull, os.O_RDONLY)
        os.dup2(null, 0)
        os.dup2(out_fd, 1)
        os.dup2(err_fd, 2)
        env = dict(req["env"], HOME=pw.pw_dir, USER=pw.pw_name, LOGNAME=pw.pw_name)
        os.execve(req["argv"][0], req["argv"], env)
    except BaseException as e:
        try:
            os.write(err_fd, ("aos-daemon-root: %s\n" % e).encode("utf-8", "replace"))
        finally:
            os._exit(127)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sock = socket.socket(fileno=int(argv[0]))
    r, w = os.pipe()
    os.set_blocking(w, False)
    signal.set_wakeup_fd(w)
    signal.signal(signal.SIGCHLD, lambda signum, frame: None)
    signal.signal(signal.SIGINT, signal.SIG_IGN)     # 只看 socketpair 關了沒
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    policy = json.loads(sock.recv(MAX).decode("utf-8"))
    running = {}                    # pid → 請求 id

    def reply(obj):
        sock.send(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    while True:
        ready, _, _ = select.select([sock, r], [], [])
        if r in ready:
            os.read(r, 512)
            while running:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid == 0:
                    break
                rid = running.pop(pid, None)
                if rid is not None:
                    code = os.waitstatus_to_exitcode(status)
                    reply({"id": rid, "exit": 128 - code if code < 0 else code})
        if sock in ready:
            data, fds, _, _ = socket.recv_fds(sock, MAX, 2)
            if not data:
                return 0
            req = json.loads(data.decode("utf-8"))
            pw = check(policy, req["user"])
            if isinstance(pw, str):
                for fd in fds:
                    os.close(fd)
                reply({"id": req["id"], "error": pw})
                continue
            pid = os.fork()
            if pid == 0:
                child(req, pw, fds[0], fds[1])
            for fd in fds:
                os.close(fd)
            running[pid] = req["id"]


if __name__ == "__main__":
    sys.exit(main())
