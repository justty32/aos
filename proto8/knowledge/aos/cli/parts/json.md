# aos-json: read and edit aos JSON files

Address any value with `FILE#/POINTER`; `$ref` is followed only when you ask. Agents use the json tools (`json_get`, `json_ls`, `json_search`, `json_len`, `json_set`, `json_add`, `json_del`, `json_multi_get`, `json_multi_set`; for $ref/$env files `jsonx_get`, `jsonx_ls`, `jsonx_search`, `jsonx_set`, `jsonx_add`, `jsonx_del`, `jsonx_multi_get`, `jsonx_multi_set`); aos-json is for shells and scripts. It also reads a `.md` file (`get`, `ls`, `where`, `peek`, `search`; `get --tree FILE.md` prints the whole file as one JSON value) and never writes one; the path rules are in `aos/tools/json_get.md#/JSON tools: reading markdown`.

# Reading

```sh
aos-json get c.json#/a/b                  # 1
aos-json get --follow --str c.json#/r/y   # hi      (r is {"$ref": "other.json#/x"})
aos-json get --resolve c.json#/e          # "/home/me"   (e is {"$env": "HOME"})
aos-json peek c.json                      # one level; big children folded
aos-json where c.json#/r/y                # c.json#/r, then other.json#/x/y
```

Without `--follow`, a pointer through a `$ref` = `PointerMissing ... add --follow to go through it`. A pointer that is not there = `PointerMissing`. `peek --depth N` expands more levels. `ls [--long] [--depth N] [--offset N] [--limit N] FILE#/PTR` lists children; `search --key K --value JSON [--contains] [--up] [--limit N] FILE#/PTR` finds keys or values (give `--key`, `--value` or both; `--up` looks at the parents, not with `--follow` or `--resolve`). `env --prefix P` sets `$prefix`. More flags: run `aos-json SUBCOMMAND --help`.

# Writing

```sh
aos-json set c.json#/a/c '[1,2]'
aos-json set --str c.json#/a/s 'plain text'
aos-json set --parents c.json#/n/m 1      # without --parents: PointerMissing
aos-json add c.json#/a/d 7                # like set, but KeyExists if it is already there
aos-json append c.json#/a/c 3
aos-json merge c.json#/a '{"b": 9}'
aos-json del c.json#/n
echo '{"/a/b": 5, "/z": true}' | aos-json batch c.json
aos-json env --path /x c.json#/h HOME     # writes {"$env": "HOME", "$path": "/x"}
aos-json ref --move c.json#/a parts.json  # moves the value to parts.json, leaves {"$ref": "parts.json"}
```

Writes print nothing (`add` prints where it wrote). VALUE comes from argv, or stdin when omitted. Each changed file is written atomically (a temp file, then rename). `--check` refuses a change that adds problems. Without `--follow`, a write through a `$ref`/`$env` = `FollowMissing`. `--raw` (set, add, append, del) treats `$ref`/`$env` objects on the way as plain objects (`aos-json set --raw c.json#/r/k 1` adds k next to the `$ref`); not with `--follow` (`ArgumentsBad`).

# Checking

```sh
aos-json check c.json        # exit 0: no problems
aos-json check bad.json      # exit 10, one line per problem:
# bad.json#/k: DirectiveBad $ref gone.json cannot be read (file not found: /.../gone.json)
```

It checks references, directive forms and exec forms. `--env` also reports unset environment variables.
