# aos-share: set ACLs on a shared folder or a file for named users

It applies one of six ACL templates (`mkdir`, `chmod`, `setfacl`) so that another group id or user id, for example an agent running under a sub-id, can use a path. It changes permissions for real: run it with `--dry-run` first.

```sh
aos-share --dry-run team /shared/team --group sub:600   # prints each command, changes nothing
aos-share team /shared/team --group sub:600
```

`aos-share [--dry-run] KIND PATH (--group G | --uid U)...`; flags may stand anywhere.

Two more subcommands, which must be the first word:

- `aos-share check [-R] [--list-acl] PATH...` changes nothing: one line per finding (`secret-open` a secret file such as `.env`, `*.key` or `exec.json` readable by group or other; `acl-masked` the mask cuts a named ACL entry; `acl-missing` no extended ACL although the parent has a default ACL; `acl-present` any ACL, only with `--list-acl`; `unreadable`), last line `total: N`; exit 1 when N > 0.
- `aos-share reset [-R] [--dry-run] PATH...` undoes the templates: `setfacl -b`, then `chmod g-s,-t` on folders; rwx bits and ownership stay.

`-R` also covers every entry below PATH (symlinks skipped).

| KIND | what it makes | needs |
|---|---|---|
| `team` | a folder the group can write (created if missing) | one `--group` |
| `work` | like `team`, with the sticky bit | one `--group` |
| `drop` | a delivery box with `tmp`, `new`, `cur`: the group can put things in, not list them; whoever drops a file or folder there must create it with group bits (for example 0660 / 0777) | one `--group` |
| `read` | an existing path, read-only for the groups, recursive | one or more `--group` |
| `key` | an existing regular file (set to mode 600), readable by the users | one or more `--uid` |
| `stack` | a private folder (mode 700) shared with one user (created if missing) | one `--uid` |

G and U are a plain number (the real id) or `sub:N` (1 to 65536): the N-th id of your first range in `/etc/subgid` (`--group`) or `/etc/subuid` (`--uid`). No leading zeroes or signs.

It prints nothing on success. After a real run it may print `aos-share: warning: DIR gives no x to others: uid/gid N cannot reach PATH` for a parent folder; it does not fix that. `--dry-run` does not check that PATH exists, but still resolves `sub:N`.

Errors (`aos-share: error: CODE reason`, exit 1): `ArgumentsBad` (unknown KIND, `--uid` where `--group` belongs or the reverse, the wrong number of them, a bad id), `SubidMissing` (no usable line for you in the subid file, or N is past the range), `PathMissing` (`read` and `key` do not create PATH; `key` needs a regular file), `CommandMissing` (`setfacl` or `getfacl` not on PATH), `AclFailed` (a step failed; earlier steps stay done), `FlagUnknown`.
