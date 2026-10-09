"""僅綁本機的 LiteLLM 劇本伺服器；完整受理請求後才注入傳輸故障。"""
import json
import queue
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def reply(code, obj_or_bytes, delay=0):
    """延後送出含正確長度的完整回應。"""
    return ("reply", code, obj_or_bytes, delay)


def truncate(code, data, cut):
    """宣告完整長度，只寫指定前綴後斷線。"""
    return ("truncate", code, data, cut)


def close_no_length(code, data):
    """不宣告長度，寫入呼叫者提供的部分內容後關閉。"""
    return ("close", code, data, 0)


def drop(delay=0):
    """受理後不回任何位元組；可先等待以製造逾時。"""
    return ("drop", 0, b"", delay)


def reset():
    """受理後以 SO_LINGER 零秒送出 RST。"""
    return ("reset", 0, b"", 0)


def drip(gap, obj, pieces=4):
    """完整 200 分 pieces 段送出、段間隔 gap：每段都在 socket timeout 內，總時長超過 deadline。"""
    return ("drip", 200, obj, (gap, pieces))


def late(delay, obj):
    """延後送出完整 200，成功寫完才記錄原物件與 monotonic 時間。"""
    return ("late", 200, obj, delay)


def normal(usage=120, finish_reason="stop"):
    """預設模型正常回覆，可指定 token 數與結束原因。"""
    return {"choices": [{"message": {"content": "OK"}, "finish_reason": finish_reason}],
            "usage": {"total_tokens": usage}}


class FakeLiteLLM:
    """可重用、可排隊且停止時不等待睡眠 handler 的本機 HTTP 工具。"""


    def __init__(self):
        self.bodies = []
        self.late_sent = []
        self._steps = queue.Queue()
        self._stopped = threading.Event()
        self._server = None
        self._worker = None

    @property
    def url(self):
        return "http://127.0.0.1:%d/v1" % self._server.server_port

    def plan(self, *steps):
        """依完整請求的受理順序取用劇本，佇列空時回預設正常回應。"""
        for step in steps:
            self._steps.put(step)
        return self

    def start(self):
        """只綁 127.0.0.1 的隨機埠。"""
        fake = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 5             # 半截請求不讓 handler 永遠卡著

            def do_POST(self):
                if self.path != "/v1/chat/completions":
                    self.send_error(404)
                    return
                body = self.rfile.read(int(self.headers["Content-Length"]))
                fake.bodies.append(json.loads(body))
                try:
                    step = fake._steps.get_nowait()
                except queue.Empty:
                    step = reply(200, normal())
                kind, code, obj, arg = step
                if kind in ("reply", "late", "drop") and fake._stopped.wait(arg):
                    return
                self.close_connection = True
                try:
                    if kind == "reset":
                        self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                                   struct.pack("ii", 1, 0))
                        self.connection.close()
                        return
                    if kind == "drop":
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    data = obj if isinstance(obj, bytes) else json.dumps(obj).encode("utf-8")
                    if kind == "drip":
                        gap, pieces = arg
                        head = ("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n"
                                "Connection: close\r\nContent-Length: %d\r\n\r\n" % len(data)).encode("ascii")
                        self.connection.sendall(head)
                        step = -(-len(data) // pieces)
                        for k in range(0, len(data), step):
                            if fake._stopped.wait(gap):
                                return
                            self.connection.sendall(data[k:k + step])
                        fake.late_sent.append((obj, time.monotonic()))
                        return
                    if kind == "late":
                        # 客戶端已關線；合成一次寫入，避免 headers 寫完後的
                        # RST 讓第二次 body 寫入失敗。只記成功 sendall 的回覆。
                        headers = ("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n"
                                   "Connection: close\r\nContent-Length: %d\r\n\r\n" % len(data))
                        self.connection.sendall(headers.encode("ascii") + data)
                        fake.late_sent.append((obj, time.monotonic()))
                        return
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Connection", "close")
                    if kind != "close":
                        self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data[:arg] if kind == "truncate" else data)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._server.block_on_close = False
        self._worker = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": .01}, daemon=True)
        self._worker.start()
        return self

    def stop(self):
        """打斷等待、停止受理並 join 伺服器執行緒。"""
        self._stopped.set()
        self._server.shutdown()
        self._server.server_close()
        self._worker.join()
