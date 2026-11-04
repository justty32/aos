"""`aos-team crystal` 的句型與統計：句子→空格骨架與正規式、讀門房 log 與信、對上任務單、落穿句型歸類計數。"""
import json
from pathlib import Path
import re

import aos_team_format as fmt
from aos_team_format import Layout, TeamError


REASONS = (('nomatch', '沒命中'), ('multi', '命中兩條以上'), ('negation', '含否定詞'), ('nolead', '沒領隊'))
MATCH_SECONDS = 120          # 舊 log 沒 letter 格：信的 at 跟 log 的 at 差多少秒內算同一句

# 句型的「空格」（佔位）：先引號內文、再檔名、再路徑、再數字。只抓 ASCII 的檔名與路徑（中文句子沒有空白分字）。
SLOT_RX = re.compile(
    r'「(?P<q>[^」]+)」'
    r'|(?P<f>(?<![A-Za-z0-9_~./-])[A-Za-z0-9_~./][A-Za-z0-9_~./-]*\.[A-Za-z0-9]{1,8}(?![A-Za-z0-9_./-]))'
    r'|(?P<p>(?<![A-Za-z0-9_~./-])[A-Za-z0-9_~.-]*(?:/[A-Za-z0-9_~.-]+)+/?(?![A-Za-z0-9_./-]))'
    r'|(?P<n>(?<![A-Za-z0-9_.])[0-9]+(?![A-Za-z0-9_.]))')
# 候選規則裡的群組只收「專案裡的相對路徑」：每一段都以英數或底線開頭——擋掉 /開頭、~、-開頭（像選項）、..（第三波 W3-2）。
# 歸類（TOKEN）照舊認得寬的寫法，這樣 ../x.md 仍歸進同一類，只是候選不會吃它、照樣落穿給領隊。
SEG = '[A-Za-z0-9_][A-Za-z0-9_.-]*'
SLOT_PATTERN = {'q': '[^」]+', 'f': '(?:%s/)*%s\\.[A-Za-z0-9]{1,8}' % (SEG, SEG),
                'p': '%s(?:/%s)+/?' % (SEG, SEG), 'n': '[0-9]+'}
SLOT_LABEL = {'q': '引號內文', 'f': '檔名', 'p': '路徑', 'n': '數字'}


# ------------------------------------------------------------------ 句型 ----

def tokens(text):
    """一句話 → [('lit', 字) | ('slot', 種類, 值)…]。"""
    out, pos = [], 0
    for m in SLOT_RX.finditer(text):
        if m.start() > pos:
            out.append(('lit', text[pos:m.start()]))
        kind = m.lastgroup
        if kind == 'q':
            out += [('lit', '「'), ('slot', 'q', m.group('q')), ('lit', '」')]
        else:
            out.append(('slot', kind, m.group(kind)))
        pos = m.end()
    if pos < len(text):
        out.append(('lit', text[pos:]))
    return out


def skeleton(text):
    """句型骨架：空格換成 {檔名} 這種佔位、拿掉所有空白。同一個骨架＝同一類。"""
    return ''.join(re.sub(r'\s+', '', t[1]) if t[0] == 'lit' else '{%s}' % SLOT_LABEL[t[1]] for t in tokens(text))


def slot_names(text):
    """每個空格的群組名（種類＋第幾個：f1、f2、q1、n1）與值，照出現順序。"""
    seen, out = {}, []
    for t in tokens(text):
        if t[0] == 'slot':
            seen[t[1]] = seen.get(t[1], 0) + 1
            out.append(('%s%d' % (t[1], seen[t[1]]), t[1], t[2]))
    return out


def make_pattern(text):
    """從一句例句產整句正規式：字面照抄（空白可有可無）、空格換成具名群組。"""
    parts, seen = [], {}
    for t in tokens(text):
        if t[0] == 'lit':
            lit = t[1].strip()
            if lit:
                parts.append('\\s*'.join(re.escape(w) for w in lit.split()))
        else:
            seen[t[1]] = seen.get(t[1], 0) + 1
            parts.append('(?P<%s%d>%s)' % (t[1], seen[t[1]], SLOT_PATTERN[t[1]]))
    return '\\s*'.join(parts)


def literal_pattern(text):
    """整句照抄（空白可有可無），沒有群組。"""
    return '\\s*'.join(re.escape(w) for w in text.split())


# ------------------------------------------------------------------ 讀檔 ----

def _jsonl(path):
    rows, bad = [], 0
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return [], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(obj, dict) and isinstance(obj.get('text'), str) and isinstance(obj.get('result'), str):
            rows.append(obj)
        else:
            bad += 1
    return rows, bad


def reason_of(row):
    if row['result'] == 'none':
        return 'nolead'
    why = str(row.get('why') or '')
    if why.startswith('含否定詞'):
        return 'negation'
    if why.startswith('命中兩條'):
        return 'multi'
    return 'nomatch'


def ticket_kind(t):
    """「同一種單」的比法：負責人＋工作流＋驗收條目的種類（check 帶名字），不比 goal 字面（模型每次寫法不同）。"""
    items = []
    for it in t.get('done_when') or []:
        if isinstance(it, dict):
            items.append(it.get('kind') + (':' + str(it.get('name')) if it.get('kind') == 'check' else ''))
    return {'assignee': t.get('assignee'), 'workflow': t.get('workflow'), 'done_when': sorted(items)}


def _picked(r):
    import aos_team_score
    return aos_team_score.when(r.get('picked_up_at'))


