"""`tools wrap-cli` 機械版之二：用規則解 help 文字的 usage 行與選項行 → 參數表；解不出來的列出來，不猜。"""
import re

from aos_agent_tools_wrapcli_const import FLAG, FLOAT_META, HELP_MAX, INT_META, SKIP_FLAGS
from aos_agent_tools_wrapcli_argparse import _dest, _safe_name


# ------------------------------------------------------------------ 機械版：help 文字 ----

USAGE = re.compile(r'\s*usage:\s*(.*)\Z', re.I)
PLACEHOLDER = {'option', 'options', 'opts', 'flags', 'flag', 'switches'}
ITEM = re.compile(r'-{1,2}[A-Za-z0-9][A-Za-z0-9_.-]*')
MENTION = re.compile(r'(?<![\w/.\-])(-{1,2}[A-Za-z][\w-]*)')
REPEAT = re.compile(r'\b(repeatable|can be repeated|may be repeated|multiple times|more than once)\b', re.I)
CAN_BE = re.compile(r'\b(?:can be|is one of|one of|must be one of)\s*:?\s*'
                    r'([\w.-]+(?:\s*,\s*(?:or\s+)?[\w.-]+)+)', re.I)


def _usage_tokens(s):
    """usage 字串 → 巢狀清單：('opt', [...]) 方括號、('group', [...]) 圓括號、('choice', [..])、('word', w)、
    ('ellipsis',)、('bar',)。"""
    pos = 0

    def seq(end):
        nonlocal pos
        items = []
        while pos < len(s):
            c = s[pos]
            if c.isspace():
                pos += 1
            elif c == end:
                pos += 1
                return items
            elif c in '])}':
                pos += 1
            elif c == '[':
                pos += 1
                items.append(('opt', seq(']')))
            elif c == '(':
                pos += 1
                items.append(('group', seq(')')))
            elif c in '{<':
                close = '}' if c == '{' else '>'
                j = s.find(close, pos)
                j = len(s) if j < 0 else j
                inner = s[pos + 1:j]
                pos = j + 1
                if c == '{':
                    items.append(('choice', [x.strip() for x in inner.split(',') if x.strip()]))
                else:
                    items.append(('word', inner.strip()))
            elif s.startswith('...', pos) or s.startswith('…', pos):
                pos += 3 if s.startswith('...', pos) else 1
                items.append(('ellipsis',))
            elif c == '|':
                pos += 1
                items.append(('bar',))
            else:
                m = re.match(r'[^\s\[\](){}<>|]+', s[pos:])
                w = m.group()
                pos += len(w)
                if w.endswith('...') and len(w) > 3:
                    items += [('word', w[:-3]), ('ellipsis',)]
                else:
                    items.append(('word', w))
        return items

    return seq(None)


def _usage_walk(items, optional, out):
    """把 usage 的 token 變成 out['pos']（位置參數）與 out['opts']（旗標 → 屬性）。"""
    i = 0
    while i < len(items):
        it = items[i]
        many = i + 1 < len(items) and items[i + 1][0] == 'ellipsis'
        kind = it[0]
        if kind == 'opt':
            inner = it[1]
            words = [x for x in inner if x[0] == 'word']
            if words and all(x[0] in ('word', 'ellipsis') for x in inner) and len(words) == 1 \
                    and words[0][1].lower() in PLACEHOLDER:
                pass                                       # [OPTION]... [options] 這種佔位
            elif inner and inner[0][0] == 'word' and inner[0][1].startswith('-') and len(inner[0][1]) > 1:
                _usage_opts(inner, True, out)
            elif len(inner) == 1 and many:
                _usage_walk(inner + [('ellipsis',)], True, out)
            else:
                _usage_walk(inner, True, out)
        elif kind == 'group':
            _usage_walk(it[1], optional, out)
        elif kind == 'choice':
            out['pos'].append({'raw': 'choice', 'choices': it[1], 'required': not optional, 'array': many})
        elif kind == 'word':
            w = it[1]
            if w.startswith('-') and len(w) > 1:
                arg = None
                nxt = items[i + 1] if i + 1 < len(items) else None
                if nxt and nxt[0] == 'word' and not nxt[1].startswith('-') and re.match(r'[A-Z][A-Z0-9_-]*\Z', nxt[1]):
                    arg = nxt[1]
                    i += 1
                _usage_flag(w, arg, not optional, many, out)
            elif w.lower() not in PLACEHOLDER:
                out['pos'].append({'raw': w, 'required': not optional, 'array': many})
        i += 1


