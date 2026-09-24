"""kernel 命令列的參數解析、請求投遞與摘要輸出。"""
import argparse
import json
import os
from pathlib import Path
import sys

import aos_client
import aos_home
from aos_kernel_boot import boot, status, stop
from aos_kernel_engine import tick
from aos_kernel_info import CONFIG_EXAMPLE, CLIUsage, KernelError, init, load_info
from aos_kernel_ls import ls_data, render

ENV = "AOS_KERNEL_HOME"


def _summary(home, snapshot, as_json=False, verbose=False, pool=None, procs=False):
    """ls 的輸出（advice-r1）：--json 是 ls_data() 那份穩定 schema，文字版是對齊的表；池式（proto5-2 納入）多 --pool／--procs。"""
    data = ls_data(home, snapshot, pool=pool)
    if data["health"]["code"] == "broken":  # astra 必修 5：讀不到就退 1、stdout 空（cli-ls.md）
        raise KernelError("ReadFailed", data["health"]["message"])
    return json.dumps(data, ensure_ascii=False) if as_json else render(data, verbose=verbose, procs=procs)


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        # 不收縮寫：舊的 --daemon 不能被當成 --daemon-target 的縮寫悄悄吃掉。
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        raise CLIUsage(message)


TARGET_HELP = "kernel 家（省略＝AOS_KERNEL_HOME，再沒有就目前資料夾）"
DAEMON_HELP = "再多查一個 daemon 家（池表裡提到的 daemon 家一律會查）"
INIT_EPILOG = ("--config 是一份 JSON，就是 info.json 要寫的那幾格：kernel 參數＋pools 池表，工作池可以一個都沒有"
               "（kernel 池沒寫就補 {\"count\": 1}）。沒給 --config＝只有 kernel 池，之後用 aos-kernel cpu add 加池。例：\n  "
               + CONFIG_EXAMPLE)
CPU_EPILOG = ("cpu add／rm 只改 K/info.json 的池表，不放單、不用 boot：kernel 在跑就下一格照新數字做，沒在跑就下次 boot 生效。\n"
              "例：\n  aos-kernel cpu add --pool default --count 4\n"
              "  aos-kernel cpu add --pool llm --env AOS_LLM_CONFIG=/abs/llm.json\n"
              "  aos-kernel cpu rm default/3            # 永久退休 3 號（寫進 skip）\n"
              "  aos-kernel cpu rm --pool default --count 2   # 收最大的 2 號\n"
              "  aos-kernel cpu ls --pool default")


