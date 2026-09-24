"""aos-team score：把六軸表（notes/2026-09-24-tool-era/axes.md §4 團隊欄）能量的部分自動填好（spec/team/score.md）。

只讀、不叫模型、不寫任何檔。資料來源：
- 每個成員家的 log/events.jsonl（連輪換舊檔）→ 照 ev＋id 去重；
- 每個成員家的 log/usage.jsonl（連輪換舊檔；每行一次 HTTP，不去重）；
- team/post/sent/*.json（郵差的投遞紀錄）；team/tasks/*.json（任務單）。
壞行、讀不到的檔：跳過、計數，印在輸出裡；不丟 Traceback。
"""
import argparse
import datetime
import json
import re
from pathlib import Path

import aos_agent_events as events
import aos_team_format as fmt
from aos_team_format import HUMAN, TERMINAL, Layout, TeamError, load_roster

AXES = ('L', 'S', 'R', 'F', 'H', 'B')
AXIS_NAME = {'L': 'LLM 參與', 'S': '穩定', 'R': '資源', 'F': '快', 'H': '人易懂', 'B': '邊界'}
RUNS_NEEDED = 10


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


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


# ------------------------------------------------------------------ 讀檔 ----

def when(text):
    """ISO 時間 → 帶時區的 datetime（沒時區的當本機）；讀不懂＝None。"""
    t = fmt.parse_iso(text) if isinstance(text, str) else None
    if t is None:
        return None
    return t.astimezone() if t.tzinfo is None else t


class Reader:
    """讀檔、數跳過的行與檔。"""

    def __init__(self):
        self.bad_lines = 0
        self.bad_files = 0

    def jsonl(self, path):
        out = []
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        value = json.loads(line)
                    except ValueError:
                        self.bad_lines += 1
                        continue
                    if isinstance(value, dict) and when(value.get('at')) is not None:
                        out.append(value)
                    else:
                        self.bad_lines += 1
        except FileNotFoundError:
            pass
        except OSError:
            self.bad_files += 1
        return out

    def jsonl_all(self, path):
        """連輪換舊檔（<名>.1.jsonl …）一起讀，舊的在前。"""
        olds = [events.rotated(path, i) for i in range(1, 21) if events.rotated(path, i).exists()]   # 缺號也往下看
        return [row for p in reversed(olds) for row in self.jsonl(p)] + self.jsonl(path)

    def json_dir(self, folder):
        out = []
        try:
            paths = fmt.json_files(folder)
        except OSError:                                   # 資料夾讀不到（權限）：算一個跳過的檔
            self.bad_files += 1
            return out
        for path in paths:
            try:
                value = fmt.read_json(path)
            except TeamError:
                self.bad_files += 1
                continue
            if isinstance(value, dict):
                out.append(value)
            else:
                self.bad_files += 1
        return out


def load_member_logs(lay, names, rd):
    """回 ({名: [事件（去重後）]}, {名: [用量行]})。"""
    evs, use = {}, {}
    for name in names:
        home = lay.member(name)
        rows = rd.jsonl_all(home / events.EVENTS)
        good = [r for r in rows if isinstance(r.get('ev'), str) and (r.get('id') is None or isinstance(r.get('id'), str))]
        rd.bad_lines += len(rows) - len(good)             # ev 不是字串、id 不是字串或 null：壞行（去重要拿 id 當鍵）
        evs[name] = events.dedupe(good)
        use[name] = rd.jsonl_all(home / events.USAGE)
    return evs, use


def load_tasks(lay, rd):
    out = {}
    for t in rd.json_dir(lay.tasks):
        tid = t.get('id')
        if isinstance(tid, str) and fmt.TASK_ID.match(tid) and isinstance(t.get('history'), list):
            out[tid] = t
        else:
            rd.bad_files += 1
    return out


def load_sent(lay, rd):
    return [r for r in rd.json_dir(lay.post_sent) if isinstance(r.get('id'), str)]


