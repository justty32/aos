"""aos-team hr：HR 部（spec/team/hr.md）。薪資表、試用（換模型跑同一份任務集、打分、記紀錄、照規則調薪）、
政策（正式員工人頭、cpu 上限）。大半是程式：不叫模型；只有 trial 跑的那支試用團隊會叫模型。

HR 的檔都在「HR 家」：--hr DIR，沒給看 AOS_HR_HOME，再沒有＝$AOS_KERNEL_HOME/hr。
  salary.json   薪資表（人可用文字編輯器改）
  policy.json   政策（人改；沒有＝內建預設 DEFAULT_POLICY）
  trials.jsonl  試用紀錄（一行一次，只追加）
  teams.json    登記過的團隊資料夾（數全公司正式員工用；init／hr 指令會自動登記）
  trials/tr-NNNN/  每次試用的團隊副本（team/）與專案副本（proj/）
"""
import argparse
import contextlib
import datetime
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from aos_team_format import (Layout, TeamError, load_roster, read_json, roster_lock, template_dir, validate_roster,
                             write_json)

TIERS = ('程式', '笨', '中', '強')          # 由便宜到貴；「程式」＝這個位子已經不用模型
STAGES = {                 # 董事 09-25：先當新創（小），擴張後才用大的；policy.json 寫 stage 選一組，寫了數字就蓋過
    'startup': {'regular_max': 10, 'cpu_max': 20, 'llm_cpu_max': 5},
    'grown': {'regular_max': 100, 'cpu_max': 200, 'llm_cpu_max': 20},
}
DEFAULT_POLICY = {
    '_metainfo': {'_type': 'aos_hr_policy', '_version': 1},
    'stage': 'startup',        # startup＝新創（預設）、grown＝擴張後
    'regular_max': 10,         # 正式員工（employment=regular）人頭上限，跨所有登記的團隊
    'cpu_max': 20,             # 全公司 kernel 開著的 cpu（不含 llm 池）
    'llm_cpu_max': 5,          # 全公司 llm 池的 cpu
    'margin': 5,               # 調薪：試用分數 ≥ 強模型基準 − margin（滿分 100）
    'expand': {'backlog_min': 3, 'qc_below': 80},   # 擴編理由的門檻（spec/team/hr.md〈擴編規則〉）
}
DEFAULT_TIERS = {'chatgpt-gpt-6-astra': '強', 'claude-opus-5': '強', 'claude-fable-5-1': '強',
                 'chatgpt-gpt-5.6-sol': '中', 'claude-sonnet-5': '中',
                 'deepseek-chat': '笨', 'chatgpt-gpt-5.6-luna-nothink': '笨'}
TERMINAL = ('done', 'failed', 'cancelled')
CLI = Path(__file__).resolve().parent.parent / 'cli' / 'aos-team'


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


# --------------------------------------------------------------- HR 家 ----

def hr_home(given=None, env=None):
    env = os.environ if env is None else env
    if given:
        return Path(os.path.abspath(os.path.expanduser(given)))
    if env.get('AOS_HR_HOME'):
        return Path(os.path.abspath(os.path.expanduser(env['AOS_HR_HOME'])))
    k = env.get('AOS_KERNEL_HOME')
    if k and os.path.isabs(k):
        return Path(k) / 'hr'
    raise TeamError('Usage', '找不到 HR 家：給 --hr DIR，或設 AOS_HR_HOME，或設 AOS_KERNEL_HOME（用 $AOS_KERNEL_HOME/hr）')


