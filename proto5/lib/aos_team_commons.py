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
"""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

from aos_team_format import (HUMAN, Layout, TeamError, bad, json_files, load_roster, read_json, write_json,
                             template_may)

INDEX_TYPE = 'aos_commons_index'
TYPES = {'lesson': 'lessons', 'team': 'teams', 'workflow': 'workflows', 'tool': 'tools'}
SLUG = re.compile(r'[a-z0-9][a-z0-9-]{0,47}\Z')
TAG = re.compile(r'[^\s,/\\]{1,24}\Z')
TASK = re.compile(r't-[0-9]{4,}(\.r[0-9]+)?\Z')
FIELDS = ('type', 'title', 'tags', 'fits', 'body', 'files', 'task', 'slug')
LIMITS = {'title': 120, 'fits': 300, 'body': 16000, 'files': 20, 'file_bytes': 64 * 1024, 'total_bytes': 256 * 1024,
          'tags': 8}
SIMILAR = 0.5            # 標題字的重疊比例（Jaccard）≥ 這個＝「像」，要模型判
WRITE_KIND = 'commons_write'   # 圖書館員模板 may 要有這個


# ------------------------------------------------------------ 在哪、誰開 ----

def team_cfg(roster):
    """名冊頂層 commons：沒寫＝開、放 ../commons；false＝關；{"on", "dir"}。"""
    c = roster.get('commons', True)
    if isinstance(c, bool):
        return {'on': c, 'dir': '../commons'}
    return {'on': c.get('on', True), 'dir': c.get('dir', '../commons')}


def commons_dir(team_dir, roster):
    """這支團隊的 commons 資料夾（絕對路徑）；不管開不開都回。"""
    raw = os.path.expanduser(team_cfg(roster)['dir'])
    return Path(os.path.abspath(os.path.join(str(team_dir), raw)))


def member_on(roster, name):
    """成員 name 有沒有 commons（掛、兩支工具、能投稿）：成員層 commons 蓋過團隊層，團隊層沒寫＝開。"""
    m = roster['members'].get(name)
    if m is None:
        return False
    own = m.get('commons')
    if isinstance(own, bool):
        return own
    return bool(team_cfg(roster)['on'])


def librarians(roster):
    """名冊裡能寫 commons 的成員（模板 may 有 commons_write）。"""
    return [n for n, m in roster['members'].items() if WRITE_KIND in template_may(m['template'])]


def validate_roster_keys(obj, where):
    """給 aos_team_format.validate_roster 叫：頂層 commons、成員層 commons。"""
    c = obj.get('commons', True)
    if isinstance(c, dict):
        extra = sorted(set(c) - {'on', 'dir'})
        if extra:
            bad(where + '.commons', '不認得的鍵 %s（可用：on、dir）' % '、'.join(extra))
        if not isinstance(c.get('on', True), bool):
            bad(where + '.commons.on', '要是 true／false')
        d = c.get('dir', '../commons')
        if not isinstance(d, str) or not d.strip() or '\n' in d:
            bad(where + '.commons.dir', '要是資料夾路徑字串（相對團隊資料夾，可用 ~）')
    elif not isinstance(c, bool):
        bad(where + '.commons', '要是 true／false 或 {"on": …, "dir": …}')
    for name, m in (obj.get('members') or {}).items():
        if isinstance(m, dict) and 'commons' in m and not isinstance(m['commons'], bool):
            bad('%s.members.%s.commons' % (where, name), '要是 true／false')


# ------------------------------------------------------------ 資料夾 ----

class Commons:
    def __init__(self, root):
        self.root = Path(root)
        self.index_path = self.root / 'index.json'
        self.inbox = self.root / 'inbox'

    def ensure(self):
        for sub in list(TYPES.values()) + ['inbox']:
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.save_index({'_metainfo': {'_type': INDEX_TYPE, '_version': 1}, 'entries': {}})
        return self

    @contextlib.contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / '.lock', 'a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def load_index(self):
        if not self.index_path.exists():
            return {'_metainfo': {'_type': INDEX_TYPE, '_version': 1}, 'entries': {}}
        obj = read_json(self.index_path, 'commons/index.json')
        if not isinstance(obj, dict) or not isinstance(obj.get('entries'), dict):
            raise TeamError('FormatInvalid', 'commons/index.json 要有 "entries" 物件（人改壞了？）')
        return obj

    def save_index(self, idx):
        write_json(self.index_path, idx, indent=2)
        (self.root / '.INDEX.md.tmp').write_text(render_index(idx), encoding='utf-8')
        os.replace(self.root / '.INDEX.md.tmp', self.root / 'INDEX.md')


def render_index(idx):
    lines = ['# commons 索引', '', '機器用的是 `index.json`（可以用文字編輯器改，改完跑 `aos-team commons reindex` 重生這一頁）。', '']
    by = {}
    for eid, e in sorted(idx['entries'].items()):
        by.setdefault(e.get('type', '?'), []).append((eid, e))
    if not by:
        lines.append('（還沒有條目）')
    for t in TYPES:
        if t not in by:
            continue
        lines += ['## %s' % TYPES[t], '', '| id | 標題 | 適合 | 標籤 | 來自 | 日期 |', '|---|---|---|---|---|---|']
        for eid, e in by[t]:
            src = e.get('from') or {}
            who = '%s/%s%s' % (src.get('team', '?'), src.get('member', '?'), ' ' + src['task'] if src.get('task') else '')
            lines.append('| [%s](%s) | %s | %s | %s | %s | %s |' % (
                eid, e.get('path', ''), _cell(e.get('title')), _cell(e.get('fits')), '、'.join(e.get('tags', [])),
                who, e.get('date', '')))
        lines.append('')
    return '\n'.join(lines) + '\n'


def _cell(text):
    return str(text or '').replace('|', '／').replace('\n', ' ')


# ------------------------------------------------------------ 檢查 ----

def check_fields(sub, where='contribute'):
    """投稿欄位（成員的申請、人 add 都用）。回整理過的 dict。"""
    extra = sorted(set(sub) - set(FIELDS) - {'id', 'from', 'kind', 'at', 'cid', 'request', 'source'})
    if extra:
        bad(where, '不認得的欄位 %s（可用：%s）' % ('、'.join(extra), '、'.join(FIELDS)))
    t = sub.get('type')
    if t not in TYPES:
        bad(where + '.type', '要是 %s 之一' % '／'.join(TYPES), 'MissingField' if t is None else 'FormatInvalid')
    out = {'type': t}
    for key in ('title', 'fits', 'body'):
        v = sub.get(key)
        if not isinstance(v, str) or not v.strip():
            bad('%s.%s' % (where, key), '必填（非空字串）', 'MissingField')
        if len(v) > LIMITS[key]:
            bad('%s.%s' % (where, key), '太長（上限 %d 字）' % LIMITS[key], 'TooLarge')
        if key != 'body' and '\n' in v.strip():
            bad('%s.%s' % (where, key), '只能一行')
        out[key] = v.strip() if key != 'body' else v
    tags = sub.get('tags')
    if not isinstance(tags, list) or not tags or len(tags) > LIMITS['tags'] or \
            not all(isinstance(x, str) and TAG.match(x) for x in tags):
        bad(where + '.tags', '必填：1～%d 個標籤，每個 1～24 字、不含空白與 , / \\' % LIMITS['tags'], 'MissingField')
    out['tags'] = [x.lower() for x in tags]
    task = sub.get('task')
    if task is not None and (not isinstance(task, str) or not TASK.match(task)):
        bad(where + '.task', '要是任務單號（t-0001）')
    out['task'] = task
    slug = sub.get('slug')
    if slug is not None and (not isinstance(slug, str) or not SLUG.match(slug)):
        bad(where + '.slug', '只能小寫英數與 -，1～48 字')
    out['slug'] = slug
    files = sub.get('files') or []
    if not isinstance(files, list) or len(files) > LIMITS['files']:
        bad(where + '.files', '要是 0～%d 個相對路徑' % LIMITS['files'])
    if files and t == 'lesson':
        bad(where + '.files', '經驗（lesson）一條一檔，內容寫在 body，不能附檔')
    out['files'] = [check_rel(where + '.files', f) for f in files]
    return out


def check_rel(where, value):
    """附件路徑：相對、沒 .. 段、不以 / ~ 開頭、沒控制字元、不是 README.md（那格是條目的說明）。"""
    if not isinstance(value, str) or not value or value != value.strip() or value.startswith(('/', '~')) \
            or any(ord(ch) < 32 for ch in value) or any(seg in ('', '.', '..') for seg in value.split('/')):
        bad(where, '路徑 %r 要是相對路徑（不以 / ~ 開頭、不含 .. 或空段）' % (value,), 'BadPath')
    if value == 'README.md':
        bad(where, 'README.md 是條目自己的說明（由 body 生），附件不能叫這個名字', 'BadPath')
    return value


def check_files(folder, files):
    """已抄進 inbox 的附件：一般檔、大小、執行位只准給 #! 開頭的腳本。回 sha256 表。"""
    total, sums = 0, {}
    for rel in files:
        p = Path(folder) / rel
        st = os.lstat(p) if os.path.lexists(p) else None
        if st is None or not stat.S_ISREG(st.st_mode):
            raise TeamError('BadFile', '附件 %s 不在或不是一般檔（符號連結、資料夾都不收）' % rel)
        if st.st_size > LIMITS['file_bytes']:
            raise TeamError('TooLarge', '附件 %s 有 %d bytes（一檔上限 %d）' % (rel, st.st_size, LIMITS['file_bytes']))
        total += st.st_size
        data = p.read_bytes()
        if st.st_mode & 0o111 and not data.startswith(b'#!'):
            raise TeamError('BadMode', '附件 %s 有執行位但不是腳本（不以 #! 開頭）；只有可執行檔能有執行位' % rel)
        sums[rel] = hashlib.sha256(data).hexdigest()
    if total > LIMITS['total_bytes']:
        raise TeamError('TooLarge', '附件總共 %d bytes（上限 %d）' % (total, LIMITS['total_bytes']))
    return sums


