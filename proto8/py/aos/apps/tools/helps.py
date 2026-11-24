"""aos-tools 的英文說明：頂層 HELP 與各子命令的 HELPS（--help 印的、錯誤行 usage 取的都是這裡）。"""
HELP = """aos-tools - keep the list of tools an agent can call

usage: aos-tools [--file F] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-tools SUBCOMMAND --help

The list is one JSON file, the registry (default: ./tools.json). A tool is a folder
with _tooldef.json, a JSON file with a _tooldef key (or FILE.json#/POINTER: the
object there has the _tooldef key), or an executable that answers --tooldef. Agents read the list before each thought and call tools through it.
Folders and JSON objects may also carry the definition as "tooldef" inside
_metainfo(.json); when both exist they are merged one level deep and the
separate _tooldef wins on the same key.

A registry may carry one line, "$override": OTHER_FILE (or a list of files). It then
holds only the differences from OTHER_FILE (which may override another file in turn).
Files are applied in order, later wins; an entry whose value is null is not a tool.
Each agent's own changes to its definition's tools are kept this way.

subcommands:
  add XXX          put a tool on the list (XXX = folder, JSON file, FILE.json#/POINTER
                   or executable)
  rm XXX           take it off the list (XXX = name, else path; tool files are kept)
  ls               show the list
  get XXX          print one tool's definition as JSON (XXX = name, else path)
  call NAME [JSON] run a tool once
  override BASE... make F a list of differences on top of BASE

examples:
  aos-tools add tools/clock                     # name = clock
  aos-tools add --name now tools/clock          # pick the name
  aos-tools add "$AOS_HOME/lib/tools/base/shell"     # the shell expands it now
  aos-tools add --path-json '{"$env":"AOS_HOME","$path":"/lib/tools/base/shell"}'
                                                # looked up on every use instead
  aos-tools ls -l
  aos-tools call clock '{"tz": "Asia/Taipei"}'

flags (anywhere: before or after the subcommand and its XXX / NAME; a subcommand's own
flags may go before or after its XXX / NAME too; after -- nothing is a flag):
      --file F   the registry to read and write (default: ./tools.json;
                 missing = no tools, with a warning for the default).
                 add / rm write only F, never what it overrides.
  -h, --help     show this help

Relative paths are stored relative to the file they are written in, so a registry
and its tools can move together.

exit codes: 0 ok; 1 error ("aos-tools: error: CODE reason" on stderr);
            call returns the tool's own code (killed by signal N = 128+N).
more: proto8/py/aos/apps/tools/README.md
"""
HELPS = {
    "add": """aos-tools add - put a tool on the list

usage: aos-tools [--file F] add [--name N] [--replace] [--no-cache] [--uses N]
                 [--env-file FILE] [--envs K=V]... (XXX | --path-json JSON)

XXX is a tool folder, JSON file or executable; flags may go before or after it.
It may also be FILE.json#/POINTER: the object at that JSON Pointer holds _entry,
_tooldef (or _metainfo.tooldef) and optional _metainfo keys (aos-exec runs it from the JSON file's folder).
It is stored the way you give it: absolute stays absolute; relative (to the
current directory) is stored relative to F. --path-json stores the JSON as given - a path string or a
directive such as {"$env": "AOS_HOME", "$path": "/lib/tools/base/shell"} - and it is
resolved on every use.

Prints: added NAME -> ABSOLUTE_PATH (FILE_WRITTEN: STORED_VALUE)

flags:
  -n, --name N        list it under this name (default: the folder name, or the file
                      name without extension, or the last part of #/POINTER;
                      only A-Z a-z 0-9 _ -, at most 64)
      --replace       replace a tool already listed under that name (keys that F
                      overrides and this add does not give are written as null)
      --path-json J   store this JSON path value instead of XXX
      --envs K=V      set K to V for every call of this tool (repeatable; V is stored
                      as typed in F - not for secrets)
      --env-file FILE remember where FILE is (stored like XXX); it is read on every
                      call, never copied into F. Use it for secrets.
      --no-cache      ask the executable for its definition every time
      --uses N        take it off the list again after N successful calls (exit 0);
                      1 = once, 2 = twice. Stored as "uses" in F and counted down
                      there by call; at 0 the entry is deleted from F (a tool F
                      replaced comes back). ls and get show what is left.
  -h, --help          show this help

On a call, later wins: the tool's own .env (fills gaps only), the caller's
environment, --env-file, --envs. A missing env file is a warning here and an error
on call. A tool that declares variables you have not set gives a warning; add still
succeeds.

exit codes: 0 added; 1 error (PathMissing, ToolDefMissing, ToolDefBad, NameBad, ToolExists...).
""",
    "rm": """aos-tools rm - take a tool off the list

usage: aos-tools [--file F] rm XXX

A listed name wins. Otherwise XXX is read as a path, and every name that points
there is removed. When the tool comes from a file that F overrides, F gets "NAME": null
(an entry whose value is null is not a tool) and that file is left alone; otherwise
the name's key is deleted from F. Prints one line per name:
removed NAME (F: key deleted | F: set to null over FILE). The tool's own files are never deleted.

flags:
  -h, --help   show this help

exit codes: 0 removed; 1 error (ToolMissing, RegistryBad, WriteFailed...).
""",
    "ls": """aos-tools ls - show the list

usage: aos-tools [--file F] ls [-l | --json]

One line per tool, sorted by name: NAME TAB the first sentence of its description
(see one tool in full with get NAME). Every tool is checked. A broken tool (its
path is gone, its definition is missing or bad) is skipped with a warning naming it,
and the others are listed as usual: shown as "NAME TAB broken: CODE (...)", with
KIND broken in -l, and left out of --json. get NAME or call NAME on it still fails
with its own error. Executables are asked with --tooldef (answers are cached in
$AOS_STACK/tooldef_cache.json when AOS_STACK is a folder).

flags:
  -l, --long     NAME TAB KIND TAB PATH (absolute) TAB FROM (the file and key its
                 path comes from) TAB STORED (the path as written there, as JSON)
                 TAB ENV (variable names and @ the env file; never values).
                 KIND is dir (folder), json (JSON file), exe (executable) or
                 broken (skipped, see above).
                 Also lists names turned off with null:
                 NAME null PATH-IT-HIDES FILE-THAT-SAYS-NULL#/tools/NAME null -
  -j, --json     one JSON array with name, kind, path, tooldef and optional metainfo
  -h, --help     show this help

exit codes: 0 listed (also when some tools were skipped as broken);
            1 error (RegistryBad, DirectiveBad, CommandMissing...: the registry itself).
""",
    "get": """aos-tools get - print one tool's definition as JSON

usage: aos-tools [--file F] get XXX

A listed name wins; otherwise XXX is read as a path. Prints one JSON object per
match: name, kind, path, tooldef and optional metainfo. Variable values are not
printed (see ls -l).

flags:
  -h, --help   show this help

exit codes: 0 printed; 1 error (ToolMissing, RegistryBad, ToolDefBad...).
""",
    "call": """aos-tools call - run a tool once

usage: aos-tools [--file F] call NAME [ARGS_JSON]
       echo ARGS_JSON | aos-tools [--file F] call NAME

The tool gets ARGS_JSON on its stdin (given on the command line as is, or read from
stdin when omitted); its stdout is the result. The variables registered with add
are set for the call; a registered env file is read now, and a missing one is an
error (the tool does not run). The tool runs through aos-exec in its own scratch
folder: $AOS_STACK/tools/NAME/ when AOS_STACK is set (not created beforehand: a
tool that writes there creates it), otherwise aos-exec's default (.stack/ in the
current directory). With AOS_STACK set the tool also gets
AOS_STACK_IN_CALLER=tools/NAME (where its folder sits in your stack), so a path
it prints as $AOS_STACK/tools/NAME/... can be opened from your stack as written.
A tool registered with --uses ("uses": N) runs as a child of aos-tools instead of in
its place: when it exits 0, N goes down by one in the file that holds it, and at 0
its entry is deleted there. A failed call (exit not 0, killed) does not count.

flags:
  -h, --help   show this help

exit codes: the tool's code (killed by signal N = 128+N);
            1 with "aos-tools: error:" on stderr = aos-tools itself failed.
""",
    "override": """aos-tools override - make F a list of differences on top of other registries

usage: aos-tools [--file F] override (BASE... | --path-json JSON)

Writes "$override": BASE into F (creating F when missing; several BASEs make a list).
From then on F shows BASE with F applied on top: files are applied in order, later
wins (a list of BASEs in its order, then F); an entry whose value is null is not a tool.
BASE is stored like a tool path: absolute stays absolute, relative is stored
relative to F, --path-json is stored as given and resolved on every use. BASE may
itself override another file. Prints: F $override -> STORED_VALUE

flags:
      --path-json J   store this JSON value (a path, a directive or a list) instead
  -h, --help          show this help

exit codes: 0 written; 1 error (RegistryBad when F already lists tools of its own
            without $override or the chain loops, PathMissing, WriteFailed...).
""",
}
