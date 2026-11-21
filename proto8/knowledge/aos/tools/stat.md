# Tool stat

Show facts about one file, folder or link, as one JSON object (not the content).

Use it to check a path: is it there, file or folder, text or binary, how big, JSON or not. Use `ls` for a whole folder, `read` or `view` for the content.

```json
{"path": "cfg.json"}
```
-> `{"path":"cfg.json","type":"file","mtime":"2026-11-11T03:17:02.222+00:00","mode":"0644","size":82,"exec":false,"text":true,"counter_lines":1,"top":{"type":"object","counter_keys":3},"format":"json"}`

- Every path: `type` (file, dir, link), `mtime` (UTC), `mode`.
- Files: `size` (bytes), `exec`, `text` (UTF-8 without zero bytes); text files add `counter_lines` and `format` (json, python, markdown, shell, text); JSON files add `top` (a summary of the top level).
- Only the first 4MB of a file is read: `text`, `counter_lines` and `format` come from that part.
- Folders: `counter_children`, `aos` (aos files inside, like `["_entry", "_tooldef.json"]`).
- Links: `link_to`, then the facts of the target; a link to nothing: `{"path":"dead","type":"link","link_to":"nowhere","broken":true}`.

Errors: `aos/tools/stat.md#/stat: errors`.

# stat: errors

- `FileMissing`: nothing at that path. `ls` the folder above it.
- `ReadFailed`: a file is there but could not be read (a folder you cannot read is not `ReadFailed`: the tool crashes with a traceback; report it); its facts so far are not printed. `ReadFailed`, `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
