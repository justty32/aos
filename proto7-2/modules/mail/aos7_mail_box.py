"""辦結日誌、歸檔與只讀自身信箱的輪詢。"""
from contextlib import contextmanager
from pathlib import Path
import os
import re
from aos7_mail import (inbox, name, load, letters, letter, send, team_of,
                       validate_reply, TERMINAL, locked, write_json, test_point)
from aos7_mail_ack import ack, event_ack


def finish(root, me, path, journal):
    for reply in journal['replies']:
        send(root, me, **reply)
    test_point('mail.after_reply')
    with locked(str(path.parent / '.delivery')):
        target = path.parent / 'done' / path.name
        target.parent.mkdir(exist_ok=True)
        if path.exists():
            n = 0
            while True:
                try:
                    os.link(path, target)
                    break
                except FileExistsError:
                    if letter(target)['id'] == journal['id']:
                        break
                    n += 1
                    stamp, _, tail = path.name.partition('-')
                    target = target.parent / f"{stamp.split('_')[0]}_{n}-{tail}"
            path.unlink()


def complete(root, me, path, status=None, title=None, body='', handler=None):
    if status is not None and status not in TERMINAL:
        raise ValueError('辦結 STATUS 必須是終局狀態。只能是 DONE、BLOCKED、NEEDS-USER、FAILED')
    l = letter(path)
    jp = path.parent / '.handled' / (l['id'] + '.json')
    journal = load(jp)
    if journal is None:
        if handler:
            status, title, body = handler(l)
        replies = []
        if l['status'] == 'REQUEST':
            if status not in TERMINAL or not title:
                raise ValueError(f"這封是請求（REQUEST），辦完要給一句結論回給寄件人。例：done {me} <序號> '做完了'")
            validate_reply(status, title, body)
            reply_to = l.get('reply-to') or l['from']
            to = l['from'] if '/' not in reply_to else Path(reply_to).parent.name
            name(to)
            destinations = [to]
            team = team_of(root, me)
            if team and team[1] != to:
                destinations.append(team[1])
            replies = [dict(to=d, status=status, title=title, body=body, re_id=l['id'],
                            ident=f"re-{l['id']}-{status}") for d in destinations]
        journal = {'id': l['id'], 'replies': replies}
        write_json(str(jp), journal)
        test_point('mail.after_journal')
    finish(root, me, path, journal)


def done(root, me, filename, status=None, title=None, body=''):
    name(me)
    box = inbox(root, me)
    with locked(str(box / '.handle')):
        if filename.isdecimal():
            snapshot = load(box / '.numbers.json', {})
            ident = snapshot.get(str(int(filename)))
            if ident is None:
                raise ValueError(f'序號 {filename} 不在最近一次 read 的清單裡。請先 read {me} 再用它列的序號'
                                 '（序號只認你看過的清單，避免辦到剛到、還沒看過的信）')
            path = next((p for p in letters(box, True) if letter(p)['id'] == ident), None)
            if path is None:
                raise ValueError(f'找不到這封信。先 read {me} 看清單，再給它列的序號')
        else:
            path = next((p for p in letters(box, True)
                         if p.name == filename or letter(p)['id'] == filename), None)
            if path is None:
                raise ValueError(f'找不到這封信。先 read {me} 看清單，再給它列的序號')
        l = letter(path)
        if path.parent == box:
            complete(root, me, path, status, title, body)
        ack(root, me)  # finish 不 ack；一批做完才確認一次
        journal = load(box / '.handled' / (l['id'] + '.json'), {})
        return {'file': path.name, 'already': path.parent != box, 'to': [r['to'] for r in journal.get('replies', [])],
                'status': next((r['status'] for r in journal.get('replies', [])), None)}


def handle(root, me, handler):
    name(me)
    box = inbox(root, me)
    with locked(str(box / '.handle')):
        for path in letters(box):
            complete(root, me, path, handler=handler)
        ack(root, me)


@contextmanager
def poll(root, me, quiet=False):
    name(me)
    box = inbox(root, me)
    output, updates = [], {}
    with locked(str(box / '.handle')):
        seen_mail = set(load(box / '.seen', []))
        number = 0
        for path in letters(box):
            l = letter(path)
            jp = box / '.handled' / (l['id'] + '.json')
            journal = load(jp)
            if journal is not None:
                finish(root, me, path, journal)
                output.append({'type': 'recovered', 'file': str(path), 'title': l['title']})
            else:
                number += 1
                if not quiet or l['id'] not in seen_mail:
                    output.append(dict(l, type='mail', number=number))
                seen_mail.add(l['id'])
        updates[box / '.numbers.json'] = {str(l['number']): l['id'] for l in output if l['type'] == 'mail'}
        updates[box / '.seen'] = sorted(seen_mail)
        ack(root, me)
        team = team_of(root, me)
        seenpath = box / '.seen-team'
        seen = set(load(seenpath, []))
        if team:
            for path in letters(inbox(root, 'team:' + team[0])):
                l = letter(path)
                if l['id'] not in seen:
                    output.append(dict(l, type='team'))
                    seen.add(l['id'])
            updates[seenpath] = sorted(seen)
        orders = box / 'orders' / f'{me}.md'
        if orders.exists():
            data = orders.read_bytes()
            offset = load(box / '.orders-offset', 0)
            if offset > len(data):
                raise ValueError('orders 被截短。請恢復成只追加的原檔再 read')
            if len(data) > offset:
                for part in re.split(r'(?m)(?=^## )', data[offset:].decode('utf-8')):
                    if part.strip():
                        output.append({'type': 'orders', 'file': str(orders), 'title': part.strip()})
                updates[box / '.orders-offset'] = len(data)
        yield output
        test_point('mail.before_seen_commit')
        for path, value in updates.items():
            write_json(str(path), value)

