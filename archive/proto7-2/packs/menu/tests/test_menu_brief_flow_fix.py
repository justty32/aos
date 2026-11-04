"""MN3 審查 3：真的由選檔走完 K=2／3／4 的逐段交件。"""
import json
import subprocess
import sys
from unittest.mock import Mock
from menucase import MenuCase, PACK, read_json
from aos7_menu import load, new_state, after, step, view
from aos7_menu_check import brief_sections
from aos7_menu_run import prompt

EXAMPLE = PACK / 'examples/aos-tool'


class MenuBriefFlowFix(MenuCase):
    def test_every_work_reaches_ai_in_real_code_chain_and_absent_parts_skip(self):
        menu = load(read_json(str(EXAMPLE / 'menu.json')),
                    read_json(str(PACK / 'tools.json')))
        for count in (2, 3, 4):
            with self.subTest(count=count):
                # 800-character indivisible entries force exactly one entry per
                # section; two entries alone already exceed the 1500 limit.
                work = ['需求原文 %d：' % i + chr(0x7532 + i) * 800
                        for i in range(1, count + 1)]
                req = dict(v=1, rid='flow%d' % count, kind='aos-tool', name='flow',
                           task='逐段流程', goal='原文送到每一步',
                           scope={'only': ['packs/flow/'], 'not': [], 'max_files': 8},
                           work=work, accept=['原文完整'], tools=[], deliver='交整份')
                request = self.node / ('request%d.json' % count)
                request.write_text(json.dumps(req, ensure_ascii=False), encoding='utf-8')
                built = subprocess.run([sys.executable, '-B', str(EXAMPLE / 'build.py'),
                                        'brief', str(request)], capture_output=True,
                                       text=True, timeout=30)
                self.assertEqual(built.returncode, 0, built.stderr)
                parsed = brief_sections(built.stdout)
                self.assertEqual([key for key in parsed if key.startswith('work')],
                                 ['work%d' % i for i in range(1, count + 1)])
                directory = self.node / ('run%d' % count)
                directory.mkdir()
                state = new_state(menu, 'flow%d' % count, {'name': 'flow'},
                                  built.stdout, 'hash')
                seen, prompts, writes = [], [], []
                fake_ai = Mock(side_effect=lambda layer, text:
                               '選：3' if layer == 'which' else '選：1\n格：# complete file\n')

                # Treat every ask returned by view as an AI call. Never assign
                # state.layer: transitions must all go through step and after.
                def answer():
                    nxt = view(menu, state)
                    self.assertEqual(nxt['kind'], 'ask')
                    seen.append(nxt['layer'])
                    prompts.append(prompt(menu, state, directory))
                    return fake_ai(nxt['layer'], prompts[-1])

                self.assertEqual(state['layer'], 'which')
                state, nxt = step(menu, state, answer())
                while state['layer'] != 'which':
                    self.assertLessEqual(len(seen), 5, 'code chain did not return to which')
                    state, nxt = step(menu, state, answer())
                    self.assertEqual(nxt['kind'], 'act')
                    act = nxt['act']
                    self.assertEqual(act['write'], 'out/packs/flow/aos7_flow.py')
                    target = directory / act['write']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(act['text'], encoding='utf-8')
                    writes.append(state['layer'])
                    state, nxt = after(menu, state, {'rc': 0})
                    self.assertEqual(nxt['kind'], 'ask')
                seen.append(state['layer'])
                prompts.append(prompt(menu, state, directory))

                expected = ['code'] + ['code%d' % i for i in range(2, count + 1)]
                self.assertEqual(seen, ['which', *expected, 'which'])
                self.assertEqual(writes, expected)
                called_layers = [call.args[0] for call in fake_ai.call_args_list]
                self.assertEqual(called_layers, ['which', *expected])
                for item in work:
                    self.assertTrue(any(item in text for text in prompts),
                                    'work original never reached an AI prompt')
                for i in range(count + 1, 5):
                    self.assertNotIn('code%d' % i, seen, 'absent section called AI')
                    self.assertNotIn('code%d' % i, called_layers, 'absent section called AI')
                    self.assertNotIn('code%d' % i, writes, 'absent section wrote a file')
                self.assertIn('packs/flow/aos7_flow.py', state['done'])