def _usage_opts(inner, optional, out):
    """方括號裡以 - 開頭：[-abc] 一串開關、[-f file]、[--foo=FOO]、[-a | -b]。"""
    if len(inner) == 1 and re.match(r'-[A-Za-z0-9]{2,}\Z', inner[0][1]):
        for ch in inner[0][1][1:]:
            _usage_flag('-' + ch, None, False, False, out)
        return
    parts, cur = [], []
    for x in inner:
        if x[0] == 'bar':
            parts.append(cur)
            cur = []
        else:
            cur.append(x)
    parts.append(cur)
    for part in parts:
        if not part or part[0][0] != 'word' or not part[0][1].startswith('-'):
            continue
        many = any(x[0] == 'ellipsis' for x in part)
        args = [x[1] for x in part[1:] if x[0] == 'word']
        choice = [x[1] for x in part[1:] if x[0] == 'choice']
        _usage_flag(part[0][1], args[0] if args else ('{%s}' % ','.join(choice[0]) if choice else None),
                    False, many, out)


def _usage_flag(word, arg, required, many, out):
    if '=' in word:
        word, arg = word.split('=', 1)
    if not FLAG.match(word):
        return
    out['opts'].setdefault(word, {'arg': arg, 'required': required, 'array': many, 'line': out['line']})


def _parse_usage(lines):
    """找 usage 區塊：回 (第一種用法的 token 解讀, 用到的行號集合, 附註)。"""
    for idx, line in enumerate(lines):
        m = USAGE.match(line)
        if not m:
            continue
        used = {idx}
        first = m.group(1).strip()
        body_lines = []
        j = idx + 1
        if not first:                                     # Usage: 單獨一行，下一行才是用法
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].startswith(' '):
                first = lines[j].strip()
                used.add(j)
                j += 1
        prog = first.split()[0] if first else ''
        notes = []
        while j < len(lines) and lines[j].strip() and lines[j].startswith(' '):
            s = lines[j].strip()
            if s.lower().startswith('or:') or (prog and s.split()[0] == prog):
                notes.append((j + 1, '另一種用法，只照第一種解'))
            elif not ITEM.match(s) or s.startswith(('[', '<', '{')):
                body_lines.append(s)
            else:
                break
            used.add(j)
            j += 1
        text = ' '.join([first] + body_lines)
        out = {'pos': [], 'opts': {}, 'line': idx + 1}
        _usage_walk(_usage_tokens(text)[1:], False, out)   # 第一個 token 是程式名
        return out, used, notes
    return {'pos': [], 'opts': {}, 'line': None}, set(), []


def _option_line(text):
    """'-x, --long=ARG  說明' → (items [(旗標, 參數名, 寫法)], 說明或 None, 問題或 None)；不是選項行回 None。"""
    pos, items = 0, []
    while True:
        m = ITEM.match(text, pos)
        if not m:
            break
        flag, pos, arg, style = m.group(), m.end(), None, None
        rest = text[pos:]
        if rest.startswith('[='):
            j = rest.find(']')
            if j > 2:
                arg, style, pos = rest[2:j], '=', pos + j + 1
        elif rest.startswith('='):
            m2 = re.match(r'=([^\s,:]+)', rest)
            if m2:
                arg, style, pos = m2.group(1), '=', pos + m2.end()
        else:
            m2 = (re.match(r' (<[^>]+>|\{[^}]+\}|[A-Z][A-Z0-9_-]*)(?=\s|$|,|:)', rest)
                  or re.match(r' ([^\s,:\-][^\s,:]*)(?=\s{2,}|$|,|:)', rest))
            if m2:
                arg, style, pos = m2.group(1), ' ', pos + m2.end()
        items.append((flag, arg, style))
        sep = re.match(r'\s*[,|/]\s*(?=-)', text[pos:])
        if not sep:
            break
        pos += sep.end()
    if not items:
        return None
    rest = text[pos:]
    if not rest.strip():
        return items, None, None
    if rest.startswith(':'):
        return items, rest[1:].strip(), None
    if re.match(r'\s{2,}', rest):
        return items, rest.strip(), None
    return items, None, '旗標後面只隔一格就接字，分不出是參數名還是說明'


