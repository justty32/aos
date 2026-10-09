"""檔案是權威的郵局；events must 只作提醒。"""
import datetime
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'events'), str(HERE.parents[1] / 'lib')]
from aos7_fs import locked, write_json, test_point
from aos7_events_pub import publish
from aos7_events_read import read as events_read

class Refused(ValueError):
    """做不到（撞名、前提不在）：CLI 退 1；其他 ValueError 是用法錯退 2。"""


TERMINAL = {'DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED'}
STATUSES = TERMINAL | {'REQUEST', 'PROGRESS'}
HEADINGS = ('做了什麼', '產出（檔案路徑 / commit / 分支）', '沒做到、或證據不足的部分', '需要對方或使用者決定的事')


def name(value):
    if not re.fullmatch(r'[A-Za-z0-9._-]+', value) or value in ('.', '..', 'teams'):
        raise ValueError(f'名字 {value!r} 不行。只准英數字、點、底線、短橫線，且不能是 . .. teams，例：alice')
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
    paths = sorted(p for p in box.glob('*.md') if not p.name.startswith('.') and p.is_file())
    return paths + letters(box / 'done') if done else paths


def letter(path):
    text = Path(path).read_text(encoding='utf-8')
    parts = re.split(r'^---\r?$', text, maxsplit=2, flags=re.M)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError('信件缺少 frontmatter。信檔要照 ADVANCED.md〈完整指令〉的格式，請用 send 寄，不要手寫')
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
        raise ValueError('同一人出現在兩個團隊的 members。請把多的那份 teams/<隊>/members 改掉')
    return found[0] if found else None


def upstream(root, me):
    team = team_of(root, me)
    if team and team[1] != me:
        return team[1]
    p = Path(root) / me / 'wf/workflows/inbox/ROSTER.md'
    text = p.read_text() if p.exists() else ''
    match = re.search(r'^### `' + re.escape(me) + r'`\n(.*?)(?=^### |^## |\Z)', text, re.M | re.S)
    up = re.search(r'^- \*\*上游\*\*：(.*)$', match[1], re.M) if match else None
    if not up or not up[1].strip():
        raise Refused('找不到你的上游：你不在團隊裡，ROSTER 也沒寫上游。先用 roster 寫上游，或直接寫收件人名字')
    return name(up[1].strip().strip('`'))


def body_text(body):
    if body and all('## ' + h in body for h in HEADINGS):
        return body.rstrip() + '\n'
    return '\n\n'.join('## ' + h + '\n' + (body if i == 0 and body else '無')
                         for i, h in enumerate(HEADINGS)) + '\n'


def validate_reply(status, title, body):
    if status not in STATUSES:
        raise ValueError(f'STATUS {status} 不認得。只能是 REQUEST、PROGRESS、DONE、BLOCKED、NEEDS-USER、FAILED')
    if not isinstance(title, str) or not title.strip() or '\n' in title or '\r' in title:
        raise ValueError('結論必須是非空的一行。例：\'檢查完了\'')
    body_text(body).encode('utf-8')
    title.encode('utf-8')


def send(root, me, to, status, title, body='', re_id='', ident=None):
    name(me)
    validate_reply(status, title, body)
    if re_id:
        name(re_id)
    to = upstream(root, me) if to == '--up' else to
    if to.startswith('team:') and status == 'REQUEST':
        raise ValueError('團隊信箱只收廣播（PROGRESS／終局）。要人辦事請直接寄給成員')
    box = inbox(root, to)
    if to.startswith('team:') and (not team_of(root, me) or team_of(root, me)[0] != to[5:]):
        raise Refused('只有團隊成員可以投團隊信箱。請直接寄給個人')
    stamp = datetime.datetime.now().astimezone()
    ts = stamp.strftime('%Y%m%dT%H%M')
    ident = name(ident or f"{me}-{stamp.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(6)}")
    data = {'from': me, 'to': to, 'status': status, 'at': stamp.isoformat(),
            'reply-to': str(inbox(root, me)), 'id': ident, 're': re_id}
    text = '---\n' + ''.join(f'{k}: {v}\n' for k, v in data.items()) + '---\n# ' + title + '\n\n' + body_text(body)
    if not to.startswith('team:') and not (Path(root) / to).exists():
        print(f'aos7-mail: 注意：{to} 是新信箱（第一次收信）。確認名字沒打錯；沒錯就不用管', file=sys.stderr)
    inbox(root, me).mkdir(parents=True, exist_ok=True)  # 寄件者也算有信箱：回信時不再提示「新信箱」
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
    if status == 'REQUEST' and (Path(root) / to / 'events').is_dir():
        try:
            result = publish((box.parent if to.startswith('team:') else Path(root) / to) / 'events', kind='mail.request', event_id=ident,
                             payload={'id': ident, 'from': me, 'to': to, 'file': str(final)}, must=True, node=to)
            if not result['ok']:
                print('aos7-mail: 必達提醒未保存（' + ' '.join(str(result.get('why')).splitlines()) + '），信已寄出。信是權威，下次 read 或 done 會再試', file=sys.stderr)
        except Exception as e:
            print('aos7-mail: 必達提醒未保存（' + ' '.join(str(e).splitlines()) + '），信已寄出。信是權威，下次 read 或 done 會再試', file=sys.stderr)
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


from aos7_mail_setup import roster, team
from aos7_mail_box import ack, event_ack, finish, complete, done, handle, poll
