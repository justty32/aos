#!/usr/bin/env python3
# mail.py：aos-procfs 信箱資料夾 mailbox/ 的測試——照 Maildir 投遞（tmp/ 寫好再搬進 new/）、撞名、上限、拒收、take、過期、大信、暫停、1000 封時讀 status 的速度、proto8 aos-post 實寄。
"""用法：timeout 300 python3 tests/mail.py [測試名 ...]   （不給＝全部；名字見 TESTS）"""
import errno, hashlib, os, subprocess, sys, time
import common
common.SCRATCH = os.path.expanduser("~/.aos/scratch/proto9-mailbox-1125")
common.MNT = os.path.join(common.SCRATCH, "mnt")
from common import DEMO, RESULTS as results, check, start_demo, sh, status, wait_until, cleanup, leftovers
from mail_more import err_of, put, mail, stop, ctl_done, t_guards, t_folder, t_aospost, t_stopped, t_many


def t_shell():
    p, pid, root, mnt = start_demo("mshell")
    mb = root + "/mailbox"
    rc, out, _ = sh("cat %s/attrs %s/settings; ls %s" % (root, root, mb))
    check("attrs has aos_mailbox: yes; settings aos_mailbox stays -; mailbox has cur new tmp",
          "aos_mailbox: yes" in out and "aos_mailbox: -" in out and out.split()[-3:] == ["cur", "new", "tmp"], out)
    rc, _, err = sh("printf 'hello\\n' > %s/tmp/a && mv %s/tmp/a %s/new/a" % (mb, mb, mb))
    rc2, out, _ = sh("ls %s/tmp; cat %s/new/a" % (mb, mb))
    check("shell delivery (printf > tmp/a && mv tmp/a new/a): tmp empty, new/a readable", rc == 0 and out == "hello\n", (err, out))
    st = status(root)
    check("status: mail_waiting 1, mail_delivered 1, mail_writing 0", mail(st, "waiting", "delivered", "writing") == ("1", "1", "0"), st)
    stop(p, root)


def t_half():
    p, pid, root, mnt = start_demo("mhalf")
    mb = root + "/mailbox"
    fd = os.open(mb + "/tmp/h", os.O_WRONLY | os.O_CREAT, 0o644)
    os.write(fd, b"first half ")
    seen = sorted(os.listdir(mb + "/new")), sorted(os.listdir(mb + "/tmp"))
    check("half-written letter: in tmp/, not in new/", seen == ([], ["h"]), seen)
    os.write(fd, b"second half")
    os.close(fd)
    os.rename(mb + "/tmp/h", mb + "/new/h")
    rc, out, _ = sh("cat %s/new/h" % mb)
    check("after the move: whole letter in new/", out == "first half second half", out)
    fd = os.open(mb + "/tmp/w", os.O_WRONLY | os.O_CREAT, 0o644)
    os.write(fd, b"x")
    os.rename(mb + "/tmp/w", mb + "/new/w")
    e = err_of(os.write, fd, b"more")
    os.close(fd)
    check("writing through an fd kept open after the move fails (EPERM): letters in new/ are sealed", e == "EPERM", e)
    stop(p, root)


def t_clash():
    p, pid, root, mnt = start_demo("mclash")
    mb = root + "/mailbox"
    put(mb + "/tmp/x", b"first")
    os.rename(mb + "/tmp/x", mb + "/new/x")
    put(mb + "/tmp/x", b"second")
    e = err_of(os.rename, mb + "/tmp/x", mb + "/new/x")
    rc, out, err = sh("mv %s/tmp/x %s/new/x" % (mb, mb))
    rc2, first, _ = sh("cat %s/new/x" % mb)
    check("move onto an existing name in new/: EEXIST (rename and mv), first letter intact, second still in tmp/",
          e == "EEXIST" and rc != 0 and "exists" in err and first == "first" and os.path.exists(mb + "/tmp/x"), (e, err, first))
    e = err_of(os.rename, mb + "/tmp/x", mb + "/new/.x")
    check("moving a name starting with . into new/ is refused (EINVAL)", e == "EINVAL", e)
    stop(p, root)


def t_limits():
    p, pid, root, mnt = start_demo("mlimits", "--mail-max-bytes", "1000", "--mail-max-letters", "3", "--mail-max-total", "2000")
    mb = root + "/mailbox"
    e = err_of(put, mb + "/tmp/big", b"b" * 1001)
    st = status(root)
    check("over max letter bytes: the write fails with EFBIG, reason LetterTooBig",
          e == "EFBIG" and mail(st, "last_refusal")[0].startswith("LetterTooBig"), (e, st))
    os.unlink(mb + "/tmp/big")
    put(mb + "/tmp/a", b"a" * 900)
    put(mb + "/tmp/b", b"b" * 900)
    e = err_of(put, mb + "/tmp/c", b"c" * 900)
    st = status(root)
    check("over max total bytes: the write fails with ENOSPC, reason MailboxFull",
          e == "ENOSPC" and "max_total_bytes" in mail(st, "last_refusal")[0], (e, st))
    e = err_of(put, mb + "/tmp/d", b"d")
    rc, _, err = sh("printf x > %s/tmp/e" % mb)
    check("over max letters (tmp/ + new/): creating a 4th entry fails with ENOSPC", e == "ENOSPC" and rc != 0
          and "space" in err, (e, err))
    os.rename(mb + "/tmp/a", mb + "/new/a")
    ctl_done(root, "take")
    os.unlink(mb + "/tmp/c")
    e = err_of(put, mb + "/tmp/d", b"d" * 900)
    check("after take and rm, room again: a new letter fits", e == 0, e)
    st = status(root)
    check("mail_bytes counts tmp/ + new/ (1800), mail_refused counts the refusals",
          mail(st, "bytes")[0] == "1800" and int(mail(st, "refused")[0]) >= 4, st)
    stop(p, root)


