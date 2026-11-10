"""Inspect public definition declarations and group agents by tools, endpoint and knowledge."""
import json
import os
from pathlib import Path
import re
import subprocess

from tool_io import Error


def read(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('%s must contain an object' % path)
    return value


def definitions(root):
    """Stop at definition boundaries and never enter hidden trees."""
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        if 'interfaces.json' in files or '_metainfo.json' in files:
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


AOS_TOOLS = Path(__file__).resolve().parents[3] / 'cmd' / 'aos-tools' / 'bin' / 'aos-tools'


def stacked(table):
    """tools.json 疊了 "$override"（11-10 tool-packs，範本疊 lib/packs）：交給 aos-tools ls -l 合併，取每格寫的 path 原樣（STORED 欄）。
    合併規則只在 aos-tools 一處；沒設 AOS_HOME 時用這份 proto8（底檔多半寫 {"$env": "AOS_HOME", …}）。"""
    env = dict(os.environ)
    env.setdefault('AOS_HOME', str(AOS_TOOLS.parents[3]))
    try:
        r = subprocess.run([str(AOS_TOOLS), '--file', str(table), 'ls', '-l'], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, env=env, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ValueError('cannot merge %s with aos-tools: %s' % (table, e))
    if r.returncode:
        raise ValueError(' '.join((r.stderr or r.stdout).strip().splitlines()[-1:]) or 'aos-tools ls failed')
    entries = {}
    for line in r.stdout.splitlines():
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
    if 'lineage' in meta:
        row['lineage'] = meta['lineage']
    if agent is None:
        return row
    entries = tools(path, agent)
    llm_file = agent.get('llm')
    if not isinstance(llm_file, str) or not llm_file:
        raise ValueError('aos-agent.llm must name a file')
    # llm.json 的 model＝kernel 的 endpoint 包代號（11-10 晚 fsm 的鍵 endpoint 改名 model）；這裡的分組欄照舊叫 endpoint
    endpoint = read(path / llm_file).get('model', 'default')
    if not isinstance(endpoint, str):
        raise ValueError('model in llm.json must be a string')
    knowledge = None
    if agent.get('knowledge') is not None:
        filename = agent['knowledge']
        if not isinstance(filename, str) or not filename:
            raise ValueError('aos-agent.knowledge must name a file')
        knowledge_file = path / filename
        knowledge = read(knowledge_file).get('base')
        if isinstance(knowledge, str):
            knowledge = relative(knowledge_file.parent / knowledge, root)
        elif knowledge is not None and not isinstance(knowledge, dict):
            raise ValueError('knowledge base must be a path or environment object')
    table_dir = (path / agent['tools']).parent
    row.update(tools=sorted({tool_key(table_dir, t['path'], root) for t in entries.values()}),
               endpoint=endpoint, knowledge=knowledge)
    return row


def signature(row):
    return json.dumps({k: row[k] for k in ('tools', 'endpoint', 'knowledge')},
                      sort_keys=True, separators=(',', ':'))


def check(path, root):
    problems = []
    def problem(reason):
        problems.append({'path': relative(path, root), 'reason': reason})
    if any(not re.fullmatch('[a-z0-9_-]+', part) for part in path.relative_to(root).parts):
        problem('definition path segments must match [a-z0-9_-]+')
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
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        problem(str(error))
    return problems


def run(args):
    root = Path(args['root']).resolve()
    if not root.is_dir():
        raise Error('RootMissing', 'definition root is not a directory: %s' % root)
    paths = list(definitions(root))
    op = args['op']
    if op == 'check':
        return {'problems': [p for path in paths for p in check(path, root)]}
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
                thought = entry.get('env', {}).get('AOS_THOUGHT_FROM')
                thought_path = None
                if isinstance(thought, str) and thought:
                    candidate = Path(thought)
                    if candidate.is_absolute():
                        thought_path = candidate.resolve()
                    elif os.environ.get('AOS_WS'):
                        thought_path = (Path(os.environ['AOS_WS']) / candidate).resolve()
                if source == target or thought_path == target:
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
