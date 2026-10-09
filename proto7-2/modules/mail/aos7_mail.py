"""檔案是權威的郵局；events must 只作提醒。"""
import datetime
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'events'), str(HERE.parents[1] / 'lib')]
from aos7_fs import locked, write_json, test_point
from aos7_events_pub import publish
from aos7_events_read import read as events_read

TERMINAL = {'DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED'}
STATUSES = TERMINAL | {'REQUEST', 'PROGRESS'}
HEADINGS = ('做了什麼', '產出（檔案路徑 / commit / 分支）', '沒做到、或證據不足的部分', '需要對方或使用者決定的事')


def name(value):
    if not re.fullmatch(r'[A-Za-z0-9._-]+', value) or value in ('.', '..', 'teams'):
        raise ValueError('名字只准英數字、點、底線、短橫線，不能使用保留名')
    return value


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def inbox(root, who):
    if who.startswith('team:'):
        return Path(root) / 'teams' / name(who[5:]) / 'inbox'
    return Path(root) / name(who) / 'inbox'


def letters(box, done=False):
    paths = sorted(box.glob('*.md'))
    return paths + sorted((box / 'done').glob('*.md')) if done else paths


def letter(path):
    text = Path(path).read_text(encoding='utf-8')
    parts = re.split(r'^---\r?$', text, maxsplit=2, flags=re.M)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError('信件缺少 frontmatter')
    data = dict(line.split(': ', 1) for line in parts[1].strip().splitlines() if ': ' in line)
    name(data['from'])
    name(data['id'])
    data['title'] = next((s[2:] for s in parts[2].splitlines() if s.startswith('# ')), '')
    data['file'] = str(path)
    data['body'] = parts[2].split('\n', 2)[-1].strip()
    return data


def team_of(root, me):
    found = []
    for p in sorted((Path(root) / 'teams').glob('*/members')):
        members = p.read_text().splitlines()
        if me in members:
            found.append((p.parent.name, members[0]))
    if len(found) > 1:
        raise ValueError('同一人不能屬於兩個團隊')
    return found[0] if found else None


def upstream(root, me):
    team = team_of(root, me)
    if team and team[1] != me:
        return team[1]
    p = Path(root) / me / 'wf/ROSTER.md'
    text = p.read_text() if p.exists() else ''
    match = re.search(r'^### `' + re.escape(me) + r'`\n(.*?)(?=^### |\Z)', text, re.M | re.S)
    up = re.search(r'^- \*\*上游\*\*：(.*)$', match[1], re.M) if match else None
    if not up or not up[1].strip():
        raise ValueError('找不到團隊領導或 ROSTER 上游')
    return name(up[1].strip().strip('`'))


def body_text(body):
    if body and all('## ' + h in body for h in HEADINGS):
        return body.rstrip() + '\n'
    return '\n\n'.join('## ' + h + '\n' + (body if i == 0 and body else '無')
                         for i, h in enumerate(HEADINGS)) + '\n'


def validate_reply(status, title, body):
    if status not in STATUSES:
        raise ValueError('STATUS 不在白名單')
    if not isinstance(title, str) or not title.strip() or '\n' in title or '\r' in title:
        raise ValueError('結論必須是非空的一行')
    body_text(body).encode('utf-8')
    title.encode('utf-8')


