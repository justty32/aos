"""人的信箱固定叫 you；只收這次 REQUEST 的終局回信。"""
import json
from pathlib import Path
import re
import time
from aos7_up_brain import mail, trouble, Parser


def show_body(text, title):
    headings = ('做了什麼', '產出（檔案路徑 / commit / 分支）',
                '沒做到、或證據不足的部分', '需要對方或使用者決定的事')
    parts = re.split(r'(?m)^## (' + '|'.join(map(re.escape, headings)) + r')[ \t]*\r?\n', text)
    for heading, body in zip(parts[1::2], parts[2::2]):
        body = body.strip('\n')
        if heading == '做了什麼':
            if body and not (len(body.splitlines()) == 1 and body == title):
                print(body)
        elif body.strip() and body.strip() != '無':
            print('## ' + heading + '\n' + body)


def main(argv):
    ap = Parser()
    ap.add_argument('cmd', choices=['ask'])
    ap.add_argument('node')
    ap.add_argument('sentence')
    ap.add_argument('--wait', type=float, default=60)
    a = ap.parse_args(argv)
    node = Path(a.node).absolute()
    if not node.is_dir() or not re.fullmatch(r'[A-Za-z0-9._-]+', node.name) or node.name in ('.', '..', 'teams'):
        print(trouble('找不到 node，或名字不能用', '確認 node 路徑再 ask 一次'))
        return 2
    try:
        sent = json.loads(mail(node, 'send', 'you', node.name, 'REQUEST', a.sentence))
        end = time.monotonic() + max(0, a.wait)
        while time.monotonic() < end:
            rows = json.loads(mail(node, 'read', 'you', '--json'))
            for l in rows:
                if l.get('re') != sent['id'] or l.get('status') not in ('DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED'):
                    continue
                print(f"{node.name} 回信（{l['status']}）：{l['title']}")
                show_body(l.get('body', ''), l['title'])
                mail(node, 'done', 'you', l['id'])
                return 0
            time.sleep(min(0.5, max(0, end - time.monotonic())))
        print(trouble(f'{node.name} 還沒回（等了 {a.wait:g} 秒）', f'等一下用 aos7-up status {node} 看'))
        return 0
    except Exception:
        print(trouble('寄信或讀信沒完成', '確認 node 信箱可讀寫，再 ask 一次'))
        return 2