def content_sha(sub, sums):
    h = hashlib.sha256()
    h.update(sub['type'].encode())
    h.update(b'\0' + sub['body'].strip().encode('utf-8'))
    for rel in sorted(sums):
        h.update(('\0%s\0%s' % (rel, sums[rel])).encode())
    return h.hexdigest()


def _words(text):
    text = text.lower()
    return set(re.findall(r'[a-z0-9]+', text)) | set(ch for ch in text if '一' <= ch <= '鿿')


STOP = {'the', 'and', 'for', 'with', 'must', 'use', 'into', 'from', 'that', 'this', 'are', 'not', 'your', 'when', 'what'}


def _keys(title, tags, fits):
    """「像不像」用的關鍵字：英數字詞（≥ 3 字、去虛詞）＋中文兩字詞，從標題、標籤、適合三格取。"""
    text = ' '.join([title or '', ' '.join(tags or []), fits or '']).lower()
    out = {w for w in re.findall(r'[a-z0-9]+', text) if len(w) >= 3 and w not in STOP}
    for run in re.findall(r'[一-鿿]+', text):
        out |= {run[i:i + 2] for i in range(len(run) - 1)}
    return out


def similar(idx, sub, sha):
    """回 (完全一樣的 id 或 None, 像的 id 陣列)。像＝同 slug；或同種類，且標題字重疊（Jaccard）≥ SIMILAR，
    或「標題＋標籤＋適合」關鍵字交集／較小那邊 ≥ SIMILAR（09-25 真跑 r2：同一件事換說法，標題重疊只有 0.21，漏掉了）。"""
    same, like = None, []
    mine = _words(sub['title'])
    mine_keys = _keys(sub['title'], sub['tags'], sub['fits'])
    for eid, e in idx['entries'].items():
        if e.get('sha256') == sha:
            same = eid
            continue
        if sub.get('slug') and eid == sub['slug']:
            like.append(eid)
            continue
        if e.get('type') == sub['type']:
            theirs = _words(e.get('title', ''))
            keys = _keys(e.get('title'), e.get('tags'), e.get('fits'))
            if (mine and theirs and len(mine & theirs) / len(mine | theirs) >= SIMILAR) or \
                    (mine_keys and keys and len(mine_keys & keys) / min(len(mine_keys), len(keys)) >= SIMILAR):
                like.append(eid)
    return same, sorted(like)


