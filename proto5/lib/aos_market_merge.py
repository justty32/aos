"""市場的合併：剩兩家時的合併計畫（經理只留一個、名額滿了改臨時工、notes 帶過去）與照計畫逐步做。"""
from pathlib import Path
import shutil
import time
import uuid

import aos_company as co
import aos_team_cost as cost
import aos_team_format as fmt

from aos_market_book import (
    _event, cost_base, DEPT_ORDER, load, market_lock, MarketError, now, operating, save
)
from aos_market_close import _stop


# ------------------------------------------------------------------ 合併 ----

def _bare(cfg, name):
    p = cfg['prefix']
    return name[len(p):] if p and name.startswith(p) else name


def _unique(cand, taken):
    """改名撞到既有或這次已經排好的名字＝後面加 -2、-3…（截短到 32 字內），astra 必修 14。"""
    if fmt.NAME.match(cand) and cand not in taken:
        return cand
    for i in range(2, 1000):
        suffix = '-%d' % i
        c = cand[:32 - len(suffix)] + suffix
        if fmt.NAME.match(c) and c not in taken:
            return c
    raise MarketError('NameTaken', '%s 找不到不撞的名字' % cand)


def plan_merge(a_dir, b_dir, b_name, order=None):
    """B 併進 A 的計畫（不動任何檔）：

    1. 同部門的經理（template lead）只留 A 的，B 的經理**裁掉**（家跟著 B 封存；筆記抄一份進 A 的 team/notes/_merged/）。
    2. 其餘 B 的成員照部門優先序併進 A 同一個部門的團隊，改名 `<A 前綴><原職位>-<B 名>`（例 c1-mfg-writer1-c2）；
       撞到 A 既有的名字（或這次排好的）就再加 -2、-3。
       A 的正式員工還有名額＝**正式**，滿了＝**臨時工**（名冊寫 employment: temp，不算人頭）。
    3. A 沒有那個部門的團隊（或那部門沒開）＝那些人**裁掉**。
    4. 新成員的 mail_to：A 那個部門的經理（有的話）＋human；A 那個部門的經理 mail_to 加上新成員。
    """
    order = order or DEPT_ORDER
    a_cfg, b_cfg = co.load(a_dir), co.load(b_dir)
    a_teams, b_teams = co.team_dirs(a_dir, a_cfg), co.team_dirs(b_dir, b_cfg)
    regular, _t, _r = co.headcount(a_dir, a_cfg)
    room = a_cfg['limits']['regular'] - len(regular)
    b_regular, _bt, b_rows = co.headcount(b_dir, b_cfg)
    taken = set(co.all_member_names(a_dir, a_cfg)) | {fmt.HUMAN, fmt.BEAT, fmt.POST}
    depts = sorted(b_teams, key=lambda d: (order.index(d) if d in order else len(order), d))
    moves = []
    for dept in depts:
        b_roster = fmt.load_roster(b_teams[dept])
        a_roster = fmt.load_roster(a_teams[dept]) if dept in a_teams else None
        a_leads = fmt.members_by_template(a_roster, 'lead') if a_roster else []
        for name, mem in b_roster['members'].items():
            row = {'dept': dept, 'from': name, 'template': mem['template'], 'model': mem['model']}
            if a_roster is None:
                row.update(action='layoff', why='%s 部在 %s 沒有團隊' % (dept, a_cfg['name']))
            elif mem['template'] == 'lead' and a_leads:
                row.update(action='layoff', why='%s 部已經有經理 %s' % (dept, a_leads[0]))
            else:
                new = '%s%s-%s' % (a_cfg['prefix'], _bare(b_cfg, name), b_name)
                if not fmt.NAME.match(new):
                    new = ('%s%s' % (a_cfg['prefix'], _bare(b_cfg, name)))[:28] + '-' + b_name[:3]
                new = _unique(new, taken)
                taken.add(new)
                was_regular = name in b_regular
                if was_regular and room > 0:
                    emp, room = 'regular', room - 1
                else:
                    emp = 'temp'
                row.update(action='join', to=new, employment=emp, lead=a_leads[0] if a_leads else None,
                           why='正式名額還有' if emp == 'regular' else ('正式名額滿了，改臨時工' if was_regular else '本來就是臨時工'))
            moves.append(row)
    return {'into': a_cfg['name'], 'from': b_name, 'moves': moves, 'room_left': room}


def apply_merge(mdir, a, b, plan=None, env=None, start=True):
    """B 併進 A。整段拿市場鎖；先在鎖裡**重算**計畫（人頭、名字是最新的；跟傳進來的不一樣＝Stale，重新 --dry-run），
    存成 market.json 的 pending（B 標 merging）再動手；每一步都能重做，崩了重跑 `merge` 接著做（astra 必修 1～3、14）。
    順序：停 B（失敗＝停在 merging）→ 搬人（拿名冊鎖）→ A 動到的部門開工 → 停好後才讀 B 的餘額、一筆轉帳給 A → 封存 B → 結案。"""
    with market_lock(mdir):
        base = cost_base(env)
        m = load(mdir)
        pend = m.get('pending')
        if pend and pend.get('kind') == 'merge':
            if (pend['into'], pend['from']) != (a, b):
                raise MarketError('Pending', '上次 %s 併進 %s 還沒做完；先跑完那個' % (pend['from'], pend['into']))
        else:
            if pend:
                raise MarketError('Pending', '還有沒做完的 %s（再跑一次那個指令接著做）' % pend.get('kind'))
            for n in (a, b):
                if n not in operating(m):
                    raise MarketError('NotFound', '%s 不在營業' % n)
            fresh = plan_merge(m['companies'][a]['dir'], m['companies'][b]['dir'], b, m['params']['dept_order'])
            if plan is not None and plan['moves'] != fresh['moves']:
                raise MarketError('Stale', '合併計畫跟現在的名冊對不上（有人改了名冊或名額）；重新 merge --dry-run 看過再合')
            a_names = set(co.all_member_names(m['companies'][a]['dir']))
            hit = [mv['to'] for mv in fresh['moves'] if mv['action'] == 'join' and mv['to'] in a_names]
            if hit:
                raise MarketError('NameTaken', '改名撞到 %s 既有成員：%s' % (a, '、'.join(hit)))
            pend = {'kind': 'merge', 'into': a, 'from': b, 'plan': fresh,
                    'op': 'merge-%s-%s-%s' % (b, a, uuid.uuid4().hex[:8]),
                    'archive': str(Path(mdir) / 'archive' / ('%s-merged-%s' % (b, time.strftime('%Y%m%d-%H%M%S')))),
                    'moved': None}
            m['pending'] = pend
            m['companies'][b]['status'] = 'merging'
            save(mdir, m)
        return _merge_steps(mdir, m, base, pend, start)


