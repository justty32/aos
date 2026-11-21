# Tool trash

Delete a file, folder or link so that you can undo it: it is moved to `.trash/<time>/<its path>` in your workspace. Prints `{"path", "to"}`; `to` is where it is now.

Use trash by default when you delete. Use `remove` only when it must really be gone (a big temporary folder, emptying the trash).

```json
{"path": "out/hello.txt"}
```
prints `{"path":"out/hello.txt","to":".trash/20261111-111744/out/hello.txt"}`.

- Trashing the same path again in the same second goes to `.trash/<time>-1/<its path>`, then `-2`, and so on; different paths in the same second share `.trash/<time>/`.
- Undo: `move` with `"from"` = that `to` and `"to"` = the old path (`aos/tools/move.md`).
- `<time>` is the local time `YYYYMMDD-HHMMSS`. A path outside the workspace keeps its whole absolute path: `/tmp/b1out/f.txt` goes to `.trash/<time>/tmp/b1out/f.txt`.
- The trash is never emptied by itself. To empty it: `remove` with `{"path": ".trash", "recursive": true}` (no undo). `ls` hides `.trash` unless `"hidden": true`.

Errors: `aos/tools/trash.md#/trash: errors`.

# trash: errors

- `FileMissing`: nothing at that path.
- `PathBad`: the workspace itself, something already in `.trash`, or a folder that contains `.trash`.
- `MoveFailed`: the system refused the move (`aos/errors/common.md#/Codes from file work`).
- `WsMissing`: the trash is always in your workspace, so trash needs one even for an absolute path. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