def send(root, me, to, status, title, body='', re_id='', ident=None):
    name(me)
    validate_reply(status, title, body)
    if status not in STATUSES:
        raise ValueError('STATUS 不在白名單')
    if not title.strip() or '\n' in title or '\r' in title:
        raise ValueError('結論必須是非空的一行')
    if re_id:
        name(re_id)
    to = upstream(root, me) if to == '--up' else to
    box = inbox(root, to)
    if to.startswith('team:') and (not team_of(root, me) or team_of(root, me)[0] != to[5:]):
        raise ValueError('只有團隊成員可以投團隊信箱')
    stamp = datetime.datetime.now().astimezone()
    ts = stamp.strftime('%Y%m%dT%H%M%S')
    ident = name(ident or f'{me}-{ts}-{secrets.token_hex(6)}')
    data = {'from': me, 'to': to, 'status': status, 'at': stamp.isoformat(),
            'reply-to': str(inbox(root, me)), 'id': ident, 're': re_id}
    text = '---\n' + ''.join(f'{k}: {v}\n' for k, v in data.items()) + '---\n# ' + title + '\n\n' + body_text(body)
    if not to.startswith('team:') and not box.parent.exists():
        print(f'注意：{to} 是新信箱（第一次收信）', file=sys.stderr)
    tmpdir = box / '.tmp'
    tmpdir.mkdir(parents=True, exist_ok=True)
    # 回信的固定 id 去重；獨立 delivery 鎖不佔收件者的辦結鎖。
    with locked(str(box / '.delivery')):
        existing = next((p for p in letters(box, True) if letter(p)['id'] == ident), None)
        if existing:
            return {'sent': str(existing), 'id': ident}
        with tempfile.NamedTemporaryFile(dir=tmpdir, delete=False) as f:
            tmp = Path(f.name)
            f.write(text.encode('utf-8'))
        try:
            n = 0
            while True:
                suffix = f'_{n}' if n else ''
                final = box / f'{ts}{suffix}-{me}-{status}.md'
                if (box / 'done' / final.name).exists():
                    n += 1
                    continue
                try:
                    os.link(tmp, final)
                    break
                except FileExistsError:
                    n += 1
        finally:
            tmp.unlink(missing_ok=True)
    if status == 'REQUEST':
        try:
            result = publish(box.parent / 'events', kind='mail.request', event_id=ident,
                             payload={'id': ident, 'from': me, 'to': to, 'file': str(final)}, must=True, node=to)
            if not result['ok']:
                print('必達提醒未保存：' + str(result.get('why')), file=sys.stderr)
        except Exception as e:
            print('必達提醒未保存：' + str(e).replace('\n', ' '), file=sys.stderr)
    return {'sent': str(final), 'id': ident}


def audit(root, me=None):
    if me is not None:
        name(me)
    boxes = sorted(set(Path(root).glob('*/inbox')) | set(Path(root).glob('teams/*/inbox')))
    all_mail = []
    for box in boxes:
        with locked(str(box / '.delivery')):
            all_mail.extend(letter(p) for p in letters(box, True))
    requests = {l['id']: l for l in all_mail if l['status'] == 'REQUEST'}
    closed = {l.get('re') for l in all_mail if l['status'] in TERMINAL}
    return [dict(l, type='audit') for id_, l in requests.items() if id_ not in closed
            and (me is None or me in (l['from'], l['to']))]


def ack(root, me):
    box = inbox(root, me)
    events = box.parent / 'events'
    if not events.exists():
        return
    marker = box / '.acked'
    actual = event_ack(events, 0)
    if actual is None:
        return
    upto = actual
    write_json(str(marker), upto)
    cursor = upto + 1
    ended = {l['id'] for p in (box / 'done').glob('*.md')
             if (l := letter(p))['status'] == 'REQUEST'}
    while True:
        result = events_read(events, 'must', cursor=cursor)
        records = result['records']
        for rec in records:
            if rec['seq'] != cursor or rec.get('kind') != 'mail.request' or rec.get('payload', {}).get('id') not in ended:
                records = []
                break
            upto, cursor = rec['seq'], rec['seq'] + 1
        if not records or len(records) < 100 or result['errors']:
            break
    if upto > load(marker, 0):
        confirmed = event_ack(events, upto)
        if confirmed is not None:
            test_point('mail.after_event_ack')
            write_json(str(marker), confirmed)


