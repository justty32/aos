"""aos_sweep_files 清道夫的檔案那半：stderr 的 copytruncate 封存（gzip）、封存檔名的 UTC 時間戳、保留期刪除、purge、.bad- 計數；aos_sweep 叫它。
只認自己寫的檔名樣式（<UTC 毫秒>[-N]<副檔名>.gz、點開頭的 .…gz.tmp），封存夾裡別人的檔不碰。"""
import datetime
import errno
import gzip
import os
import re
import stat
import zlib

CHUNK = 1 << 20
_STAMP = r"\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d\.\d{3}Z"
ARCHIVE_RE = re.compile(r"^(%s)(?:-\d+)?(?:\.[^/]*)?\.gz$" % _STAMP)   # 自己寫的封存檔；同一毫秒撞名加 -N
TMP_RE = re.compile(r"^\.%s.*\.gz\.tmp$" % _STAMP)                     # 自己寫一半的暫存（點開頭＝已被 **/.* 擋）


def stamp(t):
    """UTC 毫秒、冒號換成 -（跟 .bad- 留證檔同一種時間戳）。"""
    dt = datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H-%M-%S.") + "%03dZ" % (dt.microsecond // 1000)


def stamp_time(name):
    """封存檔名的時間（epoch 秒）；不是自己的樣式＝None。"""
    m = ARCHIVE_RE.match(name)
    if not m:
        return None
    try:
        dt = datetime.datetime.strptime(m.group(1)[:-1], "%Y-%m-%dT%H-%M-%S.%f")
    except ValueError:
        return None
    return dt.replace(tzinfo=datetime.timezone.utc).timestamp()


def archive_dir(stack, err_name):
    """（封存夾, 副檔名）：stderr.txt → stderr_archives/、.txt；err.log → err_archives/、.log。"""
    stem, ext = os.path.splitext(err_name)
    return os.path.join(stack, (stem or err_name) + "_archives"), ext


