"""aos7-run：任務的包裝程式——讀 birth.json，把任務起在自己的程序群組，寫 pid.json，等它，寫 exit.json（spec.md 第 5 節）。

    aos7-run <taskdir> [<taskdir 的 fd>]

tick 用新 session 起它，並把任務資料夾的 fd 傳進來、cwd 設成它抓著的 node（astra-6 G-02）、不等；它自己活到任務結束。環境變數（AOS7_*）由 tick 給好，這裡原樣傳下去。

**第二個參數是內部交接用的能力，不是身分約束**（astra-7 H-09）：它必須是呼叫者開好、繼承下來的任務資料夾 fd，cwd 也由呼叫者保證
是那個 node。給了第二參數，fd 就是權威：讀 birth、寫 pid／out／exit 都經它，`<taskdir>` 字串只拿來對照環境；fd 無效（不是數字、
沒開、不是資料夾）時 stderr 說清楚、退出碼 2，**不回退**去寫 `<taskdir>` 字串指的地方（可能已被換掉）。這不是驗證或隔離任務身分的邊界。
"""
import json
import os
import re
import stat
import subprocess
import sys

from aos7_fs import BIN, now


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


def read_birth(dfd):
    """經任務資料夾的 fd 讀 birth.json；讀不到或壞掉回 None。"""
    try:
        fd = os.open("birth.json", os.O_RDONLY | os.O_NONBLOCK, dir_fd=dfd)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return None
        with os.fdopen(fd, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def fail(dfd, msg):
    """起程序前就失敗：stderr 說明，經 fd 寫 exit.json `{"code": 127, "error"}`（任務不會永遠 born；astra-7 H-06）。
    連 exit.json 都寫不進去時 stderr 再說一次；tick 記下的 runner.json 讓 tock 之後把它判成 lost。"""
    print("aos7-run: %s" % msg, file=sys.stderr, flush=True)
    if not write_at(dfd, "exit.json", {"code": 127, "at": now(), "round": round_at(dfd), "error": msg}):
        print("aos7-run: exit.json 也寫不進去；tock 會照 runner.json 判 lost", file=sys.stderr, flush=True)
    return 1


def env_mismatch(dfd):
    """最後交接（astra-7 H-05）：給任務的 `AOS7_TASK`／`AOS7_NODE`（字串路徑，也是 argv 展開與掛載點記錄用的）
    現在還指著 runner 抓著的任務資料夾（fd）與 node（cwd）嗎。不一致（起任務的半路 node 被搬走、換掉）回說明，否則 None。
    沒有這些環境變數（人手跑）不比。"""
    for var, here in (("AOS7_TASK", lambda: os.fstat(dfd)), ("AOS7_NODE", lambda: os.stat("."))):
        p = os.environ.get(var)
        if not p:
            continue
        try:
            same = os.path.samestat(os.stat(p), here())
        except OSError:
            same = False
        if not same:
            return "%s=%s 已經不是 runner 抓著的資料夾（node 在起任務時被搬走或換掉），沒起" % (var, p)
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2):
        print("用法: aos7-run <taskdir> [<taskdir 的 fd>]", file=sys.stderr)
        return 1
    tdir = os.path.abspath(argv[0])
    held = len(argv) == 2   # tick 起的：第二個參數是任務資料夾的 fd，cwd 是 tick 抓著的 node（astra-6 G-02）
    if held:
        try:
            dfd = int(argv[1])
            os.set_inheritable(dfd, False)   # 不傳給任務
            if not stat.S_ISDIR(os.fstat(dfd).st_mode):
                raise OSError("不是資料夾")
        except (OSError, ValueError) as e:
            # 第二參數是繼承來的目錄 fd（內部交接，H-09）：無效就說清楚、不回退去寫字串路徑（可能已被換掉）
            print("aos7-run: 第二個參數 %r 不是繼承來的任務資料夾 fd（%s）；不照 %s 字串路徑寫任何東西。"
                  "這個參數只給 aos7-tick 用，人手跑請只給 <taskdir>" % (argv[1], e, tdir), file=sys.stderr)
            return 2
    else:
        try:
            dfd = os.open(tdir, os.O_RDONLY | os.O_DIRECTORY)   # 先抓住任務資料夾本身：node 搬家後照樣寫到它現在的位置
        except OSError:
            return 1   # 任務資料夾已經不在（剛被刪）：不建回來
    birth = read_birth(dfd)
    if not birth:
        # 經 fd 寫 exit.json：任務不會永遠算剛起（astra-6 G-02）；資料夾已刪就等於丟掉，不建回來
        return fail(dfd, "讀不到 birth.json")
    node = os.environ.get("AOS7_NODE") or os.getcwd()
    if held:
        why = env_mismatch(dfd)
        if why:
            return fail(dfd, why)
    env = dict(os.environ)
    site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_site")
    if env.get("AOS7_AUDIT") and site not in env.get("PYTHONPATH", "").split(os.pathsep):
        # 寫入紀錄（spec 第 5 節）：只給任務，不給 aos7-run 自己（probes/polyglot N7）
        env["PYTHONPATH"] = os.pathsep.join(x for x in (site, env.get("PYTHONPATH")) if x)
    try:
        out = os.fdopen(os.open("out.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644, dir_fd=dfd), "ab")
    except OSError as e:
        return fail(dfd, "開不了 out.log：%s" % e)   # 例如 out.log 被建成資料夾（astra-7 H-06）
    try:
        cmd = build_argv(birth, node) if isinstance(birth, dict) else []
        if not cmd:
            raise FileNotFoundError("argv 是空的")
        proc = subprocess.Popen(cmd, cwd=None if held else node, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, process_group=0)
    except (OSError, TypeError, ValueError) as e:   # argv 有非字串、NUL：照樣寫 exit.json，不留「永遠剛起」的任務（probes/chaos B4）
        try:
            out.write(("aos7-run: 起不來: %s\n" % e).encode())
            out.close()
        except OSError:
            pass
        write_at(dfd, "exit.json", {"code": 127, "at": now(), "round": round_at(dfd), "error": str(e)})
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
    不會在舊路徑把資料夾建回來（probes/rename N8、N9，subtimeline 1）。回有沒有寫成。"""
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
