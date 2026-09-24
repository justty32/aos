"""第三波 W3-2：aos-agent compact --summarize（spec/agent/compact-summarize.md）。

單元測試不打真模型：patch aos_llm_ask.ask。
"""
import io
import json
import os
import unittest
from unittest.mock import patch

import aos_agent_compact as compact_api
import aos_agent_context as context_api
import aos_agent_info as info_api
import aos_llm_ask
from aos_agent_home import AgentError
import test_agent_memory as memory
from test_agent_memory import MemoryBase, call, rounds, tree


def talk(n):
    """n 輪：長的原話（帶檔名與數字）→ read 一個 40 行的檔 → 長的回話。keep 1、上限 2300 會封出一段有本體的摘要。"""
    h = []
    for r in range(n):
        cid = 'c%d' % r
        h += [{'role': 'user', 'content': '第 %d 個問題：讀 long%d.txt，我有 %d 隻貓。' % (r, r, r + 3) + '說明' * 300},
              {'role': 'assistant', 'content': '', 'tool_calls': [call(cid, 'read', '{"path": "long%d.txt"}' % r)]},
              {'role': 'tool', 'tool_call_id': cid, 'content': '\n'.join('第 %d 行 內容' % i for i in range(40))},
              {'role': 'assistant', 'content': '共 40 行。' + '回話' * 300}]
    return h


def fake_ask(mode='good', calls=None):
    """假的 ask：good＝只留關鍵詞（一定比原文短）；long＝原文抄兩遍；lose＝丟掉檔名；fail＝EngineFailed。"""
    def ask(system, user, *, alias=None, env=None, max_tokens=None):
        if calls is not None:
            calls.append({'system': system, 'user': user, 'alias': alias, 'max_tokens': max_tokens})
        if mode == 'fail':
            raise AgentError('EngineFailed', 'HTTP 502：壞了')
        if mode == 'timeout':
            raise AgentError('Timeout', 'HTTP 等了 1 ms 仍未完成')
        words = compact_api.keywords(user.split('\n'))
        text = {'good': '使用者問了幾個問題；關鍵：' + ' '.join(words),
                'fence': '```\n使用者問了幾個問題；關鍵：' + ' '.join(words) + '\n```',
                'long': user + '\n' + user,
                'lose': '使用者問了幾個問題；關鍵：' + ' '.join(w for w in words if w != 'long0.txt'),
                'aos': '[aos 已封存] ' + ' '.join(words)}[mode]
        return {'text': text, 'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
                'ms': 7, 'alias': alias, 'model': 'real-small'}
    return ask


class KeywordTests(unittest.TestCase):
    def test_keywords(self):
        body = ['第 1 輪', '  使用者：用 read 讀 /work/a/long.txt，告訴我 3 件事、幾行', '  呼叫 read {"path": "x/b.py"}',
                '  結果 read（40 行）：', '    第 1 行 other.md', '  回話：共 40 行', '第 2 輪',
                '  使用者：記住 12345…', '  工具：ls（7 行）、date（1 行）']
        self.assertEqual(compact_api.keywords(body), ['long.txt', '3', 'b.py', '40', '7', '1'])

    def test_check_summary(self):
        body = ['第 1 輪', '  使用者：讀 long.txt 告訴我幾行，還有 3 件事', '  結果 read（40 行）：', '    ' + 'x' * 200]
        self.assertIsNone(compact_api.check_summary(body, '使用者叫我讀 long.txt（40 行），有 3 件事。'))
        self.assertIn('丟了關鍵詞：40', compact_api.check_summary(body, '讀了 long.txt 有 3 件事，400 行'))
        self.assertIn('丟了關鍵詞：long.txt', compact_api.check_summary(body, '讀了檔（40 行），3 件事'))
        self.assertIn('沒有比原摘要短', compact_api.check_summary(body, '\n'.join(body) + ' long.txt 40 3'))
        self.assertIn('空的', compact_api.check_summary(body, '  '))
        self.assertIn('[aos', compact_api.check_summary(body, '[aos 已封存 long.txt 40 3'))

    def test_clean_strips_fence(self):
        self.assertEqual(compact_api._clean('```text\n一句話\n```'), '一句話')
        self.assertEqual(compact_api._clean('  一句話 \n'), '一句話')


