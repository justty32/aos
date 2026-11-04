"""參數、錯誤與公開入口分派。"""
import argparse
import math
import os
from pathlib import Path
import re
import signal
import sys

from aos7_up import up, stop
from aos7_up_status import status, UpError, BEAT_MS

HELP = """用法：
  aos7-up <node>                起 node；開著別關，停＝按 Ctrl-C
  aos7-up ask <node> '一句話'    另開視窗寄信給它，等回信（最多 60 秒）
  aos7-up status <node>         看它現在怎樣
例：aos7-up /tmp/aos/bob
更多（真 AI、背景跑、停）見 proto7-2/modules/up/ADVANCED.md"""


def show_help(argv):
    if any(arg in ('-h', '--help') for arg in argv):
        print(HELP)
        return True
    return False


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, command='up', **kwargs):
        super().__init__(*args, **kwargs)
        self.command = command

    def error(self, message):
        examples = {
            'up': ('參數不對，起 node 只要給資料夾', 'aos7-up /tmp/aos/bob'),
            'ask': ('ask 要 node 和一句話', "aos7-up ask /tmp/aos/bob '一句話'"),
            'brain': ('brain 只能由心跳起', 'aos7-up /tmp/aos/bob'),
            'status': ('status 要 node', 'aos7-up status /tmp/aos/bob'),
            'stop': ('stop 要 node', 'aos7-up stop /tmp/aos/bob'),
        }
        why, example = examples[self.command]
        self.exit(2, f'aos7-up: {why}。例如 {example}\n')


def beat(args):
    """--interval 秒、--early／--fixed → up.json 的節拍欄（沒給的不放，沿用舊值）。壞值退 2、什麼都沒動。"""
    out = {}
    if args.early and args.fixed:
        raise UpError(2, '--early 和 --fixed 只能選一個。例如 aos7-up /tmp/aos/bob --early')
    if args.early or args.fixed:
        out['early_tock'] = bool(args.early)
    if args.interval is not None:
        try:
            seconds = float(args.interval)
        except ValueError:
            seconds = None
        if seconds is None or not math.isfinite(seconds) or \
                not BEAT_MS[0] <= round(seconds * 1000) <= BEAT_MS[1]:
            raise UpError(2, f'--interval 要是 0.01 到 86400 之間的秒數，拿到 {args.interval[:40]!r}。'
                             '例如 aos7-up /tmp/aos/bob --interval 0.5')
        out['interval_ms'] = round(seconds * 1000)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if show_help(argv):
        return 0
    sub = argv.pop(0) if argv and argv[0] in ('ask', 'brain', 'status', 'stop') else 'up'
    if sub in ('ask', 'brain'):
        import aos7_up_brain
        return aos7_up_brain.main([sub, *argv])
    parser = Parser(command=sub)
    parser.add_argument('node')
    if sub == 'up':
        parser.add_argument('--model', help=argparse.SUPPRESS)
        parser.add_argument('-d', action='store_true', help=argparse.SUPPRESS)
        parser.add_argument('--interval', help=argparse.SUPPRESS)
        parser.add_argument('--early', action='store_true', help=argparse.SUPPRESS)
        parser.add_argument('--fixed', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    node = Path(os.path.abspath(args.node))
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)  # 背景啟動的 shell 會把 SIGINT 設成忽略；前景要收得到
    try:
        if not re.fullmatch(r'[A-Za-z0-9._-]+', node.name) or node.name.startswith('.') or node.name == 'you':
            raise UpError(2, 'node 名只准英數、點、底線、短橫線，不能以點開頭，you 留給人。請換名字，例如 aos7-up /tmp/aos/bob')
        if sub == 'status':
            return status(node)
        if sub == 'stop':
            return stop(node)
        return up(node, args.model, args.d, beat(args))
    except KeyboardInterrupt:
        print('aos7-up: 不確定：裝到一半被中斷，已裝的留著。照原樣再跑一次會接續', file=sys.stderr)
        return 3
    except UpError as error:
        detail = ' '.join(str(error).splitlines())
        print(f'aos7-up: {detail}', file=sys.stderr)
        return error.code
    except Exception as error:
        detail = ' '.join(str(error).splitlines())
        print(f'aos7-up: 不確定：{detail}，已裝的留著。照原樣再跑一次會接續', file=sys.stderr)
        return 3
