"""恢復 state 的結構驗證；pending 動作值已凍結，不重展模板。"""
from pathlib import Path
import re
from aos7_menu_check import BUILTINS, normalize_out

def pending_ok(p, menu, s):
    if p is None:
        return True
    if not isinstance(p, dict) or s['layer'] not in menu['layers']:
        return False
    layer = menu['layers'][s['layer']]
    if 'act' not in p:
        count = sum(c['layer'] == s['layer'] for c in s['calls']) + 1
        expected = {'call_id': f"menu/{s['run']}/{s['layer']}/{count}", 'layer': s['layer']}
        received = p.get('received')
        return ('ask' in layer and set(p) in (set(expected), set(expected) | {'received'})
                and all(p.get(k) == v for k, v in expected.items())
                and ('received' not in p or isinstance(received, dict)
                     and set(received) == {'reply', 'used', 'rc'}
                     and isinstance(received['reply'], str) and type(received['rc']) is int
                     and received['rc'] in (0, 4)
                     and (received['used'] is None or type(received['used']) is int)))
    targets = ([o['next'] for o in layer.get('options', [])]
               if isinstance(layer.get('options'), list) else [layer.get('next')])

    def action_ok(item, checking=False):
        if not isinstance(item, dict) or not isinstance(item.get('act'), dict):
            return False
        act = item['act']
        if checking:
            then = item.get('then')
            return (set(item) == {'act', 'then'} and set(act) == {'check', 'text'}
                    and act['check'] == layer.get('slot', {}).get('tool')
                    and isinstance(act['check'], str) and isinstance(act['text'], str)
                    and isinstance(then, dict)
                    and (action_ok(then) if 'act' in then else
                         set(then) == {'next'} and then['next'] in targets and 'do' not in layer))
        do = layer.get('do', {})
        if 'write' in act:
            return (set(item) == {'act', 'next'} and set(act) == {'write', 'text'}
                    and 'ask' in layer and 'write' in do and isinstance(act['text'], str)
                    and isinstance(act['write'], str)
                    and act['write'] == 'out/' + normalize_out(act['write'])
                    and item['next'] in targets)
        expected = {'act', 'next'} if 'ask' in layer else {'act'}
        return (set(item) == expected and set(act) == {'tool', 'args'}
                and act['tool'] == do.get('tool') and isinstance(act['tool'], str)
                and isinstance(act['args'], dict) and set(act['args']) == set(do.get('args', {}))
                and all(isinstance(v, str) for v in act['args'].values())
                and ('ask' not in layer or item['next'] in targets))

    return action_ok(p, 'check' in p['act']) if isinstance(p['act'], dict) else False

def valid_state(s, menu):
    return (isinstance(s, dict) and s.get('v') == 1 and s.get('status') in ('walking', 'done', 'stuck')
            and s.get('layer') in (*menu['layers'], 'end') and 'pending' in s and 'why' in s
            and (s['why'] is None or isinstance(s['why'], str))
            and (s['status'] != 'stuck' or isinstance(s['why'], str) and type(s.get('code')) is int)
            and all(isinstance(s.get(k), str) for k in ('run', 'menu', 'menu_sha', 'brief', 'nonce'))
            and bool(re.fullmatch(r'[0-9a-f]{16}', s['nonce']))
            and all(isinstance(s.get(k), dict) for k in ('vars', 'initial_vars', 'gate_rounds', 'var_owner'))
            and all(isinstance(k, str) and k not in BUILTINS and k in s['vars']
                    and isinstance(v, str) for k, v in s['var_owner'].items())
            and all(isinstance(s.get(k), list) for k in ('done', 'calls', 'journal'))
            and all(isinstance(x, str) and normalize_out('out/' + x) == x for x in s['done'])
            and all(isinstance(v, (str, int, float, bool)) for v in (*s['vars'].values(), *s['initial_vars'].values()))
            and all(isinstance(s['vars'].get(k), str) for k in ('run', 'node', 'run_dir'))
            and s['vars']['run'] == s['run']
            and s['vars']['run_dir'] == str(Path(s['vars']['node']) / 'menu' / s['run'])
            and (s['status'] != 'done' or s['layer'] == 'end')
            and (s['status'] == 'walking' or s['pending'] is None)
            and all(isinstance(x, dict) and all(isinstance(x.get(k), str) for k in ('layer', 'call_id'))
                    and x['layer'] in menu['layers'] and 'used' in x and type(x.get('rc')) is int for x in s['calls'])
            and all(type(v) is int and v >= 0 for v in s['gate_rounds'].values())
            and all(isinstance(x, dict) and type(x.get('step')) is int
                    and all(k in x for k in ('kind', 'layer', 'call_id', 'rc', 'used', 'why')) for x in s['journal'])
            and all(type(s.get(k)) is int and s[k] >= 0 for k in ('tries', 'step'))
            and pending_ok(s.get('pending'), menu, s))

