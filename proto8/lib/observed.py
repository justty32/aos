# observed.py - Record public stack observations and measured downstream calls.
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

import tool_io


def prepare_strict(stack):
    """Initialize the ledger and declaration, returning an open append stream."""
    root = Path(stack)
    root.mkdir(parents=True, exist_ok=True)
    interface = root / 'interfaces.json'
    declarations = json.loads(interface.read_text(encoding='utf-8')) if interface.exists() else {}
    if not isinstance(declarations, dict):
        raise ValueError('interfaces.json must be an object')
    if declarations.get('aos-observed') != {'file': 'observed.jsonl'}:
        declarations['aos-observed'] = {'file': 'observed.jsonl'}
        interface.write_text(json.dumps(declarations, ensure_ascii=False) + '\n', encoding='utf-8')
    stream = (root / 'observed.jsonl').open('a+', encoding='utf-8')
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            record = {'kind': 'self', 'def': os.environ.get('AOS_CD'),
                      'ws': os.environ.get('AOS_WS'),
                      'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')}
            if 'AOS_LLM_KERNEL' in os.environ:
                record['llm_kernel'] = os.environ['AOS_LLM_KERNEL']
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            stream.flush()
        return stream
    except BaseException:
        stream.close()
        raise


def append_strict(stack, record):
    """Append an observation, propagating initialization and write failures."""
    line = json.dumps(record, ensure_ascii=False) + '\n'
    with prepare_strict(stack) as stream:
        stream.write(line)
        stream.flush()


def program(prog=None):
    """Name for warning lines: the given one, else the tool that ran tool_io.start, else agent-fsm."""
    if prog:
        return prog
    return tool_io.NAME if tool_io.NAME != 'tool' else 'agent-fsm'


def append(stack, record, prog=None):
    """Append best effort without changing the caller's result."""
    try:
        append_strict(stack, record)
    except (OSError, ValueError, TypeError) as error:
        tool_io.warn('cannot append to observed.jsonl: %s' % error, prog=program(prog))


def call(name, target, stdin, stack=None, prog=None):
    """Run aos-exec with a tool cell, returning code and raw output bytes."""
    from observed_children import clear_child, take_child

    stack = os.environ.get('AOS_STACK') if stack is None else stack
    target = os.path.abspath(target)
    payload = stdin.encode('utf-8') if isinstance(stdin, str) else stdin
    env = os.environ.copy()
    relative = 'tools/' + name
    if stack:
        child_stack = Path(os.path.abspath(stack)) / relative   # 11-11 tool-cells-lazy: the cell is not made beforehand
        clear_child(child_stack)
        env['AOS_STACK'] = str(child_stack)
    started = time.monotonic_ns()
    result = subprocess.run(['aos-exec'] + (['--stack-lazy'] if stack else []) + [target], input=payload, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)
    if stack:
        record = {'kind': 'tool', 'name': name, 'def': target, 'stack': relative,
                  'code': result.returncode, 'elapsed_ms': (time.monotonic_ns() - started) / 1_000_000,
                  'in_bytes': len(payload), 'out_bytes': len(result.stdout)}
        child = take_child(child_stack)
        if child:
            record['child'] = relative + '/' + child
        append(stack, record, prog)
    return result.returncode, result.stdout, result.stderr
