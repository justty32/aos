"""aos7-run：任務的包裝程式——讀 birth.json，把任務起在自己的程序群組，寫 pid.json，等它，寫 exit.json（spec.md 第 5 節）。

    aos7-run <taskdir> [<taskdir 的 fd>]

tick 用新 session 起它，並把任務資料夾的 fd 傳進來、cwd 設成它抓著的 node（astra-6 G-02）、不等；它自己活到任務結束。環境變數（AOS7_*）由 tick 給好，這裡原樣傳下去。
人手跑可省 fd；runner 讀 birth.json 與 node 的 round.json，寫 out.log、pid.json、exit.json，
替 tick 保留等待任務與記錄退出的責任（spec §4／§5；S-09／S-10）。

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
    """由出生物件 birth、node 路徑組實際 argv，回命令字串清單（spec §4／§5）。

    有 inst 就交搬來的 aos-exec 跑（S-12），相對 node 定位；否則展開 argv 的 AOS7_*。
    沒有可用 argv 回空清單；格式錯誤留給呼叫者處理，不在這裡讀檔。
    """
    if birth.get("inst"):
        inst = os.path.normpath(os.path.join(node, birth["inst"]))
        return [sys.executable, os.path.join(BIN, "aos-exec"), inst]
    return [expand(a) for a in birth.get("argv") or []]


def expand(arg):
    """展開參數 arg 裡的 `$AOS7_TASK`、`${AOS7_NODE}` 等 AOS7_*，回展開後值（spec §4）。

    讓 argv 指得到掛載點；未設變數、其他 `$` 與非字串參數原樣保留。
    """
    return re.sub(r"\$\{?(AOS7_[A-Z_]+)\}?", lambda m: os.environ.get(m.group(1), m.group(0)), arg) \
        if isinstance(arg, str) else arg


def read_birth(dfd):
    """經任務目錄 fd（dfd）讀 birth.json，回解析出的 JSON 值（不保證是物件；spec §0／§5）。

    讀不到、不是一般檔或解析失敗回 None；非阻塞開檔避免 FIFO 卡住 runner。
    """
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
    """起程序前就失敗：stderr 說明，經 fd 寫 exit.json `{"code": 127, "error"}`（寫成才不會永遠 born；astra-7 H-06）。
    連 exit.json 都寫不進去時 stderr 再說一次；需 runner.json 已發布且 runner 身分可判，tock 才能據此判 lost。

    dfd 是任務目錄 fd，msg 是失敗原因；不論寫入成否都回 runner 退出碼 1（spec §5）。
    """
    print("aos7-run: %s" % msg, file=sys.stderr, flush=True)
    if not write_at(dfd, "exit.json", {"code": 127, "at": now(), "round": round_at(dfd), "error": msg}):
        print("aos7-run: exit.json 也寫不進去；tock 會照 runner.json 判 lost", file=sys.stderr, flush=True)
    return 1


def env_mismatch(dfd):
    """最後交接（astra-7 H-05）：給任務的 `AOS7_TASK`／`AOS7_NODE`（字串路徑，也是 argv 展開與掛載點記錄用的）
    現在還指著 runner 抓著的任務資料夾（fd）與 node（cwd）嗎。不一致（起任務的半路 node 被搬走、換掉）回說明，否則 None。
    沒有這些環境變數（人手跑）不比；dfd 是任務目錄 fd，stat 讀不到也回不一致的說明（spec §4／§5）。
    """
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
    """由 tick 或人啟動 runner；argv 為 taskdir 與可選 fd，None 取命令列（spec §5）。

    讀出生定義、起任務、等結束並寫狀態；正常收尾或任務 Popen 失敗回 0，前置失敗回 1，
    繼承 fd 不合法回 2。真正任務的退出碼寫 exit.json，不直接作為 runner 的回傳值。
    """
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
        # spec §5／§6：讓真任務另成程序群組，kill 可收任務，runner 留著等候並寫 exit.json。
        # 已知問題 K-06：env_mismatch 後到 Popen 前仍可搬 node，任務的字串路徑可能建回舊目錄（未修，proto7-2 重做）。
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
    # 已知問題 K-04：任務已出生但 pid.json 未發布時 runner 若死，tock 可誤判 lost 後重起（未修，proto7-2 重做）。
    write_at(dfd, "pid.json", {"pid": proc.pid, "pgid": proc.pid, "runner_pid": os.getpid(), "at": now()})
    code = proc.wait()
    out.close()
    write_at(dfd, "exit.json", {"code": code, "at": now(), "round": round_at(dfd)})
    return 0


def round_at(dfd):
    """經任務目錄 fd（dfd）讀 `../../round.json`，回 round 欄位（node 搬走也讀得到；spec §5）。

    讀取／解析失敗、不是物件或缺 round 時回 None；現行不驗證 round 型別。
    """
    try:
        fd = os.open("../../round.json", os.O_RDONLY, dir_fd=dfd)
        with os.fdopen(fd, encoding="utf-8") as f:
            r = json.load(f)
        return r.get("round") if isinstance(r, dict) else None
    except (OSError, ValueError):
        return None


def write_at(dfd, name, obj):
    """經過 fd 原子寫 `name`（exit.json、pid.json）：node 被搬走就寫到新位置；被刪掉則寫入失敗，
    不會在舊路徑把資料夾建回來（probes/rename N8、N9，subtimeline 1）。回有沒有寫成。

    dfd 是任務目錄 fd，name 是檔名，obj 是 JSON 值；OSError 回 False（含目錄已刪），
    JSON 序列化錯誤仍上拋。暫存檔以點開頭，rename 前不暴露半份狀態（spec §0／§5）。
    """
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
