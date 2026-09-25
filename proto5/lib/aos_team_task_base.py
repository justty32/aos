"""任務單的底：常數、讀寫與列單、單子的文字（派工信、審查信、驗收結果）與信件效果（寄誰、通知誰）。"""
from aos_team_format import BEAT, HUMAN, POST, TASK_ID, TeamError, json_files, read_json, validate_ticket, write_json


JUDGE = 'judge'
DEFAULT_ATTEMPTS = 3
NO_FLOW = ('無', '-', 'none', '（無）')


# ------------------------------------------------------------------ 讀寫 ----

def load(lay, tid):
    if not isinstance(tid, str) or not TASK_ID.match(tid):
        raise TeamError('BadTask', '%r 不是任務單號' % (tid,))
    path = lay.task(tid)
    if not path.exists():
        raise TeamError('NoSuchTask', '沒有任務單 %s（%s）' % (tid, path))
    return validate_ticket(read_json(path), str(path))


def save(lay, ticket):
    write_json(lay.task(ticket['id']), ticket, indent=2)


def all_tickets(lay):
    """(單號排序) 全部任務單；壞檔略過（aos-team task ls 另外報）。"""
    out = []
    for p in json_files(lay.tasks):
        try:
            out.append(validate_ticket(read_json(p), str(p)))
        except TeamError:
            continue
    return out


def find_by_request(lay, request_id):
    for t in all_tickets(lay):
        if t.get('request') == request_id:
            return t
    return None


# ------------------------------------------------------------------ 文字 ----

def describe_item(it):
    kind = it['kind']
    if kind == 'file_exists':
        return '檔案在：%s' % it['path']
    if kind == 'table_filled':
        extra = {k: v for k, v in it.items() if k not in ('kind', 'path')}
        return '表格填滿：%s%s' % (it['path'], ' %s' % extra if extra else '')
    if kind == 'check':
        return '檢查器 %s%s' % (it['name'], ' %s' % it['args'] if it.get('args') else '')
    if kind == 'cmd_ok':
        return '指令退 0（驗收員在牢裡跑，專案唯讀）：%s%s' % (' '.join(it['run']),
                                                     '（%d 秒內）' % it['timeout_s'] if 'timeout_s' in it else '')
    return '（審查員判）%s' % it['text']


def render_handoff(t):
    """派給負責人的那封 REQUEST 的內文。"""
    reply = t['opened_by'] if t['opened_by'] not in (POST,) else HUMAN
    flow = t['workflow'].strip()
    lines = ['任務 %s（rev%d，第 %d/%d 次）：%s' % (t['id'], t['rev'], t['attempt'], t['max_attempts'], t['goal']),
             ] + (['這張單是心跳（定時器）照例行派的，不是人或領隊當下派的。'] if t['opened_by'] == BEAT else []) + [
             '沒有指定工作流，照目標與事實做' if flow in NO_FLOW else '照這份工作流做：%s' % flow,
             '事實：%s' % (t.get('facts') or '無')]
    lines.append('驗收（你回 DONE 之後驗收員自動逐條查；「檔案在」「含某段字」不用你先 read 確認，'
                 '有同名工具的檢查器（例如 wf_residue、wf_lint）可以先自己跑）：')
    lines += ['  %d. %s' % (i, describe_item(it)) for i, it in enumerate(t['done_when'])]
    lines.append('做完用 team_say 回 DONE 給 %s，reply_to "%s"、rev %d；卡住回 BLOCKED 說原因；'
                 '要人決定用 ask_human。回完這一輪就結束，不用等。' % (reply, t['id'], t['rev']))
    return '\n'.join(lines)


def render_review(sub, parent):
    """（09-24 W2C 修：條目保留父單原編號，不從 0 重編，task show／review_result 才對得起來）"""
    indices = sub['review_of']['indices']
    lines = ['審查單 %s：替 %s（rev%d，第 %d 次）判下面幾條（編號跟 %s 一致，不是從 0 數）；機械檢查已經過了。'
             % (sub['id'], parent['id'], sub['review_of']['rev'], sub['review_of']['attempt'], parent['id']),
             '任務目標：%s' % parent['goal']]
    if parent.get('facts'):
        lines.append('事實（開單人給的，例如改之前的原文）：%s' % parent['facts'])
    lines += ['  %d. %s' % (i, it['text']) for i, it in zip(indices, sub['done_when'])]
    example = indices[0] if indices else 0
    lines.append('用 review_result 逐條回：{"task": "%s", "items": [{"i": %d, "pass": true, "why": "一句理由"}, …]}；'
                 '每一條都要回。回完這一輪就結束。' % (sub['id'], example))
    return '\n'.join(lines)


def _results_text(results):
    """驗收或審查的逐條結果 → 給負責人看的幾行。results：[{i, pass|result, why|message}]。"""
    lines = []
    for r in results or []:
        ok = r.get('pass')
        if ok is None:
            ok = r.get('result') == 'pass'
        lines.append('  %s %s. %s' % ('過' if ok else '不過', r.get('i', '?'), r.get('why') or r.get('message') or ''))
    return '\n'.join(lines)


# ------------------------------------------------------------------ 效果 ----

def letter(to, status, t, text):
    return {'do': 'letter', 'to': to, 'status': status, 'reply_to': t['id'], 'rev': t['rev'], 'text': text}


def dispatch(t, text):
    """派給負責人的那封（開單、修正、改派）：多帶 dispatch，郵差投到／被收走時要原樣交回 letter_delivered／picked_up。"""
    e = letter(t['assignee'], 'REQUEST', t, text)
    e['dispatch'] = {'task': t['id'], 'rev': t['rev'], 'attempt': t['attempt']}
    return e


def _tell_human_for_beat(t, status, ev):
    """心跳派的例行單卡住：等的是人，但回報多半寄給 beat（只記不投）→ 補一封給人（原信就寄給人＝不重複）。"""
    if t['opened_by'] != BEAT or ev.get('to') == HUMAN:
        return []
    return [letter(HUMAN, status, t, '例行單 %s 的負責人 %s 回 %s，等你決定：%s'
                   % (t['id'], t['assignee'], status, ev.get('note') or ''))]


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _notify(t, status, text, skip=()):
    """通知開單人與人（去掉重複、去掉 skip 裡的）。"""
    out = []
    for who in (t['opened_by'], HUMAN):
        who = HUMAN if who == POST else who
        if who == BEAT:
            continue                      # 心跳自己看單子，不用寄給它
        if t['opened_by'] == BEAT and who == HUMAN and status == 'DONE':
            continue                      # 例行做完不吵人（2026-09-24 使用者裁）：只有失敗、逾時、檢查器壞才寄
        if who in skip or any(e['to'] == who for e in out):
            continue
        out.append(letter(who, status, t, text))
    return out