def load_runs(path, rd):
    """--runs：JSON 陣列，或一行一個 JSON（jsonl）。每筆 {"ok": true/false, …} 或直接 true/false。回 (過, 總)。"""
    try:
        raw = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        raise TeamError('NotFound', '--runs 的檔 %s 不存在' % path)
    except (OSError, UnicodeError) as e:
        raise TeamError('ReadFailed', '讀不到 --runs 的檔 %s：%s' % (path, e))
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            items = [items]
    except ValueError:
        items = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except ValueError:
                rd.bad_lines += 1
    ok = total = 0
    for it in items:
        v = it.get('ok') if isinstance(it, dict) else it
        if isinstance(v, bool):
            total += 1
            ok += v
        else:
            rd.bad_lines += 1
    return ok, total


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
    if by in leads:
        prev = [o for o in (task_open(x) for x in tasks.values()
                            if x is not t and x.get('opened_by') == by and not x.get('parent')) if o and o < opened]
        after = max(prev) if prev else None
        cands = [when(r['at']) for r in human_letters(sent) if r.get('to') == by and r.get('status') == 'REQUEST'
                 and when(r['at']) <= opened and (after is None or when(r['at']) > after)]
        if cands:
            return max(cands), '人寄給 %s 的信' % by
    return opened, '開單'


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


