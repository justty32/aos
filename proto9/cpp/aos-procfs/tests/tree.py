#!/usr/bin/env python3
# tree.py：remove_tree 的測試——掛上之後加一整棵夾、拿掉（連同底下）、拿掉後路徑馬上走不到、開著的檔照舊讀完、同名再加看到新的、ctl 與信箱不給拿、邊讀邊加拿不卡。
"""用法：python3 tests/tree.py [測試名 ...]   （不給＝全部；名字見 TESTS）"""
import errno, os, sys, time
from common import start_demo, sh, bg, status, wait_until, mounted, leftovers, check, RESULTS


def ctl(root, line, timeout=5.0):
    """寫一道指令（demo 起時給了 --ctl-wait：寫入回來就做完了）；回 (寫入的 errno 或 0, status)。"""
    err = 0
    try:
        fd = os.open(root + "/ctl", os.O_WRONLY)
        try:
            os.write(fd, (line + "\n").encode())
        finally:
            os.close(fd)
    except OSError as e:
        err = e.errno
    return err, status(root) or {}


def read(p):
    with open(p) as f:
        return f.read()


def t_basic():
    p, pid, root, mnt = start_demo("tree", "--ctl-wait")
    t = root + "/trees"
    err, st = ctl(root, "tree a")
    check("tree a: write ok, done", err == 0 and st.get("aos_ctl_state") == "done", (err, st))
    check("trees/a/ has info, count, sub, link", sorted(os.listdir(t + "/a")) == ["count", "info", "link", "sub"],
          os.listdir(t + "/a"))
    check("files read right (info, sub/deep, link)", read(t + "/a/info") == "tree: a\n" and
          read(t + "/a/sub/deep") == "deep\n" and read(t + "/a/link") == "tree: a\n")
    err, st = ctl(root, "tree a")
    check("same name again: EIO, failed TreeFailed, the first tree untouched",
          err == errno.EIO and st.get("aos_ctl_error", "").startswith("TreeFailed") and read(t + "/a/info") == "tree: a\n",
          (err, st))

    # 先讓核心快取 trees/a（entry_valid 1 秒），開著一個檔、一個夾，再拿掉
    os.stat(t + "/a")
    os.stat(t + "/a/sub/deep")
    f = open(t + "/a/count")
    dfd = os.open(t + "/a", os.O_RDONLY | os.O_DIRECTORY)
    first = read(t + "/a/count")
    t0 = time.monotonic()
    err, st = ctl(root, "rmtree trees/a")
    gone = not os.path.lexists(t + "/a") and not os.path.lexists(t + "/a/sub/deep")
    dt = time.monotonic() - t0
    check("rmtree trees/a: write ok, done", err == 0 and st.get("aos_ctl_state") == "done", (err, st))
    check("right after it returns the path is gone, though the kernel had it cached (%.0f ms)" % (dt * 1000), gone and dt < 0.5)
    check("ls trees/ no longer lists it", "a" not in os.listdir(t), os.listdir(t))
    v = f.read()
    check("a file opened before still reads what it had at open", v == "1\n" and first == "2\n", (v, first))
    try:
        f.close()
        closed = True
    except OSError as e:
        closed = e
    check("... and closes without error", closed is True, closed)
    try:
        os.stat("sub", dir_fd=dfd)
        r = "ok"
    except OSError as e:
        r = errno.errorcode.get(e.errno)
    check("a lookup from a dir fd opened before: ENOENT", r == "ENOENT", r)
    try:
        names = sorted(os.listdir(dfd))
    except OSError as e:
        names = errno.errorcode.get(e.errno)
    check("listing that dir fd: ENOENT or the old names, no hang", names in ("ENOENT", ["count", "info", "link", "sub"]), names)
    os.close(dfd)

    err, st = ctl(root, "tree a")
    check("same name again right away: new tree visible at once", err == 0 and read(t + "/a/count") == "1\n",
          (err, st))
    err, st = ctl(root, "rmtree trees/a/sub/deep")
    check("rmtree of one text file: only that file goes", err == 0 and not os.path.lexists(t + "/a/sub/deep") and
          os.path.isdir(t + "/a/sub") and read(t + "/a/info") == "tree: a\n", (err, st))
    err, st = ctl(root, "rmtree trees/a/link")
    check("rmtree of a symlink works too", err == 0 and not os.path.lexists(t + "/a/link"), (err, st))
    err, st = ctl(root, "rmtree trees/a")
    check("rmtree of the rest", err == 0 and not os.path.lexists(t + "/a"), (err, st))

    for path in ("ctl", "mailbox", "mailbox/new", "trees/nothere", "/", "."):
        err, st = ctl(root, "rmtree " + path)
        check("rmtree %s refused: EIO, failed RemoveRefused" % path,
              err == errno.EIO and st.get("aos_ctl_error", "").startswith("RemoveRefused"), (err, st))
    check("ctl, mailbox and status all still there", os.path.isdir(root + "/mailbox/new") and
          (status(root) or {}).get("aos_name") == "tree")
    err, st = ctl(root, "rmtree trees")
    check("rmtree trees (a plain dir the demo made before mount) works", err == 0 and not os.path.lexists(t), (err, st))
    err, st = ctl(root, "tree b")
    check("tree under a removed dir: EIO, failed", err == errno.EIO and st.get("aos_ctl_state") == "failed", (err, st))
    sh("echo stop > %s/ctl" % root)
    p.wait(5)
    check("stops cleanly", not mounted(mnt))


