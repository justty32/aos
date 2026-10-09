"""CLI 參數與白話輸出；郵局邏輯見 aos7_mail。"""
import argparse
import json
import os
from pathlib import Path
import sys
from aos7_mail import send, done, poll, audit, roster, team, test_point, STATUSES, Refused

from aos7_mail_help import HELP, SUB_HELP


def output(rows, as_json=False, quiet=False):
    if as_json:
        if rows or not quiet:
            print(json.dumps(rows, ensure_ascii=False))
    else:
        for row in rows:
            prefix = str(row['number']) if row['type'] == 'mail' else {
                'team': '團隊', 'orders': '指示', 'audit': '等回信', 'recovered': '復原'}[row['type']]
            detail = row['title'].splitlines()[0] if row['type'] == 'orders' else Path(row['file']).name + '  ' + row['title']
            print(prefix + '  ' + detail)
        if not rows and not quiet:
            print('（沒有新信）')
    test_point('mail.before_output_flush')
    sys.stdout.flush()


EXAMPLE = {'send': "aos7-mail send alice bob '請檢查'", 'read': 'aos7-mail read bob', 'done': "aos7-mail done bob 1 '做完了'",
           'audit': 'aos7-mail audit alice', 'team': 'aos7-mail team dev lead bob',
           'roster': "aos7-mail roster alice --who 寄件者 --up chief --territory 我的夾 --can 寄信 --cannot 驗身份"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('用法錯誤：' + message)


def _main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    words = [w for w in argv if w not in ('-h', '--help')]
    if argv[:1] == ['help']:
        words = argv[1:]
    if not argv or len(words) < len(argv) or argv[:1] == ['help']:
        cmd = next((w for w in words if w in SUB_HELP), None)
        print(SUB_HELP[cmd] if cmd else HELP, file=sys.stdout if argv else sys.stderr)
        if argv:
            sys.stdout.flush()
        return 0 if argv else 2
    try:
        # --up 是 send 的位置參數；--root 可放指令前或後。
        root = os.environ.get('AOS_MAIL_ROOT')
        if '--root' in argv:
            i = argv.index('--root')
            root = argv[i + 1]
            del argv[i:i + 2]
        if argv and argv[0] not in SUB_HELP:
            raise ValueError(f'沒有 {argv[0]} 這個指令。日常用 send／read／done，例：aos7-mail send alice bob \'請檢查\'')
        if not root:
            raise ValueError('還沒指定郵局資料夾。先 export AOS_MAIL_ROOT=<資料夾>，或加 --root <資料夾>（用法見 aos7-mail --help）')
        root = str(Path(root).absolute())
        if len(argv) > 2 and argv[0] == 'send' and argv[2] == '--up':
            argv[2] = '__up__'
        # 省略 STATUS：send 預設 REQUEST；done 只給一句話時預設 DONE。
        if argv and argv[0] == 'send':
            pos = [i for i, w in enumerate(argv) if i and not w.startswith('--')
                   and argv[i - 1] != '--re']
            if len(pos) >= 3 and argv[pos[2]] not in STATUSES:
                argv.insert(pos[2], 'REQUEST')
        if argv and argv[0] == 'done' and len(argv) == 4 and argv[3] not in STATUSES:
            argv.insert(3, 'DONE')
        ap = Parser()
        sub = ap.add_subparsers(dest='cmd', required=True, parser_class=Parser)
        for cmd in ('send', 'read', 'done', 'audit', 'roster', 'team'):
            p = sub.add_parser(cmd)
            p.add_argument('me', nargs='?' if cmd == 'audit' else None)
            if cmd == 'send':
                p.add_argument('to'); p.add_argument('status'); p.add_argument('title'); p.add_argument('body', nargs='?'); p.add_argument('--re', default='')
            if cmd == 'done':
                p.add_argument('file'); p.add_argument('status', nargs='?'); p.add_argument('title', nargs='?'); p.add_argument('body', nargs='?')
            if cmd in ('read', 'audit'):
                p.add_argument('--json', action='store_true'); p.add_argument('--quiet', action='store_true')
            if cmd == 'roster':
                for flag in ('who', 'up', 'territory', 'can', 'cannot'):
                    p.add_argument('--' + flag, required=True)
                p.add_argument('--team')
            if cmd == 'team':
                p.add_argument('leader'); p.add_argument('members', nargs='*')
        a = ap.parse_args(argv)
        body = Path(a.body).read_text() if getattr(a, 'body', None) else ''
        if a.cmd == 'send':
            print(json.dumps(send(root, a.me, '--up' if a.to == '__up__' else a.to, a.status, a.title, body, a.re)))
        elif a.cmd == 'done':
            result = done(root, a.me, a.file, a.status, a.title, body)
            if result['already']:
                print('已辦結過 ' + result['file'])
            elif result['to']:
                print(f"已辦結 {result['file']}，已回 {result['status']} 給 {', '.join(result['to'])}")
            else:
                print('已歸檔 ' + result['file'])
        elif a.cmd in ('read', 'audit'):
            if a.cmd == 'read':
                with poll(root, a.me, a.quiet) as rows:
                    output(rows, a.json, a.quiet)
            else:
                rows = audit(root, a.me)
                output(rows, a.json, a.quiet if a.json else True)
            return int(a.cmd == 'audit' and bool(rows))
        elif a.cmd == 'roster':
            roster(root, a.me, a.who, a.up, a.territory, a.can, a.cannot, a.team)
        else:
            team(root, a.me, a.leader, a.members)
        sys.stdout.flush()
        return 0
    except (ValueError, KeyError, IndexError) as e:
        msg = ' '.join(str(e).splitlines())
        usage = SUB_HELP[argv[0]].splitlines()[0] if argv and argv[0] in SUB_HELP else 'aos7-mail send alice bob \'請檢查\''
        if msg.startswith('用法錯誤'):
            msg = f'{argv[0] if argv else ""} 的參數不對。用法：{usage}，例：{EXAMPLE.get(argv[0] if argv else "", EXAMPLE["send"])}'
        elif isinstance(e, IndexError):
            msg = '--root 後面少了郵局資料夾。例：aos7-mail --root /tmp/post read alice'
        elif isinstance(e, KeyError):
            msg = f'信缺少必要欄位 {msg}。信檔要照 ADVANCED.md 的格式，請用 send 寄'
        elif '。' not in msg:
            msg += '。用法見 aos7-mail --help'
        print('aos7-mail: ' + msg, file=sys.stderr)
        return 1 if isinstance(e, Refused) else 2

def main(argv=None):
    try:
        return _main(argv)
    except OSError as e:
        msg = " ".join(str(e).splitlines())
        print(f"aos7-mail: 不確定：讀寫檔案或輸出時出錯（{msg}），這次可能只做了一半，已寫下的信與狀態都留著。照原樣再跑一次會接續", file=sys.stderr)
        try:  # 輸出壞了：丟掉沒寫出去的，免得結束時再炸一次、退出碼變 120
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        return 3