def t_refuse():
    p, pid, root, mnt = start_demo("mrefuse")
    mb = root + "/mailbox"
    ctl_done(root, "refuse on")
    rc, _, err = sh("printf 'no thanks' > %s/tmp/r && mv %s/tmp/r %s/new/r" % (mb, mb, mb))
    st = status(root)
    check("refuse on: the mv fails (EPERM) and nothing lands in new/", rc != 0 and "not permitted" in err
          and os.listdir(mb + "/new") == [] and mail(st, "waiting") == ("0",), (rc, err, st))
    check("... the letter is still in tmp/; mail_refused 1, mail_last_refusal MailRefused",
          os.path.exists(mb + "/tmp/r") and mail(st, "refused", "last_refusal")[0] == "1"
          and mail(st, "last_refusal")[0].startswith("MailRefused"), st)
    ctl_done(root, "refuse off")
    rc, _, err = sh("mv %s/tmp/r %s/new/r" % (mb, mb))
    check("refuse off: the same mv goes through", rc == 0 and os.listdir(mb + "/new") == ["r"], err)
    stop(p, root)


def t_take():
    p, pid, root, mnt = start_demo("mtake")
    mb = root + "/mailbox"
    for n, d in (("one", b"1"), ("two", b"22")):
        put(mb + "/tmp/" + n, d)
        os.rename(mb + "/tmp/" + n, mb + "/new/" + n)
    st = ctl_done(root, "take")
    check("take: the oldest letter (one) is gone from new/; counts moved", st.get("aos_ctl_state") == "done" and os.listdir(mb + "/new") == ["two"]
          and mail(st, "waiting", "taken", "last_name", "last_bytes") == ("1", "1", "one", "1"), st)
    st = ctl_done(root, "take")
    check("take again: two (2 bytes); new/ empty", os.listdir(mb + "/new") == [] and mail(st, "last_name", "last_bytes") == ("two", "2"), st)
    st = ctl_done(root, "take")
    check("take with nothing waiting: accepted, then failed MailEmpty", st.get("aos_ctl_state") == "failed" and st.get("aos_ctl_error", "").startswith("MailEmpty"), st)
    stop(p, root)


def t_stale():
    p, pid, root, mnt = start_demo("mstale", "--mail-stale", "1")
    mb = root + "/mailbox"
    put(mb + "/tmp/old", b"forgotten")
    os.mkdir(mb + "/tmp/olddir")
    time.sleep(1.6)
    put(mb + "/tmp/fresh", b"new one")
    left = sorted(os.listdir(mb + "/tmp"))
    st = status(root)
    check("stale tmp/ entries (file and folder) dropped after --mail-stale 1; fresh one kept",
          left == ["fresh"] and mail(st, "dropped_stale", "bytes") == ("2", "7"), (left, st))
    stop(p, root)


def t_big():
    p, pid, root, mnt = start_demo("mbig")
    mb = root + "/mailbox"
    data = os.urandom(1 << 20)
    t = time.monotonic()
    put(mb + "/tmp/big", data, chunk=100000)
    os.rename(mb + "/tmp/big", mb + "/new/big")
    dt = time.monotonic() - t
    with open(mb + "/new/big", "rb") as f:
        back = f.read()
    check("1 MB letter in 11 writes arrives byte-identical (%.1f ms to deliver)" % (dt * 1000),
          hashlib.sha256(back).digest() == hashlib.sha256(data).digest() and os.stat(mb + "/new/big").st_size == len(data))
    st = ctl_done(root, "take")
    check("take reports 1048576 bytes; mail_bytes back to 0", mail(st, "last_bytes", "bytes") == ("1048576", "0"), st)
    stop(p, root)


TESTS = {"shell": t_shell, "half": t_half, "clash": t_clash, "limits": t_limits, "refuse": t_refuse, "take": t_take,
         "stale": t_stale, "big": t_big, "guards": t_guards, "folder": t_folder, "aospost": t_aospost,
         "stopped": t_stopped, "many": t_many}


def main():
    names = sys.argv[1:] or list(TESTS)
    if not os.path.exists(DEMO):
        print("FAIL  demo not built: %s (run make)" % DEMO)
        return 1
    try:
        for n in names:
            print("== %s" % n, flush=True)
            try:
                TESTS[n]()
            except Exception as e:
                check("%s raised" % n, False, repr(e))
    finally:
        cleanup()
    procs, mounts = leftovers()
    check("no leftover processes or mounts", not procs and not mounts, (procs, mounts))
    print("%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