# ------------------------------------------------------------ 入庫 ----

def _slug_for(idx, sub):
    if sub.get('slug') and sub['slug'] not in idx['entries']:
        return sub['slug']
    base = sub.get('slug') or sub['type']
    n = 1
    while '%s-%04d' % (base, n) in idx['entries']:
        n += 1
    return '%s-%04d' % (base, n)


def _header(sub, src, date):
    who = '%s/%s' % (src.get('team', '?'), src.get('member', '?')) + (' 單 %s' % src['task'] if src.get('task') else '')
    return '# %s\n\n- 來自：%s\n- 適合：%s\n- 標籤：%s\n- 日期：%s\n\n' % (
        sub['title'], who, sub['fits'], '、'.join(sub['tags']), date)


def ingest(c, sub, src, files_dir=None, *, date=None, sha=None):
    """寫條目檔＋更新 index；回條目 id。呼叫者要拿著 c.lock()。src＝{"team", "member", "task"}。"""
    c.ensure()
    idx = c.load_index()
    eid = _slug_for(idx, sub)
    date = date or datetime.date.today().isoformat()
    text = _header(sub, src, date) + sub['body'].strip() + '\n'
    folder = c.root / TYPES[sub['type']]
    if sub['type'] == 'lesson':
        rel = '%s/%s.md' % (TYPES['lesson'], eid)
        tmp = folder / ('.%s.tmp' % eid)
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, folder / (eid + '.md'))
    else:
        rel = '%s/%s/' % (TYPES[sub['type']], eid)
        tmp = folder / ('.%s.tmp' % eid)
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        (tmp / 'README.md').write_text(text, encoding='utf-8')
        for f in sub['files']:
            dst = tmp / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(files_dir) / f, dst)
            if os.stat(Path(files_dir) / f).st_mode & 0o111:
                os.chmod(dst, 0o755)
        final = folder / eid
        if final.exists():
            shutil.rmtree(final)
        os.replace(tmp, final)
    summary = ' '.join(sub['body'].split())[:160]
    idx['entries'][eid] = {'type': sub['type'], 'title': sub['title'], 'tags': sub['tags'], 'fits': sub['fits'],
                           'summary': summary, 'path': rel, 'from': src, 'date': date,
                           'sha256': sha or content_sha(sub, {})}
    c.save_index(idx)
    return eid