def archive_one(rep, name, stack, err_name, min_bytes, dry_run, now):
    """超過門檻的 stderr 複製成 gzip 封存、再截成 0。只有封存檔寫到檔尾、flush 成功並改成正式名之後才截。"""
    path = os.path.join(stack, err_name)
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as e:
        return rep.warn("%s: cannot look at %s: %s; left alone" % (name, path, e.strerror or e))
    if not stat.S_ISREG(st.st_mode):
        return rep.warn("%s: %s is not a regular file (symlink or other); left alone" % (name, path))
    if st.st_nlink > 1:
        return rep.warn("%s: %s has %d hard links; left alone" % (name, path, st.st_nlink))
    if st.st_size < min_bytes:
        return
    adir, ext = archive_dir(stack, err_name)
    final = os.path.join(adir, stamp(now) + ext + ".gz")
    n = 1
    while os.path.lexists(final):
        final = os.path.join(adir, "%s-%d%s.gz" % (stamp(now), n, ext))
        n += 1
    item = {"name": name, "file": path, "archive": final, "bytes": st.st_size}
    if dry_run:
        rep.data["archived"].append(item)
        return
    try:
        os.makedirs(adir, exist_ok=True)
        if not stat.S_ISDIR(os.lstat(adir).st_mode):
            raise OSError(errno.ENOTDIR, "not a folder")
    except OSError as e:
        return rep.warn("%s: cannot use archive folder %s: %s; %s not archived" % (name, adir, e.strerror or e, path))
    clean_tmps(rep, adir)
    tmp = os.path.join(adir, "." + os.path.basename(final) + ".tmp")
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as e:
        return rep.warn("%s: cannot open %s: %s; left alone" % (name, path, e.strerror or e))
    try:
        fst = os.fstat(fd)
        if (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
            return rep.warn("%s: %s was replaced while looking at it; left alone this round" % (name, path))
        copied = _copy_truncate(rep, name, fd, path, tmp, final, err_name)
    finally:
        os.close(fd)
    if copied is not None:
        item["bytes"] = copied
        rep.data["archived"].append(item)


def _copy_truncate(rep, name, fd, path, tmp, final, err_name):
    """串流 gzip 到 tmp → 補抄增量到很小 → flush → 改正式名 → 抄最後一點 → 截 0 → 關檔。回抄了幾位元組；沒截＝None。"""
    pos = 0
    raw = gz = None

    def pump():
        nonlocal pos
        while True:
            b = os.pread(fd, CHUNK, pos)
            if not b:
                return
            gz.write(b)
            pos += len(b)
    try:
        raw = open(tmp, "xb")
        gz = gzip.GzipFile(filename=err_name, mode="wb", fileobj=raw)
        pump()
        for _ in range(5):                     # 狂寫的零件：追到增量 < 64 KiB 再截，把會掉的窗縮到最小
            if os.fstat(fd).st_size - pos < 65536:
                break
            pump()
        gz.flush(zlib.Z_SYNC_FLUSH)
        raw.flush()
        os.fsync(raw.fileno())
        os.rename(tmp, final)
    except OSError as e:
        for f in (gz, raw):
            try:
                if f is not None:
                    f.close()
            except OSError:
                pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        rep.warn("%s: cannot write archive %s: %s; %s not truncated" % (name, final, e.strerror or e, path))
        return None
    try:
        pump()
        os.ftruncate(fd, 0)
    except OSError as e:
        rep.warn("%s: archived to %s but cannot truncate %s: %s (the next round archives it again)" % (name, final, path, e.strerror or e))
        pos = None
    try:
        gz.close()
        raw.close()
    except OSError as e:
        rep.warn("%s: archive %s may be incomplete at its end: %s" % (name, final, e.strerror or e))
    return pos


def clean_tmps(rep, adir):
    """上一輪寫一半被殺留下的自己的暫存：刪掉（拿著鎖，不會有人正在寫）。"""
    try:
        names = os.listdir(adir)
    except OSError:
        return
    for n in names:
        if TMP_RE.match(n):
            try:
                os.unlink(os.path.join(adir, n))
            except OSError as e:
                rep.warn("cannot remove stale %s: %s" % (os.path.join(adir, n), e.strerror or e))


def own_files(adir):
    """封存夾裡自己的封存檔：[(路徑, 大小, 檔名時間)]，只算一般檔。"""
    out = []
    try:
        names = sorted(os.listdir(adir))
    except OSError:
        return out
    for n in names:
        t = stamp_time(n)
        if t is None:
            continue
        p = os.path.join(adir, n)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        if stat.S_ISREG(st.st_mode):
            out.append((p, st.st_size, t))
    return out


def expire(rep, label, adir, days, dry_run, now):
    """刪檔名時間超過保留期的封存檔（看檔名不看 mtime：cp 搬過 mtime 會變）。"""
    gone, size = 0, 0
    for p, b, t in own_files(adir):
        if now - t <= days * 86400:
            continue
        if not dry_run:
            try:
                os.unlink(p)
            except OSError as e:
                rep.warn("%s: cannot remove expired %s: %s" % (label, p, e.strerror or e))
                continue
        gone, size = gone + 1, size + b
    if gone:
        rep.data["expired"].append({"name": label, "dir": adir, "files": gone, "bytes": size})


def purge_dir(rep, label, adir, dry_run):
    """刪封存夾裡自己的封存檔與暫存，空了把夾也拿掉；別人的檔留著、提醒一次。"""
    try:
        names = os.listdir(adir)
    except FileNotFoundError:
        return
    except OSError as e:
        return rep.warn("%s: cannot list %s: %s" % (label, adir, e.strerror or e))
    gone, size, other = 0, 0, 0
    for n in names:
        p = os.path.join(adir, n)
        if not (ARCHIVE_RE.match(n) or TMP_RE.match(n)):
            other += 1
            continue
        try:
            st = os.lstat(p)
            if not stat.S_ISREG(st.st_mode):
                other += 1
                continue
            if not dry_run:
                os.unlink(p)
        except OSError as e:
            rep.warn("%s: cannot remove %s: %s" % (label, p, e.strerror or e))
            continue
        gone, size = gone + 1, size + st.st_size
    if other:
        rep.warn("%s: %d file(s) in %s are not archives written by the sweeper; left alone" % (label, other, adir))
    elif not dry_run:
        try:
            os.rmdir(adir)
        except OSError:
            pass
    rep.data["purged"].append({"name": label, "dir": adir, "files": gone, "bytes": size})


def count_bad(folder):
    """資料夾頂層 *.bad-* 留證檔的數量（使用者 11-09「擋掉，不自動清」：只數不碰）。"""
    try:
        return sum(1 for n in os.listdir(folder) if ".bad-" in n)
    except OSError:
        return 0