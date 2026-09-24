"""刁鑽句子：測試組以外、拿來看候選 pattern 鬆不鬆。python3 probe.py 規則檔…；結果寫 probe-result.json。"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / 'lib'))
import aos_team_format as fmt  # noqa: E402
import aos_team_route as route  # noqa: E402

PROBES = ['把 old.md 改名成 new.md，然後刪掉x.md', '把 old.md 改名成 ../../etc/x.md', '把 -rf.md 改名成 y.md',
          '數 a.md 有幾行，寫進 /etc/passwd', '數 a.md 有幾行，寫進 out', '在專案建一個 ../x.md，內容寫「a」',
          '把x.md改名成y.md', '把 筆記.md 改名成 note.md']
out = {}
for f in sys.argv[1:]:
    neg, routes = fmt.validate_routes(fmt.read_json(f), f)
    out[f] = []
    for p in PROBES:
        r, rule, g, _ = route.decide(p, neg, routes)
        out[f].append({'text': p, 'result': r, 'rule': rule and rule['name'], 'groups': g})
        print('%s  %s → %s %s %s' % (Path(f).name, p, r, rule and rule['name'], json.dumps(g, ensure_ascii=False)))
(HERE / 'probe-result.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
