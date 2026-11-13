#!/usr/bin/env python3
# copy_tree.py - 把 repo 某個 commit 的 lib／templates／knowledge／py／kernel 抄進一棵樹，每夾留一份 .aos-source.json 記抄自哪個 commit、何時抄的（11-13 線瑣，agents-feedback T05）。
# 抄法照 aos-teams/06「停樹換檔的做法」：來源是 git archive <commit>，不抄工作樹；每夾先解到樹裡的暫存夾、寫好 .aos-source.json，再兩次改名換上（舊的先改名移開、最後刪）。
# --stamp-only：不抄，只替已經用別的方法（例：repo 外的停樹腳本）從那個 commit 抄好的夾補寫 .aos-source.json（how 欄寫 stamp-only，表示內容沒經這支核對）。
# 不停樹、不碰行程：py、templates 在樹跑著時換掉的後果由呼叫者負責（停樹做法見 aos-teams/06）；只重抄 knowledge、lib 照 ops-notes-to-aos ⑯ 可以不停。
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.realpath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(HERE, "..", "..", "py"))
import aos_flags  # noqa: E402

PROG = "copy_tree.py"
FOLDERS = ("lib", "templates", "knowledge", "py", "kernel")
STAMP = ".aos-source.json"
USAGE = "(usage: copy_tree.py [--ref REF] [--repo REPO] [--stamp-only] [--dry-run] TREE [FOLDER...])"
HELP = """copy_tree.py - copy proto8 folders of one repo commit into an aos tree, and stamp each with where it came from

usage: copy_tree.py [--ref REF] [--repo REPO] [--stamp-only] [--dry-run] TREE [FOLDER...]

FOLDER defaults to: lib templates knowledge py kernel (each is proto8/FOLDER in the repo).
Each folder is taken from `git archive REF` (never from the working tree), unpacked inside TREE,
stamped, then swapped in by rename (the old folder is renamed away first, then deleted).
Every copied folder gets TREE/FOLDER/.aos-source.json:
  {"description", "commit", "ref", "copied_at", "from", "how"}
so an agent reading TREE/knowledge can tell which version of aos it describes.

flags:
  --ref REF      the commit to copy (default: HEAD); recorded as its full hash
  --repo REPO    the git repo (default: the repo holding this script)
  --stamp-only   do not copy; only write .aos-source.json into folders already copied from REF
                 by other means ("how": "stamp-only": the content was not checked)
  --dry-run      only print what would be done
  -h, --help     show this help

It does not stop the tree or touch any process. Replacing py or templates while the tree runs is
the caller's choice; knowledge and lib can be recopied while it runs.
Uncommitted changes under proto8/FOLDER are not copied: one warning line per folder.
exit codes: 0 ok; 1 error ("copy_tree.py: error: CODE reason" on stderr): ArgumentsBad, FlagUnknown,
RefBad (REF is not a commit), FolderMissing (proto8/FOLDER not in REF, or TREE/FOLDER missing with
--stamp-only), CopyFailed.
more: proto8/extras/aos-home/README.md"""


