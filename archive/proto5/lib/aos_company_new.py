"""生一家公司：照樣板把名冊與門房規則加上成員名前綴、寫出整家、列全公司成員名。"""
import json
import os
from pathlib import Path
import shutil

import aos_team_format as fmt
from aos_team_format import HUMAN, BEAT, POST

from aos_company_config import CompanyError, EXAMPLE, load, PREFIX, team_dirs, validate


# ------------------------------------------------------------------ 生一家 ----

def _prefixed(prefix, name):
    return name if name in (HUMAN, BEAT, POST) else prefix + name


def materialize_roster(src, prefix, project):
    """樣板名冊 → 這家的名冊：成員名、mail_to、成員層 spawn 不動；名字加前綴，project 換成絕對路徑，mounts 展開 ~。"""
    obj = json.loads(json.dumps(src))
    obj['project'] = str(project)
    members = {}
    for name, m in obj['members'].items():
        m = dict(m)
        m['mail_to'] = [_prefixed(prefix, x) for x in m.get('mail_to', [])]
        for k, v in list(m.get('mounts', {}).items()):
            if isinstance(v, dict):
                v['$val'] = os.path.expanduser(v['$val'])
            else:
                m['mounts'][k] = os.path.expanduser(v)
        members[_prefixed(prefix, name)] = m
    obj['members'] = members
    fmt.validate_roster(obj, 'team.json（前綴 %r）' % prefix)
    return obj


def materialize_routes(src, prefix):
    obj = json.loads(json.dumps(src))
    for r in obj.get('routes', []):
        if r.get('do') == 'handoff':
            r['handoff']['assignee'] = _prefixed(prefix, r['handoff']['assignee'])
    return obj


def new(dst, src=EXAMPLE, prefix='', project=None, llm_cpu=None, cpu=None, name=None):
    """照樣板（examples/company）生一家公司的資料夾。已存在＝AlreadyExists（不蓋）。"""
    src, dst = Path(src), Path(os.path.abspath(os.path.expanduser(str(dst))))
    raw = fmt.read_json(src / 'company.json')
    base = validate(raw, str(src / 'company.json'))
    if (dst / 'company.json').exists():
        raise CompanyError('AlreadyExists', '%s 已經有 company.json' % dst)
    if not PREFIX.match(prefix):
        raise CompanyError('Usage', '前綴要是空字串或 [a-z][a-z0-9]{0,7}-（例 c1-）')
    project = Path(os.path.abspath(os.path.expanduser(str(project or base['project'] or dst / 'proj'))))
    out = json.loads(json.dumps(raw))
    out['prefix'] = prefix
    out['name'] = name or (prefix[:-1] if prefix else base['name'])
    out['project'] = str(project)
    if llm_cpu is not None or cpu is not None:
        lim = dict(base['limits'])
        if llm_cpu is not None:
            lim['llm_cpu'] = llm_cpu
        if cpu is not None:
            lim['cpu'] = cpu
        out['limits'] = lim
        pools = dict(base['pools'])
        pools['llm'] = max(1, min(pools['llm'], lim['llm_cpu']))
        pools['default'] = max(1, min(pools['default'], lim['cpu']))
        out['pools'] = pools
    out['staff'] = {_prefixed(prefix, n): s for n, s in raw.get('staff', {}).items()}
    for d in out['departments'].values():
        if d.get('desk'):
            d['desk'] = _prefixed(prefix, d['desk'])
    validate(out, str(dst / 'company.json'))
    dst.mkdir(parents=True, exist_ok=True)
    for key, d in base['departments'].items():
        if d['team'] is None:
            continue
        tsrc = src / d['team']
        tdst = dst / d['team']
        tdst.mkdir(parents=True, exist_ok=True)
        fmt.write_json(tdst / 'team.json', materialize_roster(fmt.read_json(tsrc / 'team.json'), prefix, project),
                       indent=2)
        if (tsrc / 'routes.json').is_file():
            (dst / 'config').mkdir(exist_ok=True)
            fmt.write_json(dst / 'config' / ('%s.routes.json' % key),
                           materialize_routes(fmt.read_json(tsrc / 'routes.json'), prefix), indent=2)
    if (src / 'persona').is_dir():
        shutil.copytree(src / 'persona', dst / 'persona', dirs_exist_ok=True)
    llm = src / base['llm']
    if llm.is_file():
        shutil.copy(llm, dst / 'llm.json')
    out['llm'] = 'llm.json'
    fmt.write_json(dst / 'company.json', out, indent=2)
    return dst


def all_member_names(cdir, cfg=None):
    cfg = cfg or load(cdir)
    names = []
    for dept, tdir in team_dirs(cdir, cfg).items():
        roster = fmt.load_roster(tdir)
        names += list(roster['members'])
    return names
