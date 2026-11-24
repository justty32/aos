"""Inspect public definition declarations and group agents by tools and endpoint."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from aos.tool_io import Error


def read(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('%s must contain an object' % path)
    return value


VIEW_KEYS = {'index', 'tooldef'}   # N-69 11-12: the only notes about a node that may sit in _metainfo


def marks_definition(base, files):
    """interfaces.json, or _metainfo.json - unless nothing beside it runs (no _entry) and that _metainfo.json is a
    non-empty object holding only index/tooldef: such a folder is a plain folder with notes, not a definition (thinking
    11-12 metainfo M11). {} still marks one (user 11-12: "只有{}的_metainfo.json也算agent定義"), so does any other key;
    an unreadable or non-object _metainfo.json still marks one, so check reports it."""
    if 'interfaces.json' in files:
        return True
    if '_metainfo.json' not in files:
        return False
    if '_entry' in files or '_entry.json' in files:
        return True
    try:
        meta = json.loads(Path(base, '_metainfo.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return True
    return not (isinstance(meta, dict) and meta and set(meta) <= VIEW_KEYS)


def definitions(root):
    """Stop at definition boundaries and never enter hidden trees."""
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        if marks_definition(base, files):
            yield Path(base)
            dirs[:] = []


def relative(path, root):
    return os.path.relpath(path.resolve(), root).replace(os.sep, '/')


def declared(path):
    if not (path / 'interfaces.json').exists():
        return None
    interfaces = read(path / 'interfaces.json')
    agent = interfaces.get('aos-agent')
    if agent is not None and not isinstance(agent, dict):
        raise ValueError('aos-agent must be an object')
    return agent


def tools(path, agent):
    if agent is None:
        return {}
    filename = agent.get('tools')
    if not isinstance(filename, str) or not filename:
        raise ValueError('aos-agent.tools must name a file')
    table = read(path / filename)
    if '$override' in table:
        return stacked(path / filename)
    entries = table.get('tools')
    if not isinstance(entries, dict):
        raise ValueError('tools must contain an object')
    for entry in entries.values():
        if not isinstance(entry, dict) or not (isinstance(entry.get('path'), str) and entry['path']
                                               or is_directive(entry.get('path'))):
            raise ValueError('each tool must declare a path')
        if not isinstance(entry.get('env', {}), dict):
            raise ValueError('tool env must be an object')
    return entries


HOME_OF_LIB = Path(__file__).resolve().parents[4]   # 放這份 lib/ 的資料夾：proto8，或抄出去的樹（沒有 cmd/）


class Unresolved(ValueError):
    """A {"$env": NAME} the definition names is not set where check runs: what it points at is only known where the agent runs.
    check reports it as a warning, not a problem (11-19 aos-check-refs: 解不了的環境變數照實說而不是誤報)."""
    def __init__(self, what, name):
        super().__init__('%s not checked: environment variable %s is not set here (it is read when the agent runs)' % (what, name))
        self.name = name


UNSET_RE = re.compile(r'environment variable (\S+) is not set')
# 11-24 起 aos-tools 讀到疊進來的 pack 壞了＝只跳過那份、退 0、stderr 一行這個（a551bba03）；check 照舊要說出來
PACK_SKIPPED_RE = re.compile(r'aos-tools: warning: (pack \S+(?: \(from \S+\))? skipped \((\w+) .*?\)); its tools are left out')


def run_env():
    """The environment check resolves things in: the caller's, AOS_HOME defaulting to the folder holding this lib (tool-packs);
    no AOS_STACK, so aos-tools keeps no tooldef cache anywhere (check only reads)."""
    env = dict(os.environ)
    env.setdefault('AOS_HOME', str(HOME_OF_LIB))
    env.pop('AOS_STACK', None)
    env.pop('AOS_STACK_IN_CALLER', None)
    return env


_listed = {}


def tools_ls(table):
    """aos-tools --file TABLE ls -l, the same reader the agent uses when it runs (merges $override, resolves paths, marks
    broken tools); once per table per run. Returns (stdout, stderr). aos-tools from PATH (lib may be copied to a tree without cmd/)."""
    key = str(table)
    if key in _listed:
        return _listed[key]
    tools = shutil.which('aos-tools')
    if not tools:
        raise ValueError('cannot merge %s: aos-tools is not on PATH (source $AOS_HOME/env.sh)' % table)
    try:
        r = subprocess.run([tools, '--file', str(table), 'ls', '-l'], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, env=run_env(), timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ValueError('cannot merge %s with aos-tools: %s' % (table, e))
    skipped = PACK_SKIPPED_RE.search(r.stderr or '')
    if r.returncode or skipped:              # 跑起來時壞的 pack 只少那份工具；check 照舊當成要報的（變數沒設＝warning，其他＝problem）
        unset = UNSET_RE.search(r.stderr or '')
        if unset:
            raise Unresolved('tool paths in %s' % Path(table).name, unset.group(1))
        if skipped:
            raise ValueError('%s (when the agent runs, the tools of that pack are left out)' % skipped.group(1))
        raise ValueError(' '.join((r.stderr or r.stdout).strip().splitlines()[-1:]) or 'aos-tools ls failed')
    _listed[key] = (r.stdout, r.stderr)
    return _listed[key]


def stacked(table):
    """tools.json 疊了 "$override"（11-10 tool-packs，範本疊 py/packs）：交給 aos-tools ls -l 合併，取每格寫的 path 原樣（STORED 欄）。
    合併規則只在 aos-tools 一處；aos-tools 從 PATH 找（同 def_edit、cli_mcp：lib 可以被抄到沒有 cmd/ 的樹）；
    沒設 AOS_HOME 時用放這份 lib 的資料夾（底檔多半寫 {"$env": "AOS_HOME", …}）。指示詞的變數沒設＝Unresolved。"""
    stdout, _ = tools_ls(table)
    entries = {}
    for line in stdout.splitlines():
        cols = line.split('\t')
        if len(cols) < 5 or cols[1] == 'null':
            continue
        entries[cols[0]] = {'path': json.loads(cols[4])}
    return entries


def is_directive(value):
    """{"$env": NAME, "$path": ...}: a tool path written for each machine's own value; kept as written, never resolved here."""
    return isinstance(value, dict) and isinstance(value.get('$env'), str) and bool(value['$env'])


