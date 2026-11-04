"""跨團隊公共資料夾 commons（spec/team/commons.md，2026-09-25）。

一台機器一份（預設在團隊資料夾的上一層 `commons/`），所有團隊的成員都唯讀掛成 `/work/commons`：
- 投稿：成員 `commons_submit` → 自己 outbox 一份 `kind: contribute` → **自己團隊的郵差** `on_contribute`
  驗欄位、把附件從 outbox 抄進 `commons/inbox/<投稿號>/`（只抄一般檔、相對路徑、有大小上限）→ 回信「送到了」。
- 審：**圖書館員團隊的郵差**每輪 `desk()`：機械檢查 → 壞的直接退、乾淨的直接入庫；
  跟既有條目像（同名、標題很像）才寄一封信叫圖書館員（模型）判，模型只能回 `commons_verdict`（入庫／退回＋理由），
  那是一份 `kind: commons_write` 申請，郵差 `on_commons_write` 照判決做。
- 回信：投稿者團隊的郵差每輪看自己送出去的投稿有沒有結果（`inbox/<號>/result.json`），有就寄信給投稿者。
- 入庫＝寫條目檔＋更新 `index.json`（機器用）與 `INDEX.md`（人看）。只有圖書館員那邊（它的郵差、人的 CLI）寫 commons；
  各團隊郵差只寫 `inbox/` 底下自己新開的投稿資料夾。
不叫模型（模型只在圖書館員成員那一格）。
這個檔留匯入 playbook（playbook_items 讀法不動）與人的指令 cmd_commons；實作分在 aos_team_commons_base／ingest／post，
這裡匯出外部用到的名字。
"""
import json
import os
import re
from pathlib import Path

from aos_team_format import HUMAN, Layout, TeamError, load_roster

from aos_team_commons_base import (
    Commons, commons_dir, librarians, LIMITS, member_on, TYPES, validate_roster_keys
)
from aos_team_commons_ingest import (
    check_fields, check_files, content_sha, ingest, remove, search, similar
)
from aos_team_commons_post import (
    _mark_sent, _team_tag, desk, on_commons_write, on_contribute, pending_results, post_round
)


# ------------------------------------------------------------ 匯入 playbook ----

LESSON_HEAD = re.compile(r'^### (\d+)[（(]([^）)]+)[）)]\s*(.+?)\s*$')


def playbook_items(folder):
    """proto5/playbook 形狀的資料夾 → 投稿清單（每條帶 slug）：lessons.md 每個「### N（部門）標題」一條 lesson；
    teams/、workflows/ 底下除 README.md 以外的 .md 各一條 team／workflow（內容當 body，不附檔）。"""
    folder = Path(folder)
    items = []
    lessons = folder / 'lessons.md'
    if lessons.is_file():
        cur = None
        for line in lessons.read_text(encoding='utf-8').splitlines():
            m = LESSON_HEAD.match(line)
            if m:
                cur = {'type': 'lesson', 'slug': 'playbook-lesson-%s' % m.group(1), 'title': m.group(3)[:LIMITS['title']],
                       'tags': ['playbook', m.group(2)[:24]], 'fits': '%s（playbook 經驗）' % m.group(2), 'lines': []}
                items.append(cur)
            elif line.startswith('## ') and cur is not None:
                cur = None
            elif cur is not None:
                cur['lines'].append(line)
    for kind, sub in (('team', 'teams'), ('workflow', 'workflows')):
        d = folder / sub
        for p in sorted(d.glob('*.md')) if d.is_dir() else []:
            if p.name == 'README.md':
                continue
            text = p.read_text(encoding='utf-8')
            first = next((l.lstrip('# ').strip() for l in text.splitlines() if l.strip()), p.stem)
            slug = re.sub(r'[^a-z0-9-]', '-', ('playbook-%s-%s' % (kind, p.stem)).lower())[:48].strip('-')
            items.append({'type': kind, 'slug': slug, 'title': first[:LIMITS['title']], 'tags': ['playbook', kind],
                          'fits': '見內文（playbook %s）' % sub, 'body': text})
    for it in items:
        if 'lines' in it:
            it['body'] = '\n'.join(it.pop('lines')).strip() or it['title']
        it['body'] = it['body'][:LIMITS['body']]
    return items


def import_dir(c, folder):
    """匯入 playbook 形狀的資料夾；回 (新加, 換新, 跳過) 三個 id 清單。同 slug 內容一樣＝跳過；不一樣＝換新（以來源為準）。"""
    added, replaced, same = [], [], []
    src = {'team': 'playbook', 'member': HUMAN, 'task': None}
    with c.lock():
        c.ensure()
        for it in playbook_items(folder):
            sub = check_fields(it, 'import.%s' % it['slug'])
            sha = content_sha(sub, {})
            old = c.load_index()['entries'].get(sub['slug'])
            if old is not None and old.get('sha256') == sha and old.get('title') == sub['title'] \
                    and old.get('tags') == sub['tags'] and old.get('fits') == sub['fits']:
                same.append(sub['slug'])
                continue
            if old is not None and (old.get('from') or {}).get('team') != 'playbook':
                raise TeamError('Conflict', 'commons 已有 %s，但不是從 playbook 匯入的（來自 %s）；先 rm 或改名再匯入'
                                % (sub['slug'], (old.get('from') or {}).get('team')))   # astra 10：不刪別人的條目
            if old is not None:
                remove(c, sub['slug'])            # 換新：新版的檔已在 playbook，刪舊寫新都在同一把鎖裡
                replaced.append(sub['slug'])
            else:
                added.append(sub['slug'])
            ingest(c, sub, src, sha=sha)
    return added, replaced, same


# ------------------------------------------------------------ 人的指令 ----

