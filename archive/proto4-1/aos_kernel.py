#!/usr/bin/env python3
"""aos-kernel（Python 版）：時鐘。登記一群資料夾，每走一格，輪到的資料夾就
「cd 進去、執行 ./.aos/inst」一次。怎麼執行看那個資料夾的 .aos/config.json。

    python3 aos_kernel.py DIR... [--steps N] [--interval SEC]
    DIR 寫法：[名字=]資料夾[:間隔]

.aos/config.json（可以沒有、可以是 {}；沒設的就默默吞掉）：
    version   1（沒寫＝1；不認識的版本＝錯誤、不跑）
    args      ["a", "b"]      接在 tick 後面的參數，預設 []
    env       {"K": "v"}      加進環境（環境一律繼承；kernel 另給 AOS_TICK、AOS_DIR）
    stdin     "null"|"inherit"|相對路徑     預設 null
    stdout    "null"|"inherit"|相對路徑     預設 null（路徑＝append）
    stderr    "null"|"inherit"|"stdout"|相對路徑   預設 null
    exit      {"ok":[0], "pause":[], "unregister":[]}  沒設＝任何退出碼都不算錯
    user      "bob"           用誰跑（跟現在不同就走 runuser，要 root）
    interval  N               資料夾自己宣告幾格跑一次；register 沒給就用它
    timeout   秒              跑超過就砍掉、算錯誤
"""
import argparse
import json
import os
import subprocess
import sys
import time

INST = ".aos/inst"
CONFIG = ".aos/config.json"


def read_config(d):
    """讀 .aos/config.json。沒有或空的＝{}。壞掉／版本不認識就 raise。"""
    p = os.path.join(d, CONFIG)
    if not os.path.isfile(p):
        return {}
    with open(p, encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return {}
    cfg = json.loads(raw)
    if not isinstance(cfg, dict):
        raise ValueError("config.json 頂層要是物件")
    v = cfg.get("version", 1)
    if v != 1:
        raise ValueError("不認識的 config 版本：%r" % (v,))
    return cfg


def _direct_exec(inst):
    """有執行位、而且開頭是 #! 或 ELF → 直接執行；否則退回 /bin/sh（跟 shell 遇到 ENOEXEC 一樣）。"""
    if not os.access(inst, os.X_OK):
        return False
    with open(inst, "rb") as f:
        head = f.read(4)
    return head.startswith(b"#!") or head.startswith(b"\x7fELF")


def _stdio(d, spec, default, mode):
    """把 config 的 stdin/stdout/stderr 描述變成 subprocess 要的東西。回 (值, 要關的檔)。"""
    if spec is None or spec == "null":
        return default, None
    if spec == "inherit":
        return None, None
    if spec == "stdout":
        return subprocess.STDOUT, None
    f = open(os.path.join(d, spec), mode)
    return f, f


def exec_inst(d, tick):
    """跑一次 <d>/.aos/inst。回 dict：code／mode／ok／action／error。
    ok=False 只有幾種情況：inst 不在、config 壞、runuser 失敗、timeout、或 config 有設 exit 而退出碼不在 ok 裡。"""
    d = os.path.abspath(d)
    inst = os.path.join(d, INST)
    r = {"code": None, "mode": None, "ok": False, "action": None, "error": None}
    if not os.path.isfile(inst):
        r["error"] = "找不到 " + inst
        return r
    try:
        cfg = read_config(d)
    except Exception as e:
        r["error"] = "config.json 壞了：%s" % e
        return r

    argv = [inst, str(tick)] + [str(a) for a in cfg.get("args", [])]
    if _direct_exec(inst):
        r["mode"] = "exec"
    else:
        r["mode"] = "sh"
        argv = ["/bin/sh"] + argv
    user = cfg.get("user")
    if user and user != os.environ.get("USER", ""):
        argv = ["runuser", "-u", user, "--"] + argv

    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in cfg.get("env", {}).items()})
    env["AOS_TICK"] = str(tick)
    env["AOS_DIR"] = d

    opened = []
    try:
        stdin, f = _stdio(d, cfg.get("stdin"), subprocess.DEVNULL, "rb"); opened.append(f)
        stdout, f = _stdio(d, cfg.get("stdout"), subprocess.DEVNULL, "ab"); opened.append(f)
        stderr, f = _stdio(d, cfg.get("stderr"), subprocess.DEVNULL, "ab"); opened.append(f)
        p = subprocess.run(argv, cwd=d, env=env, stdin=stdin, stdout=stdout, stderr=stderr,
                           timeout=cfg.get("timeout"))
        r["code"] = p.returncode
    except subprocess.TimeoutExpired:
        r["error"] = "超過 %s 秒，砍掉了" % cfg.get("timeout")
        return r
    except OSError as e:
        r["error"] = "跑不起來：%s" % e
        return r
    finally:
        for f in opened:
            if f:
                f.close()

    ex = cfg.get("exit")
    if ex is None:                      # 沒設 exit：什麼退出碼都吞掉
        r["ok"] = True
        return r
    code = r["code"]
    if code in ex.get("pause", []):
        r["action"] = "pause"
    elif code in ex.get("unregister", []):
        r["action"] = "unregister"
    if r["action"] or code in ex.get("ok", [0]):
        r["ok"] = True
    else:
        r["error"] = "退出碼 %d" % code
    return r


