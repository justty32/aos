# doc-run: test a how-to page by running the page itself

For pages that outsiders type in word for word (getting started, README quickstart, tutorials). Instead of writing a separate test script, pull the commands out of the page and run them, so you test exactly what a reader types. A second script checks that copies of the quickstart (README, landing page) did not drift from the page you ran.

Files: `run-doc.py`, `check-cmds.py` (python3 only, no other dependency).

## Use
    python3 run-doc.py PAGE.md REPO_URL OUT.sh
- Every ```` ```bash ```` / ```` ```sh ```` block, in order, goes into `OUT.sh` (with `set -x` on top). `<REPO_URL>` in the page is replaced by `REPO_URL` (use a local mirror, `file://...`).
- Run it in a clean copy, with an empty home and no `AOS_*` variables, e.g.
  `bash -c 'for v in $(compgen -e | grep ^AOS_); do unset "$v"; done; exec env HOME=$PWD/home-x bash OUT.sh'`
- Then check: the output matches what the page says you will see; no process is left behind in the work folder (look at `/proc/*/cwd`); what appeared under the fake `HOME` matches what the page says is written.
- Put expected output in ```` ```text ```` blocks: they are not extracted, so commands and expected output can sit side by side. A command you show but do not want run must not be in a bash/sh block.

      python3 check-cmds.py MASTER.md COPY [COPY...]
- Every command line in each COPY (`.md`: bash/sh blocks; `.html`: `<pre>` blocks) must also be in MASTER. Prints `COPY: not in master: LINE` for each one, then `check-cmds: N lines not in master`. Exit 0 all found, 1 some missing, 2 bad arguments.
- Normalizes quotes around `$HOME`/`$AOS_HOME` paths, `$HOME/` to `~/`, trailing comments, `&&` chains, whitespace.

## Install / remove
Nothing to install; run with python3. Delete the folder to remove.

## Known limits
- check-cmds only counts lines that start with a known command word (`aos-`, `cd`, `cp`, `mkdir`, `nohup`, `export`, `git`, `cmake`, `tail`, `ls`, `timeout`, `sleep`, `echo`, `chmod`, `cat`, `for`); add yours to the `cmd` regex. `python3` and `make` are not in the list, so since 11-17 (aos builds with `python3 install.py`, no more cmake) the build line is not checked unless you add them. It checks copy -> master only, not the other way.
- run-doc does not check its arguments (wrong count = Python traceback) and does not run anything itself.
- Until 11-17, building aos with vcpkg wrote `~/.cache/vcpkg` under the fake HOME. Since 11-17 aos builds with `python3 install.py` (no vcpkg), which writes only inside the proto8 folder; still compare "what gets written" after a real run.

## Author
ok-release, 2026-11-14 (used on the "getting started" page and README; found 4 doc errors). Curated by repo-aos (docstring wording only; tested on small fake pages).
