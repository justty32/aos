"""aos_mdpath - 把一份 markdown 照它本來就有的結構讀成 json 值：給路徑拿一格（get）、列一層（ls）、整份倒成一棵樹（tree）。

使用者 11-21 晚（thinking 2026-11/21/知識庫-骨架加md-規劃-1121，規則全文在 07-尋址規則.md）：
「#/xxx尋址md，不要在那邊加東西，就用md現有的格式，比如#這種topic，大概尋一下就好」、「#標題段落中的第一個清單，可以用array尋址」、
「在子標題之外，#標題也會有自己的東西……弄一個保留key: _」、「如果一個#標題下，只有'''json ... '''，完全沒有其他內容，那他就可以當json」、
「表格可以有，一律先y軸再x軸……當二軸陣列」「表格的值一律字串，空的就是空字串」、「把xxx: yyy當做一個key-value pair，讓清單變成字典」、
「既有清單又有表格，那就只認清單」、「實作的時候先實作.md和json的轉換」。
路徑是 RFC 6901 的 token 串（已還原 ~0 ~1）。一段 token 在一個標題範圍裡的找法，順序固定：`_`（自己的內文）› 標題（整份第一個同字的、
不管幾個 #；完全一樣優先、不然 ASCII 不分大小寫）› 數字（自己內文裡第一個清單的第幾項；沒有清單才看第一張表的第幾列）› 清單的鍵（`鍵: 值`）。
整節只有一個 ```json 區塊＝那一節就是那份 json，往下照 json 走。C++ 對應的是 aos-directive 的 src/md.cpp；兩邊跑同一張表 py/tests/md_path_cases.json。
純標準庫、不讀檔、不寫 md。"""
import json
import re

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEAD = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*))?$")
ITEM = re.compile(r"^( *)([-*+]|[0-9]{1,9}[.)])(?:( +)(.*))?$")
SEP = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
INT = re.compile(r"^(0|[1-9][0-9]*)$")


class Missing(LookupError):
    """路徑指不到東西。reason 是英文一句（呼叫者接在自己的錯誤代號後面，例 PointerMissing）。"""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _lines(text):
    return [l[:-1] if l.endswith("\r") else l for l in text.split("\n")]


def _fenced(lines):
    """每一行在不在程式碼區塊裡（圍欄那兩行也算在裡面）。"""
    out, mark = [], None
    for l in lines:
        m = FENCE.match(l)
        if mark is None:
            if m:
                mark = m.group(1)
                out.append(True)
            else:
                out.append(False)
        else:
            out.append(True)
            s = l.strip()
            if m and s[0] == mark[0] and len(m.group(1)) >= len(mark) and not s.strip(mark[0]):
                mark = None
    return out


def _title(rest):
    t = (rest or "").strip()
    cut = t.rstrip("#")
    if cut != t and (not cut or cut[-1] in " \t"):
        t = cut.rstrip()
    return t


def _heads(lines):
    """[(行號, 級數, 標題字)]，程式碼區塊裡的不算。"""
    inside, out = _fenced(lines), []
    for i, l in enumerate(lines):
        if not inside[i]:
            m = HEAD.match(l)
            if m:
                out.append((i, len(m.group(1)), _title(m.group(2))))
    return out


def _text(lines, lead=True):
    """幾行 → 一段文字：頭尾空行去掉（lead＝False 不去頭）、有字就結尾一個換行。"""
    a, b = 0, len(lines)
    while b > a and not lines[b - 1].strip():
        b -= 1
    while lead and a < b and not lines[a].strip():
        a += 1
    return "\n".join(lines[a:b]) + "\n" if b > a else ""


def _same(a, b):
    return a.lower() == b.lower() if a.isascii() and b.isascii() else a == b


def _pick(names, tok):
    """names 裡第一個等於 tok 的位置；沒有就第一個 ASCII 不分大小寫相等的；都沒有＝-1。"""
    for i, n in enumerate(names):
        if n == tok:
            return i
    for i, n in enumerate(names):
        if _same(n, tok):
            return i
    return -1


def _indent(l):
    return len(l) - len(l.lstrip(" "))


def _list(lines):
    """幾行裡的第一個清單 → [項的幾行（已去掉記號與縮排）]；沒有＝None。"""
    inside = _fenced(lines)
    start = next((i for i, l in enumerate(lines) if not inside[i] and ITEM.match(l) and _indent(l) <= 3), None)
    if start is None:
        return None
    base = _indent(lines[start])
    items, cur, width = [], None, 0
    i = start
    while i < len(lines):
        l = lines[i]
        m = None if inside[i] else ITEM.match(l)
        if m and len(m.group(1)) == base:
            width = base + len(m.group(2)) + (len(m.group(3)) if m.group(3) and m.group(4) else 1)
            cur = [m.group(4) or ""]
            items.append((cur, width))
        elif inside[i] or not l.strip() or _indent(l) > base:
            cur.append(l[min(width, _indent(l)):] if l.strip() else "")
        elif i > start and lines[i - 1].strip() and not HEAD.match(l) and not (m and len(m.group(1)) < base):
            cur.append(l.lstrip(" "))                   # 接在有字的行後面、沒縮排的續行
        else:
            break
        i += 1
    out = []
    for cur, _w in items:
        while len(cur) > 1 and not cur[-1].strip():
            cur.pop()
        out.append(cur)
    return out


