#!/usr/bin/env python3
"""市場層（spec/team/market.md）：幾家一樣的小公司做同樣的單，經理人照表現撥額度；花光倒閉、剩兩家合併。

董事長＝human，經理人＝調度者（不在 aos 裡）；這支是經理人手上的**機械**指令，發多少照 market.json 的參數算，經理人可以覆寫。
帳戶用財務部的 `aos_team_cost`（`$AOS_COST_HOME/accounts.json`，cost.md §6）：配額＝撥款加總、已花＝帳本裡落在公司資料夾底下的呼叫。

子命令（`python3 aos_market.py <子命令> [--market 資料夾]`；沒給看 AOS_MARKET_HOME）：
  open 名 公司資料夾 [--usd X] [--tokens N]    開戶＋撥開辦費、登記進 market.json
  score 名 [--quality Q] [--eval 結果.json] [--seconds S] [--hops H] [--done N]   記這一輪的表現（沒給的從董事的單與總機單算）
  rank [--json]                                 算排名（不寫帳）
  grant [--dry-run] [--usd 名=X]… [--tokens 名=N]…   照排名撥這一輪的額度；--usd／--tokens 覆寫單一家
  bankrupt [--dry-run]                          餘額 ≤ 0 的：停公司、封存資料夾；剩的配額與名額回總池
  close 名 [--dry-run]                          經理人裁撤：沒花完的配額全部收回總池
  pool [--json]                                 總池：錢＝總量 − 已花 − 各家手上沒花的；名額＝機器 − 各家 limits
  slots 名 [--regular N] [--cpu N] [--llm-cpu N]    從總池撥名額（只收 ≥ 0）
  merge [A B] [--into A] [--dry-run] [--force]  剩兩家時合併（§5 of market.md）；上次合到一半＝接著做

改東西的子命令都拿 `<市場>/.market.lock`；grant／bankrupt／close／merge 先把要做的記進 market.json 再動手，
崩了重跑同一個指令接著做（帳戶照操作 ID 去重，不會重撥）。
  ls [--json]                                   每家：狀態、配額、已花、餘額、最近分數
"""
import argparse
import contextlib
import datetime
import fcntl
import json
import math
import os
import re
from pathlib import Path
import shutil
import sys
import time
import uuid

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))

import aos_company as co                                                   # noqa: E402
import aos_team_cost as cost                                               # noqa: E402
import aos_team_format as fmt                                              # noqa: E402
from aos_team_format import TeamError                                      # noqa: E402

