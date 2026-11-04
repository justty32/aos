"""T-crystal 真跑：測試組。拿規則檔（或沒有＝只有範例規則）用門房的 decide 判 sentences.json 的 test_pos／test_neg。

用法：python3 eval.py 規則檔 [規則檔…]    # 每個檔一列；檔名給 - ＝ spec/team/examples/routes.json（沒候選）
正例算「對」：判成 handoff，且命中的規則是對的那一型（規則的 tests.hit 多半是那一型的訓練句），填好的 goal 裡看得到句子的值。
負例算「誤觸」：判成 tool／handoff（沒落穿給領隊）。
"""
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
LIB = HERE.parents[4] / 'lib'
sys.path.insert(0, str(LIB))
import aos_team_format as fmt  # noqa: E402
import aos_team_route as route  # noqa: E402

TYPES = ('create', 'rename', 'count', 'delline')


def train_types(data):
    """訓練句照順序每 5 句一輪：create、rename、count、delline、雜。"""
    return {s: (TYPES[i % 5] if i % 5 < 4 else 'misc') for i, s in enumerate(data['train'])}


def rule_type(rule, ttypes):
    got = [ttypes[h] for h in rule['tests']['hit'] if h in ttypes]
    return max(set(got), key=got.count) if got else None


def evaluate(path, data):
    obj = fmt.read_json(path)
    neg, routes = fmt.validate_routes(obj, str(path))
    ttypes = train_types(data)
    rows, pos_ok, pos_n = [], 0, 0
    for typ, sents in data['test_pos'].items():
        for s in sents:
            pos_n += 1
            result, rule, groups, why = route.decide(s, neg, routes)
            ok = False
            if result == 'handoff' and rule_type(rule, ttypes) == typ:
                goal = route.fill(rule['handoff'], groups)['goal']
                ok = all(v in goal for v in groups.values())
            pos_ok += ok
            rows.append({'set': 'pos', 'type': typ, 'text': s, 'result': result,
                         'rule': rule['name'] if rule else None, 'why': why, 'ok': ok})
    mis = 0
    for s in data['test_neg']:
        result, rule, groups, why = route.decide(s, neg, routes)
        bad = result != 'lead'
        mis += bad
        rows.append({'set': 'neg', 'text': s, 'result': result, 'rule': rule['name'] if rule else None,
                     'why': why, 'misfire': bad})
    cands = (obj.get('_metainfo') or {}).get('crystal', {}).get('candidates', [])
    return {'file': str(path), 'candidates': cands, 'pos': '%d/%d' % (pos_ok, pos_n),
            'neg_misfire': '%d/%d' % (mis, len(data['test_neg'])), 'rows': rows}


def main():
    data = json.loads((HERE / 'sentences.json').read_text(encoding='utf-8'))
    out = []
    for a in sys.argv[1:]:
        path = HERE.parents[4] / 'spec' / 'team' / 'examples' / 'routes.json' if a == '-' else Path(a)
        if not path.exists():             # 那次沒有候選＝沒寫提案檔＝只有範例規則
            print('%s：沒有提案檔（沒有候選）' % a)
            path = HERE.parents[4] / 'spec' / 'team' / 'examples' / 'routes.json'
        res = evaluate(path, data)
        out.append(res)
        print('%s：候選 %d 條，正例 %s，負例誤觸 %s' % (a, len(res['candidates']), res['pos'], res['neg_misfire']))
        for r in res['rows']:
            if (r['set'] == 'pos' and not r['ok']) or (r['set'] == 'neg' and r['misfire']):
                print('   %s %s「%s」→ %s %s（%s）' % ('漏' if r['set'] == 'pos' else '誤', r.get('type', ''),
                                                r['text'], r['result'], r['rule'], r['why']))
    return out


if __name__ == '__main__':
    json.dump(main(), open(HERE / 'eval-result.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
