#!/usr/bin/env python3
"""aos-cpu：一顆 cpu ＝ 一個 Linux process，反覆執行同一份 inst.json。

    python3 aos_cpu.py DIR [--interval SEC] [--max-runs N] [--time-limit SEC] [--inst REL]

一次執行（＝aos 的「一個指令」）＝讀 DIR/<--inst> 那份 JSON 物件（格式與指示詞在
aos_inst.py），照裡面的八個欄位叫一次 POSIX 程式，結果寫 DIR/.aos/last.json，再
append 一行到 DIR/.aos/runs.jsonl。每跑完一次也把自己的近況寫 DIR/.aos/cpu.json。

停止條件三個：跑滿 --max-runs（沒給＝無限）、收到 SIGTERM（跑完這次就退）、
--time-limit 到（硬時限，正在跑的那次直接當逾時砍掉）。退之前 cpu.json 補上
stopped（"max_runs"／"sigterm"／"time_limit"）與 ended_at。
"""
import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time

import aos_inst
from aos_inst import abspath

DEFAULT_INST = os.path.join(".aos", "inst.json")
GRACE = 2.0             # 逾時：SIGTERM 之後給整個 process group 這麼久，還在就 SIGKILL


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


def run_once(d, tick, inst_rel=DEFAULT_INST, deadline=None):
    """執行一次 inst.json，回傳（也寫進 last.json／runs.jsonl）結果 JSON。

    deadline＝cpu 整體時限的到期時刻（time.monotonic()），會跟這筆自己的 timeout_ms
    取比較早的那個；None＝只看 timeout_ms。
    """
    d = os.path.abspath(d)
    res = {"tick": tick, "exit": None, "signal": None, "stdout": "", "stderr": "",
           "timed_out": False, "started_at": now(), "ended_at": None}
    try:
        inst = aos_inst.load(os.path.join(d, inst_rel), d)
        _exec(d, tick, inst, res, deadline)
    except aos_inst.InstError as e:      # 格式／解析被拒：記一條就好，這次不跑、cpu 不炸
        res["error"] = str(e)
    except Exception as e:
        res["error"] = "%s: %s" % (type(e).__name__, e)
    res["ended_at"] = now()
    write_json(os.path.join(d, ".aos", "last.json"), res)
    append_jsonl(os.path.join(d, ".aos", "runs.jsonl"), res)
    return res


def _exec(d, tick, inst, res, deadline):
    """把一份解好的 inst 變成一次子行程，結果填回 res。"""
    env = dict(os.environ)
    env.update(inst["env"])
    env["AOS_DIR"] = d                  # 手腳：proc 靠這兩個知道自己是誰、第幾格
    env["AOS_TICK"] = str(tick)
    cwd = abspath(d, inst["cwd"] or ".")

    opened = []
    try:
        try:
            fin = open(abspath(d, inst["stdin"]), "rb") if inst["stdin"] \
                else open(os.devnull, "rb")
            opened.append(fin)
            if inst["stdout"]:                              # 有寫＝導到檔（建立並清空）
                fout = open(abspath(d, inst["stdout"]), "wb")
                opened.append(fout)
            else:                                           # 空＝cpu 抓回 last.json
                fout = subprocess.PIPE
            if inst["stderr_merge"]:                        # {"$opt":"merge"}＝跟 stdout 同一條
                ferr = subprocess.STDOUT if fout is subprocess.PIPE else fout
            elif inst["stderr"]:
                ferr = open(abspath(d, inst["stderr"]), "wb")
                opened.append(ferr)
            else:
                ferr = subprocess.PIPE
        except OSError as e:
            res["exit"] = 126                               # 重導向開檔失敗＝設定階段失敗
            res["stderr"] = "aos-cpu: 重導向的檔案開不起來：%s（exit 126）\n" % e
            return

        limit = (inst["timeout_ms"] / 1000.0) if inst["timeout_ms"] else None
        if deadline is not None:                            # 整體時限也是一種期限，取早的
            left = max(0.0, deadline - time.monotonic())
            limit = left if limit is None else min(limit, left)
        out, err, code, timed_out, note = _call(inst["argv"], cwd, env, fin, fout, ferr, limit)
        if note:                                            # 127／126 的說明寫進 stderr 那條
            if ferr is subprocess.PIPE:
                err = (err or "") + note
            elif ferr is subprocess.STDOUT:
                out = (out or "") + note
            else:
                ferr.write(note.encode("utf-8"))
    finally:
        for f in opened:
            f.close()

    res["stdout"], res["stderr"] = out, err                 # 導到檔的那條在這裡是 None
    res["timed_out"] = timed_out
    if code < 0:
        res["signal"] = -code
    else:
        res["exit"] = code
    if inst["exit"]:
        _write_exit(abspath(d, inst["exit"]), code if code >= 0 else 128 + (-code))


