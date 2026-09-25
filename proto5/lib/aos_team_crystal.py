"""固化建議（spec/team/crystal.md，第三波 W3-2）：aos-team crystal。

讀 team/route.log＋任務表＋投遞紀錄，找「門房沒中、領隊每次都開同一種單」的句型，
機械地產 routes.json 的**候選**規則，寫成一份完整的規則檔提案給人批（不自動生效）：
  aos-team crystal [--min N] [--json] [--out FILE]
  aos-team crystal --suggest-with-llm [--model ALIAS]   # 改叫模型歸納一次，一樣機械檢查兜底、只寫提案
批法：aos-team route test --file 提案 → aos-team route save 提案。
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import sys
import time

import aos_team_format as fmt
from aos_team_format import HUMAN, Layout, TeamError
import aos_team_route as route

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


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


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


# ------------------------------------------------------------------ 候選 ----

def _templ(value, pairs):
    """把字串裡的具體值換成 {群組}（長的先換，免得短值吃掉長值的一段）。"""
    if isinstance(value, str):
        for name, val in sorted(pairs, key=lambda p: -len(p[1])):
            if re.fullmatch(r'[A-Za-z0-9_~./-]+', val):     # 檔名、數字：前後不能黏著英數（「1」不吃 worker-1 的 1）
                value = re.sub(r'(?<![A-Za-z0-9_./-])%s(?![A-Za-z0-9_-])' % re.escape(val), '{%s}' % name, value)
            else:
                value = value.replace(val, '{%s}' % name)
        return value
    if isinstance(value, list):
        return [_templ(v, pairs) for v in value]
    if isinstance(value, dict):
        return {k: _templ(v, pairs) for k, v in value.items()}
    return value


def _placeholders(value):
    return set(re.findall(r'\{(\w+)\}', json.dumps(value, ensure_ascii=False)))


def make_handoff(c, literal=False):
    """挑一張領隊開的單當範本，具體值換成 {群組}。挑法：goal 把每個空格的值都寫到的那幾句裡，值最長的那句
    （短的值像「1」比較容易撞到不相干的字）；都沒有＝goal 用人自己那句話（也換成 {群組}）。
    facts 不抄（那是領隊當時看到的專案狀態，換一句就不對了）。"""
    def ok(it):
        return all(v in (it['tickets'][0].get('goal') or '') for _, _, v in slot_names(it['text']))

    def score(it):
        vals = [len(v) for _, _, v in slot_names(it['text'])]
        return min(vals) if vals else 0
    good = [it for it in c['usable'] if ok(it)] if not literal else []
    item = max(good, key=score) if good else c['usable'][0]
    t = item['tickets'][0]
    pairs = [] if literal else [(n, v) for n, _, v in slot_names(item['text'])]
    goal = t.get('goal') if good or literal else item['text']
    h = {'assignee': t['assignee'], 'workflow': t.get('workflow') or '無', 'goal': _templ(goal, pairs),
         'done_when': _templ(t.get('done_when') or [], pairs)}
    if t.get('max_attempts'):
        h['max_attempts'] = t['max_attempts']
    return h


def _unique_name(base, taken):
    name, i = base, 1
    while name in taken:
        i += 1
        name = '%s-%d' % (base, i)
    taken.add(name)
    return name


def mechanical_candidates(cls, falls, min_count, taken):
    out, skipped = [], []
    others = [f['text'] for f in falls]
    for i, c in enumerate(cls, 1):
        if len(c['usable']) < min_count:
            if c['count'] >= min_count:
                skipped.append({'skeleton': c['skeleton'],
                                'why': '%d 句配信有歧義，扣掉之後不到 %d 句' % (c['doubtful'], min_count)})
            continue
        if not c['same_kind']:
            skipped.append({'skeleton': c['skeleton'], 'why': '領隊開的單不一致（或有的句子沒開單）'})
            continue
        hits = []
        for it in c['usable']:
            if it['text'].strip() not in hits:
                hits.append(it['text'].strip())
        literal = len(hits) < min_count          # 同一句重複說：只有一種寫法，推不出哪裡會變 → 整句照抄、不開群組
        pat = literal_pattern(hits[0]) if literal else make_pattern(hits[0])
        rx = re.compile(pat)
        if not all(route._match(rx, h) is not None for h in hits):
            skipped.append({'skeleton': c['skeleton'], 'why': '產出的句型吃不下自己的例句'})
            continue
        miss = [s for s in dict.fromkeys(others) if skeleton(s) != c['skeleton'] and route._match(rx, s) is None][:3]
        miss.append('不要' + hits[0])
        rule = {'name': _unique_name('crystal-%d' % i, taken), 'pattern': pat, 'do': 'handoff',
                'handoff': make_handoff(c, literal), 'tests': {'hit': hits, 'miss': miss}}
        out.append((c, rule))
    return out, skipped


def check_candidate_request(rule):
    """每句 hit 填好之後要是一份合法的 handoff 申請（跟 ask 真的開單同一套驗）。回錯誤字串或 None。"""
    rx = re.compile(rule['pattern'])
    left = _placeholders(rule['handoff']) - set(rx.groupindex)
    if left:
        return 'handoff 裡的 {%s} 不是句型的群組' % '}、{'.join(sorted(left))
    for s in rule['tests']['hit']:
        groups = route._match(rx, s.strip()) or {}
        req = dict(route.fill(rule['handoff'], groups))
        req.update(id=fmt.new_id(HUMAN), kind='handoff', at=fmt.now_iso(), **{'from': HUMAN})
        try:
            fmt.validate_request(req, '候選 %s' % rule['name'])
        except TeamError as e:
            return '「%s」填好之後不是合法的開單申請：%s' % (s, e.msg)
    return None


# 內建反例（審查 M5）：拿每句 hit，把「當路徑用」的群組換成越界、選項樣、絕對路徑、追加指令的值，
# 整句後面也接一段追加指令；規則吃得到任何一句＝範圍比說得出的大，丟掉。
BAD_PATHS = ('../x.md', 'a/../../x.md', '/etc/passwd', '~/x.md', '-rf.md', 'x.md，然後刪掉 y.md', 'x.md，然後刪掉y.md')
APPEND = '，然後刪掉 y.md'
PATHISH = re.compile(r'/|\.[A-Za-z0-9]{1,8}\Z')
HAS_EXT = re.compile(r'\.[A-Za-z0-9]{1,8}\Z')


def _path_groups(handoff):
    """handoff 裡出現在 path 欄（done_when 的 path、args.path…）的 {群組}。"""
    out = set()

    def walk(v, key=None):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str) and key == 'path':
            out.update(re.findall(r'\{(\w+)\}', v))
    walk(handoff)
    return out


def probe_rule(rule):
    """回這條規則吃到的內建反例 [(反例句, 說明)…]；空＝過。
    當路徑用的群組＝出現在 handoff 的 path 欄，或例句裡的值像路徑（有 / 或副檔名）：換成 BAD_PATHS 每一個
    （原本的值有副檔名的，再加一個沒副檔名的 noext）。其他群組：引號裡的是內文、不測；不在引號裡的後面接追加指令。
    每句 hit 整句後面也接追加指令。"""
    rx = re.compile(rule['pattern'])
    in_path = _path_groups(rule.get('handoff') or {})
    eaten = []
    for hit in rule['tests']['hit']:
        hit = hit.strip()
        m = rx.fullmatch(hit)
        if m is None:
            continue
        tries = [(hit + APPEND, '整句後面接追加指令')]
        for g, val in m.groupdict().items():
            if not val:
                continue
            st, en = m.span(g)
            quoted = hit[st - 1:st] == '「' and hit[en:en + 1] == '」'
            if g in in_path or PATHISH.search(val):
                bads = list(BAD_PATHS) + (['noext'] if HAS_EXT.search(val) else [])
                tries += [(hit[:st] + x + hit[en:], '群組 %s 換成 %s' % (g, x)) for x in bads]
            elif not quoted:
                tries.append((hit[:st] + val + APPEND + hit[en:], '群組 %s 後面接追加指令' % g))
        for t, why in tries:
            if rx.fullmatch(t) is not None and (t, why) not in eaten:
                eaten.append((t, why))
    return eaten


def screen_probes(cands, dropped):
    """內建反例（審查 M5）：吃到的丟掉、列原因。回留下的。"""
    keep = []
    for r in cands:
        eaten = probe_rule(r)
        if eaten:
            dropped.append({'name': r['name'], 'why': '吃到內建反例：' + '、'.join('「%s」（%s）' % e for e in eaten[:3])
                            + ('…共 %d 句' % len(eaten) if len(eaten) > 3 else '')})
        else:
            keep.append(r)
    return keep


def _with(base_obj, cands):
    obj = dict(base_obj)
    obj['routes'] = list(base_obj.get('routes', [])) + list(cands)
    return obj


def _failures(obj):
    """整份規則檔（現有＋候選）裡例句沒過的每一條：{名: [失敗…]}。"""
    neg, routes = fmt.validate_routes(obj, '提案')
    return {n: fails for n, ok, fails in route.run_tests(neg, routes) if not ok}


def assemble(base_obj, cands):
    """現有規則＋候選 → 提案。一條一條照順序加：加進去之後**整份**（現有規則也算）例句全過才收（審查 M3），
    不過的不寫進提案、列原因（兩條候選互相搶句子時，先來的留下）。現有規則本來就沒全過＝一條都不收。
    回 (提案, 被拿掉的)。"""
    base_bad = _failures(_with(base_obj, []))
    if base_bad:
        why = '現有 routes.json 的例句本來就沒全過（%s）；先修好（aos-team route test）' % '、'.join(sorted(base_bad))
        return _with(base_obj, []), [{'name': r['name'], 'why': why} for r in cands]
    kept, dropped = [], []
    for r in cands:
        fails = _failures(_with(base_obj, kept + [r]))
        if fails:
            why = fails.get(r['name']) or ['加了它之後 %s 的例句不過' % '、'.join(sorted(fails))]
            dropped.append({'name': r['name'], 'why': '例句沒全過：' + '；'.join(why)})
        else:
            kept.append(r)
    return _with(base_obj, kept), dropped


def backtest(obj, cand_names, rows, own):
    """每條候選拿 route.log 裡沒參與提案的舊句子跑 decide：列它新吃到的句子；別類的＝疑似誤觸。
    own[名]＝這條自己那幾類的骨架。回 {名: {'checked': n, 'eats': [...]}}。"""
    neg, routes = fmt.validate_routes(obj, '提案')
    rxs = {r['name']: rx for r, rx in routes}
    hits = {r['name']: set(s.strip() for s in r['tests']['hit']) for r, _ in routes}
    texts = list(dict.fromkeys(r['text'].strip() for r in rows))
    out = {}
    for name in cand_names:
        olds = [t for t in texts if t not in hits[name]]
        eats = []
        for t in olds:
            if route._match(rxs[name], t) is None:
                continue
            result, got, _, why = route.decide(t, neg, routes)
            prev = next((r for r in rows if r['text'].strip() == t), {})
            stolen = prev.get('result') in ('tool', 'handoff')      # 原本別條規則接住的，現在命中兩條、改落穿
            if not stolen and (got is None or got['name'] != name):
                continue                                            # 否定詞之類本來就落穿，不算它吃到
            eats.append({'text': t, 'decide': result, 'why': why, 'was': prev.get('result'),
                         'misfire': stolen or skeleton(t) not in own[name]})
        out[name] = {'checked': len(olds), 'eats': eats}
    return out


# ------------------------------------------------------------------ 模型版 ----

LLM_SYSTEM = """你幫一個「門房」寫規則。門房用正規式整句比對人說的一句話，命中就照規則直接開一張任務單給工人，不必叫領隊（模型）。
下面給你：現有規則、門房沒接住（落穿給領隊）的句子，以及領隊看了每句之後開的單。
請把「同一種句型、領隊每次開同一種單」的句子歸納成規則。只輸出 JSON：{"routes": [規則…]}，沒有就 {"routes": []}。
每條規則的格式：
{"name": "英文小寫短名", "pattern": "Python 正規式（整句 fullmatch），會變的部分用具名群組 (?P<名>…)",
 "do": "handoff",
 "handoff": {"assignee": "成員名", "workflow": "…", "goal": "…可以用 {群組名}…", "done_when": [...同領隊開的單的格式，可用 {群組名}...]},
 "tests": {"hit": ["會命中的句子…（放落穿過的原句）"], "miss": ["不該命中的句子…（至少一句）"]}}