def _cpu_parser(subs):
    description = "增減與查看 cpu 池（改 K/info.json 的 pools）"
    p = subs.add_parser("cpu", help=description, description=description, epilog=CPU_EPILOG,
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    cpu = p.add_subparsers(dest="cpu_command", required=True, parser_class=_Parser, metavar="{add,rm,ls}")
    add = cpu.add_parser("add", help="加池或加 count", description="池不在就新增，在就把 count 加 N；下一格（或下次 boot）生效",
                         usage="aos-kernel cpu add [--target K] --pool P [--count N] [--env KEY=VALUE]... [--daemon D] [--dpool NAME]")
    add.add_argument("--pool", metavar="P", required=True, help="池名（不能是 kernel）")
    add.add_argument("--count", metavar="N", type=int, help="加幾顆（省略＝1）")
    add.add_argument("--env", metavar="KEY=VALUE", action="append", help="新池的環境變數（字面字串，可重複；既有池不收）")
    add.add_argument("--daemon", metavar="D", help="新池交給哪個 daemon 家（省略＝info 頂層的 daemon）")
    add.add_argument("--dpool", metavar="NAME", help="新池在 daemon 那邊的名字（省略＝池名）")
    rm = cpu.add_parser("rm", help="退休一顆或收掉幾顆", description="P/<i>＝永久退休那一號（寫進 skip）；--pool P --count N＝收最大的 N 號。"
                        "手上有工作的做完才真的收",
                        usage="aos-kernel cpu rm [--target K] (P/<i> | --pool P --count N)")
    rm.add_argument("name", metavar="P/<i>", nargs="?", help="要永久退休的那顆")
    rm.add_argument("--pool", metavar="P", help="池名")
    rm.add_argument("--count", metavar="N", type=int, help="收幾顆（正整數）")
    ls = cpu.add_parser("ls", help="一池一行；--pool 再一顆一行", description="一池一行（帳本＋daemon 的 summary.json）；--pool P 再一顆一行",
                        usage="aos-kernel cpu ls [--target K] [--pool P] [--json]")
    ls.add_argument("--pool", metavar="P", help="只看這池，並一顆一行")
    ls.add_argument("--json", action="store_true", help="輸出 JSON")
    for sub in (add, rm, ls):
        sub.add_argument("--target", metavar="K", help=TARGET_HELP)


def _parser():
    parser = _Parser(prog="aos-kernel", description="管理 kernel 家、cpu 池與排程行程；K 一律用 --target 給")
    subs = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    descriptions = {"init": "建立 kernel 家（照 --config 寫 info.json）", "boot": "交接並啟動 kernel 池與 tick 鏈",
                    "cpu": None, "tick": "執行一格排程（鏈自己會叫）", "add": "登記工作", "rm": "移除行程",
                    "wake": "叫醒停車中的行程（下一格就能派）",
                    "ls": "顯示健康、按池摘要與行程", "halt": "要求 kernel 停機並等停好", "ack": "確認已收回音",
                    "check": "啟動前檢查 kernel 的設定與執行環境（agent 的用 aos-agent check）"}
    for command, description in descriptions.items():
        if command == "cpu":
            _cpu_parser(subs)
            continue
        p = subs.add_parser(command, help=description, description=description,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
        if command == "add":
            p.add_argument("inst", metavar="INST", help="要執行的目標（inst.json、資料夾或普通檔）；-- ARG... 傳入目標參數")
        elif command in ("rm", "ack", "wake"):
            p.add_argument("name", help="回音檔名或路徑" if command == "ack" else "行程名稱")
        p.add_argument("--target", metavar="K", help=TARGET_HELP)
        if command == "init":
            p.usage = "aos-kernel init [--target K] [--config FILE] [--daemon D]"
            p.epilog = INIT_EPILOG
            p.add_argument("--config", metavar="FILE", help="info 設定檔（JSON）；省略＝只有 kernel 池")
            p.add_argument("--daemon", metavar="D", help="預設的 daemon 家（省略＝config 裡的，再沒有就 AOS_DAEMON_HOME）")
        elif command == "check":
            # advice-r1：agent 的檢查搬到 aos-agent check；舊旗標只為了給清楚的錯誤訊息。
            p.add_argument("--agent", action="append", nargs="?", const="DIR", help=argparse.SUPPRESS)
            p.add_argument("--daemon-target", action="append", metavar="D", help=DAEMON_HELP)
            p.add_argument("--probe", action="store_true", help="真的對 llm.json 的每個 endpoint 打一次最小請求")
        elif command == "halt":
            p.add_argument("--wait-ms", type=int, default=30000, help="停機等待上限（毫秒，預設 30000）")
            p.add_argument("--no-wait", action="store_true", help="只放 stop 單，不等待、不輸出")
        elif command == "ls":
            p.usage = "aos-kernel ls [--target K] [--pool P] [--procs] [--json] [-v]"
            p.add_argument("--pool", metavar="P", help="只看這池的 cpu（一顆一行）與行程")
            p.add_argument("--procs", action="store_true", help="每個行程一行（預設只印各狀態數量，與 bad／暫停／重試中的）")
            p.add_argument("--json", action="store_true", help="印一個 JSON 物件（欄位穩定，見 spec kernel/cli-ls.md）")
            p.add_argument("-v", "--verbose", action="store_true", help="多印 K、D、chain、行程全名與 target")
        elif command == "boot":
            p.add_argument("--wait-ms", type=int, default=30000, help="交接等待上限（毫秒，預設 30000）")
        elif command == "tick":
            p.add_argument("--chain", required=True, help="tick 所屬鏈 id")
            p.add_argument("--seq", required=True, type=int, help="tick 序號（從 1 起）")
        elif command == "add":
            for key, help_text in (("name", "行程名稱"), ("pool", "工作池（省略＝default；池要先 aos-kernel cpu add）"),
                                   ("dir-target", "資料夾內的 inst 路徑")):
                p.add_argument("--" + key, help=help_text)
            for key, help_text in (("interval-ms", "反覆執行間隔（毫秒）"),
                                   ("timeout-ms", "工作逾時（毫秒）"), ("park-ms", "退 102 停車後最晚多久再派（毫秒）"),
                                   ("wait-ms", "等待回音上限（毫秒）")):
                p.add_argument("--" + key, type=int, help=help_text)
            p.add_argument("--once", action="store_true", help="只執行一次；--wait-ms 可等回音")
    return parser


def _cli_request(args, trailing):
    home = Path(args.home).absolute()
    name = aos_client.new_name("cli")
    params = {"name": args.name} if args.command in ("rm", "wake") else {"target": os.path.abspath(args.inst), "once": args.once}
    if args.command == "add":
        for key in ("name", "pool", "dir_target", "interval_ms", "timeout_ms", "park_ms"):
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
        data = error.get("data") if isinstance(error.get("data"), dict) else {}
        message = error["message"]
        if args.command == "add" and data.get("position") == ["params", "pool"]:
            message += "（池 %s 不在 info.json 的 pools；先 aos-kernel cpu add --target %s --pool %s）" % (
                params.get("pool", "default"), home, params.get("pool", "default"))
        raise KernelError(data.get("code", str(error["code"])), message)
    if args.command == "add" and args.once:
        print(json.dumps(response["result"], ensure_ascii=False))
    else:
        print(response["result"]["name"])
    return 0


def _run(args, trailing):
    if args.command == "init":
        if args.config == "" or args.daemon == "":
            raise CLIUsage("--config／--daemon 不可為空")
        config = aos_home.read_json(Path(args.config)) if args.config else None
        if args.config and config is None:
            # fix-r4（astra 審查）：JSON null 不能落回「沒給 --config」的預設家。
            raise KernelError("FieldTypeMismatch", "--config 的頂層必須是物件（JSON null 不行）")
        print("initialized " + init(args.home, config=config, daemon=args.daemon))
        return 0
    if args.command == "check":
        from aos_kernel_check import check
        if args.agent is not None:
            raise CLIUsage("--agent 搬走了：agent 的檢查改用 aos-agent check --target %s [--probe]"
                           "（K 由 AOS_KERNEL_HOME 或 agent 家的 tick.json 找）" % args.agent[0])
        for key in ("daemon_target",):
            values = getattr(args, key)
            if values is not None and len(values) > 1:
                raise CLIUsage("--%s 只能給一次；要查多個請分開跑 check" % key.replace("_", "-"))
            setattr(args, key, values[0] if values else None)
        if args.daemon_target == "":
            raise CLIUsage("--daemon-target 不可為空")
        return check(args.home, args.daemon_target, note=args.note, probe=args.probe)
    if args.command == "halt":
        return stop(args.home, args.wait_ms, args.no_wait)
    if args.command == "boot":
        code = boot(args.home, args.wait_ms)
        pools = load_info(args.home)["pools"]
        # fix-r5：成功也講一聲
        print("booted %d pools, %d cpus" % (len(pools), sum(p["count"] for p in pools.values())))
        return code
    if args.command == "tick":
        return tick(args.home, args.chain, args.seq)
    if args.command == "ls":
        if args.pool == "":
            raise CLIUsage("--pool 不可為空")
        snapshot = status(args.home)
        print(_summary(args.home, snapshot, as_json=args.json, verbose=args.verbose, pool=args.pool, procs=args.procs))
        return 0
    if args.command == "cpu":
        return _run_cpu(args)
    if args.command == "ack":
        name = Path(args.name).name
        path = Path(args.home) / "responses" / name
        if not path.is_file():
            raise KernelError("NotFound", "回音不存在：%s" % path)
        aos_client.ack(args.home, name)
        return 0
    return _cli_request(args, trailing)


def _run_cpu(args):
    import aos_kernel_cpu
    if args.cpu_command == "add":
        print(aos_kernel_cpu.cpu_add(args.home, args.pool, args.count, args.env, args.daemon, args.dpool))
    elif args.cpu_command == "rm":
        print(aos_kernel_cpu.cpu_rm(args.home, args.name, args.pool, args.count))
    else:
        if args.pool == "":
            raise CLIUsage("--pool 不可為空")
        print(aos_kernel_cpu.cpu_ls(args.home, args.pool, args.json))
    return 0


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
        for key in ("wait_ms", "interval_ms", "timeout_ms", "park_ms", "seq"):
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
