"""訊息模組系列測試共用：aos-mq 路徑、MQMOD 設定、task() 與 MqCase 基底。"""
import json
import os
import subprocess

from _util import PY
from _ctl_util import CtlCase
from _daemon_util import BIN, CLEAN_ENV, sh


MQ = os.path.join(BIN, "aos-mq")
MQMOD = {"mq": {"socket": "./mq.sock"}}


def task(script):
    """inst：sh -c script，環境多帶 PY、MQ。"""
    return sh(script, envs={"PY": PY, "MQ": MQ})


class MqCase(CtlCase):

    @property
    def mq_sock(self):
        return os.path.join(self.d, "mq.sock")

    def up_mq(self, insts, interval_ms, modules=None, **top):
        cfg = self.config(dict({"interval_ms": interval_ms, "modules": modules or MQMOD, "insts": insts}, **top))
        p, out, err = self.start(cfg)
        self.wait_for(lambda: self.exists("mq.sock"))
        return p, out, err

    def mq(self, *args, stdin=None, **env):
        """跑 aos-mq；env 給的變數加在乾淨環境上（給 None＝拿掉）。"""
        e = dict(CLEAN_ENV, AOS_DAEMON_MQ_SOCKET=self.mq_sock)
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return subprocess.run([PY, MQ] + list(args), env=e, input=stdin, capture_output=True,
                              text=True, timeout=10)

    def take(self, inst, *args, cmd="take"):
        """以 inst 的身分（AOS_DAEMON_INST）取（或 peek）自己的信箱。"""
        r = self.mq(cmd, *args, AOS_DAEMON_INST=inst)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(l) for l in r.stdout.splitlines()]

    def peek(self, inst, *args):
        return self.take(inst, *args, cmd="peek")

    def letter(self, sender, msg, sock=True, to="b.json"):
        """一封信：用 aos-mq 寄的 from_socket 是 self.mq_sock（第二十一批）；直接連 socket 寄的沒帶就是 null。
        to＝收件地址（第二十二批：單寄是收件 inst、全體 "*"、頻道 "#名字"）。"""
        return {"from": sender, "from_socket": self.mq_sock if sock is True else sock, "to": to, "msg": msg}
