# aos/apps/kit/__init__.py - aos-kit body: parse flags, dispatch ls / make / check / add, print. Recipe logic is in recipe.py, writing a definition in add.py.
import json
import os
import sys

from aos import flags as aos_flags

from . import add as add_mod
from . import recipe
from .recipe import Fail

PROG = 'aos-kit'

HELP = """aos-kit - kits: ready-made system texts and tool sets for one agent role, laid over agent-fsm

usage: aos-kit [--kits DIR] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-kit SUBCOMMAND --help

subcommands:
  ls      list the kits in DIR/kits.json
  make    assemble a kit's system text from its layers (general, site, role)
  check   compare a kit's shipped system text with its assembled layers
  add     lay a kit over an agent-fsm definition folder (system.txt, tools.json)

flags:
  --kits DIR    the kits folder (default: $AOS_HOME/templates/kits)
  -h, --help    show this help
Flags may go anywhere after the name they belong to.

exit codes: 0 ok; 1 error ("aos-kit: error: CODE reason" on stderr).
more: proto8/py/aos/apps/kit/README.md"""

LS_HELP = """aos-kit ls - list the kits

usage: aos-kit ls [--kits DIR] [-j]

One line per kit: NAME TAB ROLE TAB TIERS TAB SYSTEM TAB TOOLS TAB RECIPE (make = has a make block, - = none).
-j / --json gives {"kits_dir", "kits": [{name, role, tiers, system, tools, make}]}."""

MAKE_HELP = """aos-kit make - assemble a kit's system text

usage: aos-kit make KIT [--kits DIR] [--site FILE] [--set KEY=VALUE ...] [-o FILE]

Layers come from the kit's make block in kits.json, in order (general, @site, role); @site is the
--site file, left out when none is given. Placeholders <NAME> are filled per line; the first of these
wins: --set NAME_LINE=TEXT (replaces the whole line), --set NAME=TEXT (in place), the kit's default
NAME_LINE, the kit's default NAME. An empty value drops the line. Known names: KNOWLEDGE, BOARD, OWN_BOARD.
Prints the text on stdout, or writes it to FILE with -o / --output. Warns (does not fail) when a
placeholder is left or the text is over the kit's limit."""

CHECK_HELP = """aos-kit check - check a kit

usage: aos-kit check KIT [--kits DIR] [-j]

Assembles the kit with its defaults (no site) and compares the result with the kit's shipped system
file. Problems: missing files, stale (the shipped file differs), unresolved <NAME> placeholders, length
over the kit's limit, a tools file that is not JSON. Prints "ok ..." and exits 0 when clean; else one
line per problem, then the error line CheckFailed (exit 1). -j = one JSON object {kit, ok, problems, chars, limit}."""

ADD_HELP = """aos-kit add - lay a kit over an agent-fsm definition

usage: aos-kit add KIT DEF [--kits DIR] [--site FILE] [--set KEY=VALUE ...] [--force]

Writes DEF/system.txt (assembled as in make) and DEF/tools.json (copied from the kit). DEF must hold an
interfaces.json (else DefMissing). A system.txt or tools.json already in DEF must be the stock one of
$AOS_HOME/templates/agent-fsm, else it is refused (FileChanged; StockMissing when there is nothing to
compare with) unless --force. Each file that is replaced is first saved as FILE.before-kit (.before-kit.2,
.3 ... when taken; nothing is deleted). Checks both files before writing either. hooks.json and llm.json
are not touched: set the brain in llm.json yourself."""


def parse(argv, name, help_text, flags=None, switches=None, multi=None, short=None):
    try:
        return aos_flags.parse(argv, flags or {}, switches or {}, multi or {}, help=help_text, short=short)
    except aos_flags.Error as e:
        raise Fail(e.code, '%s (see aos-kit %s --help)' % (e, name))


ROOT = [{}]                                     # [opts of the top level]; aos_flags writes --kits given after the subcommand into it


def kits_dir():
    return ROOT[0].get('kits') or recipe.default_kits_dir()


def one_kit(rest, name, usage, count=1):
    if len(rest) != count:
        raise Fail('ArgumentsBad', '%s takes %s (usage: %s)' % (name, 'KIT' if count == 1 else 'KIT DEF', usage))
    return rest


def out(text):
    sys.stdout.buffer.write(text.encode('utf-8'))
    sys.stdout.flush()


def cmd_ls(argv):
    opts, rest = parse(argv, 'ls', LS_HELP, switches={'--json': 'json'}, short={'-j': '--json'})
    if rest:
        raise Fail('ArgumentsBad', 'ls takes no arguments (usage: aos-kit ls [--kits DIR] [-j])')
    d = kits_dir()
    data = recipe.load_kits(d)
    rows = []
    for name, kit in data['kits'].items():
        kit = kit if isinstance(kit, dict) else {}
        tiers = kit.get('tiers') if isinstance(kit.get('tiers'), list) else []
        rows.append({'name': name, 'role': kit.get('role'), 'tiers': tiers, 'system': kit.get('system'),
                     'tools': kit.get('tools'), 'make': isinstance(kit.get('make'), dict)})
    if opts.get('json'):
        out(json.dumps({'kits_dir': d, 'kits': rows}, ensure_ascii=False) + '\n')
        return 0
    for r in rows:
        out('\t'.join([r['name'], str(r['role'] or '-'), ','.join(map(str, r['tiers'])) or '-',
                       str(r['system'] or '-'), str(r['tools'] or '-'), 'make' if r['make'] else '-']) + '\n')
    return 0


