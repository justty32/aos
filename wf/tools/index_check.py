#!/usr/bin/env python3
"""index_check — 查 aos 的 index（`_index.json`）跟實際的樹對不對得上：列了但不在、在但沒列、連結指不到、形狀不對。

  index_check.py [--root DIR] [--fs] [--view] [--quiet] [PATH…]
    PATH    要查的夾（相對 --root；預設整個 root），底下每一份 `_index.json` 都查；被 `index` 連到的檔內 `_index` 也查。
    --root  樹的根（預設這份腳本所在的 repo）。
    --fs    「在但沒列」照磁碟上有什麼算（給不在 git 裡的樹用，例如裝好的 knowledge）；預設照 `git ls-files`（root 不是 git 的樹時自動照磁碟算）。
    --view  不查「在但沒列」（index 是視角、本來就可以只列一部分；只想查列的東西與連結對不對時用）。
  每個問題一行 `index_check: error: 代號 哪一份: 說明`，最後一行總數；有問題退 1，沒有退 0。只讀、不改任何檔。
  代號：IndexBad（整份或某項形狀不對：要 `{名: {"description": "…", "index": "路徑"}}`，description 非空字串）、
        EntryGone（列了但不在）、EntryMissing（在但沒列）、LinkBad（`index` 指不到另一份 index）、
        LinkMissing（子夾自己有 `_index.json`，上一層那一項卻沒帶 `index`）。
  路徑算法照 proto8/lib/aos_index.py 的 link()，這裡只做資料夾的 `_index.json` 用得到的部分（相對所在夾、`檔#/指標`、`#/指標`＝本檔）。
  規格：proto8/thinking/2026-11/13/index-build.md。生成用 index_gen.py。純標準庫。
"""
import json
import os
import subprocess
import sys

PROG = "index_check"
NAME = "_index.json"
SKIP = {".git", "__pycache__", "build", "install", "vcpkg_installed", "node_modules", ".cache"}
USAGE = "(usage: index_check.py [--root DIR] [--fs] [--view] [--quiet] [PATH…])"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pointer(doc, ptr):
    """JSON Pointer（/a/b）→ (找到沒, 值)。"""
    cur = doc
    for tok in ptr.split("/")[1:] if ptr else []:
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
        elif isinstance(cur, list) and tok.isdigit() and int(tok) < len(cur):
            cur = cur[int(tok)]
        else:
            return False, None
    return True, cur


def children(root, d, fs, cache):
    """夾 d（相對 root）底下實際有的名字。"""
    if fs or cache.get("fs"):
        try:
            return {n for n in os.listdir(os.path.join(root, d)) if n not in SKIP and n != NAME}
        except OSError:
            return set()
    if "kids" not in cache:
        got = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True)
        if got.returncode:                              # 不是 git 的樹：照磁碟算
            print(f"{PROG}: warning: {root} is not in git, counting what is on disk (same as --fs)", file=sys.stderr)
            cache["fs"] = True
            return children(root, d, True, cache)
        out = got.stdout.decode()
        kids = {}
        for p in out.split("\0"):
            if not p or not os.path.lexists(os.path.join(root, p)):
                continue
            parts = p.split("/")
            for i in range(len(parts)):
                kids.setdefault("/".join(parts[:i]) or ".", set()).add(parts[i])
        cache["kids"] = kids
    here = set(cache["kids"].get(d, set()))
    try:                                                # 還沒進 git 的 `_index.json` 所在的夾也算在（剛生成、還沒 commit）
        for n in os.listdir(os.path.join(root, d)):
            if os.path.isfile(os.path.join(root, d, n, NAME)):
                here.add(n)
    except OSError:
        pass
    here.discard(NAME)
    return here


def check_table(table, where, problems):
    """形狀：回 True＝是物件、可以往下查各項。"""
    if not isinstance(table, dict):
        problems.append(("IndexBad", where, "is not a JSON object"))
        return False
    for k, e in table.items():
        if not isinstance(e, dict):
            problems.append(("IndexBad", where, "entry %s is not an object {\"description\": ...}" % k))
        elif not isinstance(e.get("description"), str) or not e["description"].strip():
            problems.append(("IndexBad", where, "entry %s has no description" % k))
        elif "index" in e and (not isinstance(e["index"], str) or not e["index"]):
            problems.append(("IndexBad", where, "entry %s: index is not a path string" % k))
    return True


