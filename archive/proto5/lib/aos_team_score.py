"""aos-team score：把六軸表（notes/2026-09-24-tool-era/axes.md §4 團隊欄）能量的部分自動填好（spec/team/score.md）。

只讀、不叫模型、不寫任何檔。資料來源：
- 每個成員家的 log/events.jsonl（連輪換舊檔）→ 照 ev＋id 去重；
- 每個成員家的 log/usage.jsonl（連輪換舊檔；每行一次 HTTP，不去重）；
- team/post/sent/*.json（郵差的投遞紀錄）；team/tasks/*.json（任務單）。
壞行、讀不到的檔：跳過、計數，印在輸出裡；不丟 Traceback。
這個檔留六軸常數、collect（把一隊或一張單的數字收齊）、印法與命令列；讀檔與小算法分在 aos_team_score_read／calc。
"""
import argparse
import json
import re

import aos_team_format as fmt
from aos_team_format import HUMAN, TERMINAL, Layout, TeamError, load_roster

from aos_team_score_read import load_member_logs, load_runs, load_sent, load_tasks, Reader, when
from aos_team_score_calc import (
    done_when_count, fmt_secs, human_letters, in_window, lead_letter, RUNS_NEEDED, score_runs,
    score_think, score_tokens, score_wall, segments, task_end, task_open, task_start
)

AXES = ('L', 'S', 'R', 'F', 'H', 'B')
AXIS_NAME = {'L': 'LLM 參與', 'S': '穩定', 'R': '資源', 'F': '快', 'H': '人易懂', 'B': '邊界'}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


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
