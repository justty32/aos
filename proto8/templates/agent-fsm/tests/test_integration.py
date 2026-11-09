# Verify agent cells through the real local kernel, llm_fake endpoint, and wall_clock tool.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

CELLS = Path(__file__).resolve().parents[1]
PROTO = CELLS.parents[1]


class KernelIntegration(unittest.TestCase):
    def test_fake_brain_and_tool(self):
        with tempfile.TemporaryDirectory(prefix='aos-cells-') as tmp:
            root = Path(tmp)
            kernel_stack = root / 'kernel'
            kernel_stack.mkdir()
            agent_stack = root / 'agent'
            agent_stack.mkdir()
            definition = root / 'definition'
            definition.mkdir()
            (definition / 'interfaces.json').write_text(json.dumps({'aos-agent': {
                'llm':'llm.json', 'tools':'tools.json'}}))
            (definition / 'llm.json').write_text('{"endpoint":"fake"}')
            (definition / 'tools.json').write_text(json.dumps({'tools':{
                'wall_clock':{'path':str(PROTO / 'lib/base/wall_clock')}}}))
            (agent_stack / 'history.jsonl').write_text('{"role":"user","content":"local test"}\n')
            config = root / 'kernel.json'
            config.write_text(json.dumps({'exec':str(PROTO / 'lib/base/llm_fake'),
                                          'endpoint':'fake', 'endpoints':{'fake':{}}}))
            daemon_config = root / 'daemon.json'
            daemon_config.write_text(json.dumps({'interval_ms':10, 'exec':{
                'argv':[str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(config)]}}))
            env = {k:v for k,v in os.environ.items() if not k.startswith('AOS_')}
            bins = [str(path) for path in (PROTO / 'impls').glob('*/bin')]
            env['PATH'] = os.pathsep.join(bins + [str(PROTO / 'cmd/aos-tools/bin'), env['PATH']])
            env.update(AOS_STACK=str(kernel_stack), AOS_CD=str(root), AOS_WS=str(root))
            with open(root / 'daemon.log', 'w+') as log:
                daemon = subprocess.Popen(['aos-daemon', str(daemon_config)], cwd=root,
                                          env=env, stdout=log, stderr=log)
                try:
                    env.update(AOS_STACK=str(agent_stack), AOS_CD=str(definition),
                               AOS_LLM_KERNEL=str(kernel_stack))

                    def cell(name, *args):
                        return subprocess.run([sys.executable, str(CELLS / (name + '.py')), *args],
                                              env=env, capture_output=True, text=True, timeout=5)

                    for turn in range(2):
                        result = cell('brain', '--history', 'task', '--max-tool-calls', '1')
                        self.assertEqual(result.returncode, 0, result.stderr)
                        deadline = time.monotonic() + 10
                        while True:
                            result = cell('wait')
                            if result.returncode != 10 or time.monotonic() >= deadline:
                                break
                            time.sleep(0.02)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        result = cell('act')
                        self.assertEqual(result.returncode, 0 if turn == 0 else 10, result.stderr)
                    history = [json.loads(line) for line in (agent_stack / 'history.jsonl').read_text().splitlines()]
                    self.assertIn('FAKE ANSWER', history[-1]['content'])
                    records = [json.loads(line) for line in (agent_stack / 'observed.jsonl').read_text().splitlines()]
                    self.assertEqual([r['kind'] for r in records], ['self','think','tool','think'])
                    self.assertEqual(records.pop(0)['kind'], 'self')
                    self.assertEqual(records[0]['model'], 'fake')
                    self.assertEqual(records[0]['endpoint'], 'fake')
                    self.assertEqual(records[1]['code'], 0)
                    self.assertEqual(records[0]['usage']['total_tokens'], 0)
                    deadline = time.monotonic() + 2
                    while True:
                        ledger_path = kernel_stack / 'ledger.jsonl'
                        ledger = [json.loads(line) for line in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
                        if len(ledger) == 2 or time.monotonic() >= deadline:
                            break
                        time.sleep(0.02)
                    thoughts = [r for r in records if r['kind'] == 'think']
                    self.assertEqual(len(ledger), 2)
                    self.assertEqual([r['letter'] for r in thoughts], [r['id'] for r in ledger])
                    self.assertEqual(len({r['letter'] for r in thoughts}), 2)
                finally:
                    (kernel_stack / 'ctl.json').write_text('{"cmd":"stop","seq":1}')
                    try:
                        daemon.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        daemon.terminate()
                        daemon.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
