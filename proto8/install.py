#!/usr/bin/env python3
# install.py [--check] [-j N] - build and install aos in place: checks dependencies, builds cpp/ with make, fills bin/, lib/ and include/.
#
# Run it in the proto8 folder of a cloned repo (python3 install.py). It only writes inside this folder:
#   bin/        the commands (C++ executables for now)
#   lib/        a copy of py/ without tests/ folders, py/docs and __pycache__ (what runs: the aos package, tools/, packs/, schema/),
#               plus the C++ libraries (libaos-*.a, libaos-inst.so)
#   include/    public C++ headers, copied from cpp/aos-*/include
#   cpp/build/  objects and build.log (kept, so a rerun only rebuilds what changed)
#   cpp/compile_commands.json   for clangd
# bin/, lib/ and include/ are emptied first, so a rerun gives the same result as a fresh install.
# Programs run only from bin/ and lib/: a change in py/ shows up after the next install.py.
# --check only checks dependencies (required ones missing -> exit 1; optional ones are listed, never block).
# Errors are one line: "install.py: error: <Code> <reason>", exit 1.
# Standard library only. Written in old syntax on purpose, so an old python can still print the version error.
import os
import sys

MIN_PY = (3, 11)
PROG = "install.py"


def die(code, msg):
    sys.stderr.write("%s: error: %s %s\n" % (PROG, code, msg))
    sys.exit(1)


if sys.version_info[:2] < MIN_PY:
    die("DepMissing", "python >= %d.%d (found %d.%d)" % (MIN_PY + tuple(sys.version_info[:2])))

import json
import re
import shutil
import subprocess
from pathlib import Path

HOME = Path(__file__).resolve().parent
CPP = HOME / "cpp"
BIN = HOME / "bin"
INC = HOME / "include"
PY = HOME / "py"
LIB = HOME / "lib"
BUILD = CPP / "build"

# (command, what needs it)
REQUIRED = [("g++", "C++20 compiler"), ("gcc", "C compiler (aos-inst)"), ("make", "build"), ("ar", "static libraries")]
OPTIONAL = [
    ("git", "updates (git pull), some file walks"),
    ("tmux", "agent screens (screen, ask, linger), aos-eca-screen"),
    ("bwrap", "aos-sandbox"),
    ("s6-softlimit", "aos-sandbox with limits"),
    ("s6-setuidgid", "aos-sandbox with user"),
    ("s6-applyuidgid", "aos-sandbox with user"),
    ("newuidmap", "aos-asuser sub:N identities"),
    ("setfacl", "aos-share"),
    ("systemd-run", "aos-daemon cgroup delegation"),
    ("node", "tools written in JavaScript"),
    ("claude", "agent backend"),
    ("codex", "agent backend"),
    ("eca", "agent backend"),
]
GXX_MIN = 10


def optional_modules():
    """Python modules listed in requirements-optional.txt (name only, comments skipped)."""
    out = []
    p = PY / "requirements-optional.txt"
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(re.split(r"[<>=!~\[; ]", line, 1)[0])
    return out


def check():
    """Print the dependency table; return False when something required is missing."""
    ok = True
    rows = []
    for cmd, why in REQUIRED:
        path = shutil.which(cmd)
        rows.append(("required", cmd, path or "MISSING", why))
        if not path:
            sys.stderr.write("%s: error: DepMissing %s not found on PATH (%s)\n" % (PROG, cmd, why))
            ok = False
    if shutil.which("g++"):
        r = subprocess.run(["g++", "-dumpversion"], capture_output=True, text=True)
        major = int((r.stdout.strip().split(".") or ["0"])[0] or 0) if r.returncode == 0 else 0
        if major < GXX_MIN:
            sys.stderr.write("%s: error: DepMissing g++ >= %d (found %s)\n" % (PROG, GXX_MIN, r.stdout.strip() or "?"))
            ok = False
    for cmd, why in OPTIONAL:
        rows.append(("optional", cmd, shutil.which(cmd) or "-", why))
    for mod in optional_modules():
        found = subprocess.run([sys.executable, "-c", "import " + mod], capture_output=True).returncode == 0
        rows.append(("optional", "python:" + mod, "ok" if found else "-", "pip install " + mod))
    w = max(len(r[1]) for r in rows)
    for kind, name, where, why in rows:
        print("%-8s  %-*s  %-6s  %s" % (kind, w, name, "ok" if where not in ("MISSING", "-") else where, why))
    return ok


