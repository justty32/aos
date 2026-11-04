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
    """假的 ask：good＝只留關鍵詞（一定比原文短）；long＝原文抄兩遍；lose＝丟掉行數 40；fail＝EngineFailed。"""
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
                'lose': '使用者問了幾個問題；關鍵：' + ' '.join(w for w in words if w != '40'),
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
        body = ['第 1 輪', '  使用者：讀 long.txt 告訴我幾行，還有 3 件事', '  呼叫 read {"path": "/w/b.py"}',
                '  結果 read（40 行）：', '    ' + 'x' * 300]
        self.assertIsNone(compact_api.check_summary(body, '讀了 b.py（40 行）。'))
        self.assertIn('丟了關鍵詞：40', compact_api.check_summary(body, '讀了 b.py，400 行'))
        self.assertIn('丟了關鍵詞：40', compact_api.check_summary(body, '讀了 b.py，40.5 行'))   # 完整的數才算
        self.assertIn('丟了關鍵詞：b.py', compact_api.check_summary(body, '讀了檔（40 行）'))
        self.assertIn('沒有比原摘要短', compact_api.check_summary(body, '\n'.join(body) + ' b.py 40'))
        self.assertIn('空的', compact_api.check_summary(body, '  '))
        self.assertIn('[aos', compact_api.check_summary(body, '[aos 已封存 b.py 40'))

    def test_has_whole_numbers(self):
        for text, ok in (('40 行', True), ('共40行', True), ('40.5', False), ('4.40', False), ('400', False),
                         ('結尾 40。', True)):
            self.assertEqual(compact_api._has(text, '40'), ok, text)

    def test_user_lines_kept_verbatim(self):
        """astra M6：「芒果」被模型改成「蘋果」——原話那行原樣在新摘要裡，模型改不到。"""
        body = ['第 1 輪', '  使用者：記住：我最喜歡的水果是芒果。', '  回話：記住了。' + '好' * 100,
                '第 2 輪', '  使用者：讀 a.txt', '  工具：read（3 行）', '  回話：3 行']
        text = '使用者最喜歡蘋果；讀了 a.txt（3 行）'
        self.assertIsNone(compact_api.check_summary(body, text))       # 檢查擋不住改寫，所以原話不給模型改
        new = compact_api.compose(body, text)
        self.assertEqual(new[:3], [compact_api.KEPT_HEAD, '第 1 輪 使用者：記住：我最喜歡的水果是芒果。',
                                   '第 2 輪 使用者：讀 a.txt'])
        self.assertEqual(new[3:], [compact_api.CONDENSED_HEAD, text])

    def test_clean_strips_fence(self):
        self.assertEqual(compact_api._clean('```text\n一句話\n```'), '一句話')
        self.assertEqual(compact_api._clean('  一句話 \n'), '一句話')

    def test_clean_polite_words_around_fence(self):
        # 09-25 收尾 S4：前後一兩句客套話＋一個圍欄＝只取圍欄裡的
        self.assertEqual(compact_api._clean('好的，以下是濃縮後的摘要：\n```\n一句話\n```\n希望有幫助'), '一句話')
        self.assertEqual(compact_api._clean('```markdown\n一句話'), '一句話')        # 沒收尾
        self.assertEqual(compact_api._clean('```'), '')

    def test_clean_keeps_summary_with_code_inside(self):
        # 圍欄外字多（摘要裡夾一段程式）或兩個圍欄：不猜，原樣
        text = '第一段摘要說了很多事情。\n第二段也是。\n```\nprint(1)\n```\n結尾'
        self.assertEqual(compact_api._clean(text), text)
        two = '```\na\n```\n```\nb\n```'
        self.assertEqual(compact_api._clean(two), two)

    def test_clean_review2_m2_meaningful_words_kept(self):
        # 複審 M2：圍欄外的話有意思（不是固定客套話）就不刪，原樣交給檢查
        text = '修改失敗，尚未寫入；以下只是檔名與行數：\n```\na.md 40\n```'
        self.assertEqual(compact_api._clean(text), text)
        self.assertEqual(compact_api._clean('這是摘要：\n```\n一句話\n```'), '一句話')
        self.assertEqual(compact_api._clean("Here's the summary:\n```\none\n```\nHope this helps!"), 'one')
        self.assertEqual(compact_api._clean('好的\n```\n一句話\n```\n以上'), '一句話')
        odd = '好的\n```\n一句話\n```\n另外 b.txt 沒讀到'
        self.assertEqual(compact_api._clean(odd), odd)


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
        self.assertEqual(nl[1], compact_api.KEPT_HEAD)
        users = [l.strip() for l in ol if l.strip().startswith('使用者：')]
        self.assertEqual([l.split(' ', 3)[-1] for l in nl[2:2 + len(users)]], users)   # 原話原樣
        self.assertEqual(nl[2 + len(users)], compact_api.CONDENSED_HEAD)
        self.assertTrue(nl[3 + len(users)].startswith('使用者問了幾個問題'))
        self.assertLess(len(new['content']), len(old['content']))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['alias'], 'small')                    # 預設＝agent 自己的 llm.model
        self.assertEqual(calls[0]['user'], '\n'.join(ol[1:-1]))           # 只送中間
        # 其他訊息跟機械版一樣
        self.assertEqual([m for m in history if m is not new and m != new], [m for m in mech if m != old])
        self.assertIn('--summarize：1 段封存摘要，送了 1 段、用了模型版 1 段', out)
        ev = self.events()[-1]
        self.assertEqual(ev['ev'], 'compact')
        self.assertEqual([ev['summarize'][k] for k in ('planned', 'sent', 'used', 'prompt_tokens')], [1, 1, 1, 100])
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
        ev, _ = self.fallback_case('lose', '丟了關鍵詞：40')
        self.assertEqual(ev['summarize']['fallback'], ['第 1 段：丟了關鍵詞：40'])

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
        self.assertEqual((rep['planned'], rep['sent'], rep['used']), (2, 2, 1))
        self.assertTrue(out[0]['content'].split('\n')[-2].startswith('短短的'))
        self.assertEqual(out[2], other)
        self.assertEqual(rep['fallback'][0][:5], '第 2 段')

    def test_answered_error_still_recorded(self):
        """astra S2：HTTP 2xx 但 message 驗不過（ask 丟錯、例外上帶用量）也照記；預定／實送／採用分開。"""
        [seg] = self.sealed(self.mechanical())
        after = [seg, {'role': 'assistant', 'content': '中間'},
                 dict(seg, content=seg['content'].replace('第 1 輪', '第 9 輪'))]

        def ask(system, user, **kw):
            exc = AgentError('EngineFailed', '模型回覆不合規：role')
            exc.answered, exc.usage, exc.ms, exc.alias, exc.model = True, {'prompt_tokens': 42}, 5, 'small', 'm'
            raise exc
        with patch.object(aos_llm_ask, 'ask', ask):
            out, rep = compact_api.make_summarizer(self.base, {}, 'small')([], after, 'abc')
        self.assertEqual(out, after)
        self.assertEqual([rep[k] for k in ('planned', 'sent', 'used', 'prompt_tokens')], [2, 1, 0, 42])
        [row] = self.usage()
        self.assertEqual((row['batch'], row['usage']), ('compact-summarize-abc', {'prompt_tokens': 42}))

    def test_old_digests_not_resent(self):
        """記憶裡本來就有的封存摘要不再送模型（只濃縮這次生的）。"""
        h = self.mechanical()
        out, rep = compact_api.make_summarizer(self.base, {}, 'small')(h, h, 'abc')
        self.assertEqual((rep['planned'], rep['sent'], out), (0, 0, h))

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