def _commons_for(team_dir, args):
    if getattr(args, 'dir', None):
        return Commons(os.path.abspath(os.path.expanduser(args.dir)))
    roster = load_roster(team_dir)
    return Commons(commons_dir(team_dir, roster))


def cmd_commons(team_dir, argv):
    from aos_team import Parser
    ap = Parser(prog='aos-team commons', description='跨團隊公共資料夾：ls／show／search／add／rm／reindex／import／desk')
    ap.add_argument('--dir', help='commons 資料夾（沒給＝照這支團隊名冊的 commons）')
    sp = ap.add_subparsers(dest='op', required=True)
    p = sp.add_parser('ls', help='一條一行')
    p.add_argument('--json', action='store_true')
    p = sp.add_parser('show', help='看一條的全文')
    p.add_argument('id')
    p = sp.add_parser('search', help='跟 commons_search 工具同一套算法')
    p.add_argument('query', nargs='?', default='')
    p.add_argument('--tag', action='append', default=[])
    p.add_argument('--limit', type=int, default=5)
    p = sp.add_parser('add', help='人直接加一條（不用投稿；檢查一樣跑）')
    p.add_argument('type', choices=list(TYPES))
    p.add_argument('--title', required=True)
    p.add_argument('--fits', required=True)
    p.add_argument('--tags', required=True, help='逗號分隔')
    p.add_argument('--body-file', required=True, help='內容（markdown）檔')
    p.add_argument('--slug')
    p.add_argument('--file', action='append', default=[], help='附件（team／workflow／tool 用），相對目前資料夾')
    p = sp.add_parser('rm', help='拿掉一條')
    p.add_argument('id')
    sp.add_parser('reindex', help='index.json 用文字編輯器改過後，重生 INDEX.md（順便驗格式）')
    p = sp.add_parser('import', help='匯入 proto5/playbook 形狀的資料夾（lessons.md 一段一條、teams／workflows 一檔一條）')
    p.add_argument('folder')
    sp.add_parser('desk', help='圖書館員的機械檢查手動走一輪（平常郵差每輪會走）')
    args = ap.parse_args(argv)
    c = _commons_for(team_dir, args)
    if args.op == 'ls':
        idx = c.load_index()
        if args.json:
            print(json.dumps(idx['entries'], ensure_ascii=False, indent=2))
        for eid, e in sorted(idx['entries'].items()):
            if not args.json:
                print('%s  %-8s %s  〔%s〕  %s' % (eid, e.get('type'), e.get('title'), '、'.join(e.get('tags', [])),
                                                  e.get('path')))
        if not idx['entries'] and not args.json:
            print('（commons %s 還沒有條目）' % c.root)
        return 0
    if args.op == 'show':
        e = c.load_index()['entries'].get(args.id)
        if e is None:
            raise TeamError('NotFound', '沒有 %s' % args.id)
        p = c.root / e['path'].rstrip('/')
        print((p / 'README.md' if p.is_dir() else p).read_text(encoding='utf-8'), end='')
        if p.is_dir():
            print('\n附件：%s' % '、'.join(sorted(str(x.relative_to(p)) for x in p.rglob('*') if x.is_file()
                                              and x.name != 'README.md')))
        return 0
    if args.op == 'search':
        for score, eid, e in search(c.load_index(), args.query, args.tag, None, args.limit):
            print('%s  %s  %s → %s' % (eid, e.get('title'), e.get('summary', '')[:60], e.get('path')))
        return 0
    if args.op == 'add':
        body = Path(args.body_file).read_text(encoding='utf-8')
        files = [f for f in args.file]
        sub = check_fields({'type': args.type, 'title': args.title, 'fits': args.fits, 'body': body,
                            'tags': [t.strip() for t in args.tags.split(',') if t.strip()], 'slug': args.slug,
                            'files': files}, 'add')
        sums = check_files(os.getcwd(), sub['files'])
        sha = content_sha(sub, sums)
        with c.lock():
            same, like = similar(c.ensure().load_index(), sub, sha)
            if same:
                raise TeamError('Duplicate', '跟 %s 內容完全一樣' % same)
            eid = ingest(c, sub, {'team': HUMAN, 'member': HUMAN, 'task': None}, os.getcwd(), sha=sha)
        print('加了 %s%s' % (eid, '（注意：跟 %s 很像）' % '、'.join(like) if like else ''))
        return 0
    if args.op == 'rm':
        with c.lock():
            remove(c, args.id)
        print('拿掉了 %s' % args.id)
        return 0
    if args.op == 'reindex':
        with c.lock():
            idx = c.load_index()
            for eid, e in idx['entries'].items():
                if not isinstance(e, dict) or e.get('type') not in TYPES or not isinstance(e.get('path'), str):
                    raise TeamError('FormatInvalid', 'index.json entries.%s 要有 type（%s）與 path'
                                    % (eid, '／'.join(TYPES)))
            c.save_index(idx)
        print('INDEX.md 重生了（%d 條）' % len(idx['entries']))
        return 0
    if args.op == 'import':
        added, replaced, same = import_dir(c, os.path.abspath(os.path.expanduser(args.folder)))
        print('匯入 %s：新加 %d、換新 %d、一樣跳過 %d' % (args.folder, len(added), len(replaced), len(same)))
        return 0
    if args.op == 'desk':
        lay = Layout(team_dir)
        roster = load_roster(team_dir)
        if not librarians(roster):
            raise TeamError('NotAllowed', '這支團隊沒有圖書館員（模板 may 有 commons_write 的成員）')
        asks = desk(lay, roster)
        print('走完一輪；要叫模型判的 %d 份：%s' % (len(asks), '、'.join(r for r, _ in asks) or '-'))
        return 0
    return 2
