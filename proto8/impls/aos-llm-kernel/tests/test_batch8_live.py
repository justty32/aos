# Verify copied kernel templates nest through two real daemons and batch local packs without blocking urgent mail.
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[3]
REQUEST = {'messages': [{'role': 'user', 'content': 'batch 8 live'}]}
ERROR = {'error': {'code': 'DownstreamTest', 'msg': 'failure from lower kernel', 'details': [3, True]}}


class Batch8Live(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-batch8-live-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'lib').symlink_to(PROTO / 'lib', target_is_directory=True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        bins = [str(p) for p in (PROTO / 'impls').glob('*/bin')]
        cmds = [str(p) for p in (PROTO / 'cmd').glob('*/bin')]
        self.env['PATH'] = os.pathsep.join(bins + cmds + [self.env['PATH']])
        for name in ('aos-exec', 'aos-daemon', 'aos-llm', 'aos-llm-kernel'):
            self.assertTrue(shutil.which(name, path=self.env['PATH']).startswith(str(PROTO)))
        self.processes = []

    def copy_template(self, name):
        stack = self.root / name
        stack.mkdir()
        subprocess.run(['cp', '-a', str(PROTO/'kernel'/name), str(stack/'def')], check=True)
        return stack

    def launch(self, stack):
        log = open(stack / 'test-daemon.log', 'w+')
        self.addCleanup(log.close)
        daemon = subprocess.Popen(['aos-exec', '--stack', '.', 'def'], cwd=stack,
                                  env=self.env, stdout=log, stderr=log)
        self.processes.append((daemon, stack))
        self.addCleanup(self.stop, daemon, stack)
        self.wait_for(lambda: (stack/'endpoints.json').exists(), 'kernel startup')

    def stop(self, daemon, stack):
        (stack/'ctl.json').write_text('{"cmd":"stop","seq":9001}')
        try:
            daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            daemon.terminate()
            daemon.wait(timeout=5)
        self.assertEqual(daemon.returncode, 0, (stack/'test-daemon.log').read_text())

    def wait_for(self, check, message, timeout=20):
        until = time.monotonic()+timeout
        while time.monotonic() < until:
            value = check()
            if value:
                return value
            for daemon, stack in self.processes:
                if daemon.poll() is not None:
                    self.fail(message+': '+(stack/'test-daemon.log').read_text())
            time.sleep(0.01)
        logs = '\n'.join((stack/'test-daemon.log').read_text()[-3000:] for _,stack in self.processes)
        self.fail(message+': '+logs)

    def llm(self, stack, args, body=None):
        return subprocess.run(['aos-llm', *args], input=json.dumps(body) if body else None,
                              capture_output=True, text=True, timeout=20,
                              env=dict(self.env, AOS_LLM_KERNEL=str(stack)))

    def ledger(self, stack):
        try:
            return [json.loads(line) for line in (stack/'ledger.jsonl').read_text().splitlines()]
        except (FileNotFoundError, ValueError):
            return []

    def test_unmodified_templates_two_daemons_success_error_and_missing_kernel(self):
        lower = self.copy_template('llm-kernel')
        upper = self.copy_template('llm-team')
        self.assertFalse(any(k.startswith('AOS_') for k in self.env))
        self.launch(lower)
        self.launch(upper)
        direct = self.llm(lower, ['ask','--full'], {'request': REQUEST})
        nested = self.llm(upper, ['ask','--full'], {'request': REQUEST})
        self.assertEqual((direct.returncode,direct.stderr,nested.returncode,nested.stderr), (0,'',0,''))
        # Remove only the generated letter member, preserving all other output bytes.
        strip_letter = lambda s: re.sub(r',\s*"letter":\s*"[^"\\]*"(?=})', '', s)
        self.assertNotEqual(strip_letter(nested.stdout), nested.stdout)
        self.assertEqual(strip_letter(nested.stdout), strip_letter(direct.stdout))
        upper_id = json.loads(nested.stdout)['letter']
        rows = self.wait_for(lambda: self.ledger(upper), 'upper ledger')
        row = next(row for row in rows if row['id'] == upper_id)
        child = row['child']
        lower_rows = self.wait_for(lambda: self.ledger(lower) if any(
            r['id']==child['letter'] for r in self.ledger(lower)) else None, 'lower child ledger')
        self.assertEqual(child['kernel'], str(upper)+'/../llm-kernel')
        self.assertEqual(Path(child['kernel']).resolve(),lower)
        self.assertIn(child['letter'], [row['id'] for row in lower_rows])
        self.assertNotIn('child', json.loads(nested.stdout))
        # The lower kernel sees the team daemon as one sender, never the original caller.
        child_row = next(row for row in lower_rows if row['id'] == child['letter'])
        self.assertEqual(child_row['sender'], str(upper))
        self.assertEqual(row['usage'], child_row['usage'])
        for stack in (lower,upper):
            declaration = json.loads((stack/'def/interfaces.json').read_text())
            self.assertEqual(declaration['aos-ledger'], {'file':'ledger.jsonl'})
        # Add test-only error packs after the unchanged templates have passed.
        endpoint = self.root/'error-endpoint'
        endpoint.mkdir()
        entry = endpoint/'_entry'
        entry.write_text('#!/usr/bin/env python3\n# Emit a structured downstream failure with exit status 3.\n'
                         'import sys\nprint('+repr(json.dumps(ERROR))+')\nsys.exit(3)\n')
        entry.chmod(0o755)
        path = lower/'def/kernel.json'
        cfg = json.loads(path.read_text())
        cfg['endpoints']['failure'] = {'exec':str(endpoint)}
        path.write_text(json.dumps(cfg))
        path = upper/'def/kernel.json'
        cfg = json.loads(path.read_text())
        cfg['endpoints']['failure'] = {'to':'failure','kernel':str(lower)}
        cfg['endpoints']['missing'] = {'to':'fake'}
        cfg['endpoints']['unknown-backend'] = {'to':'fake','kernel':str(lower),'backend':'undeclared'}
        path.write_text(json.dumps(cfg))
        direct = self.llm(lower,['ask','--full'], {'endpoint':'failure','request':REQUEST})
        nested = self.llm(upper,['ask','--full'], {'endpoint':'failure','request':REQUEST})
        self.assertEqual((nested.stdout,nested.stderr.splitlines()[-1],nested.returncode),
                         (direct.stdout,direct.stderr.splitlines()[-1],direct.returncode))
        self.assertEqual(direct.returncode,1)  # aos-llm's public error status; endpoint itself exited 3.
        self.assertEqual(json.loads(nested.stdout),ERROR)
        missing = self.llm(upper,['ask','--full'], {'endpoint':'missing','request':REQUEST})
        line = 'llm_forward: error: CfgBad endpoint pack has no "kernel"'
        self.assertEqual(missing.returncode,1)
        self.assertEqual(json.loads(missing.stdout), {'error':{'code':'EndpointFailed',
                         'msg':'endpoint function exited with code 1: '+line}})
        unknown = self.llm(upper,['ask','--full'], {'endpoint':'unknown-backend','request':REQUEST})
        self.assertEqual(unknown.returncode,1)
        self.assertEqual(json.loads(unknown.stdout)['error']['code'],'CfgBad')

    def start_backend(self):
        stack = self.copy_template('llm-kernel')
        endpoint = self.root/'slow-endpoint'
        endpoint.mkdir()
        entry = endpoint/'_entry'
        entry.write_text('''#!/usr/bin/env python3
# Hold the first fake request until all competing letters have been queued.
import json,os,pathlib,subprocess,sys,time
raw = sys.stdin.buffer.read()
(pathlib.Path(os.environ['AOS_STACK'])/'started').touch()
gate = pathlib.Path('''+repr(str(self.root/'release'))+''')
until = time.monotonic()+15
while not gate.exists():
    if time.monotonic()>until:
        sys.exit('test release timed out')
    time.sleep(0.01)
time.sleep(0.08)
r = subprocess.run(['aos-exec','''+repr(str(PROTO/'lib/base/llm_fake'))+'''],input=raw)
sys.exit(r.returncode)
''')
        entry.chmod(0o755)
        (stack/'def/kernel.json').write_text(json.dumps({'slots':4,'aging_ticks':1000000,
            'exec':str(endpoint),'backends':{'local':{'slots':1,'max_packs':1}},
            'endpoints':{'a':{'backend':'local'},'b':{'backend':'local'}}}))
        (stack/'def/daemon.json').write_text('{"exec":{"argv":["aos-llm-kernel","kernel.json"]},"interval_ms":10}')
        self.launch(stack)
        return stack

    def send(self, stack, pack, priority='normal'):
        result = self.llm(stack,['send','--reply-to',str(self.root/'replies')],
                          {'endpoint':pack,'request':REQUEST,'priority':priority})
        self.assertEqual((result.returncode,result.stderr),(0,''))
        return result.stdout.strip()

    def monitor_until_done(self, stack, count):
        observed = set()
        def check():
            # Check both the durable in-flight letters and daemon's actual running table.
            packs = set()
            for path in (stack/'requests/cur').glob('*/proc.json'):
                try:
                    packs.add(json.loads(path.read_text())['endpoint'])
                except FileNotFoundError:
                    pass
            self.assertLessEqual(len(packs),1)
            observed.update(packs)
            table = stack/'procs_state.json'
            if table.exists():
                table = json.loads(table.read_text())
                running = [name for name,row in table.get('procs',{}).items()
                           if name.startswith('llm_') and row.get('phase')=='running']
                self.assertLessEqual(len(running),1)
            rows = self.ledger(stack)
            return rows if len(rows)==count else None
        rows = self.wait_for(check,'backend calls did not finish')
        self.assertEqual(observed,{'a','b'})
        return rows

    def test_live_local_packs_batch_once_and_switch_twice(self):
        stack = self.start_backend()
        first = self.send(stack,'a')
        self.wait_for(lambda: (stack/'requests/cur'/first/'started').exists(), 'first fake not running')
        for pack in ('b','a','b','a','b'):
            self.send(stack,pack)
        (self.root/'release').touch()
        rows = self.monitor_until_done(stack,6)
        self.assertEqual([row['endpoint'] for row in rows],list('aaabbb'))
        self.assertEqual([row['switched'] for row in rows],[True,False,False,True,False,False])
        state = json.loads((stack/'queue.json').read_text())['backends']['local']
        self.assertEqual((state['pack'],state['counter_switches']),('b',2))
        self.assertEqual(state['switched_at'],rows[3]['mounted_at'])

    def test_live_urgent_b_runs_before_sticky_a(self):
        stack = self.start_backend()
        first = self.send(stack,'a')
        self.wait_for(lambda: (stack/'requests/cur'/first/'started').exists(), 'first fake not running')
        self.send(stack,'a')
        self.send(stack,'b','high')
        (self.root/'release').touch()
        rows = self.monitor_until_done(stack,3)
        self.assertEqual([row['endpoint'] for row in rows],list('aba'))
        self.assertEqual([row['switched'] for row in rows],[True,True,True])


if __name__ == '__main__':
    unittest.main()
