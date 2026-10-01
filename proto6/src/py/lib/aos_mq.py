"""aos-mq：寄信給 aos-daemon 的一項、取一項的信（plan m3m-daemon-modules.md 模組四）。

    aos-mq send [--urgent] <收件 inst> <JSON|->
    aos-mq take [<inst>]

socket 只從 AOS_DAEMON_MQ_SOCKET 拿。send 的 `from` 自動填 AOS_DAEMON_INST（沒有就 null，M1）；
JSON 給 `-` 就從 stdin 讀。take 沒給 <inst> 用 AOS_DAEMON_INST（M3：給了就可以取別項的），
每封一行 `{"from":…,"msg":…}` 印到 stdout，沒信什麼都不印。
連上、送一行、讀一行、關掉；不重試、不另設逾時（默認一切正常）。
結束碼照 aos-ctl：daemon 回 ok:true 回 0，其餘一律 1，stderr 一行 `代碼: 說明`。
"""
import json
import os
import socket
import sys

from aos_ctl import fail

USAGE = "aos-mq send [--urgent] <收件 inst> <JSON|->｜aos-mq take [<inst>]"


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main(argv=None, env=None, stdin=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if not argv or argv[0] not in ("send", "take"):
        return fail("usage", USAGE)
    cmd, urgent, rest = argv[0], False, []
    for a in argv[1:]:
        if a == "--urgent" and cmd == "send":
            urgent = True
        elif a.startswith("--"):            # 只有 -- 開頭算旗標：`-` 是讀 stdin，`-5` 是 JSON 負數
            return fail("usage", "%s 不認得 %s；%s" % (cmd, a, USAGE))
        else:
            rest.append(a)
    if cmd == "send":
        if len(rest) != 2:
            return fail("usage", "send 要剛好 <收件 inst> 與 <JSON>；%s" % USAGE)
        text = (stdin or sys.stdin).read() if rest[1] == "-" else rest[1]
        try:
            msg = json.loads(text)
        except ValueError:
            return fail("usage", "<JSON> 不是 JSON；%s" % USAGE)
        req = {"send": rest[0], "msg": msg, "from": env.get("AOS_DAEMON_INST") or None, "urgent": urgent}
    else:
        if len(rest) > 1:
            return fail("usage", "只能給一個 <inst>；%s" % USAGE)
        inst = rest[0] if rest else env.get("AOS_DAEMON_INST")
        if not inst:
            return fail("no_inst", "沒給 <inst>，也沒有 AOS_DAEMON_INST")
        req = {"take": inst}
    path = env.get("AOS_DAEMON_MQ_SOCKET")
    if not path:
        return fail("no_daemon", "沒有 AOS_DAEMON_MQ_SOCKET（不在 daemon 底下，或 daemon 沒掛訊息模組）")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(path)
    except OSError as e:
        return fail("connect", "%s: %s" % (path, e.strerror or e))
    with s:
        s.sendall((dump(req) + "\n").encode("utf-8"))
        line = s.makefile("rb").readline()
    reply = json.loads(line.decode("utf-8"))
    if not reply.get("ok"):
        return fail(reply.get("error"), reply.get("detail"))
    for m in reply.get("messages", []):
        sys.stdout.write(dump(m) + "\n")
    return 0
