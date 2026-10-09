"""CLI 參數與白話輸出；郵局邏輯見 aos7_mail。"""
import argparse
import json
import os
from pathlib import Path
import sys
from aos7_mail import send, done, poll, audit, roster, team, test_point, STATUSES

HELP = """aos7-mail：用檔案寄信的小郵局。
先指定郵局資料夾：export AOS_MAIL_ROOT=<資料夾>（或每個指令加 --root <資料夾>）。

日常三個指令：
  aos7-mail send  <我> <對象> '<一句話>'    寄一個請求（REQUEST）給對象
  aos7-mail read  <我>                      看我的信，每封前面有序號
  aos7-mail done  <我> <序號> ['<一句話>']  辦完這封：歸檔；若是請求，自動回 DONE 給寄件人

例：
  export AOS_MAIL_ROOT=$(mktemp -d)
  aos7-mail send alice bob '請 bob 檢查範例'
  aos7-mail read bob
  aos7-mail done bob 1 '檢查完了'
  aos7-mail read alice

各指令細節：aos7-mail <指令> --help。
進階指令 audit（查整個郵局未辦請求）、roster、team，及其他狀態，見 ADVANCED.md。
退出碼：0 成功；2 用法或檔案錯誤（stderr 一行說明）；audit 找到未辦請求時退出 1。"""

SUB_HELP = {
    'send': """aos7-mail send <我> <對象> '<一句話>' [正文檔]
  寄一個請求給 <對象>；對方用 read 看、用 done 辦完後你會收到 DONE 回信。
  成功印一行 JSON：{"sent": 信檔路徑, "id": 信id}。
進階：aos7-mail send <我> <對象|--up|team:<隊>> <STATUS> '<一句話>' [正文檔] [--re <請求id>]
  STATUS 可為 REQUEST PROGRESS DONE BLOCKED NEEDS-USER FAILED，見 ADVANCED.md。""",
    'read': """aos7-mail read <我> [--quiet] [--json]
  列出我的未辦信：<序號>  <檔名>  <一句話>。序號給 done 用。
  沒有信印「（沒有新信）」。--quiet 只報新的、沒東西就不印；--json 印 JSON 陣列。""",
    'done': """aos7-mail done <我> <序號> ['<一句話>']
  辦完 read 列出的第 <序號> 封：搬進 done/ 歸檔。
  若那封是請求（REQUEST），必須給一句結論，會自動回 DONE 給寄件人。
  序號只認最近一次 read 的清單（避免辦到你沒看過、剛到的新信）；也可給信檔名或信 id。
進階：aos7-mail done <我> <序號> <DONE|BLOCKED|NEEDS-USER|FAILED> '<一句話>' [正文檔]""",
    'audit': """（進階）aos7-mail audit [<我>] [--json]
  查還有沒有寄出卻沒人辦完的請求。沒有就退出 0；有就列出並退出 1。
  給 <我> 只看跟我有關的。""",
    'roster': """aos7-mail roster <我> --who W --up U --territory T --can C --cannot X [--team 隊]
  （進階）在我的 ROSTER 加一格身份，之後 send <我> --up 會寄給 U。見 ADVANCED.md。""",
    'team': """aos7-mail team <隊名> <領導> [成員...]
  （進階）建立團隊；成員可用 send <我> team:<隊名> PROGRESS '...' 廣播。見 ADVANCED.md。""",
}


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
    words = [w for w in argv if w not in ('-h', '--help')]
    if argv[:1] == ['help']:
        words = argv[1:]
    if not argv or len(words) < len(argv) or argv[:1] == ['help']:
        cmd = next((w for w in words if w in SUB_HELP), None)
        print(SUB_HELP[cmd] if cmd else HELP, file=sys.stdout if argv else sys.stderr)
        return 0 if argv else 2
    try:
        # --up 是 send 的位置參數；--root 可放指令前或後。
        root = os.environ.get('AOS_MAIL_ROOT')
        if '--root' in argv:
            i = argv.index('--root')
            root = argv[i + 1]
            del argv[i:i + 2]
        if argv and argv[0] not in SUB_HELP:
            raise ValueError(f'沒有 {argv[0]} 這個指令；日常用 send／read／done（見 aos7-mail --help）')
        if not root:
            raise ValueError('還沒指定郵局資料夾：先 export AOS_MAIL_ROOT=<資料夾>，或加 --root <資料夾>（用法見 aos7-mail --help）')
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
        return 0
    except (ValueError, OSError, KeyError, IndexError) as e:
        msg = str(e).replace('\n', ' ')
        if msg.startswith('用法錯誤') and argv and argv[0] in SUB_HELP:
            msg = f'用法錯誤：{argv[0]} 的參數不對；用法：' + SUB_HELP[argv[0]].splitlines()[0]
        print(msg, file=sys.stderr)
        return 2
