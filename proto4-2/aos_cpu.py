#!/usr/bin/env python3
"""aos-cpu：一顆 cpu ＝ 一個 Linux process，反覆執行同一份 inst.json。

    python3 aos_cpu.py DIR [--interval SEC] [--max-runs N] [--inst REL]

一次執行（＝aos 的「一個指令」）＝讀 DIR/<--inst> 那份 JSON 物件，照裡面的
argv／env／cwd／stdin／timeout_ms 叫一次 POSIX 程式，結果寫 DIR/.aos/last.json，
再 append 一行到 DIR/.aos/runs.jsonl。每跑完一次也把自己的近況寫 DIR/.aos/cpu.json。

停止條件只有兩個：跑滿 --max-runs（沒給＝無限），或收到 SIGTERM（跑完這次就退）。
"""
import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time

DEFAULT_INST = os.path.join(".aos", "inst.json")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, obj):
    """先寫 .tmp 再 rename，別人不會讀到半個檔。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_inst(path):
    """讀一份 inst.json。必須是「嚴格一個 JSON 物件」，argv 必填。"""
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("inst.json 必須是一個 JSON 物件")
    argv = obj.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        raise ValueError("inst.json 的 argv 必填，要是非空字串陣列")
    return obj


def run_once(d, tick, inst_rel=DEFAULT_INST):
    """執行一次 inst.json，回傳（也寫進 last.json／runs.jsonl）結果 JSON。"""
    d = os.path.abspath(d)
    last = os.path.join(d, ".aos", "last.json")
    runs = os.path.join(d, ".aos", "runs.jsonl")
    started = now()
    res = {"tick": tick, "exit": None, "signal": None, "stdout": "", "stderr": "",
           "started_at": started, "ended_at": None}
    try:
        inst = load_inst(os.path.join(d, inst_rel))
        cwd = os.path.normpath(os.path.join(d, inst.get("cwd") or "."))
        env = dict(os.environ)
        env.update({k: str(v) for k, v in (inst.get("env") or {}).items()})
        env["AOS_DIR"] = d
        env["AOS_TICK"] = str(tick)
        ms = inst.get("timeout_ms") or 0
        out, err, code = _call(inst["argv"], cwd, env, inst.get("stdin"), (ms / 1000.0) if ms else None)
        res["stdout"], res["stderr"] = out, err
        if code < 0:
            res["signal"] = -code
        else:
            res["exit"] = code
    except Exception as e:                      # 壞 JSON／不是物件／argv 跑不起來：記一條就好，cpu 不炸
        res["error"] = "%s: %s" % (type(e).__name__, e)
    res["ended_at"] = now()
    write_json(last, res)
    append_jsonl(runs, res)
    return res


def _call(argv, cwd, env, stdin_data, timeout_s):
    """跑一次，回 (stdout, stderr, returncode)。逾時＝殺整個 process group，returncode -9。"""
    p = subprocess.Popen(argv, cwd=cwd, env=env, text=True, start_new_session=True,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(stdin_data or "", timeout=timeout_s)
        return out, err, p.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except OSError:
            pass
        out, err = p.communicate()
        return out, err, -9


def main():
    ap = argparse.ArgumentParser(prog="aos-cpu")
    ap.add_argument("dir")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--max-runs", type=int, default=0)
    ap.add_argument("--inst", default=DEFAULT_INST)
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    cpuf = os.path.join(d, ".aos", "cpu.json")

    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(True))

    tick = 0
    while True:
        tick += 1
        run_once(d, tick, a.inst)
        write_json(cpuf, {"pid": os.getpid(), "tick": tick, "dir": d, "interval": a.interval})
        if stop or (a.max_runs and tick >= a.max_runs):
            break
        t0 = time.time()
        while time.time() - t0 < a.interval and not stop:
            time.sleep(0.05)
        if stop:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
