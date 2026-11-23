#!/usr/bin/env python3
# stack_paths.py - 一次性的改表工具（templates 三分切換用，規格在 06f）：照 06a 對照表把一棵樹每台 daemon 的 stack（與 --defs 給的定義夾）裡的舊範本路徑換成新路徑；預設只列不改，--apply 先備份、記清冊、改完重新解析 JSON 並數命中為 0，--restore 照清冊蓋回。
"""Rewrite old proto8/templates paths to the tri-split layout (06a table) in a stopped tree's stacks.

Default: list only (every daemon, every file, every "old -> new"; nothing is written).
--apply: back up each file to <file>.bak-trisplit-1124, append it to the manifest, rewrite it,
         parse it again as JSON and count the hits again (must be 0).
--restore MANIFEST: copy the backups back over the files (newest first).
--defs DIR...: the same for every *.json under definition folders (other projects).

Safety:
- --apply / --restore take an exclusive flock on every daemon stack of the tree (the same lock
  aos-daemon takes on its stack); a lock that cannot be taken = a daemon of this tree is running
  = refuse (exit 2). The locks are held until the end, so no daemon of this tree can start meanwhile.
- --apply / --restore also refuse while ANY aos-daemon process runs on this machine (06f), unless
  --allow-other-daemons is given; then only this tree's locks decide (they are proof, the process
  list is not). List mode takes no lock and refuses nothing (06e step 12 runs it on a live tree).
- Nothing from the environment is printed or stored; output = paths, JSON pointers and the
  replaced segment only.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import time

SUFFIX = ".bak-trisplit-1124"
DEFAULT_MANIFEST = os.path.expanduser("~/.aos/scratch/tri-split-1123/out/manifest.tsv")
TABLE = "procs_state.json"
ROW_FILES = ("exec.json", "loop.json", "tools.json", "llm.json", "hookeds.json", "subagents.json")
SKIP_DIRS = {"mailbox", "queue", "think", "claude", ".git", "__pycache__", "node_modules"}
SKIP_FILE_PREFIX = ("history", "stderr")
LIST_MAX_BYTES = 512 * 1024

# 06a table. Files first (they are longer), then folders; the alternation lists longer names first.
FSM_FILES = ("idle", "brain", "wait", "act", "compact", "cell_common", "atomic_file", "llm_settings")
FOLDERS = {
    "eca-claude-alt": "agents/eca-claude-alt",
    "agent-python": "agents/agent-python",
    "agent-fsm": "agents/agent-fsm",
    "eca-claude": "agents/eca-claude",
    "reviewer": "agents/reviewer",
    "eca-pi": "agents/eca-pi",
    "kits": "agents/kits",
    "kernel": "kernels",
    "daemon-root": "daemons/daemon-root",
    "daemon-sub": "daemons/daemon-sub",
    "start-api": "starts/start-api",
    "start-eca": "starts/start-eca",
    "tool-python": "tools/tool-python",
    "judge-llm": "tools/judge-llm",
}
_files = "|".join(["agent-fsm/(?:%s)\\.py" % "|".join(FSM_FILES), "agent-fsm/hooks\\.json"])
_dirs = "|".join(re.escape(n) for n in sorted(FOLDERS, key=len, reverse=True))
# Boundary: 06a says / " # whitespace ) ` or end of line; ' and \ added (a path inside a quoted shell string in JSON).
PATTERN = re.compile(r"(?<![A-Za-z0-9_.\-])templates/(?:(?P<file>%s)|(?P<dir>%s))(?=[/\"#\s)`'\\]|$)" % (_files, _dirs), re.M)


def _new(m):
    if m.group("file"):
        return "lib/aos/apps/agent_fsm/" + m.group("file").split("/", 1)[1]
    return "templates/" + FOLDERS[m.group("dir")]


def sub_text(s):
    return PATTERN.sub(_new, s)


def hits_text(s):
    return [(m.group(0), _new(m)) for m in PATTERN.finditer(s)]


def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8", "surrogateescape")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def walk_strings(v, ptr=""):
    """(pointer, string) for every string in a JSON value, keys included (pointer of a key ends with '<key>')."""
    if isinstance(v, str):
        yield ptr, v
    elif isinstance(v, dict):
        for k, x in v.items():
            p = ptr + "/" + k.replace("~", "~0").replace("/", "~1")
            yield p + " <key>", k
            yield from walk_strings(x, p)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from walk_strings(x, "%s/%d" % (ptr, i))


def map_strings(v):
    if isinstance(v, str):
        return sub_text(v)
    if isinstance(v, dict):
        return {sub_text(k): map_strings(x) for k, x in v.items()}
    if isinstance(v, list):
        return [map_strings(x) for x in v]
    return v


class Plan:
    def __init__(self):
        self.change = []      # (kind, daemon_stack, path)
        self.listed = []      # (path, [line numbers])
        self.seen = set()
        self.daemons = []
        self.notes = []
        self.errors = []

    def add_change(self, kind, dstack, path):
        rp = os.path.realpath(path)
        if rp in self.seen or not os.path.isfile(path):
            return
        self.seen.add(rp)
        self.change.append((kind, dstack, path))


def table_files(dstack, plan):
    """procs_state.json and its $ref part files -> (files, merged rows)."""
    main = os.path.join(dstack, TABLE)
    try:
        doc = json.loads(read_text(main))
    except (OSError, ValueError) as e:
        plan.errors.append("%s: cannot read the table (%s)" % (main, e.__class__.__name__))
        return [], {}
    files = [main]
    procs = doc.get("procs") if isinstance(doc, dict) else None
    rows = {}
    if isinstance(procs, dict) and "$ref" in procs:
        refs = procs["$ref"]
        for ref in refs if isinstance(refs, list) else [refs]:
            if not isinstance(ref, str):
                plan.errors.append("%s: a $ref entry is not a string; part files not followed" % main)
                continue
            fpart, _, frag = ref.partition("#")
            part = fpart if os.path.isabs(fpart) else os.path.join(dstack, fpart)
            files.append(part)
            try:
                v = json.loads(read_text(part))
                for key in [k for k in frag.split("/") if k]:
                    v = v[key.replace("~1", "/").replace("~0", "~")]
                if isinstance(v, dict):
                    rows.update(v)
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                plan.errors.append("%s: cannot read the part file %s" % (main, part))
    elif isinstance(procs, dict):
        rows = procs
    else:
        plan.errors.append("%s: no procs object" % main)
    return files, rows


def row_stack(dstack, name, row):
    st = row.get("stack")
    if not (isinstance(st, str) and st):
        launch = row.get("launch")
        st = launch.get("stack") if isinstance(launch, dict) else None
    if not (isinstance(st, str) and st):
        st = os.path.join("procs", name)
    return st if os.path.isabs(st) else os.path.normpath(os.path.join(dstack, st))


def json_files_named(v, base):
    """Absolute paths of 'file.json#...' strings and {"$env": "AOS_DAEMON", "$path": ...} directives in a row."""
    out = []
    for _, s in walk_strings(v):
        if "#" in s and ".json" in s:
            f = s.split("#", 1)[0]
            if f.endswith(".json"):
                out.append(f if os.path.isabs(f) else os.path.join(base, f))
    stack = [v]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x.get("$env") == "AOS_DAEMON" and isinstance(x.get("$path"), str):
                f = x["$path"].split("#", 1)[0]
                if f.endswith(".json"):
                    out.append(os.path.normpath(os.path.join(base, f)))
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return out


def scan_listed(folder, plan, skip_procs, recursive=True):
    """List-only: other small files under folder that carry old paths (line numbers only)."""
    for dirpath, dirnames, filenames in os.walk(folder):
        rel = os.path.relpath(dirpath, folder)
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith("history")
                       and not (skip_procs and rel == "." and d == "procs")]
        if not recursive:
            dirnames[:] = []
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if (fn.startswith(SKIP_FILE_PREFIX) or SUFFIX in fn or ".bad-" in fn
                    or os.path.realpath(p) in plan.seen or not os.path.isfile(p)):
                continue
            try:
                if os.path.getsize(p) > LIST_MAX_BYTES:
                    continue
                lines = [i + 1 for i, ln in enumerate(read_text(p).splitlines()) if PATTERN.search(ln)]
            except OSError:
                continue
            if lines:
                plan.listed.append((p, lines))


class Locks:
    def __init__(self, enabled):
        self.enabled = enabled
        self.fds = {}

    def take(self, dstack):
        if not self.enabled or dstack in self.fds:
            return
        try:
            fd = os.open(dstack, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        except OSError:
            raise SystemExit(fail(2, "StackMissing", "cannot open %s" % dstack))
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise SystemExit(fail(2, "DaemonRunning", "a daemon is running on %s (its stack lock is held); stop the tree first" % dstack))
        self.fds[dstack] = fd


def fail(code, kind, msg):
    print("stack_paths.py: error: %s %s" % (kind, msg), file=sys.stderr)
    return code


def walk_tree(root, plan, locks):
    todo = [os.path.realpath(root)]
    done = set()
    while todo:
        dstack = todo.pop(0)
        if dstack in done:
            continue
        done.add(dstack)
        locks.take(dstack)
        files, rows = table_files(dstack, plan)
        plan.daemons.append((dstack, len(rows)))
        for f in files:
            plan.add_change("table", dstack, f)
        for bad in sorted(os.listdir(dstack)):
            if bad.startswith(TABLE + ".bad-"):
                plan.notes.append("%s: has %s (a table the daemon could not read)" % (dstack, bad))
        for name, row in rows.items():
            if not isinstance(row, dict):
                continue
            st = os.path.realpath(row_stack(dstack, name, row))
            cell = os.path.realpath(os.path.join(dstack, "procs", name))
            for folder in (st, cell):
                for fn in ROW_FILES:
                    plan.add_change("row", dstack, os.path.join(folder, fn))
            for f in json_files_named(row, dstack):
                if os.path.basename(f) in ROW_FILES:
                    plan.add_change("row", dstack, f)
            if st != dstack and os.path.isfile(os.path.join(st, TABLE)):
                todo.append(st)
        # list-only pass after this daemon's change files are known
        scan_listed(dstack, plan, skip_procs=True, recursive=False)
        for name, row in rows.items():
            if not isinstance(row, dict):
                continue
            st = os.path.realpath(row_stack(dstack, name, row))
            cell = os.path.realpath(os.path.join(dstack, "procs", name))
            for folder in {st, cell}:
                # a child daemon's own stack is scanned when it is walked as a daemon
                if os.path.isdir(folder) and folder != dstack and not os.path.isfile(os.path.join(folder, TABLE)):
                    scan_listed(folder, plan, skip_procs=False, recursive=True)


def walk_defs(dirs, plan):
    for d in dirs:
        if not os.path.isdir(d):
            plan.errors.append("%s: not a folder" % d)
            continue
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = sorted(x for x in dirnames if x not in (".git", "__pycache__", "node_modules"))
            for fn in sorted(filenames):
                if fn.endswith(".json") and SUFFIX not in fn:
                    plan.add_change("def", "-", os.path.join(dirpath, fn))


def file_hits(path):
    """(raw hits, [(pointer, old, new)], parsed or None)."""
    text = read_text(path)
    raw = hits_text(text)
    try:
        doc = json.loads(text)
    except ValueError:
        return raw, None, None
    per = []
    for ptr, s in walk_strings(doc):
        for old, new in hits_text(s):
            per.append((ptr or "/", old, new))
    return raw, per, doc


def other_daemons():
    pids = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/comm" % d) as f:
                    if f.read().strip() == "aos-daemon":
                        pids.append(int(d))
            except OSError:
                pass
    return sorted(pids)


def check_processes(args):
    pids = other_daemons()
    if not pids:
        return 0
    if args.allow_other_daemons:
        print("# note: %d aos-daemon processes run on this machine; none holds a stack of this tree (all locks taken)" % len(pids))
        return 0
    return fail(2, "DaemonRunning", "%d aos-daemon processes run on this machine (pids %s); stop them, or give "
                "--allow-other-daemons if they belong to other trees (this tree's stack locks are checked either way)"
                % (len(pids), " ".join(map(str, pids))))


def write_atomic(path, data):
    st = os.stat(path)
    tmp = "%s.tmp-trisplit-%d" % (path, os.getpid())
    with open(tmp, "wb") as f:
        f.write(data)
    os.chmod(tmp, st.st_mode & 0o7777)
    os.replace(tmp, path)


def backup_name(path, digest):
    """<file>.bak-trisplit-1124; an existing one with the same bytes is reused; one with other bytes (an older
    run: e.g. apply, restore, the daemon rewrote the table, apply again) is kept and the next free -2, -3 ... is used."""
    n = 1
    while True:
        bak = path + SUFFIX + ("" if n == 1 else "-%d" % n)
        if not os.path.exists(bak) or sha(bak) == digest:
            return bak
        n += 1


def manifest_append(manifest, row):
    os.makedirs(os.path.dirname(os.path.abspath(manifest)), exist_ok=True)
    new = not os.path.exists(manifest)
    with open(manifest, "a") as f:
        if new:
            f.write("kind\tdaemon_stack\tfile\tbackup\tsha_before\tsha_after\ttime\n")
        f.write("\t".join(row) + "\n")


def run(args):
    plan = Plan()
    locks = Locks(args.apply)   # --apply: locks first (they are the proof for this tree), then the process check
    if args.root:
        if not os.path.isfile(os.path.join(args.root, TABLE)):
            return fail(1, "TableMissing", "no %s in %s" % (TABLE, args.root))
        walk_tree(args.root, plan, locks)
    if args.defs:
        walk_defs(args.defs, plan)
    if args.apply and args.root:
        rc = check_processes(args)
        if rc:
            return rc

    mode = "apply" if args.apply else "list only (nothing written; add --apply to change)"
    print("# mode: %s" % mode)
    for dstack, n in plan.daemons:
        print("daemon %s (%d rows)" % (dstack, n))
    total = 0
    todo = []
    for kind, dstack, path in plan.change:
        raw, per, doc = file_hits(path)
        if not raw:
            continue
        if per is None:
            plan.errors.append("%s: %d old paths but not valid JSON; not changed (fix it by hand)" % (path, len(raw)))
            continue
        if len(per) != len(raw):
            plan.errors.append("%s: %d old paths in the bytes but %d in the parsed strings (escaped text?); not changed"
                               % (path, len(raw), len(per)))
            continue
        print("change [%s] %s: %d" % (kind, path, len(raw)))
        for ptr, old, new in per:
            print("  %s: %s -> %s" % (ptr, old, new))
        total += len(raw)
        todo.append((kind, dstack, path, doc))
    for path, lines in plan.listed:
        print("listed only (not changed) %s: lines %s" % (path, ",".join(map(str, lines[:20])) + (" ..." if len(lines) > 20 else "")))
    for n in plan.notes:
        print("# note: " + n)
    for e in plan.errors:
        print("# problem: " + e)
    print("# summary: %d daemons, %d files to change, %d places; %d files listed only; %d problems"
          % (len(plan.daemons), len(todo), total, len(plan.listed), len(plan.errors)))
    if not args.apply:
        return 1 if plan.errors else 0
    if plan.errors and not args.force:
        return fail(2, "PlanBad", "%d problems above; nothing written (fix them, or --force to change only the clean files)" % len(plan.errors))

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    bad = 0
    for kind, dstack, path, doc in todo:
        before = sha(path)
        bak = backup_name(path, before)
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
        data = sub_text(read_text(path)).encode("utf-8", "surrogateescape")
        # manifest line first: a crash between here and the write still leaves the backup on record
        manifest_append(args.manifest, [kind, dstack, path, bak, before, hashlib.sha256(data).hexdigest(), stamp])
        write_atomic(path, data)
        ok = True
        try:
            new_doc = json.loads(read_text(path))
            if new_doc != map_strings(doc):
                ok = False
                why = "parsed result differs from the expected one"
        except ValueError:
            ok = False
            why = "not valid JSON after the change"
        left = len(hits_text(read_text(path)))
        if ok and left:
            ok = False
            why = "%d old paths left" % left
        if not ok:
            shutil.copy2(bak, path)
            print("# problem: %s: %s; put the backup back" % (path, why))
            bad += 1
            continue
        print("changed %s (backup %s)" % (path, bak))
    # recount every change file
    left = sum(len(hits_text(read_text(p))) for _, _, p in plan.change if os.path.isfile(p))
    print("# after: %d old paths left in the files this tool changes; manifest %s" % (left, args.manifest))
    return 1 if bad or left else 0


def restore(args):
    try:
        with open(args.restore) as f:
            lines = [ln.rstrip("\n").split("\t") for ln in f if ln.strip()]
    except OSError as e:
        return fail(1, "ManifestMissing", "%s (%s)" % (args.restore, e.__class__.__name__))
    rows = [r for r in lines[1:] if len(r) >= 6]
    locks = Locks(True)
    for r in rows:
        if r[1] != "-":
            locks.take(r[1])
    if any(r[1] != "-" for r in rows):
        rc = check_processes(args)
        if rc:
            return rc
    # pass 1: check every file; any problem = restore nothing (no half-restored tree)
    done = set()
    bad = 0
    todo = []
    for r in reversed(rows):
        kind, dstack, path, bak, before, after = r[:6]
        if path in done:
            continue
        done.add(path)
        if not os.path.isfile(bak):
            print("# problem: backup %s is missing; %s cannot be restored" % (bak, path))
            bad += 1
            continue
        now = sha(path) if os.path.isfile(path) else "-"
        if now == before:
            print("already as before: %s" % path)
            continue
        if now != after:
            if not args.force:
                print("# problem: %s changed since the apply (a daemon rewrote it, or a person did); "
                      "--force restores the backup anyway and loses that change" % path)
                bad += 1
                continue
            print("# note: %s changed since the apply; --force: the backup wins" % path)
        todo.append((path, bak, before))
    if bad:
        print("# restore: %d files in the manifest, %d problems; nothing restored" % (len(done), bad))
        return 1
    for path, bak, before in todo:
        if args.dry_run:
            print("would restore %s from %s" % (path, bak))
            continue
        data = open(bak, "rb").read()
        if os.path.isfile(path):
            write_atomic(path, data)
        else:
            with open(path, "wb") as f:
                f.write(data)
        ok = sha(path) == before
        print("%s %s" % ("restored" if ok else "# problem: restored but sha differs:", path))
        bad += 0 if ok else 1
    print("# restore: %d files in the manifest, %d problems; backups are kept" % (len(done), bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(
        prog="stack_paths.py",
        description="Rewrite old proto8/templates paths (06a table) in a stopped tree's daemon stacks and in "
                    "definition folders. Lists only unless --apply.",
        epilog="exit codes: 0 ok; 1 problems found or left; 2 refused (a daemon is running, or problems before --apply)")
    ap.add_argument("--root", help="the root daemon's stack; child daemons (rows whose stack has procs_state.json) are walked too")
    ap.add_argument("--defs", nargs="+", metavar="DIR", help="definition folders: every *.json under them")
    ap.add_argument("--apply", action="store_true", help="back up, rewrite, check (default: list only)")
    ap.add_argument("--restore", metavar="MANIFEST", help="copy the backups listed in MANIFEST back (newest first)")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST, help="where --apply appends (default %(default)s)")
    ap.add_argument("--allow-other-daemons", action="store_true",
                    help="with --apply/--restore: run although aos-daemon processes of OTHER trees are alive "
                         "(this tree's stacks are flock-checked and held either way)")
    ap.add_argument("--force", action="store_true", help="--apply: change the clean files despite problems; --restore: restore files changed since")
    ap.add_argument("--dry-run", action="store_true", help="--restore: say what would be restored")
    args = ap.parse_args()
    if args.restore:
        if args.root or args.defs or args.apply:
            return fail(1, "ArgumentsBad", "--restore goes alone")
        return restore(args)
    if not args.root and not args.defs:
        return fail(1, "ArgumentsBad", "give --root STACK and/or --defs DIR...")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
