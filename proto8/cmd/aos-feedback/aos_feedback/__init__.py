"""Parse feedback commands through aos_flags and present records and comfort reports."""
import json
import sys

import aos_flags
from . import storage
from .comfort import score

NAME = 'aos-feedback'
USAGES = {
    'add': 'aos-feedback add COMMAND PAIN [SUGGEST] [--kind KIND] [--score N] [--by WHO] [--model MODEL] [--family FAMILY] [--tier TIER] [--json]',
    'ls': 'aos-feedback ls [--json]',
    'show': 'aos-feedback show KEY [--json]',
    'score': 'aos-feedback score KEY [--observed FILE]... [--json]',
}
USAGE = 'aos-feedback [--json] {add|ls|show|score} ...'
HELP = '''aos-feedback - collect command feedback and report observed AI comfort

usage: aos-feedback [--json] {add|ls|show|score} ...
       aos-feedback SUBCOMMAND --help

commands:
  add COMMAND PAIN [SUGGEST]   append feedback, without changing the target
  ls                           list KEY  COUNT  LATEST, most feedback first
  show KEY                     show every feedback record for a key
  score KEY [--observed FILE]...  print a comfort report as JSON

flags:
  -j, --json    machine-readable output (also accepted after arguments)
  -h, --help    show help

The store is $AOS_FEEDBACK, or proto8/feedback relative to this script.
Model classification uses that store's raters.json, first substring match wins.
Exit codes: 0 printed or recorded; 1 error; 130 interrupted; 141 closed stdout.
'''
HELPS = {
    'add': '''Append one opinion as a JSONL record; command text is stored unchanged.

usage: %s

flags:
  --kind KIND      usage, help, errors, args or other (default: other)
  --score N        finite score from 0 to 1 (1 means comfortable); optional
  --by WHO         author (default: basename of $AOS_CD, else unknown)
  --model MODEL    model name (default: unknown)
  --family FAMILY  free-form family, overriding the matching rater rule
  --tier TIER      free-form tier, overriding the matching rater rule
  -j, --json       print the recorded object instead of the recorded path
  -h, --help       show this help

Options may precede or follow arguments; -- treats all remaining text literally.
The key is the first command word's lowercase basename, with other characters
replaced by underscores. Examples: aos-agent ctl add -> aos-agent; lib/base/read -> read.
''' % USAGES['add'],
    'ls': '''List one row per non-empty key, sorted by count descending, then key.

usage: %s

Text rows: KEY  COUNT  LATEST. --json prints [{key, feedback, latest}, ...].
-h, --help shows this help. -j is short for --json.
''' % USAGES['ls'],
    'show': '''Print all records for a key in append order, one readable line per record.

usage: %s

--json prints an array of the original records; an absent key is an empty array.
-h, --help shows this help. -j is short for --json.
''' % USAGES['show'],
    'score': '''Print observed comfort without writing feedback or metainfo.

usage: %s

--observed FILE may be repeated. Reads tool rows whose name or def basename
matches KEY. Retries are consecutive calls to the same definition after a nonzero
code; other tool calls break the sequence, non-tool rows do not. Files are separate
sequences. Calls with no def use their name as identity.
AI subitems are the mean scored feedback for usage/help/errors/args. The overall
and family/tier values use mean(subitems) * calls/(calls+errors+retries).
Without matching calls, use mean(subitems); without scored subitems, use the
behavior factor alone. Without either, val is null. user is always null.
Output is JSON with or without --json. -j is short for --json; -h shows help.
''' % USAGES['score'],
}


def parse_arguments(argv, command):
    """The action layer of the shared parser: options before or after the arguments (P-44 continued, 11-11)."""
    flags = {('--' + key): key for key in ('kind', 'score', 'by', 'model', 'family', 'tier')} if command == 'add' else {}
    multi = {'--observed': 'observed'} if command == 'score' else {}
    options, arguments = aos_flags.parse(argv, flags, {'--json': 'json'}, multi, help=HELPS[command], short=('-j',))
    if '--' in arguments:   # -- after an argument comes back with the rest; the old parser dropped it
        i = arguments.index('--')
        arguments = arguments[:i] + arguments[i + 1:]
    return options, arguments


def json_output(value):
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))


def readable(row):
    rated = row.get('rater', {})
    fields = [row['at'], row['command'], row['kind'], 'by=' + row['by'],
              'rater=' + '/'.join(rated.get(k, 'unknown') for k in ('model', 'family', 'tier')),
              'pain=' + json.dumps(row['pain'], ensure_ascii=False)]
    if 'suggest' in row:
        fields.append('suggest=' + json.dumps(row['suggest'], ensure_ascii=False))
    if 'score' in row:
        fields.append('score=' + str(row['score']))
    if 'cwd' in row:
        fields.append('cwd=' + str(row['cwd']))
    return '  '.join(' '.join(field.splitlines()) for field in fields)


def main():
    command = None
    try:
        common, rest = aos_flags.parse(sys.argv[1:], {}, {'--json': 'json'},
                                       help=HELP, short=('-j',), sub='root')
        if not rest:
            storage.fail('ArgumentsBad', 'a subcommand is required')
        command = rest[0]
        if command not in USAGES:
            storage.fail('CommandUnknown', 'unknown command %s' % command)
        options, arguments = parse_arguments(rest[1:], command)
        options = dict(common, **options)
        count = len(arguments)
        if command == 'add' and count not in (2, 3):
            storage.fail('ArgumentsBad', 'add needs COMMAND PAIN and optional SUGGEST')
        if command == 'ls' and count:
            storage.fail('ArgumentsBad', 'ls takes no arguments')
        if command in ('show', 'score') and count != 1:
            storage.fail('ArgumentsBad', '%s needs one KEY' % command)
        root = storage.directory()
        if command == 'add':
            path, row = storage.add(root, arguments, options)
            if options.get('json'):
                json_output(row)
            else:
                print('%s: recorded %s' % (NAME, path))
        elif command == 'ls':
            rows = storage.listing(root)
            if options.get('json'):
                json_output(rows)
            else:
                for row in rows:
                    print('%s  %d  %s' % (row['key'], row['feedback'], row['latest']))
        else:
            key = arguments[0]
            rows = storage.records(root, key)
            if command == 'score':
                json_output(score(key, rows, options.get('observed', [])))
            elif options.get('json'):
                json_output(rows)
            else:
                for row in rows:
                    print(readable(row))
    except aos_flags.Error as error:
        usage = USAGES.get(command, USAGE)
        aos_flags.die(NAME, error.code, '%s (usage: %s)' % (error, usage))
    except (OSError, UnicodeError, ValueError) as error:
        aos_flags.die(NAME, 'FileBad', str(error))