def make_args(jobs):
    return ["make", "-C", str(CPP), "-j%d" % jobs, "BUILD=" + str(BUILD), "BINDIR=" + str(BIN), "LIBDIR=" + str(LIB)]


def build(jobs):
    BUILD.mkdir(parents=True, exist_ok=True)
    log = BUILD / "build.log"
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run(make_args(jobs), stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        die("BuildFailed", "make exited %d, see %s" % (r.returncode, log.relative_to(HOME)))


def compile_commands():
    """Write cpp/compile_commands.json from a dry run of make (every compile line)."""
    r = subprocess.run(make_args(1) + ["-B", "-n"], capture_output=True, text=True)
    entries = []
    for line in r.stdout.splitlines():
        words = line.split()
        if "-c" in words and "-o" in words:
            src = words[words.index("-c") + 1]
            entries.append({"directory": str(CPP), "file": str(CPP / src), "command": line.strip()})
    (CPP / "compile_commands.json").write_text(json.dumps(entries, indent=1) + "\n", encoding="utf-8")
    return len(entries)


def copy_headers():
    n = 0
    for d in sorted(CPP.glob("aos-*/include")):
        shutil.copytree(d, INC, dirs_exist_ok=True)
        n += sum(1 for p in d.rglob("*") if p.is_file())
    return n


def copy_py():
    """py/ -> lib/ (merged with the C++ libraries already there); skips tests/ at any depth, py/docs and __pycache__."""
    def skip(folder, names):
        top = Path(folder) == PY
        return [n for n in names if n in ("tests", "__pycache__") or (top and n == "docs")]
    shutil.copytree(PY, LIB, ignore=skip, dirs_exist_ok=True)
    return sum(1 for p in LIB.rglob("*") if p.is_file() and not p.name.startswith("libaos-"))


def main(argv):
    jobs = os.cpu_count() or 2
    only_check = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--check":
            only_check = True
        elif a == "-j" and i + 1 < len(argv) and argv[i + 1].isdigit():
            jobs = int(argv[i + 1]); i += 1
        elif a in ("-h", "--help"):
            print("usage: python3 install.py [--check] [-j N]")
            return 0
        else:
            die("ArgBad", "unknown argument %s (usage: python3 install.py [--check] [-j N])" % a)
        i += 1
    if not check():
        return 1
    if only_check:
        return 0
    for src in (CPP / "Makefile", PY / "aos" / "__init__.py"):
        if not src.is_file():
            die("SourceMissing", "%s not found" % src)
    for d in (BIN, LIB, INC):
        if d.is_dir():
            shutil.rmtree(d)
        d.mkdir()
    print("building cpp/ (make -j%d, log: cpp/build/build.log) ..." % jobs, flush=True)
    build(jobs)
    nh = copy_headers()
    npy = copy_py()
    nc = compile_commands()
    bins = sorted(p.name for p in BIN.iterdir())
    nlib = sum(1 for p in LIB.iterdir() if p.name.startswith("libaos-"))
    print("installed %d commands into %s, %d files from py/ and %d C++ libraries into %s, %d headers into %s, "
          "%d entries in cpp/compile_commands.json" % (len(bins), BIN, npy, nlib, LIB, nh, INC, nc))
    print("next: export AOS_HOME=%s   (once per machine, e.g. in ~/.bashrc), then source $AOS_HOME/env.sh" % HOME)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