def tool_key(table_dir, tool_path, root):
    """How a tool path shows in ls/dup: a relative string from the root, or the directive itself as compact JSON."""
    if is_directive(tool_path):
        return json.dumps(tool_path, sort_keys=True, separators=(',', ':'))
    return relative(table_dir / tool_path, root)


def describe(path, root):
    meta = read(path / '_metainfo.json') if (path / '_metainfo.json').exists() else {}
    agent = declared(path)
    row = {'path': relative(path, root), 'summary': meta.get('summary', ''), 'brain': agent is not None}
    if agent is None:
        return row
    entries = tools(path, agent)
    system_file = agent.get('system')            # 11-11 self-system：定義裡的相對檔名；檔可以不在（＝空文字）
    if system_file is not None and (not isinstance(system_file, str) or not system_file or os.path.isabs(system_file)
                                    or '..' in system_file.split('/') or (path / system_file).is_dir()):
        raise ValueError('aos-agent.system must name a text file by a relative path inside the definition')
    llm_file = agent.get('llm')
    if not isinstance(llm_file, str) or not llm_file:
        raise ValueError('aos-agent.llm must name a file')
    # llm.json 的 model＝kernel 的 endpoint 包代號（11-10 晚 fsm 的鍵 endpoint 改名 model）；這裡的分組欄照舊叫 endpoint
    endpoint = read(path / llm_file).get('model', 'default')
    if not isinstance(endpoint, str):
        raise ValueError('model in llm.json must be a string')
    table_dir = (path / agent['tools']).parent
    row.update(tools=sorted({tool_key(table_dir, t['path'], root) for t in entries.values()}),
               endpoint=endpoint)
    return row


