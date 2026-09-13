#!/usr/bin/env python3
"""llm-cpu：資料夾型 LLM 請求佇列的命令列入口。"""
import argparse
import sys

import llm_cpu_home as home
import llm_cpu_tick as ticker
import llm_cpu_worker as worker


def _parser():
    parser = argparse.ArgumentParser(
        prog="llm-cpu", description="收 LLM 請求、排序，再分發給 endpoint")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="建立一個 llm-cpu 家")
    init.add_argument("dir")

    tick = commands.add_parser("tick", help="跑一格排程")
    tick.add_argument("dir", nargs="?", default=".")

    submit = commands.add_parser("submit", help="投入一份 JSON 請求")
    submit.add_argument("paths", nargs="+", metavar="PATH")
    submit.add_argument("--name", help="指定 request id")

    listing = commands.add_parser("ls", help="看 endpoint 與佇列")
    listing.add_argument("dir", nargs="?", default=".")

    internal = commands.add_parser("worker", help=argparse.SUPPRESS)
    internal.add_argument("dir")
    internal.add_argument("id")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "init":
        return home.init_home(args.dir)
    if args.command == "tick":
        # tick 是服務的一格；內部再壞也不能用退出碼殺死普通 cpu。
        try:
            ticker.tick(args.dir)
        except BaseException as exc:
            home.emergency_tick_log(args.dir, exc)
        return 0
    if args.command == "submit":
        if len(args.paths) == 1:
            directory, source = ".", args.paths[0]
        elif len(args.paths) == 2:
            directory, source = args.paths
        else:
            _parser().error("submit 要 REQ.json，或 DIR REQ.json")
        return home.submit(directory, source, args.name)
    if args.command == "ls":
        return home.show(args.dir)
    if args.command == "worker":
        return worker.run(args.dir, args.id)
    return 2


if __name__ == "__main__":
    sys.exit(main())