def _call(argv, cwd, env, fin, fout, ferr, limit):
    """跑一次，回 (stdout, stderr, returncode, timed_out, note)。

    returncode < 0 ＝被訊號 N 砍（-N）。逾時：先對整個 process group 送 SIGTERM、
    給 GRACE 秒，直接子行程還活著就 SIGKILL 整個 group（收完屍再補一發 SIGKILL——
    直接子行程死了不代表群組空了）。argv[0] 走**疊加後**的 env 裡的 PATH
    （subprocess 帶 env= 時本來就是這樣查的），找不到＝127、沒執行權＝126，
    這兩種都算「跑完了一次」，不是 error。
    """
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, text=True, start_new_session=True,
                             stdin=fin, stdout=fout, stderr=ferr)
    except PermissionError as e:
        return None, None, 126, False, "aos-cpu: 沒有執行權：%s（exit 126）\n" % e
    except (FileNotFoundError, NotADirectoryError) as e:
        return None, None, 127, False, "aos-cpu: 找不到程式：%s（exit 127）\n" % e
    except OSError as e:
        return None, None, 126, False, "aos-cpu: 起不了子行程：%s（exit 126）\n" % e

    timed_out = False
    try:
        out, err = p.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        _sig_group(p, signal.SIGTERM)
        try:
            out, err = p.communicate(timeout=GRACE)
        except subprocess.TimeoutExpired:
            _sig_group(p, signal.SIGKILL)
            out, err = p.communicate()
        _sig_group(p, signal.SIGKILL)
    return out, err, p.returncode, timed_out, None


def _sig_group(p, sig):
    """砍整個 process group：留在群組裡的孫行程要跟著走。空群組＝ESRCH，無害。"""
    try:
        os.killpg(os.getpgid(p.pid), sig)
    except OSError:
        pass


def _write_exit(path, status):
    """`exit` 欄位：十進位結束碼＋一個換行，fsync 檔案與它的父目錄（崩潰後對帳的證據）。"""
    d = os.path.dirname(path) or "."
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)
    try:
        os.write(fd, ("%d\n" % status).encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def main():
    ap = argparse.ArgumentParser(prog="aos-cpu")
    ap.add_argument("dir")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--max-runs", type=int, default=0)
    ap.add_argument("--time-limit", type=float, default=0.0, help="整體時限（秒），0＝不限")
    ap.add_argument("--inst", default=DEFAULT_INST)
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    cpuf = os.path.join(d, ".aos", "cpu.json")
    deadline = (time.monotonic() + a.time_limit) if a.time_limit > 0 else None

    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(True))

    def snap(tick, **extra):
        s = {"pid": os.getpid(), "tick": tick, "dir": d,
             "interval": a.interval, "time_limit": a.time_limit}
        s.update(extra)
        write_json(cpuf, s)

    def out_of_time():
        return deadline is not None and time.monotonic() >= deadline

    tick = 0
    while True:
        tick += 1
        run_once(d, tick, a.inst, deadline)
        snap(tick)
        if out_of_time():           # 硬時限先判：那次可能就是被它砍掉的
            stopped = "time_limit"
            break
        if stop:
            stopped = "sigterm"
            break
        if a.max_runs and tick >= a.max_runs:
            stopped = "max_runs"
            break
        t0 = time.time()            # 睡覺中時限到＝醒來直接退
        while time.time() - t0 < a.interval and not stop and not out_of_time():
            time.sleep(0.05)
        if out_of_time():
            stopped = "time_limit"
            break
        if stop:
            stopped = "sigterm"
            break
    snap(tick, stopped=stopped, ended_at=now())
    return 0


if __name__ == "__main__":
    sys.exit(main())