def _colon_end(after):
    """半形冒號後面：行尾、空白，或 `**` 再接行尾或空白（`**鍵:** 值`）才算分隔。"""
    if after.startswith("**"):
        after = after[2:]
    return not after or after[0] in " \t"


def _key(first):
    """清單項的第一行 → (鍵, 冒號後面的字) 或 None。冒號＝半形後面接空白或行尾，或全形；反引號裡的不算。"""
    tick, pos = False, -1
    for i, c in enumerate(first):
        if c == "`":
            tick = not tick
        elif not tick and (c == "\uff1a" or (c == ":" and _colon_end(first[i + 1:]))):
            pos = i
            break
    if pos < 0:
        return None
    key, rest = first[:pos].strip(), first[pos + 1:]
    if rest.startswith("**"):                           # **鍵:** 值
        rest = rest[2:]
    rest = rest.strip()
    if key.startswith("**"):
        key = key[2:]
    if key.endswith("**"):
        key = key[:-2]
    key = key.strip()
    if len(key) >= 2 and key[0] == "`" and key[-1] == "`":
        key = key[1:-1].strip()
    return (key, rest) if key else None


def _cells(line):
    s = line.strip()
    cells, cur, i = [], "", 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if s[i] == "|":
            cells.append(cur)
            cur = ""
        else:
            cur += s[i]
        i += 1
    cells.append(cur)
    if s.startswith("|"):
        cells = cells[1:]
    if cells and s.endswith("|") and not s.endswith("\\|"):
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _table(lines):
    """幾行裡的第一張表 → [[格…]…]（表頭是第 0 列，分隔線不算）；沒有＝None。"""
    inside = _fenced(lines)
    for i in range(len(lines) - 1):
        if inside[i] or inside[i + 1] or "|" not in lines[i] or "-" not in lines[i + 1] or not SEP.match(lines[i + 1]):
            continue
        rows, j = [_cells(lines[i])], i + 2
        while j < len(lines) and not inside[j] and lines[j].strip() and "|" in lines[j]:
            rows.append(_cells(lines[j]))
            j += 1
        return rows
    return None


def _json_block(body):
    """自己的內文整段只有一個 ```json 區塊 → (True, 值)；否則 (False, None)。"""
    a, b = 0, len(body)
    while b > a and not body[b - 1].strip():
        b -= 1
    while a < b and not body[a].strip():
        a += 1
    if b - a < 2:
        return False, None
    m, s = FENCE.match(body[a]), body[b - 1].strip()
    if not m or m.group(2).strip().lower() != "json":
        return False, None
    mark = m.group(1)
    if not (s and s[0] == mark[0] and len(s) >= len(mark) and not s.strip(mark[0])):
        return False, None
    inside = _fenced(body[a:b])
    if not all(inside) or any(FENCE.match(l) and l.strip()[0] == mark[0] and len(FENCE.match(l).group(1)) >= len(mark)
                              and not l.strip().strip(mark[0]) for l in body[a + 1:b - 1]):
        return False, None
    try:
        return True, json.loads("\n".join(body[a + 1:b - 1]))
    except ValueError:
        return False, None


class _Scope:
    """一個標題的範圍（root＝整份）：lines 全文、a..b 這一節的行、level 級數（root＝0）。"""
    def __init__(self, lines, heads, a, b, level):
        self.lines, self.heads, self.a, self.b, self.level = lines, heads, a, b, level

    def inner(self):
        return [h for h in self.heads if (self.a < h[0] if self.level else self.a <= h[0]) and h[0] < self.b and h[1] > self.level]

    def body(self):
        first = self.a + (1 if self.level else 0)
        subs = self.inner()
        return self.lines[first:subs[0][0] if subs else self.b]

    def direct(self):
        """直接的小節（跳過小節裡面的）。"""
        out, skip = [], -1
        for h in self.inner():
            if h[0] >= skip:
                out.append(h)
                skip = self.end(h)
        return out

    def end(self, h):
        return next((x[0] for x in self.heads if x[0] > h[0] and x[0] < self.b and x[1] <= h[1]), self.b)

    def child(self, tok):
        subs = self.inner()
        i = _pick([h[2] for h in subs], tok)
        if i < 0:
            return None
        return _Scope(self.lines, self.heads, subs[i][0], self.end(subs[i]), subs[i][1])

    def json(self):
        if not self.level or self.inner():
            return False, None
        return _json_block(self.body())

    def value(self):
        if not self.level:
            return "\n".join(self.lines)
        ok, v = self.json()
        return v if ok else _text(self.lines[self.a:self.b], lead=False)


