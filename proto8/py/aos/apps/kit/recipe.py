# aos/apps/kit/recipe.py - read kits.json and a kit's make block, assemble the system text from its layers, check a kit.
import json
import os
import re

PLACEHOLDER = re.compile(r'<([A-Z][A-Z0-9_]*)>')
KEY = re.compile(r'[A-Z][A-Z0-9_]*$')
SITE = '@site'


class Fail(Exception):
    """One error line: code (e.g. KitUnknown) and reason."""
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code


def read_text(path, what):
    try:
        with open(path, encoding='utf-8', newline='') as fh:
            return fh.read()
    except FileNotFoundError:
        raise Fail('FileMissing', '%s %s does not exist' % (what, path))
    except IsADirectoryError:
        raise Fail('FileMissing', '%s %s is a folder, not a file' % (what, path))
    except OSError as e:
        raise Fail('ReadFailed', 'cannot read %s %s: %s' % (what, path, e.strerror or e))
    except UnicodeError:
        raise Fail('ReadFailed', '%s %s is not UTF-8 text' % (what, path))


def default_kits_dir(env=None):
    env = os.environ if env is None else env
    home = env.get('AOS_HOME')
    if not home:
        raise Fail('KitsMissing', 'no --kits DIR and AOS_HOME is not set')
    return os.path.join(home, 'templates', 'kits')


def load_kits(kits_dir):
    """kits.json of kits_dir -> its dict (with a dict "kits")."""
    path = os.path.join(kits_dir, 'kits.json')
    if not os.path.isfile(path):
        raise Fail('KitsMissing', 'no kits.json in %s' % kits_dir)
    try:
        data = json.loads(read_text(path, 'kits index'))
    except ValueError:
        raise Fail('JsonBad', '%s is not valid JSON' % path)
    if not isinstance(data, dict) or not isinstance(data.get('kits'), dict):
        raise Fail('KitsBad', '%s has no "kits" object' % path)
    return data


def get_kit(data, name, kits_dir):
    kit = data['kits'].get(name)
    if kit is None:
        known = ', '.join(sorted(data['kits'])) or 'none'
        raise Fail('KitUnknown', 'no kit %s in %s (kits: %s)' % (name, os.path.join(kits_dir, 'kits.json'), known))
    if not isinstance(kit, dict):
        raise Fail('KitsBad', 'kit %s in kits.json is not an object' % name)
    return kit


def get_make(kit, name):
    """The kit's make block, checked: {"layers": [...], "defaults": {...}, "limit": N or None}."""
    make = kit.get('make')
    if make is None:
        raise Fail('MakeMissing', 'kit %s has no "make" block in kits.json' % name)
    if not isinstance(make, dict):
        raise Fail('RecipeBad', 'kit %s: "make" is not an object' % name)
    layers = make.get('layers')
    if not isinstance(layers, list) or not layers or not all(isinstance(x, str) and x for x in layers):
        raise Fail('RecipeBad', 'kit %s: make.layers must be a non-empty list of file names' % name)
    for x in layers:
        if x.startswith('@') and x != SITE:
            raise Fail('RecipeBad', 'kit %s: unknown layer %s (only %s is special)' % (name, x, SITE))
        if not x.startswith('@') and os.path.isabs(x):
            raise Fail('RecipeBad', 'kit %s: layer %s must be relative to the kits folder' % (name, x))
    defaults = make.get('defaults', {})
    if not isinstance(defaults, dict) or not all(isinstance(k, str) and KEY.match(k) and isinstance(v, str)
                                                 for k, v in defaults.items()):
        raise Fail('RecipeBad', 'kit %s: make.defaults must map NAME (A-Z, 0-9, _) to text' % name)
    limit = make.get('limit')
    if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
        raise Fail('RecipeBad', 'kit %s: make.limit must be a positive whole number' % name)
    return {'layers': layers, 'defaults': defaults, 'limit': limit}


def parse_sets(items):
    """["KEY=VALUE", ...] -> {KEY: VALUE}; the last one of a key wins."""
    out = {}
    for item in items or ():
        key, eq, value = item.partition('=')
        if not eq or not KEY.match(key):
            raise Fail('ArgumentsBad', '--set takes KEY=VALUE with KEY in A-Z, 0-9, _ (got %r)' % item)
        out[key] = value
    return out


