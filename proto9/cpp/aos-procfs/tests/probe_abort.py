#!/usr/bin/env python3
# probe_abort.py：實測「伺服器不回答時讀的人卡住；往 /sys/fs/fuse/connections/<編號>/abort 寫 1 會怎樣」，印出觀察。
import os, signal, time
from common import start_demo, bg, sh, our_mounts, leftovers, cleanup


def conn_of(mnt):
    with open("/proc/self/mountinfo") as f:
        for line in f:
            p = line.split()
            if p[4] == mnt:
                maj, mi = map(int, p[2].split(":"))
                return maj, mi, (maj << 20) | mi
    return None


def state_of(pid):
    try:
        s = open("/proc/%d/stat" % pid).read()
        st = s[s.rindex(")") + 2]
        wchan = open("/proc/%d/wchan" % pid).read()
        return "%s wchan=%s" % (st, wchan)
    except OSError as e:
        return "gone (%s)" % e.strerror


def main():
    p, pid, root, mnt = start_demo("abort")
    maj, mi, cid = conn_of(mnt)
    print("mountinfo dev %d:%d -> connection %d; exists in /sys/fs/fuse/connections: %s"
          % (maj, mi, cid, os.path.isdir("/sys/fs/fuse/connections/%d" % cid)))
    os.kill(pid, signal.SIGSTOP)
    t0 = time.monotonic()
    # 先只放一個讀的人，看它卡在哪、SIGKILL 殺不殺得掉
    victim = bg("cat %s/status" % root)
    time.sleep(1.0)
    print("one reader, server SIGSTOPped 1s: %s, rc=%s" % (state_of(victim.pid), victim.poll()))
    print("waiting =", open("/sys/fs/fuse/connections/%d/waiting" % cid).read().strip())
    victim.kill()
    time.sleep(0.3)
    print("after SIGKILL to it: %s, rc=%s" % (state_of(victim.pid), victim.poll()))
    print("waiting =", open("/sys/fs/fuse/connections/%d/waiting" % cid).read().strip())
    reader = bg("cat %s/status" % root)
    reader2 = bg("cat %s/settings" % root)
    time.sleep(1.0)
    print("two more readers 1s: %s / %s" % (state_of(reader.pid), state_of(reader2.pid)))
    print("waiting =", open("/sys/fs/fuse/connections/%d/waiting" % cid).read().strip())
    with open("/sys/fs/fuse/connections/%d/abort" % cid, "w") as f:
        f.write("1")
    try:
        out, err = reader.communicate(timeout=3)
        print("after abort: reader rc=%s stderr=%r (stuck %.1fs total)" % (reader.returncode, err.strip(), time.monotonic() - t0))
        out, err = reader2.communicate(timeout=3)
        print("after abort: reader2 rc=%s stderr=%r" % (reader2.returncode, err.strip()))
    except Exception as e:
        print("after abort: reader still stuck (%s)" % e)
    print("mount still in /proc/mounts:", mnt in our_mounts())
    print("stat mountpoint:", sh("stat -c %%i %s" % mnt)[2].strip())
    print("ls /proc/PID/cwd/:", sh("ls %s/" % root)[2].strip())
    print("cat status again:", sh("cat %s/status" % root)[2].strip())
    os.kill(pid, signal.SIGCONT)
    try:
        rc = p.wait(5)
        print("server after SIGCONT: exited rc=%s stderr=%r" % (rc, p.stderr.read().decode().strip()))
    except Exception:
        print("server after SIGCONT: still running")
    print("mount after server exit:", mnt in our_mounts(), "; dir exists:", os.path.isdir(mnt))
    cleanup()
    print("leftovers:", leftovers())


if __name__ == "__main__":
    main()
