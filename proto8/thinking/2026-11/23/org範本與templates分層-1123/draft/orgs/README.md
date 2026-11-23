Org templates: the documents that say who owns what in a workspace and who gets the work next; copy one into the workspace's `wf/org/`.

# orgs

An org is not an agent and not a daemon. It is a small set of documents in the workspace that every agent there reads: which seats exist, what each seat owns, how work is handed over, and where things go. The agents themselves are made from the agent templates (`agent-fsm`, `eca-claude`, ...) and attached as usual.

## What is here

| folder | what it is |
|---|---|
| [basic/](basic/README.md) | The skeleton. Its files are the org itself: the entry (seat table, standard flow), `places.md`, `letters.md`, the lead's role card, and a blank role card. |
| [basic/CHOICES.md](basic/CHOICES.md) | Nine choices every org makes once (who commits, are seats always attached, ...). Answer them before you fill the rest. |
| [basic/extras/](basic/extras/README.md) | Optional parts: the system text that points an agent to its card, a site layer for kits, a helper card, an improvement log, a quality gate table. Take what you need and delete the folder. |

## How to use

1. Copy the skeleton into the workspace:
   ```
   cp -r $AOS_HOME/templates/orgs/basic <workspace>/wf/org
   ```
2. Read `wf/org/CHOICES.md` and write your answer under each choice. The other files have a line marked `CHOICE n` wherever an answer goes.
3. Fill the placeholders. A name in capitals is one value used in several files; text in small letters between `<` and `>` is a blank to write out in that place. This lists what is still open:
   ```
   grep -rn '<[^>]*>' <workspace>/wf/org
   ```
   | placeholder | what to write |
   |---|---|
   | `<PROJECT>` | the name of the workspace or project |
   | `<LEAD>` | the lead's agent name on the daemon table |
   | `<SEAT>` | a seat's short name (the folder name of its card) |
   | `<AGENT>` | the agent name of the one in that seat |
   | `<PATHS>` | the paths a seat may write |
   | `<TEMP>` | where throwaway files go |
   | `<ASK_USER>` | how questions reach the user (the user zone, or a file) |
   | `<AOS_CONTACT>` | who to ask about aos itself, or `nobody` |
   | `<FEEDBACK_FILE>` | the file where problems with aos are collected |
   | `<LANGUAGE>` | the language of letters and documents (in `extras/system.seat.txt` and `extras/site.txt`) |
   | `<N>` | a number you choose |
4. Make one card for each seat: `cp -r wf/org/seat wf/org/<SEAT>`, fill its four sections, and add a row to the seat table in `wf/org/README.md`. Then delete `wf/org/seat/` or keep it as the blank.
5. Point the workspace's entry file (`AGENTS.md`) to `wf/org/README.md` with one line: who owns what and who gets it next.
6. Attach the agents. The org template ships no agent definition; make each seat's definition from an agent template and put the text of [basic/extras/system.seat.txt](basic/extras/system.seat.txt) into its system text, so that the definition points to the card and repeats nothing:
   ```
   agent_def {"op":"new","template":"agent-fsm","path":"<where your definitions live>/<SEAT>"}
   ```
   or `cp -r $AOS_HOME/templates/eca-claude <...>/<SEAT>` for a coding CLI. Set the brain in `llm.json`, run `agent_def check`, then `aos-agent ctl add` (a person) or `subagent add` (the lead).

Write the cards in the language your agents and your user work in. The template is in English so that it reads the same everywhere; the placeholders and the user's own words go in as they are.

## What it is next to the other templates

- **start-api, start-eca** start a tree (a root daemon and one agent). Do that first. An org is what you add when one workspace has more than one agent.
- **daemon-sub** gives a workspace its own daemon under the root. Use it when the org's agents should start, stop and be listed together; the seats are then attached under that daemon.
- **agent-fsm, eca-claude, eca-pi, agent-python** are the bodies of the seats. One definition per seat, or one stock template used by several seats when only the card differs.
- **kits** are a system text and a tool set for one kind of helper (gatherer, reviewer). A helper attached for one job uses a kit and does not read the role cards. The kit's site layer (who to report to, local rules) comes from the org: see [basic/extras/site.txt](basic/extras/site.txt).

## What it does not do

- It enforces nothing. The paths a card lists are an agreement: all agents on one account can write anywhere, and nothing checks who committed whose file. Say which layer holds each limit: the text of a card, a check inside a tool, or the operating system.
- It does not choose models, attach agents, or create folders outside `wf/org/`.
- It is not a workflow. How a kind of work is done stays in `wf/workflows/`.