@contextlib.contextmanager
def hr_lock(hr):
    hr.mkdir(parents=True, exist_ok=True)
    with open(hr / '.hr.lock', 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load_policy(hr):
    p = Path(hr) / 'policy.json'
    out = json.loads(json.dumps(DEFAULT_POLICY))
    if not p.exists():
        return out
    raw = read_json(p)
    if not isinstance(raw, dict):
        raise TeamError('FormatInvalid', '%s 要是物件' % p)
    stage = raw.get('stage', 'startup')
    if stage not in STAGES:
        raise TeamError('FormatInvalid', '%s.stage 要是 %s 之一' % (p, '／'.join(STAGES)))
    out['stage'] = stage
    out.update(STAGES[stage])
    for k, v in raw.items():
        if k in ('_metainfo', 'stage'):
            continue
        if k not in DEFAULT_POLICY:
            raise TeamError('FormatInvalid', '%s：不認得的欄位 %s（可用：%s）' % (p, k, '、'.join(
                x for x in DEFAULT_POLICY if x != '_metainfo')))
        if k == 'expand':
            if not isinstance(v, dict):
                raise TeamError('FormatInvalid', '%s.expand 要是物件' % p)
            out['expand'].update(v)
        elif not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            raise TeamError('FormatInvalid', '%s.%s 要是不小於 0 的數字' % (p, k))
        else:
            out[k] = v
    return out


def empty_salary():
    return {'_metainfo': {'_type': 'aos_hr_salary', '_version': 1}, 'tiers': dict(DEFAULT_TIERS), 'positions': {}}


def load_salary(hr):
    p = Path(hr) / 'salary.json'
    if not p.exists():
        return empty_salary()
    raw = read_json(p)
    if not isinstance(raw, dict) or not isinstance(raw.get('positions', {}), dict) \
            or not isinstance(raw.get('tiers', {}), dict):
        raise TeamError('FormatInvalid', '%s：要有 tiers（模型代號→等級）與 positions（位子→一列）兩個物件' % p)
    for code, t in raw.get('tiers', {}).items():
        if t not in TIERS:
            raise TeamError('FormatInvalid', '%s.tiers.%s：等級要是 %s 之一' % (p, code, '／'.join(TIERS)))
    raw.setdefault('tiers', {})
    raw.setdefault('positions', {})
    return raw


def save_salary(hr, sal):
    Path(hr).mkdir(parents=True, exist_ok=True)
    write_json(Path(hr) / 'salary.json', sal, indent=2)


def tier_of(sal, model):
    if model is None:
        return '程式'
    return sal.get('tiers', {}).get(model)


def cheaper(a, b):
    """等級 a 比 b 便宜？（不明＝False）"""
    return a in TIERS and b in TIERS and TIERS.index(a) < TIERS.index(b)


def read_trials(hr):
    p = Path(hr) / 'trials.jsonl'
    out = []
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and 'id' in rec:
                out.append(rec)
    return out


def append_trial(hr, rec):
    with open(Path(hr) / 'trials.jsonl', 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')


def next_trial_id(hr):
    nums = [int(r['id'][3:]) for r in read_trials(hr) if str(r['id']).startswith('tr-') and r['id'][3:].isdigit()]
    d = Path(hr) / 'trials'
    if d.is_dir():
        nums += [int(p.name[3:]) for p in d.iterdir() if p.name.startswith('tr-') and p.name[3:].isdigit()]
    return 'tr-%04d' % (max(nums, default=0) + 1)


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
    p = Path(hr) / 'teams.json'
    with hr_lock(Path(hr)):
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
    _, by = count_regular(hr, team_dir)
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


# ------------------------------------------------------------------ ls ----

def ls_rows(team_dir, hr):
    roster = load_roster(team_dir)
    sal = load_salary(hr)
    rows = []
    for name, m in roster['members'].items():
        model = member_model(roster, name)
        pos = sal['positions'].get(m['template']) or {}
        mp = pos.get('min_pass') or {}
        rows.append({'name': name, 'position': m['template'], 'model': model, 'tier': tier_of(sal, model) or '?',
                     'employment': m['employment'], 'min_pass': mp.get('model'), 'min_pass_tier': mp.get('tier'),
                     'evidence': mp.get('trial')})
    return rows


def cmd_ls(team_dir, hr, args):
    rows = ls_rows(team_dir, hr)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print('%-12s %-10s %-6s %-30s %-4s %s' % ('成員', '位子', '類型', '模型', '等級', '最低通過（證據）'))
    for r in rows:
        mp = '%s（%s，%s）' % (r['min_pass'], r['min_pass_tier'], r['evidence']) if r['min_pass'] else '—（沒試過）'
        print('%-12s %-10s %-6s %-30s %-4s %s' % (r['name'], r['position'], '正式' if r['employment'] == 'regular'
                                                   else '臨時', r['model'], r['tier'], mp))
    return 0


# ----------------------------------------------------------------- set ----

def set_member(team_dir, hr, name, model=None, employment=None, restart=True, env=None, out=print):
    """改名冊一個成員的 model／employment；model 改了也改它家的 info.json、登記著就重啟。"""
    env = os.environ if env is None else env
    lay = Layout(team_dir)
    with roster_lock(lay):
        raw = read_json(lay.roster)
        if name not in raw.get('members', {}):
            raise TeamError('NotFound', '%s 不在名冊裡（有：%s）' % (name, '、'.join(raw.get('members', {}))))
        row = raw['members'][name]
        if model is not None:
            row['model'] = model
        if employment is not None:
            row['employment'] = employment
        after = validate_roster(raw, str(lay.roster))
        if employment == 'regular':
            check_regular(hr, team_dir, after)
        write_json(lay.roster, raw, indent=2)
    register_team(hr, team_dir)
    out('team.json 的 %s 改好了%s%s' % (name, '：model=%s' % model if model else '',
                                        '：employment=%s' % employment if employment else ''))
    if model is None:
        return 0
    home = lay.member(name)
    info_p = home / 'info.json'
    if not info_p.exists():
        out('%s 還沒有家；aos-team init 生家時就會用新模型' % name)
        return 0
    info = read_json(info_p)
    info.setdefault('llm', {})['model'] = model
    write_json(info_p, info, indent=2)
    out('%s 的家 info.json 的 llm.model 改成 %s' % (name, model))
    if not restart:
        return 0
    import aos_agent
    import aos_agent_status
    k = aos_agent_status.kernel_status(str(home), env)
    if aos_agent_status.unregistered(k):
        out('%s 沒登記在 kernel，不用重啟' % name)
        return 0
    rc = aos_agent.stop(str(home), env=env)
    rc = rc or aos_agent.start(str(home), env=env)
    out('%s 重啟%s' % (name, '好了' if rc == 0 else '失敗（aos-agent status --target %s 看）' % home))
    return 1 if rc else 0


# --------------------------------------------------------------- trial ----

def load_taskset(path):
    path = Path(os.path.abspath(os.path.expanduser(path)))
    ts = read_json(path)
    if not isinstance(ts, dict):
        raise TeamError('FormatInvalid', '%s 要是物件' % path)
    for k in ('name', 'project', 'asks'):
        if k not in ts:
            raise TeamError('FormatInvalid', '%s 缺 %s（任務集要有 name、project、asks）' % (path, k))
    if not isinstance(ts['asks'], list) or not ts['asks'] or not all(isinstance(a, str) for a in ts['asks']):
        raise TeamError('FormatInvalid', '%s.asks 要是一句句話的陣列' % path)
    ts['_dir'] = path.parent
    ts['_path'] = str(path)
    return ts


def trial_roster(raw, member, model):
    """原名冊的副本：project 指 ../proj、那個成員換模型。原物件不動。"""
    out = json.loads(json.dumps(raw))
    out['project'] = '../proj'
    out['members'][member]['model'] = model
    return out


def _team(cli_env, team, *argv, timeout=300):
    return subprocess.run([sys.executable, str(CLI)] + [str(a) for a in argv] + ['--target', str(team)],
                          env=cli_env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def run_score_cmd(cmd, cwd, env, timeout=900):
    """評分指令：stdout 最後一行非空的要是 JSON 物件，至少有 score（0～100）、mech_ok（布林）。"""
    try:
        r = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {'score': None, 'mech_ok': False, 'error': '評分指令跑不起來：%s' % e}
    lines = [x for x in r.stdout.splitlines() if x.strip()]
    try:
        res = json.loads(lines[-1])
        if not isinstance(res, dict):
            raise ValueError
    except (ValueError, IndexError):
        return {'score': None, 'mech_ok': False,
                'error': '評分指令退 %d，最後一行不是 JSON 物件：%s' % (r.returncode, (r.stdout + r.stderr)[-300:])}
    if r.returncode != 0:
        res.setdefault('error', '評分指令退 %d' % r.returncode)
    s = res.get('score')
    res['score'] = s if isinstance(s, (int, float)) and not isinstance(s, bool) else None
    res['mech_ok'] = res.get('mech_ok') is True
    return res


def verdict(hr, rec, policy, sal):
    """調薪規則：回 (verdict, why)；通過就更新 sal（呼叫者存檔）。"""
    pos, ts = rec['position'], rec['taskset']
    if rec['tier'] == '強':
        return '基準', '強模型的分數當這個位子、這份任務集的基準'
    base = [r for r in read_trials(hr) if r['position'] == pos and r['taskset'] == ts and r.get('tier') == '強'
            and r.get('mech_ok') and isinstance(r.get('score'), (int, float))]
    if rec['tier'] not in TIERS:
        return '等級不明', '模型 %s 不在 salary.json 的 tiers；先補上它的等級' % rec['model']
    if not base:
        return '沒有基準', '這個位子（%s）、任務集（%s）還沒有強模型機械全過的試用；先試一次強模型' % (pos, ts)
    b = base[-1]
    need = b['score'] - policy['margin']
    if rec['score'] is None or not rec['mech_ok'] or rec['score'] < need:
        why = '分數 %s（要 ≥ %s＝基準 %s 的 %s − margin %s）、機械檢查%s' % (
            rec['score'], need, b['id'], b['score'], policy['margin'], '全過' if rec['mech_ok'] else '沒全過')
        if rec.get('status') != 'done':
            why += '（單子沒走到 done：%s；mech_ok 要單子 done 才算）' % rec.get('status')
        return '不通過', why
    row = sal['positions'].setdefault(pos, {})
    cur = (row.get('min_pass') or {}).get('tier')
    why = '分數 %s ≥ %s（基準 %s 的 %s − %s），機械全過' % (rec['score'], need, b['id'], b['score'], policy['margin'])
    if cur is None or cheaper(rec['tier'], cur) or cur == rec['tier']:
        row['min_pass'] = {'model': rec['model'], 'tier': rec['tier'], 'trial': rec['id'], 'baseline': b['id'],
                           'at': rec['at']}
        row.setdefault('evidence', [])
        for x in (b['id'], rec['id']):
            if x not in row['evidence']:
                row['evidence'].append(x)
        return '通過', why + '；薪資表 %s 的最低通過改成 %s（%s）' % (pos, rec['model'], rec['tier'])
    return '通過', why + '；薪資表原本的最低通過（%s）更便宜，不動' % cur


def trial(team_dir, hr, member, model, taskset, score_cmd=None, out_dir=None, timeout=None, env=None,
          note='', out=print):
    env = dict(os.environ if env is None else env)
    lay = Layout(team_dir)
    raw = read_json(lay.roster)
    roster = validate_roster(raw, str(lay.roster))
    if member not in roster['members']:
        raise TeamError('NotFound', '%s 不在名冊裡（有：%s）' % (member, '、'.join(roster['members'])))
    ts = load_taskset(taskset)
    cmd = shlex.split(score_cmd) if score_cmd else ts.get('score_cmd')
    if not cmd:
        raise TeamError('Usage', '要有評分指令：--score-cmd "…" 或任務集的 score_cmd')
    policy = load_policy(hr)
    check_cpus(hr, env, policy)
    with hr_lock(hr):
        tid = next_trial_id(hr)
        base = Path(out_dir) if out_dir else hr / 'trials' / tid
        base.mkdir(parents=True, exist_ok=False)
    team, proj = base / 'team', base / 'proj'
    src = Path(ts['_dir']) / ts['project']
    if not src.is_dir():
        raise TeamError('NotFound', '任務集的 project %s 不在' % src)
    shutil.copytree(src, proj)
    team.mkdir()
    (base / 'roster.json').write_text(json.dumps(trial_roster(raw, member, model), ensure_ascii=False, indent=2),
                                      encoding='utf-8')
    orig_model = member_model(roster, member)
    out('%s：%s 的 %s（位子 %s）%s → %s，任務集 %s，在 %s' % (tid, lay.root.name, member,
                                                   roster['members'][member]['template'], orig_model, model,
                                                   ts['name'], base))
    cli_env = dict(env, PYTHONDONTWRITEBYTECODE='1', AOS_HR_TRIAL=tid)   # 試用副本不登記、不算人頭
    cli_env.pop('AOS_TEAM_HOME', None)
    steps = [('init', '--config', base / 'roster.json')]
    if ts.get('routes'):
        steps.append(('route', 'save', Path(ts['_dir']) / ts['routes']))
    steps.append(('start',))
    for st in steps:
        r = _team(cli_env, team, *st)
        if r.returncode != 0:
            _team(cli_env, team, 'stop')
            raise TeamError('TrialSetup', 'aos-team %s 失敗：%s' % (st[0], (r.stdout + r.stderr)[-500:]))
    t0 = time.time()
    for a in ts['asks']:
        _team(cli_env, team, 'ask', a)
    limit = timeout or ts.get('timeout_s', 900)
    expect = ts.get('expect_tasks', len(ts['asks']))
    status, answered = 'timeout', set()
    while time.time() - t0 < limit:
        time.sleep(3)
        if ts.get('answer'):
            r = _team(cli_env, team, 'wait', 'ls', '--json')
            try:
                for q in json.loads(r.stdout or '[]'):
                    if q['id'] not in answered:
                        answered.add(q['id'])
                        _team(cli_env, team, 'answer', q['id'], ts['answer'])
            except (ValueError, KeyError, TypeError):
                pass
        r = _team(cli_env, team, 'task', 'ls', '--all', '--json')
        try:
            top = [t for t in json.loads(r.stdout or '[]') if not t.get('parent')]
        except ValueError:
            continue
        if len(top) >= expect and all(t['status'] in TERMINAL for t in top):
            status = 'done' if all(t['status'] == 'done' for t in top) else 'failed'
            break
    wall = round(time.time() - t0, 1)
    _team(cli_env, team, 'stop')
    sc = _team(cli_env, team, 'score', '--json')
    try:
        six = json.loads(sc.stdout)
    except ValueError:
        six = {}
    axes = six.get('axes') or {}
    senv = dict(cli_env, AOS_HR_TEAM=str(team), AOS_HR_PROJECT=str(proj), AOS_HR_TRIAL=tid, AOS_HR_STATUS=status)
    res = run_score_cmd(cmd, ts['_dir'], senv)
    sal = load_salary(hr)
    rec = {'id': tid, 'at': now(), 'team': str(lay.root.resolve()), 'member': member,
           'position': roster['members'][member]['template'], 'from_model': orig_model, 'model': model,
           'tier': tier_of(sal, model) or '?', 'taskset': ts['name'], 'taskset_path': ts['_path'],
           'score_cmd': cmd, 'status': status, 'score': res['score'], 'mech_ok': res['mech_ok'] and status == 'done',
           'score_detail': {k: v for k, v in res.items() if k not in ('score', 'mech_ok')},
           'tokens': (axes.get('R') or {}).get('tokens'), 'wall_s': wall,
           'think': (axes.get('L') or {}).get('think'),
           'think_by_member': (axes.get('L') or {}).get('by_member'),
           'axes': {k: (axes.get(k) or {}).get('score') for k in ('L', 'S', 'R', 'F', 'H', 'B')},
           'dir': str(base), 'note': note}
    with hr_lock(hr):
        policy = load_policy(hr)
        sal = load_salary(hr)
        row = sal['positions'].setdefault(rec['position'], {})
        row.setdefault('model', orig_model)
        row.setdefault('tier', tier_of(sal, orig_model) or '?')
        row.setdefault('employment', roster['members'][member]['employment'])
        rec['verdict'], rec['why'] = verdict(hr, rec, policy, sal)
        append_trial(hr, rec)
        save_salary(hr, sal)
    register_team(hr, team_dir)
    print_trials([rec], out)
    out('判定：%s——%s' % (rec['verdict'], rec['why']))
    return rec


# -------------------------------------------------------------- trials ----

def print_trials(recs, out=print):
    out('%-8s %-10s %-28s %-4s %-12s %-7s %-5s %-4s %-8s %-6s %-11s %s' % (
        '試用', '位子', '模型', '等級', '任務集', '結果', '分數', '機械', 'token', '秒', 'L S R F H B', '判定'))
    for r in recs:
        ax = ' '.join('-' if (r.get('axes') or {}).get(k) is None else str(r['axes'][k]) for k in 'LSRFHB')
        out('%-8s %-10s %-28s %-4s %-12s %-7s %-5s %-4s %-8s %-6s %-11s %s' % (
            r['id'], r['position'], r['model'], r.get('tier', '?'), r['taskset'], r.get('status'),
            '-' if r.get('score') is None else r['score'], '過' if r.get('mech_ok') else '沒過',
            '-' if r.get('tokens') is None else r['tokens'], r.get('wall_s'), ax, r.get('verdict')))


def cmd_hr(team_dir, argv):
    ap = Parser(prog='aos-team hr', description='HR：薪資表、試用、調薪（spec/team/hr.md）')
    ap.add_argument('--hr', help='HR 家（預設 AOS_HR_HOME，再沒有 $AOS_KERNEL_HOME/hr）')
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('ls', help='每個成員：位子、模型、等級、員工類型、最低通過')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('set', help='改名冊一個成員的模型或員工類型（model 改了連家一起改、登記著就重啟）')
    p.add_argument('name')
    p.add_argument('--model')
    p.add_argument('--employment', choices=('regular', 'temp'))
    p.add_argument('--no-restart', action='store_true')
    p = sub.add_parser('trial', help='換模型試用：複製團隊、換一個成員的模型、跑任務集、評分、記紀錄、照規則調薪')
    p.add_argument('--member', required=True)
    p.add_argument('--model', required=True, help='llm.json 裡的模型代號')
    p.add_argument('--taskset', required=True, help='任務集 JSON（spec/team/hr.md〈任務集〉）')
    p.add_argument('--score-cmd', help='評分指令（蓋過任務集的 score_cmd）')
    p.add_argument('--out', help='試用資料夾（預設 HR 家/trials/tr-NNNN）')
    p.add_argument('--timeout', type=int)
    p.add_argument('--note', default='')
    p = sub.add_parser('trials', help='看試用紀錄')
    p.add_argument('--position')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('salary', help='印薪資表')
    p.add_argument('--json', action='store_true')
    sub.add_parser('cap', help='全公司正式員工人頭、cpu、llm cpu 與上限；這隊的積壓與擴編理由')
    args = ap.parse_args(argv)
    if not args.cmd:
        print(ap.format_help())
        return 2
    hr = hr_home(args.hr)
    if args.cmd == 'ls':
        return cmd_ls(team_dir, hr, args)
    if args.cmd == 'set':
        if args.model is None and args.employment is None:
            raise TeamError('Usage', 'hr set 要給 --model 或 --employment')
        return set_member(team_dir, hr, args.name, args.model, args.employment, restart=not args.no_restart)
    if args.cmd == 'trial':
        rec = trial(team_dir, hr, args.member, args.model, args.taskset, args.score_cmd, args.out, args.timeout,
                    note=args.note)
        return 0 if rec['status'] == 'done' else 1
    if args.cmd == 'trials':
        recs = [r for r in read_trials(hr) if not args.position or r.get('position') == args.position]
        if args.json:
            print(json.dumps(recs, ensure_ascii=False, indent=2))
        elif not recs:
            print('還沒有試用紀錄（%s）' % (hr / 'trials.jsonl'))
        else:
            print_trials(recs)
        return 0
    if args.cmd == 'salary':
        sal = load_salary(hr)
        if args.json:
            print(json.dumps(sal, ensure_ascii=False, indent=2))
            return 0
        print('%-10s %-6s %-28s %-4s %-28s %s' % ('位子', '類型', '目前模型', '等級', '最低通過', '證據'))
        for pos, row in sorted(sal['positions'].items()):
            mp = row.get('min_pass') or {}
            print('%-10s %-6s %-28s %-4s %-28s %s' % (pos, row.get('employment', '-'), row.get('model', '-'),
                                                      row.get('tier', '-'),
                                                      '%s（%s）' % (mp['model'], mp['tier']) if mp else '—',
                                                      '、'.join(row.get('evidence', [])) or '—'))
        return 0
    if args.cmd == 'cap':
        policy = load_policy(hr)
        n, _ = count_regular(hr, team_dir if Layout(team_dir).roster.exists() else None)
        c = count_cpus()
        print('階段 %s；正式員工 %d／%d 人（跨 %s 登記的團隊）' % (policy['stage'], n, policy['regular_max'],
                                                          hr / 'teams.json'))
        print('cpu %d／%d、llm cpu %d／%d（%d 個 kernel）' % (c['cpu'], policy['cpu_max'], c['llm_cpu'],
                                                          policy['llm_cpu_max'], len(c['kernels'])))
        if Layout(team_dir).roster.exists():
            print('這隊積壓 %d 張單；擴編理由：%s' % (backlog(team_dir), expand_reason(hr, team_dir, policy) or '沒有'))
        return 0
    return 2
