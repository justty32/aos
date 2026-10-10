"""LiteLLM 金鑰只經 daemon／runner 環境送到 HTTP，不寫任務證據；全程本地假伺服器。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import patch

from base import DaemonCase, TOP
from aos7_fs import read_json, write_json

BUDGET = os.path.join(TOP, "packs", "budget", "bin", "aos7-budget")
LLMCALL = os.path.join(TOP, "packs", "llmcall", "bin", "aos7-llmcall")

# URL 與檔案位置不是秘密，可以放 argv；金鑰由任務繼承，絕不印出或寫檔。
CALLER = '''import os, subprocess, sys
sys.path.insert(0, sys.argv[1])
import aos7_budget as bg
assert bg.ledger_running(bg.Bud("budget/llm"), wait=10), "帳任務未起動"
assert not any(k in os.environ for k in ("AOS7_FOO", "AOS7_SUBROOT", "AOS7_TEST_PROBE", "AOS7_LITELLM_URL"))
os.environ["AOS7_LITELLM_URL"] = sys.argv[2]
sys.exit(subprocess.run([sys.executable, "-B", sys.argv[3], "call", "budget/llm",
    "--holder", "probe", "--call", "key", "--request", "request.json",
    "--reserve", "20", "--deadline", "5"], timeout=10).returncode)
'''


class TestDaemonEnvKey(DaemonCase):
    """〔core〕daemon 起的任務真的送出 Authorization，且證據完全不含金鑰。"""

    def setUp(self):
        with patch("base.PREFIX", "fx1-a-key-"):
            super().setUp()

    def test_daemon_key_reaches_litellm_without_persisting(self):
        headers, paths = [], []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                paths.append(self.path)
                headers.append(self.headers.get("Authorization"))
                self.rfile.read(int(self.headers["Content-Length"]))
                body = json.dumps({"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                                   "usage": {"total_tokens": 7}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .02})
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%d/v1" % server.server_port
        node = self.mknode("a", [
            {"name": "budget-llm", "mode": "keep", "argv": [sys.executable, "-B", BUDGET, "ledger", "budget/llm"]},
            {"name": "probe", "mode": "once", "argv": [sys.executable, "-B", "-c", CALLER,
             os.path.join(TOP, "packs", "budget"), url, LLMCALL]}], interval_ms=100)
        write_json(os.path.join(node, "budget", "llm", "grant.json"), {
            "v": 1, "grant": "key-test", "budget": "llm", "holder": "probe", "resource": "llm.tokens",
            "gateway": "llm.litellm", "amount": 100, "clock": "completed_tock", "from": 0,
            "until": 1000, "delegate": False})
        write_json(os.path.join(node, "request.json"), {
            "litellm": {"model": "local-test", "messages": [{"role": "user", "content": "回 OK"}]}})
        init = subprocess.run([sys.executable, "-B", BUDGET, "init", "budget/llm"], cwd=node,
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(init.returncode, 0, init.stderr)
        aosd = Path(self.root, ".aosd")
        aosd.mkdir()
        (aosd / "log.on").touch()
        # 錯端點也放在 daemon 環境，確認核心仍擋掉 URL，任務才使用 argv 指定的端點。
        daemon = self.start_daemon(register=("a",), env={"AOS7_LITELLM_KEY": "fx1-test-key",
            "AOS7_LITELLM_URL": "http://example.invalid/v1", "AOS7_FOO": "1", "AOS7_SUBROOT": "/nope",
            "AOS7_TEST_PROBE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        ended = self.wait_ended(node, "probe", 1, timeout=15)
        self.assertEqual(ended["code"], 0, "llmcall 任務未完成")
        self.stop_daemon(daemon)
        self.assertTrue((aosd / "log.jsonl").is_file(), "未產生 daemon 日誌")
        self.assertEqual(paths, ["/v1/chat/completions"])
        self.assertTrue(headers == ["Bearer fx1-test-key"], "HTTP 未收到 daemon 環境中的金鑰")
        receipt = read_json(os.path.join(node, "llmcall", "llm", "key", "receipt.json"))
        self.assertEqual((receipt["text"], receipt["used"], receipt["billing"]), ("OK", 7, "final"))
        birth = self.birth(node, "probe")
        self.assertNotIn("env", birth)
        for path in Path(self.root).rglob("*"):
            if path.is_file():
                self.assertFalse(b"fx1-test-key" in path.read_bytes(), str(path.relative_to(self.root)))


if __name__ == "__main__":
    unittest.main()
