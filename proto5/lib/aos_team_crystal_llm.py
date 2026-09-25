"""`aos-team crystal --suggest-with-llm`：叫模型提候選規則（預設關），回來的照機械規則再篩一次。"""
import json
import re

import aos_team_format as fmt
from aos_team_format import TeamError
import aos_team_route as route

from aos_team_crystal_stats import skeleton
from aos_team_crystal_rules import _unique_name, check_candidate_request


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
