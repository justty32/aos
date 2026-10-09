"""參數、錯誤與公開入口分派。"""
import argparse
import os
from pathlib import Path
import re
import signal
import sys

from aos7_up import up, stop
from aos7_up_status import status, UpError

class Parser(argparse.ArgumentParser):
    def error(self, message):
        message = ' '.join(message.splitlines())
        self.exit(2, f'aos7-up: {message}。請看 aos7-up --help 的用法，例如 aos7-up /tmp/aos/bob\n')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sub = argv.pop(0) if argv and argv[0] in ('ask', 'brain', 'status', 'stop') else 'up'
    if sub in ('ask', 'brain'):
        import aos7_up_brain
        return aos7_up_brain.main([sub, *argv])
    parser = Parser(description='起 node、看心跳與信；另開 shell 用 ask 問它。',
                                     epilog="問它：aos7-up ask <node> '一句話'；看：aos7-up status <node>；停背景心跳：aos7-up stop <node>")
    parser.epilog += '\n退出：0 做到了、1 做不到、2 參數不對、3 不確定（照原樣再跑會接續）'
    parser._optionals.title = '選項'
    parser._positionals.title = '位置參數'
    parser._actions[0].help = '顯示說明'
    parser.add_argument('node', help='AI 住的資料夾')
    if sub == 'up':
        parser.add_argument('--model', help='使用真的 AI 模型；預設假 AI')
        parser.add_argument('-d', action='store_true', help='讓心跳在背景跑')
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
        return up(node, args.model, args.d)
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
