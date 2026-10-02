"""控制模組系列測試共用：aos-ctl 路徑、CONTROL 設定、時間戳記與 CtlCase 基底。"""
import json
import os
import socket
import stat
import subprocess

from _util import PY
from _daemon_util import BIN, CLEAN_ENV, DaemonCase


CTL = os.path.join(BIN, "aos-ctl")
CONTROL = {"control": {"socket": "./aos.sock"}}
UPTIME = "cut -d' ' -f1 /proc/uptime"         # 精度 0.01 秒，夠用
STAMP = UPTIME + " >> runs"


class CtlCase(DaemonCase):

    @property
    def sock(self):
        return os.path.join(self.d, "aos.sock")

    def up(self, insts, interval_ms, **top):
        """開一個掛了控制模組的 daemon（socket 在 self.d/aos.sock），等 socket 出現。"""
        cfg = self.config(dict({"interval_ms": interval_ms, "modules": CONTROL, "insts": insts}, **top))
        p, out, err = self.start(cfg)
        self.wait_for(lambda: self.exists("aos.sock"))
        return p, out, err

    def send(self, payload, sock=None):
        """直接連 socket 送一行（dict 就 dump、bytes 原樣），回解好的回應。"""
        raw = payload if isinstance(payload, bytes) else (json.dumps(payload) + "\n").encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(sock or self.sock)
            s.sendall(raw)
            if not raw.endswith(b"\n"):
                s.shutdown(socket.SHUT_WR)              # 沒送完一行就關寫的那一邊
            line = s.makefile("rb").readline()
        return json.loads(line)

    def ctl(self, *args, **env):
        """跑 aos-ctl；env 給的變數加在乾淨環境上（給 None＝拿掉）。"""
        e = dict(CLEAN_ENV, AOS_DAEMON_SOCKET=self.sock)
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return subprocess.run([PY, CTL] + list(args), env=e, capture_output=True, text=True, timeout=10)

    def runs(self, rel="runs"):
        """任務寫的時間（秒，浮點）。"""
        if not self.exists(rel):
            return []
        return [float(x) for x in self.read(rel).split()]

    def is_sock(self, rel="aos.sock"):
        try:
            return stat.S_ISSOCK(os.stat(os.path.join(self.d, rel)).st_mode)
        except FileNotFoundError:
            return False

    @staticmethod
    def has(out, text):
        return any(l.endswith(" " + text) for l in list(out))