def collect(team_dir, tid=None, runs_file=None):
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    names = list(roster['members'])
    leads = fmt.members_by_template(roster, 'lead')
    rd = Reader()
    evs, use = load_member_logs(lay, names, rd)
    tasks = load_tasks(lay, rd)
    sent = load_sent(lay, rd)
    runs = load_runs(runs_file, rd) if runs_file else None

    # ---- 範圍與時間窗
    if tid:
        if tid not in tasks:
            raise TeamError('NotFound', '找不到任務單 %s（team/tasks/%s.json 不在或壞了）' % (tid, tid))
        scope_tasks = [tasks[k] for k in sorted(tasks) if k == tid or re.fullmatch(re.escape(tid) + r'\.r[0-9]+', k)]
        main = [tasks[tid]]
        lo, start_from = task_start(tasks[tid], sent, leads, tasks)
        hi = task_end(tasks[tid])
    else:
        scope_tasks = [tasks[k] for k in sorted(tasks)]
        main = [t for t in scope_tasks if not t.get('parent')]
        starts = [s for s in [when(r['at']) for r in human_letters(sent)] + [task_open(t) for t in scope_tasks] if s]
        lo = min(starts) if starts else None
        start_from = '最早一封人信或最早開單' if starts else '沒有信也沒有單'
        ends = [task_end(t) for t in main]
        hi = max(ends) if main and all(ends) else None
    unfinished = [t['id'] for t in main if t.get('status') not in TERMINAL]
    # 事件與用量：沒給 --task＝全部；給了＝時間窗內（單子還沒結束＝到現在）
    wlo, whi = (lo, hi) if tid else (None, None)

    # ---- L
    think_by, think_fail, think_ms, think_ms_missing, act_ms = {}, 0, 0, 0, 0
    for name in names:
        n = 0
        for e in evs[name]:
            if not in_window(e.get('at'), wlo, whi):
                continue
            if e['ev'] == 'think_end':
                n += 1
                think_fail += e.get('ok') is False
                if isinstance(e.get('ms'), (int, float)):
                    think_ms += e['ms']
                else:
                    think_ms_missing += 1
            elif e['ev'] == 'act_end':
                for c in e.get('calls') or []:
                    if isinstance(c, dict) and isinstance(c.get('ms'), (int, float)):
                        act_ms += c['ms']
        think_by[name] = n
    think = sum(think_by.values())
    lead_part = '、'.join('%s（領隊）%d' % (n, think_by[n]) for n in leads)
    others = '、'.join('%s %d' % (n, think_by[n]) for n in names if n not in leads)
    L = {'score': score_think(think), 'think': think, 'failed': think_fail, 'by_member': think_by,
         'model_steps': None,
         'why': 'think %d 次（含失敗 %d 次）：%s' % (think, think_fail, '、'.join(x for x in (lead_part, others) if x))}

    # ---- S
    if tid:
        st = tasks[tid].get('status')
        this = 'ok' if st == 'done' else 'fail' if st in TERMINAL else 'unfinished'
    else:
        sts = [t.get('status') for t in main]
        this = ('none' if not sts else 'ok' if all(s == 'done' for s in sts)
                else 'fail' if any(s in ('failed', 'cancelled') for s in sts) else 'unfinished')
    this_word = {'ok': '這次成了', 'fail': '這次沒成', 'unfinished': '這次還沒結束', 'none': '沒有單子'}[this]
    if runs is None:
        ok, total = (1, 1) if this == 'ok' else (0, 1) if this == 'fail' else (0, 0)
        S = {'score': None, 'this_run': this, 'runs': None,
             'why': '%s；%d/%d 次過，跑不到 %d 次不給分（用 --runs 給多次結果）' % (this_word, ok, total, RUNS_NEEDED)}
    else:
        ok, total = runs
        sc = score_runs(ok, total)
        why = '%d/%d 次過' % (ok, total)
        if sc is None:
            why += '，跑不到 %d 次不給分' % RUNS_NEEDED
        elif sc == 4:
            why += '；5 分要崩潰恢復測試，團隊層這裡只給 4'
        S = {'score': sc, 'this_run': this, 'runs': {'ok': ok, 'total': total}, 'why': why}

    # ---- R
    tok_by, no_usage, rows = {}, 0, 0
    for name in names:
        n = 0
        for u in use[name]:
            if not in_window(u.get('at'), wlo, whi):
                continue
            rows += 1
            got = u.get('usage') if isinstance(u.get('usage'), dict) else {}
            if isinstance(got.get('total_tokens'), int):
                n += got['total_tokens']
            else:
                no_usage += 1
        tok_by[name] = n
    tokens = sum(tok_by.values())
    if think and not rows:
        r_score, r_why = None, '有 think %d 次但沒有用量紀錄（usage.jsonl），token 量不到' % think
    else:
        r_score = score_tokens(tokens)
        r_why = 'token %s（%s）' % ('{:,}'.format(tokens), '、'.join('%s %s' % (n, '{:,}'.format(tok_by[n]))
                                                                     for n in names))
        if no_usage:
            r_why += '；%d 次呼叫端點沒回用量，沒算進去' % no_usage
    R = {'score': r_score, 'tokens': tokens, 'by_member': tok_by, 'calls': rows, 'no_usage': no_usage,
         'cpu_s': None, 'mem_mb': None, 'why': r_why + '；cpu 秒、記憶體另量（這裡是 null，不算）'}

    # ---- F
    wall = (hi - lo).total_seconds() if lo and hi else None
    parts = {'model_s': think_ms / 1000.0, 'tools_s': act_ms / 1000.0,
             'pickup_s': sum(segments(t, ('sent',), hi) for t in scope_tasks),
             'verify_s': sum(segments(t, ('verifying',), hi) for t in scope_tasks),
             'human_s': sum(segments(t, ('waiting_user',), hi) for t in scope_tasks)}
    parts['other_s'] = max(0.0, wall - sum(parts.values())) if wall is not None else None
    if wall is None:
        f_why = ('還沒結束（%s）' % '、'.join(unfinished) if unfinished
                 else '找不到起點或終點（%s）' % start_from)
    else:
        f_why = '%s（起點：%s %s；終點：單子結束 %s）' % (fmt_secs(wall), start_from, lo.isoformat(timespec='seconds'),
                                                    hi.isoformat(timespec='seconds'))
    F = {'score': score_wall(wall) if wall is not None else None, 'wall_s': wall,
         'start': lo.isoformat() if lo else None, 'end': hi.isoformat() if hi else None, 'start_from': start_from,
         'parts': parts, 'think_ms_missing': think_ms_missing, 'why': f_why}

    blank = {'score': None, 'why': '給人填'}
    axes = {'L': L, 'S': S, 'R': R, 'F': F, 'H': dict(blank), 'B': dict(blank)}

    # ---- 單子、信
    task_rows = []
    for t in scope_tasks:
        s, e = task_open(t), task_end(t)
        task_rows.append({'id': t['id'], 'status': t.get('status'), 'assignee': t.get('assignee'),
                          'rev': t.get('rev'), 'attempt': t.get('attempt'), 'max_attempts': t.get('max_attempts'),
                          'done_when': done_when_count(t),
                          'opened_at': s.isoformat() if s else None, 'ended_at': e.isoformat() if e else None})
    by_sender, rejected = {}, 0
    scope_ids = {t['id'] for t in scope_tasks}
    for r in sent:
        # 郵差在單子結束那一刻寄的終局通知（完成、失敗）常記在結束之後一點點：算這張單的；其他信照時間窗（score.md）
        mine = (r.get('from') == 'post' and r.get('status') in ('DONE', 'FAILED')
                and str(r.get('reply_to') or '').split('.r')[0] in scope_ids)
        if not mine and not in_window(r.get('at') or r.get('recorded_at'), wlo, whi):
            continue
        if r.get('kind') == 'letter':
            k = str(r.get('from'))
            by_sender[k] = by_sender.get(k, 0) + 1
        elif r.get('kind') == 'rejected':
            rejected += 1
    letters = {'total': sum(by_sender.values()), 'by_sender': dict(sorted(by_sender.items())), 'rejected': rejected}

    scope_word = tid or '整支團隊'
    bits = [scope_word, this_word, '問模型 %d 次' % think]
    bits.append('用了 %s token' % '{:,}'.format(tokens) if r_score is not None else 'token 量不到')
    bits.append('牆上 %s' % fmt_secs(wall) if wall is not None else '牆上時間量不到')
    summary = '，'.join(bits) + '。'
    return {'scope': 'task' if tid else 'team', 'task': tid, 'summary': summary, 'axes': axes,
            'tasks': task_rows, 'letters': letters,
            'skipped': {'lines': rd.bad_lines, 'files': rd.bad_files}}


