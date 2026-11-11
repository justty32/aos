"""knowledge_check 的八項檢查：指標、表與孤兒、工具／指令／impls 覆蓋、錯誤代號、開發殘留、大小；每項回一串 Problem，不寫檔。

路徑解析照抄不重寫：統一路徑、表的格（含 $env 格）、子節點一律用 lib/agent/knowledge_fs（knowledge_read 的事實來源）；
只有「這個位置在不在」用純 Python 讀 JSON（同 knowledge_read 的 find，不逐處起 aos-json）。
"""
import json
import os
import re
from collections import namedtuple

import knowledge_fs as fs

Problem = namedtuple("Problem", "level check code where reason")   # level: error／warning；warning 的 code＝""
CHECKS = ("refs", "index", "tools", "cmds", "impls", "codes", "residue", "size")
SKIP_DIRS = {"tests", "thinking", "archive", "__pycache__", "build", "node_modules", "fixtures", ".git"}
CODE_DIRS = ("lib", "cmd", "templates", "kernel")
# 知識庫路徑字串：前面不能接路徑字元（knowledge/aos/x.json 是 repo 路徑、不算）；要帶 .json 或以 / 結尾才當指標
REF_RE = re.compile(r"(?<![\w/.\-])aos/[a-z0-9_][a-z0-9_/\-]*(?:\.json(?:#/[A-Za-z0-9_/~\-]*)?)?")
DETAILS_RE = re.compile(r"Details: knowledge_read ([^\s\"]+)")
RESIDUE = (("DateNoteBad", re.compile(r"(?<![\d-])\d{1,2}-\d{2} note\b", re.I), "a dated development note"),
           ("ThinkingRefBad", re.compile(r"thinking/"), "a link or path into thinking/"),
           ("PlaceholderBad", re.compile(r"\bXXX\b"), "an undefined XXX placeholder"))


class Tree:
    """出廠庫：root＝庫根、home＝proto8（工具、指令、impls 從這裡找）；JSON 只讀一次。"""

    def __init__(self, root, home):
        self.root, self.home, self._cache = root, home, {}

    def json(self, path):
        """一份 .json 的值；讀不到或壞＝(None, 原因)。"""
        real = os.path.realpath(path)
        if real not in self._cache:
            try:
                with open(real, encoding="utf-8") as h:
                    self._cache[real] = (json.load(h), None)
            except (OSError, ValueError) as e:
                self._cache[real] = (None, str(e))
        return self._cache[real]

    def files(self):
        """庫根底下的實體 .json（不跟捷徑、跳過 . 與 _ 開頭的資料夾）；回絕對路徑。"""
        for d, dirs, names in os.walk(self.root):
            dirs[:] = sorted(n for n in dirs if fs.visible(n))
            for n in sorted(names):
                if n.endswith(".json"):
                    yield os.path.join(d, n)

    def folders(self):
        for d, dirs, _ in os.walk(self.root):
            dirs[:] = sorted(n for n in dirs if fs.visible(n))
            yield d

    def show(self, loc):
        return fs.show(self.root, loc)

    def rel_home(self, path):
        return os.path.relpath(path, self.home)

    def exists(self, loc, depth=0):
        """位置在不在：路上的 $ref 照跟（相對＝含它那份檔的資料夾）；碰到 $env＝當作在（看環境，不判）。"""
        if depth > 20:
            return False
        if loc.tokens is None:
            return os.path.exists(loc.fs)
        if not loc.fs.endswith(".json") or not os.path.isfile(loc.fs):
            return False
        value, bad = self.json(loc.fs)
        if bad:
            return False
        for i, t in enumerate(loc.tokens):
            if isinstance(value, dict) and "$env" in value:
                return True
            if isinstance(value, dict) and isinstance(value.get("$ref"), str):
                try:
                    target = fs.join(fs.Loc(os.path.dirname(loc.fs), None), value["$ref"], False)
                except fs.ToolError:
                    return False
                return self.exists(fs.Loc(target.fs, (target.tokens or ()) + loc.tokens[i:]), depth + 1)
            if isinstance(value, dict) and t in value:
                value = value[t]
            elif isinstance(value, list) and t.isdigit() and int(t) < len(value):
                value = value[int(t)]
            else:
                return False
        return True

    def strings(self):
        """庫裡每個字串值 → (Loc, 字串)。"""
        for f in self.files():
            value, bad = self.json(f)
            if bad is None:
                yield from walk_strings(f, value, ())


def walk_strings(f, value, tokens):
    if isinstance(value, str):
        yield fs.Loc(f, tokens or None), value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from walk_strings(f, v, tokens + (k,))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk_strings(f, v, tokens + (str(i),))


def ref_problem(tree, text, where, base=None):
    """一條知識庫路徑；指不到＝RefMissing。base＝相對的起點（預設庫根）。"""
    try:
        loc = fs.join(base or fs.Loc(tree.root, None), text, False)
    except fs.ToolError as e:
        return Problem("error", "refs", "RefBad", where, "%s: %s" % (text, e))
    if tree.exists(loc):
        return None
    return Problem("error", "refs", "RefMissing", where, "%s does not resolve" % text)