TYPE = 'aos_market'
DEFAULT_PARAMS = {
    'weights': {'quality': 0.6, 'speed': 0.25, 'cost': 0.15},   # 排名分＝加權和（三項各 0～100）
    'round_pool': {'usd': 2.0, 'tokens': 50000000},             # 每輪撥出去的總額（約 10 張單）
    'shares': [0.35, 0.25, 0.2, 0.12, 0.08],                     # 第 1 名、第 2 名…拿總額的幾成（家數少就取前幾個再按比例放大）
    'seed': {'usd': 1.0, 'tokens': 25000000},                     # 開辦費：約 5 張單（試玩 09-25：deepseek 一張單 451 萬 token）
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


# ------------------------------------------------------------------ 開戶 ----

def open_company(mdir, name, cdir, usd=None, tokens=None, env=None):
    with market_lock(mdir):
        return _open_company(mdir, name, cdir, usd, tokens, env)


def _open_company(mdir, name, cdir, usd, tokens, env):
    base = cost_base(env)
    m = load(mdir)
    cdir = Path(os.path.abspath(os.path.expanduser(str(cdir))))
    co.load(cdir)                                    # 要是一家公司（company.json 驗得過）
    if name in m['companies']:
        # 收掉的名字不再用：舊帳戶還帶著它的撥款與花費，重用會把舊帳算進新公司（astra 必修 5）
        raise MarketError('AlreadyExists', '%s 已經在市場裡（%s）；換一個名字' % (name, m['companies'][name]['status']))
    real = os.path.realpath(str(cdir))
    for other, a in cost.load_accounts(base).items():
        root = a.get('root') or ''
        if other != name and root and _overlap(real, root):
            raise MarketError('Conflict', '%s 跟帳戶 %s 的資料夾 %s 重疊（同一個、或包著／被包著）：帳會重複算；換一個資料夾'
                              % (cdir, other, root))
    for other, c in m['companies'].items():
        if _overlap(real, os.path.realpath(c['dir'])):
            raise MarketError('Conflict', '%s 跟 %s（%s）用過的資料夾 %s 重疊' % (cdir, other, c['status'], c['dir']))
    seed = m['params']['seed']
    usd = seed.get('usd') if usd is None else usd
    tokens = seed.get('tokens') if tokens is None else tokens
    _finite(usd, 'usd', 0)
    _finite(tokens, 'tokens', 0)
    pool = pool_status(m, cost.balances(base))
    for k, v in (('usd', usd), ('tokens', tokens)):
        if k in pool['money'] and (v or 0) > pool['money'][k]:
            raise MarketError('PoolEmpty', '總池的 %s 只剩 %s，開辦費要 %s' % (k, pool['money'][k], v))
    lim = co.load(cdir)['limits']
    short = [k for k in pool['slots'] if lim.get(k, 0) > pool['slots'][k]]
    if short:
        raise MarketError('NoSlots', '機器名額不夠：%s（剩 %s，這家要 %s）' % (
            '、'.join(short), json.dumps(pool['slots']), json.dumps(lim)))
    cost.account_open(base, name, str(cdir))
    cost.account_grant(base, name, usd=usd, tokens=tokens, note='開辦費', op='open-%s' % name)
    m['companies'][name] = {'dir': str(cdir), 'status': 'operating', 'opened_at': now(), 'closed_at': None,
                            'note': ''}
    _event(m, kind='open', company=name, grant={'usd': usd, 'tokens': tokens}, slots=lim)
    save(mdir, m)
    return m['companies'][name]


# ------------------------------------------------------------------ 表現 ----

ALIAS_DEF = re.compile(r'(?<![A-Za-z0-9])([A-Z])\s*檔\s*`([^`\s]+)`')


def expand_codes(text):
    """證據檔的「代號 L30」寫法展開成檔名（真跑 09-25：「行號依據 A 檔 `…奇石.md`」再寫「A L30-L37」，
    證據檢查器認不出檔名，整份算壞）。回 (展開後的文字, {代號: 檔名})；沒有代號定義＝原樣、空 dict。"""
    codes = dict(ALIAS_DEF.findall(text))
    if not codes:
        return text, {}
    rx = re.compile(r'(?<![A-Za-z0-9_./`-])(%s)(?=\s*L\d)' % '|'.join(map(re.escape, codes)))
    out = [rx.sub(lambda m: codes[m.group(1)], ln) if ln.lstrip().startswith('|') else ln
           for ln in text.split('\n')]
    return '\n'.join(out), codes


def _recheck_evidence(project, name, notes):
    """證據列有「無檔名」的：展開代號後用同一支 evidence_check 重跑（展開的是暫存副本，不動原檔）。
    回新的 summary；展開不了回 None（notes 寫原因）。"""
    import tempfile
    sys.path.insert(0, str(LIB.parent / 'examples' / 'arknights' / 'eval'))
    try:
        import evidence_check as evc
    except ImportError as e:
        notes.append('%s：證據列有「無檔名」，展開不了（載不到 evidence_check：%s），證據那一項算 0' % (name, e))
        return None
    files = evc.evidence_files_for(Path(project), name) if project else []
    if not files:
        notes.append('%s：證據列有「無檔名」，展開不了（在 %s 找不到證據檔），證據那一項算 0' % (name, project))
        return None
    with tempfile.TemporaryDirectory(prefix='market-ev-') as td:
        tmp, found = [], {}
        for i, f in enumerate(files):
            text, codes = expand_codes(f.read_text(encoding='utf-8'))
            found.update(codes)
            t = Path(td) / ('%d-%s' % (i, f.name))
            t.write_text(text, encoding='utf-8')
            tmp.append(t)
        if not found:
            notes.append('%s：證據列有「無檔名」，展開不了（證據檔裡沒有「X 檔 `檔名`」這種代號定義），證據那一項算 0' % name)
            return None
        summary = evc.run(Path(project), files=tmp, corpus=evc.Corpus(Path(project)))['summary']
    notes.append('%s：證據檔的代號 %s 展開成檔名後重跑證據檢查：%d/%d 列 ok（原本全算「無檔名」）' % (
        name, '、'.join('%s＝%s' % kv for kv in sorted(found.items())), summary['ok'], summary['checked_rows']))
    return summary


def quality_from_eval(result, project=None, notes=False):
    """arknights eval 的結果檔 → 0～100：每人 機械 40％＋證據列 40％＋評審 20％（沒評審就前兩項放大成 100）。
    證據列有「無檔名」的：先把證據檔（這人的 cand_root，沒有就用 project）裡的代號展開成檔名重跑證據檢查；
    展開不了＝證據那一項照原樣（通常是 0），notes 寫原因。notes=True 回 (分數, [說明…])。"""
    people = result.get('people') or []
    msgs = []
    if not people:
        return (None, msgs) if notes else None
    total = 0.0
    for p in people:
        mech = p.get('mech') or {}
        ev = p.get('evidence') or {}
        if (ev.get('by_status') or {}).get('無檔名'):
            root = p.get('cand_root') or project
            fixed = _recheck_evidence(root, p.get('name', '?'), msgs) if root else None
            if root is None:
                msgs.append('%s：證據列有 %d 列「無檔名」，展開不了（不知道證據檔在哪；給公司的專案），證據那一項算 0'
                            % (p.get('name', '?'), ev['by_status']['無檔名']))
            ev = fixed or {'checked_rows': ev.get('checked_rows'), 'ok': 0}
        m = (mech.get('passed', 0) / mech['total']) if mech.get('total') else 0.0
        e = (ev.get('ok', 0) / ev['checked_rows']) if ev.get('checked_rows') else 0.0
        j = None
        judge = p.get('judge') or {}
        scores = judge.get('scores') if isinstance(judge, dict) else None
        if isinstance(scores, dict) and scores:
            vals = [v for v in scores.values() if isinstance(v, (int, float))]
            j = sum(vals) / len(vals) / 5.0 if vals else None
        total += (40 * m + 40 * e + 20 * j) if j is not None else (50 * m + 50 * e)
    q = round(total / len(people), 2)
    return (q, msgs) if notes else q


def _aware(t):
    return t if t is None or t.tzinfo is not None else t.astimezone()


def _read_letters(folder):
    out = []
    for p in fmt.json_files(folder) if folder.is_dir() else []:
        try:
            out.append(fmt.read_json(p))
        except TeamError:
            continue
    return out


def board_from_company(cdir, since=None):
    """董事的單（company.py order → 前台部門）這一輪的結果（真跑 09-25 修正：快＝董事等的時間，不是部門間跳的平均）。

    - 董事的單：前台部門 human 寄件格（含郵差收走的 done/）裡 human 寄出的 REQUEST、沒有 reply_to、不是總機寫的。
    - 結案信：前台部門 human 收件格裡狀態 DONE／FAILED、第一行不是〔給 …〕的信（總裁寫給董事的）。
      照時間先後配：每張單配它之後第一封還沒配走的結案信；還沒結案的單不算。
    - **成功**＝結案信是 DONE、信裡寫了品管的「結論：合格」、且這段時間裡有結案（done）的品管總機單。其他結案＝失敗。
    - 「這一輪」看結案信的時間（上一輪 grant 之後）；跨輪完成的單算在結案那一輪。
    回 {'done': 成功張數, 'failed': 失敗張數, 'seconds': 成功那幾張董事平均等幾秒（沒有＝None）,
        'hops': 成功那幾張平均經過幾張總機單＋1（只記、不算分）}。"""
    cdir = Path(cdir)
    cfg = co.load(cdir)
    front = co.host_dept(cfg, cfg['front'])
    tdir = co.team_dirs(cdir, cfg).get(front)
    t_since = _aware(fmt.parse_iso(since)) if since else None
    folder = cdir / 'switchboard' / 'orders'
    orders = [fmt.read_json(p) for p in fmt.json_files(folder)] if folder.is_dir() else []
    out_ids = {o.get('out_id') for o in orders}
    res = {'done': 0, 'failed': 0, 'seconds': None, 'hops': None}
    if tdir is None:
        return res
    lay = fmt.Layout(tdir)
    box = lay.outbox(fmt.HUMAN)
    asks = [x for x in _read_letters(box) + _read_letters(box / 'done')
            if x.get('from') == fmt.HUMAN and x.get('status') == 'REQUEST' and not x.get('reply_to')
            and 'kind' not in x and x.get('id') not in out_ids]
    closes = [x for x in _read_letters(lay.human_inbox)
              if x.get('status') in co.TERMINAL_STATUS and not co.MARK.match(x.get('text') or '')
              and x.get('from') not in (fmt.HUMAN, fmt.POST, fmt.BEAT)]

    def t(x):
        return _aware(fmt.parse_iso(x.get('at') or ''))
    asks = sorted((a for a in asks if t(a)), key=t)
    closes = sorted((c for c in closes if t(c)), key=t)
    secs, hops, used = [], [], set()
    for a in asks:
        t0 = t(a)
        c = next((c for c in closes if c['id'] not in used and t(c) >= t0), None)
        if c is None:
            continue
        used.add(c['id'])
        t1 = t(c)
        if t_since is not None and t1 < t_since:
            continue
        inside = [o for o in orders if _aware(fmt.parse_iso(o.get('at') or '')) and
                  t0 <= _aware(fmt.parse_iso(o['at'])) <= t1]
        qa_ok = any(o['to'].get('dept') == 'qa' and o.get('status') == 'done' for o in inside)
        text = c.get('text') or ''
        if c['status'] == 'DONE' and '結論：合格' in text and qa_ok:
            res['done'] += 1
            secs.append(max(0.0, (t1 - t0).total_seconds()))
            hops.append(len(inside) + 1)
        else:
            res['failed'] += 1
    if secs:
        res['seconds'] = round(sum(secs) / len(secs), 1)
        res['hops'] = round(sum(hops) / len(hops), 2)
    return res


def record_score(mdir, name, quality=None, eval_path=None, seconds=None, hops=None, done=None):
    with market_lock(mdir):
        return _record_score(mdir, name, quality, eval_path, seconds, hops, done)


def _record_score(mdir, name, quality, eval_path, seconds, hops, done):
    m = load(mdir)
    if name not in m['companies']:
        raise MarketError('NotFound', '市場裡沒有 %s' % name)
    src, notes = 'manual', []
    cdir = m['companies'][name]['dir']
    if eval_path is not None:
        try:
            project = co.load(cdir).get('project')
        except TeamError:
            project = None
        quality, notes = quality_from_eval(fmt.read_json(eval_path), project=project, notes=True)
        src = 'eval:%s' % eval_path
    _finite(quality, 'quality', 0, 100)
    _finite(seconds, 'seconds', 0)
    _finite(hops, 'hops', 0)
    _finite(done, 'done', 0)
    since = m['history'][-1]['at'] if m['history'] else None
    try:
        bd = board_from_company(cdir, since)
    except TeamError:
        bd = {'done': 0, 'failed': 0, 'seconds': None, 'hops': None}
    if done is None:
        done = 1 if seconds is not None else bd['done']        # 經理人手給秒數＝他認定有一張成功
    s = {'quality': quality, 'seconds': seconds if seconds is not None else bd['seconds'],
         'hops': hops if hops is not None else bd['hops'], 'done': done, 'failed': bd['failed'],
         'at': now(), 'source': src, 'round': len(m['history']) + 1}     # 分數綁輪次：grant 之後就不算了
    if notes:
        s['notes'] = notes
    m['scores'][name] = s
    save(mdir, m)
    return s


# ------------------------------------------------------------------ 排名 ----

def rank(m, bal):
    """回一列一家（照排名分高到低）：quality、speed、cost 三項各 0～100，再加權。

    - **這輪沒有成功結案（done＝0）的：品質、快、省、排名分全 0**（真跑 09-25：做壞的單照樣拿滿分品質）。
    - 品質：記下的分數（沒記＝0）。
    - 快：成功的幾家比董事等的秒數，最快那家 ÷ 自己 ×100。
    - 省：這一輪花的 token（這輪已花 − 上輪記下的已花），**只在成功的幾家之間比**，最省那家 ÷ 自己 ×100；成功但沒花＝100。
    - 只有一家成功：快、省都是滿分，那一列 note 寫「無對照」。
    - 同分同名次（名次跳號，例 1、1、3）；列的順序同分再照品質、名字排，只為了印得穩定。
    """
    w = m['params']['weights']
    last_spent = (m['history'][-1].get('spent') if m['history'] else None) or {}
    cur = len(m['history']) + 1
    rows = []
    for name in operating(m):
        s = m['scores'].get(name) or {}
        if s.get('round') != cur:           # 上一輪（或沒記輪次）的分數不算：這輪沒做事就沒分（astra 必修 9）
            s = {}
        b = bal.get(name) or {}
        spent_now = (b.get('spent') or {}).get('tokens') or 0
        spent = max(0, spent_now - (last_spent.get(name) or 0))
        done = s.get('done') or 0
        rows.append({'name': name, 'quality': float(s.get('quality') or 0) if done else 0.0,
                     'raw_quality': s.get('quality'), 'seconds': s.get('seconds'),
                     'hops': s.get('hops'), 'done': done, 'failed': s.get('failed') or 0, 'spent_tokens': spent,
                     'spent_total': spent_now, 'balance': b.get('balance'), 'broke': b.get('broke', False),
                     'scored': bool(s), 'note': None})
    ok = [r for r in rows if r['done']]
    fast = [r['seconds'] for r in ok if r['seconds']]
    cheap = [r['spent_tokens'] for r in ok if r['spent_tokens']]
    for r in rows:
        r['speed'] = round(100 * min(fast) / r['seconds'], 2) if r['done'] and fast and r['seconds'] else 0.0
        if not r['done']:
            r['cost'] = 0.0
        elif not r['spent_tokens']:
            r['cost'] = 100.0                  # 成功、這輪沒花 token＝最省（試玩 09-25：三家都 0 不該全拿 0）
        else:
            r['cost'] = round(100 * min(cheap) / r['spent_tokens'], 2)
        if r['done'] and len(ok) == 1:
            r['note'] = '省、快：無對照（這輪只有它成功）'
        r['score'] = round(w['quality'] * r['quality'] + w['speed'] * r['speed'] + w['cost'] * r['cost'], 2)
    rows.sort(key=lambda r: (-r['score'], -r['quality'], r['name']))
    for i, r in enumerate(rows, 1):
        r['rank'] = i if i == 1 or r['score'] != rows[i - 2]['score'] else rows[i - 2]['rank']
    return rows


def plan_grants(m, rows, usd_over=None, tok_over=None):
    """照排名分這一輪的總額：shares 取前 n 個按比例放大到 1；**同分的把那幾個名次的 shares 平均分**（不照名字破平）；
    這輪沒成功結案的、品質低於 min_quality 的、已經花光（broke）的拿 0；
    覆寫的照覆寫（花光的不准覆寫：先 bankrupt，astra 必修 11）。美元往下取到 0.0001。"""
    usd_over, tok_over = usd_over or {}, tok_over or {}
    for over in (usd_over, tok_over):
        for n, v in over.items():
            _finite(v, '%s 的覆寫' % n, 0)
            r = next((r for r in rows if r['name'] == n), None)
            if r is None:
                raise MarketError('NotFound', '%s 不在營業，不能覆寫' % n)
            if r['broke']:
                raise MarketError('Broke', '%s 已經花光，要先 bankrupt，不能撥款救活' % n)
    pool = m['params']['round_pool']
    shares = list(m['params']['shares'])[:len(rows)]
    shares += [0.0] * (len(rows) - len(shares))
    for sc in {r['score'] for r in rows}:                   # 同分均分
        idx = [i for i, r in enumerate(rows) if r['score'] == sc]
        avg = sum(shares[i] for i in idx) / len(idx)
        for i in idx:
            shares[i] = avg
    eligible = [r['done'] > 0 and r['quality'] >= m['params']['min_quality'] and not r['broke'] for r in rows]
    tot = sum(s for s, ok in zip(shares, eligible) if ok) or 1.0
    out = {}
    for r, s, ok in zip(rows, shares, eligible):
        frac = s / tot if ok else 0.0
        g = {'usd': usd_floor(pool.get('usd', 0) * frac) if pool.get('usd') is not None else None,
             'tokens': int(pool.get('tokens', 0) * frac) if pool.get('tokens') is not None else None,
             'share': round(frac, 4), 'override': False}
        if r['name'] in usd_over:
            g['usd'], g['override'] = usd_over[r['name']], True
        if r['name'] in tok_over:
            g['tokens'], g['override'] = tok_over[r['name']], True
        out[r['name']] = g
    return out


def do_grant(mdir, usd_over=None, tok_over=None, dry_run=False, env=None):
    """一輪撥款。順序（astra 必修 1、11）：先確定這輪要撥什麼（排名、縮額）→ 存進 market.json 的 pending
    （含操作 ID）→ 逐家撥（帳戶照操作 ID 去重）→ 記 history、清 pending。崩在中間重跑＝接著同一份計畫撥，不重撥。
    花光的公司不撥：先跑 bankrupt 再 grant。"""
    if dry_run:
        return _plan_grant(mdir, load(mdir), cost.balances(cost_base(env)), usd_over, tok_over)[:3]
    with market_lock(mdir):
        base = cost_base(env)
        m = load(mdir)
        pend = m.get('pending')
        if pend and pend.get('kind') == 'grant':
            rnd, rows, grants, capped, op = pend['round'], pend['ranking'], pend['grants'], pend['capped'], pend['op']
        else:
            if pend:
                raise MarketError('Pending', '還有沒做完的 %s（再跑一次那個指令接著做）' % pend.get('kind'))
            rnd, rows, grants, capped = _plan_grant(mdir, m, cost.balances(base), usd_over, tok_over)
            op = 'grant-r%d-%s' % (rnd, uuid.uuid4().hex[:8])
            m['pending'] = {'kind': 'grant', 'round': rnd, 'op': op, 'ranking': rows, 'grants': grants, 'capped': capped}
            save(mdir, m)
        for name, g in grants.items():
            if (g['usd'] or 0) == 0 and (g['tokens'] or 0) == 0:
                continue
            cost.account_grant(base, name, usd=g['usd'], tokens=g['tokens'], op='%s:%s' % (op, name),
                               note='第 %d 輪 第 %d 名%s' % (rnd, next(r['rank'] for r in rows if r['name'] == name),
                                                          '（經理人覆寫）' if g['override'] else ''))
        m['history'].append({'round': rnd, 'at': now(), 'ranking': rows, 'grants': grants, 'capped': capped,
                             'spent': {r['name']: r['spent_total'] for r in rows}, 'op': op})
        _event(m, kind='grant', round=rnd, grants={n: {'usd': g['usd'], 'tokens': g['tokens']} for n, g in grants.items()},
               capped=capped)
        m.pop('pending', None)
        save(mdir, m)
        return rnd, rows, grants


def _plan_grant(mdir, m, bal, usd_over, tok_over):
    rows = rank(m, bal)
    grants = plan_grants(m, rows, usd_over, tok_over)
    if not any(r['scored'] for r in rows):
        # 真跑 09-25：撥完一輪什麼都沒做再 grant，第 2 輪照樣整份發出去。這輪一家都沒 score＝拒絕、什麼都不發
        raise MarketError('NoScores', '本輪無分數（第 %d 輪還沒有任何一家 score）：什麼都沒發；先 score 再 grant'
                          % (len(m['history']) + 1))
    pool = pool_status(m, bal)
    capped = {}
    for k, left in pool['money'].items():
        want = sum((g[k] or 0) for g in grants.values() if (g[k] or 0) > 0)
        if want > left:                                  # 總池不夠：照比例往下縮（不會超過剩的）
            f = max(0.0, left) / want if want else 0.0
            for g in grants.values():
                if (g[k] or 0) > 0:
                    g[k] = usd_floor(g[k] * f) if k == 'usd' else int(g[k] * f)
            got = sum((g[k] or 0) for g in grants.values() if (g[k] or 0) > 0)
            assert got <= max(0.0, left) + 1e-9, (k, got, left)
            capped[k] = {'want': want, 'pool': left}
    return len(m['history']) + 1, rows, grants, capped


def grant_slots(mdir, name, regular=0, cpu=0, llm_cpu=0, env=None):
    """從總池撥名額給一家：llm cpu＝limits.llm_cpu、pools.llm +1；cpu（不含 llm，同 HR 的算法）＝limits.cpu、
    pools.default +1；人頭＝limits.regular +1。不能超過那家的 limits_max 與總池。
    kernel 開著的話池要 aos-kernel cpu add 才真的多開（這裡只改 company.json；下次 up 對齊 K 的池）。
    只收 ≥ 0：收回名額不走這裡（名額只在公司收掉、確定停好時回總池，astra 必修 12）。"""
    with market_lock(mdir):
        return _grant_slots(mdir, name, regular, cpu, llm_cpu, env)


def _grant_slots(mdir, name, regular, cpu, llm_cpu, env):
    m = load(mdir)
    if name not in operating(m):
        raise MarketError('NotFound', '%s 不在營業' % name)
    want = {'regular': regular, 'cpu': cpu, 'llm_cpu': llm_cpu}
    for k, v in want.items():
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise MarketError('Usage', 'slots 的 %s 要是 ≥ 0 的整數（收回名額不走這裡）：%r' % (k, v))
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

def _close_row(mdir, m, bal, name, reason):
    """收掉一家要記的東西（試算也用）：餘額、要收回的、名額、放出的名字、封存到哪。"""
    c = m['companies'][name]
    cdir = Path(c['dir'])
    left = (bal.get(name) or {}).get('balance') or {}
    try:
        cfg = co.load(cdir)
        freed = co.all_member_names(cdir, cfg)
        slots = dict(cfg['limits'])
    except TeamError:
        freed, slots = [], {}
    dest = Path(mdir) / 'archive' / ('%s-%s-%s' % (name, reason, time.strftime('%Y%m%d-%H%M%S')))
    return {'name': name, 'reason': reason, 'balance': left,
            'recycled': {k: v for k, v in left.items() if v is not None and v > 0}, 'slots': slots, 'freed': freed,
            'archive': str(dest)}


def _stop(cdir, stop):
    """停一家；停不乾淨＝StopFailed（不封存、不收回、不放名額，astra 必修 4）。"""
    cdir = Path(cdir)
    if stop and (cdir / 'company.json').is_file() and (cdir / 'K').is_dir():
        if co.down(cdir, out=lambda *_: None) != 0:
            raise MarketError('StopFailed', '%s 沒停乾淨（company.py down -C %s 看哪裡），先不封存、名額不放；'
                              '停好再跑一次同一個指令' % (cdir, cdir))


def _shutdown(mdir, m, base, name, reason, stop=True):
    """收掉一家，分兩段、每段先記再做（astra 必修 2、4）：
    1. 標 closing（記下封存目的地、操作 ID、名額）並存檔——這時還占著名額與錢；
    2. 停（失敗＝停在 closing，重跑同一個指令接著做）→ 停好後才讀餘額、收回（操作 ID 去重）→ 搬進 archive → 標結案。"""
    c = m['companies'][name]
    if c['status'] != 'closing':
        row = _close_row(mdir, m, cost.balances(base), name, reason)
        c['closing'] = {'reason': reason, 'archive': row['archive'], 'slots': row['slots'], 'freed': row['freed'],
                        'op': '%s-%s-%s' % (reason, name, uuid.uuid4().hex[:8]), 'recycled': None}
        c['status'] = 'closing'
        save(mdir, m)
    return _finish_close(mdir, m, base, name, stop)


def _finish_close(mdir, m, base, name, stop=True):
    c = m['companies'][name]
    cl = c['closing']
    cdir, dest = Path(c['dir']), Path(cl['archive'])
    if cdir.is_dir():
        _stop(cdir, stop)
    b = cost.balances(base).get(name) or {}
    left = b.get('balance') or {}
    if cl.get('recycled') is None:                   # 停好後才算：還在跑的單記的帳都進來了
        cl['recycled'] = {k: v for k, v in left.items() if v is not None and v > 0}
        cl['balance'] = left
        save(mdir, m)
    rec = cl['recycled']
    if rec:
        cost.account_grant(base, name, usd=-rec['usd'] if 'usd' in rec else None,
                           tokens=-rec['tokens'] if 'tokens' in rec else None, op=cl['op'] + ':recycle',
                           note='%s：沒花完的配額收回總池' % ('倒閉' if cl['reason'] == 'bankrupt' else '裁撤'))
    if cdir.is_dir() and not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(cdir), str(dest))
    reason = cl['reason']
    c.update(status='bankrupt' if reason == 'bankrupt' else 'closed', closed_at=now(), archive=str(dest),
             freed=cl['freed'])
    c.pop('closing', None)
    _event(m, kind=reason, company=name, recycled=rec, slots=cl['slots'], freed=cl['freed'])
    save(mdir, m)
    return {'name': name, 'reason': reason, 'balance': cl.get('balance', left), 'recycled': rec,
            'slots': cl['slots'], 'freed': cl['freed'], 'archive': str(dest)}


