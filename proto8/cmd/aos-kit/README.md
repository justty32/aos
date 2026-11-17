# aos-kit

`aos-kit` works with kits (see `templates/kits/README.md`): ready-made system texts and tool sets for one agent role, laid over the agent-fsm template. It lists the kits, assembles a kit's system text from its layers, checks that the shipped text is up to date, and lays a kit over an agent definition folder.

```
aos-kit [--kits DIR] ls [-j]
aos-kit [--kits DIR] make KIT [--site FILE] [--set KEY=VALUE ...] [-o FILE]
aos-kit [--kits DIR] check KIT [-j]
aos-kit [--kits DIR] add KIT DEF [--site FILE] [--set KEY=VALUE ...] [--force]
```

Examples:

```sh
aos-kit ls
aos-kit make gather --site my-site.txt --set KNOWLEDGE=/srv/aos/knowledge -o /tmp/gather.txt
aos-kit check gather
aos-kit add gather defs/gather            # after agent_def new from the agent-fsm template
```

`--kits DIR` is the kits folder (default `$AOS_HOME/templates/kits`); it may go before or after the subcommand.

## The recipe: a make block in kits.json

Each kit that `make`, `check` and `add` work with has a `make` block in its entry of `kits.json`:

```json
"make": {
 "layers": ["general.A.txt", "@site", "roles/gather.txt"],
 "defaults": {"KNOWLEDGE_LINE": "2. Read ...", "BOARD_LINE": "BOARD: ...", "OWN_BOARD_LINE": "OWN BOARD: ..."},
 "limit": 3000
}
```

- `layers`: files relative to the kits folder, in order. `@site` is the `--site` file; with no `--site` it is left out.
- Joining: every layer but the last loses its trailing newlines; layers are joined by one blank line; the last layer is kept as it is (so the text ends the way the role file ends). An empty layer is skipped.
- `defaults`: values for placeholders, by name (A-Z, 0-9, `_`).
- `limit`: the most characters the text may have (optional).

A kit without a `make` block can be listed but not made, checked or added (`MakeMissing`).

## Placeholders

A placeholder is `<NAME>` (capital letters, digits, `_`). The layers use `<KNOWLEDGE>`, `<BOARD>` and `<OWN_BOARD>`. Each line is filled on its own; for a placeholder on a line the first of these wins:

1. `--set NAME_LINE=TEXT`: the whole line becomes TEXT.
2. `--set NAME=TEXT`: the placeholder is replaced in place.
3. the kit's default `NAME_LINE`: the whole line.
4. the kit's default `NAME`: in place.

An empty value drops the line (`--set BOARD_LINE=` leaves the BOARD line out; `--set OWN_BOARD=` drops the `<OWN_BOARD>` line). When a line has several placeholders and one of them takes a whole-line value, the first such one replaces the line. Values are not scanned again for placeholders.

The shipped `gather/system.txt` and `review/system.txt` are the whole-line defaults: step 2 of START, the BOARD line and the OWN BOARD line. With no `--site` and no `--set`, `aos-kit make gather` gives the shipped file byte for byte (the tests check this).

## Commands

- **ls**: one line per kit, `NAME TAB ROLE TAB TIERS TAB SYSTEM TAB TOOLS TAB RECIPE` (RECIPE is `make` when the kit has a make block, else `-`). `-j` gives `{"kits_dir", "kits": [{name, role, tiers, system, tools, make}]}`.
- **make**: prints the assembled text on stdout (exact bytes, no newline added), or writes it to `-o FILE` (temporary file, then rename) and prints one line. Warnings on stderr (exit stays 0): a placeholder is left, the text is over the limit, a `--set` key no layer uses.
- **check**: assembles with the kit's defaults and no site, then reports, one line per problem: a missing file (system, tools, a layer), `stale` (the shipped system file differs; the line of the first difference is given), `unresolved` placeholders (in the assembled text, and in the shipped file when it is stale), `too long` (over the limit), a tools file that is not JSON. Clean = `ok KIT (N chars, limit L)` and exit 0; else the problem lines on stdout and the error line `CheckFailed`. `-j` gives `{kit, ok, problems, chars, limit}`.
- **add**: lays the kit over an agent-fsm definition folder DEF:
  - DEF must be a folder with `interfaces.json`, else `DefMissing`.
  - Writes `DEF/system.txt` (assembled as in make, with `--site` and `--set`) and `DEF/tools.json` (a copy of the kit's tools file).
  - A `system.txt` or `tools.json` already in DEF must be the stock file of `$AOS_HOME/templates/agent-fsm`; otherwise it is refused with `FileChanged` (or `StockMissing` when there is no stock file to compare with, e.g. AOS_HOME not set), unless `--force`. A file that already has the kit's content is left as it is (`unchanged`).
  - Both files are checked before either is written. Each file that is replaced is first saved as `FILE.before-kit`; when that name is taken, `FILE.before-kit.2`, `.3` and so on. Nothing is deleted.
  - Prints one line per file saved or written, then which layers and tools file were used.
  - This version does not touch `hooks.json` or `llm.json`: set the brain in `llm.json` yourself, then run `agent_def check`.

## Output and errors

Output is English. Errors are one line on stderr, `aos-kit: error: CODE reason`, exit 1; warnings are `aos-kit: warning: sentence`. Codes: `ArgumentsBad`, `FlagUnknown`, `CommandUnknown`, `KitsMissing` (no kits folder or kits.json, or no `--kits` and no AOS_HOME), `KitsBad`, `JsonBad`, `KitUnknown`, `MakeMissing`, `RecipeBad`, `FileMissing`, `ReadFailed`, `WriteFailed`, `CheckFailed`, `DefMissing`, `FileChanged`, `StockMissing`.

## Layout and tests

- `bin/aos-kit`: thin launcher; finds `lib/aos_flags.py` via `../../../lib` (the same home's `lib/`).
- `aos_kit/__init__.py`: flags, dispatch, printing. `aos_kit/recipe.py`: kits.json, make block, assembling, check. `aos_kit/add.py`: laying a kit over a definition.
- Python 3 standard library only.
- Tests: `python3 -m unittest discover -s proto8/cmd/aos-kit/tests -v`. They use `tests/fixtures/kits` (a copy of `templates/kits` with make blocks added; a test keeps it equal to the shipped files apart from the make blocks) and `tests/fixtures/kits-stale` (a kit whose system text is out of date). Temporary folders are kept; set `TMPDIR` to choose where they go.

## Known limits

- The shipped `templates/kits/kits.json` has no make blocks yet; until it does, `make`, `check` and `add` on the shipped kits stop with `MakeMissing`, and only `ls` works there.
- `add` compares with the stock agent-fsm files byte for byte; a definition made from an older template counts as edited (use `--force`; the old files are kept).
- Lengths are counted in characters, not bytes or tokens.
