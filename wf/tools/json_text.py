#!/usr/bin/env python3
"""json_text — 把一份 json 展開成給人看、給 git 逐行比的文字（git textconv 用；純標準庫；--help 與 --setup 在同夾的 json_text_cli.py，兩支一起整支抄到別的 repo 就能用）。

  json_text.py FILE            展開成逐行文字，印到 stdout（git textconv 就這樣叫）
  json_text.py --md FILE       展開成簡單的 Markdown（每個字串一節，內容原樣）
  json_text.py --setup         在這支所在的 repo 設好 diff.json_text.textconv（只寫該 repo 的 .git/config；重跑不出錯、印現況）
  json_text.py --setup --check 只看不改：設好了退 0，沒設或不一樣退 1
  json_text.py --help         （--help、--setup 由同夾的 json_text_cli.py 做；少了它這兩個退 1，展開照常）

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
import sys

PROG = "json_text"
USAGE = "(usage: json_text.py [--md] FILE | --setup [--check])"

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


def main(argv):
    args = argv[1:]
    if not args:
        fail("ArgumentsBad no FILE given %s" % USAGE)
        return 2
    if args[0] in ("-h", "--help", "--setup"):
        here = os.path.abspath(__file__)
        cli = os.path.join(os.path.dirname(here), "json_text_cli.py")      # load by path: works under -I too
        if not os.path.isfile(cli):
            fail("CliMissing %s needs json_text_cli.py next to json_text.py" % args[0])
            return 1
        import importlib.util
        spec = importlib.util.spec_from_file_location("json_text_cli", cli)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.main(here, args)
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
