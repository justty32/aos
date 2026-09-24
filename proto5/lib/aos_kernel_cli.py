"""kernel 命令列的參數解析、請求投遞與摘要輸出。"""
import argparse
import json
import os
from pathlib import Path
import sys

import aos_client
import aos_daemon
import aos_home
from aos_kernel_boot import boot, status, stop
from aos_kernel_engine import tick
from aos_kernel_health import health
from aos_kernel_info import CONFIG_EXAMPLE, CLIUsage, KernelError, init, load_info

ENV = "AOS_KERNEL_HOME"
DAEMON_ENV = "AOS_DAEMON_HOME"


def _stderr_hint(target):
    path = Path(target)
    try:
        raw = aos_home.read_json(path) if path.suffix == ".json" else None
    except (aos_home.HomeError, OSError, ValueError):
        return str(path)
    value = raw.get("stderr") if isinstance(raw, dict) else None
    if isinstance(value, dict) and "$opt" in value:
        value = value.get("$val")
    if isinstance(value, str):
        return os.path.abspath(path.parent / value)
    return "%s 的 stderr 設定" % target


def _summary(home, snapshot, as_json=False):
    info = load_info(home)
    code, message = health(home, snapshot=snapshot, info=info)
    if as_json:
        return json.dumps({**snapshot, "health": {"code": code, "message": message}}, ensure_ascii=False)
    kcpu = snapshot["kernel_cpu"]
    daemon = snapshot["daemon"]
    lines = ["health " + message, "chain %s  phase %s  last_seq %s  daemon %s" % (
        snapshot["chain"] or "-", snapshot["phase"] or "-",
        snapshot["last_seq"] if snapshot["last_seq"] is not None else "-",
        "alive" if daemon["alive"] else "dead"),
        "kernel cpu %s  current %s  requests %s" % (
            kcpu["name"] or "-", (kcpu["current"] or {}).get("name", "-"), kcpu["requests"])]
    slots = snapshot["cpus"] or {}
    names = dict.fromkeys([*info["cpus"], *slots])
    if kcpu["name"]:
        names[kcpu["name"]] = None
    for name in names:
        slot = slots.get(name, {})
        busy = "busy %s (%s)" % (slot.get("proc"), slot["req"]) if slot.get("req") else "idle"
        child = daemon["children"].get(name)
        child_status = child["state"] if child else "missing"
        pool = info["cpus"].get(name, {}).get("pool", "-")
        lines.append("cpu %s  pool %s  %s  %s" % (name, pool, busy, child_status))
    for name, proc in (snapshot["procs"] or {}).items():
        lines.append("proc %s  %s  %s  runs %s  fails %s  pending %s" % (
            name, "once" if proc["once"] else "repeat", proc["status"], proc["runs"], proc["fails"],
            "有" if proc["pending"] else "-") +
            ("  看 " + _stderr_hint(proc["target"]) if proc["status"] == "bad" else ""))
    lines.append("queue %s" % (" ".join(snapshot["queue"] or []) or "-"))
    return "\n".join(lines)




class _Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        # 不收縮寫：舊的 --daemon 不能被當成 --daemon-target 的縮寫悄悄吃掉。
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        raise CLIUsage(message)


TARGET_HELP = "kernel 家（省略＝AOS_KERNEL_HOME，再沒有就目前資料夾）"
DAEMON_HELP = "daemon 家（省略＝AOS_DAEMON_HOME，再沒有就目前資料夾）"
INIT_EPILOG = ("--config 是一份 JSON，就是 info.json 要寫的那幾格（cpus 必填；tick_ms、interval_ms、timeout_ms、"
               "done_exit、bad_after 可省）。沒有 pool 是 kernel 的 cpu 就自動加 k。最小例子：\n  " + CONFIG_EXAMPLE)