def _block_step(lines, tok, skip_first):
    """一段文字（自己的內文、清單項、鍵的值）往下一格 → ("block", 幾行) / ("row", 格) / None。"""
    rest = lines[1:] if skip_first else lines
    items = _list(rest)
    if INT.match(tok):
        n = int(tok)
        if items is not None:
            return ("item", items[n]) if n < len(items) else None
        rows = _table(rest)
        if rows is not None and n < len(rows):
            return ("row", rows[n])
        return None
    if items is None:
        return None
    keyed = [(_key(it[0]), it) for it in items]
    keyed = [(k, it) for k, it in keyed if k]
    i = _pick([k[0] for k, _it in keyed], tok)
    if i < 0:
        return None
    (key, rest1), it = keyed[i]
    return ("value", ([rest1] if rest1 else []) + it[1:])


def _block_text(lines):
    return _text(lines).rstrip("\n")


def _json_step(v, tok):
    if isinstance(v, dict) and tok in v:
        return True, v[tok]
    if isinstance(v, list) and INT.match(tok) and int(tok) < len(v):
        return True, v[int(tok)]
    return False, None


def _walk(text, toks):
    """走到底 → (種類, 東西)：scope／body／item／value／row／json。走不到丟 Missing。"""
    lines = _lines(text)
    kind, at = "scope", _Scope(lines, _heads(lines), 0, len(lines), 0)
    for n, tok in enumerate(toks):
        nxt = None
        if kind == "scope":
            ok, v = at.json()
            if tok == "_":
                nxt = ("body", at.body())
            elif ok:
                found, v2 = _json_step(v, tok)
                nxt = ("json", v2) if found else None
            else:
                sub = at.child(tok)
                nxt = ("scope", sub) if sub is not None else _block_step(at.body(), tok, False)
        elif kind in ("body", "item", "value"):
            nxt = _block_step(at, tok, kind == "item")
        elif kind == "row":
            nxt = ("json", at[int(tok)]) if INT.match(tok) and int(tok) < len(at) else None
        elif kind == "json":
            found, v2 = _json_step(at, tok)
            nxt = ("json", v2) if found else None
        if nxt is None:
            here = "/" + "/".join(t.replace("~", "~0").replace("/", "~1") for t in toks[:n]) if n else "the document"
            names = _names(kind, at)
            raise Missing("%s has no %s%s" % (here, tok, " (it has: %s)" % ", ".join(names[:20]) if names else " (nothing to go into)"))
        kind, at = nxt
    return kind, at


def _names(kind, at):
    """這一格底下有哪些名字（給 ls 與錯誤訊息）。"""
    if kind == "scope":
        ok, v = at.json()
        if ok:
            return _names("json", v)
        body = at.body()
        return (["_"] if _text(body) else []) + [h[2] for h in at.direct()] + _block_names(body, False)
    if kind in ("body", "item", "value"):
        return _block_names(at, kind == "item")
    if kind == "row":
        return [str(i) for i in range(len(at))]
    if isinstance(at, dict):
        return list(at)
    if isinstance(at, list):
        return [str(i) for i in range(len(at))]
    return []


def _block_names(lines, skip_first):
    rest = lines[1:] if skip_first else lines
    items = _list(rest)
    if items is not None:
        return [(_key(it[0]) or (str(i),))[0] for i, it in enumerate(items)]
    rows = _table(rest)
    return [str(i) for i in range(len(rows))] if rows is not None else []


def get(text, toks):
    """text 這份 md 的 toks 那一格的值：文字、字串陣列（表格的一列）或 json 值（json 區塊）。toks 空＝整份文字。"""
    kind, at = _walk(text, list(toks))
    if kind == "scope":
        return text if not toks else at.value()
    if kind == "body":
        return _text(at)
    if kind in ("item", "value"):
        return _block_text(at)
    return at


def ls(text, toks):
    """那一格底下的名字，照出現的順序：`_`（自己的內文有字時）、直接的小節、清單的項（有鍵用鍵、沒有用號碼）或表格的列號；json 區塊＝它的鍵。"""
    return _names(*_walk(text, list(toks)))


def tree(text):
    """整份倒成一棵 json：標題＝鍵；沒有小節＝自己的內文（或那份 json）；有小節＝物件（`_` 放自己的內文，沒字就不放）；同名標題只留第一個。"""
    lines = _lines(text)

    def build(sc):
        subs = sc.direct()
        ok, v = sc.json()
        if ok:
            return v
        own = _text(sc.body())
        if not subs and sc.level:
            return own
        out = {"_": own} if own else {}
        for h in subs:
            if h[2] != "_" and h[2] not in out:         # 叫 `_` 的標題尋不到（保留名）
                out[h[2]] = build(_Scope(sc.lines, sc.heads, h[0], sc.end(h), h[1]))
        return out
    return build(_Scope(lines, _heads(lines), 0, len(lines), 0))


def split(path):
    """`檔#/指標` → (檔, token 串)；沒有 # ＝整份。指標不以 / 開頭丟 ValueError。"""
    f, sep, ptr = path.partition("#")
    if not sep or ptr in ("", "/"):
        return f, []
    if not ptr.startswith("/"):
        raise ValueError("after # the pointer must start with /")
    return f, [t.replace("~1", "/").replace("~0", "~") for t in ptr[1:].split("/")]
