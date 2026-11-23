Role card of the helper in <PROJECT>, written for whoever attaches one: what a helper may be given, what it may not, how to attach it and how to remove it.

# Helper `helper`

Back to [org](../README.md). Move this folder to `wf/org/helper/` if the org uses helpers.

A helper is attached for one job and removed when the job is done. It holds no seat, owns no paths and keeps no notes. It does not read this card: it is made from a kit (`$AOS_HOME/templates/kits/`, knowledge page `aos/kits.md`) and knows only the kit's text, the site layer and its brief.

## Duties

- **May be given**
  - **Finding facts** (the gatherer kit): search, count, read and sort out, each item with its source. It does not design, advise, or change what it looks at.
  - **Checking point by point** (the reviewer kit): compare work with a brief or a plan, one item at a time. It points out; it does not fix.
  - **Mechanical changes that need no judgement** (rename by a table, move files, apply a format): only if a kit with writing tools exists here: <which kit, or "none yet">.
- **May not be given**
  - Writing code, or any change where something must be understood or chosen. If you cannot tell, it needs judgement.
  - Design, structure, deciding what is right.
  - Committing, pushing, deleting, asking the user, attaching agents of its own.
  - Anything that needs a command to be run, when its kit has no shell: run the command yourself and give it the output.
- **Done when** its answer file is there and whoever attached it has checked each item against the sources.

## Read and write scope

An agreement, not a wall ([places](../places.md)).

- **May read:** the paths the brief names; the knowledge folder the brief names (give the full path).
- **May write:** only its own workspace folder, `<TEMP>/<agent name>/`. Only the kit's text says so; nothing stops a write elsewhere.

## Handoffs

| who | gives it | gets back | then |
|---|---|---|---|
| whoever attached it (the lead or a seat) | one brief with one goal: what to read, what to write, what to deliver, when it is done | an answer file, or the whole answer in its last reply | checks each item against the sources without running the job again; moves what must stay into the workspace and commits it; removes the helper |

- Whoever attaches a helper answers for its result. The result goes neither to the user nor to another seat directly.
- Do not wait for it inside one turn. Send the brief, end the turn, and look again when its letter or a timer wakes you.
- It counts against your limit of subagents until it is removed.

## How to attach one

1. Make a definition and lay the kit over it:
   ```
   agent_def {"op":"new","template":"agent-fsm","path":"<where your definitions live>/gather"}
   ```
   Copy the kit's `system.txt` and `tools.json` over it. If the org has a site layer (`extras/site.txt`, filled in), put it into `system.txt` between the general part and the role part. Set the brain in `llm.json`. Run `agent_def check`.
2. `subagent add` with a name like `<your name>-<role>-<number>` and its own workspace folder.
3. Send the brief. Remove the helper with `subagent rm` when the job is checked.

## Model

- **Brain:** <the endpoint pack and tier this org uses for helpers>.
- **How many at once:** one per brief; the limit is the attacher's limit of subagents.
- **When it cannot be attached:** <who does the job instead>.
