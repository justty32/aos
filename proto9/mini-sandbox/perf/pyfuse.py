"""A minimal FUSE server in pure Python (one read-only file "f" whose content is read again from BACKING on every open) that mounts itself with mount(2) inside a user+mount namespace; used by perf/dynbench.py to price "ask a service on every read"."""
# usage (inside unshare -Urm): python3 pyfuse.py MOUNTPOINT TTL BACKING [HANGFLAG]
#   TTL: entry/attr cache seconds (0 = ask every time); HANGFLAG: if this file exists when an OPEN comes in,
#   never answer (a stuck service).
import errno
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MS_NODEV, MS_NOSUID, mount  # noqa: E402

mnt, ttl, backing = sys.argv[1], int(sys.argv[2]), sys.argv[3]
hang = sys.argv[4] if len(sys.argv) > 4 else None
IN = struct.Struct("<IIQQIIIHH")
OUT = struct.Struct("<IiQ")
ATTR = struct.Struct("<QQQQQQIIIIIIIIII")
fd = os.open("/dev/fuse", os.O_RDWR)
mount("pyfuse", mnt, "fuse.pyfuse", MS_NOSUID | MS_NODEV,
      "fd=%d,rootmode=40000,user_id=0,group_id=0,default_permissions" % fd)
print("READY", os.getpid(), flush=True)


def attr(nid):
    now = int(time.time())
    mode = 0o40555 if nid == 1 else 0o100444
    return ATTR.pack(nid, 0, 0, now, now, now, 0, 0, 0, mode, 2 if nid == 1 else 1, 0, 0, 0, 4096, 0)


def reply(u, err=0, data=b""):
    try:
        os.write(fd, OUT.pack(OUT.size + len(data), -err, u) + data)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


fh, nxt = {}, 1
while True:
    try:
        buf = os.read(fd, (1 << 20) + 4096)
    except OSError as e:
        if e.errno in (errno.EINTR, errno.EAGAIN, errno.ENOENT):
            continue
        break  # ENODEV: unmounted
    ln, op, u, nid, _uid, _gid, _pid, _e, _p = IN.unpack_from(buf)
    body = buf[IN.size:ln]
    if op == 26:  # INIT
        major_minor = struct.unpack_from("<IIII", body)
        reply(u, 0, struct.pack("<IIIIHHIIHHI", 7, 31, major_minor[2], 0, 16, 12, 1 << 17, 1, 0, 0, 0) + b"\0" * 28)
    elif op in (2, 42, 36):  # FORGET, BATCH_FORGET, INTERRUPT: no reply
        pass
    elif op == 1:  # LOOKUP
        name = body.split(b"\0", 1)[0]
        if nid == 1 and name == b"f":
            reply(u, 0, struct.pack("<QQQQII", 2, 0, ttl, ttl, 0, 0) + attr(2))
        else:
            reply(u, errno.ENOENT)
    elif op == 3:  # GETATTR
        reply(u, 0, struct.pack("<QII", ttl, 0, 0) + attr(nid))
    elif op == 14:  # OPEN: "ask the service" = read the backing file now
        if hang and os.path.exists(hang):
            time.sleep(10 ** 6)
        with open(backing, "rb") as b:
            fh[nxt] = b.read()
        reply(u, 0, struct.pack("<QII", nxt, 1, 0))  # FOPEN_DIRECT_IO
        nxt += 1
    elif op == 15:  # READ
        h, off, size = struct.unpack_from("<QQI", body)
        reply(u, 0, fh.get(h, b"")[off:off + size])
    elif op == 18:  # RELEASE
        fh.pop(struct.unpack_from("<Q", body)[0], None)
        reply(u)
    elif op in (25, 29):  # FLUSH, RELEASEDIR
        reply(u)
    elif op == 27:  # OPENDIR
        reply(u, 0, struct.pack("<QII", 0, 0, 0))
    elif op == 28:  # READDIR
        h, off, size = struct.unpack_from("<QQI", body)
        out = b""
        for i, (nm, c, t) in enumerate([(b".", 1, 4), (b"..", 1, 4), (b"f", 2, 8)][off:], start=off):
            e = struct.pack("<QQII", c, i + 1, len(nm), t) + nm
            out += e + b"\0" * (-len(e) % 8)
        reply(u, 0, out)
    elif op == 38:  # DESTROY
        reply(u)
        break
    else:
        reply(u, errno.ENOSYS)