class Resolver:
    """Fills placeholders line by line. For a placeholder <NAME> on a line, the first of these wins:
    --set NAME_LINE (whole line), --set NAME (in place), default NAME_LINE (whole line), default NAME (in place).
    A whole-line value replaces the line; an empty one, or a line left blank by an empty value, drops the line."""

    def __init__(self, sets, defaults):
        self.sets, self.defaults = sets, defaults
        self.used = set()

    def lookup(self, name):
        for src in (self.sets, self.defaults):
            if name + '_LINE' in src:
                return 'line', src[name + '_LINE'], (src, name + '_LINE')
            if name in src:
                return 'inline', src[name], (src, name)
        return None

    def line(self, text):
        """One line (no newline) -> the new line, or None to drop it."""
        found = [(m.group(1), self.lookup(m.group(1))) for m in PLACEHOLDER.finditer(text)]
        for name, hit in found:
            if hit and hit[0] == 'line':
                self._use(hit)
                return hit[1] if hit[1] != '' else None
        if not any(hit for _, hit in found):
            return text

        def sub(m):
            hit = self.lookup(m.group(1))
            if hit is None:
                return m.group(0)
            self._use(hit)
            return hit[1]
        out = PLACEHOLDER.sub(sub, text)
        if out.strip() == '' and text.strip() != '':
            return None
        return out

    def _use(self, hit):
        src, key = hit[2]
        if src is self.sets:
            self.used.add(key)

    def text(self, text):
        lines = []
        for one in text.split('\n'):
            new = self.line(one)
            if new is not None:
                lines.append(new)
        return '\n'.join(lines)


def assemble(kits_dir, make, site=None, sets=None):
    """-> {"text", "layers" (the files used, in order), "unresolved" (names left), "unused_sets"}.
    Layers in recipe order; @site is the --site file, skipped when none is given. Every layer but the
    last loses its trailing newlines; layers are joined by one blank line; the last is kept as it is."""
    sets = sets or {}
    resolver = Resolver(sets, make['defaults'])
    parts, used = [], []
    for layer in make['layers']:
        if layer == SITE:
            if site is None:
                continue
            path, what = site, 'site layer'
        else:
            path, what = os.path.join(kits_dir, layer), 'layer'
        parts.append(resolver.text(read_text(path, what)))
        used.append(path if layer == SITE else layer)
    if not parts:
        raise Fail('RecipeBad', 'no layers to assemble')
    body = [p.rstrip('\n') for p in parts[:-1]] + [parts[-1]]
    last = len(body) - 1
    text = '\n\n'.join(p for i, p in enumerate(body) if i == last or p.strip() != '')
    return {'text': text, 'layers': used,
            'unresolved': sorted(set(PLACEHOLDER.findall(text))),
            'unused_sets': sorted(set(sets) - resolver.used)}


def first_difference(a, b):
    """1-based line number of the first line that differs."""
    la, lb = a.split('\n'), b.split('\n')
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            return i + 1
    return min(len(la), len(lb)) + 1


def check(kits_dir, data, name):
    """-> {"kit", "ok", "problems": [str], "chars", "limit"}: the kit's files exist, its system file equals the
    assembled layers with defaults (no site), no placeholder is left, and both stay within the limit."""
    kit = get_kit(data, name, kits_dir)
    problems = []
    chars = limit = None
    files = {}
    for key in ('system', 'tools'):
        rel = kit.get(key)
        if not isinstance(rel, str) or not rel:
            problems.append('kits.json has no "%s" file for this kit' % key)
            continue
        path = os.path.join(kits_dir, rel)
        if not os.path.isfile(path):
            problems.append('missing: %s' % rel)
            continue
        files[key] = (rel, path)
    if 'tools' in files:
        try:
            json.loads(read_text(files['tools'][1], 'tools file'))
        except ValueError:
            problems.append('tools file %s is not valid JSON' % files['tools'][0])
        except Fail as e:
            problems.append(str(e))
    try:
        make = get_make(kit, name)
    except Fail as e:
        problems.append(str(e))
        make = None
    if make is not None:
        limit = make['limit']
        missing = [x for x in make['layers'] if x != SITE and not os.path.isfile(os.path.join(kits_dir, x))]
        for x in missing:
            problems.append('missing: %s (a layer)' % x)
        if not missing:
            try:
                built = assemble(kits_dir, make)
            except Fail as e:
                problems.append(str(e))
                built = None
            if built is not None:
                text = built['text']
                chars = len(text)
                for n in built['unresolved']:
                    problems.append('unresolved: <%s> is left in the assembled text' % n)
                if limit is not None and chars > limit:
                    problems.append('too long: the assembled text is %d chars, the limit is %d' % (chars, limit))
                if 'system' in files:
                    rel, path = files['system']
                    try:
                        shipped = read_text(path, 'system file')
                    except Fail as e:
                        problems.append(str(e))
                    else:
                        if shipped != text:
                            problems.append('stale: %s differs from the assembled layers (first difference at line %d); '
                                            'assemble it again with aos-kit make %s -o %s' % (rel, first_difference(shipped, text), name, path))
                            for n in sorted(set(PLACEHOLDER.findall(shipped))):
                                problems.append('unresolved: <%s> is left in %s' % (n, rel))
                            if limit is not None and len(shipped) > limit:
                                problems.append('too long: %s is %d chars, the limit is %d' % (rel, len(shipped), limit))
    return {'kit': name, 'ok': not problems, 'problems': problems, 'chars': chars, 'limit': limit}