def remove(c, eid):
    idx = c.load_index()
    e = idx['entries'].pop(eid, None)
    if e is None:
        raise TeamError('NotFound', 'commons 沒有 %s（aos-team commons ls 看有哪些）' % eid)
    p = c.root / e['path'].rstrip('/')
    if p.is_dir():
        shutil.rmtree(p)
    elif p.exists():
        p.unlink()
    c.save_index(idx)
    return e


# ------------------------------------------------------------ 查閱 ----

def search(idx, query='', tags=(), type_=None, limit=5):
    """關鍵字＋標籤查 index（commons_search 工具用同一套算法）。回 [(分數, id, 條目)]。"""
    words = _words(query or '')
    want = {t.lower() for t in tags}
    out = []
    for eid, e in idx['entries'].items():
        if type_ and e.get('type') != type_:
            continue
        etags = set(e.get('tags', []))
        if want and not want <= etags:
            continue
        hay = _words(' '.join([eid, e.get('title', ''), e.get('fits', ''), e.get('summary', ''), ' '.join(etags)]))
        score = len(words & hay) + 2 * len(words & etags) if words else 1
        if words and not score:
            continue
        out.append((score, eid, e))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out[:limit]


# ------------------------------------------------------------ 郵差：投稿端 ----

def _team_tag(lay):
    return re.sub(r'[^a-z0-9_-]', '-', lay.root.name.lower())[:32] or 'team'