def _meta_type(arg):
    """參數名 → (型別, choices)。{a,b}、a|b＝choices；N、NUM、<n>…＝integer；FLOAT＝number；其他 string。"""
    if arg is None:
        return 'boolean', None
    a = arg.strip('<>')
    if a.startswith('{') and a.endswith('}'):
        return 'string', [x.strip() for x in a[1:-1].split(',') if x.strip()]
    if '|' in a and all(re.match(r'[a-z0-9][\w.-]*\Z', x) for x in a.split('|')):
        return 'string', a.split('|')
    if a.lower() in INT_META:
        return 'integer', None
    if a.lower() in FLOAT_META:
        return 'number', None
    return 'string', None


def parse_help(text):
    """help 文字 → {'description', 'params', 'rows', 'unparsed': [(行, 原文, 為什麼)], 'notes'}。規則見 tools-llm.md。"""
    lines = text.split('\n')
    usage, used, notes = _parse_usage(lines)
    opt_lines = []                                        # (行號, items, 說明, 縮排)
    unparsed, section, cont_indent, current = [], None, None, None
    prose = []
    for idx, line in enumerate(lines):
        if idx in used:
            current = None
            continue
        if not line.strip():
            current = None
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if current is not None and cont_indent is None and indent > current[3] and not (
                ITEM.match(s) and _option_line(s)):
            cont_indent = indent                          # 說明寫在下一行：第一行續行定下續行的縮排
        if current is not None and cont_indent is not None and indent >= cont_indent:
            if current[2] is None:
                current[2] = s
            else:
                current[2] += ' ' + s
            continue
        got = _option_line(s) if ITEM.match(s) else None
        if got:
            items, desc, problem = got
            if problem:
                unparsed.append((idx + 1, s, problem))
                current = None
                continue
            current = [idx + 1, items, desc, indent]
            opt_lines.append(current)
            cont_indent = (indent + len(s) - len(desc)) if desc else None
            continue
        current = None
        if indent == 0 and s.endswith(':'):
            section = s
            continue
        if section and indent > 0 and re.search(r'option|flag|argument', section, re.I) \
                and 'positional' not in section.lower():
            unparsed.append((idx + 1, s, '在「%s」段裡，但不是選項行' % section))
            continue
        if section and 'positional' in section.lower() and indent > 0:
            m = re.match(r'(\S+)\s{2,}(.*)', s)
            if m:
                prose.append((idx + 1, s, ('positional', m.group(1), m.group(2))))
                continue
        prose.append((idx + 1, s, None))
    # 同一個旗標有沒有「光溜溜」的寫法：有的話 --check=quiet 這種是固定值別名，不是參數
    bare, values = set(), {}
    for _, items, _, _ in opt_lines:
        for flag, arg, style in items:
            if arg is None:
                bare.add(flag)
            elif style == '=':
                values.setdefault(flag, set()).add(arg)
    params, rows, seen_flags, seen_names = [], [], {}, set()
    for line_no, items, desc, _ in opt_lines:
        flags, arg, joiner, literal = [], None, ' ', []
        for flag, a, style in items:
            if a is not None and style == '=' and re.match(r'[a-z][\w-]*\Z', a) and (
                    flag in bare or len(values.get(flag, ())) > 1):
                literal.append('%s=%s' % (flag, a))
                continue
            if flag not in flags:
                flags.append(flag)
            if a is not None and arg is None:
                arg = a
            if style == '=':
                joiner = '='
        label = ', '.join(f for f, _, _ in items)
        if any(f in SKIP_FLAGS for f in flags) or (flags in (['-h'], ['-?']) and 'help' in (desc or '').lower()):
            rows.append(['skip', label, 'help／version 不收', line_no])
            continue
        dup = [f for f in flags if f in seen_flags]
        if dup:
            rows.append(['reject', label, '旗標 %s 在第 %d 行已經有了' % ('、'.join(dup), seen_flags[dup[0]]), line_no])
            continue
        t, choices = _meta_type(arg)
        desc = desc or ''
        if arg is not None and not choices:
            m = CAN_BE.search(desc)
            if m:
                choices = [x.strip() for x in re.split(r'\s*,\s*(?:or\s+)?', m.group(1)) if x.strip()]
        p = {'name': _safe_name(_dest(flags)), 'flags': flags, 'kind': 'flag' if arg is None else 'option',
             'type': t, 'array': False, 'required': False, 'help': desc, 'line': line_no}
        if arg is None:
            shorts = [f for f in flags if re.match(r'-[A-Za-z]\Z', f)]
            if any(re.search(r'(?<![\w-])-%s{2,}(?![\w-])' % re.escape(f[1]), desc) for f in shorts):
                p.update(kind='count', type='integer')    # 說明裡寫了 -vv：可重複的開關
        else:
            if choices:
                p['choices'] = choices
            if any(f.startswith('--') for f in flags):
                p['joiner'] = joiner
            if REPEAT.search(desc):
                p.update(array=True, multi='repeat')
        note = '；'.join(['固定值寫法 %s 不當參數' % '、'.join(literal)] if literal else [])
        params.append(p)
        rows.append(['ok', p['name'], note, line_no])
        for f in flags:
            seen_flags[f] = line_no
    # usage 裡的旗標：補必填、補選項段沒寫的
    for flag, u in usage['opts'].items():
        if flag in SKIP_FLAGS or flag == '-h':
            continue
        owner = next((p for p in params if flag in p['flags']), None)
        if owner:
            if u['required']:
                owner['required'] = True
            continue
        t, choices = _meta_type(u['arg'])
        p = {'name': _safe_name(_dest([flag])), 'flags': [flag], 'kind': 'flag' if u['arg'] is None else 'option',
             'type': t, 'array': u['array'] and u['arg'] is not None, 'required': u['required'], 'help': '',
             'line': u['line']}
        if choices:
            p['choices'] = choices
        params.append(p)
        rows.append(['ok', p['name'], '只在 usage 行出現', u['line']])
        seen_flags[flag] = u['line']
    # 位置參數
    pos_help = {x[2][1].strip('<>'): x[2][2] for x in prose if x[2]}
    positionals = []
    for u in usage['pos']:
        raw = u['raw'].strip('<>')
        p = {'name': _safe_name(raw.lower()), 'flags': [], 'kind': 'positional', 'type': 'string',
             'array': u['array'], 'required': u['required'], 'help': pos_help.get(raw, ''), 'line': usage['line']}
        if u.get('choices'):
            p['choices'] = u['choices']
            p['help'] = pos_help.get('{%s}' % ','.join(u['choices']), '')
        positionals.append(p)
        rows.append(['ok', p['name'], '位置參數（usage 行）', usage['line']])
    # 名字撞：選項之間撞＝後面的拒收；位置參數撞到選項＝加 _arg
    final = []
    for p in params:
        if p['name'] in seen_names:
            _reject_row(rows, p, '名字 %s 跟前面的撞了' % p['name'])
            continue
        seen_names.add(p['name'])
        final.append(p)
    for p in positionals:
        while p['name'] in seen_names:
            p['name'] += '_arg'
        seen_names.add(p['name'])
    known = {f for p in final for f in p['flags']}
    for line_no, s, extra in prose:
        if extra:
            continue
        unknown = []
        for f in MENTION.findall(s):
            if f in known or f in SKIP_FLAGS or f in unknown:
                continue
            if re.match(r'-([A-Za-z])\1+\Z', f) and '-' + f[1] in known:
                continue
            unknown.append(f)
        if unknown:
            unparsed.append((line_no, s, '提到 %s，但沒有它的選項行' % '、'.join(unknown)))
    return {'description': _describe(lines, used), 'params': positionals + final, 'rows': rows,
            'unparsed': unparsed, 'notes': notes}


