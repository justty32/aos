# Orgs: who owns what in a workspace, and who gets the work next

An org is a small set of documents in a workspace's `wf/org/` that every agent there reads: which seats exist, what each seat owns, how work is handed over, and where things go.

Key points:

- An org is not an agent and not a daemon: it enforces nothing, chooses no models and attaches no agents.
- Use one when one workspace has more than one agent; start the tree first.
- The template is `$AOS_HOME/templates/orgs/basic`: copy it to `wf/org`, answer nine choices, fill the placeholders, make one card per seat.
- It ships no agent definition: each seat's definition is made from an agent template and gets a short system text that points to its card.

More: `aos/orgs.md#/What is in the template`, `aos/orgs.md#/How to set one up`, `aos/orgs.md#/The nine choices`, `aos/orgs.md#/Orgs and kits`, `aos/orgs.md#/What an org does not do`.

# What is in the template

- `$AOS_HOME/templates/orgs/README.md`: what an org is, the steps to set one up, the placeholder tables, how it sits next to the other templates.
- `basic/`: the skeleton. Its files are the org itself: the entry `README.md` (seat table, standard flow), `places.md` (where things go, what may be written), `letters.md` (requests and replies), the lead's card `lead/README.md` and a blank card `seat/README.md`.
- A card has four sections: Duties, Read and write scope, Handoffs, Model.
- `basic/CHOICES.md`: the nine choices; the other files mark each place an answer goes with `CHOICE n`.
- `basic/extras/`: optional parts (its README says when each is worth taking and where it goes): `system.seat.txt`, `site.txt`, `helper/`, `improvements.md`, `gates.md`.
- The template is in English; write the cards in the language your agents and your user work in.

# How to set one up

Follow the steps in `$AOS_HOME/templates/orgs/README.md#/orgs/How to use`; they are the source, this is only the outline:

1. Copy `basic` to `<workspace>/wf/org` (`wf/` must exist, `wf/org` must not).
2. Answer `wf/org/CHOICES.md`, then write each answer where a file says `CHOICE n`.
3. Take the parts of `extras/` you need; delete the folder after the last step.
4. Fill the placeholders that hold one value for the whole org (`<PROJECT>`, `<LEAD>`, `<TEMP>`, ...). `grep -rn '<[^>]*>' <workspace>/wf/org` lists what is still open.
5. Make one card per seat from `seat/` and add a row to the seat table.
6. Add one line to the workspace's `AGENTS.md` that points to `wf/org/README.md`.
7. Make each seat's definition from an agent template (which ones: `$AOS_HOME/templates/README.md`), put `extras/system.seat.txt` with `<SEAT>` and `<AGENT>` filled into its `system.txt`, set the brain, check it, and attach it (`aos/agents.md`).

# The nine choices

Every org answers these once in `CHOICES.md`; none has a right answer, and each option there says when it fits.

1. What body does the lead have (a coding CLI or an agent-fsm)?
2. Are the seats always attached?
3. How are the seats cut?
4. Who commits?
5. How is work checked by someone who did not do it?
6. What do you do about a change you did not make?
7. Where do throwaway files and a seat's own notes go?
8. May a seat start subordinates, or improve itself when idle?
9. Where do the definitions live, and are they copies?

# Orgs and kits

- A seat has a card in `wf/org/` and reads it. A helper attached for one job is made from a kit (`aos/kits.md`) and does not read the cards.
- The kit's site layer (who to report to, language, local rules) comes from the org: `basic/extras/site.txt`.
- To use it, make a kit of your own: copy the kit folder and put the filled `site.txt` into its `system.txt` just before the role part (`aos/kits.md#/Layers of a kit's system text`).

# What an org does not do

- Its write scopes are an agreement: agents on one account can write anywhere, and nothing checks who committed whose file. A card should say which layer holds each limit: the card's text, a check inside a tool, or the operating system.
- It does not create folders outside `wf/org/`.
- It is not a workflow: how a kind of work is done stays in `wf/workflows/`.
