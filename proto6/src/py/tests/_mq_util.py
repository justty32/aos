"""訊息模組系列測試共用：aos-mq 路徑、MQMOD 設定、task() 與 MqCase 基底（第二十五批：多扇門）。"""
import json
import os
import subprocess

from _util import PY
from _ctl_util import CtlCase
from _daemon_util import BIN, CLEAN_ENV, sh


MQ = os.path.join(BIN, "aos-mq")
MQMOD = {"mq": {"S1": "./mq.sock"}}
SUB = {"mq": ["S1"]}                    # 一項訂 S1


def task(script):
    """inst：sh -c script，環境多帶 PY、MQ。"""
    return sh(script, envs={"PY": PY, "MQ": MQ})


class MqCase(CtlCase):

    @property
    def mq_sock(self):
        return os.path.join(self.d, "mq.sock")

    def up_mq(self, insts, interval_ms, modules=None, **top):
        modules = modules or MQMOD
        cfg = self.config(dict({"interval_ms": interval_ms, "modules": modules, "insts": insts}, **top))
        p, out, err = self.start(cfg)
        self.wait_for(lambda: all(self.is_sock(path) for path in modules["mq"].values()))
        return p, out, err

    def mq(self, *args, stdin=None, cwd=None, **env):
        """跑 aos-mq；env 給的變數加在乾淨環境上（給 None＝拿掉）。"""
        e = dict(CLEAN_ENV)
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return subprocess.run([PY, MQ] + list(args), env=e, input=stdin, capture_output=True,
                              text=True, timeout=10, cwd=cwd)

    def put(self, msg, sock=None):
        """往一扇門寄一封（msg 是 JSON 字串），要成功、什麼都不印。"""
        r = self.mq("send", sock or self.mq_sock, msg)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def take(self, inst, cmd="take", sock=None):
        """以 inst 的身分（AOS_DAEMON_INST）從某扇門取（或 peek）自己的信箱。"""
        r = self.mq(cmd, sock or self.mq_sock, AOS_DAEMON_INST=inst)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(l) for l in r.stdout.splitlines()]

    def peek(self, inst, sock=None):
        return self.take(inst, "peek", sock)
