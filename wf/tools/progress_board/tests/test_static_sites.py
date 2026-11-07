"""Verify read-only mounted files, traversal refusal, Host validation, and HTTP methods."""
import functools
import http.client
import http.server
import io
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from static_sites import StaticSiteHandlerMixin


class Handler(StaticSiteHandlerMixin, http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class StaticSiteTests(unittest.TestCase):
    def test_http_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site = root / 'site'
            site.mkdir()
            (site / 'index.html').write_text('<h1>測試</h1>', encoding='utf-8')
            (site / 'round1.html').write_text('round one')
            (site / 'assets').mkdir()
            (site / 'assets/style.css').write_text('body{}')
            (root / 'secret.txt').write_text('secret')
            (site / 'escape.txt').symlink_to(root / 'secret.txt')
            cfg = {'sites': [{'mount': 'arknights', 'dir': str(site)}]}
            with patch('static_sites.load_config', return_value=cfg):
                try:
                    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
                        functools.partial(Handler, directory=str(root)))
                except PermissionError:
                    server = None
                if server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    port = server.server_port
                    def request(method, path, host=None):
                        conn = http.client.HTTPConnection('127.0.0.1', port)
                        conn.request(method, path, headers={'Host': host or f'127.0.0.1:{port}'})
                        response = conn.getresponse()
                        result = response.status, dict(response.getheaders()), response.read()
                        conn.close()
                        return result
                else:
                    port = 8765
                    def request(method, path, host=None):
                        class Connection:
                            output = b''
                            def makefile(self, *args):
                                return io.BytesIO(f'{method} {path} HTTP/1.0\r\nHost: {host or "127.0.0.1:8765"}\r\nContent-Length: 0\r\n\r\n'.encode())
                            def sendall(self, data):
                                self.output += data
                        connection = Connection()
                        Handler(connection, ('127.0.0.1', 1), types.SimpleNamespace(server_port=port), directory=str(root))
                        raw_headers, body = connection.output.split(b'\r\n\r\n', 1)
                        rows = raw_headers.decode().split('\r\n')
                        return int(rows[0].split()[1]), dict(row.split(': ', 1) for row in rows[1:]), body
                try:
                    status, headers, body = request('GET', '/arknights/index.html')
                    self.assertEqual(status, 200)
                    self.assertIn('測試'.encode(), body)
                    self.assertEqual(headers['Content-Type'], 'text/html; charset=utf-8')
                    status, head_headers, body = request('HEAD', '/arknights/index.html')
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b'')
                    self.assertEqual(head_headers['Content-Length'], headers['Content-Length'])
                    for path in ('/arknights/round1.html', '/arknights/assets/style.css', '/arknights/'):
                        self.assertEqual(request('GET', path)[0], 200)
                    for path in ('/arknights/missing.html', '/arknights/assets/'):
                        self.assertEqual(request('GET', path)[0], 404)
                    for path in ('/arknights/../secret.txt', '/arknights/%2e%2e/secret.txt',
                                 '/arknights/%252e%252e%252fsecret.txt', '/arknights/escape.txt',
                                 '/arknights/..%5csecret.txt'):
                        self.assertEqual(request('GET', path)[0], 403, path)
                    for method in ('GET', 'HEAD'):
                        self.assertEqual(request(method, '/arknights/index.html', 'attacker.invalid')[0], 403)
                        self.assertEqual(request(method, '/', 'attacker.invalid')[0], 403)
                    self.assertEqual(request('POST', '/arknights/index.html')[0], 405)
                    self.assertEqual((root / 'secret.txt').read_text(), 'secret')
                    self.assertEqual((site / 'round1.html').read_text(), 'round one')
                finally:
                    if server:
                        server.shutdown()
                        server.server_close()
                        thread.join()


if __name__ == '__main__':
    unittest.main()
