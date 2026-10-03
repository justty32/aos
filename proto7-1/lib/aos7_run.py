"""aos7-run：任務的包裝程式——讀 birth.json，把任務起在自己的程序群組，寫 pid.json，等它，寫 exit.json（spec.md 第 5 節）。

    aos7-run <taskdir>

tick 用新 session 起它、不等；它自己活到任務結束。環境變數（AOS7_*）由 tick 給好，這裡原樣傳下去。
"""
import json
import os
import re
import subprocess
import sys

from aos7_fs import BIN, now, read_json


def build_argv(birth, node):
    """birth.json → 實際 argv。`inst` 用搬來的 aos-exec 跑（S-12）。"""
    if birth.get("inst"):
        inst = os.path.normpath(os.path.join(node, birth["inst"]))
        return [sys.executable, os.path.join(BIN, "aos-exec"), inst]
    return [expand(a) for a in birth.get("argv") or []]


def expand(arg):
    """argv 裡的 `$AOS7_TASK`、`${AOS7_NODE}` 這類 AOS7_* 變數展開（讓 argv 指得到掛載點）；其他 `$` 原樣。"""
    return re.sub(r"\$\{?(AOS7_[A-Z_]+)\}?", lambda m: os.environ.get(m.group(1), m.group(0)), arg) \
        if isinstance(arg, str) else arg


def node_round(node):
    r = read_json(os.path.join(node, ".aos", "round.json"), {})
    return r.get("round") if isinstance(r, dict) else None


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
    node = os.environ.get("AOS7_NODE") or os.getcwd()
    env = dict(os.environ)
    site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_site")
    if env.get("AOS7_AUDIT") and site not in env.get("PYTHONPATH", "").split(os.pathsep):
        # 寫入紀錄（spec 第 5 節）：只給任務，不給 aos7-run 自己（probes/polyglot N7）
        env["PYTHONPATH"] = os.pathsep.join(x for x in (site, env.get("PYTHONPATH")) if x)
    try:
        dfd = os.open(tdir, os.O_RDONLY | os.O_DIRECTORY)   # 先抓住任務資料夾本身：node 搬家後照樣寫到它現在的位置
    except OSError:
        return 1   # 任務資料夾已經不在（剛被刪）：不建回來
    try:
        out = os.fdopen(os.open("out.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644, dir_fd=dfd), "ab")
    except OSError:
        return 1
    try:
        cmd = build_argv(birth, node) if isinstance(birth, dict) else []
        if not cmd:
            raise FileNotFoundError("argv 是空的")
        proc = subprocess.Popen(cmd, cwd=node, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, process_group=0)
    except (OSError, TypeError, ValueError) as e:   # argv 有非字串、NUL：照樣寫 exit.json，不留「永遠剛起」的任務（probes/chaos B4）
        out.write(("aos7-run: 起不來: %s\n" % e).encode())
        out.close()
        write_at(dfd, "exit.json", {"code": 127, "at": now(), "round": node_round(node), "error": str(e)})
        return 0
    # pid.json 也經過 fd 寫：任務資料夾剛被刪（測試收尾、node 被 rm -rf）時不會用 makedirs 把它建回來
    write_at(dfd, "pid.json", {"pid": proc.pid, "pgid": proc.pid, "runner_pid": os.getpid(), "at": now()})
    code = proc.wait()
    out.close()
    write_at(dfd, "exit.json", {"code": code, "at": now(), "round": round_at(dfd)})
    return 0


def round_at(dfd):
    """經過任務資料夾的 fd 讀 `../../round.json`（node 搬走也讀得到）。"""
    try:
        fd = os.open("../../round.json", os.O_RDONLY, dir_fd=dfd)
        with os.fdopen(fd, encoding="utf-8") as f:
            r = json.load(f)
        return r.get("round") if isinstance(r, dict) else None
    except (OSError, ValueError):
        return None


def write_at(dfd, name, obj):
    """經過 fd 原子寫 `name`（exit.json、pid.json）：node 被搬走就寫到新位置；被刪掉就寫進已刪的資料夾（等於丟掉），
    不會在舊路徑把資料夾建回來（probes/rename N8、N9，subtimeline 1）。"""
    tmp = ".%s.tmp.%d" % (name, os.getpid())
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644, dir_fd=dfd)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
    except OSError:
        pass
