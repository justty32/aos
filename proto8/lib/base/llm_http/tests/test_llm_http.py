"""llm_http 金鑰：--key-env 變數沒設或空＝不帶 Authorization 照打、401 才提沒設；設了照帶；壞字＝KeyBad 送出前擋（11-10 夜）。"""

import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"
VAR = "LLM_HTTP_TEST_KEY"
REPLY = {"choices": [{"message": {"role": "assistant", "content": "hi"}}], "model": "m"}


class FakeEndpoint(http.server.BaseHTTPRequestHandler):
    """本機假端點：記下收到的標頭；server.status 決定回 200 還是拒絕。"""

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.seen.append(dict(self.headers))
        if self.server.status == 200:
            body = json.dumps(REPLY).encode()
        else:
            body = b'{"error": "no key"}'
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class LlmHttpKeyTest(unittest.TestCase):
    def setUp(self):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), FakeEndpoint)
        self.server.seen, self.server.status = [], 200
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def call(self, key=None, key_env=True):
        env = {k: v for k, v in os.environ.items() if k != VAR}
        if key is not None:
            env[VAR] = key
        args = {"endpoint": {"url": self.url, "model": "m"}, "request": {"messages": [{"role": "user", "content": "hi"}]}}
        argv = [str(ENTRY)] + (["--key-env", VAR] if key_env else [])
        r = subprocess.run(argv, input=json.dumps(args), text=True, capture_output=True, env=env, timeout=30)
        return r.returncode, r.stdout.strip(), r.stderr.strip()

    def auth(self):
        return [h.get("Authorization") for h in self.server.seen]

    def test_unset_sends_no_header(self):
        code, out, err = self.call()
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["message"]["content"], "hi")
        self.assertEqual(err, "")                          # 安靜：不印 warning
        self.assertEqual(self.auth(), [None])

    def test_empty_sends_no_header(self):
        code, out, err = self.call(key="")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.auth(), [None])

    def test_set_sends_bearer(self):
        code, out, err = self.call(key="sk-abc123")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.auth(), ["Bearer sk-abc123"])

    def test_bad_key_blocked_before_sending(self):
        for bad in ("填你的金鑰", "sk-abc\n", "sk abc"):
            code, out, err = self.call(key=bad)
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("llm_http: error: KeyBad environment variable %s (--key-env)" % VAR), out)
            self.assertNotIn(bad.strip(), out)             # 不印金鑰內容
            self.assertNotIn("bad url", out)
        self.assertEqual(self.server.seen, [])

    def test_401_without_key_names_variable(self):
        self.server.status = 401
        code, out, err = self.call()
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("llm_http: error: EndpointFailed HTTP 401 (the endpoint refused the request "
                                       "and may need a key: environment variable %s (--key-env) is not set)" % VAR), out)

    def test_401_with_key_says_refused_key(self):
        self.server.status = 401
        code, out, err = self.call(key="sk-wrong")
        self.assertEqual(code, 1)
        self.assertIn("HTTP 401 (the endpoint refused the key from %s)" % VAR, out)
        self.assertNotIn("sk-wrong", out)
        self.assertNotIn("not set", out)

    def test_other_status_does_not_mention_key(self):
        self.server.status = 500
        code, out, err = self.call()
        self.assertEqual(code, 1)
        self.assertNotIn(VAR, out)


if __name__ == "__main__":
    unittest.main()