class SummarizeTests(MemoryBase):
    LIMIT = '2300'

    def setUp(self):
        super().setUp()
        self.original = talk(5)
        self.history(self.original)
        self.llm = self.root / 'llm.json'
        self.put(self.llm, {'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {'small': {'endpoint': 'http://127.0.0.1:9/v1', 'model': 'real-small'},
                                       'big': {'endpoint': 'http://127.0.0.1:9/v1', 'model': 'real-big'}}})
        self.llm_env = {'AOS_LLM_CONFIG': str(self.llm)}

    def run_compact(self, *extra, mode='good', env=None, calls=None):
        with patch.object(aos_llm_ask, 'ask', fake_ask(mode, calls)):
            return self.cli('compact', '--keep-rounds', '1', '--max-tokens', self.LIMIT, *extra,
                            env=self.llm_env if env is None else env)

    def mechanical(self):
        """同樣選項的機械版結果（在一份複本上算）。"""
        return compact_api.plan(self.original, keep_rounds=1, max_tokens=int(self.LIMIT),
                                archive='prompts/archive/%s.json' % compact_api.sha_of(
                                    (self.base / 'prompts/history.json').read_bytes()))['history']

    def sealed(self, history):
        return [m for m in history if m['role'] == 'user' and m['content'].startswith(compact_api.SEALED)]

    def usage(self):
        path = self.base / 'log/usage.jsonl'
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []

    def test_good_summary_replaces_middle_only(self):
        mech = self.mechanical()
        calls = []
        code, out = self.run_compact('--summarize', calls=calls)
        self.assertEqual(code, 0, out + self.err.getvalue())
        history = self.history()
        compact_api.check_pairs(history)
        info_api.load(self.base, env={})
        [new], [old] = self.sealed(history), self.sealed(mech)
        nl, ol = new['content'].split('\n'), old['content'].split('\n')
        self.assertEqual(nl[0], ol[0].replace('，下面是機械摘要：', '，下面是模型濃縮的摘要：'))   # 開頭：封幾輪幾則照舊
        self.assertEqual(nl[-1], ol[-1])                                                     # 結尾那句照舊
        self.assertTrue(nl[1].startswith('使用者問了幾個問題'))
        self.assertLess(len(new['content']), len(old['content']))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['alias'], 'small')                    # 預設＝agent 自己的 llm.model
        self.assertEqual(calls[0]['user'], '\n'.join(ol[1:-1]))           # 只送中間
        # 其他訊息跟機械版一樣
        self.assertEqual([m for m in history if m is not new and m != new], [m for m in mech if m != old])
        self.assertIn('--summarize：1 段封存摘要，用了模型版 1 段', out)
        ev = self.events()[-1]
        self.assertEqual(ev['ev'], 'compact')
        self.assertEqual((ev['summarize']['segments'], ev['summarize']['used'], ev['summarize']['prompt_tokens']),
                         (1, 1, 100))
        self.assertEqual(ev['after']['tokens'], context_api.history_tokens(history))
        [row] = self.usage()
        self.assertEqual((row['batch'], row['alias'], row['model'], row['usage']['prompt_tokens']),
                         ('compact-summarize-' + ev['id'], 'small', 'real-small', 100))

    def test_fence_is_stripped(self):
        code, out = self.run_compact('--summarize', mode='fence')
        self.assertEqual(code, 0)
        self.assertNotIn('```', self.sealed(self.history())[0]['content'])

    def test_model_flag(self):
        calls = []
        self.assertEqual(self.run_compact('--summarize', '--model', 'big', calls=calls)[0], 0)
        self.assertEqual(calls[0]['alias'], 'big')
        self.assertEqual(self.usage()[0]['alias'], 'big')

    def fallback_case(self, mode, why):
        mech = self.mechanical()
        code, out = self.run_compact('--summarize', mode=mode)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.history(), mech)                  # 退回機械版，照樣壓縮
        self.assertIn(why, out)
        ev = self.events(dedupe=False)[-1]
        self.assertEqual(ev['summarize']['used'], 0)
        return ev, out

    def test_too_long_falls_back(self):
        ev, out = self.fallback_case('long', '沒有比原摘要短')
        self.assertIn('退回機械摘要：第 1 段', out)
        self.assertEqual(len(self.usage()), 1)                  # 模型有回就記用量

    def test_lost_keyword_falls_back(self):
        ev, _ = self.fallback_case('lose', '丟了關鍵詞：long0.txt')
        self.assertEqual(ev['summarize']['fallback'], ['第 1 段：丟了關鍵詞：long0.txt'])

    def test_aos_marker_falls_back(self):
        self.fallback_case('aos', '[aos')

    def test_engine_failure_still_compacts(self):
        for mode, code_name in (('fail', 'EngineFailed'), ('timeout', 'Timeout')):
            with self.subTest(mode=mode):
                self.history(self.original)
                ev, out = self.fallback_case(mode, '模型出錯，整次退回機械摘要（照樣壓縮了）：' + code_name)
                self.assertEqual(ev['summarize']['error'][:len(code_name)], code_name)
                self.assertEqual(self.usage(), [])              # 沒拿到 2xx 就沒有用量可記

    def test_several_segments_each_checked(self):
        """兩段封存（中間隔著沒做完的任務那種不封的輪）：每段各自檢查；一段不過只退那一段。"""
        mech_parts = compact_api.plan(self.original, keep_rounds=1, max_tokens=int(self.LIMIT),
                                      archive='x')
        self.assertEqual(len(self.sealed(mech_parts['history'])), 1)
        # 直接測 summarizer：做一份有兩段新摘要的「機械版」
        h = self.mechanical()
        [seg] = self.sealed(h)
        other = dict(seg, content=seg['content'].replace('第 1 輪', '第 9 輪'))
        after = [seg, {'role': 'assistant', 'content': '中間'}, other]
        answers = iter(['短短的：' + ' '.join(compact_api.keywords(seg['content'].split('\n')[1:-1])), 'x'])

        def ask(system, user, **kw):
            return {'text': next(answers), 'usage': None, 'ms': 1, 'alias': 'small', 'model': 'm'}
        with patch.object(aos_llm_ask, 'ask', ask):
            out, rep = compact_api.make_summarizer(self.base, {}, 'small')([], after, 'abc')
        self.assertEqual((rep['segments'], rep['used']), (2, 1))
        self.assertTrue(out[0]['content'].split('\n')[1].startswith('短短的'))
        self.assertEqual(out[2], other)
        self.assertEqual(rep['fallback'][0][:5], '第 2 段')

    def test_old_digests_not_resent(self):
        """記憶裡本來就有的封存摘要不再送模型（只濃縮這次生的）。"""
        h = self.mechanical()
        out, rep = compact_api.make_summarizer(self.base, {}, 'small')(h, h, 'abc')
        self.assertEqual((rep['segments'], out), (0, h))

    def test_dry_run_calls_nothing_writes_nothing(self):
        before = tree(self.base)
        calls = []
        code, out = self.run_compact('--summarize', '--dry-run', calls=calls)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertEqual(tree(self.base), before)
        self.assertIn('dry-run 不叫模型；正式跑會把 1 段封存摘要送模型濃縮', out)

    def test_no_seal_no_call(self):
        calls = []
        with patch.object(aos_llm_ask, 'ask', fake_ask('good', calls)):
            code, out = self.cli('compact', '--keep-rounds', '1', '--summarize', env=self.llm_env)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn('沒有新的封存摘要，沒叫模型', out)

    def test_config_missing_or_bad_alias_changes_nothing(self):
        before = tree(self.base)
        for env, extra, word in (({}, (), 'AOS_LLM_CONFIG'), (self.llm_env, ('--model', 'nope'), 'nope')):
            with self.subTest(word=word):
                calls = []
                code, _ = self.run_compact('--summarize', *extra, env=env, calls=calls)
                self.assertEqual(code, 1)
                self.assertIn(word, self.err.getvalue())
                self.assertEqual(calls, [])
                self.assertEqual(tree(self.base, skip=('.tick.lock',)), [r for r in before])

    def test_usage_errors(self):
        self.assertEqual(self.cli('compact', '--model', 'small', env={})[0], 2)
        self.assertEqual(self.cli('compact', '--prune-archive', '3', '--summarize', env={})[0], 2)

    def test_second_run_is_noop(self):
        self.assertEqual(self.run_compact('--summarize')[0], 0)
        once = self.history()
        calls = []
        code, out = self.run_compact('--summarize', calls=calls)
        self.assertIn('nothing to compact', out)
        self.assertEqual((self.history(), calls), (once, []))

    def test_kill_after_archive_rerun_recovers(self):
        """崩在 archive 寫完、記憶還沒換：記憶是完整舊版；重跑再叫一次模型、照樣縮完。"""
        def boom(step):
            if step == 'compact.archive':
                raise KeyboardInterrupt
        with patch.object(compact_api, '_hook', boom), self.assertRaises(KeyboardInterrupt):
            self.run_compact('--summarize')
        self.assertEqual(self.history(), self.original)
        self.assertEqual(len(list((self.base / 'prompts/archive').glob('*.json'))), 1)
        self.assertEqual(self.run_compact('--summarize')[0], 0)
        self.assertTrue(self.sealed(self.history())[0]['content'].split('\n')[0].endswith('模型濃縮的摘要：'))


