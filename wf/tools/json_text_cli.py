#!/usr/bin/env python3
"""json_text_cli — json_text.py 的 --help 文字與 --setup（在所在 repo 的 .git/config 設 diff.json_text.textconv）；跟 json_text.py 放同一夾，由它 import，不單獨跑。"""
import os
import subprocess
import sys

PROG = "json_text"
KEY = "diff.json_text.textconv"
USAGE = "(usage: json_text.py [--md] FILE | --setup [--check])"
HELP = """json_text - expand a JSON file into line-oriented text for humans and for git diff (textconv).

usage: json_text.py [--md] FILE
       json_text.py --setup [--check]
  FILE      the JSON file; output goes to stdout as UTF-8
  --md      print a simple Markdown view instead (one section per string)
  --setup   set diff.json_text.textconv in the .git/config of the repo this
            script lives in (safe to rerun; prints the current state)
  --check   with --setup: only look; exit 0 if set as expected, 1 if not
  --help    show this help

Default output, in document order (keys are not sorted):
  #/a/b            a string node: a header line (JSON Pointer), then the content;
    line one       each content line is indented by two spaces; long lines are
    ↪ next one      folded after sentence ends, folded lines start with '↪ '
  #/n = 3          numbers (as written), true/false/null, "", {}, []
  #/list/-/name    array elements are written as '-', never as an index, so
                   inserting an element does not change the lines after it
  #/x = {"$ref": "a.json"}   objects with a '$' key are printed on one line
Control characters other than tab are shown as \\u000d etc.
If FILE is not valid JSON (or not UTF-8), a warning goes to stderr, the raw text
is printed unchanged and the exit code is 0, so git falls back to a plain diff.

git: put 'PATTERN diff=json_text' in .gitattributes, then once per clone run
  python3 wf/tools/json_text.py --setup      (or: python ... on Windows)
"""


def write(text):
    sys.stdout.buffer.write(text.encode("utf-8", "backslashreplace"))
    sys.stdout.buffer.flush()


def fail(what):
    sys.stderr.write("%s: error: %s\n" % (PROG, what))


def git(top, *args):
    return subprocess.run(["git", "-C", top] + list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def interpreter():
    """The name of a Python 3 on PATH, as it should appear in the git config ('python3' or 'python')."""
    for name in ("python3", "python"):
        try:
            r = subprocess.run([name, "-c", "import sys; sys.exit(sys.version_info[0] != 3)"], capture_output=True)
        except OSError:
            continue
        if r.returncode == 0:
            return name
    return None


def setup(script, check):
    """script: the absolute path of json_text.py; the git config points at it, relative to the work tree top."""
    here = os.path.dirname(script)
    r = git(here, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        fail("NotInRepo %s is not inside a git work tree" % here)
        return 1
    top = r.stdout.strip()
    rel = os.path.relpath(script, os.path.abspath(top)).replace(os.sep, "/")
    name = interpreter()
    if name is None:
        fail("PythonMissing neither python3 nor python on PATH runs Python 3")
        return 1
    want = '%s -B "%s"' % (name, rel) if " " in rel else "%s -B %s" % (name, rel)
    now = git(top, "config", "--local", "--get", KEY).stdout.strip()
    used = git(top, "ls-files", ":(attr:diff=json_text)").stdout.split("\n")
    note = "%d tracked files use diff=json_text" % len([u for u in used if u])
    if now == want:
        write("%s = %s (already set; %s)\n" % (KEY, want, note))
        return 0
    if check:
        write("%s is %s, expected %s (%s)\n" % (KEY, repr(now) if now else "not set", want, note))
        return 1
    r = git(top, "config", "--local", KEY, want)
    if r.returncode != 0:
        fail("ConfigFailed git config: %s" % r.stderr.strip())
        return 1
    write("%s = %s (was %s; %s)\n" % (KEY, want, repr(now) if now else "not set", note))
    return 0


def main(script, args):
    """Called by json_text.py with its own path and its arguments (args[0] is --help, -h or --setup)."""
    if args[0] in ("-h", "--help"):
        write(HELP)
        return 0
    if args[1:] not in ([], ["--check"]):
        fail("ArgumentsBad --setup takes only --check %s" % USAGE)
        return 2
    return setup(script, args[1:] == ["--check"])
