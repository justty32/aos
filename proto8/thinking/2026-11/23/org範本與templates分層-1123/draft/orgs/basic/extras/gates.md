Quality gates of <PROJECT>: the checks a piece of work passes in order, who holds each gate, and what counts as evidence.

# Gates

Back to [org](README.md). Move this file to `wf/org/gates.md` if every piece of work here passes the same line of checks; link it from the standard flow.

| gate | what is checked | who holds it | evidence |
|---|---|---|---|
| G0 authority | the user agreed to this work and this much of it | lead | the user's own words, with the date |
| G1 input | the sources are the right ones, the right version, and not damaged | <...> | <a record: where from, which version, size or hash> |
| G2 form | the files exist, are named and linked as they should be | <...> | <the output of a listing or a check tool> |
| G3 content | an independent check found nothing left open | <the checker reports, the lead decides> | <the checker's report> |
| G4 integration | the shared files, the indexes and the build agree | <...> | <the output of the check command> |
| G5 commit | the commit holds only this work's paths | <CHOICE 4> | `git show --stat` |
| G6 outside | pushing, publishing | the user | needs its own go-ahead |

- Nobody's own word that it is finished counts as evidence at any gate.
- A gate that fails sends the work back to the one who did it. After <N> rounds at one gate, stop and tell the user; do not let it through and do not fix it yourself.
- Before the content gate passes, nothing is written into the shared files. A failure before that point leaves nothing to undo there.
- Reaching a threshold for more seats or more agents only means the question may be put to the user. Write the thresholds here as numbers that can be changed: <...>.
