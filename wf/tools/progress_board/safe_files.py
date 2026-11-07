"""Read bounded UTF-8 text only from regular allowed files beneath configured roots."""

import datetime as dt
import os
from pathlib import Path
import stat

SUFFIXES = {".md", ".txt", ".log", ".json", ".jsonl"}


class ApiError(Exception):
    def __init__(self, status, code, reason):
        super().__init__(f"{code} {reason}")
        self.status = status


def _inside_roots(cfg, path):
    for root in cfg.get("read_roots", []):
        root = os.path.realpath(os.path.expanduser(root))
        try:
            if os.path.commonpath((root, path)) == root:
                return True
        except ValueError:
            continue
    return False


def safe_read(cfg, path, max_bytes, *, tail=False):
    """Return file metadata and bounded text; tail reads only the final max_bytes."""
    try:
        path = os.path.realpath(os.path.expanduser(os.fspath(path)))
    except (TypeError, ValueError, OSError):
        raise ApiError(403, "PathRefused", "File path is invalid") from None
    if not _inside_roots(cfg, path):
        raise ApiError(403, "RootRefused", "File is outside configured read_roots")
    if Path(path).suffix not in SUFFIXES:
        raise ApiError(403, "SuffixRefused", "File suffix is not allowed")
    try:
        # O_NONBLOCK avoids hanging if a regular file is replaced by a FIFO.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            actual = os.path.realpath(f"/proc/self/fd/{stream.fileno()}")
            if not _inside_roots(cfg, actual):
                raise ApiError(403, "RootRefused", "Opened file is outside read_roots")
            if Path(actual).suffix not in SUFFIXES:
                raise ApiError(403, "SuffixRefused", "Opened file suffix is not allowed")
            if not stat.S_ISREG(info.st_mode):
                raise ApiError(403, "TypeRefused", "Path must be a regular file")
            offset = max(0, info.st_size - max_bytes) if tail else 0
            if offset:
                stream.seek(offset)
            raw = stream.read(max_bytes)
    except FileNotFoundError:
        raise ApiError(404, "FileMissing", "File does not exist") from None
    except OSError:
        raise ApiError(403, "ReadRefused", "File could not be read safely") from None
    return {"path": path, "mtime": dt.datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(),
            "size": info.st_size, "text": raw.decode("utf-8", errors="replace"),
            "truncated": info.st_size > max_bytes}


def file_payload(value):
    return {key: value[key] for key in ("path", "mtime", "text", "truncated")}
