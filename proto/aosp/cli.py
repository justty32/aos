"""指令面。子命令名照 WRITER-BRIEF 4.10。

錯誤一律「指路」：講出哪個檔、哪一欄、下一步敲什麼。
"""
import argparse
import json
import os
import sys

from . import exits, execute, fsutil, inbox, layout, loader, registry, series as S


def _land(path):
    return layout.Land(path)


def _die(msg, code, hint=None):
    sys.stderr.write("錯誤：%s\n" % msg)
    if hint:
        sys.stderr.write("下一步：%s\n" % hint)
    return code


# ---------- init ----------
def cmd_init(args):
    land, created = layout.init(args.land, force=args.force)
    src = land.source("main")
    if not os.path.exists(src) and args.with_example:
        fsutil.write_json(src, {
            "format_version": 1, "name": "main",
            "steps": [{"name": "hello", "kind": "inst",
                       "inst": {"argv": ["echo", "hello from aos"]}, "then": "end"}],
        })
    print("%s %s" % ("建好了" if created else "已經是一塊地：", land.root))
    print("  .aos/layout.json  .aos/config.json")
    return exits.OK


# ---------- compile ----------
def cmd_compile(args):
    land = _land(args.land)
    if not land.is_land():
        return _die("%s 不是一塊地" % land.root, exits.NOT_A_LAND,
                    "python3 proto/aos.py init %s" % land.root)
    try:
        names = loader.compile_all(land)
    except loader.ParseError as e:
        return _die(str(e), exits.PARSE, "改好 %s 再跑一次" % land.source("main"))
    if not names:
        return _die("%s 上找不到任何 *.aos.json 原稿" % land.root, exits.PARSE,
                    "先寫一份 %s" % land.source("main"))
    for n in names:
        print("編好 %s -> %s" % (land.source(n), land.program(n)))
    return exits.OK


# ---------- exec ----------
def cmd_exec(args):
    land = _land(args.land)
    try:
        rep = execute.exec_once(land, timeout_ms=args.timeout)
    except execute.NotALand as e:
        return _die(str(e), exits.NOT_A_LAND, "先跑 init")
    except loader.ParseError as e:
        return _die(str(e), exits.PARSE, "改原稿或模板")
    except fsutil.LockBusy as e:
        return _die(str(e), exits.LOCK_BUSY, "等別人跑完，或確認沒有孤兒 %s" % land.lock)
    _print_tick(rep, args.json)
    return exits.OK


def _print_tick(rep, as_json=False):
    if as_json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        return
    print("第 %d 格 @ %s" % (rep["tick"], rep["land"]))
    for n in rep["notes"]:
        print("  " + n)
    box = rep.get("inbox") or {}
    for k, label in (("mail", "搬信"), ("inst", "跑投遞指令"), ("rejected", "拒收")):
        if box.get(k):
            print("  收件匣 %s：%d 筆" % (label, len(box[k])))
    print("  %s" % ("閒著了" if rep["idle"] else "還有串在跑"))


# ---------- status ----------
def cmd_status(args):
    land = _land(args.land)
    if not land.is_land():
        return _die("%s 不是一塊地" % land.root, exits.NOT_A_LAND,
                    "python3 proto/aos.py init %s" % land.root)
    baton = S.load(land)
    if args.json:
        print(json.dumps({
            "land": land.root, "series": baton, "stopped": fsutil.read_json(land.stopped),
        }, ensure_ascii=False, indent=2))
        return exits.OK
    print("地：%s" % land.root)
    if baton is None:
        print("  還沒開跑（沒有 .aos/series.json）")
        return exits.OK
    print("  批 %s，下一格 %d" % (baton["batch_id"][:8], baton["tick"]))
    for sr in baton["series"]:
        line = "  串 %s  模板 %s  游標 %s  狀態 %s" % (
            sr["id"][:8], sr["template"], sr["cursor"], sr["status"])
        print(line)
        if sr.get("fail_reason"):
            fr = sr["fail_reason"]
            print("      壞在：%s — %s" % (fr.get("reason"), fr.get("message")))
        if sr.get("regs"):
            print("      暫存器：%s" % ", ".join("%s=%s" % kv for kv in sr["regs"].items()))
    st = fsutil.read_json(land.stopped)
    if st:
        print("  停止原因檔：%s — %s" % (st.get("reason"), st.get("message")))
    pend = inbox.scan(land)
    if pend:
        print("  收件匣待處理：%d 封" % len(pend))
    return exits.OK


# ---------- deliver ----------
def cmd_deliver(args):
    land = _land(args.land)
    raw = args.json_arg
    if raw == "-":
        raw = sys.stdin.read()
    elif os.path.exists(raw):
        with open(raw, "r", encoding="utf-8") as f:
            raw = f.read()
    try:
        obj = json.loads(raw)
    except ValueError as e:
        return _die("投遞物不是合法 json：%s" % e, exits.USAGE,
                    "傳一段 json、一個檔名、或 - 從 stdin 讀")
    obj.setdefault("format_version", 1)
    obj.setdefault("id", fsutil.new_id())
    obj.setdefault("at", fsutil.now_iso())
    obj.setdefault("from", os.path.abspath(args.sender or os.getcwd()))
    try:
        inbox.validate(obj)
    except inbox.Rejected as e:
        return _die("投遞物不合格（%s）：%s" % (e.reason, e.message), exits.USAGE,
                    "看 WRITER-BRIEF 4.5 投遞物欄位")
    ok, info = inbox.deliver(land, obj)
    if not ok:
        return _die(info, exits.USAGE, "換一個 id 再投")
    print("投進去了：%s" % info)
    return exits.OK


