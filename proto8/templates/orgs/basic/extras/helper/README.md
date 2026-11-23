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

1. Pick the kit. If the org has a site layer (`extras/site.txt`, filled in), make a kit of your own first: copy the kit folder and put the site layer into its `system.txt` just before the role part (the last block, the same text as the kit's `roles/<role>.txt`).
2. Attach it.
   - From a shell: `aos-agent ctl add --kit <the kit folder> -n <agent name> -w <its workspace folder> <an agent-fsm definition>`; the kit's two files go into the agent's stack and the definition is not changed (`$AOS_HOME/templates/kits/README.md`).
   - As an agent: make a definition with `agent_def {"op":"new","template":"agent-fsm","path":"<where your definitions live>/gather"}`, copy the kit's `system.txt` and `tools.json` over it, set the brain in `llm.json`, run `agent_def check`, then `subagent` add with a name like `<your name>-<role>-<number>` and its own workspace folder. The `def` and `subagent` tool packs are in no stock template; add them first (knowledge page `aos/agents.md`).
3. Send the brief. When the job is checked, remove the helper (`subagent` rm, or `aos-agent ctl rm`).

## Model

- **Brain:** <the endpoint pack and tier this org uses for helpers>.
- **How many at once:** one per brief; the limit is the attacher's limit of subagents.
- **When it cannot be attached:** <who does the job instead>.