def _records(lay):
    return lay.team / 'commons'


def on_contribute(lay, roster, req):
    """kind: contribute（投稿者團隊的郵差叫）：驗欄位 → 附件從 outbox 抄進 commons/inbox/<號>/ → 回信「送到了」。
    冪等：紀錄 team/commons/<號>.json 在＝回同一份動作。"""
    sender = req['from']
    if not member_on(roster, sender):
        raise TeamError('NotAllowed', '%s 沒開 commons（名冊 commons: false）' % sender)
    sub = check_fields(req)
    cid = 'c-%s--%s' % (_team_tag(lay), req['id'])
    recs = _records(lay)
    rec_path = recs / (cid + '.json')
    if rec_path.exists():
        return read_json(rec_path).get('effects', [])
    c = Commons(commons_dir(lay.root, roster)).ensure()
    outbox = Path(os.path.realpath(lay.outbox(sender)))
    staging = c.inbox / ('.%s.tmp' % cid)
    shutil.rmtree(staging, ignore_errors=True)
    (staging / 'files').mkdir(parents=True)
    total = 0
    try:
        for rel in sub['files']:
            src = outbox / rel
            real = os.path.realpath(src)
            if not real.startswith(str(outbox) + os.sep) or os.path.islink(src) or not os.path.isfile(src):
                raise TeamError('BadFile', '附件 %s 不在你的 outbox、或不是一般檔（符號連結不收）' % rel)
            size = os.path.getsize(src)
            total += size
            if size > LIMITS['file_bytes'] or total > LIMITS['total_bytes']:
                raise TeamError('TooLarge', '附件 %s 太大（一檔 %d、總共 %d bytes 為上限）'
                                % (rel, LIMITS['file_bytes'], LIMITS['total_bytes']))
            dst = staging / 'files' / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            if os.stat(src).st_mode & 0o111:
                os.chmod(dst, 0o755)
        meta = dict(sub, cid=cid, request=req['id'],
                    source={'team': _team_tag(lay), 'member': sender, 'task': sub['task']}, at=req.get('at'))
        write_json(staging / 'submission.json', meta, indent=2)
        final = c.inbox / cid
        if not final.exists():
            os.replace(staging, final)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    effects = [{'do': 'letter', 'to': sender, 'status': 'DONE', 'reply_to': req['id'], 'rev': None,
                'text': '投稿 %s（%s）送到圖書館了；入庫或退回會另寄一封信。' % (cid, sub['title'])}]
    recs.mkdir(parents=True, exist_ok=True)
    write_json(rec_path, {'cid': cid, 'request': req['id'], 'from': sender, 'title': sub['title'],
                          'status': None, 'effects': effects}, indent=2)
    return effects


