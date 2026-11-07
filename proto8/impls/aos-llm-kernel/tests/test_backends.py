# Verify backend limits, durable switch records, and priority-safe sticky ordering with prepared mailboxes.
import json
import subprocess
import time
import unittest

import test_ledger


class BackendFixtures(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp
    prepare = test_ledger.LedgerTests.prepare
    run_kernel = test_ledger.LedgerTests.run_kernel
    ledger = test_ledger.LedgerTests.ledger

    def config_backends(self, slots=1, max_packs=1, total=8):
        cfg = {'exec': str(test_ledger.FAKE.parent), 'slots': total,
               'aging_ticks': 1000000,
               'backends': {'local': {'slots': slots}},
               'endpoints': {'a': {'backend': 'local', 'speed': 'slow'},
                             'b': {'backend': 'local', 'speed': 'fast'}, 'free': {}}}
        if max_packs is not None:
            cfg['backends']['local']['max_packs'] = max_packs
        self.config.write_text(json.dumps(cfg))
        return cfg

    def send(self, name, endpoint, priority=None):
        folder = self.stack / 'requests/new' / name
        folder.mkdir()
        body = {'endpoint': endpoint, 'request': {'messages': []}}
        if priority is not None:
            body['priority'] = priority
        (folder / 'letter.json').write_text(json.dumps({'body': body}))
        return folder

    def proc(self, name):
        return json.loads((self.stack / 'requests/cur' / name / 'proc.json').read_text())

    def state(self):
        return json.loads((self.stack / 'queue.json').read_text())

    def sticky(self, pack='a'):
        (self.stack / 'queue.json').write_text(json.dumps({'counter_runs': 0,
            'backends': {'local': {'pack': pack, 'switched_at': 1.25, 'counter_switches': 1}}}))

    def test_invalid_backend_config_and_undeclared_pack(self):
        cfg = self.config_backends()
        for bad in (None, [], {'local': {}}, {'local': {'slots': 0}},
                    {'local': {'slots': True}}, {'local': {'slots': 1.5}},
                    {'local': {'slots': 2**63}}, {'local': {'slots': 1, 'max_packs': 0}},
                    {'local': {'slots': 1, 'max_packs': None}}, {'local': {'slots': 1, 'max_packs': True}}):
            with self.subTest(backends=bad):
                self.config.write_text(json.dumps(dict(cfg, backends=bad)))
                result = subprocess.run([str(test_ledger.KERNEL), str(self.config)], env=self.env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn(': error: CfgBad ', result.stderr)
        self.config.write_text(json.dumps(dict(cfg, backends={})))
        self.send('undeclared', 'a')
        self.run_kernel()
        self.assertFalse((self.stack / 'requests/new/undeclared').exists())
        window = json.loads((self.stack / 'endpoints.json').read_text())
        self.assertTrue(window['a']['error'].startswith('CfgBad '))
        self.assertFalse((self.stack / 'requests/cur/undeclared/proc.json').exists())

    def test_queue_backends_validate_types(self):
        self.config_backends()
        for bad in (None, [], {'local': {}}, {'local': {'pack': 1, 'switched_at': 1, 'counter_switches': 1}},
                    {'local': {'pack': 'a', 'switched_at': 'now', 'counter_switches': 1}},
                    {'local': {'pack': 'a', 'switched_at': 1, 'counter_switches': -1}},
                    {'local': {'pack': 'a', 'switched_at': 1, 'counter_switches': True}}):
            with self.subTest(backends=bad):
                (self.stack / 'queue.json').write_text(json.dumps({'counter_runs': 0, 'backends': bad}))
                result = subprocess.run([str(test_ledger.KERNEL), str(self.config)], env=self.env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn(': error: QueueBad ', result.stderr)

    def test_backend_slots_count_existing_and_new_mounts_and_skip(self):
        self.config_backends(slots=2, max_packs=None)
        self.send('01', 'a')
        self.send('02', 'a')
        self.run_kernel()
        self.send('03', 'b')
        self.send('04', 'free')
        self.run_kernel()
        self.assertTrue((self.stack / 'requests/new/03').exists())
        self.assertEqual(self.proc('04')['endpoint'], 'free')
        self.assertEqual(self.state()['backends']['local']['counter_switches'], 1)
        self.assertIs(self.proc('01')['switched'], True)
        self.assertIs(self.proc('02')['switched'], False)
        request = json.loads((self.stack / 'requests/cur/01/request.json').read_text())
        self.assertNotIn('backend', request['endpoint'])
        window = json.loads((self.stack / 'endpoints.json').read_text())
        self.assertEqual(window['a']['backend'], 'local')
        self.assertNotIn('backend', window['free'])

    def test_max_packs_counts_distinct_and_skips_blocked_pack(self):
        self.config_backends(slots=5, max_packs=1)
        self.send('01', 'a')
        self.run_kernel()
        self.send('02', 'b', priority='high')
        self.send('03', 'a')
        self.send('04', 'free')
        self.run_kernel()
        self.assertTrue((self.stack / 'requests/new/02').exists())
        self.assertEqual(self.proc('03')['endpoint'], 'a')
        self.assertEqual(self.proc('04')['endpoint'], 'free')
        self.assertIs(self.proc('03')['switched'], False)
        self.assertEqual(self.state()['backends']['local']['counter_switches'], 1)

    def test_stickiness_precedes_speed_but_not_priority_deadline_or_aging(self):
        self.config_backends(total=1)
        for index, kind in enumerate(('sticky', 'high', 'deadline', 'aging')):
            with self.subTest(kind=kind):
                self.sticky()
                a, b = f'a{index}', f'b{index}'
                self.send(a, 'a')
                self.send(b, 'b', priority='high' if kind == 'high' else
                          {'level': 'normal', 'deadline': time.time()+3600} if kind == 'deadline' else None)
                if kind == 'aging':
                    cfg = json.loads(self.config.read_text())
                    cfg['aging_ticks'] = 1
                    self.config.write_text(json.dumps(cfg))
                    q = self.state()
                    q['seen_at_ms'] = {b: int(time.time()*1000)-10000}
                    (self.stack / 'queue.json').write_text(json.dumps(q))
                self.run_kernel()
                chosen = a if kind == 'sticky' else b
                self.assertEqual(self.proc(chosen)['endpoint'], 'a' if kind == 'sticky' else 'b')
                folder = self.stack / 'requests/cur' / chosen
                (folder / 'state.json').write_text('{"phase":"done","code":0}')
                (folder / 'reply.json').write_text(json.dumps(self.reply))
                # Discard the other test-owned waiting letter before collecting the result.
                import shutil
                shutil.rmtree(self.stack / 'requests/new' / (b if chosen == a else a))
                self.run_kernel()

    def test_switched_persists_across_remount_and_is_copied_to_ledger(self):
        self.config_backends()
        self.send('retry', 'a')
        self.run_kernel()
        initial = self.proc('retry')
        q = self.state()['backends']['local']
        self.assertIs(initial['switched'], True)
        folder = self.stack / 'requests/cur/retry'
        (folder / 'state.json').write_text('{"phase":"running","code":null}')
        self.run_kernel()
        self.assertEqual(self.proc('retry')['retries'], 1)
        self.assertIs(self.proc('retry')['switched'], True)
        self.assertEqual(self.state()['backends']['local'], q)
        (folder / 'state.json').write_text('{"phase":"done","code":0}')
        (folder / 'reply.json').write_text(json.dumps(self.reply))
        self.run_kernel()
        self.assertIs(self.ledger()[0]['switched'], True)

    def test_pack_slots_still_apply(self):
        cfg = self.config_backends(slots=5)
        cfg['endpoints']['a']['slots'] = 1
        self.config.write_text(json.dumps(cfg))
        self.send('a1','a')
        self.send('a2','a')
        self.send('f','free')
        self.run_kernel()
        self.assertEqual(self.proc('a1')['endpoint'],'a')
        self.assertEqual(self.proc('f')['endpoint'],'free')
        self.assertTrue((self.stack / 'requests/new/a2').exists())

    def test_reserved_slots_still_apply(self):
        cfg = self.config_backends(slots=5, total=3)
        cfg['reserved'] = {'high': 1}
        self.config.write_text(json.dumps(cfg))
        for index in range(3):
            self.send('a'+str(index),'a')
        self.run_kernel()
        self.assertEqual(len(list((self.stack / 'requests/cur').iterdir())),2)
        self.assertTrue((self.stack / 'requests/new/a2').exists())
        self.send('high','a','high')
        self.run_kernel()
        self.assertEqual(self.proc('high')['endpoint'],'a')
        self.assertTrue((self.stack / 'requests/new/a2').exists())

    def test_two_distinct_packs_and_mixed_backend_order(self):
        cfg = self.config_backends(slots=5,max_packs=2,total=4)
        cfg['backends']['remote'] = {'slots':2}
        cfg['endpoints']['remote'] = {'backend':'remote'}
        cfg['endpoints']['c'] = {'backend':'local'}
        self.config.write_text(json.dumps(cfg))
        self.sticky()
        # Baseline speed order b, remote, a becomes a, remote, b for local only.
        self.send('01','b')
        self.send('02','remote')
        self.send('03','a')
        self.run_kernel()
        self.assertIs(self.proc('03')['switched'],False)
        self.assertIs(self.proc('01')['switched'],True)
        self.assertIs(self.proc('02')['switched'],True)
        self.send('04','c','high')
        self.send('05','b')
        self.run_kernel()
        self.assertTrue((self.stack / 'requests/new/04').exists())
        self.assertEqual(self.proc('05')['endpoint'],'b')

    def test_backend_directives_resolve_without_resolving_unused_pack_fields(self):
        cfg = self.config_backends()
        (self.stack/'limits.json').write_text('{"local":{"slots":2,"max_packs":1}}')
        cfg['backends'] = {'$ref':'limits.json'}
        cfg['endpoints']['a']['backend'] = {'$env':'TEST_BATCH8_BACKEND'}
        cfg['endpoints']['a']['custom'] = {'$env':'TEST_BATCH8_ABSENT'}
        self.env['TEST_BATCH8_BACKEND'] = 'local'
        self.config.write_text(json.dumps(cfg))
        self.run_kernel()
        window = json.loads((self.stack/'endpoints.json').read_text())
        self.assertEqual(window['a']['backend'],'local')
        self.send('unused-field','a')
        self.run_kernel()
        self.assertFalse((self.stack/'requests/cur/unused-field/proc.json').exists())


if __name__ == '__main__':
    unittest.main()
