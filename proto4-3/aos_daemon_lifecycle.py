"""aos-daemon 的 state 落地、前台主迴圈、收工與 log。"""
import os
import signal
import subprocess
import time

from aos_daemon_entry import TERM_WAIT
from aos_home import write_json

TICK = 0.2              # 主迴圈：多久跑一圈（掃 requests/、推狀態機、收屍）
SAVE = 0.5              # 多久寫一次 state.json


class _Lifecycle:
    def save(self):
        write_json(self.home.statef, {"pid": os.getpid(), "home": self.home.dir,
                                      "runs": {k: r.entry() for k, r in self.table.items()}})

    def serve(self):
        """前台跑到收工為止（背景化是 CLI 的事）。SIGTERM＝跟 `{"op":"stop"}` 一樣。"""
        with open(self.home.pidf, "w") as f:
            f.write(str(os.getpid()))
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, lambda *_: setattr(self, "stopping", True))
        self.say("起來了 pid=%d home=%s" % (os.getpid(), self.home.dir))
        self.save()
        last = 0.0
        try:
            while not self.stopping:
                self.tick()
                if time.monotonic() - last >= SAVE:
                    self.save()
                    last = time.monotonic()
                t0 = time.monotonic()
                while time.monotonic() - t0 < TICK and not self.stopping:
                    time.sleep(0.02)
        finally:
            self.shutdown()

    def shutdown(self):
        """收工：全部 SIGCONT＋SIGTERM，同步等（上限 5 秒），還活著就 SIGKILL 整個 group。

        **這裡可以卡**——收工就是要等大家走乾淨，跟「主迴圈不等人」是兩件事。
        """
        self.say("收工中：%d 個 aos-run 送 SIGTERM" % len(self.table))
        for r in self.table.values():
            r.sig(signal.SIGCONT)                       # 暫停中的要先叫醒才收得到
            r.sig(signal.SIGTERM)
        t0 = time.monotonic()
        while time.monotonic() - t0 < TERM_WAIT:
            if all(not r.alive() for r in self.table.values()):
                break
            time.sleep(0.02)
        for key, r in list(self.table.items()):
            if r.alive():
                r.killpg()
                try:
                    r.proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    pass
            r.join()
            self.say("收工帶走 %s pid=%d exit=%s last=%s"
                     % (key, r.proc.pid, r.code(), r.last_line))
        self.table.clear()
        for f in (self.home.statef, self.home.pidf):
            try:
                os.remove(f)
            except OSError:
                pass
        self.say("收工了 pid=%d" % os.getpid())

    def say(self, s):
        with self._lock:
            try:
                with open(self.home.logf, "a", encoding="utf-8") as f:
                    f.write("%s %s\n" % (time.strftime("%H:%M:%S"), s))
            except OSError:
                pass
