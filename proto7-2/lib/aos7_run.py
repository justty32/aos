"""aos7-run <taskdir> [<taskdir 的 fd>]：任務的包裝程式（spec.md 5.3）——讀 birth.json，把任務起在自己的程序群組，
寫 pid.json，等它結束，寫 exit.json。tick 用新 session 起它、不等。第二個參數是 tick 開好、繼承下來的任務資料夾 fd（cwd 是
tick 抓著的 node）：給了它，讀寫都經它（node 搬家照樣寫到它，被刪就寫不進去、不建鬼目錄）；fd 無效時退出碼 2、不回退去寫
字串路徑。任務起來前的任何失敗都寫 exit.json code 127。環境的 AOS7_* 原樣傳給任務，AOS7_TEST_* 不傳。"""
import json
import os
import re
import stat
import subprocess
import sys

from aos7_fs import BIN, OK, fact, now, proc_starttime, test_point

RUN = [None]   # 這次的 run（讀到 birth.json 後填上；寫 pid.json／exit.json 用）


def build_argv(birth, node):
    """birth 的定義 → 實際 argv：inst 交給 aos-exec（相對 node）；argv 展開 `$AOS7_*`。"""
    if birth.get("inst"):
        return [sys.executable, os.path.join(BIN, "aos-exec"), os.path.normpath(os.path.join(node, birth["inst"]))]
    return [expand(a) for a in birth.get("argv") or []]


def expand(arg):
    """展開字串裡的 `$AOS7_X`／`${AOS7_X}`（沒設的保留原文，其他 `$` 不動），讓 argv 指得到槽與掛載點。"""
    return re.sub(r"\$\{?(AOS7_[A-Z_]+)\}?", lambda m: os.environ.get(m.group(1), m.group(0)), arg) \
        if isinstance(arg, str) else arg


def fail(dfd, msg):
    """任務起不來：stderr 說明、經 fd 寫 exit.json code 127（連它都寫不進去，tock 照 birth 的 runner 判 lost）。回 1。"""
    print("aos7-run: %s" % msg, file=sys.stderr, flush=True)
    if not write_at(dfd, "exit.json", {"run": RUN[0], "code": 127, "at": now(), "round": round_at(dfd), "error": msg}):
        print("aos7-run: exit.json 也寫不進去；tock 會照 birth.json 的 runner 判 lost", file=sys.stderr, flush=True)
    return 1


def main(argv=None):
    """命令列入口：0＝走完（任務的結果在 exit.json），1＝用法錯或起不來，2＝交接的 fd 無效。"""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2):
        print("用法: aos7-run <taskdir> [<taskdir 的 fd>]", file=sys.stderr)
        return 1
    tdir = os.path.abspath(argv[0])
    held = len(argv) == 2
    if held:
        try:
            dfd = int(argv[1])
            os.set_inheritable(dfd, False)   # 不傳給任務
            if not stat.S_ISDIR(os.fstat(dfd).st_mode):
                raise OSError("不是資料夾")
        except (OSError, ValueError) as e:
            print("aos7-run: 第二個參數 %r 不是繼承來的任務資料夾 fd（%s）；不照 %s 字串路徑寫任何東西。"
                  "這個參數只給 aos7-tick 用，人手跑請只給 <taskdir>" % (argv[1], e, tdir), file=sys.stderr)
            return 2
    else:
        try:
            dfd = os.open(tdir, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return 1   # 任務資料夾已經不在：不建回來
    st, birth = fact("birth.json", dir_fd=dfd)
    if st != OK or not isinstance(birth, dict) or not birth:
        return fail(dfd, "讀不到 birth.json")
    RUN[0] = birth.get("run")
    node = os.environ.get("AOS7_NODE") or os.getcwd()
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS7_TEST_")}
    try:
        out = os.fdopen(os.open("out.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644, dir_fd=dfd), "ab")
    except OSError as e:
        return fail(dfd, "開不了 out.log：%s" % e)
    try:
        cmd = build_argv(birth, node)
        if not cmd:
            raise FileNotFoundError("argv 是空的")
        # 任務自己一個程序群組：收任務的群組時 runner 留下來 wait、記退出結果
        proc = subprocess.Popen(cmd, cwd=None if held else node, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, process_group=0)
    except (OSError, TypeError, ValueError) as e:   # 包含 argv 有非字串、NUL
        try:
            out.write(("aos7-run: 起不來: %s\n" % e).encode())
            out.close()
        except OSError:
            pass
        return fail(dfd, "起不來：%s" % e)
    test_point("runner-before-pid")
    # 記 starttime：pid 會被重用，連同它才認得出還是不是同一個程序
    write_at(dfd, "pid.json", {"run": RUN[0], "pid": proc.pid, "pgid": proc.pid, "starttime": proc_starttime(proc.pid),
                               "runner_pid": os.getpid(), "at": now()})
    code = proc.wait()
    out.close()
    test_point("runner-before-exit")
    write_at(dfd, "exit.json", {"run": RUN[0], "code": code, "at": now(), "round": round_at(dfd)})
    return 0


def round_at(dfd):
    """../../round.json 的 round（寫進 exit.json）；讀不到、壞掉回 None，不猜。"""
    st, r = fact("../../round.json", dir_fd=dfd)
    return r.get("round") if st == OK and isinstance(r, dict) else None


def write_at(dfd, name, obj):
    """經目錄 fd 原子寫 name（先寫 `.` 開頭的暫存檔再 rename）；成功 True、I/O 失敗 False。"""
    tmp = ".%s.tmp.%d" % (name, os.getpid())
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644, dir_fd=dfd)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
    except OSError:
        return False
    return True
