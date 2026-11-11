# fork 工具本身（不起 daemon）：參數錯、深度上限、環境錯、收尾次序；fork_copy 的抄法（補 tool 訊息、相對路徑換算、只抄宣告的檔、記號檔）。
import ast
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

HERE = Path(__file__).resolve().parents[1]
LIB = HERE.parents[1]
ENTRY = HERE / '_entry'
sys.path.insert(0, str(LIB / 'agent'))
import fork_copy  # noqa: E402


def run(arguments, **env):
    base = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
    base.update(env)
    r = subprocess.run([str(ENTRY)], input=arguments if isinstance(arguments, str) else json.dumps(arguments),
                       capture_output=True, text=True, env=base, timeout=30)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


class Arguments(unittest.TestCase):
    def assertCode(self, arguments, code, **env):
        rc, out, err = run(arguments, **env)
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.startswith('fork: error: %s ' % code), out)
        self.assertEqual(out, err)                               # 給腦用的工具兩邊印同一行

    def test_bad_arguments(self):
        for arguments in ({}, {'goal': ' '}, {'goal': 'x', 'max_chars': 0}, {'goal': 'x', 'keep': 'yes'},
                          {'goal': 'x', 'timeout_s': 0}, {'goal': 'x', 'timeout_s': 1, 'timeout_cycles': 1},
                          {'goal': 'x', 'timeout_cycles': 0}):
            with self.subTest(arguments=arguments):
                self.assertCode(arguments, 'ArgumentsBad')

    def test_other_definitions_and_settings_are_not_arguments(self):
        for key, value in (('from', 'helpers/basic'), ('tools', []), ('model', 'fake'), ('context', 'x')):
            with self.subTest(key=key):
                rc, out, _ = run({'goal': 'x', key: value})
                self.assertEqual(rc, 1)
                self.assertIn('ArgumentsBad unknown key %s' % key, out)

    def test_depth_limit(self):
        self.assertCode({'goal': 'x'}, 'DepthExceeded', AOS_FORK_DEPTH='1')
        self.assertCode({'goal': 'x'}, 'DepthExceeded', AOS_FORK_DEPTH='7')
        self.assertCode({'goal': 'x'}, 'ArgumentsBad', AOS_FORK_DEPTH='-1')
        self.assertCode({'goal': 'x'}, 'ArgumentsBad', AOS_FORK_DEPTH='two')
        rc, out, _ = run({'goal': 'x'}, AOS_DO_TASK_DEPTH='5')   # 舊 do_task 的變數不算
        self.assertIn('DaemonMissing', out)

    def test_environment(self):
        self.assertCode({'goal': 'x'}, 'DaemonMissing')
        with tempfile.TemporaryDirectory() as tmp:
            self.assertCode({'goal': 'x'}, 'StackMissing', AOS_DAEMON=tmp)
            self.assertCode({'goal': 'x'}, 'WsMissing', AOS_DAEMON=tmp, AOS_STACK=tmp, AOS_WS=os.path.join(tmp, 'nope'))

    def test_help(self):
        r = subprocess.run([str(ENTRY), '--help'], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith('usage: fork < ARGUMENTS.json'))

    def test_copies_the_account_before_keep_and_remove(self):
        source = ENTRY.read_text()
        ending = source[source.index('# ---- 問、收 ----'):]
        for keep in (False, True):
            with self.subTest(keep=keep):
                events = []

                def agent(argv, **kwargs):
                    events.append(argv[1] if argv[0] == 'ctl' else argv[0])
                    return 'answer', None

                def leave(code):
                    raise SystemExit(code)
                ns = dict(OPENING='{goal}{n}{again}', AGAIN_NO='', AGAIN_YES='', MAX_DEPTH=1, depth=0, max_chars=600,
                          goal='task', kid='kid', stack='tool', kid_stack='/daemon/kid', keep=keep,
                          timeout_cycles=None, timeout_s=600, agent=agent,
                          copy_child=lambda *args: events.append('copy'),
                          mark=Mock(), forget=Mock(), tool_io=Mock(), rel=lambda value: value,
                          sys=SimpleNamespace(stdout=io.StringIO(), exit=leave))
                with self.assertRaises(SystemExit) as result:
                    exec(compile(ending, str(ENTRY), 'exec'), ns)
                self.assertEqual(result.exception.code, 0)
                self.assertEqual(events, ['say', 'listen', 'copy', 'stop' if keep else 'rm'])
                if keep:
                    ns['mark'].assert_called_once_with('kid', 'kept')
                else:
                    ns['forget'].assert_called_once_with('kid')

    def test_opening_says_fork_goal_and_no_more_forks(self):
        tree = ast.parse(ENTRY.read_text())
        consts = {t.id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  for t in n.targets if isinstance(t, ast.Name) and t.id in ('OPENING', 'AGAIN_NO')}
        text = consts['OPENING'].format(goal='Find the port.', n=600, again=consts['AGAIN_NO'])
        self.assertTrue(text.startswith('[aos] fork: you are a fork'))
        self.assertIn('Your task: Find the port.', text)
        self.assertIn('conclusion only', text)
        self.assertIn('At most 600 characters.', text)
        self.assertIn('You cannot fork again', text)


