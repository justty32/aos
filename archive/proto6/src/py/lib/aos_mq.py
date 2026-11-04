"""aos-mq：往 aos-daemon 的某扇訊息門寄信、取或看自己的信（plan m3m-daemon-modules.md 模組四；第二十五批改版）。

    aos-mq send <socket 路徑> <JSON|->
    aos-mq take <socket 路徑>
    aos-mq peek <socket 路徑>

`<socket 路徑>` 是某扇訊息門（任務裡通常寫 `"$AOS_DAEMON_MQ_<門名>"`；別的 daemon 的門也行），相對路徑以呼叫者的 cwd 為準。
- send：信＝`<JSON>` 原樣（給 `-` 就從 stdin 讀），daemon 放進訂了那扇門的每一項的信箱並叫醒它們；成功什麼都不印。
  不需要任何環境變數。
- take、peek：連這個 daemon 的任何一扇門都行，取／看 `AOS_DAEMON_INST` 那一項全部的信（沒有就回 1、`no_inst`），
  不收 inst 參數；每封一行印到 stdout，沒信什麼都不印。take 取走、peek 只看不取。
連上、送一行、讀一行、關掉；不重試、不另設逾時（默認一切正常）。
結束碼照 aos-ctl：daemon 回 ok:true 回 0，其餘一律 1，stderr 一行 `代碼: 說明`。
〔使用者 2026-10-02 第二十五批〕拿掉 `--urgent`、`--socket`、`--all`、`--channel`、`--from`、`--to`、收件 inst、印收到項數。
"""
import json
import os
import socket
import sys

from aos_ctl import fail

USAGE = "aos-mq send <socket 路徑> <JSON|->｜aos-mq take|peek <socket 路徑>"


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main(argv=None, env=None, stdin=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if not argv or argv[0] not in ("send", "take", "peek"):
        return fail("usage", USAGE)
    cmd, args = argv[0], argv[1:]
    for a in args:
        if a.startswith("--"):          # 只有 -- 開頭算旗標：`-` 是讀 stdin，`-5` 是 JSON 負數
            return fail("usage", "%s 不認得 %s；%s" % (cmd, a, USAGE))
    if len(args) != (2 if cmd == "send" else 1):
        return fail("usage", USAGE)
    path = args[0]
    if cmd == "send":
        text = (stdin or sys.stdin).read() if args[1] == "-" else args[1]
        try:
            msg = json.loads(text)
        except ValueError:
            return fail("usage", "<JSON> 不是 JSON；%s" % USAGE)
        req = {"send": msg}
    else:
        inst = env.get("AOS_DAEMON_INST")
        if not inst:
            return fail("no_inst", "沒有 AOS_DAEMON_INST（%s 只對自己那一項的信箱）" % cmd)
        req = {cmd: inst}
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