def link_letters(lay, rows):
    """每一行落穿的 log → 那封信的 id（有 letter 格直接用；沒有就用原文＋時間對投遞紀錄）；
    再用 aos-team score 的 lead_letter 反查每張領隊開的單是哪封信開出來的。
    有歧義的記下來（審查 S3，這些不拿來產候選）：
    - 舊 log 配信：時間窗內同文的信不只一封；
    - 信 → 單：這張單的時間窗裡還有別封人寫給這位領隊的信，而且那封在被選中的這封寄出時還沒被收走（排在一起）。
    回 (sent, {信 id: [單…]}, {信 id: 歧義說明})。"""
    import aos_team_post
    import aos_team_score
    import aos_team_task
    sent = aos_team_post.load_records(lay)
    try:
        leads = fmt.members_by_template(fmt.load_roster(lay.root), 'lead')
    except TeamError:
        leads = []
    tasks = {t['id']: t for t in aos_team_task.all_tickets(lay)}
    human = [r for r in aos_team_score.human_letters(sent) if r.get('status') == 'REQUEST' and r.get('to') in leads]
    by_letter, unsure = {}, {}
    for t in tasks.values():
        if t.get('parent'):
            continue
        ltr = aos_team_score.lead_letter(t, sent, leads, tasks)
        if ltr is None:
            continue
        by_letter.setdefault(ltr['id'], []).append(t)
        opened, by = aos_team_score.task_open(t), t.get('opened_by')
        prev = [o for o in (aos_team_score.task_open(x) for x in tasks.values()
                            if x is not t and x.get('opened_by') == by and not x.get('parent')) if o and o < opened]
        after = max(prev) if prev else None
        chosen_at = aos_team_score.when(ltr['at'])
        for r in human:
            at = aos_team_score.when(r['at'])
            if r['id'] == ltr['id'] or r.get('to') != by or at > opened or (after is not None and at <= after):
                continue
            if _picked(r) is None or _picked(r) >= chosen_at:
                unsure[ltr['id']] = '開 %s 之前領隊手上同時有別封信（%s），分不清是哪封開的單' % (t['id'], r['id'])
    used = set(r['letter'] for r in rows if isinstance(r.get('letter'), str))
    for row in rows:
        if row['result'] != 'lead' or isinstance(row.get('letter'), str):
            continue
        at = aos_team_score.when(row.get('at'))
        near = []
        for r in human:
            if r['id'] in used or r.get('text') != row['text'] or at is None:
                continue
            gap = abs((aos_team_score.when(r['at']) - at).total_seconds())
            if gap <= MATCH_SECONDS:
                near.append((gap, r['id']))
        if len(near) == 1:
            row['_letter'] = near[0][1]
            used.add(near[0][1])
        elif near:
            row['_ambiguous'] = '舊 log 沒有 letter 格，%d 秒內同文的信有 %d 封，配不準' % (MATCH_SECONDS, len(near))
    return sent, by_letter, unsure


# ------------------------------------------------------------------ 統計 ----

def collect(team_dir):
    lay = Layout(team_dir)
    rows, bad = _jsonl(lay.route_log)
    sent, by_letter, unsure = link_letters(lay, rows)
    stats = {'lines': len(rows), 'bad_lines': bad, 'by_result': {}, 'by_rule': {}, 'fallthrough': {}}
    falls = []
    for row in rows:
        stats['by_result'][row['result']] = stats['by_result'].get(row['result'], 0) + 1
        if row['result'] in ('tool', 'handoff') and row.get('route'):
            stats['by_rule'][row['route']] = stats['by_rule'].get(row['route'], 0) + 1
        if row['result'] in ('lead', 'none'):
            why = reason_of(row)
            stats['fallthrough'][why] = stats['fallthrough'].get(why, 0) + 1
            letter = row.get('letter') if isinstance(row.get('letter'), str) else row.get('_letter')
            tickets = by_letter.get(letter, []) if letter else []
            linked = 'log' if isinstance(row.get('letter'), str) else ('matched' if letter else None)
            doubt = row.get('_ambiguous') or (unsure.get(letter) if letter else None)
            falls.append({'at': row.get('at'), 'text': row['text'], 'reason': why, 'letter': letter, 'linked': linked,
                          # 可信度（審查 S3）：high＝log 有 letter 格；medium＝舊 log 靠原文＋時間配到唯一一封；
                          # low＝有歧義（不拿來產候選）；none＝對不上信
                          'confidence': 'low' if doubt else {'log': 'high', 'matched': 'medium'}.get(linked, 'none'),
                          'doubt': doubt,
                          'tickets': [{'id': t['id'], 'assignee': t.get('assignee'), 'workflow': t.get('workflow'),
                                       'goal': t.get('goal'), 'facts': t.get('facts'),
                                       'done_when': t.get('done_when'), 'max_attempts': t.get('max_attempts'),
                                       'kind': ticket_kind(t)} for t in sorted(tickets, key=lambda x: x['id'])]})
    return lay, rows, stats, falls


def classes(falls):
    """只拿「沒命中」的落穿歸類（否定、命中兩條的，加規則也不會變；沒領隊的沒單）。照第一次出現排。"""
    out = {}
    for f in falls:
        if f['reason'] != 'nomatch':
            continue
        key = skeleton(f['text'])
        c = out.setdefault(key, {'skeleton': key, 'items': []})
        c['items'].append(f)
    for c in out.values():
        c['usable'] = [x for x in c['items'] if x['confidence'] != 'low']     # 配信有歧義的只列、不拿來產候選
        kinds = [json.dumps(x['tickets'][0]['kind'], ensure_ascii=False, sort_keys=True) if x['tickets'] else None
                 for x in c['usable']]
        c['count'] = len(c['items'])
        c['doubtful'] = len(c['items']) - len(c['usable'])
        c['with_ticket'] = sum(1 for k in kinds if k)
        c['same_kind'] = bool(kinds) and all(kinds) and len(set(kinds)) == 1
    return list(out.values())