def event_ack(events, upto):
    p = subprocess.run([sys.executable, str(HERE.parent / 'events/aos7-events'), 'read',
                        '--events', str(events), '--channel', 'must', '--ack', str(upto)], capture_output=True, text=True)
    if p.returncode == 0:
        return json.loads(p.stdout)['acked_upto']
    print('必達提醒確認失敗：' + p.stdout.strip(), file=sys.stderr)
    return None


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
                    target = target.parent / f'{path.stem}_archive{n}.md'
            path.unlink()
    ack(root, me)


def complete(root, me, path, status=None, title=None, body='', handler=None):
    if status is not None and status not in TERMINAL:
        raise ValueError('辦結 STATUS 必須是終局狀態')
    l = letter(path)
    jp = path.parent / '.handled' / (l['id'] + '.json')
    journal = load(jp)
    if journal is None:
        if handler:
            status, title, body = handler(l)
        replies = []
        if l['status'] == 'REQUEST':
            if status not in TERMINAL or not title:
                raise ValueError('REQUEST 辦結必須給終局 STATUS 與一句結論')
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
        pending = [p for p in letters(box) if not (box / '.handled' / (letter(p)['id'] + '.json')).exists()]
        if filename.isdecimal():
            index = int(filename) - 1
            if not 0 <= index < len(pending):
                raise ValueError('找不到這個未辦信序號')
            path = pending[index]
        else:
            path = next((p for p in letters(box, True)
                         if p.name == filename or letter(p)['id'] == filename), None)
            if path is None:
                raise ValueError('找不到這封信')
        l = letter(path)
        if path.parent == box:
            complete(root, me, path, status, title, body)
        else:
            ack(root, me)
        journal = load(box / '.handled' / (l['id'] + '.json'), {})
        return {'file': path.name, 'to': [r['to'] for r in journal.get('replies', [])],
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
        orders = box.parent / 'orders.md'
        if orders.exists():
            data = orders.read_bytes()
            offset = load(box / '.orders-offset', 0)
            if offset > len(data):
                raise ValueError('orders 被截短，請恢復 append-only 檔案')
            if len(data) > offset:
                for part in re.split(r'(?m)(?=^## )', data[offset:].decode('utf-8')):
                    if part.strip():
                        output.append({'type': 'orders', 'file': str(orders), 'title': part.strip()})
                updates[box / '.orders-offset'] = len(data)
        waiting = audit(root, me)
        if not quiet:
            output.extend(l for l in waiting if l['from'] == me)
        yield output
        test_point('mail.before_seen_commit')
        for path, value in updates.items():
            write_json(str(path), value)


def roster(root, me, who, up, territory, can, cannot, team=None):
    name(me)
    name(up)
    if team:
        name(team)
    path = Path(root) / me / 'wf/ROSTER.md'
    with locked(str(path)):
        text = path.read_text() if path.exists() else '# ROSTER\n\n## 現役成員\n'
        if f'### `{me}`' in text.splitlines():
            raise ValueError('同名 ROSTER 格已存在')
        fields = [('狀態', '現役'), ('我是誰', who), ('團隊', f'`teams/{team}`' if team else '無'),
                  ('上游', up), ('領地', territory), ('答得出什麼', can), ('答不出什麼', cannot),
                  ('怎麼找我', str(inbox(root, me))), ('訂閱主題', '無')]
        if any('\n' in v or '\r' in v for _, v in fields):
            raise ValueError('ROSTER 每欄必須是一行')
        with path.open('a') as f:
            if not path.stat().st_size:
                f.write(text)
            f.write(f'\n### `{me}`\n' + ''.join(f'- **{k}**：{v}\n' for k, v in fields))


def team(root, group, leader, members):
    name(group)
    people = [name(p) for p in [leader, *members]]
    with locked(str(Path(root) / 'teams/.membership')):
        if len(set(people)) != len(people) or any(team_of(root, p) for p in people):
            raise ValueError('成員重複或已在別的團隊')
        folder = Path(root) / 'teams' / group
        folder.mkdir()
        (folder / 'inbox').mkdir()
        (folder / 'members').write_text('\n'.join(people) + '\n')