class Kernel:
    """時鐘。procs 以 name 為 key，每個是 dict：dir/name/interval/paused/runs/last/error。"""

    def __init__(self):
        self.procs = {}
        self.steps = 0
        self.running = False

    def register(self, d, name=None, interval=None):
        d = os.path.abspath(d)
        name = name or os.path.basename(d.rstrip("/"))
        if interval is None:
            try:
                interval = read_config(d).get("interval", 1)
            except Exception:
                interval = 1
        p = {"dir": d, "name": name, "interval": max(1, int(interval)),
             "paused": False, "runs": 0, "last": None, "error": None}
        self.procs[name] = p
        return p

    def unregister(self, name):
        return self.procs.pop(name, None)

    def pause(self, name):
        p = self.procs.get(name)
        if p:
            p["paused"] = True
        return p

    def resume(self, name):
        p = self.procs.get(name)
        if p:
            p["paused"] = False
        return p

    def ls(self):
        return [self.procs[k] for k in sorted(self.procs)]

    def step(self):
        """走一格。回這格跑到的 name 清單。炸了只記在那個 proc，別人照跑。"""
        self.steps += 1
        now = self.steps
        did = []
        for p in self.ls():
            if p["paused"] or now % p["interval"] != 0:
                continue
            did.append(p["name"])
            r = exec_inst(p["dir"], now)
            p["last"] = {"code": r["code"], "mode": r["mode"]}
            if r["ok"]:
                p["error"] = None
                p["runs"] += 1
                if r["action"] == "pause":
                    p["paused"] = True
                elif r["action"] == "unregister":
                    self.procs.pop(p["name"], None)
            else:
                p["error"] = r["error"]
                print("kernel：第 %d 格 %s 炸了：%s" % (now, p["name"], r["error"]), file=sys.stderr)
        return did

    def stop(self):
        self.running = False

    def run(self, steps=None, interval=0):
        """同步連走 steps 格（None＝到有人 stop），格間睡 interval 秒。回實際走了幾格。"""
        self.running = True
        n = 0
        while self.running and (steps is None or n < steps):
            self.step()
            n += 1
            if interval > 0:
                time.sleep(interval)
        self.running = False
        return n


def parse_spec(s):
    """[名字=]資料夾[:間隔] → (dir, name, interval)。間隔只認結尾純數字。"""
    name = None
    if "=" in s:
        name, s = s.split("=", 1)
    interval = None
    if ":" in s and s.rsplit(":", 1)[1].isdigit():
        s, iv = s.rsplit(":", 1)
        interval = int(iv)
    return s, name, interval


def main():
    ap = argparse.ArgumentParser(prog="aos-kernel", description="登記幾個資料夾，一格一格跑它們的 .aos/inst")
    ap.add_argument("dirs", nargs="+", help="[名字=]資料夾[:間隔]")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--interval", type=float, default=0)
    a = ap.parse_args()
    k = Kernel()
    for s in a.dirs:
        k.register(*parse_spec(s))
    n = k.run(a.steps, a.interval)
    print("跑了 %d 格：" % n)
    for p in k.ls():
        print("  %s  runs=%d%s" % (p["name"], p["runs"], ("  error=" + p["error"]) if p["error"] else ""))


if __name__ == "__main__":
    main()
