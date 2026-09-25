"""市場的帳本：常數與預設參數、MarketError、市場資料夾與鎖、market.json 讀寫、營業中／持有中的判定、總池（錢與名額）。"""
import contextlib
import datetime
import fcntl
import json
import math
import os
from pathlib import Path

import aos_company as co
import aos_team_cost as cost
import aos_team_format as fmt
from aos_team_format import TeamError


TYPE = 'aos_market'
DEFAULT_PARAMS = {
    'weights': {'quality': 0.6, 'speed': 0.25, 'cost': 0.15},   # 排名分＝加權和（三項各 0～100）
    'round_pool': {'usd': 2.0, 'tokens': 50000000},             # 每輪撥出去的總額（約 10 張單）
    'shares': [0.35, 0.25, 0.2, 0.12, 0.08],                     # 第 1 名、第 2 名…拿總額的幾成（家數少就取前幾個再按比例放大）
    'seed': {'usd': 1.0, 'tokens': 25000000},                     # 開辦費：約 5 張單（試玩 09-25：deepseek 一張單 451 萬 token）
    'review_factors': [1.0, 0.7, 0.4],                           # 品質×審查係數：第 1／2／3 次審查才過（第 75 題，經理人 09-25 晚定的起始值、可調）
    'min_quality': 0,                                            # 品質分低於這個＝這輪不撥（0＝不設門檻）
    'merge_at': 2,                                               # 營業中的剩幾家就合併
    'dept_order': ['mfg', 'qa', 'rd', 'lib', 'hq'],               # 合併時先收哪個部門的人
    'total': {},                                                 # 董事給的總量 {"usd", "tokens"}；空＝不設總池（撥款不檢查）
    'machine': {'regular': 100, 'cpu': 200, 'llm_cpu': 25},      # 整台機器的名額：各家 limits 加總不能超過（董事 09-25 14:20：llm cpu 20→25）
}
DEPT_ORDER = DEFAULT_PARAMS['dept_order']


class MarketError(TeamError):
    pass


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


USD_UNIT = 10000          # 美元的最小單位 0.0001：撥款一律往下取到這一位，不會四捨五入超發（astra 必修 15）


def usd_floor(v):
    return math.floor(v * USD_UNIT + 1e-9) / USD_UNIT


def _finite(v, where, lo=None, hi=None):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise MarketError('Usage', '%s 要是有限的數字：%r' % (where, v))
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise MarketError('Usage', '%s 要在 %s～%s：%r' % (where, lo, '' if hi is None else hi, v))
    return v


@contextlib.contextmanager
def market_lock(mdir):
    """市場的交易鎖（astra 必修 3）：讀 market.json → 算 → 撥款／改名冊 → 寫，整段拿著；兩個經理人指令不會同時撥款或合併。"""
    Path(mdir).mkdir(parents=True, exist_ok=True)
    with open(Path(mdir) / '.market.lock', 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


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


def holding(m):
    """還占著錢與名額的：營業中＋收到一半的（closing／merging：還沒確定停好，不能放名額，astra 必修 4）。"""
    return [n for n, c in m['companies'].items() if c['status'] in ('operating', 'closing', 'merging')]


# ------------------------------------------------------------------ 總池 ----

def pool_status(m, bal):
    """總池（董事 09-25）：錢＝總量 − 各家已花（含收掉的）− 營業中各家手上沒花的配額；
    名額＝機器上限 − 營業中各家 limits 加總。收掉的公司手上沒花的配額在收掉時已收回（撥負的），名額自然回來。"""
    money = {}
    for k, total in (m['params'].get('total') or {}).items():
        if total is None:
            continue
        spent = sum(((b.get('spent') or {}).get(k) or 0) for n, b in bal.items() if n in m['companies'])
        held = sum(max(0, ((bal.get(n) or {}).get('balance') or {}).get(k) or 0) for n in holding(m))
        money[k] = round(total - spent - held, 6)
    used = {k: 0 for k in m['params']['machine']}
    for n in holding(m):
        c = m['companies'][n]
        try:
            lim = co.load(c['dir'])['limits']
        except TeamError:
            lim = (c.get('closing') or {}).get('slots') or {}    # 資料夾已經搬走、還沒結案：用記下的
        for k in used:
            used[k] += lim.get(k, 0)
    slots = {k: m['params']['machine'][k] - used[k] for k in used}
    return {'money': money, 'slots': slots, 'slots_used': used}


def _event(m, **kw):
    kw.setdefault('at', now())
    m['events'].append(kw)
    return kw


def _overlap(a, b):
    a, b = a.rstrip('/'), b.rstrip('/')
    return a == b or a.startswith(b + '/') or b.startswith(a + '/')
