#!/usr/bin/env python3
"""Provide commands to validate, render, parse, apply, and land decision batches."""
import json
import os
from pathlib import Path
import sys

from model import Error, load
import reply

USAGE = 'decide_page.py <check|build|parse|apply|land> DATA [options]'
HELP = '''Usage: decide_page.py <command> DATA [options]

Commands:
  check DATA                       Validate the question data.
  build DATA [--out PATH]           Write an offline HTML page.
  parse DATA REPLY_FILE|-           Print parsed answers as JSON lines.
  apply DATA REPLY_FILE|-           Save parsed answers into DATA.
  land DATA                        Print source-grouped landing markdown.

Reply input alternatives for parse and apply:
  --text STR                       Read literal reply text.
  --from-board ASK_ID               Read the last matching board comment.

Options:
  --help                           Show this help and exit.
'''


def fail(code, reason):
    raise Error(code, reason)


def read_reply(args):
    if len(args) == 1 and args[0] == '-':
        return sys.stdin.read()
    if len(args) == 1 and not args[0].startswith('-'):
        return Path(args[0]).expanduser().read_text(encoding='utf-8')
    if len(args) != 2 or args[0] not in ('--text', '--from-board'):
        fail('ArgumentsBad', 'provide one reply file, -, --text STR, or --from-board ASK_ID')
    if args[0] == '--text':
        return args[1]
    directory = Path(os.environ.get('AOS_PROGRESS_DIR', '~/Desktop/aos-進度')).expanduser()
    path = directory / 'data/answers.jsonl'
    found = None
    if path.exists():
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                fail('JsonBad', f'board answer record {number} is invalid JSON')
            if not isinstance(record, dict):
                fail('FieldBad', f'board answer record {number} must be an object')
            if record.get('id') == args[1]:
                found = record.get('comment')
    if found is None:
        fail('AnswerMissing', f'no board answer found for {args[1]}')
    if not isinstance(found, str):
        fail('FieldBad', f'board answer {args[1]}.comment must be a string')
    return found


def main(args):
    if args and args[0] in ('--help', '-h'):
        print(HELP, end='')
        return 0
    if not args:
        fail('ArgumentsBad', 'a command and DATA are required')
    command = args[0]
    if command.startswith('-'):
        fail('FlagUnknown', f'unknown flag {command}')
    if command not in ('check', 'build', 'parse', 'apply', 'land'):
        fail('CommandUnknown', f'unknown command {command}')
    allowed = {'build': {'--out'}, 'parse': {'--text', '--from-board'},
               'apply': {'--text', '--from-board'}}.get(command, set())
    if '--help' in args[1:] or '-h' in args[1:]:
        print(HELP, end='')
        return 0
    index = 1
    while index < len(args):
        item = args[index]
        if item.startswith('-') and item != '-':
            if item not in allowed:
                fail('FlagUnknown', f'unknown flag {item}')
            index += 2
        else:
            index += 1
    if len(args) < 2 or args[1].startswith('-'):
        fail('ArgumentsBad', 'DATA is required before command options')
    path = Path(args[1]).expanduser()
    rest = args[2:]
    if command in ('check', 'land') and rest:
        fail('ArgumentsBad', f'{command} accepts only DATA')
    if command == 'build' and rest and (len(rest) != 2 or rest[0] != '--out'):
        fail('ArgumentsBad', 'build accepts DATA and optional --out PATH')
    data = load(path)
    if command == 'check':
        print(f'decide_page: ok {len(data["rows"])} questions in {len(data["sections"])} sections')
    elif command == 'build':
        from render import render
        out = Path(rest[1]).expanduser() if rest else Path.home() / 'Desktop' / f'aos-{data["batch"]}-待你裁.html'
        out.write_text(render(data, path), encoding='utf-8')
        print(f'decide_page: wrote {out}')
    elif command in ('parse', 'apply'):
        answers = reply.parse(data, read_reply(rest))
        if command == 'parse':
            for answer in answers:
                print(json.dumps(answer, ensure_ascii=False))
        else:
            print(reply.apply(data, path, answers))
    else:
        print(reply.land(data, path))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Error as exc:
        print(f'decide_page: error: {exc.code} {exc.reason} (usage: {USAGE})', file=sys.stderr)
        sys.exit(1)
    except (OSError, UnicodeError) as exc:
        code = 'FileMissing' if isinstance(exc, FileNotFoundError) else 'FileBad'
        print(f'decide_page: error: {code} {exc} (usage: {USAGE})', file=sys.stderr)
        sys.exit(1)
