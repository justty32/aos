#!/usr/bin/env python3
# split.py - one-off tool for the templates split (06c rules R1-R5): moves folders, fixes md links, rewrites path strings in a repo copy; rerunnable.
"""usage: split.py [--repo DIR] [--moves FILE] [--dry-run | --apply | --check]

Mechanical layer of the templates split (planning folder 06c/06d). Works on a git clone, never on the live repo.

  --dry-run  (default once any flag is given) dry run: print the R1 moves still to do and how many R3-R5 rewrites each file would get
  --apply    R1 git mv, R2 relative md links (wf/tools/fix_moved_links.py logic, only for moves done in this run),
             R3 moved cell paths, R4 literal template paths, R5 joined paths; running it twice gives the same tree
  --check    list old paths still left outside the excluded ranges (exit 1 if any), dynamic forms to read by hand,
             and a count per excluded range

--repo   the clone (default: current directory's git top)
--moves  old<TAB>new table (default: moves.tsv next to this script)
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

EXCLUDE_PREFIXES = (
    "proto8/thinking/", "wf/session_logs/", "wf/workflows/refactor/reports/", "wf/workflows/tidy/reports/",
    "proto8/knowledge-zh-md/", "proto8/lib/", "proto8/bin/", "proto8/include/", "wf/knowledge/code-map/",
    "wf/user/", "wf/inbox/", "archive/", "proto8/archive/",
)
EXCLUDE_FILES = ("wf/progress.json",)   # live state: changed only through commit-request --op
CELLS = r"(?:idle|brain|wait|act|compact|cell_common|atomic_file|llm_settings)\.py|hooks\.json"
CATEGORIES = ("agents", "kernels", "orgs", "daemons", "starts", "tools", "tests", "docs")


def die(msg):
    print("split.py: error: " + msg, file=sys.stderr)
    sys.exit(1)


def excluded(rel):
    base = rel.rsplit("/", 1)[-1]
    if rel.startswith(EXCLUDE_PREFIXES) or rel in EXCLUDE_FILES:
        return True
    if base == "_index.json" and not rel.startswith("proto8/knowledge/"):
        return True   # generated; commit-request regenerates them
    if rel.startswith("wf/ws/") and base == "notes.md":
        return True   # each seat's own notes
    return False


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True)
    if check and r.returncode != 0:
        die("GitFailed git %s: %s" % (" ".join(args), r.stderr.decode(errors="replace").strip()))
    return r.stdout.decode("utf-8", errors="surrogateescape")


def tracked(repo, path=None):
    out = git(repo, "-c", "core.quotepath=off", "ls-files", "-z", *([path] if path else []))
    return [p for p in out.split("\0") if p]


def load_moves(path):
    moves = []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        old, new = line.split("\t")[:2]
        moves.append((old.strip(), new.strip()))
    return moves


class Rules:
    """R3-R5 regexes built from the moves table."""

    def __init__(self, moves):
        self.cells = {}   # "templates/agent-fsm/idle.py" -> (source path, lib path)
        self.dirs = {}    # "agent-fsm" -> "agents/agent-fsm"
        for old, new in moves:
            if not old.startswith("proto8/templates/"):
                die("MovesBad %s is not under proto8/templates" % old)
            rel = old[len("proto8/"):]
            if new.startswith("proto8/py/"):
                self.cells[rel] = (new, "lib/" + new[len("proto8/py/"):])
            else:
                self.dirs[rel[len("templates/"):]] = new[len("proto8/templates/"):]
        names = "|".join(re.escape(n) for n in sorted(self.dirs, key=len, reverse=True))
        cells = "|".join(re.escape(c) for c in sorted(self.cells, key=len, reverse=True))
        self.r3 = re.compile(r"(?<![\w-])(proto8/)?(%s)(?![\w-])" % cells)
        self.r4 = re.compile(r"(?<![\w-])templates/(%s)(?![\w-]|\.\w)" % names)
        self.r5a = re.compile(r"""(["'])templates\1(\s*[,/]\s*)(["'])(%s)(?=\3|/)""" % names)
        self.r5b = re.compile(r"""(?<![\w.])TEMPLATES(\s*/\s*)(["'])(%s)(?=\2|/)""" % names)
        self.stale_joined = re.compile(r"""agent-fsm["']\s*[,/]\s*["'](%s)["']""" % CELLS)
        self.stale_parents = re.compile(r"""parents\[\d\]\s*/\s*(["'])(%s)\1""" % names)   # templates/tests/<夾>/ 往上數到 templates
        self.stale_moved = re.compile(r"templates/agents/agent-fsm/(%s|%%s\.py)\b"
                                      % CELLS.replace(r"\.py", "").replace(r"\.json", ""))
        cat = "|".join(CATEGORIES)
        self.review = re.compile(r"""templates/%%s|templates/\{|["']templates["']\s*[,/]\s*(?!["'](%s)["'/])[\w(]"""
                                 r"""|\bTEMPLATES\s*/\s*[A-Za-z_(]""" % cat)

    def _r3(self, m):
        src, lib = self.cells[m.group(2)]
        return src if m.group(1) else lib

    def _r5a(self, m):
        q, sep, q2, name = m.groups()
        parts = self.dirs[name].split("/")
        if len(parts) == 1:
            return "%stemplates%s%s%s%s" % (q, q, sep, q2, parts[0])
        return "%stemplates%s%s%s%s%s%s%s%s" % (q, q, sep, q2, parts[0], q2, sep, q2, name)

    def _r5b(self, m):
        sep, q, name = m.groups()
        parts = self.dirs[name].split("/")
        if len(parts) == 1:
            return "TEMPLATES%s%s%s" % (sep, q, parts[0])
        return "TEMPLATES%s%s%s%s%s%s%s" % (sep, q, parts[0], q, sep, q, name)

    def rewrite(self, text):
        counts = []
        text, n = self.r3.subn(self._r3, text); counts.append(n)
        text, n = self.r4.subn(lambda m: "templates/" + self.dirs[m.group(1)], text); counts.append(n)
        a, b = 0, 0
        text, a = self.r5a.subn(self._r5a, text)
        text, b = self.r5b.subn(self._r5b, text)
        counts.append(a + b)
        return text, counts

    def stale(self, line):
        return bool(self.r3.search(line) or self.r4.search(line) or self.r5a.search(line)
                    or self.r5b.search(line) or self.stale_joined.search(line)
                    or self.stale_moved.search(line) or self.stale_parents.search(line))


def read_text(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def r1(repo, moves, apply):
    done = []
    for old, new in moves:
        has_old = bool(tracked(repo, old))
        has_new = os.path.exists(os.path.join(repo, new))
        if not has_old:
            if not has_new:
                die("MoveBad neither %s nor %s is there" % (old, new))
            continue
        if has_new:
            die("MoveBad both %s and %s are there" % (old, new))
        print("R1 move %s -> %s" % (old, new))
        if apply:
            os.makedirs(os.path.dirname(os.path.join(repo, new)), exist_ok=True)
            git(repo, "mv", old, new)
            done.append((old, new))
    return done


def r2(repo, done):
    """fix_moved_links.py logic, limited to files outside the excluded ranges; links in excluded files are only counted."""
    if not done:
        print("R2 nothing moved in this run, links left as they are")
        return
    sys.path.insert(0, os.path.join(repo, "wf", "tools"))
    import fix_moved_links as fml   # noqa: E402
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False, encoding="utf-8") as t:
        t.write("".join("%s\t%s\n" % m for m in done))
    fml.ROOT = os.path.abspath(repo)
    fml.RW = fml.fmtx.Rewriter(fml.remap, fml.retarget, fml.sub_md, fml.ARCHIVED, fml.ROOT)
    fml.load_moves([(t.name, None)])
    os.unlink(t.name)
    changed, left = 0, {}
    for f in fml.scanned():
        rel = fml.fmtx.relposix(f, fml.ROOT)
        skip = excluded(rel)
        bn, bo, edits = os.path.dirname(f), fml.old_dir_of(f), []
        try:
            if f.endswith(".md"):
                text = fml.fix_md(f, bo, bn, edits)
                if edits and not skip:
                    open(f, "w", newline="\n", encoding="utf-8").write(text)
            else:
                fml.fix_table(f, bo, bn, edits, not skip)
        except (UnicodeDecodeError, OSError, ValueError):
            continue
        if edits and skip:
            top = "/".join(rel.split("/")[:2])
            left[top] = left.get(top, 0) + len(edits)
        elif edits:
            changed += 1
    print("R2 links fixed in %d files" % changed)
    for top in sorted(left):
        print("R2 left (excluded range) %s: %d links" % (top, left[top]))


def r345(repo, rules, apply):
    total = [0, 0, 0]
    files = 0
    for rel in tracked(repo):
        if excluded(rel):
            continue
        path = os.path.join(repo, rel)
        if os.path.islink(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        new, counts = rules.rewrite(text)
        if new == text:
            continue
        files += 1
        total = [a + b for a, b in zip(total, counts)]
        if not apply:
            print("R3-R5 %s: %s" % (rel, "/".join(map(str, counts))))
        else:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
    print("R3 %d, R4 %d, R5 %d rewrites in %d files (%s)" % (total[0], total[1], total[2], files,
                                                             "applied" if apply else "dry run"))


def check(repo, moves, rules):
    bad = 0
    for old, new in moves:
        if tracked(repo, old):
            print("move not done: %s" % old); bad += 1
        if not tracked(repo, new):
            print("move target missing: %s" % new); bad += 1
    stale, review, left = [], [], {}
    for rel in tracked(repo):
        path = os.path.join(repo, rel)
        if os.path.islink(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        skip = excluded(rel)
        for i, line in enumerate(text.split("\n"), 1):
            if rules.stale(line):
                if skip:
                    top = "/".join(rel.split("/")[:2])
                    left[top] = left.get(top, 0) + 1
                else:
                    stale.append("%s:%d: %s" % (rel, i, line.strip()[:160]))
            elif not skip and rules.review.search(line):
                review.append("%s:%d: %s" % (rel, i, line.strip()[:160]))
    print("== stale (old paths outside the excluded ranges): %d" % len(stale))
    for s in stale:
        print(s)
    print("== review (paths built at run time; read once by hand): %d" % len(review))
    for s in review:
        print(s)
    print("== excluded ranges (left as they are): %d lines" % sum(left.values()))
    for top in sorted(left):
        print("%s: %d" % (top, left[top]))
    return 1 if (stale or bad) else 0


def main(argv):
    usage = "(usage: split.py [--repo DIR] [--moves FILE] [--dry-run | --apply | --check])"
    if not argv:
        print("split.py: error: ArgumentsBad no arguments " + usage, file=sys.stderr)
        return 1
    if argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    repo, moves_path, mode = None, os.path.join(HERE, "moves.tsv"), "dry"
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--repo" and args:
            repo = args.pop(0)
        elif a == "--moves" and args:
            moves_path = args.pop(0)
        elif a in ("--apply", "--check"):
            mode = a[2:]
        elif a == "--dry-run":
            mode = "dry"
        else:
            print("split.py: error: FlagUnknown %s %s" % (a, usage), file=sys.stderr)
            return 1
    repo = os.path.abspath(repo or git(os.getcwd(), "rev-parse", "--show-toplevel").strip())
    if not os.path.isfile(moves_path):
        die("PathMissing %s" % moves_path)
    moves = load_moves(moves_path)
    rules = Rules(moves)
    if mode == "check":
        return check(repo, moves, rules)
    done = r1(repo, moves, mode == "apply")
    if mode == "apply":
        r2(repo, done)
    r345(repo, rules, mode == "apply")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
