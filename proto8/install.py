#!/usr/bin/env python3
# install.py [--check] [-j N] - build and install aos in place: checks dependencies, builds cpp/ with make, fills bin/, lib/ and include/, writes the Python commands' entries.
#
# Run it in the proto8 folder of a cloned repo (python3 install.py). It only writes inside this folder:
#   bin/        the commands: the C++ executables, and one small Python entry per line of py/entries.json
#               (it puts lib/ on sys.path and runs that module of lib/aos/apps/ as __main__)
#   lib/        a copy of py/ without tests/ folders, py/docs and __pycache__ (what runs: the aos package with aos/apps/, tools/, packs/,
#               schema/; symlinks are copied as symlinks), every .py compiled once into __pycache__/ (programs never write .pyc
#               while they run; a .pyc whose .py is gone is removed),
#               plus the C++ libraries (libaos-*.a, libaos-inst.so)
#   include/    public C++ headers, copied from cpp/aos-*/include
#   cpp/build/  objects and build.log (kept, so a rerun only rebuilds what changed)
#   cpp/compile_commands.json   for clangd
# bin/, lib/ and include/ are not emptied first (a running tree keeps importing from lib/ meanwhile): every file is copied over
# (changed ones through a temporary file and a rename), then whatever is left over is removed: files py/ no longer has,
# entries py/entries.json no longer lists, headers cpp/ no longer has, and C++ outputs the Makefile no longer makes
# (what make makes is read from its dry run). So a rerun gives the same result as a fresh install.
# Programs run only from bin/ and lib/: a change in py/ shows up after the next install.py.
# At the end it prints the next steps: set AOS_HOME once (it is never set for you; a warning when it points at another home),
# then copy a starter template (templates/starts/start-api or start-eca) to a tree and source that tree's env.sh.
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


def dry_run():
    """The lines of make's dry run (-B -n: every command it would run for a full build)."""
    r = subprocess.run(make_args(1) + ["-B", "-n"], capture_output=True, text=True)
    return r.stdout.splitlines()


def compile_commands(lines):
    """Write cpp/compile_commands.json from the dry run (every compile line)."""
    entries = []
    for line in lines:
        words = line.split()
        if "-c" in words and "-o" in words:
            src = words[words.index("-c") + 1]
            entries.append({"directory": str(CPP), "file": str(CPP / src), "command": line.strip()})
    (CPP / "compile_commands.json").write_text(json.dumps(entries, indent=1) + "\n", encoding="utf-8")
    return len(entries)


def cpp_outputs(lines):
    """What make puts into bin/ and lib/ (read from the dry run: the file after -o, or after `ar rcs`): {"bin": names, "lib": names}."""
    out = {"bin": set(), "lib": set()}
    for line in lines:
        for part in line.split(";"):
            words = part.split()
            target = None
            if len(words) > 2 and words[0] == "ar" and words[1].startswith("r"):
                target = words[2]
            elif "-o" in words and words.index("-o") + 1 < len(words):
                target = words[words.index("-o") + 1]
            if target:
                p = Path(os.path.normpath(os.path.join(str(CPP), target)))
                for key, folder in (("bin", BIN), ("lib", LIB)):
                    if p.parent == folder:
                        out[key].add(p.name)
    return out


def same_file(src, dst):
    """dst already holds what src holds (a symlink with the same text, or a regular file with the same bytes and mode)."""
    if src.is_symlink():
        return dst.is_symlink() and os.readlink(dst) == os.readlink(src)
    if dst.is_symlink() or not dst.is_file():
        return False
    a, b = src.stat(), dst.stat()
    if a.st_size != b.st_size or (a.st_mode & 0o777) != (b.st_mode & 0o777):
        return False
    return src.read_bytes() == dst.read_bytes()


def put(dst, write):
    """Replace dst in one rename: write(tmp) fills a temporary file next to it (a reader sees the old file or the new one, never half)."""
    if dst.is_dir() and not dst.is_symlink():
        shutil.rmtree(dst)                       # a folder where a file now goes
    tmp = dst.parent / (".%s.install-tmp" % dst.name)
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    write(tmp)
    os.replace(tmp, dst)