class Copy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.defn, self.src, self.dst = self.root / 'def', self.root / 'ws' / '.stack', self.root / 'daemon' / 'procs' / 'kid'
        for p in (self.defn, self.src, self.dst):
            p.mkdir(parents=True)
        (self.defn / 'interfaces.json').write_text(json.dumps({'aos-agent': {
            'history': 'history.jsonl', 'tools': 'tools.json', 'llm': 'llm.json', 'hooks': 'hooks.json', 'system': 'system.txt'}}))

    def test_pending_tool_calls_get_answers(self):
        calls = [{'id': 'a', 'function': {'name': 'peek'}}, {'id': 'b', 'function': {'name': 'fork'}},
                 {'id': 'c', 'function': {'name': 'math'}}]
        lines = [json.dumps({'role': 'user', 'content': 'hi'}), 'not json',
                 json.dumps({'role': 'assistant', 'tool_calls': calls}),
                 json.dumps({'role': 'tool', 'tool_call_id': 'a', 'content': 'ok'})]
        got = fork_copy.pending_tools(lines)
        self.assertEqual([(m['tool_call_id'], m['content']) for m in got],
                         [('b', fork_copy.OWN_CALL), ('c', fork_copy.OTHER_CALL)])
        self.assertEqual(fork_copy.pending_tools(lines[:1]), [])
        self.assertEqual(fork_copy.pending_tools([json.dumps({'role': 'assistant', 'content': 'done'})]), [])

    def test_copy_only_the_declared_files_and_move_relative_paths(self):
        (self.src / 'history.jsonl').write_text(json.dumps({'role': 'user', 'content': 'secret'}) + '\n\n'
                                                + json.dumps({'role': 'assistant', 'tool_calls': [{'id': 'x'}]}) + '\n')
        (self.src / 'tools.json').write_text(json.dumps({'$override': '../../def/tools.json', 'tools': {
            'mine': {'path': '../tools/mine', 'env_file': 'my.env'}, 'abs': {'path': '/opt/t'},
            'dir': {'path': {'$env': 'AOS_HOME', '$path': '/lib/x'}}, 'off': None}}))
        (self.src / 'hooks.json').write_text(json.dumps({'hooks': {'h': {'event': 'after_tool', 'handler': 'hooks/h'}, 'off': None}}))
        (self.src / 'llm.json').write_text('{"model": "luna"}\n')
        (self.src / 'system.txt').write_text('You are Pat.\n')
        for name in ('goal.json', 'stage.txt', 'history_removed.jsonl', 'observed.jsonl'):
            (self.src / name).write_text('{}\n')
        (self.src / 'tools' / 'todo').mkdir(parents=True)
        (self.src / 'tools' / 'todo' / 'todo.json').write_text('{}')
        got = fork_copy.copy_stack(str(self.defn), str(self.src), str(self.dst))
        self.assertEqual(got, {'messages': 2, 'filled': 1, 'files': ['tools.json', 'llm.json', 'hooks.json', 'system.txt']})
        hist = [json.loads(l) for l in (self.dst / 'history.jsonl').read_text().splitlines()]
        self.assertEqual(hist[0]['content'], 'secret')
        self.assertEqual(hist[-1], {'role': 'tool', 'tool_call_id': 'x', 'content': fork_copy.OWN_CALL})
        tools = json.loads((self.dst / 'tools.json').read_text())
        for value, original in ((tools['$override'], '../../def/tools.json'), (tools['tools']['mine']['path'], '../tools/mine'),
                                (tools['tools']['mine']['env_file'], 'my.env')):
            self.assertEqual(os.path.normpath(self.dst / value), os.path.normpath(self.src / original))
        self.assertEqual(tools['tools']['abs'], {'path': '/opt/t'})
        self.assertEqual(tools['tools']['dir'], {'path': {'$env': 'AOS_HOME', '$path': '/lib/x'}})
        self.assertIsNone(tools['tools']['off'])
        hooks = json.loads((self.dst / 'hooks.json').read_text())
        self.assertEqual(os.path.normpath(self.dst / hooks['hooks']['h']['handler']), os.path.normpath(self.src / 'hooks/h'))
        self.assertEqual((self.dst / 'llm.json').read_text(), '{"model": "luna"}\n')
        self.assertEqual((self.dst / 'system.txt').read_text(), 'You are Pat.\n')
        left = sorted(str(p.relative_to(self.dst)) for p in self.dst.rglob('*'))
        self.assertEqual(left, sorted(['history.jsonl', 'tools.json', 'llm.json', 'hooks.json', 'system.txt']))

    def test_no_history_declared_or_no_declaration(self):
        (self.defn / 'interfaces.json').write_text(json.dumps({'aos-agent': {'tools': 'tools.json'}}))
        with self.assertRaises(fork_copy.ForkCopyBad) as e:
            fork_copy.copy_stack(str(self.defn), str(self.src), str(self.dst))
        self.assertEqual(e.exception.code, 'HistoryMissing')
        (self.defn / 'interfaces.json').write_text('{}')
        with self.assertRaises(fork_copy.ForkCopyBad) as e:
            fork_copy.declaration(str(self.defn))
        self.assertEqual(e.exception.code, 'InterfaceMissing')
        (self.defn / 'interfaces.json').write_text(json.dumps({'aos-agent': {'history': '../h.jsonl'}}))
        with self.assertRaises(fork_copy.ForkCopyBad) as e:
            fork_copy.copy_stack(str(self.defn), str(self.src), str(self.dst))
        self.assertEqual(e.exception.code, 'InterfaceBad')

    def test_not_an_fsm_body(self):
        """eca 的 history 只有 user／assistant 文字、沒有叫到一半的 tool call＝BodyUnsupported，叫它用 subagent；什麼都不寫。"""
        for history in ('', json.dumps({'role': 'user', 'content': 'hi'}) + '\n',
                        json.dumps({'role': 'user', 'content': 'q'}) + '\n' + json.dumps({'role': 'assistant', 'content': 'a'}) + '\n',
                        json.dumps({'role': 'assistant', 'tool_calls': [{'id': 'x'}]}) + '\n'
                        + json.dumps({'role': 'tool', 'tool_call_id': 'x', 'content': 'done'}) + '\n'):
            with self.subTest(history=history):
                (self.src / 'history.jsonl').write_text(history)
                with self.assertRaises(fork_copy.ForkCopyBad) as e:
                    fork_copy.copy_stack(str(self.defn), str(self.src), str(self.dst))
                self.assertEqual(e.exception.code, 'BodyUnsupported')
                self.assertIn('use subagent', str(e.exception))
                self.assertEqual(list(self.dst.iterdir()), [])

    def test_no_own_settings(self):
        (self.src / 'history.jsonl').write_text(json.dumps({'role': 'assistant', 'tool_calls': [{'id': 'x'}]}) + '\n')
        got = fork_copy.copy_stack(str(self.defn), str(self.src), str(self.dst))
        self.assertEqual(got, {'messages': 1, 'filled': 1, 'files': []})


if __name__ == '__main__':
    unittest.main()
