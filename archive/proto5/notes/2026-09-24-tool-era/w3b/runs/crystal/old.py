"""把前兩波真跑的 route.log（只讀）餵給 aos-team crystal：每個團隊各跑一次，再把五隊合成一個假團隊跑一次。
合併：route.log 接起來、投遞紀錄照抄（id 本來就不撞）、任務單重新編號（t-0001 起）、名冊用各隊成員聯集。
用法：python3 old.py [輸出資料夾，預設 ~/tmp/w3b-crystal/old-merged]；結果印 JSON（也寫 old-result.json）。
"""
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / 'lib'))
import aos_team_crystal as crystal  # noqa: E402
import aos_team_format as fmt  # noqa: E402

TEAMS = [Path.home() / 'tmp' / x for x in ('t5-play/myteam', 't5-tut/myteam', 'wf-try/team', 'w2a-try/team',
                                           'wf-try-b/team')]


def brief(res):
    return {'lines': res['stats']['lines'], 'by_result': res['stats']['by_result'],
            'fallthrough': res['stats']['fallthrough'],
            'classes': [{'skeleton': c['skeleton'], 'count': c['count'], 'with_ticket': c['with_ticket'],
                         'same_kind': c['same_kind']} for c in res['classes']],
            'linked': [f['linked'] for f in res['fallthrough']],
            'confidence': [f['confidence'] for f in res['fallthrough']],
            'candidates': [c['rule']['name'] for c in res['candidates']], 'skipped': res['skipped'],
            'dropped': res['dropped']}


def main():
    merged = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / 'tmp' / 'w3b-crystal' / 'old-merged')
    out = {'per_team': {}, 'merged': None}
    for t in TEAMS:
        res = crystal.crystal(str(t), out=str(merged.parent / 'old-proposal-should-not-exist.json'))
        out['per_team'][str(t)] = brief(res)
    if merged.exists():
        shutil.rmtree(merged)
    lay = fmt.Layout(merged)
    members = {}
    for t in TEAMS:
        members.update(fmt.read_json(t / 'team.json')['members'])
    roster = {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': '../p', 'members': members}
    merged.mkdir(parents=True)
    fmt.write_json(merged / 'team.json', roster)
    for d in lay.skeleton(members):
        d.mkdir(parents=True, exist_ok=True)
    n = 0
    logs = []
    for t in TEAMS:
        src = fmt.Layout(t)
        if src.route_log.exists():
            logs += src.route_log.read_text(encoding='utf-8').splitlines()
        for p in src.post_sent.glob('*.json'):
            shutil.copy(p, lay.post_sent / p.name)
        for p in sorted(src.tasks.glob('t-*.json')):
            tk = fmt.read_json(p)
            if tk.get('parent'):
                continue
            n += 1
            tk['id'] = 't-%04d' % n
            fmt.write_json(lay.tasks / (tk['id'] + '.json'), tk)
    lay.route_log.write_text('\n'.join(logs) + '\n', encoding='utf-8')
    res = crystal.crystal(str(merged), out=str(merged / 'proposal.json'))
    out['merged'] = brief(res)
    out['merged']['fallthrough_detail'] = [{'text': f['text'], 'reason': f['reason'], 'linked': f['linked'],
                                            'tickets': [x['kind'] for x in f['tickets']]} for f in res['fallthrough']]
    (HERE / 'old-result.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print('\n--- 合併團隊的文字報告 ---')
    print(crystal.render(res))


if __name__ == '__main__':
    main()