def code_files(home):
    """lib、cmd、templates、kernel 底下的 .py／.json／_entry 與 bin/ 裡的檔（跳過 tests、thinking、archive 等）。"""
    for top in CODE_DIRS:
        for d, dirs, names in os.walk(os.path.join(home, top)):
            dirs[:] = sorted(n for n in dirs if n not in SKIP_DIRS)
            for n in sorted(names):
                if n.endswith((".py", ".json")) or n == "_entry" or os.path.basename(d) == "bin":
                    yield os.path.join(d, n)


def check_refs(tree):
    out, seen = [], set()
    for loc, text in tree.strings():                       # 內文裡的 aos/… 與 {"$ref": …}
        where = tree.show(loc)
        for m in REF_RE.findall(text):
            if (m.endswith(".json") or "#" in m or m.endswith("/")) and (where, m) not in seen:
                seen.add((where, m))
                p = ref_problem(tree, m, where)
                if p:
                    out.append(p)
        if loc.tokens and loc.tokens[-1] == "$ref":
            p = ref_problem(tree, text, where, fs.Loc(os.path.dirname(loc.fs), None))
            if p:
                out.append(p)
    for f in code_files(tree.home):                        # 程式字串（每支 _tooldef.json 的 Details: 路徑也在這裡掃到）
        try:
            with open(f, encoding="utf-8") as h:
                text = h.read()
        except (OSError, UnicodeDecodeError):
            continue
        where = tree.rel_home(f)
        found = {m for m in REF_RE.findall(text) if m.endswith(".json") or "#" in m or m.endswith("/")}
        for m in sorted(found):
            p = ref_problem(tree, m, where)
            if p:
                out.append(p)
    return out


def check_index(tree):
    out = []
    def table_problems(base, table, kids, inside, where):
        covered = set()
        for c in fs.cells(base, table, inside):
            if c.env:                                      # $env 格看環境，不判在不在
                continue
            if c.target is None:
                out.append(Problem("error", "index", "IndexBad", where, "entry %s: %s" % (c.key, c.note)))
                continue
            covered.add(c.target)
            if not tree.exists(c.target):
                out.append(Problem("error", "index", "NodeMissing", where, "index lists %s, which is not there" % c.key))
        for k in kids:
            if k not in covered:
                out.append(Problem("error", "index", "IndexEntryMissing", tree.show(k), "not listed in its index"))
    for d in tree.folders():
        idx = os.path.join(d, "_index.json")
        table, bad = tree.json(idx) if os.path.isfile(idx) else ({}, None)
        if bad or not isinstance(table, dict):
            out.append(Problem("error", "index", "IndexBad", tree.show(fs.Loc(idx, None)), bad or "must be a JSON object"))
            continue
        table_problems(fs.Loc(d, None), table, fs.folder_kids(d), False, tree.show(fs.Loc(d, None)))
    for f in tree.files():
        value, bad = tree.json(f)
        if bad:
            out.append(Problem("error", "index", "FileBad", tree.show(fs.Loc(f, None)), bad))
            continue
        for tokens, obj in branches(value, ()):
            loc = fs.Loc(f, tokens or None)
            if not isinstance(obj["_index"], dict):
                out.append(Problem("error", "index", "IndexBad", tree.show(loc), "_index must be an object"))
                continue
            table_problems(loc, obj["_index"], fs.value_kids(loc, obj), True, tree.show(loc))
    return out


def check_residue(tree):
    """庫內容（每個字串值）裡的日期註、指進 thinking/ 的路徑、XXX 記號；同一處同一種只報一次。"""
    out = []
    for loc, text in tree.strings():
        for code, pattern, what in RESIDUE:
            m = pattern.search(text)
            if m:
                out.append(Problem("error", "residue", code, tree.show(loc), "%s: %r" % (what, line_of(text, m.start()))))
    return out


def line_of(text, at, width=80):
    start = text.rfind("\n", 0, at) + 1
    end = text.find("\n", at)
    row = text[start:end if end >= 0 else len(text)]
    lo = max(0, at - start - width // 2)
    return row[lo:lo + width]


def check_size(tree, max_file, max_text):
    out = []
    for f in tree.files():
        n = os.path.getsize(f)
        if n > max_file:
            out.append(Problem("warning", "size", "", tree.show(fs.Loc(f, None)), "file is %d bytes (over %d)" % (n, max_file)))
    for loc, text in tree.strings():
        n = len(text.encode("utf-8"))
        if n > max_text:
            out.append(Problem("warning", "size", "", tree.show(loc), "text is %d bytes (over %d)" % (n, max_text)))
    return out


def branches(value, tokens):
    """JSON 裡每個帶 _index 的物件 → (指標段, 物件)。"""
    if isinstance(value, dict):
        if "_index" in value:
            yield tokens, value
        for k, v in value.items():
            if fs.visible(k):
                yield from branches(v, tokens + (k,))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from branches(v, tokens + (str(i),))
