#!/usr/bin/env python3
"""市場層（spec/team/market.md）：幾家一樣的小公司做同樣的單，經理人照表現撥額度；花光倒閉、剩兩家合併。

董事長＝human，經理人＝調度者（不在 aos 裡）；這支是經理人手上的**機械**指令，發多少照 market.json 的參數算，經理人可以覆寫。
帳戶用財務部的 `aos_team_cost`（`$AOS_COST_HOME/accounts.json`，cost.md §6）：配額＝撥款加總、已花＝帳本裡落在公司資料夾底下的呼叫。

子命令（`python3 aos_market.py <子命令> [--market 資料夾]`；沒給看 AOS_MARKET_HOME）：
  open 名 公司資料夾 [--usd X] [--tokens N]    開戶＋撥開辦費、登記進 market.json
  score 名 [--quality Q] [--eval 結果.json] [--seconds S] [--hops H]   記這一輪的表現（沒給的從公司的總機單算）
  rank [--json]                                 算排名（不寫帳）
  grant [--dry-run] [--usd 名=X]… [--tokens 名=N]…   照排名撥這一輪的額度；--usd／--tokens 覆寫單一家
  bankrupt [--dry-run]                          餘額 ≤ 0 的：停公司、封存資料夾；剩的配額與名額回總池
  close 名 [--dry-run]                          經理人裁撤：沒花完的配額全部收回總池
  pool [--json]                                 總池：錢＝總量 − 已花 − 各家手上沒花的；名額＝機器 − 各家 limits
  slots 名 [--regular N] [--cpu N] [--llm-cpu N]    從總池撥名額
  merge [A B] [--into A] [--dry-run] [--force]  剩兩家時合併（§5 of market.md）
  ls [--json]                                   每家：狀態、配額、已花、餘額、最近分數
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

import aos_company as co                                                   # noqa: E402
import aos_team_cost as cost                                               # noqa: E402
import aos_team_format as fmt                                              # noqa: E402
from aos_team_format import TeamError                                      # noqa: E402

TYPE = 'aos_market'
DEFAULT_PARAMS = {
    'weights': {'quality': 0.6, 'speed': 0.25, 'cost': 0.15},   # 排名分＝加權和（三項各 0～100）
    'round_pool': {'usd': 2.0, 'tokens': 4000000},              # 每輪撥出去的總額
    'shares': [0.35, 0.25, 0.2, 0.12, 0.08],                     # 第 1 名、第 2 名…拿總額的幾成（家數少就取前幾個再按比例放大）
    'seed': {'usd': 1.0, 'tokens': 2000000},                      # 開辦費
    'min_quality': 0,                                            # 品質分低於這個＝這輪不撥（0＝不設門檻）
    'merge_at': 2,                                               # 營業中的剩幾家就合併
    'dept_order': ['mfg', 'qa', 'rd', 'lib', 'hq'],               # 合併時先收哪個部門的人
    'total': {},                                                 # 董事給的總量 {"usd", "tokens"}；空＝不設總池（撥款不檢查）
    'machine': {'regular': 100, 'cpu': 200, 'llm_cpu': 20},      # 整台機器的名額：各家 limits 加總不能超過
}
DEPT_ORDER = DEFAULT_PARAMS['dept_order']


class MarketError(TeamError):
    pass


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def market_dir(arg=None):
    d = arg or os.environ.get('AOS_MARKET_HOME')
    if not d:
        raise MarketError('Usage', '要 --market 資料夾（或設 AOS_MARKET_HOME）')
    return Path(os.path.abspath(os.path.expanduser(d)))


def cost_base(env=None):
    base = cost.home(env)
    if not base:
        raise MarketError('NoLedger', '要設 AOS_COST_HOME（財務部的帳本資料夾，cost.md §1）')
    return base


def load(mdir):
    p = Path(mdir) / 'market.json'
    if not p.is_file():
        return {'_metainfo': {'_type': TYPE, '_version': 1}, 'params': json.loads(json.dumps(DEFAULT_PARAMS)),
                'companies': {}, 'scores': {}, 'history': [], 'events': []}
    obj = fmt.read_json(p)
    params = json.loads(json.dumps(DEFAULT_PARAMS))
    params.update(obj.get('params') or {})
    obj['params'] = params
    obj.setdefault('companies', {})
    obj.setdefault('scores', {})
    obj.setdefault('history', [])
    obj.setdefault('events', [])
    return obj


def save(mdir, obj):
    Path(mdir).mkdir(parents=True, exist_ok=True)
    fmt.write_json(Path(mdir) / 'market.json', obj, indent=1)


def operating(m):
    return [n for n, c in m['companies'].items() if c['status'] == 'operating']


# ------------------------------------------------------------------ 總池 ----

def pool_status(m, bal):
    """總池（董事 09-25）：錢＝總量 − 各家已花（含收掉的）− 營業中各家手上沒花的配額；
    名額＝機器上限 − 營業中各家 limits 加總。收掉的公司手上沒花的配額在收掉時已收回（撥負的），名額自然回來。"""
    money = {}
    for k, total in (m['params'].get('total') or {}).items():
        if total is None:
            continue
        spent = sum(((b.get('spent') or {}).get(k) or 0) for n, b in bal.items() if n in m['companies'])
        held = sum(max(0, ((bal.get(n) or {}).get('balance') or {}).get(k) or 0) for n in operating(m))
        money[k] = round(total - spent - held, 6)
    used = {k: 0 for k in m['params']['machine']}
    for n in operating(m):
        try:
            lim = co.load(m['companies'][n]['dir'])['limits']
        except TeamError:
            continue
        for k in used:
            used[k] += lim.get(k, 0)
    slots = {k: m['params']['machine'][k] - used[k] for k in used}
    return {'money': money, 'slots': slots, 'slots_used': used}


def _event(m, **kw):
    kw.setdefault('at', now())
    m['events'].append(kw)
    return kw


# ------------------------------------------------------------------ 開戶 ----

def open_company(mdir, name, cdir, usd=None, tokens=None, env=None):
    base = cost_base(env)
    m = load(mdir)
    cdir = Path(os.path.abspath(os.path.expanduser(str(cdir))))
    co.load(cdir)                                    # 要是一家公司（company.json 驗得過）
    if name in m['companies'] and m['companies'][name]['status'] == 'operating':
        raise MarketError('AlreadyExists', '%s 已經在營業' % name)
    cost.account_open(base, name, str(cdir))
    seed = m['params']['seed']
    usd = seed.get('usd') if usd is None else usd
    tokens = seed.get('tokens') if tokens is None else tokens
    pool = pool_status(m, cost.balances(base))
    for k, v in (('usd', usd), ('tokens', tokens)):
        if k in pool['money'] and (v or 0) > pool['money'][k]:
            raise MarketError('PoolEmpty', '總池的 %s 只剩 %s，開辦費要 %s' % (k, pool['money'][k], v))
    lim = co.load(cdir)['limits']
    short = [k for k in pool['slots'] if lim.get(k, 0) > pool['slots'][k]]
    if short:
        raise MarketError('NoSlots', '機器名額不夠：%s（剩 %s，這家要 %s）' % (
            '、'.join(short), json.dumps(pool['slots']), json.dumps(lim)))
    cost.account_grant(base, name, usd=usd, tokens=tokens, note='開辦費')
    m['companies'][name] = {'dir': str(cdir), 'status': 'operating', 'opened_at': now(), 'closed_at': None,
                            'note': ''}
    _event(m, kind='open', company=name, grant={'usd': usd, 'tokens': tokens}, slots=lim)
    save(mdir, m)
    return m['companies'][name]


# ------------------------------------------------------------------ 表現 ----

def quality_from_eval(result):
    """arknights eval 的結果檔 → 0～100：每人 機械 40％＋證據列 40％＋評審 20％（沒評審就前兩項放大成 100）。"""
    people = result.get('people') or []
    if not people:
        return None
    total = 0.0
    for p in people:
        mech = p.get('mech') or {}
        ev = p.get('evidence') or {}
        m = (mech.get('passed', 0) / mech['total']) if mech.get('total') else 0.0
        e = (ev.get('ok', 0) / ev['checked_rows']) if ev.get('checked_rows') else 0.0
        j = None
        judge = p.get('judge') or {}
        scores = judge.get('scores') if isinstance(judge, dict) else None
        if isinstance(scores, dict) and scores:
            vals = [v for v in scores.values() if isinstance(v, (int, float))]
            j = sum(vals) / len(vals) / 5.0 if vals else None
        total += (40 * m + 40 * e + 20 * j) if j is not None else (50 * m + 50 * e)
    return round(total / len(people), 2)


def speed_from_company(cdir, since=None):
    """公司總機單：這一輪結的（done）張數、平均秒數（下單 → 最後一封回覆）、平均跳數（回覆信數＋1）。"""
    cdir = Path(cdir)
    folder = cdir / 'switchboard' / 'orders'
    secs, hops = [], []
    for p in fmt.json_files(folder) if folder.is_dir() else []:
        o = fmt.read_json(p)
        if o.get('status') != 'done' or not o.get('replies'):
            continue
        if since and (o.get('at') or '') < since:
            continue
        t0 = fmt.parse_iso(o['at'])
        t1 = fmt.parse_iso(o['replies'][-1].get('at') or '')
        if t0 is None or t1 is None:
            continue
        secs.append(max(0.0, (t1 - t0).total_seconds()))
        hops.append(len(o['replies']) + 1)
    if not secs:
        return None
    return {'done': len(secs), 'seconds': round(sum(secs) / len(secs), 1), 'hops': round(sum(hops) / len(hops), 2)}


def record_score(mdir, name, quality=None, eval_path=None, seconds=None, hops=None, done=None):
    m = load(mdir)
    if name not in m['companies']:
        raise MarketError('NotFound', '市場裡沒有 %s' % name)
    src = 'manual'
    if eval_path is not None:
        quality = quality_from_eval(fmt.read_json(eval_path))
        src = 'eval:%s' % eval_path
    since = m['history'][-1]['at'] if m['history'] else None
    sp = speed_from_company(m['companies'][name]['dir'], since) if seconds is None else None
    s = {'quality': quality, 'seconds': seconds if seconds is not None else (sp or {}).get('seconds'),
         'hops': hops if hops is not None else (sp or {}).get('hops'),
         'done': done if done is not None else (sp or {}).get('done', 1 if seconds is not None else 0),
         'at': now(), 'source': src}
    m['scores'][name] = s
    save(mdir, m)
    return s


# ------------------------------------------------------------------ 排名 ----

def rank(m, bal):
    """回一列一家（照排名分高到低）：quality、speed、cost 三項各 0～100，再加權。

    - 品質：記下的分數（沒記＝0）。
    - 快：這一輪有結單的，最快那家的平均秒數 ÷ 自己的 ×100；沒結單＝0。
    - 省：這一輪花的 token（這輪已花 − 上輪記下的已花），最省那家 ÷ 自己 ×100；沒花也沒結單＝0。
    """
    w = m['params']['weights']
    last_spent = (m['history'][-1].get('spent') if m['history'] else None) or {}
    rows = []
    for name in operating(m):
        s = m['scores'].get(name) or {}
        b = bal.get(name) or {}
        spent_now = (b.get('spent') or {}).get('tokens') or 0
        spent = max(0, spent_now - (last_spent.get(name) or 0))
        rows.append({'name': name, 'quality': float(s.get('quality') or 0), 'seconds': s.get('seconds'),
                     'hops': s.get('hops'), 'done': s.get('done') or 0, 'spent_tokens': spent,
                     'spent_total': spent_now, 'balance': b.get('balance'), 'broke': b.get('broke', False)})
    fast = [r['seconds'] for r in rows if r['seconds'] and r['done']]
    cheap = [r['spent_tokens'] for r in rows if r['spent_tokens'] and r['done']]
    for r in rows:
        r['speed'] = round(100 * min(fast) / r['seconds'], 2) if fast and r['seconds'] and r['done'] else 0.0
        r['cost'] = round(100 * min(cheap) / r['spent_tokens'], 2) if cheap and r['spent_tokens'] and r['done'] else 0.0
        r['score'] = round(w['quality'] * r['quality'] + w['speed'] * r['speed'] + w['cost'] * r['cost'], 2)
    rows.sort(key=lambda r: (-r['score'], -r['quality'], r['name']))
    for i, r in enumerate(rows, 1):
        r['rank'] = i
    return rows


def plan_grants(m, rows, usd_over=None, tok_over=None):
    """照排名分這一輪的總額：shares 取前 n 個按比例放大到 1；品質低於 min_quality 的拿 0；覆寫的照覆寫。"""
    usd_over, tok_over = usd_over or {}, tok_over or {}
    pool = m['params']['round_pool']
    shares = list(m['params']['shares'])[:len(rows)]
    shares += [0.0] * (len(rows) - len(shares))
    eligible = [r['quality'] >= m['params']['min_quality'] for r in rows]
    tot = sum(s for s, ok in zip(shares, eligible) if ok) or 1.0
    out = {}
    for r, s, ok in zip(rows, shares, eligible):
        frac = s / tot if ok else 0.0
        g = {'usd': round(pool.get('usd', 0) * frac, 4) if pool.get('usd') is not None else None,
             'tokens': int(pool.get('tokens', 0) * frac) if pool.get('tokens') is not None else None,
             'share': round(frac, 4), 'override': False}
        if r['name'] in usd_over:
            g['usd'], g['override'] = usd_over[r['name']], True
        if r['name'] in tok_over:
            g['tokens'], g['override'] = tok_over[r['name']], True
        out[r['name']] = g
    return out


def do_grant(mdir, usd_over=None, tok_over=None, dry_run=False, env=None):
    base = cost_base(env)
    m = load(mdir)
    bal = cost.balances(base)
    rows = rank(m, bal)
    grants = plan_grants(m, rows, usd_over, tok_over)
    pool = pool_status(m, bal)
    capped = {}
    for k, left in pool['money'].items():
        want = sum((g[k] or 0) for g in grants.values() if (g[k] or 0) > 0)
        if want > left:                                  # 總池不夠：照比例縮到剛好發完
            f = max(0.0, left) / want if want else 0.0
            for g in grants.values():
                if (g[k] or 0) > 0:
                    g[k] = round(g[k] * f, 4) if k == 'usd' else int(g[k] * f)
            capped[k] = {'want': want, 'pool': left}
    rnd = len(m['history']) + 1
    if not dry_run:
        for name, g in grants.items():
            if (g['usd'] or 0) == 0 and (g['tokens'] or 0) == 0:
                continue
            cost.account_grant(base, name, usd=g['usd'], tokens=g['tokens'],
                               note='第 %d 輪 第 %d 名%s' % (rnd, next(r['rank'] for r in rows if r['name'] == name),
                                                          '（經理人覆寫）' if g['override'] else ''))
        m['history'].append({'round': rnd, 'at': now(), 'ranking': rows, 'grants': grants, 'capped': capped,
                             'spent': {r['name']: r['spent_total'] for r in rows}})
        _event(m, kind='grant', round=rnd, grants={n: {'usd': g['usd'], 'tokens': g['tokens']} for n, g in grants.items()},
               capped=capped)
        save(mdir, m)
    return rnd, rows, grants


def grant_slots(mdir, name, regular=0, cpu=0, llm_cpu=0, env=None):
    """從總池撥名額給一家：llm cpu 也是 cpu（撥 1 顆 llm cpu＝limits.cpu、limits.llm_cpu、pools.llm 各 +1）；
    cpu＝limits.cpu、pools.default +1；人頭＝limits.regular +1。不能超過那家的 limits_max 與總池。
    kernel 開著的話池要 aos-kernel cpu add 才真的多開（這裡只改 company.json；下次 up 生效）。"""
    m = load(mdir)
    if name not in operating(m):
        raise MarketError('NotFound', '%s 不在營業' % name)
    want = {'regular': regular, 'cpu': cpu + llm_cpu, 'llm_cpu': llm_cpu}
    pool = pool_status(m, cost.balances(cost_base(env)))
    short = [k for k, v in want.items() if v > pool['slots'][k]]
    if short:
        raise MarketError('NoSlots', '總池名額不夠：%s（剩 %s）' % ('、'.join(short), json.dumps(pool['slots'])))
    cdir = Path(m['companies'][name]['dir'])
    raw = fmt.read_json(cdir / 'company.json')
    cfg = co.load(cdir)
    lim = dict(cfg['limits'])
    for k, v in want.items():
        lim[k] += v
    pools = dict(cfg['pools'])
    pools['llm'] += llm_cpu
    pools['default'] += cpu
    raw['limits'], raw['pools'] = lim, pools
    co.validate(raw, str(cdir / 'company.json'))          # 超過 limits_max＝擋
    fmt.write_json(cdir / 'company.json', raw, indent=2)
    _event(m, kind='slots', company=name, slots=want)
    save(mdir, m)
    return lim


# ------------------------------------------------------------------ 倒閉 ----

def _shutdown(mdir, m, base, bal, name, reason, dry_run=False, stop=True):
    """收掉一家：手上沒花完的配額（任一種 > 0 的）撥負的收回總池、名額（它的 limits）回總池、停、封存。"""
    c = m['companies'][name]
    cdir = Path(c['dir'])
    b = bal.get(name) or {}
    left = b.get('balance') or {}
    recycled = {k: v for k, v in left.items() if v is not None and v > 0}
    try:
        cfg = co.load(cdir)
        freed = co.all_member_names(cdir, cfg)
        slots = dict(cfg['limits'])
    except TeamError:
        cfg, freed, slots = None, [], {}
    dest = Path(mdir) / 'archive' / ('%s-%s-%s' % (name, reason, time.strftime('%Y%m%d-%H%M%S')))
    row = {'name': name, 'reason': reason, 'balance': left, 'recycled': recycled, 'slots': slots, 'freed': freed,
           'archive': str(dest)}
    if dry_run:
        return row
    if recycled:
        cost.account_grant(base, name, usd=-recycled['usd'] if 'usd' in recycled else None,
                           tokens=-recycled['tokens'] if 'tokens' in recycled else None,
                           note='%s：沒花完的配額收回總池' % ('倒閉' if reason == 'bankrupt' else '裁撤'))
    if stop and cfg is not None and (cdir / 'K').is_dir():
        co.down(cdir, out=lambda *_: None)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if cdir.is_dir():
        shutil.move(str(cdir), str(dest))
    c.update(status='bankrupt' if reason == 'bankrupt' else 'closed', closed_at=now(), archive=str(dest), freed=freed)
    _event(m, kind=reason, company=name, recycled=recycled, slots=slots)
    return row


def bankrupt(mdir, dry_run=False, env=None, stop=True):
    """餘額 ≤ 0（有撥過的那一種）的營業中公司倒閉：另一種還有剩的收回總池；名額回總池；停、封存（前綴可以再用）。"""
    base = cost_base(env)
    m = load(mdir)
    bal = cost.balances(base)
    out = [_shutdown(mdir, m, base, bal, n, 'bankrupt', dry_run, stop) for n in operating(m)
           if (bal.get(n) or {}).get('broke')]
    if not dry_run and out:
        save(mdir, m)
    return out


def close(mdir, name, dry_run=False, env=None, stop=True):
    """經理人裁撤一家（還沒花光）：沒花完的配額全部收回總池，其餘同倒閉。"""
    base = cost_base(env)
    m = load(mdir)
    if name not in operating(m):
        raise MarketError('NotFound', '%s 不在營業' % name)
    row = _shutdown(mdir, m, base, cost.balances(base), name, 'closed', dry_run, stop)
    if not dry_run:
        save(mdir, m)
    return row


# ------------------------------------------------------------------ 合併 ----

def _bare(cfg, name):
    p = cfg['prefix']
    return name[len(p):] if p and name.startswith(p) else name


def plan_merge(a_dir, b_dir, b_name, order=None):
    """B 併進 A 的計畫（不動任何檔）：

    1. 同部門的經理（template lead）只留 A 的，B 的經理**裁掉**（家跟著 B 封存；筆記抄一份進 A 的 team/notes/_merged/）。
    2. 其餘 B 的成員照部門優先序併進 A 同一個部門的團隊，改名 `<A 前綴><原職位>-<B 名>`（例 c1-mfg-writer1-c2）；
       A 的正式員工還有名額＝**正式**，滿了＝**臨時工**（company.json staff 寫 temp，不算人頭）。
    3. A 沒有那個部門的團隊（或那部門沒開）＝那些人**裁掉**。
    4. 新成員的 mail_to：A 那個部門的經理（有的話）＋human；A 那個部門的經理 mail_to 加上新成員。
    """
    order = order or DEPT_ORDER
    a_cfg, b_cfg = co.load(a_dir), co.load(b_dir)
    a_teams, b_teams = co.team_dirs(a_dir, a_cfg), co.team_dirs(b_dir, b_cfg)
    regular, _t, _r = co.headcount(a_dir, a_cfg)
    room = a_cfg['limits']['regular'] - len(regular)
    b_regular, _bt, b_rows = co.headcount(b_dir, b_cfg)
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
                was_regular = name in b_regular
                if was_regular and room > 0:
                    emp, room = 'regular', room - 1
                else:
                    emp = 'temp'
                row.update(action='join', to=new, employment=emp, lead=a_leads[0] if a_leads else None,
                           why='正式名額還有' if emp == 'regular' else ('正式名額滿了，改臨時工' if was_regular else '本來就是臨時工'))
            moves.append(row)
    return {'into': a_cfg['name'], 'from': b_name, 'moves': moves, 'room_left': room}


def apply_merge(mdir, a, b, plan, env=None, start=True):
    base = cost_base(env)
    m = load(mdir)
    a_dir, b_dir = Path(m['companies'][a]['dir']), Path(m['companies'][b]['dir'])
    a_cfg_raw = fmt.read_json(a_dir / 'company.json')
    a_cfg = co.load(a_dir)
    a_teams, b_teams = co.team_dirs(a_dir, a_cfg), co.team_dirs(b_dir, co.load(b_dir))
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
        roster = fmt.read_json(tdir / 'team.json')
        b_mem = fmt.read_json(b_teams[mv['dept']] / 'team.json')['members'][mv['from']]
        mem = {'template': b_mem['template'], 'mail_to': [x for x in [mv['lead'], 'human'] if x]}
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
        a_cfg_raw.setdefault('staff', {})[mv['to']] = {'dept': mv['dept'], 'employment': mv['employment'],
                                                        'roles': ['併自 %s 的 %s' % (b, mv['from'])]}
        if src_notes.is_file():
            dst = fmt.Layout(tdir).notes(mv['to'])
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_notes, dst / 'notes.json')            # 跨任務記憶帶過去（對話紀錄留在 B 的封存）
        touched.add(mv['dept'])
    co.validate(a_cfg_raw, str(a_dir / 'company.json'))
    fmt.write_json(a_dir / 'company.json', a_cfg_raw, indent=2)
    if start and (a_dir / 'K').is_dir():
        e = co.env_for(a_dir, a_cfg)
        for dept in sorted(touched):
            co._run([co.CLI / 'aos-team', 'init', '--target', a_teams[dept]], e)
            co._run([co.CLI / 'aos-team', 'start', '--target', a_teams[dept]], e, check=False)
    # 帳：B 的餘額撥給 A（B 收回同額），B 標 merged、停、封存
    bal = cost.balances(base).get(b) or {}
    left = bal.get('balance') or {}
    usd = left.get('usd') if (left.get('usd') or 0) > 0 else None
    tok = left.get('tokens') if (left.get('tokens') or 0) > 0 else None
    if usd is not None or tok is not None:
        cost.account_grant(base, a, usd=usd, tokens=tok, note='併入 %s 的餘額' % b)
        cost.account_grant(base, b, usd=-usd if usd else None, tokens=-tok if tok else None, note='併入 %s' % a)
    if start and (b_dir / 'K').is_dir():
        co.down(b_dir, out=lambda *_: None)
    dest = Path(mdir) / 'archive' / ('%s-merged-%s' % (b, time.strftime('%Y%m%d-%H%M%S')))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(b_dir), str(dest))
    m = load(mdir)
    m['companies'][b].update(status='merged', closed_at=now(), archive=str(dest), merged_into=a)
    m['companies'][a]['note'] = (m['companies'][a].get('note') or '') + '併了 %s；' % b
    _event(m, kind='merge', company=b, into=a, moved_balance={'usd': usd, 'tokens': tok})
    save(mdir, m)
    return {'moved': [x for x in plan['moves'] if x['action'] == 'join'],
            'laid_off': [x for x in plan['moves'] if x['action'] == 'layoff'], 'balance_moved': {'usd': usd, 'tokens': tok}}


# ------------------------------------------------------------------ 指令 ----

def _pairs(items, cast):
    out = {}
    for it in items or []:
        if '=' not in it:
            raise MarketError('Usage', '要寫成 名=數字：%r' % it)
        k, v = it.split('=', 1)
        out[k] = cast(v)
    return out


def _print_rank(rows):
    print('名次  公司    排名分   品質   快    省    結單  平均秒   跳數  這輪花 token   餘額')
    for r in rows:
        print('%-4d  %-6s  %6.2f  %5.1f  %5.1f  %5.1f  %3d  %7s  %5s  %11d   %s' % (
            r['rank'], r['name'], r['score'], r['quality'], r['speed'], r['cost'], r['done'],
            r['seconds'] if r['seconds'] is not None else '-', r['hops'] if r['hops'] is not None else '-',
            r['spent_tokens'], json.dumps(r['balance'], ensure_ascii=False)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='market.py', description='市場層：排名、撥額度、倒閉、合併（spec/team/market.md）')
    ap.add_argument('--market', '-M')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('open')
    p.add_argument('name')
    p.add_argument('dir')
    p.add_argument('--usd', type=float)
    p.add_argument('--tokens', type=int)
    p = sub.add_parser('score')
    p.add_argument('name')
    p.add_argument('--quality', type=float)
    p.add_argument('--eval', dest='eval_path')
    p.add_argument('--seconds', type=float)
    p.add_argument('--hops', type=float)
    p = sub.add_parser('rank')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('grant')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--usd', action='append', help='名=美元（覆寫這一家這輪撥多少）')
    p.add_argument('--tokens', action='append', help='名=token')
    p = sub.add_parser('bankrupt')
    p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('close', help='經理人裁撤一家：沒花完的配額收回總池')
    p.add_argument('name')
    p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('pool', help='總池：錢還剩多少、名額還剩多少')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('slots', help='從總池撥名額給一家')
    p.add_argument('name')
    p.add_argument('--regular', type=int, default=0)
    p.add_argument('--cpu', type=int, default=0)
    p.add_argument('--llm-cpu', type=int, default=0)
    p = sub.add_parser('merge')
    p.add_argument('names', nargs='*')
    p.add_argument('--into')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--force', action='store_true')
    p = sub.add_parser('ls')
    p.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    try:
        mdir = market_dir(a.market)
        if a.cmd == 'open':
            c = open_company(mdir, a.name, a.dir, a.usd, a.tokens)
            print('開了 %s：%s' % (a.name, c['dir']))
            return 0
        if a.cmd == 'score':
            s = record_score(mdir, a.name, a.quality, a.eval_path, a.seconds, a.hops)
            print(json.dumps(s, ensure_ascii=False))
            return 0
        if a.cmd in ('rank', 'ls'):
            m = load(mdir)
            bal = cost.balances(cost_base())
            if a.cmd == 'rank':
                rows = rank(m, bal)
                if a.json:
                    print(json.dumps(rows, ensure_ascii=False, indent=1))
                else:
                    _print_rank(rows)
                return 0
            out = {n: dict(c, account=bal.get(n), score=m['scores'].get(n)) for n, c in m['companies'].items()}
            if a.json:
                print(json.dumps(out, ensure_ascii=False, indent=1))
            else:
                for n, c in out.items():
                    acc = c['account'] or {}
                    print('%-6s %-9s 餘額 %s  已花 %s  品質 %s' % (n, c['status'], json.dumps(acc.get('balance')),
                                                         json.dumps(acc.get('spent')), (c['score'] or {}).get('quality')))
            return 0
        if a.cmd == 'grant':
            rnd, rows, grants = do_grant(mdir, _pairs(a.usd, float), _pairs(a.tokens, int), a.dry_run)
            _print_rank(rows)
            for n, g in grants.items():
                print('第 %d 輪撥給 %s：usd %s、tokens %s（%s%s）' % (rnd, n, g['usd'], g['tokens'],
                                                             '%.0f%%' % (100 * g['share']), '，覆寫' if g['override'] else ''))
            print('（只是試算，沒寫帳）' if a.dry_run else '已記帳')
            return 0
        if a.cmd in ('bankrupt', 'close'):
            out = bankrupt(mdir, a.dry_run) if a.cmd == 'bankrupt' else [close(mdir, a.name, a.dry_run)]
            for o in out:
                print('%s %s：餘額 %s；收回總池 %s；名額回總池 %s；放出 %d 個名字；封存到 %s%s' % (
                    o['name'], '倒閉' if o['reason'] == 'bankrupt' else '裁撤', json.dumps(o['balance']),
                    json.dumps(o['recycled'] or '（沒有剩）', ensure_ascii=False), json.dumps(o['slots']),
                    len(o['freed']), o['archive'], '（只是試算）' if a.dry_run else ''))
            if not out:
                print('沒有公司倒閉')
            return 0
        if a.cmd == 'pool':
            m = load(mdir)
            p = pool_status(m, cost.balances(cost_base()))
            if a.json:
                print(json.dumps(p, ensure_ascii=False, indent=1))
            else:
                print('總池 錢：%s（董事給的總量 %s；沒設＝不管）' % (json.dumps(p['money']), json.dumps(m['params']['total'])))
                print('總池 名額：%s（機器 %s，營業中各家用掉 %s）' % (json.dumps(p['slots']), json.dumps(m['params']['machine']),
                                                           json.dumps(p['slots_used'])))
            return 0
        if a.cmd == 'slots':
            lim = grant_slots(mdir, a.name, a.regular, a.cpu, a.llm_cpu)
            print('%s 的上限變成 %s（kernel 開著要 aos-kernel cpu add 或下次 up 才多開）' % (a.name, json.dumps(lim)))
            return 0
        if a.cmd == 'merge':
            m = load(mdir)
            ops = operating(m)
            names = a.names or ops
            if len(names) != 2:
                raise MarketError('Usage', '合併要剛好兩家（營業中：%s）' % '、'.join(ops))
            if len(ops) > m['params']['merge_at'] and not a.force:
                raise MarketError('TooEarly', '營業中還有 %d 家，剩 %d 家才合併（--force 硬來）' % (len(ops), m['params']['merge_at']))
            if a.into:
                into = a.into
            else:
                rows = rank(m, cost.balances(cost_base()))
                into = next(r['name'] for r in rows if r['name'] in names)
            other = [n for n in names if n != into][0]
            plan = plan_merge(m['companies'][into]['dir'], m['companies'][other]['dir'], other,
                              m['params']['dept_order'])
            for mv in plan['moves']:
                print('%-4s %-22s → %s' % (mv['dept'], mv['from'], ('%s（%s）' % (mv['to'], '正式' if mv['employment'] == 'regular' else '臨時工'))
                                           if mv['action'] == 'join' else '裁掉：%s' % mv['why']))
            if a.dry_run:
                print('（只是計畫，%s 併進 %s；沒動任何檔）' % (other, into))
                return 0
            res = apply_merge(mdir, into, other, plan)
            print('%s 併進 %s：%d 人轉入、%d 人裁掉；餘額轉 %s' % (other, into, len(res['moved']), len(res['laid_off']),
                                                          json.dumps(res['balance_moved'])))
            return 0
    except (TeamError, cost.CostError) as e:
        print('market.py: %s: %s' % (getattr(e, 'code', 'Error'), getattr(e, 'msg', e)), file=sys.stderr)
        return 1
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
