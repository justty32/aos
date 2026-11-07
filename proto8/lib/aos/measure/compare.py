"""Compare workspace artifacts using bytes or an observed custom comparator."""
import json
import math
import time
from pathlib import Path

import observed
from ledger import empty_cost, fold


def compare(expect, got, case, check, stack, defs):
    if check.get('compare'):
        stack.mkdir(parents=True, exist_ok=True)
        target = Path(check['compare'])
        if not target.is_absolute():
            target = defs / target
        started = time.monotonic_ns()
        code, out, _ = observed.call('compare', target, json.dumps({
            'expect': str(expect), 'got': str(got), 'input': str(case)}), stack=stack)
        _, cost = fold(stack / 'tools/compare', defs, target=target, elapsed_ms=(time.monotonic_ns() - started) / 1_000_000)
        if code:
            return {'score': 0, 'diff': [], 'code': code, 'cost': cost}
        result = json.loads(out)
        if not isinstance(result, dict) or not isinstance(result.get('diff'), list) or not all(isinstance(d, str) for d in result['diff']):
            raise ValueError('comparator must return an object with a string array diff')
        score = result['score']
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('comparator score must be a finite number between 0 and 1')
        return {**result, 'cost': cost}
    files = sorted(p for p in expect.rglob('*') if p.is_file())
    diff = [p.relative_to(expect).as_posix() for p in files
            if not (got / p.relative_to(expect)).is_file()
            or p.read_bytes() != (got / p.relative_to(expect)).read_bytes()]
    return {'score': (len(files) - len(diff)) / len(files) if files else 1.0,
            'diff': diff, 'cost': empty_cost()}
