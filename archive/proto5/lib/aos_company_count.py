"""數人頭、數 cpu 與狀態：正式員工人頭、`aos-kernel ls --json` 的 cpu、上限檢查、daemon 家與環境、狀態資料與印法。"""
import json
import os
from pathlib import Path
import subprocess

import aos_team_format as fmt
from aos_team_format import Layout, TeamError

from aos_company_config import CLI, LIMIT_KEYS, load, team_dirs
from aos_company_switchboard import Switchboard


# ------------------------------------------------------------------ 數人頭、數 cpu ----

def headcount(cdir, cfg):
    """正式／臨時看名冊的 employment（HR 部 hr.md §7：人寫的預設 regular、spawn 生的 temp）；company.json 的 staff 只記兼任角色。"""
    regular, temp, rows = [], [], []
    for dept, tdir in sorted(team_dirs(cdir, cfg).items()):
        try:
            roster = fmt.load_roster(tdir)
        except TeamError:
            continue
        for name, m in roster['members'].items():
            staff = cfg['staff'].get(name)
            emp = m.get('employment', 'regular')
            (regular if emp == 'regular' else temp).append(name)
            rows.append({'dept': dept, 'name': name, 'template': m['template'], 'model': m['model'],
                         'employment': emp, 'roles': (staff or {}).get('roles', [])})
    return regular, temp, rows


def cpu_from_ls(ls):
    """aos-kernel ls --json → (cpu 顆數, llm cpu 顆數)：llm 池以外的 want 加總、llm 池的 want。
    跟 HR 部 count_cpus 同一個算法（cpu 不含 llm 池）。"""
    pools = (ls or {}).get('pools') or {}
    llm = int((pools.get('llm') or {}).get('want') or 0)
    total = sum(int(p.get('want') or 0) for name, p in pools.items() if name != 'llm')
    return total, llm


def caps_line(counts, limits):
    return '正式 %d/%d、cpu %d/%d、llm cpu %d/%d' % (
        counts['regular'], limits['regular'], counts['cpu'], limits['cpu'], counts['llm_cpu'], limits['llm_cpu'])


def over_caps(counts, limits):
    return [k for k in LIMIT_KEYS if counts[k] > limits[k]]


def daemon_dir(cdir, cfg):
    return Path(os.path.abspath(Path(cdir) / cfg['daemon']))


def own_daemon(cdir, cfg):
    """daemon 在公司資料夾裡（預設 <公司>/D，董事 09-25：一家一個 daemon＋kernel）＝只有這家用。"""
    c, d = str(Path(os.path.abspath(str(cdir)))), str(daemon_dir(cdir, cfg))
    return d.startswith(c.rstrip('/') + '/')


def env_for(cdir, cfg, daemon=False):
    """給 aos-team 的環境：這家的 kernel、HR 家＝K/hr（不管外面設了什麼 AOS_HR_HOME）。
    AOS_DAEMON_HOME：daemon 是這家自己的（在公司資料夾裡，預設）＝照帶，HR 數 cpu 只數得到自己；
    幾家共用 daemon（company.json 寫 "daemon": "../D"）＝不帶，免得 HR 把別家的 kernel 也數進來互相擋。
    開關機、建 kernel（daemon=True）一律帶。"""
    cdir = Path(cdir)
    e = dict(os.environ)
    e['PATH'] = '%s:%s' % (CLI, e.get('PATH', os.defpath))
    e['AOS_KERNEL_HOME'] = str(cdir / 'K')
    e['AOS_HR_HOME'] = str(cdir / 'K' / 'hr')
    e.pop('AOS_DAEMON_HOME', None)
    if daemon or own_daemon(cdir, cfg):
        e['AOS_DAEMON_HOME'] = str(daemon_dir(cdir, cfg))
    e['PYTHONDONTWRITEBYTECODE'] = '1'
    e.pop('AOS_TEAM_HOME', None)
    return e


