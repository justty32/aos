# Summarize declared shell accounts and effective arbitrary execution tools.
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from agent.agent_files import declared_files


def records(stack):
    interface = stack / 'interfaces.json'
    if not interface.exists():
        return []
    declaration = json.loads(interface.read_text()).get('aos-observed', {})
    filename = declaration.get('file') if isinstance(declaration, dict) else None
    if not filename:
        return []
    rows = [json.loads(line) for line in (stack / filename).read_text().splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError('observation records must be objects')
    return rows


def command_shapes(command):
    """Return independent shell segment shapes and resolved executable paths."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segments, segment = [], []
    for token in lexer:
        if token in ('|', '&&', '||', ';'):
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(token)
    if segment:
        segments.append(segment)
    result = []
    for tokens in segments:
        shape, executable, i = [], None, 0
        while i < len(tokens):
            token = tokens[i]
            # A descriptor prefix belongs to the redirection, not its arguments.
            if token.isdecimal() and i + 1 < len(tokens) and any(c in tokens[i + 1] for c in '<>'):
                i += 1
                token = tokens[i]
            if token and all(c in '<>&|' for c in token) and any(c in token for c in '<>'):
                shape.append('<redir>')
                i += 2
                continue
            if executable is None:
                executable = token
                shape.append(token)
            else:
                shape.append(token if token.startswith('-') else '<arg>')
            i += 1
        if executable is not None:
            binary = shutil.which(executable)
            result.append((' '.join(shape), str(Path(binary).resolve()) if binary else None))
    return result


def effective_stage(definition, stack):
    """Ask the registry reader to merge declared tools and stack overrides."""
    relative = declared_files(definition).get('tools')
    if not relative:
        return 'none', []
    own = stack / relative                    # the agent's own registry "$override"s the definition's (aos-tools merges)
    args = ['aos-tools', '--file', str(own if own.is_file() else definition / relative)]
    result = subprocess.run(args + ['ls', '--json'], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('cannot list effective tools for %s (exit %d)' % (definition, result.returncode))
    tools = json.loads(result.stdout)
    arbitrary = [tool for tool in tools if tool.get('metainfo', {}).get('arbitrary_exec') is True]
    stage = ('open' if any('sandbox' not in tool['metainfo'] for tool in arbitrary)
             else 'boxed' if arbitrary else 'none')
    return stage, sorted(tool['name'] for tool in arbitrary)


def report(stacks, defs=None):
    """Aggregate per definition, following only public tool and child references."""
    reports, visited = {}, set()
    base = Path(defs).resolve() if defs else None

    def definition_path(value):
        path = Path(value)
        if not path.is_absolute():
            if base is None:
                raise ValueError('relative self.def requires defs')
            path = base / path
        return path.resolve()

    def walk(stack, case, owner=None, agent_root=False):
        stack = stack.resolve()
        if stack in visited:
            return
        visited.add(stack)
        rows = records(stack)
        own = next((row for row in rows if row.get('kind') == 'self'), {})
        if own.get('def') and (agent_root or owner is None):
            owner = str(definition_path(own['def']))
            stage, arbitrary = effective_stage(Path(owner), stack)
            current = reports.setdefault(owner, {'agent': owner, 'shell_stage': stage,
                                                 'arbitrary': [], 'binaries': set(), 'shapes': {}})
            rank = {'none': 0, 'boxed': 1, 'open': 2}
            if rank[stage] > rank[current['shell_stage']]:
                current['shell_stage'] = stage
            current['arbitrary'] = sorted(set(current['arbitrary']) | set(arbitrary))
        for row in rows:
            if row.get('kind') == 'cmd' and owner is not None:
                current = reports[owner]
                for shape, binary in command_shapes(row['command']):
                    if binary:
                        current['binaries'].add(binary)
                    item = current['shapes'].setdefault(shape, {'shape': shape, 'count': 0, 'exit_zero': 0, 'cases': set()})
                    item['count'] += 1
                    item['exit_zero'] += row.get('exit') == 0
                    item['cases'].add(case)
            elif row.get('kind') == 'tool':
                if row.get('stack'):
                    walk(stack / row['stack'], case, owner)
                if row.get('child'):
                    walk(stack / row['child'], case, owner, agent_root=True)

    for value in stacks:
        stack = Path(value)
        if not stack.is_absolute() or not stack.is_dir():
            raise ValueError('stacks must name existing absolute directories')
        case = str(stack)
        walk(stack, case, agent_root=True)
    result = []
    for owner in sorted(reports):
        item = reports[owner]
        item['binaries'] = sorted(item['binaries'])
        item['shapes'] = [dict(shape, cases=sorted(shape['cases'])) for _, shape in sorted(item['shapes'].items())]
        result.append(item)
    return {'reports': result}