def _merge_steps(mdir, m, base, pend, start):
    a, b, plan = pend['into'], pend['from'], pend['plan']
    a_dir, b_dir = Path(m['companies'][a]['dir']), Path(m['companies'][b]['dir'])
    dest = Path(pend['archive'])
    src_root = b_dir if b_dir.is_dir() else dest            # 崩在搬家之後：從封存讀
    if b_dir.is_dir():
        _stop(b_dir, start)
    a_cfg = co.load(a_dir)
    a_teams, b_teams = co.team_dirs(a_dir, a_cfg), co.team_dirs(src_root, co.load(src_root))
    touched = set()
    for mv in plan['moves']:
        src_notes = fmt.Layout(b_teams[mv['dept']]).notes(mv['from']) / 'notes.json'
        if mv['action'] == 'layoff':
            if mv['dept'] in a_teams and src_notes.is_file():
                keep = fmt.Layout(a_teams[mv['dept']]).notes('_merged') / mv['from']
                keep.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_notes, keep / 'notes.json')
            continue
        tdir = a_teams[mv['dept']]
        with fmt.roster_lock(fmt.Layout(tdir)):
            roster = fmt.read_json(tdir / 'team.json')
            if mv['to'] not in roster['members']:          # 已經在＝上次做到一半（計畫時已驗過不撞名）
                b_mem = fmt.read_json(b_teams[mv['dept']] / 'team.json')['members'][mv['from']]
                mem = {'template': b_mem['template'], 'mail_to': [x for x in [mv['lead'], 'human'] if x],
                       'employment': mv['employment']}
                for k in ('model', 'mounts', 'tools'):
                    if k in b_mem:
                        mem[k] = b_mem[k]
                roster['members'][mv['to']] = mem
            if mv['lead'] and mv['to'] not in roster['members'][mv['lead']].setdefault('mail_to', []):
                roster['members'][mv['lead']]['mail_to'].append(mv['to'])
            lim = roster.setdefault('limits', {})
            lim['max_members'] = max(lim.get('max_members', fmt.LIMIT_DEFAULTS['max_members']), len(roster['members']))
            fmt.validate_roster(roster, str(tdir / 'team.json'))
            fmt.write_json(tdir / 'team.json', roster, indent=2)
        if src_notes.is_file():
            dst = fmt.Layout(tdir).notes(mv['to'])
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_notes, dst / 'notes.json')            # 跨任務記憶帶過去（對話紀錄留在 B 的封存）
        touched.add(mv['dept'])
    a_cfg_raw = fmt.read_json(a_dir / 'company.json')
    for mv in plan['moves']:
        if mv['action'] == 'join':
            a_cfg_raw.setdefault('staff', {})[mv['to']] = {'dept': mv['dept'], 'roles': ['併自 %s 的 %s' % (b, mv['from'])]}
    co.validate(a_cfg_raw, str(a_dir / 'company.json'))
    fmt.write_json(a_dir / 'company.json', a_cfg_raw, indent=2)
    if start and (a_dir / 'K').is_dir():
        e = co.env_for(a_dir, a_cfg)
        for dept in sorted(touched):
            co._run([co.CLI / 'aos-team', 'init', '--target', a_teams[dept]], e)
            co._run([co.CLI / 'aos-team', 'start', '--target', a_teams[dept]], e, check=False)
    # 帳：B 停好後才讀餘額（還在跑的單記的帳都進來了），一筆轉帳給 A（操作 ID 去重，不會只做一半）
    if pend.get('moved') is None:
        left = (cost.balances(base).get(b) or {}).get('balance') or {}
        pend['moved'] = {'usd': left.get('usd') if (left.get('usd') or 0) > 0 else None,
                         'tokens': left.get('tokens') if (left.get('tokens') or 0) > 0 else None}
        save(mdir, m)
    usd, tok = pend['moved']['usd'], pend['moved']['tokens']
    if usd is not None or tok is not None:
        cost.account_transfer(base, b, a, usd=usd, tokens=tok, note='%s 併入 %s 的餘額' % (b, a), op=pend['op'])
    if b_dir.is_dir() and not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(b_dir), str(dest))
    m['companies'][b].update(status='merged', closed_at=now(), archive=str(dest), merged_into=a)
    m['companies'][a]['note'] = (m['companies'][a].get('note') or '') + '併了 %s；' % b
    _event(m, kind='merge', company=b, into=a, moved_balance={'usd': usd, 'tokens': tok})
    m.pop('pending', None)
    save(mdir, m)
    return {'moved': [x for x in plan['moves'] if x['action'] == 'join'],
            'laid_off': [x for x in plan['moves'] if x['action'] == 'layoff'], 'balance_moved': {'usd': usd, 'tokens': tok}}
