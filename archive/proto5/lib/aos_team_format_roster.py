"""名冊 team.json：讀驗、名冊鎖、讀名冊、專案資料夾、按模板列成員。"""
import contextlib
import os
from pathlib import Path

from aos_team_format_base import (
    _int, _metainfo, _obj, _opt_str, _str, _unknown, bad, BEAT, check_name, HUMAN, Layout,
    LIMIT_DEFAULTS, POST_DEFAULTS, ROSTER_TYPE
)
from aos_team_format_io import read_json
from aos_team_format_cmd import _cmd_whitelist, _member_spawn, _mounts, _spawn_cfg, TOOL_ENTRY_KEYS


# ------------------------------------------------------------------ 名冊 ----

MEMBER_KEYS = ('template', 'model', 'mail_to', 'mounts', 'tools', 'spawn', 'commons', 'employment')
EMPLOYMENT = ('regular', 'temp')   # HR 09-25（spec/team/hr.md）：正式員工／臨時工；沒寫＝regular
ROSTER_KEYS = ('_metainfo', 'project', 'tz', 'members', 'limits', 'post', 'cmd_ok', 'spawn', 'budget', 'commons')


def validate_roster(obj, where='team.json'):
    """驗 team.json，回補好預設值的新物件（原物件不動）。"""
    _obj(obj, where)
    _unknown(obj, ROSTER_KEYS, where)
    _metainfo(obj, ROSTER_TYPE, where)
    out = {'project': _str(obj.get('project'), where + '.project'),
           'tz': _opt_str(obj.get('tz'), where + '.tz'),
           'members': {}, 'limits': dict(LIMIT_DEFAULTS), 'post': dict(POST_DEFAULTS),
           'cmd_ok': _cmd_whitelist(obj.get('cmd_ok', []), where + '.cmd_ok'),
           'spawn': _spawn_cfg(obj.get('spawn', {}), where + '.spawn')}
    import aos_team_commons                    # 09-25 commons：頂層與成員層的 commons 開關（commons.md）
    aos_team_commons.validate_roster_keys(obj, where)
    if 'commons' in obj:
        out['commons'] = obj['commons']
    post = _obj(obj.get('post', {}), where + '.post')
    _unknown(post, tuple(POST_DEFAULTS), where + '.post')
    import aos_team_cost                      # 財務部（spec/team/cost.md）：預算形狀在那邊驗
    try:
        out['budget'] = aos_team_cost.check_budget(obj.get('budget'), where + '.budget')
    except ValueError as e:
        bad(where + '.budget', str(e))
    if 'interval_s' in post:
        out['post']['interval_s'] = _int(post['interval_s'], where + '.post.interval_s', 1, 3600)
    members = _obj(obj.get('members'), where + '.members')
    if not members:
        bad(where + '.members', '至少要有一個成員')
    limits = _obj(obj.get('limits', {}), where + '.limits')
    _unknown(limits, tuple(LIMIT_DEFAULTS), where + '.limits')
    for k, v in limits.items():
        out['limits'][k] = _int(v, '%s.limits.%s' % (where, k), 1, 100000)
    if len(members) > out['limits']['max_members']:
        bad(where + '.members', '%d 個成員，超過 limits.max_members=%d' % (len(members), out['limits']['max_members']))
    for name, m in members.items():
        w = '%s.members.%s' % (where, name)
        check_name(name, w)
        _obj(m, w)
        _unknown(m, MEMBER_KEYS, w)
        mail_to = m.get('mail_to', [])
        if not isinstance(mail_to, list) or not all(isinstance(x, str) for x in mail_to):
            bad(w + '.mail_to', '要是名字的陣列')
        for x in mail_to:
            if x not in (HUMAN, BEAT) and x not in members:
                bad(w + '.mail_to', '%s 不在名冊裡（也不是 human、beat）' % x)
            if x == name:
                bad(w + '.mail_to', '不能寄給自己')
        mounts = _mounts(m.get('mounts', {}), w + '.mounts')
        tools = m.get('tools', [])
        if not isinstance(tools, list):
            bad(w + '.tools', '要是陣列')
        for i, t in enumerate(tools):
            _obj(t, '%s.tools[%d]' % (w, i))
            _unknown(t, TOOL_ENTRY_KEYS, '%s.tools[%d]' % (w, i))
            _str(t.get('pack'), '%s.tools[%d].pack' % (w, i))
        out['members'][name] = {
            'template': _str(m.get('template'), w + '.template'),
            'model': _opt_str(m.get('model'), w + '.model'),
            'mail_to': list(dict.fromkeys(mail_to)),
            'mounts': dict(mounts), 'tools': list(tools),
            'spawn': _member_spawn(m.get('spawn'), w + '.spawn'),
            'employment': _employment(m.get('employment', 'regular'), w + '.employment')}
        if 'commons' in m:
            out['members'][name]['commons'] = m['commons']
    return out


def _employment(v, where):
    if v not in EMPLOYMENT:
        bad(where, '要是 regular（正式員工）或 temp（臨時工），不是 %r' % (v,))
    return v


@contextlib.contextmanager
def roster_lock(lay):
    """改 team.json（讀→檢查→改→寫）時拿的一把鎖：郵差不用人批生成員、人 spawn approve、aos-team rm 共用，
    免得兩邊同時讀到舊名冊、後寫的蓋掉先寫的（astra 09-25）。人用文字編輯器改不受這把鎖管。"""
    import fcntl
    lay.team.mkdir(parents=True, exist_ok=True)
    with open(lay.team / '.roster.lock', 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load_roster(team_dir):
    lay = Layout(team_dir)
    return validate_roster(read_json(lay.roster), str(lay.roster))


def project_dir(team_dir, roster):
    """project 相對 team.json 所在資料夾；回絕對路徑（不檢查存在）。"""
    p = os.path.expanduser(roster['project'])
    return Path(os.path.abspath(os.path.join(Layout(team_dir).root, p)))


def members_by_template(roster, template):
    """名冊裡用這個模板的成員。自訂模板（含 / 的資料夾路徑）看資料夾名：叫 lead、reviewer 的就算領隊、審查員
    （09-25 arknights 隊修：之前自訂模板的領隊、審查員認不出來，門房說沒有領隊、審查單開不出去）。"""
    def same(name):
        return name == template or ('/' in name and Path(name.rstrip('/')).name == template)
    return [n for n, m in roster['members'].items() if same(m['template'])]
