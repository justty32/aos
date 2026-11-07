"""Verify byte scoring and independent custom comparator costs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import compare


class CompareTest(unittest.TestCase):
    def test_bytes_fraction_and_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            expect, got = root / 'expect', root / 'got'
            expect.mkdir()
            got.mkdir()
            (expect / 'a').write_bytes(b'a')
            (expect / 'b').write_bytes(b'b')
            (got / 'a').write_bytes(b'a')
            result = compare.compare(expect, got, root, {}, root / 'stack', root)
            self.assertEqual(result['score'], 0.5)
            self.assertEqual(result['diff'], ['b'])

    def test_custom_call_contract_and_cost(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cost = {'token': {'in': 7, 'out': 2, 'cached': 0}, 'counter_calls': 1, 'time_ms': 3}
            with patch.object(compare.observed, 'call', return_value=(0, b'{"score":0.5,"diff":["x"],"why":"different"}', b'')) as call, patch.object(compare, 'fold', return_value=({}, cost)):
                result = compare.compare(root, root, root, {'compare': 'judge'}, root / 'stack', root)
            self.assertEqual(result['cost'], cost)
            self.assertEqual(result['score'], .5)
            self.assertEqual(json.loads(call.call_args.args[2]), {'expect': str(root), 'got': str(root), 'input': str(root)})

    def test_nonzero_comparator_is_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(compare.observed, 'call', return_value=(9, b'', b'')), patch.object(compare, 'fold', return_value=({}, {})):
                result = compare.compare(root, root, root, {'compare': 'judge'}, root / 'stack', root)
            self.assertEqual(result['code'], 9)
            self.assertEqual(result['score'], 0)


if __name__ == '__main__':
    unittest.main()