def git(repo, *args, binary=False):
    """跑 git -C repo …；失敗回 None（呼叫者決定代號）。"""
    p = subprocess.run(["git", "-C", repo, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if p.returncode != 0:
        return None
    return p.stdout if binary else p.stdout.decode("utf-8", "replace").strip()


def stamp(commit, ref, src, how):
    """一夾的 .aos-source.json 內容。copied_at 是本機時間、帶時區。"""
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "description": "Where this folder was copied from: the aos repo commit and when (written by proto8/extras/aos-home/copy_tree.py). Files in the repo may be newer than this copy.",
        "commit": commit, "ref": ref, "copied_at": now, "from": src, "how": how,
    }


def write_json(path, value):
    """先寫旁邊的暫存檔再改名。"""
    tmp = path + ".tmp-%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def copy_one(repo, commit, ref, tree, name):
    """把 proto8/name 從 commit 抄成 tree/name：解到 tree/.aos-copy-PID/、寫 stamp、舊的改名移開、新的改名換上、刪暫存夾。"""
    data = git(repo, "archive", "--format=tar", commit, "proto8/" + name, binary=True)
    if data is None:
        aos_flags.die(PROG, "CopyFailed", "git archive %s proto8/%s failed" % (commit, name))
    work = os.path.join(tree, ".aos-copy-%d" % os.getpid())
    os.makedirs(work, exist_ok=False)
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            tar.extractall(work, filter="data")
        new = os.path.join(work, "proto8", name)
        write_json(os.path.join(new, STAMP), stamp(commit, ref, os.path.join(repo, "proto8", name), "git archive"))
        dst = os.path.join(tree, name)
        if os.path.lexists(dst):
            os.rename(dst, os.path.join(work, "old-" + name))
        os.rename(new, dst)
    except (OSError, tarfile.TarError) as e:
        aos_flags.die(PROG, "CopyFailed", "%s: %s (leftovers, if any, are in %s)" % (name, e, work))
    shutil.rmtree(work, ignore_errors=True)


def main():
    aos_flags.HELP = HELP
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {"--ref": "ref", "--repo": "repo"},
                                     switches={"--stamp-only": "stamp_only", "--dry-run": "dry_run"}, anywhere=True)
    except aos_flags.Error as e:
        aos_flags.die(PROG, e.code, "%s %s" % (e, USAGE))
    if not rest:
        aos_flags.die(PROG, "ArgumentsBad", "missing TREE " + USAGE)
    tree, names = os.path.abspath(rest[0]), rest[1:] or list(FOLDERS)
    ref = opts.get("ref", "HEAD")
    repo = git(opts.get("repo", HERE), "rev-parse", "--show-toplevel")
    if not repo:
        aos_flags.die(PROG, "ArgumentsBad", "%s is not in a git repo %s" % (opts.get("repo", HERE), USAGE))
    if not os.path.isdir(tree):
        aos_flags.die(PROG, "ArgumentsBad", "TREE %s is not a folder %s" % (tree, USAGE))
    real_tree, real_repo = os.path.realpath(tree), os.path.realpath(repo)
    if real_tree == real_repo or real_tree.startswith(real_repo + os.sep):
        aos_flags.die(PROG, "ArgumentsBad", "TREE %s is inside the repo %s" % (tree, USAGE))
    for n in names:
        if n not in FOLDERS:
            aos_flags.die(PROG, "ArgumentsBad", "FOLDER %s is not one of %s %s" % (n, " ".join(FOLDERS), USAGE))
    commit = git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    if not commit:
        aos_flags.die(PROG, "RefBad", "%s is not a commit in %s" % (ref, repo))
    for n in names:
        if git(repo, "cat-file", "-e", "%s:proto8/%s" % (commit, n)) is None:
            aos_flags.die(PROG, "FolderMissing", "proto8/%s is not in %s" % (n, commit))
        if opts.get("stamp_only") and not os.path.isdir(os.path.join(tree, n)):
            aos_flags.die(PROG, "FolderMissing", "%s is not a folder (--stamp-only stamps folders already copied)" % os.path.join(tree, n))
    short = commit[:9]
    for n in names:
        dst = os.path.join(tree, n)
        if opts.get("stamp_only"):
            if opts.get("dry_run"):
                print("would stamp %s as %s" % (dst, short))
            else:
                write_json(os.path.join(dst, STAMP), stamp(commit, ref, os.path.join(repo, "proto8", n), "stamp-only"))
                print("stamped %s as %s" % (dst, short))
            continue
        if git(repo, "status", "--porcelain", "--", "proto8/" + n):
            aos_flags.warn(PROG, "proto8/%s has uncommitted changes; they are not copied (copying %s)" % (n, short))
        if opts.get("dry_run"):
            print("would copy proto8/%s at %s -> %s" % (n, short, dst))
            continue
        copy_one(repo, commit, ref, tree, n)
        print("copied proto8/%s at %s -> %s" % (n, short, dst))
    verb = "would do" if opts.get("dry_run") else "done"
    print("%s: %d folder(s), commit %s, tree %s" % (verb, len(names), commit, tree))


if __name__ == "__main__":
    aos_flags.run(main)