def sync_tree(src, dst, skip=None):
    """Copy the tree src into dst without emptying dst first; unchanged files are left as they are. Symlinks stay symlinks.
    skip(folder, names) -> names not to copy. Returns (files, folders) copied, as paths relative to dst (for prune)."""
    files, folders = set(), set()
    for folder, dirs, names in os.walk(src):
        rel = Path(folder).relative_to(src)
        gone = set(skip(folder, dirs + names)) if skip else set()
        dirs[:] = [d for d in dirs if d not in gone]
        here = dst / rel
        if here.is_symlink() or (here.exists() and not here.is_dir()):
            here.unlink()
        here.mkdir(parents=True, exist_ok=True)
        folders.add(rel)
        for name in sorted(names + [d for d in dirs if (Path(folder) / d).is_symlink()]):
            if name in gone:
                continue
            s, d = Path(folder) / name, here / name
            files.add(rel / name)
            if same_file(s, d):
                continue
            if s.is_symlink():
                put(d, lambda tmp, s=s: os.symlink(os.readlink(s), tmp))
            else:
                put(d, lambda tmp, s=s: shutil.copy2(s, tmp))
        dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()]   # a symlinked folder is one entry, copied as a link
    return files, folders


def prune(root, files, folders):
    """Remove what is under root but not in files / folders (paths relative to root): the leftovers of an earlier install."""
    n = 0
    for folder, dirs, names in os.walk(root, topdown=False):
        rel = Path(folder).relative_to(root)
        for name in names + [d for d in dirs if (Path(folder) / d).is_symlink()]:
            if rel / name not in files:
                (Path(folder) / name).unlink()
                n += 1
        if rel not in folders and folder != str(root) and not os.listdir(folder):
            os.rmdir(folder)
    return n


def copy_headers():
    """cpp/aos-*/include -> include/ (all projects merged)."""
    files, folders = set(), set()
    for d in sorted(CPP.glob("aos-*/include")):
        f, fo = sync_tree(d, INC)
        files |= f
        folders |= fo
    return files, folders


def copy_py():
    """py/ -> lib/ (next to the C++ libraries); skips tests/ at any depth, py/docs and __pycache__.
    Symlinks stay symlinks (the aos-sandbox examples point at lib/tools/... with relative links)."""
    def skip(folder, names):
        top = Path(folder) == PY
        return [n for n in names if n in ("tests", "__pycache__") or (top and n == "docs")]
    return sync_tree(PY, LIB, skip)


def compile_lib(pfiles):
    """lib/ 的 .py 全部編一次 .pyc（idle-polling 第 0 刀，使用者 11-24 第 5 題「a」＝.pyc 直接放 lib/）：每次起 Python 都省掉重新編譯
    （aos-eca-turn 起動約省一半）。執行期照舊不寫 bytecode（入口與工具的 sys.dont_write_bytecode）；只有這裡寫，所以定義資料夾不會多出
    __pycache__。回 (要留的 .pyc, 它們的資料夾, 編不過的支數)：給 prune 用，原始碼還在的 .pyc 才留（py/ 刪掉的模組，它的 .pyc 一起清）。"""
    import importlib.util
    import py_compile
    files, folders, bad = set(), set(), 0
    for rel in sorted(pfiles):
        if rel.suffix != ".py" or not (LIB / rel).is_file():
            continue
        src = LIB / rel
        cached = Path(importlib.util.cache_from_source(str(src)))
        try:
            py_compile.compile(str(src), cfile=str(cached), doraise=True)
        except (py_compile.PyCompileError, OSError) as e:
            bad += 1
            print("install.py: warning: cannot compile %s (it still runs, compiled at each start): %s"
                  % (rel, " ".join(str(e).split())[:200]), file=sys.stderr)
            continue
        files.add(cached.relative_to(LIB))
        folders.add(cached.parent.relative_to(LIB))
    return files, folders, bad


ENTRY = """#!/usr/bin/env python3
# %(name)s - generated by install.py from py/entries.json: runs lib/%(file)s (change py/, then rerun install.py).
import os, runpy, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
runpy.run_module("%(module)s", run_name="__main__", alter_sys=True)
"""
ENTRY_NAME = re.compile(r"aos-[a-z0-9]+(-[a-z0-9]+)*\Z")
ENTRY_MODULE = re.compile(r"aos\.apps(\.[a-z_][a-z0-9_]*)+\Z")


