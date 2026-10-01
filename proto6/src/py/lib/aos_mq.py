"""aos-mq：寄信給 aos-daemon 的一項、取一項的信（plan m3m-daemon-modules.md 模組四）。

    aos-mq send [--urgent] <收件 inst> <JSON|->
    aos-mq take [--from <寄件 inst>]

socket 只從 AOS_DAEMON_MQ_SOCKET 拿。send 的 `from` 自動填 AOS_DAEMON_INST（沒有就 null，M1）；
JSON 給 `-` 就從 stdin 讀。take 只取自己的信箱（AOS_DAEMON_INST；使用者 2026-10-01 第十四批），
`--from` 只取那個寄件人的、不給就全部；每封一行 `{"from":…,"msg":…}` 印到 stdout，沒信什麼都不印。
連上、送一行、讀一行、關掉；不重試、不另設逾時（默認一切正常）。
結束碼照 aos-ctl：daemon 回 ok:true 回 0，其餘一律 1，stderr 一行 `代碼: 說明`。
"""
import json
import os
import socket
import sys

from aos_ctl import fail

USAGE = "aos-mq send [--urgent] <收件 inst> <JSON|->｜aos-mq take [--from <寄件 inst>]"


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main(argv=None, env=None, stdin=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if not argv or argv[0] not in ("send", "take"):
        return fail("usage", USAGE)
    cmd, urgent, sender, rest = argv[0], False, None, []
    args = iter(argv[1:])
    for a in args:
        if a == "--urgent" and cmd == "send":
            urgent = True
        elif a == "--from" and cmd == "take":
            sender = next(args, None)
            if sender is None:
                return fail("usage", "--from 後面要接寄件 inst；%s" % USAGE)
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
        if rest:
            return fail("usage", "take 只取自己的信箱，不收 <inst>；%s" % USAGE)
        inst = env.get("AOS_DAEMON_INST")
        if not inst:
            return fail("no_inst", "沒有 AOS_DAEMON_INST（take 只取自己那一項的信箱）")
        req = {"take": inst}
        if sender is not None:
            req["from"] = sender
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
