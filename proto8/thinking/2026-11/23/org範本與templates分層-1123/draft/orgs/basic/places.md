Where a thing belongs in <PROJECT>, why write scopes are only an agreement, how a seat is opened, and how a definition points to its role card.

# Where things go, what may be written

Back to [org](README.md).

## Where things go

Ask the questions in order. The first one you answer with yes gives the place.

| question | place |
|---|---|
| Is it the product itself: code, tests, product documents? | `<the product folders of this workspace>` |
| Does it say who owns what and who gets it next? | `wf/org/` (the entry and the role cards only) |
| Does it say how a kind of work is done, for everyone? | `wf/workflows/` |
| Is it a seat's own notes, drafts, proposals, or lasting output? | <CHOICE 7> |
| Is it a record of one investigation, plan or review? | `<where this workspace keeps such records>` |
| Is it work that is not finished? | `<the progress file>`; only the lead writes it, the others say it in their letters |
| Is it a question for the user? | `<ASK_USER>`; it goes through the lead |
| Is it throwaway: logs, outputs of a run, copies, scratch? | `<TEMP>` (not in version control; it may be cleaned at any time) |

Only things that must last go into `wf/`. What is still moving (progress, questions waiting for the user) is not kept in `wf/org/`.

## Write scopes are an agreement

Each card lists what the seat may write and what it only reads. This is an agreement, not a wall: all agents run as one account, a file tool takes any absolute path, and a shell goes anywhere. Taking one tool away does not make a limit.

When you describe a limit, say which layer holds it:

1. **the text of a card or a system text** - holds only while the agent follows it;
2. **a check inside a tool** - holds for whoever uses that tool, and not for a shell beside it;
3. **the operating system** (a sandbox, a resource scope) - holds.

To write inside another seat's paths, write to that seat first.

## Opening a seat

- **When:** the work has paths of its own and rules that must outlive one job. If it has neither, it is a single job, not a seat.
- **How:** write its card (`cp -r wf/org/seat wf/org/<SEAT>`, fill the four sections), make the folders it needs, add a row to the seat table. Opening a seat is new work: the user agrees first.
- **Closing:** remove the row and the card in one change; say in the commit message where its paths went.

## A definition points to its card

A seat's system text says only: which seat you are; read the workspace's entry file, [the org entry](README.md), your card and your notes before you start; where the card and the system text disagree, the card wins. Duties and paths are written once, in the card. The text to start from is in `extras/system.seat.txt`.

A helper attached for one job does not read the cards. Its card, if the org has one, is written for whoever attaches it.

## Shared resources

List here what only one agent may use at a time (a browser, a port, a heavy build), who gives it out, and how: `<...>`. A lock that callers take by agreement makes them wait in line; it does not stop one that skips it. If the limit must hold, put it inside the tool that runs the job.
