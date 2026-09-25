"""commons 的投稿檢查、入庫與查閱：欄位與附檔檢查、內容 sha、「像不像」比對、取 slug、入庫與移除、搜尋。"""
import datetime
import hashlib
import os
import re
import shutil
import stat
from pathlib import Path

from aos_team_format import TeamError, bad

from aos_team_commons_base import FIELDS, LIMITS, SIMILAR, SLUG, TAG, TASK, TYPES


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
    if value.split('/')[0] == 'README.md':          # astra 7：README.md/x 也不行（入庫時會撞條目的說明檔）
        bad(where, 'README.md 是條目自己的說明（由 body 生），附件不能叫這個名字、也不能放在它底下', 'BadPath')
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
