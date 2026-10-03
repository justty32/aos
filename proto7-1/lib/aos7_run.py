"""aos7-run：任務的包裝程式——讀 birth.json，把任務起在自己的程序群組，寫 pid.json，等它，寫 exit.json（spec.md 第 5 節）。

    aos7-run <taskdir>

tick 用新 session 起它、不等；它自己活到任務結束。環境變數（AOS7_*）由 tick 給好，這裡原樣傳下去。
"""
import os
import subprocess
import sys

from aos7_fs import BIN, now, read_json, write_json


def build_argv(birth, node):
    """birth.json → 實際 argv。`inst` 用搬來的 aos-exec 跑（S-12）。"""
    if birth.get("inst"):
        inst = os.path.normpath(os.path.join(node, birth["inst"]))
        return [sys.executable, os.path.join(BIN, "aos-exec"), inst]
    return list(birth.get("argv") or [])


def node_round(node):
    r = read_json(os.path.join(node, ".aos", "round.json"), {})
    return r.get("round")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("用法: aos7-run <taskdir>", file=sys.stderr)
        return 1
    tdir = os.path.abspath(argv[0])
    birth = read_json(os.path.join(tdir, "birth.json"))
    if not birth:
        print("aos7-run: 讀不到 birth.json", file=sys.stderr)
        return 1
    node = birth["dirs"][0] if birth.get("dirs") else os.getcwd()
    cmd = build_argv(birth, node)
    out = open(os.path.join(tdir, "out.log"), "ab")
    try:
        if not cmd:
            raise FileNotFoundError("argv 是空的")
        proc = subprocess.Popen(cmd, cwd=node, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, process_group=0)
    except OSError as e:
        out.write(("aos7-run: 起不來: %s\n" % e).encode())
        out.close()
        write_json(os.path.join(tdir, "exit.json"),
                   {"code": 127, "at": now(), "round": node_round(node), "error": str(e)})
        return 0
    write_json(os.path.join(tdir, "pid.json"),
               {"pid": proc.pid, "pgid": proc.pid, "runner_pid": os.getpid(), "at": now()})
    code = proc.wait()
    out.close()
    write_json(os.path.join(tdir, "exit.json"), {"code": code, "at": now(), "round": node_round(node)})
    return 0