def kernel_ls(cdir, cfg):
    if not (Path(cdir) / 'K').is_dir():
        return None
    r = subprocess.run([str(CLI / 'aos-kernel'), 'ls', '--json'], env=env_for(cdir, cfg, daemon=True), capture_output=True,
                       text=True, timeout=60, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def status_data(cdir, cfg=None, ls=None, use_kernel=True):
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = cfg or load(cdir)
    regular, temp, rows = headcount(cdir, cfg)
    if ls is None and use_kernel:
        ls = kernel_ls(cdir, cfg)
    if ls is not None:
        cpu, llm = cpu_from_ls(ls)
        h = ls.get('health')
        code = h if isinstance(h, str) else (h or {}).get('code') if isinstance(h, dict) else None
        # health 不是 ok＝照實說（down 之後是 stopped，不再印 up；試玩 09-25）
        kernel = 'up' if code in (None, 'ok') else '%s（%s）' % (code, (h.get('message') if isinstance(h, dict) else '') or '')
    else:
        cpu, llm = cfg['pools']['default'], cfg['pools']['llm']
        kernel = 'down（cpu 照 company.json 的池算）'
    counts = {'regular': len(regular), 'cpu': cpu, 'llm_cpu': llm}
    sb = Switchboard(cdir, cfg)
    depts = []
    tdirs = team_dirs(cdir, cfg)
    for key, d in cfg['departments'].items():
        row = {'dept': key, 'title': d['title'], 'state': d['state'], 'team': d['team'], 'part_of': d['part_of'],
               'members': [r['name'] for r in rows if r['dept'] == key], 'tasks_open': 0, 'tasks_all': 0,
               'questions': 0}
        if key in tdirs:
            lay = Layout(tdirs[key])
            for p in fmt.json_files(lay.tasks) if lay.tasks.is_dir() else []:
                try:
                    t = fmt.read_json(p)
                except TeamError:
                    continue
                if t.get('parent'):
                    continue
                row['tasks_all'] += 1
                row['tasks_open'] += t.get('status') not in fmt.TERMINAL
            for p in fmt.json_files(lay.wait_user) if lay.wait_user.is_dir() else []:
                try:
                    row['questions'] += fmt.read_json(p).get('status') == 'open'
                except TeamError:
                    pass
        depts.append(row)
    orders = sb.all_orders()
    return {'name': cfg['name'], 'stage': cfg['stage'], 'kernel': kernel, 'counts': counts, 'limits': cfg['limits'],
            'limits_max': cfg['limits_max'], 'over': over_caps(counts, cfg['limits']), 'temp': len(temp),
            'caps': caps_line(counts, cfg['limits']), 'departments': depts, 'staff': rows,
            'orders': [{k: o[k] for k in ('id', 'status', 'via', 'task', 'text')} | {'to': o['to']['dept'],
                        'from': sb._who(o)} for o in orders],
            'board_letters': len(sb.board_letters()),
            'hr_env': {'AOS_KERNEL_HOME': str(cdir / 'K'), 'AOS_HR_HOME': str(cdir / 'K' / 'hr')}}


def print_status(s):
    print('公司 %s（%s）  kernel %s' % (s['name'], s['stage'], s['kernel']))
    print(s['caps'] + ('  ← 超過：%s' % '、'.join(s['over']) if s['over'] else '') + '  （臨時工 %d，不算人頭）' % s['temp'])
    for d in s['departments']:
        where = d['team'] or ('併在 %s' % d['part_of'] if d['part_of'] else '沒有團隊')
        print('  %-5s %-8s %-18s 成員 %-2d 單 %d 進行／%d 全部  等人答 %d  %s' % (
            d['dept'], d['title'][:8], where, len(d['members']), d['tasks_open'], d['tasks_all'], d['questions'],
            d['state']))
    for o in s['orders'][-8:]:
        print('  總機 %s  %s → %s  %s  %s  %s' % (o['id'], o['from'], o['to'], o['status'], o['task'] or '-',
                                              o['text'][:40].replace('\n', ' ')))
    print('董事收件匣：%d 封（company.py mail 看）' % s['board_letters'])
    if s.get('hr_env'):     # 真跑 09-25：aos-team hr cap 不帶這兩個就找不到 HR 家
        print('HR 自己查：%s aos-team hr cap（或 company.py hr cap 自動帶）' % ' '.join(
            '%s=%s' % kv for kv in sorted(s['hr_env'].items())))