def _reject_row(rows, p, why):
    for r in rows:
        if r[0] == 'ok' and r[1] == p['name'] and r[3] == p['line']:
            r[0], r[2] = 'reject', why
            return


def _describe(lines, used):
    """一句話描述：第一行不是 usage 也不是選項＝「名字 - 描述」；不然 usage 後第一段文字的第一句。"""
    nonblank = [(i, s.strip()) for i, s in enumerate(lines) if s.strip()]
    if not nonblank:
        return None
    i0, first = nonblank[0]
    if i0 not in used and not ITEM.match(first):
        m = re.match(r'\S+(?:\s+v?[\d.]+)?\s+-{1,2}\s+(.*)', first)
        return (m.group(1) if m else first)[:HELP_MAX]
    after = [(i, s) for i, s in nonblank if i not in used and i > max(used, default=-1)]
    for i, s in after:
        if not ITEM.match(s) and not s.endswith(':') and not lines[i].startswith(' '):
            para = [s]
            for j in range(i + 1, len(lines)):
                if not lines[j].strip() or lines[j].startswith(' '):
                    break
                para.append(lines[j].strip())
            text = ' '.join(para)
            m = re.match(r'(.+?[.!?])(\s|$)', text)
            return (m.group(1) if m else text)[:HELP_MAX]
    return None
