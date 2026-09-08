#!/usr/bin/env python3
"""aos：一支給人用的 CLI。

    python3 aos.py start|stop|ls
    python3 aos.py register DIR [NAME] [INTERVAL]
    python3 aos.py unregister NAME

家目錄走 --home 或環境變數 AOS_HOME。

start／stop 直接轉呼叫 daemon；register／unregister 只是寫一個請求檔到 H/requests/，
等 kernel 下一格撿走翻譯成 daemon 請求（規矩：使用者與 CLI 只寫 requests/，
只有 kernel 可以寫 daemon/requests/）；ls 讀 daemon/state.json 印表格。
"""
import argparse
import json
import os
import sys
import time

import aos_daemon as d
from aos_cpu import write_json


def put_request(home, req):
    """檔名 <毫秒>-<pid>.json，先寫 .tmp 再 rename（aos_cpu.write_json 就是這樣寫的）。"""
    home.ensure()
    name = "%013d-%d.json" % (time.time() * 1000, os.getpid())
    write_json(os.path.join(home.requests, name), req)
    print("送出 %s：%s" % (name, json.dumps(req, ensure_ascii=False)))
    return name


def ls(home):
    st = home.state()
    print("daemon  %s  pid=%s  家=%s" % ("alive" if home.alive() else "stopped",
                                          (st or {}).get("pid"), home.dir))
    if not st:
        print("（還沒有 state.json，daemon 沒起來過）")
        return
    print("%-14s %-8s %-6s %-6s %s" % ("NAME", "PID", "ALIVE", "TICK", "RSS_KB"))
    for name, c in sorted(st.get("cpus", {}).items()):
        print("%-14s %-8s %-6s %-6s %s" % (name, c.get("pid"), "yes" if c.get("alive") else "no",
                                           c.get("tick"), c.get("rss_kb")))


def main():
    ap = argparse.ArgumentParser(prog="aos")
    ap.add_argument("cmd", choices=["start", "stop", "ls", "register", "unregister"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--home", default=os.environ.get("AOS_HOME"))
    a = ap.parse_args()
    if not a.home:
        print("沒有家：給 --home 或設 AOS_HOME", file=sys.stderr)
        return 2
    home = d.Home(a.home)
    if a.cmd == "start":
        return 0 if d.start(home) else 1
    if a.cmd == "stop":
        return 0 if d.stop(home) else 1
    if a.cmd == "ls":
        ls(home)
        return 0
    if a.cmd == "register":
        if not a.args:
            print("register 要給 DIR", file=sys.stderr)
            return 2
        req = {"op": "register", "dir": os.path.abspath(a.args[0])}
        if len(a.args) > 1:
            req["name"] = a.args[1]
        if len(a.args) > 2:
            req["interval"] = float(a.args[2])
    else:
        if not a.args:
            print("unregister 要給 NAME", file=sys.stderr)
            return 2
        req = {"op": "unregister", "name": a.args[0]}
    put_request(home, req)
    return 0


if __name__ == "__main__":
    sys.exit(main())
