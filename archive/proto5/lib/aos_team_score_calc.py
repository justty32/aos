"""`aos-team score` 的門檻與小算法：各軸分數門檻、任務單歷史的起訖與開著的時段、領隊的那封信、done_when 條數、時窗與秒數印法。"""
from aos_team_format import HUMAN, TERMINAL

from aos_team_score_read import when


RUNS_NEEDED = 10


# ------------------------------------------------------------------ 門檻 ----

def score_think(n):
    """團隊欄：0～1→5、2～5→4、6～15→3、16～40→2、>40→1。"""
    return 5 if n <= 1 else 4 if n <= 5 else 3 if n <= 15 else 2 if n <= 40 else 1


def score_tokens(n):
    """團隊每件事的 token：<20k→5、<60k→4、<150k→3、<400k→2、否則 1。"""
    return 5 if n < 20000 else 4 if n < 60000 else 3 if n < 150000 else 2 if n < 400000 else 1


def score_wall(seconds):
    """牆上時間：<1 分→5、<3→4、<10→3、<30→2、否則 1。"""
    m = seconds / 60.0
    return 5 if m < 1 else 4 if m < 3 else 3 if m < 10 else 2 if m < 30 else 1


def score_runs(ok, total):
    """跑不到 10 次＝None。全過＝4（5 分要崩潰恢復測試，團隊層這裡不給）；≥80%→3；≥50%→2；否則 1。"""
    if total < RUNS_NEEDED:
        return None
    rate = ok / total
    return 4 if ok == total else 3 if rate >= 0.8 else 2 if rate >= 0.5 else 1


# ------------------------------------------------------------------ 算 ----

def history_at(t, i):
    h = t['history'][i]
    return when(h.get('at')) if isinstance(h, dict) else None


def task_end(t):
    """單子結束（done／failed／cancelled）那一刻：最後一筆「進到目前這個結束狀態」的 history。沒結束＝None。"""
    if t.get('status') not in TERMINAL:
        return None
    for i in range(len(t['history']) - 1, -1, -1):
        h = t['history'][i]
        if isinstance(h, dict) and h.get('to') == t['status']:
            return history_at(t, i)
    return when(t.get('updated_at'))


def task_open(t):
    return when(t.get('created_at')) or next((history_at(t, i) for i, h in enumerate(t['history'])
                                               if isinstance(h, dict) and h.get('event') == 'opened'), None)


def human_letters(sent):
    return [r for r in sent if r.get('kind') == 'letter' and r.get('from') == HUMAN and when(r.get('at'))]


def task_start(t, sent, leads, tasks):
    """起點（spec/team/score.md〈起點〉）。回 (datetime 或 None, 說明)。

    人開的單（門房 handoff、人寄的申請）：那份申請的 at。領隊開的單：人寄給這位領隊的 REQUEST 信裡，
    落在「這位領隊上一張單開單之後、這張開單之前」的最後一封（落穿給領隊的那句話）；沒有＝開單時間。
    """
    opened = task_open(t)
    if opened is None:
        return None, '單子沒有開單時間'
    by = t.get('opened_by')
    if by == HUMAN:
        for r in sent:
            if r.get('kind') == 'request' and r.get('id') == t.get('request') and when(r.get('at')):
                return min(when(r['at']), opened), '人寄出開單申請'
        return opened, '開單'
    r = lead_letter(t, sent, leads, tasks)
    if r is not None:
        return when(r['at']), '人寄給 %s 的信' % by
    return opened, '開單'


def lead_letter(t, sent, leads, tasks):
    """領隊開的單：落穿給這位領隊、開出這張單的那封人寫的 REQUEST（投遞紀錄）；不是領隊開的或找不到＝None。
    挑法見 task_start；aos-team mail --task 也用這一份（w2a，astra M11）。"""
    opened = task_open(t)
    by = t.get('opened_by')
    if opened is None or by not in leads:
        return None
    prev = [o for o in (task_open(x) for x in tasks.values()
                        if x is not t and x.get('opened_by') == by and not x.get('parent')) if o and o < opened]
    after = max(prev) if prev else None
    cands = [r for r in human_letters(sent) if r.get('to') == by and r.get('status') == 'REQUEST'
             and when(r['at']) <= opened and (after is None or when(r['at']) > after)]
    return max(cands, key=lambda r: when(r['at'])) if cands else None


def segments(t, states, hi=None):
    """history 裡停在 states 的每一段加總（秒）；還停在那裡＝算到 hi（沒 hi 不算）。"""
    total, cur, since = 0.0, None, None
    for i, h in enumerate(t['history']):
        if not isinstance(h, dict) or not isinstance(h.get('to'), str) or h['to'] == cur:
            continue
        at = history_at(t, i)
        if at is None:
            continue
        if since is not None:
            total += max(0.0, (at - since).total_seconds())
        cur = h['to']
        since = at if cur in states else None
    if since is not None and hi is not None and hi > since:
        total += (hi - since).total_seconds()
    return total


def done_when_count(t):
    """最後一次機械驗收＋最後一次審查：{"total", "checked", "passed"}。"""
    items = t.get('done_when') if isinstance(t.get('done_when'), list) else []
    checked = passed = 0
    for key, field in (('verify', 'results'), ('review', 'items')):
        runs = t.get(key) if isinstance(t.get(key), list) else []
        last = runs[-1] if runs and isinstance(runs[-1], dict) else None
        vals = (last or {}).get(field)
        for r in vals if isinstance(vals, list) else []:
            if not isinstance(r, dict):
                continue
            checked += 1
            ok = r.get('pass')
            passed += bool(ok) if ok is not None else r.get('result') == 'pass'
    return {'total': len(items), 'checked': checked, 'passed': passed}


def in_window(at, lo, hi):
    t = when(at)
    return t is not None and (lo is None or t >= lo) and (hi is None or t <= hi)


def fmt_secs(s):
    if s is None:
        return '?'
    s = int(round(s))
    if s < 60:
        return '%d 秒' % s
    if s < 3600:
        return '%d 分 %d 秒' % (s // 60, s % 60)
    return '%d 時 %d 分' % (s // 3600, s % 3600 // 60)