class NeverAskOnAutoTests(MemoryBase):
    """tick 自動壓縮與 compact 申請一律不叫模型。"""

    def setUp(self):
        super().setUp()
        self.history(talk(5))
        self.put(self.base / 'info.json', dict(self.info, compact={'max_tokens': 2300, 'keep_rounds': 1}))

    def boom(self, *a, **kw):
        raise AssertionError('自動壓縮不該叫模型')

    def test_tick_auto(self):
        with patch.object(aos_llm_ask, 'ask', self.boom), \
                patch.dict(os.environ, {'AOS_LLM_CONFIG': '/nonexistent/llm.json'}):
            self.assertEqual(self.tick(), 0)
        ev = self.events()[-1]
        self.assertEqual((ev['ev'], ev['auto']), ('compact', True))
        self.assertNotIn('summarize', ev)
        self.assertTrue(self.history()[0]['content'].split('\n')[0].endswith('，下面是機械摘要：'))

    def test_request(self):
        self.put(self.base / 'compact-req/r-1.json', {'id': 'r-1', 'from': 'human', 'at': 'x', 'max_tokens': 2300})
        with patch.object(aos_llm_ask, 'ask', self.boom):
            self.assertEqual(self.tick(), 0)
        self.assertTrue((self.base / 'compact-req/done/r-1.json').exists())
        self.assertNotIn('summarize', self.events()[-1])


del memory  # 只借 MemoryBase，別讓 discover 重跑它的測試


if __name__ == '__main__':
    unittest.main()
