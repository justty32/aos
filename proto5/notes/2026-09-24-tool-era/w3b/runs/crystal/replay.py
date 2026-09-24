"""astra 審查（M2～M5、S3）改完之後重判，不再叫模型。

1. 把訓練結束時的狀態搬到一份拷貝（~/tmp/w3b-crystal/replay）：成員的家不抄，只抄 team.json、team/post/sent、team/tasks；
   route.log 用 out/route.log（訓練那 20 行，批准試驗之前存的），routes.json 用範例規則（批准之前的）。
2. 機械版照新的程式重跑一次 → out/mech.json（覆蓋，--force）、out/mech-report.json。
3. 模型版不重叫：把當初三次模型回的規則（out/llm-N-report.json 的 candidates；當初 4 條全收，等於模型原樣回的 4 條，
   名字去掉 llm- 前綴）用假的 ask 餵回去，經新的 screen 重篩 → out/llm-N-rescreen.json（有候選才有）與 -rescreen-report.json。
   token／秒照當初的紀錄（out/llm-N-time.json、report 的 usage）。
用法：python3 replay.py（之後 python3 eval.py …、python3 probe.py … 重判）
"""
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[4]
sys.path.insert(0, str(PROTO / 'lib'))
import aos_team_crystal as crystal  # noqa: E402

SRC = Path.home() / 'tmp' / 'w3b-crystal' / 'myteam'
DST = Path.home() / 'tmp' / 'w3b-crystal' / 'replay'
OUT = HERE / 'out'


def build():
    if DST.exists():
        shutil.rmtree(DST)
    (DST / 'team').mkdir(parents=True)
    shutil.copy(SRC / 'team.json', DST / 'team.json')
    for d in ('post/sent', 'tasks'):
        shutil.copytree(SRC / 'team' / d, DST / 'team' / d)
    shutil.copy(OUT / 'route.log', DST / 'team' / 'route.log')
    shutil.copy(PROTO / 'spec' / 'team' / 'examples' / 'routes.json', DST / 'team' / 'routes.json')


def fake(rules):
    def ask(system, user, alias=None, **kw):
        return {'text': json.dumps({'routes': rules}, ensure_ascii=False), 'usage': None, 'ms': 0,
                'alias': alias or 'default', 'model': 'replay（不叫模型）'}
    return ask


def brief(res):
    return {'candidates': [c['rule']['name'] for c in res['candidates']], 'dropped': res['dropped'],
            'skipped': res['skipped'], 'proposal': res['proposal'],
            'confidence': sorted({f['confidence'] for f in res['fallthrough']})}


def main():
    build()
    summary = {}
    res = crystal.crystal(str(DST), out=str(OUT / 'mech.json'), force=True)
    (OUT / 'mech-report.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    summary['mech'] = brief(res)
    for i in (1, 2, 3):
        old = json.loads((OUT / ('llm-%d-report.json' % i)).read_text(encoding='utf-8'))
        rules = []
        for c in old['candidates']:
            r = dict(c['rule'])
            r['name'] = r['name'][4:] if r['name'].startswith('llm-') else r['name']
            rules.append(r)
        target = OUT / ('llm-%d-rescreen.json' % i)
        target.unlink(missing_ok=True)
        res = crystal.crystal(str(DST), out=str(target), use_llm=True, asker=fake(rules))
        res['llm'].update(usage=old['llm']['usage'], ms=old['llm']['ms'], model=old['llm']['model'],
                          note='重篩：模型回的規則取自當初那次，沒有重叫')
        (OUT / ('llm-%d-rescreen-report.json' % i)).write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n',
                                                               encoding='utf-8')
        summary['llm-%d' % i] = brief(res)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
