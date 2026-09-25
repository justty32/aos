"""財務部的預算與名額：budget.json 讀驗（全公司／團隊）、用量對預算、超了沒（郵差退件理由、ls 第一行）、kernel 的 cpu 名額那行。"""
import json
import os
import subprocess

from aos_team_cost_ledger import (
    BUDGET, CostError, CPU_LIMITS, family, home, LIMIT_KEYS, load_prices, read_ledger, select,
    since_time, usd
)
from aos_team_cost_account import account_of, balances


# ------------------------------------------------------------------ 預算 ----

def check_budget(obj, where):
    """驗預算的形狀（team.json 的 budget 與 budget.json 共用）；回補好 since 的新物件。錯丟 ValueError(白話)。

    {"since": "week"|"day"|"all"|"YYYY-MM-DD", "<家族>|all": {"usd": 數字, "tokens": 整數}, …}"""
    if obj is None:
        return None
    if not isinstance(obj, dict):
        raise ValueError('%s 要是物件' % where)
    out = {'since': obj.get('since', 'week')}
    if not isinstance(out['since'], str):
        raise ValueError('%s.since 要是字串（week、day、all、YYYY-MM-DD）' % where)
    try:
        since_time(out['since'])
    except CostError as e:
        raise ValueError('%s.since：%s' % (where, e.msg))
    for fam, lim in obj.items():
        if fam in ('since', '_metainfo', '_note'):
            continue
        if fam == 'cpus':                  # 只給 cost 表的 cpu 行當上限顯示，不是花費預算
            if not isinstance(lim, dict) or set(lim) - set(CPU_LIMITS) or not all(
                    type(v) is int and v > 0 for v in lim.values()):
                raise ValueError('%s.cpus 要是 {"max": 正整數, "llm_max": 正整數}' % where)
            out['cpus'] = dict(lim)
            continue
        if not isinstance(lim, dict) or not (set(lim) - {'since'}) or set(lim) - set(LIMIT_KEYS):
            raise ValueError('%s.%s 要是 {"usd": 數字} 或 {"tokens": 整數}（可兩個都寫，可另加 since）' % (where, fam))
        if 'since' in lim:
            try:
                since_time(lim['since'] if isinstance(lim['since'], str) else '?')
            except CostError as e:
                raise ValueError('%s.%s.since：%s' % (where, fam, e.msg))
        for k, v in lim.items():
            if k == 'since':
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or (k == 'tokens' and not isinstance(v, int)):
                raise ValueError('%s.%s.%s 要是 ≥ 0 的%s' % (where, fam, k, '整數' if k == 'tokens' else '數字'))
        out[fam] = dict(lim)
    return out


def load_company_budget(base):
    path = os.path.join(base, BUDGET)
    try:
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise CostError('BudgetInvalid', '%s 讀不了：%s' % (path, e))
    try:
        return check_budget(obj, BUDGET)
    except ValueError as e:
        raise CostError('BudgetInvalid', str(e))


def load_team_budget(team_dir):
    path = os.path.join(team_dir, 'team.json')
    try:
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
    except (OSError, ValueError):
        return None
    try:
        return check_budget(obj.get('budget') if isinstance(obj, dict) else None, 'team.json.budget')
    except ValueError:
        return None       # 名冊壞了由 load_roster 報；這裡當沒預算


def usage_against(budget, rows, prices, scope, now=None):
    """一份預算 → [{scope, family, kind, used, limit, ratio, since}]。"""
    if not budget:
        return []
    out = []
    for fam, lim in budget.items():
        if fam in ('since', 'cpus'):
            continue
        start = lim.get('since', budget['since'])
        mine = [r for r in select(rows, since_time(start, now))
                if fam == 'all' or family(r.get('model') or '', prices) == fam]
        for kind, limit in lim.items():
            if kind == 'since':
                continue
            if kind == 'tokens':
                used = sum(int(r.get('prompt_tokens') or 0) + int(r.get('completion_tokens') or 0) for r in mine)
            else:
                used = round(sum(usd(r.get('model') or '', int(r.get('prompt_tokens') or 0),
                                     int(r.get('completion_tokens') or 0), prices) or 0 for r in mine), 4)
            out.append({'scope': scope, 'family': fam, 'kind': kind, 'used': used, 'limit': limit,
                        'ratio': (used / limit) if limit else (1.0 if used else 0.0), 'since': start})
    return out