def _recover_closing(mdir, m, base, stop=True):
    """上次收到一半（closing）的先收完。"""
    return [_finish_close(mdir, m, base, n, stop) for n, c in list(m['companies'].items()) if c['status'] == 'closing']


def bankrupt(mdir, dry_run=False, env=None, stop=True):
    """餘額 ≤ 0（有撥過的那一種）的營業中公司倒閉：另一種還有剩的收回總池；名額回總池；停、封存（前綴可以再用）。
    上次收到一半的（closing）先收完。"""
    base = cost_base(env)
    if dry_run:
        m, bal = load(mdir), cost.balances(base)
        return [_close_row(mdir, m, bal, n, 'bankrupt') for n in operating(m) if (bal.get(n) or {}).get('broke')]
    with market_lock(mdir):
        m = load(mdir)
        out = [r for r in _recover_closing(mdir, m, base, stop) if r['reason'] == 'bankrupt']
        bal = cost.balances(base)
        for n in [n for n in operating(m) if (bal.get(n) or {}).get('broke')]:
            out.append(_shutdown(mdir, m, base, n, 'bankrupt', stop))
        return out


def close(mdir, name, dry_run=False, env=None, stop=True):
    """經理人裁撤一家（還沒花光）：沒花完的配額全部收回總池，其餘同倒閉。"""
    base = cost_base(env)
    if dry_run:
        m = load(mdir)
        if name not in operating(m):
            raise MarketError('NotFound', '%s 不在營業' % name)
        return _close_row(mdir, m, cost.balances(base), name, 'closed')
    with market_lock(mdir):
        m = load(mdir)
        c = m['companies'].get(name)
        if c is not None and c['status'] == 'closing':
            return _finish_close(mdir, m, base, name, stop)
        if name not in operating(m):
            raise MarketError('NotFound', '%s 不在營業' % name)
        return _shutdown(mdir, m, base, name, 'closed', stop)


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
    print('名次  公司    排名分   品質   快    省    成功 失敗  董事等秒  跳數  這輪花 token   餘額')
    for r in rows:
        extra = []
        if r.get('scored') is False:
            extra.append('這輪沒 score')
        elif not r['done']:
            extra.append('這輪沒有成功結案：全項 0（原品質 %s）' % r.get('raw_quality'))
        if r.get('note'):
            extra.append(r['note'])
        print('%-4d  %-6s  %6.2f  %5.1f  %5.1f  %5.1f  %3d  %3d  %8s  %5s  %11d   %s%s' % (
            r['rank'], r['name'], r['score'], r['quality'], r['speed'], r['cost'], r['done'], r.get('failed') or 0,
            r['seconds'] if r['seconds'] is not None else '-', r['hops'] if r['hops'] is not None else '-',
            r['spent_tokens'], json.dumps(r['balance'], ensure_ascii=False),
            '  ← ' + '；'.join(extra) if extra else ''))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='market.py', description='市場層：排名、撥額度、倒閉、合併（spec/team/market.md）')
    ap.add_argument('--market', '-M', help='市場資料夾（market.json、archive/）；沒給看 AOS_MARKET_HOME')
    sub = ap.add_subparsers(dest='cmd', required=True)
    DRY = '只算給你看，不寫帳、不動檔'
    p = sub.add_parser('open', help='開戶＋撥開辦費、登記進市場（從總池出）')
    p.add_argument('name', help='帳戶名（例 c1；收掉的名字不能再用）')
    p.add_argument('dir', help='公司資料夾（company.py new 生的）；不能跟別家的重疊')
    p.add_argument('--usd', type=float, help='開辦費美元（預設 params.seed.usd）')
    p.add_argument('--tokens', type=int, help='開辦費 token（預設 params.seed.tokens）')
    p = sub.add_parser('score', help='記這一輪的表現（grant 之後就換下一輪、要重記）')
    p.add_argument('name', help='公司')
    p.add_argument('--quality', type=float, help='品質分 0～100（經理人直接給）')
    p.add_argument('--eval', dest='eval_path', help='arknights 評分器的結果檔（算品質分，取代 --quality）')
    p.add_argument('--seconds', type=float, help='董事平均等幾秒（不給＝從董事的單到總裁結案信算；給了＝算一張成功）')
    p.add_argument('--hops', type=float, help='平均跳數（只記、不算分；不給＝從總機單算）')
    p.add_argument('--done', type=int, help='這輪成功結案幾張（經理人覆寫；不給＝品管合格＋總裁結案信的張數）')
    p = sub.add_parser('rank', help='算這一輪的排名（品質、快、省加權；不寫帳）')
    p.add_argument('--json', action='store_true', help='印 JSON')
    p = sub.add_parser('grant', help='照排名撥這一輪的額度（花光的不撥，先跑 bankrupt）')
    p.add_argument('--dry-run', action='store_true', help=DRY)
    p.add_argument('--usd', action='append', help='名=美元：覆寫這一家這輪撥多少（≥ 0；要收回用 close）')
    p.add_argument('--tokens', action='append', help='名=token：同上')
    p = sub.add_parser('bankrupt', help='花光的（某一種餘額 ≤ 0）倒閉：停、剩的收回總池、封存')
    p.add_argument('--dry-run', action='store_true', help=DRY)
    p = sub.add_parser('close', help='經理人裁撤一家：沒花完的配額收回總池')
    p.add_argument('name', help='公司')
    p.add_argument('--dry-run', action='store_true', help=DRY)
    p = sub.add_parser('pool', help='總池：錢還剩多少、名額還剩多少')
    p.add_argument('--json', action='store_true', help='印 JSON')
    p = sub.add_parser('slots', help='從總池撥名額給一家（只加不減；下次 company.py up 生效）')
    p.add_argument('name', help='公司')
    p.add_argument('--regular', type=int, default=0, help='正式員工名額 +N')
    p.add_argument('--cpu', type=int, default=0, help='cpu（default 池）+N')
    p.add_argument('--llm-cpu', type=int, default=0, help='llm cpu（llm 池）+N')
    p = sub.add_parser('merge', help='剩 merge_at 家時合併：排名高的併掉低的；上次合到一半＝接著做')
    p.add_argument('names', nargs='*', help='兩家（不給＝營業中那兩家）')
    p.add_argument('--into', help='指定併入方（不給＝排名高的）')
    p.add_argument('--dry-run', action='store_true', help='只印計畫（誰轉入、誰裁掉、正式或臨時）')
    p.add_argument('--force', action='store_true', help='營業中還多於 merge_at 家也硬合')
    p = sub.add_parser('ls', help='每家：狀態、餘額、已花、這輪品質')
    p.add_argument('--json', action='store_true', help='印 JSON')
    a = ap.parse_args(argv)
    try:
        mdir = market_dir(a.market)
        if a.cmd == 'open':
            c = open_company(mdir, a.name, a.dir, a.usd, a.tokens)
            print('開了 %s：%s' % (a.name, c['dir']))
            return 0
        if a.cmd == 'score':
            s = record_score(mdir, a.name, a.quality, a.eval_path, a.seconds, a.hops, a.done)
            print(json.dumps(s, ensure_ascii=False))
            for n in s.get('notes') or []:
                print('說明：' + n)
            if not s['done']:
                print('注意：%s 這輪沒有成功結案（失敗 %d 張），排名時品質、快、省都算 0' % (a.name, s['failed']))
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
            if not any(r['done'] for r in rows):
                print('這輪沒有公司成功結案：照公式全部撥 0')
            for n, g in grants.items():
                print('第 %d 輪撥給 %s：usd %s、tokens %s（%s）' % (rnd, n, g['usd'], g['tokens'],
                                                           '經理人覆寫' if g['override'] else '%.0f%%' % (100 * g['share'])))
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
            pend = m.get('pending') or {}
            if pend.get('kind') == 'merge' and not a.dry_run:          # 上次合到一半：接著做
                res = apply_merge(mdir, pend['into'], pend['from'])
                print('接著做完：%s 併進 %s；餘額轉 %s' % (pend['from'], pend['into'], json.dumps(res['balance_moved'])))
                return 0
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