def check_dir(root, d, fs, view, cache, problems, seen_inner):
    where = NAME if d == "." else d + "/" + NAME
    base = os.path.join(root, d)
    try:
        table = load(os.path.join(base, NAME))
    except (OSError, ValueError) as e:
        problems.append(("IndexBad", where, "cannot be read as JSON (%s)" % type(e).__name__))
        return 0
    if not check_table(table, where, problems):
        return 0
    have = children(root, d, fs, cache)
    for k, e in table.items():
        f, _, ptr = k.partition("#")
        target = os.path.join(base, f)
        if not os.path.lexists(target):
            problems.append(("EntryGone", where, "%s is listed but not there" % k))
            continue
        if ptr:
            try:
                ok, _v = pointer(load(target), ptr)
            except (OSError, ValueError):
                ok = False
            if not ok:
                problems.append(("EntryGone", where, "%s is listed but that place is not in the file" % k))
        if not isinstance(e, dict):
            continue
        link = e.get("index")
        if isinstance(link, str) and link:
            lf, _, lptr = link.partition("#")
            lpath = os.path.join(base, NAME) if not lf else os.path.normpath(os.path.join(base, lf))
            if "#" in link and not lptr.startswith("/"):
                problems.append(("LinkBad", where, "%s: index %s is not a path (after # comes /)" % (k, link)))
            elif not os.path.isfile(lpath):
                problems.append(("LinkBad", where, "%s: index %s points to nothing" % (k, link)))
            else:
                try:
                    ok, v = pointer(load(lpath), lptr)
                except (OSError, ValueError):
                    ok, v = False, None
                if not ok or not isinstance(v, (dict, str)):
                    problems.append(("LinkBad", where, "%s: index %s does not hold an index" % (k, link)))
                elif lptr and isinstance(v, dict) and (lpath, lptr) not in seen_inner:
                    seen_inner.add((lpath, lptr))       # 檔內的 _index：它列的鍵要在裝著它的那個物件裡
                    inner_where = os.path.relpath(lpath, root) + "#" + lptr
                    if check_table(v, inner_where, problems):
                        _ok, holder = pointer(load(lpath), lptr.rsplit("/", 1)[0])
                        for ik in v:
                            if not isinstance(holder, dict) or ik not in holder:
                                problems.append(("EntryGone", inner_where, "%s is listed but not in that object" % ik))
        elif os.path.isfile(os.path.join(target, NAME)) and "#" not in k:
            problems.append(("LinkMissing", where, "%s has its own %s but the entry has no index" % (k, NAME)))
    if not view:
        listed = {k.partition("#")[0].split("/")[0] for k in table}
        for n in sorted(have - listed):
            problems.append(("EntryMissing", where, "%s is there but not listed" % n))
    return len(table)


def main(argv):
    root, fs, view, quiet, paths = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), False, False, False, []
    it = iter(argv)
    for a in it:
        if a == "--fs":
            fs = True
        elif a == "--view":
            view = True
        elif a == "--quiet":
            quiet = True
        elif a == "--root":
            root = next(it, None)
            if root is None:
                print(f"{PROG}: error: ArgumentsBad --root needs a value {USAGE}", file=sys.stderr)
                return 1
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        elif a.startswith("-"):
            print(f"{PROG}: error: FlagUnknown {a} {USAGE}", file=sys.stderr)
            return 1
        else:
            paths.append(a)
    root = os.path.realpath(os.path.expanduser(root))
    problems, cache, seen_inner, files, entries = [], {}, set(), 0, 0
    for p in paths or ["."]:
        top = os.path.join(root, p)
        if not os.path.isdir(top):
            print(f"{PROG}: error: PathBad {p} is not a folder under the root {USAGE}", file=sys.stderr)
            return 1
        for cur, dirs, names in os.walk(top):
            dirs[:] = sorted(x for x in dirs if x not in SKIP)
            if NAME in names:
                files += 1
                entries += check_dir(root, os.path.relpath(cur, root), fs, view, cache, problems, seen_inner)
    for code, where, msg in problems:
        print(f"{PROG}: error: {code} {where}: {msg}", file=sys.stderr)
    if not quiet:
        kinds = {}
        for code, _w, _m in problems:
            kinds[code] = kinds.get(code, 0) + 1
        print("%s: %d index files, %d entries, %d problems%s" % (
            PROG, files, entries, len(problems),
            "" if not problems else " (" + ", ".join("%s %d" % kv for kv in sorted(kinds.items())) + ")"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
