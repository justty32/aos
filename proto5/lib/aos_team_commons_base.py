"""公共資料夾 commons 的底：常數與上限、在哪與誰開（名冊設定、圖書館員）、資料夾 Commons 與索引印法。"""
import contextlib
import fcntl
import json
import os
import re
from pathlib import Path

from aos_team_format import TeamError, bad, read_json, write_json, template_may


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
        if not self.index_path.exists():               # astra 11：只建不蓋（別隊可能同時建好又入庫了）
            empty = {'_metainfo': {'_type': INDEX_TYPE, '_version': 1}, 'entries': {}}
            tmp = self.root / ('.index.%d.tmp' % os.getpid())
            tmp.write_text(json.dumps(empty, indent=2) + '\n', encoding='utf-8')
            try:
                os.link(tmp, self.index_path)
                (self.root / 'INDEX.md').write_text(render_index(empty), encoding='utf-8')
            except FileExistsError:
                pass
            finally:
                tmp.unlink(missing_ok=True)
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
