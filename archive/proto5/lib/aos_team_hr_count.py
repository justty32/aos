"""HR 的人頭與名額：成員用哪個模型、登記團隊、正式員工人頭與上限、全公司 cpu 計數與上限（init／start／spawn 的擋點）、擴張理由。"""
import os
from pathlib import Path

from aos_team_format import Layout, TeamError, load_roster, read_json, template_dir, write_json

from aos_team_hr_book import hr_lock, load_policy, read_trials, TERMINAL


# ------------------------------------------------------------ 成員與模型 ----

def member_model(roster, name):
    """成員實際用的模型代號：名冊 model → 模板 llm.model → default。"""
    m = roster['members'][name]
    if m.get('model'):
        return m['model']
    try:
        tpl = read_json(template_dir(m['template']) / 'template.json')
        return (tpl.get('llm') or {}).get('model') or 'default'
    except TeamError:
        return 'default'


def register_team(hr, team_dir):
    """把團隊資料夾記進 HR 的 teams.json（數全公司正式員工用）。"""
    with hr_lock(Path(hr)):
        register_team_locked(hr, team_dir)


def register_team_locked(hr, team_dir):
    """同上，呼叫者已經拿著 hr_lock。"""
    p = Path(hr) / 'teams.json'
    teams = read_json(p) if p.exists() else []
    if not isinstance(teams, list):
        teams = []
    team_dir = str(Path(team_dir).resolve())
    if team_dir not in teams:
        teams.append(team_dir)
        write_json(p, teams, indent=2)


def count_regular(hr, extra_team=None):
    """跨所有登記的團隊數 employment=regular 的成員；回 (人數, {團隊: 人數})。讀不到的團隊略過（不算）。"""
    p = Path(hr) / 'teams.json'
    teams = read_json(p) if p.exists() else []
    teams = [t for t in teams if isinstance(t, str)]
    if extra_team and str(Path(extra_team).resolve()) not in teams:
        teams.append(str(Path(extra_team).resolve()))
    by = {}
    for t in teams:
        try:
            r = load_roster(t)
        except TeamError:
            continue
        by[t] = sum(1 for m in r['members'].values() if m['employment'] == 'regular')
    return sum(by.values()), by


def check_regular(hr, team_dir, roster_after, policy=None):
    """team_dir 的名冊換成 roster_after 之後，全公司正式員工會不會超過 regular_max；超了丟 TooMany。"""
    policy = policy or load_policy(hr)
    _, by = count_regular(hr, team_dir)   # 呼叫者要拿著 hr_lock 才算數（set_member、aos_team._hr_gate）
    key = str(Path(team_dir).resolve())
    by[key] = sum(1 for m in roster_after['members'].values() if m['employment'] == 'regular')
    total = sum(by.values())
    if total > policy['regular_max']:
        raise TeamError('TooMany', '全公司正式員工會變成 %d 人，超過 policy.json 的 regular_max=%d；'
                                   '改成臨時工（employment: temp）或先收掉別的正式員工' % (total, policy['regular_max']))
    return total


def is_llm_pool(name, pool):
    return name == 'llm' or 'AOS_LLM_CONFIG' in (pool.get('envs') or {})


def count_cpus(env=None):
    """全公司開著的 cpu：AOS_DAEMON_HOME 登記的每個 kernel（沒設就只看 AOS_KERNEL_HOME）的池表 count 加總。
    回 {'cpu': n, 'llm_cpu': m, 'kernels': [kernel 家…]}；一個 kernel 讀不到就略過。"""
    env = os.environ if env is None else env
    homes = []
    d = env.get('AOS_DAEMON_HOME')
    if d and os.path.isabs(d):
        try:
            import aos_daemon_ticks
            homes = [r['home'] for r in aos_daemon_ticks.registered(d)]
        except Exception:                   # noqa: BLE001  daemon 家壞了：退回只看自己的 kernel
            homes = []
    k = env.get('AOS_KERNEL_HOME')
    if k and os.path.isabs(k) and k not in homes:
        homes.append(k)
    cpu = llm = 0
    seen = []
    for h in homes:
        try:
            info = read_json(Path(h) / 'info.json')
            pools = info.get('pools') or {}
        except TeamError:
            continue
        seen.append(h)
        for name, pool in pools.items():
            if name == 'kernel' or not isinstance(pool, dict):
                continue
            n = max(0, int(pool.get('count', 0) or 0) - len(pool.get('skip') or []))
            if is_llm_pool(name, pool):
                llm += n
            else:
                cpu += n
    return {'cpu': cpu, 'llm_cpu': llm, 'kernels': seen}


def check_cpus(hr, env=None, policy=None):
    """start／spawn 前的擋點：全公司 cpu、llm cpu 超過 policy 就丟 TooMany。"""
    policy = policy or load_policy(hr)
    c = count_cpus(env)
    if c['cpu'] > policy['cpu_max'] or c['llm_cpu'] > policy['llm_cpu_max']:
        raise TeamError('TooMany', '全公司 cpu %d／上限 %d、llm cpu %d／上限 %d（policy.json）；先 aos-kernel cpu rm 減一些'
                        % (c['cpu'], policy['cpu_max'], c['llm_cpu'], policy['llm_cpu_max']))
    return c


def backlog(team_dir):
    """積壓量：還沒結束的頂層單數（擴編理由之一）。"""
    lay = Layout(team_dir)
    n = 0
    if lay.tasks.is_dir():
        for p in lay.tasks.glob('t-*.json'):
            try:
                t = read_json(p)
            except TeamError:
                continue
            if not t.get('parent') and t.get('status') not in TERMINAL:
                n += 1
    return n


def expand_reason(hr, team_dir, policy=None):
    """加人的理由（spec/team/hr.md〈擴編規則〉）：積壓 ≥ backlog_min，或這隊最近一次試用／品管分數 < qc_below。
    回白話理由字串；沒有理由回 None。"""
    policy = policy or load_policy(hr)
    b = backlog(team_dir)
    if b >= policy['expand']['backlog_min']:
        return '積壓 %d 張單（≥ %d）' % (b, policy['expand']['backlog_min'])
    key = str(Path(team_dir).resolve())
    mine = [r for r in read_trials(hr) if r.get('team') == key and isinstance(r.get('score'), (int, float))]
    if mine and mine[-1]['score'] < policy['expand']['qc_below']:
        return '最近一次分數 %s（< %s，%s）' % (mine[-1]['score'], policy['expand']['qc_below'], mine[-1]['id'])
    return None
