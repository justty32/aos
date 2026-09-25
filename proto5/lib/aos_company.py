#!/usr/bin/env python3
"""公司（spec/team/company.md；examples/company/）：幾支團隊合成一間公司，加一個機械的總機。

一間公司＝一個資料夾：`company.json`（部門、編制、上限）＋每個部門一支普通的 aos 團隊（`teams/<部門>/`）
＋自己的 kernel（`K/`，池的大小＝這家的 cpu 上限）＋總機的帳（`switchboard/`）。
**總機（relay）不叫模型**：每輪看每個部門寄給 human 的信（`team/human/`）——
  - 第一行寫 `〔給 <部門>〕…` 的＝跨部門的單：開一張總機單 `o-NNNN`，照對方門房的規則開單（命中 handoff）
    或寫信給對方的窗口（沒命中），寄件人都是 human（對方看來就是「公司」交辦的）；
  - 回的是總機單（reply_to 對得上單號、對方的任務單、或那封信）＝抄一封回給下單的人；
  - 其他＝留給董事（`company.py mail` 看）。
人（董事）還是 human：`order` 交給前台部門的門房，`answer` 回各部門的題。

子命令（`python3 aos_company.py <子命令> --company 資料夾 …`；examples/company/company.py 是同一支的包裝）：
  new 資料夾 [--prefix c1-] [--project P] [--llm-cpu N] [--cpu N]   照樣板生一家公司（成員名加前綴）
  up／down／status [--json]／order "一句話" [--to 部門]／relay [--quiet]／mail／answer 部門 q-NNNN "…"
這個檔留開機、關機（測試換掉這裡的 _run）與命令列；實作分在 aos_company_config／new／switchboard／count，
這裡匯出外部用到的名字。
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

import aos_team_format as fmt                                              # noqa: E402
from aos_team_format import TeamError

from aos_company_config import (
    bad, CLI, CompanyError, EXAMPLE, host_dept, load, MARK, PROTO, resolve_dept, STARTUP,
    team_dirs, TERMINAL_STATUS, TYPE, validate
)
from aos_company_new import all_member_names, new
from aos_company_switchboard import Switchboard
from aos_company_count import (
    caps_line, cpu_from_ls, env_for, headcount, over_caps, print_status, status_data
)


# ------------------------------------------------------------------ 開機、關機 ----

def _run(argv, env, check=True, timeout=300):
    r = subprocess.run([str(a) for a in argv], env=env, capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise CompanyError('Failed', '%s 失敗（%d）：%s%s' % (' '.join(map(str, argv)), r.returncode, r.stdout[-2000:],
                                                          r.stderr[-2000:]))
    return r


def relay_proc_name(cdir):
    return 'company-relay-%08x' % (zlib.crc32(str(Path(os.path.abspath(str(cdir)))).encode()) & 0xffffffff)


def up(cdir, out=print):
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = load(cdir)
    regular, _temp, _rows = headcount(cdir, cfg)
    if len(regular) > cfg['limits']['regular']:
        raise CompanyError('OverLimit', '正式員工 %d 人超過上限 %d；先改名冊或 company.json staff'
                           % (len(regular), cfg['limits']['regular']))
    names = all_member_names(cdir, cfg)
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise CompanyError('NameTaken', '部門之間有同名成員：%s' % '、'.join(dup))
    env = env_for(cdir, cfg)
    kenv = env_for(cdir, cfg, daemon=True)
    llm = cdir / cfg['llm']
    kcfg = {'pools': {'default': {'count': cfg['pools']['default']},
                      'llm': {'count': cfg['pools']['llm'], 'envs': {'AOS_LLM_CONFIG': str(llm)}}}}
    if os.environ.get('AOS_COST_HOME'):
        for p in kcfg['pools'].values():
            p.setdefault('envs', {})['AOS_COST_HOME'] = os.environ['AOS_COST_HOME']
    fmt.write_json(cdir / 'kernel.json', kcfg, indent=1)
    if not (cdir / 'K').exists():
        _run([CLI / 'aos-kernel', 'init', '--config', cdir / 'kernel.json'], kenv)
    else:
        for line in sync_kernel_pools(cdir, cfg):
            out(line)
    _run([CLI / 'aos', 'up'], kenv, timeout=120)
    write_hr_policy(cdir, cfg)
    out('kernel 開了：%s（default %d、llm %d 顆）' % (cdir / 'K', cfg['pools']['default'], cfg['pools']['llm']))
    for dept, tdir in sorted(team_dirs(cdir, cfg).items()):
        _run([CLI / 'aos-team', 'init', '--target', tdir], env)
        routes = cdir / 'config' / ('%s.routes.json' % dept)
        if routes.is_file():
            _run([CLI / 'aos-team', 'route', 'save', routes, '--target', tdir], env)
        roster = fmt.load_roster(tdir)
        for name in roster['members']:
            _persona(cdir, cfg, dept, tdir, name, env)
        _run([CLI / 'aos-team', 'start', '--target', tdir], env)
        out('%s 部開工：%s' % (dept, '、'.join(roster['members'])))
    out(register_relay(cdir, cfg, env))
    return 0


def sync_kernel_pools(cdir, cfg):
    """K 已經在：把 K/info.json 兩池的顆數對到 company.json 的 pools（aos-kernel cpu add／rm），
    再驗一次；對不上＝不開（astra 必修 13：市場層 slots 改了上限，下次 up 才真的生效）。回印出來的幾行。
    池的 envs（AOS_COST_HOME 等）cpu add／rm 不改：K 建好後改 envs 要手編 K/info.json。"""
    import aos_kernel_cpu
    from aos_kernel_info import load_info
    home = Path(cdir) / 'K'
    want = {'default': cfg['pools']['default'], 'llm': cfg['pools']['llm']}
    lines = []
    try:
        pools = (load_info(home).get('pools') or {})
        for name, n in want.items():
            cur = pools.get(name)
            if cur is None:
                env = ['AOS_LLM_CONFIG=%s' % (Path(cdir) / cfg['llm'])] if name == 'llm' else None
                lines.append(aos_kernel_cpu.cpu_add(home, name, n, env))
                continue
            have = int(cur.get('count') or 0)
            if n > have:
                lines.append(aos_kernel_cpu.cpu_add(home, name, n - have))
            elif n < have:
                lines.append(aos_kernel_cpu.cpu_rm(home, pool=name, count=have - n))
        got = {name: int(((load_info(home).get('pools') or {}).get(name) or {}).get('count') or 0) for name in want}
    except TeamError:
        raise
    except Exception as e:           # kernel 那邊的錯（NotLiteral、Busy…）：包成公司的錯，不開
        raise CompanyError('KernelSync', 'K/info.json 的池對不上 company.json：%s' % getattr(e, 'msg', e))
    if got != want:
        raise CompanyError('KernelSync', 'K/info.json 的池 %s 對不上 company.json 的 %s' % (got, want))
    return lines


def write_hr_policy(cdir, cfg):
    """這家的名額寫進這家的 HR 政策（K/hr/policy.json）：company.json 的 limits 是來源，HR 的擋點（init／start／spawn）
    與 status 用同一組數。policy 其他欄位（margin、expand）原樣留著。"""
    p = Path(cdir) / 'K' / 'hr' / 'policy.json'
    raw = fmt.read_json(p) if p.is_file() else {'_metainfo': {'_type': 'aos_hr_policy', '_version': 1}}
    raw.update({'stage': 'startup' if cfg['limits'] == STARTUP else 'grown', 'regular_max': cfg['limits']['regular'],
                'cpu_max': cfg['limits']['cpu'], 'llm_cpu_max': cfg['limits']['llm_cpu']})
    p.parent.mkdir(parents=True, exist_ok=True)
    fmt.write_json(p, raw, indent=2)
    return p


def _persona(cdir, cfg, dept, tdir, name, env):
    """公司層的人格（persona/<去掉前綴的名字>.md，再沒有就 persona/<部門>.md）接在模板人格後面；每個家只接一次。"""
    bare = name[len(cfg['prefix']):] if cfg['prefix'] and name.startswith(cfg['prefix']) else name
    src = None
    for cand in (cdir / 'persona' / ('%s.md' % bare), cdir / 'persona' / ('%s.md' % dept)):
        if cand.is_file():
            src = cand
            break
    if src is None:
        return
    mark = cdir / 'state' / 'persona' / name
    if mark.exists():
        return
    common = cdir / 'persona' / '_company.md'
    text = (common.read_text(encoding='utf-8') + '\n' if common.is_file() else '') + src.read_text(encoding='utf-8')
    text = text.replace('{prefix}', cfg['prefix']).replace('{dept}', dept)
    _run([CLI / 'aos-agent', 'persona', 'append', text, '--target', Path(tdir) / 'members' / name], env)
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text('ok\n', encoding='utf-8')


def register_relay(cdir, cfg, env):
    import aos_client
    kernel = env['AOS_KERNEL_HOME']
    folder = Path(cdir) / 'switchboard'
    folder.mkdir(parents=True, exist_ok=True)
    inst = folder / 'relay.inst.json'
    fmt.write_json(inst, {'_metainfo': {'_type': 'posix', '_version': 1},
                          'argv': [sys.executable, str(LIB / 'aos_company.py'), 'relay', '--quiet',
                                   '--company', str(cdir)],
                          'cwd': str(cdir), 'envs': {'AOS_KERNEL_HOME': kernel, 'PYTHONDONTWRITEBYTECODE': '1'},
                          'stderr': {'$opt': ['append', 'mkdir'], '$val': str(folder / 'relay.err')}}, indent=2)
    name = relay_proc_name(cdir)
    res = aos_client.call(kernel, 'add', {'target': str(inst), 'name': name,
                                          'interval_ms': cfg['relay']['interval_s'] * 1000},
                          client='company', timeout_ms=10000)
    if 'error' in res and (res['error'].get('data') or {}).get('code') != 'AlreadyExists':
        raise CompanyError('Failed', '總機登記失敗：%s' % res['error'].get('message'))
    return '總機開了：%s（每 %d 秒一輪）' % (name, cfg['relay']['interval_s'])


def down(cdir, out=print):
    import aos_client
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = load(cdir)
    env = env_for(cdir, cfg)
    if not (cdir / 'K').is_dir():
        out('kernel 沒開過')
        return 0
    res = aos_client.call(env['AOS_KERNEL_HOME'], 'rm', {'name': relay_proc_name(cdir)}, client='company', timeout_ms=10000)
    out('總機撤了：%s' % relay_proc_name(cdir) if 'error' not in (res or {}) else
        '總機沒撤到（%s；kernel 停了它也不會再跑）' % ((res.get('error') or {}).get('message') or res['error']))
    failed = []
    for dept, tdir in sorted(team_dirs(cdir, cfg).items()):
        if (Path(tdir) / 'members').is_dir():
            r = _run([CLI / 'aos-team', 'stop', '--target', tdir], env, check=False)
            if r.returncode != 0:
                failed.append('%s 部 aos-team stop 退 %d' % (dept, r.returncode))
            out('%s 部收工' % dept if r.returncode == 0 else '%s 部收工失敗（%d）' % (dept, r.returncode))
    r = _run([CLI / 'aos', 'down'], env_for(cdir, cfg, daemon=True), check=False, timeout=180)
    for line in (r.stdout or '').strip().splitlines():
        out(line)                                         # kernel 停了沒、daemon 停了沒（aos down 自己的摘要）
    if r.returncode != 0:
        failed.append('aos down 退 %d：%s' % (r.returncode, (r.stdout + r.stderr).strip()[-500:]))
    if failed:                      # 市場層靠這個退出碼決定能不能封存、放名額（astra 必修 4）
        out('沒停乾淨：' + '；'.join(failed))
        return 1
    out('kernel 關了')
    return 0


def order(cdir, text, to=None, out=print):
    cdir = Path(os.path.abspath(str(cdir)))
    cfg = load(cdir)
    if to is None:
        tdir = team_dirs(cdir, cfg)[cfg['front']]
        r = _run([CLI / 'aos-team', 'ask', text, '--target', tdir], env_for(cdir, cfg), check=False)
        out((r.stdout + r.stderr).strip())
        return r.returncode
    o = Switchboard(cdir, cfg).board_order(to, text)
    out('董事直接下單給 %s：總機 %s（%s，交給 %s）' % (to, o['id'], o['via'], o['to']['member']))
    return 0


def mail(cdir, out=print, last=20):
    sb = Switchboard(cdir)
    letters = sorted(sb.board_letters(), key=lambda x: x[1].get('at', ''))
    for dept, l in letters[-last:]:
        out('%s  %-4s %s → 董事  %s  %s  %s' % (fmt.short_time(l.get('at', '')) if l.get('at') else '-', dept,
                                              l.get('from'), l.get('status'), l.get('reply_to') or '-',
                                              l.get('text', '')[:120].replace('\n', ' ')))
    if not letters:
        out('董事收件匣是空的')
    return 0


# ------------------------------------------------------------------ 指令 ----

def main(argv=None, default_src=EXAMPLE):
    ap = argparse.ArgumentParser(prog='company.py', description='公司：幾支 aos 團隊＋機械總機（spec/team/company.md）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('new', help='照樣板生一家公司')
    p.add_argument('dir')
    p.add_argument('--prefix', default='')
    p.add_argument('--project')
    p.add_argument('--llm-cpu', type=int)
    p.add_argument('--cpu', type=int)
    p.add_argument('--name')
    p.add_argument('--from', dest='src', default=str(default_src))
    for name in ('up', 'down', 'status', 'relay', 'mail'):
        p = sub.add_parser(name)
        p.add_argument('--company', '-C', default=os.environ.get('AOS_COMPANY_HOME', '.'))
        if name == 'status':
            p.add_argument('--json', action='store_true')
            p.add_argument('--no-kernel', action='store_true')
        if name == 'relay':
            p.add_argument('--quiet', action='store_true')
    p = sub.add_parser('order', help='董事下單：預設交給前台部門的門房；--to 直接交給某部門')
    p.add_argument('text', nargs='+')
    p.add_argument('--to')
    p.add_argument('--company', '-C', default=os.environ.get('AOS_COMPANY_HOME', '.'))
    p = sub.add_parser('hr', help='跑 aos-team hr（cap、ls…），自動帶這家的 AOS_KERNEL_HOME／AOS_HR_HOME')
    p.add_argument('args', nargs=argparse.REMAINDER)
    p.add_argument('--company', '-C', default=os.environ.get('AOS_COMPANY_HOME', '.'))
    p = sub.add_parser('answer', help='回某部門的題')
    p.add_argument('dept')
    p.add_argument('q')
    p.add_argument('text', nargs='+')
    p.add_argument('--company', '-C', default=os.environ.get('AOS_COMPANY_HOME', '.'))
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'new':
            d = new(a.dir, a.src, a.prefix, a.project, a.llm_cpu, a.cpu, a.name)
            cfg = load(d)
            print('生好了 %s：%s；%s' % (d, '、'.join(all_member_names(d, cfg)), caps_line(
                {'regular': len(headcount(d, cfg)[0]), 'cpu': cfg['pools']['default'],   # cpu 不含 llm（同 status、HR）
                 'llm_cpu': cfg['pools']['llm']}, cfg['limits'])))
            return 0
        if a.cmd == 'up':
            return up(a.company)
        if a.cmd == 'down':
            return down(a.company)
        if a.cmd == 'status':
            s = status_data(a.company, use_kernel=not a.no_kernel)
            if a.json:
                print(json.dumps(s, ensure_ascii=False, indent=1))
            else:
                print_status(s)
            return 1 if s['over'] else 0
        if a.cmd == 'relay':
            log = Switchboard(a.company).round()
            if not a.quiet or log:
                for line in log:
                    print(line)
            return 0
        if a.cmd == 'mail':
            return mail(a.company)
        if a.cmd == 'order':
            return order(a.company, ' '.join(a.text), a.to)
        if a.cmd == 'hr':
            args, comp = list(a.args or []), a.company
            for flag in ('-C', '--company'):                 # 寫在子命令後面的 -C 也認（REMAINDER 會吞掉）
                while flag in args[:-1]:
                    i = args.index(flag)
                    comp = args[i + 1]
                    del args[i:i + 2]
            comp = os.path.abspath(comp)
            cfg = load(comp)
            r = _run([CLI / 'aos-team', 'hr'] + (args or ['cap']), env_for(comp, cfg), check=False)
            print((r.stdout + r.stderr).strip())
            return r.returncode
        if a.cmd == 'answer':
            cfg = load(a.company)
            tdir = team_dirs(a.company, cfg).get(host_dept(cfg, a.dept) or '')
            if tdir is None:
                raise CompanyError('NotOpen', '%s 部門沒有團隊' % a.dept)
            r = _run([CLI / 'aos-team', 'answer', a.q, ' '.join(a.text), '--target', tdir], env_for(a.company, cfg),
                     check=False)
            print((r.stdout + r.stderr).strip())
            return r.returncode
    except TeamError as e:
        print('company.py: %s: %s' % (e.code, e.msg), file=sys.stderr)
        return 1
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
