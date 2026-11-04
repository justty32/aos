"""`aos-team crystal` 的機械候選規則：照落穿句型生規則與開單內容、候選申請檢查、內建反例篩掉範圍太大的、組回規則檔並回測。"""
import json
import re

import aos_team_format as fmt
from aos_team_format import HUMAN, TeamError
import aos_team_route as route

from aos_team_crystal_stats import literal_pattern, make_pattern, skeleton, slot_names


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
