#!/usr/bin/env python3
# mail_more.py：mail.py 的後半與共用小工具——擋下不該做的、信夾形狀的信、proto8 aos-post 實寄、proc 被暫停時投遞、1000 封等著時讀 status 的速度。
import errno, json, os, signal, statistics, subprocess, time
import common
from common import check, start_demo, sh, bg, status, wait_until

# proto8 的寄信程式（只讀、只拿來寄進 demo 的 mailbox/；不碰任何活的樹）
POST = os.path.normpath(os.path.join(common.HERE, "..", "..", "..", "..", "proto8", "bin", "aos-post"))


def err_of(fn, *a):
    """跑 fn(*a)；回 0 或 errno 的名字。"""
    try:
        fn(*a)
        return 0
    except OSError as e:
        return errno.errorcode.get(e.errno, e.errno)


def put(path, data, chunk=65536):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        for i in range(0, len(data), chunk):
            os.write(fd, data[i:i + chunk])
        os.fsync(fd)
    finally:
        os.close(fd)


def mail(st, *keys):
    return tuple((st or {}).get("mail_" + k) for k in keys)


def ctl_done(root, line):
    """寫 ctl 並等那道做完；回 status。收下的那一刻 state 就是 doing（回答的線上設的），所以寫完等「不是 doing」就是等這一道。
    take 的 mail_taken 在 take() 裡就加了、mail_last_name 要到做事的線做完才寫，只等計數會讀到一半。"""
    sh("echo '%s' > %s/ctl" % (line, root))
    return wait_until(lambda: (lambda s: s.get("aos_ctl_state") not in (None, "doing") and s)(status(root) or {})) or {}


def stop(p, root):
    sh("echo stop > %s/ctl" % root)
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        pass


def t_guards():
    p, pid, root, mnt = start_demo("mguards")
    mb = root + "/mailbox"
    put(mb + "/tmp/a", b"a")
    os.rename(mb + "/tmp/a", mb + "/new/a")
    put(mb + "/tmp/b", b"b")
    tries = {
        "create in new/": "printf y > %s/new/y" % mb,
        "mkdir in new/": "mkdir %s/new/d" % mb,
        "rm new/a": "rm -f %s/new/a" % mb,
        "mv new/a back to tmp/": "mv %s/new/a %s/tmp/a" % (mb, mb),
        "mv new/a to cur/": "mv %s/new/a %s/cur/a" % (mb, mb),
        "create in cur/": "printf z > %s/cur/z" % mb,
        "mkdir in the mailbox root": "mkdir %s/x" % mb,
        "hard link tmp/b into new/": "ln %s/tmp/b %s/new/b" % (mb, mb),
        "write to new/a": "printf more >> %s/new/a" % mb,
    }
    bad = {k: r[2].strip() for k, c in tries.items() for r in [sh(c)] if r[0] == 0}
    rc, out, _ = sh("cat %s/new/a" % mb)
    seen = os.listdir(mb + "/new"), os.listdir(mb + "/cur"), sorted(os.listdir(mb))
    check("refused: create/mkdir in new/, rm or move out of new/, anything in cur/ or the root, link, writing a letter in new/",
          not bad and out == "a" and seen == (["a"], [], ["cur", "new", "tmp"]), (bad, out, seen))
    os.rename(mb + "/tmp/b", mb + "/tmp/b2")
    check("rename inside tmp/ is allowed (no overwrite either)", os.listdir(mb + "/tmp") == ["b2"])
    stop(p, root)


def t_folder():
    p, pid, root, mnt = start_demo("mfolder")
    mb = root + "/mailbox"
    # aos-post 的形狀：mkdir tmp/<名>，裡面先寫 .letter.json.<pid>.tmp、fsync、改名成 letter.json，再把整個夾搬進 new/
    rc, _, err = sh("cd %s && mkdir tmp/L && printf '{\"body\": 1}' > tmp/L/.letter.json.1.tmp && "
                    "mv tmp/L/.letter.json.1.tmp tmp/L/letter.json && printf att > tmp/L/extra && mv tmp/L new/L" % mb)
    rc2, out, _ = sh("ls %s/new/L; cat %s/new/L/letter.json" % (mb, mb))
    check("folder letter (mkdir, write, rename inside, move the folder): new/L/letter.json readable",
          rc == 0 and out == 'extra\nletter.json\n{"body": 1}', (err, out))
    os.mkdir(mb + "/tmp/M")
    put(mb + "/tmp/M/f", b"x")
    e1 = err_of(os.mkdir, mb + "/tmp/M/sub")
    e2 = err_of(os.rmdir, mb + "/tmp/M")
    os.unlink(mb + "/tmp/M/f")
    e3 = err_of(os.rmdir, mb + "/tmp/M")
    check("inside a folder letter: no sub-folder (EPERM); rmdir non-empty ENOTEMPTY; empty rmdir ok",
          (e1, e2, e3) == ("EPERM", "ENOTEMPTY", 0), (e1, e2, e3))
    st = ctl_done(root, "take")
    check("take a folder letter: size = all its files (11 + 3)", mail(st, "last_name", "last_bytes") == ("L", "14"), st)
    stop(p, root)