def signature(row):
    return json.dumps({k: row[k] for k in ('tools', 'endpoint')},
                      sort_keys=True, separators=(',', ':'))


def check(path, root):
    """Returns (problems, warnings): problems make check fail; warnings are what could not be checked here."""
    problems, warnings = [], []
    def problem(reason):
        problems.append({'path': relative(path, root), 'reason': reason})
    def warn(reason):
        warnings.append({'path': relative(path, root), 'reason': reason})
    parts = path.relative_to(root).parts
    if not parts:                                # root 本身就是定義（agent_def check 一份）：它自己的名字照查（11-12 Q10）
        if not re.fullmatch('[a-z0-9_-]+', path.name):
            problem('definition folder name %r must match [a-z0-9_-]+' % path.name)
    elif any(not re.fullmatch('[a-z0-9_-]+', part) for part in parts):
        problem('definition path segments must match [a-z0-9_-]+')
    import links_check                           # 11-20 第 4 刀：斷掉的連結先判、一個只報一條（同夾，同 refs_check）
    if links_check.check(path, problem):
        return problems, warnings
    try:
        first = (path / 'README.md').read_text(encoding='utf-8').splitlines()
        if not first or not first[0].strip():
            problem('README.md first line must be nonempty')
    except (OSError, UnicodeError) as error:
        problem(str(error))
    try:
        meta = read(path / '_metainfo.json')
        if not isinstance(meta.get('summary'), str) or not meta['summary'].strip():
            problem('_metainfo.json must contain a nonempty summary')
    except (OSError, ValueError, UnicodeError) as error:
        problem(str(error))
    try:
        read(path / 'interfaces.json')
        describe(path, root)
    except Unresolved as error:
        warn(str(error))
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        problem(str(error))
    try:
        agent = declared(path)
    except (OSError, ValueError, TypeError, UnicodeError):
        agent = None                             # already reported above
    if isinstance(agent, dict):                  # 11-19 aos-check-refs（使用者選「只放進檢查指令」）：叫的東西在不在、腦設定的型別
        import refs_check                        # 同夾（_entry 把本夾放在 sys.path 最前面）；用到才載
        refs_check.check(path, agent, problem, warn)
    return problems, warnings


def run(args):
    root = Path(args['root']).resolve()
    if not root.is_dir():
        raise Error('RootMissing', 'definition root is not a directory: %s' % root)
    paths = list(definitions(root))
    op = args['op']
    if op == 'check':
        problems, warnings = [], []
        for path in paths:
            p, w = check(path, root)
            problems += p
            warnings += w
        return dict({'problems': problems}, **({'warnings': warnings} if warnings else {}))
    if op == 'refs':
        target = args.get('def')
        if not isinstance(target, str) or not target:
            raise Error('ArgumentsBad', 'refs requires def')
        target = (root / target).resolve()
        if not target.is_dir():
            raise Error('DefBad', 'reference target is not a directory')
        refs = []
        for path in paths:
            if path.resolve() == target:
                continue
            agent = declared(path)
            for entry in tools(path, agent).values():
                if is_directive(entry['path']):        # written for each machine's own value: not a path into this root
                    continue
                source = ((path / agent['tools']).parent / entry['path']).resolve()
                if source == target:
                    refs.append(relative(path, root))
                    break
        return {'refs': sorted(set(refs))}
    if op not in ('ls', 'dup'):
        raise Error('CommandUnknown', 'unknown operation: %s' % op)
    rows = [describe(path, root) for path in paths]
    if op == 'ls':
        match = args.get('match', '').casefold()
        return {'defs': [r for r in rows if match in (r['path'] + '\n' + r['summary']).casefold()]}
    groups = {}
    for row in rows:
        if row['brain']:
            groups.setdefault(signature(row), []).append(row['path'])
    return {'groups': [{'key': key, 'members': sorted(members)} for key, members in sorted(groups.items()) if len(members) >= 2]}