def write_entries(cpp_bin):
    """bin/<command> for every line of py/entries.json ({"commands": {name: module}}); the module must be in lib/ already.
    cpp_bin = the names make puts into bin/ (an entry may not have one of them). Returns the entry names."""
    path = PY / "entries.json"
    rel = path.relative_to(HOME)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die("EntriesBad", "cannot read %s: %s" % (rel, e))
    cmds = data.get("commands") if isinstance(data, dict) else None
    if not isinstance(cmds, dict) or not cmds:
        die("EntriesBad", "%s needs a non-empty object \"commands\" (name -> module)" % rel)
    for name, module in sorted(cmds.items()):
        if not ENTRY_NAME.match(name) or not isinstance(module, str) or not ENTRY_MODULE.match(module):
            die("EntriesBad", "%s: bad line %s: %s (want aos-NAME: aos.apps.MODULE)" % (rel, json.dumps(name), json.dumps(module)))
        file = module.replace(".", "/") + ".py"
        if not (LIB / file).is_file():
            die("EntriesBad", "%s: %s -> %s, but py/%s does not exist" % (rel, name, module, file))
        if name in cpp_bin:
            die("EntriesBad", "%s: %s is also a C++ executable in bin/" % (rel, name))
        text = ENTRY % {"name": name, "file": file, "module": module}
        target = BIN / name
        if target.is_file() and not target.is_symlink() and target.read_text(encoding="utf-8", errors="replace") == text \
                and os.access(target, os.X_OK):
            continue

        def write(tmp, text=text):
            tmp.write_text(text, encoding="utf-8")
            tmp.chmod(0o755)
        put(target, write)
    return set(cmds)


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
    for src in (CPP / "Makefile", PY / "aos" / "__init__.py", PY / "entries.json"):
        if not src.is_file():
            die("SourceMissing", "%s not found" % src)
    for d in (BIN, LIB, INC):
        if d.is_symlink() or (d.exists() and not d.is_dir()):
            d.unlink()
        d.mkdir(exist_ok=True)
    lines = dry_run()
    made = cpp_outputs(lines)
    if not made["bin"]:
        die("BuildBad", "make -n -B names nothing it puts into bin/ (nothing was changed; is cpp/Makefile all right?)")
    print("building cpp/ (make -j%d, log: cpp/build/build.log) ..." % jobs, flush=True)
    build(jobs)
    missing = sorted(n for key, folder in (("bin", BIN), ("lib", LIB)) for n in made[key] if not (folder / n).exists())
    if missing:
        die("BuildBad", "make finished but did not make %s (nothing was removed)" % ", ".join(missing))
    hfiles, hfolders = copy_headers()
    pfiles, pfolders = copy_py()
    cfiles, cfolders, _ = compile_lib(pfiles)
    entries = write_entries(made["bin"])
    gone = prune(INC, hfiles, hfolders)
    gone += prune(LIB, pfiles | cfiles | {Path(n) for n in made["lib"]}, pfolders | cfolders)
    gone += prune(BIN, {Path(n) for n in made["bin"] | entries}, {Path(".")})
    nc = compile_commands(lines)
    ncpp, nent, nlib = len(made["bin"]), len(entries), len(made["lib"])
    npy = sum(1 for p in pfiles if not (PY / p).is_dir())
    print("installed %d commands into %s (%d C++, %d Python entries), %d files from py/ (%d compiled to .pyc) and %d C++ libraries into %s, "
          "%d headers into %s, %d entries in cpp/compile_commands.json; removed %d left over from an earlier install"
          % (ncpp + nent, BIN, ncpp, nent, npy, len(cfiles), nlib, LIB, len(hfiles), INC, nc, gone))
    print_next()
    return 0


def print_next():
    """The next steps: AOS_HOME is the user's to set (env.sh never sets it, 11-18 S6); say whether it already points here."""
    have = os.environ.get("AOS_HOME", "")
    if not have:
        print("next: export AOS_HOME=%s   (once per machine, e.g. in ~/.bashrc, then open a new window)" % HOME)
    elif os.path.realpath(have) == str(HOME):
        print("AOS_HOME already points at this home")
    else:
        sys.stderr.write("%s: warning: AOS_HOME is %s, not this home %s; env.sh and the trees follow AOS_HOME, "
                         "so change it (e.g. in ~/.bashrc) if this home is the one you want\n" % (PROG, have, HOME))
    print("then: cp -r $AOS_HOME/templates/starts/start-api ~/aos-home   (or start-eca; see templates/starts/start-api/README.md), "
          "and in every window: cd ~/aos-home && source env.sh")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
