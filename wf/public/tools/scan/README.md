# scan: check files for private values and secrets before publishing

Run it before you push, publish, or put files on a public site. It prints one line for each private value or secret it finds. Python 3 standard library only.

Files: `scan.py`.

## Use
    python3 -I scan.py [--private VALUES.txt] PATH...
- `PATH` = files or folders (folders are walked; hidden folders such as `.git` are skipped, pass them by name if you need them).
- `VALUES.txt` = your own values (account name, real name, host name), one per line, `#` = comment. Keep this file **outside** the repo (or in a git-ignored folder) and never commit it. Each value matches case-insensitively, as a whole word only (`alice` does not hit `alicehost`), and also in URL-encoded form (`Ann%20Lee`).
- Built-in rules (no private data in them): key shapes (`sk-`, `ghp_`/`gho_`/..., `github_pat_`, `xox?-`, `AKIA`, private key headers, `Bearer` tokens), any `/home/<name>` path, e-mail addresses, private IPv4 ranges, SVG editor metadata, PNG text chunks and JPEG EXIF, and any file that is not UTF-8 text or has a NUL byte (`binary`).
- Output: `FILE:LINE: RULE: TEXT` per hit (`LINE` 0 = whole file), last line `scan: N hits in M files` (M = files with hits).
- Exit: 0 no hits, 1 hits, 2 bad arguments (no PATH, `--private` without a file, a PATH that does not exist).

## Install / remove
Nothing to install. Delete the folder to remove. It never changes the files it reads.

## Known limits
- `TEXT` is the matched line itself, so the output contains the secret or private value. Do not paste it into reports or commits; report only "N hits in which file".
- One hit per rule per line: a second value of the same rule on that line is not shown (each `--private` value and its URL form count as separate rules).
- It finds patterns, not meaning: a name spelled another way, or a value split across lines, is missed. Version strings like `1.10.0.5.9` hit `private-ip`.
- Images: metadata only, not what they show; look at screenshots yourself. Every other non-text file is just reported as `binary`; decide by hand.
- An unreadable file (no permission) stops the run with a Python traceback and exit 1, which looks like "hits". A `VALUES.txt` that is not UTF-8 also gives a traceback.
- Scanning this folder gives 3 expected hits: `scan.py` itself (2 `svg-meta` on its own rule text) and this README (1 `private-ip` on the version-string example above).
- Fix hits by editing; it never rewrites anything, and do not rewrite git history for it.

## Tested
- By ok-release, 2026-11-14: self-test hit home-path, email, private-ip, `sk-` key, svg-meta and private values; word boundary held; exit codes 0/1/2. Used on the ok-release drafts and a whole repo.
- By repo-aos when curating, 2026-11-14, on fake files in a scratch folder: every key shape above, home path, e-mail, three private IP ranges, SVG metadata, PNG `tEXt`, JPEG `Exif`, NUL file, bad UTF-8 file, private values (word boundary, case, URL form), hidden folder skipped and scanned by name; exit 0 on a clean file; exit 2 for no PATH, `--private` with no file or a missing file, and a missing PATH.
- Not tested: real images from an editor or camera (only hand-made headers), `zTXt`/`iTXt`/`eXIf` chunks, very large files or trees, symlinks, non-Linux systems, false-positive rate on real code beyond the one version-string case.

## Author
ok-release, 2026-11-14. Curated by repo-aos (README rewritten; `scan.py` unchanged).
