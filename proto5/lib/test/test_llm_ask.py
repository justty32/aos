"""aos_llm_ask（第三波 W3-2）：多問一次模型的共用入口——本機假端點，不打真模型。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

import aos_llm_ask as ask
from aos_agent_home import AgentError


class ParseJsonTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(ask.parse_json('{"a": 1}'), {'a': 1})

    def test_fence(self):
        self.assertEqual(ask.parse_json('好的：\n```json\n[1, 2]\n```\n以上'), [1, 2])

    def test_embedded(self):
        self.assertEqual(ask.parse_json('結果是 {"x": "y"} 謝謝'), {'x': 'y'})

    def test_skips_broken_brace(self):
        self.assertEqual(ask.parse_json('{壞掉 然後 {"ok": true}'), {'ok': True})

    def test_bad(self):
        with self.assertRaises(AgentError) as cm:
            ask.parse_json('沒有 JSON')
        self.assertEqual(cm.exception.code, 'BadModelOutput')

    def test_empty(self):
        with self.assertRaises(AgentError):
            ask.parse_json(None)


class PickTest(unittest.TestCase):
    def test_default_first(self):
        cfg = {'models': {'a': {'m': 1}, 'default': {'m': 2}}}
        self.assertEqual(ask.pick(cfg), ('default', {'m': 2}))

    def test_first_when_no_default(self):
        self.assertEqual(ask.pick({'models': {'a': {'m': 1}}})[0], 'a')

    def test_unknown(self):
        with self.assertRaises(AgentError) as cm:
            ask.pick({'models': {'a': {}}}, 'zz')
        self.assertEqual(cm.exception.code, 'UnknownModel')

    def test_empty_models(self):
        with self.assertRaises(AgentError):
            ask.pick({'models': {}})


class AskTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.bodies = []
        self.reply = None
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers['Content-Length'])
                test.bodies.append(json.loads(self.rfile.read(n)))
                out = json.dumps(test.reply or {
                    'choices': [{'message': {'role': 'assistant', 'content': '```json\n{"k": 1}\n```'}}],
                    'usage': {'prompt_tokens': 7, 'completion_tokens': 3}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        cfg = {'_metainfo': {'_type': 'llm_config', '_version': 1},
               'models': {'default': {'endpoint': 'http://127.0.0.1:%d/v1' % self.server.server_port, 'model': 'm1'}}}
        (self.base / 'llm.json').write_text(json.dumps(cfg))
        self.env = {'AOS_LLM_CONFIG': str(self.base / 'llm.json')}

    def test_ask_json(self):
        obj, got = ask.ask_json('系統', '使用者', env=self.env, max_tokens=50)
        self.assertEqual(obj, {'k': 1})
        self.assertEqual(got['usage']['prompt_tokens'], 7)
        self.assertEqual(got['alias'], 'default')
        body = self.bodies[0]
        self.assertEqual(body['model'], 'm1')
        self.assertEqual(body['temperature'], 0)
        self.assertEqual(body['max_tokens'], 50)
        self.assertNotIn('tools', body)
        self.assertEqual([m['role'] for m in body['messages']], ['system', 'user'])
        self.assertIn('prompt 7', ask.usage_line(got))

    def test_no_config(self):
        with self.assertRaises(AgentError) as cm:
            ask.ask('a', 'b', env={})
        self.assertEqual(cm.exception.code, 'ConfigInvalid')

    def test_engine_down(self):
        self.server.shutdown()
        self.server.server_close()
        with self.assertRaises(AgentError) as cm:
            ask.ask('a', 'b', env=self.env)
        self.assertEqual(cm.exception.code, 'EngineFailed')
        self.assertFalse(cm.exception.answered)            # 沒拿到 2xx：沒有用量可記
        self.assertIsNone(cm.exception.usage)

    def test_bad_message_keeps_usage(self):
        """astra S2：2xx 帶 usage、但 message 驗不過——例外上帶著用量，呼叫端照樣記。"""
        self.reply = {'choices': [{'message': {'role': 'user', 'content': 'x'}}], 'usage': {'prompt_tokens': 5}}
        with self.assertRaises(AgentError) as cm:
            ask.ask('a', 'b', env=self.env)
        self.assertEqual(cm.exception.code, 'EngineFailed')
        e = cm.exception
        self.assertEqual((e.answered, e.usage, e.alias, e.model), (True, {'prompt_tokens': 5}, 'default', 'm1'))


class ContextSkipsSummarizeTest(unittest.TestCase):
    """aos-agent context 的「上一次問模型」不算 compact --summarize 那一問。"""
    def test_skip(self):
        import aos_agent_context
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'log').mkdir()
            rows = [{'at': '2026-09-24T10:00:00', 'batch': 'b1', 'usage': {'prompt_tokens': 111}},
                    {'at': '2026-09-24T10:01:00', 'batch': 'compact-summarize-abc', 'usage': {'prompt_tokens': 9}}]
            (Path(d) / 'log' / 'usage.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            self.assertEqual(aos_agent_context.last_usage(d)['prompt'], 111)


if __name__ == '__main__':
    unittest.main()
