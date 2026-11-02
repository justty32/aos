"""fake_brain - 測試共用的假 OpenAI 相容 server 與劇本小幫手（不是測試；檔名不叫 test_*）。

11-02 晚從 test_dan.py 原樣搬出來（demo/agent-dan 與 test_dan.py 刪了；test_kai、test_meg、test_pi_tools、
test_file_tools、test_self_improve 原本都從 test_dan import 這幾樣）。"""
import http.server, json, threading

REAL_URL = "http://localhost:4000/v1"   # 家機 LiteLLM；連真模型的案例連不上就 skip


def call(cid, name, arguments):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def tool_reply(*calls):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": list(calls)}}]}


def answer(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


class FakeBrain:
    """假的 OpenAI 相容 server：每次 POST /v1/chat/completions 回劇本的下一個；記下每個 request body。
    劇本一項＝dict（200 回 JSON）或 (狀態碼, 字串)。"""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        brain = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                brain.requests.append(json.loads(body))
                item = brain.script.pop(0) if brain.script else (500, "劇本用完了")
                status, text = (200, json.dumps(item)) if isinstance(item, dict) else item
                if self.path != "/v1/chat/completions":
                    status, text = 404, "path " + self.path
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