def t_busy(threads="1"):
    """邊讀邊加拿：兩支殼一直讀 trees/x 底下的檔，同時加拿 200 次；讀的人都在限時內結束、伺服器沒事。"""
    p, pid, root, mnt = start_demo("busy" + threads, "--threads", threads)
    t = root + "/trees/x"
    readers = [bg("end=$((SECONDS+30)); while [ $SECONDS -lt $end ]; do "
                  "cat %s/info %s/sub/deep %s/count >/dev/null 2>&1; ls %s >/dev/null 2>&1; done" % (t, t, t, t))
               for _ in range(2)]
    bad = 0
    for i in range(200):
        for line in ("tree x", "rmtree trees/x"):
            # 預設的 ctl（不是做完才回）：等這一道做完再下一道
            fd = os.open(root + "/ctl", os.O_WRONLY)
            os.write(fd, (line + "\n").encode())
            os.close(fd)
            if not wait_until(lambda: (status(root) or {}).get("aos_ctl_state") in ("done", "failed"), 5):
                bad += 1
    check("threads %s: 200 add/remove rounds under two busy readers, every command finished" % threads, bad == 0, bad)
    st = status(root) or {}
    check("threads %s: status still answers, last command done" % threads, st.get("aos_ctl_state") == "done", st)
    check("threads %s: nothing left under trees/" % threads, os.listdir(root + "/trees") == [])
    for r in readers:
        r.kill()
    t0 = time.monotonic()
    ok = all(wait_until(lambda: r.poll() is not None, 5) for r in readers)
    check("threads %s: readers end at once (no one stuck in the kernel)" % threads, ok and time.monotonic() - t0 < 5)
    sh("echo stop > %s/ctl" % root)
    p.wait(5)
    check("threads %s: stops cleanly" % threads, not mounted(mnt))


TESTS = {"basic": t_basic, "busy": lambda: t_busy("1"), "busy4": lambda: t_busy("4")}


def main():
    names = sys.argv[1:] or list(TESTS)
    for n in names:
        try:
            TESTS[n]()
        except Exception as e:
            check("%s raised %r" % (n, e), False)
    alive, mounts = leftovers()
    check("no leftover processes or mounts", not alive and not mounts, (alive, mounts))
    fails = RESULTS.count(False)
    print("%d passed, %d failed" % (len(RESULTS) - fails, fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