def budget_status(env, team_dir=None, now=None):
    """回 (各條預算用了幾成, 超了的那幾條)。沒設 AOS_COST_HOME＝([], [])。預算檔壞了丟 CostError。"""
    base = home(env)
    if base is None:
        return [], []
    prices = load_prices(base)
    rows, _ = read_ledger(base)
    lines = usage_against(load_company_budget(base), rows, prices, 'company', now)
    if team_dir:
        team = os.path.realpath(team_dir)
        lines += usage_against(load_team_budget(team), [r for r in rows if r.get('team') == team], prices,
                               'team', now)
        acct = account_of(base, team)
        if acct:
            b = balances(base, prices, rows)[acct]
            for kind in ('usd', 'tokens'):
                if b['quota'][kind] is not None:
                    lines.append({'scope': 'account', 'family': acct, 'kind': kind, 'used': b['spent'][kind],
                                  'limit': b['quota'][kind], 'since': '開戶',
                                  'ratio': (b['spent'][kind] / b['quota'][kind]) if b['quota'][kind] else 1.0})
    return lines, [x for x in lines if x['used'] >= x['limit']]


def _fmt_amount(kind, v):
    return ('$%.4f' % v) if kind == 'usd' else ('%s token' % format(int(v), ','))


SCOPE_NAMES = {'company': '全公司', 'team': '本團隊', 'account': '帳戶'}


def over_text(over):
    return '、'.join('%s %s %s 用了 %s／上限 %s（%s 起）' % (
        SCOPE_NAMES[o['scope']], o['family'], '金額' if o['kind'] == 'usd' else 'token',
        _fmt_amount(o['kind'], o['used']), _fmt_amount(o['kind'], o['limit']), o['since']) for o in over)


def ls_line(env, team_dir):
    """aos-team ls 的第一行；沒設 AOS_COST_HOME＝None（不印）。"""
    if home(env) is None:
        return None
    try:
        _, over = budget_status(env, team_dir)
    except CostError as e:
        return '財務：預算檔壞了（%s）——郵差照常派工，修好再看' % e.msg
    if over:
        return '財務：超預算，郵差不派新單：%s' % over_text(over)
    return '財務：ok（預算內；aos-team cost budget 看幾成）'


def hold_reason(env, team_dir):
    """郵差派工前問：要不要擋。回 None（不擋）或 (白話原因, 簽名)。預算檔壞了不擋（只在 ls 報）。"""
    try:
        _, over = budget_status(env, team_dir)
    except CostError:
        return None
    if not over:
        return None
    sig = ';'.join(sorted('%s/%s/%s' % (o['scope'], o['family'], o['kind']) for o in over))
    return over_text(over), sig


# ------------------------------------------------------------------ kernel 的 cpu 數 ----

def cpu_limits(env):
    """cpu 行印的上限：預設新創規模 20／5；budget.json 的 "cpus" 可改（例：擴張 {"max": 200, "llm_max": 20}）。"""
    out = dict(CPU_LIMITS)
    base = home(env)
    try:
        b = load_company_budget(base) if base else None
    except CostError:
        b = None
    out.update((b or {}).get('cpus') or {})
    return out


def cpu_line(env):
    """現在開著幾個 cpu／幾個 llm cpu（上限由 HR 管，這裡只印、超了標出來）。拿不到回白話原因。"""
    lim = cpu_limits(env)
    cap = '上限 %d／llm %d，由 HR 管' % (lim['max'], lim['llm_max'])
    k = env.get('AOS_KERNEL_HOME')
    if not k or not os.path.isabs(k):
        return 'cpu：沒設 AOS_KERNEL_HOME，看不到（%s）' % cap
    exe = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cli', 'aos-kernel')
    try:
        p = subprocess.run([exe, 'ls', '--json', '--target', k], capture_output=True, text=True, timeout=15)
        data = json.loads(p.stdout)
        total = data['counts']['pools']['want']
        llm = (data.get('pools') or {}).get('llm', {}).get('want', 0)
        busy = data['counts']['pools'].get('busy')
    except Exception as e:                       # noqa: BLE001 — 只少一行，不擋查帳
        return 'cpu：aos-kernel ls 讀不到（%s）' % (' '.join(str(e).split())[:120])
    over = '  ← 超過上限' if (total or 0) > lim['max'] or (llm or 0) > lim['llm_max'] else ''
    return 'cpu：開著 %s 個（忙 %s）、其中 llm cpu %s 個（%s）%s' % (total, busy, llm, cap, over)
