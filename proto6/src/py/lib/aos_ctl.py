"""aos-ctl：送一個控制指令給 aos-daemon 的控制模組（plan m3n-control-module.md 步驟 5）。

    aos-ctl wake [--skip-while-running] [--keep-schedule] [<inst>]
    aos-ctl pause|resume|status [<inst>]

每個指令都只對一項；沒給 <inst> 用 AOS_DAEMON_INST。socket 只從 AOS_DAEMON_SOCKET 拿。
連上、送一行、讀一行、關掉；不重試、不另設逾時（默認一切正常）。
結束碼：daemon 回 ok:true 回 0，其餘一律 1，stderr 一行 `代碼: 說明`。
"""
import json
import os
import socket
import sys

COMMANDS = ("wake", "pause", "resume", "status")
FLAGS = {"--skip-while-running": "skip_while_running", "--keep-schedule": "keep_schedule"}
USAGE = ("aos-ctl wake [--skip-while-running] [--keep-schedule] [<inst>]"
         "｜aos-ctl pause|resume|status [<inst>]")


def fail(code, detail):
    sys.stderr.write("%s: %s\n" % (code, detail))
    return 1


def main(argv=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if not argv or argv[0] not in COMMANDS:
        return fail("usage", USAGE)
    cmd, req, rest = argv[0], {}, []
    for a in argv[1:]:
        if a in FLAGS and cmd == "wake":
            req[FLAGS[a]] = True
        elif a.startswith("-"):
            return fail("usage", "%s 不認得 %s；%s" % (cmd, a, USAGE))
        else:
            rest.append(a)
    if len(rest) > 1:
        return fail("usage", "只能給一個 <inst>；%s" % USAGE)
    path = env.get("AOS_DAEMON_SOCKET")
    if not path:
        return fail("no_daemon", "沒有 AOS_DAEMON_SOCKET（不在 daemon 底下，或 daemon 沒掛控制模組）")
    inst = rest[0] if rest else env.get("AOS_DAEMON_INST")
    if not inst:
        return fail("no_inst", "沒給 <inst>，也沒有 AOS_DAEMON_INST")
    req[cmd] = inst
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(path)
    except OSError as e:
        return fail("connect", "%s: %s" % (path, e.strerror or e))
    with s:
        s.sendall((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
        line = s.makefile("rb").readline()
    reply = json.loads(line.decode("utf-8"))
    if not reply.get("ok"):
        return fail(reply.get("error"), reply.get("detail"))
    if cmd == "status":
        sys.stdout.write(line.decode("utf-8"))
    return 0
