"""CLI 參數與白話輸出；郵局邏輯見 aos7_mail。"""
import argparse
import json
import os
from pathlib import Path
import sys
from aos7_mail import send, done, poll, audit, roster, team, test_point


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


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('用法錯誤：' + message)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        # --up 是 send 的位置參數；--root 可放指令前或後。
        root = os.environ.get('AOS_MAIL_ROOT')
        if '--root' in argv:
            i = argv.index('--root')
            root = argv[i + 1]
            del argv[i:i + 2]
        if not root:
            raise ValueError('請設定 --root 或 AOS_MAIL_ROOT')
        root = str(Path(root).absolute())
        if len(argv) > 2 and argv[0] == 'send' and argv[2] == '--up':
            argv[2] = '__up__'
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
            if result['to']:
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
        return 0
    except (ValueError, OSError, KeyError, IndexError) as e:
        print(str(e).replace('\n', ' '), file=sys.stderr)
        return 2
