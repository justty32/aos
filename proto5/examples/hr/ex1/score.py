#!/usr/bin/env python3
"""例子 1 的評分指令（spec/team/hr.md〈評分指令〉）：在試用的專案副本（AOS_HR_PROJECT）逐條跑 checks.json 的 11 條機械檢查。
分數＝過幾條／11 × 100；mech_ok＝11 條全過。不叫模型。最後一行印一個 JSON 物件。"""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'lib'))
import aos_team_verify as v  # noqa: E402

proj = Path(os.environ['AOS_HR_PROJECT'])
items = json.loads((HERE / 'checks.json').read_text(encoding='utf-8'))
rows = []
for it in items:
    try:
        if it['kind'] == 'file_exists':
            ok, why = (proj / it['path']).is_file(), it['path']
        else:
            ok, why = getattr(v, 'check_' + it['name'])(proj, it.get('args', {}))[:2]
    except Exception as e:                      # noqa: BLE001  檢查器壞了＝這條沒過
        ok, why = False, '檢查器壞了：%s' % e
    rows.append({'item': it.get('name') or it['kind'], 'args': it.get('args') or it.get('path'), 'ok': bool(ok),
                 'why': str(why)[:160]})
    print(('PASS ' if ok else 'FAIL ') + json.dumps(rows[-1], ensure_ascii=False))
passed = sum(r['ok'] for r in rows)
print(json.dumps({'score': round(100 * passed / len(rows)), 'mech_ok': passed == len(rows),
                  'passed': passed, 'total': len(rows),
                  'failed': [r['args'] or r['item'] for r in rows if not r['ok']]}, ensure_ascii=False))
