#!/usr/bin/env python3
"""只給測試用的 OpenAI 相容假 endpoint。"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
import time


class Handler(BaseHTTPRequestHandler):
    gets = 0
    posts = 0

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/stats":
            data = json.dumps({"gets": self.gets,
                               "posts": self.posts}).encode()
            self._send_json(data)
            return
        type(self).gets += 1
        if self.path == "/models-404/v1/models":
            self.send_error(404)
            return
        if self.path != "/v1/models":
            self.send_error(404)
            return
        data = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self._send_json(data)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        type(self).posts += 1
        if self.path not in ("/v1/chat/completions",
                             "/models-404/v1/chat/completions"):
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(size))
        content = body["messages"][-1]["content"]
        if content.startswith("slow:"):
            time.sleep(float(content.split(":", 1)[1]))
        if content == "fail:500":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"fake failure")
            return
        if content == "badjson":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"not json")
            return
        model = "other" if content == "model:other" else body["model"]
        text = content.split(":", 1)[1] if content.startswith("echo:") else content
        answer = {
            "id": "fake", "model": model,
            "choices": [{"message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 11, "completion_tokens": 7,
                "total_tokens": 18,
                "prompt_tokens_details": {"cached_tokens": 3},
                "completion_tokens_details": {"reasoning_tokens": 2},
            },
        }
        data = json.dumps(answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(server.server_address[1], flush=True)
    server.serve_forever()
