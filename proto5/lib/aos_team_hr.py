"""aos-team hr：HR 部（spec/team/hr.md）。薪資表、試用（換模型跑同一份任務集、打分、記紀錄、照規則調薪）、
政策（正式員工人頭、cpu 上限）。大半是程式：不叫模型；只有 trial 跑的那支試用團隊會叫模型。

HR 的檔都在「HR 家」：--hr DIR，沒給看 AOS_HR_HOME，再沒有＝$AOS_KERNEL_HOME/hr。
  salary.json   薪資表（人可用文字編輯器改）
  policy.json   政策（人改；沒有＝內建預設 DEFAULT_POLICY）
  trials.jsonl  試用紀錄（一行一次，只追加）
  teams.json    登記過的團隊資料夾（數全公司正式員工用；init／hr 指令會自動登記）
  trials/tr-NNNN/  每次試用的團隊副本（team/）與專案副本（proj/）
這個檔留 trial（測試換掉這裡的 _team、check_cpus、time.sleep）、列試用紀錄與命令列；
實作分在 aos_team_hr_book／count／members，這裡匯出外部用到的名字。
"""
import argparse
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from aos_team_format import Layout, TeamError, read_json, validate_roster

from aos_team_hr_book import (
    append_trial, cheaper, CLI, DEFAULT_POLICY, empty_salary, hr_home, hr_lock, load_policy,
    load_salary, next_trial_id, now, read_trials, save_salary, TERMINAL, tier_of, TIERS
)
from aos_team_hr_count import (
    backlog, check_cpus, check_regular, count_cpus, count_regular, expand_reason, member_model,
    register_team, register_team_locked
)
from aos_team_hr_members import cmd_ls, set_member


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


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


def _overlap(a, b):
    a, b = os.path.realpath(a), os.path.realpath(b)
    return a == b or a.startswith(b.rstrip(os.sep) + os.sep) or b.startswith(a.rstrip(os.sep) + os.sep)


def trial_roster(raw, member, model):
    """原名冊的副本：project 指 ../proj、那個成員換模型。原物件不動。"""
    out = json.loads(json.dumps(raw))
    out['project'] = '../proj'
    out['members'][member]['model'] = model
    for m in out['members'].values():       # astra 09-25：多掛的資料夾可能指原專案（可寫），副本一律拿掉
        m.pop('mounts', None)
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
    s = res.get('score')
    ok_num = isinstance(s, (int, float)) and not isinstance(s, bool) and math.isfinite(s) and 0 <= s <= 100
    res['score'] = s if ok_num else None
    res['mech_ok'] = res.get('mech_ok') is True and ok_num
    if not ok_num and s is not None:
        res.setdefault('error', 'score 要是 0～100 的數字，拿到 %r' % (s,))
    if r.returncode != 0:                   # astra 09-25：退非 0＝這次評分不算數，不能拿來調薪
        res.setdefault('error', '評分指令退 %d' % r.returncode)
        res['score'], res['mech_ok'] = None, False
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


def _drive(cli_env, team, ts, timeout, t0):
    """丟每一句、輪詢到頂層單全結束或逾時；有題目而任務集給了 answer 就回。回 done／failed／timeout。"""
    for a in ts['asks']:
        _team(cli_env, team, 'ask', a)
    limit = timeout or ts.get('timeout_s', 900)
    expect = ts.get('expect_tasks', len(ts['asks']))
    answered = set()
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
            return 'done' if all(t['status'] == 'done' for t in top) else 'failed'
    return 'timeout'


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
    import aos_team_format
    orig_proj = aos_team_format.project_dir(lay.root, roster)
    with hr_lock(hr):
        tid = next_trial_id(hr)
        base = Path(os.path.abspath(out_dir)) if out_dir else hr / 'trials' / tid
        for inside in (lay.root, orig_proj):
            if _overlap(base, inside):
                raise TeamError('BadProject', '試用資料夾 %s 跟原團隊／原專案 %s 重疊；換一個 --out' % (base, inside))
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
    status = 'error'
    try:
        status = _drive(cli_env, team, ts, timeout, t0)
    finally:                                # astra 09-25：出了例外也要把試用團隊停掉
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