# ---------- reset ----------
def cmd_reset(args):
    land = _land(args.land)
    baton = S.load(land)
    if baton is None:
        print("本來就沒串。")
        return exits.OK
    n = 0
    keep = []
    for sr in baton["series"]:
        if sr["status"] in (S.FAILED, S.STOPPED):
            n += 1
            continue
        keep.append(sr)
    baton["series"] = keep
    S.save(land, baton)
    try:
        os.unlink(land.stopped)
    except FileNotFoundError:
        pass
    print("清掉 %d 條壞掉／停住的串，%s" % (n, "現在閒著了" if S.idle(baton) else "還有串在跑"))
    return exits.OK


# ---------- run / stop / daemon / llm 由各自模組接手 ----------
def cmd_run(args):
    from . import run as runmod
    return runmod.cli_run(args)


def cmd_stop(args):
    from . import daemon as dmod
    return dmod.cli_stop(args)


def cmd_daemon(args):
    from . import daemon as dmod
    return dmod.cli_daemon(args)


def cmd_llm(args):
    from . import llm as lmod
    return lmod.cli_llm(args)


def build_parser():
    p = argparse.ArgumentParser(prog="aos", description="aos 原型（不是正式實作）")
    sub = p.add_subparsers(dest="cmd")

    q = sub.add_parser("init", help="建一塊地")
    q.add_argument("land")
    q.add_argument("--force", action="store_true")
    q.add_argument("--with-example", action="store_true", help="順手寫一份 main.aos.json")
    q.set_defaults(func=cmd_init)

    q = sub.add_parser("compile", help="原稿 -> 模板")
    q.add_argument("land")
    q.set_defaults(func=cmd_compile)

    q = sub.add_parser("exec", help="走一格")
    q.add_argument("land")
    q.add_argument("--timeout", type=int, default=None, help="每筆指令的 timeout（毫秒）")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_exec)

    q = sub.add_parser("run", help="反覆 exec")
    q.add_argument("land")
    q.add_argument("--steps", type=int, default=None)
    q.add_argument("--every", type=int, default=None, metavar="MS")
    q.add_argument("--until", default=None, choices=["idle"])
    q.add_argument("--budget", type=int, default=None)
    q.add_argument("--timeout", type=int, default=60000, metavar="MS")
    q.add_argument("--register", action="store_true")
    q.add_argument("--json", action="store_true")
    q.add_argument("--quiet", action="store_true")
    q.set_defaults(func=cmd_run)

    q = sub.add_parser("status", help="看串與游標")
    q.add_argument("land")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_status)

    q = sub.add_parser("deliver", help="投遞一個 json")
    q.add_argument("land")
    q.add_argument("json_arg", metavar="JSON")
    q.add_argument("--sender", default=None, help="投遞者的地（預設 cwd）")
    q.set_defaults(func=cmd_deliver)

    q = sub.add_parser("reset", help="清掉壞掉／停住的串")
    q.add_argument("land")
    q.set_defaults(func=cmd_reset)

    q = sub.add_parser("stop", help="請一塊地在格尾停")
    q.add_argument("land")
    q.add_argument("--kill", action="store_true", help="不走控制收件匣，直接 SIGKILL")
    q.set_defaults(func=cmd_stop)

    q = sub.add_parser("daemon", help="看管者")
    q.add_argument("op", choices=["start", "stop", "ls", "exec", "status", "add"])
    q.add_argument("land", nargs="?", default=None)
    q.add_argument("--foreground", action="store_true")
    q.add_argument("--every", type=int, default=500, metavar="MS")
    q.add_argument("--steps", type=int, default=None, help="只有 add 用：固定次數的鐘")
    q.add_argument("--until", default=None, choices=["idle"], help="只有 add 用")
    q.add_argument("--budget", type=int, default=None, help="只有 add 用")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_daemon)

    q = sub.add_parser("llm", help="LLM 世界")
    q.add_argument("op", choices=["init", "serve", "tick", "ls", "ask"])
    q.add_argument("rest", nargs="*")
    q.add_argument("--land", default=None, help="LLM 世界的地（預設 $AOS_HOME/.aos/llm）")
    q.add_argument("--until", default=None, choices=["idle"])
    q.add_argument("--steps", type=int, default=None)
    q.add_argument("--every", type=int, default=200, metavar="MS")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_llm)

    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    p = build_parser()
    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return exits.USAGE
    try:
        return args.func(args)
    except fsutil.LockBusy as e:
        return _die(str(e), exits.LOCK_BUSY, "等別人跑完再來")
    except loader.ParseError as e:
        return _die(str(e), exits.PARSE, "改原稿")
    except execute.NotALand as e:
        return _die(str(e), exits.NOT_A_LAND, "先 init")
    except KeyboardInterrupt:
        return exits.CANCELLED
