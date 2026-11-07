"""Write, promote and remove knowledge nodes atomically under directory locks."""
import json
import os
import shutil
import signal
import stat
import tempfile
import time
import uuid

import memory_fs as fs
import tool_io
from locking import check_descendants, with_lock


def discard(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.unlink(path)


def clean_old(folder):
    for name in os.listdir(folder):
        if name.startswith((".tmp.", ".new.", ".rm.")):
            path = os.path.join(folder, name)
            try:
                if time.time() - os.lstat(path).st_mtime > 600:
                    discard(path)
            except FileNotFoundError:
                pass


def text_bytes(text, target=""):
    if not isinstance(text, str):
        tool_io.die("TextBad", "text must be a UTF-8 string")
    try:
        raw = text.encode("utf-8")
    except UnicodeError:
        tool_io.die("TextBad", "text must be a UTF-8 string")
    if not text.endswith("\n"):
        raw += b"\n"
    if len(raw) > 8000:
        tool_io.die("TextBad", "text exceeds 8000 bytes; split into child nodes")
    if target.endswith(".json"):
        try:
            json.loads(text)
        except ValueError:
            tool_io.die("TextBad", "text for a JSON leaf must be valid JSON")
    elif not text.splitlines() or not text.splitlines()[0].startswith("# "):
        tool_io.die("TextBad", "text must start with # Title")
    return raw


def write_text(target, raw, exclusive=False, mode=None):
    target = os.path.realpath(target)
    fd, temporary = tempfile.mkstemp(prefix=".tmp.", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "wb") as stream:
            if mode is None and os.path.exists(target):
                mode = stat.S_IMODE(os.stat(target).st_mode)
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.write(raw)
        if exclusive:
            try:
                os.link(temporary, target)
            except FileExistsError:
                tool_io.die("NodeExists", "node already exists")
        else:
            os.replace(temporary, target)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def ensure_absent(root, segs):
    base = os.path.join(root, *segs)
    if any(os.path.lexists(base + ext) for ext in ("", ".md", ".json")):
        tool_io.die("NodeExists", "node %s already exists" % fs.show(segs))


def add(root, segs, text):
    raw = text_bytes(text)
    kind, parent = fs.node_or_die(root, segs[:-1])
    if kind == "leaf" and parent.endswith(".json"):
        tool_io.die("PathBad", "node %s is a JSON leaf; it cannot have child nodes" % fs.show(segs[:-1]))
    lock_folder = parent if kind == "dir" else os.path.dirname(parent)
    with with_lock(lock_folder, "memory_write add " + fs.show(segs)) as locked:
        clean_old(locked.folder)
        kind, parent = fs.node_or_die(root, segs[:-1])
        if kind == "leaf" and parent.endswith(".json"):
            tool_io.die("PathBad", "node %s is a JSON leaf; it cannot have child nodes" % fs.show(segs[:-1]))
        ensure_absent(root, segs)
        if kind == "dir":
            write_text(os.path.join(parent, segs[-1] + ".md"), raw, exclusive=True)
        else:
            old_text = fs.read_text(kind, parent).encode("utf-8")
            destination = os.path.join(root, *segs[:-1])
            temporary = tempfile.mkdtemp(prefix=".new.", dir=os.path.dirname(destination))
            try:
                mode = stat.S_IMODE(os.stat(parent).st_mode)
                write_text(os.path.join(temporary, "README.md"), old_text, mode=mode)
                write_text(os.path.join(temporary, segs[-1] + ".md"), raw, exclusive=True)
                os.rename(temporary, destination)
                os.unlink(parent)
            finally:
                if os.path.lexists(temporary):
                    discard(temporary)
    return len(raw)


def edit(root, segs, text):
    kind, where = fs.node_or_die(root, segs)
    target = os.path.realpath(os.path.join(where, "README.md") if kind == "dir" else where)
    if target == os.path.realpath(os.path.join(root, "README.md")):
        tool_io.die("PathBad", "root is read-only; a human edits it")
    raw = text_bytes(text, where if kind == "leaf" else "")
    with with_lock(os.path.dirname(target), "memory_write edit " + fs.show(segs)) as locked:
        clean_old(locked.folder)
        kind, where = fs.node_or_die(root, segs)
        target = os.path.realpath(os.path.join(where, "README.md") if kind == "dir" else where)
        if target == os.path.realpath(os.path.join(root, "README.md")):
            tool_io.die("PathBad", "root is read-only; a human edits it")
        raw = text_bytes(text, where if kind == "leaf" else "")
        write_text(target, raw)
    return len(raw)


def remove(root, segs, recursive):
    kind, where = fs.node_or_die(root, segs)
    # Unlinking a link changes its containing directory, never its target.
    folder = os.path.dirname(where)
    with with_lock(folder, "memory_write rm " + fs.show(segs)) as locked:
        clean_old(locked.folder)
        kind, where = fs.node_or_die(root, segs)
        if os.path.islink(where):
            os.unlink(where)
        elif kind == "leaf":
            os.unlink(where)
        else:
            with with_lock(where, "memory_write rm " + fs.show(segs)) as node_lock:
                kind, where = fs.node_or_die(root, segs)
                if fs.children(kind, where) and not recursive:
                    tool_io.die("ChildrenExist", "node %s has children; use recursive: true" % fs.show(segs))
                if recursive:
                    check_descendants(where)
                renamed = os.path.join(folder, ".rm." + uuid.uuid4().hex)
                # Register release at the renamed path before handling termination.
                old = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                try:
                    os.rename(where, renamed)
                    node_lock.release(renamed)
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, old)
            shutil.rmtree(renamed)
