#!/usr/bin/env python3
"""Independent budget audit: stdlib only, no imports from budget or tests.
Reads stable budget directory snapshots; validates every persisted log transition,
ops, full business keys, digests, gateway evidence hashes and backend effect counter.
"""
import argparse, hashlib, json
from pathlib import Path

def sha(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def read(p, default=None):
    return json.loads(p.read_text()) if p.exists() else default

def audit(path, final=False):
    p = Path(path)
    L = read(p/'ledger.json')
    errors = []
    def check(ok, why):
        if not ok: errors.append(why)
    if not isinstance(L, dict): return {'ok': False, 'errors': ['missing or unreadable ledger'], 'path': str(p)}
    initial = L['initial']; balance = [initial, 0, 0]
    reserve, settle, stages = {}, {}, {}
    for seq, row in enumerate(L['log'], 1):
        k, amount = row['kid'], row['amount']
        check(row['seq'] == seq, f'log {seq}: sequence')
        check(isinstance(amount, int) and not isinstance(amount, bool) and amount > 0, f'log {seq}: amount')
        if row['op'] == 'reserve':
            check(k not in reserve, f'{k}: duplicate reserve')
            reserve[k] = row
            stages[k] = 'reserved'
            balance[0] -= amount; balance[1] += amount
        elif row['op'] == 'settle':
            check(k in reserve and k not in settle, f'{k}: missing reserve or duplicate settle')
            check(k in reserve and amount == reserve[k]['amount'], f'{k}: settlement amount differs')
            check(row['used'] in (0, amount), f'{k}: invalid used')
            settle[k] = row; stages[k] = 'settled'
            balance[0] += amount - row['used']; balance[1] -= amount; balance[2] += row['used']
        else: errors.append(f'log {seq}: unknown operation')
        check(balance == [row['available'], row['inflight'], row['used_total']], f'log {seq}: replay balances')
        check(min(balance) >= 0 and sum(balance) == initial, f'log {seq}: conservation/nonnegative')
    check(balance == [L['available'], L['inflight'], L['used']], 'final replay balances')
    check(L['seq'] == len(L['log']), 'final seq')
    check(set(L['ops']) == set(reserve), 'ops/log key set differs')
    gateways = {f.stem: read(f) for f in (p/'gateway').glob('*.json')} if (p/'gateway').exists() else {}
    backend = read(p/'backend.json', {'accepted': 0, 'effects': {}})
    effects = backend['effects']
    spent = {k: e for k, e in effects.items() if e['used'] > 0}
    check(backend['accepted'] == len(spent), 'backend accepted != positive effects: possible repeated K')
    check(sorted(e['n'] for e in spent.values()) == list(range(1, backend['accepted']+1)), 'backend effect ordinals are not unique contiguous')
    full_keys = []
    for k, op in L['ops'].items():
        key = op['key']; triple = [key['budget'], key['holder'], key['request']]
        full_keys.append(tuple(triple))
        check(sha(triple)[:20] == k, f'{k}: key hash')
        check(op['digest'] == sha({'key': key, 'content': op['content']}), f'{k}: content digest')
        check(op['stage'] == stages.get(k), f'{k}: op stage')
        check(op['amount'] == reserve[k]['amount'] and op['reserve']['seq'] == reserve[k]['seq'], f'{k}: reserve evidence')
        if k in settle:
            g = gateways.get(k, {})
            check(g.get('stage') == 'done' and g.get('used') == settle[k]['used'], f'{k}: gateway settlement evidence')
            check(op['settle']['evidence'] == sha(g), f'{k}: gateway receipt hash')
            check(op['settle']['seq'] == settle[k]['seq'] and op['settle']['used'] == settle[k]['used'], f'{k}: op settlement')
    check(len(full_keys) == len(set(full_keys)), 'duplicate full K under different kids')
    for k, eff in effects.items():
        g = gateways.get(k, {})
        check(k in reserve, f'{k}: effect without reserve')
        check(g.get('stage') in ('intent', 'done'), f'{k}: effect without gateway admission')
        check(eff['key'] == L['ops'].get(k, {}).get('key'), f'{k}: backend key differs')
        if g.get('stage') == 'done':
            check((g.get('used'),g.get('outcome')) == (eff['used'],eff['outcome']), f'{k}: backend/gateway differs')
    for k, g in gateways.items():
        if g.get('stage') == 'done':
            if g.get('outcome') in ('accepted', 'failed'):
                check(k in spent and spent[k]['used'] == g['used'], f'{k}: spent receipt without effect')
            elif g.get('outcome') in ('denied','cancelled','rejected'):
                check(g.get('used') == 0 and k not in spent, f'{k}: nonspending receipt has effect')
    if final:
        check(balance[1] == 0, 'final inflight != 0')
        check(balance[2] == sum(e['used'] for e in effects.values()), 'final used != backend effects sum')
    return {'ok': not errors, 'errors': errors, 'path': str(p), 'transitions': len(L['log']), 'keys': len(reserve), 'accepted': backend['accepted'], 'balances': balance, 'final': final}

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('paths', nargs='+'); ap.add_argument('--final', action='store_true'); a=ap.parse_args()
    out=[audit(p,a.final) for p in a.paths]
    print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(0 if all(x['ok'] for x in out) else 1)