規則：pattern 要夠緊，只吃這一種句型，不要吃到別種句子；群組的值不要能吞掉整句。句子出現少於 %d 次、或領隊開的單不一致的句型不要寫。"""


def llm_candidates(stats_falls, base_obj, min_count, model, asker=None):
    """叫模型一次。回 ([規則…], ask 的回傳, 錯誤或 None)。"""
    import aos_llm_ask
    items = []
    for f in stats_falls:
        if f['reason'] != 'nomatch':
            continue
        items.append({'text': f['text'], 'tickets': [{k: t.get(k) for k in ('assignee', 'workflow', 'goal', 'done_when')}
                                                     for t in f['tickets']]})
    user = json.dumps({'existing_routes': [{'name': r.get('name'), 'pattern': r.get('pattern')}
                                           for r in base_obj.get('routes', [])],
                       'fallthrough': items}, ensure_ascii=False, indent=1)
    ask = asker or aos_llm_ask.ask
    got = ask(LLM_SYSTEM % min_count, user, alias=model)
    try:
        val = aos_llm_ask.parse_json(got['text'])
    except Exception as e:
        return [], got, str(getattr(e, 'msg', e))
    rules = val.get('routes') if isinstance(val, dict) else val
    if not isinstance(rules, list):
        return [], got, '模型回的 JSON 沒有 routes 陣列'
    return rules, got, None


def screen_llm(rules, falls, cls, min_count, taken):
    """模型給的規則先過機械檢查。次數與單子一致性都從歷史算（審查 M4），不信模型給的 hit：
    它的 pattern 在 route.log 裡吃得到的「沒命中」落穿句（配信有歧義的不算）≥ min 句；有群組的要 ≥ min 種寫法；
    那些句子每句都對到單、單都是同一種，而且跟模型寫的 assignee、workflow 一樣。
    回 ([(規則, 自己那幾類骨架)…], [丟掉的…])。"""
    ok, dropped = [], []
    pool = [f for f in falls if f['reason'] == 'nomatch' and f['confidence'] != 'low']
    for i, r in enumerate(rules, 1):
        label = r.get('name') if isinstance(r, dict) else '#%d' % i
        if not isinstance(r, dict):
            dropped.append({'name': label, 'why': '不是物件'})
            continue
        if r.get('do') != 'handoff':
            dropped.append({'name': label, 'why': '只收 do=handoff（tool 會直接跑指令，模型提的不收）'})
            continue
        r = dict(r)
        r['name'] = _unique_name('llm-%s' % re.sub(r'[^A-Za-z0-9_-]', '', str(r.get('name') or i)) or 'llm-%d' % i, taken)
        try:
            _, compiled = fmt.validate_routes({'routes': [r]}, '模型規則 %s' % label)
        except TeamError as e:
            dropped.append({'name': r['name'], 'why': '形狀不對或編不過：%s' % e.msg})
            continue
        except (OverflowError, RecursionError, ValueError) as e:   # 例：a{99999999999999999999}（09-25 複審 M4）
            dropped.append({'name': r['name'], 'why': '正規式編不過：%s' % ' '.join(str(e).split())[:120]})
            continue
        rx = compiled[0][1]
        mine = [f for f in pool if route._match(rx, f['text'].strip()) is not None]
        distinct = set(f['text'].strip() for f in mine)
        if len(mine) < min_count:
            dropped.append({'name': r['name'],
                            'why': 'route.log 裡它吃得到的真落穿句只有 %d 句（要 ≥ %d）' % (len(mine), min_count)})
            continue
        if rx.groupindex and len(distinct) < min_count:
            dropped.append({'name': r['name'], 'why': '吃得到的只有 %d 種寫法，推不出群組' % len(distinct)})
            continue
        kinds = {json.dumps(f['tickets'][0]['kind'], ensure_ascii=False, sort_keys=True) if f['tickets'] else None
                 for f in mine}
        if None in kinds or len(kinds) != 1:
            dropped.append({'name': r['name'], 'why': '它吃得到的那些句子，領隊開的單不一致（或有的沒開單）'})
            continue
        kind = mine[0]['tickets'][0]['kind']
        h = r['handoff']
        if h.get('assignee') != kind['assignee'] or h.get('workflow') != kind['workflow']:
            dropped.append({'name': r['name'], 'why': '模型寫的負責人／工作流（%s／%s）跟領隊開的單（%s／%s）不一樣'
                            % (h.get('assignee'), h.get('workflow'), kind['assignee'], kind['workflow'])})
            continue
        err = check_candidate_request(r)
        if err:
            dropped.append({'name': r['name'], 'why': err})
            continue
        ok.append((r, {skeleton(f['text']) for f in mine}))
    return ok, dropped


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def out_path(lay, out, force=False):
    """提案寫到哪（審查 M2）：不准是正式的 team/routes.json（別名、符號連結、硬連結都算）；
    沒給＝team/crystal/proposal-<時間>-<奈秒>-<pid>.json（唯一）；給了而且已經在＝要 --force。"""
    if out is None:
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        out = lay.team / 'crystal' / ('proposal-%s-%09d-%d.json' % (stamp, time.time_ns() % 10 ** 9, os.getpid()))
    out = Path(os.path.abspath(out))
    if os.path.realpath(out) == os.path.realpath(lay.routes) or _same_file(out, lay.routes):
        raise TeamError('Refused', '--out %s 就是生效中的規則檔 %s；提案要另存，批准走 aos-team route save' % (out, lay.routes))
    if out.is_dir():
        raise TeamError('Usage', '--out %s 是資料夾，要給檔名' % out)
    if out.exists() and not force:
        raise TeamError('AlreadyExists', '%s 已經在，不覆蓋（換個檔名，或加 --force）' % out)
    return out


# ------------------------------------------------------------------ 主體 ----

def crystal(team_dir, min_count=2, out=None, use_llm=False, model=None, asker=None, force=False):
    lay, rows, stats, falls = collect(team_dir)
    out = out_path(lay, out, force)          # 先檢查，免得叫完模型才發現寫不了
    base_obj = fmt.read_json(lay.routes) if lay.routes.exists() else {}
    base_obj = dict(base_obj)
    base_obj.setdefault('_metainfo', {'_type': fmt.ROUTES_TYPE, '_version': 1})
    taken = {r.get('name') for r in base_obj.get('routes', [])}
    cls = classes(falls)
    res = {'stats': stats, 'fallthrough': falls, 'classes': cls, 'min': min_count,
           'source': 'llm' if use_llm else 'mechanical', 'candidates': [], 'skipped': [], 'dropped': [],
           'proposal': None, 'llm': None}
    if use_llm:
        rules, got, err = llm_candidates(falls, base_obj, min_count, model, asker)
        res['llm'] = {'usage': got.get('usage'), 'ms': got.get('ms'), 'alias': got.get('alias'),
                      'model': got.get('model'), 'error': err, 'raw_count': len(rules)}
        screened, res['dropped'] = screen_llm(rules, falls, cls, min_count, taken)
        own = {r['name']: sk for r, sk in screened}
        cands = [r for r, _ in screened]
    else:
        pairs, res['skipped'] = mechanical_candidates(cls, falls, min_count, taken)
        cands = []
        own = {}
        for c, r in pairs:
            err = check_candidate_request(r)
            if err:
                res['dropped'].append({'name': r['name'], 'why': err})
                continue
            cands.append(r)
            own[r['name']] = {c['skeleton']}
    cands = screen_probes(cands, res['dropped'])
    obj, dropped = assemble(base_obj, cands)
    res['dropped'] += dropped
    names = [r['name'] for r in obj['routes'] if r['name'] in own]
    bt = backtest(obj, names, rows, own) if names else {}
    if use_llm:                              # 模型版：回測誤觸別類的丟掉（再組一次）
        bad = [n for n in names if any(e['misfire'] for e in bt[n]['eats'])]
        if bad:
            for n in bad:
                res['dropped'].append({'name': n, 'why': '回測誤觸別類：' + '、'.join(
                    '「%s」' % e['text'] for e in bt[n]['eats'] if e['misfire'])})
            obj, more = assemble(base_obj, [r for r in obj['routes'] if r['name'] in names and r['name'] not in bad])
            res['dropped'] += more
            names = [r['name'] for r in obj['routes'] if r['name'] in own]
            bt = backtest(obj, names, rows, own) if names else {}
    for r in obj['routes']:
        if r['name'] in names:
            res['candidates'].append({'rule': r, 'backtest': bt[r['name']]})
    if names:
        meta = dict(obj.get('_metainfo') or {})
        meta['crystal'] = {'candidates': names, 'source': res['source'], 'made_at': fmt.now_iso(),
                           'note': '候選不會自動生效：aos-team route test --file 這個檔 → aos-team route save 這個檔'}
        obj['_metainfo'] = meta
        left = _failures(obj)                # 寫檔前整份再跑一次（審查 M3）
        if left:
            raise TeamError('RoutesFailed', '提案整份例句沒全過（%s），沒寫檔' % '、'.join(sorted(left)))
        out = out_path(lay, out, force)      # 叫模型那段時間裡可能有人建了同名檔
        out.parent.mkdir(parents=True, exist_ok=True)
        if force:
            fmt.write_json(out, obj, indent=2)
        elif not fmt.write_new(out, obj, indent=2):
            raise TeamError('AlreadyExists', '%s 已經在，不覆蓋（換個檔名，或加 --force）' % out)
        res['proposal'] = str(out)
    return res


def _cut(text, n=50):
    text = ' '.join(str(text or '').split())
    return text[:n] + ('…' if len(text) > n else '')


def render(res):
    s = res['stats']
    lines = ['route.log：%d 句%s' % (s['lines'], '（另有 %d 行讀不懂，略過）' % s['bad_lines'] if s['bad_lines'] else '')]
    if s['by_rule']:
        lines.append('命中規則：' + '、'.join('%s %d 次' % kv for kv in sorted(s['by_rule'].items())))
    ft = s['fallthrough']
    lines.append('落穿 %d 次：%s' % (sum(ft.values()), '、'.join('%s %d' % (label, ft.get(k, 0)) for k, label in REASONS)))
    lines.append('')
    lines.append('沒命中的句型（%d 類；只看「沒命中」的，否定詞、命中兩條的加規則也沒用）：' % len(res['classes']))
    for c in sorted(res['classes'], key=lambda c: -c['count']):
        mark = '  ← 領隊每次開同一種單' if c['same_kind'] and c['count'] >= 2 else ''
        lines.append('- %s  ×%d%s%s' % (c['skeleton'], c['count'], mark,
                                        '（其中 %d 句配信有歧義，不拿來產候選）' % c['doubtful'] if c['doubtful'] else ''))
        for it in c['items'][:3]:
            if it['tickets']:
                t = it['tickets'][0]
                k = t['kind']
                tk = '%s 開單給 %s，工作流 %s，驗收 %s：%s' % (t['id'], k['assignee'], k['workflow'],
                                                       '、'.join(k['done_when']) or '無', _cut(t['goal'], 40))
            else:
                tk = '沒對到領隊開的單' if it['letter'] else '對不上信（舊 log）'
            lines.append('    「%s」→ %s' % (_cut(it['text'], 40), tk))
        if len(c['items']) > 3:
            lines.append('    …另 %d 句' % (len(c['items']) - 3))
    lines.append('')
    if res['llm']:
        u = res['llm']
        lines.append('模型 %s（%s）：prompt %s、completion %s token，%s ms；回了 %d 條%s'
                     % (u['alias'], u['model'], (u['usage'] or {}).get('prompt_tokens', '?'),
                        (u['usage'] or {}).get('completion_tokens', '?'), u['ms'], u['raw_count'],
                        '；讀不懂：' + u['error'] if u['error'] else ''))
    for x in res['skipped']:
        lines.append('沒提：%s（%s）' % (x['skeleton'], x['why']))
    for x in res['dropped']:
        lines.append('丟掉：%s（%s）' % (x['name'], x['why']))
    if not res['candidates']:
        lines.append('沒有候選規則（出現 ≥ %d 次、領隊開的單一致的句型才會提）；沒寫提案檔。' % res['min'])
        return '\n'.join(lines)
    lines.append('候選規則 %d 條（%s；不會自動生效）：' % (len(res['candidates']),
                                             '模型歸納、機械檢查過' if res['source'] == 'llm' else '機械產生'))
    for c in res['candidates']:
        r, bt = c['rule'], c['backtest']
        lines.append('- %s：%s%s' % (r['name'], r['pattern'], '' if re.compile(r['pattern']).groupindex
                                      else '（整句照抄：只有同一句重複說，推不出哪裡會變）'))
        lines.append('    → 開單給 %s：%s' % (r['handoff']['assignee'], _cut(r['handoff']['goal'], 60)))
        lines.append('    例句 hit %d、miss %d，全過；回測 %d 句舊句子，新吃到 %d 句%s'
                     % (len(r['tests']['hit']), len(r['tests']['miss']), bt['checked'], len(bt['eats']),
                        '' if not bt['eats'] else '：' + '、'.join('「%s」%s' % (_cut(e['text'], 30),
                                                                     '（疑似誤觸）' if e['misfire'] else '')
                                                            for e in bt['eats'])))
    lines.append('')
    lines.append('提案（現有規則＋候選）：%s' % res['proposal'])
    lines.append('怎麼批：先看一眼，再')
    lines.append('  aos-team route test --file %s' % res['proposal'])
    lines.append('  aos-team route save %s' % res['proposal'])
    lines.append('不要的候選，從檔裡刪掉那條再批。')
    return '\n'.join(lines)


def cmd_crystal(team_dir, argv):
    ap = _Parser(prog='aos-team crystal',
                 description='固化建議：從 route.log＋領隊開的單找常落穿的句型，產候選規則提案（不自動生效）')
    ap.add_argument('--min', type=int, default=2, help='句型至少出現幾次才提候選（預設 2）')
    ap.add_argument('--json', action='store_true', help='印 JSON')
    ap.add_argument('--out', help='提案寫到哪（預設 team/crystal/proposal-<時間>-<奈秒>-<pid>.json；不准是 team/routes.json）')
    ap.add_argument('--force', action='store_true', help='--out 的檔已經在也覆蓋（team/routes.json 永遠不行）')
    ap.add_argument('--suggest-with-llm', action='store_true', help='改叫模型歸納一次（預設關；一樣機械檢查、只寫提案）')
    ap.add_argument('--model', help='模型代號（--suggest-with-llm 用；預設 default）')
    args = ap.parse_args(argv)
    if args.min < 1:
        raise TeamError('Usage', '--min 至少 1')
    if args.model and not args.suggest_with_llm:
        raise TeamError('Usage', '--model 要跟 --suggest-with-llm 一起用')
    lay = Layout(team_dir)
    if not lay.team.is_dir():
        raise TeamError('NotFound', '%s 不是團隊資料夾（沒有 team/）' % team_dir)
    from aos_agent_home import AgentError
    try:
        res = crystal(team_dir, args.min, args.out, args.suggest_with_llm, args.model, force=args.force)
    except AgentError as e:                  # 叫模型失敗（設定錯、端點不通、逾時）：照 aos-llm call 的代號
        raise TeamError(e.code, e.msg)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(render(res))
    return 0