# ------------------------------------------------------------------ 印 ----

def render(res):
    ax = res['axes']
    out = [res['summary'], '', '| 軸 | 分 | 依據 |', '|---|---|---|']
    for k in AXES:
        a = ax[k]
        out.append('| %s %s | %s | %s |' % (k, AXIS_NAME[k], '—' if a['score'] is None else a['score'], a['why']))
    p = ax['F']['parts']
    out += ['', '時間花在哪（秒，各自加總，會重疊；其他＝牆上時間減掉前面的，不到 0 算 0）：',
            '  等模型 %.1f、跑工具 %.1f、等收件 %.1f、等驗收 %.1f、等人 %.1f、排隊與郵差（其他）%s'
            % (p['model_s'], p['tools_s'], p['pickup_s'], p['verify_s'], p['human_s'],
               '?' if p['other_s'] is None else '%.1f' % p['other_s'])]
    if ax['F']['think_ms_missing']:
        out.append('  （有 %d 次 think 沒記 ms，等模型少算了）' % ax['F']['think_ms_missing'])
    out += ['', '單子：']
    if not res['tasks']:
        out.append('  （沒有）')
    for t in res['tasks']:
        d = t['done_when']
        out.append('  %s  %s  %s  rev%s 第%s/%s次  Done when %d 條，最後一次驗過 %d 條、過 %d 條'
                   % (t['id'], t['status'], t['assignee'], t['rev'], t['attempt'], t['max_attempts'],
                      d['total'], d['checked'], d['passed']))
    lt = res['letters']
    senders = '、'.join('%s %d' % ('人' if k == HUMAN else k, v) for k, v in lt['by_sender'].items())
    out += ['', '信：共 %d 封%s%s' % (lt['total'], '（%s）' % senders if senders else '',
                                     '；退件 %d' % lt['rejected'] if lt['rejected'] else '')]
    sk = res['skipped']
    if sk['lines'] or sk['files']:
        out.append('跳過 %d 行、%d 個檔（壞掉或讀不到）' % (sk['lines'], sk['files']))
    return '\n'.join(out)


def cmd_score(team_dir, argv):
    p = _Parser(prog='aos-team score', description='六軸能量的部分自動彙整（只讀、不叫模型）')
    p.add_argument('--task', help='只看這張單（含審查子單）從開單到結束；沒給＝整支團隊')
    p.add_argument('--runs', help='多次結果的檔（JSON 陣列或 jsonl，每筆 {"ok": true/false}），給穩定軸用')
    p.add_argument('--json', action='store_true', help='印一個 JSON 物件')
    args = p.parse_args(argv)
    if args.task and not fmt.TASK_ID.match(args.task):
        raise TeamError('Usage', '--task 要像 t-0001（收到 %r）' % args.task)
    if not Layout(team_dir).root.is_dir():
        raise TeamError('NotFound', '團隊資料夾 %s 不在' % team_dir)
    res = collect(team_dir, args.task, args.runs)
    print(json.dumps(res, ensure_ascii=False) if args.json else render(res))
    return 0