def pending_results(lay, roster):
    """投稿者團隊的郵差每輪看：自己送出去還沒回信的投稿，有結果了就回 [(notice id, 動作)]，並記下已處理。"""
    out = []
    recs = _records(lay)
    if not recs.is_dir():
        return out
    c = Commons(commons_dir(lay.root, roster))
    for p in json_files(recs):
        rec = read_json(p)
        if rec.get('status') is not None:
            continue
        rp = c.inbox / rec['cid'] / 'result.json'
        if not rp.exists():
            continue
        res = read_json(rp)
        if res.get('status') == 'accepted':
            text = '投稿 %s 入庫了：/work/commons/%s（%s；%s）' % (rec['cid'], res.get('path'), res.get('id'),
                                                            res.get('reason') or '機械檢查過')
            status = 'DONE'
        else:
            text = '投稿 %s 被退回（%s）：%s' % (rec['cid'], res.get('by'), res.get('reason'))
            status = 'FAILED'
        out.append(('commons.result.%s' % rec['cid'],
                    [{'do': 'letter', 'to': rec['from'], 'status': status, 'reply_to': rec['request'], 'rev': None,
                      'text': text}]))
        rec['status'] = res.get('status')
        write_json(p, rec, indent=2)
    return out


# ------------------------------------------------------------ 郵差：圖書館員端 ----

def _result(folder, status, by, reason, **extra):
    write_json(folder / 'result.json', dict({'status': status, 'by': by, 'reason': reason,
                                             'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds')},
                                            **extra), indent=2)


def judge_one(c, folder):
    """一份投稿走機械檢查；回 ('rejected'|'accepted'|'ask', 細節)。呼叫者拿著 c.lock()。"""
    try:
        raw = read_json(folder / 'submission.json')
        sub = check_fields(raw, 'submission')
        sums = check_files(folder / 'files', sub['files'])
    except TeamError as e:
        _result(folder, 'rejected', 'machine', '%s：%s' % (e.code, e.msg))
        return 'rejected', e.code
    sha = content_sha(sub, sums)
    idx = c.load_index()
    same, like = similar(idx, sub, sha)
    if same:
        _result(folder, 'rejected', 'machine', 'Duplicate：跟既有條目 %s 內容完全一樣' % same)
        return 'rejected', 'Duplicate'
    if like:
        return 'ask', like
    eid = ingest(c, sub, raw.get('source') or {}, folder / 'files', sha=sha)
    _result(folder, 'accepted', 'machine', None, id=eid, path=idx_path(c, eid))
    return 'accepted', eid


def idx_path(c, eid):
    return c.load_index()['entries'][eid]['path']


def desk(lay, roster):
    """圖書館員團隊的郵差每輪叫：處理 inbox 裡還沒結果的投稿。回 [(notice id, 動作)]（叫模型判的信）。"""
    libs = librarians(roster)
    if not libs:
        return []
    c = Commons(commons_dir(lay.root, roster)).ensure()
    out = []
    with c.lock():
        for folder in sorted(p for p in c.inbox.iterdir() if p.is_dir() and not p.name.startswith('.')):
            if (folder / 'result.json').exists() or not (folder / 'submission.json').exists():
                continue
            if not (folder / 'judge.json').exists():
                verdict, detail = judge_one(c, folder)
                if verdict != 'ask':
                    continue
                sub = read_json(folder / 'submission.json')
                idx = c.load_index()
                lines = ['投稿 %s 跟既有條目很像，請判：入庫還是退回。' % folder.name,
                         '新投稿：%s（%s）適合：%s 標籤：%s' % (sub['title'], sub['type'], sub['fits'],
                                                        '、'.join(sub['tags'])),
                         '內容：read /work/commons/inbox/%s/submission.json（body 欄）' % folder.name, '像的：']
                for eid in detail:
                    e = idx['entries'][eid]
                    lines.append('- %s：%s → /work/commons/%s' % (eid, e.get('title'), e.get('path')))
                lines.append('用 commons_verdict {"submission": "%s", "verdict": "accept" 或 "reject", '
                             '"reason": "一句話"} 回。' % folder.name)
                write_json(folder / 'judge.json', {'team': _team_tag(lay), 'to': libs[0], 'similar': detail,
                                                   'text': '\n'.join(lines)}, indent=2)
            judge = read_json(folder / 'judge.json')
            if judge.get('team') != _team_tag(lay):
                continue                                  # 別的圖書館員團隊在判
            # 每輪都給；郵差的 notice 靠 id 去重（崩在寫 judge.json 與寄信之間，下一輪也會補寄）
            out.append(('commons.judge.%s' % folder.name,
                        [{'do': 'letter', 'to': judge['to'], 'status': 'REQUEST', 'reply_to': None, 'rev': None,
                          'text': judge['text']}]))
    return out


