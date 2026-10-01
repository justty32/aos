"""aos-mq：寄信給 aos-daemon 的一項、取或看自己的信（plan m3m-daemon-modules.md 模組四）。

    aos-mq send [--urgent] <收件 inst> <JSON|->
    aos-mq take [--from [<寄件 inst>…]]…
    aos-mq peek [--from [<寄件 inst>…]]…

socket 只從 AOS_DAEMON_MQ_SOCKET 拿。send 的 `from` 自動填 AOS_DAEMON_INST（沒有就 null，M1）；
JSON 給 `-` 就從 stdin 讀。take、peek 只對自己的信箱（AOS_DAEMON_INST；使用者 2026-10-01 第十四批）；
take 取走、peek 只看不取（第十五批）。`--from a c d` 把後面接的參數（到下一個 `--` 開頭的參數為止）都當寄件人，
`--from` 後面什麼都不接＝寄件人是 null 的信，可以重複寫、疊加；不給 `--from` 就全部（第十五批）。
每封一行 `{"from":…,"msg":…}` 印到 stdout，沒信什麼都不印。
連上、送一行、讀一行、關掉；不重試、不另設逾時（默認一切正常）。
結束碼照 aos-ctl：daemon 回 ok:true 回 0，其餘一律 1，stderr 一行 `代碼: 說明`。
"""
import json
import os
import socket
import sys

from aos_ctl import fail

USAGE = ("aos-mq send [--urgent] <收件 inst> <JSON|->"
         "｜aos-mq take|peek [--from [<寄件 inst>…]]…")


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main(argv=None, env=None, stdin=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if not argv or argv[0] not in ("send", "take", "peek"):
        return fail("usage", USAGE)
    cmd, urgent, senders, rest = argv[0], False, None, []
    args = argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--urgent" and cmd == "send":
            urgent = True
        elif a == "--from" and cmd != "send":
            # 後面接的到下一個 -- 開頭的參數為止都是寄件人；一個都沒接＝null（寄件人是 null 的信）
            got = []
            while i < len(args) and not args[i].startswith("--"):
                got.append(args[i])
                i += 1
            senders = (senders or []) + (got or [None])
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
            return fail("usage", "%s 只對自己的信箱，不收 <inst>；%s" % (cmd, USAGE))
        inst = env.get("AOS_DAEMON_INST")
        if not inst:
            return fail("no_inst", "沒有 AOS_DAEMON_INST（%s 只對自己那一項的信箱）" % cmd)
        req = {cmd: inst}
        if senders is not None:
            req["from"] = senders
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