def post(box, name=None, body='{"hi": 1}'):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/")}   # 不帶 AOS_*：不讀任何活的鐘、stack
    p = subprocess.run([POST, "send", box] + ([name] if name else []), input=body, capture_output=True, text=True, env=env,
                       cwd=common.SCRATCH, timeout=10)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def t_aospost():
    if not os.access(POST, os.X_OK):
        check("proto8 aos-post is built (%s)" % POST, False)
        return
    p, pid, root, mnt = start_demo("mpost")
    mb = root + "/mailbox"
    rc, name, err = post(mb)
    try:
        letter = json.load(open(os.path.join(mb, "new", name, "letter.json")))
    except (OSError, ValueError) as e:
        letter = repr(e)
    check("real proto8 aos-post send into the live mailbox/: exit 0, new/<name>/letter.json has the body",
          rc == 0 and isinstance(letter, dict) and letter.get("body") == {"hi": 1} and os.listdir(mb + "/tmp") == [], (rc, err, letter))
    rc1, _, _ = post(mb, "named", body='"first"')
    rc2, _, err2 = post(mb, "named", body='"second"')
    body = json.load(open(mb + "/new/named/letter.json")).get("body")
    check("aos-post with the same given name twice: second is LetterExists, first intact, tmp/ cleaned",
          rc1 == 0 and rc2 == 1 and "LetterExists" in err2 and body == "first" and os.listdir(mb + "/tmp") == [], (err2, body))
    ctl_done(root, "refuse on")
    rc, _, err = post(mb)
    check("refusing proc: aos-post fails (WriteFailed ... not permitted) and cleans its tmp/",
          rc == 1 and "WriteFailed" in err and "not permitted" in err and os.listdir(mb + "/tmp") == [], (rc, err))
    stop(p, root)


def t_stopped():
    p, pid, root, mnt = start_demo("mstopped")
    mb = root + "/mailbox"
    os.kill(pid, signal.SIGSTOP)
    try:
        w = bg("printf s > %s/tmp/s && mv %s/tmp/s %s/new/s" % (mb, mb, mb))
        time.sleep(0.5)
        check("proc SIGSTOPped: a delivery just blocks (expected; same as reading its status)", w.poll() is None)
    finally:
        os.kill(pid, signal.SIGCONT)
    try:
        rc = w.wait(3)
    except subprocess.TimeoutExpired:
        rc = None
    check("SIGCONT: the blocked delivery finishes and lands", rc == 0 and os.listdir(mb + "/new") == ["s"], rc)
    stop(p, root)


def median_us(fn, n):
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return statistics.median(ts) * 1e6


def read_all(path):
    fd = os.open(path, os.O_RDONLY)
    while os.read(fd, 65536):
        pass
    os.close(fd)


def t_many():
    p, pid, root, mnt = start_demo("mmany")
    mb = root + "/mailbox"
    median_us(lambda: read_all(root + "/status"), 100)   # 先熱身
    before = median_us(lambda: read_all(root + "/status"), 300)
    ts = []
    for i in range(1000):
        t = time.perf_counter()
        put("%s/tmp/l%04d" % (mb, i), b"letter %d\n" % i)
        os.rename("%s/tmp/l%04d" % (mb, i), "%s/new/l%04d" % (mb, i))
        ts.append(time.perf_counter() - t)
    deliver = statistics.median(ts) * 1e6
    after = median_us(lambda: read_all(root + "/status"), 300)
    st = status(root)
    check("1000 letters delivered by the same syscalls (median %.0f us each: create, write, fsync, close, rename)" % deliver,
          mail(st, "waiting") == ("1000",) and len(os.listdir(mb + "/new")) == 1000, st)
    check("reading status stays fast with 1000 waiting (median %.0f us, %.0f us with none)" % (after, before),
          after < 3 * before + 50, (before, after))
    rc, out, _ = sh("cat %s/new/l0999" % mb)
    check("a waiting letter is readable with cat", out == "letter 999\n", out)
    stop(p, root)