def build(kit_name, opts):
    """Assemble for make and add; warn about what is left."""
    d = kits_dir()
    data = recipe.load_kits(d)
    kit = recipe.get_kit(data, kit_name, d)
    make = recipe.get_make(kit, kit_name)
    sets = recipe.parse_sets(opts.get('set'))
    built = recipe.assemble(d, make, site=opts.get('site'), sets=sets)
    for n in built['unresolved']:
        aos_flags.warn(PROG, 'placeholder <%s> is left in the text (give --set %s=... or --set %s_LINE=...)' % (n, n, n))
    if make['limit'] is not None and len(built['text']) > make['limit']:
        aos_flags.warn(PROG, 'the text is %d chars, over the limit %d of kit %s' % (len(built['text']), make['limit'], kit_name))
    for k in built['unused_sets']:
        aos_flags.warn(PROG, '--set %s is not used by any layer' % k)
    return d, kit, built


MAKE_FLAGS = {'--site': 'site', '--output': 'output'}


def cmd_make(argv):
    opts, rest = parse(argv, 'make', MAKE_HELP, flags=MAKE_FLAGS, multi={'--set': 'set'}, short={'-o': '--output'})
    (name,) = one_kit(rest, 'make', 'aos-kit make KIT [--site FILE] [--set KEY=VALUE ...] [-o FILE]')
    _, _, built = build(name, opts)
    if opts.get('output'):
        add_mod.write_over(opts['output'], built['text'].encode('utf-8'))
        print('wrote %s (%d chars, layers: %s)' % (opts['output'], len(built['text']), ' + '.join(built['layers'])))
    else:
        out(built['text'])
    return 0


def cmd_check(argv):
    opts, rest = parse(argv, 'check', CHECK_HELP, switches={'--json': 'json'}, short={'-j': '--json'})
    (name,) = one_kit(rest, 'check', 'aos-kit check KIT [--kits DIR] [-j]')
    d = kits_dir()
    res = recipe.check(d, recipe.load_kits(d), name)
    if opts.get('json'):
        out(json.dumps(res, ensure_ascii=False) + '\n')
    elif res['ok']:
        lim = ', limit %d' % res['limit'] if res['limit'] is not None else ', no limit'
        out('ok %s (%d chars%s)\n' % (name, res['chars'], lim))
    else:
        for p in res['problems']:
            out('%s: %s\n' % (name, p))
    if not res['ok']:
        n = len(res['problems'])
        raise Fail('CheckFailed', '%d problem%s in kit %s' % (n, '' if n == 1 else 's', name))
    return 0


def cmd_add(argv):
    opts, rest = parse(argv, 'add', ADD_HELP, flags={'--site': 'site'}, switches={'--force': 'force'},
                       multi={'--set': 'set'})
    name, defdir = one_kit(rest, 'add', 'aos-kit add KIT DEF [--site FILE] [--set KEY=VALUE ...] [--force]', 2)
    d, kit, built = build(name, opts)
    tools_rel = kit.get('tools')
    if not isinstance(tools_rel, str) or not tools_rel:
        raise Fail('KitsBad', 'kit %s has no "tools" file in kits.json' % name)
    new = {'system.txt': built['text'].encode('utf-8'),
           'tools.json': add_mod.read_bytes(os.path.join(d, tools_rel))}
    steps = add_mod.plan(defdir, new, force=bool(opts.get('force')), stock=add_mod.stock_dir())
    for line in add_mod.apply(defdir, new, steps):
        print(line)
    print('kit %s: system.txt from %s; tools.json from %s' % (name, ' + '.join(built['layers']), tools_rel))
    print('not touched: hooks.json, llm.json (set the brain in llm.json yourself, then run agent_def check)')
    return 0


SUBS = {'ls': cmd_ls, 'make': cmd_make, 'check': cmd_check, 'add': cmd_add}


def main():
    aos_flags.HELP = HELP
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {'--kits': 'kits'}, help=HELP, sub='root')
        ROOT[0] = opts
        if not rest:
            raise Fail('ArgumentsBad', 'missing subcommand (%s; see aos-kit --help)' % ', '.join(SUBS))
        if rest[0] not in SUBS:
            raise Fail('CommandUnknown', 'unknown subcommand %s (%s; see aos-kit --help)' % (rest[0], ', '.join(SUBS)))
        code = SUBS[rest[0]](rest[1:])
    except aos_flags.Error as e:
        aos_flags.die(PROG, e.code, e)
    except Fail as e:
        aos_flags.die(PROG, e.code, e)
    sys.exit(code or 0)
