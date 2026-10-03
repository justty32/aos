"""評估用：批次 tick／tock（不在 repo）。

AOS7_EVAL_MODE：
  base   ＝原樣（每條線每次一個 aos7-tick／aos7-tock 程序）
  btick  ＝tick 批次：daemon 裡一個 batcher，把所有到期要 tick 的線收成一批，開一個 aos7-batch 程序依序做；tock 照原樣
  bboth  ＝tick、tock 都批次（各一個 batcher）
  cheap  ＝不批次，tick／tock 用 python3 -S -I 起
  cfloor ＝不批次，tick／tock 換成極小 C 程式（只做回合數 +1／關回合；只能配空任務，量換語言的下限）
AOS7_BATCH_K：一批最多幾條（0＝不限）；AOS7_BATCH_PAR：同一種動作最多同時幾個批次程序。
"""
import json
import os
import subprocess
import sys
import threading
import time

from aos7_fs import BIN, env_with_bin

MODE = os.environ.get("AOS7_EVAL_MODE", "base")
K = int(os.environ.get("AOS7_BATCH_K", "0") or 0)
PAR = int(os.environ.get("AOS7_BATCH_PAR", "1") or 1)
CFLOOR = os.environ.get("AOS7_CFLOOR_BIN")


class Batcher:
    def __init__(self, prog):
        self.prog = prog
        self.q = []
        self.cv = threading.Condition()
        self.stats = []      # (批大小, 程序 wall ms)
        for _ in range(PAR):
            threading.Thread(target=self.loop, daemon=True, name="batch:" + prog).start()

    def call(self, root, node_id, extra_env, gen):
        req = {"node": node_id, "early": (extra_env or {}).get("AOS7_EARLY"), "ev": threading.Event(),
               "res": None, "root": root, "gen": gen}
        with self.cv:
            self.q.append(req)
            self.cv.notify()
        req["ev"].wait()
        return req["res"]

    def loop(self):
        while True:
            with self.cv:
                while not self.q:
                    self.cv.wait()
                n = len(self.q) if K <= 0 else min(K, len(self.q))
                batch, self.q = self.q[:n], self.q[n:]
            self.run_batch(batch)

    def run_batch(self, batch):
        env = env_with_bin()
        gen = batch[0]["gen"]
        if gen is not None:
            env["AOS7_GEN"] = str(gen)
        t0 = time.monotonic()
        byname = {r["node"]: r for r in batch}
        p = subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-batch"), self.prog, batch[0]["root"]],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        p.stdin.write(json.dumps([{"node": r["node"], "early": r["early"]} for r in batch]))
        p.stdin.close()
        for line in p.stdout:          # 一條做完就交回（不等整批）
            try:
                row = json.loads(line)
            except ValueError:
                continue
            r = byname.pop(row.get("node"), None)
            if r is not None:
                r["res"] = (row.get("rc", 1), row.get("out"), row.get("err", ""))
                r["ev"].set()
        err = p.stderr.read()
        rc = p.wait()
        self.stats.append((len(batch), (time.monotonic() - t0) * 1000))
        sf = os.environ.get("AOS7_BATCH_STATS")
        if sf:
            with open(sf, "a") as f:
                f.write(json.dumps({"prog": self.prog, "n": len(batch), "ms": round((time.monotonic() - t0) * 1000, 2), "rc": rc}) + "\n")
        for r in byname.values():       # 程序死掉時，還沒輪到的線全部算失敗
            r["res"] = (rc if rc else -999, None, "batch process died rc=%s: %s" % (rc, err[-300:]))
            r["ev"].set()


_batchers = {}
_lock = threading.Lock()


def batcher(prog):
    with _lock:
        if prog not in _batchers:
            _batchers[prog] = Batcher(prog)
        return _batchers[prog]


def wants_batch(name):
    return (MODE == "btick" and name == "aos7-tick") or (MODE == "bboth" and name in ("aos7-tick", "aos7-tock"))


def argv_for(name, root, node_id):
    if MODE == "cheap":
        return [sys.executable, "-S", "-I", os.path.join(BIN, name), root, node_id]
    if MODE == "cfloor":
        return [CFLOOR, name, root, node_id]
    return [sys.executable, os.path.join(BIN, name), root, node_id]
