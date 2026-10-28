"""hub_ipc - aos-hub 與 aos-hub-kernel 共用的小零件（10-28）：$AOS_HUB 怎麼找、跟 kernel 講一句話。

跟 kernel 講話＝連 $AOS_HUB/kernel.sock（unix socket），送一行 JSON 請求、收一行 JSON 回覆（{"ok": true, ...} 或
{"ok": false, "code": 代號, "error": 原因}）。kernel 沒在跑＝KernelMissing；$AOS_HUB 沒設＝HubMissing（10-28 決定 3、10）。"""
import json, os, socket

SOCK = "kernel.sock"


class Error(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def hub_dir():
    hub = os.environ.get("AOS_HUB")
    if not hub:
        raise Error("HubMissing", "沒設 AOS_HUB（要指向放常駐 kernel 的資料夾）")
    return os.path.abspath(hub)


def ask(req, timeout=60):
    """送一個請求給 kernel、回它的回覆（dict）；kernel 回錯就 raise Error。"""
    path = os.path.join(hub_dir(), SOCK)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        try:
            s.connect(path)
        except OSError:
            raise Error("KernelMissing", "%s 沒有在跑的 aos-hub-kernel（先跑 aos-hub-kernel）" % path)
        s.sendall((json.dumps(req, ensure_ascii=False) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        s.close()
    try:
        rep = json.loads(data.decode())
    except ValueError:
        raise Error("KernelFailed", "kernel 的回覆不是 JSON：%r" % data[:200])
    if not rep.get("ok"):
        raise Error(rep.get("code") or "KernelFailed", rep.get("error") or "")
    return rep
