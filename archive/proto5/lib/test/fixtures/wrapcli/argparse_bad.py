"""wrap-cli 的 argparse fixture（該拒收的）：子命令、非字面值、不支援的 type／action、互斥群組、隱藏參數。"""
import argparse
import pathlib

FLAGS = ['--level']
LEVELS = ['a', 'b']


def build():
    p = argparse.ArgumentParser(description='Tool with things wrap-cli cannot read.')
    p.add_argument('--name', help='plain option (accepted)')
    p.add_argument(*FLAGS, help='flags from a variable (rejected)')
    p.add_argument('--kind', choices=LEVELS, help='choices from a variable (rejected)')
    p.add_argument('--where', type=pathlib.Path, help='custom type (rejected)')
    p.add_argument('--yes', type=bool, help='type=bool trap (rejected)')
    p.add_argument('--color', action=argparse.BooleanOptionalAction, help='rejected')
    p.add_argument('--secret', help=argparse.SUPPRESS)
    p.add_argument('--home', default=pathlib.Path.home(), help='default is not literal (accepted, default dropped)')
    g = p.add_mutually_exclusive_group()
    g.add_argument('--fast', action='store_true', help='fast mode')
    g.add_argument('--slow', action='store_true', help='slow mode')
    sub = p.add_subparsers(dest='cmd')
    run = sub.add_parser('run')
    run.add_argument('--times', type=int, help='belongs to a subcommand (rejected)')
    return p


if __name__ == '__main__':
    print(build().parse_args())
