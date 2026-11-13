#!/usr/bin/env python3
"""json_text — 把一份 json 展開成給人看、給 git 逐行比的文字（git textconv 用；純標準庫、自足，可整支抄到別的 repo）。

  json_text.py FILE            展開成逐行文字，印到 stdout（git textconv 就這樣叫）
  json_text.py --md FILE       展開成簡單的 Markdown（每個字串一節，內容原樣）
  json_text.py --setup         在這支所在的 repo 設好 diff.json_text.textconv（只寫該 repo 的 .git/config；重跑不出錯、印現況）
  json_text.py --setup --check 只看不改：設好了退 0，沒設或不一樣退 1
  json_text.py --help

預設輸出（照文件順序，key 不排序）：
  #/steps/build            字串節點：一行標頭（JSON Pointer，~ 與 / 轉成 ~0、~1），
    first line             接著內容；\\n 照實換行，每行前面兩格空白。
    ↪ next sentence        一行超過 LONG 字時在句尾（. ! ? 後的空白、。！？後）折行（行首的清單編號「1. 」「1) 」後面不折），
                           折出來的接續行前面是「↪ 」（只為了讓改一句話只動一行；不是內容裡的換行）。
  #/n = 3                  數字（照原文字面）、true／false／null、空字串 ""、空物件 {}、空陣列 []
  #/records/-/date         陣列元素的路徑一律寫 `-`、不寫索引：前面插一筆，後面各筆的行不會跟著變
  #/x = {"$ref": "a.json"} 有 `$` 開頭鍵的物件（$ref、$fmt、$env 這類指示詞）不展開、印成一行
內容裡的控制字元（tab 以外，含 CR）印成 \\u000d 這種寫法；整份 json 是一個純量時路徑是 `#`。
讀不懂（不是 JSON、不是 UTF-8）就在 stderr 印一行提醒、把原文照樣印出、退 0，git 等於退回一般文字比對。
接上 git：.gitattributes 寫 `路徑樣式 diff=json_text`，每個 clone 跑一次 `--setup`（git 叫 textconv 時 cwd 是工作樹根，所以設定裡用相對路徑）。
"""
import json
import os
import re
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

INDENT = "  "
FOLD = "↪ "          # marks a folded continuation line (not a newline in the content)
LONG = 100                # lines longer than this are folded at sentence ends
_SENT = re.compile(r"(?<=[.!?]) +(?=\S)|(?<=[。！？])(?=\S)")
_LIST = re.compile(r"[ \t]*\d+(?:\.\d+)*[.)] +")   # a list number at the start of a line ("1. ", "  12. ", "1.2. ", "1) "): never fold right after it
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_CTRL_NL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")      # for paths: a newline in a key is shown too


class Raw(str):
    """A number or constant kept exactly as written in the file."""


class Obj(list):
    """An object as its (key, value) pairs, so order and duplicate keys survive."""


def parse(text):
    return json.loads(text, object_pairs_hook=Obj, parse_float=Raw, parse_int=Raw, parse_constant=Raw)


def visible(s, pattern=_CTRL):
    return pattern.sub(lambda m: "\\u%04x" % ord(m.group()), s)


def token(key):
    return key.replace("~", "~0").replace("/", "~1")


def fold(line):
    if len(line) <= LONG:
        return [line]
    m = _LIST.match(line)
    head = m.group() if m else ""
    parts = [p for p in _SENT.split(line[len(head):]) if p != ""] or [""]
    parts[0] = head + parts[0]
    return parts


def is_text(v):
    return isinstance(v, str) and not isinstance(v, Raw)


def is_directive(v):
    return isinstance(v, Obj) and any(k.startswith("$") for k, _ in v)


def compact(v):
    """One-line JSON of a parsed value, numbers as written."""
    if isinstance(v, Raw):
        return str(v)
    if is_text(v):
        return json.dumps(v, ensure_ascii=False)
    if v is True or v is False or v is None:
        return json.dumps(v)
    if isinstance(v, Obj):
        return "{" + ", ".join("%s: %s" % (json.dumps(k, ensure_ascii=False), compact(c)) for k, c in v) + "}"
    return "[" + ", ".join(compact(c) for c in v) + "]"


def walk(doc):
    """Yield (pointer, value) for every leaf in document order; array elements get '-' instead of an index."""
    stack = [("", doc)]
    while stack:
        path, v = stack.pop()
        if isinstance(v, Obj) and v and not is_directive(v):
            stack.extend(reversed([(path + "/" + token(k), c) for k, c in v]))
        elif isinstance(v, list) and not isinstance(v, Obj) and v:
            stack.extend(reversed([(path + "/-", c) for c in v]))
        else:
            yield "#" + visible(path, _CTRL_NL), v


def render_text(doc):
    out = []
    for path, v in walk(doc):
        if is_text(v) and v != "":
            out.append(path)
            for line in v.split("\n"):
                parts = fold(visible(line))
                out.append(INDENT + parts[0])
                out.extend(INDENT + FOLD + p for p in parts[1:])
        else:
            out.append("%s = %s" % (path, visible(compact(v))))
    return out


def render_md(doc):
    out = []
    for path, v in walk(doc):
        if is_text(v) and v != "":
            out += ["", "## `%s`" % path, "", visible(v).rstrip("\n")]
        else:
            out += ["", "- `%s = %s`" % (path, visible(compact(v)))]
    return out[1:]


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


def setup(check):
    here = os.path.dirname(os.path.abspath(__file__))
    r = git(here, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        fail("NotInRepo %s is not inside a git work tree" % here)
        return 1
    top = r.stdout.strip()
    rel = os.path.relpath(os.path.abspath(__file__), os.path.abspath(top)).replace(os.sep, "/")
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


def main(argv):
    args = argv[1:]
    if not args:
        fail("ArgumentsBad no FILE given %s" % USAGE)
        return 2
    if args[0] in ("-h", "--help"):
        write(HELP)
        return 0
    if args[0] == "--setup":
        if args[1:] not in ([], ["--check"]):
            fail("ArgumentsBad --setup takes only --check %s" % USAGE)
            return 2
        return setup(args[1:] == ["--check"])
    md = args[0] == "--md"
    if md:
        args = args[1:]
    if len(args) != 1 or (args[0].startswith("-") and args[0] != "-"):
        fail(("FlagUnknown " + args[0] if args and args[0].startswith("-") else "ArgumentsBad expected one FILE")
             + " " + USAGE)
        return 2
    try:
        if args[0] == "-":
            data = sys.stdin.buffer.read()
        else:
            with open(args[0], "rb") as f:
                data = f.read()
    except OSError as e:
        fail("FileUnreadable %s: %s" % (args[0], e.strerror))
        return 1
    try:
        doc = parse(data.decode("utf-8-sig"))
    except (ValueError, RecursionError):
        sys.stderr.write("%s: warning: not valid JSON, showing raw text\n" % PROG)
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return 0
    write("\n".join(render_md(doc) if md else render_text(doc)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