def on_commons_write(lay, roster, req):
    """kind: commons_write（圖書館員的判決）：{"submission", "verdict": accept|reject, "reason"}。"""
    extra = sorted(set(req) - {'id', 'from', 'kind', 'at', 'submission', 'verdict', 'reason'})
    if extra:
        bad('commons_write', '不認得的欄位 %s' % '、'.join(extra))
    cid, verdict, reason = req.get('submission'), req.get('verdict'), req.get('reason')
    if not isinstance(cid, str) or not re.match(r'c-[A-Za-z0-9_.~-]+\Z', cid):
        bad('commons_write.submission', '要是投稿號 c-…')
    if verdict not in ('accept', 'reject'):
        bad('commons_write.verdict', '要是 accept 或 reject')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        bad('commons_write.reason', '必填，一句話（≤ 500 字）')
    c = Commons(commons_dir(lay.root, roster)).ensure()
    folder = c.inbox / cid
    with c.lock():
        if not (folder / 'submission.json').exists():
            raise TeamError('NotFound', '沒有投稿 %s' % cid)
        res_path = folder / 'result.json'
        if res_path.exists():
            res = read_json(res_path)
            if res.get('request') == req['id']:
                return res.get('effects', [])
            raise TeamError('AlreadyDone', '投稿 %s 已經有結果（%s）' % (cid, res.get('status')))
        if not (folder / 'judge.json').exists():
            raise TeamError('NotAsked', '投稿 %s 沒有要你判（機械就能判的不用模型）' % cid)
        by = '%s/%s' % (_team_tag(lay), req['from'])
        if verdict == 'reject':
            text = '退回 %s：%s' % (cid, reason)
            effects = [{'do': 'letter', 'to': req['from'], 'status': 'DONE', 'reply_to': req['id'], 'rev': None,
                        'text': text}]
            _result(folder, 'rejected', by, reason, request=req['id'], effects=effects)
            return effects
        raw = read_json(folder / 'submission.json')
        sub = check_fields(raw, 'submission')
        sums = check_files(folder / 'files', sub['files'])
        eid = ingest(c, sub, raw.get('source') or {}, folder / 'files', sha=content_sha(sub, sums))
        path = idx_path(c, eid)
        effects = [{'do': 'letter', 'to': req['from'], 'status': 'DONE', 'reply_to': req['id'], 'rev': None,
                    'text': '入庫 %s → %s（%s）' % (cid, path, eid)}]
        _result(folder, 'accepted', by, reason, id=eid, path=path, request=req['id'], effects=effects)
        return effects


def post_round(post):
    """郵差每輪（process_outboxes 之後）叫：圖書館員端 desk、投稿者端 pending_results；各開一份 notice（冪等）。"""
    roster = post.roster
    try:
        for rid, effects in desk(post.lay, roster) + pending_results(post.lay, roster):
            if post.notice(rid, effects):
                post.say('commons：%s' % rid)
    except (TeamError, OSError, ValueError, KeyError) as e:
        post.warn('commons 這輪做不下去：%s（下一輪再試）' % e)


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
            if old is not None and old.get('sha256') == sha:
                same.append(sub['slug'])
                continue
            if old is not None:
                remove(c, sub['slug'])
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
