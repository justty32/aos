"""按標題切 Markdown 成「節」：md_section 工具與 aos-directives（人格編輯）共用，只用標準庫。

一節＝一行 ATX 標題（`#`～`######` 後接空白或行尾）起，到下一個「同級或更高級」標題之前（含子節）。
``` 或 ~~~ 圍起來的程式碼區塊裡的 # 不算標題。第一個標題之前的文字＝前言（不算一節）。
行一律用 splitlines(keepends=True) 切，原本的換行字元（LF／CRLF）照留。
"""
import re

HEADING = re.compile(r'^(#{1,6})(?:[ \t]+(.*?))?[ \t]*#*[ \t]*$')
FENCE = re.compile(r'^[ ]{0,3}(`{3,}|~{3,})')
ITEM = re.compile(r'^[ ]{0,3}[-*+][ \t]+\S')
WF_ITEM = re.compile(r'^- \[[^\]\n]+\] .+ → .+$')


class Section:
    __slots__ = ('index', 'level', 'title', 'start', 'end')

    def __init__(self, index, level, title, start):
        self.index, self.level, self.title, self.start, self.end = index, level, title, start, None

    @property
    def heading(self):
        return '#' * self.level + ' ' + self.title


def split_lines(text):
    return text.splitlines(True)


def sections(lines):
    """回 [Section]；start＝標題那行的索引（從 0），end＝節結束的下一行索引。"""
    out, fence = [], None
    for i, line in enumerate(lines):
        bare = line.rstrip('\r\n')
        m = FENCE.match(bare)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        h = HEADING.match(bare)
        if h:
            out.append(Section(len(out), len(h.group(1)), (h.group(2) or '').strip(), i))
    for k, s in enumerate(out):
        s.end = len(lines)
        for t in out[k + 1:]:
            if t.level <= s.level:
                s.end = t.start
                break
    return out


def normalize(heading):
    """比對用：去掉前後空白、開頭的 #（有的話）與結尾的 #。回 (級數或 None, 標題文字)。"""
    h = heading.strip()
    m = HEADING.match(h)
    if m and h.startswith('#'):
        return len(m.group(1)), (m.group(2) or '').strip()
    return None, h


def find(secs, heading):
    """照標題找：給了 # 就要級數也對；回符合的 Section 串列（可能 0 或多個）。"""
    level, title = normalize(heading)
    return [s for s in secs if s.title == title and (level is None or s.level == level)]


def body_range(s, lines):
    """節的本文（不含標題行）：(開始, 結束)；結束不含節尾的空白行，讓新增的東西貼著內容。"""
    end = s.end
    while end > s.start + 1 and not lines[end - 1].strip():
        end -= 1
    return s.start + 1, end


def newline_of(lines):
    for line in lines:
        if line.endswith('\r\n'):
            return '\r\n'
        if line.endswith('\n'):
            return '\n'
    return '\n'


def as_lines(text, nl):
    """把使用者給的文字轉成行（換行統一成檔案的），最後一行補換行。空字串＝沒有行。"""
    if text == '':
        return []
    parts = text.replace('\r\n', '\n').split('\n')
    if parts[-1] == '':
        parts.pop()
    return [p + nl for p in parts]


def items(lines, start, end):
    """[start, end) 裡的清單項目行（只看頂層的 - * + 開頭）；回 [(行索引, 去掉換行的內容)]。"""
    out, fence = [], None
    for i in range(start, end):
        bare = lines[i].rstrip('\r\n')
        m = FENCE.match(bare)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        if ITEM.match(bare):
            out.append((i, bare))
    return out