def _parser():
    parser = _Parser(prog="aos-kernel", description="管理 kernel 家、cpu 與排程行程；K 一律用 --target 給")
    subs = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    descriptions = {"init": "建立 kernel 家（照 --config 寫 info.json）", "boot": "交接並啟動 cpu 與 tick 鏈",
                    "tick": "執行一格排程（鏈自己會叫）", "add": "登記工作", "rm": "移除行程",
                    "ls": "顯示狀態摘要", "halt": "要求 kernel 停機並等停好", "ack": "確認已收回音",
                    "check": "啟動前檢查設定與執行環境"}
    for command, description in descriptions.items():
        p = subs.add_parser(command, help=description, description=description,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
        if command == "add":
            p.add_argument("inst", metavar="INST", help="要執行的目標（inst.json、資料夾或普通檔）；-- ARG... 傳入目標參數")
        elif command in ("rm", "ack"):
            p.add_argument("name", help="回音檔名或路徑" if command == "ack" else "行程名稱")
        p.add_argument("--target", metavar="K", help=TARGET_HELP)
        if command == "init":
            p.usage = "aos-kernel init [--target K] --config FILE"
            p.epilog = INIT_EPILOG
            p.add_argument("--config", metavar="FILE", help="info 設定檔（JSON）；必填")
        elif command == "check":
            p.add_argument("--agent", action="append", help="一併檢查 agent 家")
            p.add_argument("--daemon-target", action="append", metavar="D", help=DAEMON_HELP)
        elif command == "halt":
            p.add_argument("--wait-ms", type=int, default=30000, help="停機等待上限（毫秒，預設 30000）")
            p.add_argument("--no-wait", action="store_true", help="只放 stop 單，不等待、不輸出")
        elif command == "ls":
            p.add_argument("--json", action="store_true", help="輸出完整狀態 JSON")
        elif command == "boot":
            p.add_argument("--daemon-target", metavar="D", help=DAEMON_HELP)
            p.add_argument("--wait-ms", type=int, default=30000, help="交接等待上限（毫秒，預設 30000）")
        elif command == "tick":
            p.add_argument("--chain", required=True, help="tick 所屬鏈 id")
            p.add_argument("--seq", required=True, type=int, help="tick 序號（從 1 起）")
        elif command == "add":
            for key, help_text in (("name", "行程名稱"), ("pool", "工作池"), ("dir-target", "資料夾內的 inst 路徑")):
                p.add_argument("--" + key, help=help_text)
            for key, help_text in (("interval-ms", "反覆執行間隔（毫秒）"),
                                   ("timeout-ms", "工作逾時（毫秒）"), ("wait-ms", "等待回音上限（毫秒）")):
                p.add_argument("--" + key, type=int, help=help_text)
            p.add_argument("--once", action="store_true", help="只執行一次；--wait-ms 可等回音")
    return parser


def _cli_request(args, trailing):
    home = Path(args.home).absolute()
    name = aos_client.new_name("cli")
    params = {"name": args.name} if args.command == "rm" else {"target": os.path.abspath(args.inst), "once": args.once}
    if args.command == "add":
        for key in ("name", "pool", "dir_target", "interval_ms", "timeout_ms"):
            value = getattr(args, key)
            if value is not None:
                params[key] = value
        if args.once and "name" not in params:
            params["name"] = name
        if trailing is not None:
            params["args"] = trailing
    aos_client.submit(home, args.command, params, name=name)
    path = home / "responses" / name
    if args.command == "add" and args.once and args.wait_ms is None:
        print("%s %s" % (name, path))
        return 0
    wait_ms = args.wait_ms if args.command == "add" and args.wait_ms is not None else 10000
    try:
        response = aos_client.wait_response(home, name, timeout_ms=wait_ms, poll_ms=5)
    except aos_client.ClientError:
        print(path)
        raise
    aos_client.ack(home, name)
    if "error" in response:
        error = response["error"]
        raise KernelError(error.get("data", {}).get("code", str(error["code"])), error["message"])
    if args.command == "add" and args.once:
        print(json.dumps(response["result"], ensure_ascii=False))
    else:
        print(response["result"]["name"])
    return 0


def _run(args, trailing):
    if args.command == "init":
        if not args.config:
            raise CLIUsage("init 要給 --config FILE：一份 JSON，就是 info.json 要寫的那幾格（cpus 必填），"
                           "例：" + CONFIG_EXAMPLE)
        config = aos_home.read_json(Path(args.config))
        print("initialized " + init(args.home, config=config))
        return 0
    if args.command == "check":
        from aos_kernel_check import check
        for key in ("agent", "daemon_target"):
            values = getattr(args, key)
            if values is not None and len(values) > 1:
                raise CLIUsage("--%s 只能給一次；要查多個請分開跑 check" % key.replace("_", "-"))
            setattr(args, key, values[0] if values else None)
        if args.daemon_target == "":
            raise CLIUsage("--daemon-target 不可為空")
        return check(args.home, args.agent, args.daemon_target, note=args.note)
    if args.command == "halt":
        return stop(args.home, args.wait_ms, args.no_wait)
    if args.command == "boot":
        if args.daemon_target == "":
            raise CLIUsage("--daemon-target 不可為空")
        return boot(args.home, args.daemon_target, args.wait_ms)
    if args.command == "tick":
        return tick(args.home, args.chain, args.seq)
    if args.command == "ls":
        snapshot = status(args.home)
        print(_summary(args.home, snapshot, as_json=args.json))
        return 0
    if args.command == "ack":
        name = Path(args.name).name
        path = Path(args.home) / "responses" / name
        if not path.is_file():
            raise KernelError("NotFound", "回音不存在：%s" % path)
        aos_client.ack(args.home, name)
        return 0
    return _cli_request(args, trailing)


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    trailing = None
    if "--" in values:
        pos = values.index("--")
        values, trailing = values[:pos], values[pos + 1:]
    note = ""
    try:
        args = _parser().parse_args(values)
        if trailing is not None and args.command != "add":
            raise CLIUsage("只有 add 能帶 -- ARG...")
        if args.target == "":
            raise CLIUsage("--target 不可為空")
        for key in ("wait_ms", "interval_ms", "timeout_ms", "seq"):
            value = getattr(args, key, None)
            if value is not None and value < (1 if key == "seq" else 0):
                raise CLIUsage("%s 不在合法範圍" % key)
        home, source = aos_home.resolve_target(args.target, ENV)
        args.home = str(home)
        note = args.note = aos_home.target_note("K", home, source, ENV)
        return _run(args, trailing)
    except aos_home.HomeError as exc:
        usage = isinstance(exc, CLIUsage)
        sys.stderr.write("aos-kernel: %s: %s%s\n" % (exc.code, exc.msg.replace("\n", " "), "" if usage else note))
        return 2 if usage else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        sys.stderr.write("aos-kernel: IOFailed: %s%s\n" % (str(exc).replace("\n", " "), note))
        return 1
